"""Mnemos MCP server — MnemosApp core logic + FastMCP tool registration.

v1.0 narrative-first pivot: the mining/drawer paradigm is gone. ``MnemosApp``
no longer has ``palace``, ``miner``, ``handle_mine``, ``handle_add``, or the
``on_vault_change`` watcher event handler — they all coupled to mnemos.miner /
mnemos.palace which were deleted in Task 3. The remaining surface is the
narrative-first read path: search, status, recall, graph, timeline, wake_up.

Task 21 also retired the SQLite ``KnowledgeGraph`` triple store: ``handle_graph``
and ``handle_timeline`` now scan Obsidian wikilinks (``[[Entity]]``) directly
from ``Sessions/<date>-<slug>.md`` files. The graph is no longer a separate
durable index — it is derived on demand from the canonical vault.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from mnemos.config import MnemosConfig, load_config

if TYPE_CHECKING:
    from mnemos.search import SearchEngine
    from mnemos.stack import MemoryStack


# Module-level wikilink pattern reused by handle_graph and handle_timeline.
_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def _coerce_date(value) -> Optional[str]:
    """Return an ISO date string for ``value``, or None if unset.

    YAML parses bare ``date: 2026-04-01`` as ``datetime.date``; we want a
    JSON-serialisable ISO string for the MCP envelope and for lexicographic
    date comparisons.
    """
    if value is None or value == "":
        return None
    if isinstance(value, str):
        return value
    isofmt = getattr(value, "isoformat", None)
    if callable(isofmt):
        return isofmt()
    return str(value)


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
        from mnemos.search import SearchEngine
        from mnemos.stack import MemoryStack

        self.config = config
        self.search_engine = SearchEngine(config, in_memory=chromadb_in_memory)
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
        collection: str = "raw",
    ) -> list[dict]:
        """Semantic search over indexed drawers with optional filters.

        v1.0 narrative-first pivot: only the ``raw`` collection (Sessions/
        <date>-<slug>.md) remains indexed. The legacy ``mined`` and ``both``
        values are accepted for backward compatibility but emit a
        ``DeprecationWarning`` and fall back to ``raw``.
        """
        if collection in ("mined", "both"):
            import warnings
            warnings.warn(
                f"collection={collection!r} is deprecated in v1.0; "
                "the mined collection was retired in the narrative-first "
                "pivot — falling back to 'raw'",
                DeprecationWarning,
                stacklevel=2,
            )
            collection = "raw"
        if collection != "raw":
            raise ValueError(f"unknown collection: {collection!r}")
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

        v1.0 also surfaces Identity Layer metadata (``identity_last_refreshed``
        + ``identity_session_count_at_refresh``) so clients can decide when to
        prompt an auto-refresh. Both keys are ``None`` when the vault hasn't
        been bootstrapped yet (no ``_identity/L0-identity.md``).
        """
        stats = self.search_engine.get_stats()
        wings = self._list_wings_from_disk()
        sp = self.search_engine.storage_path()

        status = {
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

        # Identity Layer metadata (v1.0)
        identity_path = Path(self.config.vault_path) / "_identity" / "L0-identity.md"
        if identity_path.exists():
            from mnemos.identity import _parse_frontmatter
            fm = _parse_frontmatter(identity_path.read_text(encoding="utf-8"))
            last_refreshed = fm.get("last_refreshed")
            # YAML parses bare ``2026-04-25`` as datetime.date; coerce to ISO
            # string so the MCP JSON envelope serializes cleanly.
            if last_refreshed is not None and not isinstance(last_refreshed, str):
                last_refreshed = last_refreshed.isoformat()
            status["identity_last_refreshed"] = last_refreshed
            status["identity_session_count_at_refresh"] = fm.get("session_count_at_refresh")
        else:
            status["identity_last_refreshed"] = None
            status["identity_session_count_at_refresh"] = None

        return status

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

    def handle_recall(self, level: str = "L0", wing: Optional[str] = None) -> dict:
        """Recall memory at the specified stack level.

        v1.0: only ``L0`` (Identity Layer) is supported. ``L1`` and ``L2``
        return a deprecation marker — the drawer paradigm was retired in the
        narrative-first pivot. The default level changed from ``L1`` to
        ``L0`` accordingly.
        """
        return self.stack.recall(level=level, wing=wing)

    # ------------------------------------------------------------------
    # handle_graph
    # ------------------------------------------------------------------

    def handle_graph(self, entity: str, as_of: Optional[str] = None) -> dict:
        """Query the Obsidian wikilink graph for an entity's neighbours.

        v1.0: scans ``Sessions/<date>-<slug>.md`` for ``[[Entity]]`` mentions
        and emits a ``co-mentioned-in`` triple for every other wikilink found
        in the same session. The SQLite triple store was retired — the vault
        is the canonical graph.
        """
        from mnemos.obsidian import parse_frontmatter

        sessions_dir = Path(self.config.vault_path) / "Sessions"
        if not sessions_dir.exists():
            return {"entity": entity, "as_of": as_of, "triples": []}

        triples: list[dict] = []
        vault_root = Path(self.config.vault_path)
        for session in sorted(sessions_dir.glob("*.md")):
            try:
                fm, body = parse_frontmatter(session)
            except Exception:
                continue
            session_date = _coerce_date(fm.get("date"))
            if as_of is not None and session_date is not None and session_date > as_of:
                continue
            mentions = set(_WIKILINK_RE.findall(body))
            if entity not in mentions:
                continue
            for other in sorted(mentions - {entity}):
                triples.append({
                    "subject": entity,
                    "predicate": "co-mentioned-in",
                    "object": other,
                    "valid_from": session_date,
                    "source_file": str(session.relative_to(vault_root)),
                })
        return {"entity": entity, "as_of": as_of, "triples": triples}

    # ------------------------------------------------------------------
    # handle_timeline
    # ------------------------------------------------------------------

    def handle_timeline(
        self,
        entity: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> list:
        """Chronological list of Sessions mentioning ``entity`` via wikilink.

        v1.0: scans ``Sessions/<date>-<slug>.md`` for ``[[entity]]`` mentions,
        sorts ascending by frontmatter ``date``, and returns one entry per
        session. ``from_date`` / ``to_date`` are optional ISO-string bounds.
        """
        from mnemos.obsidian import parse_frontmatter

        sessions_dir = Path(self.config.vault_path) / "Sessions"
        if not sessions_dir.exists():
            return []

        entity_pattern = re.compile(r"\[\[" + re.escape(entity) + r"\]\]")
        vault_root = Path(self.config.vault_path)
        timeline: list[dict] = []
        for session in sorted(sessions_dir.glob("*.md")):
            try:
                content = session.read_text(encoding="utf-8")
            except OSError:
                continue
            if not entity_pattern.search(content):
                continue
            try:
                fm, _ = parse_frontmatter(session)
            except Exception:
                fm = {}
            date = _coerce_date(fm.get("date"))
            if from_date is not None and date is not None and date < from_date:
                continue
            if to_date is not None and date is not None and date > to_date:
                continue
            timeline.append({
                "subject": entity,
                "predicate": "mentioned-in",
                "object": session.name,
                "valid_from": date,
                "source_file": str(session.relative_to(vault_root)),
            })
        timeline.sort(key=lambda e: e.get("valid_from") or "")
        return timeline

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
        "At the START of every session, call mnemos_wake_up to load the "
        "Identity Layer (~200 tokens). "
        "When the user mentions a project or topic, call mnemos_search to "
        "retrieve relevant memories from Sessions/<date>-<slug>.md before "
        "responding. The drawer paradigm (L1 wings / L2 rooms) is retired "
        "in v1.0 — mnemos_recall returns only L0 (Identity)."
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
        collection: str = "raw",
    ) -> str:
        """Search the memory palace (Sessions). collection: 'raw' (default).

        v1.0: 'mined' and 'both' are deprecated and silently fall back to
        'raw' — the mined collection was retired in the narrative-first pivot.
        """
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
        level: str = "L0",
        wing: Optional[str] = None,
    ) -> str:
        """Recall memory at the specified stack level.

        v1.0: only ``L0`` (Identity Layer) is supported; ``L1`` and ``L2``
        return a deprecation marker. The drawer paradigm (wings/rooms) was
        retired in the narrative-first pivot.
        """
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
