# Gate 2 Live Acquisition Cycle (2026-03-07)

## Summary

Executed the first real end-to-end Gate 2 acquisition cycle using the
`prepare-gate2` orchestrator. Three fresh 5-minute tapes were recorded from
live NHL Stanley Cup playoff markets. All three tapes are INELIGIBLE due to
**no positive edge** — the combined ask price (YES + NO) never dropped below
the 0.99 threshold during any of the recording windows.

Gate 2 remains FAILED. Gate 3 remains blocked.

---

## Cycle Timeline

| Step | Time (UTC) | Command |
|---|---|---|
| Snapshot scan | ~19:50 | `scan-gate2-candidates --top 10` |
| Full acquisition started | 19:50:39 | `prepare-gate2 --top 3 --duration 300` |
| Toronto tape recorded | 19:50:39 – 19:55:42 | (candidate 1) |
| Vancouver tape recorded | 19:55:42 – 20:01:05 | (candidate 2) |
| Calgary tape recorded | 20:01:05 – 20:06:xx | (candidate 3) |
| Summary printed | ~20:06 | all three INELIGIBLE |

---

## Commands Run

### 1. Initial snapshot scan

```bash
python -m polytool scan-gate2-candidates --top 10
```

Output: 35 live active binary markets found; top 10 all showed `Depth=1`,
`Edge=0`, `Exec=0`, `BestEdge=-0.0110`.

### 2. Full acquisition cycle

```bash
python -m polytool prepare-gate2 --top 3 --duration 300
```

Exit code: `0`

---

## Candidate Rankings (Snapshot Scan)

Top 10 from live scan (`candidates=50`, `max_size=50`, `buffer=0.01`,
`threshold=0.99`):

| Rank | Market | Exec | Edge | Depth | BestEdge | MaxDepth YES/NO |
|---|---|---|---|---|---|---|
| 1 | will-the-toronto-maple-leafs-win-the-2026-nhl-stanley-cup | 0 | 0 | 1 | -0.0110 | 11924 / 130961 |
| 2 | will-the-vancouver-canucks-win-the-2026-nhl-stanley-cup | 0 | 0 | 1 | -0.0110 | 5252 / 94902 |
| 3 | will-the-calgary-flames-win-the-2026-nhl-stanley-cup | 0 | 0 | 1 | -0.0110 | 3939 / 96450 |
| 4 | will-the-nashville-predators-win-the-2026-nhl-stanley-cup | 0 | 0 | 1 | -0.0110 | 2296 / 52695 |
| 5 | will-the-st-louis-blues-win-the-2026-nhl-stanley-cup | 0 | 0 | 1 | -0.0110 | 2267 / 65497 |
| 6 | will-the-new-york-rangers-win-the-2026-nhl-stanley-cup | 0 | 0 | 1 | -0.0110 | 1679 / 66880 |
| 7 | will-the-tampa-bay-lightning-win-the-2026-nhl-stanley-cup | 0 | 0 | 1 | -0.0110 | 3302 / 1604 |
| 8 | gta-vi-released-before-june-2026 | 0 | 0 | 1 | -0.0110 | 1480 / 2234 |
| 9 | will-bitcoin-hit-1m-before-gta-vi-872 | 0 | 0 | 1 | -0.0110 | 74017 / 1164 |
| 10 | will-the-philadelphia-flyers-win-the-2026-nhl-stanley-cup | 0 | 0 | 1 | -0.0110 | 1098 / 1959 |

Note: 34 of 50 live markets scanned had at least one signal dimension > 0
(Depth). None had Edge > 0 or Exec > 0.

---

## Tapes Recorded

| Tape | Path | event_count | frame_count |
|---|---|---|---|
| Toronto Maple Leafs | `artifacts/simtrader/tapes/20260307T195039Z_will-the-toronto-map/` | 80 | 93 |
| Vancouver Canucks | `artifacts/simtrader/tapes/20260307T195542Z_will-the-vancouver-c/` | 66 | 70 |
| Calgary Flames | `artifacts/simtrader/tapes/20260307T200105Z_will-the-calgary-fla/` | 30 | 76 |

