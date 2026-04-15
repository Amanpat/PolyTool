---
phase: quick
plan: 260415-q5s
subsystem: crypto-pair-runner
tags: [risk-controls, track2, paper-runner, position-store, cli]
dependency_graph:
  requires: [crypto-pair-runner-v0, position-store-v0, paper-ledger-v0]
  provides: [capital-window-risk-control, cumulative-notional-tracking, preflight-risk-surface]
  affects: [paper_runner.py, position_store.py, crypto_pair_run.py]
tech_stack:
  added: []
  patterns: [frozen-dataclass-validation, operator-ceiling-constant, gate-enforcement-chain]
key_files:
  created:
    - tests/test_crypto_pair_risk_controls.py
    - docs/dev_logs/2026-04-15_track2_risk_controls.md
  modified:
    - packages/polymarket/crypto_pairs/paper_runner.py
    - packages/polymarket/crypto_pairs/position_store.py
    - tools/cli/crypto_pair_run.py
decisions:
  - "max_capital_per_window_usdc on CryptoPairRunnerSettings (operator-level), not PaperModeConfig (strategy-level)"
  - "cumulative_committed_notional_usdc counts ALL intents (settled + open) for session budget correctness"
  - "operator ceiling hard-coded at 50 USDC for v0 with per-run CLI override via --max-capital-window-usdc"
metrics:
  duration: ~25 minutes
  completed: 2026-04-15T23:04:00Z
  tasks_completed: 3
  files_changed: 5
---

# Phase quick Plan 260415-q5s: Track 2 Risk Controls SUMMARY

## One-liner

Added `max_capital_per_window_usdc` session-level capital budget ceiling (50 USDC operator cap) to the crypto-pair runner, enforced via cumulative committed notional tracking across settled and open intents.

## Objective Achieved

The crypto-pair paper runner now enforces four operator risk controls:

| Control | Setting | Block reason |
|---------|---------|--------------|
| Kill switch | `kill_switch.txt` file | `kill_switch` |
| Open pairs cap | `max_open_pairs` | `open_pairs_cap_reached` |
| Daily loss cap | `daily_loss_cap_usdc` | `daily_loss_cap_reached` |
| Capital window (new) | `max_capital_per_window_usdc` | `capital_window_exceeded` |

All four are surfaced in `--dry-run` preflight output.

## Tasks Completed

### Task 1 — Settings field + enforcement gate
**Commit:** `55ad7fc`
- Added `_OPERATOR_MAX_CAPITAL_PER_WINDOW_USDC = Decimal("50")` operator ceiling constant
- Added `max_capital_per_window_usdc` field to `CryptoPairRunnerSettings` with coercion, > 0 validation, and operator ceiling validation
- Propagated through `with_artifact_base_dir()`, `to_dict()`, `build_runner_settings()`
- Added `cumulative_committed_notional_usdc()` to `CryptoPairPositionStore` (counts ALL intents regardless of settled status)
- Wired enforcement gate in `_process_opportunity()` after daily-loss-cap check

### Task 2 — CLI flag + preflight surface
**Commit:** `ee1ec97`
- Added `--max-capital-window-usdc` CLI argument
- Updated `format_preflight_summary()` to show capital window alongside other three controls
- Wired through both `--dry-run` path and normal `main()` execution path

### Task 3 — Tests + dev log
**Commit:** `c85e2b6`
- 9 deterministic offline tests in `tests/test_crypto_pair_risk_controls.py` covering all four controls, constructor validation, cumulative vs open notional semantics, and preflight surface
- Dev log at `docs/dev_logs/2026-04-15_track2_risk_controls.md`

## Verification Results

```
tests/test_crypto_pair_risk_controls.py   9 passed
tests/test_crypto_pair_run.py            23 passed
tests/test_crypto_pair_live_safety.py     4 passed
tests/test_crypto_pair_soak_workflow.py   2 passed
Total: 38 passed, 0 failed
```

Full suite (excluding crypto-pair tests): 2528 passed, 1 pre-existing failure
(`test_ris_phase2_cloud_provider_routing.py::test_gemini_provider_success` —
unrelated to this work packet, pre-dates this session).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed PaperPairSettlement field names in test 7**
- **Found during:** Task 3 test run
- **Issue:** Test used incorrect field names (`settled_at`, `yes_resolution`, `no_resolution`, `yes_proceeds_usdc`, `no_proceeds_usdc`, `total_proceeds_usdc`, `yes_filled_size`, `no_filled_size`, `yes_average_price`, `no_average_price`) that don't exist on `PaperPairSettlement`
- **Fix:** Replaced with actual dataclass fields (`resolved_at`, `winning_leg`, `paired_size`, `paired_cost_usdc`, `paired_fee_adjustment_usdc`, `paired_net_cash_outflow_usdc`, `settlement_value_usdc`, `gross_pnl_usdc`, `net_pnl_usdc`, `unpaired_leg`, `unpaired_size`)
- **Files modified:** `tests/test_crypto_pair_risk_controls.py`
- **Commit:** `c85e2b6`

## Decisions Made

1. **max_capital_per_window_usdc belongs on CryptoPairRunnerSettings** (operator-level), not on `CryptoPairPaperModeConfig` (strategy-level). Operator caps sit at the runner/settings layer alongside `daily_loss_cap_usdc` and `max_open_pairs`.

2. **Cumulative method counts all intents (settled + open)** because a session-level budget ceiling must account for capital already deployed and recovered. Using only open notional would allow re-deploying the same capital slot repeatedly without limit.

3. **50 USDC hard ceiling for v0** matches the per-pair sizing (0.5–2 USDC per pair, up to 10 pairs) leaving a reasonable safety margin. Operator can set lower via `--max-capital-window-usdc`; the ceiling prevents accidental over-exposure during early soak.

## Known Stubs

None — all four risk controls are fully wired and enforced.

## Self-Check: PASSED

- `tests/test_crypto_pair_risk_controls.py` exists: FOUND
- `docs/dev_logs/2026-04-15_track2_risk_controls.md` exists: FOUND
- Commit `55ad7fc` exists: FOUND
- Commit `ee1ec97` exists: FOUND
- Commit `c85e2b6` exists: FOUND
