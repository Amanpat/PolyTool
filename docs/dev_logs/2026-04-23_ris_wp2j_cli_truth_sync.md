# WP2-J: CLI Truth Sync

**Date:** 2026-04-23
**Track:** RIS Phase 2A
**Work packet:** WP2-J — make `research-eval` CLI surface truthful about the current provider stack
**Codex review:** Skip (CLI formatting + routing only; no execution/risk paths)

## Problem

After WP2-A/B/C (cloud provider implementations) and WP2-H/I (routing + budget), the CLI had three accuracy gaps:

1. **Unimplemented provider UX gap**: `--provider openai --enable-cloud` would pass `_check_provider_guard` (env var set), then fail inside the backend with a generic `ValueError` caught as `"Error: evaluation failed: Cloud provider 'openai' is recognized but not yet implemented."` — the error surfaced too late and too generically.

2. **`list-providers` missing routing state**: Output listed provider names but gave no indication of current routing mode, primary provider, escalation provider, or budget caps — operator couldn't tell what mode they were in without reading the config file directly.

3. **Missing `compare` subcommand**: No CLI path to run the same document through two providers and see a side-by-side gate/score diff.

## What Changed

### `tools/cli/research_eval.py`

**New constants:**
```python
_IMPLEMENTED_CLOUD_PROVIDERS = frozenset({"gemini", "deepseek"})
_UNIMPLEMENTED_CLOUD_PROVIDERS = frozenset({"openai", "anthropic"})
```

**`_KNOWN_SUBCOMMANDS`**: Added `"compare"`.

**`_check_provider_guard()` — two-stage check:**
- Stage 1: if `provider_name in _UNIMPLEMENTED_CLOUD_PROVIDERS` → immediate `rc=1` with clear "recognized but not yet implemented" message, regardless of cloud guard state. This intercepts the error before the backend is touched.
- Stage 2: existing cloud guard check (unchanged semantics, updated message to say "Implemented cloud providers (gemini, deepseek)" instead of listing all four).

**`_cmd_list_providers()` — expanded output:**
- Separate sections: Local / Cloud implemented / Cloud not-yet-implemented
- Per-provider key status (GEMINI_API_KEY, DEEPSEEK_API_KEY) and readiness summary (READY / needs key / needs guard+key)
- Routing config block: mode, primary_provider, escalation_provider (read live from `get_eval_config()`)
- Budget caps block: per-provider daily call limits from config

**`_cmd_compare()` — new subcommand:**
- Args: `--provider-a`, `--provider-b`, `--file`/`--title`/`--body`, `--enable-cloud`, `--json`, `--artifacts-dir`
- Both providers run in direct mode (routing config bypassed — explicit provider_name forces direct)
- Guard checks both slots before any evaluation begins; unimplemented providers blocked at stage 1
- Text output: two labeled result lines + gate-changed indicator + per-dimension diffs
- JSON output: `provider_a`, `provider_b`, `gate_a`, `gate_b`, `gate_changed`, `scores_a`, `scores_b`, `dim_diffs`

**Module docstring and `_print_top_help()`**: Updated to mention `compare` subcommand.

**`main()` dispatch**: Routes `"compare"` → `_cmd_compare`.

## Tests

New file: `tests/test_ris_wp2j_cli_truth_sync.py` — 21 tests

| Test | What it proves |
|---|---|
| `test_list_providers_shows_implemented_cloud` | gemini + deepseek present in output |
| `test_list_providers_shows_unimplemented_cloud` | openai + anthropic present, marked "not yet implemented" |
| `test_list_providers_separates_local_and_cloud` | local section before cloud section |
| `test_list_providers_shows_routing_config` | routing mode/primary present in output |
| `test_list_providers_cloud_guard_status_not_set` | "not set" shown when env var absent |
| `test_list_providers_cloud_guard_status_set` | "SET" shown when env var present |
| `test_provider_openai_blocked_without_cloud_guard` | openai without guard → rc=1, "not yet implemented" |
| `test_provider_anthropic_blocked_without_cloud_guard` | anthropic without guard → rc=1, "not yet implemented" |
| `test_provider_openai_blocked_even_with_cloud_guard` | openai WITH guard → still rc=1, "not yet implemented" |
| `test_provider_anthropic_blocked_even_with_cloud_guard` | anthropic WITH guard → still rc=1, "not yet implemented" |
| `test_provider_gemini_blocked_without_cloud_guard` | gemini without guard → rc=1, cloud guard msg (not "not yet implemented") |
| `test_provider_deepseek_blocked_without_cloud_guard` | deepseek without guard → rc=1, cloud guard msg |
| `test_compare_both_manual_succeeds` | compare manual+manual → rc=0, gate output present |
| `test_compare_gate_changed_field_present` | compare output always has gate-changed indicator |
| `test_compare_json_output_structure` | compare --json → valid JSON with all required keys |
| `test_compare_json_gate_changed_bool` | gate_changed is bool; same provider → False |
| `test_compare_openai_in_slot_a_blocked` | --provider-a openai → rc=1, "not yet implemented" |
| `test_compare_anthropic_in_slot_b_blocked` | --provider-b anthropic → rc=1, "not yet implemented" |
| `test_compare_unimplemented_blocked_even_with_cloud_guard` | unimplemented + cloud guard still blocked |
| `test_compare_gemini_without_guard_blocked` | --provider-a gemini without guard → rc=1, cloud guard msg |
| `test_compare_no_args_shows_help` | no-arg compare → rc=1 |

## Commands Run

```
python -m pytest tests/test_ris_wp2j_cli_truth_sync.py -v --tb=short
Exit 0
21 passed in 0.19s
```

```
python -m pytest tests/ -x -q --tb=short
Exit 0 (stop-on-first-failure mode)
2332 passed, 1 pre-existing failure (test_ris_claim_extraction.py::test_each_claim_has_required_fields — unchanged)
```

```
python -m polytool --help
Exit 0
CLI loaded without import errors.
```

## WP2-J Status

COMPLETE. All three gaps from the problem statement are resolved:

1. ~~Unimplemented provider UX gap~~ — Fixed: `_check_provider_guard` now intercepts `openai`/`anthropic` at stage 1 with a clear "recognized but not yet implemented" message before any backend call.
2. ~~`list-providers` missing routing state~~ — Fixed: output now shows local/implemented/unimplemented sections, per-provider key status and readiness, routing config (mode/primary/escalation), and budget caps.
3. ~~Missing `compare` subcommand~~ — Fixed: `compare` added with `--provider-a`/`--provider-b`, direct-mode semantics, text and JSON output, and full guard coverage for both slots.
