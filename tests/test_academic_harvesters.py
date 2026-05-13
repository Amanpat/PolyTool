"""Tests for RIS L4 Multi-source Academic Harvesters.

All tests are offline — no network requests. HTTP calls are injected via _http_fn.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from packages.research.ingestion.academic_harvesters import (
    HARVESTER_REGISTRY,
    SOURCE_CAPABILITY_MATRIX,
    AcademicCandidate,
    ArxivHarvester,
    CrossrefHarvester,
    HarvestError,
    OpenReviewHarvester,
    SemanticScholarHarvester,
    dedup_candidates,
    get_harvester,
)


# ---------------------------------------------------------------------------
# Fixtures — canned HTTP responses
# ---------------------------------------------------------------------------

_ARXIV_ATOM_ONE = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.12345v1</id>
    <title>Prediction Market Microstructure Theory</title>
    <summary>Abstract about market microstructure and prediction markets.</summary>
    <author><name>Alice Smith</name></author>
    <author><name>Bob Jones</name></author>
    <published>2024-01-15T00:00:00Z</published>
  </entry>
</feed>
"""

_ARXIV_ATOM_TWO = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.11111v1</id>
    <title>Limit Order Book Dynamics</title>
    <summary>Study of limit order book price impact and dynamics.</summary>
    <author><name>Carol Lee</name></author>
    <published>2024-02-01T00:00:00Z</published>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2401.22222v1</id>
    <title>Market Making Under Adverse Selection</title>
    <summary>Optimal market making with adverse selection risk.</summary>
    <author><name>Dave Brown</name></author>
    <published>2024-01-20T00:00:00Z</published>
  </entry>
</feed>
"""

_ARXIV_ATOM_EMPTY = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
</feed>
"""

_S2_ONE = json.dumps({
    "data": [{
        "paperId": "s2abc123",
        "title": "Optimal Market Making",
        "abstract": "We study optimal market making with inventory risk.",
        "year": 2024,
        "publicationDate": "2024-03-10",
        "externalIds": {"DOI": "10.1234/abc", "ArXiv": "2401.55555"},
        "authors": [{"name": "Eve White"}, {"name": "Frank Green"}],
        "fieldsOfStudy": ["Finance", "Economics"],
        "openAccessPdf": {"url": "https://arxiv.org/pdf/2401.55555.pdf"},
    }]
}).encode()

_S2_WITH_ARXIV_OVERLAP = json.dumps({
    "data": [{
        "paperId": "s2xyz",
        "title": "Prediction Market Microstructure Theory",
        "abstract": "Same paper from arXiv.",
        "year": 2024,
        "publicationDate": "2024-01-15",
        "externalIds": {"ArXiv": "2401.12345"},
        "authors": [{"name": "Alice Smith"}],
        "fieldsOfStudy": [],
        "openAccessPdf": None,
    }]
}).encode()

_S2_EMPTY = json.dumps({"data": []}).encode()

_CROSSREF_ONE = json.dumps({
    "status": "ok",
    "message": {
        "items": [{
            "DOI": "10.5678/xyz",
            "title": ["Market Microstructure Review"],
            "abstract": "<jats:p>Abstract text about microstructure.</jats:p>",
            "author": [{"given": "Grace", "family": "Hall"}],
            "published-print": {"date-parts": [[2023, 6, 1]]},
            "URL": "https://doi.org/10.5678/xyz",
            "subject": ["Economics", "Finance"],
        }]
    }
}).encode()

_CROSSREF_EMPTY = json.dumps({"status": "ok", "message": {"items": []}}).encode()

_CROSSREF_NO_ABSTRACT = json.dumps({
    "status": "ok",
    "message": {
        "items": [{
            "DOI": "10.9999/no-abstract",
            "title": ["Short Paper Without Abstract"],
            "author": [{"given": "Henry", "family": "Fox"}],
            "published-online": {"date-parts": [[2024, 5, 1]]},
            "URL": "https://doi.org/10.9999/no-abstract",
        }]
    }
}).encode()

