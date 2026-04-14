"""Mnemos search engine — ChromaDB-backed semantic search with 3-layer filtering."""
from __future__ import annotations

import hashlib
import uuid
from contextlib import nullcontext
from typing import Any

import chromadb
from filelock import FileLock

from mnemos.config import MnemosConfig


class SearchEngine:
    """Indexes memory drawers in ChromaDB and provides semantic search with metadata filters.

    Two collections are maintained:
    - ``mnemos_mined``  (formerly ``mnemos_drawers``) — mined fragments / knowledge units
    - ``mnemos_raw``    — verbatim file content chunks for MemPalace-matching recall

    Writes (upsert/delete) are serialized across processes with a file lock
    living next to the ChromaDB directory. Reads are not locked; ChromaDB
    allows single-writer / multi-reader access safely.
    """

    # Legacy name kept for backward compat; the mined collection uses this base.
    COLLECTION_NAME = "mnemos_drawers"
    MINED_COLLECTION_NAME = "mnemos_mined"
    RAW_COLLECTION_NAME = "mnemos_raw"

    # How long a writer will wait for the lock before failing (seconds).
    WRITE_LOCK_TIMEOUT = 120

    def __init__(self, config: MnemosConfig, in_memory: bool = False) -> None:
        if in_memory:
            # Use EphemeralClient for a truly isolated in-memory store per instance.
            # A unique suffix guards against any shared state in test runs.
            self._client = chromadb.EphemeralClient()
            uid = uuid.uuid4().hex
            mined_name = f"{self.MINED_COLLECTION_NAME}_{uid}"
            raw_name = f"{self.RAW_COLLECTION_NAME}_{uid}"
            self._write_lock = None  # no cross-process contention for ephemeral
        else:
            chroma_path = config.chromadb_full_path
            self._client = chromadb.PersistentClient(path=str(chroma_path))
            mined_name = self.MINED_COLLECTION_NAME
            raw_name = self.RAW_COLLECTION_NAME
            # Lock file lives next to chromadb — one lock guards all writes
            lock_path = chroma_path.parent / ".chromadb.write.lock"
            self._write_lock = FileLock(
                str(lock_path), timeout=self.WRITE_LOCK_TIMEOUT
            )

        self._collection = self._client.get_or_create_collection(
            name=mined_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._raw_collection = self._client.get_or_create_collection(
            name=raw_name,
            metadata={"hnsw:space": "cosine"},
        )

    def _writing(self):
        """Return a context manager that holds the cross-process write lock."""
        if self._write_lock is None:
            return nullcontext()
        return self._write_lock

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def raw_doc_id(source_path: str, chunk_index: int | None = None) -> str:
        """Return a stable document ID based on a SHA-256 hash of the source path.

        If *chunk_index* is supplied the hash input includes the index so each
        chunk gets a distinct, deterministic ID.
        """
        key = source_path if chunk_index is None else f"{source_path}::{chunk_index}"
        return hashlib.sha256(key.encode()).hexdigest()

    # ------------------------------------------------------------------
    # Indexing — mined / drawer collection
    # ------------------------------------------------------------------

    def index_drawer(self, drawer_id: str, text: str, metadata: dict) -> None:
        """Upsert a drawer into the mined ChromaDB collection.

        Backward-compatible with the original ``mnemos_drawers`` API.
        ChromaDB only accepts str/int/float/bool metadata values.
        Lists are converted to comma-separated strings.
        """
        clean_meta = self._clean_metadata(metadata)
        with self._writing():
            self._collection.upsert(
                ids=[drawer_id],
                documents=[text],
                metadatas=[clean_meta],
            )

    def delete_drawer(self, drawer_id: str) -> None:
        """Remove a drawer from the mined index. Silently ignores unknown IDs."""
        try:
            with self._writing():
                self._collection.delete(ids=[drawer_id])
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Indexing — raw collection
    # ------------------------------------------------------------------

    def index_raw(self, doc_id: str, text: str, metadata: dict) -> None:
        """Upsert verbatim file content into the raw ChromaDB collection.

        Use :meth:`raw_doc_id` to generate a stable deterministic *doc_id*.
        """
        clean_meta = self._clean_metadata(metadata)
        with self._writing():
            self._raw_collection.upsert(
                ids=[doc_id],
                documents=[text],
                metadatas=[clean_meta],
            )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        wing: str | list[str] | None = None,
        room: str | list[str] | None = None,
        hall: str | list[str] | None = None,
        exclude_wing: str | list[str] | None = None,
        limit: int = 5,
        collection: str = "both",
    ) -> list[dict]:
        """Semantic search with optional metadata filters.

        Parameters
        ----------
        query:
            Free-text query string.
        wing, room, hall:
            Scalar string → exact ``$eq`` match.
            List of strings → ``$in`` match (any of the listed values).
        exclude_wing:
            Scalar or list of wing values to exclude (``$nin``).
        limit:
            Maximum number of results to return.
        collection:
            ``"mined"`` — search the mined/drawer collection only.
            ``"raw"``   — search the raw collection only.
            ``"both"``  — search both and merge with Reciprocal Rank Fusion (RRF).

        Returns a list of dicts with keys: drawer_id, text, metadata, score.
        For *mined*-only or *raw*-only queries, score = 1 − cosine_distance.
        For *both*, score is the RRF-merged score.
        """
        if collection == "mined":
            return self._search_collection(
                self._collection, query, wing, room, hall, exclude_wing, limit
            )
        if collection == "raw":
            return self._search_collection(
                self._raw_collection, query, wing, room, hall, exclude_wing, limit
            )
        if collection == "both":
            return self._search_rrf(query, wing, room, hall, exclude_wing, limit)

        raise ValueError(f"collection must be 'mined', 'raw', or 'both'; got {collection!r}")

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return total drawer count, per-wing counts, and raw document count."""
        total = self._collection.count()
        raw_total = self._raw_collection.count()
        wings: dict[str, int] = {}

        if total > 0:
            batch_size = 500
            offset = 0
            while offset < total:
                batch = self._collection.get(
                    include=["metadatas"],
                    limit=batch_size,
                    offset=offset,
                )
                metas = batch["metadatas"]
                if not metas:
                    break
                for meta in metas:
                    wing_name = meta.get("wing", "")
                    if wing_name:
                        wings[wing_name] = wings.get(wing_name, 0) + 1
                offset += batch_size

        return {"total_drawers": total, "wings": wings, "raw_documents": raw_total}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_metadata(metadata: dict) -> dict[str, Any]:
        """Convert metadata values to ChromaDB-compatible scalar types.

        Lists become comma-separated strings; all other non-scalar types are
        cast to ``str``.
        """
        clean: dict[str, Any] = {}
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)):
                clean[key] = value
            elif isinstance(value, list):
                clean[key] = ",".join(str(v) for v in value)
            else:
                clean[key] = str(value)
        return clean

    def _build_where_filter(
        self,
        wing: str | list[str] | None,
        room: str | list[str] | None,
        hall: str | list[str] | None,
        exclude_wing: str | list[str] | None = None,
    ) -> dict | None:
        """Build a ChromaDB *where* filter from the supplied parameters.

        Scalar value → ``{"field": {"$eq": value}}``
        List value   → ``{"field": {"$in": [...]}}``
        exclude_wing → ``{"wing": {"$nin": [...]}}``

        Single condition: returned as-is.
        Multiple conditions: wrapped in ``{"$and": [...]}``.
        Returns ``None`` when no filters are specified.
        """
        conditions: list[dict] = []

        for field, value in [("wing", wing), ("room", room), ("hall", hall)]:
            if value is None:
                continue
            if isinstance(value, list):
                conditions.append({field: {"$in": value}})
            else:
                conditions.append({field: {"$eq": value}})

        if exclude_wing is not None:
            if isinstance(exclude_wing, str):
                exclude_wing = [exclude_wing]
            conditions.append({"wing": {"$nin": exclude_wing}})

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    def _search_collection(
        self,
        col: Any,
        query: str,
        wing: str | list[str] | None,
        room: str | list[str] | None,
        hall: str | list[str] | None,
        exclude_wing: str | list[str] | None,
        limit: int,
    ) -> list[dict]:
        """Run a query against a single ChromaDB collection and return formatted results."""
        where = self._build_where_filter(wing, room, hall, exclude_wing)

        count = col.count()
        if count == 0:
            return []

        n_results = min(limit, count)

        kwargs: dict[str, Any] = {
            "query_texts": [query],
            "n_results": n_results,
        }
        if where is not None:
            kwargs["where"] = where

        results = col.query(**kwargs)
        return self._format_results(results)

    @staticmethod
    def _format_results(results: dict) -> list[dict]:
        """Convert a raw ChromaDB query result into the standard output format."""
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

    @staticmethod
    def _rrf_score(ranks: list[int], k: int = 60) -> float:
        """Compute the Reciprocal Rank Fusion score for a document.

        score = Σ 1 / (k + rank)   where rank is 1-based.
        """
        return sum(1.0 / (k + rank) for rank in ranks)

    def _search_rrf(
        self,
        query: str,
        wing: str | list[str] | None,
        room: str | list[str] | None,
        hall: str | list[str] | None,
        exclude_wing: str | list[str] | None,
        limit: int,
        k: int = 60,
    ) -> list[dict]:
        """Search both collections and merge results with Reciprocal Rank Fusion.

        Each collection is queried for up to *limit* results.  Documents are
        ranked within their collection (1-based).  The RRF score for each
        unique document is the sum of ``1/(k+rank)`` across collections.
        Results are sorted by descending RRF score and truncated to *limit*.
        """
        # Fetch more candidates than limit for better RRF quality
        fetch_n = min(limit * 3, 30)
        mined_results = self._search_collection(
            self._collection, query, wing, room, hall, exclude_wing, fetch_n
        )
        raw_results = self._search_collection(
            self._raw_collection, query, wing, room, hall, exclude_wing, fetch_n
        )

        # Map doc_id → {drawer_id, text, metadata, rrf_ranks}
        merged: dict[str, dict] = {}

        for rank, hit in enumerate(mined_results, start=1):
            did = hit["drawer_id"]
            if did not in merged:
                merged[did] = {**hit, "_ranks": []}
            merged[did]["_ranks"].append(rank)

        for rank, hit in enumerate(raw_results, start=1):
            did = hit["drawer_id"]
            if did not in merged:
                merged[did] = {**hit, "_ranks": []}
            merged[did]["_ranks"].append(rank)

        # Compute RRF scores and sort
        output: list[dict] = []
        for entry in merged.values():
            ranks = entry.pop("_ranks")
            entry["score"] = self._rrf_score(ranks, k=k)
            output.append(entry)

        output.sort(key=lambda x: x["score"], reverse=True)
        return output[:limit]
