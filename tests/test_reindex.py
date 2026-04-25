"""Tests for mnemos reindex (v1.0 backend switch + recovery)."""
import tempfile
from pathlib import Path
import pytest


def test_reindex_rebuilds_from_sessions(tmp_path):
    from mnemos.reindex import reindex
    vault = tmp_path / "vault"
    (vault / "Sessions").mkdir(parents=True)
    for i in range(3):
        (vault / "Sessions" / f"2026-01-{i+1:02d}-test.md").write_text(
            f"---\ndate: 2026-01-{i+1:02d}\n---\n\n# Test {i}\n", encoding="utf-8"
        )
    (vault / "mnemos.yaml").write_text(
        f"vault_path: {vault}\nlanguages: [en]\nsearch_backend: sqlite-vec\n",
        encoding="utf-8",
    )
    result = reindex(vault, backend=None, no_backup=False)
    assert result["session_count"] == 3
    assert result["backend"] == "sqlite-vec"


def test_reindex_with_backend_override_updates_yaml(tmp_path):
    from mnemos.reindex import reindex
    vault = tmp_path / "vault"
    (vault / "Sessions").mkdir(parents=True)
    (vault / "mnemos.yaml").write_text(
        f"vault_path: {vault}\nlanguages: [en]\nsearch_backend: chromadb\n",
        encoding="utf-8",
    )
    reindex(vault, backend="sqlite-vec", no_backup=True)
    yaml_content = (vault / "mnemos.yaml").read_text(encoding="utf-8")
    assert "sqlite-vec" in yaml_content


def test_reindex_creates_backup_unless_disabled(tmp_path):
    from mnemos.reindex import reindex
    vault = tmp_path / "vault"
    (vault / "Sessions").mkdir(parents=True)
    storage = vault / "Mnemos"
    storage.mkdir()
    (storage / "search.sqlite3").write_text("dummy index", encoding="utf-8")
    (vault / "mnemos.yaml").write_text(
        f"vault_path: {vault}\nlanguages: [en]\nsearch_backend: sqlite-vec\n",
        encoding="utf-8",
    )
    reindex(vault, backend=None, no_backup=False)
    backups = list(storage.glob("search.sqlite3.bak-*"))
    assert len(backups) == 1
