# Plays View Documentation

This document explains the "Plays" concept in PolyTool and how to interpret the plays-related panels in Grafana dashboards.

## What is a "Play"?

A **play** is a single trade-level record representing one transaction on Polymarket. Each play captures:

- A user buying or selling outcome tokens
- The specific market and outcome involved
- Price, size, and timing information

Plays are the atomic unit of trading activity. Higher-level metrics (PnL, strategy signals, exposure) are computed by aggregating plays.

## Data Source

Plays are stored in the `polyttool.user_trades` table, but dashboards read from the
`polyttool.user_trades_resolved` view. This view resolves token ids in three steps:

1. Direct match on `market_tokens.token_id` (canonical CLOB token ids)
2. Alias lookup in `token_aliases` (Data API / legacy token ids)
3. Condition + outcome fallback using `markets` (match outcome index to `clob_token_ids`)

Once resolved, the view attaches market metadata (question, slug, category, outcome name)
so the Plays panels show consistent labels even when Data API token ids differ from Gamma.

## Field Definitions

### Latest Trades Table

| Field | Description | Source |
|-------|-------------|--------|
| **time** | Timestamp when the trade occurred | `user_trades.ts` |
| **market** | Human-readable market question. Falls back to market_slug, then condition_id if unavailable. | `market_tokens.question` or `market_tokens.market_slug` or `user_trades.condition_id` |
| **outcome** | The outcome being traded (e.g., "Yes", "No", candidate name). Falls back to raw outcome value if mapping unavailable. | `market_tokens.outcome_name` or `user_trades.outcome` |
| **side** | Trade direction: **BUY** (green) = acquiring tokens, **SELL** (red) = disposing tokens | `user_trades.side` |
| **price** | Price per token (0.00 to 1.00), representing implied probability | `user_trades.price` |
| **size** | Number of tokens traded | `user_trades.size` |
| **notional** | USD value of trade = size × price | Computed: `size * price` |
| **tx_hash** | Polygon transaction hash (truncated). Clickable link to PolygonScan. Empty if not available. | `user_trades.transaction_hash` |

### Top Markets Table

| Field | Description |
|-------|-------------|
| **market** | Market question or identifier |
| **notional** | Total USD volume in this market (sum of size × price) |
| **trades** | Count of individual trades in this market |

### Top Outcomes Table

| Field | Description |
|-------|-------------|
| **outcome** | Outcome name (e.g., "Yes", "Trump") |
| **market** | Associated market question |
| **notional** | Total USD volume for this outcome |
| **trades** | Count of trades for this outcome |

### Top Categories Table

| Field | Description |
|-------|-------------|
| **category** | Market category (e.g., "Politics", "Sports", "Crypto"). Shows "Unknown" when metadata unavailable. |
| **notional** | Total USD volume in this category |
| **trades** | Count of trades in this category |
| **pct** | Percentage of user's total volume in this category |

## Interpreting Plays

### Side Colors
- **Green (BUY)**: User is acquiring exposure to this outcome
- **Red (SELL)**: User is reducing/closing exposure to this outcome

### Price Interpretation
- Price represents implied probability (0.00 = 0%, 1.00 = 100%)
- BUY at 0.30 = buying "Yes" tokens at 30 cents (believing outcome >30% likely)
- SELL at 0.70 = selling "Yes" tokens at 70 cents (taking profit or reducing risk)

### Notional Value
- Represents the dollar value at risk/exchanged
- A BUY of 100 tokens at $0.50 = $50 notional
- Useful for comparing trade sizes across different price levels

## Limitations

1. **Market Metadata Coverage**: Some trades may still show condition_id instead of market question if market metadata hasn't been ingested. Run `/api/ingest/markets` (or backfill) to improve coverage. The token resolution view will map aliases when possible.

2. **Category Coverage**: Categories depend on market metadata. "Unknown" category explicitly shows trades without category mappings.

3. **Time Range**: Plays table respects the Grafana time picker. Large time ranges may be slow for users with many trades.

4. **Row Limit**: Latest Trades table is capped at 100 rows to prevent browser performance issues. For full trade history, use the dedicated User Trades dashboard or export via ClickHouse.

5. **Transaction Hash**: Not all trades have transaction hashes recorded (depends on API response). Missing hashes show as empty.

6. **Deduplication**: The underlying `user_trades` table uses ReplacingMergeTree with `ingested_at` as the version column. Use `argMax()` aggregation for accurate counts when querying directly.

## Related Documentation

- [DASHBOARDS.md](./DASHBOARDS.md) - Full dashboard documentation
- [STRATEGY_CATALOG.md](./STRATEGY_CATALOG.md) - How plays feed into strategy detection
- [TROUBLESHOOTING_PNL.md](./TROUBLESHOOTING_PNL.md) - PnL calculation from plays
