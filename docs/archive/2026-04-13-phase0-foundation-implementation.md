# Phase 0 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** API kullanmadan MemPalace ile esit recall (%96+) yakalamak — raw verbatim storage, dual collection, conversation normalizer, mining engine overhaul, benchmark.

**Architecture:** ChromaDB dual collection (mnemos_raw + mnemos_mined) with Reciprocal Rank Fusion search merge. Conversation normalizer converts 5 chat formats to standard transcript. Mining engine uses exchange-pair chunking, 72+ room patterns, heuristic entity detection, 87+ EN + ~80 TR markers with scoring/disambiguation, and code line filtering. LongMemEval benchmark measures Recall@5/10.

**Tech Stack:** Python 3.10+, ChromaDB, pytest, PyYAML, hashlib, json

**Spec:** `docs/specs/2026-04-13-phase0-foundation-design.md`

---

## File Map

### New Files
| File | Responsibility |
|------|---------------|
| `mnemos/normalizer.py` | Conversation format detection + normalize to transcript |
| `mnemos/room_detector.py` | 72+ pattern folder/keyword room detection |
| `mnemos/entity_detector.py` | Two-pass heuristic entity detection (person/project) |
| `mnemos/prose.py` | Code line filtering — extract human prose only |
| `mnemos/patterns/rooms.yaml` | Room detection folder + keyword patterns |
| `tests/test_normalizer.py` | Normalizer tests |
| `tests/test_room_detector.py` | Room detector tests |
| `tests/test_entity_detector.py` | Entity detector tests |
| `tests/test_prose.py` | Prose extraction tests |
| `benchmarks/__init__.py` | Package init |
| `benchmarks/longmemeval/__init__.py` | Package init |
| `benchmarks/longmemeval/dataset.py` | HuggingFace dataset download + parse |
| `benchmarks/longmemeval/metrics.py` | Recall@K, NDCG@10 computation |
| `benchmarks/longmemeval/runner.py` | Benchmark orchestrator |

### Modified Files
| File | Changes |
|------|---------|
| `mnemos/search.py` | Dual collection, index_raw(), RRF merge, $in/$nin filters |
| `mnemos/miner.py` | Exchange-pair chunking, scoring/disambiguation, prose filter, new detector integration |
| `mnemos/server.py` | Raw indexing in handle_mine, collection param in handle_search, atomic rebuild |
| `mnemos/cli.py` | --rebuild flag, --collection flag, benchmark subcommand |
| `mnemos/config.py` | New config fields (chunk_max_size, min_confidence) |
| `mnemos/patterns/en.yaml` | 87+ markers (decisions 21, preferences 16, problems 17, events 33) |
| `mnemos/patterns/tr.yaml` | ~80 markers (expanded TR equivalents) |
| `tests/test_search.py` | Dual collection tests, RRF tests, $in filter tests |
| `tests/test_miner.py` | Exchange-pair chunking tests, scoring tests |
| `tests/test_server.py` | Raw indexing tests, rebuild tests |
| `tests/conftest.py` | New fixtures (conversation samples, benchmark data) |
| `pyproject.toml` | benchmark optional dependency (huggingface_hub) |

---

## Task 1: SearchEngine Dual Collection + RRF

**Files:**
- Modify: `mnemos/search.py`
- Modify: `tests/test_search.py`

- [ ] **Step 1: Write failing tests for dual collection**

Add to `tests/test_search.py`:

```python
# --- Dual collection tests ---

def test_index_raw_and_search_raw(engine: SearchEngine) -> None:
    """Raw collection stores and retrieves verbatim text."""
    engine.index_raw(
        doc_id="raw-abc123",
        text="We had a long discussion about Supabase RLS policies and decided to enable them on all tables.",
        metadata={"wing": "ProcureTrack", "room": "supabase", "source_path": "/sessions/2026-04-10.md"},
    )
    results = engine.search("Supabase row level security", collection="raw", limit=5)
    assert len(results) >= 1
    assert results[0]["drawer_id"] == "raw-abc123"


def test_search_both_collections_rrf(engine: SearchEngine) -> None:
    """Search 'both' merges raw+mined via RRF, deduplicates by source_path."""
    engine.index_raw(
        doc_id="raw-abc123",
        text="Full session about Supabase RLS. We decided to enable RLS on all tables. Next step: test policies.",
        metadata={"wing": "ProcureTrack", "room": "supabase", "source_path": "/sessions/2026-04-10.md"},
    )
    engine.index_drawer(
        drawer_id="mined-001",
        text="We decided to enable RLS on all tables.",
        metadata={"wing": "ProcureTrack", "room": "supabase", "hall": "decisions", "source_path": "/sessions/2026-04-10.md"},
    )
    results = engine.search("Supabase RLS decision", collection="both", limit=5)
    assert len(results) >= 1
    # Both sources found, merged by RRF
    ids = [r["drawer_id"] for r in results]
    assert any("raw" in id or "mined" in id for id in ids)


def test_search_mined_only(engine: SearchEngine) -> None:
    """collection='mined' only searches mined collection."""
    engine.index_raw(
        doc_id="raw-only",
        text="This is only in raw.",
        metadata={"wing": "Test", "source_path": "test.md"},
    )
    engine.index_drawer(
        drawer_id="mined-only",
        text="This is only in mined.",
        metadata={"wing": "Test", "hall": "facts"},
    )
    results = engine.search("only in raw", collection="mined", limit=5)
    ids = [r["drawer_id"] for r in results]
    assert "raw-only" not in ids


def test_rrf_score_calculation() -> None:
    """RRF formula: sum(1/(k+rank)) with k=60."""
    from mnemos.search import _rrf_score
    # Rank 1 in one list: 1/(60+1) = 0.01639
    assert abs(_rrf_score([1], k=60) - 1 / 61) < 1e-6
    # Rank 1 in two lists: 2/(60+1) = 0.03279
    assert abs(_rrf_score([1, 1], k=60) - 2 / 61) < 1e-6
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /c/Projeler/mnemos && python -m pytest tests/test_search.py -v -k "raw or rrf or both" 2>&1 | head -30`
Expected: FAIL (index_raw not defined, collection param not supported)

- [ ] **Step 3: Implement dual collection in SearchEngine**

Modify `mnemos/search.py`:

```python
"""Mnemos search engine — ChromaDB-backed semantic search with dual collection + RRF."""
from __future__ import annotations

import hashlib
import uuid
from typing import Any

import chromadb

from mnemos.config import MnemosConfig


def _rrf_score(ranks: list[int], k: int = 60) -> float:
    """Reciprocal Rank Fusion score from a list of ranks."""
    return sum(1.0 / (k + r) for r in ranks)


class SearchEngine:
    """Dual-collection search: mnemos_raw (verbatim) + mnemos_mined (fragments)."""

    COLLECTION_RAW = "mnemos_raw"
    COLLECTION_MINED = "mnemos_mined"

    def __init__(self, config: MnemosConfig, in_memory: bool = False) -> None:
        if in_memory:
            self._client = chromadb.EphemeralClient()
            suffix = uuid.uuid4().hex
            raw_name = f"{self.COLLECTION_RAW}_{suffix}"
            mined_name = f"{self.COLLECTION_MINED}_{suffix}"
        else:
            self._client = chromadb.PersistentClient(
                path=str(config.chromadb_full_path)
            )
            raw_name = self.COLLECTION_RAW
            mined_name = self.COLLECTION_MINED

        self._raw = self._client.get_or_create_collection(
            name=raw_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._mined = self._client.get_or_create_collection(
            name=mined_name,
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_raw(self, doc_id: str, text: str, metadata: dict) -> None:
        """Index verbatim file content into the raw collection."""
        clean_meta = self._clean_metadata(metadata)
        self._raw.upsert(ids=[doc_id], documents=[text], metadatas=[clean_meta])

    def index_drawer(self, drawer_id: str, text: str, metadata: dict) -> None:
        """Index a mined fragment into the mined collection."""
        clean_meta = self._clean_metadata(metadata)
        self._mined.upsert(ids=[drawer_id], documents=[text], metadatas=[clean_meta])

    def delete_drawer(self, drawer_id: str) -> None:
        """Remove a drawer from the mined index."""
        try:
            self._mined.delete(ids=[drawer_id])
        except Exception:
            pass

    def delete_raw(self, doc_id: str) -> None:
        """Remove a document from the raw index."""
        try:
            self._raw.delete(ids=[doc_id])
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        wing: str | list[str] | None = None,
        room: str | list[str] | None = None,
        hall: str | list[str] | None = None,
        exclude_wing: str | list[str] | None = None,
        limit: int = 5,
        collection: str = "both",
    ) -> list[dict]:
        """Search with optional metadata filters.

        Args:
            collection: "raw", "mined", or "both" (RRF merge)
        """
        where = self._build_where_filter(wing, room, hall, exclude_wing)

        if collection == "raw":
            return self._search_collection(self._raw, query, where, limit)
        elif collection == "mined":
            return self._search_collection(self._mined, query, where, limit)
        else:
            return self._search_both(query, where, limit)

    def _search_collection(
        self,
        coll,
        query: str,
        where: dict | None,
        limit: int,
    ) -> list[dict]:
        """Search a single collection, return scored results."""
        count = coll.count()
        if count == 0:
            return []

        n_results = min(limit, count)
        kwargs: dict[str, Any] = {"query_texts": [query], "n_results": n_results}
        if where is not None:
            kwargs["where"] = where

        results = coll.query(**kwargs)
        return self._format_results(results)

    def _search_both(self, query: str, where: dict | None, limit: int) -> list[dict]:
        """Search raw+mined, merge via Reciprocal Rank Fusion."""
        # Fetch from both collections (get more than limit to improve RRF quality)
        fetch_n = min(limit * 2, 20)
        raw_results = self._search_collection(self._raw, query, where, fetch_n)
        mined_results = self._search_collection(self._mined, query, where, fetch_n)

        # Build rank maps: doc_id -> list of ranks
        rank_map: dict[str, list[int]] = {}
        result_map: dict[str, dict] = {}

        for rank, r in enumerate(raw_results, 1):
            doc_id = r["drawer_id"]
            rank_map.setdefault(doc_id, []).append(rank)
            result_map[doc_id] = r

        for rank, r in enumerate(mined_results, 1):
            doc_id = r["drawer_id"]
            rank_map.setdefault(doc_id, []).append(rank)
            if doc_id not in result_map:
                result_map[doc_id] = r

        # Compute RRF scores and sort
        scored = []
        for doc_id, ranks in rank_map.items():
            rrf = _rrf_score(ranks)
            entry = dict(result_map[doc_id])
            entry["score"] = rrf
            scored.append(entry)

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return total drawer count and per-wing counts (mined collection)."""
        total = self._mined.count()
        raw_total = self._raw.count()
        wings: dict[str, int] = {}

        if total > 0:
            all_items = self._mined.get(include=["metadatas"])
            for meta in all_items["metadatas"]:
                wing_name = meta.get("wing", "")
                if wing_name:
                    wings[wing_name] = wings.get(wing_name, 0) + 1

        return {"total_drawers": total, "raw_documents": raw_total, "wings": wings}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_metadata(metadata: dict) -> dict[str, Any]:
        """ChromaDB only accepts str/int/float/bool metadata values."""
        clean: dict[str, Any] = {}
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)):
                clean[key] = value
            elif isinstance(value, list):
                clean[key] = ",".join(str(v) for v in value)
            else:
                clean[key] = str(value)
        return clean

    def _build_where_filter(
        self,
        wing: str | list[str] | None,
        room: str | list[str] | None,
        hall: str | list[str] | None,
        exclude_wing: str | list[str] | None = None,
    ) -> dict | None:
        """Build ChromaDB where filter with $in and $nin support."""
        conditions: list[dict] = []

        for field, value in [("wing", wing), ("room", room), ("hall", hall)]:
            if value is not None:
                if isinstance(value, list):
                    conditions.append({field: {"$in": value}})
                else:
                    conditions.append({field: value})

        if exclude_wing is not None:
            if isinstance(exclude_wing, list):
                conditions.append({"wing": {"$nin": exclude_wing}})
            else:
                conditions.append({"wing": {"$nin": [exclude_wing]}})

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    @staticmethod
    def _format_results(results: dict) -> list[dict]:
        """Convert ChromaDB query results to list of dicts."""
        output: list[dict] = []
        ids = results["ids"][0]
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        for drawer_id, text, meta, dist in zip(ids, documents, metadatas, distances):
            output.append({
                "drawer_id": drawer_id,
                "text": text,
                "metadata": meta,
                "score": 1.0 - dist,
            })
        return output

    @staticmethod
    def raw_doc_id(source_path: str, chunk_index: int | None = None) -> str:
        """Generate a deterministic raw document ID from source path."""
        h = hashlib.sha256(source_path.encode()).hexdigest()[:16]
        if chunk_index is not None:
            return f"raw-{h}-{chunk_index}"
        return f"raw-{h}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /c/Projeler/mnemos && python -m pytest tests/test_search.py -v 2>&1 | tail -20`
