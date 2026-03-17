# Dev Log: Hypothesis Validation Loop v0 - Packet 3 Summary Fix

**Date:** 2026-03-12
**Branch:** phase-1
**Track:** Track B - Research Loop

---

## Summary

Fixed the Packet 3 review regressions in the deterministic `hypothesis-summary` surface.

This pass keeps the work scoped to Packet 3 on `phase-1`. Packet 1 validation behavior, Packet 2 diff behavior, Track A work, Gate 2 work, and Phase 4 automation work were not modified.

---

## What Changed

### `packages/polymarket/hypotheses/summary.py`

Adjusted summary extraction so malformed structure is explicit and does not get promoted into the real hypothesis surface.

Fixes:
- non-object `hypotheses[]` items are now skipped from `hypothesis_count` and cannot become `primary_hypothesis`
- malformed structure is surfaced under top-level `structure_issues`
- duplicate ids and duplicate claims now suffix from canonical structural ordering instead of source index
- canonical hypothesis signatures normalize nested evidence and tags before duplicate ordering
- primary evidence is selected from canonicalized evidence ordering instead of incoming array order
- raw-string fallbacks now keep real source locations (`limitations`, `evidence[0]`) instead of invented paths like `limitations[0]` or `evidence[0].text`

### Tests

Added focused regressions covering:
- skipped malformed `hypotheses[]` items with explicit `structure_issues`
- stable duplicate-id suffixing across reorderings
- stable duplicate-claim suffixing across reorderings
- canonical primary-evidence selection across evidence-array reorderings
- real-path raw-string fallbacks through both module and CLI coverage

---

## Files Changed

- `packages/polymarket/hypotheses/summary.py`
- `tests/test_hypothesis_summary.py`
- `tests/test_hypotheses_cli.py`
- `docs/dev_logs/2026-03-12_hypothesis_validation_loop_v0_packet3_summary_fix.md`

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
33 passed in 5.05s
```

### Help Surface

```text
usage: __main__.py hypothesis-summary [-h] --hypothesis-path HYPOTHESIS_PATH
```

---

## Final Behavior Contract

### Malformed input

- Non-object `hypotheses[]` entries are not treated as real hypotheses.
- They are skipped from `summary.hypothesis_count`.
- They cannot become `summary.primary_hypothesis_key` or `primary_hypothesis`.
- They are surfaced under top-level `structure_issues` with the real document path such as `hypotheses[0]`.
- Raw-string list fallbacks still preserve readable text, but their source paths stay real:
  - top-level string fallback uses `limitations`, `risks`, etc.
  - raw-string evidence entry fallback uses `evidence[0]`

### Duplicate-key ordering

Duplicate hypothesis keys are assigned after sorting valid hypothesis objects by a canonical tuple:
1. numeric `H<n>` ids
2. other ids
3. claims without ids
4. anonymous objects

Within the same id/claim bucket, suffix order is determined by the normalized structural signature of the hypothesis object, where nested evidence, `trade_uids`, and tags are canonicalized before comparison. Source index is no longer used to break duplicate-id or duplicate-claim ties.

### Primary-evidence selection

Primary evidence is selected from the canonicalized evidence ordering for the chosen primary hypothesis:
1. entries with text before entries without text
2. structured evidence objects before raw-string fallbacks when both have text
3. normalized evidence signature as the deterministic tie-breaker

The reported `primary_evidence.path` stays hypothesis-relative (`evidence[0]` or `evidence[0].text`), while malformed-input `structure_issues.path` points to the real document location (`hypotheses[1].evidence[0]`).

---

## Acceptance Readiness

Packet 3 is honestly ready for acceptance.

The four review issues were fixed, deterministic regressions were added, the requested test sweep passed, and the CLI help surface still works.