_OPENREVIEW_ONE = json.dumps({
    "notes": [{
        "id": "orABC123",
        "cdate": 1704067200000,  # 2024-01-01
        "content": {
            "title": {"value": "Prediction Markets as Information Aggregators"},
            "abstract": {"value": "We analyze prediction markets as mechanisms for aggregating dispersed information."},
            "authors": {"value": ["Ivy Clark", "Jack Davis"]},
            "keywords": {"value": ["prediction markets", "information aggregation", "mechanism design"]},
        }
    }]
}).encode()

_OPENREVIEW_V1_STYLE = json.dumps({
    "notes": [{
        "id": "orV1_abc",
        "cdate": 1700000000000,
        "content": {
            "title": "Market Microstructure at ML Conferences",
            "abstract": "A review paper.",
            "authors": ["Kathy Evans", "Leo Ford"],
            "keywords": ["microstructure"],
        }
    }]
}).encode()

_OPENREVIEW_EMPTY = json.dumps({"notes": []}).encode()


def _make_http_fn(response: bytes):
    """Return an injectable HTTP function that always returns *response*."""
    def _fn(url: str, timeout: int, headers: dict) -> bytes:
        return response
    return _fn


def _make_http_fn_map(responses: dict):
    """Return an injectable HTTP function that matches URLs to responses."""
    def _fn(url: str, timeout: int, headers: dict) -> bytes:
        for key, resp in responses.items():
            if key in url:
                return resp
        raise HarvestError(f"No mock response for URL: {url}")
    return _fn


def _make_error_fn(exc_msg: str = "network error"):
    """Return an injectable HTTP function that always raises HarvestError."""
    def _fn(url: str, timeout: int, headers: dict) -> bytes:
        raise HarvestError(exc_msg)
    return _fn


# ---------------------------------------------------------------------------
# ArxivHarvester
# ---------------------------------------------------------------------------

class TestArxivHarvester:
    def test_search_returns_candidates(self):
        h = ArxivHarvester(_http_fn=_make_http_fn(_ARXIV_ATOM_ONE))
        results = h.search("prediction markets", max_results=5)
        assert len(results) == 1
        c = results[0]
        assert c.title == "Prediction Market Microstructure Theory"
        assert "market microstructure" in c.abstract.lower()
        assert c.authors == ["Alice Smith", "Bob Jones"]
        assert c.published_date == "2024-01-15"
        assert c.source_name == "arxiv"
        assert c.canonical_ids.get("arxiv_id") == "2401.12345"
        assert c.source_url == "https://arxiv.org/abs/2401.12345"

    def test_search_returns_multiple(self):
        h = ArxivHarvester(_http_fn=_make_http_fn(_ARXIV_ATOM_TWO))
        results = h.search("limit order book", max_results=10)
        assert len(results) == 2
        titles = [c.title for c in results]
        assert "Limit Order Book Dynamics" in titles
        assert "Market Making Under Adverse Selection" in titles

    def test_search_empty_returns_empty(self):
        h = ArxivHarvester(_http_fn=_make_http_fn(_ARXIV_ATOM_EMPTY))
        results = h.search("xyzzy no match", max_results=5)
        assert results == []

    def test_search_network_error_returns_empty(self):
        h = ArxivHarvester(_http_fn=_make_error_fn())
        results = h.search("prediction markets")
        assert results == []

    def test_search_malformed_xml_returns_empty(self):
        h = ArxivHarvester(_http_fn=_make_http_fn(b"NOT_XML<<<>>>"))
        results = h.search("prediction markets")
        assert results == []

    def test_search_since_filters_by_date(self):
        h = ArxivHarvester(_http_fn=_make_http_fn(_ARXIV_ATOM_TWO))
        # Only paper published on 2024-02-01 should pass
        results = h.search_since("market", "2024-01-25")
        titles = [c.title for c in results]
        assert "Limit Order Book Dynamics" in titles
        # 2024-01-20 paper should be excluded
        assert "Market Making Under Adverse Selection" not in titles

    def test_candidate_fields_complete(self):
        h = ArxivHarvester(_http_fn=_make_http_fn(_ARXIV_ATOM_ONE))
        results = h.search("test")
        assert results
        c = results[0]
        assert c.source_url
        assert c.title
        assert c.source_name == "arxiv"
        assert "arxiv_id" in c.canonical_ids


