# Gate 2 Preset Sizing Sanity Check (2026-03-06)

## Scope

Sanity-check whether the current Gate 2 `binary_complement_arb` preset size
(`strategy_preset=sane`, `max_size=50`) looks aligned with the repo's current
capital-stage assumptions and conservative validation philosophy.

This is docs analysis only. No preset, threshold, or code changes were made.

## Files inspected

- `packages/polymarket/simtrader/strategy_presets.py`
- `packages/polymarket/simtrader/strategies/binary_complement_arb.py`
- `packages/polymarket/simtrader/sweeps/eligibility.py`
- `tools/cli/scan_gate2_candidates.py`
- `docs/README_SIMTRADER.md`
- `docs/ROADMAP.md`
- `docs/CURRENT_STATE.md`
- `docs/specs/SPEC-0010-simtrader-vision-and-roadmap.md`
- `docs/specs/SPEC-0011-live-execution-layer.md`
- `docs/features/FEATURE-trackA-week1-execution-primitives.md`
- `docs/dev_logs/2026-03-05_trackA_week1_execution_primitives.md`
- `docs/ARCHITECTURE.md`
- `docs/ARCHITECT_CONTEXT_PACK.md`
- `docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md`
- `README.md`
- `docs/dev_logs/2026-03-06_gate2_sweep_failure_diagnosis.md`
- `docs/dev_logs/2026-03-06_gate2_candidate_tapes.md`
- `docs/dev_logs/2026-03-06_gate2_live_acquisition_cycle.md`
- `docs/dev_logs/2026-03-06_gate2_tape_capture_playbook.md`

## Current preset size and implied notional

Current `binary_complement_arb` `sane` config:

- `buffer = 0.01`
- `max_size = 50`
- `legging_policy = wait_N_then_unwind`
- `unwind_wait_ticks = 5`
- `enable_merge_full_set = True`

Entry conditions under the current strategy/runtime path:

- both YES and NO best-ask sizes must be `>= 50`
- `yes_ask + no_ask < 1 - buffer = 0.99`
- strategy notional is computed as `sum_ask * max_size`

Implication:

- One attempted arb entry is `50` YES shares plus `50` NO shares.
- Because entry requires `sum_ask < 0.99`, combined deployed notional is
  strictly `< 49.50 USDC`.
- Gross full-set payout at resolution is `50.00 USDC`, so the gross locked-in
  edge before fees is `> 0.50 USDC` for an executable tick.
- Around a balanced market, this is roughly `~25 USDC` per leg.

Important nuance:

- The `sane` preset does not set an explicit `max_notional_usdc`.
- In practice, current size is bounded implicitly by `max_size=50` plus the
  `sum_ask < 0.99` entry rule.

## Capital-stage constraints found in docs

Current validation order is consistently documented as:

`Gate 1 replay -> Gate 2 sweep -> Gate 3 shadow -> Gate 4 dry-run live -> Stage 0 72h paper-live -> Stage 1 live capital`

Relevant stage constraints:

- No live capital is allowed before all gates pass and Stage 0 completes cleanly.
- Stage 0 is explicitly a `72 hour` zero-capital / dry-run paper-live stage.
- Stage 1 is the first live-capital stage and is described as a minimal cap.
- Current docs pin Stage 1 at `500 USDC`.

Current documented Stage 1 operator limits:

- `--max-position-usd 500`
- `--daily-loss-cap-usd 100`
- `--max-order-usd 200`
- `--inventory-skew-limit-usd 400`

Current documented conservative Stage-0 live-execution defaults:

- `--max-order-usd 25`
- `--max-position-usd 100`
- `--daily-loss-cap-usd 15`
- small/default safety-first caps before any real capital deployment

## Sanity check against current project stage

### 1. Relative to capital stage

`50` shares does **not** look oversized relative to the repo's current
capital-stage assumptions.

Why:

- Gate 2 happens before any live capital and before Stage 0; this is a
  validation executability threshold, not a live bankroll allocation.
- The implied pair spend for an executable arb is `< 49.50 USDC`, which is only
  about `10%` of the documented Stage 1 `500 USDC` capital envelope.
- That combined spend is also well below the documented Stage 1
  `--max-position-usd 500`.
- In balanced markets, `50` shares implies about `~25 USDC` per leg, which is
  very close to the documented conservative Stage-0 `--max-order-usd 25`
  default.

One caveat:

- If one leg is far above `0.50`, that single 50-share order can exceed the
  Stage-0 `25 USDC` per-order default.
- That does not create a current mismatch by itself, because Gate 2 is not a
  live-capital path and `binary_complement_arb` is not currently documented as a
  Stage-0 live deployment strategy.

### 2. Relative to conservative validation philosophy

`50` shares looks consistent with the repo's realism-first / conservative
validation posture.

Why:

- SimTrader docs explicitly say realism assumptions skew conservative by
  default, not optimistic.
- Gate 2 tooling (`scan_gate2_candidates`, tape eligibility, tape capture
  playbook) repeatedly treats `max_size=50` as the `sane` preset's required
  executable depth and says scanner thresholds must match the strategy.
- Recent Gate 2 logs explicitly recommend **not** lowering `max_size`, `buffer`,
  or the 70% sweep threshold.
- Requiring real 50-share top-of-book depth is materially different from
  proving a toy 1-share or 5-share edge. That matches the project's current
  "strict before capital" philosophy.

### 3. What current evidence says is actually binding

Current evidence does **not** point to `50` shares being the main project-stage
misalignment.

Observed in recent Gate 2 notes:

- The original sweep failure diagnosis found both depth failure and no positive
  edge on the recorded tape.
- The broader tape scan and live acquisition cycle found markets where
  `depth >= 50` was already satisfied, but `edge_ticks` still remained `0`.
- The latest diagnosis therefore points to candidate/tape acquisition and edge
  availability as the real blocker, not an obviously oversized validation size.

## Verdict

`50` shares looks **intentional and acceptable**, not suspicious.

Reasoned verdict:

- It is small relative to the documented Stage 1 capital stage.
- It is in-family with conservative Stage-0 order sizing on a per-leg basis in
  balanced markets.
- It preserves the current validation philosophy: prove executable depth at a
  non-toy size before any live capital stage is even considered.

## Recommendation

Keep the current Gate 2 preset as-is for now.

Do **not** revisit `max_size=50` as part of the current Gate 2 unblock effort.
If a revisit is needed later, it should happen only when:

- `binary_complement_arb` is being considered for an actual Stage-0/Stage-1 live
  deployment path, or
- the project introduces explicit stage-specific sizing policy for this
  strategy.

If that later review happens, the right question is probably not "lower
`max_size`?" but "should this strategy get an explicit `max_notional_usdc` or
stage-specific risk envelope?"

## Bottom line

For the repo's current stage, `max_size=50` reads as a deliberate conservative
executability threshold, not an out-of-scale capital assumption. The current
recommendation is: **keep it unchanged and revisit only later if this strategy
graduates toward a real capital stage.**
