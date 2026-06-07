"""Tests for FastAPI endpoints via test client."""

from __future__ import annotations

import io

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# System endpoints
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
    """GET /readiness returns 200 after startup."""

    @pytest.mark.asyncio
    async def test_readiness(self, client: AsyncClient):
        resp = await client.get("/readiness")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ready"] is True


class TestMetricsEndpoint:
    """GET /metrics returns prometheus metrics."""

    @pytest.mark.asyncio
    async def test_metrics(self, client: AsyncClient):
        resp = await client.get("/metrics")
        # May be 200 or 501 depending on prometheus_client availability
        assert resp.status_code in (200, 501)
        if resp.status_code == 200:
            assert "http_requests_total" in resp.text or "HELP" in resp.text


# ---------------------------------------------------------------------------
# Workspace endpoints
# ---------------------------------------------------------------------------


class TestWorkspaceEndpoints:
    """POST /api/v1/workspaces creates workspace."""

    @pytest.mark.asyncio
    async def test_create_workspace(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/workspaces",
            json={"workspace_id": "test_ws", "name": "Test Workspace"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["workspace_id"] == "test_ws"

    @pytest.mark.asyncio
    async def test_list_workspaces(self, client: AsyncClient):
        # Create one first
        await client.post(
            "/api/v1/workspaces",
            json={"workspace_id": "ws_list", "name": "List WS"},
        )
        resp = await client.get("/api/v1/workspaces")
        assert resp.status_code == 200
        data = resp.json()
        assert any(ws["workspace_id"] == "ws_list" for ws in data)

    @pytest.mark.asyncio
    async def test_create_duplicate_workspace_409(self, client: AsyncClient):
        await client.post(
            "/api/v1/workspaces",
            json={"workspace_id": "dup_ws", "name": "Dup"},
        )
        resp = await client.post(
            "/api/v1/workspaces",
            json={"workspace_id": "dup_ws", "name": "Dup Again"},
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Path traversal protection
# ---------------------------------------------------------------------------


class TestPathTraversal:
    """Path traversal in ws/col returns 400."""

    @pytest.mark.asyncio
    async def test_traversal_in_workspace_id(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/workspaces",
            json={"workspace_id": "../etc", "name": "Evil"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_traversal_in_ws_path_param(self, client: AsyncClient):
        resp = await client.get("/api/v1/workspaces/../etc")
        # FastAPI path matching won't match this pattern, but validate_id
        # should reject it if it does get through
        # The important thing is it doesn't return 200 with data
        assert resp.status_code in (400, 404, 422)

    @pytest.mark.asyncio
    async def test_traversal_in_entity_ws_col(self, client: AsyncClient):
        resp = await client.get("/api/v1/workspaces/../etc/collections/test/entities")
        assert resp.status_code in (400, 404, 422)


# ---------------------------------------------------------------------------
# Entity CRUD flow
# ---------------------------------------------------------------------------


class TestEntityCRUD:
    """Entity create, list, get, patch, delete flow."""

    @pytest.mark.asyncio
    async def test_full_crud_flow(self, client: AsyncClient):
        ws = "crud_ws"
        col = "crud_col"

        # 1. Create workspace + collection
        await client.post(
            "/api/v1/workspaces",
            json={"workspace_id": ws, "name": "CRUD WS"},
        )
        await client.post(
            f"/api/v1/workspaces/{ws}/collections",
            json={"collection_id": col, "name": "CRUD Col"},
        )

        # 2. Create entity via file upload
        file_content = "# Test Document\nThis is a test markdown file."
        files = {"file": ("test.md", io.BytesIO(file_content.encode()), "text/markdown")}
        resp = await client.post(
            f"/api/v1/workspaces/{ws}/collections/{col}/entities",
            files=files,
        )
        assert resp.status_code == 201
        entity = resp.json()
        entity_id = entity["entity_id"]
        assert entity["name"] == "test.md"
        assert entity["status"] == "enabled"

        # 3. List entities
        resp = await client.get(
            f"/api/v1/workspaces/{ws}/collections/{col}/entities"
        )
        assert resp.status_code == 200
        entities = resp.json()
        assert len(entities) >= 1
        assert any(e["entity_id"] == entity_id for e in entities)

        # 4. Get entity
        resp = await client.get(
            f"/api/v1/workspaces/{ws}/collections/{col}/entities/{entity_id}"
        )
        assert resp.status_code == 200
        assert resp.json()["entity_id"] == entity_id

        # 5. Patch entity (change status)
        resp = await client.patch(
            f"/api/v1/workspaces/{ws}/collections/{col}/entities/{entity_id}",
            json={"status": "hidden"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "hidden"

        # 6. Patch entity (change labels)
        resp = await client.patch(
            f"/api/v1/workspaces/{ws}/collections/{col}/entities/{entity_id}",
            json={"labels": ["important", "test"]},
        )
        assert resp.status_code == 200
        assert resp.json()["labels"] == ["important", "test"]

        # 7. Soft delete
        resp = await client.delete(
            f"/api/v1/workspaces/{ws}/collections/{col}/entities/{entity_id}"
        )
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        # 8. Get after soft delete — should still exist with status=deleted
        resp = await client.get(
            f"/api/v1/workspaces/{ws}/collections/{col}/entities/{entity_id}"
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    @pytest.mark.asyncio
    async def test_get_nonexistent_entity_404(self, client: AsyncClient):
        ws = "crud_ws2"
        col = "crud_col2"
        await client.post(
            "/api/v1/workspaces",
            json={"workspace_id": ws, "name": "WS2"},
        )
        await client.post(
            f"/api/v1/workspaces/{ws}/collections",
            json={"collection_id": col, "name": "Col2"},
        )
        resp = await client.get(
            f"/api/v1/workspaces/{ws}/collections/{col}/entities/nonexistent"
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_entity_404(self, client: AsyncClient):
        ws = "crud_ws3"
        col = "crud_col3"
        await client.post(
            "/api/v1/workspaces",
            json={"workspace_id": ws, "name": "WS3"},
        )
        await client.post(
            f"/api/v1/workspaces/{ws}/collections",
            json={"collection_id": col, "name": "Col3"},
        )
        resp = await client.delete(
            f"/api/v1/workspaces/{ws}/collections/{col}/entities/nonexistent"
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_entity_non_md_rejected(self, client: AsyncClient):
        ws = "crud_ws4"
        col = "crud_col4"
        await client.post(
            "/api/v1/workspaces",
            json={"workspace_id": ws, "name": "WS4"},
        )
        await client.post(
            f"/api/v1/workspaces/{ws}/collections",
            json={"collection_id": col, "name": "Col4"},
        )
        files = {"file": ("test.pdf", io.BytesIO(b"not a pdf"), "application/pdf")}
        resp = await client.post(
            f"/api/v1/workspaces/{ws}/collections/{col}/entities",
            files=files,
        )
        assert resp.status_code == 400
