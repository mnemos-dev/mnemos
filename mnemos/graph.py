"""SQLite temporal knowledge graph for Mnemos."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class KnowledgeGraph:
    """Temporal knowledge graph backed by SQLite.

    Stores entities and (subject, predicate, object) triples with optional
    valid_from / valid_to date strings for point-in-time queries.
    """

    def __init__(self, db_path: Path | str):
        self._path = Path(db_path)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _create_tables(self) -> None:
        cur = self._conn
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS entities (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL UNIQUE,
                type        TEXT    NOT NULL DEFAULT '',
                properties  TEXT    NOT NULL DEFAULT '{}',
                created_at  TEXT    NOT NULL,
                updated_at  TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS triples (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                subject     TEXT    NOT NULL,
                predicate   TEXT    NOT NULL,
                object      TEXT    NOT NULL,
                valid_from  TEXT,
                valid_to    TEXT,
                confidence  REAL    NOT NULL DEFAULT 1.0,
                source_file TEXT    NOT NULL DEFAULT '',
                created_at  TEXT    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_triples_subject
                ON triples(subject);

            CREATE INDEX IF NOT EXISTS idx_triples_object
                ON triples(object);

            CREATE INDEX IF NOT EXISTS idx_triples_source_file
                ON triples(source_file);
            """
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Entities
    # ------------------------------------------------------------------

    def add_entity(
        self,
        name: str,
        entity_type: str,
        properties: dict | None = None,
    ) -> None:
        """Insert or update an entity by name."""
        now = datetime.now(timezone.utc).isoformat()
        props = json.dumps(properties or {})
        self._conn.execute(
            """
            INSERT INTO entities (name, type, properties, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                type       = excluded.type,
                properties = excluded.properties,
                updated_at = excluded.updated_at
            """,
            (name, entity_type, props, now, now),
        )
        self._conn.commit()

    def get_entity(self, name: str) -> dict | None:
        """Return entity dict or None if not found."""
        row = self._conn.execute(
            "SELECT name, type, properties, created_at FROM entities WHERE name = ?",
            (name,),
        ).fetchone()
        if row is None:
            return None
        return {
            "name": row["name"],
            "type": row["type"],
            "properties": json.loads(row["properties"]),
            "created_at": row["created_at"],
        }

    def _ensure_entity(self, name: str) -> None:
        """Create entity with blank type if it doesn't already exist."""
        existing = self._conn.execute(
            "SELECT id FROM entities WHERE name = ?", (name,)
        ).fetchone()
        if existing is None:
            self.add_entity(name, "")

    # ------------------------------------------------------------------
    # Triples
    # ------------------------------------------------------------------

    def add_triple(
        self,
        subject: str,
        predicate: str,
        obj: str,
        valid_from: str | None = None,
        valid_to: str | None = None,
        confidence: float = 1.0,
        source_file: str = "",
    ) -> None:
        """Insert a triple, auto-creating subject and object entities."""
        self._ensure_entity(subject)
        self._ensure_entity(obj)
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """
            INSERT INTO triples
                (subject, predicate, object, valid_from, valid_to,
                 confidence, source_file, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (subject, predicate, obj, valid_from, valid_to,
             confidence, source_file, now),
        )
        self._conn.commit()

    def query_entity(self, entity: str, as_of: str | None = None) -> list[dict]:
        """Return triples where entity is the subject.

        If *as_of* is provided, return temporally valid triples at that date:
            valid_from <= as_of AND (valid_to IS NULL OR valid_to > as_of)

        Otherwise return open-ended triples (valid_to IS NULL).
        """
        if as_of is not None:
            rows = self._conn.execute(
                """
                SELECT predicate, object, valid_from, valid_to,
                       confidence, source_file
                FROM   triples
                WHERE  subject = ?
                  AND  (valid_from IS NULL OR valid_from <= ?)
                  AND  (valid_to   IS NULL OR valid_to   >  ?)
                """,
                (entity, as_of, as_of),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT predicate, object, valid_from, valid_to,
                       confidence, source_file
                FROM   triples
                WHERE  subject  = ?
                  AND  valid_to IS NULL
                """,
                (entity,),
            ).fetchall()

        return [
            {
                "predicate":   r["predicate"],
                "object":      r["object"],
                "valid_from":  r["valid_from"],
                "valid_to":    r["valid_to"],
                "confidence":  r["confidence"],
                "source_file": r["source_file"],
            }
            for r in rows
        ]

    def timeline(self, entity: str) -> list[dict]:
        """Return all triples for entity that have a valid_from, ordered ASC."""
        rows = self._conn.execute(
            """
            SELECT predicate, object, valid_from, valid_to,
                   confidence, source_file
            FROM   triples
            WHERE  subject    = ?
              AND  valid_from IS NOT NULL
            ORDER  BY valid_from ASC
            """,
            (entity,),
        ).fetchall()
        return [
            {
                "predicate":   r["predicate"],
                "object":      r["object"],
                "valid_from":  r["valid_from"],
                "valid_to":    r["valid_to"],
                "confidence":  r["confidence"],
                "source_file": r["source_file"],
            }
            for r in rows
        ]

    def delete_triples_by_source(self, source_file: str) -> int:
        """Delete all triples matching source_file. Return number deleted."""
        cur = self._conn.execute(
            "DELETE FROM triples WHERE source_file = ?", (source_file,)
        )
        self._conn.commit()
        return cur.rowcount

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the SQLite connection."""
        self._conn.close()
