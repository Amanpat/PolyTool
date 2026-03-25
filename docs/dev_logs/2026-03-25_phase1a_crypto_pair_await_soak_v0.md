# 2026-03-25 Phase 1A Crypto Pair Await Soak v0

## Summary

Added an operator-safe Track 2 launcher at `python -m polytool crypto-pair-await-soak`.
It reuses the existing market watch contract to block until eligible BTC/ETH/SOL
5m or 15m markets appear, then launches the standard Coinbase paper smoke soak
command and records the handoff in a small launcher artifact bundle.

No live path was added or enabled.

## Files Changed And Why

| File | Why |
|------|-----|
| `packages/polymarket/crypto_pairs/await_soak.py` | New await-and-launch core: wait via `run_watch_loop`, build the standard Coinbase paper command, stream child output, and write launcher artifacts. |
| `tools/cli/crypto_pair_await_soak.py` | New CLI entrypoint with timeout, poll interval, duration override, and launcher artifact output flags. |
| `polytool/__main__.py` | Registered `crypto-pair-await-soak` in top-level command dispatch and help output. |
| `tests/test_crypto_pair_await_soak.py` | Added offline tests for timeout, immediate eligible hit, command construction, CLI wiring, and live-flag safety. |
| `docs/features/FEATURE-crypto-pair-await-soak-v0.md` | Added operator-facing usage and artifact documentation for the new launcher. |
| `docs/dev_logs/2026-03-25_phase1a_crypto_pair_await_soak_v0.md` | Mandatory implementation log for this work unit. |

## Commands Run + Output

### 1. Help

Command:

```bash
python -m polytool crypto-pair-await-soak --help
```

Result:

```text
usage: __main__.py [-h] [--timeout TIMEOUT] [--poll-interval POLL_INTERVAL]
                   [--duration-seconds DURATION_SECONDS] [--output OUTPUT]

Wait for eligible BTC/ETH/SOL 5m/15m markets, then launch the standard paper-
only Coinbase smoke soak.
```

Exit code: `0`

### 2. Await-soak unit tests

Command:

```bash
python -m pytest tests/test_crypto_pair_await_soak.py -q
```

Result:

```text
collected 7 items
tests\test_crypto_pair_await_soak.py .......                             [100%]
============================== 7 passed in 0.28s ==============================
```

Exit code: `0`

### 3. Watch + await-soak contract tests

Command:

```bash
python -m pytest tests/test_crypto_pair_watch.py tests/test_crypto_pair_await_soak.py -q
```

Result:

```text
collected 25 items
tests\test_crypto_pair_watch.py ..................                       [ 72%]
tests\test_crypto_pair_await_soak.py .......                             [100%]
============================= 25 passed in 2.39s ==============================
```

Exit code: `0`

## Test Results

| Command | Pass/Fail | Notes |
|---------|-----------|-------|
| `python -m polytool crypto-pair-await-soak --help` | PASS | CLI registered and parser renders expected flags. |
| `python -m pytest tests/test_crypto_pair_await_soak.py -q` | PASS | 7 passed, 0 failed. |
| `python -m pytest tests/test_crypto_pair_watch.py tests/test_crypto_pair_await_soak.py -q` | PASS | 25 passed, 0 failed. |

## Launch Behavior

1. `crypto-pair-await-soak` enters a watch loop using the existing
   `run_watch_loop` contract from `packages/polymarket/crypto_pairs/market_watch.py`.
2. If no eligible markets appear before timeout:
   - it exits cleanly with exit code `1`
   - it does not launch `crypto-pair-run`
   - it still writes `availability_summary.json` and `launcher_manifest.json`
3. If eligible markets appear:
   - it prints the exact operator-facing launch command
   - it launches:

```bash
python -m polytool crypto-pair-run --reference-feed-provider coinbase --duration-seconds 1800 --heartbeat-seconds 60
```

   - it streams child output back to the terminal
   - it records the child exit code
   - it records child `artifact_dir`, `run_manifest_path`, and `run_summary_path` when the child prints them
   - it stores the streamed child output in `launch_output.log`
   - if the child process cannot be started, it still writes `launcher_manifest.json` with `status = "launch_failed"` and the recorded error

Launcher artifacts land under:

```text
artifacts/crypto_pairs/await_soak/<YYYY-MM-DD>/<run_id>/
```

## Safety Constraints Enforced

- Paper only: the launcher never inserts `--live`.
- Provider is fixed to Coinbase for the launched smoke soak.
- Duration defaults to `1800` seconds and heartbeat defaults to `60` seconds.
- Eligibility checks are delegated to the existing watcher/discovery contract; no duplicate market-classification logic was added.
- The launcher calls the standard `crypto-pair-run` CLI instead of bypassing runtime guardrails.
- Child output is forced unbuffered so operator heartbeat lines can stream while the soak is running.
- No strategy math, live execution code, Gate 2 files, or Grafana assets were touched.
- No soak execution was performed during this prompt.

## Open Questions For Next Prompt

1. Should the default wait timeout remain `3600` seconds, or should this launcher default to a longer unattended window such as 6 to 12 hours?
2. Should the launcher optionally append `--auto-report` once the Coinbase smoke soak path is considered the stable default?
3. Should the launcher emit an additional markdown handoff summary, or is the JSON manifest plus captured child output sufficient for operators?
