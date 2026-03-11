# Gate 2 Pre-Sweep Eligibility Check (2026-03-06)

## Motivation

Gate 2 (Scenario Sweep) failed with `0/24` profitable scenarios on commit
`4f5f8c2`.  The failure diagnosis (`2026-03-06_gate2_sweep_failure_diagnosis.md`)
confirmed that the failure was real but non-actionable: the recorded tape had
insufficient best-ask depth for the configured strategy size (`max_size=50`)
and no positive complement edge at top-of-book (`yes_ask + no_ask = 1.015 ≥
0.99` threshold).  None of the 24 scenario knobs (fee rate, cancel latency,
mark method) ever became operative because no orders were ever submitted.

The recommended fix was to add a diagnostic pre-sweep eligibility check that
detects these conditions early — before running 24 scenarios and writing a
`gate_failed.json` whose only meaningful content is rejection counts.

**Invariant**: the check is diagnostic only.  It does not soften any gate
threshold, strategy entry logic, or profitability criterion.

---

## Files Changed

| File | Change |
|---|---|
| `packages/polymarket/simtrader/sweeps/eligibility.py` | **New** — eligibility check module |
| `packages/polymarket/simtrader/sweeps/runner.py` | **Edit** — call `check_sweep_eligibility()` at start of `run_sweep()` |
| `tests/test_simtrader_sweep_eligibility.py` | **New** — 29 test cases |

---

## Eligibility Rules (binary_complement_arb)

A tape is eligible if it contains **at least one tick** where **both** of the
following hold simultaneously:

### Rule 1 — Sufficient depth

```
yes_best_ask_size >= strategy.max_size
AND
no_best_ask_size  >= strategy.max_size
```

This mirrors the depth gate in `BinaryComplementArb.on_event()`:

```python
# binary_complement_arb.py lines 336-346
yes_depth = self._best_ask_size(self._yes_book)
no_depth  = self._best_ask_size(self._no_book)
depth_blocked = False
if yes_depth is None or yes_depth < self._max_size:
    self.rejection_counts["insufficient_depth_yes"] += 1
    depth_blocked = True
if no_depth is None or no_depth < self._max_size:
    self.rejection_counts["insufficient_depth_no"] += 1
    depth_blocked = True
if depth_blocked:
    return intents   # no order submitted
```

### Rule 2 — Positive edge

```
yes_best_ask + no_best_ask < 1 - buffer
```

This mirrors the edge gate in `BinaryComplementArb.on_event()`:

```python
# binary_complement_arb.py lines 348-355
sum_ask = yes_ask_d + no_ask_d
threshold = _ONE - self._buffer
if sum_ask >= threshold:
    ...
    return intents   # no order submitted
```

Both rules must hold **at the same tick** — depth occurring without edge (or
vice versa) on different ticks is not sufficient.

### Default thresholds (preset: `sane`)

| Parameter | Value |
|---|---|
| `max_size` | 50 shares |
| `buffer` | 0.01 |
| `threshold` (derived) | 0.99 |

### Failure categories and error messages

| Root cause | Error message fragment |
|---|---|
| Both depth and edge fail | `"insufficient depth … AND no positive edge …"` |
| Only depth fails | `"insufficient depth: best-ask size never >= N …"` |
| Only edge fails | `"no positive edge: yes_ask + no_ask never < N …"` |
| Depth and edge on non-overlapping ticks | `"depth and edge never overlap on the same tick …"` |

---

## Diagnostic Stats

`EligibilityResult.stats` contains:

```json
{
  "events_scanned": 312,
  "ticks_with_both_bbo": 247,
  "ticks_with_depth_ok": 0,
  "ticks_with_edge_ok": 0,
  "ticks_with_depth_and_edge": 0,
  "min_yes_ask_size_seen": "1.88",
  "min_no_ask_size_seen": "15",
  "min_sum_ask_seen": "1.015",
  "required_depth": "50",
  "required_edge_threshold": "0.99"
}
```

These stats surface in the `SweepEligibilityError` message so the operator
immediately knows why the tape was rejected and what needs to change.

---

## Sample Output (ineligible tape)

When the tape is non-actionable, `run_sweep()` raises `SweepEligibilityError`
before any scenario directory is created.  The CLI catches it as
`SweepConfigError` (parent class) and prints:

```
Error: [pre-sweep eligibility] Tape is non-actionable — insufficient depth (YES
min ask size=1.88, NO min ask size=15, required=50) AND no positive edge
(min sum_ask=1.015, required < 0.99). Skipping 24-scenario sweep.  Diagnostic
stats: {...}
```

`close_sweep_gate.py` sees exit code 1 and writes `gate_failed.json` with
`failure_reason: "quickrun exited with code 1"` and the full output tail
containing the eligibility error message.

---

## Tests Added

File: `tests/test_simtrader_sweep_eligibility.py` — **29 tests, all passing**

| Class | Tests | Description |
|---|---:|---|
| `TestInsufficientDepth` | 6 | Shallow tape rejected; reason mentions depth; stats correct |
| `TestNoEdge` | 5 | Deep but over-priced tape rejected; reason mentions edge |
| `TestEligibleTape` | 7 | Eligible tape passes; boundary conditions; stats populated |
| `TestOtherStrategiesSkipped` | 2 | Non-arb strategies are always eligible (no-op) |
| `TestRunSweepIntegration` | 3 | `run_sweep()` raises before any scenario; no dirs written |
| `TestEdgeCases` | 6 | Empty tape, LTP-only events, batched format, missing file |

---

## Rationale

- **No thresholds changed** — `max_size`, `buffer`, and the 70% profitable
  gate are all unchanged.
- **No strategy alpha logic changed** — the check reads and replicates the
  same entry preconditions the strategy already uses, it does not replace them.
- **Actionable error message** — the operator knows whether to: (a) choose a
  more liquid market, (b) reduce `max_size` (separate sizing decision), or (c)
  wait for a market with tighter spread.
- **Zero cost on eligible tapes** — the check is a single-pass scan of the
  tape file, typically completing in < 10 ms for a 60-second tape.

---

## Architecture

```
packages/polymarket/simtrader/sweeps/
├── eligibility.py   ← new; SweepEligibilityError, EligibilityResult,
│                       check_sweep_eligibility(), check_binary_arb_tape_eligibility()
└── runner.py        ← edited; calls check_sweep_eligibility() lazily at top
                        of run_sweep() before scenario loop
```

The lazy import inside `run_sweep()` avoids a circular-import cycle:
`eligibility.py` imports `SweepConfigError` from `runner.py`, so `runner.py`
cannot import from `eligibility.py` at module level.  Since
`SweepEligibilityError` is a subclass of `SweepConfigError`, the existing
`except SweepConfigError` clauses in the CLI catch it automatically with no
CLI changes required.
