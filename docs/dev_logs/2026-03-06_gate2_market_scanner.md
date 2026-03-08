# Gate 2 Market Scanner (2026-03-06)

## Summary

Added a diagnostic market scanner that identifies Polymarket markets (live or
from local tapes) that are likely candidates for recording a new Gate 2 tape
for the `binary_complement_arb` strategy under the `sane` preset.

## Files Created

| File | Purpose |
|---|---|
| `tools/cli/scan_gate2_candidates.py` | Scanner CLI — fetches and ranks markets |
| `tests/test_scan_gate2_candidates.py` | 20 offline tests covering ranking and scoring |

## Motivation

Gate 2 failed on all 9 existing local tapes:
- `edge_ticks > 0` in 0/9 tapes
- `executable_ticks > 0` in 0/9 tapes

The strategy (`sane` preset) requires both conditions simultaneously:
1. **Depth condition**: both YES and NO best-ask sizes >= `max_size` (50 shares)
2. **Edge condition**: `yes_ask + no_ask < 1 - buffer` (< 0.99)

Before recording a new tape, operators need a way to identify which live
markets are worth the effort.

## Ranking Formula

Each market is scored on:

| Column | Meaning |
|---|---|
| `executable_ticks` | Ticks where depth AND edge both satisfied simultaneously |
| `edge_ok_ticks` | Ticks where `sum_ask < threshold` (regardless of depth) |
| `depth_ok_ticks` | Ticks where both ask sizes >= `max_size` (regardless of edge) |
| `best_edge` | Max observed `(threshold - sum_ask)`; positive = arb window existed |
| `max_depth_yes / max_depth_no` | Peak best-ask size per leg |

Ranking priority (all descending):
1. `executable_ticks` — most simultaneously executable ticks first
2. `edge_ok_ticks` — edge signal is more actionable than depth alone
3. `depth_ok_ticks` — depth availability (edge may appear later)
4. `best_edge` — how close (or far above threshold) the complement sum came
5. `min(max_depth_yes, max_depth_no)` — best worst-leg depth as tiebreaker

## Commands to Run

### Live market scan (default)

Scans up to 50 live active binary markets and scores their current snapshot:

```bash
python -m polytool scan-gate2-candidates
```

Show more markets with custom parameters:

```bash
python -m polytool scan-gate2-candidates --candidates 100 --top 30
```

Show all markets including zero-signal ones:

```bash
python -m polytool scan-gate2-candidates --all --top 50
```

Custom strategy parameters (e.g., to check with the `loose` preset):

```bash
python -m polytool scan-gate2-candidates --max-size 1 --buffer 0.0005
```

### Tape scan (offline)

Replay all local tapes and rank by tick-level statistics:

```bash
python -m polytool scan-gate2-candidates --tapes-dir artifacts/simtrader/tapes
```

### Debug mode

```bash
python -m polytool scan-gate2-candidates -v
```

## Sample Output

Live scan (each market shows a single-snapshot score; 0 or 1 per column):

```
Market                                       |   Exec |   Edge |  Depth |  BestEdge | MaxDepth YES/NO
-------------------------------------------- | ------ | ------ | ------ | --------- | ----------------
trump-wins-2028                              |      1 |      1 |      1 |   +0.0140 |          120 / 110
eth-over-4k-2025                             |      0 |      1 |      0 |   -0.0050 |           22 / 85
will-the-okc-thunder-win-nba-finals          |      0 |      0 |      1 |   -0.0200 |          210 / 180
some-illiquid-market                         |      0 |      0 |      0 |   -0.0800 |            3 / 2
-------------------------------------------- | ------ | ------ | ------ | --------- | ----------------
Showed 4/50 candidates. Mode: live (snapshot). Threshold: sum_ask < 0.9900, depth >= 50 shares.
```

Tape scan (multi-tick statistics over the full tape duration):

```
Market                                       |   Exec |   Edge |  Depth |  BestEdge | MaxDepth YES/NO
-------------------------------------------- | ------ | ------ | ------ | --------- | ----------------
will-okc-thunder-win-nba-finals              |      0 |      0 |     21 |   -0.0200 |        21.0 / 21.0
bitboy-convicted                             |      0 |      0 |      0 |   -0.0110 |        20.0 / 20.0
will-trump-deport-less-than-250000           |      0 |      0 |      0 |   -0.0170 |         5.0 / 5.0
-------------------------------------------- | ------ | ------ | ------ | --------- | ----------------
Showed 3/9 candidates. Mode: tape (over 21+ ticks/tape). Threshold: sum_ask < 0.9900, depth >= 50 shares.
```

## How Operators Should Interpret Results

### Executable market found (`Exec > 0`)

Record a tape immediately:

```bash
python -m polytool simtrader shadow --market <slug> --duration 300
```

Then run the Gate 2 sweep on the recorded tape.

### Edge only, no depth (`Edge > 0`, `Depth == 0`, `BestEdge > 0`)

The complement sum dips below the threshold, but best-ask size is below 50.
Options:
- Monitor this market at a different time (depth can improve)
- Temporarily lower `--max-size` for a diagnostic sweep to confirm edge is real

### Depth only, no edge (`Depth > 0`, `Edge == 0`, `BestEdge < 0`)

Deep book but no pricing dislocation. `BestEdge` tells you how far away the
sum_ask is from the threshold. Markets with `BestEdge > -0.02` are worth
watching — the gap is narrow and a volatile period may push it through.

### No signal (`Exec == 0`, `Edge == 0`, `Depth == 0`)

Market has neither adequate depth nor complement edge at the time of scanning.
Skip; check again later or try a different market category.

### Interpreting `BestEdge`

| Value | Interpretation |
|---|---|
| `+0.05` | Strong arb window: sum_ask was 5 cents below threshold |
| `+0.001` | Marginal: edge barely crossed threshold |
| `-0.001` | Near-miss: sum_ask came within 0.1 cents of threshold |
| `-0.10` | Far from threshold; unlikely to become executable soon |

## Notes

- **Live mode** scores a single point-in-time snapshot per market. A market
  scoring 0 now may be executable minutes later during volatile periods.
- **Tape mode** scores every event tick in the tape, giving richer signal but
  only for historical data.
- The scanner does **not** modify any strategy, preset, or gate threshold.
- `best_edge` for tape mode accounts for the worst-case (most negative) gap
  across the entire tape, not just the snapshot.
