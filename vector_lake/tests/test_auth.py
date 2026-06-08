"""Tests for user isolation (auth + workspace binding).

Covers:
1. AuthService unit tests (authenticate, enforce_workspace, extract_api_key)
2. Auth middleware integration (401 on missing/invalid key, 403 on wrong workspace)
3. Workspace router isolation (list/create filtering)
4. Admin access (can access any workspace)
5. Auth disabled (no authentication required)
6. Public paths bypass auth
7. Backward compat (api_keys format)
"""

from __future__ import annotations

import os

os.environ["EMBEDDING_MOCK"] = "1"

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.auth import AuthService, AuthUser, UserInfo, build_auth_service_from_config, is_public_path
from app.config import Settings
from app.services.chunking import ChunkingService
from app.services.embedding import EmbeddingService
from app.services.entity_service import EntityService
from app.services.event_bus import EventBus
from app.services.index import IndexService
from app.services.pipeline import PipelineService
from app.services.reconciler import ReconcilerService
from app.services.templates import register_builtin_templates
from app.services.vfs import VfsService
from app.services.watch import WatchService
from app.storage.local import LocalStorage

register_builtin_templates()


# ---------------------------------------------------------------------------
# AuthService unit tests
# ---------------------------------------------------------------------------


class TestAuthService:
    """Unit tests for AuthService."""

    def _make_service(self, enabled=True, admin_key="admin_key", users=None):
        return AuthService(
            enabled=enabled,
            admin_api_key=admin_key,
            users=users or [],
        )

    def test_auth_disabled_returns_none(self):
        """When auth is disabled, authenticate returns None."""
        svc = self._make_service(enabled=False)
        from fastapi import Request
        from starlette.testclient import TestClient
        # Use a minimal ASGI scope to create a Request
        scope = {"type": "http", "headers": [], "method": "GET", "path": "/"}
        request = Request(scope)
        result = svc.authenticate(request)
        assert result is None

    def test_auth_enabled_missing_key_raises_401(self):
        """When auth is enabled and no key is provided, raise 401."""
        from fastapi import HTTPException, Request
        svc = self._make_service(enabled=True)
        scope = {"type": "http", "headers": [], "method": "GET", "path": "/"}
        request = Request(scope)
        with pytest.raises(HTTPException) as exc_info:
            svc.authenticate(request)
        assert exc_info.value.status_code == 401

    def test_auth_enabled_invalid_key_raises_401(self):
        """When auth is enabled and an invalid key is provided, raise 401."""
        from fastapi import HTTPException, Request
        svc = self._make_service(enabled=True, users=[
            UserInfo(api_key="valid_key", user_id="u1", workspace_id="ws1"),
        ])
        scope = {
            "type": "http",
            "headers": [(b"authorization", b"Bearer wrong_key")],
            "method": "GET",
            "path": "/",
        }
        request = Request(scope)
        with pytest.raises(HTTPException) as exc_info:
            svc.authenticate(request)
        assert exc_info.value.status_code == 401

    def test_auth_enabled_valid_key_returns_user(self):
        """When auth is enabled and a valid key is provided, return AuthUser."""
        from fastapi import Request
        svc = self._make_service(enabled=True, users=[
            UserInfo(api_key="user1_key", user_id="user1", workspace_id="ws_user1"),
        ])
        scope = {
            "type": "http",
            "headers": [(b"authorization", b"Bearer user1_key")],
            "method": "GET",
            "path": "/",
        }
        request = Request(scope)
        user = svc.authenticate(request)
        assert user is not None
        assert user.user_id == "user1"
        assert user.workspace_id == "ws_user1"
        assert user.is_admin is False

    def test_admin_key_is_admin(self):
        """Admin key creates an admin user with workspace_id='*'."""
        from fastapi import Request
        svc = self._make_service(enabled=True, admin_key="admin_key")
        scope = {
            "type": "http",
            "headers": [(b"authorization", b"Bearer admin_key")],
            "method": "GET",
            "path": "/",
        }
        request = Request(scope)
        user = svc.authenticate(request)
        assert user.is_admin is True
        assert user.workspace_id == "*"

    def test_x_api_key_header(self):
        """API Key can be provided via X-API-Key header."""
        from fastapi import Request
        svc = self._make_service(enabled=True, users=[
            UserInfo(api_key="my_key", user_id="u1", workspace_id="ws1"),
        ])
        scope = {
            "type": "http",
            "headers": [(b"x-api-key", b"my_key")],
            "method": "GET",
            "path": "/",
        }
        request = Request(scope)
        user = svc.authenticate(request)
        assert user is not None
        assert user.user_id == "u1"

    def test_enforce_workspace_same_workspace_ok(self):
        """User accessing their own workspace is allowed."""
        svc = self._make_service(enabled=True)
        user = AuthUser(user_id="u1", workspace_id="ws1", is_admin=False)
        # Should not raise
        svc.enforce_workspace(user, "ws1")

    def test_enforce_workspace_different_workspace_403(self):
        """User accessing another workspace raises 403."""
        from fastapi import HTTPException
        svc = self._make_service(enabled=True)
        user = AuthUser(user_id="u1", workspace_id="ws1", is_admin=False)
        with pytest.raises(HTTPException) as exc_info:
            svc.enforce_workspace(user, "ws2")
        assert exc_info.value.status_code == 403

    def test_enforce_workspace_admin_can_access_any(self):
        """Admin user can access any workspace."""
        svc = self._make_service(enabled=True)
        user = AuthUser(user_id="admin", workspace_id="*", is_admin=True)
        # Should not raise for any workspace
        svc.enforce_workspace(user, "ws_other")

    def test_enforce_workspace_auth_disabled_noop(self):
        """When auth is disabled (user=None), enforce_workspace is a no-op."""
        svc = self._make_service(enabled=True)
        svc.enforce_workspace(None, "any_workspace")

    def test_get_user_workspace(self):
        """get_user_workspace returns the bound workspace for regular users."""
        svc = self._make_service(enabled=True)
        user = AuthUser(user_id="u1", workspace_id="ws1", is_admin=False)
        assert svc.get_user_workspace(user) == "ws1"

    def test_get_user_workspace_admin_returns_none(self):
        """get_user_workspace returns None for admin (no fixed workspace)."""
        svc = self._make_service(enabled=True)
        user = AuthUser(user_id="admin", workspace_id="*", is_admin=True)
        assert svc.get_user_workspace(user) is None

    def test_get_user_workspace_auth_disabled_returns_none(self):
        """get_user_workspace returns None when auth is disabled."""
        svc = self._make_service(enabled=True)
        assert svc.get_user_workspace(None) is None


