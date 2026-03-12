# Dev Log: Hypothesis Validation Loop v0 - Packet 2

**Date:** 2026-03-12
**Branch:** phase-1
**Track:** Track B - Research Loop

---

## Summary

Implemented Packet 2 of the Track B Hypothesis Validation Loop milestone.

This packet adds a deterministic `hypothesis-diff` review surface for comparing
saved `hypothesis.json` artifacts across LLM runs. The output is JSON-first and
structured around the fields that matter for research review: metadata identity,
executive summary bullets, per-hypothesis changes, confidence deltas, evidence
/citation deltas, limitations, and next-feature or execution recommendation
fields.

Packet 1 behavior was left intact. No `llm-save` persistence behavior, schema
validation behavior, summary extraction, or experiment execution wiring changed.

---

## What Was Built

### `packages/polymarket/hypotheses/diff.py` (new)

Added a dedicated comparison module for saved hypothesis artifacts.

Core behavior:
- `load_hypothesis_artifact(path)` loads a saved JSON artifact and rejects non-object roots.
- `diff_hypothesis_documents(old_doc, new_doc, *, old_path, new_path)` returns a deterministic JSON diff payload.
- Output includes:
  - document schema-version comparison
  - metadata identity/context field rows with `old/new/status`
  - executive summary diff (`overall_assessment`, bullets added/removed/unchanged)
  - hypothesis entry diff keyed deterministically by `id`, then `claim`, then fallback index
  - confidence change summary
  - evidence/citation change summary with added/removed citation payloads
  - top-level limitations / missing-backtest-data / next-features diffs
  - optional `risks` and `execution_recommendations` top-level diffs when present
  - `field_changes.added|removed|changed` path lists for quick review
- Determinism rules:
  - hypotheses are keyed and emitted in sorted order
  - evidence citations are normalized and sorted before comparison
  - `trade_uids` and `tags` order does not create false diffs
  - JSON output is emitted with sorted keys

### `tools/cli/hypotheses.py` (modified)

Added `hypothesis-diff` to the existing hypothesis CLI surface.

- New command:
  - `python -m polytool hypothesis-diff --old PATH --new PATH`
- Behavior:
  - reads both JSON files
  - prints a structured JSON diff to stdout
  - exits 0 on success, 1 on missing file / invalid JSON / invalid root type

### `polytool/__main__.py` (modified)

Registered `hypothesis-diff` in the top-level module dispatcher and help output.

- Added to `_COMMAND_HANDLER_NAMES`
- Added to `_FULL_ARGV_COMMANDS`
- Listed under the Track B Research Loop help surface

### `tests/test_hypothesis_diff.py` (new)

Added focused unit coverage for Packet 2 behavior.

Coverage includes:
- added / removed / changed field paths
- metadata identity field changes
- executive summary bullet diffs
- per-hypothesis confidence and evidence changes
- added hypothesis entries
- order-only stability for hypotheses, tags, and citations
- non-object root rejection when loading saved artifacts

### `tests/test_hypotheses_cli.py` (modified)

Extended CLI coverage for the new command.

- top-level help now asserts `hypothesis-diff` is listed
- CLI diff smoke verifies JSON payload shape and core changed fields
- missing-file error path exits 1

---

## Files Changed

| File | Change |
|------|--------|
| `packages/polymarket/hypotheses/diff.py` | New deterministic hypothesis diff module |
| `tools/cli/hypotheses.py` | Added `hypothesis-diff` handler and subparser |
| `polytool/__main__.py` | Registered `hypothesis-diff` and updated help text |
| `tests/test_hypothesis_diff.py` | New focused unit tests for Packet 2 |
| `tests/test_hypotheses_cli.py` | Added CLI coverage for `hypothesis-diff` |
| `docs/dev_logs/2026-03-12_hypothesis_validation_loop_v0_packet2_diff.md` | Packet 2 implementation log |

---

## Commands Run

```bash
pytest -q tests/test_hypothesis_diff.py tests/test_hypotheses_cli.py tests/test_polytool_main_module_smoke.py
python -m polytool hypothesis-diff --help
```

---

## Scope Constraints

**Did NOT touch:**
- Track A code or Gate 2 behavior
- Packet 1 validator / `llm-save` behavior
- summary extraction / LLM_notes changes
- experiment-run execution wiring
- hypothesis schema contract

---

## Notes

The current schema does not define an execution recommendation field, so the
diff module handles that case defensively as an optional extra field rather than
expanding the schema in this packet.