Expected: ALL PASS (both old and new tests)

- [ ] **Step 5: Write tests for $in and exclude filters**

Add to `tests/test_search.py`:

```python
def test_search_with_wing_list_filter(engine: SearchEngine) -> None:
    """$in filter: search across multiple wings."""
    engine.index_drawer("d1", "Auth decision", {"wing": "ProcureTrack", "hall": "decisions"})
    engine.index_drawer("d2", "GYP budget", {"wing": "GYP", "hall": "facts"})
    engine.index_drawer("d3", "LinkedIn post", {"wing": "LinkedIn", "hall": "facts"})

    results = engine.search("decision budget", wing=["ProcureTrack", "GYP"], collection="mined")
    ids = [r["drawer_id"] for r in results]
    assert "d3" not in ids  # LinkedIn excluded by filter


def test_search_with_exclude_wing(engine: SearchEngine) -> None:
    """$nin filter: exclude specific wing."""
    engine.index_drawer("d1", "Important fact", {"wing": "ProcureTrack", "hall": "facts"})
    engine.index_drawer("d2", "General noise", {"wing": "General", "hall": "facts"})

    results = engine.search("fact", exclude_wing="General", collection="mined")
    ids = [r["drawer_id"] for r in results]
    assert "d2" not in ids
    assert "d1" in ids
```

- [ ] **Step 6: Run filter tests**

Run: `cd /c/Projeler/mnemos && python -m pytest tests/test_search.py -v -k "wing_list or exclude" 2>&1 | tail -10`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add mnemos/search.py tests/test_search.py
git commit -m "feat: dual collection (raw+mined) with RRF merge and $in/$nin filters"
```

---

## Task 2: Code Line Filtering (prose.py)

**Files:**
- Create: `mnemos/prose.py`
- Create: `tests/test_prose.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_prose.py`:

```python
"""Tests for mnemos.prose — code line filtering."""
from mnemos.prose import extract_prose


def test_removes_code_blocks():
    text = "Important decision here.\n\n```python\ndef foo():\n    return 42\n```\n\nAnother fact."
    result = extract_prose(text)
    assert "def foo" not in result
    assert "Important decision" in result
    assert "Another fact" in result


def test_removes_shell_commands():
    text = "We decided to deploy.\n$ git push origin main\n$ npm install\nDeployment complete."
    result = extract_prose(text)
    assert "git push" not in result
    assert "npm install" not in result
    assert "decided to deploy" in result
    assert "Deployment complete" in result


def test_removes_import_statements():
    text = "The module works.\nimport os\nfrom pathlib import Path\nAll tests pass."
    result = extract_prose(text)
    assert "import os" not in result
    assert "from pathlib" not in result
    assert "module works" in result


def test_removes_low_alpha_lines():
    text = "Good line here.\n>>>>>>>>>>>>>>>>>\n{'key': 123, 'val': 456}\nAnother good line."
    result = extract_prose(text)
    assert ">>>>>" not in result
    assert "Good line" in result


def test_preserves_prose_only():
    text = "We chose React for the frontend.\nIt was a tough decision but the ecosystem won us over."
    result = extract_prose(text)
    assert "chose React" in result
    assert "tough decision" in result


def test_empty_input():
    assert extract_prose("") == ""


def test_all_code_returns_empty():
    text = "import os\nimport sys\ndef main():\n    pass"
    result = extract_prose(text)
    assert result.strip() == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /c/Projeler/mnemos && python -m pytest tests/test_prose.py -v 2>&1 | head -20`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement prose extraction**

Create `mnemos/prose.py`:

```python
"""Prose extraction — filter out code, shell commands, and non-human text."""
from __future__ import annotations

import re

# Shell command prefixes
_SHELL_PREFIXES = (
    "$ ", "% ", "> ", "# ", "cd ", "git ", "pip ", "npm ", "yarn ",
    "python ", "node ", "cargo ", "go ", "make ", "docker ", "kubectl ",
    "brew ", "apt ", "sudo ", "curl ", "wget ", "chmod ", "mkdir ",
    "ls ", "cat ", "echo ", "export ", "source ", "rm ", "cp ", "mv ",
)

# Programming constructs (start of line)
_CODE_PATTERNS = re.compile(
    r"^\s*("
    r"import |from .+ import |def |class |return |yield |async |await |"
    r"if __name__|raise |try:|except |finally:|with |elif |else:|"
    r"const |let |var |function |export |module\.|require\(|"
    r"public |private |protected |static |void |int |string |"
    r"@\w+|#include|using |namespace "
    r")",
    re.MULTILINE,
)

# Fenced code block markers
_CODE_FENCE = re.compile(r"^```", re.MULTILINE)


def extract_prose(text: str) -> str:
    """Remove code lines, keep only human-written prose.

    Filters:
    1. Fenced code blocks (``` ... ```)
    2. Shell commands (lines starting with $, git, pip, etc.)
    3. Programming constructs (import, def, class, return, etc.)
    4. Low-alpha lines (<40% alphabetic characters)
    """
    if not text:
        return ""

    # Step 1: Remove fenced code blocks
    text = _remove_code_blocks(text)

    # Step 2: Filter line by line
    lines = text.splitlines()
    kept: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            kept.append("")
            continue

        # Skip shell commands
        if any(stripped.startswith(p) for p in _SHELL_PREFIXES):
            continue

        # Skip programming constructs
        if _CODE_PATTERNS.match(stripped):
            continue

        # Skip low-alpha lines
        if not _is_prose_line(stripped):
            continue

        kept.append(line)

    # Clean up multiple blank lines
    result = "\n".join(kept)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def _remove_code_blocks(text: str) -> str:
    """Remove fenced code blocks (```...```)."""
    parts = _CODE_FENCE.split(text)
    # Odd-indexed parts are inside code fences
    kept = [parts[i] for i in range(0, len(parts), 2)]
    return "".join(kept)


def _is_prose_line(line: str) -> bool:
    """Return True if line has >= 40% alphabetic characters."""
    if not line:
        return False
    alpha_count = sum(1 for c in line if c.isalpha())
    return (alpha_count / len(line)) >= 0.4
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /c/Projeler/mnemos && python -m pytest tests/test_prose.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add mnemos/prose.py tests/test_prose.py
git commit -m "feat: prose extraction — filter code lines from mining input"
```

---

## Task 3: Room Detection (room_detector.py)

**Files:**
- Create: `mnemos/patterns/rooms.yaml`
- Create: `mnemos/room_detector.py`
- Create: `tests/test_room_detector.py`

- [ ] **Step 1: Create room patterns YAML**

Create `mnemos/patterns/rooms.yaml`:

```yaml
# Room detection patterns — 13 categories, 72+ folder patterns + keywords
rooms:
  frontend:
    folders: [frontend, front-end, front_end, client, ui, views, components, pages]
    keywords: [react, vue, angular, css, html, dom, render, component, tailwind, jsx, tsx, styled, layout, responsive]

  backend:
    folders: [backend, back-end, back_end, server, api, routes, services, controllers, models, database, db]
    keywords: [endpoint, middleware, query, schema, migration, orm, rest, graphql, express, fastapi, django, supabase, postgres]

  documentation:
    folders: [docs, doc, documentation, wiki, readme, notes]
    keywords: [document, readme, changelog, guide, tutorial, reference, specification]

  design:
    folders: [design, designs, mockups, wireframes, assets, storyboard]
    keywords: [figma, sketch, wireframe, mockup, prototype, user experience, ux, ui design]

  costs:
    folders: [costs, cost, budget, finance, financial, pricing, invoices, accounting]
    keywords: [budget, price, cost, invoice, billing, payment, subscription, expense, revenue]

  meetings:
    folders: [meetings, meeting, calls, meeting_notes, standup, minutes]
    keywords: [meeting, call, standup, discussed, attendees, agenda, action items, follow-up, retrospective]

  team:
    folders: [team, staff, hr, hiring, employees, people]
    keywords: [hire, interview, onboard, team, role, responsibility, performance, review]

  research:
    folders: [research, references, reading, papers]
    keywords: [research, study, paper, article, benchmark, comparison, analysis, evaluate]

  planning:
    folders: [planning, roadmap, strategy, specs, requirements]
    keywords: [plan, roadmap, milestone, deadline, priority, sprint, scope, spec, requirement, epic, story]

  testing:
    folders: [tests, test, testing, qa]
    keywords: [test, assert, fixture, mock, coverage, e2e, integration, unit test, regression]

  scripts:
    folders: [scripts, tools, utils]
    keywords: [script, utility, helper, automation, batch, cron, pipeline]

  configuration:
    folders: [config, configs, settings, infrastructure, infra, deploy]
    keywords: [config, environment, deploy, docker, kubernetes, ci, cd, pipeline, terraform, nginx]

  security:
    folders: [security, auth, authentication, authorization]
    keywords: [auth, login, password, token, jwt, oauth, rls, permission, role, encryption, ssl]
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_room_detector.py`:

```python
"""Tests for mnemos.room_detector — folder + keyword room detection."""
from pathlib import Path

