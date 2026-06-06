"""Pipeline orchestrators (§6.8, §6.9): RepPipeline and IndexPipeline execution."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from vector_lake.models.enums import TriggerType
from vector_lake.pipeline.protocols import (
    RepStepContext,
    RepStepOutput,
)
from vector_lake.pipeline.registry import IndexStepRegistry, RepStepRegistry
from vector_lake.queue.streams import (
    GROUP_INDEX_WORKERS,
    GROUP_REP_WORKERS,
    STREAM_INDEX_PIPELINE,
    STREAM_REP_PIPELINE,
    IndexPipelineMessage,
    RepPipelineMessage,
    StreamConsumer,
    StreamProducer,
)

logger = logging.getLogger(__name__)


# Built-in RepPipeline definitions (§6.6.3)
BUILTIN_REP_PIPELINES: dict[str, list[str]] = {
    "pipeline_a": ["parse"],  # raw → canonical_md + plain_text
    "pipeline_b": ["render_page"],  # raw → page_image
    "pipeline_c": ["render_page", "ocr"],  # raw → page_image → ocr_text
    "pipeline_d": ["parse", "compile_mind_map"],  # raw → canonical_md → mind_map (v0.2)
    "pipeline_e": ["parse", "compile_summary"],  # raw → canonical_md → summary (v0.2)
    "pipeline_f": ["transcribe"],  # raw → transcript + audio_segment
    "pipeline_g": ["table_parse"],  # raw → table_parquet + table_md + table_json
}

# Built-in IndexPipeline definitions (§6.7.4)
BUILTIN_INDEX_PIPELINES: dict[str, list[str]] = {
    "index_pipeline_text": ["chunk_and_embed_text", "build_vector_index", "build_fts_index"],
    "index_pipeline_image": ["chunk_and_embed_image", "build_vector_index"],
    "index_pipeline_audio": ["chunk_and_embed_audio", "build_vector_index"],
    "index_pipeline_graph": ["build_graph_index"],
    "index_pipeline_table": ["chunk_and_embed_table", "build_vector_index"],
}

# Entity type → default RepPipeline mapping (§6.3)
ENTITY_PIPELINE_MAP: dict[str, list[str]] = {
    "document": ["pipeline_a", "pipeline_b", "pipeline_c"],
    "image": ["pipeline_b"],
    "audio": ["pipeline_f"],
    "video": ["pipeline_f"],
    "table": ["pipeline_g"],
    "mixed": ["pipeline_a", "pipeline_b", "pipeline_c"],
}


@dataclass
class PipelineRunResult:
    """Result of a pipeline run."""

    pipeline_id: str
    entity_id: str
    status: str  # success / partial_success / failed
    step_results: dict[str, list[RepStepOutput]] = field(default_factory=dict)
    failed_steps: list[str] = field(default_factory=list)
    skipped_steps: list[str] = field(default_factory=list)


class RepPipelineOrchestrator:
    """Orchestrates RepPipeline execution (§6.8).

    Key rules:
    - Entity内RepPipeline间并行
    - RepPipeline内step串行
    - Lock granularity: RepPipeline-level (not Entity-level)
    """

    def __init__(self, producer: StreamProducer):
        self._producer = producer

    def get_pipelines_for_entity(self, entity_type: str) -> list[str]:
        """Get applicable RepPipeline IDs for an entity type."""
        return ENTITY_PIPELINE_MAP.get(entity_type, ["pipeline_a"])

    def get_pipeline_steps(self, pipeline_id: str) -> list[str]:
        """Get ordered step IDs for a pipeline."""
        return BUILTIN_REP_PIPELINES.get(pipeline_id, [])

    async def dispatch_entity(
        self,
        entity_id: str,
        entity_type: str,
        workspace_id: str,
        collection_id: str,
        content_hash: str,
        entity_version: int,
        trigger: str = TriggerType.MANUAL,
    ) -> list[str]:
        """Dispatch all applicable RepPipelines for an entity.

        Entity is a TRIGGER — this method only XADDs to Redis Streams.
        Workers execute the actual steps.
        Returns list of entry IDs.
        """
        pipeline_ids = self.get_pipelines_for_entity(entity_type)
        entry_ids = []

        for pipeline_id in pipeline_ids:
            steps = self.get_pipeline_steps(pipeline_id)
            for step_id in steps:
                step = RepStepRegistry.get(step_id)
                msg = RepPipelineMessage(
                    entity_id=entity_id,
                    step_id=step_id,
                    workspace_id=workspace_id,
                    collection_id=collection_id,
                    pipeline_id=pipeline_id,
                    trigger=trigger,
                    input_reps={
                        "required": step.required_input_reps,
                        "optional": step.optional_input_reps,
                    },
                )
                entry_id = await self._producer.submit_rep_task(msg)
                entry_ids.append(entry_id)
                logger.info(
                    f"Dispatched step={step_id} pipeline={pipeline_id} "
                    f"entity={entity_id} entry={entry_id}"
                )

        return entry_ids

    async def check_rep_all_ready(
        self,
        entity_id: str,
        workspace_id: str,
        collection_id: str,
        available_reps: list[str],
    ) -> bool:
        """Check if all required Reps are ready for an entity (§5.9.4 rep_all_ready)."""
        # Check if all expected rep_types for this entity are in available_reps
        # A rep is ready if its status is 'ready'
        # Simplified: check if any required rep is missing
        # Full implementation would check VFS for actual status
        return len(available_reps) > 0

    async def dispatch_index_pipeline(
        self,
        entity_id: str,
        workspace_id: str,
        collection_id: str,
        available_reps: list[str],
    ) -> list[str]:
        """Dispatch IndexPipeline after rep_all_ready event (§6.7.5)."""
        applicable_steps = IndexStepRegistry.steps_for_reps(available_reps)
        entry_ids = []

        for step in applicable_steps:
            msg = IndexPipelineMessage(
                entity_id=entity_id,
                workspace_id=workspace_id,
                collection_id=collection_id,
                available_reps=available_reps,
            )
            entry_id = await self._producer.submit_index_task(msg)
            entry_ids.append(entry_id)
            logger.info(f"Dispatched index step={step.step_id} entity={entity_id} entry={entry_id}")

        return entry_ids


class RepStepWorker:
    """Worker that consumes RepPipeline tasks from Redis Streams (§6.9.3)."""

    def __init__(
        self,
        redis_client: Any,
        worker_id: str,
        producer: StreamProducer,
        orchestrator: RepPipelineOrchestrator,
    ):
        self._consumer = StreamConsumer(
            redis=redis_client,
            group=GROUP_REP_WORKERS,
            consumer=f"rep-worker-{worker_id}",
            stream=STREAM_REP_PIPELINE,
        )
        self._producer = producer
        self._orchestrator = orchestrator
        self._running = False

    async def start(self) -> None:
        """Start the worker loop."""
        await self._consumer.ensure_group()
        self._running = True
        logger.info("RepStepWorker started")

        while self._running:
            try:
                # Read new messages
                messages = await self._consumer.read_new()
                for msg_id, fields in messages:
                    await self._process_message(msg_id, fields)

                # Claim pending messages (idle > 5 min)
                claimed = await self._consumer.claim_pending(min_idle_ms=300000)
                for msg_id, fields in claimed:
                    await self._process_message(msg_id, fields)

            except Exception as e:
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(1)

    async def stop(self) -> None:
        """Stop the worker."""
        self._running = False

    async def _process_message(self, msg_id: str, fields: dict[str, str]) -> None:
        """Process a single RepPipeline message."""
        msg = RepPipelineMessage.from_dict(fields)
        logger.info(f"Processing step={msg.step_id} entity={msg.entity_id}")

        try:
            step = RepStepRegistry.get(msg.step_id)
            ctx = RepStepContext(
                entity_id=msg.entity_id,
                entity_type="",  # TODO: resolve from VFS
                workspace_id=msg.workspace_id,
                collection_id=msg.collection_id,
                content_hash="",
                entity_version=1,
            )
            step.execute(ctx)
            await self._consumer.ack(msg_id)
            logger.info(f"Step {msg.step_id} completed for entity={msg.entity_id}")

        except KeyError:
            logger.error(f"Unknown step: {msg.step_id}")
            await self._consumer.ack(msg_id)

        except Exception as e:
            logger.error(f"Step {msg.step_id} failed: {e}")
            if msg.retry_count >= msg.max_retries:
                await self._producer.submit_dead_letter(msg, str(e))
                await self._consumer.ack(msg_id)
            # else: message stays pending, will be reclaimed


class IndexStepWorker:
    """Worker that consumes IndexPipeline tasks from Redis Streams."""

    def __init__(
        self,
        redis_client: Any,
        worker_id: str,
    ):
        self._consumer = StreamConsumer(
            redis=redis_client,
            group=GROUP_INDEX_WORKERS,
            consumer=f"index-worker-{worker_id}",
            stream=STREAM_INDEX_PIPELINE,
        )
        self._running = False

    async def start(self) -> None:
        """Start the worker loop."""
        await self._consumer.ensure_group()
        self._running = True
        logger.info("IndexStepWorker started")

        while self._running:
            try:
                messages = await self._consumer.read_new()
                for msg_id, fields in messages:
                    await self._process_message(msg_id, fields)

                claimed = await self._consumer.claim_pending(min_idle_ms=300000)
                for msg_id, fields in claimed:
                    await self._process_message(msg_id, fields)

            except Exception as e:
                logger.error(f"Index worker error: {e}")
                await asyncio.sleep(1)

    async def stop(self) -> None:
        self._running = False

    async def _process_message(self, msg_id: str, fields: dict[str, str]) -> None:
        """Process a single IndexPipeline message."""
        msg = IndexPipelineMessage(
            entity_id=fields.get("entity_id", ""),
            workspace_id=fields.get("workspace_id", ""),
            collection_id=fields.get("collection_id", ""),
        )
        logger.info(f"Processing index for entity={msg.entity_id}")

        try:
            # TODO: resolve applicable IndexSteps and execute
            await self._consumer.ack(msg_id)
        except Exception as e:
            logger.error(f"Index step failed for entity={msg.entity_id}: {e}")
