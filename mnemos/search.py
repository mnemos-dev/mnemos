"""Mnemos search — pluggable vector backends behind a single SearchEngine facade.

Two backends are available:
  - ``chromadb``   — ChromaDB PersistentClient (default historically).
  - ``sqlite-vec`` — sqlite-vec extension + manual embeddings. More robust on
                     Windows/Python 3.14 where ChromaDB 1.x HNSW flushes are
                     unreliable.

Pick the backend via ``config.search_backend``. Both backends share the same
public API (index_drawer, delete_drawer, index_raw, search, get_stats, close).
"""
from __future__ import annotations

import hashlib
import sqlite3
import struct
import uuid
from abc import ABC, abstractmethod
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Iterable

import chromadb
from filelock import FileLock

from mnemos.config import MnemosConfig


# ---------------------------------------------------------------------------
# Abstract backend
# ---------------------------------------------------------------------------


class SearchBackend(ABC):
    """Common contract for mnemos search backends.

    A backend maintains two logical collections:
      - *mined*: classified knowledge fragments
      - *raw*:   verbatim chunks of source content

    Search can target either collection or merge both with Reciprocal Rank
    Fusion (RRF). Writes should be safe across processes (use a file lock).
    """

    @staticmethod
    def raw_doc_id(source_path: str, chunk_index: int | None = None) -> str:
        """Stable SHA-256 document ID from source path (+ optional chunk index)."""
        key = source_path if chunk_index is None else f"{source_path}::{chunk_index}"
        return hashlib.sha256(key.encode()).hexdigest()

    @abstractmethod
    def index_drawer(self, drawer_id: str, text: str, metadata: dict) -> None: ...

    @abstractmethod
    def delete_drawer(self, drawer_id: str) -> None: ...

    @abstractmethod
    def index_raw(self, doc_id: str, text: str, metadata: dict) -> None: ...

    def index_drawers_bulk(
        self, items: list[tuple[str, str, dict]]
    ) -> None:
        """Bulk insert for the mined collection.

        *items* is an iterable of ``(drawer_id, text, metadata)`` tuples.
        Default implementation falls back to sequential index_drawer calls;
        backends override for batched embedding and a single transaction.
        """
        for drawer_id, text, metadata in items:
            self.index_drawer(drawer_id, text, metadata)

    def index_raw_bulk(
        self, items: list[tuple[str, str, dict]]
    ) -> None:
        """Bulk insert for the raw collection (same semantics as index_drawers_bulk)."""
        for doc_id, text, metadata in items:
            self.index_raw(doc_id, text, metadata)

    @abstractmethod
    def search(
        self,
        query: str,
        wing: str | list[str] | None = None,
        room: str | list[str] | None = None,
        hall: str | list[str] | None = None,
        exclude_wing: str | list[str] | None = None,
        limit: int = 5,
        collection: str = "both",
    ) -> list[dict]: ...

    @abstractmethod
    def get_stats(self) -> dict: ...

    def storage_path(self) -> Path | None:
        """Return the on-disk path for this backend's index, or None in memory.

        Used by ``mnemos status`` to show users which file/directory backs the
        current vector index. File-based backends (sqlite-vec) return a
        concrete file; directory-based backends (ChromaDB) return the root
        dir. In-memory backends return ``None``.

        Default returns ``None`` — subclasses override.
        """
        return None

    def close(self) -> None:  # noqa: D401
        """Optional hook for flushing/closing resources before exit."""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


# ---------------------------------------------------------------------------
# Shared helpers (metadata cleaning, RRF)
# ---------------------------------------------------------------------------


def _path_size_bytes(path: Path | None) -> int:
    """Total bytes consumed by *path* — file size, or recursive dir size.

    Returns 0 when the path is None, missing, or unreadable. Swallows per-file
    errors so a half-written index still produces a best-effort total.
    """
    if path is None or not path.exists():
        return 0
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            try:
                total += child.stat().st_size
            except OSError:
                continue
    return total


def _dedup_by_id(
    items: list[tuple[str, str, dict]],
) -> list[tuple[str, str, dict]]:
    """Collapse duplicate drawer IDs in a bulk-upsert batch, last write wins.

    Miner pipelines occasionally emit two drawers with the same ID when two
    chunks share a slugged prefix (e.g. short repeated user replies). Both
    backends reject duplicates within a single batch (Chroma DuplicateIDError
    and sqlite UNIQUE on vec_*), so we dedup here with upsert semantics.
    """
    by_id: dict[str, tuple[str, str, dict]] = {}
    for item in items:
        by_id[item[0]] = item
    return list(by_id.values())


