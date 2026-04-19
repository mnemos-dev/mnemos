"""Pilot orchestrator for skill-mine vs script-mine side-by-side evaluation.

See docs/specs/2026-04-19-phase1-ai-boost-design.md §4.2.2.

Flow:
  1. `build_plan(vault, limit=10)` discovers recent refined Sessions/ .md files
     and returns a PilotPlan with two target palace roots.
  2. `run_pilot(plan, runner)` iterates the planned sessions and invokes the
     mnemos-mine-llm skill via `claude --print` for each, collecting token
     usage and drawer counts from a per-skill ledger.
  3. `format_pilot_report(plan, result)` emits a markdown skeleton for the
     compare-palaces skill to fill in.

The orchestrator itself does NOT run script-mine; it assumes the Mnemos/
palace (script-mined) already exists in the vault. Spec §4.2.2 step 3.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence


CLAUDE_CMD = "claude"
SKILL_LEDGER_SUFFIX = Path(".claude/skills/mnemos-mine-llm/state/mined.tsv")
DEFAULT_LIMIT = 10
DEFAULT_PILOT_PALACE = "Mnemos-pilot"
DEFAULT_SCRIPT_PALACE = "Mnemos"


Runner = Callable[[Sequence[str]], "RunnerResult"]


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class PilotError(Exception):
    """Raised when the pilot cannot proceed (missing inputs, invalid paths)."""


@dataclass
class RunnerResult:
    exit_code: int
    stdout: str


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0

    def total(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_input_tokens
            + self.cache_creation_input_tokens
        )

    def add(self, other: "TokenUsage") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_input_tokens += other.cache_read_input_tokens
        self.cache_creation_input_tokens += other.cache_creation_input_tokens


@dataclass
class PilotPlan:
    vault: Path
    sessions: list[Path]
    script_palace: Path  # existing, e.g. <vault>/Mnemos/
    skill_palace: Path  # to be produced, e.g. <vault>/Mnemos-pilot/
    limit: int

    @property
    def session_count(self) -> int:
        return len(self.sessions)


@dataclass
class SessionOutcome:
    session: Path
    exit_code: int
    drawer_count: int  # 0 = SKIP or error
    outcome: str  # "ok" | "skip" | "error"
    reason: str = ""  # SKIP gerekçe veya error mesajı
    usage: TokenUsage = field(default_factory=TokenUsage)


@dataclass
class PilotResult:
    plan: PilotPlan
    outcomes: list[SessionOutcome]
    skill_total_tokens: TokenUsage = field(default_factory=TokenUsage)
    skill_elapsed_sec: float = 0.0
    report_path: Path | None = None

    @property
    def ok_count(self) -> int:
        return sum(1 for o in self.outcomes if o.outcome == "ok")

    @property
    def skip_count(self) -> int:
        return sum(1 for o in self.outcomes if o.outcome == "skip")

    @property
    def error_count(self) -> int:
        return sum(1 for o in self.outcomes if o.outcome == "error")

    @property
    def total_drawers(self) -> int:
        return sum(o.drawer_count for o in self.outcomes)


# ---------------------------------------------------------------------------
# Plan building
# ---------------------------------------------------------------------------


def _sessions_dir(vault: Path) -> Path:
    return Path(vault) / "Sessions"


def _discover_sessions(vault: Path) -> list[Path]:
    """Return all refined session .md files sorted newest-first by mtime."""
    sdir = _sessions_dir(vault)
    if not sdir.exists() or not sdir.is_dir():
        return []
    mds = [p for p in sdir.glob("*.md") if p.is_file()]
    mds.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return mds


def build_plan(
    vault: Path,
    limit: int = DEFAULT_LIMIT,
    script_palace_name: str = DEFAULT_SCRIPT_PALACE,
    skill_palace_name: str = DEFAULT_PILOT_PALACE,
) -> PilotPlan:
    """Discover candidate sessions + compute palace paths.

    Raises PilotError if vault lacks a non-empty Sessions/ directory.
    """
    vault = Path(vault)
    if not vault.exists() or not vault.is_dir():
        raise PilotError(f"Vault path does not exist or is not a directory: {vault}")

    sessions = _discover_sessions(vault)
    if not sessions:
        raise PilotError(
            f"No refined sessions found in {_sessions_dir(vault)}. "
            "Run the mnemos-refine-transcripts skill first."
        )

    if limit < 1:
        raise PilotError(f"limit must be >= 1, got {limit}")

    picked = sessions[:limit]

    return PilotPlan(
        vault=vault,
        sessions=picked,
        script_palace=vault / script_palace_name,
        skill_palace=vault / skill_palace_name,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# Claude --print output parsing
# ---------------------------------------------------------------------------


def parse_claude_json_output(stdout: str) -> tuple[str, TokenUsage]:
    """Parse `claude --print --output-format json` stdout.

    Expected shape (Claude Code subscription stream result):
      {"type": "result", "subtype": "success", "result": "...",
       "usage": {"input_tokens": N, "output_tokens": M, ...}}

    Returns (result_text, token_usage). If stdout is malformed or empty,
    returns ("", TokenUsage()) without raising — pilot should still record
    the session as an error via exit code, not crash.
    """
    stdout = (stdout or "").strip()
    if not stdout:
        return "", TokenUsage()

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return "", TokenUsage()

    if not isinstance(data, dict):
        return "", TokenUsage()

    result = str(data.get("result") or "")
    usage_raw = data.get("usage") or {}
    usage = TokenUsage(
        input_tokens=int(usage_raw.get("input_tokens") or 0),
        output_tokens=int(usage_raw.get("output_tokens") or 0),
        cache_read_input_tokens=int(usage_raw.get("cache_read_input_tokens") or 0),
        cache_creation_input_tokens=int(usage_raw.get("cache_creation_input_tokens") or 0),
    )
    return result, usage


# ---------------------------------------------------------------------------
# Ledger reading (mine-llm skill writes, orchestrator reads)
# ---------------------------------------------------------------------------


def default_ledger_path() -> Path:
    """Absolute path to the mnemos-mine-llm ledger in the user's home."""
    return Path.home() / SKILL_LEDGER_SUFFIX


