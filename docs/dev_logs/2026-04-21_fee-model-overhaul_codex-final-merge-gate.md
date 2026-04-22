# Fee Model Overhaul Codex Final Merge Gate

**Date:** 2026-04-21
**Reviewer:** Codex
**Scope:** Final merge-gate review for Deliverable A after the CLI truthfulness fix.

## Files Reviewed

- `tools/cli/simtrader.py`
- `tests/test_simtrader_strategy.py`
- `docs/dev_logs/2026-04-21_fee-model-overhaul_cli-truthfulness-fix.md`
- `docs/dev_logs/2026-04-21_fee-model-overhaul_codex-merge-gate.md`
- `tests/test_simtrader_shadow.py`
- `tests/test_simtrader_portfolio.py`
- `packages/polymarket/simtrader/strategy/runner.py`
- `packages/polymarket/simtrader/shadow/runner.py`
- `packages/polymarket/simtrader/sweeps/runner.py`
- `packages/polymarket/simtrader/portfolio/ledger.py`

## Files Changed And Why

- `docs/dev_logs/2026-04-21_fee-model-overhaul_codex-final-merge-gate.md`
  - Record the final merge-gate review outcome and push recommendation.

## Verdict

**MERGE-READY**

## Remaining Blockers

- None for Deliverable A.

## Decisions Made

- `simtrader run` now prints a truthful category-aware fee label when `fees.market_category` is present in strategy config.
- `simtrader sweep` now prints the same truthful category-aware label under the same condition.
- No normal operator-facing Deliverable A path reviewed in the live workspace still emits the old `default (200)` CLI label.
- The two new CLI tests are sufficient for the last identified bug surface because they exercise the real CLI entrypoints and assert both the expected `category-aware (...)` text and the absence of the legacy label.
- The unrelated RIS full-suite failure remains a separate repo-health issue and should not be counted as a Deliverable A functional blocker.

## Commands Run

```text
git status --short
-> exit 0
-> dirty worktree present, including feature files under packages/polymarket/simtrader/,
   tests/test_simtrader_strategy.py, tools/cli/simtrader.py, and multiple docs/dev_logs files

git log --oneline -5
-> exit 0
-> 42d9985 docs: add AGENTS.md and CURRENT_DEVELOPMENT.md for workflow refresh
-> 2dc03a7 docs(quick-260415-rdy): complete Loop D feasibility -- add plan artifact and update STATE.md
-> b01c80a docs(quick-260415-rdp): complete Loop B phase 0 feasibility -- add plan artifact and update STATE.md
-> 9f09690 docs(quick-260415-rdy): complete Loop D feasibility plan -- add SUMMARY and update STATE.md
-> fce1935 docs(quick-260415-rdp): update STATE.md -- Loop B feasibility complete

python -m polytool --help
-> exit 0

python -m pytest tests/test_simtrader_strategy.py tests/test_simtrader_shadow.py tests/test_simtrader_portfolio.py -q --tb=short
-> exit 0
-> 200 passed in 2.23s

python -m pytest tests/test_simtrader_strategy.py -q -k "test_cli_run_fee_label_category_aware or test_cli_sweep_fee_label_category_aware" --tb=short
-> exit 0
-> 2 passed, 51 deselected in 0.35s

python -m pytest tests/ -x -q --tb=short
-> exit 1
-> 1 failed, 2606 passed, 3 deselected, 19 warnings in 68.59s
-> unrelated first failure:
   tests/test_ris_phase2_cloud_provider_routing.py::test_gemini_provider_success
   AttributeError: packages.research.evaluation.providers has no attribute '_post_json'
```

## Open Questions Or Blockers

- No open SimTrader blockers remain for Deliverable A.
- Push policy for a known unrelated red full suite remains an operator decision.

## Codex Review Summary

- Tier: skip (CLI/operator-facing truthfulness on a normal path; no execution semantics changed in this final fix)
- Blocking issues found: 0
- Blocking issues addressed and verified closed:
  - truthful `simtrader run` fee label for category-aware execution
  - truthful `simtrader sweep` fee label for category-aware execution

## Push Recommendation

Deliverable A is ready to merge. Push to `main` if the team is willing to treat the RIS full-suite failure as an explicitly acknowledged unrelated red and track it separately; otherwise hold only for repo-wide green policy, not because this SimTrader fee-model feature is still incomplete.
