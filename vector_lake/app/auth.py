"""Authentication and user isolation for Vector Lake.

Model: User = Workspace
- Each API Key maps to exactly one user, who owns exactly one workspace.
- Authenticated users can only access their own workspace.
- System endpoints (/health, /readiness, /status, /metrics) are public.
- Admin API Key can access all workspaces.

Configuration (config.yaml):
  auth:
    enabled: true
    admin_api_key: "vl_admin_key"
    users:
      - api_key: "user1_key"
        user_id: "user1"
        workspace_id: "ws_user1"
      - api_key: "user2_key"
        user_id: "user2"
        workspace_id: "ws_user2"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException, Request, status
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class UserInfo(BaseModel):
    """A single user's identity and workspace binding."""
    api_key: str
    user_id: str
    workspace_id: str


class AuthConfig(BaseModel):
    """Authentication configuration (replaces the simple AuthConfig in config.py)."""
    enabled: bool = False
    admin_api_key: str = ""
    users: list[UserInfo] = []


@dataclass
class AuthUser:
    """Resolved user from API Key authentication."""
    user_id: str
    workspace_id: str
    is_admin: bool = False


class AuthService:
    """API Key authentication service with user→workspace binding.

    - Validates API Key from Authorization header
    - Resolves user identity and workspace
    - Enforces workspace isolation
    """

    def __init__(self, enabled: bool, admin_api_key: str, users: list[UserInfo]):
        self.enabled = enabled
        self.admin_api_key = admin_api_key
        # api_key → AuthUser lookup
        self._key_to_user: dict[str, AuthUser] = {}
        for u in users:
            self._key_to_user[u.api_key] = AuthUser(
                user_id=u.user_id,
                workspace_id=u.workspace_id,
                is_admin=False,
            )
        # Admin key
        if admin_api_key:
            self._key_to_user[admin_api_key] = AuthUser(
                user_id="admin",
                workspace_id="*",
                is_admin=True,
            )

    def authenticate(self, request: Request) -> AuthUser | None:
        """Extract and validate API Key from request.

        Returns AuthUser if valid, None if auth is disabled.
        Raises HTTPException(401) if auth is enabled but key is invalid.
        """
        if not self.enabled:
            return None  # Auth disabled, no user context

        api_key = self._extract_api_key(request)
        if api_key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing API Key. Use Authorization: Bearer <key> or X-API-Key header.",
            )

        user = self._key_to_user.get(api_key)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API Key.",
            )

        return user

    def enforce_workspace(self, user: AuthUser | None, workspace_id: str) -> None:
        """Ensure user has access to the requested workspace.

        Raises HTTPException(403) if user tries to access another workspace.
        Admin users can access any workspace.
        No-op if auth is disabled (user is None).
        """
        if user is None:
            return  # Auth disabled

        if user.is_admin:
            return  # Admin can access everything

        if user.workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User '{user.user_id}' cannot access workspace '{workspace_id}'. "
                       f"Allowed workspace: '{user.workspace_id}'",
            )

    def get_user_workspace(self, user: AuthUser | None) -> str | None:
        """Get the user's bound workspace_id, or None if auth disabled."""
        if user is None:
            return None
        if user.is_admin:
            return None  # Admin has no fixed workspace
        return user.workspace_id

    @staticmethod
    def _extract_api_key(request: Request) -> str | None:
        """Extract API Key from Authorization header or X-API-Key header."""
        # Try Authorization: Bearer <key>
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:].strip()

        # Try X-API-Key header
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return api_key.strip()

        return None


# ---------------------------------------------------------------------------
# Public paths that don't require authentication
# ---------------------------------------------------------------------------

PUBLIC_PATHS = frozenset({
    "/health",
    "/readiness",
    "/status",
    "/metrics",
    "/docs",
    "/openapi.json",
    "/redoc",
})


def is_public_path(path: str) -> bool:
    """Check if a path should bypass authentication."""
    return path in PUBLIC_PATHS or path.startswith("/docs") or path.startswith("/redoc")


def build_auth_service_from_config(auth_config_dict: dict[str, Any]) -> AuthService:
    """Build AuthService from the auth section of config.yaml.

    Supports both old format (api_keys: {key: name}) and new format (users list).
    """
    enabled = auth_config_dict.get("enabled", False)
    admin_api_key = auth_config_dict.get("admin_api_key", "")

    # New format: users list
    raw_users = auth_config_dict.get("users", [])
    users = [UserInfo(**u) for u in raw_users]

    # Backward compat: old format api_keys → auto-create workspace per key
    old_api_keys = auth_config_dict.get("api_keys", {})
    for key, name in old_api_keys.items():
        ws_id = f"ws_{name}" if name else f"ws_{key[:8]}"
        users.append(UserInfo(api_key=key, user_id=name or key[:8], workspace_id=ws_id))

    return AuthService(enabled=enabled, admin_api_key=admin_api_key, users=users)
