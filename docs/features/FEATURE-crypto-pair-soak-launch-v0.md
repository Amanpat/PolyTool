# Feature: Crypto Pair Soak Launch v0

## Purpose

`python -m polytool crypto-pair-run` now has paper-soak launch ergonomics for
the first real 24 to 48 hour Track 2 soak:

- soak-friendly duration flags
- periodic heartbeat/status output
- optional auto-report on graceful paper exit

The command remains paper-first and does not require ClickHouse.

## New CLI Flags

- `--duration-hours N`
- `--duration-minutes N`
- `--duration-seconds N`
  - duration components are additive
  - if all duration flags are omitted, the default remains `30` seconds
- `--heartbeat-minutes N`
- `--heartbeat-seconds N`
  - heartbeat components are additive
  - if omitted, heartbeat output is disabled
- `--auto-report`
  - paper mode only
  - on graceful exit, runs the existing local artifact report and prints the
    generated summary paths

## Heartbeat Output

When heartbeat output is enabled, the runner emits operator-facing status lines
and records matching `runner_heartbeat` runtime events.

Each heartbeat includes:

- elapsed runtime
- cycle number
- opportunities observed
- intents generated
- completed pairs so far
- partial exposure count
- latest per-symbol feed state
- stale symbols, if any

## Graceful Exit Behavior

Two paper stop reasons are treated as graceful:

- `completed`
- `operator_interrupt`

On graceful paper exit, `--auto-report` writes:

- `paper_soak_summary.json`
- `paper_soak_summary.md`

The runner also prints:

- `artifact_dir`
- `manifest_path`
- `run_summary`
- report paths when auto-report runs

## Safe Defaults

- paper mode remains the default
- no ClickHouse dependency is required
- live runner guardrails are unchanged
- heartbeat/report behavior is opt-in for live-invariant safety

## Example

```bash
python -m polytool crypto-pair-run ^
  --duration-hours 24 ^
  --heartbeat-minutes 5 ^
  --auto-report
```

This produces a long-running paper soak with periodic operator status output and
automatic local summary artifacts when the run exits cleanly.