def _clean_metadata(metadata: dict) -> dict[str, Any]:
    """Coerce metadata values to scalar types suitable for backend storage."""
    clean: dict[str, Any] = {}
    for key, value in metadata.items():
        if isinstance(value, (str, int, float, bool)):
            clean[key] = value
        elif isinstance(value, list):
            clean[key] = ",".join(str(v) for v in value)
        else:
            clean[key] = str(value)
    return clean


def _rrf_score(ranks: list[int], k: int = 60) -> float:
    return sum(1.0 / (k + rank) for rank in ranks)


def _merge_rrf(
    mined: list[dict], raw: list[dict], limit: int, k: int = 60
) -> list[dict]:
    """Reciprocal Rank Fusion across two already-ranked result lists."""
    merged: dict[str, dict] = {}
    for rank, hit in enumerate(mined, start=1):
        did = hit["drawer_id"]
        if did not in merged:
            merged[did] = {**hit, "_ranks": []}
        merged[did]["_ranks"].append(rank)
    for rank, hit in enumerate(raw, start=1):
        did = hit["drawer_id"]
        if did not in merged:
            merged[did] = {**hit, "_ranks": []}
        merged[did]["_ranks"].append(rank)

    output: list[dict] = []
    for entry in merged.values():
        ranks = entry.pop("_ranks")
        entry["score"] = _rrf_score(ranks, k=k)
        output.append(entry)
    output.sort(key=lambda x: x["score"], reverse=True)
    return output[:limit]


# ---------------------------------------------------------------------------
# ChromaDB backend
# ---------------------------------------------------------------------------


