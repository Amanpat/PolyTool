# WP2-I: Daily Budget Enforcement

**Date:** 2026-04-23  
**Track:** RIS Phase 2A  
**Work packet:** WP2-I — Daily per-provider call caps  
**Codex review:** N/A (budget logic only; no execution/risk paths)

## What Was Built

Daily per-provider API call caps enforced in the RIS evaluation pipeline. Enforcement is fully opt-in via a new `budget_tracker_path` parameter — existing callers are unaffected (full backward compatibility).

### New file: `packages/research/evaluation/budget.py`

Stateless helpers for loading, checking, incrementing, and saving the daily budget tracker.

- `load_budget_tracker(path)` — loads `budget_tracker.json`; resets counts if the stored date differs from today
- `save_budget_tracker(tracker, path)` — writes tracker to disk, creating parent dirs
- `is_budget_available(provider_name, cap, tracker)` — returns True if provider has remaining budget; local providers (`manual`, `ollama`) always return True regardless of cap
- `increment_provider_count(provider_name, tracker)` — mutates tracker in place; no-op for local providers

### `packages/research/evaluation/config.py` changes

- Added `BudgetConfig` frozen dataclass (`per_provider: dict`)
- Added `budget: BudgetConfig` field to `EvalConfig`
- `load_eval_config()` now parses `budget.per_provider` from JSON
- Env var overrides: `RIS_EVAL_BUDGET_<UPPER_NAME>` (e.g. `RIS_EVAL_BUDGET_GEMINI=42`)
- Defaults: gemini=500, deepseek=500

### `config/ris_eval_config.json`

Added `_comment` and `per_provider` keys to the existing `budget` section.

### `packages/research/evaluation/evaluator.py` changes

`DocumentEvaluator.__init__` gains `budget_tracker_path: Optional[Path] = None`.

`_score_with_routing()` is now budget-aware:
- Tracker loaded once per call from `budget_tracker_path` (None → skip all budget logic)
- **Primary budget check** before any provider call
  - Direct mode exhausted: append stub, return `REJECT budget_exhausted`
  - Route mode exhausted: skip primary stub, attempt escalation immediately
- **Escalation budget check** in both the "primary exhausted → escalate directly" path and the normal "primary REVIEW → escalate" path
- **Increment + save** only after a non-`scorer_failure` result (failed calls don't consume budget)

Three private helpers added:
- `_check_budget(provider_name, tracker, cfg)` — wrapper around `is_budget_available`
- `_increment_and_save(provider_name, tracker)` — increment + persist; no-op when tracker is None
- `_make_budget_exhausted_result(provider_name, cfg)` — returns a fail-closed `ScoringResult` with `reject_reason="budget_exhausted"`

## Tests

New file: `tests/test_ris_phase2_budget_enforcement.py` — 22 tests, all passing.

Coverage:
- `budget_tracker_path=None` → no enforcement, call proceeds (backward compat)
- Under-budget call proceeds and increments tracker count
- Failed call (scorer_failure) does not increment count
- Direct mode primary exhausted → REJECT budget_exhausted, 1 stub event in artifact
- Direct mode primary exhausted does not increment count
- Route mode primary exhausted → escalation succeeds, 2 events (stub + real), escalation count increments
- Route mode both exhausted → REJECT budget_exhausted, 2 stubs, neither count changes
- Route mode primary REVIEW + escalation exhausted → REJECT budget_exhausted, 2 events
- Stale date resets counts (fresh tracker for today)
- `manual` and `ollama` always uncapped
- `budget.py` unit tests: load/save/check/increment edge cases
- `BudgetConfig` JSON parsing and env var overrides

Full suite: 22 budget tests pass, 2332 total pass, 1 pre-existing failure in `test_ris_claim_extraction.py` (unrelated).

## Behavior Summary

| Scenario | Mode | Outcome |
|---|---|---|
| `budget_tracker_path=None` | any | Enforcement skipped (backward compat) |
| Primary under cap | direct | Call proceeds, count +1 |
| Primary exhausted | direct | REJECT `budget_exhausted`, 1 stub event |
| Primary exhausted | route | Skip to escalation; if escalation succeeds → ACCEPT |
| Both exhausted | route | REJECT `budget_exhausted`, 2 stub events |
| Primary REVIEW + esc exhausted | route | REJECT `budget_exhausted`, 2 events |
| Local provider (manual/ollama) | any | Always uncapped |
| Stale tracker date | any | Counts reset, fresh start |
| Scorer failure | any | Does NOT increment budget count |
