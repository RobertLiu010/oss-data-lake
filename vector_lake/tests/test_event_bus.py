"""Tests for app.services.event_bus — EventBus pub/sub."""

from __future__ import annotations

import asyncio
import time

import pytest

from app.services.event_bus import EventBus, Event, EventType


class TestEventBusSubscribe:
    """subscribe returns a queue."""

    def test_subscribe_returns_queue(self):
        bus = EventBus()
        q = bus.subscribe(EventType.ENTITY_CREATED)
        assert isinstance(q, asyncio.Queue)

    def test_subscribe_same_type_multiple(self):
        bus = EventBus()
        q1 = bus.subscribe(EventType.ENTITY_CREATED)
        q2 = bus.subscribe(EventType.ENTITY_CREATED)
        assert q1 is not q2


class TestEventBusPublish:
    """publish delivers to subscribers."""

    @pytest.mark.asyncio
    async def test_publish_delivers_event(self):
        bus = EventBus()
        q = bus.subscribe(EventType.ENTITY_CREATED)
        event = Event(
            event_type=EventType.ENTITY_CREATED,
            workspace_id="ws1",
            collection_id="col1",
            entity_id="ent1",
        )
        await bus.publish(event)
        received = q.get_nowait()
        assert received.entity_id == "ent1"
        assert received.event_type == EventType.ENTITY_CREATED

    @pytest.mark.asyncio
    async def test_publish_to_multiple_subscribers(self):
        bus = EventBus()
        q1 = bus.subscribe(EventType.ENTITY_CREATED)
        q2 = bus.subscribe(EventType.ENTITY_CREATED)
        event = Event(
            event_type=EventType.ENTITY_CREATED,
            workspace_id="ws1",
            collection_id="col1",
            entity_id="ent1",
        )
        await bus.publish(event)
        assert q1.get_nowait().entity_id == "ent1"
        assert q2.get_nowait().entity_id == "ent1"

    @pytest.mark.asyncio
    async def test_publish_wrong_type_not_delivered(self):
        bus = EventBus()
        q = bus.subscribe(EventType.ENTITY_CREATED)
        event = Event(
            event_type=EventType.ENTITY_DELETED,
            workspace_id="ws1",
            collection_id="col1",
            entity_id="ent1",
        )
        await bus.publish(event)
        assert q.empty()


class TestEventBusHistory:
    """get_history returns recent events."""

    @pytest.mark.asyncio
    async def test_history_records_events(self):
        bus = EventBus()
        event = Event(
            event_type=EventType.ENTITY_CREATED,
            workspace_id="ws1",
            collection_id="col1",
            entity_id="ent1",
        )
        await bus.publish(event)
        history = bus.get_history()
        assert len(history) == 1
        assert history[0].entity_id == "ent1"

    @pytest.mark.asyncio
    async def test_history_filtered_by_type(self):
        bus = EventBus()
        e1 = Event(EventType.ENTITY_CREATED, "ws1", "col1", "ent1")
        e2 = Event(EventType.ENTITY_DELETED, "ws1", "col1", "ent2")
        await bus.publish(e1)
        await bus.publish(e2)
        history = bus.get_history(event_type=EventType.ENTITY_CREATED)
        assert len(history) == 1
        assert history[0].entity_id == "ent1"

    @pytest.mark.asyncio
    async def test_history_respects_limit(self):
        bus = EventBus()
        for i in range(10):
            await bus.publish(
                Event(EventType.ENTITY_CREATED, "ws1", "col1", f"ent{i}")
            )
        history = bus.get_history(limit=3)
        assert len(history) == 3

    @pytest.mark.asyncio
    async def test_history_max_size(self):
        bus = EventBus()
        bus._max_history = 5
        for i in range(10):
            await bus.publish(
                Event(EventType.ENTITY_CREATED, "ws1", "col1", f"ent{i}")
            )
        history = bus.get_history(limit=100)
        assert len(history) == 5


class TestEventBusCleanup:
    """cleanup_stale_subscribers removes old queues."""

    def test_cleanup_removes_stale(self):
        bus = EventBus()
        q = bus.subscribe(EventType.ENTITY_CREATED)
        # Simulate an old queue by manipulating metadata
        bus._queue_meta[id(q)]["created_at"] = time.time() - 7200
        bus._queue_meta[id(q)]["last_read"] = time.time() - 7200
        removed = bus.cleanup_stale_subscribers(max_age_seconds=3600)
        assert removed == 1
        # Queue should be gone from subscribers
        assert q not in bus._subscribers.get(EventType.ENTITY_CREATED, [])

    def test_cleanup_keeps_active(self):
        bus = EventBus()
        q = bus.subscribe(EventType.ENTITY_CREATED)
        removed = bus.cleanup_stale_subscribers(max_age_seconds=3600)
        assert removed == 0
        assert q in bus._subscribers.get(EventType.ENTITY_CREATED, [])


class TestEventBusQueueFull:
    """QueueFull doesn't crash the bus."""

    @pytest.mark.asyncio
    async def test_queue_full_does_not_crash(self):
        bus = EventBus()
        # Create a queue with very small maxsize
        q = asyncio.Queue(maxsize=1)
        bus._subscribers[EventType.ENTITY_CREATED] = [q]
        bus._queue_meta[id(q)] = {"created_at": time.time(), "last_read": time.time()}

        # Fill the queue
        await bus.publish(
            Event(EventType.ENTITY_CREATED, "ws1", "col1", "ent1")
        )
        # This should trigger QueueFull but not crash
        await bus.publish(
            Event(EventType.ENTITY_CREATED, "ws1", "col1", "ent2")
        )
        # Queue still has just 1 item
        assert q.qsize() == 1
