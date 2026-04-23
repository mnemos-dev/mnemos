"""Cwd-aware SessionStart auto-briefing hook wrapper.

Called by Claude Code's SessionStart hook when `recall_mode: skill`. Decides
between fast-path (inject existing briefing + bg regen) and blocking catch-up
(sync refine + mine + brief for this cwd's unrefined JSONLs) based on a
per-cwd state file (.mnemos-cwd-state.json).

See docs/specs/2026-04-23-v0.4-task-4.3-first-ship-design.md for the full
decision tree.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any


STATE_FILENAME = ".mnemos-cwd-state.json"
CACHE_DIR = ".mnemos-briefings"
STATE_LOCK = STATE_FILENAME + ".flock"
CATCH_UP_LOCK = ".mnemos-catch-up.flock"
STALE_THRESHOLD = 3  # session-count diff that triggers sync regen in SUB-B1


# ---------------------------------------------------------------------------
# Cwd slug normalization
# ---------------------------------------------------------------------------

def cwd_to_slug(cwd: str) -> str:
    """Convert a cwd path to the Claude-Code-style slug used in project dirs.

    Rules:
      - Strip leading/trailing whitespace and trailing path separators
      - Replace any non-\\w-hyphen char with "-"
      - Collapse repeated dashes
      - Preserve underscores and letters (including Unicode word chars)
    """
    s = cwd.strip().rstrip("/\\")
    s = re.sub(r"[^\w-]", "-", s, flags=re.UNICODE)
    s = re.sub(r"-{2,}", "--", s)  # cap at double-dash (original pattern)
    return s


# ---------------------------------------------------------------------------
# State file
# ---------------------------------------------------------------------------

@dataclass
class CwdState:
    version: int = 1
    cwds: Dict[str, Dict[str, Any]] = field(default_factory=dict)


def load_state(vault: Path) -> CwdState:
    """Load cwd-state.json; return empty state if missing or corrupt."""
    path = vault / STATE_FILENAME
    if not path.exists():
        return CwdState()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return CwdState()
    if not isinstance(raw, dict):
        return CwdState()
    return CwdState(
        version=int(raw.get("version", 1)),
        cwds=dict(raw.get("cwds", {})),
    )


def save_state(vault: Path, state: CwdState) -> None:
    """Atomic write of state JSON (write-then-rename)."""
    path = vault / STATE_FILENAME
    tmp_path = vault / (STATE_FILENAME + ".tmp")
    data = {"version": state.version, "cwds": state.cwds}
    tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_path, path)


# ---------------------------------------------------------------------------
# Mode yaml inline read (mirror of auto_refine._read_mine_mode)
# ---------------------------------------------------------------------------

def read_recall_mode(vault: Path) -> str:
    """Return recall_mode from <vault>/mnemos.yaml (default: "script")."""
    yaml_path = vault / "mnemos.yaml"
    if not yaml_path.exists():
        return "script"
    try:
        text = yaml_path.read_text(encoding="utf-8")
    except OSError:
        return "script"
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("recall_mode:"):
            return s.split(":", 1)[1].strip().strip("'\"")
    return "script"


# ---------------------------------------------------------------------------
# Cache file (<vault>/.mnemos-briefings/<slug>.md)
# ---------------------------------------------------------------------------

def cache_path_for(vault: Path, cwd_slug: str) -> Path:
    return vault / CACHE_DIR / f"{cwd_slug}.md"


def read_cache_body(cache_path: Path) -> str:
    """Return cache body (frontmatter stripped). Empty string if missing/corrupt."""
    if not cache_path.exists():
        return ""
    try:
        text = cache_path.read_text(encoding="utf-8")
    except OSError:
        return ""
    m = re.match(r"^---\r?\n.*?\r?\n---\r?\n", text, re.DOTALL)
    if m:
        return text[m.end():].lstrip("\n")
    return text


def write_cache(
    cache_path: Path,
    body: str,
    cwd: str,
    session_count: int,
    drawer_count: int,
    generated_at: str | None = None,
) -> None:
    """Write cache file with frontmatter + body. Creates parent dir if needed."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if generated_at is None:
        from datetime import datetime
        generated_at = datetime.now().isoformat(timespec="seconds")
    front = (
        f"---\n"
        f"cwd: {cwd}\n"
        f"generated_at: {generated_at}\n"
        f"session_count_used: {session_count}\n"
        f"drawer_count_used: {drawer_count}\n"
        f"---\n\n"
    )
    cache_path.write_text(front + body.lstrip("\n"), encoding="utf-8")