Asset IDs per tape (from `meta.json`):

**Toronto** (YES / NO):
- `32761305560497515266298907010603238583784271883422104419001315861857080693737`
- `30580289066077385758914266674062143052968657613582607009092130555241353168752`

**Vancouver** (YES / NO):
- `57745051474175280715827307490433711376781914565134185656043688787803746924931`
- `57570727462566321730404354146447303221727390678709525312520457788305050508188`

**Calgary** (YES / NO):
- `54811975275387163364864047298373893386525828579003336506827163723659384966681`
- `17418807248757707943441849488237613682726174832918019086909228030480182452290`

Note: Calgary resolve encountered a Gamma API read timeout (retried successfully
before recording began).

---

## Eligibility Verdicts

### Orchestrator summary output

```
Market                                       | Status      | Detail
-----------------------------------------------------------------------------------------------------------------------
will-the-toronto-maple-leafs-win-the-2026-nh | INELIGIBLE  | no positive edge: yes_ask + no_ask never < 0.99 (min sum_ask seen=1.001)
will-the-vancouver-canucks-win-the-2026-nhl- | INELIGIBLE  | no positive edge: yes_ask + no_ask never < 0.99 (min sum_ask seen=1.001)
will-the-calgary-flames-win-the-2026-nhl-sta | INELIGIBLE  | no positive edge: yes_ask + no_ask never < 0.99 (min sum_ask seen=1.001)
-----------------------------------------------------------------------------------------------------------------------
Candidates: 3  |  Eligible: 0
```

### Tape scan stats (multi-tick over full tape duration)

```
Market                                 |   Exec |   Edge |  Depth |  BestEdge |  MaxDepth YES/NO
------------------------------------------------------------------------------------------------
20260307T195039Z_will-the-toronto-map  |      0 |      0 |     77 |   -0.0110 |   130961 / 11924
20260307T195542Z_will-the-vancouver-c  |      0 |      0 |     65 |   -0.0110 |     94902 / 5769
20260307T200105Z_will-the-calgary-fla  |      0 |      0 |     29 |   -0.0110 |     3939 / 96450
```

All three tapes:
- `ticks_with_depth_ok`: >= 29 (depth condition satisfied throughout)
- `ticks_with_edge_ok`: 0
- `ticks_with_depth_and_edge`: 0 (executable ticks)
- `min_sum_ask_seen`: 1.001 on all three

---

## Full Historical Tape Scan

Running `scan-gate2-candidates --tapes-dir artifacts/simtrader/tapes --all`
against all 12 tapes ever recorded (9 previous + 3 new):

| Tape | Exec | Edge | Depth | BestEdge | MaxDepth YES/NO |
|---|---|---|---|---|---|
| 20260307T195039Z_will-the-toronto-map | 0 | 0 | 77 | -0.0110 | 130961 / 11924 |
| 20260307T195542Z_will-the-vancouver-c | 0 | 0 | 65 | -0.0110 | 94902 / 5769 |
| 20260307T200105Z_will-the-calgary-fla | 0 | 0 | 29 | -0.0110 | 3939 / 96450 |
| 20260305T223919Z_shadow_will-the-oklahoma-ci | 0 | 0 | 21 | -0.0200 | 34448 / 51368 |
| 20260305T223428Z_shadow_will-the-oklahoma-ci | 0 | 0 | 17 | -0.0200 | 34448 / 51379 |
| 20260306T044247Z_tape_bitboy-convicted | 0 | 0 | 0 | -0.0110 | 216 / 20 |
| 20260306T044313Z_tape_bitboy-convicted | 0 | 0 | 0 | -0.0110 | 20 / 216 |
| 20260306T044438Z_tape_bitboy-convicted | 0 | 0 | 0 | -0.0110 | 20 / 110 |
| 20260226T181825Z_shadow_10167699 | 0 | 0 | 0 | -0.0170 | 108 / 5 |
| 20260225T234032Z_shadow_97449340 | 0 | 0 | 0 | -0.0180 | 22 / 19 |
| 20260306T003541Z_tape_bitboy-convicted | 0 | 0 | 0 | -0.0250 | 2 / 15 |
| 20260306T003627Z_tape_bitboy-convicted | 0 | 0 | 0 | -0.0250 | 2 / 15 |

