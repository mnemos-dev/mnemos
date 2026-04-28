# Phase 0 — Foundation Design Spec

**Date:** 2026-04-13
**Status:** Approved
**Goal:** Reach recall parity (96%+) with MemPalace without using an API.
The API (Phase 1) will only be used to push above 96%.

---

## Background

### Why not 96%?

Mnemos v0.1 does **lossy mining**:
- Splits files into paragraphs, classifies with regex, and stores only the fragments
- The original context (conversation flow, question-answer relationship) is lost
- Mining patterns are insufficient: 25 EN patterns, 24 TR patterns (MemPalace: 115+)
- Room detection: only filename + first H2 (MemPalace: 72 patterns)
- Entity detection: only CamelCase (MemPalace: heuristic scoring)
- No conversation format support (MemPalace: 5 formats)

### How does MemPalace reach 96%?

Three fundamental pillars — none requiring an API:
1. **Raw verbatim storage** — the entire file is preserved in ChromaDB
2. **Exchange-pair chunking** — question+answer are chunked together, context is preserved
3. **Metadata filtering** — wing/room narrows the search space (+34% improvement)

### Strategy

```
Phase 0: 96%+ recall without an API
  0.1 + 0.3  Raw storage + dual collection
  0.2        Strengthen metadata filtering
  0.5        Conversation format normalizer
  0.6        Strengthen mining engine (API-free)
  0.7        Benchmark (LongMemEval) — 96% target

Phase 1: Push above 96% with the API
  1.1  LLM mining (catch what regex misses)
  1.2  LLM reranking
  1.3  Contradiction detection
  1.4  Rerun benchmark — 100% target
```

---

## 0.1 + 0.3: Raw Verbatim Storage + Dual Collection

### Design

Two ChromaDB collections instead of the current single one:

```
ChromaDB
├── mnemos_raw       ← original full file text (verbatim, lossless)
└── mnemos_mined     ← extracted fragments (existing structure)
```

### mnemos_raw Collection

- The **full content** of each mined file is stored as a single document
- If the file is large it is chunked (ChromaDB embedding limit is ~8191 tokens / ~30K characters)
  - Context is preserved with overlap between chunks
  - MemPalace approach: 800-char chunks, the overflow carries to the next chunk, nothing is dropped
- Metadata: `wing`, `room`, `source_path`, `language`, `mined_at`, `chunk_index` (if chunked)
- Document ID: `raw-<source_path_hash>` (or `raw-<hash>-<chunk_index>` when chunked)

### mnemos_mined Collection

- The existing `mnemos_drawers` collection is renamed to `mnemos_mined`
- Existing behavior continues unchanged
- New metadata: `raw_id` (a reference to the related raw document)

### SearchEngine Changes

```python
class SearchEngine:
    COLLECTION_RAW = "mnemos_raw"
    COLLECTION_MINED = "mnemos_mined"

    def __init__(self, config, in_memory=False):
        self._raw = client.get_or_create_collection(COLLECTION_RAW, ...)
        self._mined = client.get_or_create_collection(COLLECTION_MINED, ...)

    def index_raw(self, doc_id, text, metadata):
        """Write the full file content into the raw collection."""

    def index_drawer(self, drawer_id, text, metadata):
        """Write a fragment into the mined collection (existing behavior)."""

    def search(self, query, ..., collection="both"):
        """
        collection="raw"   -> search raw only
        collection="mined" -> search mined only
        collection="both"  -> search both, merge with RRF

        Merge strategy: Reciprocal Rank Fusion (RRF)
        - Take the top-N results from each collection
        - RRF score = sum(1 / (k + rank)) for each collection, k=60
        - Dedup results that share the same source_path (keep the highest RRF score)
        - Sort the final list by RRF score

        Why RRF:
        - Weighted merge has a score calibration problem (raw vs mined scores
          can't be compared)
        - In a raw-first approach, the structural advantage of mined is lost
        - RRF is rank-based and score-agnostic — it merges results from
          different collections fairly
        """
```

### Miner / Server Changes

- `handle_mine()`: first store the full content via `index_raw()`, then store the fragments via `index_drawer()`
- `mnemos_search` tool: new `collection` parameter (default: "both")
- The existing drawer .md files in Obsidian remain unchanged — the raw collection lives only in ChromaDB