# ---------------------------------------------------------------------------
# Session frontmatter counter for staleness check
# ---------------------------------------------------------------------------

def count_refined_sessions_for_cwd(vault: Path, cwd: str) -> int:
    """Count Sessions/*.md files whose frontmatter cwd matches exactly.

    Case-sensitive, trailing whitespace/slash on both sides trimmed before
    compare. Sessions without cwd frontmatter are excluded.
    """
    target = cwd.strip().rstrip("/\\")
    sessions_dir = vault / "Sessions"
    if not sessions_dir.exists():
        return 0
    count = 0
    for md in sessions_dir.glob("*.md"):
        try:
            text = md.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
        if not m:
            continue
        front = m.group(1)
        for line in front.splitlines():
            s = line.strip()
            if s.startswith("cwd:"):
                val = s.split(":", 1)[1].strip().strip("'\"")
                if val.rstrip("/\\") == target:
                    count += 1
                break
    return count


# ---------------------------------------------------------------------------
# Refine ledger + unrefined JSONL discovery
# ---------------------------------------------------------------------------

DEFAULT_REFINE_LEDGER = Path.home() / ".claude/skills/mnemos-refine-transcripts/state/processed.tsv"
DEFAULT_CLAUDE_PROJECTS = Path.home() / ".claude/projects"


def load_refine_ledger_jsonls(ledger: Path) -> set[str]:
    """Return set of JSONL abs paths with OK status in the refine ledger.

    Ledger format: <jsonl>\\t<status>\\t<session_md> (3 cols, tab-separated).
    """
    out: set[str] = set()
    if not ledger.exists():
        return out
    try:
        with ledger.open("r", encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                parts = raw.rstrip("\r\n").split("\t")
                if len(parts) < 3:
                    continue
                if parts[1] == "OK":
                    out.add(parts[0])
    except OSError:
        pass
    return out


def find_unrefined_jsonls_for_cwd(
    cwd_slug: str,
    projects_root: Path,
    ledger: Path,
) -> list[Path]:
    """List .jsonl files in ~/.claude/projects/<slug>/ NOT in refine ledger.

    Sorted by mtime (oldest first). The caller should also skip any JSONL
    whose PID marker indicates a live session.
    """
    proj_dir = projects_root / cwd_slug
    if not proj_dir.exists():
        return []
    processed = load_refine_ledger_jsonls(ledger)
    candidates: list[Path] = []
    for jsonl in proj_dir.glob("*.jsonl"):
        if str(jsonl) not in processed:
            candidates.append(jsonl)
    return sorted(candidates, key=lambda p: p.stat().st_mtime)


# ---------------------------------------------------------------------------
# Statusline status file (shared with auto_refine.STATUS_FILENAME)
# ---------------------------------------------------------------------------

STATUS_FILENAME = ".mnemos-hook-status.json"


def read_status(vault: Path) -> Dict[str, Any]:
    p = vault / STATUS_FILENAME
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def write_status(
    vault: Path,
    phase: str,
    current: int | None = None,
    total: int | None = None,
    cwd_slug: str | None = None,
    sub_phase: str | None = None,
    last_outcome: str | None = None,
) -> None:
    """Merge given fields into .mnemos-hook-status.json.

    Preserves fields written by other hooks (e.g. auto_refine's last_ok,
    last_skip, backlog) — only overwrites the keys we pass.
    """
    data = read_status(vault)
    data["phase"] = phase
    if current is not None:
        data["current"] = current
    if total is not None:
        data["total"] = total
    if cwd_slug is not None:
        data["cwd_slug"] = cwd_slug
    if sub_phase is not None:
        data["sub_phase"] = sub_phase
    elif phase != "idle":
        data.setdefault("sub_phase", "catch-up")
    if last_outcome is not None:
        data["last_outcome"] = last_outcome

    path = vault / STATUS_FILENAME
    tmp_path = vault / (STATUS_FILENAME + ".tmp")
    tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_path, path)


