"""Watch Mode service — monitor local directories and auto-create entities.

v0.1 implementation:
- Watch a local directory for new/modified/deleted .md files
- Auto-create Entity via EntityService when new file appears
- Track file hashes to detect modifications
- Background task using asyncio

Based on PRD §5.15 (Watch Mode 自动构建模式).
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from app.config import Settings
from app.services.entity_service import EntityService
from app.storage.local import LocalStorage

logger = logging.getLogger(__name__)


class WatchStatus(str, Enum):
    INITIALIZING = "initializing"
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"
    STOPPED = "stopped"


class FileEventType(str, Enum):
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"


@dataclass
class FileEvent:
    """A file change event detected by the watcher."""
    event_type: FileEventType
    file_path: Path
    file_name: str
    detected_at: datetime = field(default_factory=datetime.now)
    entity_id: Optional[str] = None
    processed: bool = False
    error: Optional[str] = None


@dataclass
class WatchStrategy:
    """Configuration for a single watch."""
    watch_id: str
    workspace_id: str
    collection_id: str
    watch_dir: str                    # local directory to watch
    allowed_extensions: list[str] = field(default_factory=lambda: [".md"])
    entity_id_strategy: str = "filename"  # filename | filepath | hash
    on_conflict: str = "update"       # update | skip | error
    recursive: bool = True
    max_file_size_mb: int = 500
    backend: str = "polling"          # polling | inotify
    scan_interval: int = 10           # seconds between scans (polling mode)
    status: WatchStatus = WatchStatus.INITIALIZING
    created_at: datetime = field(default_factory=datetime.now)
    last_scan_at: Optional[datetime] = None
    total_events: int = 0
    total_processed: int = 0
    total_errors: int = 0


@dataclass
class DeadLetterEntry:
    """A failed event that couldn't be processed."""
    entry_id: str
    workspace_id: str
    collection_id: str
    file_path: str
    error: str
    created_at: datetime = field(default_factory=datetime.now)
    replayed: bool = False


