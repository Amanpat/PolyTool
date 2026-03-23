# Dev Log: gap-fill summarizer v0

**Date**: 2026-03-20
**Branch**: phase-1
**Objective**: Build a read-only CLI (`summarize-gap-fill`) that loads a
`gap_fill_run.json` artifact and prints a clean diagnostic summary — without
touching live data, ClickHouse, or any active batch codepaths.

---

## Files changed

| File | Action | Why |
|------|--------|-----|
| `tools/cli/summarize_gap_fill.py` | Created | New CLI + summariser core |
| `tests/test_summarize_gap_fill.py` | Created | 35 offline tests |
| `polytool/__main__.py` | Modified | Register `summarize-gap-fill` command + help text |
| `docs/specs/SPEC-summarize-gap-fill-v0.md` | Created | Spec |
| `docs/dev_logs/2026-03-20_gap_fill_summarizer_v0.md` | Created | This log |
| `docs/CURRENT_STATE.md` | Modified | Truth update |

**Not touched**: `tools/cli/close_benchmark_v1.py`,
`tools/cli/batch_reconstruct_silver.py`,
`packages/polymarket/silver_reconstructor.py`, any artifact files.

---

## Command added

```
python -m polytool summarize-gap-fill --path <gap_fill_run.json> [--json]
```

- `--path`: required; path to a `benchmark_gap_fill_run_v1` JSON artifact.
- `--json`: optional; emit machine-readable JSON instead of human-readable text.

---

## Design decisions

1. **Pure read**: opens one file, prints to stdout, exits. No writes, no net,
   no ClickHouse dependency.
2. **Warning normalization**: extracts the prefix before the first `:` as the
   warning class (e.g. `pmxt_anchor_missing`). Falls back to stripping long
   token IDs and timestamps. This groups the common `pmxt_anchor_missing` and
   `jon_fills_missing` patterns that dominate the current probe artifacts.
3. **Success classes**: labels each successful outcome with a
   `confidence=<tier>, <fill_presence>` label (e.g. `confidence=low,
   price_2min_only`) so operators can see at a glance whether any fills or
   pmxt anchors were found.
4. **Unknown schema**: warns to stderr and continues rather than hard-failing,
   so the tool stays useful if the schema version bumps in a future patch.
5. **Artifact paths capped at 20**: prevents overwhelming output on 120-target
   runs.

---

## Commands run and output

### Test run
```
python -m pytest tests/test_summarize_gap_fill.py -v --tb=short
```
Output: **35 passed in 0.24s**

### CLI help check
```
python -m polytool --help
```
`summarize-gap-fill` appears in the Data Import section.

### Smoke: probe-3 (3-target real artifact)
```
python -m polytool summarize-gap-fill \
  --path artifacts/silver/manual_gap_fill_probe3_20260319_190329/gap_fill_run.json
```
Output (abridged):
```
TOTALS
  targets_attempted : 3
  tapes_created     : 3
  failure_count     : 0
  skip_count        : 0

BY BUCKET
  crypto               success=1  failure=0  skip=0  confidence=[low:1]
  politics             success=1  failure=0  skip=0  confidence=[low:1]
  sports               success=1  failure=0  skip=0  confidence=[low:1]

SUCCESS CLASSES
  confidence=low, price_2min_only: 3

WARNING CLASSES
  pmxt_anchor_missing: 3
  jon_fills_missing: 3
```

### Smoke: full-manifest run (120-target real artifact)
```
python -m polytool summarize-gap-fill \
  --path artifacts/silver/manual_gap_fill_full_20260319_213841/gap_fill_run.json
```
Key output:
```
TOTALS
  targets_attempted : 120
  tapes_created     : 120
  failure_count     : 0
  skip_count        : 0

BY BUCKET
  crypto               success=30  failure=0  skip=0  confidence=[low:10, none:20]
  near_resolution      success=30  failure=0  skip=0  confidence=[low:9, none:21]
  politics             success=30  failure=0  skip=0  confidence=[low:10, none:20]
  sports               success=30  failure=0  skip=0  confidence=[low:11, none:19]

SUCCESS CLASSES
  confidence=none, empty_tape: 80
  confidence=low, price_2min_only: 40

WARNING CLASSES
  pmxt_anchor_missing: 120
  jon_fills_missing: 120
  price_2min_missing: 80

BENCHMARK REFRESH
  triggered : True
  outcome   : gap_report_updated
  gap_report: config/benchmark_v1.gap_report.json
  return_code: 2
```

This confirms: the full 120-target run produced tapes for all four non-new-market
buckets. 80 of 120 targets had `confidence=none` (empty tape — `price_2min_missing`
in addition to the pmxt/jon warnings), while 40 had at least `confidence=low`
with `price_2min_only`. No hard failures. The benchmark refresh returned code 2
(gap_report updated, manifest not yet writeable) — consistent with `new_market`
shortage still blocking closure.

### Regression suite
```
python -m pytest tests/ -q --tb=no
```
Result: **13 failed, 2287 passed** — all 13 failures are pre-existing and
unrelated to this change (5 in `test_batch_silver_gap_fill.py`,
3 in `test_gate2_eligible_tape_acquisition.py`,
5 in `test_new_market_capture.py`).
My 35 new tests: all passing.

---

## Example usage (operator)

```bash
# After running batch-reconstruct-silver --targets-manifest ..., inspect result:
python -m polytool summarize-gap-fill \
  --path artifacts/silver/manual_gap_fill_full_20260319_213841/gap_fill_run.json

# Machine-readable output for scripting:
python -m polytool summarize-gap-fill \
  --path artifacts/silver/manual_gap_fill_full_20260319_213841/gap_fill_run.json \
  --json | python -m json.tool
```

---

## Open questions / blockers

- The full 120-target run confirms all non-new-market buckets ran without hard
  failures, but 80/120 tapes are `confidence=none` (no price_2min data found
  either). This is consistent with the `price_2min` ClickHouse table not being
  populated for those token IDs during the run window.
- The `new_market` bucket (5 targets needed) remains the primary benchmark
  closure blocker — see `close-benchmark-v1 --status`.
- The `summarize-gap-fill` tool will become more useful as the full-manifest
  gap-fill runs accumulate; the confidence distribution is the key signal for
  whether Silver tapes are Gate-2-grade or price_2min-only.