# ---------------------------------------------------------------------------
# Subprocess runners for skill invocations
# ---------------------------------------------------------------------------

import tempfile


@dataclass
class RefineResult:
    ok: bool
    jsonl: Path


@dataclass
class MineResult:
    ok: bool
    session_md: Path


@dataclass
class BriefResult:
    ok: bool
    body: str


def _default_runner(cmd) -> int:
    """Invoke claude subprocess; strip ANTHROPIC_API_KEY so subscription is used."""
    import subprocess
    kwargs: dict = {}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    kwargs["env"] = env
    try:
        return subprocess.call(list(cmd), **kwargs)
    except (FileNotFoundError, OSError):
        return 1


def _default_runner_stdout(cmd, stdout_path=None) -> int:
    """Like _default_runner but redirects stdout to the given file path."""
    import subprocess
    kwargs: dict = {}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    kwargs["env"] = env
    try:
        if stdout_path is not None:
            with open(stdout_path, "w", encoding="utf-8") as fh:
                return subprocess.call(list(cmd), stdout=fh, **kwargs)
        return subprocess.call(list(cmd), **kwargs)
    except (FileNotFoundError, OSError):
        return 1


def _build_skill_cmd(skill: str, arg: str) -> list[str]:
    """Build: claude --print --dangerously-skip-permissions --model sonnet "/<skill> <arg>" """
    return [
        "claude",
        "--print",
        "--dangerously-skip-permissions",
        "--model", "sonnet",
        f"/{skill} {arg}",
    ]


def run_refine_sync(jsonl: Path, runner=None) -> RefineResult:
    runner = runner or _default_runner
    cmd = _build_skill_cmd("mnemos-refine-transcripts", str(jsonl))
    rc = runner(cmd)
    return RefineResult(ok=(rc == 0), jsonl=jsonl)


def run_mine_sync(session_md: Path, runner=None) -> MineResult:
    runner = runner or _default_runner
    cmd = _build_skill_cmd("mnemos-mine-llm", str(session_md))
    rc = runner(cmd)
    return MineResult(ok=(rc == 0), session_md=session_md)


def run_brief_sync(cwd: str, runner=None) -> BriefResult:
    runner = runner or _default_runner_stdout
    cmd = _build_skill_cmd("mnemos-briefing", cwd)
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
    tmp_path = tmp.name
    tmp.close()
    try:
        rc = runner(cmd, stdout_path=tmp_path)
        if rc != 0:
            return BriefResult(ok=False, body="")
        body = Path(tmp_path).read_text(encoding="utf-8")
        return BriefResult(ok=True, body=body)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Main decision tree — handle_session_start
# ---------------------------------------------------------------------------

import time
import subprocess as _subprocess

VALID_SESSION_SOURCES = {"", "startup", "resume", "clear"}


@dataclass
class SessionStartInput:
    cwd: str
    source: str  # "startup" | "resume" | "clear" | "compact" | ""
    transcript_path: str


@dataclass
class HandleOutcome:
    outcome: str
    injected_context: str = ""


def _spawn_bg_brief(cwd: str) -> None:
    """Spawn a detached bg process that runs the briefing skill.

    Non-blocking. Errors are swallowed (diagnostic-only).
    """
    try:
        cmd = _build_skill_cmd("mnemos-briefing", cwd)
        kwargs: dict = {"stdout": _subprocess.DEVNULL, "stderr": _subprocess.DEVNULL}
        if os.name == "nt":
            kwargs["creationflags"] = getattr(_subprocess, "DETACHED_PROCESS", 0)
        env = os.environ.copy()
        env.pop("ANTHROPIC_API_KEY", None)
        kwargs["env"] = env
        _subprocess.Popen(cmd, **kwargs)
    except (OSError, FileNotFoundError):
        pass


