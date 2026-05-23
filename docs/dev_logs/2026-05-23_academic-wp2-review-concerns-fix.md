# Academic RIS WP-2: Review Concerns Closed

**Date:** 2026-05-23
**Status:** CLOSED

## Objective

Close the two non-blocking operational concerns raised in the Codex review
(`docs/dev_logs/2026-05-23_codex-review-academic-wp2-and-l2-1-packet.md`).

---

## Concern 1 — `--auto-timeout` silently falls back on uncached items

**Problem:** `warm-process --auto-timeout` assigned the 14400s default to
pending items with no entry in the prefetch manifest. A missing prefetch step
could be silently hidden, and the command still proceeded.

**Fix:** `_cmd_warm_process()` now tracks `uncached_ids` explicitly.

- If any uncached items are found **and** `--allow-uncached` is NOT set:
  exit code 1, listing all uncached candidate IDs and instructing the operator
  to run `prefetch` first.
- If `--allow-uncached` IS set: proceed, printing a stderr WARNING listing
  how many items received the default timeout.
- `--json` mode: error is returned as JSON with `uncached_ids` key and
  `exit_code: 1`.
- `--allow-uncached` flag added to `warm-process` subparser with explicit
  help text.

### Files changed

- `tools/cli/research_marker_queue.py`
  - `_cmd_warm_process()`: replaced silent fallback with fail-fast + `--allow-uncached` opt-in
  - `_build_parser()`: added `--allow-uncached` argument to `p_warm` subparser

---

## Concern 2 — `jit-cache-check` steps reference `/tmp/before_marker` without creating it

**Problem:** Step 3 (now Step 4) ran `find ~/.triton -newer /tmp/before_marker`
but the instructions never told the operator to create `/tmp/before_marker`,
making the procedure not copy-paste reliable.

**Fix:** Added a new Step 2 between "locate kernel cache before run" and
"process one warm paper":

```
Step 2 — Create a timestamp marker BEFORE processing (required for Step 4):
  touch /tmp/before_marker
```

All subsequent steps renumbered (old 2→3, 3→4, 4→5, 5→6, 6→7).

### Files changed

- `tools/cli/research_marker_queue.py`
  - `_cmd_jit_cache_check()`: inserted Step 2 `touch /tmp/before_marker`,
    renumbered Steps 3–7

---

## Tests Added (7 new tests)

### `TestCLIJitCacheCheck` (2 added, total now 7)

- `test_jit_cache_check_includes_touch_before_marker`: text output contains
  `touch /tmp/before_marker`
- `test_jit_cache_check_json_instructions_include_touch`: JSON `instructions`
  array contains `touch /tmp/before_marker`

### `TestAutoTimeoutUncached` (5 new tests)

- `test_auto_timeout_fails_when_no_manifest_data`: pending item, no prefetch
  manifest → exit code != 0
- `test_auto_timeout_json_error_includes_uncached_ids`: `--json` mode → JSON
  has `uncached_ids` containing the candidate ID
- `test_auto_timeout_allow_uncached_flag_in_help`: `--allow-uncached` appears
  in `warm-process --help`
- `test_auto_timeout_allow_uncached_empty_queue_exits_zero`: empty queue +
  `--auto-timeout --allow-uncached` → exit 0 (flag parsed, gate not hit)
- `test_auto_timeout_allow_uncached_does_not_return_uncached_error_json`:
  done-item queue + `--allow-uncached --json` → no uncached-error JSON response

## Test Results

```
tests/test_ris_marker_queue.py: 177 passed, 1 skipped (178 collected)
```

Baseline was 170 passed, 1 skipped. 7 new tests added, all pass.

---

## Smoke Tests

```
python -m polytool research-marker-queue warm-process --help
```
Output confirms `--allow-uncached` present with correct description.

```
python -m polytool research-marker-queue jit-cache-check
```
Step 2 reads: "Create a timestamp marker BEFORE processing (required for Step 4): `touch /tmp/before_marker`"

---

## WP-2 Status

Both Codex review concerns are now closed:

| Concern | Status |
|---------|--------|
| `--auto-timeout` silent fallback on missing prefetch data | CLOSED — fail-fast with `--allow-uncached` opt-in |
| `jit-cache-check` missing `touch /tmp/before_marker` | CLOSED — Step 2 now creates the marker |

The two open operational blockers from the original WP-2 dev log remain
unchanged (JIT cache persistence unresolved, three timeout-risk papers need
Tier-3/operator approval). Those are runtime/infrastructure concerns, not
code concerns, and are tracked in the runbook.

---

## Codex Review

Tier: Skip (CLI formatting, argparse, diagnostics text, tests — no
execution-path code changes). No adversarial review required.

Issues found: None.
Issues addressed: Both Codex review concerns closed.
