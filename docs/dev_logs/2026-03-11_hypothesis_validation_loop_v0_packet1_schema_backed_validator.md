# Dev Log: Hypothesis Validation Loop v0 — Packet 1 Schema-Backed Validator

**Date:** 2026-03-11
**Branch:** phase-1
**Track:** Track B — Research Loop

---

## Summary

Replaced the hand-rolled validator core in `validator.py` with real
schema-backed validation using `jsonschema` (Draft 2020-12) against the
canonical `docs/specs/hypothesis_schema_v1.json`.  This closes the final
Packet 1 blocking issue: the validator can no longer drift from the schema
because it validates against the schema file directly.

---

## Blocking Findings Closed

### 1. `hypotheses[].next_feature_needed` not type-checked

Schema: `"type": "string"`.  The hand-rolled validator never inspected this
field.  Now enforced automatically by jsonschema.

### 2. `created_at_utc` datetime validation too loose

The stdlib `datetime.fromisoformat()` call accepted:
- `2026-03-11T00:00+00:00` (missing seconds)
- `2026-03-11 00:00:00+00:00` (space instead of T separator)

Fix: added `_RFC3339_DT_RE` regex that requires `T` separator and full
`HH:MM:SS`, followed by `datetime.fromisoformat()` for calendar/clock
validation.  jsonschema does not enforce `"format": "date-time"` by default
(it is an annotation in Draft 2020-12), so this is applied as a post-schema
check.

### 3. Schema-invalid documents accepted as valid

Root cause: hand-rolled rules drifted from the spec over three rounds of
fixes.  Replaced with `jsonschema.Draft202012Validator` that validates
directly against the spec file.  Recommended-field warnings are preserved
as a layer on top.

### 4. Stale `--report-path` wording in touched dev log

`docs/dev_logs/2026-03-11_hypothesis_validation_loop_v0_packet1.md` line 47
still referenced `--report-path PATH`; corrected to `--hypothesis-path PATH`.

---

## Implementation Choice: jsonschema

`jsonschema>=4.0.0` was already installed (v4.26.0).  Added to
`pyproject.toml` core `dependencies` to make the requirement explicit.

Higher ROI than continuing hand-rolled:
- Schema file is the single source of truth — no more drift
- `$ref`, `$defs`, `const`, `pattern`, `minItems`, `maxItems`, `enum` all
  handled automatically
- Future schema changes need zero validator code changes
- Recommended-field warnings kept as advisory layer on top

---

## Artifact Contract (unchanged)

| Scenario | hypothesis.json | validation_result.json | exit |
|----------|----------------|------------------------|------|
| Parseable + schema-valid | written | `valid=true` | 0 |
| Parseable + schema-invalid | written | `valid=false, errors=[...]` | 0 |
| Malformed JSON | **NOT written** | `valid=false`, parse error | **1** |
| Unreadable file | **NOT written** | `valid=false`, read error | **1** |

---

## Files Changed

| File | Change |
|------|--------|
| `packages/polymarket/hypotheses/validator.py` | Replaced hand-rolled validation with `jsonschema.Draft202012Validator`; added RFC 3339 regex; kept recommended-field warnings |
| `tests/test_hypothesis_validator.py` | +4 new tests (next_feature_needed, no-seconds datetime, space-separator datetime); updated 3 minItems assertions for jsonschema error format |
| `pyproject.toml` | Added `jsonschema>=4.0.0` to core dependencies |
| `docs/dev_logs/2026-03-11_hypothesis_validation_loop_v0_packet1.md` | Fixed stale `--report-path` → `--hypothesis-path` on line 47 |

---

## Test Results

```
pytest -v --tb=short tests/test_hypothesis_validator.py tests/test_llm_save.py \
  tests/test_hypotheses_cli.py tests/test_polytool_main_module_smoke.py

82 passed in 2.88s

tests/test_hypothesis_validator.py  59 passed
tests/test_llm_save.py               9 passed
tests/test_hypotheses_cli.py          7 passed
tests/test_polytool_main_module_smoke.py  7 passed
```

---

## Scope Constraints

Did NOT touch:
- Gate 2, Track A, any live execution code
- `llm_save.py`, `hypotheses.py`, `__main__.py` (no behavior changes needed)
- The hypothesis schema itself
- Packet 2 or later work
