# Gate 2 Prep Orchestrator (2026-03-06)

## Summary

Added a thin Gate 2 preparation orchestrator that takes an operator from
candidate discovery to recorded tapes to eligibility verdict in a single
command, without reimplementing any existing logic.

Also added a deferred backlog entry for Opportunity Radar in `docs/ROADMAP.md`.

---

## Problem

Three pieces of Gate 2 tooling existed independently:

1. `scan-gate2-candidates` — ranks live markets by Gate 2 executability
2. `simtrader record` (tape capture) — records WS events to `events.jsonl`
3. `sweeps.eligibility.check_binary_arb_tape_eligibility` — checks tapes

No single command connected them. Operators had to run all three manually and
interpret results across separate outputs. The workflow bottleneck was
orchestration, not market intelligence.

---

## Files Changed

| File | Change |
|---|---|
| `tools/cli/prepare_gate2.py` | **New** — orchestrator CLI |
| `tests/test_prepare_gate2.py` | **New** — 30 tests, all passing |
| `polytool/__main__.py` | **Edit** — register `prepare-gate2` command |
| `docs/ROADMAP.md` | **Edit** — add Opportunity Radar deferred backlog entry |

---

## Command Added

```bash
python -m polytool prepare-gate2 [options]
```

### Arguments

| Flag | Default | Purpose |
|---|---|---|
| `--top N` | 3 | Number of candidates to process |
| `--duration SECS` | 300 | Tape recording duration per market |
| `--tapes-dir DIR` | — | Score existing tapes (skip scan and record) |
| `--tapes-base-dir DIR` | `artifacts/simtrader/tapes` | Output directory for new tapes |
| `--max-size N` | 50 | Strategy max_size for eligibility (must match preset) |
| `--buffer F` | 0.01 | Strategy buffer for eligibility (must match preset) |
| `--candidates N` | 50 | Max live markets to scan |
| `--dry-run` | off | Show candidates, skip recording and eligibility |
| `-v / --verbose` | off | Debug logging |

### Orchestration Flow

```
scan_live_markets()          (scan_gate2_candidates.py — reused)
        |
rank_candidates()            (scan_gate2_candidates.py — reused)
        |
  top N selected
        |
for each candidate:
    MarketPicker.resolve_slug()    -> YES/NO token IDs
    TapeRecorder.record()          -> events.jsonl written to tapes_base_dir
    check_binary_arb_tape_eligibility()  (sweeps.eligibility — reused)
        |
print_summary()              -> market | tape_path | ELIGIBLE/INELIGIBLE | reason
```

---

## Sample Operator Usage

### Full workflow (scan -> record -> check)

```bash
# Scan 50 live markets, process top 3, record 5-minute tapes, check eligibility:
python -m polytool prepare-gate2

# Process top 5 candidates with 10-minute tapes:
python -m polytool prepare-gate2 --top 5 --duration 600
```

### Dry-run (see candidates without recording)

```bash
python -m polytool prepare-gate2 --dry-run
```

### Score pre-recorded tapes (skip scan and record)

```bash
python -m polytool prepare-gate2 --tapes-dir artifacts/simtrader/tapes
```

### Sample output

```
Market                                       | Status      | Detail
-------------------------------------------------------------------------------------------
will-okc-thunder-win-nba-finals              | ELIGIBLE    | artifacts/simtrader/tapes/...
btc-100k-eoy-2025                            | INELIGIBLE  | no positive edge: sum_ask=1.03 >= 0.99
trump-wins-2028                              | INELIGIBLE  | insufficient depth: YES min=5.0, NO min=8.0
-------------------------------------------------------------------------------------------
Candidates: 3  |  Eligible: 1

Eligible tapes — proceed to Gate 2 sweep:
  python -m polytool simtrader sweep --tape artifacts/simtrader/tapes/.../events.jsonl
```

---

## Tests Run

```bash
python -m pytest tests/test_prepare_gate2.py -v
# 30 passed in 0.20s
```

### Test coverage

| Class | Tests | What is covered |
|---|---:|---|
| `TestScannerOutputConsumed` | 3 | Top N selection, cap at candidate count, empty list |
| `TestRecorderInvoked` | 3 | Correct args, per-candidate invocation, tape dir placement |
| `TestEligibilityResultsSummarized` | 4 | Eligible/ineligible results, mixed list, reason capture |
| `TestDryRun` | 3 | Recorder/check skipped, eligible=None, slug preserved |
| `TestTapesDirMode` | 6 | Eligible/ineligible tapes, multiple tapes, no-metadata error, event stream fallback, empty dir |
| `TestFailureHandling` | 4 | Resolve fail, record fail, check fail, fail-continues-next |
| `TestPrintSummary` | 7 | Eligible/ineligible/dry-run rows, count line, sweep command, no sweep in dry-run, empty |

---

## Design Decisions

**Thin layer only**: `prepare_gate2.py` contains zero scoring, eligibility, or
strategy logic. It imports and delegates to the three existing components.

**Injectable functions**: `prepare_candidates()` and `check_existing_tapes()`
accept `_resolve_fn`, `_record_fn`, and `_check_fn` kwargs for testing.
No monkey-patching required.

**Asset ID metadata**: When recording, the orchestrator writes `prep_meta.json`
alongside the tape. This lets the tapes-only mode (`--tapes-dir`) find the
YES/NO IDs without requiring the user to pass them again. Falls back to
`meta.json` (shadow runner format), then to event stream discovery.

**Failure isolation**: A resolve, record, or eligibility failure for one
candidate is captured as an INELIGIBLE result and logged. Subsequent candidates
continue.

**No gate threshold changes**: `--max-size` defaults to 50 and `--buffer`
defaults to 0.01, matching the `sane` preset exactly. These defaults exist only
to pass the values through to `check_binary_arb_tape_eligibility`; they do not
redefine or loosen any gate criterion.

---

## Backlog / TODO Note Added

`docs/ROADMAP.md` now contains a **Deferred Backlog** section with the
Opportunity Radar entry:

> **Trigger**: Start planning Opportunity Radar only after the first clean
> Gate 2 -> Gate 3 progression is completed (a tape passes the sweep gate
> and shadow gate in sequence with no manual workarounds).

The current bottleneck is a valid tape, not market intelligence. Building a
monitoring layer before that tape exists adds infrastructure without unblocking
the validation pipeline.

---

## Next Steps for Operator

1. Run `python -m polytool scan-gate2-candidates` to see current market landscape.
2. If any market has `Exec > 0` (live snapshot), run `prepare-gate2 --dry-run --top 5` to confirm candidates.
3. Run `python -m polytool prepare-gate2 --top 3 --duration 300` during market hours.
4. If any tape is ELIGIBLE, run the Gate 2 sweep command printed in the summary.
5. After Gate 2 passes, proceed to Gate 3 shadow validation.
