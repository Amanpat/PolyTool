# Dev Log: RIS Phase 2 Cloud Provider Routing

**Date:** 2026-04-08  
**Task:** Implement RIS Phase 2 Gemini/DeepSeek provider clients and routed evaluation fallback behavior

## Files changed and why

| File | Why |
|---|---|
| `config/ris_eval_config.json` | Added canonical routing defaults (`gemini -> deepseek -> ollama`) plus provider runtime defaults. |
| `packages/research/evaluation/config.py` | Extended config loading to cover routing and provider settings with env-var overrides. |
| `packages/research/evaluation/providers.py` | Implemented real Gemini and DeepSeek HTTP clients, tightened Ollama error handling, and preserved the existing cloud guard. |
| `packages/research/evaluation/scoring.py` | Added strict JSON/schema validation so malformed or incomplete provider output fails closed. |
| `packages/research/evaluation/types.py` | Added `eval_provider` to scoring results and `routing` to gate decisions. |
| `packages/research/evaluation/artifacts.py` | Added replay-grade provider attempt traces and routing decision metadata. |
| `packages/research/evaluation/evaluator.py` | Implemented deterministic primary/escalation/fallback routing with fail-closed behavior on invalid output and unavailable providers. |
| `tools/cli/research_eval.py` | Surfaced routing/provider metadata in CLI output and updated provider listing/help text. |
| `tests/test_ris_evaluation.py` | Updated parser expectations for strict validation. |
| `tests/test_ris_phase2_weighted_gate.py` | Updated fail-closed parsing tests for missing required fields. |
| `tests/test_ris_phase5_provider_enablement.py` | Updated provider enablement tests now that Gemini is implemented. |
| `tests/test_ris_phase2_cloud_provider_routing.py` | Added focused coverage for Gemini success, DeepSeek success, routing order, timeout/unavailable behavior, malformed JSON fail-closed behavior, config/env loading, and CLI smoke paths. |

## Commands run + output

```powershell
python -m pytest tests/test_ris_evaluation.py tests/test_ris_phase2_weighted_gate.py tests/test_ris_phase5_provider_enablement.py tests/test_ris_phase2_cloud_provider_routing.py -q
```

Output summary:

- `120 passed in 2.44s`

```powershell
python -m pytest tests/test_ris_phase3_features.py tests/test_ris_ingestion_integration.py -q
```

Output summary:

- `59 passed in 3.62s`

```powershell
python -m polytool research-eval eval --title "Manual Smoke" --body "This manual smoke document covers prediction market microstructure, spread setting, inventory risk, and calibration details for a market making system." --json
```

Output summary:

- `gate=REVIEW`
- `eval_provider=manual`
- `routing.mode=direct`

```powershell
@'
import json
import os
from packages.research.evaluation import providers
from tools.cli.research_eval import main

os.environ['RIS_ENABLE_CLOUD_PROVIDERS'] = '1'
os.environ['GEMINI_API_KEY'] = 'smoke-key'

def build_payload():
    return json.dumps({
        'relevance': {'score': 4, 'rationale': 'Relevant.'},
        'novelty': {'score': 4, 'rationale': 'Novel.'},
        'actionability': {'score': 4, 'rationale': 'Actionable.'},
        'credibility': {'score': 4, 'rationale': 'Credible.'},
        'total': 16,
        'epistemic_type': 'EMPIRICAL',
        'summary': 'Mocked cloud smoke response.',
        'key_findings': ['Finding A'],
        'eval_model': 'gemini-2.5-flash',
    })

def fake_post_json(endpoint, payload, headers, timeout_seconds):
    return {'candidates': [{'content': {'parts': [{'text': build_payload()}]}}]}

providers._post_json = fake_post_json
raise SystemExit(main([
    'eval', '--provider', 'gemini', '--enable-cloud', '--title', 'Gemini Smoke',
    '--body', 'This mocked cloud smoke document covers prediction market microstructure, spread setting, inventory risk, and calibration details for a market making system.',
    '--json'
]))
'@ | python -
```

Output summary:

- `gate=ACCEPT`
- `eval_provider=gemini`
- `routing.final_reason=primary_success`

## Test results

- Focused provider/routing suite: passed
- Evaluation regression slice (`phase3_features`, `ingestion_integration`): passed
- Manual CLI smoke: passed
- Guarded cloud CLI smoke with offline-safe mocking: passed

## Routing behavior summary

- Primary path is config-driven and defaults to `gemini`.
- If the primary provider returns a valid result with `gate != REVIEW`, that result is final.
- If the primary provider returns a valid `REVIEW`, the evaluator escalates to `deepseek`.
- If a cloud provider is unavailable, rate-limited, or missing credentials, the evaluator can continue down the configured chain.
- `ollama` is only used as the configured fallback path after cloud-provider unavailability/rate-limit style failures.
- Malformed JSON, missing required fields, total mismatches, or other schema-invalid outputs fail closed with `reject_reason="scorer_failure"`.
- Artifacts now record:
  - `provider_event` for the terminal attempt
  - `provider_events` for the full attempt trace
  - `routing_decision` for the final path selection

## Required env vars / setup

Required for cloud routing:

- `RIS_ENABLE_CLOUD_PROVIDERS=1`
- `GEMINI_API_KEY` or `GOOGLE_API_KEY`
- `DEEPSEEK_API_KEY`

Optional runtime overrides:

- `RIS_EVAL_PRIMARY_PROVIDER`
- `RIS_EVAL_ESCALATION_PROVIDER`
- `RIS_EVAL_FALLBACK_PROVIDER`
- `RIS_EVAL_ESCALATE_REVIEW_DECISIONS`
- `RIS_EVAL_FALLBACK_ON_PROVIDER_UNAVAILABLE`
- `RIS_EVAL_GEMINI_*`
- `RIS_EVAL_DEEPSEEK_*`
- `RIS_EVAL_OLLAMA_*`

Fallback setup:

- Local Ollama server reachable at the configured base URL when fallback behavior is desired.

## Open questions for next prompt

1. Should the routed cloud chain become the CLI default once operators have keys configured, or should `manual` remain the default operator path?
2. Should invalid structured output from Gemini/DeepSeek ever be allowed to continue to a later provider, or should the current stricter fail-closed behavior remain policy?
3. Should `research_eval` replay output be extended to diff full `provider_events` / `routing_decision` traces in addition to the terminal `provider_event`?
