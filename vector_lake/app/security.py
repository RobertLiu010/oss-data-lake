"""Security utilities for path validation."""
from __future__ import annotations

import re
from pathlib import Path

# Only allow alphanumeric, underscore, hyphen, dot in identifiers
SAFE_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_\-.]+$')

def validate_id(value: str, name: str = "id") -> str:
    """Validate that an identifier contains only safe characters and no path traversal."""
    if not value:
        raise ValueError(f"{name} must not be empty")
    if '..' in value or '/' in value or '\\' in value:
        raise ValueError(f"{name} contains invalid characters: {value}")
    if not SAFE_ID_PATTERN.match(value):
        raise ValueError(f"{name} contains invalid characters: {value}")
    return value

def validate_path_under_root(path: Path, root: Path) -> Path:
    """Validate that a resolved path is under the given root directory."""
    resolved = path.resolve()
    root_resolved = root.resolve()
    if not str(resolved).startswith(str(root_resolved)):
        raise ValueError(f"Path {resolved} is outside root {root_resolved}")
    return resolved
