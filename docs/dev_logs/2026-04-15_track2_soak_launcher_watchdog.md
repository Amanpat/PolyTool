# 2026-04-15 Track 2 Soak Launcher Watchdog

## Summary

Hardened the `crypto-pair-await-soak` entrypoint into a single safe command
for launching a full 24h paper soak with validated defaults. Previously the
launcher produced a bare-bones command that omitted `--auto-report`,
`--sink-enabled`, a proper 24h duration, and a 30-minute heartbeat interval.
Operators had to remember all these flags manually or risk an incomplete soak.
This work packet upgrades the launcher to emit the full runbook-grade paper
soak command by default, validates the kill switch is clear before launching,
and surfaces the `verdict.json` path in post-run output so the operator can
immediately triage results.

## Files Changed

### `packages/polymarket/crypto_pairs/await_soak.py`

- Added `DEFAULT_SOAK_DURATION_SECONDS = 86400` (24h) and
  `DEFAULT_SOAK_HEARTBEAT_SECONDS = 1800` (30min). Old constants kept as
  backward-compat aliases.
- Expanded `AwaitSoakLaunchPlan` dataclass with `auto_report`, `sink_enabled`,
  and `max_capital_window_usdc` fields (all default-safe).
- Added `launched_run_verdict` field to `AwaitSoakLaunchResult`.
- `build_coinbase_smoke_soak_launch_plan()` now defaults to 24h/30min and
  conditionally appends `--auto-report`, `--sink-enabled`, and
  `--max-capital-window-usdc` to the argv/display_argv tuples.
- Added `validate_soak_prerequisites(kill_switch_path)` which reads the kill
  switch file and returns a list of blocking issues (empty = all clear).
  Truthy values checked: `"1"`, `"true"`, `"yes"`, `"on"`. Missing or empty
  file passes.
- `run_crypto_pair_await_soak()` now: accepts `auto_report`, `sink_enabled`,
  `max_capital_window_usdc`, `kill_switch_path`, and `_validate_fn` params;
  runs preflight check after markets are found; returns `status=preflight_failed`
  with exit_code=1 if kill switch is tripped without launching; extracts
  `report_verdict` from child output via `_extract_cli_value` and prints it
  alongside the `verdict_json` path.

### `tools/cli/crypto_pair_await_soak.py`

- Updated imports to use `DEFAULT_SOAK_DURATION_SECONDS` and
  `DEFAULT_SOAK_HEARTBEAT_SECONDS`.
- Added CLI flags: `--auto-report` / `--no-auto-report` (default on),
  `--sink-enabled` (default off), `--heartbeat-minutes` (default 30),
  `--max-capital-window-usdc` (optional float), `--kill-switch` (path string).
- `main()` converts `--heartbeat-minutes` to seconds and wires all new params
  through to `run_crypto_pair_await_soak()`.

### `tests/test_crypto_pair_await_soak.py`

- Updated `test_launch_command_construction_uses_standard_coinbase_smoke_soak_defaults`
  to assert new heartbeat (1800s) and `--auto-report` in argv.
- Added 10 new deterministic offline tests (see below).

## Commands Run and Results

### Targeted test suite

```
python -m pytest tests/test_crypto_pair_await_soak.py -v --tb=short
```

Result: **17 passed, 0 failed** in 0.40s

### Crypto-pair regression slice

```
python -m pytest tests/test_crypto_pair_await_soak.py tests/test_crypto_pair_soak_workflow.py
  tests/test_crypto_pair_run.py tests/test_crypto_pair_risk_controls.py
  tests/test_crypto_pair_report.py -v --tb=short
```

Result: **64 passed, 0 failed** in 2.66s

### CLI smoke test

```
python -m polytool --help          # CLI loads, crypto-pair-await-soak listed
python -m polytool crypto-pair-await-soak --help  # All new flags visible
```

Result: CLI loads cleanly. All new flags present:
`--auto-report`, `--no-auto-report`, `--sink-enabled`, `--heartbeat-minutes`,
`--max-capital-window-usdc`, `--kill-switch`.

## New Tests Added (10)

1. `test_default_launch_plan_includes_auto_report_and_24h_duration` — no-arg
   call produces 86400s duration, 1800s heartbeat, `--auto-report` in argv.
2. `test_launch_plan_with_sink_enabled` — `--sink-enabled` appears when set.
3. `test_launch_plan_with_capital_window` — `--max-capital-window-usdc 25.0`
   appended correctly.
4. `test_launch_plan_without_auto_report` — `--auto-report` absent when
   `auto_report=False`.
5. `test_preflight_blocks_on_tripped_kill_switch` — `validate_soak_prerequisites`
   returns non-empty list when file contains `"1"`.
6. `test_preflight_passes_when_kill_switch_absent` — empty list when no file.
7. `test_preflight_passes_when_kill_switch_file_empty` — empty list when file
   is blank.
8. `test_await_soak_refuses_launch_on_tripped_kill_switch` — `run_crypto_pair_await_soak`
   returns `status=preflight_failed`, `exit_code=1`, `launched=False` when
   kill switch is tripped; launcher is never called.
9. `test_verdict_extracted_from_child_output` — `launched_run_verdict` and
   `launched_run_verdict_json_path` populated in manifest from child output.
10. `test_no_live_flag_in_hardened_launch_command` — `--live` never appears
    in `argv` or `display_argv` even with all optional flags enabled.

## Operator Friction Removed

Before this change, a correct 24h paper soak required manually adding four
flags that were easy to forget:

```
python -m polytool crypto-pair-await-soak \
  --duration-seconds 86400 \
  --heartbeat-minutes 30 \
  ...  # also had to remember --auto-report on the wrapped crypto-pair-run call
```

After this change, the default command is:

```
python -m polytool crypto-pair-await-soak
```

This automatically produces:
- 24h duration (`--duration-seconds 86400`)
- 30-min heartbeat (`--heartbeat-seconds 1800`)
- Auto-report (`--auto-report`)
- Kill switch preflight check before launch
- Verdict text and `paper_soak_verdict.json` path printed after the child exits

Operator no longer needs to inspect the artifact directory manually to find
the verdict; it is printed to stdout at the end of the run.

## Remaining Gaps Before Live Use

These are unchanged from prior dev logs and are pre-conditions for live
deployment, not soak launchers:

- **EU VPS**: Deployment latency assumptions require an EU-based VPS.
- **Oracle mismatch**: Coinbase reference feed vs Chainlink on-chain settlement
  oracle discrepancy not yet resolved.
- **Micro-live scaffold**: Stage 0 / micro-live execution scaffolding not yet
  built.
- **SOL adverse selection review**: SOL-specific adverse selection patterns
  flagged for review before capital deployment.
- **Active markets**: Live deployment requires BTC/ETH/SOL 5m/15m markets to
  be available on Polymarket (12 returned as of 2026-04-14).

## Codex Review Note

Tier: Skip (no execution, risk, order-placement, or kill_switch.py code
touched). All changes confined to the await_soak launcher module and its CLI.
No mandatory Codex review required per policy.