class TestPublicPaths:
    """Test public path detection."""

    def test_health_is_public(self):
        assert is_public_path("/health") is True

    def test_readiness_is_public(self):
        assert is_public_path("/readiness") is True

    def test_status_is_public(self):
        assert is_public_path("/status") is True

    def test_metrics_is_public(self):
        assert is_public_path("/metrics") is True

    def test_docs_is_public(self):
        assert is_public_path("/docs") is True

    def test_openapi_is_public(self):
        assert is_public_path("/openapi.json") is True

    def test_api_endpoint_is_not_public(self):
        assert is_public_path("/api/v1/workspaces") is False

    def test_entity_endpoint_is_not_public(self):
        assert is_public_path("/api/v1/workspaces/ws1/collections/col1/entities") is False


class TestBuildAuthServiceFromConfig:
    """Test build_auth_service_from_config with various config formats."""

    def test_new_format_users(self):
        """New format with users list."""
        config = {
            "enabled": True,
            "admin_api_key": "admin_key",
            "users": [
                {"api_key": "key1", "user_id": "u1", "workspace_id": "ws1"},
                {"api_key": "key2", "user_id": "u2", "workspace_id": "ws2"},
            ],
        }
        svc = build_auth_service_from_config(config)
        assert svc.enabled is True
        assert len(svc._key_to_user) == 3  # 2 users + 1 admin

    def test_old_format_api_keys(self):
        """Old format with api_keys dict → auto-create workspace."""
        config = {
            "enabled": True,
            "api_keys": {"key1": "alice", "key2": "bob"},
        }
        svc = build_auth_service_from_config(config)
        assert svc.enabled is True
        # 2 auto-created users
        user1 = svc._key_to_user.get("key1")
        assert user1 is not None
        assert user1.user_id == "alice"
        assert user1.workspace_id == "ws_alice"

    def test_mixed_format(self):
        """Both users list and api_keys are merged."""
        config = {
            "enabled": True,
            "users": [
                {"api_key": "key1", "user_id": "u1", "workspace_id": "ws1"},
            ],
            "api_keys": {"key2": "u2"},
        }
        svc = build_auth_service_from_config(config)
        assert len(svc._key_to_user) == 2  # 1 from users + 1 from api_keys


# ---------------------------------------------------------------------------
# Integration tests: auth middleware + workspace isolation
# ---------------------------------------------------------------------------


