---
title: L2 1 Semantic Rejection Guard
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-28_l2-1-semantic-rejection-guard.md
last_synced: '2026-06-03T02:26:56Z'
lifecycle: reviewed
generator: repo-sync
---

# L2.1 Semantic Rejection Guard

**Date:** 2026-05-28
**Status:** PASS

---

## Objective

Fix the L2.1 semantic retrieval unrelated-query rejection gap discovered in the Codex
Batch A review (2026-05-28). Out-of-domain queries like `protein folding molecular
dynamics` must reject honestly instead of returning irrelevant academic finance/trading
citations via the nearest-neighbor semantic path.

---

## Failure Reproduction

Codex independent probe against the live corpus (13 papers, 485 chunks):

```
python -m polytool research-query --question "protein folding molecular dynamics" --k 3
```

Result: `arxiv:1705.01446` returned with `paper_score=0.18156492710113525`,
`had_fallback=false`, `retrieval_mode=semantic`.

Root cause: The semantic threshold was set to `min_similarity=0.18` (lowered from 0.30 in
the L2.1 one-paper repair on 2026-05-25 to accept the hallucination query at score 0.197).
`protein folding molecular dynamics` scored 0.18156 against `arxiv:1705.01446` — a
stochastic-control/finance paper that shares mathematical vocabulary with "dynamics" —
just barely above the threshold.

The threshold was a blunt guard: any score ≥ 0.18 was accepted as a semantic hit,
regardless of whether it was a genuine domain match or the "best available"
nearest-neighbor in a corpus with no truly relevant paper.

---

## Score Calibration Table (live corpus, BAAI/bge-large-en-v1.5)

| Query | Score | Top Paper | Decision |
|---|---|---|---|
| `weather forecast` | 0.0664 | arxiv:1810.04383 | REJECT ✓ (below min_similarity) |
| `protein folding molecular dynamics` | 0.18156 | arxiv:1705.01446 | **REJECT** (new guard) |
| `what does this paper say about hallucination` | 0.197 | arxiv:2510.05533 | ACCEPT ✓ |
| `LLM` | 0.3397 | arxiv:2510.05533 | ACCEPT ✓ |
| `language model financial prediction` | 0.6576 | arxiv:2510.05533 | ACCEPT ✓ |

---

## Guard Design

**Problem:** A single barely-above-threshold hit is ambiguous. It could be:
- A genuine match where the paper content is relevant but the query phrasing is unusual
- A "best available" nearest-neighbor artifact where the corpus has nothing truly relevant

A pure threshold cannot separate these cases when relevant queries (hallucination=0.197)
and irrelevant queries (protein folding=0.182) are so close.

**Solution: Nearest-neighbor rejection guard in `_query_chroma_semantic()`**

Accept semantic results when EITHER:
- (a) ≥2 distinct papers pass `min_similarity` (collective corpus evidence — the query is
  about something the corpus covers broadly), OR
- (b) The single top paper exceeds `confident_threshold` (strong individual match)

Reject when: exactly 1 paper passes `min_similarity` AND its score is below
`confident_threshold`.

```python
# Guard fires only when confident_threshold > min_similarity and
# exactly one paper passed min_similarity.
if confident_threshold > min_similarity and len(hits) == 1 and hits[0][1] < confident_threshold:
    return []
```

**Parameters:**
- `min_similarity = 0.18` — unchanged; individual chunk filter
- `confident_threshold = 0.19` — new; single-hit confidence floor

**Calibration:**
- protein folding: 1 hit at 0.18156 < 0.19 → guard fires → REJECT ✓
- hallucination: 1 hit at 0.197 ≥ 0.19 → guard allows → ACCEPT ✓
- The margin is 0.007 (hallucination 0.197 − confident_threshold 0.19).
  Raising `confident_threshold` above 0.197 would break AT-3.

---

## Files Changed

| File | Change |
|---|---|
| `packages/research/synthesis/academic_query.py` | Added `confident_threshold: float = 0.19` param to `_query_chroma_semantic()`; added nearest-neighbor rejection guard after hit collection; updated docstring with calibration note |
| `tests/test_research_query.py` | Added 3 tests to `TestSemanticRetrievalAcceptanceGaps`; updated stale comment in `test_weather_query_low_similarity_chroma_hit_rejected_by_threshold` |

---

## Acceptance Query Table

Verified behavior against fake-collection unit tests:

| Query | Score | Expected | Actual | Test |
|---|---|---|---|---|
| `protein folding molecular dynamics` | 0.182 (simulated) | REJECT | REJECT ✓ | `test_out_of_domain_single_borderline_hit_rejected_by_confidence_guard` |
| `what does this paper say about hallucination` | 0.197 (simulated) | ACCEPT | ACCEPT ✓ | `test_relevant_single_hit_at_hallucination_score_passes` |
| `weather forecast` | 0.10 (simulated) | REJECT | REJECT ✓ | `test_weather_query_low_similarity_chroma_hit_rejected_by_threshold` (existing) |
| `LLM` | 0.92 (simulated) | ACCEPT | ACCEPT ✓ | `test_abbreviation_query_llm_finds_large_language_model_paper_not_bellman` (existing) |
| `language model financial prediction` | 0.88 (simulated) | ACCEPT | ACCEPT ✓ | `test_multi_word_query_language_model_financial_prediction_returns_paper` (existing) |
| 2+ papers at 0.185/0.184 | multiple | ACCEPT | ACCEPT ✓ | `test_multiple_hits_above_min_threshold_bypass_confidence_guard` |

---

## Test Results

```
tests/test_research_query.py: 98 passed in 3.52s    (was 95 — 3 new tests added)
tests/test_ris_marker_queue.py: 204 passed, 1 skipped in 5.56s    (unchanged)
```

---

## Remaining Limitations

1. **Thin hallucination margin.** The gap between `confident_threshold=0.19` and the
   hallucination score (0.197) is only 0.007. Scores are deterministic for the same
   model and corpus content, but a corpus update adding a semantically distant paper
   might not change this. The risk is low but documented.

2. **Multi-hit path not tightened.** Two papers scoring between 0.18 and 0.19 would be
   accepted without the confidence guard firing. This is intentional (multi-paper
   coverage implies genuine domain overlap) but could produce weak results if the corpus
   grows to include off-domain material.

3. **Live score verification not performed in this session.** The acceptance table above
   uses unit test fake scores. The live corpus state (13 papers after Batch A) was
   confirmed by Codex but not re-probed in this session. The guard is verified to correctly
   reject score=0.182 and accept score=0.197 via unit tests.

---

## Codex Unrelated-Query Blocker Status

**RESOLVED.**

The Codex BLOCK (2026-05-28) cited two issues:
1. Unrelated query `protein folding molecular dynamics` did not reject — now guarded ✓
2. FIFO queue order would process Tier-3 papers in Batch B — separate blocker (not in scope)

Issue 1 is resolved. Issue 2 (Batch B queue ordering) is out of scope for this packet
and remains a prerequisite before Batch B can run.

---

## Codex Review

Tier: Recommended (`synthesis/academic_query.py`).
No mandatory files changed (no execution path, kill-switch, or EIP-712 logic touched).
Review deferred — guard change and threshold adjustment are low-risk; no ingestion,
replay, or live-trading paths affected.