def read_ledger_entry(
    ledger_path: Path, session: Path, palace_root: Path
) -> tuple[str, int, str] | None:
    """Find the latest ledger row for (session, palace_root).

    Ledger format (tab-separated):
      <session-abs-path>\\t<palace-root>\\t<drawer-count>\\t<timestamp-or-SKIP-reason>

    Returns (outcome, drawer_count, reason) or None if no row matches.
    outcome is "ok" | "skip" | "error".
    """
    if not ledger_path.exists():
        return None

    target_session = os.path.normcase(os.path.normpath(str(session)))
    target_palace = os.path.normcase(os.path.normpath(str(palace_root)))
    latest: tuple[str, int, str] | None = None

    for line in ledger_path.read_text(encoding="utf-8", errors="replace").splitlines():
        cols = line.split("\t")
        if len(cols) < 4:
            continue
        row_session = os.path.normcase(os.path.normpath(cols[0].strip()))
        row_palace = os.path.normcase(os.path.normpath(cols[1].strip()))
        if row_session != target_session or row_palace != target_palace:
            continue
        try:
            drawer_count = int(cols[2].strip() or "0")
        except ValueError:
            drawer_count = 0
        last_col = cols[3].strip()
        if last_col.startswith("SKIP"):
            outcome = "skip"
            reason = last_col.partition(":")[2].strip() or last_col
        elif drawer_count > 0:
            outcome = "ok"
            reason = ""
        else:
            # zero drawers, non-SKIP marker → treat as error (skill crashed
            # or returned no decision); we don't conflate with explicit SKIP.
            outcome = "error"
            reason = last_col
        latest = (outcome, drawer_count, reason)
    return latest


def sessions_needing_run(
    plan: PilotPlan, ledger_path: Path
) -> list[Path]:
    """Filter plan.sessions to those NOT already recorded for skill_palace.

    An OK or SKIP row counts as processed; an error row does not (retry).
    """
    out: list[Path] = []
    for s in plan.sessions:
        entry = read_ledger_entry(ledger_path, s, plan.skill_palace)
        if entry is None:
            out.append(s)
            continue
        outcome, _count, _reason = entry
        if outcome == "error":
            out.append(s)
    return out


# ---------------------------------------------------------------------------
# Subprocess runner
# ---------------------------------------------------------------------------