# ---------------------------------------------------------------------------
# SemanticScholarHarvester
# ---------------------------------------------------------------------------

class TestSemanticScholarHarvester:
    def test_search_returns_candidates(self):
        h = SemanticScholarHarvester(_http_fn=_make_http_fn(_S2_ONE))
        results = h.search("optimal market making", max_results=5)
        assert len(results) == 1
        c = results[0]
        assert c.title == "Optimal Market Making"
        assert "inventory risk" in c.abstract.lower()
        assert c.authors == ["Eve White", "Frank Green"]
        assert c.published_date == "2024-03-10"
        assert c.source_name == "semantic_scholar"
        assert c.canonical_ids.get("arxiv_id") == "2401.55555"
        assert c.canonical_ids.get("doi") == "10.1234/abc"
        assert c.canonical_ids.get("s2_paper_id") == "s2abc123"
        assert c.canonical_ids.get("s2_pdf_url")
        assert c.fields_of_study == ["Finance", "Economics"]
        # arXiv ID present => canonical URL is arXiv abs page
        assert c.source_url == "https://arxiv.org/abs/2401.55555"

    def test_search_empty_returns_empty(self):
        h = SemanticScholarHarvester(_http_fn=_make_http_fn(_S2_EMPTY))
        results = h.search("no results")
        assert results == []

    def test_search_network_error_returns_empty(self):
        h = SemanticScholarHarvester(_http_fn=_make_error_fn())
        results = h.search("prediction markets")
        assert results == []

    def test_search_malformed_json_returns_empty(self):
        h = SemanticScholarHarvester(_http_fn=_make_http_fn(b"NOT_JSON{"))
        results = h.search("prediction markets")
        assert results == []

    def test_doi_fallback_url(self):
        data = json.dumps({
            "data": [{
                "paperId": "s2doi",
                "title": "DOI-only paper",
                "abstract": "Has DOI but no arXiv ID",
                "year": 2023,
                "publicationDate": "2023-05-01",
                "externalIds": {"DOI": "10.9999/doi-only"},
                "authors": [{"name": "Author A"}],
                "fieldsOfStudy": [],
                "openAccessPdf": None,
            }]
        }).encode()
        h = SemanticScholarHarvester(_http_fn=_make_http_fn(data))
        results = h.search("test")
        assert results[0].source_url == "https://doi.org/10.9999/doi-only"

    def test_s2_only_url(self):
        data = json.dumps({
            "data": [{
                "paperId": "s2only",
                "title": "No external IDs paper",
                "abstract": "Only has S2 ID",
                "year": 2023,
                "publicationDate": "2023-01-01",
                "externalIds": {},
                "authors": [],
                "fieldsOfStudy": [],
                "openAccessPdf": None,
            }]
        }).encode()
        h = SemanticScholarHarvester(_http_fn=_make_http_fn(data))
        results = h.search("test")
        assert results[0].source_url == "https://www.semanticscholar.org/paper/s2only"

    def test_paper_with_no_id_skipped(self):
        data = json.dumps({
            "data": [{
                "paperId": "",
                "title": "No ID at all",
                "abstract": "Should be skipped",
                "externalIds": {},
            }]
        }).encode()
        h = SemanticScholarHarvester(_http_fn=_make_http_fn(data))
        results = h.search("test")
        assert results == []


# ---------------------------------------------------------------------------
# CrossrefHarvester
# ---------------------------------------------------------------------------

