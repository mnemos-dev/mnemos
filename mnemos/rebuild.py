"""Atomic rebuild of the mnemos palace.

See docs/specs/2026-04-18-v0.3.2-palace-hygiene-design.md §4.
"""
from __future__ import annotations

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
