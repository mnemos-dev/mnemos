"""Tests for the v1.0 MCP tool surface.

After the narrative-first pivot, the MCP server no longer exposes the
mining/drawer entry points (``mnemos_mine``, ``mnemos_add``). These tests
lock that surface down so a future refactor can't silently re-introduce
them.
"""
from __future__ import annotations

import asyncio
import warnings
from pathlib import Path

import pytest

from mnemos.config import MnemosConfig
from mnemos.server import MnemosApp, create_mcp_server


def _registered_tool_names(mcp) -> list[str]:
    """Return the names of every tool registered on a FastMCP instance.

    FastMCP exposes a coroutine ``list_tools()`` that yields the canonical
    tool registry (the public, MCP-protocol view). We use it instead of
    poking at the private ``_tool_manager`` attribute so this test stays
    stable across FastMCP minor versions.
    """
    tools = asyncio.run(mcp.list_tools())
    return [t.name for t in tools]


def test_mnemos_mine_tool_removed(tmp_path: Path) -> None:
    """v1.0: ``mnemos_mine`` MCP tool no longer exists."""
    cfg = MnemosConfig(vault_path=str(tmp_path))
    mcp = create_mcp_server(cfg)
    tool_names = _registered_tool_names(mcp)
    assert "mnemos_mine" not in tool_names, (
        f"mnemos_mine still registered: {tool_names}"
    )


def test_mnemos_add_tool_removed(tmp_path: Path) -> None:
    """v1.0: ``mnemos_add`` MCP tool was retired alongside the mining paradigm.

    Manual drawer creation no longer makes sense — Sessions/<date>-<slug>.md
    is the canonical memory unit, written by users / the refine skill.
    """
    cfg = MnemosConfig(vault_path=str(tmp_path))
    mcp = create_mcp_server(cfg)
    tool_names = _registered_tool_names(mcp)
    assert "mnemos_add" not in tool_names, (
        f"mnemos_add still registered: {tool_names}"
    )


def test_v1_mcp_surface_has_six_read_tools(tmp_path: Path) -> None:
    """v1.0 MCP surface is read-only (search/recall/wake_up + graph/timeline + status)."""
    cfg = MnemosConfig(vault_path=str(tmp_path))
    mcp = create_mcp_server(cfg)
    tool_names = set(_registered_tool_names(mcp))
    expected = {
        "mnemos_search",
        "mnemos_status",
        "mnemos_recall",
        "mnemos_graph",
        "mnemos_timeline",
        "mnemos_wake_up",
    }
    assert expected.issubset(tool_names), (
        f"v1.0 surface missing tools. Have: {tool_names}, expected: {expected}"
    )


# ---------------------------------------------------------------------------
# handle_search — collection parameter v1.0 deprecation
# ---------------------------------------------------------------------------


def test_search_raw_collection_works(tmp_path: Path) -> None:
    """mnemos_search(collection='raw') returns results normally."""
    vault = tmp_path / "vault"
    (vault / "Sessions").mkdir(parents=True)
    cfg = MnemosConfig(vault_path=str(vault), languages=["en"])
    app = MnemosApp(cfg, chromadb_in_memory=True)
    try:
        result = app.handle_search(query="test", limit=5, collection="raw")
        # handle_search returns list[dict]; on a fresh vault it's just empty
        assert isinstance(result, list)
    finally:
        app.close()


def test_search_mined_collection_warns_falls_back_to_raw(tmp_path: Path) -> None:
    """mnemos_search(collection='mined') logs a warning and uses raw."""
    vault = tmp_path / "vault"
    (vault / "Sessions").mkdir(parents=True)
    cfg = MnemosConfig(vault_path=str(vault), languages=["en"])
    app = MnemosApp(cfg, chromadb_in_memory=True)
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            app.handle_search(query="test", limit=5, collection="mined")
        assert any("deprecated" in str(w.message).lower() for w in caught), (
            f"Expected DeprecationWarning, got: {[str(w.message) for w in caught]}"
        )
    finally:
        app.close()


def test_search_both_collection_falls_back_to_raw(tmp_path: Path) -> None:
    """mnemos_search(collection='both') logs a warning and uses raw."""
    vault = tmp_path / "vault"
    (vault / "Sessions").mkdir(parents=True)
    cfg = MnemosConfig(vault_path=str(vault), languages=["en"])
    app = MnemosApp(cfg, chromadb_in_memory=True)
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            app.handle_search(query="test", limit=5, collection="both")
        assert any("deprecated" in str(w.message).lower() for w in caught), (
            f"Expected DeprecationWarning, got: {[str(w.message) for w in caught]}"
        )
    finally:
        app.close()
