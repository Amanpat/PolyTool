# RIS WP2-B Codex Verification

Date: 2026-04-23

## Scope

Read-only verification of the landed WP2-B Gemini provider implementation. Code,
config, workflows, infra, and repo state were not modified. This dev log is the
only file written.

## Files inspected

- `packages/research/evaluation/providers.py`
- `packages/research/evaluation/evaluator.py`
- `packages/research/evaluation/artifacts.py`
- `packages/research/evaluation/replay.py`
- `tools/cli/research_eval.py`
- `tests/test_ris_wp2b_gemini_provider.py`
- `tests/test_ris_phase5_provider_enablement.py`
- `tests/test_ris_wp2c_deepseek_provider.py`

## What matched

- `GeminiFlashProvider` is a real provider, not a stub. It reads
  `GEMINI_API_KEY`, raises `PermissionError` when missing, uses Gemini's native
  `generateContent` REST endpoint, and passes the API key as the Gemini query
  parameter rather than as a Bearer header.
- The structured-output path is present. Requests send
  `generationConfig.responseMimeType = application/json` and
  `generationConfig.responseSchema`, then `_validate_and_extract()` parses the
  Gemini response envelope and calls the shared score post-validation path.
- `get_provider("gemini")` is wired behind the existing
  `RIS_ENABLE_CLOUD_PROVIDERS=1` guard and returns `GeminiFlashProvider` when
  the guard and API key are present.
- Manual and Ollama provider construction paths remain local and do not require
  cloud-provider opt-in. DeepSeek remains wired as `DeepSeekV3Provider` behind
  the cloud guard and `DEEPSEEK_API_KEY`.
- No executable provider router, fallback chain, or budget logic was added.
  The only matches for routing/fallback terms were factory-routing comments,
  existing CLI backward-compat command routing, OpenAI-compatible JSON extraction
  fallback, and artifact legacy-format fallback.

## Issues

Blocking:

- None.

Non-blocking:

- `tests/test_ris_wp2b_gemini_provider.py` verifies endpoint/auth behavior and
  provider metadata, but does not assert the outbound request body contains
  `generationConfig.responseMimeType` and `generationConfig.responseSchema`.
  The implementation currently sends both fields, so this is a coverage gap,
  not an implementation blocker.

## Commands run and exact results

`git status --short`

Result: exit 0. Worktree was dirty before verification, including the landed RIS
provider/evaluator/test changes and prior dev logs. No existing changes were
reverted or overwritten.

`git log --oneline -5`

```text
a610f18 Hermes Agent containerization
05389a8 docs(quick-260422-ll0): PMXT Deliverable C close-out artifacts
0efd895 fix(ris): remove retriever over-fetch truncation for text_query path; Deliverable C gap1 fix
2d926c6 feat(ris): strip YAML frontmatter in heuristic claim extractor (v2)
5962d46 docs(simtrader): PMXT Deliverable B docs close-out
```

`python -m polytool --help`

Result: exit 0. Help loaded and printed the PolyTool command list, including the
RIS commands such as `research-eval`, `research-precheck`, `research-ingest`,
`research-seed`, and provider-related evaluation commands.

`rg -n "Gemini|gemini|get_provider|manual|ollama|deepseek|fallback|budget|routing|route" ...`

Result: failed because `rg.exe` returned `Access is denied`. Verification
continued with PowerShell `Select-String`.

`Select-String -Path 'packages/research/evaluation/*.py','tools/cli/research_eval.py','tests/test_ris_wp2b_gemini_provider.py','tests/test_ris_phase5_provider_enablement.py','tests/test_ris_wp2c_deepseek_provider.py' -Pattern 'fallback|budget|router|routing' -CaseSensitive:$false`

Result: exit 0. Matches were limited to artifact/replay compatibility comments,
provider factory/test comments, OpenAI-compatible JSON extraction fallback, and
CLI backward-compat command routing. No budget logic or executable provider
fallback/router was found.

`python -m pytest -q tests/test_ris_wp2b_gemini_provider.py tests/test_ris_phase5_provider_enablement.py tests/test_ris_wp2c_deepseek_provider.py`

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 100 items

tests\test_ris_wp2b_gemini_provider.py ................................. [ 33%]
...........                                                              [ 44%]
tests\test_ris_phase5_provider_enablement.py .........................   [ 69%]
tests\test_ris_wp2c_deepseek_provider.py ............................... [100%]

============================= 100 passed in 0.44s =============================
```

## Recommendation

Proceed with the next WP2 work unit. If there is another small hardening pass,
add one WP2-B test that decodes the captured Gemini request body and asserts
`responseMimeType` plus `responseSchema` are present under `generationConfig`.
