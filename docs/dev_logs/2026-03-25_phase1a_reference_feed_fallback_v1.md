# 2026-03-25 Phase 1A Reference Feed Fallback v1

**Work unit**: Phase 1A / Track 2 reference-feed fallback unblock for the next paper smoke soak.
**Author**: Codex
**Status**: CLOSED

---

## Summary

Implemented Coinbase as an alternative Track 2 reference source while keeping
Binance as the default and preferred path. The paper runner and CLI now accept
provider selection, the snapshot contract stays provider-agnostic, and the
requested offline coverage passes.

The practical unblock for the next smoke soak is:

```powershell
python -m polytool crypto-pair-run --reference-feed-provider coinbase
```

---

## Files Changed And Why

| File | Why |
|------|-----|
| `packages/polymarket/crypto_pairs/reference_feed.py` | Added Coinbase feed support, provider normalization, provider factory, Coinbase symbol normalization helpers, and optional Binance-first `auto` wrapper. |
| `packages/polymarket/crypto_pairs/paper_runner.py` | Added `reference_feed_provider` to runner settings and used the provider factory instead of hardcoding `BinanceFeed()`. |
| `tools/cli/crypto_pair_run.py` | Added `--reference-feed-provider`, wired config/CLI override behavior, and guarded live mode from silently claiming unsupported provider behavior. |
| `tests/test_crypto_pair_reference_feed.py` | Added offline tests for Coinbase normalization, provider construction, Coinbase stale/disconnect semantics, and Binance-first `auto` behavior. |
| `tests/test_crypto_pair_run.py` | Added CLI/provider-selection tests and config snapshot assertions. |
| `docs/features/FEATURE-crypto-pair-reference-feed-v1.md` | Documented the new provider-selection behavior and operator usage. |
| `docs/dev_logs/2026-03-25_phase1a_reference_feed_fallback_v1.md` | Recorded this implementation, commands, results, and remaining limits. |

---

## Commands Run And Output

### 1. Syntax check

```powershell
python -m py_compile packages\polymarket\crypto_pairs\reference_feed.py packages\polymarket\crypto_pairs\paper_runner.py tools\cli\crypto_pair_run.py tests\test_crypto_pair_reference_feed.py tests\test_crypto_pair_run.py
```

Output:

```text
(no output, exit 0)
```

### 2. CLI help check

```powershell
python -m polytool crypto-pair-run --help
```

Relevant output:

```text
--reference-feed-provider {binance,coinbase,auto}
Reference price feed provider for paper mode. Default: binance.
```

### 3. Targeted scoped tests, first run

```powershell
python -m pytest tests\test_crypto_pair_reference_feed.py tests\test_crypto_pair_run.py -q
```

Output:

```text
1 failed, 49 passed
FAILED tests/test_crypto_pair_reference_feed.py::TestAutoReferenceFeed::test_auto_prefers_binance_when_both_feeds_are_usable
```

Reason:

- `auto` initially preferred the fresher Coinbase timestamp even when both
  feeds were fully usable.

### 4. Targeted scoped tests, rerun after fix

```powershell
python -m pytest tests\test_crypto_pair_reference_feed.py tests\test_crypto_pair_run.py -q
```

Output:

```text
50 passed in 0.53s
```

### 5. Broader Track 2 regression suite

```powershell
python -m pytest tests\test_crypto_pair_scan.py tests\test_crypto_pair_paper_ledger.py tests\test_crypto_pair_run.py tests\test_crypto_pair_live_safety.py tests\test_crypto_pair_reference_feed.py tests\test_crypto_pair_fair_value.py tests\test_crypto_pair_accumulation_engine.py tests\test_crypto_pair_backtest.py tests\test_crypto_pair_clickhouse_sink.py tests\test_crypto_pair_runner_events.py tests\test_crypto_pair_report.py tests\test_crypto_pair_soak_workflow.py -q
```

Output:

```text
251 passed in 8.74s
```

---

## Test Results

| Command | Result |
|------|-----|
| `python -m py_compile ...` | pass |
| `python -m polytool crypto-pair-run --help` | pass |
| Targeted scoped suite, first run | fail: 49 passed / 1 failed |
| Targeted scoped suite, rerun | pass: 50 passed / 0 failed |
| Broader Track 2 regression suite | pass: 251 passed / 0 failed |

Final state:

- Scoped touched-file tests pass
- Broader requested Track 2 suite passes
- CLI exposes provider selection
- Paper runner can be forced to Coinbase for the next soak

---

## Provider Selection Behavior

- Default provider is `binance`
- Config key is `reference_feed_provider`
- CLI flag `--reference-feed-provider` overrides config
- `coinbase` uses Coinbase Exchange ticker feed and normalizes `BTC-USD`,
  `ETH-USD`, and `SOL-USD` onto the internal `BTC` / `ETH` / `SOL` contract
- `auto` opens both feeds, returns Binance when both feeds are usable, and
  falls back to Coinbase when Binance is stale or disconnected
- `feed_source` on the snapshot now reports `binance`, `coinbase`, or `none`

---

## Remaining Limitations / Operator Notes

- Live mode behavior was intentionally not changed. In v1, non-Binance
  provider selection is rejected for live mode rather than silently claiming
  unsupported behavior.
- `auto` mode opens both public WebSocket feeds. For the immediate unblock,
  `coinbase` is simpler and avoids Binance 451 noise entirely.
- This change does not alter accumulation math, order generation logic, live
  execution wiring, Gate 2 files, or dashboards.
- Tests remain fully offline; no network calls were added to the test suite.
