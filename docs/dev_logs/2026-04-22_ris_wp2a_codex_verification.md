---
date: 2026-04-22
work_packet: WP2-A
phase: RIS Phase 2A
slug: ris_wp2a_codex_verification
---

# WP2-A Read-Only Verification

## Scope

Read-only verification of the current WP2-A worktree state after the OpenAI-compatible
base landed. No code, config, workflows, infra, or repo state were modified. The only
new file created is this verification log under `docs/dev_logs/`.

## Files Inspected

- `packages/research/evaluation/providers.py`
- `tests/test_ris_wp2a_openai_compatible_base.py`
- `packages/research/evaluation/evaluator.py`
- `packages/research/evaluation/scoring.py`
- `packages/research/evaluation/artifacts.py`
- `packages/research/evaluation/replay.py`
- `tools/cli/research_eval.py`
- `tests/test_ris_phase5_provider_enablement.py`
- `tests/test_ris_evaluation.py`

## What Matched

- `OpenAICompatibleProvider` now exists in `packages/research/evaluation/providers.py`
  as a reusable base parameterized by `api_key`, `base_url`, `model`, `max_retries`,
  and `timeout`.
- Scope stayed inside evaluation plumbing. The new base handles request construction,
  response parsing, validation, retry/backoff, and provider metadata exposure only.
- Structured response validation is present:
  - outer JSON envelope parse
  - `choices[0].message.content` extraction
  - fenced-code-block JSON fallback
  - required dimension checks for `relevance`, `novelty`, `actionability`, `credibility`
  - numeric normalization
  - 1-5 range enforcement
- Retry and error handling are present:
  - retryable: HTTP 429/502/503, `URLError`, timeout
  - non-retryable: HTTP 400/403 and malformed response structure
  - exhausted retryable failures surface as `ConnectionError`
- No routing, provider fallback, budget enforcement, or multi-provider orchestration
  was added in the WP2-A surface.
- `get_provider()` still only instantiates `manual` and `ollama`. Cloud names remain
  recognized-but-unimplemented behind `RIS_ENABLE_CLOUD_PROVIDERS=1`, so WP2-A did not
  silently wire in new provider selection paths.
- Existing provider contract did not regress in the tested surface:
  - `ManualProvider` behavior still passes
  - `OllamaProvider` behavior still passes
  - `get_provider_metadata()` still returns the expected metadata shape
  - `parse_scoring_response()` still accepts the validated JSON forms emitted by the
    new base

## Findings

### Blocking

- None.

### Non-blocking

- The current worktree also contains separate `provider_event` -> `provider_events`
  contract churn in evaluator, replay, CLI, and related tests. Those changes passed
  the targeted provider-enablement tests and are not routing/budget logic, but they
  are outside the claimed `providers.py`-only WP2-A surface and should stay logically
  separated when landing or reviewing this work packet.

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
?? docs/dev_logs/2026-04-22_ris_wp2a_openai_compatible_base.md
?? docs/obsidian-vault/.smart-env/multi/Claude_Desktop_08-Research_10-Roadmap-v6_0-Master-Draft_md.ajson
?? docs/obsidian-vault/.smart-env/multi/Claude_Desktop_09-Decisions_Decision_-_Roadmap_v6_0_Slim_Master_Restructure_md.ajson
?? "docs/obsidian-vault/Claude Desktop/08-Research/10-Roadmap-v6.0-Master-Draft.md"
?? "docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Roadmap v6.0 Slim Master Restructure.md"
?? tests/test_ris_wp1a_scoring_weights.py
?? tests/test_ris_wp1b_dimension_floors.py
?? tests/test_ris_wp1b_prompt_floor_drift.py
?? tests/test_ris_wp2a_openai_compatible_base.py
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
git diff --unified=0 -- packages/research/evaluation/providers.py
```

Result:
```text
Additions were limited to:
- internal retry exception types
- the new OpenAICompatibleProvider base
- comment/docstring updates for future WP2-C/D/E subclasses
- get_provider_metadata() duck-typing to support future subclasses

No new get_provider() factory wiring to cloud subclasses was introduced.
```

Command:
```powershell
git diff --unified=0 -- packages/research/evaluation/evaluator.py tests/test_ris_evaluation.py tests/test_ris_phase5_provider_enablement.py tools/cli/research_eval.py
```

Result:
```text
Observed separate provider_event -> provider_events contract changes in evaluator,
CLI, and tests. No OpenAICompatibleProvider references were introduced in those files.
```

Command:
```powershell
Select-String -Path 'packages/research/evaluation/providers.py' -Pattern 'route|routing|fallback|budget|orchestrat|multi-provider|multi_provider|chain|router'
```

Result:
```text
No executable routing, budget, or multi-provider logic was found in providers.py.
The only hits were comment-level mentions of future concrete-class routing and the
JSON code-block fallback inside response parsing.
```

Command:
```powershell
pytest -q tests/test_ris_wp2a_openai_compatible_base.py tests/test_ris_phase5_provider_enablement.py --tb=short
```

Result:
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 66 items

tests\test_ris_wp2a_openai_compatible_base.py .......................... [ 39%]
...............                                                          [ 62%]
tests\test_ris_phase5_provider_enablement.py .........................   [100%]

============================= 66 passed in 4.41s ==============================
```

## Recommendation

Implement `DeepSeekProvider` next as the first thin concrete subclass. It is the
lowest-surface follow-on because it can exercise the new base with minimal extra
behavior:

- set provider-specific `base_url`
- set a default model
- load the provider-specific API key env var
- wire the guarded factory path
- add provider-specific tests only

Do not combine that next step with routing, fallback chains, budget enforcement, or
multi-provider orchestration.

## Codex Review

Tier: Recommended review file. Verification focused on correctness, scope control,
and provider contract preservation only.
