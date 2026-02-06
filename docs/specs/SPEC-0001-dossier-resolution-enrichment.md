# SPEC-0001: Dossier Resolution Enrichment

**Status**: Accepted
**Created**: 2026-02-05

## Overview

This specification defines how market resolutions, settlement prices, and realized PnL
are computed and included in user dossiers.

## Resolution Outcome Taxonomy

Every trade or position must have exactly one of these resolution outcomes:

| Outcome | Description | Settlement Price | Position State |
|---------|-------------|------------------|----------------|
| `WIN` | Held to resolution, outcome won | 1.0 | Held position |
| `LOSS` | Held to resolution, outcome lost | 0.0 | Held position |
| `PROFIT_EXIT` | Exited before resolution at profit | N/A | Fully exited |
| `LOSS_EXIT` | Exited before resolution at loss | N/A | Fully exited |
| `PENDING` | Market not yet resolved | NULL | Any |
| `UNKNOWN_RESOLUTION` | Resolution data unavailable | NULL | Any |

## Settlement Price Semantics

### Binary Markets
- Each market has exactly 2 outcome tokens
- Winner: `settlement_price = 1.0`
- Loser: `settlement_price = 0.0`

### Multi-Outcome Markets
- Each outcome token has its own row in `market_resolutions`
- Winning outcome: `settlement_price = 1.0`
- All other outcomes: `settlement_price = 0.0`

## PnL Calculation

### Gross PnL
```
If position_remaining > 0 (held to resolution):
    gross_pnl = (settlement_price * position_remaining) + total_proceeds - total_cost

If position_remaining <= 0 (fully exited):
    gross_pnl = total_proceeds - total_cost
```

### Net PnL (realized_pnl_net)
```
realized_pnl_net = gross_pnl - fees_actual

If fees_actual unavailable:
    realized_pnl_net = gross_pnl - fees_estimated
```

### Fee Tracking Fields

| Field | Type | Description |
|-------|------|-------------|
| `fees_actual` | Float | Actual fees from on-chain data |
| `fees_estimated` | Float | Estimated fees from fee curve |
| `fees_source` | String | Source: `onchain`, `estimated`, `unknown` |

Fee estimation uses the Polymarket fee curve formula (see `packages/polymarket/fees.py`).
Do NOT hardcode a global fee rate.

## Trade UID Generation

Trade UIDs must be deterministic:
```python
trade_uid = sha256(f"{tx_hash}:{log_index}").hexdigest()
```

## Lifecycle Fields

Each position/trade record includes:

| Field | Type | Description |
|-------|------|-------------|
| `entry_price` | Float | Average entry price |
| `exit_price` | Float | Average exit price (if applicable) |
| `entry_ts` | DateTime | First buy timestamp |
| `exit_ts` | DateTime | First sell timestamp (if applicable) |
| `hold_duration` | Int | Hold time in seconds |
| `resolved_at` | DateTime | Resolution timestamp (nullable) |
| `resolution_source` | String | Where resolution was fetched from |

## Time-to-Event Fields

If event timing data is available:

| Field | Type | Description |
|-------|------|-------------|
| `event_start_time` | DateTime | When the event starts |
| `minutes_before_start` | Int | Trade time relative to event start |

If unavailable, these fields are `NULL`.

## ResolutionProvider Interface

Resolution data is fetched via a provider interface:

```python
class ResolutionProvider(Protocol):
    def get_resolution(
        self,
        condition_id: str,
        outcome_token_id: str,
    ) -> Optional[Resolution]:
        """Fetch resolution for an outcome token."""
        ...
```

Implementations:
- `GammaResolutionProvider`: Fetches from Gamma API (closed markets)
- `OnChainResolutionProvider`: Fetches from blockchain (future)
- `CachedResolutionProvider`: Wraps providers with local cache

If resolution cannot be determined, mark as `UNKNOWN_RESOLUTION` and proceed.

## Dossier JSON Additions

The enriched dossier includes:

```json
{
  "positions": [
    {
      "resolved_token_id": "...",
      "resolution_outcome": "WIN|LOSS|...",
      "settlement_price": 1.0,
      "resolved_at": "2026-01-15T12:00:00Z",
      "resolution_source": "gamma",
      "gross_pnl": 150.0,
      "realized_pnl_net": 148.5,
      "fees_actual": 1.5,
      "fees_estimated": 1.5,
      "fees_source": "onchain",
      "entry_price": 0.45,
      "exit_price": null,
      "hold_duration": 86400,
      "minutes_before_start": null
    }
  ]
}
```

## Implementation Notes

1. Resolution fetching is best-effort. If the API is unavailable or the market
   is not found, mark as `UNKNOWN_RESOLUTION` and continue.

2. Fee calculation uses stored `fee_rate_bps` from token metadata when available.
   Falls back to `fees_source="unknown"` and `fees_actual=0` if unavailable.

3. The ClickHouse view `user_trade_lifecycle_enriched` performs these calculations
   at query time using left joins to `market_resolutions`.

## References

- `infra/clickhouse/initdb/17_resolutions.sql`: Database schema
- `packages/polymarket/fees.py`: Fee calculation
- `docs/specs/hypothesis_schema_v1.json`: Output format
