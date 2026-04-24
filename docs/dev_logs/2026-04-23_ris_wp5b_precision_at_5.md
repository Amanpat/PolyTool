---
date: 2026-04-23
slug: ris_wp5b_precision_at_5
type: feature
scope: packages/polymarket/rag/eval.py, tools/cli/rag_eval.py, tests/test_rag_eval.py
feature: RIS Phase 2A — WP5-B Precision@5
---

# RIS WP5-B — Precision@5 Metric

## Objective

Add Precision@5 to the retrieval eval harness. WP5-A (query expansion to 31 queries) is
complete. WP5-D (baseline save) cannot be locked until the full metric set exists. WP5-B
fills that gap.

---

## Files Changed and Why

| File | Change | Reason |
|---|---|---|
| `packages/polymarket/rag/eval.py` | Add `_PRECISION_K = 5` constant; add `precision_at_5: float = 0.0` to `CaseResult`; add `mean_precision_at_5: float = 0.0` to `ModeAggregate`; update `_eval_single` to compute and return precision_at_5 (4-tuple); update `_build_aggregate` to average precision; update `run_eval` to unpack 4-tuple; update `write_report` to include P@5 in all tables and per-case detail | Core metric implementation |
| `tools/cli/rag_eval.py` | Add `P@5` column to `_print_mode_table` (both `show_query_count` branches) | Surface metric in CLI output |
| `tests/test_rag_eval.py` | Import `_eval_single`, `_build_aggregate`; add `PrecisionAt5UnitTests` class with 16 tests | Verify correctness at unit and integration level |

---

## Precision@5 Contract

**Definition:** Fraction of the top-5 retrieved results that are relevant to the query.

**Relevance judgment:** A result is relevant if any pattern in `must_include_any` matches it
using the existing `_match_pattern` logic (same contract as recall). This avoids inventing
a separate judgment system.

**Fixed k:** Precision always uses `_PRECISION_K = 5`, independent of the `--k` flag that
controls recall/MRR cutoff. This is intentional: P@5 measures top-of-list precision; recall
measures coverage up to a potentially larger k.

**Denominator:** Always 5 (the standard IR definition). If fewer than 5 results are returned,
the denominator is still 5, penalizing sparse retrievers equally.

**No-expectation case:** When `must_include_any` is empty, precision is 1.0 (trivially met,
consistent with the recall convention).

**Negative-control queries:** By design, negative-control cases have `must_include_any: []`,
so they get precision 1.0. This is intentional — negative controls are evaluated via
`must_exclude_any` scope violations, not precision.

---

## Where the Metric Now Appears

| Surface | Location |
|---|---|
| `CaseResult.precision_at_5` | Per-query precision computed by `_eval_single` |
| `ModeAggregate.mean_precision_at_5` | Per-mode average computed by `_build_aggregate` |
| `report.json` | Serialized via `asdict(report)` — all `ModeAggregate` instances include it |
| `summary.md` per-mode table | P@5 column between MRR@k and Scope Violations |
| `summary.md` per-class table | Same column in each class section |
| `summary.md` per-case detail | `p@5=X.XX` in each case line |
| CLI stdout overall table | P@5 column via `_print_mode_table` |
| CLI stdout per-class table | P@5 column via `_print_mode_table` |

---

## Commands Run and Exact Pass/Fail Counts

```
python -m pytest tests/test_rag_eval.py::PrecisionAt5UnitTests -v --tb=short
```
**Result:** 16 passed, 0 failed

```
python -m pytest tests/test_rag_eval.py -v --tb=short
```
**Result:** 51 passed, 0 failed (35 pre-existing + 16 new)

```
python -m polytool --help
```
**Result:** Exit 0. CLI loads cleanly.

```
python -m pytest tests/ -x -q --tb=short
```
**Result:** 1 failed (pre-existing), 2348 passed, 3 deselected
- Pre-existing failure: `test_ris_claim_extraction.py::TestExtractClaimsFromDocument::test_each_claim_has_required_fields`
  — actor name mismatch (`heuristic_v1` vs `heuristic_v2_nofrontmatter`) from an earlier WP,
  completely unrelated to eval harness.
- No new failures introduced by WP5-B.

---

## WP5-B Acceptance Checklist

- [x] `precision_at_5: float = 0.0` added to `CaseResult`
- [x] `mean_precision_at_5: float = 0.0` added to `ModeAggregate`
- [x] `_PRECISION_K = 5` constant defined (explicit, findable)
- [x] `_eval_single` computes precision using existing `_match_pattern` contract
- [x] `_build_aggregate` averages precision across case_results
- [x] `run_eval` propagates precision_at_5 from `_eval_single` into `CaseResult`
- [x] `write_report` includes P@5 in per-mode summary, per-class summary, and per-case detail
- [x] CLI `_print_mode_table` includes P@5 column in both query-count and no-query-count branches
- [x] `report.json` serializes `mean_precision_at_5` (automatic via `asdict`)
- [x] 16 new targeted tests — all passing
- [x] No existing tests broken (51/51 in test module)
- [x] Full suite passes minus pre-existing unrelated failure
- [x] No baseline save work added (WP5-D scope)
- [x] No query suite edits
- [x] No provider, infra, or workflow changes

---

## Recommendation: What Goes Next

**WP5-D (baseline save) is the correct next work unit.**

Rationale:
- WP5-A (query expansion): complete — 31 queries across 5 classes
- WP5-B (Precision@5): complete — this log
- WP5-C (segmented per-class reporting): already done before WP5-A
- WP5-D (save baseline to `artifacts/research/baseline_metrics.json`): the only remaining
  gap before Phase 2A acceptance

WP5-D scope per the roadmap:
- Add `--save-baseline PATH` flag to `tools/cli/rag_eval.py`
- After `write_report`, write `asdict(report)` (or a subset) to
  `artifacts/research/baseline_metrics.json` with a `frozen_at` timestamp
- Document that the baseline is frozen from the first full 31-query run

The baseline should include P@5 in the artifact — which is now guaranteed since
`mean_precision_at_5` is serialized in `report.json` / `asdict(report)`.

---

## Codex Review Note

Codex review tier: **Skip** — no execution, risk, or financial-logic code changed.
Eval harness is a measurement tool with no live-trading impact.
