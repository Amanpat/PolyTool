---
date: 2026-04-22
work_packet: WP2-C
phase: RIS Phase 2C
slug: ris_wp2c_codex_verification
---

# WP2-C Read-Only Verification

## Scope

Read-only verification of the landed WP2-C DeepSeek provider work. No code, config,
workflow, infra, or repo-state changes were made during this session. The only file
created is this verification log under `docs/dev_logs/`.

## Files Inspected

- `packages/research/evaluation/providers.py`
- `tests/test_ris_wp2c_deepseek_provider.py`
- `tests/test_ris_wp2a_openai_compatible_base.py`
- `packages/research/evaluation/evaluator.py`
- `packages/research/evaluation/artifacts.py`
- `packages/research/evaluation/replay.py`
- `tools/cli/research_eval.py`
- `tests/test_ris_phase5_provider_enablement.py`
- `tests/test_ris_phase2_cloud_provider_routing.py` (adjacent legacy/routing surface inspected for scope only; not part of the target run)

## What Matched

- `DeepSeekV3Provider` in `packages/research/evaluation/providers.py` is a thin
  subclass of `OpenAICompatibleProvider`.
  - It only resolves credentials/defaults and then calls `super().__init__(...)`.
  - HTTP request construction, retry/backoff, JSON extraction, and score validation
    remain in the shared base.
- Expected DeepSeek defaults are present:
  - provider name: `deepseek`
  - env key: `DEEPSEEK_API_KEY`
  - base URL: `https://api.deepseek.com/v1`
  - default model: `deepseek-chat`
  - default `max_retries=3`
  - default `timeout=60`
- `get_provider()` now wires `"deepseek"` correctly behind the existing
  `RIS_ENABLE_CLOUD_PROVIDERS=1` guard and still leaves `gemini`, `openai`, and
  `anthropic` recognized-but-unimplemented.
- Existing local-provider behavior still holds in the inspected and tested surface:
  - `manual` still constructs without cloud enablement
  - `ollama` still constructs without cloud enablement
  - `get_provider_metadata()` still returns the expected metadata shape for local
    providers and now also covers OpenAI-compatible subclasses via duck typing
- No provider routing, provider fallback chains, or budget logic was introduced in
  the touched evaluator/provider path.
  - `DocumentEvaluator.evaluate()` still executes a single provider path.
  - `evaluate_document()` still does one `get_provider(provider_name, **kwargs)` call.
  - No routing config, fallback provider selection, or budget enforcement was added
    to `providers.py`, `evaluator.py`, or the targeted WP2-C tests.

## Findings

### Blocking

- None.

### Non-blocking

- `research-eval list-providers` still reports DeepSeek as "not yet implemented"
  even though `get_provider("deepseek")` is now wired and the WP2-C tests pass.
  The stale operator-facing string lives in `tools/cli/research_eval.py` and was
  reproduced from the CLI during verification. This does not block provider
  construction or the target tests, but it does leave the CLI status surface out of
  sync with the landed implementation.

## Commands Run

### Session hygiene

Command:
```powershell
git status --short
```

