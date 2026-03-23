# Dev Log: Hypothesis Validation Loop v0 - Packet 3 Summary Final Fix

**Date:** 2026-03-12
**Branch:** phase-1
**Track:** Track B - Research Loop

---

## Summary

Closed the remaining Packet 3 blockers in the deterministic `hypothesis-summary` surface.

This final fix stays on `phase-1` and remains scoped to Track B Packet 3. Packet 1 validation behavior, Packet 2 diff behavior, Track A work, Gate 2 work, and Phase 4 automation work were not modified.

---

## What Changed

### `packages/polymarket/hypotheses/summary.py`

Finished the summary gating and evidence-provenance rules.

Fixes:
- dict-shaped but malformed `hypotheses[]` entries are now rejected by a summary-eligible hypothesis contract derived from the schema's required hypothesis fields
- malformed dict hypotheses are surfaced under `structure_issues` with explicit rejection reasons and are skipped from `hypothesis_count` and `primary_hypothesis`
- malformed dict hypotheses can no longer steal `primary_hypothesis`
- `primary_evidence.path` is now assigned from canonical evidence order instead of the raw source-array index
- evidence-derived bullet `source_fields` now use the same canonical evidence provenance, so reorder-only input changes do not drift the summary payload

### Tests

Added focused regressions covering:
- malformed dict hypotheses are skipped and surfaced without stealing the primary hypothesis
- canonical primary-evidence payload equality across evidence-array reordering
- canonical evidence bullet provenance across evidence-array reordering
- CLI summary output skips malformed hypotheses while keeping structure issues and stable evidence provenance

---

## Final Rules

### Summary-Eligible Hypothesis Rule

A hypothesis object is summary-eligible only if it satisfies the schema-derived minimal required contract from `#/$defs/hypothesis`:
- `claim` must be a non-empty string
- `confidence` must be one of `high`, `medium`, or `low`
- `falsification` must be a non-empty string
- `evidence` must be a non-empty list of object citations, and every citation must have non-empty `text`

Optional fields such as `id`, `next_feature_needed`, `execution_recommendation`, `tags`, and `file_path` do not gate eligibility.

### Primary-Evidence Provenance Rule

Evidence is first sorted canonically by:
1. entries with text before entries without text
2. structured evidence objects before raw-string fallbacks when both have text
3. normalized evidence signature as the deterministic tie-breaker

After that sort, summary provenance is rewritten onto canonical evidence positions:
- structured evidence uses `evidence[n].text`
- raw-string fallback evidence uses `evidence[n]`

The serialized `primary_evidence.path` and evidence-derived bullet `source_fields` always use those canonical positions, never the raw incoming evidence-array index. `structure_issues.path` still points to the real raw document location.

---

## Files Changed

- `packages/polymarket/hypotheses/summary.py`
- `tests/test_hypothesis_summary.py`
- `tests/test_hypotheses_cli.py`
- `docs/dev_logs/2026-03-12_hypothesis_validation_loop_v0_packet3_summary_final_fix.md`

---

## Commands Run

```bash
pytest -q tests/test_hypothesis_summary.py tests/test_hypotheses_cli.py tests/test_polytool_main_module_smoke.py
python -m polytool hypothesis-summary --help
```

---

## Acceptance Readiness

Packet 3 is honestly ready for acceptance if the verification sweep below is green.

The remaining review blockers are addressed in code, covered by focused regressions, and kept fully inside the Packet 3 summary surface.
