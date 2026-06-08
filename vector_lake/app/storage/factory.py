"""Storage backend factory — config-driven backend selection.

Usage:
    from app.storage.factory import create_storage
    storage = create_storage(settings)

The backend is selected via settings.storage.backend:
- "local" → LocalStorage (default)
- "s3"    → S3Storage (MinIO / S3-compatible)
"""

from __future__ import annotations

import logging

from app.config import Settings
from app.storage.protocol import StorageProtocol

logger = logging.getLogger(__name__)


def create_storage(settings: Settings) -> StorageProtocol:
    """Create a storage backend instance based on settings.

    The backend is determined by settings.storage.backend:
    - "local" → LocalStorage (filesystem + xattr)
    - "s3"    → S3Storage (MinIO / S3-compatible object storage)

    Returns a StorageProtocol-compliant instance.
    """
    backend = settings.storage.backend.lower()

    if backend == "local":
        from app.storage.local import LocalStorage
        logger.info("Using LocalStorage backend (root=%s)", settings.storage.local.root)
        return LocalStorage(settings)

    elif backend == "s3":
        from app.storage.s3 import S3Storage
        s3_cfg = settings.storage.s3
        logger.info(
            "Using S3Storage backend (endpoint=%s, bucket=%s, prefix=%s)",
            s3_cfg.endpoint_url, s3_cfg.bucket, s3_cfg.prefix,
        )
        return S3Storage(settings)

    else:
        raise ValueError(
            f"Unknown storage backend: '{backend}'. "
            f"Supported backends: 'local', 's3'"
        )
