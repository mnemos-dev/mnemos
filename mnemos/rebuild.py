"""Atomic rebuild of the mnemos palace.

See docs/specs/2026-04-18-v0.3.2-palace-hygiene-design.md §4.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from mnemos.config import MnemosConfig


class RebuildError(Exception):
    """Raised when rebuild cannot proceed or must abort."""


def _resolve_sources(
    cfg: MnemosConfig, explicit_path: str | None
) -> list[Path]:
    """Resolve the list of source directories to mine during rebuild.

    Order:
      1. *explicit_path* wins if given.
      2. ``cfg.mining_sources`` yaml entries if non-empty.
      3. Auto-discover ``<vault>/Sessions`` and ``<vault>/Topics`` if either
         exists.
      4. Raise :class:`RebuildError`.
    """
    vault_path = Path(cfg.vault_path)

    if explicit_path:
        p = Path(explicit_path)
        if not p.is_absolute():
            p = vault_path / p
        return [p]

    if cfg.mining_sources:
        out: list[Path] = []
        for src in cfg.mining_sources:
            p = Path(src.path)
            if not p.is_absolute():
                p = vault_path / p
            out.append(p)
        return out

    auto_paths: list[Path] = []
    for name in ("Sessions", "Topics"):
        candidate = vault_path / name
        if candidate.exists() and candidate.is_dir():
            auto_paths.append(candidate)
    if auto_paths:
        return auto_paths

    raise RebuildError(
        "No mining sources configured. Either:\n"
        "  - add `mining_sources` to mnemos.yaml, or\n"
        "  - pass an explicit path to `mnemos mine --rebuild <path>`, or\n"
        "  - create `Sessions/` or `Topics/` under the vault"
    )


def build_plan(cfg: MnemosConfig, explicit_path: str | None) -> dict:
    """Gather rebuild metadata without performing any action."""
    sources = _resolve_sources(cfg, explicit_path)
    per_source: list[dict] = []
    total_files = 0
    for src in sources:
        if src.is_file():
            files = [src]
        elif src.is_dir():
            files = list(src.rglob("*.md"))
        else:
            files = []
        per_source.append({"path": str(src), "file_count": len(files)})
        total_files += len(files)

    existing_drawers = 0
    if cfg.wings_dir.exists():
        existing_drawers = sum(
            1 for p in cfg.wings_dir.rglob("*.md")
            if not p.name.startswith("_")
        )

    ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    return {
        "sources": per_source,
        "source_count": total_files,
        "existing_drawer_count": existing_drawers,
        "backup_path": str(cfg.recycled_full_path / f"wings-{ts}"),
        "timestamp": ts,
    }


def format_plan(plan: dict) -> str:
    lines = ["Rebuild plan:"]
    src_parts = [
        f"{Path(s['path']).name} ({s['file_count']} files)"
        for s in plan["sources"]
    ]
    lines.append(f"  Sources: {', '.join(src_parts)} = {plan['source_count']} files")
    lines.append(f"  Current drawers: {plan['existing_drawer_count']}")
    lines.append(f"  Backup: {plan['backup_path']}")
    return "\n".join(lines)
