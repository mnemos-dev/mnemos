"""v1.2.2 — SessionEnd stale-OK supersession.

When a JSONL is refined while its session is still actively writing
(typical /resume scenario: user closed Claude Code, opened it again,
typed `/resume <id>`, kept working — between the close and resume a
sibling window's SessionStart auto_refine could have picked the JSONL
during an idle window and marked it OK), the resulting ledger entry
describes only a subset of the now-final transcript. SessionEnd is the
authoritative moment to detect this — the JSONL is now closed and any
post-refine content represents a real content gap.

These tests cover ``supersede_stale_refine_if_needed`` which the
SessionEnd worker calls before ``claim_jsonl_for_refine`` so the next
refine produces a Session/.md describing the full content.
"""
from __future__ import annotations

import os
import time
from pathlib import Path


def _make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "Sessions").mkdir(parents=True)
    return vault


def test_supersede_when_jsonl_grew_after_prior_refine(tmp_path: Path) -> None:
    """JSONL mtime > prior Session/.md mtime by > threshold => supersede.

    The old Session/.md is renamed with a `.bak-superseded-<utc>` suffix
    and the OK ledger row is dropped so a follow-up refine can claim
    afresh and write the full-content Session/.md.
    """
    from mnemos.session_end_hook import supersede_stale_refine_if_needed

    vault = _make_vault(tmp_path)
    sessions_dir = vault / "Sessions"
    ledger = tmp_path / "processed.tsv"

    # Old Session/.md — refined an hour ago
    old_session = sessions_dir / "2026-04-28-old-slug.md"
    old_session.write_text("---\ndate: 2026-04-28\n---\nold body", encoding="utf-8")
    one_hour_ago = time.time() - 3600
    os.utime(old_session, (one_hour_ago, one_hour_ago))

    # JSONL — written to "now" (after the prior refine)
    jsonl = tmp_path / "session-3078.jsonl"
    jsonl.write_text("entry1\nentry2\n", encoding="utf-8")

    # Ledger has prior OK row pointing to old_session (Sessions/-relative
    # filename in column 3, matching auto_refine._latest_session_for_jsonl).
    ledger.write_text(f"{jsonl}\tOK\t2026-04-28-old-slug.md\n", encoding="utf-8")

    superseded = supersede_stale_refine_if_needed(jsonl, ledger, vault)

    assert superseded is True
    assert not old_session.exists(), "old Session/.md should be renamed"
    backups = list(sessions_dir.glob("2026-04-28-old-slug.md.bak-superseded-*"))
    assert len(backups) == 1, f"expected one backup, got {[p.name for p in sessions_dir.iterdir()]}"

    text = ledger.read_text(encoding="utf-8")
    assert str(jsonl) not in text, "ledger row for the JSONL should be dropped"
    assert "2026-04-28-old-slug.md" not in text


def test_no_supersede_when_jsonl_older_than_session_md(tmp_path: Path) -> None:
    """JSONL mtime <= Session/.md mtime => leave everything in place.

    This is the normal post-refine state: the worker writes the
    Session/.md right after `claude --print` returns; the JSONL is
    older. A second SessionEnd shouldn't churn this.
    """
    from mnemos.session_end_hook import supersede_stale_refine_if_needed

    vault = _make_vault(tmp_path)
    sessions_dir = vault / "Sessions"
    ledger = tmp_path / "processed.tsv"

    # JSONL — closed an hour ago
    jsonl = tmp_path / "stable.jsonl"
    jsonl.write_text("content", encoding="utf-8")
    one_hour_ago = time.time() - 3600
    os.utime(jsonl, (one_hour_ago, one_hour_ago))

    # Session/.md — fresh
    session_md = sessions_dir / "2026-04-28-stable.md"
    session_md.write_text("body", encoding="utf-8")

    ledger.write_text(f"{jsonl}\tOK\t2026-04-28-stable.md\n", encoding="utf-8")

    superseded = supersede_stale_refine_if_needed(jsonl, ledger, vault)

    assert superseded is False
    assert session_md.exists()
    assert "2026-04-28-stable.md" in ledger.read_text(encoding="utf-8")


def test_no_supersede_when_no_prior_entry(tmp_path: Path) -> None:
    """Empty ledger / no row for this JSONL => no-op."""
    from mnemos.session_end_hook import supersede_stale_refine_if_needed

    vault = _make_vault(tmp_path)
    ledger = tmp_path / "processed.tsv"
    ledger.write_text("", encoding="utf-8")

    jsonl = tmp_path / "fresh.jsonl"
    jsonl.write_text("content", encoding="utf-8")

    assert supersede_stale_refine_if_needed(jsonl, ledger, vault) is False


def test_no_supersede_when_prior_entry_is_skip(tmp_path: Path) -> None:
    """SKIP rows are sticky — they record an explicit "no Session/.md needed"
    decision (1-turn noise, etc.). Don't overwrite them based on mtime.
    """
    from mnemos.session_end_hook import supersede_stale_refine_if_needed

    vault = _make_vault(tmp_path)
    ledger = tmp_path / "processed.tsv"

    jsonl = tmp_path / "skipped.jsonl"
    jsonl.write_text("content", encoding="utf-8")

    ledger.write_text(f"{jsonl}\tSKIP\t1-turn-noop\n", encoding="utf-8")

    assert supersede_stale_refine_if_needed(jsonl, ledger, vault) is False
    assert "SKIP" in ledger.read_text(encoding="utf-8")


def test_no_supersede_when_session_md_missing(tmp_path: Path) -> None:
    """Ledger says OK but the Session/.md was deleted manually — leave the
    ledger alone. The next refine will silently skip via the existing
    ledger=OK gate; that's the same behavior as today.
    """
    from mnemos.session_end_hook import supersede_stale_refine_if_needed

    vault = _make_vault(tmp_path)
    ledger = tmp_path / "processed.tsv"

    jsonl = tmp_path / "orphaned.jsonl"
    jsonl.write_text("content", encoding="utf-8")

    # Ledger row points to a nonexistent Session/.md
    ledger.write_text(f"{jsonl}\tOK\t2026-04-28-deleted.md\n", encoding="utf-8")

    assert supersede_stale_refine_if_needed(jsonl, ledger, vault) is False
    assert "2026-04-28-deleted.md" in ledger.read_text(encoding="utf-8")


def test_threshold_absorbs_minor_mtime_noise(tmp_path: Path) -> None:
    """JSONL mtime that's only seconds newer than Session/.md (typical
    of the same refine round) doesn't trigger supersession.
    """
    from mnemos.session_end_hook import supersede_stale_refine_if_needed

    vault = _make_vault(tmp_path)
    sessions_dir = vault / "Sessions"
    ledger = tmp_path / "processed.tsv"

    session_md = sessions_dir / "2026-04-28-tight.md"
    session_md.write_text("body", encoding="utf-8")
    base = time.time() - 100
    os.utime(session_md, (base, base))

    jsonl = tmp_path / "tight.jsonl"
    jsonl.write_text("content", encoding="utf-8")
    # JSONL only 5s newer — within threshold
    os.utime(jsonl, (base + 5, base + 5))

    ledger.write_text(f"{jsonl}\tOK\t2026-04-28-tight.md\n", encoding="utf-8")

    assert supersede_stale_refine_if_needed(jsonl, ledger, vault) is False
    assert session_md.exists()
