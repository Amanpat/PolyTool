"""Offline deterministic tests for the RIS v1 knowledge store persistence layer.

All tests use in-memory SQLite (:memory:) -- no network calls, no disk I/O.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------

from packages.polymarket.rag.knowledge_store import KnowledgeStore
from packages.polymarket.rag.freshness import (
    load_freshness_config,
    compute_freshness_modifier,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def ks() -> KnowledgeStore:
    """In-memory KnowledgeStore for all tests."""
    return KnowledgeStore(":memory:")


@pytest.fixture()
def freshness_config(tmp_path: Path) -> dict:
    """Load freshness config from a temp copy of freshness_decay.json."""
    src = Path(__file__).parent.parent / "config" / "freshness_decay.json"
    return json.loads(src.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Helper: build minimal source-doc / claim dicts
# ---------------------------------------------------------------------------

def _source_doc(**overrides) -> dict:
    base = {
        "title": "Test Source",
        "source_url": "https://example.com/test",
        "source_family": "blog",
        "content_hash": "abc123",
        "chunk_count": 1,
        "published_at": "2025-01-01T00:00:00+00:00",
        "ingested_at": "2025-06-01T00:00:00+00:00",
        "confidence_tier": "PRACTITIONER",
        "metadata_json": "{}",
    }
    base.update(overrides)
    return base


def _claim(**overrides) -> dict:
    base = {
        "claim_text": "BTC/ETH 5m spreads are consistently profitable.",
        "claim_type": "empirical",
        "confidence": 0.7,
        "trust_tier": "PRACTITIONER",
        "validation_status": "UNTESTED",
        "lifecycle": "active",
        "actor": "test_agent",
        "created_at": "2025-06-01T00:00:00+00:00",
        "updated_at": "2025-06-01T00:00:00+00:00",
    }
    base.update(overrides)
    return base


# ===========================================================================
# Schema tests
# ===========================================================================

class TestSchemaCreation:
    def test_all_four_tables_exist(self, ks: KnowledgeStore) -> None:
        """KnowledgeStore creates the core claims tables plus review-queue tables."""
        tables = ks._list_tables()
        assert "source_documents" in tables
        assert "derived_claims" in tables
        assert "claim_evidence" in tables
        assert "claim_relations" in tables
        assert "pending_review" in tables
        assert "pending_review_history" in tables

    def test_in_memory_accepts_colon_memory_string(self) -> None:
        """KnowledgeStore accepts ':memory:' as db_path."""
        store = KnowledgeStore(":memory:")
        tables = store._list_tables()
        # sqlite_sequence is an internal SQLite table created alongside
        # AUTOINCREMENT columns -- it is not one of our 6 app tables.
        app_tables = {t for t in tables if not t.startswith("sqlite_")}
        assert len(app_tables) == 6


# ===========================================================================
# CRUD: source_documents
# ===========================================================================

class TestSourceDocuments:
    def test_insert_and_retrieve_source_doc(self, ks: KnowledgeStore) -> None:
        """Insert a source doc, retrieve by ID."""
        doc = _source_doc()
        doc_id = ks.add_source_document(**doc)
        assert doc_id is not None

        retrieved = ks.get_source_document(doc_id)
        assert retrieved is not None
        assert retrieved["title"] == "Test Source"
        assert retrieved["source_family"] == "blog"

    def test_retrieve_nonexistent_source_doc_returns_none(self, ks: KnowledgeStore) -> None:
        """get_source_document returns None for unknown ID."""
        result = ks.get_source_document("nonexistent-id")
        assert result is None

    def test_source_doc_id_is_deterministic(self, ks: KnowledgeStore) -> None:
        """Same content_hash + source_url should produce same doc ID."""
        doc = _source_doc()
        id1 = ks.add_source_document(**doc)
        # Second insert with same data should return same ID (INSERT OR IGNORE)
        id2 = ks.add_source_document(**doc)
        assert id1 == id2


# ===========================================================================
# CRUD: derived_claims
# ===========================================================================

class TestDerivedClaims:
    def test_insert_and_retrieve_claim(self, ks: KnowledgeStore) -> None:
        """Insert a claim with all required fields and retrieve by ID."""
        claim = _claim()
        claim_id = ks.add_claim(**claim)
        assert claim_id is not None

        retrieved = ks.get_claim(claim_id)
        assert retrieved is not None
        assert retrieved["claim_text"] == claim["claim_text"]
        assert retrieved["claim_type"] == "empirical"
        assert retrieved["confidence"] == pytest.approx(0.7)
        assert retrieved["trust_tier"] == "PRACTITIONER"
        assert retrieved["validation_status"] == "UNTESTED"
        assert retrieved["lifecycle"] == "active"
        assert retrieved["actor"] == "test_agent"

    def test_retrieve_nonexistent_claim_returns_none(self, ks: KnowledgeStore) -> None:
        """get_claim returns None for unknown ID."""
        result = ks.get_claim("nonexistent-claim-id")
        assert result is None

    def test_claim_optional_fields(self, ks: KnowledgeStore) -> None:
        """Claims accept optional fields: scope, tags, notes, superseded_by."""
        claim = _claim(scope="crypto", tags="btc,eth", notes="Test note")
        claim_id = ks.add_claim(**claim)
        retrieved = ks.get_claim(claim_id)
        assert retrieved["scope"] == "crypto"
        assert retrieved["tags"] == "btc,eth"
        assert retrieved["notes"] == "Test note"


# ===========================================================================
# CRUD: claim_evidence
# ===========================================================================

class TestClaimEvidence:
    def test_insert_evidence_and_join_query(self, ks: KnowledgeStore) -> None:
        """Insert evidence linking a claim to a source doc, verify join works."""
        doc_id = ks.add_source_document(**_source_doc())
        claim_id = ks.add_claim(**_claim())

        ev_id = ks.add_evidence(
            claim_id=claim_id,
            source_document_id=doc_id,
            excerpt="Spreads were 2bps on average.",
            location="Section 3.2",
            created_at="2025-06-01T00:00:00+00:00",
        )
        assert ev_id is not None

        provenance = ks.get_provenance(claim_id)
        assert len(provenance) == 1
        assert provenance[0]["id"] == doc_id


# ===========================================================================
# CRUD: claim_relations
# ===========================================================================

class TestClaimRelations:
    def test_insert_supports_relation(self, ks: KnowledgeStore) -> None:
        """Insert a SUPPORTS relation between two claims."""
        c1 = ks.add_claim(**_claim(claim_text="Claim A"))
        c2 = ks.add_claim(**_claim(claim_text="Claim B"))
        rel_id = ks.add_relation(
            source_claim_id=c1,
            target_claim_id=c2,
            relation_type="SUPPORTS",
            created_at="2025-06-01T00:00:00+00:00",
        )
        assert rel_id is not None

    def test_insert_contradicts_relation(self, ks: KnowledgeStore) -> None:
        """Insert a CONTRADICTS relation."""
        c1 = ks.add_claim(**_claim(claim_text="Claim A"))
        c2 = ks.add_claim(**_claim(claim_text="Claim B (contradicting)"))
        rel_id = ks.add_relation(
            source_claim_id=c1,
            target_claim_id=c2,
            relation_type="CONTRADICTS",
            created_at="2025-06-01T00:00:00+00:00",
        )
        assert rel_id is not None

    def test_insert_supersedes_relation(self, ks: KnowledgeStore) -> None:
        """Insert a SUPERSEDES relation."""
        c1 = ks.add_claim(**_claim(claim_text="New claim"))
        c2 = ks.add_claim(**_claim(claim_text="Old claim"))
        rel_id = ks.add_relation(
            source_claim_id=c1,
            target_claim_id=c2,
            relation_type="SUPERSEDES",
            created_at="2025-06-01T00:00:00+00:00",
        )
        assert rel_id is not None

    def test_insert_extends_relation(self, ks: KnowledgeStore) -> None:
        """Insert an EXTENDS relation."""
        c1 = ks.add_claim(**_claim(claim_text="Extended claim"))
        c2 = ks.add_claim(**_claim(claim_text="Base claim"))
        rel_id = ks.add_relation(
            source_claim_id=c1,
            target_claim_id=c2,
            relation_type="EXTENDS",
            created_at="2025-06-01T00:00:00+00:00",
        )
        assert rel_id is not None

    def test_invalid_relation_type_raises(self, ks: KnowledgeStore) -> None:
        """Invalid relation type should raise an error."""
        c1 = ks.add_claim(**_claim(claim_text="Claim A"))
        c2 = ks.add_claim(**_claim(claim_text="Claim B"))
        with pytest.raises(Exception):
            ks.add_relation(
                source_claim_id=c1,
                target_claim_id=c2,
                relation_type="INVALID",
                created_at="2025-06-01T00:00:00+00:00",
            )

    def test_get_relations_by_claim(self, ks: KnowledgeStore) -> None:
        """get_relations returns all relations where claim is source or target."""
        c1 = ks.add_claim(**_claim(claim_text="Claim A"))
        c2 = ks.add_claim(**_claim(claim_text="Claim B"))
        c3 = ks.add_claim(**_claim(claim_text="Claim C"))
        ks.add_relation(c1, c2, "SUPPORTS", created_at="2025-06-01T00:00:00+00:00")
        ks.add_relation(c3, c1, "EXTENDS", created_at="2025-06-01T00:00:00+00:00")

        relations = ks.get_relations(c1)
        # c1 is source of one, target of another -> 2 relations
        assert len(relations) == 2

    def test_get_relations_filtered_by_type(self, ks: KnowledgeStore) -> None:
        """get_relations filtered by relation_type returns only matching relations."""
        c1 = ks.add_claim(**_claim(claim_text="Claim A"))
        c2 = ks.add_claim(**_claim(claim_text="Claim B"))
        c3 = ks.add_claim(**_claim(claim_text="Claim C"))
        ks.add_relation(c1, c2, "SUPPORTS", created_at="2025-06-01T00:00:00+00:00")
        ks.add_relation(c1, c3, "CONTRADICTS", created_at="2025-06-01T00:00:00+00:00")

        supports = ks.get_relations(c1, relation_type="SUPPORTS")
        assert len(supports) == 1
        assert supports[0]["relation_type"] == "SUPPORTS"


# ===========================================================================
# query_claims: lifecycle filtering
# ===========================================================================

class TestQueryClaimsLifecycle:
    def test_query_excludes_archived_by_default(self, ks: KnowledgeStore) -> None:
        """query_claims excludes lifecycle='archived' by default."""
        ks.add_claim(**_claim(claim_text="Active claim", lifecycle="active"))
        ks.add_claim(**_claim(claim_text="Archived claim", lifecycle="archived"))

        results = ks.query_claims()
        texts = [r["claim_text"] for r in results]
        assert "Active claim" in texts
        assert "Archived claim" not in texts

    def test_query_includes_archived_when_requested(self, ks: KnowledgeStore) -> None:
        """query_claims includes archived when include_archived=True."""
        ks.add_claim(**_claim(claim_text="Active claim", lifecycle="active"))
        ks.add_claim(**_claim(claim_text="Archived claim", lifecycle="archived"))

        results = ks.query_claims(include_archived=True)
        texts = [r["claim_text"] for r in results]
        assert "Active claim" in texts
        assert "Archived claim" in texts

    def test_query_excludes_superseded_by_default(self, ks: KnowledgeStore) -> None:
        """query_claims excludes lifecycle='superseded' by default."""
        ks.add_claim(**_claim(claim_text="Current claim", lifecycle="active"))
        ks.add_claim(**_claim(claim_text="Superseded claim", lifecycle="superseded"))

        results = ks.query_claims()
        texts = [r["claim_text"] for r in results]
        assert "Current claim" in texts
        assert "Superseded claim" not in texts

    def test_query_includes_superseded_when_requested(self, ks: KnowledgeStore) -> None:
        """query_claims includes superseded when include_superseded=True."""
        ks.add_claim(**_claim(claim_text="Current claim", lifecycle="active"))
        ks.add_claim(**_claim(claim_text="Superseded claim", lifecycle="superseded"))

        results = ks.query_claims(include_superseded=True)
        texts = [r["claim_text"] for r in results]
        assert "Superseded claim" in texts


# ===========================================================================
# query_claims: contradiction downranking
# ===========================================================================

class TestQueryClaimsContradiction:
    def test_contradicted_claim_sorted_last(self, ks: KnowledgeStore) -> None:
        """Contradicted claims (via CONTRADICTS relation) sort lower by default."""
        # Create a well-supported claim
        good_id = ks.add_claim(**_claim(claim_text="Good claim", confidence=0.8))
        # Create a contradicted claim with same confidence
        bad_id = ks.add_claim(**_claim(claim_text="Contradicted claim", confidence=0.8))
        # Add a claim that contradicts bad_id
        contra_id = ks.add_claim(**_claim(claim_text="Contradicting claim", confidence=0.9))
        ks.add_relation(
            source_claim_id=contra_id,
            target_claim_id=bad_id,
            relation_type="CONTRADICTS",
            created_at="2025-06-01T00:00:00+00:00",
        )

        results = ks.query_claims()
        texts = [r["claim_text"] for r in results]
        # The contradicted claim should appear after the good claim
        good_idx = texts.index("Good claim")
        bad_idx = texts.index("Contradicted claim")
        assert good_idx < bad_idx, (
            f"Expected 'Good claim' (idx={good_idx}) before 'Contradicted claim' "
            f"(idx={bad_idx})"
        )


# ===========================================================================
# Freshness config
# ===========================================================================

class TestFreshnessConfig:
    def test_freshness_config_loads(self, freshness_config: dict) -> None:
        """freshness_decay.json loads and has expected structure."""
        assert "source_families" in freshness_config
        assert "decay_floor" in freshness_config
        assert freshness_config["decay_floor"] == pytest.approx(0.3)

    def test_freshness_config_has_ten_source_families(self, freshness_config: dict) -> None:
        """freshness_decay.json has at least 10 source families."""
        families = freshness_config["source_families"]
        assert len(families) >= 10

    def test_timeless_sources_have_null_half_life(self, freshness_config: dict) -> None:
        """Academic foundational and book foundational sources have null half-life."""
        families = freshness_config["source_families"]
        assert families["academic_foundational"] is None
        assert families["book_foundational"] is None

    def test_news_has_short_half_life(self, freshness_config: dict) -> None:
        """News has a short half-life (<=3 months)."""
        families = freshness_config["source_families"]
        assert families["news"] is not None
        assert families["news"] <= 3


# ===========================================================================
# compute_freshness_modifier
# ===========================================================================

class TestComputeFreshnessModifier:
    def test_timeless_source_returns_1_0(self) -> None:
        """Timeless source (null half-life) always returns 1.0 regardless of age."""
        old_date = datetime(2000, 1, 1, tzinfo=timezone.utc)
        result = compute_freshness_modifier(
            source_family="academic_foundational",
            published_at=old_date,
        )
        assert result == pytest.approx(1.0)

    def test_timeless_source_with_book(self) -> None:
        """book_foundational also returns 1.0."""
        old_date = datetime(1950, 1, 1, tzinfo=timezone.utc)
        result = compute_freshness_modifier(
            source_family="book_foundational",
            published_at=old_date,
        )
        assert result == pytest.approx(1.0)

    def test_none_published_at_returns_1_0(self) -> None:
        """None published_at returns 1.0 (unknown age = no penalty)."""
        result = compute_freshness_modifier(
            source_family="news",
            published_at=None,
        )
        assert result == pytest.approx(1.0)

    def test_recent_news_high_modifier(self) -> None:
        """News published recently (within 2 weeks) should have modifier > 0.8.

        With half_life=3 months, at age=14 days: 2^(-14/(3*30.44)) ~= 0.89 > 0.8.
        """
        # Use a date 2 weeks ago (clearly within 1 half-life quarter)
        recent = datetime.now(tz=timezone.utc) - timedelta(days=14)
        result = compute_freshness_modifier(
            source_family="news",
            published_at=recent,
        )
        assert result > 0.8

    def test_six_month_old_news_between_floor_and_1(self) -> None:
        """News with half-life=3mo at age=6mo should be between floor and 0.5."""
        # At age = 2 * half_life, modifier = 2^(-2) = 0.25, but floored at 0.3
        # At age = half_life, modifier = 2^(-1) = 0.5
        # At age = 6mo with half_life=3mo: 2^(-6/3) = 2^(-2) = 0.25 -> floor=0.3
        six_months_ago = datetime.now(tz=timezone.utc) - timedelta(days=182)
        result = compute_freshness_modifier(
            source_family="news",
            published_at=six_months_ago,
        )
        # Should be floored at 0.3 or close to it
        assert 0.25 <= result <= 0.5, f"Expected between 0.25 and 0.5, got {result}"

    def test_very_old_blog_returns_floor(self) -> None:
        """Very old blog post (years old) should return floor=0.3."""
        very_old = datetime(2010, 1, 1, tzinfo=timezone.utc)
        result = compute_freshness_modifier(
            source_family="blog",
            published_at=very_old,
        )
        assert result == pytest.approx(0.3, abs=0.01)

    def test_modifier_between_floor_and_1(self) -> None:
        """All modifiers are between floor and 1.0."""
        now = datetime.now(tz=timezone.utc)
        for family in ["news", "blog", "reddit", "twitter", "github", "preprint"]:
            for age_days in [0, 30, 90, 180, 365, 730]:
                pub = now - timedelta(days=age_days)
                result = compute_freshness_modifier(
                    source_family=family, published_at=pub
                )
                assert 0.3 <= result <= 1.0, (
                    f"family={family} age={age_days}d result={result}"
                )

    def test_freshness_does_not_mutate_records(self) -> None:
        """compute_freshness_modifier is a pure function -- no side effects."""
        record = {
            "claim_text": "Test claim",
            "published_at": "2020-01-01T00:00:00+00:00",
        }
        original_record = dict(record)
        dt = datetime(2020, 1, 1, tzinfo=timezone.utc)
        compute_freshness_modifier("blog", dt)
        # Record unchanged
        assert record == original_record


# ===========================================================================
# Freshness applied in query_claims
# ===========================================================================

class TestQueryClaimsFreshness:
    def test_query_claims_includes_freshness_modifier(self, ks: KnowledgeStore) -> None:
        """query_claims results include freshness_modifier field when apply_freshness=True."""
        doc_id = ks.add_source_document(
            **_source_doc(source_family="news", published_at="2025-01-01T00:00:00+00:00")
        )
        ks.add_claim(**_claim(source_document_id=doc_id))

        results = ks.query_claims(apply_freshness=True)
        assert len(results) == 1
        assert "freshness_modifier" in results[0]
        assert 0.3 <= results[0]["freshness_modifier"] <= 1.0

    def test_query_claims_without_freshness_no_modifier_field(self, ks: KnowledgeStore) -> None:
        """query_claims with apply_freshness=False omits freshness_modifier."""
        ks.add_claim(**_claim())
        results = ks.query_claims(apply_freshness=False)
        assert len(results) == 1
        assert "freshness_modifier" not in results[0]


# ===========================================================================
# get_provenance
# ===========================================================================

class TestGetProvenance:
    def test_provenance_returns_source_docs_for_claim(self, ks: KnowledgeStore) -> None:
        """get_provenance returns all source docs linked to a claim via evidence."""
        doc1_id = ks.add_source_document(**_source_doc(
            title="Source Doc 1",
            source_url="https://example.com/doc1",
            content_hash="hash001",
        ))
        doc2_id = ks.add_source_document(**_source_doc(
            title="Source Doc 2",
            source_url="https://example.com/doc2",
            content_hash="hash002",
        ))
        claim_id = ks.add_claim(**_claim())

        ks.add_evidence(
            claim_id=claim_id,
            source_document_id=doc1_id,
            excerpt="First piece of evidence",
            created_at="2025-06-01T00:00:00+00:00",
        )
        ks.add_evidence(
            claim_id=claim_id,
            source_document_id=doc2_id,
            excerpt="Second piece of evidence",
            created_at="2025-06-01T00:00:00+00:00",
        )

        provenance = ks.get_provenance(claim_id)
        assert len(provenance) == 2
        titles = {doc["title"] for doc in provenance}
        assert "Source Doc 1" in titles
        assert "Source Doc 2" in titles

    def test_provenance_empty_for_claim_without_evidence(self, ks: KnowledgeStore) -> None:
        """get_provenance returns empty list when claim has no evidence."""
        claim_id = ks.add_claim(**_claim())
        provenance = ks.get_provenance(claim_id)
        assert provenance == []


# ===========================================================================
# Smoke test: end-to-end contradiction ordering
# ===========================================================================

class TestSmokeEndToEnd:
    def test_contradicted_claim_sorts_last_in_full_pipeline(self, ks: KnowledgeStore) -> None:
        """Full pipeline: source doc, two claims, CONTRADICTS relation, check order."""
        doc_id = ks.add_source_document(**_source_doc())

        # "Good" claim -- no contradictions
        good_id = ks.add_claim(**_claim(
            claim_text="Claim supported",
            confidence=0.8,
            source_document_id=doc_id,
        ))
        ks.add_evidence(
            claim_id=good_id,
            source_document_id=doc_id,
            excerpt="Evidence for good claim",
            created_at="2025-06-01T00:00:00+00:00",
        )

        # "Bad" claim -- will be contradicted
        bad_id = ks.add_claim(**_claim(
            claim_text="Claim contradicted",
            confidence=0.8,
            source_document_id=doc_id,
        ))

        # Contradicting claim
        contra_id = ks.add_claim(**_claim(
            claim_text="Contradicting evidence",
            confidence=0.85,
        ))
        ks.add_relation(
            source_claim_id=contra_id,
            target_claim_id=bad_id,
            relation_type="CONTRADICTS",
            created_at="2025-06-01T00:00:00+00:00",
        )

        # Default query should return results with contradicted claim last among
        # the active claims
        results = ks.query_claims()
        # Filter to only the "good" and "bad" claims to check relative ordering
        relevant = [r for r in results if r["claim_text"] in (
            "Claim supported", "Claim contradicted"
        )]
        assert len(relevant) == 2
        assert relevant[0]["claim_text"] == "Claim supported", (
            f"Expected 'Claim supported' first, got order: "
            f"{[r['claim_text'] for r in relevant]}"
        )
        assert relevant[1]["claim_text"] == "Claim contradicted"
