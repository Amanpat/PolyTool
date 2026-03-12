# Dev Log: Hypothesis Validation Loop v0 - Packet 2 Diff Fix

**Date:** 2026-03-12
**Branch:** phase-1
**Track:** Track B - Research Loop

---

## Summary

Fixed the Packet 2 `hypothesis-diff` correctness issues from review without
changing Packet 1, Track A, Gate 2, Packet 3, or experiment-run wiring.

The diff matcher now assigns hypothesis identity from a cross-document matching
pass instead of per-document fallback keys, malformed list-like fields no longer
silently collapse to `[]`, and focused regression coverage now covers the review
cases that were missing.

---

## Fixes

### 1. Cross-document deterministic hypothesis matching

`packages/polymarket/hypotheses/diff.py`

Replaced per-document `id -> claim -> index` key selection with a deterministic
cross-document pairing flow:

- match shared non-empty `id` buckets first
- then match shared non-empty `claim` buckets
- then match remaining entries structurally in an anonymous pass
- pair exact signature matches before similarity-based matches
- use deterministic bucket ordering plus `#N` suffixes when a key is duplicated

This fixes the prior failure mode where a once-unique claim became duplicated or
where duplicate / no-id hypotheses were reordered across runs.

### 2. No silent coercion for malformed list-like fields

`packages/polymarket/hypotheses/diff.py`

`_diff_named_collection()` now preserves malformed raw values instead of
coercing non-list inputs to `[]`.

When either side is not a JSON list, the diff now:

- compares the raw normalized values
- marks the field as added / removed / changed when appropriate
- records `old` / `new` raw values
- records a `type_mismatch` payload with the observed JSON types

This keeps detailed field truth and `summary.has_changes` aligned.

### 3. Focused regression coverage

Added test coverage for:

- duplicate-claim matching when an old unique claim becomes duplicated
- duplicate no-id hypothesis reordering
- anonymous no-id hypothesis reordering
- malformed list-like field handling
- invalid JSON on `hypothesis-diff`
- non-object-root artifact paths on `hypothesis-diff`

---

## Files Changed

- `packages/polymarket/hypotheses/diff.py`
- `tests/test_hypothesis_diff.py`
- `tests/test_hypotheses_cli.py`
- `docs/dev_logs/2026-03-12_hypothesis_validation_loop_v0_packet2_diff_fix.md`

---

## Verification

Commands run after the fix:

```bash
pytest -q tests/test_hypothesis_diff.py tests/test_hypotheses_cli.py tests/test_polytool_main_module_smoke.py
python -m polytool hypothesis-diff --help
```

Result:

- all requested pytest targets passed
- `python -m polytool hypothesis-diff --help` returned exit code 0 and showed the
  command help surface

---

## Scope Guardrails

Did not touch:

- Packet 1 validator behavior
- Track A or Gate 2 logic
- Packet 3 work
- experiment-run wiring
