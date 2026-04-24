---
date: 2026-04-23
slug: ris_wp5b_fix_codex_verification
type: verification
scope: packages/polymarket/rag/eval.py, tools/cli/rag_eval.py, tests/test_rag_eval.py
feature: RIS Phase 2A - WP5-B fix Codex verification
---

# RIS WP5-B Fix Codex Verification

## Objective

Read-only verify that the WP5-B fix pass now:

- uses a true top-5 retrieval window for Precision@5 even when `k < 5`
- keeps Recall@k and MRR@k bound to the operator-selected `k`
- still surfaces P@5 in CLI/report output
- does not pull in WP5-D baseline-save work or unrelated scope

## Files Inspected

- `packages/polymarket/rag/eval.py`
  - `_PRECISION_K = 5` at line 34
  - Recall/MRR and scope still slice `top_k = results[:k]` at line 189
  - Precision uses `top_p = results[:_PRECISION_K]` at line 222
  - `run_eval` now fetches `fetch_k = max(k, _PRECISION_K)` at line 371
  - `run_eval` still evaluates with the original user `k` via `_eval_single(case, results, k)` at line 407
  - Markdown/report output includes `P@5` and per-case `p@5=` at lines 533, 564, and 614
- `tools/cli/rag_eval.py`
  - `_print_mode_table` includes `P@5` headers and values at lines 79, 88, 91, 104, and 115
- `tests/test_rag_eval.py`
  - `FetchDepthTests` starts at line 901
  - explicit `k < 5` fetch-depth and metric-split coverage at lines 917, 942, and 962
  - CLI table P@5 coverage at line 1233
- `packages/polymarket/rag/query.py`
  - not touched by the current diff
- `docs/dev_logs/2026-04-23_ris_wp5b_precision_at_5_fix_pass.md`
  - inspected for stated contract and claimed scope

## Verification Result

Pass.

- Retrieval depth is sufficient for true P@5 when `k < 5`: `run_eval` fetches `max(k, 5)` before metric calculation.
- Recall@k and MRR@k still respect the user-selected `k`: `_eval_single` continues to compute on `results[:k]`.
- CLI and report surfaces still include P@5: both markdown report output and `_print_mode_table` print the column/value.
- No WP5-D scope was pulled in: no `baseline`, `save-baseline`, `save_baseline`, or `frozen_at` hits were present in `packages/polymarket/rag/eval.py`, `tools/cli/rag_eval.py`, or `tests/test_rag_eval.py`, and `packages/polymarket/rag/query.py` was not modified.

## Commands Run + Exact Results

```text
python -m polytool --help
```
Result: exit 0. CLI loaded successfully.

```text
python -m pytest tests/test_rag_eval.py::FetchDepthTests::test_k_less_than_5_precision_uses_full_top5 -q --tb=short
```
Result: 1 passed, 0 failed

```text
python -m pytest tests/test_rag_eval.py::FetchDepthTests tests/test_rag_eval.py::PrecisionAt5UnitTests -q --tb=short
```
Result: 22 passed, 0 failed

```text
python -m pytest tests/test_rag_eval.py -q --tb=short
```
Result: 57 passed, 0 failed

## Blocking Issues

None.

## Non-Blocking Issues

None in WP5-B scope.

Repository note: the worktree contains unrelated in-progress changes outside this verification task. This verification stayed read-only against those edits and did not modify any non-log file.

## Recommendation

WP5-D is now the next correct work unit.

Reason:

- the fetch-depth contract for P@5 is now correct for `k < 5`
- Recall@k and MRR@k still honor user `k`
- P@5 remains surfaced in both report and CLI output
- no baseline-save plumbing or unrelated eval expansion was included in this fix pass

No remaining blocker was found for WP5-B within the inspected scope.
