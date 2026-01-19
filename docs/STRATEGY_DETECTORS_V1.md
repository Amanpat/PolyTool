# Strategy Detectors v1 (Explainable Heuristics)

These detectors are heuristic, explainable, and implementable without private data.
Each detector outputs a confidence score and evidence payload.

## Inputs (public-only)

Trades (Data API `GET /trades`):
- `trade.timestamp`
- `trade.transactionHash`
- `trade.slug`
- `trade.asset` (token_id)
- `trade.conditionId`
- `trade.side`
- `trade.outcome`
- `trade.outcomeIndex`
- `trade.price`
- `trade.size`

Market metadata (Gamma `GET /events` or `/markets`):
- `market.slug`
- `market.conditionId`
- `market.endDate` or `market.endDateIso`
- `market.outcomes`
- `market.clobTokenIds`
- `market.outcomePrices`

Order book (CLOB `GET /book`):
- `book.bids[].price`, `book.bids[].size`
- `book.asks[].price`, `book.asks[].size`
- `book.timestamp`, `book.hash`

## Output schema (per detector)

```
{
  "detector": "complete_set",
  "confidence": 0.0..1.0,
  "evidence": {
    "...": "..."
  }
}
```

## Common feature computations

- `seconds_to_end`:
  - `market.endDate` (Gamma) minus `trade.timestamp`.
- `paired_trade_delay_seconds`:
  - Min time delta between opposite outcomes in the same `conditionId`.
- `exec_type` (maker-like / taker-like / inside / unknown):
  - maker-like: BUY price <= best_bid + eps
  - taker-like: BUY price >= best_ask - eps
  - inside: between best_bid and best_ask

eps default: `0.001` (same epsilon used in polybot ClickHouse views).

## Detector 1: Complete-set / arb style

Intent:
- Detect paired opposite-outcome trades with positive edge.

Heuristic:
- Group trades by `conditionId`.
- For each trade, find the nearest opposite outcome (Up vs Down, Yes vs No)
  within `window_seconds` (default 120s).
- Compute:
  - `edge = 1 - (price_a + price_b)`
  - `matched_size = min(size_a, size_b)`
- Optional (higher confidence):
  - Use CLOB order book for both outcomes at trade time and compute
    `edge_bid = 1 - (bid_up + bid_down)` and/or `edge_ask = 1 - (ask_up + ask_down)`.

Confidence (example):
- `pair_ratio = pairs / total_trades`
- `positive_edge_ratio = positive_edge_pairs / pairs`
- `fast_pair_ratio = pairs_within_30s / pairs`
- `confidence = clamp(0.4*pair_ratio + 0.4*positive_edge_ratio + 0.2*fast_pair_ratio)`

Evidence:
- `pairs`, `positive_edge_pairs`, `median_time_gap_sec`
- Top 5 pairs with `{trade_key_a, trade_key_b, time_gap_sec, price_sum, edge, matched_size}`

## Detector 2: Momentum / scalp

Intent:
- Short holding times and frequent re-entries.

Heuristic:
- Build a FIFO position ledger per `token_id` using `trade.side`.
- Compute holding times for BUY -> SELL matches.
- Detect re-entries: sequences like BUY->SELL->BUY within 60 minutes.

Confidence (example):
- `short_hold_ratio = closed_trades_with_hold<=15m / closed_trades`
- `reentry_ratio = reentry_sequences / closed_trades`
- `confidence = clamp(0.6*short_hold_ratio + 0.4*reentry_ratio)`

Evidence:
- `median_hold_seconds`, `p90_hold_seconds`
- `short_hold_ratio`
- Example re-entry sequences with timestamps

## Detector 3: Position trading

Intent:
- Long holding periods, low turnover.

Heuristic:
- Use the same ledger as above.
- Identify positions with holding time >= 24h.
- Compute trade frequency per market.

Confidence (example):
- `long_hold_ratio = closed_trades_with_hold>=24h / closed_trades`
- `low_turnover_ratio = markets_with_trades<=3 / markets_traded`
- `confidence = clamp(0.7*long_hold_ratio + 0.3*low_turnover_ratio)`

Evidence:
- `median_hold_seconds`, `p90_hold_seconds`
- Top 5 longest holds with `{token_id, open_ts, close_ts, hold_seconds}`
- `markets_traded`, `markets_low_turnover`

## Detector 4: DCA / laddering

Intent:
- Systematic size increments and laddered entry prices.

Heuristic:
- Group BUY trades by `(market_slug, outcome)`.
- Within each group, sort by timestamp and compute:
  - `size_deltas` between consecutive trades
  - `price_trend` (monotonic for buys)
- Flag a ladder if:
  - >= 3 trades within 24h
  - `stddev(size_deltas) / mean(size_deltas) <= 0.5`
  - price is non-increasing for BUYs

Confidence (example):
- `ladder_markets_ratio = markets_with_ladders / markets_traded`
- `confidence = clamp(0.5*ladder_markets_ratio + 0.5*(1 - size_delta_cv))`

Evidence:
- List of laddered sequences with `{market_slug, outcome, sizes, prices, timestamps}`
- `size_delta_cv` summary

## Detector 5: Liquidity-providing proxy

Intent:
- Maker-like execution behavior inferred from fill prices.

Heuristic:
- Join trades to order book snapshots (`/book`) using token_id and time.
- Classify trades:
  - maker-like if BUY price <= best_bid + eps
  - taker-like if BUY price >= best_ask - eps
- Signal if:
  - maker-like ratio >= 0.60
  - avg size is in the bottom 50th percentile of all trades
  - trades per hour is above a minimum threshold (e.g., 10/h)

Confidence (example):
- `confidence = clamp(0.5*maker_ratio + 0.3*small_size_ratio + 0.2*freq_score)`

Evidence:
- `maker_ratio`, `taker_ratio`, `avg_size`, `trades_per_hour`
- Example trades with `{trade_key, price, best_bid, best_ask}`

## Known limitations

- Fills do not reveal resting orders, so liquidity-providing is a proxy.
- If order book snapshots are stale or missing, exec_type is unreliable.
- Some users only buy (no sells), making hold-time detectors inconclusive.
