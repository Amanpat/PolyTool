# Reverse Engineer Feature Spec (MVP)

This spec defines the first PolyTool feature: Reverse Engineer.
It uses only public Polymarket data sources and produces explainable strategy inferences.

## Inputs and outputs

Input:
- `username` OR `wallet_address` (EOA or proxy wallet).

Outputs:
- Identity resolution (username, proxy wallet).
- Trade, position, and activity ingestion (raw + normalized).
- Derived features.
- Strategy detector results (confidence + evidence).
- Dashboard views.

## End-to-end workflow

1) Resolve identity
- If input is a username: `GET Gamma /public-search` -> pick exact username -> proxy wallet.
- Validate with `GET Gamma /public-profile?address=<proxy_wallet>`.

2) Ingest user history
- `GET Data API /trades?user=<proxy_wallet>&limit=<n>&offset=<n>` (1+ pages)
- `GET Data API /positions?user=<proxy_wallet>&limit=<n>&offset=<n>` (snapshot)
- `GET Data API /activity?user=<proxy_wallet>&limit=<n>&offset=<n>` (snapshot)

3) Ingest market metadata
- `GET Gamma /events?slug=<market_slug>&limit=1` for traded markets.
- (Optional) `GET Gamma /events?active=true&closed=false` to refresh live market cache.

4) Order book snapshots (optional for MVP)
- `GET CLOB /book?token_id=<token_id>` for tokens seen in trades.

5) Compute derived features
- seconds_to_end, complete-set edge, pairing delay, hold time, execution type.

6) Run strategy detectors
- Heuristic detectors output confidence + evidence.

7) Present dashboard
- Overview, trades, positions, detectors, and evidence views.

ASCII data flow:

  input -> identity resolve -> proxy_wallet
           |                     |
           v                     v
       Gamma APIs           Data API /trades,/positions,/activity
           |                     |
           v                     v
        market cache          local DB (raw + normalized)
           |                     |
           +------> feature layer <------+
                          |
                          v
                   detector results
                          |
                          v
                        dashboard

## Data model (MVP)

Store raw JSON plus normalized columns to keep the pipeline debuggable.

1) users
- user_id (uuid)
- input (original input string)
- username (from Gamma public-search or public-profile)
- proxy_wallet (Gamma field `proxyWallet`)
- address (address passed to public-profile)
- resolved_at
- source (public-search or public-profile)
- raw_profile_json

2) user_trades
- trade_key (unique; see dedupe rule below)
- proxy_wallet
- username (if known)
- market_slug (`trade.slug`)
- title (`trade.title`)
- token_id (`trade.asset`)
- condition_id (`trade.conditionId`)
- side (`trade.side`)
- outcome (`trade.outcome`)
- outcome_index (`trade.outcomeIndex`)
- price (`trade.price`)
- size (`trade.size`)
- timestamp (`trade.timestamp`)
- transaction_hash (`trade.transactionHash`)
- raw_trade_json (entire `trade` object)
- ingested_at

3) user_positions_snapshots
- proxy_wallet
- snapshot_ts
- positions_json (raw array from `/positions`)
- position_count

4) user_activity_snapshots
- proxy_wallet
- snapshot_ts
- activity_json (raw array from `/activity`)
- activity_count

5) markets
- market_slug (`market.slug`)
- event_id (`event.id`)
- market_id (`market.id`)
- condition_id (`market.conditionId`)
- end_date (`market.endDate` or `market.endDateIso`)
- closed (`market.closed`)
- resolved (`market.resolved`)
- resolution (`market.resolution`)
- uma_resolution_status (`market.umaResolutionStatus`)
- outcomes (`market.outcomes`)
- outcome_prices (`market.outcomePrices`)
- clob_token_ids (`market.clobTokenIds`)
- best_bid (`market.bestBid`)
- best_ask (`market.bestAsk`)
- last_trade_price (`market.lastTradePrice`)
- volume_num (`market.volumeNum`)
- liquidity_num (`market.liquidityNum`)
- captured_at
- raw_event_json
- raw_market_json

6) orderbook_snapshots (optional for MVP)
- token_id
- captured_at
- best_bid_price (from `/book` bids[0].price)
- best_bid_size (from `/book` bids[0].size)
- best_ask_price (from `/book` asks[0].price)
- best_ask_size (from `/book` asks[0].size)
- mid (computed)
- spread (computed)
- book_timestamp_ms (`book.timestamp`)
- book_hash (`book.hash`)
- bids_json
- asks_json

7) trade_features
- trade_key
- seconds_to_end
- paired_trade_delay_seconds
- complete_set_edge_bid
- complete_set_edge_ask
- holding_time_seconds
- exec_type (maker-like / taker-like / inside / unknown)
- computed_at

