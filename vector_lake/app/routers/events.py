"""Event bus endpoints: history query and SSE stream."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.services.event_bus import EventType

router = APIRouter(
    prefix="/api/v1/events",
    tags=["events"],
)


def _get_event_bus(request: Request):
    return request.app.state.event_bus


@router.get("")
async def get_events(
    event_type: str = Query(None, description="Filter by event type"),
    limit: int = Query(50, ge=1, le=1000, description="Max events to return"),
    request: Request = None,
):
    """Get recent events, optionally filtered by type."""
    event_bus = _get_event_bus(request)
    et = EventType(event_type) if event_type else None
    events = event_bus.get_history(event_type=et, limit=limit)
    return [asdict(e) for e in events]


@router.get("/stream")
async def stream_events(request: Request):
    """SSE stream of all pipeline events."""

    async def event_generator():
        event_bus = _get_event_bus(request)
        # Subscribe to all event types
        queues = {}
        for et in EventType:
            queues[et] = event_bus.subscribe(et)

        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break
                # Poll all queues with a short timeout
                for et, q in queues.items():
                    try:
                        event = q.get_nowait()
                        data = json.dumps(asdict(event), default=str)
                        yield f"data: {data}\n\n"
                    except asyncio.QueueEmpty:
                        pass
                await asyncio.sleep(0.5)
        finally:
            # Clean up queues
            for et, q in queues.items():
                subscribers = event_bus._subscribers.get(et, [])
                if q in subscribers:
                    subscribers.remove(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