class WatchService:
    """Watch Mode service — monitors local directories for file changes.

    v0.1 uses periodic polling (not inotify) for simplicity.
    """

    def __init__(
        self,
        storage: LocalStorage,
        entity_service: EntityService,
        settings: Settings,
    ):
        self.storage = storage
        self.entity_service = entity_service
        self.settings = settings
        self.root = Path(settings.storage.local.root)

        # Thread safety lock for shared state
        self._lock = threading.Lock()

        # Active watch strategies
        self._watches: dict[str, WatchStrategy] = {}
        # File hash cache: {watch_id: {file_path: sha256_hash}}
        self._file_hashes: dict[str, dict[str, str]] = {}
        # Dead letter queue
        self._dead_letters: list[DeadLetterEntry] = []
        # Background tasks
        self._tasks: dict[str, asyncio.Task] = {}

    @property
    def watches(self) -> dict[str, WatchStrategy]:
        return self._watches

    @property
    def dead_letters(self) -> list[DeadLetterEntry]:
        return self._dead_letters

    def create_watch(self, strategy: WatchStrategy) -> WatchStrategy:
        """Register a new watch strategy."""
        with self._lock:
            if strategy.watch_id in self._watches:
                raise ValueError(f"Watch {strategy.watch_id} already exists")

        # Verify watch directory exists
        watch_path = Path(strategy.watch_dir)
        if not watch_path.exists():
            watch_path.mkdir(parents=True, exist_ok=True)

        with self._lock:
            self._watches[strategy.watch_id] = strategy
            self._file_hashes[strategy.watch_id] = {}
        logger.info("Created watch strategy %s for dir=%s", strategy.watch_id, strategy.watch_dir)
        return strategy

    def start_watch(self, watch_id: str) -> None:
        """Start background watching for a watch strategy."""
        if watch_id not in self._watches:
            raise ValueError(f"Watch {watch_id} not found")

        strategy = self._watches[watch_id]
        strategy.status = WatchStatus.ACTIVE

        # Cancel existing task if any
        if watch_id in self._tasks:
            self._tasks[watch_id].cancel()

        # Choose backend
        if strategy.backend == "inotify":
            try:
                import inotify_simple  # noqa: F401
                task = asyncio.create_task(self._inotify_loop(watch_id))
                self._tasks[watch_id] = task
                logger.info("Started watch %s with inotify backend", watch_id)
                return
            except ImportError:
                logger.warning(
                    "inotify_simple not available, falling back to polling for watch %s",
                    watch_id,
                )

        # Default: polling backend
        task = asyncio.create_task(self._poll_loop(watch_id))
        self._tasks[watch_id] = task
        logger.info("Started watch %s with polling backend", watch_id)

    def pause_watch(self, watch_id: str) -> None:
        """Pause a watch strategy."""
        if watch_id not in self._watches:
            raise ValueError(f"Watch {watch_id} not found")

        strategy = self._watches[watch_id]
        strategy.status = WatchStatus.PAUSED

        if watch_id in self._tasks:
            self._tasks[watch_id].cancel()
            del self._tasks[watch_id]

        logger.info("Paused watch %s", watch_id)

    def stop_watch(self, watch_id: str) -> None:
        """Stop and remove a watch strategy."""
        if watch_id not in self._watches:
            raise ValueError(f"Watch {watch_id} not found")

        if watch_id in self._tasks:
            self._tasks[watch_id].cancel()
            del self._tasks[watch_id]

        with self._lock:
            self._watches[watch_id].status = WatchStatus.STOPPED
            del self._watches[watch_id]
            self._file_hashes.pop(watch_id, None)
        logger.info("Stopped watch %s", watch_id)

    async def _poll_loop(self, watch_id: str) -> None:
        """Background polling loop for a watch strategy."""
        strategy = self._watches.get(watch_id)
        if not strategy:
            return

        # Initial scan — record existing files (don't create entities for pre-existing)
        self._scan_files(watch_id, initial=True)

        while strategy.status == WatchStatus.ACTIVE:
            try:
                await asyncio.sleep(strategy.scan_interval)
                events = self._scan_files(watch_id)
                for event in events:
                    await self._process_event(strategy, event)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Watch %s poll error: %s", watch_id, e)
                strategy.status = WatchStatus.ERROR

    async def _inotify_loop(self, watch_id: str) -> None:
        """Background inotify-based watching loop for a watch strategy."""
        import inotify_simple

        strategy = self._watches.get(watch_id)
        if not strategy:
            return

        watch_dir = Path(strategy.watch_dir)
        if not watch_dir.exists():
            logger.error("Watch %s: directory %s does not exist", watch_id, strategy.watch_dir)
            strategy.status = WatchStatus.ERROR
            return

        # Initial scan — record existing files
        self._scan_files(watch_id, initial=True)

        inotify = inotify_simple.INotify()
        mask = (
            inotify_simple.flags.CREATE
            | inotify_simple.flags.MODIFY
            | inotify_simple.flags.DELETE
            | inotify_simple.flags.MOVED_FROM
            | inotify_simple.flags.MOVED_TO
        )
        wd = inotify.add_watch(str(watch_dir), mask)

        try:
            while strategy.status == WatchStatus.ACTIVE:
                try:
                    # Read events with a timeout to allow periodic cancellation checks
                    events = inotify.read(timeout=1000)  # 1 second timeout
                    for raw_event in events:
                        if raw_event.wd != wd:
                            continue

                        filename = raw_event.name
                        if not filename:
                            continue

                        file_path = watch_dir / filename

                        # Check extension
                        if strategy.allowed_extensions:
                            if file_path.suffix.lower() not in strategy.allowed_extensions:
                                continue

                        # Check file size (skip for deleted files)
                        if file_path.exists() and file_path.is_file():
                            size_mb = file_path.stat().st_size / (1024 * 1024)
                            if size_mb > strategy.max_file_size_mb:
                                continue

                        # Determine event type
                        flags = inotify_simple.flags.from_mask(raw_event.mask)
                        if inotify_simple.flags.CREATE in flags or inotify_simple.flags.MOVED_TO in flags:
                            if file_path.exists() and file_path.is_file():
                                event_type = FileEventType.CREATED
                            else:
                                continue
                        elif inotify_simple.flags.MODIFY in flags:
                            if file_path.exists() and file_path.is_file():
                                event_type = FileEventType.MODIFIED
                            else:
                                continue
                        elif inotify_simple.flags.DELETE in flags or inotify_simple.flags.MOVED_FROM in flags:
                            event_type = FileEventType.DELETED
                        else:
                            continue

                        event = FileEvent(
                            event_type=event_type,
                            file_path=file_path,
                            file_name=filename,
                        )
                        await self._process_event(strategy, event)

                    # Yield control to the event loop
                    await asyncio.sleep(0)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error("Watch %s inotify error: %s", watch_id, e)
                    strategy.status = WatchStatus.ERROR
                    break
        finally:
            inotify.rm_watch(wd)
            inotify.close()
            logger.info("Watch %s: inotify watcher cleaned up", watch_id)

    def _scan_files(
        self, watch_id: str, initial: bool = False
    ) -> list[FileEvent]:
        """Scan the watch directory and detect changes.

        If initial=True, just record hashes without generating events.
        """
        strategy = self._watches.get(watch_id)
        if not strategy:
            return []

        watch_dir = Path(strategy.watch_dir)
        if not watch_dir.exists():
            return []

        prev_hashes = self._file_hashes.get(watch_id, {})
        curr_hashes: dict[str, str] = {}
        events: list[FileEvent] = []

        # Collect current files
        pattern = "**/*" if strategy.recursive else "*"
        for file_path in watch_dir.glob(pattern):
            if not file_path.is_file():
                continue

            # Check extension
            if strategy.allowed_extensions:
                if file_path.suffix.lower() not in strategy.allowed_extensions:
                    continue

            # Check file size
            size_mb = file_path.stat().st_size / (1024 * 1024)
            if size_mb > strategy.max_file_size_mb:
                continue

            str_path = str(file_path)
            file_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()

            curr_hashes[str_path] = file_hash

            if not initial:
                prev_hash = prev_hashes.get(str_path)
                if prev_hash is None:
                    # New file
                    events.append(FileEvent(
                        event_type=FileEventType.CREATED,
                        file_path=file_path,
                        file_name=file_path.name,
                    ))
                elif prev_hash != file_hash:
                    # Modified file
                    events.append(FileEvent(
                        event_type=FileEventType.MODIFIED,
                        file_path=file_path,
                        file_name=file_path.name,
                    ))

        # Detect deleted files
        if not initial:
            for str_path in prev_hashes:
                if str_path not in curr_hashes:
                    file_path = Path(str_path)
                    events.append(FileEvent(
                        event_type=FileEventType.DELETED,
                        file_path=file_path,
                        file_name=file_path.name,
                    ))

        # Update hash cache
        with self._lock:
            self._file_hashes[watch_id] = curr_hashes
        strategy.last_scan_at = datetime.now()

        return events

    async def _process_event(
        self, strategy: WatchStrategy, event: FileEvent
    ) -> None:
        """Process a file event — create/update/delete entity."""
        strategy.total_events += 1

        try:
            if event.event_type == FileEventType.CREATED:
                await self._handle_created(strategy, event)
            elif event.event_type == FileEventType.MODIFIED:
                await self._handle_modified(strategy, event)
            elif event.event_type == FileEventType.DELETED:
                await self._handle_deleted(strategy, event)

            event.processed = True
            strategy.total_processed += 1

        except Exception as e:
            event.error = str(e)
            strategy.total_errors += 1
            with self._lock:
                self._dead_letters.append(DeadLetterEntry(
                    entry_id=f"dl_{len(self._dead_letters):06d}",
                    workspace_id=strategy.workspace_id,
                    collection_id=strategy.collection_id,
                    file_path=str(event.file_path),
                    error=str(e),
                ))
            logger.warning(
                "Watch %s: failed to process %s event for %s: %s",
                strategy.watch_id, event.event_type.value,
                event.file_name, e,
            )

    async def _handle_created(
        self, strategy: WatchStrategy, event: FileEvent
    ) -> None:
        """Handle new file — create Entity."""
        content = event.file_path.read_bytes()

        entity = await self.entity_service.create_from_bytes(
            strategy.workspace_id,
            strategy.collection_id,
            event.file_name,
            content,
        )
        event.entity_id = entity.entity_id
        logger.info(
            "Watch %s: auto-created entity %s from %s",
            strategy.watch_id, entity.entity_id, event.file_name,
        )

    async def _handle_modified(
        self, strategy: WatchStrategy, event: FileEvent
    ) -> None:
        """Handle modified file — re-run pipeline (v0.1: update = re-create)."""
        if strategy.on_conflict == "skip":
            logger.info(
                "Watch %s: skipping modified file %s (on_conflict=skip)",
                strategy.watch_id, event.file_name,
            )
            return

        # v0.1: re-create entity (which re-runs pipeline)
        content = event.file_path.read_bytes()

        entity = await self.entity_service.create_from_bytes(
            strategy.workspace_id,
            strategy.collection_id,
            event.file_name,
            content,
        )
        event.entity_id = entity.entity_id
        logger.info(
            "Watch %s: auto-updated entity %s from modified %s",
            strategy.watch_id, entity.entity_id, event.file_name,
        )

    async def _handle_deleted(
        self, strategy: WatchStrategy, event: FileEvent
    ) -> None:
        """Handle deleted file — v0.1: log only (no entity deletion)."""
        logger.info(
            "Watch %s: file deleted %s (v0.1: no auto-entity-deletion)",
            strategy.watch_id, event.file_name,
        )

    async def replay_dead_letter(self, entry_id: str) -> Optional[str]:
        """Replay a dead letter entry."""
        with self._lock:
            for i, dl in enumerate(self._dead_letters):
                if dl.entry_id == entry_id:
                    file_path = Path(dl.file_path)
                    if not file_path.exists():
                        return f"File no longer exists: {dl.file_path}"

                    content = file_path.read_bytes()
                    entity = await self.entity_service.create_from_bytes(
                        dl.workspace_id,
                        dl.collection_id,
                        file_path.name,
                        content,
                    )
                    dl.replayed = True
                    self._dead_letters.pop(i)
                    return f"Replayed: entity {entity.entity_id} created"

        return None

    def cleanup_dead_letters(self, max_age_hours: int = 72) -> int:
        """Remove old dead letter entries."""
        now = datetime.now()
        with self._lock:
            to_remove = []
            for i, dl in enumerate(self._dead_letters):
                age = (now - dl.created_at).total_seconds() / 3600
                if age > max_age_hours:
                    to_remove.append(i)

            for i in reversed(to_remove):
                self._dead_letters.pop(i)

        return len(to_remove)

    async def shutdown(self) -> None:
        """Stop all watch tasks."""
        for watch_id in list(self._tasks.keys()):
            self._tasks[watch_id].cancel()
        self._tasks.clear()
        for strategy in self._watches.values():
            strategy.status = WatchStatus.STOPPED
        logger.info("Watch service shut down")
