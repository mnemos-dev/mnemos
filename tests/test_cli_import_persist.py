"""Tests for `mnemos import` persisting sources into mnemos.yaml.

Pre-v0.3.2 `mnemos import` only wrote to `.mnemos-pending.json`, so every
`mnemos mine --rebuild` would silently drop the imported sources. Part 2
of the distribution-ready fix: imports append to yaml's `mining_sources`
so rebuilds include them automatically.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from mnemos.cli import _append_mining_source


def _write_yaml(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=False)


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def test_append_mining_source_creates_yaml_when_missing(tmp_path: Path) -> None:
    """First-ever import with no yaml yet writes one."""
    yaml_path = tmp_path / "mnemos.yaml"
    assert not yaml_path.exists()

    added = _append_mining_source(
        tmp_path, source_path="/some/absolute/memory", mode="curated",
    )
    assert added is True
    assert yaml_path.exists()

    data = _read_yaml(yaml_path)
    assert "mining_sources" in data
    assert len(data["mining_sources"]) == 1
    assert data["mining_sources"][0]["path"] == "/some/absolute/memory"
    assert data["mining_sources"][0]["mode"] == "curated"


def test_append_mining_source_preserves_existing_yaml_fields(tmp_path: Path) -> None:
    """Append must not wipe unrelated keys (search_backend, use_llm, etc.)."""
    yaml_path = tmp_path / "mnemos.yaml"
    _write_yaml(yaml_path, {
        "version": 1,
        "search_backend": "sqlite-vec",
        "use_llm": True,
    })

    _append_mining_source(
        tmp_path, source_path="/x/memory", mode="curated",
    )

    data = _read_yaml(yaml_path)
    assert data["search_backend"] == "sqlite-vec"
    assert data["use_llm"] is True
    assert data["version"] == 1
    assert data["mining_sources"][0]["path"] == "/x/memory"


def test_append_mining_source_is_idempotent(tmp_path: Path) -> None:
    """Re-import of the same path must not duplicate the entry."""
    yaml_path = tmp_path / "mnemos.yaml"

    first = _append_mining_source(
        tmp_path, source_path="/dup/memory", mode="curated",
    )
    second = _append_mining_source(
        tmp_path, source_path="/dup/memory", mode="curated",
    )
    assert first is True
    assert second is False

    data = _read_yaml(yaml_path)
    assert len(data["mining_sources"]) == 1


def test_append_mining_source_appends_second_path(tmp_path: Path) -> None:
    """Different paths accumulate; import 5 memory folders → 5 entries."""
    _append_mining_source(tmp_path, source_path="/one/memory", mode="curated")
    _append_mining_source(tmp_path, source_path="/two/memory", mode="curated")
    _append_mining_source(tmp_path, source_path="/three/memory", mode="curated")

    data = _read_yaml(tmp_path / "mnemos.yaml")
    assert len(data["mining_sources"]) == 3
    paths = [s["path"] for s in data["mining_sources"]]
    assert paths == ["/one/memory", "/two/memory", "/three/memory"]


def test_append_mining_source_normalizes_path_for_dedup(tmp_path: Path) -> None:
    """On Windows, same path with different slashes must be deduped.

    We compare by os.path.normpath so `C:\\foo\\memory` and `C:/foo/memory`
    are recognized as the same entry.
    """
    import os

    first_path = "C:\\foo\\memory"
    first = _append_mining_source(tmp_path, source_path=first_path, mode="curated")
    # Same path with different slashes (how Python expand returns it)
    second_path = os.path.normpath(first_path).replace("\\", "/")
    # If they point at the same place, should be a no-op
    if os.path.normpath(first_path) == os.path.normpath(second_path):
        second = _append_mining_source(tmp_path, source_path=second_path, mode="curated")
        assert first is True
        assert second is False
        data = _read_yaml(tmp_path / "mnemos.yaml")
        assert len(data["mining_sources"]) == 1
