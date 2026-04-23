# RIS WP2-I Codex Verification

Date: 2026-04-23
Scope: read-only verification after WP2-I daily budget enforcement implementation
Status: BLOCKED

## Files inspected

- `config/ris_eval_config.json`
- `packages/research/evaluation/budget.py`
- `packages/research/evaluation/config.py`
- `packages/research/evaluation/evaluator.py`
- `packages/research/evaluation/providers.py`
- `packages/research/evaluation/artifacts.py`
- `packages/research/evaluation/replay.py`
- `packages/research/evaluation/scoring.py`
- `packages/research/metrics.py`
- `tools/cli/research_eval.py`
- `tests/test_ris_phase2_budget_enforcement.py`
- `tests/test_ris_phase2_cloud_provider_routing.py`
- `tests/test_ris_phase5_provider_enablement.py`
- `docs/dev_logs/2026-04-23_ris_wp2i_budget_enforcement.md`

## What matched

- Provider budget helper logic is real when called through `DocumentEvaluator(..., budget_tracker_path=...)`: tracker load/reset, per-provider cap check, increment, and save paths exist in `budget.py` and `_score_with_routing()`.
- `config/ris_eval_config.json` now has `budget.per_provider` caps for `gemini` and `deepseek`, and `config.py` parses them with `RIS_EVAL_BUDGET_<UPPER_NAME>` overrides for configured providers.
- Internal direct mode with an exhausted provider fails closed to `REJECT` with `reject_reason="budget_exhausted"` before calling the provider.
- Internal routed mode handles exhausted primary safely: it records a primary stub, skips the primary call, attempts escalation if available, and fails closed when escalation is also exhausted.
- Tracker update/reset behavior is covered: stale dates reset, successful non-local calls increment, exhausted paths do not increment, `scorer_failure` does not increment, and local `manual`/`ollama` providers remain uncapped.
- WP2-I itself did not add new provider implementations, routing expansion, dashboards, metrics exporters, alerts, or monitoring loops. Existing broad provider/metrics diffs are attributable to earlier uncommitted RIS work packets, not the WP2-I budget files identified in the WP2-I dev log.

## Blocking issues

1. Public evaluation path does not enforce provider budgets.

   Evidence: `DocumentEvaluator` only loads a tracker when `self._budget_tracker_path is not None` (`packages/research/evaluation/evaluator.py:309`). The public `evaluate_document()` wrapper constructs `DocumentEvaluator(...)` with `provider`, `artifacts_dir`, `priority_tier`, and `routing_mode`, but does not pass `budget_tracker_path` (`packages/research/evaluation/evaluator.py:530-536`). The CLI calls `evaluate_document(..., provider_name=args.provider, artifacts_dir=artifacts_dir, ...)` and also has no budget tracker wiring (`tools/cli/research_eval.py:251-254`). Result: the CLI and module-level public API can select cloud providers through routing, but daily provider caps are skipped by default.

2. Tests prove constructor-level enforcement but do not cover public API or CLI enforcement.

   Evidence: `tests/test_ris_phase2_budget_enforcement.py` passes explicit `budget_tracker_path=tracker_path` into `DocumentEvaluator` for enforcement cases and has an explicit backward-compat test that `budget_tracker_path=None` skips budget logic. No test calls `evaluate_document()` or `tools.cli.research_eval` with exhausted provider budget. This leaves the blocking public-path gap untested.

## Non-blocking issues

- None beyond the blocker above. The internal budget behavior, routed degradation, direct fail-closed behavior, and tracker reset/update behavior are substantively covered by the targeted tests.

## Commands run

```text
git status --short
Exit 0
Result: existing dirty worktree from prior RIS/Obsidian work plus untracked dev logs; this verification did not modify code/config/workflows/infra.
```

```text
git log --oneline -5
Exit 0
a610f18 Hermes Agent containerization
05389a8 docs(quick-260422-ll0): PMXT Deliverable C close-out artifacts
0efd895 fix(ris): remove retriever over-fetch truncation for text_query path; Deliverable C gap1 fix
2d926c6 feat(ris): strip YAML frontmatter in heuristic claim extractor (v2)
5962d46 docs(simtrader): PMXT Deliverable B docs close-out
```

```text
python -m polytool --help
Exit 0
Result: CLI loaded and printed top-level PolyTool help, including Research Intelligence commands and research-eval.
```

```text
rg -n "budget|Budget|tracker|route|routed|direct|exhaust|provider" ...
Exit 1
Program 'rg.exe' failed to run: Access is denied
Fallback used: PowerShell Select-String/Get-Content.
```

```text
python -B -m pytest tests/test_ris_phase2_budget_enforcement.py -q -p no:cacheprovider
Exit 0
collected 22 items
tests\test_ris_phase2_budget_enforcement.py ......................       [100%]
22 passed in 0.28s
```

```text
python -B -m pytest tests/test_ris_phase2_cloud_provider_routing.py -q -p no:cacheprovider
Exit 0
collected 11 items
tests\test_ris_phase2_cloud_provider_routing.py ...........              [100%]
11 passed in 0.19s
```

## Recommendation

Do not proceed to the next WP2 work unit until WP2-I wires budget enforcement into the normal public evaluation path. Cheapest next patch: make `evaluate_document()`/CLI supply the default budget tracker path for cloud-provider evaluations while preserving documented local-provider uncapped behavior, then add public-path tests for routed primary exhaustion, direct explicit-provider exhaustion, and tracker increment/reset through `evaluate_document()` or the CLI.