### Migration

- If an existing `mnemos_drawers` collection is present, it is deleted and recreated as `mnemos_mined` (alpha, the user is warned)
- For files that have already been mined, the raw collection starts empty
- `mnemos mine --rebuild` command: the mine_log is reset, all sources are rescanned, and both raw and mined are populated
- The rebuild operation does not delete existing drawer .md files — the same content is updated via upsert

### Atomic Rebuild

`--rebuild` must be crash-safe:
1. Create new temporary collections (`mnemos_raw_new`, `mnemos_mined_new`)
2. Mine all sources into the temporary collections
3. On success, delete the old collections and rename the temporary ones
4. If a crash occurs, the old collections remain untouched — the temporary ones are cleaned up

This eliminates the risk of data loss during rebuild on large vaults (1000+ files).

---

## 0.2: Strengthen Metadata Filtering

### Improvements

1. **`$in` support**: search across multiple wings/rooms/halls
   ```python
   # Search in the ProcureTrack OR GYP wing
   search(query, wing=["ProcureTrack", "GYP"])
   ```
   - Parameters accept `str | list[str]`
   - Single value: `{"wing": "X"}` (existing)
   - List: `{"wing": {"$in": ["X", "Y"]}}` (new)

2. **Hall-only filter**: hall-based search without specifying a wing (already works, test is missing)

3. **Negative filter**: exclude a specific wing/room
   ```python
   search(query, exclude_wing="General")
   ```

---

## 0.5: Conversation Format Normalizer

### Purpose

MemPalace supports 5 conversation formats. We will likewise convert the same formats into markdown and feed them into the existing pipeline.

### Supported Formats

| Format | Source | File Type |
|--------|--------|------------|
| Claude Code JSONL | `~/.claude/projects/*/conversations/` | `.jsonl` |
| Claude.ai JSON | claude.ai export | `.json` |
| ChatGPT JSON | chatgpt.com export | `.json` |
| Slack JSON | Slack workspace export | `.json` |
| Plain text | Any text | `.txt`, `.md` |

### Output Format

All formats are converted to a standard transcript:

```markdown
> user message here
assistant response here

> next user message
assistant response
```

### Module Structure

```python
# mnemos/normalizer.py

def normalize_file(filepath: Path) -> str:
    """Detect the file format and convert to a standard transcript."""

def _try_claude_code_jsonl(text: str) -> str | None:
    """Parse the Claude Code JSONL format.
    - merge tool_use/tool_result messages
    - merge consecutive assistant messages
    """

def _try_chatgpt_json(text: str) -> str | None:
    """Parse the ChatGPT export format.
    - traverse the mapping tree structure
    - extract role + content
    """

def _try_slack_json(text: str) -> str | None:
    """Parse the Slack export format.
    - assign roles on speaker changes
    """

def _try_plain_text(text: str) -> str:
    """Fallback: leave as markdown/text."""
```

### Tool result truncation (MemPalace approach)

- Bash output: first 20 + last 20 lines
- Grep/Glob: first 20 results
- Other: 2048 bytes

### Integration

- The `mnemos mine` command also accepts `.jsonl` and `.json` files
- The miner first runs them through the normalizer, then feeds them into the existing pipeline
- `--format` flag: explicitly specify the format instead of auto-detect (optional)

---

## 0.6: Strengthen Mining Engine (API-free)

### 0.6.1: Exchange-Pair Chunking

Existing: paragraph-based splitting (context is lost)
New: in conversation transcripts, question+answer are chunked together

```python
def chunk_exchanges(transcript: str, max_chunk: int = 3000) -> list[str]:
    """Split a transcript into exchange pairs.

    - Lines starting with '>' are user turns
    - Following lines are the assistant response
    - The chunk boundary is always cut at an exchange boundary
    - If a single exchange exceeds max_chunk, the response is split
      but the user question always stays in the first chunk
    - Nothing is dropped — every character is preserved

    NOTE: Chunk size is dynamic — cut at the exchange boundary.
    Not 800 chars, max 3000 chars. Most exchanges are between 1000-2500
    chars, so they usually stay unsplit.
    """
```

Fallback: for non-conversation files, the existing paragraph chunking continues.

### 0.6.2: Room Detection (72 patterns)

