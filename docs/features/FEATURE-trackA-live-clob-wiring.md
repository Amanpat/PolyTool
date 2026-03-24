# Track A: Live CLOB Wiring + Gate Harness

Date: 2026-03-05 (code complete); gate status last updated 2026-03-08
Status: Code Complete / Gates Pending

## Summary

Track A has real CLOB wiring, a gated live execution path, a market selection
CLI, and an operator-facing gate harness. Sprint-end validation was 1188
passing tests. Stage 1 capital remains blocked until all four gates pass and
Stage 0 paper-live completes cleanly.

**Phase 1 mainline strategy**: `market_maker_v0` (Avellaneda-Stoikov market
maker). `binary_complement_arb` is used as a Gate 2 scouting vehicle to detect
complement-arb dislocations in the tape; it is not the Phase 1 live strategy.

## What was built

- `packages/polymarket/simtrader/execution/wallet.py`: `build_client()` reads `PK` from the environment and returns a `ClobClient`; `derive_and_print_creds()` supports one-time credential setup and includes an import guard with a pip install hint.
- `packages/polymarket/simtrader/execution/live_executor.py`: accepts an optional `real_client`; live create/cancel calls route to the real client only when `dry_run=False`.
- `packages/polymarket/simtrader/execution/risk_manager.py`: adds `inventory_skew_limit_usd`, tracks the last fill price, and rejects orders when net inventory notional breaches the configured cap.
- `packages/polymarket/simtrader/strategies/market_maker_v0.py`: upgraded from BBO-only quoting to an Avellaneda-Stoikov market maker with microprice, rolling variance, resolution guard, and bounded spreads.
- `packages/polymarket/market_selection/`: new scorer, filters, and Gamma API client package behind `python -m polytool market-scan`.
- `tools/gates/`: replay, sweep, dry-run, and gate-status scripts plus the manual shadow checklist.
- `tools/cli/simtrader.py`: adds `--live`, gate artifact enforcement, wallet loading, `CONFIRM`, USD risk flags, and `python -m polytool simtrader kill`.
- [LIVE_DEPLOYMENT_STAGE1.md](../runbooks/LIVE_DEPLOYMENT_STAGE1.md): Stage 1 live deployment operator runbook.

## Gate status (as of 2026-03-08)

The table below reflects the current authoritative status. See `docs/ROADMAP.md`
and `docs/CURRENT_STATE.md` for the full gate narrative.

| Gate | Status | Notes |
|------|--------|-------|
| Gate 1 — Replay Determinism | **PASSED** | Artifact at `artifacts/gates/replay_gate/gate_passed.json`. |
| Gate 2 — Scenario Sweep | NOT PASSED | Tooling ready; blocked on an eligible tape with `executable_ticks > 0`. |
| Gate 3 — Shadow Mode | BLOCKED | Blocked behind Gate 2; follow `tools/gates/shadow_gate_checklist.md` after Gate 2 passes. |
| Gate 4 — Dry-Run Live | **PASSED** | Artifact at `artifacts/gates/dry_run_gate/gate_passed.json`. |

Historical snapshot from 2026-03-05 (this feature doc's original date) showed
Gates 1 and 2 as "OPEN" and Gate 3 as "90% COMPLETE". Those labels are
superseded by the 2026-03-07 gate status in ROADMAP.md and CURRENT_STATE.md.

## How to check gate status

```bash
python tools/gates/gate_status.py
```

`gate_status.py` exits 0 only when all four gate directories contain a passing
artifact.

## References

- Full deployment steps: [docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md](../runbooks/LIVE_DEPLOYMENT_STAGE1.md)
- Construction Manual context: PDF Construction Manual Sections 2-4 and 7
- Local mapping note: [docs/archive/MASTER_CONSTRUCTION_MANUAL_MAPPING.md](../archive/MASTER_CONSTRUCTION_MANUAL_MAPPING.md)
