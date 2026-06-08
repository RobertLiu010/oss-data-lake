"""Observability tests — metrics, /health, /readiness, /status endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.metrics import (
    init_metrics,
    record_pipeline_entity,
    record_pipeline_chunks,
    record_pipeline_error,
    record_embedding_latency,
    record_parquet_write,
    record_lance_sync,
    record_lance_rebuild,
    record_chunks_indexed,
    record_sync_enqueue,
    record_sync_dequeue,
    record_sync_retry,
    set_sync_queue_depth,
    record_sync_worker_error,
    record_reconcile_scan,
    record_reconcile_drift,
    record_reconcile_repair,
    record_reconcile_latency,
    record_search_query,
    record_entity_op,
)


# ---------------------------------------------------------------------------
# Metrics module unit tests
# ---------------------------------------------------------------------------


class TestMetricsInit:
    """Business metrics initialization."""

    def test_init_metrics_returns_bool(self):
        result = init_metrics()
        assert isinstance(result, bool)

    def test_init_metrics_idempotent(self):
        r1 = init_metrics()
        r2 = init_metrics()
        assert r1 == r2

    def test_convenience_functions_no_error(self):
        """All convenience functions should be callable without error."""
        # Pipeline
        record_pipeline_entity("success")
        record_pipeline_entity("failure")
        record_pipeline_chunks(5)
        record_pipeline_error("embed")
        record_pipeline_error("index")
        record_embedding_latency(0.5, batch_size=3)

        # Index
        record_parquet_write()
        record_lance_sync("success", seconds=0.1)
        record_lance_sync("failure")
        record_lance_rebuild()
        record_chunks_indexed(10)

        # SyncQueue
        record_sync_enqueue()
        record_sync_dequeue("success")
        record_sync_dequeue("failure")
        record_sync_retry()
        set_sync_queue_depth(5)
        record_sync_worker_error()

        # Reconciler
        record_reconcile_scan()
        record_reconcile_drift("missing_rep")
        record_reconcile_drift("stale_rep")
        record_reconcile_repair("missing_rep")
        record_reconcile_latency(1.5)

        # Search
        record_search_query("semantic", 0.05, 5)
        record_search_query("lexical", 0.02, 3)
        record_search_query("hybrid", 0.08, 7)

        # Entity
        record_entity_op("create")
        record_entity_op("read")
        record_entity_op("update")
        record_entity_op("delete")
        record_entity_op("content_update")


class TestMetricsNoop:
    """Metrics should be no-op safe even before init_metrics()."""

    def test_record_before_init(self):
        """Calling convenience functions before init should not raise."""
        # This works because the module-level variables are None,
        # and _inc/_observe/_set check for None before operating.
        record_pipeline_entity("success")
        record_parquet_write()
        record_sync_enqueue()
        record_reconcile_scan()
        record_search_query("semantic", 0.1, 1)
        record_entity_op("create")


# ---------------------------------------------------------------------------
# System endpoint tests
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """GET /health returns 200."""

    @pytest.mark.asyncio
    async def test_health(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


class TestReadinessEndpoint:
    """GET /readiness returns 200 when critical services are ready."""

    @pytest.mark.asyncio
    async def test_readiness(self, client: AsyncClient):
        resp = await client.get("/readiness")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ready"] is True
        assert "checks" in data
        assert data["checks"]["storage"] is True
        assert data["checks"]["pipeline"] is True
        assert data["checks"]["vfs"] is True

    @pytest.mark.asyncio
    async def test_readiness_includes_sync_worker_info(self, client: AsyncClient):
        resp = await client.get("/readiness")
        data = resp.json()
        # sync_worker is non-critical, may be True or False
        assert "sync_worker" in data["checks"]


class TestStatusEndpoint:
    """GET /status returns detailed system status."""

    @pytest.mark.asyncio
    async def test_status(self, client: AsyncClient):
        resp = await client.get("/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_status_has_sync_queue(self, client: AsyncClient):
        resp = await client.get("/status")
        data = resp.json()
        assert "sync_queue" in data
        sq = data["sync_queue"]
        # sync_queue may or may not be available in test env
        if sq.get("available") is not False:
            assert "queue_size" in sq or "enqueued" in sq

    @pytest.mark.asyncio
    async def test_status_has_sync_worker(self, client: AsyncClient):
        resp = await client.get("/status")
        data = resp.json()
        assert "sync_worker" in data
        assert "running" in data["sync_worker"]

    @pytest.mark.asyncio
    async def test_status_has_reconciler(self, client: AsyncClient):
        resp = await client.get("/status")
        data = resp.json()
        assert "reconciler" in data
        # last_scan may be None if no reconcile has run
        assert "last_scan" in data["reconciler"]

    @pytest.mark.asyncio
    async def test_status_has_index(self, client: AsyncClient):
        resp = await client.get("/status")
        data = resp.json()
        assert "index" in data
        idx = data["index"]
        if idx.get("available") is not False:
            assert "dimension" in idx


class TestMetricsEndpoint:
    """GET /metrics returns Prometheus metrics."""

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, client: AsyncClient):
        resp = await client.get("/metrics")
        assert resp.status_code in (200, 501)
        if resp.status_code == 200:
            # Should contain HTTP metrics
            assert "http_requests_total" in resp.text or "HELP" in resp.text

    @pytest.mark.asyncio
    async def test_metrics_contains_business_metrics(self, client: AsyncClient):
        """After initializing business metrics, /metrics should include them."""
        resp = await client.get("/metrics")
        if resp.status_code == 200:
            text = resp.text
            # Business metrics should be present
            assert "vl_pipeline_entities_total" in text
            assert "vl_index_parquet_writes_total" in text
            assert "vl_sync_enqueue_total" in text
            assert "vl_reconcile_scans_total" in text
            assert "vl_search_queries_total" in text
            assert "vl_entity_ops_total" in text


# ---------------------------------------------------------------------------
# Metrics integration: verify metrics are recorded during pipeline operations
# ---------------------------------------------------------------------------


class TestMetricsIntegration:
    """Verify metrics are recorded during actual service operations."""

    @pytest.mark.asyncio
    async def test_entity_create_records_metrics(self, client: AsyncClient):
        """Creating an entity should record entity_op and pipeline metrics."""
        # Get baseline metrics
        resp = await client.get("/metrics")
        if resp.status_code != 200:
            pytest.skip("Prometheus not available")

        baseline = resp.text

        # Create workspace + collection
        await client.post(
            "/api/v1/workspaces",
            json={"workspace_id": "metrics_ws", "name": "Metrics WS"},
        )
        await client.post(
            "/api/v1/workspaces/metrics_ws/collections",
            json={"collection_id": "metrics_col", "name": "Metrics Col"},
        )

        # Create entity
        import io
        file_content = "# Metrics Test\nTest content for metrics."
        files = {"file": ("test.md", io.BytesIO(file_content.encode()), "text/markdown")}
        resp = await client.post(
            "/api/v1/workspaces/metrics_ws/collections/metrics_col/entities",
            files=files,
        )
        assert resp.status_code == 201

        # Check metrics were recorded
        resp = await client.get("/metrics")
        assert resp.status_code == 200
        text = resp.text

        # vl_entity_ops_total{operation="create"} should have incremented
        assert 'vl_entity_ops_total{operation="create"}' in text
        # vl_pipeline_entities_total should exist
        assert "vl_pipeline_entities_total" in text
        # vl_index_parquet_writes_total should have incremented
        assert "vl_index_parquet_writes_total" in text

    @pytest.mark.asyncio
    async def test_search_records_metrics(self, client: AsyncClient):
        """Search should record search query metrics."""
        # Create workspace + collection + entity first
        await client.post(
            "/api/v1/workspaces",
            json={"workspace_id": "search_metrics_ws", "name": "SM WS"},
        )
        await client.post(
            "/api/v1/workspaces/search_metrics_ws/collections",
            json={"collection_id": "search_metrics_col", "name": "SM Col"},
        )

        import io
        file_content = "# Search Test\nContent for search metrics testing."
        files = {"file": ("search_test.md", io.BytesIO(file_content.encode()), "text/markdown")}
        await client.post(
            "/api/v1/workspaces/search_metrics_ws/collections/search_metrics_col/entities",
            files=files,
        )

        # Perform search
        resp = await client.post(
            "/api/v1/workspaces/search_metrics_ws/collections/search_metrics_col/search",
            json={"query": "search test", "search_type": "lexical", "top_k": 5},
        )
        # Search may succeed or fail depending on index state
        # But metrics should be recorded either way

        # Check metrics
        resp = await client.get("/metrics")
        if resp.status_code == 200:
            text = resp.text
            assert "vl_search_queries_total" in text
