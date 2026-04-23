# WP2-J Codex Verification - research-eval CLI truth sync

Date: 2026-04-22
Verifier: Codex
Scope: Read-only verification after Claude Code CLI truth-sync implementation.

## Files inspected

- `tools/cli/research_eval.py`
- `packages/research/evaluation/providers.py`
- `packages/research/evaluation/config.py`
- `packages/research/evaluation/evaluator.py`
- `packages/research/evaluation/artifacts.py`
- `config/ris_eval_config.json`
- `tests/test_ris_wp2j_cli_truth_sync.py`
- `tests/test_ris_wp2b_gemini_provider.py`
- `tests/test_ris_wp2c_deepseek_provider.py`
- `tests/test_ris_phase2_cloud_provider_routing.py`
- `tests/test_ris_phase5_provider_enablement.py`
- `docs/dev_logs/2026-04-23_ris_wp2j_cli_truth_sync.md`

## What matched

- Provider truth is consistent between `research-eval` and the provider factory: `manual` and `ollama` are local, `gemini` and `deepseek` are implemented cloud providers, and `openai` plus `anthropic` are recognized but not implemented.
- `research-eval list-providers` matches `config/ris_eval_config.json`: routing mode is `direct`, primary provider is `gemini`, escalation provider is `deepseek`, and budget caps are `gemini=500`, `deepseek=500`.
- Unimplemented providers are not falsely advertised as working. `openai` is rejected before backend construction, even with `--enable-cloud`.
- Implemented cloud providers are accurately guarded. `deepseek`/`gemini` require explicit cloud opt-in and provider API keys; this environment had neither key set, and the CLI reported that as `needs guard+key`.
- `compare` uses explicit direct-provider mode and reports accurate gate/score deltas for supported local providers. `manual` vs `manual` returns equal REVIEW results and `gate_changed=false`; `manual` vs `ollama` reaches the operator surface and reports `ollama` as fail-closed `scorer_failure` because no local Ollama endpoint was available.
- Offline Gemini and DeepSeek provider tests pass, covering factory routing, credentials, metadata, request shape, response parsing, and error handling without network calls.
- No WP3 or new-provider implementation was found in the inspected WP2-J surfaces. Existing OpenRouter/Groq mentions remain comments/tests around the reusable OpenAI-compatible base and are not registered in `get_provider()` or the CLI.

## Issues

Blocking: none.

Non-blocking:

- The prompt asked to verify `list-providers/status output`. The landed WP2-J implementation has `list-providers` with provider/key/routing/budget status, but no standalone `research-eval status` subcommand. Running `python -B -m polytool research-eval status` exits 1 with `research-eval eval: error: unrecognized arguments: status`. If a separate `status` command was intended, it is absent; if "status" meant the status fields inside `list-providers`, those fields are present and accurate.
- Live cloud scoring was not verified because `GEMINI_API_KEY`, `DEEPSEEK_API_KEY`, and `RIS_ENABLE_CLOUD_PROVIDERS` were not set. Local Ollama live scoring was also not verified because the operator environment did not have an Ollama endpoint responding; the CLI correctly surfaced this as a fail-closed provider scoring failure.
- Operator-surface side effect: `compare`/`eval` call `evaluate_document()`, which defaults budget tracking on. Even local-provider probes can refresh `artifacts/research/budget_tracker.json` despite local providers being uncapped; in this run the file contained `{"date": "2026-04-22", "counts": {}}`. This is not a WP2-J truth-sync blocker, but it is a read-only verification footgun.

## Commands run

```powershell
git status --short
```

Exit 0. Worktree was already dirty from landed RIS work and unrelated Obsidian/doc-log files. Relevant modified/untracked RIS files included `tools/cli/research_eval.py`, `packages/research/evaluation/providers.py`, `packages/research/evaluation/config.py`, `packages/research/evaluation/evaluator.py`, `config/ris_eval_config.json`, and `tests/test_ris_wp2j_cli_truth_sync.py`.

```powershell
git log --oneline -5
```

Exit 0.

```text
a610f18 Hermes Agent containerization
05389a8 docs(quick-260422-ll0): PMXT Deliverable C close-out artifacts
0efd895 fix(ris): remove retriever over-fetch truncation for text_query path; Deliverable C gap1 fix
2d926c6 feat(ris): strip YAML frontmatter in heuristic claim extractor (v2)
5962d46 docs(simtrader): PMXT Deliverable B docs close-out
```

