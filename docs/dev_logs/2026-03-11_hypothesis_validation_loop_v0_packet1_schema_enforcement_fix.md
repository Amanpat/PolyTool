# Dev Log: Hypothesis Validation Loop v0 — Packet 1 Schema Enforcement Fix

**Date:** 2026-03-11
**Branch:** phase-1
**Track:** Track B — Research Loop

---

## Summary

Closed five schema-enforcement gaps in `validator.py` that allowed invalid
hypothesis documents to pass as valid.  All gaps were proven by concrete
counter-examples in the blocking review finding.

---

## Gaps Closed

### 1. `created_at_utc` — no-timezone accepted

Old code used a loose prefix regex `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}` that:
- Accepted `"2026-03-11T00:00:00"` (no timezone designator)
- Accepted `"2026-99-99T99:99:99Z"` (invalid calendar/clock values)

Fix: replaced regex with `_is_valid_datetime_str()` which:
1. Requires a timezone designator (trailing `Z` or `±HH:MM` offset)
2. Calls `datetime.fromisoformat()` after normalizing `Z` → `+00:00` to reject
   out-of-range month, day, hour, minute, and second values
3. No new dependencies — stdlib `datetime` only

### 2. `metadata.dossier_export_id` — integer accepted

Schema: `"type": "string"`.  Old code never checked this optional field.

Fix: added `isinstance(meta["dossier_export_id"], str)` check alongside the
other optional-metadata field checks.

### 3. `limitations` — non-string items accepted

Schema: `items: {type: string}`.  Old code only warned when the field was absent;
it never validated item types when the field was present.

Fix: added `_STRING_ARRAY_FIELDS = ("limitations", "missing_data_for_backtest",
"next_features_needed")` and a shared loop that validates array type and string
item type for each.

### 4. `hypotheses[i].tags` — non-string items accepted

Schema: `tags.items: {type: string}`.  `_validate_hypothesis_item` never
inspected `tags` at all.

Fix: added `tags` array-type and item-type check at the end of
`_validate_hypothesis_item`.

### 5. Stale dev log reference

`docs/dev_logs/2026-03-11_hypothesis_validation_loop_v0_packet1.md` still showed
`--report-path` in the CLI smoke-test examples — the argument was renamed to
`--hypothesis-path` in the fixup.  Corrected in-place.

---

## Implementation Choice: hand-rolled vs. jsonschema

`jsonschema` (PyPI) would eliminate all future drift between the spec file and
the validator.  It was not added for this fix because:

- The existing code comment explicitly chose stdlib-only
- The remaining gaps were small and targeted
- Adding a new dependency mid-milestone requires ADR sign-off

If drift recurs or the schema grows, switching to `jsonschema` is the right
long-term move and should be filed as a separate task.

---

## Files Changed

| File | Change |
|------|--------|
| `packages/polymarket/hypotheses/validator.py` | Replaced `_ISO8601_DATETIME_RE` with `_is_valid_datetime_str()`; added `_STRING_ARRAY_FIELDS` loop; added `dossier_export_id` type check; added `tags` validation in `_validate_hypothesis_item` |
| `tests/test_hypothesis_validator.py` | +9 tests covering all 5 proven gaps |
| `docs/dev_logs/2026-03-11_hypothesis_validation_loop_v0_packet1.md` | Fixed stale `--report-path` → `--hypothesis-path` in smoke-test examples |

---

## Test Results

```
pytest -q tests/test_hypothesis_validator.py tests/test_llm_save.py \
           tests/test_hypotheses_cli.py tests/test_polytool_main_module_smoke.py
```

(See run output below — all passing.)

---

## Scope Constraints

Did NOT touch:
- Gate 2, Track A, any live execution code
- `llm_save.py`, `hypotheses.py`, `__main__.py` (no behavior changes needed)
- The hypothesis schema itself
- Packet 2 or later work
