# Dev Log: Telonex MM Wallet Scan — Address Resolution Blocker

**Date:** 2026-03-29
**Branch:** phase-1B

## Objective

Scan two pure market-making wallets identified in the Telonex "Top 15m Crypto Traders"
research article for crypto bracket patterns, using the same pipeline run against gabagool22.
Produce gap reports in `artifacts/dossiers/users/telonex_mm_wallet_1/` and
`artifacts/dossiers/users/telonex_mm_wallet_2/`.

## Target Wallets

| Wallet | Truncated | Edge | PnL (Feb 2–8) | Volume | Markets | Maker % |
|--------|-----------|------|----------------|--------|---------|---------|
| 1 | `0x7163...a9e5` | 81% | $14,547 | $17,978 | 2,060 | 100% |
| 2 | `0xf49a...f9ba` | 80% | $23,011 | $28,641 | 2,666 | 100% |

Both wallets are pure MM bots — 100% maker ratio, quoting across thousands of simultaneous
15m BTC/ETH/SOL/XRP updown bracket markets. Neither is a directional trader.

## What Was Run

No scan commands were executed. The task blocked entirely at address resolution.

## Resolution Approaches Tried

### Local ClickHouse DB
- Searched `polytool.user_trades` and `polytool.users` for `proxy_wallet LIKE '0x7163%'` and `LIKE '0xf49a%'`.
- `polytool.jb_trades` was inspected — confirmed no wallet address columns (trade-level aggregates only).
- **Result:** No rows. These wallets are not in any local table.

### Local API `/api/resolve` (POST http://localhost:8000/api/resolve)
- Tried `{"input": "0x7163"}`.
- **Result:** Returned `0x716358720f83e4bf9388151c84bc174d96abbc50` (ends in `bc50`, not `a9e5`). Wrong wallet.
- `0xf49a` prefix returned no match.

### Gamma public-search
- `https://gamma-api.polymarket.com/profiles/public-search?q=0x7163`
- **Result:** No profile-registered match. Pure MM bots have no Polymarket username.

### Gamma profiles prefix filter
- `https://gamma-api.polymarket.com/profiles?proxy_wallet_prefix=0x7163`
- **Result:** `invalid token/cookies` — requires authentication.

### Polymarket CLOB API (`/trades`)
- Requires API key. `.env` has placeholder `CLOB_API_KEY=replace_with_clob_api_key`.
- **Result:** Unauthorized.

### Polymarket data-api
- `https://data-api.polymarket.com/activity?user=0x7163a9e5&limit=1`
- **Result:** `"required query param 'user' not provided"` — rejects non-42-char addresses.

### Polygon RPC
- `https://polygon-rpc.com` → HTTP 403: "API key disabled, tenant disabled."
- **Result:** Public endpoint unavailable without a key.

### Polygonscan API
- V1 deprecated; V2 requires API key not in `.env`.
- **Result:** No key available.

### Telonex GitHub notebook (1.4 MB)
- Fetched raw notebook via ScraplingServer. Searched all 40 cells for `7163`, `a9e5`, `f49a`, `f9ba`.
- **Result:** All occurrences are truncated form only. No full addresses in any cell.

### The Graph / Polymarket subgraph
- `https://api.thegraph.com/subgraphs/name/polymarket/polymarket-matic`
- `_meta` query returned empty body — subgraph appears deprecated/inactive.
- `orderFilledEvents` with `maker_starts_with` filter returned no output.

### Polymarket leaderboard API
- `https://gamma-api.polymarket.com/leaderboard?window=weekly` → `404 page not found`.

## Root Cause

The full addresses exist only in the **Telonex paid on-chain fills dataset** (Feb 2–8, 2026).
The Telonex research article deliberately anonymizes to 8 hex characters (4 prefix + 4 suffix)
to protect their commercial dataset. No public API, local database, or public repository
contains the full addresses.

## Output

- `artifacts/dossiers/users/telonex_mm_wallet_1/BLOCKER.md`
- `artifacts/dossiers/users/telonex_mm_wallet_2/BLOCKER.md`

Both documents contain the full resolution attempt log, known wallet statistics, and
the unblock path.

## Unblock Path

1. **Purchase Telonex dataset** — filter `maker_address LIKE '0x7163%' AND ... LIKE '%a9e5'`
   and `LIKE '0xf49a%' AND ... LIKE '%f9ba'`.
2. **Configure Polygon RPC** — valid Alchemy/Infura key + query CTF Exchange `OrderFilled`
   event logs for maker addresses matching the prefix/suffix pattern.
3. **Configure CLOB API key** — `/trades?user=<addr>` with a valid key may support
   wallet enumeration by prefix.
4. **Dune Analytics** — Polygon blockchain with maker address wildcard filter.

## Signal Value (even without scan)

The Telonex statistics alone are informative for Track 2 strategy design:

- **100% maker confirms the bet:** The profitable trade is accumulating maker positions,
  not taking. Both wallets are pure makers with 80–81% edge — meaning they collected
  ~$0.80 of profit per $1.00 of volume.
- **Scale:** 2,060–2,666 simultaneous markets means these bots quote continuously across
  every available BTC/ETH/SOL/XRP bracket, not selectively.
- **Pair cost hypothesis supported:** At 80%+ edge on 100% maker fills, these bots are
  almost certainly accumulating pair costs well below $1.00 — consistent with the gabagool22
  finding that 42% of pairs were acquired below $1.00 (taker path).
- **The maker path should achieve lower pair costs than gabagool22's taker path** — this is
  the core Track 2 thesis, and Telonex data is consistent with it.

## No Pipeline Code Modified

Per task constraint: zero changes to any pipeline code.
