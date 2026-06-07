"""Tests for app.security — validate_id and validate_path_under_root."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.security import validate_id, validate_path_under_root

# ---------------------------------------------------------------------------
# validate_id
# ---------------------------------------------------------------------------


class TestValidateId:
    """Tests for validate_id()."""

    def test_valid_alphanumeric(self):
        assert validate_id("abc123") == "abc123"

    def test_valid_with_underscore(self):
        assert validate_id("my_id") == "my_id"

    def test_valid_with_hyphen(self):
        assert validate_id("my-id") == "my-id"

    def test_valid_with_dot(self):
        assert validate_id("file.md") == "file.md"

    def test_valid_complex(self):
        assert validate_id("ws_001.v2") == "ws_001.v2"

    def test_empty_string_rejected(self):
        with pytest.raises(ValueError, match="must not be empty"):
            validate_id("")

    def test_path_traversal_dotdot_rejected(self):
        with pytest.raises(ValueError, match="invalid characters"):
            validate_id("../etc/passwd")

    def test_slash_rejected(self):
        with pytest.raises(ValueError, match="invalid characters"):
            validate_id("foo/bar")

    def test_backslash_rejected(self):
        with pytest.raises(ValueError, match="invalid characters"):
            validate_id("foo\\bar")

    def test_special_chars_rejected(self):
        with pytest.raises(ValueError, match="invalid characters"):
            validate_id("id$evil")

    def test_space_rejected(self):
        with pytest.raises(ValueError, match="invalid characters"):
            validate_id("has space")

    def test_null_byte_rejected(self):
        with pytest.raises(ValueError, match="invalid characters"):
            validate_id("id\x00evil")

    def test_custom_name_in_error(self):
        with pytest.raises(ValueError, match="workspace_id"):
            validate_id("../evil", name="workspace_id")


# ---------------------------------------------------------------------------
# validate_path_under_root
# ---------------------------------------------------------------------------


class TestValidatePathUnderRoot:
    """Tests for validate_path_under_root()."""

    def test_valid_subpath(self, tmp_path: Path):
        root = tmp_path / "root"
        root.mkdir()
        child = root / "subdir" / "file.txt"
        result = validate_path_under_root(child, root)
        assert str(result).startswith(str(root.resolve()))

    def test_exact_root_passes(self, tmp_path: Path):
        root = tmp_path / "root"
        root.mkdir()
        result = validate_path_under_root(root, root)
        assert result == root.resolve()

    def test_path_traversal_blocked(self, tmp_path: Path):
        root = tmp_path / "root"
        root.mkdir()
        escape = tmp_path / "root" / ".." / ".." / "etc" / "passwd"
        with pytest.raises(ValueError, match="outside root"):
            validate_path_under_root(escape, root)

    def test_symlink_escape_blocked(self, tmp_path: Path):
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "secret"
        outside.mkdir()
        link = root / "link"
        try:
            link.symlink_to(outside)
        except OSError:
            pytest.skip("symlinks not supported on this filesystem")
        with pytest.raises(ValueError, match="outside root"):
            validate_path_under_root(link, root)
