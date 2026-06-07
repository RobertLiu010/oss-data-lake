"""Simple async event bus for pipeline notifications."""
from __future__ import annotations
import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

class EventType(str, Enum):
    ENTITY_CREATED = "entity_created"
    REP_COMPLETED = "rep_completed"
    REP_FAILED = "rep_failed"
    INDEX_COMPLETED = "index_completed"
    INDEX_FAILED = "index_failed"
    ENTITY_DELETED = "entity_deleted"
    ENTITY_STATUS_CHANGED = "entity_status_changed"

@dataclass
class Event:
    event_type: EventType
    workspace_id: str
    collection_id: str
    entity_id: str
    payload: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

class EventBus:
    """Simple pub/sub event bus using asyncio.Queue."""

    def __init__(self):
        self._subscribers: dict[EventType, list[asyncio.Queue]] = {}
        # Track per-queue metadata: {id(queue): {"created_at": float, "last_read": float}}
        self._queue_meta: dict[int, dict[str, float]] = {}
        self._history: list[Event] = []
        self._max_history = 1000
        self._lock = threading.Lock()

    def subscribe(self, event_type: EventType) -> asyncio.Queue:
        """Subscribe to an event type, returns a Queue that receives Events."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subscribers[event_type].append(q)
        now = time.time()
        self._queue_meta[id(q)] = {"created_at": now, "last_read": now}
        return q

    async def publish(self, event: Event) -> None:
        """Publish an event to all subscribers."""
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        subscribers = self._subscribers.get(event.event_type, [])
        for q in subscribers:
            try:
                q.put_nowait(event)
                meta = self._queue_meta.get(id(q))
                if meta is not None:
                    meta["last_read"] = time.time()
            except asyncio.QueueFull:
                logger.warning("Event queue full, dropping %s", event.event_type)

        logger.info("Event: %s entity=%s ws=%s col=%s",
                    event.event_type.value, event.entity_id,
                    event.workspace_id, event.collection_id)

    def get_history(self, event_type: EventType = None, limit: int = 50) -> list[Event]:
        """Get recent events, optionally filtered by type."""
        events = self._history
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events[-limit:]

    def cleanup_stale_subscribers(self, max_age_seconds: float = 3600.0) -> int:
        """Remove closed/abandoned queues older than max_age_seconds with no reads.

        Returns the number of removed queues.
        """
        now = time.time()
        removed = 0
        for event_type in list(self._subscribers.keys()):
            queues = self._subscribers[event_type]
            to_keep: list[asyncio.Queue] = []
            for q in queues:
                meta = self._queue_meta.get(id(q))
                if meta is None:
                    # No metadata tracked, keep it
                    to_keep.append(q)
                    continue
                age = now - meta["created_at"]
                idle = now - meta["last_read"]
                # Remove if older than 1 hour AND no reads in the last hour
                if age > max_age_seconds and idle > max_age_seconds:
                    self._queue_meta.pop(id(q), None)
                    removed += 1
                else:
                    to_keep.append(q)
            self._subscribers[event_type] = to_keep
        return removed
