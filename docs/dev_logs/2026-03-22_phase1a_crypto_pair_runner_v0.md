# Dev Log: Phase 1A Crypto Pair Runner v0

**Date:** 2026-03-22
**Track:** Track 2
**Status:** COMPLETE

---

## Objective

Implement the Phase 1A runtime shell for the crypto pair bot:

- `python -m polytool crypto-pair-run`
- paper mode by default
- JSONL-first artifact bundle
- live scaffold behind `--live`
- explicit live safety gates
- no production client activation requirement
- no ClickHouse activation

---

## Files changed and why

- `packages/polymarket/crypto_pairs/position_store.py`
  - Added the JSONL-first position/run store, deterministic manifest writer, append-only event logs, and the disabled ClickHouse sink contract.
- `packages/polymarket/crypto_pairs/paper_runner.py`
  - Added shared runtime settings, operator-cap enforcement, paper-mode orchestration, feed-state freeze handling, intent generation, fill simulation, exposure accounting, and run finalization.
- `packages/polymarket/crypto_pairs/live_execution.py`
  - Added the live execution adapter contract, limit-only/post-only request validation, working-order tracking, and future real-client interface.
- `packages/polymarket/crypto_pairs/live_runner.py`
  - Added the live scaffold loop with kill-switch checks, disconnect cancellation behavior, reconnect gating, and explicit order-attempt logging.
- `tools/cli/crypto_pair_run.py`
  - Added the `crypto-pair-run` CLI, config loading, paper/live selection, `CONFIRM` enforcement, and help text describing the safety model.
- `polytool/__main__.py`
  - Registered `crypto-pair-run` in CLI dispatch and top-level help output.
- `tests/test_crypto_pair_run.py`
  - Added offline coverage for paper default behavior, bundle creation, and paper disconnect freeze transitions.
- `tests/test_crypto_pair_live_safety.py`
  - Added offline coverage for live confirmation rejection, kill-switch checks, no market-order path, and disconnect cancellation / reconnect resume behavior.
- `docs/features/FEATURE-crypto-pair-runner-v0.md`
  - Added the feature summary and artifact contract.
- `docs/dev_logs/2026-03-22_phase1a_crypto_pair_runner_v0.md`
  - Added this implementation log.

---

## Commands run + output

### 1. Top-level CLI help

Command:

```bash
python -m polytool --help
```

Output summary:

```text
PolyTool - Polymarket analysis toolchain
...
crypto-pair-scan
crypto-pair-run
...
```

### 2. New runner help

Command:

```bash
python -m polytool crypto-pair-run --help
```

Output summary:

```text
usage: __main__.py [-h] [--config CONFIG] [--duration-seconds DURATION_SECONDS]
...
Run the crypto-pair runtime shell. Paper mode is the default.
...
--live
--confirm CONFIRM
```

### 3. Targeted new runner tests

Command:

```bash
python -m pytest tests/test_crypto_pair_run.py tests/test_crypto_pair_live_safety.py -q
```

Output:

```text
collected 6 items
6 passed in 2.40s
```

### 4. Broader crypto-pair slice

Command:

```bash
python -m pytest tests/test_crypto_pair_scan.py tests/test_crypto_pair_paper_ledger.py tests/test_crypto_pair_run.py tests/test_crypto_pair_live_safety.py -q
```

Output:

```text
collected 76 items
76 passed in 2.62s
```

---

## Test results

- `tests/test_crypto_pair_run.py + tests/test_crypto_pair_live_safety.py`: **6 passed / 0 failed**
- `tests/test_crypto_pair_scan.py + tests/test_crypto_pair_paper_ledger.py + tests/test_crypto_pair_run.py + tests/test_crypto_pair_live_safety.py`: **76 passed / 0 failed**

Broader full-repo suite status:

- Not attempted in this packet.
- Known unrelated Gate 2 failure context remains unchanged and out of scope.

---

## Safety gates implemented for live scaffold

1. `--live` is required to enter the live path.
2. `--confirm CONFIRM` is required at startup.
3. Kill switch is checked every cycle before new work.
4. Only limit orders are accepted.
5. `post_only=True` is mandatory on every live request.
6. No market-order path exists; `order_type="market"` is rejected.
7. Binance disconnect or stale-feed state arms a disconnect guard.
8. Disconnect guard cancels all tracked working orders.
9. New intents stay blocked until a visibly healthy reconnect is observed and logged.
10. Live scaffold can run with no real client wired and logs `live_client_unconfigured` instead of silently pretending to submit.

---

## Artifact layout written

Paper mode bundle root:

```text
artifacts/crypto_pairs/paper_runs/<YYYY-MM-DD>/<run_id>/
```

Files:

```text
run_manifest.json
config_snapshot.json
runtime_events.jsonl
observations.jsonl
order_intents.jsonl
fills.jsonl
exposures.jsonl
settlements.jsonl
market_rollups.jsonl
run_summary.json
```

Live scaffold bundle root:

```text
artifacts/crypto_pairs/live_runs/<YYYY-MM-DD>/<run_id>/
```

Primary live scaffold artifacts are the same JSONL-first event/observation/intent
files, with working-order cancellation and reconnect behavior recorded in
`runtime_events.jsonl`.

---

## ClickHouse sink interface notes

- `CryptoPairClickHouseSink.write_rows(stream_name, rows)` is defined as the future writer contract.
- `ClickHouseSinkContract` is written into the run manifest so the disabled state is operator-visible.
- `DisabledClickHouseSink` raises if called.
- No code path in `crypto-pair-run` activates or writes to ClickHouse in v0.

---

## Open questions for next prompt

1. Should live scaffold artifacts also emit a `run_summary.json` even when no fills/settlements exist, for stricter parity with paper mode?
2. Should paper/live config files support YAML in addition to JSON, or should the runner stay JSON-only for operator clarity?
3. When a live client is eventually wired, should working-order state persist across process restarts or remain run-local in Phase 1B?
4. Does the next packet want partial-leg completion logic to open a new intent for the missing leg, or should open-unpaired exposure continue to block all new intents until an explicit unwind path exists?
