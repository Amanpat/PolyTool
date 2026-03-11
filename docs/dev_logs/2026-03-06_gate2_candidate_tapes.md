# Gate 2 Candidate Tapes Scan (2026-03-06)

## Objective
Rank locally available tapes/markets for a Gate 2 rerun under the **current** strategy settings:
- strategy: `binary_complement_arb`
- preset: `sane`
- required leg size: `max_size=50`
- entry threshold: `yes_ask + no_ask < 1 - buffer = 0.99` (`buffer=0.01`)

No strategy/tape changes were made.

## Inputs Read
- Prior diagnosis:
  - `docs/dev_logs/2026-03-06_gate2_sweep_failure_diagnosis.md`
- Gate/sweep metadata:
  - `artifacts/gates/sweep_gate/gate_failed.json`
  - `artifacts/simtrader/sweeps/*/sweep_manifest.json`
  - `artifacts/simtrader/sweeps/*/sweep_summary.json`
  - `artifacts/simtrader/sweeps/20260306T003627Z_sweep_bitboy-convicted_quick_8dfc0f9e/runs/fee0-cancel0-bid/best_bid_ask.jsonl`
- Tape metadata + events:
  - `artifacts/simtrader/tapes/*/meta.json`
  - `artifacts/simtrader/tapes/*/events.jsonl`
- Strategy requirements:
  - `packages/polymarket/simtrader/strategy_presets.py`
  - `packages/polymarket/simtrader/strategies/binary_complement_arb.py`
- Market picker behavior/output presence:
  - `packages/polymarket/simtrader/market_picker.py`
  - `tools/cli/simtrader.py`

## Market Picker Output Availability
- `quickrun_context` is present for the recent bitboy artifacts and shows `selection_mode=auto_pick`, `max_candidates=20`.
- `list_candidates=0` in those contexts, so no persisted candidate list artifact exists for this run.

## Method
For each tape directory under `artifacts/simtrader/tapes`:
1. Resolve YES/NO token IDs from `quickrun_context`/`shadow_context`; when `meta.json` was missing, infer IDs from first book snapshots in `events.jsonl`.
2. Replay `events.jsonl` through local L2 books.
3. At each tick with both books available, compute:
   - YES best ask price/size
   - NO best ask price/size
   - complement sum `yes_ask + no_ask`
4. Score executability:
   - `depth_ticks`: both best-ask sizes `>= 50`
   - `edge_ticks`: `yes_ask + no_ask < 0.99`
   - `executable_ticks`: both conditions true in the same tick
5. Track continuity (`bbo_ticks`, tape duration, max gap).

## Ranked Candidate Short List (Best -> Worst)

### 1) `will-the-oklahoma-city-thunder-win-the-2026-nba-finals`
- Best tape: `artifacts/simtrader/tapes/20260305T223919Z_shadow_will-the-oklahoma-city-thunder-win-t_fde7b16a/events.jsonl`
- Evidence:
  - `depth_ticks=21/21` (both legs satisfy `>=50`)
  - best observed sum ask: `1.01` (edge gap: `+0.02` vs `0.99`)
  - `edge_ticks=0`, `executable_ticks=0`
  - continuity: `22` events, `231.276s` span
- Verdict: **closest structurally** (depth is adequate), but still not runnable for Gate 2 because edge never appears.

### 2) `bitboy-convicted`
- Best tape: `artifacts/simtrader/tapes/20260306T044438Z_tape_bitboy-convicted_64fd7c95/events.jsonl`
- Evidence:
  - `depth_ticks=0/76` (best-ask sizes at best edge snapshot: YES `20`, NO `20`)
  - best observed sum ask: `1.001` (edge gap: `+0.011`)
  - `edge_ticks=0`, `executable_ticks=0`
  - continuity: `77` events, `19.989s` span (dense but still non-executable)
- Verdict: edge is closer than thunder, but hard-blocked by depth on both legs.

### 3) `will-trump-deport-less-than-250000`
- Tape: `artifacts/simtrader/tapes/20260226T181825Z_shadow_10167699/events.jsonl`
- Evidence:
  - `depth_ticks=0/140` (best-ask size bottleneck on NO leg: `5`)
  - best observed sum ask: `1.007` (edge gap: `+0.017`)
  - `edge_ticks=0`, `executable_ticks=0`
  - continuity: `141` events, `299.731s` span
- Verdict: long/active tape, but never satisfies edge and fails NO-leg depth for `max_size=50`.

### 4) Unknown slug (from `20260225T234032Z_shadow_97449340`)
- Tape: `artifacts/simtrader/tapes/20260225T234032Z_shadow_97449340/events.jsonl`
- Evidence:
  - `depth_ticks=0/13` (best-ask sizes `18.8` and `22.31`)
  - best observed sum ask: `1.008` (edge gap: `+0.018`)
  - `edge_ticks=0`, `executable_ticks=0`
  - continuity: sparse/uneven (`max_gap_s=122.662`)
- Verdict: not suitable.

## Full Tape-Level Ranking (All Local Tapes)
1. `20260305T223919Z_shadow_will-the-oklahoma-city-thunder-win-t_fde7b16a` (depth passes, no edge)
2. `20260305T223428Z_shadow_will-the-oklahoma-city-thunder-win-t_fde7b16a` (depth passes, no edge)
3. `20260306T044438Z_tape_bitboy-convicted_64fd7c95` (no depth, no edge)
4. `20260306T044313Z_tape_bitboy-convicted_64fd7c95` (no depth, no edge)
5. `20260306T044247Z_tape_bitboy-convicted_64fd7c95` (no `meta.json`; inferred IDs; no depth, no edge)
6. `20260226T181825Z_shadow_10167699` (no depth, no edge)
7. `20260225T234032Z_shadow_97449340` (no depth, no edge)
8. `20260306T003627Z_tape_bitboy-convicted_64fd7c95` (no depth, no edge)
9. `20260306T003541Z_tape_bitboy-convicted_64fd7c95` (no depth, no edge)

## Suitability Conclusion
No currently available local tape is suitable for a **real** Gate 2 rerun under current `binary_complement_arb` `sane` settings.

Hard facts:
- `edge_ticks > 0` in **0/9** tapes.
- `executable_ticks > 0` in **0/9** tapes.
- Only thunder tapes satisfy depth, but they still never satisfy the complement-edge condition.

## Commands / Scripts Used
```powershell
# Strategy requirement checks
Get-Content packages/polymarket/simtrader/strategy_presets.py
Get-Content packages/polymarket/simtrader/strategies/binary_complement_arb.py

# Tape/sweep metadata discovery
Get-ChildItem artifacts/simtrader/tapes -Directory
Get-Content artifacts/gates/sweep_gate/gate_failed.json
Get-Content artifacts/simtrader/sweeps/*/sweep_manifest.json
Get-Content artifacts/simtrader/sweeps/*/sweep_summary.json

# Best-bid/ask artifact spot-check
Get-Content artifacts/simtrader/sweeps/20260306T003627Z_sweep_bitboy-convicted_quick_8dfc0f9e/runs/fee0-cancel0-bid/best_bid_ask.jsonl -TotalCount 10

# One-off Python replay script (run inline) to compute per-tape depth/edge/executability metrics
@' ... replay events.jsonl through L2 books and score ticks ... '@ | python -
```
