# Feature: Crypto Pair Await Soak v0

## Purpose

`python -m polytool crypto-pair-await-soak` lets an operator leave Track 2 in a
safe wait state until eligible BTC/ETH/SOL 5m or 15m pair markets reappear, then
automatically launches the standard paper-only Coinbase smoke soak.

This closes the manual retry loop created by intermittent market availability.

## Default Behavior

- waits for eligible markets using the existing watcher/discovery contract
- paper only; there is no live-mode flag on this command
- launches the standard Coinbase smoke soak command:

```bash
python -m polytool crypto-pair-run --reference-feed-provider coinbase --duration-seconds 1800 --heartbeat-seconds 60
```

- exits `1` on timeout without launching
- returns the child `crypto-pair-run` exit code after launch

## CLI Usage

Leave it running with the default 1-hour wait window:

```bash
python -m polytool crypto-pair-await-soak
```

Wait longer and override the launched soak duration:

```bash
python -m polytool crypto-pair-await-soak --timeout 21600 --poll-interval 60 --duration-seconds 1200
```

## Artifacts

Each launcher invocation writes:

```text
artifacts/crypto_pairs/await_soak/<YYYY-MM-DD>/<run_id>/
```

Files:

- `launcher_manifest.json`
- `availability_summary.json`
- `launch_output.log` when a child soak is launched

The launcher manifest records:

- whether markets were found before timeout
- the exact paper soak command that was launched
- the child exit code
- the child paper run path, manifest path, and run summary path when they were printed by `crypto-pair-run`

## Operator Flow

1. Start `crypto-pair-await-soak`.
2. Leave the process running until markets appear or the timeout elapses.
3. When markets become eligible, the command prints the Coinbase paper soak command and immediately executes it.
4. Inspect `launcher_manifest.json` for the handoff details and the linked paper run artifact path.

## Safety Constraints

- no live enablement path exists in this command
- market eligibility remains delegated to `run_watch_loop` / `run_availability_check`
- the launched soak uses the existing paper runner CLI rather than bypassing runtime guardrails
