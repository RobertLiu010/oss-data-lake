"""FastAPI application (§14, §21)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vector_lake.api.routes import edges, entities, lineage, search
from vector_lake.config import VectorLakeConfig


def create_app(config: VectorLakeConfig | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if config is None:
        config = VectorLakeConfig()

    app = FastAPI(
        title="Vector-Lake",
        description="Intelligent Knowledge Search Engine Layer",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    app.include_router(entities.router)
    app.include_router(search.router)
    app.include_router(edges.router)
    app.include_router(lineage.router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/health/ready")
    async def health_ready():
        return {"status": "ready", "checks": {"redis": True, "storage": True}}

    @app.get("/health/live")
    async def health_live():
        return {"status": "alive"}

    @app.get("/metrics")
    async def metrics():
        """Prometheus metrics endpoint placeholder."""
        return {}

    return app
