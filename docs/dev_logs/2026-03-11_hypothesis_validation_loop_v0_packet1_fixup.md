# Dev Log: Hypothesis Validation Loop v0 — Packet 1 Fixup

**Date:** 2026-03-11
**Branch:** phase-1
**Track:** Track B — Research Loop

---

## Summary

Post-review fixup for Packet 1.  Four categories of defects were identified and
corrected: incomplete validator coverage, malformed-JSON persistence, wrong exit
codes on fatal read/parse errors, and a CLI argument name mismatch on
`hypothesis-validate`.

---

## Problems Fixed

### 1. `validator.py` — Missing schema coverage

Three groups of schema rules were not enforced:

**`metadata.created_at_utc` format**
- Schema specifies `"format": "date-time"` (ISO 8601)
- Old code: checked only that the field was a string
- Fix: added `_ISO8601_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")` and
  a format check immediately after the string type check

**`observations` type/shape**
- Schema defines `observations` as an optional array of `observation` objects,
  each requiring `statement` (string) and `evidence` (array, minItems=1)
- Old code: `observations` was never validated
- Fix: added `_validate_observation_item()` helper and an `observations` block
  that validates type, per-item required fields, and evidence array

**Evidence citation subfield typing (`trade_uids`, `file_path`, `metrics`)**
- Schema: `trade_uids` → array of strings, `file_path` → string, `metrics` → object
- Old code: only checked `text` field presence and type; subfields were unchecked
- Fix: extracted `_validate_evidence_citation()` helper (shared by both
  `_validate_hypothesis_item` and `_validate_observation_item`) that validates
  all four subfields

### 2. `llm_save.py` — Malformed JSON written as `hypothesis.json`

- Old: `hypothesis_dest.write_text(hyp_text)` happened before `json.loads()`
- Fix: parse first; only write `hypothesis.json` after successful JSON parse

### 3. `llm_save.py` — Fatal read/parse failures exited 0

- Old: `FileNotFoundError` on `--hypothesis-path` printed a Warning and
  continued (`hyp_text = None`), completing with exit 0
- Fix: both read failure and JSON parse failure now:
  1. Print `Error:` to stderr
  2. Write `validation_result.json` with `valid=false` and a descriptive error
  3. Return 1

### 4. `hypotheses.py` — CLI argument name mismatch

- Old: `hypothesis-validate` subparser used `--report-path`; handler read
  `args.report_path`
- Fix: argument renamed to `--hypothesis-path`; handler updated to
  `args.hypothesis_path`

---

## Behavior Contract (post-fixup)

| Scenario | hypothesis.json | validation_result.json | exit |
|----------|----------------|------------------------|------|
| Parseable + schema-valid | written | `valid=true` | 0 |
| Parseable + schema-invalid | written | `valid=false, errors=[...]` | 0 |
| Malformed JSON | **NOT written** | `valid=false`, parse error | **1** |
| Unreadable file | **NOT written** | `valid=false`, read error | **1** |

`hypothesis-validate`:
- Valid file → exit 0, JSON to stdout
- Schema-invalid → exit 1, JSON with errors to stdout
- Malformed JSON → exit 1, error to stderr
- Missing file → exit 1, error to stderr

---

## Files Changed

| File | Change |
|------|--------|
| `packages/polymarket/hypotheses/validator.py` | +`_ISO8601_DATETIME_RE`, +`created_at_utc` format check, +`observations` block, +`_validate_observation_item()`, +`_validate_evidence_citation()` (refactored from inline) |
| `tools/cli/llm_save.py` | Reordered parse-before-write; read/parse failures exit 1 + write validation_result.json |
| `tools/cli/hypotheses.py` | `--report-path` → `--hypothesis-path` in validate subparser and handler |
| `tests/test_hypothesis_validator.py` | +17 tests: created_at_utc format, observations shape, evidence subfield typing |
| `tests/test_llm_save.py` | +4 tests: valid/schema-invalid/malformed/unreadable hypothesis-path behaviors |
| `tests/test_hypotheses_cli.py` | +5 tests: hypothesis-validate valid/invalid/malformed/missing/arg-name |

---

## Test Results

```
69 passed in 1.62s
tests/test_hypothesis_validator.py  44 passed
tests/test_llm_save.py               9 passed
tests/test_hypotheses_cli.py         7 passed
tests/test_polytool_main_module_smoke.py  7 passed (no regression)
```

---

## Scope Constraints

Did NOT touch:
- Gate 2, Track A, any live execution code
- Hypothesis diff (`hypothesis-diff`) — Packet 2
- `experiment-run` tape/sweep wiring
- The hypothesis schema itself (no schema changes)