from mnemos.room_detector import detect_room


def test_detect_from_folder_path():
    """Folder name 'frontend' maps to room 'frontend'."""
    assert detect_room(Path("/project/frontend/App.tsx"), "") == "frontend"


def test_detect_from_nested_folder():
    """Nested folder 'api/routes' maps to 'backend'."""
    assert detect_room(Path("/project/api/routes/users.py"), "") == "backend"


def test_detect_from_keywords():
    """Content keywords override when no folder match."""
    text = "We discussed the React component architecture and Tailwind CSS integration."
    assert detect_room(Path("/project/notes/session.md"), text) == "frontend"


def test_detect_from_keyword_scoring():
    """Higher keyword count wins."""
    text = "Deploy the docker container. Configure kubernetes. Set up the CI/CD pipeline. Terraform init."
    assert detect_room(Path("/project/notes.md"), text) == "configuration"


def test_fallback_to_general():
    """No match returns 'general'."""
    assert detect_room(Path("/random/file.md"), "Nothing specific here.") == "general"


def test_folder_match_beats_keyword():
    """Folder match takes priority over keyword scoring."""
    text = "Many react components discussed"
    # File is in 'meetings' folder, even though content mentions react
    assert detect_room(Path("/project/meetings/2026-04-10.md"), text) == "meetings"


def test_case_insensitive_folder():
    """Folder matching is case-insensitive."""
    assert detect_room(Path("/project/Frontend/App.tsx"), "") == "frontend"