def default_capture_runner(cmd: Sequence[str]) -> RunnerResult:
    """Run a subprocess and capture stdout. For `claude` calls strip
    ANTHROPIC_API_KEY so Claude Code uses subscription auth (see
    auto_refine._default_runner rationale, 2026-04-16).
    """
    kwargs: dict = {"capture_output": True, "text": True, "encoding": "utf-8"}
    if os.name == "nt":
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    if cmd and cmd[0] == CLAUDE_CMD:
        env = os.environ.copy()
        env.pop("ANTHROPIC_API_KEY", None)
        kwargs["env"] = env
    result = subprocess.run(list(cmd), **kwargs)
    return RunnerResult(exit_code=result.returncode, stdout=result.stdout or "")


# ---------------------------------------------------------------------------
# Pilot execution
# ---------------------------------------------------------------------------


def _skill_cmd(session: Path, skill_palace: Path) -> list[str]:
    return [
        CLAUDE_CMD,
        "--print",
        "--dangerously-skip-permissions",
        "--output-format",
        "json",
        f"/mnemos-mine-llm {session} {skill_palace}",
    ]


def count_drawers_for_session(palace_root: Path, session: Path) -> int:
    """Count drawers under *palace_root* whose frontmatter ``source:`` field
    matches *session* (normalized path compare).

    Used as a filesystem fallback for the orchestrator when the mine-llm
    ledger has no row for a session — the skill may have written drawers
    but skipped the append (see docs/pilots/2026-04-19-v0.4-phase1-real-
    vault-pilot.md Finding 2).
    """
    return _count_drawers(palace_root, sessions=[session])


def _run_one_session(
    session: Path,
    skill_palace: Path,
    ledger_path: Path,
    runner: Runner,
) -> SessionOutcome:
    rr = runner(_skill_cmd(session, skill_palace))
    _text, usage = parse_claude_json_output(rr.stdout)

    entry = read_ledger_entry(ledger_path, session, skill_palace)

    if entry is None:
        # Filesystem fallback — did the skill write drawers but drop the
        # ledger append? Real-vault pilot showed this happens 2/3 of the time
        # on long sessions. Count drawers with matching `source:` frontmatter.
        fs_count = count_drawers_for_session(skill_palace, session)
        if fs_count > 0:
            return SessionOutcome(
                session=session,
                exit_code=rr.exit_code,
                drawer_count=fs_count,
                outcome="ok",
                reason="ledger-skipped; recovered from filesystem",
                usage=usage,
            )
        # Neither ledger nor drawers — real error
        reason = (
            f"claude exit {rr.exit_code}"
            if rr.exit_code != 0
            else "no ledger entry and no drawers on filesystem"
        )
        return SessionOutcome(
            session=session,
            exit_code=rr.exit_code,
            drawer_count=0,
            outcome="error",
            reason=reason,
            usage=usage,
        )

    outcome_str, drawer_count, reason = entry
    return SessionOutcome(
        session=session,
        exit_code=rr.exit_code,
        drawer_count=drawer_count,
        outcome=outcome_str,
        reason=reason,
        usage=usage,
    )


def run_pilot(
    plan: PilotPlan,
    runner: Runner | None = None,
    ledger_path: Path | None = None,
) -> PilotResult:
    """Run skill-mine for each planned session, sequentially.

    Resumable: ledger entries for (session, skill_palace) cause the session
    to be skipped (already processed). Parallel execution is future work
    (spec §4.2.2) — sequential keeps the flow debuggable for v0.4 MVP.
    """
    import time

    runner = runner or default_capture_runner
    ledger_path = ledger_path or default_ledger_path()

    plan.skill_palace.mkdir(parents=True, exist_ok=True)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)

    to_run = sessions_needing_run(plan, ledger_path)

    outcomes: list[SessionOutcome] = []
    total_usage = TokenUsage()
    start = time.monotonic()

    # Replay existing ledger entries for sessions already processed, so the
    # final result reflects the full plan even on resume.
    for session in plan.sessions:
        if session in to_run:
            continue
        entry = read_ledger_entry(ledger_path, session, plan.skill_palace)
        if entry is None:
            continue
        outcome_str, drawer_count, reason = entry
        outcomes.append(
            SessionOutcome(
                session=session,
                exit_code=0,
                drawer_count=drawer_count,
                outcome=outcome_str,
                reason=reason,
            )
        )

    for session in to_run:
        so = _run_one_session(session, plan.skill_palace, ledger_path, runner)
        total_usage.add(so.usage)
        outcomes.append(so)

    elapsed = time.monotonic() - start

    # Preserve plan order in outcomes
    by_session = {o.session: o for o in outcomes}
    ordered = [by_session[s] for s in plan.sessions if s in by_session]

    return PilotResult(
        plan=plan,
        outcomes=ordered,
        skill_total_tokens=total_usage,
        skill_elapsed_sec=elapsed,
    )


