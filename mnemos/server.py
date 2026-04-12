"""Mnemos MCP server — MnemosApp core logic + FastMCP tool registration."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from mnemos.config import MnemosConfig, load_config
from mnemos.graph import KnowledgeGraph
from mnemos.miner import Miner
from mnemos.palace import Palace
from mnemos.search import SearchEngine
from mnemos.stack import MemoryStack
from mnemos.watcher import VaultWatcher


# ---------------------------------------------------------------------------
# MnemosApp — core logic (testable without MCP)
# ---------------------------------------------------------------------------


class MnemosApp:
    """Core Mnemos application logic.

    All MCP tools delegate to methods on this class, making them independently
    testable without the MCP protocol overhead.
    """

    def __init__(self, config: MnemosConfig, chromadb_in_memory: bool = False) -> None:
        self.config = config
        self.palace = Palace(config)
        self.search_engine = SearchEngine(config, in_memory=chromadb_in_memory)
        # Ensure palace dir exists before opening SQLite graph
        config.graph_full_path.parent.mkdir(parents=True, exist_ok=True)
        self.graph = KnowledgeGraph(config.graph_full_path)
        self.miner = Miner(config)
        self.stack = MemoryStack(config)
        self._mine_log: dict[str, float] = self._load_mine_log()

    # ------------------------------------------------------------------
    # handle_search
    # ------------------------------------------------------------------

    def handle_search(
        self,
        query: str,
        wing: Optional[str] = None,
        room: Optional[str] = None,
        hall: Optional[str] = None,
        limit: int = 5,
    ) -> list[dict]:
        """Semantic search over indexed drawers with optional filters."""
        return self.search_engine.search(
            query=query,
            wing=wing,
            room=room,
            hall=hall,
            limit=limit,
        )

    # ------------------------------------------------------------------
    # handle_add
    # ------------------------------------------------------------------

    def handle_add(
        self,
        text: str,
        wing: str,
        room: str,
        hall: str = "facts",
        importance: float = 0.5,
    ) -> dict:
        """Create a drawer in the palace and index it in the search engine.

        Returns:
            dict with keys: drawer_id, obsidian_path, message
        """
        drawer_path = self.palace.add_drawer(
            wing=wing,
            room=room,
            hall=hall,
            text=text,
            source="manual",
            importance=importance,
            entities=[],
            language="en",
        )

        drawer_id = drawer_path.stem
        obsidian_path = str(drawer_path)

        self.search_engine.index_drawer(
            drawer_id=drawer_id,
            text=text,
            metadata={
                "wing": wing,
                "room": room,
                "hall": hall,
                "importance": importance,
                "source": "manual",
            },
        )

        return {
            "drawer_id": drawer_id,
            "obsidian_path": obsidian_path,
            "message": f"Added drawer to {wing}/{room}/{hall}",
        }

    # ------------------------------------------------------------------
    # handle_mine
    # ------------------------------------------------------------------

    def handle_mine(
        self,
        path: str,
        mode: str = "auto",
        use_llm: bool = False,
    ) -> dict:
        """Mine files at *path*, create drawers, index them, update mine_log.

        *path* may be a file or directory. Relative paths are resolved against
        config.vault_path. Already-processed files (checked via mtime) are
        skipped.

        Returns:
            dict with keys: files_scanned, drawers_created, entities_found, skipped
        """
        target = Path(path)
        if not target.is_absolute():
            target = Path(self.config.vault_path) / target

        # Collect candidate .md files
        if target.is_file():
            candidates = [target]
        elif target.is_dir():
            candidates = list(target.rglob("*.md"))
        else:
            return {
                "files_scanned": 0,
                "drawers_created": 0,
                "entities_found": 0,
                "skipped": 0,
                "error": f"Path not found: {target}",
            }

        files_scanned = 0
        drawers_created = 0
        entities_found = 0
        skipped = 0

        for filepath in candidates:
            filepath_str = str(filepath)
            try:
                mtime = filepath.stat().st_mtime
            except OSError:
                continue

            # Skip if already processed and file hasn't changed
            last_processed = self._mine_log.get(filepath_str)
            if last_processed is not None and mtime <= last_processed:
                skipped += 1
                continue

            files_scanned += 1

            fragments = self.miner.mine_file(filepath, use_llm=use_llm)

            for frag in fragments:
                drawer_path = self.palace.add_drawer(
                    wing=frag["wing"],
                    room=frag["room"],
                    hall=frag["hall"],
                    text=frag["text"],
                    source=frag["source"],
                    importance=0.5,
                    entities=frag["entities"],
                    language=frag["language"],
                )

                drawer_id = drawer_path.stem
                self.search_engine.index_drawer(
                    drawer_id=drawer_id,
                    text=frag["text"],
                    metadata={
                        "wing": frag["wing"],
                        "room": frag["room"],
                        "hall": frag["hall"],
                        "source": frag["source"],
                        "language": frag["language"],
                    },
                )

                drawers_created += 1
                entities_found += len(frag.get("entities", []))

            # Mark file as processed
            self._mine_log[filepath_str] = time.time()

        self._save_mine_log()

        return {
            "files_scanned": files_scanned,
            "drawers_created": drawers_created,
            "entities_found": entities_found,
            "skipped": skipped,
        }

    # ------------------------------------------------------------------
    # handle_status
    # ------------------------------------------------------------------

    def handle_status(self) -> dict:
        """Return current status: drawer count, vault path, wings."""
        stats = self.search_engine.get_stats()
        wings = self.palace.list_wings()

        return {
            "total_drawers": stats["total_drawers"],
            "vault_path": self.config.vault_path,
            "wings": wings,
            "wings_detail": stats.get("wings", {}),
        }

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

    # ------------------------------------------------------------------
    # on_vault_change — watcher event handler
    # ------------------------------------------------------------------

    def on_vault_change(
        self,
        event_type: str,
        filepath: Path,
        dest_path: Optional[Path] = None,
    ) -> None:
        """Handle vault watcher events.

        - deleted: remove matching drawers from search index
        - created / modified: re-mine the file
        - moved: remove old, mine new path
        """
        filepath_str = str(filepath)

        if event_type == "deleted":
            # Remove from mine_log
            self._mine_log.pop(filepath_str, None)
            self._save_mine_log()
            # Remove all triples sourced from this file
            self.graph.delete_triples_by_source(filepath_str)

        elif event_type in ("created", "modified"):
            # Force re-mine by clearing the log entry
            self._mine_log.pop(filepath_str, None)
            self.handle_mine(path=filepath_str)

        elif event_type == "moved" and dest_path is not None:
            # Remove old
            self._mine_log.pop(filepath_str, None)
            self._save_mine_log()
            self.graph.delete_triples_by_source(filepath_str)
            # Mine new location
            self.handle_mine(path=str(dest_path))

    # ------------------------------------------------------------------
    # Mine log helpers
    # ------------------------------------------------------------------

    def _load_mine_log(self) -> dict[str, float]:
        """Load mine_log.json from palace dir. Returns empty dict if missing."""
        log_path = self.config.mine_log_full_path
        if not log_path.exists():
            return {}
        try:
            with log_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return {k: float(v) for k, v in data.items()}
        except (json.JSONDecodeError, ValueError, OSError):
            pass
        return {}

    def _save_mine_log(self) -> None:
        """Persist mine_log to palace dir as JSON. Creates parent dirs if needed."""
        log_path = self.config.mine_log_full_path
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", encoding="utf-8") as fh:
            json.dump(self._mine_log, fh, indent=2)


# ---------------------------------------------------------------------------
# create_mcp_server — MCP protocol layer
# ---------------------------------------------------------------------------


def create_mcp_server(config: Optional[MnemosConfig] = None):
    """Create and configure a FastMCP server with 8 Mnemos tools.

    Returns the configured FastMCP instance (call .run() to start).
    """
    from mcp.server.fastmcp import FastMCP

    if config is None:
        config = load_config()

    app = MnemosApp(config)
    app.palace.ensure_structure()

    mcp = FastMCP("mnemos", instructions="Obsidian-native AI memory palace")

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
    ) -> str:
        """Search the memory palace using semantic similarity."""
        results = app.handle_search(query=query, wing=wing, room=room, hall=hall, limit=limit)
        return json.dumps(results, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Tool: mnemos_add
    # ------------------------------------------------------------------

    @mcp.tool()
    def mnemos_add(
        text: str,
        wing: str,
        room: str,
        hall: str = "facts",
        importance: float = 0.5,
    ) -> str:
        """Add a memory fragment to the palace and index it for search."""
        result = app.handle_add(text=text, wing=wing, room=room, hall=hall, importance=importance)
        return json.dumps(result, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Tool: mnemos_mine
    # ------------------------------------------------------------------

    @mcp.tool()
    def mnemos_mine(
        path: str,
        mode: str = "auto",
        use_llm: bool = False,
    ) -> str:
        """Mine a file or directory and extract memory fragments."""
        result = app.handle_mine(path=path, mode=mode, use_llm=use_llm)
        return json.dumps(result, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Tool: mnemos_status
    # ------------------------------------------------------------------

    @mcp.tool()
    def mnemos_status() -> str:
        """Return current status of the memory palace."""
        result = app.handle_status()
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
        result = app.handle_recall(level=level, wing=wing)
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
        result = app.handle_graph(entity=entity, as_of=as_of)
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
        result = app.handle_timeline(entity=entity, from_date=from_date, to_date=to_date)
        return json.dumps(result, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Tool: mnemos_wake_up
    # ------------------------------------------------------------------

    @mcp.tool()
    def mnemos_wake_up() -> str:
        """Load identity + wings summary for LLM context injection."""
        result = app.handle_wake_up()
        return json.dumps(result, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Start watcher if enabled
    # ------------------------------------------------------------------

    if config.watcher_enabled and config.vault_path:
        try:
            watcher = VaultWatcher(config=config, on_change=app.on_vault_change)
            watcher.start()
        except Exception:
            # Watcher failure must not prevent server startup
            pass

    return mcp
