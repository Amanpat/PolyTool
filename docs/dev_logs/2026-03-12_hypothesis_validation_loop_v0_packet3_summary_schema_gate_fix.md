# Dev Log: Hypothesis Validation Loop v0 - Packet 3 Summary Schema Gate Fix

**Date:** 2026-03-12
**Branch:** phase-1
**Track:** Track B - Research Loop

---

## Summary

Closed the final Packet 3 blocker in the deterministic `hypothesis-summary` surface.

This fix stays on `phase-1` and remains scoped to Track B Packet 3. Packet 1 validation behavior, Packet 2 diff behavior, Track A work, Gate 2 work, and Phase 4 automation work were not modified.

---

## What Changed

### `packages/polymarket/hypotheses/summary.py`

Replaced the hand-rolled summary eligibility heuristic for dict-shaped hypotheses with schema-based validation against the packaged `#/$defs/hypothesis` definition.

Results:
- schema-invalid hypothesis dicts are skipped from `summary.hypothesis_count`
- schema-invalid hypothesis dicts cannot become `primary_hypothesis`
- schema-invalid hypothesis dicts are surfaced in `structure_issues` with the real `hypotheses[i]...` paths inside concise reason strings
- malformed dict hypotheses can no longer steal primary selection from a valid duplicate

### `packages/polymarket/hypotheses/validator.py`

Added a reusable per-hypothesis validator helper backed by the packaged schema so summary gating uses the same schema source as Packet 1 document validation without changing Packet 1 behavior.

### Tests

Added focused regressions for:
- invalid hypothesis id pattern (`id="HX"`)
- non-string tags (`tags=[1]`)
- invalid evidence metrics type (`metrics="oops"`)
- invalid evidence file path type (`file_path=123`)
- malformed duplicate hypothesis cannot steal `primary_hypothesis`
- CLI summary output skips all of the above while keeping valid duplicates eligible

---

## Files Changed

- `packages/polymarket/hypotheses/summary.py`
- `packages/polymarket/hypotheses/validator.py`
- `tests/test_hypothesis_summary.py`
- `tests/test_hypotheses_cli.py`
- `docs/dev_logs/2026-03-12_hypothesis_validation_loop_v0_packet3_summary_schema_gate_fix.md`

---

## Commands Run

```bash
pytest -q tests/test_hypothesis_summary.py
pytest -q tests/test_hypotheses_cli.py
pytest -q tests/test_hypothesis_summary.py tests/test_hypotheses_cli.py tests/test_polytool_main_module_smoke.py
python -m polytool hypothesis-summary --help
```

---

## Results

### Pytest

```text
41 passed in 4.95s
```

### Help Surface

```text
usage: __main__.py hypothesis-summary [-h] --hypothesis-path HYPOTHESIS_PATH
```

---

## Final Summary-Eligible Hypothesis Rule

A dict-shaped `hypotheses[]` entry is summary-eligible only if it validates against the packaged schema's `#/$defs/hypothesis` definition.

In practice that means:
- required fields must be present (`claim`, `evidence`, `confidence`, `falsification`)
- required-field values must satisfy the schema
- optional fields also must satisfy the schema if present (`id`, `tags`, `evidence[].metrics`, `evidence[].file_path`, etc.)

If any schema error exists, the hypothesis dict is skipped from `hypothesis_count` and `primary_hypothesis`, and the validator error summaries are recorded under `structure_issues`.

---

## Acceptance Readiness

Packet 3 is honestly ready for acceptance.

The remaining blocker is closed in code, the requested regressions are present, the exact verification sweep passed, and the scope stayed inside the Packet 3 summary surface.