def test_hyphen_underscore_variants():
    """front-end and front_end both map to frontend."""
    assert detect_room(Path("/project/front-end/index.html"), "") == "frontend"
    assert detect_room(Path("/project/front_end/index.html"), "") == "frontend"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /c/Projeler/mnemos && python -m pytest tests/test_room_detector.py -v 2>&1 | head -20`
Expected: FAIL

- [ ] **Step 4: Implement room detector**

Create `mnemos/room_detector.py`:

```python
"""Room detection — folder pattern + keyword scoring for room assignment."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_PATTERNS_FILE = Path(__file__).parent / "patterns" / "rooms.yaml"
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "dist", "build", ".obsidian"}

# Loaded once at module level
_rooms_config: dict[str, Any] | None = None


def _load_rooms() -> dict[str, Any]:
    global _rooms_config
    if _rooms_config is None:
        with _PATTERNS_FILE.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        _rooms_config = data.get("rooms", {})
    return _rooms_config


def detect_room(filepath: Path, text: str, max_text_scan: int = 3000) -> str:
    """Detect room from file path folders + content keywords.

    Algorithm:
    1. Match folder names in filepath against folder patterns (case-insensitive)
    2. If no folder match: score first max_text_scan chars against keyword lists
    3. Highest scoring room wins; fallback to 'general'
    """
    rooms = _load_rooms()

    # Stage 1: Folder matching
    folder_match = _match_folders(filepath, rooms)
    if folder_match:
        return folder_match

    # Stage 2: Keyword scoring
    if text:
        keyword_match = _score_keywords(text[:max_text_scan], rooms)
        if keyword_match:
            return keyword_match

    return "general"


def _match_folders(filepath: Path, rooms: dict) -> str | None:
    """Match path components against room folder patterns."""
    # Normalize path parts to lowercase
    parts = [p.lower().replace("-", "_") for p in filepath.parts if p not in _SKIP_DIRS]

    for room_name, config in rooms.items():
        folders = config.get("folders", [])
        normalized_folders = [f.lower().replace("-", "_") for f in folders]
        for part in parts:
            if part in normalized_folders:
                return room_name
    return None


def _score_keywords(text: str, rooms: dict) -> str | None:
    """Score text against keyword lists, return highest scoring room."""
    text_lower = text.lower()
    best_room: str | None = None
    best_score = 0

    for room_name, config in rooms.items():
        keywords = config.get("keywords", [])
        score = sum(1 for kw in keywords if kw.lower() in text_lower)
        if score > best_score:
            best_score = score
            best_room = room_name

    # Require at least 2 keyword hits to avoid false positives
    return best_room if best_score >= 2 else None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /c/Projeler/mnemos && python -m pytest tests/test_room_detector.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add mnemos/patterns/rooms.yaml mnemos/room_detector.py tests/test_room_detector.py
git commit -m "feat: room detection — 72+ folder patterns + keyword scoring"
```

---

## Task 4: Entity Detection (entity_detector.py)

**Files:**
- Create: `mnemos/entity_detector.py`
- Create: `tests/test_entity_detector.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_entity_detector.py`:

```python
"""Tests for mnemos.entity_detector — heuristic entity detection."""
from mnemos.entity_detector import EntityDetector


def test_detect_person_by_dialogue():
    text = (
        "> Enver: What about the approval flow?\n"
        "We discussed it with Enver and he said the flow looks good.\n"
        "Enver asked about the timeline.\n"
        "Thanks Enver for the review.\n"
    )
    detector = EntityDetector()
    result = detector.detect(text)
    assert "Enver" in result["persons"]


def test_detect_project_by_code_refs():
    text = (
        "ProcureTrack uses Next.js 14 with Supabase.\n"
        "We shipped ProcureTrack v2 last week.\n"
        "The ProcureTrack architecture is modular.\n"
        "Run: import ProcureTrack from './lib'\n"
        "Check ProcureTrack.py for details.\n"
    )
    detector = EntityDetector()
    result = detector.detect(text)
    assert "ProcureTrack" in result["projects"]


def test_ignores_stopwords():
    text = "The Python code uses This and That pattern. The React component works."
    detector = EntityDetector()
    result = detector.detect(text)
    assert "The" not in result["persons"]
    assert "The" not in result["projects"]
    assert "This" not in result["persons"]


def test_requires_3_occurrences():
    text = "Alice said hello."
    detector = EntityDetector()
    result = detector.detect(text)
    # Only 1 occurrence, should not be detected
    assert "Alice" not in result["persons"]


def test_turkish_person_signals():
    text = (
        "Enver Bey toplantida konustu.\n"
        "Enver dedi ki onay akisi hazir.\n"
        "Enver Bey'e sordum, tamam dedi.\n"
        "Enver istedi ki deadline uzasin.\n"
    )
    detector = EntityDetector()
    result = detector.detect(text)
    assert "Enver" in result["persons"]


def test_empty_text():
    detector = EntityDetector()
    result = detector.detect("")
    assert result == {"persons": [], "projects": [], "uncertain": []}


def test_mixed_entities():
    text = (
        "> Tugra: Let's deploy Mnemos today.\n"
        "Tugra said the Mnemos architecture is ready.\n"
        "Tugra asked about the Mnemos v0.1 release.\n"
        "Building Mnemos took two weeks.\n"
        "Tugra wants to ship Mnemos this week.\n"
    )
    detector = EntityDetector()
    result = detector.detect(text)
    assert "Tugra" in result["persons"]
    assert "Mnemos" in result["projects"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /c/Projeler/mnemos && python -m pytest tests/test_entity_detector.py -v 2>&1 | head -20`
Expected: FAIL

- [ ] **Step 3: Implement entity detector**

Create `mnemos/entity_detector.py`:

```python
"""Entity detection — heuristic two-pass person/project classification."""
from __future__ import annotations

import re
from collections import Counter

# 200+ stopwords: common English words, programming keywords, Turkish common words
STOPWORDS = {
    # English common
    "The", "This", "That", "These", "Those", "What", "When", "Where", "Which",
    "Who", "How", "Why", "Just", "Also", "But", "And", "For", "Not", "All",
    "Can", "Had", "Her", "Was", "One", "Our", "Out", "Are", "Has", "His",
    "May", "New", "Now", "Old", "See", "Way", "Day", "Did", "Get", "Got",
    "Let", "Say", "She", "Too", "Use", "Yes", "Yet", "Any", "Each", "Few",
    "Its", "Own", "Per", "Set", "Try", "Two", "Add", "Big", "End", "Far",
    "Run", "Top", "Will", "With", "About", "After", "Again", "Being",
    "Could", "Every", "First", "Found", "Great", "Here", "Into", "Last",
    "Like", "Long", "Look", "Made", "Make", "Many", "Most", "Much", "Must",
    "Need", "Next", "Only", "Over", "Part", "Some", "Such", "Sure", "Take",
    "Than", "Them", "Then", "They", "Time", "Upon", "Very", "Want", "Well",
    "Were", "Work", "Would", "Been", "Best", "Both", "Come", "Done",
    "Down", "Even", "Give", "Good", "Have", "Help", "High", "Home",
    "Keep", "Kind", "Know", "Left", "Life", "Line", "Live", "More",
    "Move", "Name", "Open", "Play", "Point", "Read", "Real", "Same",
    "Should", "Show", "Side", "Small", "Still", "Thing", "Think", "Turn",
    "Under", "Using", "World", "Year", "Your", "Back", "Call", "Case",
    "Change", "Check", "Close", "Data", "Does", "Else", "File", "Find",
    "Form", "Full", "Went", "When", "While", "True", "False", "None",
    "Null", "Start", "Stop", "Test", "Type", "Note",
    # Programming
    "Python", "React", "JavaScript", "TypeScript", "HTML", "CSS", "JSON",
    "YAML", "SQL", "HTTP", "HTTPS", "API", "REST", "URL", "CLI", "GUI",
    "TODO", "FIXME", "NOTE", "HACK", "WARNING", "ERROR", "DEBUG", "INFO",
    "README", "LICENSE", "CHANGELOG",
    # Turkish common
    "Bir", "Biz", "Ben", "Sen", "Siz", "Ama", "Hem", "Ile",
    "Daha", "Icin", "Gibi", "Sonra", "Once", "Kadar",
}

# Lowercase set for case-insensitive lookup
_STOPWORDS_LOWER = {w.lower() for w in STOPWORDS}

# Person signal patterns
_PERSON_DIALOGUE = re.compile(r"(?:^|\n)\s*>?\s*(\w+)\s*:", re.MULTILINE)
_PERSON_SAID = re.compile(
    r"\b(\w+)\s+(?:said|asked|told|replied|mentioned|thinks|wants|suggested|"
    r"dedi|sordu|istedi|yapti|konustu|anlatti)\b",
    re.IGNORECASE,
)
_PERSON_ADDRESS = re.compile(
    r"\b(?:hey|thanks|thank you|hi|hello|dear|merhaba|tesekkurler)\s+(\w+)\b",
    re.IGNORECASE,
)
_PERSON_TURKISH_TITLE = re.compile(r"\b(\w+)\s+(?:Bey|Hanim|Hoca|hocam)\b")

# Project signal patterns
_PROJECT_VERB = re.compile(
    r"\b(\w+)\s+(?:uses|architecture|pipeline|system|framework|platform|"
    r"module|library|package|codebase)\b",
    re.IGNORECASE,
)
_PROJECT_VERSION = re.compile(r"\b(\w+)\s+v\d", re.IGNORECASE)
_PROJECT_CODE = re.compile(r"\b(?:import|from)\s+(\w+)|(\w+)\.(?:py|js|ts|go|rs)\b")
_PROJECT_BUILD = re.compile(
    r"\b(?:building|built|shipped|launched|deployed|installed)\s+(\w+)\b",
    re.IGNORECASE,
)


class EntityDetector:
    """API-free entity detection using heuristic scoring."""

    def detect(self, text: str, max_results: int = 15) -> dict:
        """Detect persons, projects, and uncertain entities.

        Returns: {"persons": [...], "projects": [...], "uncertain": [...]}
        """
        if not text.strip():
            return {"persons": [], "projects": [], "uncertain": []}

        # Pass 1: Find candidates (capitalized words appearing 3+ times)
        candidates = self._find_candidates(text)

        # Pass 2: Classify each candidate
        persons: list[str] = []
        projects: list[str] = []
        uncertain: list[str] = []

        for candidate in candidates:
            category, _confidence = self._classify(candidate, text)
            if category == "person":
                persons.append(candidate)
            elif category == "project":
                projects.append(candidate)
            else:
                uncertain.append(candidate)

        return {
            "persons": persons[:max_results],
            "projects": projects[:min(10, max_results)],
            "uncertain": uncertain[:min(8, max_results)],
        }

    def _find_candidates(self, text: str) -> list[str]:
        """Pass 1: Find capitalized words appearing 3+ times, filter stopwords."""
        # Find all capitalized words (3+ chars)
        words = re.findall(r"\b([A-Z][a-zA-Z]{2,})\b", text)
        counts = Counter(words)

        candidates = []
        for word, count in counts.most_common():
            if count >= 3 and word.lower() not in _STOPWORDS_LOWER:
                candidates.append(word)

        return candidates

    def _classify(self, candidate: str, text: str) -> tuple[str, float]:
        """Pass 2: Classify candidate as person, project, or uncertain."""
        person_score = 0
        person_signals = set()
        project_score = 0
        project_signals = set()

        # Person signals
        for m in _PERSON_DIALOGUE.finditer(text):
            if m.group(1) == candidate:
                person_score += 3
                person_signals.add("dialogue")

        for m in _PERSON_SAID.finditer(text):
            if m.group(1) == candidate:
                person_score += 2
                person_signals.add("action_verb")

        for m in _PERSON_ADDRESS.finditer(text):
            if m.group(1) == candidate:
                person_score += 4
                person_signals.add("direct_address")

        for m in _PERSON_TURKISH_TITLE.finditer(text):
            if m.group(1) == candidate:
                person_score += 3
                person_signals.add("turkish_title")

        # Pronoun proximity (he/she within 3 lines)
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if candidate in line:
                window = " ".join(lines[max(0, i - 1):i + 2]).lower()
                if re.search(r"\b(he|she|they|him|her|onun|ona)\b", window):
                    person_score += 2
                    person_signals.add("pronoun")
                    break

        # Project signals
        for m in _PROJECT_VERB.finditer(text):
            if m.group(1) == candidate:
                project_score += 2
                project_signals.add("architecture_verb")

        for m in _PROJECT_VERSION.finditer(text):
            if m.group(1) == candidate:
                project_score += 3
                project_signals.add("version")

        for m in _PROJECT_CODE.finditer(text):
            matched = m.group(1) or m.group(2)
            if matched == candidate:
                project_score += 3
                project_signals.add("code_ref")

        for m in _PROJECT_BUILD.finditer(text):
            if m.group(1) == candidate:
                project_score += 2
                project_signals.add("build_verb")

        # Classification
        total = person_score + project_score
        if total == 0:
            return "uncertain", 0.5

        person_ratio = person_score / total

        if person_ratio >= 0.7 and len(person_signals) >= 2 and person_score >= 5:
            confidence = min(0.99, 0.5 + person_ratio * 0.5)
            return "person", confidence
        elif person_ratio <= 0.3 and project_score >= 4:
            confidence = min(0.99, 0.5 + (1 - person_ratio) * 0.5)
            return "project", confidence
        else:
            return "uncertain", 0.5
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /c/Projeler/mnemos && python -m pytest tests/test_entity_detector.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add mnemos/entity_detector.py tests/test_entity_detector.py
git commit -m "feat: heuristic entity detection — two-pass person/project classification"
```

---

## Task 5: Expanded Pattern Files (en.yaml + tr.yaml)

**Files:**
- Modify: `mnemos/patterns/en.yaml`
- Modify: `mnemos/patterns/tr.yaml`

- [ ] **Step 1: Update en.yaml with 87+ markers**

Overwrite `mnemos/patterns/en.yaml`:

```yaml
# English mining patterns — 87 markers across 4 halls
decisions:
  - "we decided"
  - "we chose"
  - "we picked"
  - "we went with"
  - "let's use"
  - "decision is"
  - "agreed to"
  - "because"
  - "trade-off"
  - "architecture"
  - "approach"
  - "configure"
  - "the plan is"
  - "going forward"
  - "from now on"
  - "switched to"
  - "migrated to"
  - "instead of"
  - "better than"
  - "opted for"
  - "settled on"

preferences:
  - "I prefer"
  - "we prefer"
  - "always use"
  - "never use"
  - "never do"
  - "best practice"
  - "my rule is"
  - "don't like"
  - "hate when"
  - "love when"
  - "snake_case"
  - "camelCase"
  - "tabs"
  - "spaces"
  - "convention"
  - "standard"

problems:
  - "bug"
  - "error"
  - "crash"
  - "broke"
  - "doesn't work"
  - "root cause"
  - "the fix"
  - "workaround"
  - "fixed"
  - "solution is"
  - "failed"
  - "broken"
  - "stuck"
  - "regression"
  - "flaky"
  - "timeout"
  - "memory leak"

events:
  - "shipped"
  - "completed"
  - "launched"
  - "deployed"
  - "it works"
  - "figured out"
  - "migrated"
  - "breakthrough"
  - "finally"
  - "released"
  - "merged"
  - "passed"
  - "went live"
  - "first time"
  - "milestone"
  - "done"
  - "finished"
  - "resolved"
  - "got it working"
  - "up and running"
  - "production ready"
  - "all tests pass"
  - "PR approved"
  - "code review done"
  - "demo ready"
  - "cut the release"
  - "tagged"
  - "published"
  - "v1.0"
  - "v2.0"
  - "2x faster"
  - "0 errors"
  - "100%"
```

- [ ] **Step 2: Update tr.yaml with ~80 markers**

Overwrite `mnemos/patterns/tr.yaml`:

```yaml
# Turkish mining patterns — ~80 markers across 4 halls
decisions:
  - "karar verdik"
  - "karar aldik"
  - "karar aldık"
  - "ile gittik"
  - "ile gitmeye karar"
  - "secimini yaptik"
  - "tercih ettik"
  - "kullanmaya karar"
  - "cunku"
  - "çünkü"
  - "yaklasim"
  - "yaklaşım"
  - "bundan sonra"
  - "artik"
  - "artık"
  - "gecis yaptik"
  - "yerine"
  - "daha iyi"
  - "secildi"
  - "seçildi"
  - "onaylandi"
  - "onaylandı"

preferences:
  - "her zaman"
  - "asla yapma"
  - "tercihimiz"
  - "tercihim"
  - "daha iyi olur"
  - "benim kuralim"
  - "sevmiyorum"
  - "hoslanmiyorum"
  - "hoşlanmıyorum"
  - "en iyi yontem"
  - "standart"
  - "konvansiyon"
  - "kurala gore"
  - "kurala göre"
  - "aliskanligi"
  - "alışkanlığı"

problems:
  - "hata"
  - "sorun"
  - "bug"
  - "bozuldu"
  - "calismadi"
  - "çalışmadı"
  - "cozum"
  - "çözüm"
  - "duzeltildi"
  - "düzeltildi"
  - "cozum olarak"
  - "gecici cozum"
  - "geçici çözüm"
  - "kriz"
  - "patladi"
  - "patladı"
  - "timeout"
  - "bellek sorunu"
  - "crash"
  - "fail"

events:
  - "tamamlandi"
  - "tamamlandı"
  - "bitti"
  - "yayinlandi"
  - "yayınlandı"
  - "basladik"
  - "başladık"
  - "olusturuldu"
  - "oluşturuldu"
  - "eklendi"
  - "deploy edildi"
  - "merge edildi"
  - "yayina alindi"
  - "yayına alındı"
  - "ilk kez"
  - "basarili"
  - "başarılı"
  - "calisiyor"
  - "çalışıyor"
  - "gecti"
  - "geçti"
  - "hazir"
  - "hazır"
  - "cozuldu"
  - "çözüldü"
  - "cikti"
  - "çıktı"
```

- [ ] **Step 3: Run existing miner tests (must not break)**

Run: `cd /c/Projeler/mnemos && python -m pytest tests/test_miner.py -v`
Expected: ALL PASS (patterns are additive)

- [ ] **Step 4: Commit**

```bash
git add mnemos/patterns/en.yaml mnemos/patterns/tr.yaml
git commit -m "feat: expand mining patterns — 87 EN + 80 TR markers across 4 halls"
```

---

## Task 6: Conversation Normalizer (normalizer.py)

**Files:**
- Create: `mnemos/normalizer.py`
- Create: `tests/test_normalizer.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_normalizer.py`:

```python
"""Tests for mnemos.normalizer — conversation format detection + normalization."""
import json
import textwrap

from mnemos.normalizer import normalize_text, detect_format


def test_detect_claude_code_jsonl():
    lines = [
        json.dumps({"type": "human", "message": {"content": "Hello"}}),
        json.dumps({"type": "assistant", "message": {"content": "Hi there"}}),
    ]
    text = "\n".join(lines)
    assert detect_format(text) == "claude_code_jsonl"


def test_detect_chatgpt_json():
    data = {"title": "Chat", "mapping": {"node1": {"message": {"author": {"role": "user"}, "content": {"parts": ["Hello"]}}}}}
    text = json.dumps(data)
    assert detect_format(text) == "chatgpt_json"


def test_detect_slack_json():
    data = [{"type": "message", "user": "U123", "text": "Hello"}]
    text = json.dumps(data)
    assert detect_format(text) == "slack_json"


def test_detect_plain_text():
    assert detect_format("Just some regular text.\nNothing special.") == "plain_text"


def test_normalize_claude_code_jsonl():
    lines = [
        json.dumps({"type": "human", "message": {"content": "What is RLS?"}}),
        json.dumps({"type": "assistant", "message": {"content": "Row Level Security is..."}}),
    ]
    text = "\n".join(lines)
    result = normalize_text(text)
    assert "> What is RLS?" in result
    assert "Row Level Security is..." in result


def test_normalize_chatgpt_json():
    data = {
        "title": "Test",
        "mapping": {
            "root": {"id": "root", "parent": None, "children": ["msg1"], "message": None},
            "msg1": {"id": "msg1", "parent": "root", "children": ["msg2"],
                     "message": {"author": {"role": "user"}, "content": {"parts": ["Hello"]}}},
            "msg2": {"id": "msg2", "parent": "msg1", "children": [],
                     "message": {"author": {"role": "assistant"}, "content": {"parts": ["Hi!"]}}},
        },
    }
    text = json.dumps(data)
    result = normalize_text(text)
    assert "> Hello" in result
    assert "Hi!" in result


def test_normalize_slack_json():
    data = [
        {"type": "message", "user": "U001", "text": "Hey team"},
        {"type": "message", "user": "U002", "text": "Hello!"},
    ]
    text = json.dumps(data)
    result = normalize_text(text)
    assert "> Hey team" in result
    assert "Hello!" in result


def test_normalize_plain_text_passthrough():
    text = "Regular markdown content.\n\n## Section\n\nSome text."
    result = normalize_text(text)
    assert result == text


def test_normalize_merges_consecutive_assistant():
    """Consecutive assistant messages (tool loops) are merged."""
    lines = [
        json.dumps({"type": "human", "message": {"content": "Fix the bug"}}),
        json.dumps({"type": "assistant", "message": {"content": "Let me check..."}}),
        json.dumps({"type": "assistant", "message": {"content": "Found it. The fix is..."}}),
    ]
    text = "\n".join(lines)
    result = normalize_text(text)
    # Should be merged into one assistant response
    assert result.count("> Fix the bug") == 1
    assert "Let me check..." in result
    assert "Found it." in result


def test_tool_result_truncation():
    """Long tool results are truncated."""
    long_output = "\n".join([f"line {i}" for i in range(100)])
    lines = [
        json.dumps({"type": "human", "message": {"content": "Run tests"}}),
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "pytest"}},
            {"type": "tool_result", "tool_use_id": "t1", "content": long_output},
            {"type": "text", "text": "All tests passed."},
        ]}}),
    ]
    text = "\n".join(lines)
    result = normalize_text(text)
    # Should be truncated, not all 100 lines
    assert "All tests passed" in result
    result_lines = result.splitlines()
    assert len(result_lines) < 80
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /c/Projeler/mnemos && python -m pytest tests/test_normalizer.py -v 2>&1 | head -20`
Expected: FAIL

- [ ] **Step 3: Implement normalizer**

Create `mnemos/normalizer.py`:

```python
"""Conversation format normalizer — detect and convert 5 formats to standard transcript."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def normalize_file(filepath: Path) -> str:
    """Read a file, detect its format, and normalize to transcript."""
    text = filepath.read_text(encoding="utf-8", errors="replace")
    return normalize_text(text)