Existing: filename + first H2 heading
New: add MemPalace's 72 folder/filename patterns + content keyword scoring

```yaml
# mnemos/patterns/rooms.yaml
rooms:
  frontend:
    folders: [frontend, front-end, client, ui, views, components, pages]
    keywords: [react, vue, angular, css, html, dom, render, component]
  backend:
    folders: [backend, server, api, routes, services, controllers, models, database, db]
    keywords: [endpoint, middleware, query, schema, migration, orm]
  planning:
    folders: [planning, roadmap, strategy, specs, requirements]
    keywords: [plan, roadmap, milestone, deadline, priority, sprint, scope, spec]
  decisions:
    folders: [decisions, adrs]
    keywords: [decided, chose, picked, switched, migrated, trade-off, approach]
  problems:
    folders: [issues, bugs]
    keywords: [problem, issue, broken, failed, crash, stuck, workaround, fix]
  meetings:
    folders: [meetings, calls, meeting_notes, standup, minutes]
    keywords: [meeting, call, standup, discussed, attendees, agenda]
  # ... 13 categories in total (same as MemPalace)
```

Algorithm:
1. Match folder names in the file path against the patterns
2. If no match: keyword scoring on the first 3000 characters
3. Pick the highest-scoring room
4. If still no match: "general"

### 0.6.3: Heuristic Entity Detection

Existing: only CamelCase regex
New: MemPalace's two-pass heuristic approach

```python
# mnemos/entity_detector.py

class EntityDetector:
    """API-free entity detection — heuristic scoring."""

    # 200+ stopwords (common words, programming keywords)
    STOPWORDS = {...}

    def detect(self, text: str) -> dict:
        """Return {persons: [...], projects: [...], uncertain: [...]}"""

    def _pass1_candidates(self, text: str) -> list[str]:
        """Find capitalized words occurring 3+ times, filter stopwords."""

    def _pass2_classify(self, candidate: str, text: str) -> tuple[str, float]:
        """
        Person signals (weighted):
          - Dialogue: '> Speaker:', 'Speaker said' (x3)
          - Action: said, asked, told, thinks, wants (x2)
          - Pronoun proximity: he/she/they within 3 lines (x2)
          - Direct address: 'hey Name', 'thanks Name' (x4)

        Project signals (weighted):
          - Verbs: building, shipped, deployed (x2)
          - Architecture: 'Name architecture', 'Name pipeline' (x2)
          - Version: 'Name v2', 'Name-core' (x3)
          - Code: 'import Name', 'Name.py' (x3)

        Classification:
          person_ratio >= 0.7 + 2+ signal types + score >= 5 -> Person
          person_ratio <= 0.3 -> Project
          Otherwise -> Uncertain
        """
```

Turkish extensions:
- Turkish action verbs: "dedi", "sordu", "istedi", "yapti"
- Turkish honorifics: "Bey", "Hanim", "hocam"

### 0.6.4: General Extractor (115+ markers)

Existing: 4 halls, ~25 EN patterns, ~24 TR patterns = 49 total
New: 4 halls (emotional deferred to Phase 1), MemPalace-level markers + Turkish equivalents

```yaml
# mnemos/patterns/en.yaml (to be updated)
decisions:  # 21 markers
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

preferences:  # 16 markers
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

problems:  # 17 markers
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

events:  # 33 markers (milestones)
  - "shipped"
  - "completed"
  - "launched"
  - "deployed"
  - "it works"
  - "figured out"
  - "migrated"
  - "breakthrough"
  - "finally"
  - "v1.0"
  - "v2.0"
  - "2x faster"
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
  - "0 errors"
  - "100%"
  - "PR approved"
  - "code review done"
  - "demo ready"
  - "cut the release"
  - "tagged"
  - "published"

  # NOTE: the emotional hall will not be added in Phase 0.
  # Generic markers like "love", "thank you", "amazing" cause false positives.
  # In Phase 1, smart classification will be done with the Claude API.
```

Turkish markers will be expanded by the same proportion (~80 patterns, excluding emotional).

### 0.6.5: Scoring + Disambiguation

Existing: assign hall directly when a pattern matches
New: MemPalace's scoring approach