# ---------------------------------------------------------------------------
# Pilot report (markdown skeleton)
# ---------------------------------------------------------------------------


def _drawer_source(drawer_path: Path) -> str | None:
    """Extract the `source:` field from a drawer .md's YAML frontmatter.

    Reads at most the first ~60 lines to find the field; robust against
    missing/unterminated frontmatter. Returns the raw string as stored in
    frontmatter (no normalization), or ``None`` if absent.
    """
    try:
        with drawer_path.open("r", encoding="utf-8", errors="replace") as fh:
            first = fh.readline()
            if first.strip() != "---":
                return None
            for i, line in enumerate(fh):
                if i > 80 or line.strip() == "---":
                    break
                if ":" not in line:
                    continue
                key, _, value = line.partition(":")
                if key.strip() == "source":
                    return value.strip()
    except OSError:
        return None
    return None


def _sessions_key_set(sessions: Sequence[Path] | None) -> set[str] | None:
    """Normalize a sequence of session paths to a case-insensitive key set.

    Returns ``None`` if *sessions* is None — caller should treat as "no filter".
    """
    if sessions is None:
        return None
    return {os.path.normcase(os.path.normpath(str(s))) for s in sessions}


def _drawer_matches_sessions(drawer: Path, session_keys: set[str] | None) -> bool:
    """True if *drawer*'s ``source:`` field normalizes to a key in the set.

    When *session_keys* is None (no filter), all drawers match.
    """
    if session_keys is None:
        return True
    src = _drawer_source(drawer)
    if src is None:
        return False
    return os.path.normcase(os.path.normpath(src)) in session_keys


def _hall_counts_for_palace(
    palace_root: Path,
    sessions: Sequence[Path] | None = None,
) -> dict[str, int]:
    """Count drawer .md files under palace_root/wings/*/*/<hall>/.

    When *sessions* is provided, only count drawers whose frontmatter
    ``source:`` field matches one of the session paths (pilot-scoped
    comparison). Default ``None`` preserves the whole-palace count.
    """
    counts: dict[str, int] = {}
    wings = palace_root / "wings"
    if not wings.exists():
        return counts
    keys = _sessions_key_set(sessions)
    for md in wings.rglob("*.md"):
        # hall = parent dir name; skip _wing.md / _room.md
        if md.name.startswith("_"):
            continue
        if not _drawer_matches_sessions(md, keys):
            continue
        hall = md.parent.name
        counts[hall] = counts.get(hall, 0) + 1
    return counts


def _count_drawers(
    palace_root: Path,
    sessions: Sequence[Path] | None = None,
) -> int:
    """Count drawers under palace_root. Pilot-filter via *sessions* (see
    :func:`_hall_counts_for_palace`).
    """
    wings = palace_root / "wings"
    if not wings.exists():
        return 0
    keys = _sessions_key_set(sessions)
    total = 0
    for md in wings.rglob("*.md"):
        if md.name.startswith("_"):
            continue
        if not _drawer_matches_sessions(md, keys):
            continue
        total += 1
    return total