def handle_session_start(
    inp: SessionStartInput,
    vault: Path,
    projects_root: Path,
    ledger: Path,
    subprocess_runner=None,
    brief_runner=None,
    bg_spawn=None,
) -> HandleOutcome:
    """Main decision tree. Returns HandleOutcome (no side effects to hook I/O).

    injected_context (if non-empty) is what the wrapper should emit as
    additionalContext JSON to Claude Code's stdout.
    """
    bg_spawn = bg_spawn or _spawn_bg_brief

    # Filter: bad source → exit
    if inp.source not in VALID_SESSION_SOURCES:
        return HandleOutcome(outcome="skipped_source")

    # Subagent dispatches
    if "/subagents/" in (inp.transcript_path or ""):
        return HandleOutcome(outcome="skipped_subagent")

    # Mode gate
    if read_recall_mode(vault) != "skill":
        return HandleOutcome(outcome="skipped_mode")

    # Load state
    state = load_state(vault)
    slug = cwd_to_slug(inp.cwd)
    now = time.time()

    cwd_info = state.cwds.get(slug)

    # CASE A — first visit ever
    if cwd_info is None:
        state.cwds[slug] = {
            "cwd": inp.cwd,
            "first_seen": now,
            "last_seen": now,
            "visit_count": 1,
            "last_session_id": None,
        }
        save_state(vault, state)
        return HandleOutcome(outcome="first_visit")

    # CASE B — return visit
    cwd_info["last_seen"] = now
    cwd_info["visit_count"] = cwd_info.get("visit_count", 1) + 1

    # Check for unrefined JSONLs in this cwd
    pending = find_unrefined_jsonls_for_cwd(
        cwd_slug=slug,
        projects_root=projects_root,
        ledger=ledger,
    )
    # Exclude the current live session's transcript
    live = Path(inp.transcript_path) if inp.transcript_path else None
    if live is not None:
        pending = [p for p in pending if p != live]

    if pending:
        # SUB-B2: blocking catch-up — implemented in Task 13
        return _run_sub_b2(
            inp=inp,
            vault=vault,
            state=state,
            cwd_info=cwd_info,
            pending=pending,
            ledger=ledger,
            subprocess_runner=subprocess_runner,
            brief_runner=brief_runner,
        )

    # SUB-B1 — no pending
    cache_p = cache_path_for(vault, slug)
    if cache_p.exists():
        # Staleness check
        try:
            cache_text = cache_p.read_text(encoding="utf-8")
            m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", cache_text, re.DOTALL)
            cached_n = 0
            if m:
                for line in m.group(1).splitlines():
                    s = line.strip()
                    if s.startswith("session_count_used:"):
                        try:
                            cached_n = int(s.split(":", 1)[1].strip().strip("'\""))
                        except ValueError:
                            cached_n = 0
                        break
        except OSError:
            cached_n = 0

        current_n = count_refined_sessions_for_cwd(vault, inp.cwd)

        if (current_n - cached_n) >= STALE_THRESHOLD:
            # SYNC regen
            write_status(vault, phase="briefing", cwd_slug=slug, sub_phase="stale-regen")
            result = run_brief_sync(inp.cwd, runner=brief_runner)
            write_status(vault, phase="idle", last_outcome="ok" if result.ok else "error")
            save_state(vault, state)
            if result.ok and result.body:
                write_cache(cache_p, body=result.body, cwd=inp.cwd, session_count=current_n, drawer_count=0)
                return HandleOutcome(outcome="sync_regen_injected", injected_context=result.body)
            return HandleOutcome(outcome="sync_regen_failed")

        # Fresh-enough → inject + bg regen
        body = read_cache_body(cache_p)
        bg_spawn(inp.cwd)
        save_state(vault, state)
        return HandleOutcome(outcome="fast_path_injected", injected_context=body)

    # No cache → bg spawn, no inject this turn
    bg_spawn(inp.cwd)
    save_state(vault, state)
    return HandleOutcome(outcome="fast_path_no_cache")


def _run_sub_b2(
    inp: SessionStartInput,
    vault: Path,
    state: CwdState,
    cwd_info: dict,
    pending: list[Path],
    ledger: Path,
    subprocess_runner,
    brief_runner,
) -> HandleOutcome:
    """Placeholder — SUB-B2 blocking catch-up implemented in Task 13."""
    save_state(vault, state)
    return HandleOutcome(outcome="sub_b2_pending_stub")