class ChromaBackend(SearchBackend):
    """SearchBackend implementation backed by chromadb.PersistentClient."""

    COLLECTION_NAME = "mnemos_drawers"
    MINED_COLLECTION_NAME = "mnemos_mined"
    RAW_COLLECTION_NAME = "mnemos_raw"

    WRITE_LOCK_TIMEOUT = 120

    def __init__(self, config: MnemosConfig, in_memory: bool = False) -> None:
        if in_memory:
            self._client = chromadb.EphemeralClient()
            uid = uuid.uuid4().hex
            mined_name = f"{self.MINED_COLLECTION_NAME}_{uid}"
            raw_name = f"{self.RAW_COLLECTION_NAME}_{uid}"
            self._write_lock = None
            self._storage_path: Path | None = None
        else:
            chroma_path = config.chromadb_full_path
            self._client = chromadb.PersistentClient(path=str(chroma_path))
            mined_name = self.MINED_COLLECTION_NAME
            raw_name = self.RAW_COLLECTION_NAME
            lock_path = chroma_path.parent / ".chromadb.write.lock"
            self._write_lock = FileLock(
                str(lock_path), timeout=self.WRITE_LOCK_TIMEOUT
            )
            self._storage_path = chroma_path

        self._collection = self._client.get_or_create_collection(
            name=mined_name, metadata={"hnsw:space": "cosine"},
        )
        self._raw_collection = self._client.get_or_create_collection(
            name=raw_name, metadata={"hnsw:space": "cosine"},
        )

    def _writing(self):
        if self._write_lock is None:
            return nullcontext()
        return self._write_lock

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass

    def index_drawer(self, drawer_id: str, text: str, metadata: dict) -> None:
        clean_meta = _clean_metadata(metadata)
        with self._writing():
            self._collection.upsert(
                ids=[drawer_id], documents=[text], metadatas=[clean_meta],
            )

    def delete_drawer(self, drawer_id: str) -> None:
        try:
            with self._writing():
                self._collection.delete(ids=[drawer_id])
        except Exception:
            pass

    def index_raw(self, doc_id: str, text: str, metadata: dict) -> None:
        clean_meta = _clean_metadata(metadata)
        with self._writing():
            self._raw_collection.upsert(
                ids=[doc_id], documents=[text], metadatas=[clean_meta],
            )

    def _bulk_upsert(self, col, items: list[tuple[str, str, dict]]) -> None:
        if not items:
            return
        items = _dedup_by_id(items)
        ids = [i[0] for i in items]
        docs = [i[1] for i in items]
        metas = [_clean_metadata(i[2]) for i in items]
        with self._writing():
            col.upsert(ids=ids, documents=docs, metadatas=metas)

    def index_drawers_bulk(self, items: list[tuple[str, str, dict]]) -> None:
        self._bulk_upsert(self._collection, items)

    def index_raw_bulk(self, items: list[tuple[str, str, dict]]) -> None:
        self._bulk_upsert(self._raw_collection, items)

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
        if collection == "mined":
            return self._search_collection(self._collection, query, wing, room, hall, exclude_wing, limit)
        if collection == "raw":
            return self._search_collection(self._raw_collection, query, wing, room, hall, exclude_wing, limit)
        if collection == "both":
            fetch_n = min(limit * 3, 30)
            m = self._search_collection(self._collection, query, wing, room, hall, exclude_wing, fetch_n)
            r = self._search_collection(self._raw_collection, query, wing, room, hall, exclude_wing, fetch_n)
            return _merge_rrf(m, r, limit)
        raise ValueError(f"collection must be 'mined', 'raw', or 'both'; got {collection!r}")

    def get_stats(self) -> dict:
        total = self._collection.count()
        raw_total = self._raw_collection.count()
        wings: dict[str, int] = {}
        if total > 0:
            batch_size = 500
            offset = 0
            while offset < total:
                batch = self._collection.get(
                    include=["metadatas"], limit=batch_size, offset=offset,
                )
                metas = batch["metadatas"]
                if not metas:
                    break
                for meta in metas:
                    wing_name = meta.get("wing", "")
                    if wing_name:
                        wings[wing_name] = wings.get(wing_name, 0) + 1
                offset += batch_size
        return {
            "total_drawers": total,
            "wings": wings,
            "raw_documents": raw_total,
            "storage_bytes": _path_size_bytes(self._storage_path),
        }

    def storage_path(self) -> Path | None:
        return self._storage_path

    # ------------------------------------------------------------------
    # ChromaDB-specific helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_where_filter(
        wing, room, hall, exclude_wing,
    ) -> dict | None:
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
        self, col, query, wing, room, hall, exclude_wing, limit,
    ) -> list[dict]:
        where = self._build_where_filter(wing, room, hall, exclude_wing)
        count = col.count()
        if count == 0:
            return []
        n_results = min(limit, count)
        kwargs: dict[str, Any] = {"query_texts": [query], "n_results": n_results}
        if where is not None:
            kwargs["where"] = where
        results = col.query(**kwargs)
        return self._format_results(results)

    @staticmethod
    def _format_results(results: dict) -> list[dict]:
        output: list[dict] = []
        ids = results["ids"][0]
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]
        for drawer_id, text, meta, dist in zip(ids, documents, metadatas, distances):
            output.append({
                "drawer_id": drawer_id,
                "text": text,
                "metadata": meta,
                "score": _clamp_unit(1.0 - float(dist)),
            })
        return output


# ---------------------------------------------------------------------------
# SQLite-vec backend
# ---------------------------------------------------------------------------


def _serialize_vec(vec: Iterable[float]) -> bytes:
    """Pack a float vector for sqlite-vec BLOB storage."""
    vec_list = list(vec)
    return struct.pack(f"{len(vec_list)}f", *vec_list)


def _clamp_unit(x: float) -> float:
    """Clamp *x* into [0, 1]. Backend distance math can produce values a
    few float32 ULPs outside the interval for near-identical vectors."""
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def _l2_to_cosine_sim(l2_dist: float) -> float:
    """Convert L2 distance between unit-length vectors to cosine similarity.

    sqlite-vec's vec0 virtual table defaults to L2 distance. For unit vectors
    u, v the identity ``||u - v||² = 2(1 - u·v)`` gives
    ``cos_sim = 1 - L2² / 2``. Clamped to [0, 1] so callers can treat score
    as a similarity monotonically increasing with relevance.
    """
    return _clamp_unit(1.0 - (l2_dist * l2_dist) / 2.0)