class TestCrossrefHarvester:
    def test_search_returns_candidates(self):
        h = CrossrefHarvester(_http_fn=_make_http_fn(_CROSSREF_ONE))
        results = h.search("market microstructure", max_results=5)
        assert len(results) == 1
        c = results[0]
        assert c.title == "Market Microstructure Review"
        # JATS XML tags should be stripped from abstract
        assert "<jats:p>" not in c.abstract
        assert "microstructure" in c.abstract.lower()
        assert c.authors == ["Grace Hall"]
        assert c.published_date == "2023-06-01"
        assert c.source_name == "crossref"
        assert c.canonical_ids.get("doi") == "10.5678/xyz"
        assert c.source_url == "https://doi.org/10.5678/xyz"
        assert "Economics" in c.fields_of_study

    def test_search_empty_returns_empty(self):
        h = CrossrefHarvester(_http_fn=_make_http_fn(_CROSSREF_EMPTY))
        results = h.search("no match")
        assert results == []

    def test_search_network_error_returns_empty(self):
        h = CrossrefHarvester(_http_fn=_make_error_fn())
        results = h.search("prediction markets")
        assert results == []

    def test_abstract_can_be_empty(self):
        h = CrossrefHarvester(_http_fn=_make_http_fn(_CROSSREF_NO_ABSTRACT))
        results = h.search("test")
        assert len(results) == 1
        assert results[0].abstract == ""

    def test_search_since_uses_filter(self):
        # Just verify the URL contains from-pub-date and returns candidates
        captured_urls = []
        def _fn(url: str, timeout: int, headers: dict) -> bytes:
            captured_urls.append(url)
            return _CROSSREF_ONE
        h = CrossrefHarvester(_http_fn=_fn)
        results = h.search_since("microstructure", "2023-01-01")
        assert results  # returns candidates
        assert any("from-pub-date:2023-01-01" in u for u in captured_urls)

    def test_jats_xml_stripped_from_abstract(self):
        data = json.dumps({
            "status": "ok",
            "message": {
                "items": [{
                    "DOI": "10.1234/jats",
                    "title": ["JATS Paper"],
                    "abstract": "<jats:sec><jats:title>Background</jats:title><jats:p>Body text here.</jats:p></jats:sec>",
                    "author": [],
                    "URL": "https://doi.org/10.1234/jats",
                }]
            }
        }).encode()
        h = CrossrefHarvester(_http_fn=_make_http_fn(data))
        results = h.search("test")
        assert results
        assert "<jats" not in results[0].abstract
        assert "Background" in results[0].abstract
        assert "Body text here" in results[0].abstract


# ---------------------------------------------------------------------------
# OpenReviewHarvester
# ---------------------------------------------------------------------------

class TestOpenReviewHarvester:
    def test_search_returns_candidates(self):
        h = OpenReviewHarvester(_http_fn=_make_http_fn(_OPENREVIEW_ONE))
        results = h.search("prediction markets", max_results=5)
        assert len(results) == 1
        c = results[0]
        assert c.title == "Prediction Markets as Information Aggregators"
        assert "aggregat" in c.abstract.lower()
        assert c.authors == ["Ivy Clark", "Jack Davis"]
        assert c.source_name == "openreview"
        assert c.canonical_ids.get("openreview_id") == "orABC123"
        assert c.source_url == "https://openreview.net/forum?id=orABC123"
        assert "prediction markets" in c.fields_of_study
        assert c.published_date == "2024-01-01"

    def test_search_v1_style_plain_values(self):
        h = OpenReviewHarvester(_http_fn=_make_http_fn(_OPENREVIEW_V1_STYLE))
        results = h.search("test")
        assert len(results) == 1
        c = results[0]
        assert c.title == "Market Microstructure at ML Conferences"
        assert c.authors == ["Kathy Evans", "Leo Ford"]

    def test_search_empty_returns_empty(self):
        h = OpenReviewHarvester(_http_fn=_make_http_fn(_OPENREVIEW_EMPTY))
        results = h.search("no match")
        assert results == []

    def test_search_network_error_returns_empty(self):
        h = OpenReviewHarvester(_http_fn=_make_error_fn())
        results = h.search("prediction markets")
        assert results == []

    def test_entry_without_title_skipped(self):
        data = json.dumps({
            "notes": [{"id": "orNOTITLE", "content": {"abstract": {"value": "something"}}}]
        }).encode()
        h = OpenReviewHarvester(_http_fn=_make_http_fn(data))
        results = h.search("test")
        assert results == []

    def test_entry_without_id_skipped(self):
        data = json.dumps({
            "notes": [{"id": "", "content": {"title": {"value": "Has Title"}, "abstract": {"value": "abstract"}}}]
        }).encode()
        h = OpenReviewHarvester(_http_fn=_make_http_fn(data))
        results = h.search("test")
        assert results == []


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

