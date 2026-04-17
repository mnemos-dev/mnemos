"""Mnemos custom exception hierarchy.

Keep error classes here (not inside the module they most relate to) so
CLI entry points can catch `MnemosError` to render user-friendly
messages without importing every implementation module.
"""
from __future__ import annotations


class MnemosError(Exception):
    """Root of the mnemos exception tree."""


class BackendInitError(MnemosError):
    """A vector backend failed to initialise at runtime.

    Raised when the search factory cannot load or open the configured
    backend — HNSW binary corruption, sqlite-vec extension load failure,
    disk permission errors, etc. The message suggests migrating to the
    other backend so panicked users have a single copy-paste recovery
    path.
    """

    _OTHER = {"chromadb": "sqlite-vec", "sqlite-vec": "chromadb"}

    def __init__(self, backend: str, cause: BaseException) -> None:
        self.backend = backend
        self.cause = cause
        self.alternative = self._OTHER.get(backend, "chromadb")

        summary = (
            f"Failed to initialise search backend '{backend}': "
            f"{cause.__class__.__name__}: {cause}\n\n"
            f"If this looks like index corruption or a broken storage file, "
            f"switch backends with:\n"
            f"  mnemos migrate --backend {self.alternative}\n\n"
            f"Your Obsidian .md files are the source of truth — migrating "
            f"backs up the old index and rebuilds from them."
        )
        super().__init__(summary)