def format_pilot_report(result: PilotResult) -> str:
    """Produce markdown skeleton for the compare-palaces skill to fill."""
    plan = result.plan
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Session-filter both palaces so quantitative summary is apples-to-apples
    # (whole-palace drawer totals were misleading — see docs/pilots/
    # 2026-04-19-v0.4-phase1-real-vault-pilot.md Finding 3).
    script_count = _count_drawers(plan.script_palace, plan.sessions)
    skill_count = _count_drawers(plan.skill_palace, plan.sessions)
    script_halls = _hall_counts_for_palace(plan.script_palace, plan.sessions)
    skill_halls = _hall_counts_for_palace(plan.skill_palace, plan.sessions)

    def _halls_line(halls: dict[str, int]) -> str:
        if not halls:
            return "(empty)"
        return ", ".join(f"{h}:{n}" for h, n in sorted(halls.items()))

    usage = result.skill_total_tokens
    lines = [
        f"# LLM-mine pilot — {date}",
        "",
        f"**Vault:** `{plan.vault}`",
        f"**Sessions piloted:** {plan.session_count} (limit={plan.limit})",
        f"**Skill elapsed:** {result.skill_elapsed_sec:.1f}s",
        "",
        "## Quantitative summary",
        "",
        "| | Script-mine (`Mnemos/`) | Skill-mine (`Mnemos-pilot/`) |",
        "|---|---|---|",
        f"| Total drawers | {script_count} | {skill_count} |",
        f"| Hall distribution | {_halls_line(script_halls)} | {_halls_line(skill_halls)} |",
        f"| Tokens consumed | 0 (regex, no LLM) | {usage.total():,} total "
        f"(in:{usage.input_tokens:,} out:{usage.output_tokens:,} "
        f"cache-r:{usage.cache_read_input_tokens:,} cache-w:{usage.cache_creation_input_tokens:,}) |",
        "",
        "**Per-session outcomes (skill-mine):**",
        "",
        "| Session | Outcome | Drawers | Reason |",
        "|---|---|---|---|",
    ]
    for o in result.outcomes:
        lines.append(
            f"| `{o.session.name}` | {o.outcome} | {o.drawer_count} | {o.reason or '—'} |"
        )
    lines.extend([
        "",
        f"**Totals:** OK={result.ok_count}, SKIP={result.skip_count}, ERROR={result.error_count}, drawers={result.total_drawers}",
        "",
        "## Qualitative judgment",
        "",
        "*Run `/mnemos-compare-palaces` to populate this section with a drawer-by-drawer",
        "comparison (3 sample sessions side-by-side, richness / cleanliness / hall accuracy /",
        "body readability / wikilink validity). The skill will NOT decide for you — you pick",
        "the mode based on the evidence.*",
        "",
        "## Next step",
        "",
        "After reviewing this report, pick one:",
        "",
        "- `mnemos pilot --accept script` — keep script-mine (recycle `Mnemos-pilot/`)",
        "- `mnemos pilot --accept skill` — switch to skill-mine (recycle `Mnemos/`, promote `Mnemos-pilot/`)",
        "",
        f"_Generated by `mnemos mine --pilot-llm` on {date}_",
        "",
    ])
    return "\n".join(lines)


def write_pilot_report(result: PilotResult, pilots_dir: Path | None = None) -> Path:
    """Write the formatted report under <vault>/docs/pilots/ (default) and
    return the path written.
    """
    if pilots_dir is None:
        pilots_dir = result.plan.vault / "docs" / "pilots"
    pilots_dir.mkdir(parents=True, exist_ok=True)
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fname = f"{date}-llm-mine-pilot.md"
    path = pilots_dir / fname
    # collision-safe: if exists add -2, -3, ...
    if path.exists():
        i = 2
        while (pilots_dir / f"{date}-llm-mine-pilot-{i}.md").exists():
            i += 1
        path = pilots_dir / f"{date}-llm-mine-pilot-{i}.md"
    path.write_text(format_pilot_report(result), encoding="utf-8")
    result.report_path = path
    return path


# ---------------------------------------------------------------------------
# Accept — promote a pilot outcome to steady-state palace
# ---------------------------------------------------------------------------


@dataclass
class AcceptResult:
    mode: str  # "script" | "skill"
    recycled_paths: list[Path]
    promoted_from: Path | None = None  # for skill mode: Mnemos-pilot → Mnemos
    yaml_updated: bool = False
    index_stale_warning: str = ""
    indexed_drawers: int = 0  # populated by accept_skill when reindex=True


def _recycled_target(vault: Path, source_name: str) -> Path:
    """Compute a collision-safe _recycled/ path for an accepted-pilot move."""
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    recycled = vault / "_recycled"
    recycled.mkdir(parents=True, exist_ok=True)
    base = recycled / f"{source_name}-{date}"
    if not base.exists():
        return base
    i = 2
    while (recycled / f"{source_name}-{date}.{i}").exists():
        i += 1
    return recycled / f"{source_name}-{date}.{i}"


