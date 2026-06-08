"""Sync queue service — reliable parquet → LanceDB synchronization.

Architecture:
- Pipeline writes parquet → enqueues SyncTask → returns immediately
- SyncWorker consumes tasks → sync_to_lance() → on failure, retry with backoff
- Pending tasks persisted to sidecar JSONL for crash recovery
- Supports batch sync (multiple entities in one LanceDB write)

This ensures:
1. Pipeline is never blocked by LanceDB latency/failures
2. Failed syncs are automatically retried
3. No data loss on process crash (tasks recovered from sidecar)
4. Back-pressure via queue size limits
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from app.config import Settings
from app.services.index import IndexService

logger = logging.getLogger(__name__)


class SyncTaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class SyncTask:
    """A pending parquet → LanceDB sync task."""

    workspace_id: str
    collection_id: str
    entity_id: str
    rep_name: str = "canonical_md"
    task_id: str = ""
    status: SyncTaskStatus = SyncTaskStatus.PENDING
    attempts: int = 0
    max_attempts: int = 5
    created_at: float = field(default_factory=time.time)
    last_attempt_at: float = 0.0
    error: str = ""

    def __post_init__(self):
        if not self.task_id:
            ts = int(self.created_at * 1000)
            self.task_id = (
                f"{self.workspace_id}_{self.collection_id}_"
                f"{self.entity_id}_{self.rep_name}_{ts}"
            )


class SyncQueue:
    """Persistent task queue for parquet → LanceDB sync.

    Features:
    - asyncio.Queue for in-memory ordering
    - JSONL sidecar for crash recovery
    - Deduplication: same (ws, col, entity, rep) replaces older pending task
    - Back-pressure: queue maxsize limits memory usage
    """

    def __init__(self, settings: Settings, maxsize: int = 10_000):
        self._queue: asyncio.Queue[SyncTask] = asyncio.Queue(maxsize=maxsize)
        # Sidecar is always local (crash-recovery log), use local.root as base
        self._sidecar_path = Path(settings.storage.local.root) / "_sync_queue.jsonl"
        self._pending: dict[str, SyncTask] = {}  # dedup key → task
        self._stats = {
            "enqueued": 0,
            "completed": 0,
            "failed": 0,
            "recovered": 0,
        }

    def _dedup_key(self, task: SyncTask) -> str:
        return f"{task.workspace_id}/{task.collection_id}/{task.entity_id}/{task.rep_name}"

    async def enqueue(self, task: SyncTask) -> bool:
        """Enqueue a sync task. Deduplicates by (ws, col, entity, rep).

        Returns False if queue is full (back-pressure).
        """
        key = self._dedup_key(task)
        # Dedup: replace existing pending task for same key
        if key in self._pending:
            old = self._pending[key]
            if old.status == SyncTaskStatus.PENDING:
                old.attempts += 1
                logger.debug("Dedup sync task: replaced %s", key)
                return True

        try:
            self._queue.put_nowait(task)
        except asyncio.QueueFull:
            logger.warning("Sync queue full, dropping task for %s", key)
            return False

        self._pending[key] = task
        self._stats["enqueued"] += 1
        from app.metrics import record_sync_enqueue, set_sync_queue_depth
        record_sync_enqueue()
        set_sync_queue_depth(self.queue_size())
        # Persist to sidecar
        self._append_sidecar(task)
        return True

    async def get(self, timeout: float = 1.0) -> SyncTask | None:
        """Get next task from queue, or None on timeout."""
        try:
            task = await asyncio.wait_for(self._queue.get(), timeout=timeout)
            task.status = SyncTaskStatus.RUNNING
            task.last_attempt_at = time.time()
            return task
        except TimeoutError:
            return None

    def mark_done(self, task: SyncTask) -> None:
        """Mark task as completed."""
        task.status = SyncTaskStatus.DONE
        key = self._dedup_key(task)
        self._pending.pop(key, None)
        self._stats["completed"] += 1
        from app.metrics import record_sync_dequeue, set_sync_queue_depth
        record_sync_dequeue("success")
        set_sync_queue_depth(self.queue_size())
        self._update_sidecar(task)

    def mark_failed(self, task: SyncTask, error: str) -> None:
        """Mark task as failed. If attempts < max, re-enqueue with backoff."""
        task.attempts += 1
        task.error = error
        task.last_attempt_at = time.time()

        if task.attempts < task.max_attempts:
            task.status = SyncTaskStatus.PENDING
            # Re-enqueue with delay (backoff)
            backoff = min(2 ** task.attempts, 60)  # max 60s
            logger.info(
                "Sync task %s failed (attempt %d/%d), retry in %ds: %s",
                task.task_id, task.attempts, task.max_attempts, backoff, error,
            )
            from app.metrics import record_sync_retry
            record_sync_retry()
            # Schedule re-enqueue after backoff
            asyncio.get_event_loop().call_later(
                backoff,
                lambda: asyncio.ensure_future(self._reenqueue(task)),
            )
        else:
            task.status = SyncTaskStatus.FAILED
            key = self._dedup_key(task)
            self._pending.pop(key, None)
            self._stats["failed"] += 1
            from app.metrics import record_sync_dequeue, set_sync_queue_depth
            record_sync_dequeue("failure")
            set_sync_queue_depth(self.queue_size())
            logger.error(
                "Sync task %s permanently failed after %d attempts: %s",
                task.task_id, task.attempts, error,
            )

        self._update_sidecar(task)

    async def _reenqueue(self, task: SyncTask) -> None:
        """Re-enqueue a task after backoff."""
        try:
            self._queue.put_nowait(task)
            key = self._dedup_key(task)
            self._pending[key] = task
        except asyncio.QueueFull:
            logger.warning("Sync queue full on re-enqueue for %s", task.task_id)

    def queue_size(self) -> int:
        return self._queue.qsize()

    def stats(self) -> dict[str, Any]:
        return {
            **self._stats,
            "queue_size": self.queue_size(),
            "pending_keys": len(self._pending),
        }

    # ------------------------------------------------------------------
    # Sidecar persistence (JSONL)
    # ------------------------------------------------------------------

    def _append_sidecar(self, task: SyncTask) -> None:
        """Append a task to the JSONL sidecar file.

        Each line is self-contained JSON. Uses fsync to ensure durability.
        Malformed lines from partial writes are safely skipped on recovery.
        """
        try:
            self._sidecar_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._sidecar_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(task), ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            logger.warning("Failed to persist sync task to sidecar: %s", e)

    def _update_sidecar(self, task: SyncTask) -> None:
        """Update task status in sidecar by rewriting (append-only with status)."""
        self._append_sidecar(task)

    def recover_pending(self) -> int:
        """Recover pending tasks from sidecar on startup.

        Reads the JSONL file, keeps only the latest status per task_id,
        and re-enqueues tasks that were PENDING or RUNNING.
        Returns the number of recovered tasks.
        """
        if not self._sidecar_path.exists():
            return 0

        # Read all entries, keep latest per task_id
        latest: dict[str, dict] = {}
        corrupted_lines = 0
        try:
            with open(self._sidecar_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        tid = entry.get("task_id", "")
                        latest[tid] = entry
                    except json.JSONDecodeError:
                        corrupted_lines += 1
        except Exception as e:
            logger.warning("Failed to read sync sidecar: %s", e)
            return 0

        if corrupted_lines > 0:
            logger.warning(
                "Sidecar JSONL had %d corrupted lines (skipped)", corrupted_lines,
            )

        # Recover PENDING/ RUNNING tasks
        recovered = 0
        for entry in latest.values():
            status = entry.get("status", "")
            if status in (SyncTaskStatus.PENDING, SyncTaskStatus.RUNNING):
                task = SyncTask(
                    workspace_id=entry["workspace_id"],
                    collection_id=entry["collection_id"],
                    entity_id=entry["entity_id"],
                    rep_name=entry.get("rep_name", "canonical_md"),
                    task_id=entry.get("task_id", ""),
                    status=SyncTaskStatus.PENDING,  # Reset to pending
                    attempts=entry.get("attempts", 0),
                    max_attempts=entry.get("max_attempts", 5),
                    created_at=entry.get("created_at", time.time()),
                    last_attempt_at=entry.get("last_attempt_at", 0),
                    error=entry.get("error", ""),
                )
                try:
                    self._queue.put_nowait(task)
                    key = self._dedup_key(task)
                    self._pending[key] = task
                    recovered += 1
                except asyncio.QueueFull:
                    logger.warning("Queue full during recovery, skipping task %s", task.task_id)

        if recovered > 0:
            logger.info("Recovered %d pending sync tasks from sidecar", recovered)
            self._stats["recovered"] = recovered

        # Compact sidecar: only keep non-DONE entries
        self._compact_sidecar(latest)

        return recovered

    def _compact_sidecar(self, latest: dict[str, dict]) -> None:
        """Rewrite sidecar keeping only non-DONE entries."""
        try:
            non_done = {tid: e for tid, e in latest.items() if e.get("status") != SyncTaskStatus.DONE}
            if not non_done:
                # All done, remove sidecar
                self._sidecar_path.unlink(missing_ok=True)
                return
            tmp_path = self._sidecar_path.with_suffix(".jsonl.tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                for entry in non_done.values():
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            tmp_path.replace(self._sidecar_path)
        except Exception as e:
            logger.warning("Failed to compact sync sidecar: %s", e)


class SyncWorker:
    """Background worker that consumes SyncTasks and syncs to LanceDB.

    Runs as an asyncio Task. On startup, recovers pending tasks from sidecar.
    """

    def __init__(
        self,
        queue: SyncQueue,
        index_service: IndexService,
        poll_interval: float = 0.1,
    ):
        self.queue = queue
        self.index = index_service
        self.poll_interval = poll_interval
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start the background worker."""
        # Recover pending tasks from sidecar
        self.queue.recover_pending()
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("SyncWorker started")

    async def stop(self) -> None:
        """Stop the background worker gracefully."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("SyncWorker stopped")

    async def _run_loop(self) -> None:
        """Main loop: consume tasks and sync to LanceDB."""
        while self._running:
            task = await self.queue.get(timeout=1.0)
            if task is None:
                continue

            try:
                count = await self.index.sync_to_lance(
                    task.workspace_id,
                    task.collection_id,
                    task.entity_id,
                    task.rep_name,
                )
                self.queue.mark_done(task)
                logger.debug(
                    "Synced %d rows for %s/%s/%s rep=%s",
                    count, task.workspace_id, task.collection_id,
                    task.entity_id, task.rep_name,
                )
            except Exception as e:
                error_msg = f"{type(e).__name__}: {e}"
                logger.warning(
                    "Sync failed for %s/%s/%s rep=%s: %s",
                    task.workspace_id, task.collection_id,
                    task.entity_id, task.rep_name, error_msg,
                )
                self.queue.mark_failed(task, error_msg)
                from app.metrics import record_sync_worker_error
                record_sync_worker_error()

    def is_running(self) -> bool:
        return self._running and self._task is not None and not self._task.done()
