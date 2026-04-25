"""Mnemos MCP server — MnemosApp core logic + FastMCP tool registration.

v1.0 narrative-first pivot: the mining/drawer paradigm is gone. ``MnemosApp``
no longer has ``palace``, ``miner``, ``handle_mine``, ``handle_add``, or the
``on_vault_change`` watcher event handler — they all coupled to mnemos.miner /
mnemos.palace which were deleted in Task 3. The remaining surface is the
narrative-first read path: search, status, recall, graph, timeline, wake_up.

Subsequent v1.0 tasks will reshape these:
  - Task 18: ``mnemos_search`` collection becomes raw-only
  - Task 19: ``mnemos_wake_up`` returns the Identity Layer
  - Task 20: ``mnemos_recall`` becomes L0-only
  - Task 21: ``mnemos_graph`` / ``mnemos_timeline`` become wikilink-driven
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from mnemos.config import MnemosConfig, load_config

if TYPE_CHECKING:
    from mnemos.graph import KnowledgeGraph
    from mnemos.search import SearchEngine
    from mnemos.stack import MemoryStack


# ---------------------------------------------------------------------------
# MnemosApp — core logic (testable without MCP)
# ---------------------------------------------------------------------------


class MnemosApp:
    """Core Mnemos application logic.

    All MCP tools delegate to methods on this class, making them independently
    testable without the MCP protocol overhead.
    """

    def __init__(self, config: MnemosConfig, chromadb_in_memory: bool = False) -> None:
        # Lazy imports to avoid slow chromadb import at server startup
        from mnemos.graph import KnowledgeGraph
        from mnemos.search import SearchEngine
        from mnemos.stack import MemoryStack

        self.config = config
        self.search_engine = SearchEngine(config, in_memory=chromadb_in_memory)
        # Ensure palace dir exists before opening SQLite graph
        config.graph_full_path.parent.mkdir(parents=True, exist_ok=True)
        self.graph = KnowledgeGraph(config.graph_full_path)
        self.stack = MemoryStack(config)

    def close(self) -> None:
        """Flush and close the underlying search index.

        Call before process exit for write workloads to ensure ChromaDB's
        HNSW segments are persisted to disk.
        """
        self.search_engine.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    # ------------------------------------------------------------------
    # handle_search
    # ------------------------------------------------------------------

    def handle_search(
        self,
        query: str,
        wing: Optional[str] = None,
        room: Optional[str] = None,
        hall: Optional[str] = None,
        exclude_wing: Optional[str] = None,
        limit: int = 5,
        collection: str = "both",
    ) -> list[dict]:
        """Semantic search over indexed drawers with optional filters."""
        return self.search_engine.search(
            query=query,
            wing=wing,
            room=room,
            hall=hall,
            exclude_wing=exclude_wing,
            limit=limit,
            collection=collection,
        )

    # ------------------------------------------------------------------
    # handle_status
    # ------------------------------------------------------------------

    def handle_status(self) -> dict:
        """Return current status: drawer count, vault path, wings, backend.

        ``wings`` is now derived from the on-disk ``wings_dir`` layout (any
        subdirectory of ``palace_dir/wings/`` counts), not from the deleted
        ``Palace.list_wings`` helper.
        """
        stats = self.search_engine.get_stats()
        wings = self._list_wings_from_disk()
        sp = self.search_engine.storage_path()

        return {
            "total_drawers": stats["total_drawers"],
            "vault_path": self.config.vault_path,
            "wings": wings,
            "wings_detail": stats.get("wings", {}),
            "backend": {
                "name": self.config.search_backend,
                "path": str(sp) if sp is not None else None,
                "storage_bytes": stats.get("storage_bytes", 0),
            },
        }

    def _list_wings_from_disk(self) -> list[str]:
        """Lightweight replacement for the deleted ``Palace.list_wings``.

        Returns the names of immediate subdirectories of ``wings_dir``.
        Returns an empty list if the directory doesn't exist yet (e.g.
        on a fresh vault that hasn't been onboarded).
        """
        wings_dir = self.config.wings_dir
        if not wings_dir.exists():
            return []
        return sorted(p.name for p in wings_dir.iterdir() if p.is_dir())

    # ------------------------------------------------------------------
    # handle_recall
    # ------------------------------------------------------------------

    def handle_recall(self, level: str = "L1", wing: Optional[str] = None) -> dict:
        """Recall memory at the specified stack level."""
        return self.stack.recall(level=level, wing=wing)

    # ------------------------------------------------------------------
    # handle_graph
    # ------------------------------------------------------------------

    def handle_graph(self, entity: str, as_of: Optional[str] = None) -> dict:
        """Query the knowledge graph for triples about an entity."""
        triples = self.graph.query_entity(entity=entity, as_of=as_of)
        return {
            "entity": entity,
            "as_of": as_of,
            "triples": triples,
        }

    # ------------------------------------------------------------------
    # handle_timeline
    # ------------------------------------------------------------------

    def handle_timeline(
        self,
        entity: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> list:
        """Return timeline of triples for an entity, optionally filtered by date range."""
        entries = self.graph.timeline(entity=entity)

        if from_date is not None:
            entries = [e for e in entries if e.get("valid_from") and e["valid_from"] >= from_date]
        if to_date is not None:
            entries = [e for e in entries if e.get("valid_from") and e["valid_from"] <= to_date]

        return entries

    # ------------------------------------------------------------------
    # handle_wake_up
    # ------------------------------------------------------------------

    def handle_wake_up(self) -> dict:
        """Load identity + wings summary for context injection."""
        return self.stack.wake_up()


# ---------------------------------------------------------------------------
# create_mcp_server — MCP protocol layer
# ---------------------------------------------------------------------------


def build_instructions(cfg: MnemosConfig) -> str:
    """Return MCP server instructions string based on recall_mode.

    Two modes:
      - "script" (default): AI auto-calls mnemos_search when user mentions a
        project/topic. Backwards-compatible with existing clients.
      - "skill": SessionStart briefing hook (see mnemos.recall_briefing) has
        already injected per-cwd context as additionalContext. AI should NOT
        auto-call mnemos_search on every turn, but user-explicit asks still
        trigger search.
    """
    base = "Obsidian-native AI memory palace.\n"

    if cfg.recall_mode == "skill":
        return base + (
            "SessionStart briefing is already injected as additionalContext "
            "for the current cwd — rely on it as primary project memory. Do "
            "NOT auto-call mnemos_search on every user turn; it wastes "
            "tokens when briefing already covers the context. However, IF the "
            "user explicitly asks to recall something not in the briefing "
            "(cross-project reference, older history, keyword lookup), CALL "
            "mnemos_search — user-explicit requests override the default-off "
            "rule. /mnemos-recall <query> skill (when available) is the "
            "preferred entry point for cross-context queries."
        )

    # Default: script mode (also catches unknown values defensively)
    return base + (
        "At the START of every session, call mnemos_wake_up to load identity "
        "and project context (~200 tokens). "
        "When the user mentions a project or topic, call mnemos_search to "
        "retrieve relevant memories before responding. "
        "Use mnemos_recall with level=L2 and a wing name to get deeper "
        "room-level details when needed."
    )


def create_mcp_server(config: Optional[MnemosConfig] = None):
    """Create and configure a FastMCP server with the v1.0 Mnemos tools.

    v1.0 surface: ``mnemos_search``, ``mnemos_status``, ``mnemos_recall``,
    ``mnemos_graph``, ``mnemos_timeline``, ``mnemos_wake_up``. The
    ``mnemos_mine`` and ``mnemos_add`` tools were removed when the
    mining/drawer paradigm was retired.

    Returns the configured FastMCP instance (call .run() to start).
    """
    from mcp.server.fastmcp import FastMCP

    if config is None:
        config = load_config()

    # Eager init: create app at startup so tool calls don't block
    _app = MnemosApp(config)

    # Ensure ChromaDB flushes its HNSW segments on process exit.
    # Without this, binary index files are left partial and the next
    # process can't load the index ("Error loading hnsw index").
    import atexit
    atexit.register(_app.close)

    def _get_app() -> MnemosApp:
        return _app

    mcp = FastMCP(
        "mnemos",
        instructions=build_instructions(config),
    )

    # ------------------------------------------------------------------
    # Tool: mnemos_search
    # ------------------------------------------------------------------

    @mcp.tool()
    def mnemos_search(
        query: str,
        wing: Optional[str] = None,
        room: Optional[str] = None,
        hall: Optional[str] = None,
        limit: int = 5,
        collection: str = "both",
    ) -> str:
        """Search the memory palace. collection: 'raw', 'mined', or 'both' (default)."""
        results = _get_app().handle_search(query=query, wing=wing, room=room, hall=hall, limit=limit, collection=collection)
        return json.dumps(results, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Tool: mnemos_status
    # ------------------------------------------------------------------

    @mcp.tool()
    def mnemos_status() -> str:
        """Return current status of the memory palace."""
        result = _get_app().handle_status()
        return json.dumps(result, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Tool: mnemos_recall
    # ------------------------------------------------------------------

    @mcp.tool()
    def mnemos_recall(
        level: str = "L1",
        wing: Optional[str] = None,
    ) -> str:
        """Recall memory at the specified stack level (L0, L1, L2)."""
        result = _get_app().handle_recall(level=level, wing=wing)
        return json.dumps(result, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Tool: mnemos_graph
    # ------------------------------------------------------------------

    @mcp.tool()
    def mnemos_graph(
        entity: str,
        as_of: Optional[str] = None,
    ) -> str:
        """Query the knowledge graph for an entity's relations."""
        result = _get_app().handle_graph(entity=entity, as_of=as_of)
        return json.dumps(result, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Tool: mnemos_timeline
    # ------------------------------------------------------------------

    @mcp.tool()
    def mnemos_timeline(
        entity: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> str:
        """Return the temporal timeline of an entity's relations."""
        result = _get_app().handle_timeline(entity=entity, from_date=from_date, to_date=to_date)
        return json.dumps(result, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Tool: mnemos_wake_up
    # ------------------------------------------------------------------

    @mcp.tool()
    def mnemos_wake_up() -> str:
        """Load identity + wings summary for LLM context injection."""
        result = _get_app().handle_wake_up()
        return json.dumps(result, ensure_ascii=False)

    return mcp