def normalize_text(text: str) -> str:
    """Detect format and normalize to standard transcript.

    Output format:
        > user message
        assistant response

        > next user
        next assistant
    """
    fmt = detect_format(text)

    if fmt == "claude_code_jsonl":
        return _normalize_claude_code_jsonl(text)
    elif fmt == "chatgpt_json":
        return _normalize_chatgpt_json(text)
    elif fmt == "slack_json":
        return _normalize_slack_json(text)
    else:
        return text


def detect_format(text: str) -> str:
    """Detect conversation format from content."""
    stripped = text.strip()

    # Claude Code JSONL: each line is a JSON object with "type" field
    if stripped.startswith("{"):
        first_line = stripped.split("\n", 1)[0]
        try:
            obj = json.loads(first_line)
            if isinstance(obj, dict) and "type" in obj and "message" in obj:
                return "claude_code_jsonl"
        except json.JSONDecodeError:
            pass

    # Try full JSON parse for ChatGPT and Slack
    try:
        data = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return "plain_text"

    # ChatGPT: object with "mapping" key
    if isinstance(data, dict) and "mapping" in data:
        return "chatgpt_json"

    # Slack: array of objects with "type": "message"
    if isinstance(data, list) and data and isinstance(data[0], dict):
        if data[0].get("type") == "message":
            return "slack_json"

    return "plain_text"


# ---------------------------------------------------------------------------
# Format-specific normalizers
# ---------------------------------------------------------------------------


def _normalize_claude_code_jsonl(text: str) -> str:
    """Parse Claude Code JSONL export to transcript."""
    messages: list[tuple[str, str]] = []

    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        msg_type = obj.get("type", "")
        content = _extract_content(obj.get("message", {}).get("content", ""))

        if not content.strip():
            continue

        role = "user" if msg_type in ("human", "user") else "assistant"
        messages.append((role, content))

    return _messages_to_transcript(_merge_consecutive_assistant(messages))


def _normalize_chatgpt_json(text: str) -> str:
    """Parse ChatGPT JSON export to transcript."""
    data = json.loads(text)
    mapping = data.get("mapping", {})

    # Find root node (parent=None, no message)
    root_id = None
    for node_id, node in mapping.items():
        if node.get("parent") is None:
            root_id = node_id
            break

    if root_id is None:
        return text

    # Traverse tree via children
    messages: list[tuple[str, str]] = []
    queue = [root_id]
    visited = set()

    while queue:
        node_id = queue.pop(0)
        if node_id in visited:
            continue
        visited.add(node_id)

        node = mapping.get(node_id, {})
        msg = node.get("message")

        if msg:
            role_raw = msg.get("author", {}).get("role", "")
            parts = msg.get("content", {}).get("parts", [])
            content = " ".join(str(p) for p in parts if isinstance(p, str))

            if content.strip() and role_raw in ("user", "assistant"):
                role = "user" if role_raw == "user" else "assistant"
                messages.append((role, content))

        for child_id in node.get("children", []):
            queue.append(child_id)

    return _messages_to_transcript(messages)


def _normalize_slack_json(text: str) -> str:
    """Parse Slack JSON export to transcript."""
    data = json.loads(text)
    messages: list[tuple[str, str]] = []

    # Alternate roles for different speakers
    speakers: dict[str, str] = {}
    role_toggle = ["user", "assistant"]
    role_idx = 0

    for msg in data:
        if msg.get("type") != "message":
            continue
        user = msg.get("user") or msg.get("username", "unknown")
        content = msg.get("text", "")

        if not content.strip():
            continue

        if user not in speakers:
            speakers[user] = role_toggle[role_idx % 2]
            role_idx += 1

        messages.append((speakers[user], content))

    return _messages_to_transcript(messages)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_content(content: Any) -> str:
    """Extract text from various content formats."""
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                block_type = block.get("type", "")
                if block_type == "text":
                    parts.append(block.get("text", ""))
                elif block_type == "tool_use":
                    name = block.get("name", "tool")
                    inp = block.get("input", {})
                    cmd = inp.get("command", "") if isinstance(inp, dict) else ""
                    if cmd:
                        parts.append(f"[{name}: {cmd}]")
                    else:
                        parts.append(f"[{name}]")
                elif block_type == "tool_result":
                    raw = block.get("content", "")
                    truncated = _truncate_tool_result(str(raw), block.get("tool_use_id", ""))
                    if truncated:
                        parts.append(f"-> {truncated}")
        return "\n".join(parts)

    if isinstance(content, dict):
        return content.get("text", "")

    return str(content)


def _truncate_tool_result(text: str, tool_id: str = "", max_lines: int = 20) -> str:
    """Truncate long tool results — keep head + tail."""
    lines = text.splitlines()
    if len(lines) <= max_lines * 2:
        return text

    head = lines[:max_lines]
    tail = lines[-max_lines:]
    skipped = len(lines) - max_lines * 2
    return "\n".join(head) + f"\n... ({skipped} lines truncated) ...\n" + "\n".join(tail)


