"""Two-phase consistency checker and reconciler (§5.9, §5.12)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from vector_lake.models.enums import RepStatus
from vector_lake.queue.streams import StreamProducer
from vector_lake.vfs.storage import ObjectStorage
from vector_lake.vfs.vfs import VFS

logger = logging.getLogger(__name__)


@dataclass
class ConsistencyResult:
    """Result of a consistency check."""

    entity_id: str
    phase: str  # phase0 / phase1 / phase2
    status: str  # consistent / inconsistent / error
    details: str = ""
    action: str = ""  # none / rebuild_rep / rebuild_index / fix_tag


class ConsistencyChecker:
    """Two-phase consistency checker (§5.9).

    Phase 0: ETag quick scan (HeadObject, zero-download)
    Phase 1: Rep ↔ Raw consistency (content consistency)
    Phase 2: Index ↔ Rep consistency (index consistency)
    """

    def __init__(self, storage: ObjectStorage, vfs: VFS, producer: StreamProducer):
        self._storage = storage
        self._vfs = vfs
        self._producer = producer

    async def check_phase0(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        known_etag: str,
    ) -> ConsistencyResult:
        """Phase 0: ETag-based quick scan (§5.12.3).

        Compares known ETag with current ETag via HeadObject (zero-download).
        O(file_size) → O(1).
        """
        source_key = f"vector-lake/{workspace_id}/{collection_id}/{entity_id}/source/original"
        try:
            current_etag = await self._storage.compute_etag(source_key)
            if current_etag == known_etag:
                return ConsistencyResult(
                    entity_id=entity_id,
                    phase="phase0",
                    status="consistent",
                    action="none",
                )
            else:
                return ConsistencyResult(
                    entity_id=entity_id,
                    phase="phase0",
                    status="inconsistent",
                    details=f"ETag mismatch: known={known_etag}, current={current_etag}",
                    action="phase1",
                )
        except FileNotFoundError:
            return ConsistencyResult(
                entity_id=entity_id,
                phase="phase0",
                status="error",
                details=f"Source object not found: {source_key}",
                action="none",
            )

    async def check_phase1(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
    ) -> ConsistencyResult:
        """Phase 1: Rep ↔ Raw consistency (§5.9).

        Checks if all Reps are consistent with the current Raw content.
        Detects stale Reps by comparing content_hash.
        """
        try:
            reps = await self._vfs.list_representations(workspace_id, collection_id, entity_id)
            stale_reps = [r for r in reps if r.status == RepStatus.STALE]
            failed_reps = [r for r in reps if r.status == RepStatus.FAILED]

            if stale_reps or failed_reps:
                details = []
                if stale_reps:
                    details.append(f"stale: {[r.rep_type for r in stale_reps]}")
                if failed_reps:
                    details.append(f"failed: {[r.rep_type for r in failed_reps]}")
                return ConsistencyResult(
                    entity_id=entity_id,
                    phase="phase1",
                    status="inconsistent",
                    details="; ".join(details),
                    action="rebuild_rep",
                )

            return ConsistencyResult(
                entity_id=entity_id,
                phase="phase1",
                status="consistent",
                action="none",
            )
        except Exception as e:
            return ConsistencyResult(
                entity_id=entity_id,
                phase="phase1",
                status="error",
                details=str(e),
                action="none",
            )

    async def check_phase2(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        index_built_from_hash: str,
        build_from_hash_set: str,
    ) -> ConsistencyResult:
        """Phase 2: Index ↔ Rep consistency (§5.9).

        Compares index_built_from_hash with current build_from_hash_set.
        """
        if index_built_from_hash == build_from_hash_set:
            return ConsistencyResult(
                entity_id=entity_id,
                phase="phase2",
                status="consistent",
                action="none",
            )
        return ConsistencyResult(
            entity_id=entity_id,
            phase="phase2",
            status="inconsistent",
            details=(
                f"Index hash mismatch: "
                f"built_from={index_built_from_hash}, current={build_from_hash_set}"
            ),
            action="rebuild_index",
        )


class Reconciler:
    """Periodic reconciler (§5.9, §21).

    Runs Phase 0/1/2 on a schedule to detect and fix state drift.
    v0.1: 15 min cycle, batch of 100 entities.
    """

    def __init__(
        self,
        checker: ConsistencyChecker,
        producer: StreamProducer,
        batch_size: int = 100,
    ):
        self._checker = checker
        self._producer = producer
        self._batch_size = batch_size
        self._running = False

    async def run_once(self, workspace_id: str, collection_id: str) -> list[ConsistencyResult]:
        """Run one reconciliation cycle."""
        results = []
        # TODO: list all entities in workspace/collection
        # For each entity, run Phase 0 → Phase 1 → Phase 2
        logger.info(f"Reconciler running for {workspace_id}/{collection_id}")
        return results

    async def run_cycle(self, workspace_id: str, collection_id: str) -> None:
        """Run a full reconciliation cycle (Phase 0 + 1 + 2)."""
        self._running = True
        try:
            results = await self.run_once(workspace_id, collection_id)
            inconsistent = [r for r in results if r.status == "inconsistent"]
            for result in inconsistent:
                if result.action == "rebuild_rep":
                    logger.warning(f"Triggering Rep rebuild for entity={result.entity_id}")
                    # TODO: dispatch RepPipeline rebuild
                elif result.action == "rebuild_index":
                    logger.warning(f"Triggering Index rebuild for entity={result.entity_id}")
                    # TODO: dispatch IndexPipeline rebuild
        finally:
            self._running = False

    async def fix_tag_missing(self, key: str, tags: dict[str, str]) -> None:
        """Fix TAG_MISSING state by re-writing tags (§5.12.2)."""
        try:
            await self._storage.put_tags(key, tags)
            logger.info(f"Fixed TAG_MISSING for {key}")
        except Exception as e:
            logger.error(f"Failed to fix TAG_MISSING for {key}: {e}")
