# Dev Log — Phase 1A: Crypto Pair Scan v0

**Date**: 2026-03-22
**Branch**: phase-1
**Track**: Track 2 — Crypto Asymmetric Pair Bot
**Status**: COMPLETE

---

## Objective

Implement the first Phase 1A executable surface: a dry-run crypto pair opportunity
scanner accessible via `python -m polytool crypto-pair-scan`.

**Done means**: the command discovers eligible 5m/15m BTC/ETH/SOL up-or-down markets,
computes paired opportunity metrics, ranks them deterministically, and writes an
artifact bundle — without placing any orders or requiring wallet credentials.

---

## What Was Built

### New packages

**`packages/polymarket/crypto_pairs/`** (new subpackage)

- `__init__.py` — package stub, docstring only
- `market_discovery.py` — discovers eligible binary markets from Gamma API
- `opportunity_scan.py` — fetches live order-book best-asks and computes pair metrics

### New CLI tool

**`tools/cli/crypto_pair_scan.py`** — orchestrates discovery → scan → rank → artifact
write.  Exposed as `python -m polytool crypto-pair-scan`.

### CLI wiring

**`polytool/__main__.py`** — added:
- `crypto_pair_scan_main` entrypoint
- `"crypto-pair-scan"` in `_COMMAND_HANDLER_NAMES`
- Track 2 section in `print_usage()`

### Tests

**`tests/test_crypto_pair_scan.py`** — 47 offline tests (all mocked, no network).

---

## Key Design Decisions

### Why `GammaClient.fetch_all_markets()` (not `fetch_recent_markets()`)

`fetch_recent_markets()` only returns the first CLOB token ID per market.  The pair
strategy requires **both** YES and NO token IDs.  `GammaClient.fetch_all_markets()`
returns full `Market` objects with `clob_token_ids: list[str]`, enabling both legs
to be resolved.

### YES/NO token resolution

Outcome names are matched against frozensets (`_YES_OUTCOMES`, `_NO_OUTCOMES`):

```python
_YES_OUTCOMES = frozenset({"yes", "y", "true", "up", "higher", "above"})
_NO_OUTCOMES  = frozenset({"no",  "n", "false", "down", "lower", "below"})
```

Falls back to `clob_token_ids[0]=YES, clob_token_ids[1]=NO` (Polymarket convention)
when outcome names don't match any keyword.

### Regex word boundaries around `5m` / `15m`

`\b5m\b` correctly matches inside hyphenated slugs like `btc-5m-up` because `-` is
a non-word character that creates word boundaries.

### Pair cost edge boundary

`gross_edge = 1.00 - paired_cost`.  Strictly `> 0.0` is required for `has_opportunity`.
Exactly 0.00 (paired_cost == 1.00) is NOT an opportunity — one leg settles $1.00
but the other settles $0.00 and the combined cost was also $1.00, so net = $0.

### Assumption tagging

Every `PairOpportunity` record carries `assumptions: list[str]` with four static
flags: `maker_rebate_20bps`, `no_slippage`, `fills_not_guaranteed`, `rapid_resolution`.
These appear in both `opportunities.json` and `opportunities.md` so operators always
have context when reading the artifact bundle.

---

## Artifact Bundle Layout

```
artifacts/crypto_pairs/scan/
  YYYY-MM-DD/
    <run_id_hex12>/
      scan_manifest.json   # run metadata + summary counts
      opportunities.json   # list of PairOpportunity records
      opportunities.md     # Markdown table for human review
```

`scan_manifest.json` schema:
```json
{
  "run_id": "...",
  "generated_at": "...",
  "mode": "dry_run",
  "filters": { "symbol": null, "duration_min": null },
  "summary": {
    "markets_discovered": 12,
    "markets_scanned": 12,
    "opportunities_found": 2,
    "top_requested": 20
  },
  "artifact_dir": "artifacts/crypto_pairs/scan/YYYY-MM-DD/<id>"
}
```

---

## CLI Usage

```bash
# Discover all BTC/ETH/SOL 5m/15m markets, print top 20
python -m polytool crypto-pair-scan

# Filter by symbol and duration
python -m polytool crypto-pair-scan --symbol BTC --duration 5

# Show more rows
python -m polytool crypto-pair-scan --top 50

# Custom artifact directory
python -m polytool crypto-pair-scan --output /tmp/crypto_scan
```

---

## Test Results

```
pytest tests/test_crypto_pair_scan.py -q --tb=short
47 passed, 0 failed, 0 skipped
```

Full regression suite:
```
pytest tests/ -x -q --tb=short
[all existing tests pass — no regressions]
```

---

## Open Questions / Next Steps

1. **Live smoke**: Run `python -m polytool crypto-pair-scan` against live Gamma API
   and CLOB API; verify at least one BTC/ETH/SOL 5m/15m market is discovered and
   both token IDs resolve to valid order books.

2. **Maker order submission**: Phase 1A v1 will add a `--live` flag that, after
   operator confirmation, submits GTC maker orders for YES and NO legs when
   `gross_edge > threshold`.  This requires wallet credentials and CLOB auth.
   **Out of scope for this PR.**

3. **Scheduling**: Phase 1A v2 will schedule this scan every 5 minutes via cron or
   APScheduler. **Out of scope for this PR.**

4. **Grafana visibility**: Append `opportunities_found` count to ClickHouse for
   Grafana dashboarding.  **Out of scope for this PR.**

---

## Files Changed

```
packages/polymarket/crypto_pairs/__init__.py         (new)
packages/polymarket/crypto_pairs/market_discovery.py (new)
packages/polymarket/crypto_pairs/opportunity_scan.py (new)
tools/cli/crypto_pair_scan.py                        (new)
polytool/__main__.py                                 (modified)
tests/test_crypto_pair_scan.py                       (new)
docs/dev_logs/2026-03-22_phase1a_crypto_pair_scan_v0.md (this file)
```
