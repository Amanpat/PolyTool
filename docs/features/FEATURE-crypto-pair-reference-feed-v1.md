# Feature: Crypto Pair Reference Feed v1

**Status**: Implemented (2026-03-25)
**Track**: Phase 1A / Track 2
**CLI command**: `python -m polytool crypto-pair-run`

---

## What it does

Track 2 now supports configurable reference-feed selection for BTC, ETH, and
SOL without changing the accumulation engine contract or strategy math.

The runtime still uses the same `ReferencePriceSnapshot` shape:

- `symbol`
- `price`
- `observed_at_s`
- `connection_state`
- `is_stale`
- `stale_threshold_s`
- `feed_source`

The runner can now source that snapshot from:

- `binance` - default, unchanged Binance-first behavior
- `coinbase` - explicit Coinbase Exchange public ticker feed
- `auto` - optional dual-feed mode that prefers Binance when both feeds are
  healthy and falls back to Coinbase when Binance is unusable

---

## Provider Selection

Use the CLI flag:

```powershell
python -m polytool crypto-pair-run --reference-feed-provider coinbase
```

Or set it in a JSON config payload:

```json
{
  "reference_feed_provider": "coinbase"
}
```

Selection rules:

- Default is `binance`
- CLI overrides config when both are provided
- `auto` opens both feeds and keeps Binance-first selection semantics
- Live mode remains Binance-only in v1; non-Binance selection is rejected there

---

## Coinbase Normalization

Coinbase ticker products are normalized onto the same internal symbol contract
already used by the engine:

- `BTC-USD` -> `BTC`
- `ETH-USD` -> `ETH`
- `SOL-USD` -> `SOL`

Only ticker messages for those products are accepted. Non-ticker payloads and
unsupported Coinbase products are ignored or rejected in offline validation
helpers without changing runner behavior.

---

## State Semantics

Feed-state semantics are intentionally provider-agnostic:

- No price received -> `price=None`, `is_stale=True`, `feed_source="none"`
- Fresh connected price -> usable snapshot
- Stale price -> `is_usable=False`
- Explicit disconnect -> `connection_state="disconnected"` and new intents freeze

This keeps the Track 2 paper runner and accumulation engine unchanged apart
from where the snapshot originates.

---

## Operator Notes

For the next smoke soak, the cheapest unblock is:

```powershell
python -m polytool crypto-pair-run --reference-feed-provider coinbase
```

Use `auto` only if you want dual-feed behavior and are comfortable with both
public WebSocket connections being opened for the run.
