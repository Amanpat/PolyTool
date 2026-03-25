# Dev Log: Phase 1A Crypto Pair Soak Launch v0

**Date:** 2026-03-23  
**Track:** Track 2 / Phase 1A

## Files Changed And Why

| File | Why |
|------|-----|
| `tools/cli/crypto_pair_run.py` | Added soak-launch duration parsing, heartbeat/status formatting, paper-only `--auto-report`, graceful report handoff, and final artifact-path printing. |
| `packages/polymarket/crypto_pairs/paper_runner.py` | Added paper heartbeat snapshots, `runner_heartbeat` runtime events, `KeyboardInterrupt` graceful finalization, and heartbeat settings plumbing. |
| `packages/polymarket/crypto_pairs/reporting.py` | Added shared graceful paper-stop handling plus report-artifact path helpers so manual paper stops can still auto-report cleanly. |
| `tests/test_crypto_pair_run.py` | Added offline coverage for duration-based stop windows, heartbeat emission, and graceful operator-interrupt finalization. |
| `tests/test_crypto_pair_report.py` | Added coverage that `operator_interrupt` is treated as a graceful stop instead of a report-time safety violation. |
| `tests/test_crypto_pair_soak_workflow.py` | Added end-to-end paper soak workflow coverage for auto-report artifact writing plus CLI flag parsing and heartbeat/status printing. |
| `docs/features/FEATURE-crypto-pair-soak-launch-v0.md` | Documented the new soak-launch flags, heartbeat payload, graceful exit behavior, and operator-facing outputs. |
| `docs/dev_logs/2026-03-23_phase1a_crypto_pair_soak_launch_v0.md` | Recorded implementation scope, commands run, test counts, new flags, heartbeat/report behavior, and next questions. |

## Commands Run And Output

| Command | Output |
|---------|--------|
| `python -m polytool crypto-pair-run --help` | Printed the new duration/heartbeat/auto-report flags: `--duration-minutes`, `--duration-hours`, `--heartbeat-seconds`, `--heartbeat-minutes`, `--auto-report`. |
| `python -m polytool crypto-pair-report --help` | Printed the existing `--run PATH` artifact-first report help. |
| `python -m pytest tests/test_crypto_pair_run.py tests/test_crypto_pair_report.py tests/test_crypto_pair_soak_workflow.py -q` | `11 passed in 0.78s` |
| `python -m pytest tests/test_crypto_pair_scan.py tests/test_crypto_pair_paper_ledger.py tests/test_crypto_pair_run.py tests/test_crypto_pair_live_safety.py tests/test_crypto_pair_reference_feed.py tests/test_crypto_pair_fair_value.py tests/test_crypto_pair_accumulation_engine.py tests/test_crypto_pair_backtest.py tests/test_crypto_pair_clickhouse_sink.py tests/test_crypto_pair_runner_events.py tests/test_crypto_pair_report.py tests/test_crypto_pair_soak_workflow.py -q` | `235 passed in 8.68s` |

## Test Results

| Scope | Result |
|------|--------|
| `tests/test_crypto_pair_run.py` + `tests/test_crypto_pair_report.py` + `tests/test_crypto_pair_soak_workflow.py` | PASS (`11/11`) |
| Requested Track 2 regression slice | PASS (`235/235`) |
| `crypto-pair-run --help` smoke | PASS |
| `crypto-pair-report --help` smoke | PASS |

## New CLI Flags

- `--duration-hours`
- `--duration-minutes`
- `--duration-seconds`
  - now acts as one duration component; the three duration flags sum together
  - if all are omitted, default runtime remains `30` seconds
- `--heartbeat-minutes`
- `--heartbeat-seconds`
  - sum together
  - default is disabled
- `--auto-report`
  - paper-only
  - runs the existing local report path after graceful exit

## Heartbeat And Report Behavior

### Heartbeat

When `heartbeat_interval_seconds > 0`, the paper runner now:

- emits `runner_heartbeat` entries into `runtime_events.jsonl`
- invokes the CLI heartbeat callback for stdout status lines
- includes:
  - elapsed runtime
  - cycle number
  - opportunities observed
  - intents generated
  - completed pairs
  - partial exposure count
  - open pair count
  - latest feed states
  - stale symbol list

Heartbeat output is artifact-backed through `runtime_events.jsonl`, so soak-time
stdout and local artifacts report the same operator status.

### Graceful Stop And Auto-Report

The paper runner now catches `KeyboardInterrupt`, finalizes artifacts, records
`stopped_reason="operator_interrupt"`, and writes an `operator_interrupt`
runtime event.

`reporting.py` now treats these paper stop reasons as graceful:

- `completed`
- `operator_interrupt`

When `--auto-report` is enabled and the paper run exits gracefully, the CLI:

- generates `paper_soak_summary.json`
- generates `paper_soak_summary.md`
- persists the `auto_report` result into `run_manifest.json`
- prints `manifest_path`, `run_summary`, `report_json`, `report_md`, and report verdict

Non-graceful paper stops leave artifacts finalized but skip auto-report with
`skipped_reason="non_graceful_stop"`.

## Open Questions For Next Prompt

1. Should the soak launcher add a small operator-facing status file outside the
   per-run directory so a long soak can be tailed without finding the active
   `run_id` first?
2. Should `--auto-report` fail closed exactly as implemented now, or should it
   optionally downgrade report-generation failures to warnings after the run
   artifacts are already finalized?
3. The heartbeat is cycle-bound today; confirm whether the next packet should
   add sub-cycle scheduling if cycle intervals become longer than the desired
   operator heartbeat cadence.
