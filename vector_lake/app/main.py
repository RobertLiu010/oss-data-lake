"""FastAPI application entry point for Vector Lake."""

from __future__ import annotations

import asyncio
import contextvars
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, Response

from app.config import load_settings
from app.routers import entities, events, reconcile, search, vfs, workspaces
from app.services.chunking import ChunkingService
from app.services.embedding import EmbeddingService
from app.services.entity_service import EntityService
from app.services.event_bus import EventBus
from app.services.index import IndexService
from app.services.pipeline import PipelineService
from app.services.reconciler import ReconcilerService
from app.services.vfs import VfsService
from app.services.watch import WatchService
from app.storage.local import LocalStorage

# ---------------------------------------------------------------------------
# Structured JSON logging with request_id support
# ---------------------------------------------------------------------------


class JsonFormatter(logging.Formatter):
    """Emit logs as JSON with request_id from thread-local context."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }
        # Inject request_id from thread-local if available
        req_id = getattr(record, "request_id", None) or _current_request_id.get()
        if req_id:
            log_entry["request_id"] = req_id
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = str(record.exc_info[1])
        return json.dumps(log_entry, ensure_ascii=False)


_current_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")

handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
# silence noisy libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prometheus metrics (lazy init)
# ---------------------------------------------------------------------------

_metrics_registry: object | None = None
_metrics_generated = None

REQUEST_COUNT = None
REQUEST_LATENCY = None


def _init_metrics():
    """Initialize Prometheus metrics (only if prometheus_client is available)."""
    global _metrics_registry, _metrics_generated, REQUEST_COUNT, REQUEST_LATENCY

    try:
        from prometheus_client import REGISTRY, Counter, Histogram, generate_latest
    except ImportError:
        logger.info("prometheus_client not installed, /metrics endpoint disabled")
        return

    _metrics_registry = REGISTRY
    _metrics_generated = generate_latest

    REQUEST_COUNT = Counter(
        "http_requests_total",
        "Total HTTP requests",
        ["method", "endpoint", "status"],
    )
    REQUEST_LATENCY = Histogram(
        "http_request_duration_seconds",
        "HTTP request latency",
        ["method", "endpoint"],
    )


_init_metrics()


# ---------------------------------------------------------------------------
# Rate limiter (lazy init)
# ---------------------------------------------------------------------------

_limiter: object | None = None


def _init_rate_limiter():
    """Initialize slowapi rate limiter (only if slowapi is available)."""
    global _limiter

    try:
        from slowapi import Limiter
        from slowapi.util import get_remote_address
        _limiter = Limiter(key_func=get_remote_address)
    except ImportError:
        logger.info("slowapi not installed, rate limiting disabled")


_init_rate_limiter()


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    settings = load_settings()

    storage = LocalStorage(settings)
    chunking = ChunkingService(settings)
    embedding = EmbeddingService(settings)
    index = IndexService(settings)
    event_bus = EventBus()
    pipeline = PipelineService(storage, chunking, embedding, index, settings, event_bus=event_bus)
    entity_service = EntityService(storage, pipeline, settings)
    vfs_service = VfsService(storage, settings)
    reconciler_service = ReconcilerService(storage, entity_service, pipeline, settings)
    watch_service = WatchService(storage, entity_service, settings)

    app.state.settings = settings
    app.state.entity_service = entity_service
    app.state.embedding_service = embedding
    app.state.index_service = index
    app.state.vfs_service = vfs_service
    app.state.reconciler_service = reconciler_service
    app.state.watch_service = watch_service
    app.state.event_bus = event_bus

    # Periodic cleanup of stale event bus subscribers
    async def _event_bus_cleanup_loop():
        while True:
            await asyncio.sleep(600)  # every 10 minutes
            event_bus.cleanup_stale_subscribers()

    cleanup_task = asyncio.create_task(_event_bus_cleanup_loop())

    yield

    # Shutdown: cancel cleanup task
    cleanup_task.cancel()
    # Shutdown: close embedding client
    await embedding.close()
    # Shutdown: stop all watch tasks
    await watch_service.shutdown()


# ---------------------------------------------------------------------------
# App creation
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Vector Lake",
    version="0.1.0",
    description="OSS-based knowledge lake with Entity → Representation → Chunk → Index model",
    lifespan=lifespan,
)

# Middleware: X-Request-ID (must run first — before CORS/GZip/Prometheus)
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Extract/generate X-Request-ID, inject into logging, record Prometheus metrics."""
    req_id = request.headers.get("X-Request-ID", "") or str(uuid.uuid4())
    _current_request_id.set(req_id)

    start = time.monotonic()
    response = await call_next(request)
    elapsed = time.monotonic() - start

    response.headers["X-Request-ID"] = req_id

    # Prometheus metrics
    if REQUEST_COUNT is not None:
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code,
        ).inc()
    if REQUEST_LATENCY is not None:
        REQUEST_LATENCY.labels(
            method=request.method,
            endpoint=request.url.path,
        ).observe(elapsed)

    # Access log (structured JSON)
    logger.info(
        "request",
        extra={
            "request_id": req_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round(elapsed * 1000, 3),
            "client": request.client.host if request.client else "-",
        },
    )
    return response


# Middleware (best practice: gzip large responses, allow CORS for web clients)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS — origins from config (env: CORS_ORIGINS)
_settings_for_cors = load_settings()
_cors_origins = _settings_for_cors.cors.origins.split(",") if _settings_for_cors.cors.origins != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware
if _limiter is not None:
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    app.state.limiter = _limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Global exception handler (best practice: never leak internals)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(
        "Unhandled exception: %s %s",
        request.method,
        request.url.path,
        extra={"request_id": _current_request_id.get()},
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": type(exc).__name__,
            "request_id": _current_request_id.get(),
        },
    )


# ---------------------------------------------------------------------------
# Prometheus metrics endpoint (middleware merged with request_id_middleware above)
# ---------------------------------------------------------------------------

@app.get("/metrics", tags=["system"], include_in_schema=False)
async def metrics():
    """Prometheus metrics endpoint."""
    if _metrics_generated is None:
        return Response(content="prometheus_client not installed", status_code=501)
    content = _metrics_generated()
    return Response(content=content, media_type="text/plain; version=0.0.4; charset=utf-8")


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(entities.router)
app.include_router(search.router)
app.include_router(vfs.router)
app.include_router(reconcile.router)
app.include_router(events.router)
app.include_router(workspaces.router)


# ---------------------------------------------------------------------------
# System endpoints
# ---------------------------------------------------------------------------

@app.get("/health", tags=["system"])
async def health():
    """Liveness probe — returns 200 as long as the process is alive."""
    return {"status": "ok"}


@app.get("/readiness", tags=["system"])
async def readiness():
    """Readiness probe — returns 200 only when all critical services are ready."""
    settings = getattr(app.state, "settings", None)
    if settings is None:
        return JSONResponse(status_code=503, content={"ready": False, "reason": "not_initialized"})
    checks = {
        "storage": app.state.entity_service is not None,
        "pipeline": True,
        "vfs": app.state.vfs_service is not None,
    }
    if not all(checks.values()):
        return JSONResponse(status_code=503, content={"ready": False, "checks": checks})
    return {"ready": True, "checks": checks}