def _merge_consecutive_assistant(messages: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Merge consecutive assistant messages into one."""
    if not messages:
        return []

    merged: list[tuple[str, str]] = [messages[0]]
    for role, content in messages[1:]:
        if role == "assistant" and merged[-1][0] == "assistant":
            merged[-1] = ("assistant", merged[-1][1] + "\n" + content)
        else:
            merged.append((role, content))

    return merged


def _messages_to_transcript(messages: list[tuple[str, str]]) -> str:
    """Convert (role, content) pairs to transcript format."""
    parts: list[str] = []
    for role, content in messages:
        if role == "user":
            parts.append(f"> {content}")
        else:
            parts.append(content)

    return "\n\n".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /c/Projeler/mnemos && python -m pytest tests/test_normalizer.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add mnemos/normalizer.py tests/test_normalizer.py
git commit -m "feat: conversation normalizer — Claude Code, ChatGPT, Slack, plain text"
```

---

## Task 7: Miner Overhaul (exchange-pair chunking + scoring + integration)

**Files:**
- Modify: `mnemos/miner.py`
- Modify: `tests/test_miner.py`

- [ ] **Step 1: Write failing tests for exchange-pair chunking**

Add to `tests/test_miner.py`:

```python
from mnemos.miner import chunk_exchanges, classify_segment


def test_chunk_exchanges_basic():
    """Each exchange stays as one chunk."""
    transcript = "> What is RLS?\nRow Level Security controls access.\n\n> How to enable?\nUse ALTER TABLE."
    chunks = chunk_exchanges(transcript)
    assert len(chunks) == 2
    assert "> What is RLS?" in chunks[0]
    assert "Row Level Security" in chunks[0]
    assert "> How to enable?" in chunks[1]


def test_chunk_exchanges_large_response():
    """Long response gets split but user question stays in first chunk."""
    user = "> Tell me everything about databases"
    response = "A " * 2000  # ~4000 chars, exceeds max_chunk=3000
    transcript = f"{user}\n{response}"
    chunks = chunk_exchanges(transcript, max_chunk=3000)
    assert len(chunks) >= 2
    assert chunks[0].startswith("> Tell me")  # User question in first chunk
    # All text preserved
    total_len = sum(len(c) for c in chunks)
    assert total_len >= len(transcript) - 10  # Allow for whitespace


def test_chunk_exchanges_non_conversation():
    """Non-conversation text returns None (caller should use paragraph chunking)."""
    text = "Regular markdown without any > markers.\n\nJust paragraphs."
    result = chunk_exchanges(text)
    assert result is None


def test_classify_segment_decision():
    """Text with decision markers classified as 'decisions'."""
    text = "We decided to use Supabase because of its RLS capabilities. The trade-off was worth it."
    hall, confidence = classify_segment(text, "en")
    assert hall == "decisions"
    assert confidence >= 0.3


def test_classify_segment_problem():
    """Problem markers detected."""
    text = "There's a critical bug in the auth module. The root cause is a race condition."
    hall, confidence = classify_segment(text, "en")
    assert hall == "problems"


def test_classify_segment_disambiguation():
    """Problem + 'fixed' disambiguates to events (milestone)."""
    text = "The crash bug was fixed yesterday. Got it working after a long debugging session."
    hall, confidence = classify_segment(text, "en")
    assert hall == "events"


def test_classify_segment_low_confidence():
    """Generic text returns None (below min_confidence)."""
    text = "Just a random sentence about nothing specific."
    hall, confidence = classify_segment(text, "en")
    assert hall is None


def test_classify_segment_turkish():
    """Turkish decision markers work."""
    text = "Supabase ile gitmeye karar verdik çünkü RLS desteği var."
    hall, confidence = classify_segment(text, "tr")
    assert hall == "decisions"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /c/Projeler/mnemos && python -m pytest tests/test_miner.py -v -k "exchange or classify" 2>&1 | head -20`
Expected: FAIL

- [ ] **Step 3: Add exchange-pair chunking and scoring to miner.py**

Add to `mnemos/miner.py` (keep existing code, add new functions):

```python
# Add these imports at the top
from mnemos.prose import extract_prose
from mnemos.room_detector import detect_room
from mnemos.entity_detector import EntityDetector

# Add these new functions:

def chunk_exchanges(transcript: str, max_chunk: int = 3000) -> list[str] | None:
    """Split transcript into exchange pairs (user question + assistant response).

    Returns None if text is not a conversation (fewer than 3 '>' markers).
    Each chunk boundary is at exchange boundaries.
    If a single exchange exceeds max_chunk, response is split but user
    question stays in the first chunk.
    """
    # Check if this is a conversation
    user_turns = [i for i, line in enumerate(transcript.splitlines())
                  if line.strip().startswith(">")]
    if len(user_turns) < 3:
        return None

    # Parse into exchanges
    lines = transcript.splitlines(keepends=True)
    exchanges: list[str] = []
    current: list[str] = []

    for line in lines:
        if line.strip().startswith(">") and current:
            # New user turn — flush previous exchange
            exchanges.append("".join(current))
            current = [line]
        else:
            current.append(line)

    if current:
        exchanges.append("".join(current))

    # Merge small exchanges, split large ones
    chunks: list[str] = []
    for exchange in exchanges:
        if len(exchange) <= max_chunk:
            chunks.append(exchange.strip())
        else:
            # Split large exchange — keep user question in first chunk
            ex_lines = exchange.splitlines(keepends=True)
            # Find where user turn ends
            user_end = 0
            for i, line in enumerate(ex_lines):
                if line.strip().startswith(">"):
                    user_end = i + 1
                else:
                    break

            user_part = "".join(ex_lines[:user_end])
            response_part = "".join(ex_lines[user_end:])

            # First chunk: user question + start of response
            remaining_space = max_chunk - len(user_part)
            if remaining_space > 0:
                first = user_part + response_part[:remaining_space]
                chunks.append(first.strip())
                rest = response_part[remaining_space:]
            else:
                chunks.append(user_part.strip())
                rest = response_part

            # Remaining response in subsequent chunks
            while rest:
                chunk = rest[:max_chunk]
                chunks.append(chunk.strip())
                rest = rest[max_chunk:]

    return [c for c in chunks if c]


def classify_segment(
    text: str,
    language: str,
    min_confidence: float = 0.3,
) -> tuple[str | None, float]:
    """Score text against hall markers, return (hall, confidence).

    Returns (None, 0.0) if below min_confidence threshold.
    Includes disambiguation: problem + resolution markers -> events.
    """
    patterns_dir = Path(__file__).parent / "patterns"
    pattern_file = patterns_dir / f"{language}.yaml"

    if not pattern_file.exists():
        return None, 0.0

    with pattern_file.open("r", encoding="utf-8") as fh:
        lang_patterns = yaml.safe_load(fh) or {}

    text_lower = text.lower()

    # Score each hall
    scores: dict[str, int] = {}
    for hall, markers in lang_patterns.items():
        if not isinstance(markers, list):
            continue
        score = sum(1 for marker in markers if marker.lower() in text_lower)
        scores[hall] = score

    if not scores or max(scores.values()) == 0:
        return None, 0.0

    # Length bonus
    text_len = len(text)
    bonus = 2 if text_len > 500 else (1 if text_len > 200 else 0)

    best_hall = max(scores, key=lambda h: scores[h] + bonus)
    best_score = scores[best_hall] + bonus

    # Disambiguation: problem + resolution -> events
    if best_hall == "problems":
        resolution_markers = ["fixed", "solved", "got it working", "resolved",
                              "duzeltildi", "düzeltildi", "cozuldu", "çözüldü"]
        if any(m in text_lower for m in resolution_markers):
            best_hall = "events"
            best_score = scores.get("events", 0) + bonus + 2

    confidence = min(1.0, best_score / 5.0)

    if confidence < min_confidence:
        return None, 0.0

    return best_hall, confidence
```

- [ ] **Step 4: Update mine_file to use new components**

Replace the `mine_file` method in the `Miner` class:

```python
def mine_file(self, filepath: Path, use_llm: bool = False) -> list[dict[str, Any]]:
    """Mine a file — returns list of memory fragment dicts.

    Pipeline:
    1. Detect if conversation format -> normalize
    2. Detect language
    3. Resolve wing (frontmatter > entity > path > General)
    4. Detect room (folder patterns > keyword scoring > general)
    5. Extract entities (heuristic two-pass)
    6. Filter prose (remove code lines)
    7. Chunk (exchange-pair for conversations, paragraph for other)
    8. Classify each chunk (scoring + disambiguation)
    """
    from mnemos.normalizer import normalize_file, detect_format

    meta, body = parse_frontmatter(filepath)

    # Step 1: Normalize conversation formats
    raw_text = filepath.read_text(encoding="utf-8", errors="replace")
    fmt = detect_format(raw_text)
    if fmt != "plain_text":
        from mnemos.normalizer import normalize_text
        body = normalize_text(raw_text)

    # Step 2: Language
    language = detect_language(body)

    # Step 3: Wing
    wing: str = meta.get("project") or ""
    if not wing:
        path_entities = extract_entities_from_path(filepath)
        wing = path_entities[0] if path_entities else "General"

    # Step 4: Room (new — folder + keyword detection)
    room = detect_room(filepath, body)
    # Override with frontmatter tags if available
    tags = meta.get("tags") or []
    if isinstance(tags, list) and tags:
        room = str(tags[0])

    # Step 5: Entities (new — heuristic detection)
    detector = EntityDetector()
    detected = detector.detect(body)
    entities: list[str] = extract_entities_from_path(filepath)
    entities.extend(detected["persons"])
    entities.extend(detected["projects"])
    entities.extend(_extract_wikilinks(body))
    if meta.get("project"):
        entities.append(str(meta["project"]))
    for tag in tags:
        entities.append(str(tag))
    entities = list(dict.fromkeys(entities))

    source = str(filepath)

    # Step 6: Filter prose (remove code)
    prose_text = extract_prose(body)

    # Step 7: Chunk
    exchange_chunks = chunk_exchanges(prose_text)

    if exchange_chunks is not None:
        # Conversation: use exchange-pair chunks
        raw_chunks = exchange_chunks
    else:
        # Non-conversation: paragraph chunking (existing logic)
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", prose_text) if p.strip()]
        raw_chunks = paragraphs if paragraphs else [prose_text]

    # Step 8: Classify each chunk
    results: list[dict[str, Any]] = []
    for chunk in raw_chunks:
        if not chunk.strip():
            continue

        hall, confidence = classify_segment(chunk, language)
        if hall is None:
            hall = "facts"  # fallback

        results.append({
            "wing": wing,
            "room": room,
            "hall": hall,
            "text": chunk,
            "entities": entities,
            "language": language,
            "source": source,
        })

    # Fallback: if no results, chunk whole body as facts
    if not results and body.strip():
        chunks = chunk_text(body)
        if not chunks:
            chunks = [body]
        for chunk in chunks:
            results.append({
                "wing": wing,
                "room": room,
                "hall": "facts",
                "text": chunk,
                "entities": entities,
                "language": language,
                "source": source,
            })

    return results
```

- [ ] **Step 5: Run ALL miner tests**

Run: `cd /c/Projeler/mnemos && python -m pytest tests/test_miner.py -v`
Expected: ALL PASS (old tests still work, new tests pass)

- [ ] **Step 6: Run full test suite**

Run: `cd /c/Projeler/mnemos && python -m pytest tests/ -v 2>&1 | tail -20`
Expected: ALL PASS (51+ existing tests + new tests)

- [ ] **Step 7: Commit**

```bash
git add mnemos/miner.py tests/test_miner.py
git commit -m "feat: miner overhaul — exchange-pair chunking, scoring, prose filter, detectors"
```

---

## Task 8: Server + CLI Integration

**Files:**
- Modify: `mnemos/server.py`
- Modify: `mnemos/cli.py`
- Modify: `mnemos/config.py`
- Modify: `tests/test_server.py`

- [ ] **Step 1: Update config.py with new fields**

Add to `MnemosConfig` dataclass:

```python
# In MnemosConfig, add after existing fields:
chunk_max_size: int = 3000
min_confidence: float = 0.3
```

- [ ] **Step 2: Write failing tests for raw indexing and rebuild**

Add to `tests/test_server.py`:

```python
def test_handle_mine_indexes_raw(app: MnemosApp) -> None:
    """Mining a file stores raw content in raw collection."""
    # Assumes sample_session_en fixture exists
    result = app.handle_mine(path="Sessions/")
    assert result["drawers_created"] > 0
    # Raw collection should have entries
    raw_stats = app.search_engine._raw.count()
    assert raw_stats > 0


def test_handle_search_collection_param(app: MnemosApp) -> None:
    """Search accepts collection parameter."""
    app.handle_mine(path="Sessions/")
    # Search raw only
    results = app.handle_search(query="test", collection="raw")
    assert isinstance(results, list)
    # Search mined only
    results = app.handle_search(query="test", collection="mined")
    assert isinstance(results, list)


def test_handle_search_default_both(app: MnemosApp) -> None:
    """Default search uses both collections."""
    app.handle_mine(path="Sessions/")
    results = app.handle_search(query="RLS Supabase")
    assert isinstance(results, list)
```

- [ ] **Step 3: Update handle_mine in server.py to index raw**

In `MnemosApp.handle_mine()`, after the file reading and before fragment mining, add raw indexing:

```python
# Inside the for loop over candidates, after fragments = self.miner.mine_file(...)
# Add raw indexing BEFORE fragment processing:

# Index raw content
raw_text = filepath.read_text(encoding="utf-8", errors="replace")
raw_doc_id = SearchEngine.raw_doc_id(filepath_str)
self.search_engine.index_raw(
    doc_id=raw_doc_id,
    text=raw_text,
    metadata={
        "wing": fragments[0]["wing"] if fragments else "General",
        "room": fragments[0]["room"] if fragments else "general",
        "source_path": filepath_str,
        "language": fragments[0]["language"] if fragments else "en",
    },
)
```

- [ ] **Step 4: Update handle_search to accept collection parameter**

```python
def handle_search(
    self,
    query: str,
    wing: str | list[str] | None = None,
    room: str | list[str] | None = None,
    hall: str | list[str] | None = None,
    exclude_wing: str | list[str] | None = None,
    limit: int = 5,
    collection: str = "both",
) -> list[dict]:
    """Semantic search with optional collection selector."""
    return self.search_engine.search(
        query=query,
        wing=wing,
        room=room,
        hall=hall,
        exclude_wing=exclude_wing,
        limit=limit,
        collection=collection,
    )
```

- [ ] **Step 5: Update MCP tool mnemos_search with collection parameter**

In `create_mcp_server()`, update the search tool:

```python
@mcp.tool()
def mnemos_search(
    query: str,
    wing: Optional[str] = None,
    room: Optional[str] = None,
    hall: Optional[str] = None,
    limit: int = 5,
    collection: str = "both",
) -> str:
    """Search the memory palace using semantic similarity.

    Args:
        collection: "raw" (verbatim), "mined" (fragments), or "both" (RRF merge, default)
    """
    results = _get_app().handle_search(
        query=query, wing=wing, room=room, hall=hall,
        limit=limit, collection=collection,
    )
    return json.dumps(results, ensure_ascii=False)
```

- [ ] **Step 6: Add --rebuild flag to CLI**

In `cli.py`, update `cmd_mine` and add `--rebuild` argument:

```python
def cmd_mine(args: argparse.Namespace) -> None:
    vault_path = _resolve_vault(args.vault)
    _require_vault(vault_path, "mine")
    cfg = load_config(vault_path)
    from mnemos.server import MnemosApp

    app = MnemosApp(cfg)

    if args.rebuild:
        # Atomic rebuild: clear mine_log, re-mine everything
        app._mine_log = {}
        app._save_mine_log()
        print("Rebuild: mine_log cleared, re-mining all sources...")

    result = app.handle_mine(path=args.path, use_llm=args.llm)
    print(json.dumps(result, indent=2, ensure_ascii=False))


# In argparse setup for mine subcommand, add:
parser_mine.add_argument(
    "--rebuild",
    action="store_true",
    default=False,
    help="Clear mine log and re-mine all files (rebuild raw+mined collections)",
)
```

- [ ] **Step 7: Run full test suite**

Run: `cd /c/Projeler/mnemos && python -m pytest tests/ -v 2>&1 | tail -30`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add mnemos/server.py mnemos/cli.py mnemos/config.py tests/test_server.py
git commit -m "feat: server integration — raw indexing, collection param, rebuild flag"
```

---

## Task 9: Benchmark (LongMemEval)

**Files:**
- Create: `benchmarks/__init__.py`
- Create: `benchmarks/longmemeval/__init__.py`
- Create: `benchmarks/longmemeval/dataset.py`
- Create: `benchmarks/longmemeval/metrics.py`
- Create: `benchmarks/longmemeval/runner.py`
- Modify: `mnemos/cli.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add benchmark dependency to pyproject.toml**

```toml
[project.optional-dependencies]
llm = ["anthropic>=0.40"]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]
benchmark = ["huggingface_hub>=0.20"]
```

- [ ] **Step 2: Create dataset loader**

Create `benchmarks/__init__.py` (empty) and `benchmarks/longmemeval/__init__.py` (empty).

Create `benchmarks/longmemeval/dataset.py`:

```python
"""LongMemEval dataset loader — download from HuggingFace and parse."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DATASET_DIR = Path(__file__).parent / "data"
DATASET_FILE = DATASET_DIR / "longmemeval.json"

# HuggingFace dataset reference
HF_REPO = "xiaowu0162/LongMemEval"
HF_FILENAME = "data.json"


def download_dataset() -> Path:
    """Download LongMemEval dataset from HuggingFace if not cached."""
    if DATASET_FILE.exists():
        return DATASET_FILE

    DATASET_DIR.mkdir(parents=True, exist_ok=True)

    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        raise ImportError(
            "huggingface_hub required for benchmarks. "
            "Install with: pip install mnemos-dev[benchmark]"
        )

    downloaded = hf_hub_download(
        repo_id=HF_REPO,
        filename=HF_FILENAME,
        repo_type="dataset",
        local_dir=str(DATASET_DIR),
    )

    # Rename to our standard name if needed
    dl_path = Path(downloaded)
    if dl_path != DATASET_FILE:
        dl_path.rename(DATASET_FILE)

    return DATASET_FILE


def load_dataset() -> list[dict[str, Any]]:
    """Load and parse the LongMemEval dataset.

    Returns list of dicts with keys:
        question, answer, session_ids, conversations
    """
    path = download_dataset()
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    if isinstance(data, list):
        return data
    elif isinstance(data, dict):
        # Some datasets wrap in a top-level key
        for key in ("data", "questions", "items"):
            if key in data and isinstance(data[key], list):
                return data[key]
    return []
```

- [ ] **Step 3: Create metrics module**

Create `benchmarks/longmemeval/metrics.py`:

```python
"""Recall@K and NDCG@K metrics for benchmark evaluation."""
from __future__ import annotations

import math


def recall_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    """Recall@K: fraction of relevant items in top-K retrieved results.

    Returns 1.0 if any relevant item is in top-K, 0.0 otherwise.
    (Binary relevance per question — standard for memory retrieval.)
    """
    top_k = set(retrieved_ids[:k])
    relevant = set(relevant_ids)
    return 1.0 if top_k & relevant else 0.0


def ndcg_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    """NDCG@K: normalized discounted cumulative gain.

    Binary relevance: 1 if relevant, 0 if not.
    """
    relevant = set(relevant_ids)
    dcg = 0.0
    for i, doc_id in enumerate(retrieved_ids[:k]):
        if doc_id in relevant:
            dcg += 1.0 / math.log2(i + 2)  # i+2 because log2(1)=0

    # Ideal DCG: all relevant items at top
    ideal_dcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(relevant), k)))

    return dcg / ideal_dcg if ideal_dcg > 0 else 0.0


