# Dev Log: Hypothesis Validation Loop v0 — Packet 1

**Date:** 2026-03-11
**Branch:** phase-1
**Track:** Track B — Research Loop

---

## Summary

Implemented Packet 1 of the Track B Hypothesis Validation Loop milestone.

The hypothesis schema (`hypothesis_schema_v1.json`) existed but nothing enforced
it.  A well-formed `hypothesis.json` and a malformed one were indistinguishable
at save time.  This packet closes that gap: every `llm-save` run that includes
`--hypothesis-path` now produces a `validation_result.json` alongside the saved
report, and a standalone `hypothesis-validate` command supports post-hoc
auditing.

---

## What Was Built

### `packages/polymarket/hypotheses/validator.py` (new)

Hand-rolled validator against `hypothesis_schema_v1.json`.  No third-party
library required (`jsonschema` not added as a dependency).

- `ValidationResult(valid, errors, warnings)` dataclass
- `validate_hypothesis_json(data) -> ValidationResult`
- Rules enforced:
  - Top-level required: `schema_version`, `metadata`, `executive_summary`, `hypotheses`
  - `schema_version` const: must be `"hypothesis_v1"`
  - `metadata` required sub-fields: `user_slug`, `run_id`, `created_at_utc`, `model`
  - `metadata.proxy_wallet`: optional, must match `^0x[a-fA-F0-9]{40}$` if present
  - `metadata.window_days`: optional, must be integer >= 1 if present
  - `executive_summary.bullets`: required, minItems=1, maxItems=10, all strings
  - `executive_summary.overall_assessment`: optional enum (profitable / unprofitable / mixed / insufficient_data)
  - `hypotheses[i]` required: `claim`, `evidence` (minItems=1), `confidence` (high/medium/low), `falsification`
  - `hypotheses[i].evidence[j]`: must have `text` field
  - `hypotheses[i].id`: optional, must match `^H[0-9]+$` if present
- Recommended fields → warnings (not errors): `limitations`, `missing_data_for_backtest`

### `tools/cli/hypotheses.py` (modified)

- Added `handle_hypothesis_validate(args)` handler
- Added `hypothesis-validate` subparser with `--hypothesis-path PATH`
- Prints JSON `{valid, errors, warnings}` to stdout
- Exits 0 on valid, 1 on invalid

### `tools/cli/llm_save.py` (modified)

- Added optional `--hypothesis-path PATH` argument
- If provided:
  1. Reads and saves the file as `hypothesis.json` alongside `report.md`
  2. Validates against schema using `validate_hypothesis_json()`
  3. Writes `validation_result.json` with `{valid, errors, warnings, validated_at_utc, schema}`
  4. On invalid: prints each error to stderr, save still completes (exit 0)
- Print summary lines added for `Hypothesis:` and `Validation result:` paths

### `polytool/__main__.py` (modified)

- `"hypothesis-validate"` added to `_COMMAND_HANDLER_NAMES` → `hypotheses_main`
- `"hypothesis-validate"` added to `_FULL_ARGV_COMMANDS`
- Help text updated: `hypothesis-validate` listed under Research Loop group

### `pyproject.toml` (modified)

- `"packages.polymarket.hypotheses"` added to `[tool.setuptools] packages`

### `tests/test_hypothesis_validator.py` (new)

30 tests covering:
- Minimal valid document passes
- All 4 top-level required fields individually missing → fail
- Wrong `schema_version` → fail
- Missing each required `metadata` sub-field → fail
- Empty `bullets` array → fail; >10 bullets → fail
- Wrong `confidence` enum → fail; all three valid values → pass
- Wrong `overall_assessment` enum → fail; all four valid values → pass
- Optional fields absent → no error (limitations, missing_data_for_backtest)
- Recommended fields absent → warnings generated; present → no warnings
- `ValidationResult` structure: has `errors` and `warnings` lists
- `hypotheses[i].evidence` requires `text` field; empty evidence → fail
- Missing `claim` / `falsification` per hypothesis item → fail
- Invalid `id` pattern → fail; valid `H1` → pass
- Invalid `proxy_wallet` format → fail; valid wallet → pass
- `window_days` must be int >= 1
- Non-dict root → fail
- Multiple hypotheses: each validated independently

---

## Files Changed

| File | Change |
|------|--------|
| `packages/polymarket/hypotheses/__init__.py` | New package init |
| `packages/polymarket/hypotheses/validator.py` | New hand-rolled validator |
| `tools/cli/hypotheses.py` | +`handle_hypothesis_validate`, +`hypothesis-validate` subparser |
| `tools/cli/llm_save.py` | +`--hypothesis-path`, validation, `validation_result.json` output |
| `polytool/__main__.py` | Registered `hypothesis-validate` command |
| `pyproject.toml` | Added `packages.polymarket.hypotheses` |
| `tests/test_hypothesis_validator.py` | 30 new tests |

---

## Commands Run

```bash
# All tests passing
pytest tests/test_hypothesis_validator.py tests/test_hypotheses_cli.py -v --tb=short
# 32 passed

# CLI smoke tests
python -m polytool hypothesis-validate --help
python -m polytool hypothesis-validate --hypothesis-path <valid.json>   # exit 0
python -m polytool hypothesis-validate --hypothesis-path <invalid.json> # exit 1

# llm-save integration
python -m polytool llm-save --user @testuser --model claude-sonnet-4-6 \
  --run-id smoke001 --report-path report.md --prompt-path prompt.txt \
  --hypothesis-path valid_hypothesis.json --no-devlog
# -> writes hypothesis.json + validation_result.json (valid: true)

python -m polytool llm-save ... --hypothesis-path invalid_hypothesis.json
# -> errors on stderr, exit 0 (save not blocked)
```

---

## Scope Constraints

**Did NOT touch:**
- Gate 2, Track A, or any live execution code
- Hypothesis diff (`hypothesis-diff`) — Packet 2
- Summary bullet extraction for LLM_notes — Packet 3
- `experiment-run` tape/sweep wiring — after Packet 2
- The hypothesis schema itself (no schema changes)

---

## References

- `docs/PLAN_OF_RECORD.md §11` — backtesting kill condition that depends on this
- `docs/specs/hypothesis_schema_v1.json` — schema contract
- `docs/dev_logs/2026-03-11_gate2_blocker_report.md` — Gate 2 parking rationale
- `docs/TODO.md` — "Hypothesis Validation" under High Priority
