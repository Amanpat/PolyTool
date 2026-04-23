# RIS WP2-H Codex Verification

Date: 2026-04-23
Scope: read-only verification after WP2-H routing implementation
Status: BLOCKED

## Files inspected

- `packages/research/evaluation/evaluator.py`
- `packages/research/evaluation/config.py`
- `packages/research/evaluation/artifacts.py`
- `packages/research/evaluation/replay.py`
- `packages/research/evaluation/providers.py`
- `packages/research/evaluation/scoring.py`
- `packages/research/evaluation/types.py`
- `tools/cli/research_eval.py`
- `config/ris_eval_config.json`
- `tests/test_ris_phase2_cloud_provider_routing.py`
- `tests/test_ris_phase5_provider_enablement.py`
- `docs/dev_logs/2026-04-22_ris_wp2h_multi_provider_routing.md`

## What matched

- `DocumentEvaluator` has an explicit `routing_mode="route"` path.
- Route mode escalates only when the primary result gates to `REVIEW`.
- Direct mode remains single-provider by default and does not call escalation.
- Persisted scoring artifacts now use canonical plural `provider_events`.
- Multi-attempt artifacts preserve attempt order: primary first, escalation second.
- Primary provider exceptions fail closed to `REJECT` with `reject_reason="scorer_failure"` and do not escalate.
- Escalation provider `score()` exceptions fail closed to `REJECT` and preserve both provider attempts in `provider_events`.
- Routing config parses JSON and env overrides for `mode`, `primary_provider`, and `escalation_provider`.
- No OpenRouter, Groq, or OllamaCloud provider implementation was added in the inspected WP2-H path. Existing OpenRouter/Groq text remains comments/docstrings only.
- No active budget enforcement logic was added. `config/ris_eval_config.json` still contains a budget placeholder, but `git diff -- config/ris_eval_config.json` shows WP2-H only added the `routing` section there; the budget block was not introduced by this diff.

## Blocking findings

1. Config-driven routing is not wired into normal evaluation entrypoints.

   Evidence: `config.py` loads `cfg.routing.mode` and `cfg.routing.primary_provider`, but `evaluate_document()` still constructs `provider = get_provider(provider_name, **kwargs)` and then `DocumentEvaluator(provider=provider, artifacts_dir=..., priority_tier=...)` without passing `routing_mode` or using `cfg.routing.primary_provider`. `tools/cli/research_eval.py` also calls `evaluate_document(..., provider_name=args.provider, ...)` and has no route-mode flag or config activation path. Result: setting `RIS_EVAL_ROUTING_MODE=route` or changing JSON `"routing": {"mode": "route"}` does not activate Gemini-primary / DeepSeek escalation through the normal module-level API or CLI.

2. Lazy escalation provider construction is not fail-closed.

   Evidence: `_score_with_routing()` calls `_get_escalation_provider()` before `_call_provider_once()`. If the config escalation provider cannot be constructed, for example because `RIS_ENABLE_CLOUD_PROVIDERS` or `DEEPSEEK_API_KEY` is missing, the exception propagates instead of returning a fail-closed `REJECT`. Read-only probe result:

   ```text
   PermissionError: Cloud provider 'deepseek' requires RIS_ENABLE_CLOUD_PROVIDERS=1 to be set. Local providers (manual, ollama) work without this flag.
   ```

## Non-blocking findings

- The targeted WP2-H tests verify constructor-level routing behavior with explicit provider stubs, but they do not cover config-driven activation through `evaluate_document()` or the CLI.
- `provider_events` records ordered attempts, but it does not include route role, selected provider, status, or failure reason fields. This is acceptable for the current WP2-H test contract, but future monitoring/replay consumers should not infer more than attempt order and provider identity from these events.
- The worktree had broad pre-existing RIS and Obsidian changes before verification. I did not modify any of them.

## Commands run

```text
git status --short
Exit 0
Result: pre-existing dirty worktree across RIS config/evaluation/tests/CLI/docs plus untracked dev logs. No code/config files were modified by this verification.
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
Result: CLI loaded and printed top-level PolyTool help, including the Research Intelligence command group and research-eval command.
```

```text
rg -n "Gemini|gemini|DeepSeek|deepseek|provider_events|yellow|escalat|route|routing|single-provider|provider" ...
Exit 1
Program 'rg.exe' failed to run: Access is denied
```

```text
python -m pytest tests/test_ris_phase2_cloud_provider_routing.py -q
Exit 0
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 8 items

tests\test_ris_phase2_cloud_provider_routing.py ........                 [100%]

============================== 8 passed in 0.16s ==============================
```

```text
python -m polytool research-eval eval --title "Direct Smoke" --body "Prediction market microstructure research about inventory risk, spread setting, market making calibration, and replay validation for Polymarket execution." --json
Exit 0
{
  "gate": "REVIEW",
  "doc_id": "cli_3c4338be63f9",
  "timestamp": "2026-04-23T01:09:32+00:00",
  "scores": {
    "relevance": 3,
    "novelty": 3,
    "actionability": 3,
    "credibility": 3,
    "total": 12,
    "epistemic_type": "UNKNOWN",
    "summary": "Manual placeholder \u2014 human review required.",
    "key_findings": [],
    "eval_model": "manual_placeholder",
    "composite_score": 3.0,
    "simple_sum_score": 12,
    "priority_tier": "priority_3",
    "reject_reason": null
  }
}
Using provider: manual
```

```text
Lazy escalation construction probe
Exit 0
PermissionError: Cloud provider 'deepseek' requires RIS_ENABLE_CLOUD_PROVIDERS=1 to be set. Local providers (manual, ollama) work without this flag.
```

## Recommendation

Do not proceed to the next WP2 work unit until WP2-H is corrected with config-driven activation coverage. Cheapest next patch: wire `evaluate_document()` to use `get_eval_config().routing` when no explicit provider is supplied or when route mode is enabled, preserve direct explicit-provider mode, catch escalation provider construction failures as fail-closed scoring failures, and add tests for env/JSON route activation through the normal API or CLI surface.