def aggregate_metrics(results: list[dict]) -> dict:
    """Aggregate per-question metrics into summary.

    Args:
        results: list of {"recall_at_5": float, "recall_at_10": float, "ndcg_at_10": float}

    Returns:
        {"recall_at_5": avg, "recall_at_10": avg, "ndcg_at_10": avg, "total_questions": int}
    """
    if not results:
        return {"recall_at_5": 0.0, "recall_at_10": 0.0, "ndcg_at_10": 0.0, "total_questions": 0}

    n = len(results)
    return {
        "recall_at_5": sum(r["recall_at_5"] for r in results) / n,
        "recall_at_10": sum(r["recall_at_10"] for r in results) / n,
        "ndcg_at_10": sum(r["ndcg_at_10"] for r in results) / n,
        "total_questions": n,
    }
```

- [ ] **Step 4: Create benchmark runner**

Create `benchmarks/longmemeval/runner.py`:

```python
"""LongMemEval benchmark runner — ingest, query, score."""
from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path
from typing import Any

from benchmarks.longmemeval.dataset import load_dataset
from benchmarks.longmemeval.metrics import recall_at_k, ndcg_at_k, aggregate_metrics
from mnemos.config import MnemosConfig
from mnemos.server import MnemosApp


RESULTS_DIR = Path(__file__).parent.parent / "results"


