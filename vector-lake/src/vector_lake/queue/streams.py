"""Redis Streams task queue (§6.9)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

import redis.asyncio as aioredis

from vector_lake.models.enums import TriggerType

# Stream names
STREAM_REP_PIPELINE = "stream:rep_pipeline"
STREAM_INDEX_PIPELINE = "stream:index_pipeline"
STREAM_DEAD_LETTER = "stream:dead_letter"

# Consumer groups
GROUP_REP_WORKERS = "rep_workers"
GROUP_INDEX_WORKERS = "index_workers"


@dataclass
class RepPipelineMessage:
    """Message format for rep_pipeline stream (§6.9.2)."""

    entity_id: str
    step_id: str
    workspace_id: str
    collection_id: str
    pipeline_id: str = "default"
    trigger: str = TriggerType.MANUAL
    input_reps: dict[str, list[str]] = field(default_factory=dict)  # required/optional → paths
    trace_id: str = ""
    retry_count: int = 0
    max_retries: int = 3
    created_at: str = field(
        default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    )

    def to_dict(self) -> dict[str, str]:
        """Convert to flat dict for XADD (Redis Streams values must be strings)."""
        return {
            "entity_id": self.entity_id,
            "step_id": self.step_id,
            "workspace_id": self.workspace_id,
            "collection_id": self.collection_id,
            "pipeline_id": self.pipeline_id,
            "trigger": self.trigger,
            "input_reps": json.dumps(self.input_reps),
            "trace_id": self.trace_id,
            "retry_count": str(self.retry_count),
            "max_retries": str(self.max_retries),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[bytes, bytes] | dict[str, str]) -> RepPipelineMessage:
        """Parse from XREADGROUP response."""
        d: dict[str, str] = {}
        for k, v in data.items():
            key = k.decode() if isinstance(k, bytes) else k
            val = v.decode() if isinstance(v, bytes) else v
            d[key] = val

        input_reps = json.loads(d.get("input_reps", "{}"))
        return cls(
            entity_id=d["entity_id"],
            step_id=d["step_id"],
            workspace_id=d["workspace_id"],
            collection_id=d["collection_id"],
            pipeline_id=d.get("pipeline_id", "default"),
            trigger=d.get("trigger", TriggerType.MANUAL),
            input_reps=input_reps,
            trace_id=d.get("trace_id", ""),
            retry_count=int(d.get("retry_count", "0")),
            max_retries=int(d.get("max_retries", "3")),
            created_at=d.get("created_at", ""),
        )


@dataclass
class IndexPipelineMessage:
    """Message format for index_pipeline stream."""

    entity_id: str
    workspace_id: str
    collection_id: str
    index_pipeline_id: str = ""
    available_reps: list[str] = field(default_factory=list)
    trace_id: str = ""
    created_at: str = field(
        default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    )

    def to_dict(self) -> dict[str, str]:
        return {
            "entity_id": self.entity_id,
            "workspace_id": self.workspace_id,
            "collection_id": self.collection_id,
            "index_pipeline_id": self.index_pipeline_id,
            "available_reps": json.dumps(self.available_reps),
            "trace_id": self.trace_id,
            "created_at": self.created_at,
        }


class StreamProducer:
    """Produce messages to Redis Streams."""

    def __init__(self, redis: aioredis.Redis, maxlen: int = 100000):
        self._redis = redis
        self._maxlen = maxlen

    async def submit_rep_task(self, msg: RepPipelineMessage) -> str:
        """Submit a RepPipeline task. Returns the stream entry ID."""
        entry_id = await self._redis.xadd(
            STREAM_REP_PIPELINE,
            msg.to_dict(),
            maxlen=self._maxlen,
            approximate=True,
        )
        return entry_id

    async def submit_index_task(self, msg: IndexPipelineMessage) -> str:
        """Submit an IndexPipeline task."""
        entry_id = await self._redis.xadd(
            STREAM_INDEX_PIPELINE,
            msg.to_dict(),
            maxlen=self._maxlen,
            approximate=True,
        )
        return entry_id

    async def submit_dead_letter(self, msg: RepPipelineMessage, error: str) -> str:
        """Submit a failed message to dead letter stream."""
        data = msg.to_dict()
        data["error"] = error
        entry_id = await self._redis.xadd(
            STREAM_DEAD_LETTER, data, maxlen=self._maxlen, approximate=True
        )
        return entry_id


class StreamConsumer:
    """Consume messages from Redis Streams consumer groups."""

    def __init__(
        self,
        redis: aioredis.Redis,
        group: str,
        consumer: str,
        stream: str,
        count: int = 10,
        block_ms: int = 5000,
    ):
        self._redis = redis
        self._group = group
        self._consumer = consumer
        self._stream = stream
        self._count = count
        self._block_ms = block_ms

    async def ensure_group(self) -> None:
        """Create consumer group if not exists."""
        try:
            await self._redis.xgroup_create(
                name=self._stream,
                groupname=self._group,
                id="$",
                mkstream=True,
            )
        except aioredis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def read_new(self) -> list[tuple[str, dict[str, str]]]:
        """Read new (unassigned) messages. Returns list of (msg_id, fields)."""
        entries = await self._redis.xreadgroup(
            groupname=self._group,
            consumername=self._consumer,
            streams={self._stream: ">"},
            count=self._count,
            block=self._block_ms,
        )
        results = []
        if entries:
            for _stream_name, messages in entries:
                for msg_id, fields in messages:
                    d = {
                        k.decode() if isinstance(k, bytes) else k: v.decode()
                        if isinstance(v, bytes)
                        else v
                        for k, v in fields.items()
                    }
                    results.append((msg_id, d))
        return results

    async def ack(self, msg_id: str) -> None:
        """Acknowledge a message."""
        await self._redis.xack(self._stream, self._group, msg_id)

    async def claim_pending(self, min_idle_ms: int = 300000) -> list[tuple[str, dict[str, str]]]:
        """Claim messages idle > min_idle_ms (default 5 min)."""
        pending = await self._redis.xpending_range(
            self._stream, self._group, min="-", max="+", count=100, idle=min_idle_ms
        )
        if not pending:
            return []

        msg_ids = [entry["message_id"] for entry in pending]
        claimed = await self._redis.xclaim(
            self._stream, self._group, self._consumer, min_idle_ms, msg_ids
        )
        results = []
        for msg_id, fields in claimed:
            d = {
                k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v
                for k, v in fields.items()
            }
            results.append((msg_id, d))
        return results

    async def stream_length(self) -> int:
        """Get current stream length."""
        info = await self._redis.xinfo_stream(name=self._stream)
        return info.get("length", 0)