**Across all 12 tapes ever recorded: 0 executable ticks, 0 edge ticks.**

---

## Failure Analysis

### Primary blocker: No positive edge

The `binary_complement_arb` strategy under the `sane` preset requires:

```
yes_best_ask + no_best_ask < 1 - 0.01 = 0.99
```

Across all 3 new tapes, the minimum observed sum_ask was **1.001**. The gap
to cross the edge threshold is **1.1 cents** (sum_ask must fall by 0.011 from
1.001 to below 0.99).

This is **not** a depth problem. The NHL playoff markets have massive liquidity:
- Toronto: 130,961 shares on the dominant leg
- Vancouver: 94,902 shares on the dominant leg
- Calgary: 96,450 shares on the dominant leg

All these markets carry far more than the required 50-share depth at all ticks.

### Why sum_ask = 1.001 is structural

On a fair binary market:
- YES ask = 1 - YES bid
- NO ask  = 1 - NO bid
- YES ask + NO ask = 2 - (YES bid + NO bid)

If YES and NO are complementary (YES bid + NO bid ≈ 1.0), then:
- sum_ask ≈ 2 - 1.0 = 1.0

The 0.01 spread per leg pushes sum_ask to ~1.01. The `sane` preset needs
the market to be mispriced by more than 1 cent (after buffer) — i.e., the
YES + NO ask total must fall below 0.99 rather than the typical ~1.001.

The current NHL playoff markets are efficiently priced with normal market-maker
spreads. The edge condition can only be satisfied when:
1. There is active price discovery (a news event shifts fair value), AND
2. Market makers on one side have not caught up, creating a window where
   the YES and NO asks sum to below 1.0 - buffer.

### Why these markets were still worth recording

- The snapshot scan had no markets with BestEdge > -0.01 (no near-misses)
- Recording was still correct: a snapshot scan is a single point in time;
  the tape captures 300 seconds of tick-by-tick data
- The consistent BestEdge = -0.0110 across the full 300-second windows
  confirms these markets are not volatile enough right now to create an
  arb window

---

## Gate 2 Status

**Gate 2: FAILED (unchanged)**

No eligible tape found. The Gate 2 sweep was not run.
The existing `artifacts/gates/sweep_gate/gate_failed.json` remains in place.

---

## Next Blocker (from evidence, not guesswork)

The **edge condition** is the binding constraint. It requires:

```
yes_ask + no_ask < 0.99
```

Observed across 12 tapes and a 50-market live snapshot:
- Best case: sum_ask = 1.001 (1.1 cents above threshold)
- All markets: BestEdge in range [-0.011, -0.025]

**The market environment right now does not produce complement-arb edge.**

To find an eligible tape, the operator needs a binary market during a period
of **active price dislocation** — typically within minutes of a significant
news event that moves the fair value of one leg faster than market makers
can reprice the other.

Suggested next actions (in priority order):

1. **Wait for a catalyst.** Monitor breaking news events tied to live binary
   markets (elections, sports scores, regulatory decisions). Run
   `prepare-gate2 --dry-run` immediately after a catalyst to check candidates.

2. **Scan more aggressively.** Run `scan-gate2-candidates --candidates 100 --top 30`
   to widen the market universe. Not all Polymarket binaries may appear in the
   default 50-market scan.

3. **Time the scan differently.** Run during US market open, major sports
   events, or around political news cycles where binary market prices are
   more likely to diverge.

4. **Do NOT** lower `max_size`, `buffer`, or the 70% profitable scenario
   threshold. The gate criteria are correct; the market environment needs
   to provide the edge, not the thresholds.

---

## No Code Changes

No strategy logic, preset sizing, gate thresholds, or tooling was modified.
All tooling used as-is per the constraint.
