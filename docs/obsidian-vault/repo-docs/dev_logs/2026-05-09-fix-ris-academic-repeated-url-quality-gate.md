---
title: Fix Ris Academic Repeated Url Quality Gate
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-09_fix-ris-academic-repeated-url-quality-gate.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Fix: RIS Academic Repeated-URL Quality Gate Too Aggressive

**Date:** 2026-05-09
**Objective:** Allow long Marker-parsed academic papers to pass `index-done` when a
repository/dataset URL is legitimately repeated a small number of times in references
or footnotes, without weakening spam protection for short or non-Marker documents.

---

## Root Cause

`packages/research/evaluation/hard_stops.py` — check 4b — rejected any document
where a single URL appeared 4 or more times, regardless of document length or source
type. This flat threshold was calibrated for spam/web content, not for full academic
PDFs that routinely cite the same repository URL in multiple sections.

Operator paper: `arxiv:2604.24366` ("The Anatomy of a Decentralized Prediction Market",
56,856 chars, `body_source=marker`) contains
`https://github.com/philippdubach/polymarket-microstructure)` in 4 places
(references, footnotes, caption) — completely normal for a methods paper with a public
code repo. `check_hard_stops` rejected it, preventing `index-done` from indexing the
paper and leaving `research-query` returning `had_fallback=True`.

---

## Rule Change and Safety Rationale

**Before:** any URL repeated ≥ 4 times → `spam_malformed` rejection, unconditionally.

**After:** two-tier threshold:

| Document type | Rejection condition |
|---|---|
| All non-Marker or short (<5000 chars) | URL repeated ≥ 4 times (unchanged) |
| Academic Marker-ready (`body_source="marker"` AND `body_length ≥ 5000`) | URL repeated ≥ 20 times **or** repeated-URL chars > 10% of body |

**Why this is safe:**

- The academic Marker path already passes a strict upstream gate in `ingest_external`
  (`body_source=marker AND body_length ≥ 5000`) before reaching `check_hard_stops`.
  Relaxing the URL count for this path doesn't open the door for pdfplumber, fallback,
  or short bodies.
- Density cap (10%) catches cases where even a long body is dominated by a repeated URL
  — a pathological signal regardless of document length.
- Absolute count cap (20) catches extreme repetition in very long papers (e.g. a URL
  pasted into every paragraph).
- For the operator paper: 4 × ~59 chars / 55,436 chars ≈ 0.4% density → well within
  the 10% limit, count 4 < 20 → PASS.

---

## Files Changed

| File | Change |
|------|--------|
| `packages/research/evaluation/hard_stops.py` | Added `_ACADEMIC_MARKER_MIN_BODY`, `_ACADEMIC_URL_MAX_COUNT`, `_ACADEMIC_URL_MAX_DENSITY` constants; check 4b now applies the two-tier threshold using `doc.metadata.get("body_source")` |
| `tests/test_ris_evaluation.py` | Added 6 tests in `TestHardStops` covering the new and preserved behaviors |

---

## Tests Run and Results

```
pytest tests/test_ris_marker_queue.py tests/test_research_query.py \
       tests/test_ris_claim_extraction.py tests/test_ris_evaluation.py -q
3 failed, 282 passed, 1 skipped
```

**3 pre-existing failures (not caused by this change):**
`test_each_claim_has_required_fields`, `test_notes_json_has_extraction_context`,
`test_class_exists_and_has_expected_interface` — all assert `actor == "heuristic_v1"`;
`EXTRACTOR_ID` is `"heuristic_v2_nofrontmatter"`. Pre-dates this work packet.

**6 new tests added, all passing:**

| Test | What it covers |
|---|---|
| `test_academic_marker_long_body_4x_url_passes` | ~56k char Marker body with URL 4x → PASS (operator case) |
| `test_academic_marker_short_body_4x_url_rejected` | Short (<5000) Marker body with URL 4x → still FAIL |
| `test_academic_marker_extreme_count_rejected` | Long Marker body with URL 20x → FAIL |
| `test_academic_marker_high_density_rejected` | Long Marker body with URL density >10% → FAIL |
| `test_pdfplumber_academic_body_4x_url_rejected` | Long pdfplumber body with URL 4x → still FAIL |
| `test_no_metadata_4x_url_rejected` | No metadata, URL 4x → still FAIL (standard gate unchanged) |

---

## Operator Smoke Result

Queue: `artifacts/research/operator_test_queue_direct` / candidate: `arxiv:2604.24366`.
Marker was NOT re-run; existing body sidecar from prior `warm-process` was used.

**index-done (JSON output):**
```json
{
  "indexed": [
    {
      "candidate_id": "arxiv:2604.24366",
      "doc_id": "a1921b9a387a3aa4cac66970f33b85dfbfcdef761b7d316a344b0581fd53a97c",
      "chunk_count": 25,
      "claims_extracted": 125
    }
  ],
  "skipped_already_indexed": [],
  "skipped_no_body": [],
  "failed": [],
  "total_claims_extracted": 125
}
```

**research-query --question "prediction markets":**
```json
{
  "question": "prediction markets",
  "citations": [
    {
      "title": "The Anatomy of a Decentralized Prediction Market",
      "arxiv_id": "2604.24366",
      "source_url": "https://arxiv.org/abs/2604.24366",
      "best_snippet": "Keywords: Prediction markets, microstructure, limit order book, ...",
      "paper_score": 0.7,
      "body_source": "marker",
      "claim_count": 4
    }
  ],
  "had_fallback": false
}
```

`had_fallback=false` confirms the pipeline is end-to-end: enqueue → warm-process →
index-done → research-query returns citations without rerunning Marker.

---

## Remaining Blockers

1. **Pre-existing actor-string test failures.** `EXTRACTOR_ID` changed from
   `"heuristic_v1"` to `"heuristic_v2_nofrontmatter"` but 3 tests still assert `v1`.
   Fix: update the 3 assertion strings in `tests/test_ris_claim_extraction.py`.
   Left unfixed — pre-dates this work packet.

2. **Windows NTFS ADS path for body sidecar.** On Windows, `candidate_id =
   "arxiv:2604.24366"` causes `bodies/arxiv:2604.24366.body.txt` to be stored as an
   NTFS alternate data stream on `bodies/arxiv` (visible as a 0-byte file). Python
   reads ADS paths correctly on Windows (confirmed: `index-done` reads the body), but
   the sidecar is invisible to normal filesystem tools. A future hardening pass could
   sanitize colons in candidate_ids (e.g. replace `:` with `_`) to avoid ADS reliance.
   Not a blocker for current correctness.

---

## Codex Review Summary

Tier: skip — no execution, kill-switch, risk-manager, or rate-limiter files touched.
Changes are in evaluation quality gate, tests, and docs only.
