"""SQLite persistence layer for the RIS v1 external_knowledge partition.

Provides ``KnowledgeStore`` -- a lightweight, stdlib-only SQLite backend
for source documents, derived claims, claim evidence, and claim relations.
Freshness decay is applied at query time (read-only; stored records are
never mutated).

Design notes:
- ``sqlite3`` stdlib only (no ORM).  Follows the pattern established in
  ``packages/polymarket/rag/lexical.py``.
- SHA-256-based deterministic IDs following the pattern in
  ``packages/polymarket/rag/metadata.py``.
- ``_llm_provider`` attribute defaults to None.  LLM provider integration
  point for claim extraction.  Cloud execution remains disabled by default
  pending authority sync between Roadmap v5.1 (Tier 1 free cloud APIs) and
  PLAN_OF_RECORD (no external LLM calls).  See
  ``docs/features/FEATURE-ris-v1-data-foundation.md``.

Usage::

    from packages.polymarket.rag.knowledge_store import KnowledgeStore

    # In-memory (tests)
    ks = KnowledgeStore(":memory:")

    # Disk-backed (production)
    ks = KnowledgeStore()  # kb/rag/knowledge/knowledge.sqlite3

    doc_id = ks.add_source_document(
        title="Jon-Becker Analysis",
        source_url="internal://jon_becker_2024",
        source_family="wallet_analysis",
        ...
    )
    claim_id = ks.add_claim(
        claim_text="gabagool22 exclusively trades 5m BTC/ETH pairs.",
        claim_type="empirical",
        confidence=0.92,
        ...
    )
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from packages.polymarket.rag.freshness import (
    compute_freshness_modifier,
    load_freshness_config,
)

DEFAULT_KNOWLEDGE_DB_PATH = Path("kb") / "rag" / "knowledge" / "knowledge.sqlite3"

# Contradiction penalty multiplier applied to freshness_modifier for
# claims that have at least one CONTRADICTS relation targeting them.
_CONTRADICTION_PENALTY = 0.5


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sha256_id(*parts: str) -> str:
    """Deterministic hex ID from one or more string parts (joined with NUL)."""
    payload = "\0".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _utcnow_iso() -> str:
    """Current UTC time as ISO-8601 string."""
    return datetime.now(tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# KnowledgeStore
# ---------------------------------------------------------------------------

class KnowledgeStore:
    """SQLite-backed persistence layer for external_knowledge claims.

    Parameters
    ----------
    db_path:
        Path to the SQLite database file.  Pass ``":memory:"`` for an
        in-memory database (tests / ephemeral use).  Parent directories
        are created if they do not exist for disk-backed paths.
    """

    def __init__(self, db_path: str | Path = DEFAULT_KNOWLEDGE_DB_PATH) -> None:
        self._db_path = str(db_path)

        # LLM provider integration point.  Defaults to None (cloud LLM calls
        # disabled pending authority sync between Roadmap v5.1 Tier 1 free
        # cloud APIs and PLAN_OF_RECORD no-external-LLM-call policy).
        # See docs/features/FEATURE-ris-v1-data-foundation.md.
        self._llm_provider: Any = None

        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._ensure_schema()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_schema(self) -> None:
        """Create all 4 tables if they do not exist."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS source_documents (
                id              TEXT PRIMARY KEY,
                title           TEXT,
                source_url      TEXT,
                source_family   TEXT,
                content_hash    TEXT,
                chunk_count     INTEGER,
                published_at    TEXT,
                ingested_at     TEXT,
                confidence_tier TEXT,
                metadata_json   TEXT
            );

            CREATE TABLE IF NOT EXISTS derived_claims (
                id                  TEXT PRIMARY KEY,
                claim_text          TEXT NOT NULL,
                claim_type          TEXT NOT NULL,
                confidence          REAL NOT NULL,
                trust_tier          TEXT NOT NULL,
                validation_status   TEXT NOT NULL DEFAULT 'UNTESTED',
                lifecycle           TEXT NOT NULL DEFAULT 'active',
                actor               TEXT NOT NULL,
                created_at          TEXT NOT NULL,
                updated_at          TEXT NOT NULL,
                source_document_id  TEXT REFERENCES source_documents(id),
                scope               TEXT,
                tags                TEXT,
                notes               TEXT,
                superseded_by       TEXT
            );

            CREATE TABLE IF NOT EXISTS claim_evidence (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                claim_id            TEXT NOT NULL REFERENCES derived_claims(id),
                source_document_id  TEXT NOT NULL REFERENCES source_documents(id),
                excerpt             TEXT,
                location            TEXT,
                created_at          TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS claim_relations (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                source_claim_id     TEXT NOT NULL REFERENCES derived_claims(id),
                target_claim_id     TEXT NOT NULL REFERENCES derived_claims(id),
                relation_type       TEXT NOT NULL
                    CHECK(relation_type IN ('SUPPORTS','CONTRADICTS','SUPERSEDES','EXTENDS')),
                created_at          TEXT NOT NULL
            );
        """)
        self._conn.commit()

    def _list_tables(self) -> set[str]:
        """Return the set of application table names in this database (for testing).

        Excludes internal SQLite tables (e.g. ``sqlite_sequence``).
        """
        rows = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        return {row["name"] for row in rows if not row["name"].startswith("sqlite_")}

    # ------------------------------------------------------------------
    # CRUD: source_documents
    # ------------------------------------------------------------------

    def add_source_document(
        self,
        *,
        title: Optional[str] = None,
        source_url: Optional[str] = None,
        source_family: Optional[str] = None,
        content_hash: Optional[str] = None,
        chunk_count: Optional[int] = None,
        published_at: Optional[str] = None,
        ingested_at: Optional[str] = None,
        confidence_tier: Optional[str] = None,
        metadata_json: Optional[str] = None,
    ) -> str:
        """Insert a source document.  Returns the deterministic document ID.

        The ID is derived from ``source_url`` and ``content_hash``.  Inserting
        the same document twice is idempotent (INSERT OR IGNORE).
        """
        url_part = source_url or ""
        hash_part = content_hash or ""
        doc_id = _sha256_id("source_document", url_part, hash_part)

        self._conn.execute(
            """INSERT OR IGNORE INTO source_documents
               (id, title, source_url, source_family, content_hash, chunk_count,
                published_at, ingested_at, confidence_tier, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                doc_id, title, source_url, source_family, content_hash,
                chunk_count, published_at, ingested_at, confidence_tier,
                metadata_json,
            ),
        )
        self._conn.commit()
        return doc_id

    def get_source_document(self, doc_id: str) -> Optional[dict]:
        """Return a source document dict by ID, or None if not found."""
        row = self._conn.execute(
            "SELECT * FROM source_documents WHERE id = ?", (doc_id,)
        ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # CRUD: derived_claims
    # ------------------------------------------------------------------

    def add_claim(
        self,
        *,
        claim_text: str,
        claim_type: str,
        confidence: float,
        trust_tier: str,
        validation_status: str = "UNTESTED",
        lifecycle: str = "active",
        actor: str,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        source_document_id: Optional[str] = None,
        scope: Optional[str] = None,
        tags: Optional[str] = None,
        notes: Optional[str] = None,
        superseded_by: Optional[str] = None,
    ) -> str:
        """Insert a derived claim.  Returns the deterministic claim ID."""
        now = _utcnow_iso()
        created_at = created_at or now
        updated_at = updated_at or now

        claim_id = _sha256_id("claim", claim_text, actor, created_at)

        self._conn.execute(
            """INSERT OR IGNORE INTO derived_claims
               (id, claim_text, claim_type, confidence, trust_tier,
                validation_status, lifecycle, actor, created_at, updated_at,
                source_document_id, scope, tags, notes, superseded_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                claim_id, claim_text, claim_type, confidence, trust_tier,
                validation_status, lifecycle, actor, created_at, updated_at,
                source_document_id, scope, tags, notes, superseded_by,
            ),
        )
        self._conn.commit()
        return claim_id

    def get_claim(self, claim_id: str) -> Optional[dict]:
        """Return a derived claim dict by ID, or None if not found."""
        row = self._conn.execute(
            "SELECT * FROM derived_claims WHERE id = ?", (claim_id,)
        ).fetchone()
        return dict(row) if row else None

    # Valid validation status values (RIS_07 Section 3)
    VALID_VALIDATION_STATUSES = ("UNTESTED", "CONSISTENT_WITH_RESULTS", "CONTRADICTED", "INCONCLUSIVE")

    def update_claim_validation_status(
        self,
        claim_id: str,
        validation_status: str,
        actor: str,
    ) -> None:
        """Update the validation_status of an existing derived claim.

        Parameters
        ----------
        claim_id:
            ID of the claim to update.
        validation_status:
            New status. Must be one of ``VALID_VALIDATION_STATUSES``.
        actor:
            Identity of the caller (e.g. ``"validation_feedback:hyp_abc"``)

        Raises
        ------
        ValueError
            If ``validation_status`` is not one of the valid values.
        ValueError
            If ``claim_id`` does not exist in the database.
        """
        if validation_status not in self.VALID_VALIDATION_STATUSES:
            raise ValueError(
                f"invalid validation_status '{validation_status}'. "
                f"Must be one of: {', '.join(self.VALID_VALIDATION_STATUSES)}"
            )

        if self.get_claim(claim_id) is None:
            raise ValueError(f"claim not found: {claim_id}")

        now = _utcnow_iso()
        self._conn.execute(
            """UPDATE derived_claims
               SET validation_status = ?, updated_at = ?
               WHERE id = ?""",
            (validation_status, now, claim_id),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # CRUD: claim_evidence
    # ------------------------------------------------------------------

    def add_evidence(
        self,
        *,
        claim_id: str,
        source_document_id: str,
        excerpt: Optional[str] = None,
        location: Optional[str] = None,
        created_at: Optional[str] = None,
    ) -> int:
        """Insert a claim-evidence link.  Returns the auto-increment evidence ID."""
        created_at = created_at or _utcnow_iso()
        cursor = self._conn.execute(
            """INSERT INTO claim_evidence
               (claim_id, source_document_id, excerpt, location, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (claim_id, source_document_id, excerpt, location, created_at),
        )
        self._conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # CRUD: claim_relations
    # ------------------------------------------------------------------

    def add_relation(
        self,
        source_claim_id: str,
        target_claim_id: str,
        relation_type: str,
        *,
        created_at: Optional[str] = None,
    ) -> int:
        """Insert a claim relation.  Returns the auto-increment relation ID.

        Parameters
        ----------
        relation_type:
            One of ``SUPPORTS``, ``CONTRADICTS``, ``SUPERSEDES``, ``EXTENDS``.

        Raises
        ------
        sqlite3.IntegrityError
            If ``relation_type`` is not one of the allowed values.
        """
        created_at = created_at or _utcnow_iso()
        cursor = self._conn.execute(
            """INSERT INTO claim_relations
               (source_claim_id, target_claim_id, relation_type, created_at)
               VALUES (?, ?, ?, ?)""",
            (source_claim_id, target_claim_id, relation_type, created_at),
        )
        self._conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Query: get_relations
    # ------------------------------------------------------------------

    def get_relations(
        self,
        claim_id: str,
        relation_type: Optional[str] = None,
    ) -> list[dict]:
        """Return all relations where ``claim_id`` is source or target.

        Parameters
        ----------
        claim_id:
            Claim to look up (source or target role).
        relation_type:
            Optional filter.  If provided, only returns relations of this type.
        """
        if relation_type is not None:
            rows = self._conn.execute(
                """SELECT * FROM claim_relations
                   WHERE (source_claim_id = ? OR target_claim_id = ?)
                     AND relation_type = ?""",
                (claim_id, claim_id, relation_type),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT * FROM claim_relations
                   WHERE source_claim_id = ? OR target_claim_id = ?""",
                (claim_id, claim_id),
            ).fetchall()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Query: get_provenance
    # ------------------------------------------------------------------

    def get_provenance(self, claim_id: str) -> list[dict]:
        """Return source documents linked to a claim via claim_evidence.

        Parameters
        ----------
        claim_id:
            Claim whose evidence chain to retrieve.

        Returns
        -------
        list[dict]
            Each entry is a source_document row dict.
        """
        rows = self._conn.execute(
            """SELECT sd.*
               FROM claim_evidence ce
               JOIN source_documents sd ON sd.id = ce.source_document_id
               WHERE ce.claim_id = ?""",
            (claim_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Query: query_claims
    # ------------------------------------------------------------------

    def query_claims(
        self,
        *,
        include_archived: bool = False,
        include_superseded: bool = False,
        apply_freshness: bool = True,
    ) -> list[dict]:
        """Return claims with optional freshness scoring and contradiction downranking.

        Default behavior:
        - Excludes ``lifecycle='archived'`` claims.
        - Excludes ``lifecycle='superseded'`` claims.
        - Applies freshness modifier from the linked source document.
        - Applies a ``0.5`` penalty multiplier to claims that have at least
          one CONTRADICTS relation targeting them.
        - Returns results sorted by ``effective_score`` descending.

        Parameters
        ----------
        include_archived:
            If ``True``, include archived claims.
        include_superseded:
            If ``True``, include superseded claims.
        apply_freshness:
            If ``True``, compute freshness modifier per claim and add
            ``freshness_modifier`` field to each result dict.

        Returns
        -------
        list[dict]
            Claim rows, each augmented with ``freshness_modifier`` (when
            ``apply_freshness=True``) and ``effective_score``.
        """
        conditions: list[str] = []
        params: list[Any] = []

        if not include_archived:
            conditions.append("dc.lifecycle != 'archived'")
        if not include_superseded:
            conditions.append("dc.lifecycle != 'superseded'")

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        sql = f"""
            SELECT dc.*, sd.source_family, sd.published_at AS sd_published_at
            FROM derived_claims dc
            LEFT JOIN source_documents sd ON sd.id = dc.source_document_id
            {where_clause}
        """
        rows = self._conn.execute(sql, params).fetchall()

        # Collect IDs of claims that are targeted by at least one CONTRADICTS relation
        contradicted_ids: set[str] = set()
        contra_rows = self._conn.execute(
            """SELECT DISTINCT target_claim_id
               FROM claim_relations
               WHERE relation_type = 'CONTRADICTS'"""
        ).fetchall()
        for cr in contra_rows:
            contradicted_ids.add(cr[0])

        freshness_config = load_freshness_config() if apply_freshness else None

        results: list[dict] = []
        for row in rows:
            claim = dict(row)
            # Remove the joined fields we don't want polluting the output
            source_family = claim.pop("source_family", None)
            sd_published_at_str = claim.pop("sd_published_at", None)

            # Compute freshness modifier
            if apply_freshness:
                sd_published_at: Optional[datetime] = None
                if sd_published_at_str:
                    try:
                        sd_published_at = datetime.fromisoformat(sd_published_at_str)
                    except ValueError:
                        sd_published_at = None

                fm = compute_freshness_modifier(
                    source_family=source_family or "unknown",
                    published_at=sd_published_at,
                    config=freshness_config,
                )
                claim["freshness_modifier"] = fm
            else:
                fm = 1.0  # no freshness applied, treat as 1.0 for scoring

            # Contradiction penalty
            contradiction_penalty = (
                _CONTRADICTION_PENALTY
                if claim["id"] in contradicted_ids
                else 1.0
            )

            # Effective score for sorting
            effective_score = fm * float(claim["confidence"]) * contradiction_penalty
            claim["effective_score"] = effective_score

            results.append(claim)

        # Sort by effective_score descending
        results.sort(key=lambda r: r["effective_score"], reverse=True)
        return results

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