8) detector_runs
- run_id
- proxy_wallet
- started_at
- completed_at
- params_json
- detector_version

9) detector_results
- run_id
- detector_name
- confidence
- evidence_json
- created_at

Dedupe rule (copied conceptually from `PolymarketUserIngestor`):
- If `transactionHash` is present: `trade_key = transactionHash + ":" + asset + ":" + side`.
- Else: `trade_key = proxy_wallet + ":" + timestamp + ":" + asset + ":" + side`.

## Derived features (MVP)

All features must be reproducible from public data:

- seconds_to_end:
  - Use `market.endDate` from Gamma; fallback: parse `market_slug` for updown-15m
    and add 900 seconds (same logic as polybot `user_trade_enriched`).
- complete_set_edge_bid:
  - If both outcomes are available and `best_bid_price` is known for each token:
    `1 - (bid_up + bid_down)`.
- complete_set_edge_ask:
  - `1 - (ask_up + ask_down)` using best ask.
- paired_trade_delay_seconds:
  - For trades with same `conditionId` and opposite outcome, min abs timestamp delta.
- holding_time_seconds:
  - For buy/sell pairs on same `token_id`, time between open and close.
- exec_type:
  - Use order book to classify maker-like vs taker-like.

## API endpoints (PolyTool)

- `GET /api/health`
- `GET /api/resolve?input=<username_or_wallet>`
- `POST /api/users/ingest`
  - body: `{ "input": "...", "pageSize": 100, "maxPages": 10, "includePositions": true, "includeActivity": true }`
- `GET /api/users/{proxy_wallet}/trades?limit=<n>&offset=<n>`
- `GET /api/users/{proxy_wallet}/positions/latest`
- `GET /api/users/{proxy_wallet}/activity/latest`
- `GET /api/users/{proxy_wallet}/markets`
- `POST /api/users/{proxy_wallet}/detectors/run`
  - body: `{ "detectors": ["complete_set", "momentum", "position", "dca", "liquidity"] }`
- `GET /api/users/{proxy_wallet}/detectors/latest`
- `GET /api/users/{proxy_wallet}/detectors/{run_id}`

## UI pages (MVP)

1) Home
- Input box for username or wallet.
- Resolve identity and show proxy wallet.

2) User overview
- Trade count, notional, first/last trade time.
- Detector summary (confidence per detector).

3) Trades
- Table with filters: market slug, outcome, side, time range.

4) Positions
- Latest positions snapshot (raw view and summary).

5) Strategy detectors
- Each detector card: confidence + evidence.
- Drill-down view for evidence rows (paired trades, sizes, timings).

## Acceptance tests

1) Identity resolution
- Given a known username, `public-search` returns `proxyWallet` and the API
  persists it in `users`.
2) Ingestion and dedupe
- A duplicated trade with the same `transactionHash + asset + side`
  is not stored twice.
3) Market metadata mapping
- Gamma `outcomes` and `clobTokenIds` align by index and map to tokens.
4) Feature computation
- seconds_to_end computed correctly from `market.endDate`.
5) Detector run
- A complete-set pair inside the time window yields confidence > 0.
6) API and UI
- Overview page renders stats for a user with trades.

## Test plan (includes smoke script)

Purpose: Validate end-to-end flow with public endpoints.

Environment variables:
- `POLYTOOL_INPUT` (username or wallet address)
- `POLYTOOL_OUT_DIR` (output dir for stored trades)
- `POLYTOOL_GAMMA_BASE_URL` (default `https://gamma-api.polymarket.com`)
- `POLYTOOL_DATA_API_BASE_URL` (default `https://data-api.polymarket.com`)
- `POLYTOOL_LIMIT` (default `100`)
- `POLYTOOL_PAIR_WINDOW_SECONDS` (default `120`)

Smoke script (recommended path: `tools/cli/smoke_reverse_engineer.py`):

