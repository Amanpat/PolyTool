# Dev Log: Phase 1A Crypto Pair Report v0

**Date:** 2026-03-23  
**Track:** Track 2 / Phase 1A

## Files Changed And Why

| File | Why |
|------|-----|
| `packages/polymarket/crypto_pairs/reporting.py` | Added the artifact-first paper-soak report loader, metric computation, explicit rubric-band logic, frozen-window safety audit, and Markdown/JSON writers. |
| `tools/cli/crypto_pair_report.py` | Added the operator CLI entrypoint: `python -m polytool crypto-pair-report --run <path>`. |
| `polytool/__main__.py` | Registered the new `crypto-pair-report` command and surfaced it in the CLI usage text. |
| `tests/test_crypto_pair_report.py` | Added offline synthetic-fixture coverage for promote, rerun, reject, and CLI output writing. |
| `docs/features/FEATURE-crypto-pair-report-v0.md` | Documented the command, artifact contract, outputs, and v0 limitations. |
| `docs/dev_logs/2026-03-23_phase1a_crypto_pair_report_v0.md` | Recorded implementation scope, commands run, test results, produced metrics, rubric mapping, and open questions. |

## Commands Run And Output

| Command | Output |
|---------|--------|
| `python -m pytest tests/test_crypto_pair_report.py -q` | `3 passed in 0.48s` |
| `python -m polytool crypto-pair-report --help` | Printed the new `--run PATH` help and description for artifact-first paper-run summarization. |
| `python -m pytest tests/test_crypto_pair_paper_ledger.py tests/test_crypto_pair_run.py tests/test_crypto_pair_backtest.py tests/test_crypto_pair_report.py -q` | `35 passed in 0.70s` |

## Test Results

| Scope | Result |
|------|--------|
| `tests/test_crypto_pair_report.py` | PASS (`3/3`) |
| Requested Track 2 regression slice | PASS (`35/35`) |
| CLI help smoke | PASS |

## Report Metrics Produced

The new report emits these operator-facing metrics:

- `soak_duration_hours`
- `opportunities_observed`
- `intents_generated`
- `completed_pairs`
- `paired_exposure_count`
- `settled_pair_count`
- `pair_completion_rate`
- `average_completed_pair_cost`
- `estimated_profit_per_completed_pair`
- `maker_fill_rate_floor`
- `partial_leg_incidence`
- `stale_count`
- `disconnect_count`
- `net_pnl_usdc`
- `safety_violation_count`

The report also writes:

- evidence-floor checks (`24h`, intents, paired exposures, settled pairs)
- per-metric rubric bands
- safety-violation findings
- final rubric verdict

Synthetic promote-fixture output used in test coverage:

- `opportunities_observed = 30`
- `intents_generated = 30`
- `completed_pairs = 30`
- `settled_pair_count = 30`
- `pair_completion_rate = 1.0`
- `average_completed_pair_cost = 0.95`
- `estimated_profit_per_completed_pair = 0.052`
- `maker_fill_rate_floor = 1.0`
- `partial_leg_incidence = 0.0`
- `stale_count = 0`
- `disconnect_count = 0`
- `safety_violation_count = 0`

## Rubric Pass / Fail Mapping

Implemented decision mapping:

- `PROMOTE TO MICRO LIVE CANDIDATE`
  - evidence floor met
  - no safety violations
  - all primary metrics in pass band
  - `net_pnl_usdc > 0`
- `RERUN PAPER SOAK`
  - no safety violation
  - no reject-band metric
  - but evidence floor fails, a metric lands in rerun band, or a required metric is unavailable from artifacts
- `REJECT CURRENT CONFIG / DO NOT PROMOTE`
  - any safety violation
  - any reject-band metric
  - unrecovered degraded feed state or frozen-window audit failure

Safety violations counted explicitly from Section 7 rubric rules:

- non-`completed` stop reason
- open unpaired exposure at finalization
- `kill_switch_tripped`
- `daily_loss_cap_reached`
- sink write failure when sink was enabled
- intent creation during a stale/disconnected frozen window

## Open Questions For Next Prompt

1. The rubric text defines completed-pair economics from `paired_cost_usdc` and
   `paired_net_cash_outflow_usdc`; confirm whether those values should stay
   literal per exposure row or be normalized by `paired_size` for larger paper
   pair sizes.
2. The current report reads feed-state counts from `runtime_events.jsonl` in
   artifact-first mode; decide whether the artifact contract should also persist
   first-class safety transition rows outside the optional sink path.
3. `settled_pair_count` remains dependent on settlement artifacts already being
   present; confirm whether paper-run finalization should start emitting
   settlements by default before the first real soak.