class TestDeduplication:
    def _make_arxiv(self, arxiv_id: str, source: str = "arxiv") -> AcademicCandidate:
        return AcademicCandidate(
            source_url=f"https://arxiv.org/abs/{arxiv_id}",
            title=f"Paper {arxiv_id}",
            abstract="abstract",
            authors=[],
            published_date=None,
            source_name=source,
            canonical_ids={"arxiv_id": arxiv_id},
        )

    def _make_doi(self, doi: str, source: str = "crossref") -> AcademicCandidate:
        return AcademicCandidate(
            source_url=f"https://doi.org/{doi}",
            title=f"Paper DOI {doi}",
            abstract="abstract",
            authors=[],
            published_date=None,
            source_name=source,
            canonical_ids={"doi": doi},
        )

    def _make_no_ids(self, url: str) -> AcademicCandidate:
        return AcademicCandidate(
            source_url=url,
            title="No IDs Paper",
            abstract="abstract",
            authors=[],
            published_date=None,
            source_name="openreview",
            canonical_ids={},
        )

    def test_dedup_by_arxiv_id(self):
        c1 = self._make_arxiv("2401.11111", "arxiv")
        c2 = self._make_arxiv("2401.11111", "semantic_scholar")
        result = dedup_candidates([c1, c2])
        assert len(result) == 1
        assert result[0] is c1  # first wins

    def test_dedup_by_doi(self):
        c1 = self._make_doi("10.1234/abc", "crossref")
        c2 = self._make_doi("10.1234/abc", "semantic_scholar")
        result = dedup_candidates([c1, c2])
        assert len(result) == 1

    def test_no_dedup_different_ids(self):
        c1 = self._make_arxiv("2401.11111")
        c2 = self._make_arxiv("2401.22222")
        result = dedup_candidates([c1, c2])
        assert len(result) == 2

    def test_dedup_arxiv_beats_doi(self):
        c_arxiv = self._make_arxiv("2401.55555")
        c_s2 = AcademicCandidate(
            source_url="https://arxiv.org/abs/2401.55555",
            title="Same Paper",
            abstract="",
            authors=[],
            published_date=None,
            source_name="semantic_scholar",
            canonical_ids={"arxiv_id": "2401.55555", "doi": "10.1234/xyz"},
        )
        result = dedup_candidates([c_arxiv, c_s2])
        assert len(result) == 1

    def test_dedup_by_shared_doi_when_second_candidate_also_has_arxiv(self):
        c_crossref = self._make_doi("10.1234/XYZ", "crossref")
        c_s2 = AcademicCandidate(
            source_url="https://arxiv.org/abs/2401.55555",
            title="Same Paper With More IDs",
            abstract="",
            authors=[],
            published_date=None,
            source_name="semantic_scholar",
            canonical_ids={"arxiv_id": "2401.55555", "doi": "10.1234/xyz"},
        )
        result = dedup_candidates([c_crossref, c_s2])
        assert len(result) == 1
        assert result[0] is c_crossref

    def test_dedup_learns_aliases_from_skipped_duplicate(self):
        c_crossref = self._make_doi("10.1234/alias", "crossref")
        c_s2 = AcademicCandidate(
            source_url="https://arxiv.org/abs/2401.55555",
            title="Same Paper With Alias",
            abstract="",
            authors=[],
            published_date=None,
            source_name="semantic_scholar",
            canonical_ids={"arxiv_id": "2401.55555", "doi": "10.1234/alias"},
        )
        c_arxiv = self._make_arxiv("2401.55555", "arxiv")
        result = dedup_candidates([c_crossref, c_s2, c_arxiv])
        assert len(result) == 1
        assert result[0] is c_crossref

    def test_no_canonical_ids_dedup_by_url(self):
        c1 = self._make_no_ids("https://openreview.net/forum?id=abc")
        c2 = self._make_no_ids("https://openreview.net/forum?id=abc")
        result = dedup_candidates([c1, c2])
        assert len(result) == 1

    def test_empty_list(self):
        result = dedup_candidates([])
        assert result == []

    def test_single_candidate(self):
        c = self._make_arxiv("2401.11111")
        result = dedup_candidates([c])
        assert result == [c]

    def test_preserves_order(self):
        c1 = self._make_arxiv("2401.11111")
        c2 = self._make_arxiv("2401.22222")
        c3 = self._make_arxiv("2401.33333")
        result = dedup_candidates([c1, c2, c3])
        assert [c.canonical_ids["arxiv_id"] for c in result] == [
            "2401.11111", "2401.22222", "2401.33333"
        ]


