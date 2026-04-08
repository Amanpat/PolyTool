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


def _json_dumps(value: Any) -> str:
    """Stable JSON encoding for persisted snapshots and deterministic IDs."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _json_loads(value: Optional[str]) -> Any:
    """Best-effort JSON decode for persisted TEXT columns."""
    if value is None:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


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

    REVIEW_STATUSES = ("pending", "deferred", "accepted", "rejected")
    REVIEW_ACTIONS = ("enqueue", "accept", "reject", "defer")
    FINAL_REVIEW_DECISIONS = ("accept", "reject")

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
        """Create or upgrade all KnowledgeStore tables if they do not exist."""
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

            CREATE TABLE IF NOT EXISTS pending_review (
                id                          TEXT PRIMARY KEY,
                source_document_id          TEXT REFERENCES source_documents(id),
                source_metadata_ref         TEXT,
                source_url                  TEXT,
                source_type                 TEXT,
                title                       TEXT,
                source_family               TEXT,
                provider_name               TEXT,
                eval_model                  TEXT,
                gate                        TEXT,
                weighted_score              REAL,
                simple_sum_score            REAL,
                gate_snapshot_json          TEXT NOT NULL,
                status                      TEXT NOT NULL
                    CHECK(status IN ('pending','deferred','accepted','rejected')),
                created_at                  TEXT NOT NULL,
                updated_at                  TEXT NOT NULL,
                final_decision              TEXT,
                final_decision_at           TEXT,
                final_decision_by           TEXT,
                final_decision_notes        TEXT,
                final_decision_metadata_json TEXT
            );

            CREATE TABLE IF NOT EXISTS pending_review_history (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                review_item_id      TEXT NOT NULL REFERENCES pending_review(id),
                action              TEXT NOT NULL
                    CHECK(action IN ('enqueue','accept','reject','defer')),
                previous_status     TEXT,
                new_status          TEXT NOT NULL,
                actor               TEXT,
                notes               TEXT,
                action_metadata_json TEXT,
                created_at          TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_pending_review_status_updated
                ON pending_review(status, updated_at DESC);

            CREATE INDEX IF NOT EXISTS idx_pending_review_history_item_created
                ON pending_review_history(review_item_id, created_at ASC);
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
    # Review queue helpers
    # ------------------------------------------------------------------

    def enqueue_pending_review(
        self,
        *,
        source_document_id: Optional[str] = None,
        source_metadata_ref: Optional[str] = None,
        source_url: Optional[str] = None,
        source_type: Optional[str] = None,
        title: Optional[str] = None,
        source_family: Optional[str] = None,
        provider_name: Optional[str] = None,
        eval_model: Optional[str] = None,
        gate: Optional[str] = None,
        weighted_score: Optional[float] = None,
        simple_sum_score: Optional[float] = None,
        gate_snapshot: Optional[Any] = None,
        scores: Optional[Any] = None,
        created_at: Optional[str] = None,
        queued_by: Optional[str] = None,
        queue_notes: Optional[str] = None,
        queue_metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Insert a review-queue item for a gray-zone document.

        The generated review item ID is deterministic from the source reference
        plus the gate snapshot so identical enqueue attempts are idempotent.
        """
        created_at = created_at or _utcnow_iso()

        if isinstance(scores, dict):
            if weighted_score is None:
                weighted_score = scores.get("composite_score")
            if simple_sum_score is None:
                simple_sum_score = scores.get("simple_sum_score", scores.get("total"))
            if eval_model is None:
                eval_model = scores.get("eval_model")

        snapshot_payload: dict[str, Any] = {}
        if gate_snapshot is not None:
            if isinstance(gate_snapshot, dict):
                snapshot_payload.update(gate_snapshot)
            else:
                snapshot_payload["gate_snapshot"] = gate_snapshot
        if scores is not None and "scores" not in snapshot_payload:
            snapshot_payload["scores"] = scores
        if gate is not None and "gate" not in snapshot_payload:
            snapshot_payload["gate"] = gate
        if provider_name is not None and "provider_name" not in snapshot_payload:
            snapshot_payload["provider_name"] = provider_name
        if eval_model is not None and "eval_model" not in snapshot_payload:
            snapshot_payload["eval_model"] = eval_model
        if weighted_score is not None and "weighted_score" not in snapshot_payload:
            snapshot_payload["weighted_score"] = weighted_score
        if simple_sum_score is not None and "simple_sum_score" not in snapshot_payload:
            snapshot_payload["simple_sum_score"] = simple_sum_score

        gate_snapshot_json = _json_dumps(snapshot_payload)
        identity_payload = _json_dumps(
            {
                "source_document_id": source_document_id or "",
                "source_metadata_ref": source_metadata_ref or "",
                "source_url": source_url or "",
                "source_type": source_type or "",
                "title": title or "",
                "source_family": source_family or "",
                "provider_name": provider_name or "",
                "eval_model": eval_model or "",
                "gate": gate or "",
                "weighted_score": weighted_score,
                "simple_sum_score": simple_sum_score,
                "gate_snapshot_json": gate_snapshot_json,
            }
        )
        review_item_id = _sha256_id("pending_review", identity_payload)

        before_changes = self._conn.total_changes
        with self._conn:
            self._conn.execute(
                """INSERT OR IGNORE INTO pending_review
                   (id, source_document_id, source_metadata_ref, source_url, source_type,
                    title, source_family, provider_name, eval_model, gate,
                    weighted_score, simple_sum_score, gate_snapshot_json,
                    status, created_at, updated_at,
                    final_decision, final_decision_at, final_decision_by,
                    final_decision_notes, final_decision_metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    review_item_id,
                    source_document_id,
                    source_metadata_ref,
                    source_url,
                    source_type,
                    title,
                    source_family,
                    provider_name,
                    eval_model,
                    gate,
                    weighted_score,
                    simple_sum_score,
                    gate_snapshot_json,
                    "pending",
                    created_at,
                    created_at,
                    None,
                    None,
                    None,
                    None,
                    None,
                ),
            )
            if self._conn.total_changes > before_changes:
                self._append_pending_review_history(
                    review_item_id=review_item_id,
                    action="enqueue",
                    previous_status=None,
                    new_status="pending",
                    actor=queued_by,
                    notes=queue_notes,
                    action_metadata=queue_metadata,
                    created_at=created_at,
                )
        return review_item_id

    def list_pending_reviews(
        self,
        *,
        statuses: Optional[list[str] | tuple[str, ...]] = None,
        limit: Optional[int] = None,
    ) -> list[dict]:
        """Return queued review items, defaulting to unresolved entries."""
        normalized_statuses = tuple(statuses or ("pending", "deferred"))
        if not normalized_statuses:
            return []
        for status in normalized_statuses:
            if status not in self.REVIEW_STATUSES:
                raise ValueError(
                    f"invalid review status '{status}'. "
                    f"Must be one of: {', '.join(self.REVIEW_STATUSES)}"
                )

        placeholders = ", ".join("?" for _ in normalized_statuses)
        sql = f"""
            SELECT *
            FROM pending_review
            WHERE status IN ({placeholders})
            ORDER BY created_at ASC, id ASC
        """
        params: list[Any] = list(normalized_statuses)
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)

        rows = self._conn.execute(sql, params).fetchall()
        return [
            self._deserialize_pending_review_row(row, include_snapshot=False)
            for row in rows
        ]

    def get_pending_review(
        self,
        review_item_id: str,
        *,
        include_history: bool = True,
    ) -> Optional[dict]:
        """Return one review item, optionally including its audit history."""
        row = self._conn.execute(
            "SELECT * FROM pending_review WHERE id = ?",
            (review_item_id,),
        ).fetchone()
        if row is None:
            return None
        item = self._deserialize_pending_review_row(row, include_snapshot=True)
        if include_history:
            item["history"] = self.get_pending_review_history(review_item_id)
        return item

    def get_pending_review_history(self, review_item_id: str) -> list[dict]:
        """Return the append-only audit trail for a review item."""
        rows = self._conn.execute(
            """SELECT *
               FROM pending_review_history
               WHERE review_item_id = ?
               ORDER BY created_at ASC, id ASC""",
            (review_item_id,),
        ).fetchall()
        history: list[dict] = []
        for row in rows:
            entry = dict(row)
            entry["action_metadata"] = _json_loads(entry.pop("action_metadata_json", None))
            history.append(entry)
        return history

    def resolve_pending_review(
        self,
        review_item_id: str,
        *,
        action: str,
        actor: Optional[str] = None,
        notes: Optional[str] = None,
        action_metadata: Optional[dict[str, Any]] = None,
    ) -> dict:
        """Resolve or defer a queued review item with audit-friendly history."""
        if action not in ("accept", "reject", "defer"):
            raise ValueError("action must be one of: accept, reject, defer")

        current = self.get_pending_review(review_item_id, include_history=False)
        if current is None:
            raise ValueError(f"pending review item not found: {review_item_id}")

        current_status = current["status"]
        if current_status in ("accepted", "rejected"):
            if (
                action in self.FINAL_REVIEW_DECISIONS
                and current.get("final_decision") == action
            ):
                existing = self.get_pending_review(review_item_id, include_history=True)
                assert existing is not None
                return existing
            raise ValueError(
                f"pending review item already resolved as {current_status}"
            )

        if current_status == "deferred" and action == "defer":
            existing = self.get_pending_review(review_item_id, include_history=True)
            assert existing is not None
            return existing

        now = _utcnow_iso()
        new_status = {
            "accept": "accepted",
            "reject": "rejected",
            "defer": "deferred",
        }[action]

        final_decision = current.get("final_decision")
        final_decision_at = current.get("final_decision_at")
        final_decision_by = current.get("final_decision_by")
        final_decision_notes = current.get("final_decision_notes")
        final_decision_metadata_json = (
            _json_dumps(action_metadata) if action_metadata is not None else None
        )

        if action in self.FINAL_REVIEW_DECISIONS:
            final_decision = action
            final_decision_at = now
            final_decision_by = actor
            final_decision_notes = notes
        else:
            existing_metadata = current.get("final_decision_metadata")
            final_decision_metadata_json = (
                _json_dumps(existing_metadata)
                if existing_metadata is not None
                else None
            )

        with self._conn:
            self._conn.execute(
                """UPDATE pending_review
                   SET status = ?,
                       updated_at = ?,
                       final_decision = ?,
                       final_decision_at = ?,
                       final_decision_by = ?,
                       final_decision_notes = ?,
                       final_decision_metadata_json = ?
                   WHERE id = ?""",
                (
                    new_status,
                    now,
                    final_decision,
                    final_decision_at,
                    final_decision_by,
                    final_decision_notes,
                    final_decision_metadata_json,
                    review_item_id,
                ),
            )
            self._append_pending_review_history(
                review_item_id=review_item_id,
                action=action,
                previous_status=current_status,
                new_status=new_status,
                actor=actor,
                notes=notes,
                action_metadata=action_metadata,
                created_at=now,
            )

        updated = self.get_pending_review(review_item_id, include_history=True)
        assert updated is not None
        return updated

    def _append_pending_review_history(
        self,
        *,
        review_item_id: str,
        action: str,
        previous_status: Optional[str],
        new_status: str,
        actor: Optional[str],
        notes: Optional[str],
        action_metadata: Optional[dict[str, Any]],
        created_at: str,
    ) -> None:
        """Append one audit event for a review-queue mutation."""
        if action not in self.REVIEW_ACTIONS:
            raise ValueError(
                f"invalid review action '{action}'. "
                f"Must be one of: {', '.join(self.REVIEW_ACTIONS)}"
            )
        self._conn.execute(
            """INSERT INTO pending_review_history
               (review_item_id, action, previous_status, new_status,
                actor, notes, action_metadata_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                review_item_id,
                action,
                previous_status,
                new_status,
                actor,
                notes,
                _json_dumps(action_metadata) if action_metadata is not None else None,
                created_at,
            ),
        )

    def _deserialize_pending_review_row(
        self,
        row: sqlite3.Row,
        *,
        include_snapshot: bool,
    ) -> dict:
        """Convert a pending_review row into a JSON-friendly dict."""
        item = dict(row)
        item["final_decision_metadata"] = _json_loads(
            item.pop("final_decision_metadata_json", None)
        )
        if include_snapshot:
            item["gate_snapshot"] = _json_loads(item.pop("gate_snapshot_json", None))
        else:
            item.pop("gate_snapshot_json", None)
        return item

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
