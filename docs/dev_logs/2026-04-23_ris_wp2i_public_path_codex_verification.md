# WP2-I Public Path Budget Enforcement Verification

Date: 2026-04-23

## Files Inspected

- `packages/research/evaluation/evaluator.py`
- `tools/cli/research_eval.py`
- `packages/research/evaluation/budget.py`
- `packages/research/evaluation/config.py`
- `config/ris_eval_config.json`
- `packages/research/evaluation/providers.py`
- `tests/test_ris_phase2_budget_enforcement.py`
- `tests/test_ris_phase2_cloud_provider_routing.py`
- `tests/test_ris_evaluation.py`

## What Matched

- Public `evaluate_document()` now imports `_DEFAULT_TRACKER_PATH`, defaults `budget_tracker_path` to `artifacts/research/budget_tracker.json`, and passes that path into `DocumentEvaluator`.
- Constructor-only coverage is no longer the only proof: `tests/test_ris_phase2_budget_enforcement.py` now covers explicit public-path exhaustion, public-path under-budget increment, and default public tracker-path enforcement.
- CLI eval path delegates to `evaluate_document()` without overriding `budget_tracker_path`, so the same default public tracker path is used for CLI evaluations.
- Direct mode exhaustion returns `REJECT` with `reject_reason="budget_exhausted"` and does not call the exhausted provider.
- Routed mode exhaustion still behaves correctly: exhausted primary falls through to escalation, both exhausted fails closed, and primary REVIEW plus exhausted escalation fails closed.
- Config/helper surface is bounded to per-provider caps and the local JSON tracker path. No WP3 provider expansion was found in the inspected budget/public-path surfaces.

## Findings

- Blocking: none.
- Non-blocking: there is still no dedicated CLI budget-exhaustion unit test. CLI enforcement is verified by call-chain inspection plus public `evaluate_document()` tests, not by a separate `_cmd_eval` or subprocess budget-exhaustion test.

## Commands Run

```powershell
git status --short
```

Result: exit 0. Worktree was already dirty before verification, including RIS evaluator/CLI/config/test edits, untracked WP2-I budget files, existing dev logs, and unrelated Obsidian files. Codex did not modify code/config/workflows/infra.

```powershell
git log --oneline -5
```

Result:

```text
a610f18 Hermes Agent containerization
05389a8 docs(quick-260422-ll0): PMXT Deliverable C close-out artifacts
0efd895 fix(ris): remove retriever over-fetch truncation for text_query path; Deliverable C gap1 fix
2d926c6 feat(ris): strip YAML frontmatter in heuristic claim extractor (v2)
5962d46 docs(simtrader): PMXT Deliverable B docs close-out
```

```powershell
python -m polytool --help
```

Result: exit 0. PolyTool help loaded successfully and listed `research-eval` under Research Intelligence commands.

```powershell
rg -n "budget|Budget|evaluate_document|tracker|exhaust|routed|direct|provider" packages/research/evaluation tools/cli tests/test_ris_phase2_budget_enforcement.py tests/test_ris_evaluation.py tests/test_ris_phase2_cloud_provider_routing.py
```

Result: failed with `Program 'rg.exe' failed to run: Access is denied`. Verification continued with PowerShell `Select-String`.

```powershell
python -m pytest tests/test_ris_phase2_budget_enforcement.py -q -p no:cacheprovider
```

Result:

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 25 items

tests\test_ris_phase2_budget_enforcement.py .........................    [100%]

============================= 25 passed in 0.28s ==============================
```

## Recommendation

WP2-I public-path enforcement has no remaining blocker. Move past WP2-I. The next work unit should be the next planned RIS item, with an optional small follow-up test if the Architect wants explicit CLI budget-exhaustion coverage in addition to the current public-path tests and CLI call-chain inspection.