def _auth_settings(tmp_data_dir: Path, tmp_lance_dir: Path) -> Settings:
    """Settings with auth enabled and two users + admin."""
    return Settings(
        storage={"backend": "local", "local": {"root": str(tmp_data_dir)}},
        lance={"data_dir": str(tmp_lance_dir)},
        embedding={"base_url": "http://127.0.0.1:8006", "model": "embedding-v5"},
        vfs={"cache_ttl": 0.0},
        auth={
            "enabled": True,
            "admin_api_key": "admin_secret",
            "users": [
                {"api_key": "user1_key", "user_id": "user1", "workspace_id": "ws_user1"},
                {"api_key": "user2_key", "user_id": "user2", "workspace_id": "ws_user2"},
            ],
        },
    )


def _no_auth_settings(tmp_data_dir: Path, tmp_lance_dir: Path) -> Settings:
    """Settings with auth disabled."""
    return Settings(
        storage={"backend": "local", "local": {"root": str(tmp_data_dir)}},
        lance={"data_dir": str(tmp_lance_dir)},
        embedding={"base_url": "http://127.0.0.1:8006", "model": "embedding-v5"},
        vfs={"cache_ttl": 0.0},
        auth={"enabled": False},
    )


@pytest_asyncio.fixture
async def auth_client(tmp_path) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient with auth enabled (2 users + admin)."""
    from app.main import app

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    lance_dir = tmp_path / "lance_data"
    lance_dir.mkdir()

    settings = _auth_settings(data_dir, lance_dir)
    storage = LocalStorage(settings)
    chunking = ChunkingService(settings)
    embedding = EmbeddingService(settings)
    index = IndexService(settings, data_dir=str(storage.root))
    event_bus = EventBus()
    from app.services.sync_queue import SyncQueue, SyncWorker
    sync_queue = SyncQueue(settings)
    sync_worker = SyncWorker(sync_queue, index)
    await sync_worker.start()
    pipeline = PipelineService(storage, chunking, embedding, index, settings, event_bus=event_bus, sync_queue=sync_queue)
    entity_svc = EntityService(storage, pipeline, settings)
    vfs_svc = VfsService(storage, settings)
    reconciler = ReconcilerService(storage, entity_svc, pipeline, settings)
    watch_svc = WatchService(storage, entity_svc, settings)

    app.state.settings = settings
    app.state.entity_service = entity_svc
    app.state.embedding_service = embedding
    app.state.index_service = index
    app.state.vfs_service = vfs_svc
    app.state.reconciler_service = reconciler
    app.state.watch_service = watch_svc
    app.state.event_bus = event_bus
    app.state.sync_queue = sync_queue
    app.state.sync_worker = sync_worker

    # Initialize AuthService
    from app.auth import build_auth_service_from_config
    auth_service = build_auth_service_from_config(settings.auth.model_dump())
    app.state.auth_service = auth_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    await sync_worker.stop()
    await embedding.close()
    await watch_svc.shutdown()


@pytest_asyncio.fixture
async def no_auth_client(tmp_path) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient with auth disabled."""
    from app.main import app

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    lance_dir = tmp_path / "lance_data"
    lance_dir.mkdir()

    settings = _no_auth_settings(data_dir, lance_dir)
    storage = LocalStorage(settings)
    chunking = ChunkingService(settings)
    embedding = EmbeddingService(settings)
    index = IndexService(settings, data_dir=str(storage.root))
    event_bus = EventBus()
    from app.services.sync_queue import SyncQueue, SyncWorker
    sync_queue = SyncQueue(settings)
    sync_worker = SyncWorker(sync_queue, index)
    await sync_worker.start()
    pipeline = PipelineService(storage, chunking, embedding, index, settings, event_bus=event_bus, sync_queue=sync_queue)
    entity_svc = EntityService(storage, pipeline, settings)
    vfs_svc = VfsService(storage, settings)
    reconciler = ReconcilerService(storage, entity_svc, pipeline, settings)
    watch_svc = WatchService(storage, entity_svc, settings)

    app.state.settings = settings
    app.state.entity_service = entity_svc
    app.state.embedding_service = embedding
    app.state.index_service = index
    app.state.vfs_service = vfs_svc
    app.state.reconciler_service = reconciler
    app.state.watch_service = watch_svc
    app.state.event_bus = event_bus
    app.state.sync_queue = sync_queue
    app.state.sync_worker = sync_worker

    # Auth disabled
    from app.auth import build_auth_service_from_config
    auth_service = build_auth_service_from_config(settings.auth.model_dump())
    app.state.auth_service = auth_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    await sync_worker.stop()
    await embedding.close()
    await watch_svc.shutdown()