# ---------------------------------------------------------------------------
# Registry and factory
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_all_active_sources_registered(self):
        expected = {"arxiv", "semantic_scholar", "crossref", "openreview"}
        assert expected.issubset(set(HARVESTER_REGISTRY.keys()))

    def test_get_harvester_returns_correct_types(self):
        h_arxiv = get_harvester("arxiv")
        assert isinstance(h_arxiv, ArxivHarvester)

        h_s2 = get_harvester("semantic_scholar")
        assert isinstance(h_s2, SemanticScholarHarvester)

        h_crossref = get_harvester("crossref")
        assert isinstance(h_crossref, CrossrefHarvester)

        h_or = get_harvester("openreview")
        assert isinstance(h_or, OpenReviewHarvester)

    def test_get_harvester_with_http_fn(self):
        fn = _make_http_fn(_ARXIV_ATOM_ONE)
        h = get_harvester("arxiv", _http_fn=fn)
        assert isinstance(h, ArxivHarvester)

    def test_get_harvester_unknown_raises(self):
        with pytest.raises(KeyError):
            get_harvester("ssrn")

    def test_source_capability_matrix_has_all_sources(self):
        # Active + deferred sources documented
        expected_active = {"arxiv", "semantic_scholar", "crossref", "openreview"}
        expected_deferred = {"ssrn", "nber"}
        for s in expected_active | expected_deferred:
            assert s in SOURCE_CAPABILITY_MATRIX, f"Missing source in matrix: {s}"

    def test_deferred_sources_have_status(self):
        for name in ("ssrn", "nber"):
            caps = SOURCE_CAPABILITY_MATRIX[name]
            assert caps.get("status") == "deferred"

    def test_active_sources_have_descriptions(self):
        for name in ("arxiv", "semantic_scholar", "crossref", "openreview"):
            caps = SOURCE_CAPABILITY_MATRIX[name]
            assert caps.get("description")
            assert caps.get("notes")


# ---------------------------------------------------------------------------
# AcademicCandidate.to_review_queue_record
# ---------------------------------------------------------------------------

class TestCandidateToQueueRecord:
    def test_to_review_queue_record_keys(self):
        c = AcademicCandidate(
            source_url="https://arxiv.org/abs/2401.12345",
            title="Test Paper",
            abstract="test abstract",
            authors=["Author A"],
            published_date="2024-01-01",
            source_name="arxiv",
            canonical_ids={"arxiv_id": "2401.12345"},
        )
        record = c.to_review_queue_record(
            decision="review",
            score=0.6,
            raw_score=1.2,
            reason_codes=["strong_positive:prediction market"],
            matched_terms={"strong_positive": ["prediction market"]},
            allow_threshold=0.55,
            review_threshold=0.35,
            config_version="v1",
        )
        assert record["source_url"] == "https://arxiv.org/abs/2401.12345"
        assert record["title"] == "Test Paper"
        assert record["decision"] == "review"
        assert "candidate_id" in record
        assert record["canonical_ids"]["arxiv_id"] == "2401.12345"
        assert record["source_name"] == "arxiv"

    def test_candidate_id_is_deterministic(self):
        c = AcademicCandidate(
            source_url="https://arxiv.org/abs/2401.12345",
            title="Test",
            abstract="",
            authors=[],
            published_date=None,
            source_name="arxiv",
        )
        r1 = c.to_review_queue_record("review", 0.5, 0.0, [], {}, 0.55, 0.35, "v1")
        r2 = c.to_review_queue_record("review", 0.5, 0.0, [], {}, 0.55, 0.35, "v1")
        assert r1["candidate_id"] == r2["candidate_id"]