```powershell
python -B -m polytool --help
```

Exit 0. CLI loaded and listed `research-eval` under "Research Intelligence (RIS v1/v2)".

```powershell
python -B -m polytool research-eval list-providers
```

Exit 0. Key output:

```text
Local providers (always enabled):
  manual   - rule-based scorer, no API key required
  ollama   - local LLM via Ollama, no API key required

Cloud providers - implemented (require RIS_ENABLE_CLOUD_PROVIDERS=1):
  gemini   - GeminiFlashProvider  [needs guard+key] (GEMINI_API_KEY not set)
  deepseek - DeepSeekV3Provider   [needs guard+key] (DEEPSEEK_API_KEY not set)

Cloud providers - not yet implemented (roadmap only):
  openai    - recognized but raises error; not yet implemented
  anthropic - recognized but raises error; not yet implemented

Cloud guard: RIS_ENABLE_CLOUD_PROVIDERS = not set
Routing config (from ris_eval_config.json / env vars):
  mode               = direct
  primary_provider   = gemini
  escalation_provider= deepseek

Budget caps (calls/day):
  gemini     = 500
  deepseek   = 500
```

```powershell
python -B -m polytool research-eval compare --provider-a manual --provider-b manual --title "WP2-J Smoke" --body "This analysis covers prediction market microstructure, spread dynamics, inventory risk, and calibration details relevant to a market-making system." --json
```

Exit 0. JSON output reported `gate_a=REVIEW`, `gate_b=REVIEW`, `gate_changed=false`, both totals `12`, both composite scores `3.0`, and empty `dim_diffs`.

```powershell
python -B -m polytool research-eval compare --provider-a openai --provider-b manual --title "WP2-J Smoke" --body "This analysis covers prediction market microstructure and inventory risk."
```

Exit 1.

```text
Error: 'openai' is recognized but not yet implemented.

Implemented providers: manual, ollama (local); gemini, deepseek (cloud).
'openai' is on the roadmap but has no backend yet.
  (failed on --provider-a='openai')
```

```powershell
python -B -m polytool research-eval compare --provider-a gemini --provider-b manual --title "WP2-J Smoke" --body "This analysis covers prediction market microstructure and inventory risk."
```

Exit 1.

```text
Error: cloud provider 'gemini' requires opt-in.

Implemented cloud providers (gemini, deepseek) are not enabled by default.
To enable, either:
  - Set the env var: RIS_ENABLE_CLOUD_PROVIDERS=1
  - Pass the --enable-cloud flag on this command

Local providers (manual, ollama) always work without this flag.
  (failed on --provider-a='gemini')
```

```powershell
python -B -m polytool research-eval status
```

Exit 1.

```text
usage: research-eval eval [-h] [--file PATH] [--title TEXT] [--body TEXT]
                          [--source-type TYPE] [--author TEXT]
                          [--provider NAME] [--enable-cloud] [--json]
                          [--artifacts-dir PATH] [--priority-tier TIER]
research-eval eval: error: unrecognized arguments: status
```

```powershell
python -B -m pytest tests/test_ris_wp2j_cli_truth_sync.py -q --tb=short -p no:cacheprovider
```

Exit 0.

```text
collected 21 items
tests\test_ris_wp2j_cli_truth_sync.py .....................              [100%]
21 passed in 0.17s
```

```powershell
python -B -m pytest tests/test_ris_wp2b_gemini_provider.py tests/test_ris_wp2c_deepseek_provider.py -q --tb=short -p no:cacheprovider
```

Exit 0.

```text
collected 75 items
tests\test_ris_wp2b_gemini_provider.py ................................. [ 44%]
...........                                                              [ 58%]
tests\test_ris_wp2c_deepseek_provider.py ............................... [100%]
75 passed in 0.29s
```

```powershell
Get-Content artifacts/research/budget_tracker.json
```

Exit 0.

```json
{
  "date": "2026-04-22",
  "counts": {}
}
```

## Recommendation

WP2 is complete enough to move to WP3, with no blocking WP2-J issues found. Before treating live cloud scoring as operationally verified, run an operator smoke with `RIS_ENABLE_CLOUD_PROVIDERS=1` plus real `GEMINI_API_KEY` and `DEEPSEEK_API_KEY`; that is an environment readiness check, not a WP2-J implementation blocker. Consider cleaning up the local-provider budget-tracker write in a later polish pass if strict read-only CLI probes matter.