# ---------------------------------------------------------------------------
# Auth middleware integration tests
# ---------------------------------------------------------------------------


class TestAuthMiddleware:
    """Integration tests for auth middleware."""

    @pytest.mark.asyncio
    async def test_no_key_returns_401(self, auth_client: AsyncClient):
        """Request without API Key returns 401."""
        resp = await auth_client.get("/api/v1/workspaces")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_key_returns_401(self, auth_client: AsyncClient):
        """Request with invalid API Key returns 401."""
        resp = await auth_client.get(
            "/api/v1/workspaces",
            headers={"Authorization": "Bearer wrong_key"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_key_returns_200(self, auth_client: AsyncClient):
        """Request with valid API Key returns 200."""
        resp = await auth_client.get(
            "/api/v1/workspaces",
            headers={"Authorization": "Bearer user1_key"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_x_api_key_header_works(self, auth_client: AsyncClient):
        """X-API-Key header also works for authentication."""
        resp = await auth_client.get(
            "/api/v1/workspaces",
            headers={"X-API-Key": "user1_key"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_public_paths_no_auth_needed(self, auth_client: AsyncClient):
        """Public paths (/health, /readiness, /status) don't require auth."""
        for path in ["/health", "/readiness", "/status"]:
            resp = await auth_client.get(path)
            assert resp.status_code == 200, f"Public path {path} should not require auth"

    @pytest.mark.asyncio
    async def test_access_own_workspace_ok(self, auth_client: AsyncClient):
        """User can access their own workspace."""
        resp = await auth_client.get(
            "/api/v1/workspaces/ws_user1",
            headers={"Authorization": "Bearer user1_key"},
        )
        # 404 is ok (workspace doesn't exist yet), but NOT 403
        assert resp.status_code in (200, 404)

    @pytest.mark.asyncio
    async def test_access_other_workspace_403(self, auth_client: AsyncClient):
        """User cannot access another user's workspace."""
        resp = await auth_client.get(
            "/api/v1/workspaces/ws_user2",
            headers={"Authorization": "Bearer user1_key"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_can_access_any_workspace(self, auth_client: AsyncClient):
        """Admin can access any workspace."""
        resp = await auth_client.get(
            "/api/v1/workspaces/ws_user1",
            headers={"Authorization": "Bearer admin_secret"},
        )
        # 404 is ok (workspace doesn't exist), but NOT 403
        assert resp.status_code in (200, 404)

    @pytest.mark.asyncio
    async def test_auth_disabled_no_key_needed(self, no_auth_client: AsyncClient):
        """When auth is disabled, no API Key is needed."""
        resp = await no_auth_client.get("/api/v1/workspaces")
        assert resp.status_code == 200


class TestWorkspaceIsolation:
    """Test workspace-level isolation in routers."""

    @pytest.mark.asyncio
    async def test_list_workspaces_filters_by_user(self, auth_client: AsyncClient):
        """Non-admin users only see their own workspace in list."""
        # Create workspace for user1
        resp = await auth_client.post(
            "/api/v1/workspaces",
            json={"workspace_id": "ws_user1"},
            headers={"Authorization": "Bearer user1_key"},
        )
        assert resp.status_code == 201

        # Create workspace for user2
        resp = await auth_client.post(
            "/api/v1/workspaces",
            json={"workspace_id": "ws_user2"},
            headers={"Authorization": "Bearer user2_key"},
        )
        assert resp.status_code == 201

        # User1 lists workspaces → only sees ws_user1
        resp = await auth_client.get(
            "/api/v1/workspaces",
            headers={"Authorization": "Bearer user1_key"},
        )
        assert resp.status_code == 200
        ws_ids = [ws["workspace_id"] for ws in resp.json()]
        assert ws_ids == ["ws_user1"]

        # User2 lists workspaces → only sees ws_user2
        resp = await auth_client.get(
            "/api/v1/workspaces",
            headers={"Authorization": "Bearer user2_key"},
        )
        assert resp.status_code == 200
        ws_ids = [ws["workspace_id"] for ws in resp.json()]
        assert ws_ids == ["ws_user2"]

    @pytest.mark.asyncio
    async def test_admin_sees_all_workspaces(self, auth_client: AsyncClient):
        """Admin can see all workspaces."""
        # Create workspaces
        await auth_client.post(
            "/api/v1/workspaces",
            json={"workspace_id": "ws_user1"},
            headers={"Authorization": "Bearer user1_key"},
        )
        await auth_client.post(
            "/api/v1/workspaces",
            json={"workspace_id": "ws_user2"},
            headers={"Authorization": "Bearer user2_key"},
        )

        # Admin lists workspaces → sees all
        resp = await auth_client.get(
            "/api/v1/workspaces",
            headers={"Authorization": "Bearer admin_secret"},
        )
        assert resp.status_code == 200
        ws_ids = [ws["workspace_id"] for ws in resp.json()]
        assert "ws_user1" in ws_ids
        assert "ws_user2" in ws_ids

    @pytest.mark.asyncio
    async def test_create_other_workspace_403(self, auth_client: AsyncClient):
        """Non-admin user cannot create a workspace they don't own."""
        resp = await auth_client.post(
            "/api/v1/workspaces",
            json={"workspace_id": "ws_other"},
            headers={"Authorization": "Bearer user1_key"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_create_own_workspace_ok(self, auth_client: AsyncClient):
        """Non-admin user can create their own workspace."""
        resp = await auth_client.post(
            "/api/v1/workspaces",
            json={"workspace_id": "ws_user1"},
            headers={"Authorization": "Bearer user1_key"},
        )
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_entity_upload_isolated_by_workspace(self, auth_client: AsyncClient):
        """User1 cannot upload to user2's workspace."""
        # Create workspace + collection for user2
        await auth_client.post(
            "/api/v1/workspaces",
            json={"workspace_id": "ws_user2"},
            headers={"Authorization": "Bearer user2_key"},
        )
        await auth_client.post(
            "/api/v1/workspaces/ws_user2/collections",
            json={"collection_id": "col1"},
            headers={"Authorization": "Bearer user2_key"},
        )

        # User1 tries to upload to user2's workspace → 403
        resp = await auth_client.post(
            "/api/v1/workspaces/ws_user2/collections/col1/entities",
            files={"file": ("test.md", b"# Hello\nWorld", "text/markdown")},
            headers={"Authorization": "Bearer user1_key"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_entity_upload_own_workspace_ok(self, auth_client: AsyncClient):
        """User can upload to their own workspace."""
        # Create workspace + collection for user1
        await auth_client.post(
            "/api/v1/workspaces",
            json={"workspace_id": "ws_user1"},
            headers={"Authorization": "Bearer user1_key"},
        )
        await auth_client.post(
            "/api/v1/workspaces/ws_user1/collections",
            json={"collection_id": "col1"},
            headers={"Authorization": "Bearer user1_key"},
        )

        # User1 uploads to their own workspace → 201
        resp = await auth_client.post(
            "/api/v1/workspaces/ws_user1/collections/col1/entities",
            files={"file": ("test.md", b"# Hello\nWorld", "text/markdown")},
            headers={"Authorization": "Bearer user1_key"},
        )
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_search_isolated_by_workspace(self, auth_client: AsyncClient):
        """User1 cannot search in user2's workspace."""
        # User1 tries to search in user2's workspace → 403
        resp = await auth_client.post(
            "/api/v1/workspaces/ws_user2/collections/col1/search",
            json={"query": "test", "search_type": "semantic"},
            headers={"Authorization": "Bearer user1_key"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_vfs_isolated_by_workspace(self, auth_client: AsyncClient):
        """User1 cannot access VFS in user2's workspace."""
        resp = await auth_client.post(
            "/api/v1/workspaces/ws_user2/collections/col1/vfs/ls",
            json={"path": "/"},
            headers={"Authorization": "Bearer user1_key"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_reconcile_isolated_by_workspace(self, auth_client: AsyncClient):
        """User1 cannot reconcile in user2's workspace."""
        resp = await auth_client.post(
            "/api/v1/workspaces/ws_user2/collections/col1/reconcile",
            headers={"Authorization": "Bearer user1_key"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_can_upload_to_any_workspace(self, auth_client: AsyncClient):
        """Admin can upload to any workspace."""
        # Create workspace + collection as admin
        await auth_client.post(
            "/api/v1/workspaces",
            json={"workspace_id": "ws_user1"},
            headers={"Authorization": "Bearer admin_secret"},
        )
        await auth_client.post(
            "/api/v1/workspaces/ws_user1/collections",
            json={"collection_id": "col1"},
            headers={"Authorization": "Bearer admin_secret"},
        )

        # Admin uploads to user1's workspace → ok
        resp = await auth_client.post(
            "/api/v1/workspaces/ws_user1/collections/col1/entities",
            files={"file": ("test.md", b"# Admin\nUpload", "text/markdown")},
            headers={"Authorization": "Bearer admin_secret"},
        )
        assert resp.status_code == 201
