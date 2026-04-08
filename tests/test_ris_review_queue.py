"""Offline tests for the RIS Phase 2 review queue contract."""

from __future__ import annotations

import io
import json
import sqlite3
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from packages.polymarket.rag.knowledge_store import KnowledgeStore
from tools.cli.research_review import main as review_main


def _legacy_schema_script() -> str:
    return """
        CREATE TABLE source_documents (
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

        CREATE TABLE derived_claims (
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

        CREATE TABLE claim_evidence (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            claim_id            TEXT NOT NULL REFERENCES derived_claims(id),
            source_document_id  TEXT NOT NULL REFERENCES source_documents(id),
            excerpt             TEXT,
            location            TEXT,
            created_at          TEXT NOT NULL
        );

        CREATE TABLE claim_relations (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            source_claim_id     TEXT NOT NULL REFERENCES derived_claims(id),
            target_claim_id     TEXT NOT NULL REFERENCES derived_claims(id),
            relation_type       TEXT NOT NULL
                CHECK(relation_type IN ('SUPPORTS','CONTRADICTS','SUPERSEDES','EXTENDS')),
            created_at          TEXT NOT NULL
        );
    """


def _make_scores(
    *,
    composite_score: float = 2.9,
    total: int = 12,
    eval_model: str = "manual",
) -> dict:
    return {
        "relevance": 3,
        "novelty": 3,
        "actionability": 3,
        "credibility": 3,
        "total": total,
        "simple_sum_score": total,
        "composite_score": composite_score,
        "priority_tier": "priority_3",
        "eval_model": eval_model,
        "summary": "Useful enough for operator review.",
        "key_findings": ["Borderline usefulness"],
    }


def _make_snapshot(
    *,
    gate: str = "REVIEW",
    composite_score: float = 2.9,
    total: int = 12,
) -> dict:
    scores = _make_scores(composite_score=composite_score, total=total)
    return {
        "gate": gate,
        "provider_name": "manual",
        "eval_model": scores["eval_model"],
        "weighted_score": composite_score,
        "simple_sum_score": total,
        "scores": scores,
        "hard_stop": {"passed": True, "reason": None, "stop_type": None},
        "timestamp": "2026-04-08T10:00:00+00:00",
    }


def _enqueue_item(
    store: KnowledgeStore,
    *,
    source_url: str = "https://example.com/research-a",
    title: str = "Borderline Research Note",
    created_at: str = "2026-04-08T10:00:00+00:00",
) -> str:
    snapshot = _make_snapshot()
    return store.enqueue_pending_review(
        source_document_id=None,
        source_metadata_ref="fixture://research-a",
        source_url=source_url,
        source_type="manual",
        title=title,
        source_family="blog",
        provider_name="manual",
        eval_model="manual",
        gate="REVIEW",
        weighted_score=2.9,
        simple_sum_score=12,
        gate_snapshot=snapshot,
        scores=snapshot["scores"],
        created_at=created_at,
        queued_by="test-suite",
        queue_notes="Queue for review",
        queue_metadata={"fixture": True},
    )


