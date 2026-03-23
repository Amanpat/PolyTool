# Dev Log: Hypothesis Validation Loop v0 - Packet 2 Final Diff Fix

**Date:** 2026-03-12
**Branch:** phase-1
**Track:** Track B - Research Loop

---

## Summary

Closed the final Packet 2 blocker in `hypothesis-diff` without touching Packet 1,
Track A, Gate 2, Packet 3, or experiment-run wiring.

The diff surface now handles malformed top-level `hypotheses` explicitly instead
of silently coercing it away, preserves raw non-object hypothesis entries during
matching, and exposes malformed hypothesis structure through deterministic diff
output.

---

## Final Fixes

### 1. Top-level `hypotheses` is explicit when malformed

`packages/polymarket/hypotheses/diff.py`

When either side provides a present-but-non-list top-level `hypotheses` value,
`_diff_hypotheses()` now:

- records `field_changes.changed = ["hypotheses"]` when the malformed value differs
- sets `summary.has_changes = true`
- returns raw normalized `old` / `new` values instead of coercing to `[]`
- returns `status` plus `type_mismatch.old_type|new_type`
- emits a deterministic `structure_issues` entry for `path="hypotheses"`

This removes the false unchanged case for payloads such as:

- old: `"hypotheses": "not-a-list"`
- new: `"hypotheses": []`

### 2. Non-object hypothesis entries keep their real structure

`packages/polymarket/hypotheses/diff.py`

Hypothesis record building now preserves raw entry values for non-object list
items instead of normalizing them through `{}` first.

Result:

- `"hypotheses": ["not-an-object"]` no longer collapses into the same shape as
  `"hypotheses": [{}]`
- added / removed hypothesis rows retain the real raw entry payload
- malformed non-object entries are surfaced under `hypotheses.structure_issues`
  with deterministic `key`, `path`, `status`, `type`, and `value`

### 3. Focused regressions added

Regression coverage now includes:

- malformed top-level `hypotheses` versus `[]`
- non-object hypothesis entries versus object entries
- CLI output for the malformed top-level `hypotheses` case

---

## Files Changed

- `packages/polymarket/hypotheses/diff.py`
- `tests/test_hypothesis_diff.py`
- `tests/test_hypotheses_cli.py`
- `docs/dev_logs/2026-03-12_hypothesis_validation_loop_v0_packet2_diff_final_fix.md`

---

## Verification

Commands run:

```bash
pytest -q tests/test_hypothesis_diff.py tests/test_hypotheses_cli.py tests/test_polytool_main_module_smoke.py
python -m polytool hypothesis-diff --help
```

Results:

- `pytest`: 28 passed
- `python -m polytool hypothesis-diff --help`: exit code 0

---

## Malformed Top-Level `hypotheses` Contract

For `old["hypotheses"] = "not-a-list"` and `new["hypotheses"] = []`, the diff now
returns:

- `field_changes.changed == ["hypotheses"]`
- `summary.has_changes == true`
- `hypotheses.status == "changed"`
- `hypotheses.old == "not-a-list"`
- `hypotheses.new == []`
- `hypotheses.type_mismatch == {"old_type": "str", "new_type": "list"}`
- `hypotheses.structure_issues[0].path == "hypotheses"`

This is explicit malformed-structure reporting rather than silent normalization.

---

## Acceptance Readiness

Packet 2 is now honestly ready for acceptance for the reviewed blocker scope.
The remaining review issue around malformed `hypotheses` structure has been
closed with deterministic output and focused regression coverage.
