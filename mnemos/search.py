"""Mnemos search engine — ChromaDB-backed semantic search with 3-layer filtering."""
from __future__ import annotations

import uuid
from typing import Any

import chromadb

from mnemos.config import MnemosConfig


class SearchEngine:
    """Indexes memory drawers in ChromaDB and provides semantic search with metadata filters."""

    COLLECTION_NAME = "mnemos_drawers"

    def __init__(self, config: MnemosConfig, in_memory: bool = False) -> None:
        if in_memory:
            # Use EphemeralClient for a truly isolated in-memory store per instance.
            # A unique collection name guards against any shared state in test runs.
            self._client = chromadb.EphemeralClient()
            collection_name = f"{self.COLLECTION_NAME}_{uuid.uuid4().hex}"
        else:
            self._client = chromadb.PersistentClient(
                path=str(config.chromadb_full_path)
            )
            collection_name = self.COLLECTION_NAME

        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_drawer(self, drawer_id: str, text: str, metadata: dict) -> None:
        """Upsert a drawer into the ChromaDB collection.

        ChromaDB only accepts str/int/float/bool metadata values.
        Lists are converted to comma-separated strings.
        """
        clean_meta: dict[str, Any] = {}
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)):
                clean_meta[key] = value
            elif isinstance(value, list):
                clean_meta[key] = ",".join(str(v) for v in value)
            else:
                clean_meta[key] = str(value)

        self._collection.upsert(
            ids=[drawer_id],
            documents=[text],
            metadatas=[clean_meta],
        )

    def delete_drawer(self, drawer_id: str) -> None:
        """Remove a drawer from the index. Silently ignores unknown IDs."""
        try:
            self._collection.delete(ids=[drawer_id])
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        wing: str | None = None,
        room: str | None = None,
        hall: str | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """Semantic search with optional metadata filters.

        Returns a list of dicts with keys: drawer_id, text, metadata, score.
        Score = 1.0 - cosine_distance (higher is more relevant).
        """
        where = self._build_where_filter(wing, room, hall)

        count = self._collection.count()
        if count == 0:
            return []

        n_results = min(limit, count)

        kwargs: dict[str, Any] = {
            "query_texts": [query],
            "n_results": n_results,
        }
        if where is not None:
            kwargs["where"] = where

        results = self._collection.query(**kwargs)

        output: list[dict] = []
        ids = results["ids"][0]
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        for drawer_id, text, meta, dist in zip(ids, documents, metadatas, distances):
            output.append(
                {
                    "drawer_id": drawer_id,
                    "text": text,
                    "metadata": meta,
                    "score": 1.0 - dist,
                }
            )

        return output

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return total drawer count and per-wing counts."""
        total = self._collection.count()
        wings: dict[str, int] = {}

        if total > 0:
            all_items = self._collection.get(include=["metadatas"])
            for meta in all_items["metadatas"]:
                wing_name = meta.get("wing", "")
                if wing_name:
                    wings[wing_name] = wings.get(wing_name, 0) + 1

        return {"total_drawers": total, "wings": wings}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_where_filter(
        self,
        wing: str | None,
        room: str | None,
        hall: str | None,
    ) -> dict | None:
        """Build a ChromaDB where filter from the supplied parameters.

        Single condition: {"wing": "X"}
        Multiple conditions: {"$and": [{"wing": "X"}, {"hall": "Y"}]}
        Returns None when no filters are specified.
        """
        conditions: list[dict] = []
        if wing is not None:
            conditions.append({"wing": wing})
        if room is not None:
            conditions.append({"room": room})
        if hall is not None:
            conditions.append({"hall": hall})

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}