def run_benchmark(
    mode: str = "combined",
    limit: int = 10,
) -> dict[str, Any]:
    """Run LongMemEval benchmark.

    Modes:
        raw-only: search only raw collection
        mined-only: search only mined collection
        combined: search both with RRF
        filtered: combined + metadata filtering

    Returns summary metrics dict.
    """
    print(f"Loading LongMemEval dataset...")
    dataset = load_dataset()
    print(f"Loaded {len(dataset)} questions")

    # Create temporary vault for benchmark
    import tempfile
    with tempfile.TemporaryDirectory(prefix="mnemos_bench_") as tmp_dir:
        config = MnemosConfig(
            vault_path=tmp_dir,
            languages=["en"],
        )
        app = MnemosApp(config, chromadb_in_memory=True)
        app.palace.ensure_structure()

        # Step 1: Ingest conversations
        print("Ingesting conversations (full pipeline)...")
        _ingest_conversations(app, dataset, tmp_dir)

        # Step 2: Query + Score
        print(f"Running queries (mode={mode})...")
        collection = _mode_to_collection(mode)

        results: list[dict] = []
        for i, item in enumerate(dataset):
            question = item.get("question", "")
            answer_ids = item.get("session_ids", [])

            if not question or not answer_ids:
                continue

            search_results = app.handle_search(
                query=question,
                limit=limit,
                collection=collection,
            )

            retrieved_ids = [r.get("metadata", {}).get("source_path", r["drawer_id"])
                           for r in search_results]

            result = {
                "question": question,
                "recall_at_5": recall_at_k(retrieved_ids, answer_ids, 5),
                "recall_at_10": recall_at_k(retrieved_ids, answer_ids, 10),
                "ndcg_at_10": ndcg_at_k(retrieved_ids, answer_ids, 10),
            }
            results.append(result)

            if (i + 1) % 50 == 0:
                print(f"  Processed {i + 1}/{len(dataset)}")

        # Aggregate
        summary = aggregate_metrics(results)
        summary["mode"] = mode
        summary["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S")

        # Save results
        _save_results(results, summary, mode)

        print(f"\n=== Results (mode={mode}) ===")
        print(f"Recall@5:  {summary['recall_at_5']:.4f}")
        print(f"Recall@10: {summary['recall_at_10']:.4f}")
        print(f"NDCG@10:   {summary['ndcg_at_10']:.4f}")
        print(f"Questions: {summary['total_questions']}")

        return summary


def _ingest_conversations(app: MnemosApp, dataset: list, tmp_dir: str) -> None:
    """Write conversation sessions as markdown files and mine them."""
    sessions_dir = Path(tmp_dir) / "Sessions"
    sessions_dir.mkdir(exist_ok=True)

    # Extract unique conversations from dataset
    seen_sessions: set[str] = set()
    for item in dataset:
        conversations = item.get("conversations", [])
        for conv in conversations:
            session_id = conv.get("session_id", "")
            if session_id in seen_sessions:
                continue
            seen_sessions.add(session_id)

            # Write as markdown transcript
            content = conv.get("content", "")
            if not content:
                continue

            filepath = sessions_dir / f"{session_id}.md"
            filepath.write_text(content, encoding="utf-8")

    # Mine all sessions (full pipeline)
    app.handle_mine(path=str(sessions_dir))


def _mode_to_collection(mode: str) -> str:
    if mode == "raw-only":
        return "raw"
    elif mode == "mined-only":
        return "mined"
    else:
        return "both"


def _save_results(results: list, summary: dict, mode: str) -> None:
    """Save detailed results to JSONL file."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    filepath = RESULTS_DIR / f"results_longmemeval_{mode}_{today}.jsonl"

    with filepath.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(summary, ensure_ascii=False) + "\n")
        for r in results:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"Results saved to: {filepath}")
```

- [ ] **Step 5: Add benchmark CLI command**

In `mnemos/cli.py`, add benchmark subcommand:

```python
def cmd_benchmark(args: argparse.Namespace) -> None:
    """Run LongMemEval benchmark."""
    from benchmarks.longmemeval.runner import run_benchmark
    run_benchmark(mode=args.mode)


# In argparse setup, add:
parser_bench = subparsers.add_parser(
    "benchmark",
    help="Run LongMemEval benchmark",
)
parser_bench.add_argument(
    "dataset",
    nargs="?",
    default="longmemeval",
    help="Benchmark dataset (default: longmemeval)",
)
parser_bench.add_argument(
    "--mode",
    choices=["raw-only", "mined-only", "combined", "filtered"],
    default="combined",
    help="Search mode (default: combined)",
)
parser_bench.set_defaults(func=cmd_benchmark)
```

- [ ] **Step 6: Write basic benchmark test**

Create `tests/test_benchmark.py`:

```python
"""Tests for benchmark metrics (no HuggingFace dependency needed)."""
from benchmarks.longmemeval.metrics import recall_at_k, ndcg_at_k, aggregate_metrics


def test_recall_at_k_hit():
    assert recall_at_k(["a", "b", "c"], ["b"], k=5) == 1.0


def test_recall_at_k_miss():
    assert recall_at_k(["a", "b", "c"], ["z"], k=5) == 0.0


def test_recall_at_k_outside_window():
    assert recall_at_k(["a", "b", "c", "d", "e", "f"], ["f"], k=3) == 0.0


def test_ndcg_at_k_perfect():
    """Relevant item at rank 1 = perfect score."""
    score = ndcg_at_k(["relevant", "other"], ["relevant"], k=5)
    assert score == 1.0


def test_ndcg_at_k_lower_rank():
    """Relevant item at rank 2 < perfect score."""
    score = ndcg_at_k(["other", "relevant"], ["relevant"], k=5)
    assert 0.0 < score < 1.0


def test_aggregate_metrics():
    results = [
        {"recall_at_5": 1.0, "recall_at_10": 1.0, "ndcg_at_10": 1.0},
        {"recall_at_5": 0.0, "recall_at_10": 1.0, "ndcg_at_10": 0.5},
    ]
    agg = aggregate_metrics(results)
    assert agg["recall_at_5"] == 0.5
    assert agg["recall_at_10"] == 1.0
    assert agg["total_questions"] == 2
```

- [ ] **Step 7: Run benchmark tests**

Run: `cd /c/Projeler/mnemos && python -m pytest tests/test_benchmark.py -v`
Expected: ALL PASS

- [ ] **Step 8: Run full test suite**

Run: `cd /c/Projeler/mnemos && python -m pytest tests/ -v 2>&1 | tail -30`
Expected: ALL PASS

- [ ] **Step 9: Commit**

```bash
git add benchmarks/ mnemos/cli.py pyproject.toml tests/test_benchmark.py
git commit -m "feat: LongMemEval benchmark — dataset loader, metrics, runner, CLI"
```

---

## Task 10: Integration Testing + Final Verification

**Files:**
- Modify: `tests/test_integration.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Add conversation sample fixture**

Add to `tests/conftest.py`:

```python
@pytest.fixture()
def sample_conversation(tmp_vault: Path) -> Path:
    """Sample conversation transcript for testing exchange-pair mining."""
    note = tmp_vault / "Sessions" / "2026-04-12-conversation.md"
    note.write_text(
        textwrap.dedent(
            """\
            ---
            date: 2026-04-12
            project: Mnemos
            tags: [architecture, decisions]
            ---

            > What storage engine should we use?
            We decided to use ChromaDB for vector search because it supports
            cosine similarity and has a good Python API. The trade-off was
            complexity vs performance.

            > What about the file format?
            We went with Obsidian markdown because it's human-readable and
            integrates with the existing Obsidian ecosystem. The decision is final.

            > Any problems so far?
            There was a bug with the watcher ignoring deleted files. The fix
            was to check the event type before processing. Got it working now.
            """
        ),
        encoding="utf-8",
    )
    return note
```

- [ ] **Step 2: Write full pipeline integration test**

Add to `tests/test_integration.py`:

```python
def test_full_pipeline_dual_collection(config, sample_conversation):
    """Full pipeline: mine -> raw + mined indexed -> search both."""
    from mnemos.server import MnemosApp

    app = MnemosApp(config, chromadb_in_memory=True)
    app.palace.ensure_structure()

    result = app.handle_mine(path=str(sample_conversation))
    assert result["drawers_created"] > 0

    # Raw collection has content
    raw_count = app.search_engine._raw.count()
    assert raw_count > 0

    # Search raw — finds verbatim text
    raw_results = app.handle_search("ChromaDB cosine similarity", collection="raw")
    assert len(raw_results) > 0

    # Search mined — finds classified fragments
    mined_results = app.handle_search("storage engine decision", collection="mined")
    assert len(mined_results) > 0

    # Search both — RRF merge
    both_results = app.handle_search("ChromaDB decision", collection="both")
    assert len(both_results) > 0


def test_exchange_pair_mining_preserves_context(config, sample_conversation):
    """Exchange pairs keep question+answer together."""
    from mnemos.server import MnemosApp

    app = MnemosApp(config, chromadb_in_memory=True)
    app.palace.ensure_structure()

    app.handle_mine(path=str(sample_conversation))

    # Search for the answer — should find it with context
    results = app.handle_search("ChromaDB cosine", collection="mined")
    assert len(results) > 0
    # The chunk should contain both question and answer
    found_text = results[0]["text"]
    assert "storage engine" in found_text.lower() or "ChromaDB" in found_text
```

- [ ] **Step 3: Run full test suite**

Run: `cd /c/Projeler/mnemos && python -m pytest tests/ -v 2>&1 | tail -40`
Expected: ALL PASS

- [ ] **Step 4: Run linting check**

Run: `cd /c/Projeler/mnemos && python -m py_compile mnemos/search.py && python -m py_compile mnemos/normalizer.py && python -m py_compile mnemos/room_detector.py && python -m py_compile mnemos/entity_detector.py && python -m py_compile mnemos/prose.py && python -m py_compile mnemos/miner.py && python -m py_compile mnemos/server.py && echo "All modules compile OK"`
Expected: "All modules compile OK"

- [ ] **Step 5: Commit integration tests**

```bash
git add tests/test_integration.py tests/conftest.py
git commit -m "test: full pipeline integration tests — dual collection, exchange-pair mining"
```

- [ ] **Step 6: Push all Phase 0 work**

```bash
git push
```

---

## Summary

| Task | Component | New Tests |
|------|-----------|-----------|
| 1 | SearchEngine dual collection + RRF + filters | ~6 |
| 2 | Prose extraction (code line filtering) | ~7 |
| 3 | Room detection (72+ patterns) | ~8 |
| 4 | Entity detection (heuristic) | ~7 |
| 5 | Expanded patterns (87 EN + 80 TR) | 0 (existing tests cover) |
| 6 | Conversation normalizer (5 formats) | ~10 |
| 7 | Miner overhaul (chunking + scoring) | ~8 |
| 8 | Server + CLI integration | ~3 |
| 9 | Benchmark (LongMemEval) | ~6 |
| 10 | Integration testing | ~2 |
| **Total** | | **~57 new tests** |

Post-Phase 0: Run `mnemos benchmark longmemeval` and compare against MemPalace's %96.6 Recall@5.
