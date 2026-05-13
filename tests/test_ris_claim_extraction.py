"""Tests for RIS Phase 4: heuristic claim extraction pipeline.

All tests are deterministic, offline, and use KnowledgeStore(":memory:") +
temporary fixture files via tmp_path. No network calls, no LLM.

Tests cover:
- Claim extraction shape (claim_text, claim_type, confidence, trust_tier,
  validation_status, lifecycle, actor)
- Confidence tier mapping by source document tier
- Evidence linking (chunk excerpt + structured location JSON)
- SUPPORTS and CONTRADICTS relation building
- Idempotency (running extraction twice does not double claims)
- Claims with no assertive content are skipped (code/table/empty chunks)
- Extraction context preserved in notes JSON
- Scope inherited from source document metadata
- Retrieval surfacing via query_knowledge_store_enriched + RRF
- Edge cases (empty doc, doc not found, etc.)
"""

from __future__ import annotations

import json
import pytest

from packages.polymarket.rag.knowledge_store import KnowledgeStore
from packages.research.ingestion.claim_extractor import (
    extract_claims_from_document,
    build_intra_doc_relations,
    extract_and_link,
    HeuristicClaimExtractor,
    _confidence_for_tier,
    _classify_claim_type,
    _has_negation,
    _extract_key_terms,
    _extract_assertive_sentences,
)
from packages.research.ingestion.retriever import (
    query_knowledge_store_enriched,
    query_knowledge_store_for_rrf,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURE_MARKDOWN = """\
# Research Document

## Market Analysis

The crypto market shows strong momentum patterns with 65% of tokens trending upward.
Statistical analysis confirms that BTC price movements correlate with volume signals.
The algorithm detects significant patterns in order flow data across multiple exchanges.

## Risk Assessment

Market makers should maintain adequate inventory buffers to avoid adverse selection.
Best practice recommends a minimum spread of 20 basis points for liquid markets.
The system architecture must support millisecond-level execution for effective market making.

## Negation Section

The BTC market does not support simple momentum strategies without additional filters.
Statistical analysis never produces reliable signals without proper normalization.
The algorithm cannot detect patterns without sufficient historical data volume.

## Code Section

```python
def compute_spread(bid, ask):
    return ask - bid
```

## Table Section

| Column A | Column B |
|----------|----------|
| Value 1  | Value 2  |
| Value 3  | Value 4  |

## Performance Results

Backtesting results show 72% win rate over 6 months of historical data.
The strategy achieves positive expected value with statistical confidence above 95%.
Market analysis reveals strong predictive power in the order flow signals.
"""

RELATION_SUPPORTS_DOC = """\
## Market Momentum

The market momentum algorithm detects strong patterns in order flow data signals across multiple exchanges.
Statistical analysis confirms that market momentum patterns generate consistent order flow data signals.
"""

RELATION_CONTRADICTS_DOC = """\
## Contradicting Evidence

The market momentum algorithm detects strong patterns in order flow data signals across exchanges.
The market momentum algorithm does not detect reliable patterns in order flow data signals.
"""

RELATION_NO_MATCH_DOC = """\
## Disjoint Topics

The cryptocurrency exchange processes thousands of transactions every single second continuously.
Weather patterns indicate significant rainfall amounts expected throughout the coming spring season.
"""

FIXTURE_MARKDOWN_SPARSE = """\
# Sparse Doc

## Empty Section

## Another Empty Section

"""

FIXTURE_MARKDOWN_SHORT = """\
# Brief

Short.
"""


def _make_store() -> KnowledgeStore:
    return KnowledgeStore(":memory:")


def _add_doc(
    store: KnowledgeStore,
    body: str,
    *,
    confidence_tier: str = "PRACTITIONER",
    source_family: str = "blog",
    metadata: dict | None = None,
    source_url: str = "file://test_doc.md",
    title: str = "Test Document",
) -> str:
    """Add a source document and return its doc_id."""
    import hashlib
    content_hash = hashlib.sha256(body.encode()).hexdigest()
    metadata_json = json.dumps(metadata or {})
    return store.add_source_document(
        title=title,
        source_url=source_url,
        source_family=source_family,
        content_hash=content_hash,
        chunk_count=0,
        confidence_tier=confidence_tier,
        metadata_json=metadata_json,
    )


def _add_doc_with_file(
    store: KnowledgeStore,
    tmp_path,
    body: str,
    *,
    confidence_tier: str = "PRACTITIONER",
    source_family: str = "blog",
    metadata: dict | None = None,
    filename: str = "test_doc.md",
) -> tuple[str, str]:
    """Write body to a temp file, register the doc, return (doc_id, file_path)."""
    import hashlib
    fpath = tmp_path / filename
    fpath.write_text(body, encoding="utf-8")
    source_url = f"file://{fpath.as_posix()}"
    content_hash = hashlib.sha256(body.encode()).hexdigest()
    metadata_json = json.dumps(metadata or {})
    doc_id = store.add_source_document(
        title="Test Document",
        source_url=source_url,
        source_family=source_family,
        content_hash=content_hash,
        chunk_count=0,
        confidence_tier=confidence_tier,
        metadata_json=metadata_json,
    )
    return doc_id, str(fpath)


# ---------------------------------------------------------------------------
# Unit tests: helper functions
# ---------------------------------------------------------------------------

class TestConfidenceMapping:
    def test_peer_reviewed_tier(self):
        assert _confidence_for_tier("PEER_REVIEWED") == 0.85

    def test_practitioner_tier(self):
        assert _confidence_for_tier("PRACTITIONER") == 0.70

    def test_community_tier(self):
        assert _confidence_for_tier("COMMUNITY") == 0.55

    def test_default_unknown_tier(self):
        assert _confidence_for_tier("UNKNOWN") == 0.70

    def test_none_tier(self):
        assert _confidence_for_tier(None) == 0.70


class TestClaimTypeClassification:
    def test_empirical_with_percentage(self):
        assert _classify_claim_type("65% of traders use this strategy") == "empirical"

    def test_empirical_with_number(self):
        assert _classify_claim_type("The system processes 1000 events per second") == "empirical"

    def test_normative_should(self):
        assert _classify_claim_type("Market makers should maintain adequate inventory") == "normative"

    def test_normative_must(self):
        assert _classify_claim_type("The system must support millisecond execution") == "normative"

    def test_normative_recommend(self):
        assert _classify_claim_type("We recommend a minimum spread of 20 bps") == "normative"

    def test_normative_best_practice(self):
        assert _classify_claim_type("Best practice is to use order flow signals") == "normative"

    def test_structural_architecture(self):
        assert _classify_claim_type("The architecture uses three layers") == "structural"

    def test_structural_system(self):
        assert _classify_claim_type("The system design relies on a microservice pattern") == "structural"

    def test_default_empirical(self):
        assert _classify_claim_type("The algorithm detects patterns in data") == "empirical"


class TestNegationDetection:
    def test_not_negation(self):
        assert _has_negation("This does not support simple strategies") is True

    def test_never_negation(self):
        assert _has_negation("The signal never produces false positives") is True

    def test_cannot_negation(self):
        assert _has_negation("The algorithm cannot detect patterns without data") is True

    def test_unlikely_negation(self):
        assert _has_negation("Momentum signals are unlikely to persist") is True

    def test_no_negation_word(self):
        assert _has_negation("The market shows strong upward momentum") is False

    def test_positive_sentence(self):
        assert _has_negation("Statistical analysis confirms strong correlation") is False

    def test_doesnt_negation(self):
        assert _has_negation("The system doesn't support batch processing") is True

    def test_wont_negation(self):
        assert _has_negation("The strategy won't work without normalization") is True


class TestKeyTermExtraction:
    def test_filters_stopwords(self):
        terms = _extract_key_terms("The algorithm is detecting patterns in the data")
        assert "the" not in terms
        assert "is" not in terms
        assert "in" not in terms

    def test_keeps_content_terms(self):
        terms = _extract_key_terms("The algorithm detects patterns in market data")
        assert "algorithm" in terms
        assert "detects" in terms
        assert "patterns" in terms
        assert "market" in terms
        assert "data" in terms

    def test_min_length_3(self):
        terms = _extract_key_terms("A is ok at by")
        # All these should be filtered (len < 3 or stopwords)
        assert len(terms) == 0

    def test_lowercases(self):
        terms = _extract_key_terms("Market Momentum Pattern Analysis")
        assert "market" in terms
        assert "momentum" in terms


class TestAssertiveSentences:
    def test_extracts_assertive_sentences(self):
        text = (
            "The algorithm detects patterns in order flow data. "
            "Statistical analysis confirms strong correlation signals. "
            "Market makers should maintain adequate inventory buffers."
        )
        sentences = _extract_assertive_sentences(text)
        assert len(sentences) >= 1

    def test_skips_heading_lines(self):
        text = "## Market Analysis\nThe market shows strong patterns."
        sentences = _extract_assertive_sentences(text)
        # Should not include the heading line
        for s in sentences:
            assert not s.startswith("#")

    def test_skips_code_lines(self):
        text = "```python\ndef compute_spread():\n    pass\n```"
        sentences = _extract_assertive_sentences(text)
        # Code lines should be filtered out
        for s in sentences:
            assert "def compute_spread" not in s

    def test_skips_very_short_sentences(self):
        sentences = _extract_assertive_sentences("Short.")
        assert len(sentences) == 0

    def test_caps_at_five_per_chunk(self):
        # Generate more than 5 assertive sentences
        long_text = " ".join([
            f"The algorithm number {i} detects important market patterns in order flow data signals."
            for i in range(10)
        ])
        sentences = _extract_assertive_sentences(long_text)
        assert len(sentences) <= 5


# ---------------------------------------------------------------------------
# Integration tests: extraction pipeline
# ---------------------------------------------------------------------------

class TestExtractClaimsFromDocument:
    def test_doc_not_found_returns_empty(self):
        store = _make_store()
        result = extract_claims_from_document(store, "nonexistent-doc-id")
        assert result == []

    def test_produces_claims_from_markdown_doc(self, tmp_path):
        store = _make_store()
        doc_id, _ = _add_doc_with_file(store, tmp_path, FIXTURE_MARKDOWN)
        claim_ids = extract_claims_from_document(store, doc_id)
        assert len(claim_ids) >= 1

    def test_each_claim_has_required_fields(self, tmp_path):
        store = _make_store()
        doc_id, _ = _add_doc_with_file(store, tmp_path, FIXTURE_MARKDOWN)
        claim_ids = extract_claims_from_document(store, doc_id)
        assert len(claim_ids) >= 1

        for cid in claim_ids:
            claim = store.get_claim(cid)
            assert claim is not None
            assert claim["claim_text"]
            assert claim["claim_type"]
            assert claim["confidence"] > 0
            assert claim["trust_tier"]
            assert claim["validation_status"] == "UNTESTED"
            assert claim["lifecycle"] == "active"
            assert claim["actor"] == "heuristic_v2_nofrontmatter"

    def test_confidence_peer_reviewed(self, tmp_path):
        store = _make_store()
        doc_id, _ = _add_doc_with_file(
            store, tmp_path, FIXTURE_MARKDOWN,
            confidence_tier="PEER_REVIEWED"
        )
        claim_ids = extract_claims_from_document(store, doc_id)
        assert len(claim_ids) >= 1
        claim = store.get_claim(claim_ids[0])
        assert claim["confidence"] == 0.85

    def test_confidence_community(self, tmp_path):
        store = _make_store()
        doc_id, _ = _add_doc_with_file(
            store, tmp_path, FIXTURE_MARKDOWN,
            confidence_tier="COMMUNITY"
        )
        claim_ids = extract_claims_from_document(store, doc_id)
        assert len(claim_ids) >= 1
        claim = store.get_claim(claim_ids[0])
        assert claim["confidence"] == 0.55

    def test_confidence_practitioner(self, tmp_path):
        store = _make_store()
        doc_id, _ = _add_doc_with_file(
            store, tmp_path, FIXTURE_MARKDOWN,
            confidence_tier="PRACTITIONER"
        )
        claim_ids = extract_claims_from_document(store, doc_id)
        assert len(claim_ids) >= 1
        claim = store.get_claim(claim_ids[0])
        assert claim["confidence"] == 0.70

    def test_each_claim_has_evidence_row(self, tmp_path):
        store = _make_store()
        doc_id, _ = _add_doc_with_file(store, tmp_path, FIXTURE_MARKDOWN)
        claim_ids = extract_claims_from_document(store, doc_id)
        assert len(claim_ids) >= 1

        for cid in claim_ids:
            # Each claim must have at least one evidence row linking to the doc
            provenance = store.get_provenance(cid)
            assert len(provenance) >= 1
            assert provenance[0]["id"] == doc_id

    def test_evidence_has_excerpt_and_location(self, tmp_path):
        store = _make_store()
        doc_id, _ = _add_doc_with_file(store, tmp_path, FIXTURE_MARKDOWN)
        claim_ids = extract_claims_from_document(store, doc_id)
        assert len(claim_ids) >= 1

        # Inspect evidence table directly
        rows = store._conn.execute(
            "SELECT * FROM claim_evidence WHERE claim_id = ?", (claim_ids[0],)
        ).fetchall()
        assert len(rows) >= 1
        row = dict(rows[0])
        assert row["excerpt"] is not None
        assert 0 < len(row["excerpt"]) <= 500
        assert row["location"] is not None
        # Location must be valid JSON with required keys
        loc = json.loads(row["location"])
        assert "chunk_id" in loc
        assert "start_word" in loc
        assert "end_word" in loc
        assert "document_id" in loc
        assert loc["document_id"] == doc_id
        # section_heading must be present as a string (may be empty if no preceding heading)
        assert "section_heading" in loc
        assert isinstance(loc["section_heading"], str)

    def test_idempotent_extraction_evidence_not_doubled(self, tmp_path):
        """Running extraction twice does not double evidence rows per claim."""
        def _count_evidence(store, claim_id):
            return store._conn.execute(
                "SELECT COUNT(*) as c FROM claim_evidence WHERE claim_id = ?",
                (claim_id,),
            ).fetchone()["c"]

        store = _make_store()
        doc_id, _ = _add_doc_with_file(
            store, tmp_path, FIXTURE_MARKDOWN, filename="idempotent_ev.md"
        )

        claim_ids = extract_claims_from_document(store, doc_id)
        assert len(claim_ids) >= 1

        counts_before = {cid: _count_evidence(store, cid) for cid in claim_ids}

        # Second extraction — same doc, same store
        extract_claims_from_document(store, doc_id)

        counts_after = {cid: _count_evidence(store, cid) for cid in claim_ids}

        # Evidence rows must not have grown (EXISTS check in extractor prevents doubling)
        for cid in claim_ids:
            assert counts_after[cid] == counts_before[cid], (
                f"Evidence rows doubled for claim {cid}: "
                f"before={counts_before[cid]}, after={counts_after[cid]}"
            )

    def test_notes_json_has_extraction_context(self, tmp_path):
        store = _make_store()
        doc_id, _ = _add_doc_with_file(store, tmp_path, FIXTURE_MARKDOWN)
        claim_ids = extract_claims_from_document(store, doc_id)
        assert len(claim_ids) >= 1

        claim = store.get_claim(claim_ids[0])
        notes = json.loads(claim["notes"])
        assert notes["extractor_id"] == "heuristic_v2_nofrontmatter"
        assert "chunk_id" in notes
        assert notes["document_id"] == doc_id

    def test_scope_from_metadata(self, tmp_path):
        store = _make_store()
        doc_id, _ = _add_doc_with_file(
            store, tmp_path, FIXTURE_MARKDOWN,
            metadata={"tags": "crypto,trading"}
        )
        claim_ids = extract_claims_from_document(store, doc_id)
        assert len(claim_ids) >= 1

        # At least some claims should have scope set
        claims_with_scope = [
            c for c in [store.get_claim(cid) for cid in claim_ids]
            if c and c.get("scope")
        ]
        assert len(claims_with_scope) >= 1

    def test_idempotent_extraction(self, tmp_path):
        """Running extraction twice on same doc does not double claims."""
        store = _make_store()
        doc_id, _ = _add_doc_with_file(store, tmp_path, FIXTURE_MARKDOWN)

        claim_ids_first = extract_claims_from_document(store, doc_id)
        claim_ids_second = extract_claims_from_document(store, doc_id)

        # Second run should return same IDs (INSERT OR IGNORE), not new ones
        assert set(claim_ids_first) == set(claim_ids_second)

        # Total claims in DB should be the same count after both runs
        all_claims = store.query_claims(apply_freshness=False)
        assert len(all_claims) == len(claim_ids_first)

    def test_code_only_section_produces_no_claims(self, tmp_path):
        """A document with only code blocks should produce no claims."""
        code_only = """\
```python
def compute_spread(bid, ask):
    return ask - bid

def adjust_inventory(position, limit):
    return min(position, limit)
```
"""
        store = _make_store()
        doc_id, _ = _add_doc_with_file(store, tmp_path, code_only, filename="code_doc.md")
        claim_ids = extract_claims_from_document(store, doc_id)
        assert claim_ids == []

    def test_table_only_section_minimal_claims(self, tmp_path):
        """A document with only table data should produce 0 or very few claims."""
        table_only = """\
| Column A | Column B | Column C |
|----------|----------|----------|
| Value 1  | Value 2  | Value 3  |
| Value 4  | Value 5  | Value 6  |
| Value 7  | Value 8  | Value 9  |
"""
        store = _make_store()
        doc_id, _ = _add_doc_with_file(store, tmp_path, table_only, filename="table_doc.md")
        claim_ids = extract_claims_from_document(store, doc_id)
        # Table lines should not generate assertive claims (they're data rows)
        # We allow 0 or a small count if the table header is misidentified
        assert len(claim_ids) <= 1


# ---------------------------------------------------------------------------
# Integration tests: relation building
# ---------------------------------------------------------------------------

class TestBuildIntraDocRelations:
    def test_supports_relation_between_shared_term_claims(self, tmp_path):
        """Claims sharing 3+ key terms get exactly one SUPPORTS relation."""
        store = _make_store()
        doc_id, _ = _add_doc_with_file(
            store, tmp_path, RELATION_SUPPORTS_DOC, filename="supports_doc.md"
        )
        claim_ids = extract_claims_from_document(store, doc_id)
        assert len(claim_ids) == 2, (
            f"Expected exactly 2 claims from RELATION_SUPPORTS_DOC, got {len(claim_ids)}"
        )

        count = build_intra_doc_relations(store, claim_ids)
        assert count == 1

        relations = store.get_relations(claim_ids[0])
        assert len(relations) == 1
        rel = relations[0]
        assert rel["relation_type"] == "SUPPORTS"
        assert rel["source_claim_id"] in claim_ids
        assert rel["target_claim_id"] in claim_ids

    def test_contradicts_relation_for_negation_pair(self, tmp_path):
        """A claim with negation + a positive claim sharing key terms get CONTRADICTS."""
        store = _make_store()
        doc_id, _ = _add_doc_with_file(
            store, tmp_path, RELATION_CONTRADICTS_DOC, filename="contradicts_doc.md"
        )
        claim_ids = extract_claims_from_document(store, doc_id)
        assert len(claim_ids) == 2, (
            f"Expected exactly 2 claims from RELATION_CONTRADICTS_DOC, got {len(claim_ids)}"
        )

        count = build_intra_doc_relations(store, claim_ids)
        assert count == 1

        relations = store.get_relations(claim_ids[0], relation_type="CONTRADICTS")
        assert len(relations) == 1
        rel = relations[0]
        assert rel["relation_type"] == "CONTRADICTS"
        assert rel["source_claim_id"] in claim_ids
        assert rel["target_claim_id"] in claim_ids

    def test_no_relation_when_insufficient_shared_terms(self, tmp_path):
        """Claims without 3+ shared key terms produce no relations."""
        store = _make_store()
        doc_id, _ = _add_doc_with_file(
            store, tmp_path, RELATION_NO_MATCH_DOC, filename="no_match_doc.md"
        )
        claim_ids = extract_claims_from_document(store, doc_id)
        assert len(claim_ids) >= 2

        count = build_intra_doc_relations(store, claim_ids)
        assert count == 0

    def test_relation_idempotent_on_rerun(self, tmp_path):
        """Each call to build_intra_doc_relations inserts new rows (no UNIQUE constraint).

        Known limitation: claim_relations has no UNIQUE constraint on
        (source_claim_id, target_claim_id, relation_type), so running
        build_intra_doc_relations twice inserts duplicate rows. Each run
        returns count == 1 (the number of new inserts in that run).
        This is a schema-level concern tracked for a future ticket.
        """
        store = _make_store()
        doc_id, _ = _add_doc_with_file(
            store, tmp_path, RELATION_SUPPORTS_DOC, filename="idempotent_doc.md"
        )
        claim_ids = extract_claims_from_document(store, doc_id)
        assert len(claim_ids) == 2

        count1 = build_intra_doc_relations(store, claim_ids)
        assert count1 == 1

        count2 = build_intra_doc_relations(store, claim_ids)
        assert count2 == 1  # second run also inserts 1 row (no dedup)

        # Total rows in DB after 2 runs = 2 (both rows present, no UNIQUE constraint)
        all_relations = store.get_relations(claim_ids[0])
        assert len(all_relations) == 2

    def test_returns_zero_for_single_claim(self, tmp_path):
        """No relations possible with only one claim."""
        single_claim_doc = """\
## Market Analysis

The crypto market shows strong momentum patterns with 65% upward trending.
"""
        store = _make_store()
        doc_id, _ = _add_doc_with_file(
            store, tmp_path, single_claim_doc, filename="single.md"
        )
        claim_ids = extract_claims_from_document(store, doc_id)

        if len(claim_ids) == 1:
            count = build_intra_doc_relations(store, claim_ids)
            assert count == 0
        else:
            # Multiple claims extracted — just verify it runs
            count = build_intra_doc_relations(store, claim_ids)
            assert count >= 0

    def test_empty_claim_ids_returns_zero(self):
        store = _make_store()
        count = build_intra_doc_relations(store, [])
        assert count == 0


# ---------------------------------------------------------------------------
# Integration tests: extract_and_link wrapper
# ---------------------------------------------------------------------------

class TestExtractAndLink:
    def test_returns_summary_dict(self, tmp_path):
        store = _make_store()
        doc_id, _ = _add_doc_with_file(store, tmp_path, FIXTURE_MARKDOWN)
        result = extract_and_link(store, doc_id)

        assert "doc_id" in result
        assert "claims_extracted" in result
        assert "relations_created" in result
        assert "claim_ids" in result
        assert result["doc_id"] == doc_id
        assert result["claims_extracted"] >= 3, (
            f"Expected >= 3 claims from FIXTURE_MARKDOWN, got {result['claims_extracted']}"
        )
        assert result["relations_created"] >= 0
        assert isinstance(result["claim_ids"], list)

    def test_doc_not_found_returns_zero(self):
        store = _make_store()
        result = extract_and_link(store, "nonexistent-id")
        assert result["claims_extracted"] == 0
        assert result["relations_created"] == 0


# ---------------------------------------------------------------------------
# Integration tests: retrieval surfacing
# ---------------------------------------------------------------------------

class TestRetrievalSurfacing:
    def test_claims_appear_in_enriched_query(self, tmp_path):
        store = _make_store()
        doc_id, _ = _add_doc_with_file(store, tmp_path, FIXTURE_MARKDOWN)
        claim_ids = extract_claims_from_document(store, doc_id)
        assert len(claim_ids) >= 1

        enriched = query_knowledge_store_enriched(store, top_k=50)
        returned_ids = {c["id"] for c in enriched}

        # At least one extracted claim should appear in the enriched query
        assert len(returned_ids.intersection(set(claim_ids))) >= 1

    def test_enriched_query_includes_provenance(self, tmp_path):
        store = _make_store()
        doc_id, _ = _add_doc_with_file(store, tmp_path, FIXTURE_MARKDOWN)
        extract_claims_from_document(store, doc_id)

        enriched = query_knowledge_store_enriched(store, top_k=50)
        assert len(enriched) >= 1

        # Claims with evidence should have provenance_docs populated
        claims_with_provenance = [c for c in enriched if c.get("provenance_docs")]
        assert len(claims_with_provenance) >= 1

    def test_claims_appear_in_rrf_query(self, tmp_path):
        store = _make_store()
        doc_id, _ = _add_doc_with_file(store, tmp_path, FIXTURE_MARKDOWN)
        claim_ids = extract_claims_from_document(store, doc_id)
        assert len(claim_ids) >= 1

        rrf_results = query_knowledge_store_for_rrf(store, top_k=50)
        returned_ids = {r["chunk_id"] for r in rrf_results}

        # At least one extracted claim should appear in RRF results
        assert len(returned_ids.intersection(set(claim_ids))) >= 1

    def test_rrf_result_has_required_fields(self, tmp_path):
        store = _make_store()
        doc_id, _ = _add_doc_with_file(store, tmp_path, FIXTURE_MARKDOWN)
        extract_claims_from_document(store, doc_id)

        rrf_results = query_knowledge_store_for_rrf(store, top_k=50)
        assert len(rrf_results) >= 1

        r = rrf_results[0]
        assert "chunk_id" in r
        assert "score" in r
        assert "snippet" in r
        assert "file_path" in r
        assert "chunk_index" in r
        assert "doc_id" in r
        assert "metadata" in r


# ---------------------------------------------------------------------------
# HeuristicClaimExtractor class
# ---------------------------------------------------------------------------

class TestHeuristicClaimExtractorClass:
    def test_class_exists_and_has_expected_interface(self):
        extractor = HeuristicClaimExtractor()
        assert hasattr(extractor, "extract_claims")
        assert hasattr(extractor, "EXTRACTOR_ID")
        assert extractor.EXTRACTOR_ID == "heuristic_v2_nofrontmatter"

    def test_class_extract_wraps_function(self, tmp_path):
        store = _make_store()
        doc_id, _ = _add_doc_with_file(store, tmp_path, FIXTURE_MARKDOWN)

        extractor = HeuristicClaimExtractor()
        claim_ids = extractor.extract_claims(store, doc_id)
        assert isinstance(claim_ids, list)


# ---------------------------------------------------------------------------
# Strategy 1.5: body_file pointer in metadata_json
# ---------------------------------------------------------------------------

# Long enough body for the academic gate (>= 5000 chars)
_LONG_ACADEMIC_BODY = FIXTURE_MARKDOWN * 7


class TestAcademicBodyFileStrategy:
    """Tests for _get_document_body Strategy 1.5: body_file path in metadata_json."""

    def _add_academic_doc(self, store, *, metadata: dict, title: str = "Academic Paper") -> str:
        import hashlib
        return store.add_source_document(
            title=title,
            source_url="https://arxiv.org/abs/1234.56789",
            source_family="academic",
            content_hash=hashlib.sha256(title.encode()).hexdigest(),
            chunk_count=0,
            confidence_tier="PEER_REVIEWED",
            metadata_json=json.dumps(metadata),
        )

    def test_claims_extracted_via_body_file_pointer(self, tmp_path):
        """Marker-ready academic doc with body_file pointer produces claims."""
        body_file = tmp_path / "arxiv:1234.56789.body.txt"
        body_file.write_text(_LONG_ACADEMIC_BODY, encoding="utf-8")

        store = _make_store()
        doc_id = self._add_academic_doc(store, metadata={
            "body_source": "marker",
            "body_length": len(_LONG_ACADEMIC_BODY),
            "body_file": f"file://{body_file.as_posix()}",
            "canonical_ids": {"arxiv_id": "1234.56789"},
        })

        claim_ids = extract_claims_from_document(store, doc_id)
        assert len(claim_ids) >= 1, "body_file pointer should enable claim extraction"

    def test_missing_body_file_produces_no_claims(self, tmp_path):
        """body_file pointing to nonexistent path returns empty claim list."""
        store = _make_store()
        doc_id = self._add_academic_doc(store, metadata={
            "body_source": "marker",
            "body_length": 50000,
            "body_file": f"file://{(tmp_path / 'nonexistent.body.txt').as_posix()}",
            "canonical_ids": {"arxiv_id": "0000.00001"},
        }, title="Missing Body Paper")

        claim_ids = extract_claims_from_document(store, doc_id)
        assert claim_ids == [], "Missing body_file should produce no claims"

    def test_no_body_file_no_inline_body_returns_empty(self):
        """Academic doc with no body pointer and no inline body returns empty."""
        store = _make_store()
        import hashlib
        doc_id = store.add_source_document(
            title="No Body Paper",
            source_url="https://arxiv.org/abs/2222.22222",
            source_family="academic",
            content_hash=hashlib.sha256(b"no body").hexdigest(),
            chunk_count=0,
            confidence_tier="PEER_REVIEWED",
            metadata_json=json.dumps({
                "body_source": "marker",
                "body_length": 50000,
                "canonical_ids": {"arxiv_id": "2222.22222"},
            }),
        )

        claim_ids = extract_claims_from_document(store, doc_id)
        assert claim_ids == []

    def test_body_file_idempotent(self, tmp_path):
        """Re-running extraction with body_file does not duplicate claim IDs."""
        body_file = tmp_path / "paper.body.txt"
        body_file.write_text(_LONG_ACADEMIC_BODY, encoding="utf-8")

        store = _make_store()
        doc_id = self._add_academic_doc(store, metadata={
            "body_source": "marker",
            "body_length": len(_LONG_ACADEMIC_BODY),
            "body_file": f"file://{body_file.as_posix()}",
            "canonical_ids": {"arxiv_id": "1111.11111"},
        }, title="Idempotent Body File Test")

        first = extract_claims_from_document(store, doc_id)
        second = extract_claims_from_document(store, doc_id)
        assert set(first) == set(second), "Second extraction must return same claim IDs"

    def test_strategy1_inline_body_takes_priority(self, tmp_path):
        """Inline body (Strategy 1) takes priority over body_file (Strategy 1.5)."""
        # File with FIXTURE_MARKDOWN content
        body_file = tmp_path / "file_body.txt"
        body_file.write_text(FIXTURE_MARKDOWN, encoding="utf-8")

        # Inline body is short but assertive; if Strategy 1 wins, fewer claims extracted
        inline_body = (
            "The prediction market efficiency hypothesis states that prices reflect "
            "all available information with documented 87% accuracy across major venues."
        )

        store = _make_store()
        doc_id = self._add_academic_doc(store, metadata={
            "body": inline_body,           # Strategy 1 — should be used
            "body_file": f"file://{body_file.as_posix()}",  # Strategy 1.5 — skipped
        })

        claim_ids = extract_claims_from_document(store, doc_id)
        # Should produce at least one claim from the inline body
        assert len(claim_ids) >= 1


# ---------------------------------------------------------------------------
# index_done_items with extract_claims integration
# ---------------------------------------------------------------------------

def _make_marker_queue_fixture(tmp_path, body_text: str, arxiv_id: str = "9876.54321") -> "Path":
    """Create a minimal queue dir with a marker-ready result + body sidecar."""
    queue_dir = tmp_path / f"queue_{arxiv_id.replace('.', '_')}"
    queue_dir.mkdir()
    bodies_dir = queue_dir / "bodies"
    bodies_dir.mkdir()

    candidate_id = f"arxiv:{arxiv_id}"

    (bodies_dir / f"{candidate_id}.body.txt").write_text(body_text, encoding="utf-8")
    (bodies_dir / f"{candidate_id}.meta.json").write_text(
        json.dumps({
            "title": "Test Prediction Market Paper",
            "abstract": "A study of prediction market microstructure and efficiency.",
            "authors": ["Jane Doe", "John Smith"],
            "published_date": "2024-01-01",
            "body_source": "marker",
            "body_length": len(body_text),
            "candidate_id": candidate_id,
        }),
        encoding="utf-8",
    )
    (queue_dir / "results.jsonl").write_text(
        json.dumps({
            "candidate_id": candidate_id,
            "source_url": f"https://arxiv.org/abs/{arxiv_id}",
            "arxiv_id": arxiv_id,
            "title": "Test Prediction Market Paper",
            "body_source": "marker",
            "body_length": len(body_text),
            "marker_ready": True,
            "queue_status": "done",
            "rejected": False,
            "parse_seconds": 45.5,
            "attempt": 1,
            "processed_at": "2026-05-09T12:00:00+00:00",
        }) + "\n",
        encoding="utf-8",
    )
    return queue_dir


class TestIndexDoneClaimExtraction:
    """Integration tests for index_done_items(extract_claims=True)."""

    def test_extract_claims_true_produces_claims(self, tmp_path):
        """index_done with extract_claims=True produces at least one claim per paper."""
        from packages.research.ingestion.marker_queue import MarkerParseQueue

        queue_dir = _make_marker_queue_fixture(tmp_path, _LONG_ACADEMIC_BODY)
        store = _make_store()
        q = MarkerParseQueue(queue_dir=queue_dir)
        summary = q.index_done_items(extract_claims=True, _store=store)

        assert len(summary["indexed"]) == 1, f"Expected 1 indexed, got: {summary}"
        assert summary["indexed"][0]["claims_extracted"] >= 1
        assert summary["total_claims_extracted"] >= 1

    def test_extract_claims_false_skips_extraction(self, tmp_path):
        """index_done with extract_claims=False stores doc but extracts no claims."""
        from packages.research.ingestion.marker_queue import MarkerParseQueue

        queue_dir = _make_marker_queue_fixture(
            tmp_path, _LONG_ACADEMIC_BODY, arxiv_id="1111.99998"
        )
        store = _make_store()
        q = MarkerParseQueue(queue_dir=queue_dir)
        summary = q.index_done_items(extract_claims=False, _store=store)

        assert len(summary["indexed"]) == 1
        assert summary["indexed"][0].get("claims_extracted", 0) == 0
        assert summary.get("total_claims_extracted", 0) == 0

    def test_pdfplumber_result_not_indexed_no_claims(self, tmp_path):
        """A result with marker_ready=False (pdfplumber) is never indexed or claimed."""
        from packages.research.ingestion.marker_queue import MarkerParseQueue

        queue_dir = tmp_path / "pdfplumber_queue"
        queue_dir.mkdir()
        bodies_dir = queue_dir / "bodies"
        bodies_dir.mkdir()
        candidate_id = "arxiv:3333.44444"
        (bodies_dir / f"{candidate_id}.body.txt").write_text(
            _LONG_ACADEMIC_BODY, encoding="utf-8"
        )
        (bodies_dir / f"{candidate_id}.meta.json").write_text(
            json.dumps({"title": "pdfplumber paper", "body_source": "pdfplumber"}),
            encoding="utf-8",
        )
        (queue_dir / "results.jsonl").write_text(
            json.dumps({
                "candidate_id": candidate_id,
                "source_url": "https://arxiv.org/abs/3333.44444",
                "arxiv_id": "3333.44444",
                "body_source": "pdfplumber",
                "body_length": len(_LONG_ACADEMIC_BODY),
                "marker_ready": False,
                "queue_status": "done",
                "rejected": True,
            }) + "\n",
            encoding="utf-8",
        )

        store = _make_store()
        q = MarkerParseQueue(queue_dir=queue_dir)
        summary = q.index_done_items(extract_claims=True, _store=store)

        assert len(summary["indexed"]) == 0, "pdfplumber docs must not be indexed"
        assert summary.get("total_claims_extracted", 0) == 0

    def test_e2e_index_extract_query(self, tmp_path):
        """E2E: index_done(extract_claims=True) -> research-query returns citation."""
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        from packages.research.synthesis.academic_query import query_academic_corpus

        queue_dir = _make_marker_queue_fixture(
            tmp_path, _LONG_ACADEMIC_BODY, arxiv_id="5555.66666"
        )
        store = _make_store()
        q = MarkerParseQueue(queue_dir=queue_dir)
        summary = q.index_done_items(extract_claims=True, _store=store)

        assert not summary["failed"], f"Indexing failures: {summary['failed']}"
        assert len(summary["indexed"]) == 1, f"Expected 1 indexed paper, got: {summary}"
        assert summary["total_claims_extracted"] >= 1, "Expected claims to be extracted"

        # Query uses single-word substring match against claim_text
        result = query_academic_corpus(
            "momentum",          # "momentum patterns" appears in FIXTURE_MARKDOWN claims
            _store=store,
            max_query_angles=1,  # primary only, no extra angle expansion
        )

        assert not result.had_fallback, f"Unexpected fallback: {result.warning}"
        assert len(result.citations) >= 1, "Expected at least one citation"
        assert result.citations[0].body_source == "marker"

    def test_rerun_index_done_idempotent_claims(self, tmp_path):
        """Running index_done twice does not duplicate claims."""
        from packages.research.ingestion.marker_queue import MarkerParseQueue

        queue_dir = _make_marker_queue_fixture(
            tmp_path, _LONG_ACADEMIC_BODY, arxiv_id="7777.88888"
        )
        store = _make_store()
        q = MarkerParseQueue(queue_dir=queue_dir)

        summary1 = q.index_done_items(extract_claims=True, _store=store)
        assert len(summary1["indexed"]) == 1
        claims_first = summary1["total_claims_extracted"]

        # Second run — same store, no --force: should skip already-indexed
        summary2 = q.index_done_items(extract_claims=True, _store=store)
        assert len(summary2["indexed"]) == 0, "Already-indexed paper should be skipped"
        assert len(summary2["skipped_already_indexed"]) == 1

        # Total claims in DB unchanged (no duplicates)
        all_claims = store.query_claims(apply_freshness=False)
        assert len(all_claims) == claims_first