def _l2_normalize(vec: list[float]) -> list[float]:
    """Return *vec* scaled to unit length. A zero vector is returned unchanged."""
    norm_sq = 0.0
    for x in vec:
        norm_sq += x * x
    if norm_sq <= 0.0:
        return vec
    inv = 1.0 / (norm_sq ** 0.5)
    return [x * inv for x in vec]


class SqliteVecBackend(SearchBackend):
    """SearchBackend implementation using the sqlite-vec extension.

    Storage: a single SQLite file at ``<palace>/search.sqlite3`` containing:
      - ``mined`` / ``raw``: metadata + document text (normal tables)
      - ``vec_mined`` / ``vec_raw``: sqlite-vec virtual tables holding embeddings

    Embeddings are produced once via ChromaDB's DefaultEmbeddingFunction so we
    stay compatible with data previously indexed by ChromaBackend.
    """

    EMBED_DIM = 384  # all-MiniLM-L6-v2 dimension
    WRITE_LOCK_TIMEOUT = 120

    def __init__(self, config: MnemosConfig, in_memory: bool = False) -> None:
        import sqlite_vec

        if in_memory:
            self._db_path: Path | None = None
            self._lock: FileLock | None = None
            self._conn = self._open_conn(":memory:", sqlite_vec)
        else:
            palace = Path(config.vault_path) / config.palace_root
            palace.mkdir(parents=True, exist_ok=True)
            self._db_path = palace / "search.sqlite3"
            lock_path = palace / ".search.write.lock"
            self._lock = FileLock(str(lock_path), timeout=self.WRITE_LOCK_TIMEOUT)
            self._conn = self._open_conn(str(self._db_path), sqlite_vec)

        self._init_schema()
        self._embed_fn = self._make_embed_fn()

    # ------------------------------------------------------------------
    # Connection / schema
    # ------------------------------------------------------------------

    @staticmethod
    def _open_conn(path: str, sqlite_vec_mod) -> sqlite3.Connection:
        conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.enable_load_extension(True)
        sqlite_vec_mod.load(conn)
        conn.enable_load_extension(False)
        return conn

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mined (
                    id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    wing TEXT,
                    room TEXT,
                    hall TEXT,
                    metadata_json TEXT
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS raw (
                    id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    wing TEXT,
                    room TEXT,
                    hall TEXT,
                    metadata_json TEXT
                )
                """
            )
            self._conn.execute(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_mined USING vec0("
                f"id TEXT PRIMARY KEY, embedding float[{self.EMBED_DIM}])"
            )
            self._conn.execute(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_raw USING vec0("
                f"id TEXT PRIMARY KEY, embedding float[{self.EMBED_DIM}])"
            )
            for field in ("wing", "room", "hall"):
                self._conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_mined_{field} ON mined({field})"
                )
                self._conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_raw_{field} ON raw({field})"
                )

    @staticmethod
    def _make_embed_fn():
        """Return a callable(list[str]) -> list[list[float]].

        Reuses ChromaDB's DefaultEmbeddingFunction (all-MiniLM-L6-v2, 384-dim)
        so data interop with ChromaBackend is preserved.
        """
        from chromadb.utils import embedding_functions
        ef = embedding_functions.DefaultEmbeddingFunction()
        return ef

    def _writing(self):
        if self._lock is None:
            return nullcontext()
        return self._lock

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def _upsert(self, table: str, vec_table: str, doc_id: str, text: str, metadata: dict) -> None:
        import json
        clean_meta = _clean_metadata(metadata)
        embedding = self._embed_fn([text])[0]
        embedding = _l2_normalize([float(x) for x in embedding])
        emb_blob = _serialize_vec(embedding)
        wing = clean_meta.get("wing")
        room = clean_meta.get("room")
        hall = clean_meta.get("hall")

        with self._writing(), self._conn:
            self._conn.execute(
                f"INSERT OR REPLACE INTO {table}(id, text, wing, room, hall, metadata_json) "
                f"VALUES (?, ?, ?, ?, ?, ?)",
                (doc_id, text, wing, room, hall, json.dumps(clean_meta, ensure_ascii=False)),
            )
            self._conn.execute(f"DELETE FROM {vec_table} WHERE id = ?", (doc_id,))
            self._conn.execute(
                f"INSERT INTO {vec_table}(id, embedding) VALUES (?, ?)",
                (doc_id, emb_blob),
            )

    def index_drawer(self, drawer_id: str, text: str, metadata: dict) -> None:
        self._upsert("mined", "vec_mined", drawer_id, text, metadata)

    def delete_drawer(self, drawer_id: str) -> None:
        try:
            with self._writing(), self._conn:
                self._conn.execute("DELETE FROM mined WHERE id = ?", (drawer_id,))
                self._conn.execute("DELETE FROM vec_mined WHERE id = ?", (drawer_id,))
        except Exception:
            pass

    def index_raw(self, doc_id: str, text: str, metadata: dict) -> None:
        self._upsert("raw", "vec_raw", doc_id, text, metadata)

    def _bulk_upsert(
        self, table: str, vec_table: str, items: list[tuple[str, str, dict]],
    ) -> None:
        """Batch embed + single transaction upsert — ~10x faster than per-row.

        The embedding model is invoked once on the full text batch so GPU/CPU
        work is coalesced; all DB writes happen inside one BEGIN/COMMIT.
        """
        import json
        if not items:
            return

        items = _dedup_by_id(items)
        texts = [i[1] for i in items]
        # One embedding call for the whole batch
        embeddings = self._embed_fn(texts)

        rows = []
        vec_rows = []
        for (doc_id, text, metadata), emb in zip(items, embeddings):
            clean_meta = _clean_metadata(metadata)
            emb_list = _l2_normalize([float(x) for x in emb])
            emb_blob = _serialize_vec(emb_list)
            rows.append((
                doc_id,
                text,
                clean_meta.get("wing"),
                clean_meta.get("room"),
                clean_meta.get("hall"),
                json.dumps(clean_meta, ensure_ascii=False),
            ))
            vec_rows.append((doc_id, emb_blob))

        ids = [r[0] for r in rows]
        placeholders = ",".join("?" for _ in ids)
        with self._writing(), self._conn:
            self._conn.executemany(
                f"INSERT OR REPLACE INTO {table}"
                f"(id, text, wing, room, hall, metadata_json) "
                f"VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )
            # Delete existing vectors for these IDs (sqlite-vec lacks upsert)
            self._conn.execute(
                f"DELETE FROM {vec_table} WHERE id IN ({placeholders})", ids,
            )
            self._conn.executemany(
                f"INSERT INTO {vec_table}(id, embedding) VALUES (?, ?)",
                vec_rows,
            )

    def index_drawers_bulk(self, items: list[tuple[str, str, dict]]) -> None:
        # Chunk to bound memory / batch size for the embedding model
        batch_size = 64
        for start in range(0, len(items), batch_size):
            self._bulk_upsert("mined", "vec_mined", items[start:start + batch_size])

    def index_raw_bulk(self, items: list[tuple[str, str, dict]]) -> None:
        batch_size = 64
        for start in range(0, len(items), batch_size):
            self._bulk_upsert("raw", "vec_raw", items[start:start + batch_size])

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
        if collection == "mined":
            return self._search_one("mined", "vec_mined", query, wing, room, hall, exclude_wing, limit)
        if collection == "raw":
            return self._search_one("raw", "vec_raw", query, wing, room, hall, exclude_wing, limit)
        if collection == "both":
            fetch_n = min(limit * 3, 30)
            m = self._search_one("mined", "vec_mined", query, wing, room, hall, exclude_wing, fetch_n)
            r = self._search_one("raw", "vec_raw", query, wing, room, hall, exclude_wing, fetch_n)
            return _merge_rrf(m, r, limit)
        raise ValueError(f"collection must be 'mined', 'raw', or 'both'; got {collection!r}")

    def _search_one(
        self, table: str, vec_table: str,
        query: str, wing, room, hall, exclude_wing, limit: int,
    ) -> list[dict]:
        import json
        # Count shortcut
        cur = self._conn.execute(f"SELECT COUNT(*) FROM {table}")
        total = cur.fetchone()[0]
        if total == 0:
            return []

        embedding = self._embed_fn([query])[0]
        embedding = _l2_normalize([float(x) for x in embedding])
        q_blob = _serialize_vec(embedding)

        # Fetch more candidates than limit to allow metadata filtering without
        # sacrificing recall.
        k = min(max(limit * 4, limit), total)

        # sqlite-vec KNN query
        cur = self._conn.execute(
            f"SELECT v.id, v.distance FROM {vec_table} v "
            f"WHERE v.embedding MATCH ? AND k = ? ORDER BY v.distance",
            (q_blob, k),
        )
        hits = cur.fetchall()
        if not hits:
            return []

        # Filter by metadata in SQL
        id_list = [h[0] for h in hits]
        placeholders = ",".join("?" for _ in id_list)
        filter_sql, filter_params = self._build_filter_sql(wing, room, hall, exclude_wing)
        rows = self._conn.execute(
            f"SELECT id, text, metadata_json FROM {table} "
            f"WHERE id IN ({placeholders}) {filter_sql}",
            [*id_list, *filter_params],
        ).fetchall()

        # Preserve KNN order, apply limit
        row_by_id = {r[0]: r for r in rows}
        dist_by_id = {h[0]: h[1] for h in hits}
        output: list[dict] = []
        for doc_id, dist in hits:
            if doc_id not in row_by_id:
                continue
            _, text, meta_json = row_by_id[doc_id]
            meta = json.loads(meta_json) if meta_json else {}
            output.append({
                "drawer_id": doc_id,
                "text": text,
                "metadata": meta,
                "score": _l2_to_cosine_sim(float(dist)),
            })
            if len(output) >= limit:
                break
        return output

    @staticmethod
    def _build_filter_sql(wing, room, hall, exclude_wing) -> tuple[str, list]:
        clauses: list[str] = []
        params: list = []
        for field, value in [("wing", wing), ("room", room), ("hall", hall)]:
            if value is None:
                continue
            if isinstance(value, list):
                placeholders = ",".join("?" for _ in value)
                clauses.append(f"{field} IN ({placeholders})")
                params.extend(value)
            else:
                clauses.append(f"{field} = ?")
                params.append(value)
        if exclude_wing is not None:
            if isinstance(exclude_wing, str):
                exclude_wing = [exclude_wing]
            placeholders = ",".join("?" for _ in exclude_wing)
            clauses.append(f"wing NOT IN ({placeholders})")
            params.extend(exclude_wing)
        if not clauses:
            return "", []
        return "AND " + " AND ".join(clauses), params

    def get_stats(self) -> dict:
        total = self._conn.execute("SELECT COUNT(*) FROM mined").fetchone()[0]
        raw_total = self._conn.execute("SELECT COUNT(*) FROM raw").fetchone()[0]
        wings: dict[str, int] = {}
        for row in self._conn.execute(
            "SELECT wing, COUNT(*) FROM mined WHERE wing IS NOT NULL AND wing != '' GROUP BY wing"
        ):
            wings[row[0]] = row[1]
        return {
            "total_drawers": total,
            "wings": wings,
            "raw_documents": raw_total,
            "storage_bytes": _path_size_bytes(self._db_path),
        }

    def storage_path(self) -> Path | None:
        return self._db_path


# ---------------------------------------------------------------------------
# Factory + backward-compat alias
# ---------------------------------------------------------------------------


def _select_backend(config: MnemosConfig) -> str:
    name = getattr(config, "search_backend", None) or "chromadb"
    name = name.lower().strip()
    if name in ("sqlite-vec", "sqlite_vec", "sqlitevec"):
        return "sqlite-vec"
    if name in ("chromadb", "chroma"):
        return "chromadb"
    raise ValueError(f"Unknown search_backend: {name!r}")


def SearchEngine(config: MnemosConfig, in_memory: bool = False) -> SearchBackend:  # noqa: N802
    """Factory returning the backend configured on *config*.

    Kept as a capitalized callable so existing ``SearchEngine(cfg)`` call sites
    continue to work without modification.

    Runtime init failures (HNSW load errors, sqlite DatabaseError, permission
    issues) are wrapped in :class:`~mnemos.errors.BackendInitError` so callers
    can surface a single actionable message — typically a ``mnemos migrate
    --backend <other>`` suggestion. A bad *backend name* in config is not
    wrapped; it remains a ``ValueError`` from :func:`_select_backend`.
    """
    from mnemos.errors import BackendInitError

    backend = _select_backend(config)
    try:
        if backend == "sqlite-vec":
            return SqliteVecBackend(config, in_memory=in_memory)
        return ChromaBackend(config, in_memory=in_memory)
    except BackendInitError:
        raise
    except Exception as exc:
        raise BackendInitError(backend=backend, cause=exc) from exc