class TestReviewQueueSchema:
    def test_schema_upgrade_adds_review_tables(self, tmp_path: Path) -> None:
        db_path = tmp_path / "legacy.sqlite3"
        conn = sqlite3.connect(db_path)
        conn.executescript(_legacy_schema_script())
        conn.execute(
            """INSERT INTO source_documents
               (id, title, source_url, source_family, content_hash, chunk_count,
                published_at, ingested_at, confidence_tier, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "legacy-doc",
                "Legacy Title",
                "https://example.com/legacy",
                "blog",
                "hash",
                1,
                None,
                "2026-04-08T09:00:00+00:00",
                None,
                "{}",
            ),
        )
        conn.commit()
        conn.close()

        store = KnowledgeStore(str(db_path))
        try:
            tables = store._list_tables()
            assert "pending_review" in tables
            assert "pending_review_history" in tables
            assert store.get_source_document("legacy-doc")["title"] == "Legacy Title"
        finally:
            store.close()


class TestReviewQueueStorage:
    def test_enqueue_pending_review_is_idempotent(self, tmp_path: Path) -> None:
        store = KnowledgeStore(str(tmp_path / "ks.sqlite3"))
        try:
            first_id = _enqueue_item(store)
            second_id = _enqueue_item(store)

            assert first_id == second_id

            items = store.list_pending_reviews()
            assert len(items) == 1
            assert items[0]["status"] == "pending"
            assert items[0]["weighted_score"] == pytest.approx(2.9)
            assert items[0]["simple_sum_score"] == pytest.approx(12)

            inspected = store.get_pending_review(first_id)
            assert inspected is not None
            assert inspected["gate_snapshot"]["gate"] == "REVIEW"
            assert inspected["history"][0]["action"] == "enqueue"
            assert len(inspected["history"]) == 1
        finally:
            store.close()

    def test_list_and_inspect_include_deferred_items(self, tmp_path: Path) -> None:
        store = KnowledgeStore(str(tmp_path / "ks.sqlite3"))
        try:
            first_id = _enqueue_item(
                store,
                source_url="https://example.com/research-a",
                title="Alpha",
                created_at="2026-04-08T10:00:00+00:00",
            )
            second_id = _enqueue_item(
                store,
                source_url="https://example.com/research-b",
                title="Beta",
                created_at="2026-04-08T10:05:00+00:00",
            )
            store.resolve_pending_review(
                second_id,
                action="defer",
                actor="analyst-1",
                notes="Need more context",
                action_metadata={"reason": "awaiting follow-up"},
            )

            items = store.list_pending_reviews()
            assert [item["id"] for item in items] == [first_id, second_id]
            assert [item["status"] for item in items] == ["pending", "deferred"]

            inspected = store.get_pending_review(second_id)
            assert inspected is not None
            assert inspected["status"] == "deferred"
            assert inspected["gate_snapshot"]["scores"]["composite_score"] == pytest.approx(2.9)
            assert [entry["action"] for entry in inspected["history"]] == ["enqueue", "defer"]
        finally:
            store.close()

    def test_accept_reject_and_defer_persist_audit_fields(self, tmp_path: Path) -> None:
        store = KnowledgeStore(str(tmp_path / "ks.sqlite3"))
        try:
            accept_id = _enqueue_item(
                store,
                source_url="https://example.com/research-a",
                created_at="2026-04-08T10:00:00+00:00",
            )
            reject_id = _enqueue_item(
                store,
                source_url="https://example.com/research-b",
                created_at="2026-04-08T10:05:00+00:00",
            )

            deferred = store.resolve_pending_review(
                accept_id,
                action="defer",
                actor="analyst-1",
                notes="Need one more source",
                action_metadata={"reason": "context_gap"},
            )
            assert deferred["status"] == "deferred"
            assert deferred["final_decision"] is None

            accepted = store.resolve_pending_review(
                accept_id,
                action="accept",
                actor="analyst-2",
                notes="Useful for research ingestion",
                action_metadata={"ticket": "RIS-42"},
            )
            assert accepted["status"] == "accepted"
            assert accepted["final_decision"] == "accept"
            assert accepted["final_decision_by"] == "analyst-2"
            assert accepted["final_decision_notes"] == "Useful for research ingestion"
            assert accepted["final_decision_metadata"] == {"ticket": "RIS-42"}
            assert [entry["action"] for entry in accepted["history"]] == [
                "enqueue",
                "defer",
                "accept",
            ]

            rejected = store.resolve_pending_review(
                reject_id,
                action="reject",
                actor="analyst-3",
                notes="Too weak for retention",
            )
            assert rejected["status"] == "rejected"
            assert rejected["final_decision"] == "reject"
            assert rejected["final_decision_by"] == "analyst-3"
            assert [entry["action"] for entry in rejected["history"]] == [
                "enqueue",
                "reject",
            ]
        finally:
            store.close()

    def test_terminal_accept_is_idempotent_and_blocks_conflicting_action(self, tmp_path: Path) -> None:
        store = KnowledgeStore(str(tmp_path / "ks.sqlite3"))
        try:
            item_id = _enqueue_item(store)
            first = store.resolve_pending_review(
                item_id,
                action="accept",
                actor="analyst-1",
                notes="Approved",
            )
            second = store.resolve_pending_review(
                item_id,
                action="accept",
                actor="analyst-2",
                notes="Repeated accept should not mutate",
            )

            assert second["status"] == "accepted"
            assert second["final_decision_by"] == "analyst-1"
            assert second["final_decision_notes"] == "Approved"
            assert len(second["history"]) == len(first["history"]) == 2

            with pytest.raises(ValueError):
                store.resolve_pending_review(
                    item_id,
                    action="reject",
                    actor="analyst-3",
                )
        finally:
            store.close()


class TestResearchReviewCLI:
    def test_cli_list_inspect_and_accept(self, tmp_path: Path) -> None:
        db_path = tmp_path / "ks.sqlite3"
        store = KnowledgeStore(str(db_path))
        try:
            item_id = _enqueue_item(store)
        finally:
            store.close()

        list_buf = io.StringIO()
        with redirect_stdout(list_buf):
            rc = review_main(["list", "--db", str(db_path), "--json"])
        assert rc == 0
        listed = json.loads(list_buf.getvalue())
        assert len(listed) == 1
        assert listed[0]["id"] == item_id

        inspect_buf = io.StringIO()
        with redirect_stdout(inspect_buf):
            rc = review_main(["inspect", item_id, "--db", str(db_path), "--json"])
        assert rc == 0
        inspected = json.loads(inspect_buf.getvalue())
        assert inspected["id"] == item_id
        assert inspected["history"][0]["action"] == "enqueue"

        accept_buf = io.StringIO()
        with redirect_stdout(accept_buf):
            rc = review_main(
                [
                    "accept",
                    item_id,
                    "--db",
                    str(db_path),
                    "--by",
                    "cli-operator",
                    "--notes",
                    "Looks useful",
                    "--metadata-json",
                    json.dumps({"ticket": "CLI-1"}),
                    "--json",
                ]
            )
        assert rc == 0
        accepted = json.loads(accept_buf.getvalue())
        assert accepted["status"] == "accepted"
        assert accepted["final_decision_by"] == "cli-operator"
        assert accepted["final_decision_metadata"] == {"ticket": "CLI-1"}
