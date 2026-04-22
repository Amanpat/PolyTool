# Fee Model Overhaul Codex Merge Gate

**Date:** 2026-04-21
**Reviewer:** Codex
**Scope:** Final re-review of Deliverable A after the final cleanup pass.

## Files Reviewed

- `tools/cli/simtrader.py`
- `tests/test_simtrader_shadow.py`
- `tests/test_simtrader_strategy.py`
- `tests/test_simtrader_broker.py`
- `tests/test_simtrader_portfolio.py`
- `packages/polymarket/simtrader/portfolio/ledger.py`
- `packages/polymarket/simtrader/strategy/runner.py`
- `packages/polymarket/simtrader/sweeps/runner.py`
- `docs/dev_logs/2026-04-21_fee-model-overhaul_final-cleanup.md`

## Verdict

**NOT MERGE-READY**

## Remaining Blockers

1. `simtrader run` still prints legacy fee metadata when `--fee-rate-bps` is omitted.
   - File: `tools/cli/simtrader.py`
   - Lines: around `1174-1175`
   - Issue: the CLI prints `default (200)` even though the same path now loads `fee_category` from strategy config and passes it into `StrategyRunParams`. When `fee_category` is present, `PortfolioLedger` ignores the legacy `fee_rate_bps` path and uses category-aware fees instead. The operator-facing stderr line is therefore still misleading.

2. `simtrader sweep` has the same operator-facing contradiction.
   - File: `tools/cli/simtrader.py`
   - Lines: around `1340-1341`
   - Issue: the CLI prints `default (200)` before dispatching a sweep that now carries `fee_category` / `fee_role` into `SweepRunParams`. This leaves a silent legacy trap on a normal operator-facing path.

## Decisions

- `_shadow()` is now directly covered at the CLI surface by `TestShadowCLIPropagation.test_shadow_cli_propagates_fee_category_and_role`.
- The failure-manifest path is now directly covered by `test_failure_manifest_truthfulness`.
- `simtrader trade` is now materially truthful enough for Deliverable A: it emits `fee_rate_bps: null`, `fee_category: null`, `fee_role: null` in the manifest and prints `null (ledger default)` instead of the misleading legacy `default (200)` string.
- Deliverable A should not be called merge-ready while `run` and `sweep` still emit legacy default-fee text that can contradict the actual category-aware fee path.

## Commands Run

```text
git status --short
-> exit 0
-> dirty worktree present, including:
   M packages/polymarket/simtrader/portfolio/fees.py
   M packages/polymarket/simtrader/shadow/runner.py
   M tests/test_simtrader_shadow.py
   M tests/test_simtrader_strategy.py
   M tools/cli/simtrader.py
   ...plus unrelated docs/obsidian changes

git log --oneline -5
-> exit 0
-> 42d9985 docs: add AGENTS.md and CURRENT_DEVELOPMENT.md for workflow refresh
-> 2dc03a7 docs(quick-260415-rdy): complete Loop D feasibility -- add plan artifact and update STATE.md
-> b01c80a docs(quick-260415-rdp): complete Loop B phase 0 feasibility -- add plan artifact and update STATE.md
-> 9f09690 docs(quick-260415-rdy): complete Loop D feasibility plan -- add SUMMARY and update STATE.md
-> fce1935 docs(quick-260415-rdp): update STATE.md -- Loop B feasibility complete

python -m polytool --help
-> exit 0

python -m pytest tests/test_simtrader_shadow.py tests/test_simtrader_strategy.py tests/test_simtrader_broker.py tests/test_simtrader_portfolio.py -q --tb=short
-> exit 0
-> 235 passed in 2.19s

python -m pytest tests/ -x -q --tb=short
-> exit 1
-> 1 failed, 2606 passed, 3 deselected, 19 warnings in 67.30s
-> unrelated first failure:
   tests/test_ris_phase2_cloud_provider_routing.py::test_gemini_provider_success
   AttributeError: packages.research.evaluation.providers has no attribute '_post_json'
```

## Codex Review Summary

- Tier: recommended review
- Blocking issues found: 2
- Blocking issues addressed in cleanup pass and verified closed:
  - direct `_shadow()` CLI propagation coverage
  - failure-manifest truthfulness coverage
  - `simtrader trade` legacy metadata cleanup
- Blocking issues still open:
  - misleading legacy `default (200)` stderr output in `simtrader run`
  - misleading legacy `default (200)` stderr output in `simtrader sweep`

## Push Recommendation

Do **not** push to `main` yet. The cleanup closes the three named blockers, but normal operator-facing `run` and `sweep` paths still print legacy `default (200)` fee text even when the actual execution path is category-aware, which is the same class of truthfulness problem that was just fixed for `trade`. After those two stderr lines are made truthful, rerun the targeted SimTrader suite and decide separately how to handle the currently unrelated RIS full-suite failure before pushing.