def accept_script(
    vault: Path,
    skill_palace_name: str = DEFAULT_PILOT_PALACE,
) -> AcceptResult:
    """Keep script-mine: move Mnemos-pilot/ to _recycled/.

    No yaml change (script-mine is the default). Idempotent if the pilot
    palace no longer exists — returns an empty-recycled result.
    """
    import shutil

    vault = Path(vault)
    skill_palace = vault / skill_palace_name
    recycled: list[Path] = []

    if skill_palace.exists():
        target = _recycled_target(vault, skill_palace_name)
        shutil.move(str(skill_palace), str(target))
        recycled.append(target)

    return AcceptResult(mode="script", recycled_paths=recycled)


def accept_skill(
    vault: Path,
    script_palace_name: str = DEFAULT_SCRIPT_PALACE,
    skill_palace_name: str = DEFAULT_PILOT_PALACE,
    reindex: bool = True,
) -> AcceptResult:
    """Switch to skill-mine: recycle Mnemos/, promote Mnemos-pilot/ → Mnemos/,
    update yaml, and — when *reindex* is True (default) — rebuild the vector
    index from the promoted palace's drawer frontmatter (4.2.9).

    Raises PilotError if the skill palace is missing (cannot promote nothing).
    Script palace absence is tolerated (fresh vault).
    """
    import shutil

    vault = Path(vault)
    script_palace = vault / script_palace_name
    skill_palace = vault / skill_palace_name

    if not skill_palace.exists():
        raise PilotError(
            f"Skill palace not found at {skill_palace}. "
            "Run `mnemos mine --pilot-llm` first."
        )

    recycled: list[Path] = []

    if script_palace.exists():
        target = _recycled_target(vault, script_palace_name)
        shutil.move(str(script_palace), str(target))
        recycled.append(target)

    shutil.move(str(skill_palace), str(script_palace))
    promoted_from = skill_palace

    yaml_updated = _update_mine_mode(vault, "skill")

    indexed = 0
    warning = ""
    if reindex:
        try:
            indexed = _reindex_after_accept(vault, script_palace)
        except Exception as e:  # pragma: no cover — surfaced to user
            warning = (
                f"Index rebuild failed after file moves: {e}. "
                "Run `mnemos mine --from-palace <new-mnemos-path>` manually "
                "to refresh the vector index."
            )
    else:
        warning = (
            "Index left untouched (reindex=False). Search results will "
            "reflect the recycled script-mine palace until you run "
            "`mnemos mine --from-palace <new-mnemos-path>`."
        )

    return AcceptResult(
        mode="skill",
        recycled_paths=recycled,
        promoted_from=promoted_from,
        yaml_updated=yaml_updated,
        index_stale_warning=warning,
        indexed_drawers=indexed,
    )


def _reindex_after_accept(vault: Path, palace: Path) -> int:
    """Open a SearchEngine against *vault*'s config and re-index drawers
    from *palace* via palace_indexer. Returns drawers indexed count.

    Isolated helper so tests can patch it.
    """
    from mnemos.config import load_config
    from mnemos.palace_indexer import index_palace
    from mnemos.search import SearchEngine

    cfg = load_config(vault)
    with SearchEngine(cfg) as backend:
        stats = index_palace(backend, palace)
    return stats.indexed


def _update_mine_mode(vault: Path, mode: str) -> bool:
    """Write `mine_mode: <mode>` to <vault>/mnemos.yaml, preserving other keys.

    Returns True if yaml existed and was updated, False if missing.
    Uses a minimal line-level edit so existing comments and key ordering
    survive (the project's yaml wrangling pattern, see mnemos/config.py).
    """
    import yaml

    yaml_path = vault / "mnemos.yaml"
    if not yaml_path.exists():
        return False

    text = yaml_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    found = False
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("mine_mode:") or stripped.startswith("mine_mode :"):
            indent = line[: len(line) - len(stripped)]
            trailing_newline = "\n" if line.endswith("\n") else ""
            lines[i] = f"{indent}mine_mode: {mode}{trailing_newline}"
            found = True
            break

    if not found:
        sep = "\n" if text and not text.endswith("\n") else ""
        lines.append(f"{sep}mine_mode: {mode}\n")

    yaml_path.write_text("".join(lines), encoding="utf-8")
    return True