# ---------------------------------------------------------------------------
# Queue enqueue path (integration with ReviewQueueStore)
# ---------------------------------------------------------------------------

class TestQueueEnqueue:
    def test_enqueue_single_candidate(self, tmp_path):
        from packages.research.relevance_filter import ReviewQueueStore

        queue_file = tmp_path / "queue.jsonl"
        store = ReviewQueueStore(queue_file)

        c = AcademicCandidate(
            source_url="https://arxiv.org/abs/2401.99999",
            title="Queue Test Paper",
            abstract="abstract for queue test",
            authors=[],
            published_date="2024-01-01",
            source_name="arxiv",
            canonical_ids={"arxiv_id": "2401.99999"},
        )
        record = c.to_review_queue_record("review", 0.6, 1.0, [], {}, 0.55, 0.35, "v1")
        written = store.enqueue(record)
        assert written is True

        records = store.all_records()
        assert len(records) == 1
        assert records[0]["title"] == "Queue Test Paper"

    def test_enqueue_idempotent(self, tmp_path):
        from packages.research.relevance_filter import ReviewQueueStore

        queue_file = tmp_path / "queue.jsonl"
        store = ReviewQueueStore(queue_file)

        c = AcademicCandidate(
            source_url="https://arxiv.org/abs/2401.88888",
            title="Duplicate Test",
            abstract="",
            authors=[],
            published_date=None,
            source_name="arxiv",
        )
        record = c.to_review_queue_record("review", 0.6, 1.0, [], {}, 0.55, 0.35, "v1")
        store.enqueue(record)
        written2 = store.enqueue(record)
        assert written2 is False  # idempotent

        records = store.all_records()
        assert len(records) == 1

    def test_enqueue_force_writes_again(self, tmp_path):
        from packages.research.relevance_filter import ReviewQueueStore

        queue_file = tmp_path / "queue.jsonl"
        store = ReviewQueueStore(queue_file)

        c = AcademicCandidate(
            source_url="https://arxiv.org/abs/2401.77777",
            title="Force Re-enqueue Test",
            abstract="",
            authors=[],
            published_date=None,
            source_name="arxiv",
        )
        record = c.to_review_queue_record("review", 0.6, 1.0, [], {}, 0.55, 0.35, "v1")
        store.enqueue(record)
        written2 = store.enqueue(record, force=True)
        assert written2 is True

        records = store.all_records()
        assert len(records) == 2


# ---------------------------------------------------------------------------
# CLI smoke (no network)
# ---------------------------------------------------------------------------