Result:
```text
 M config/ris_eval_config.json
 M docs/CURRENT_DEVELOPMENT.md
 M docs/obsidian-vault/.obsidian/graph.json
 M docs/obsidian-vault/.obsidian/workspace.json
 M docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
 M packages/research/evaluation/artifacts.py
 M packages/research/evaluation/config.py
 M packages/research/evaluation/evaluator.py
 M packages/research/evaluation/providers.py
 M packages/research/evaluation/replay.py
 M packages/research/evaluation/scoring.py
 M packages/research/metrics.py
 M tests/test_ris_evaluation.py
 M tests/test_ris_phase2_weighted_gate.py
 M tests/test_ris_phase5_provider_enablement.py
 M tools/cli/research_eval.py
?? docs/dev_logs/2026-04-22_ris_phase2a_activation_override.md
?? docs/dev_logs/2026-04-22_ris_wp1_context_fetch.md
?? docs/dev_logs/2026-04-22_ris_wp1a_scoring_weights.md
?? docs/dev_logs/2026-04-22_ris_wp1b_codex_verification.md
?? docs/dev_logs/2026-04-22_ris_wp1b_dimension_floors.md
?? docs/dev_logs/2026-04-22_ris_wp1b_prompt_drift_codex_verification.md
?? docs/dev_logs/2026-04-22_ris_wp1b_prompt_floor_drift_fix.md
?? docs/dev_logs/2026-04-22_ris_wp1c_provider_events_contract.md
?? docs/dev_logs/2026-04-22_ris_wp1d_codex_verification.md
?? docs/dev_logs/2026-04-22_ris_wp1d_foundational_seed.md
?? docs/dev_logs/2026-04-22_ris_wp2a_codex_verification.md
?? docs/dev_logs/2026-04-22_ris_wp2a_openai_compatible_base.md
?? docs/dev_logs/2026-04-22_ris_wp2c_deepseek_provider.md
?? docs/obsidian-vault/.smart-env/multi/Claude_Desktop_08-Research_10-Roadmap-v6_0-Master-Draft_md.ajson
?? docs/obsidian-vault/.smart-env/multi/Claude_Desktop_09-Decisions_Decision_-_Roadmap_v6_0_Slim_Master_Restructure_md.ajson
?? "docs/obsidian-vault/Claude Desktop/08-Research/10-Roadmap-v6.0-Master-Draft.md"
?? "docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Roadmap v6.0 Slim Master Restructure.md"
?? tests/test_ris_wp1a_scoring_weights.py
?? tests/test_ris_wp1b_dimension_floors.py
?? tests/test_ris_wp1b_prompt_floor_drift.py
?? tests/test_ris_wp2a_openai_compatible_base.py
?? tests/test_ris_wp2c_deepseek_provider.py
```

Command:
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

### Verification

Command:
```powershell
python -m polytool --help
```

Result:
```text
Exit code 0. CLI help rendered successfully and included the RIS command surface,
including `research-eval`.
```

Command:
```powershell
python -m pytest -q tests/test_ris_wp2a_openai_compatible_base.py tests/test_ris_wp2c_deepseek_provider.py --tb=short
```

Result:
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 72 items

tests\test_ris_wp2a_openai_compatible_base.py .......................... [ 36%]
...............                                                          [ 56%]
tests\test_ris_wp2c_deepseek_provider.py ............................... [100%]

============================= 72 passed in 4.35s ==============================
```

Command:
```powershell
python -m polytool research-eval list-providers
```

Result:
```text
Available providers:
  manual   [local]  — always enabled (no env var needed)
  ollama   [local]  — always enabled (no env var needed)
  gemini   [cloud]  — requires RIS_ENABLE_CLOUD_PROVIDERS=1 (not yet implemented)
  deepseek [cloud]  — requires RIS_ENABLE_CLOUD_PROVIDERS=1 (not yet implemented)
  openai   [cloud]  — requires RIS_ENABLE_CLOUD_PROVIDERS=1 (not yet implemented)
  anthropic [cloud] — requires RIS_ENABLE_CLOUD_PROVIDERS=1 (not yet implemented)

Cloud guard env var: RIS_ENABLE_CLOUD_PROVIDERS = not set
  To enable cloud providers: export RIS_ENABLE_CLOUD_PROVIDERS=1
  Or pass --enable-cloud on individual commands.
```

## Recommendation

Implement `Groq` next if the goal is to preserve the same thin-subclass pattern with
minimal scope risk. It is another OpenAI-compatible provider and is less likely than
an OpenRouter-style marketplace integration to drag in routing, fallback, or budget
policy. Keep the next step limited to:

- provider-specific env var loading
- provider-specific base URL and default model
- `get_provider()` factory wiring
- targeted provider tests

Do not combine the next provider step with multi-provider orchestration or routing
policy.

## Codex Review

Tier: Recommended review file. Verification focused on correctness, provider
contract preservation, and scope control only.
