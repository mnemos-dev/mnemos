"""Tests for miner room hygiene: no tags→room, no wing==room, whitelist."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from mnemos.config import MnemosConfig
from mnemos.miner import Miner
from mnemos.room_detector import _ROOMS


ROOM_WHITELIST = set(_ROOMS.keys()) | {"general"}


def _write_session(tmp_path: Path, name: str, meta: dict, body: str) -> Path:
    p = tmp_path / name
    with p.open("w", encoding="utf-8") as f:
        f.write("---\n")
        f.write(yaml.safe_dump(meta, allow_unicode=True, sort_keys=False))
        f.write("---\n")
        f.write(body)
    return p


def test_frontmatter_tag_does_not_become_room(tmp_path: Path):
    """If tags=['architecture'] is in frontmatter but filename/content looks
    like session-log, the detected room should be session-log (or whatever
    detect_room returns), NOT 'architecture' just because it's tag[0]."""
    cfg = MnemosConfig(vault_path=str(tmp_path), languages=["en"])
    miner = Miner(cfg)

    src = _write_session(
        tmp_path,
        "2026-04-18-example-session.md",
        meta={"project": "TestProj", "tags": ["architecture"]},
        body=(
            "> User: we decided to use X\n\n"
            "Here is a long session discussion about the project. "
            "We walked through the code, ran the tests, and agreed on the plan. "
            "This is a session-log style note."
        ),
    )

    fragments = miner.mine_file(src)
    assert len(fragments) > 0
    for f in fragments:
        assert f["room"] != "architecture", \
            f"tag-derived 'architecture' should not become room, got {f['room']}"


def test_room_never_equals_wing(tmp_path: Path):
    """If detected room would equal the wing, flatten to 'general'."""
    cfg = MnemosConfig(vault_path=str(tmp_path), languages=["en"])
    miner = Miner(cfg)

    src = _write_session(
        tmp_path,
        "2026-04-18-mnemos-note.md",
        meta={"project": "Mnemos", "tags": ["mnemos"]},
        body="We mined a session. The project is Mnemos. Testing the room assignment.",
    )

    fragments = miner.mine_file(src)
    for f in fragments:
        assert f["wing"].lower() != f["room"].lower(), \
            f"wing=={f['wing']!r} and room=={f['room']!r} — should be flattened"


def test_all_rooms_in_whitelist(tmp_path: Path):
    """Every produced room must be in rooms.yaml keys or 'general'."""
    cfg = MnemosConfig(vault_path=str(tmp_path), languages=["en", "tr"])
    miner = Miner(cfg)

    cases = [
        ("2026-04-18-random.md", {"project": "X"}, "Discussion about something."),
        ("2026-04-18-with-tag.md", {"project": "Y", "tags": ["backend"]},
         "Backend code changes."),
        ("2026-04-18-title-tag.md", {"project": "Z",
         "tags": ["mnemos-—-obsidian-native-ai-memory-palace"]},
         "Prose content here."),
    ]

    for name, meta, body in cases:
        src = _write_session(tmp_path, name, meta, body)
        fragments = miner.mine_file(src)
        for f in fragments:
            assert f["room"] in ROOM_WHITELIST, \
                f"{name}: room {f['room']!r} not in whitelist"
