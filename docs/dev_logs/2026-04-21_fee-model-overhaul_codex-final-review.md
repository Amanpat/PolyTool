# Fee Model Overhaul — Codex Final Review

**Date:** 2026-04-21
**Reviewer:** Codex
**Scope:** Final finish-pass re-review for Deliverable A merge readiness

## Files Reviewed

- `tools/cli/simtrader.py`
- `packages/polymarket/simtrader/shadow/runner.py`
- `packages/polymarket/simtrader/strategy/runner.py`
- `packages/polymarket/simtrader/portfolio/ledger.py`
- `packages/polymarket/simtrader/portfolio/fees.py`
- `packages/polymarket/simtrader/config_loader.py`
- `packages/polymarket/simtrader/strategy/facade.py`
- `packages/polymarket/simtrader/sweeps/runner.py`
- `packages/polymarket/simtrader/studio/ondemand.py`
- `packages/polymarket/simtrader/studio/app.py`
- `tools/gates/mm_sweep.py`
- `tests/test_simtrader_portfolio.py`
- `tests/test_simtrader_strategy.py`
- `tests/test_simtrader_shadow.py`
- `tests/test_simtrader_shadow_probe.py`
- `docs/dev_logs/2026-04-21_fee-model-overhaul_finish-pass.md`

## Verdict

**NOT MERGE-READY**

## Remaining Blockers

1. The finish-pass still does not test the actual `simtrader shadow` CLI regression surface. The original bug lived in `tools/cli/simtrader.py::_shadow()`, but the new tests in `tests/test_simtrader_shadow.py` only instantiate `ShadowRunner` directly. A future regression where `_shadow()` stops calling `load_fee_config()` or stops passing `fee_category` / `fee_role` would still pass.
2. The new run-manifest tests do not cover the failure artifact path even though the patch changed `StrategyRunner._write_failure_artifacts()` in addition to the success writer. A fast-fail run could regress back to misleading portfolio metadata without any test failing.
3. `simtrader trade` is still on the legacy fee path and still writes `"default(200)"` into `run_manifest.json` when no explicit bps is provided. If Deliverable A is supposed to make operator-facing SimTrader runtime metadata uniformly truthful, that path is still not aligned.

## Push-To-Main Recommendation

Do **not** push `main` yet. The code changes for `run` / `shadow` look correct by inspection, and the reviewed test slice passed, but the finish-pass still misses CLI-level proof for the exact shadow regression and still leaves the strategy failure-manifest path untested; on top of that, `simtrader trade` remains legacy and misleading. The cheapest path to green is to add one CLI shadow propagation test, one failure-manifest truthfulness test, and either patch or explicitly scope-exclude `simtrader trade`.

## Commands Run

```text
git status --short
Output: worktree dirty; reviewed against current tree without reverting unrelated changes.

git log --oneline -5
Output:
42d9985 docs: add AGENTS.md and CURRENT_DEVELOPMENT.md for workflow refresh
2dc03a7 docs(quick-260415-rdy): complete Loop D feasibility -- add plan artifact and update STATE.md
b01c80a docs(quick-260415-rdp): complete Loop B phase 0 feasibility -- add plan artifact and update STATE.md
9f09690 docs(quick-260415-rdy): complete Loop D feasibility plan -- add SUMMARY and update STATE.md
fce1935 docs(quick-260415-rdp): update STATE.md -- Loop B feasibility complete

python -m polytool --help
Output: exit 0; CLI help rendered successfully.

pytest -q tests/test_simtrader_portfolio.py tests/test_simtrader_strategy.py tests/test_simtrader_shadow.py tests/test_simtrader_shadow_probe.py --tb=short
Output: 200 passed in 2.03s
```

## Decisions

- Treated this as a code review, not an implementation pass.
- Used code inspection plus targeted offline tests to answer merge-readiness.
- Kept the verdict at NOT MERGE-READY because the previous blocker explicitly required integration-style proof around shadow + manifest truthfulness, and that proof is still incomplete.
