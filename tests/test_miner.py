"""Tests for mnemos.miner — hybrid regex + LLM mining engine."""
from __future__ import annotations

from pathlib import Path

import pytest

from mnemos.miner import (
    Miner,
    chunk_exchanges,
    chunk_text,
    classify_segment,
    detect_language,
    extract_entities_from_path,
)


# ---------------------------------------------------------------------------
# detect_language
# ---------------------------------------------------------------------------


def test_detect_language_turkish():
    text = (
        "Supabase ile gittik ve karar aldık. "
        "Bu kararı bir daha değiştirmeyeceğiz. "
        "Şu an için en iyi seçenek bu."
    )
    assert detect_language(text) == "tr"


def test_detect_language_english():
    text = (
        "We decided to use Supabase for the backend. "
        "The decision is final and we agreed to proceed. "
        "This is the best practice for our use case."
    )
    assert detect_language(text) == "en"


# ---------------------------------------------------------------------------
# chunk_text
# ---------------------------------------------------------------------------


def test_chunk_text():
    """Overlapping chunks: second chunk starts before end of first."""
    words = ["word"] * 300
    text = " ".join(words)  # 300 words × 5 chars + spaces ≈ 1799 chars
    chunks = chunk_text(text, chunk_size=800, overlap=100)
    assert len(chunks) >= 2
    # Verify overlap: last 100 chars of chunk[0] appear at the start of chunk[1]
    overlap_end = chunks[0][-100:]
    assert chunks[1].startswith(overlap_end[:10])


def test_chunk_text_short():
    """Text shorter than chunk_size returns a single chunk."""
    text = "Short text that is well under 800 characters but above the minimum size threshold."
    chunks = chunk_text(text, chunk_size=800, overlap=100)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_minimum():
    """Text below min_size returns empty list."""
    text = "Hi"
    chunks = chunk_text(text, chunk_size=800, overlap=100, min_size=50)
    assert chunks == []


# ---------------------------------------------------------------------------
# extract_entities_from_path
# ---------------------------------------------------------------------------


def test_extract_entities_from_path():
    path = Path("/vault/Sessions/2026-04-10-ProcureTrack.md")
    entities = extract_entities_from_path(path)
    # Should find CamelCase "ProcureTrack" and/or capitalised words from the stem
    assert any("ProcureTrack" in e or "Procure" in e or "Track" in e for e in entities)


# ---------------------------------------------------------------------------
# chunk_exchanges
# ---------------------------------------------------------------------------


def test_chunk_exchanges_basic():
    transcript = "> What is RLS?\nRow Level Security controls access.\n\n> How to enable?\nUse ALTER TABLE.\n\n> Any caveats?\nYes, performance overhead."
    # Use a small max_chunk so the exchanges split into multiple chunks
    chunks = chunk_exchanges(transcript, max_chunk=80)
    assert chunks is not None
    assert len(chunks) >= 2
    assert "> What is RLS?" in chunks[0]
    assert "Row Level Security" in chunks[0]


def test_chunk_exchanges_large_response():
    user = "> Tell me everything about databases"
    response = "A " * 2000  # ~4000 chars
    # Need 3+ '>' markers
    extra = "\n\n> Second question\nShort answer.\n\n> Third question\nAnother answer."
    transcript = f"{user}\n{response}\n\n> Follow up?\nMore info.{extra}"
    chunks = chunk_exchanges(transcript, max_chunk=3000)
    assert chunks is not None
    assert len(chunks) >= 2
    assert chunks[0].startswith("> Tell me")


def test_chunk_exchanges_non_conversation():
    text = "Regular markdown without any > markers."
    assert chunk_exchanges(text) is None


# ---------------------------------------------------------------------------
# classify_segment
# ---------------------------------------------------------------------------


def test_classify_segment_decision():
    text = "We decided to use Supabase because of its RLS capabilities. The trade-off was worth it."
    hall, confidence = classify_segment(text, "en")
    assert hall == "decisions"
    assert confidence >= 0.3


def test_classify_segment_problem():
    text = "There's a critical bug in the auth module. The root cause is a race condition."
    hall, confidence = classify_segment(text, "en")
    assert hall == "problems"


def test_classify_segment_disambiguation():
    text = "The crash bug was fixed yesterday. Got it working after long debugging."
    hall, confidence = classify_segment(text, "en")
    assert hall == "events"


def test_classify_segment_low_confidence():
    text = "Just a random sentence."
    hall, confidence = classify_segment(text, "en")
    assert hall is None


def test_classify_segment_turkish():
    text = "Supabase ile gitmeye karar verdik çünkü RLS desteği var."
    hall, confidence = classify_segment(text, "tr")
    assert hall == "decisions"


# ---------------------------------------------------------------------------
# Miner.mine_file — Turkish
# ---------------------------------------------------------------------------


def test_regex_mining_turkish(config, sample_session_tr):
    miner = Miner(config)
    results = miner.mine_file(sample_session_tr)
    assert len(results) > 0
    # All results should be dicts with required keys
    required_keys = {"wing", "room", "hall", "text", "entities", "language", "source"}
    for r in results:
        assert required_keys.issubset(r.keys()), f"Missing keys in result: {r}"
    # Language should be detected as Turkish
    langs = {r["language"] for r in results}
    assert "tr" in langs


# ---------------------------------------------------------------------------
# Miner.mine_file — English
# ---------------------------------------------------------------------------


def test_regex_mining_english(config, sample_session_en):
    miner = Miner(config)
    results = miner.mine_file(sample_session_en)
    assert len(results) > 0
    required_keys = {"wing", "room", "hall", "text", "entities", "language", "source"}
    for r in results:
        assert required_keys.issubset(r.keys()), f"Missing keys in result: {r}"
    # Language should be detected as English
    langs = {r["language"] for r in results}
    assert "en" in langs


# ---------------------------------------------------------------------------
# Wing assignment from frontmatter
# ---------------------------------------------------------------------------


def test_wing_assignment_from_frontmatter(config, sample_session_tr):
    """Wing should be 'ProcureTrack' — the project field from frontmatter."""
    miner = Miner(config)
    results = miner.mine_file(sample_session_tr)
    assert len(results) > 0
    wings = {r["wing"] for r in results}
    assert "ProcureTrack" in wings


def test_wing_override_beats_frontmatter(config, sample_session_tr):
    """wing_override must take precedence over frontmatter ``project``.

    Use case: mining Claude Code memory/ dirs and JSONL transcripts where
    the project is known from the parent directory, not the file itself.
    """
    miner = Miner(config)
    results = miner.mine_file(sample_session_tr, wing_override="Mnemos")
    assert len(results) > 0
    wings = {r["wing"] for r in results}
    assert wings == {"Mnemos"}