```python
#!/usr/bin/env python3
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

GAMMA = os.getenv("POLYTOOL_GAMMA_BASE_URL", "https://gamma-api.polymarket.com")
DATA = os.getenv("POLYTOOL_DATA_API_BASE_URL", "https://data-api.polymarket.com")
INPUT = os.getenv("POLYTOOL_INPUT", "").strip()
LIMIT = int(os.getenv("POLYTOOL_LIMIT", "100"))
PAIR_WINDOW = int(os.getenv("POLYTOOL_PAIR_WINDOW_SECONDS", "120"))
OUT_DIR = Path(os.getenv("POLYTOOL_OUT_DIR", "./out"))

if not INPUT:
    print("POLYTOOL_INPUT is required", file=sys.stderr)
    sys.exit(1)

def get_json(url):
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "polytool-smoke/1.0"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))

def resolve_identity(user_input):
    if user_input.lower().startswith("0x"):
        profile = get_json(f"{GAMMA}/public-profile?address={user_input}")
        proxy = profile.get("proxyWallet") or user_input
        return {"input": user_input, "username": profile.get("username"), "proxy_wallet": proxy}

    name = user_input.lstrip("@")
    q = urllib.parse.quote(name)
    search = get_json(f"{GAMMA}/public-search?q={q}&search_profiles=true")
    profiles = search.get("profiles", [])
    exact = None
    for p in profiles:
        if str(p.get("username", "")).lower() == name.lower():
            exact = p
            break
    chosen = exact or (profiles[0] if profiles else {})
    proxy = chosen.get("proxyWallet")
    profile = get_json(f"{GAMMA}/public-profile?address={proxy}") if proxy else {}
    return {"input": user_input, "username": chosen.get("username"), "proxy_wallet": proxy, "profile": profile}

def fetch_trades(proxy_wallet):
    q = urllib.parse.urlencode({"user": proxy_wallet, "limit": str(LIMIT), "offset": "0"})
    return get_json(f"{DATA}/trades?{q}")

def detect_complete_sets(trades):
    pairs = 0
    positive_edge = 0
    by_cond = {}
    for t in trades:
        cond = t.get("conditionId")
        if not cond:
            continue
        by_cond.setdefault(cond, []).append(t)
    for cond, rows in by_cond.items():
        rows = sorted(rows, key=lambda r: r.get("timestamp", 0))
        for i, a in enumerate(rows):
            oa = a.get("outcome")
            if oa not in ("Up", "Down", "Yes", "No"):
                continue
            for b in rows[i + 1:]:
                ob = b.get("outcome")
                if ob == oa:
                    continue
                dt = abs(int(b.get("timestamp", 0)) - int(a.get("timestamp", 0)))
                if dt > PAIR_WINDOW:
                    continue
                price_sum = float(a.get("price", 0)) + float(b.get("price", 0))
                edge = 1.0 - price_sum
                pairs += 1
                if edge > 0:
                    positive_edge += 1
                break
    confidence = 0.0
    if pairs > 0:
        confidence = 0.5 * min(1.0, pairs / 10.0) + 0.5 * (positive_edge / pairs)
    return {
        "detector": "complete_set",
        "confidence": round(confidence, 3),
        "evidence": {"pairs": pairs, "positive_edge_pairs": positive_edge},
    }

def detect_dca(trades):
    sizes = [float(t.get("size", 0)) for t in trades if t.get("size") is not None]
    if len(sizes) < 5:
        return {"detector": "dca", "confidence": 0.0, "evidence": {"reason": "insufficient trades"}}
    sizes_sorted = sorted(sizes)
    most_common = max(set(sizes_sorted), key=sizes_sorted.count)
    frac = sizes_sorted.count(most_common) / len(sizes_sorted)
    confidence = min(1.0, frac * 1.2)
    return {
        "detector": "dca",
        "confidence": round(confidence, 3),
        "evidence": {"most_common_size": most_common, "fraction": round(frac, 3)},
    }

def detect_liquidity_proxy(trades):
    near_mid = [t for t in trades if 0.49 <= float(t.get("price", 0)) <= 0.51]
    frac = len(near_mid) / len(trades) if trades else 0.0
    confidence = min(1.0, frac * 1.5)
    return {
        "detector": "liquidity_proxy",
        "confidence": round(confidence, 3),
        "evidence": {"near_mid_fraction": round(frac, 3)},
    }

def main():
    identity = resolve_identity(INPUT)
    proxy = identity.get("proxy_wallet")
    if not proxy:
        print("Could not resolve proxy wallet", file=sys.stderr)
        sys.exit(2)

    trades = fetch_trades(proxy)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "trades.json").write_text(json.dumps(trades, indent=2))

    report = {
        "identity": identity,
        "trade_count": len(trades),
        "detectors": [
            detect_complete_sets(trades),
            detect_dca(trades),
            detect_liquidity_proxy(trades),
        ],
    }
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
```

Run:
```
POLYTOOL_INPUT=someuser POLYTOOL_OUT_DIR=./out python tools/cli/smoke_reverse_engineer.py
```

## Known limitations

- Fills only: you cannot infer resting orders or canceled orders.
- Without WS data, TOB context may be stale for execution-style detection.
- Positions and activity endpoints are stored raw in MVP; normalization is deferred.
