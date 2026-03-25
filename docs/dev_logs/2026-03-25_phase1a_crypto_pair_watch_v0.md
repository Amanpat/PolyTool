# Dev Log: Phase 1A Crypto Pair Market Availability Watcher v0

**Date:** 2026-03-25
**Quick task:** quick-024
**Branch:** phase-1A

## Context

Quick-023 (Coinbase smoke soak rerun) confirmed the Coinbase reference feed
works correctly with `--reference-feed-provider coinbase`. However, the run
was blocked because Polymarket has zero active BTC/ETH/SOL 5m/15m binary
pair markets as of 2026-03-25. The blocker shifted from reference-feed
configuration to market availability.

The immediate need is a lightweight, artifact-producing command that lets the
operator check whether eligible markets exist and optionally poll until they
appear — without running the full `crypto-pair-run` paper runner.

## What Was Built

### Core library

**`packages/polymarket/crypto_pairs/market_watch.py`** (new)

- `AvailabilitySummary` dataclass: `eligible_now`, `total_eligible`, `by_symbol`,
  `by_duration`, `first_eligible_slugs`, `rejection_reason`, `checked_at`.
- `run_availability_check(gamma_client=None, ...)` — calls `discover_crypto_pair_markets`
  directly; no fork of the classifier. Builds the summary from the returned list.
- `run_watch_loop(poll_interval_seconds, timeout_seconds, _sleep_fn, _check_fn)` —
  polls at interval, returns `(True, summary)` on first eligible result, or
  `(False, last_summary)` on timeout. Both `_sleep_fn` and `_check_fn` are injectable
  to allow full offline testing without real `time.sleep`.

### CLI

**`tools/cli/crypto_pair_watch.py`** (new)

- Follows exact same module layout as `tools/cli/crypto_pair_scan.py`.
- `build_parser()`: `--symbol`, `--duration`, `--watch`, `--poll-interval`,
  `--timeout`, `--output`.
- `run_crypto_pair_watch(watch_mode, poll_interval_seconds, timeout_seconds, ...)`:
  injectable `_check_fn` and `_sleep_fn` for offline tests.
- Writes three artifacts per run:
  - `watch_manifest.json`
  - `availability_summary.json` (via `dataclasses.asdict`)
  - `availability_summary.md` (Markdown table + next-action + assumptions)
- `main(argv) -> int`: one-shot exits 0 always; watch exits 0 on found, 1 on timeout.

### Command registration

**`polytool/__main__.py`** (modified)

- Added `crypto_pair_watch_main = _command_entrypoint("tools.cli.crypto_pair_watch")`
- Added `"crypto-pair-watch": "crypto_pair_watch_main"` to `_COMMAND_HANDLER_NAMES`.
- Added usage line to the Crypto Pair Bot section in `print_usage()`.

### Tests

**`tests/test_crypto_pair_watch.py`** (new, 20 test functions across 10 classes)

Test classes and coverage:
1. `TestNoEligibleMarkets` — gamma returns non-matching markets; `eligible_now=False`
2. `TestEligibleMarketsPresent` — 2 valid BTC 5m markets; counts verified
3. `TestMixedMarketsIrrelevantFiltered` — mix of eligible and non-eligible; correct counts
4. `TestAvailabilitySummaryFieldsPopulated` — all fields present and correct types
5. `TestWatchModeFindsMarketsImmediately` — `_check_fn` returns eligible on call 1
6. `TestWatchModeTimeout` — `_check_fn` always not-eligible; `found=False`
7. `TestArtifactsWritten` — all 3 artifact files written, JSON schema verified
8. `TestCliOneshotHelp` — `build_parser().parse_args(["--help"])` → SystemExit(0)
9. `TestCliOneshotNoMarketsExits0` — `main(...)` returns 0 when no eligible markets
10. `TestCliWatchTimeoutExits1` — `main(["--watch", "--timeout", "1", ...])` returns 1

All tests use injected stubs; no network calls.

### Docs

**`docs/features/FEATURE-crypto-pair-watch-v0.md`** (new)

- Purpose, when to use, CLI examples, eligibility rules, artifact schema,
  next-action table, exit codes, limitations.

## Commands Run and Results

```bash
# Verify import
python -c "from packages.polymarket.crypto_pairs.market_watch import \
  AvailabilitySummary, run_availability_check, run_watch_loop; print('OK')"
# OK

# Verify CLI help
python -m polytool crypto-pair-watch --help
# exits 0, shows all flags

# Run new tests + regression check
python -m pytest tests/test_crypto_pair_watch.py tests/test_crypto_pair_scan.py -q --tb=short
# 80 passed in 2.48s
```

## Key Design Decisions

1. **No classifier fork** — `run_availability_check` calls `discover_crypto_pair_markets`
   directly. All eligibility logic lives in `market_discovery.py` as before.

2. **Injectable _sleep_fn and _check_fn** — makes `run_watch_loop` and
   `run_crypto_pair_watch` fully testable without real time.sleep or network calls.

3. **One-shot exits 0 always** — market unavailability is informational, not an error.
   Only watch-mode timeout exits 1 so cron/shell scripts can distinguish.

4. **--symbol/--duration flags reserved in v0** — accepted for forward compatibility
   but do not filter the Gamma query. The discovery always returns all eligible
   markets. This is noted in help text, feature doc, and the Markdown assumptions
   section so operators are not confused.

5. **dataclasses.asdict for JSON** — canonical serialization of AvailabilitySummary
   to avoid manual field enumeration drift.

## Eligibility Rules (Recap)

A market passes the watcher's eligibility check when:
- `active=True`
- `accepting_orders` is `True` or `None` (not explicitly `False`)
- Exactly 2 CLOB token IDs (binary)
- Symbol keyword match: BTC/Bitcoin, ETH/Ethereum/Ether, SOL/Solana
- Duration keyword match: 5m/5min/5 minute or 15m/15min/15 minute

## Artifact Schema

Path: `artifacts/crypto_pairs/watch/<YYYY-MM-DD>/<run_id>/`

Files:
- `watch_manifest.json` — `run_id`, `generated_at`, `mode`, `summary_ref`, `artifact_dir`
- `availability_summary.json` — full `AvailabilitySummary` as dict
- `availability_summary.md` — human-readable table + next-action + assumptions

## Open Questions / Next Steps

1. **When do BTC/ETH/SOL 5m/15m markets rotate back in?** Polymarket appears to
   list these markets on a schedule. The watch command with `--watch --timeout 3600`
   can be left running to detect the rotation automatically.

2. **Run `crypto-pair-scan` when eligible_now=yes.** The watcher will print:
   `Next action: Run: python -m polytool crypto-pair-scan (then crypto-pair-run when ready)`

3. **Discord notification hook (future v1).** The current v0 requires the operator
   to observe terminal output. A future enhancement could wire `notify_gate_result`
   from the Discord alerting package when markets appear in watch mode.

4. **Per-symbol/duration filter wiring (future).** The `--symbol` and `--duration`
   flags currently pass through to the CLI but do not restrict the Gamma query.
   This can be wired in a future revision once the common pattern for filtering
   at the `discover_crypto_pair_markets` level is established.
