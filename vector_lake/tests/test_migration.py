"""Tests for the migration module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.migration import (
    CURRENT_VERSION,
    _migration_001_create_fts_indexes,
    _read_version,
    _write_version,
    run_migrations,
)

# ---------------------------------------------------------------------------
# _read_version / _write_version
# ---------------------------------------------------------------------------


def test_read_version_no_file(tmp_lance_dir):
    """Returns 0 when the version file does not exist."""
    assert _read_version(str(tmp_lance_dir)) == 0


def test_write_and_read_version(tmp_lance_dir):
    """Write a version and read it back."""
    _write_version(str(tmp_lance_dir), 3)
    assert _read_version(str(tmp_lance_dir)) == 3


def test_read_version_corrupt_file(tmp_lance_dir):
    """A corrupt (non-numeric) version file returns 0."""
    version_file = tmp_lance_dir / "_schema_version.txt"
    version_file.write_text("not_a_number")
    assert _read_version(str(tmp_lance_dir)) == 0


# ---------------------------------------------------------------------------
# run_migrations
# ---------------------------------------------------------------------------


def test_run_migrations_fresh(settings, tmp_lance_dir):
    """Fresh install (version 0) runs all pending migrations."""
    db = MagicMock()
    db.list_tables.return_value = []

    applied = run_migrations(db, settings)

    assert applied == CURRENT_VERSION
    assert _read_version(str(tmp_lance_dir)) == CURRENT_VERSION


def test_run_migrations_already_applied(settings, tmp_lance_dir):
    """Already at current version — no migrations run."""
    _write_version(str(tmp_lance_dir), CURRENT_VERSION)
    db = MagicMock()

    applied = run_migrations(db, settings)

    assert applied == 0
    assert _read_version(str(tmp_lance_dir)) == CURRENT_VERSION


def test_run_migrations_partial(settings, tmp_lance_dir):
    """Partially applied — only remaining migrations run."""
    # Simulate being at version 0, but patch _MIGRATIONS to have two
    # migrations so we can test partial application.
    mock_m1 = MagicMock()
    mock_m2 = MagicMock()
    fake_migrations = {1: mock_m1, 2: mock_m2}

    db = MagicMock()
    db.list_tables.return_value = []

    with patch("app.services.migration._MIGRATIONS", fake_migrations), \
         patch("app.services.migration.CURRENT_VERSION", 2):
        # Version file says 1, so only migration 2 should run
        _write_version(str(tmp_lance_dir), 1)
        applied = run_migrations(db, settings)

        mock_m1.assert_not_called()
        mock_m2.assert_called_once_with(db, settings)
        assert applied == 1
        assert _read_version(str(tmp_lance_dir)) == 2


def test_migration_failure_stops(settings, tmp_lance_dir):
    """If a migration fails, run_migrations raises and stops."""
    bad_migration = MagicMock(side_effect=RuntimeError("boom"))
    good_migration = MagicMock()
    fake_migrations = {1: bad_migration, 2: good_migration}

    db = MagicMock()

    with patch("app.services.migration._MIGRATIONS", fake_migrations), \
         patch("app.services.migration.CURRENT_VERSION", 2):
        with pytest.raises(RuntimeError, match="boom"):
            run_migrations(db, settings)

        # The bad migration was attempted, but the good one was never reached
        bad_migration.assert_called_once()
        good_migration.assert_not_called()

    # Version file should still be 0 (migration 1 never completed)
    assert _read_version(str(tmp_lance_dir)) == 0


# ---------------------------------------------------------------------------
# _migration_001_create_fts_indexes
# ---------------------------------------------------------------------------


def test_migration_001_handles_list_tables_response():
    """Migration 001 handles both plain list and ListTablesResponse."""
    # --- Case 1: db.list_tables() returns a plain list ---
    db_list = MagicMock()
    table_mock = MagicMock()
    db_list.list_tables.return_value = ["t1", "t2"]
    db_list.open_table.return_value = table_mock

    settings = MagicMock()
    _migration_001_create_fts_indexes(db_list, settings)

    assert db_list.open_table.call_count == 2
    assert table_mock.create_fts_index.call_count == 2

    # --- Case 2: db.list_tables() returns a ListTablesResponse-like object ---
    db_resp = MagicMock()
    table_mock2 = MagicMock()
    list_response = MagicMock()
    list_response.tables = ["t3"]
    # Ensure hasattr finds .tables on the mock
    db_resp.list_tables.return_value = list_response
    db_resp.open_table.return_value = table_mock2

    _migration_001_create_fts_indexes(db_resp, settings)

    db_resp.open_table.assert_called_once_with("t3")
    table_mock2.create_fts_index.assert_called_once_with("text", replace=True)