```python
def classify_segment(text: str, patterns: dict) -> tuple[str, float]:
    """
    1. Count marker hits per hall (score)
    2. Length bonus: >500 chars +2, 200-500 +1
    3. Confidence = min(1.0, max_score / 5.0)
    4. Disambiguation:
       - Problem + "fixed/solved/got it working" -> events (milestone)
       - Problem + positive sentiment -> events
    5. Drop anything below min_confidence = 0.3
    """
```

### 0.6.6: Code Line Filtering

Existing: none — code lines are also included in mining
New: MemPalace's prose extraction

```python
def extract_prose(text: str) -> str:
    """Strip code lines, leaving only human-written text.
    - Skip shell commands (cd, git, pip, npm...)
    - Skip programming constructs (import, def, class, return)
    - Skip code blocks (```)
    - Skip lines with <40% alpha ratio
    """
```

---

## 0.7: Benchmark (LongMemEval)

### Structure

```
benchmarks/
├── longmemeval/
│   ├── runner.py          ← main benchmark runner
│   ├── dataset.py         ← download + parse dataset from HuggingFace
│   └── metrics.py         ← Recall@K, NDCG@10 computation
├── results/
│   └── results_longmemeval_YYYY-MM-DD.jsonl
└── README.md
```

### Pipeline — Full Pipeline Test

The benchmark tests **the full Mnemos pipeline**, not just ChromaDB:

1. Download 500 questions + ~53 conversation sessions from HuggingFace
2. Run conversations through the normalizer (format detection + normalize)
3. **Full mine pipeline**: normalize -> exchange-pair chunk -> room detect -> entity detect -> classify -> write Obsidian .md -> ChromaDB index (raw + mined)
4. Call `mnemos_search` for each question (via MnemosApp.handle_search)
5. Check whether the ground-truth answer is in the top-K results
6. Compute Recall@5, Recall@10, NDCG@10

NOTE: The benchmark tests the full pipeline because:
- A ChromaDB-only test does not measure real-usage recall
- Issues like normalizer errors, chunking losses, room misclassification
  only surface in the full pipeline
- MemPalace also tests the full pipeline the same way

### Test Modes

| Mode | Description | Goal |
|-----|----------|-------|
| raw-only | raw collection only | Baseline |
| mined-only | mined collection only | Mining quality |
| combined | raw + mined merge | Highest recall |
| filtered | wing/room metadata filtering | +34% improvement |

### CLI

```bash
mnemos benchmark longmemeval
mnemos benchmark longmemeval --mode raw-only
mnemos benchmark results
```

### Target

| Metric | MemPalace | Mnemos Phase 0 Target |
|--------|-----------|---------------------|
| Recall@5 | 96.6% | 95%+ |
| Recall@10 | 98.2% | 97%+ |

---

## Out of Scope (Phase 1+)

- Mining/reranking with the Claude API (Phase 1)
- Contradiction detection (Phase 1)
- Auto-mining pipeline / hooks (Phase 2)
- Memory lifecycle / decay (Phase 2)
- Knowledge graph improvements (Phase 2)

---

## Implementation Order

1. **0.1 + 0.3**: Dual collection + raw storage (SearchEngine, Miner, Server)
2. **0.2**: Metadata filtering improvements
3. **0.5**: Conversation format normalizer
4. **0.6**: Strengthen mining engine (exchange-pair chunking, room detection, entity detection, general extractor, scoring, code filtering)
5. **0.7**: Benchmark + first measurement
6. All tests must pass; the existing 51 tests must not break

---

## Success Criteria

- [ ] Full file content is written to the raw collection
- [ ] The mined collection preserves existing behavior
- [ ] Search can query both raw and mined and merge the results
- [ ] Wing/room list filter ($in) works
- [ ] 5 conversation formats are normalized (Claude Code, Claude.ai, ChatGPT, Slack, plain text)
- [ ] Exchange-pair chunking works (question+answer together)
- [ ] Room detection works with 72+ patterns
- [ ] Entity detection works with heuristic scoring
- [ ] General extractor works with 87+ EN markers + ~80 TR markers (4 halls excluding emotional)
- [ ] Code line filtering works
- [ ] Scoring + disambiguation works (min_confidence=0.3)
- [ ] LongMemEval benchmark runs and Recall@5 >= 95%
- [ ] The existing 51 tests still pass
- [ ] New tests have been added (one per new module)
