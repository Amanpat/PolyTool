---
date: 2026-04-23
slug: ris_wp5b_precision_at_5_fix_pass
type: fix
scope: packages/polymarket/rag/eval.py, tests/test_rag_eval.py
feature: RIS Phase 2A — WP5-B Precision@5 fix pass (under-fetch contract bug)
---

# RIS WP5-B Fix Pass — Precision@5 Under-Fetch Contract Bug

## Objective

Fix the Codex-identified blocker: Precision@5 was defined as independent of `--k`, but
`run_eval` still retrieved only `k` results from `query_index`. With `--k < 5`, the top-5
window was silently truncated to `k` items, making P@5 invalid.

---

## Root Cause

In `packages/polymarket/rag/eval.py`, `run_eval` passed the user-supplied `k` directly to
`query_index`:

```python
results = query_index(
    ...
    k=k,   # ← always user k, never padded for P@5
    ...
)
```

`query_index` (and the underlying retrieval engine) then returned at most `k` results. When
`k=3`, only 3 results came back. `_eval_single` then computed precision from
`results[:_PRECISION_K]` (i.e., `results[:5]`), but with only 3 items in `results` the
slice contained at most 3 — making the "fixed k=5" claim false.

The `_eval_single` logic itself was correct; the bug was in the upstream fetch depth.

---

## Fix

**One line change in `packages/polymarket/rag/eval.py` inside `run_eval`:**

```python
# Before
results = query_index(..., k=k, ...)

# After
fetch_k = max(k, _PRECISION_K)   # ensure top-5 window is always available
results = query_index(..., k=fetch_k, ...)
```

`_eval_single` already sliced correctly:
- `top_k = results[:k]` → recall@k and MRR@k use the user-selected cutoff
- `top_p = results[:_PRECISION_K]` → precision@5 uses the fixed 5-item window

After the fix, `results` always has at least `_PRECISION_K=5` items (or as many as the
index contains), so both slices are valid regardless of `--k`.

No changes were needed to `query.py` — `query_index` already returns exactly the `k`
it is given; the fix only changes what `k` it is given.

---

## Files Changed and Why

| File | Change | Reason |
|---|---|---|
| `packages/polymarket/rag/eval.py` | `k=k` → `fetch_k = max(k, _PRECISION_K); k=fetch_k` in `query_index` call | Fix under-fetch so P@5 always sees a true top-5 window |
| `tests/test_rag_eval.py` | Add `FetchDepthTests` class with 6 tests | Cover the edge that the original WP5-B tests missed: k<5 behavior |

---

## Final Metric/Fetch Contract

| Metric | Fetch depth | Slice used |
|---|---|---|
| Recall@k | `max(k, 5)` fetched | `results[:k]` |
| MRR@k | `max(k, 5)` fetched | `results[:k]` |
| Precision@5 | `max(k, 5)` fetched | `results[:5]` |
| Scope violations | `max(k, 5)` fetched | `results[:k]` |

`k` is the operator-supplied `--k`. The extra fetch is invisible to the operator: reported
metrics, table headers, and `result_count` all remain consistent with the operator's intent.

Note: `result_count` in `CaseResult` reflects the actual fetch depth (`len(results)`), which
may now be 5 when the operator passed `--k 3`. This is more informative than the old value
(which was always k) and is not a breaking change.

---

## Commands Run and Exact Pass/Fail Counts

```
python -m pytest tests/test_rag_eval.py::FetchDepthTests -v --tb=short
```
**Result:** 6 passed, 0 failed

```
python -m pytest tests/test_rag_eval.py -q --tb=short
```
**Result:** 57 passed, 0 failed (51 pre-existing + 6 new)

```
python -m polytool --help
```
**Result:** Exit 0. CLI loads cleanly.

```
python -m pytest tests/ -x -q --tb=short
```
**Result:** 1 failed (pre-existing), 2354 passed, 3 deselected
- Pre-existing failure: `test_ris_claim_extraction.py::TestExtractClaimsFromDocument::test_each_claim_has_required_fields`
  — actor name mismatch from an earlier WP, unrelated to eval harness.
- No new failures introduced.
- 6 more tests passing than before this fix pass (was 2348).

---

## Is WP5-B Now Truly Complete?

**Yes.** Both the Codex blocking issues are resolved:

1. ✅ `mean_precision_at_5` wired into `ModeAggregate`, `CaseResult`, report, CLI (WP5-B initial pass)
2. ✅ Fetch depth is now `max(k, _PRECISION_K)` so P@5 is valid for any `--k` (this fix pass)
3. ✅ Tests cover k<5, k=5, k>5 fetch depth; precision correctness for each case

---

## Recommendation: What Goes Next

**WP5-D (baseline save) is now the correct next work unit.**

Scope:
- Add `--save-baseline [PATH]` flag to `tools/cli/rag_eval.py`
- After `write_report`, write `asdict(report)` to `artifacts/research/baseline_metrics.json`
  with a `frozen_at` timestamp
- Document that the baseline is frozen from the first full 31-query run

The baseline will now include the correct P@5 values since the fetch-depth bug is fixed.

---

## Codex Review Note

Codex review tier: **Skip** — no execution, risk, or financial-logic code changed.
One-line fix to eval harness fetch depth; changes are entirely within offline eval tooling.
