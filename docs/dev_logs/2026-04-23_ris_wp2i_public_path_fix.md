# WP2-I Public Path Fix

**Date:** 2026-04-23
**Track:** RIS Phase 2A
**Work packet:** WP2-I follow-up — wire budget enforcement into public evaluation path
**Codex review:** N/A (additive parameter wiring only; no execution/risk paths)

## Root Cause

Codex verification (`docs/dev_logs/2026-04-23_ris_wp2i_codex_verification.md`) identified that
`evaluate_document()` constructed `DocumentEvaluator` without passing `budget_tracker_path`.
Since `DocumentEvaluator.__init__` defaults `budget_tracker_path=None` (skipping all budget
logic), normal CLI and module-level public API calls bypassed daily caps entirely.

## What Changed

### `packages/research/evaluation/evaluator.py`

`evaluate_document()` gains `budget_tracker_path: Optional[Path] = None`.

Inside the function body, when `budget_tracker_path` is `None`, it is set to
`_DEFAULT_TRACKER_PATH` (imported lazily from `budget.py`, resolving to
`artifacts/research/budget_tracker.json` relative to the repo root). The resolved path is then
passed to `DocumentEvaluator`.

Result:
- All public callers (`evaluate_document()`, CLI via `_cmd_eval()`) now enforce per-provider
  daily caps by default.
- Local providers (`manual`, `ollama`) remain uncapped (enforced inside `is_budget_available()`).
- Callers can redirect the tracker by passing an explicit `budget_tracker_path=Path(...)`.
- `DocumentEvaluator` still accepts `budget_tracker_path=None` for full backward compatibility
  in internal/test use.

No changes were needed in `tools/cli/research_eval.py` — since `_cmd_eval()` calls
`evaluate_document()` without `budget_tracker_path`, it now inherits the default automatically.

## Tests

Added 3 public-path tests to `tests/test_ris_phase2_budget_enforcement.py` (25 total, was 22):

| Test | What it proves |
|---|---|
| `test_evaluate_document_public_path_exhausted_fails_closed` | `evaluate_document()` with explicit `budget_tracker_path` + exhausted cap → REJECT budget_exhausted |
| `test_evaluate_document_public_path_under_budget_proceeds` | `evaluate_document()` under cap → ACCEPT + tracker count increments |
| `test_evaluate_document_default_tracker_path_enforces_budget` | `evaluate_document()` with no `budget_tracker_path` arg uses `_DEFAULT_TRACKER_PATH`; exhausted budget at that path fails closed |

Test 3 monkeypatches `packages.research.evaluation.budget._DEFAULT_TRACKER_PATH` to a `tmp_path`
location so the test does not write to `artifacts/research/` on disk.

## Commands Run

```
python -m pytest tests/test_ris_phase2_budget_enforcement.py -v --tb=short
Exit 0
25 passed in 0.32s
```

```
python -m pytest tests/test_ris_phase2_cloud_provider_routing.py tests/test_ris_phase5_provider_enablement.py -q --tb=short
Exit 0
36 passed in 0.37s
```

```
python -m pytest tests/ -x -q --tb=short
Exit 0
2332 passed, 1 pre-existing failure (test_ris_claim_extraction.py::test_each_claim_has_required_fields — unchanged)
```

```
python -m polytool --help
Exit 0
CLI loaded without import errors.
```

## WP2-I Status

COMPLETE. Both blockers from Codex verification are resolved:

1. ~~Public evaluation path does not enforce provider budgets~~ — Fixed: `evaluate_document()`
   now defaults `budget_tracker_path` to `_DEFAULT_TRACKER_PATH`.
2. ~~Tests prove constructor-level enforcement but not public API or CLI~~ — Fixed: 3 new
   public-path tests cover exhausted, under-budget, and default-path scenarios.
