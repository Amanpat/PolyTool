# Track A: Live CLOB Wiring + Gate Harness

Date: 2026-03-05
Status: Code Complete / Gates Pending

## Summary

Track A now has real CLOB wiring, a gated live execution path, a market
selection CLI, and an operator-facing gate harness. Sprint-end validation was
1188 passing tests, but Stage 1 capital remains blocked until Gates 1-3 are
closed.

## What was built

- `packages/polymarket/simtrader/execution/wallet.py`: `build_client()` reads `PK` from the environment and returns a `ClobClient`; `derive_and_print_creds()` supports one-time credential setup and includes an import guard with a pip install hint.
- `packages/polymarket/simtrader/execution/live_executor.py`: accepts an optional `real_client`; live create/cancel calls route to the real client only when `dry_run=False`.
- `packages/polymarket/simtrader/execution/risk_manager.py`: adds `inventory_skew_limit_usd`, tracks the last fill price, and rejects orders when net inventory notional breaches the configured cap.
- `packages/polymarket/simtrader/strategies/market_maker_v0.py`: upgraded from BBO-only quoting to an Avellaneda-Stoikov market maker with microprice, rolling variance, resolution guard, and bounded spreads.
- `packages/polymarket/market_selection/`: new scorer, filters, and Gamma API client package behind `python -m polytool market-scan`.
- `tools/gates/`: replay, sweep, dry-run, and gate-status scripts plus the manual shadow checklist.
- `tools/cli/simtrader.py`: adds `--live`, gate artifact enforcement, wallet loading, `CONFIRM`, USD risk flags, and `python -m polytool simtrader kill`.
- [LIVE_DEPLOYMENT_STAGE1.md](../runbooks/LIVE_DEPLOYMENT_STAGE1.md): Stage 1 live deployment operator runbook.

## Gate status

| Gate | Status | Notes |
|------|--------|-------|
| Gate 1 - Replay Determinism | OPEN | Run `python tools/gates/close_replay_gate.py`; requires live Polymarket network access. |
| Gate 2 - Scenario Sweep | OPEN | Run `python tools/gates/close_sweep_gate.py`; requires live Polymarket network access. |
| Gate 3 - Shadow Mode | 90% COMPLETE | Shadow run recorded on an OKC Thunder market; reconnect validation still needs an elevated Administrator PowerShell firewall test. |
| Gate 4 - Dry-Run Live | PASSED | Artifact present at `artifacts/gates/dry_run_gate/gate_passed.json`. |

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
