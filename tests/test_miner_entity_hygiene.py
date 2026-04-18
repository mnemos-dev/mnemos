"""Tests for entity hygiene — tags are not entities, case-preserve dedup."""
from __future__ import annotations

from pathlib import Path

import yaml

from mnemos.config import MnemosConfig
from mnemos.miner import Miner


def _write(tmp_path: Path, name: str, meta: dict, body: str) -> Path:
    p = tmp_path / name
    with p.open("w", encoding="utf-8") as f:
        f.write("---\n")
        f.write(yaml.safe_dump(meta, allow_unicode=True, sort_keys=False))
        f.write("---\n")
        f.write(body)
    return p


def test_frontmatter_tags_not_added_to_entities(tmp_path: Path):
    cfg = MnemosConfig(vault_path=str(tmp_path), languages=["en"])
    miner = Miner(cfg)

    src = _write(
        tmp_path, "2026-04-18-note.md",
        meta={"project": "Mnemos", "tags": ["session-log", "architecture"]},
        body="Plain session body for mining. We discussed things and decided on X.",
    )
    frags = miner.mine_file(src)
    assert len(frags) > 0
    for f in frags:
        assert "session-log" not in f["entities"]
        assert "architecture" not in f["entities"]


def test_entity_dedup_preserves_original_casing(tmp_path: Path):
    cfg = MnemosConfig(vault_path=str(tmp_path), languages=["en"])
    miner = Miner(cfg)

    src = _write(
        tmp_path, "2026-04-18-dedup.md",
        meta={"project": "Mnemos"},
        body=(
            "Mnemos is great. Talking about Mnemos and mnemos and MNEMOS. "
            "Also mcp and MCP references throughout."
        ),
    )
    frags = miner.mine_file(src)
    for f in frags:
        lower_entities = [e.lower() for e in f["entities"]]
        # No duplicates after lowercase
        assert len(lower_entities) == len(set(lower_entities))


def test_project_frontmatter_still_in_entities(tmp_path: Path):
    cfg = MnemosConfig(vault_path=str(tmp_path), languages=["en"])
    miner = Miner(cfg)

    src = _write(
        tmp_path, "2026-04-18-proj.md",
        meta={"project": "ProcureTrack", "tags": ["backend"]},
        body="ProcureTrack backend discussion. RFQ logic and approval flow.",
    )
    frags = miner.mine_file(src)
    for f in frags:
        # project field is still an entity (real identity)
        assert any(e.lower() == "procuretrack" for e in f["entities"])
        # but tag is not
        assert "backend" not in f["entities"]
