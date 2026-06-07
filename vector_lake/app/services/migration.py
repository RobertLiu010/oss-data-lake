"""LanceDB schema migration.

Simple version-file-based migration: each migration is a function that
receives a LanceDB connection and the config. The current schema version
is stored in the lance_dir as _schema_version.txt.

Usage (called from IndexService):
    from app.services.migration import run_migrations
    run_migrations(db, settings)
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Registry of migrations: version -> callable
_MIGRATIONS: dict[int, callable] = {}

CURRENT_VERSION = 2


def _get_version_file(lance_dir: str) -> Path:
    return Path(lance_dir) / "_schema_version.txt"


def _read_version(lance_dir: str) -> int:
    vf = _get_version_file(lance_dir)
    if not vf.exists():
        return 0
    try:
        return int(vf.read_text().strip())
    except (ValueError, OSError):
        logger.warning("Corrupt schema version file, assuming 0")
        return 0


def _write_version(lance_dir: str, version: int) -> None:
    """Atomic write of schema version file (write tmp → fsync → rename)."""
    vf = _get_version_file(lance_dir)
    vf.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = vf.with_suffix(".tmp")
    tmp_path.write_text(str(version))
    tmp_path.replace(vf)


def migration(version: int):
    """Decorator to register a migration function for a specific version."""

    def decorator(func):
        _MIGRATIONS[version] = func
        return func

    return decorator


# ---------------------------------------------------------------------------
# Migrations
# ---------------------------------------------------------------------------


@migration(1)
def _migration_001_create_fts_indexes(db, settings):
    """Create FTS indexes on all existing tables."""
    tables = db.list_tables()
    # LanceDB >=0.33 returns ListTablesResponse; fall back to list for older versions
    table_names = tables.tables if hasattr(tables, "tables") else list(tables)
    for table_name in table_names:
        try:
            table = db.open_table(table_name)
            table.create_fts_index("text", replace=True)
            logger.info("Migration 001: created FTS index on %s", table_name)
        except Exception as e:
            logger.warning("Migration 001: failed on %s: %s", table_name, e)


@migration(2)
def _migration_002_add_rep_name_column(db, settings):
    """Add rep_name column to all existing chunk tables.

    For pre-existing data, set rep_name = 'canonical_md' as the default.
    New data will have the correct rep_name set by the pipeline.
    """

    tables = db.list_tables()
    table_names = tables.tables if hasattr(tables, "tables") else list(tables)
    for table_name in table_names:
        try:
            table = db.open_table(table_name)
            schema = table.schema
            # Check if rep_name column already exists
            if "rep_name" in {f.name for f in schema}:
                logger.info("Migration 002: rep_name already exists in %s, skipping", table_name)
                continue
            # Add rep_name column with default value
            table.add_columns({
                "rep_name": "'canonical_md'",
            })
            logger.info("Migration 002: added rep_name column to %s", table_name)
        except Exception as e:
            logger.warning("Migration 002: failed on %s: %s", table_name, e)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_migrations(db, settings) -> int:
    """Run all pending migrations. Returns the number applied."""
    lance_dir = settings.lance.data_dir
    current = _read_version(lance_dir)
    applied = 0

    for version in sorted(_MIGRATIONS):
        if version <= current:
            continue
        try:
            logger.info("Running migration %03d...", version)
            _MIGRATIONS[version](db, settings)
            _write_version(lance_dir, version)
            applied += 1
            logger.info("Migration %03d applied successfully.", version)
        except Exception:
            logger.exception("Migration %03d failed!", version)
            raise

    if applied == 0:
        logger.debug("Schema is up to date (version %d)", current)

    return applied