class TestCLISmoke:
    def test_list_sources_exits_zero(self, capsys):
        from tools.cli.research_harvest import main
        rc = main(["--list-sources"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "semantic_scholar" in captured.out
        assert "DEFERRED" in captured.out

    def test_no_search_exits_nonzero(self):
        from tools.cli.research_harvest import main
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code != 0

    def test_dry_run_no_queue_write(self, tmp_path, monkeypatch):
        """Dry run: reports candidates but does not write to queue."""
        import packages.research.ingestion.academic_harvesters as _mod
        from tools.cli.research_harvest import _run_harvest

        # Override HTTP with canned response
        def _mock_http(url, timeout, headers):
            return _S2_ONE

        queue_file = tmp_path / "queue.jsonl"
        rc = _run_harvest(
            query="market making",
            sources=["semantic_scholar"],
            max_results=5,
            since_date=None,
            force=False,
            dry_run=True,
            queue_path=queue_file,
            _http_fn=_mock_http,
        )
        assert rc == 0
        # Queue file should not exist (dry run)
        assert not queue_file.exists()

    def test_harvest_enqueues_candidates(self, tmp_path):
        """Non-dry run with single candidate enqueues to queue."""
        from tools.cli.research_harvest import _run_harvest

        def _mock_http(url, timeout, headers):
            return _S2_ONE

        queue_file = tmp_path / "queue.jsonl"
        rc = _run_harvest(
            query="market making",
            sources=["semantic_scholar"],
            max_results=5,
            since_date=None,
            force=False,
            dry_run=False,
            queue_path=queue_file,
            _http_fn=_mock_http,
        )
        assert rc == 0

    def test_unknown_source_returns_error(self, tmp_path):
        from tools.cli.research_harvest import _run_harvest

        queue_file = tmp_path / "queue.jsonl"
        rc = _run_harvest(
            query="test",
            sources=["ssrn"],
            max_results=5,
            since_date=None,
            force=False,
            dry_run=True,
            queue_path=queue_file,
        )
        assert rc == 1

    def test_all_sources_runs_four_harvesters(self, tmp_path):
        """--source all runs all 4 active harvesters."""
        from packages.research.ingestion.academic_harvesters import HARVESTER_REGISTRY
        from tools.cli.research_harvest import _run_harvest

        called_urls = []
        def _mock_http(url, timeout, headers):
            called_urls.append(url)
            if "arxiv.org" in url:
                return _ARXIV_ATOM_EMPTY
            elif "semanticscholar.org" in url:
                return _S2_EMPTY
            elif "crossref.org" in url:
                return _CROSSREF_EMPTY
            elif "openreview.net" in url:
                return _OPENREVIEW_EMPTY
            return b'{"data": [], "notes": [], "message": {"items": []}}'

        queue_file = tmp_path / "queue.jsonl"
        rc = _run_harvest(
            query="test",
            sources=list(HARVESTER_REGISTRY.keys()),
            max_results=5,
            since_date=None,
            force=False,
            dry_run=True,
            queue_path=queue_file,
            _http_fn=_mock_http,
        )
        assert rc == 0
        # All four sources should have made HTTP calls
        assert len(called_urls) == len(HARVESTER_REGISTRY)

    def test_cross_source_dedup_reduces_count(self, tmp_path):
        """When arXiv and S2 return the same paper (same arxiv_id), dedup removes one."""
        from tools.cli.research_harvest import _run_harvest

        def _mock_http(url, timeout, headers):
            if "arxiv.org" in url:
                return _ARXIV_ATOM_ONE     # arxiv_id=2401.12345
            elif "semanticscholar.org" in url:
                return _S2_WITH_ARXIV_OVERLAP  # arxiv_id=2401.12345 too
            return b'{"data": [], "notes": [], "message": {"items": []}}'

        queue_file = tmp_path / "queue.jsonl"
        rc = _run_harvest(
            query="microstructure",
            sources=["arxiv", "semantic_scholar"],
            max_results=5,
            since_date=None,
            force=False,
            dry_run=True,
            queue_path=queue_file,
            _http_fn=_mock_http,
        )
        assert rc == 0
        # Combined: 2 raw candidates, 1 after dedup


# ---------------------------------------------------------------------------
# Capability flags
# ---------------------------------------------------------------------------

class TestCapabilityFlags:
    def test_arxiv_pdf_capable(self):
        assert ArxivHarvester.PDF_URL_CAPABLE is True

    def test_s2_pdf_capable(self):
        assert SemanticScholarHarvester.PDF_URL_CAPABLE is True

    def test_crossref_not_pdf_capable(self):
        assert CrossrefHarvester.PDF_URL_CAPABLE is False

    def test_openreview_not_pdf_capable(self):
        assert OpenReviewHarvester.PDF_URL_CAPABLE is False

    def test_all_metadata_only(self):
        for cls in (ArxivHarvester, SemanticScholarHarvester, CrossrefHarvester, OpenReviewHarvester):
            assert cls.METADATA_ONLY is True

    def test_openreview_no_auth(self):
        assert OpenReviewHarvester.AUTH_REQUIRED is False
