# LLM Research Packets (v1)

LLM Research Packets export a deterministic User Dossier JSON plus a human-readable Research Memo markdown
for a single user and time window. Each export is written to `artifacts/` and stored in ClickHouse so you can
track changes over time.

## What gets exported

- **User Dossier JSON** (`dossier.json`)
  - Header: user input, proxy wallet, generated_at, window_start/end, window_days, max_trades
  - Coverage: trade/activity/position counts + mapping coverage
  - PnL summary: latest bucket + simple 30d trend stats
  - Distributions: buy/sell ratio, active days, trades/day, top categories/markets, notional histogram, hold-time approx
  - Liquidity summary: snapshot status counts, usable rate, execution cost stats, top/bottom tokens by exec cost
  - Detectors: latest labels/scores + recent trend
  - Anchors: curated trade samples (last/top notional/outliers) with full trade metadata

- **Research Memo** (`memo.md`)
  - A ready-to-fill template with auto-filled coverage/caveats and an evidence anchor table
  - Includes the hard rule: **any strategy claim must cite dossier metrics or trade_uids**

## How to generate

### API

`POST /api/export/user_dossier`

Request body:
```
{
  "user": "@handle_or_wallet",
  "days": 30,
  "max_trades": 200
}
```

Response body:
```
{
  "export_id": "...",
  "proxy_wallet": "...",
  "username": "@handle_or_empty",
  "username_slug": "handle_or_unknown",
  "artifact_path": "artifacts/dossiers/users/<username_slug>/<proxy_wallet>/<YYYY-MM-DD>/<run_id>/",
  "generated_at": "...",
  "path_json": "artifacts/dossiers/users/<username_slug>/<proxy_wallet>/<YYYY-MM-DD>/<run_id>/dossier.json",
  "path_md": "artifacts/dossiers/users/<username_slug>/<proxy_wallet>/<YYYY-MM-DD>/<run_id>/memo.md",
  "stats": { ... }
}
```

Optional history endpoint:

`GET /api/export/user_dossier/history?user=@handle_or_wallet&limit=20`

Use `include_body=true` if you want full JSON/memo fields returned.

### CLI

```
python -m polyttool export-dossier --user "@Pimping" --days 30 --max-trades 200
```
```
python -m polyttool export-dossier --wallet "0x..." --days 30 --max-trades 200
```

Artifacts are written to:

`artifacts/dossiers/users/<username_slug>/<proxy_wallet>/<YYYY-MM-DD>/<run_id>/`

Each export also includes a small `manifest.json` alongside the memo with the proxy wallet,
username label, slug, run id, created_at_utc, and path.

`username_slug` is derived from the resolved handle: trimmed, lowercased, and non `[a-z0-9_-]`
characters become `_`. Missing/empty usernames are recorded as `unknown`.

## ClickHouse history

Exports are stored in `polyttool.user_dossier_exports`. The latest export per wallet is in
`polyttool.user_dossier_exports_latest`.

Note: `proxy_wallet` remains the canonical ID for joins and API params. `username` is stored as a
human-friendly label and only appears once a handle has been resolved (either from a handle-based
request or a stored username for that wallet).

Example queries:

Fetch latest export summary for a user:
```
SELECT
  proxy_wallet,
  export_id,
  generated_at,
  trades_count,
  activity_count,
  positions_count,
  mapping_coverage
FROM polyttool.user_dossier_exports_latest
WHERE proxy_wallet = '0x...';
```

Compare two exports by id:
```
SELECT
  export_id,
  generated_at,
  trades_count,
  activity_count,
  positions_count,
  mapping_coverage,
  usable_liquidity_rate
FROM polyttool.user_dossier_exports
WHERE export_id IN ('<id_a>', '<id_b>')
ORDER BY generated_at;
```

Pull full dossier/memo for a specific export:
```
SELECT export_id, dossier_json, memo_md
FROM polyttool.user_dossier_exports
WHERE export_id = '<id>';
```

## Using with Opus

Paste the `memo.md` first, then attach the `dossier.json` for detailed metrics. Ensure every claim in the memo
references a dossier metric or an anchor `trade_uid`.

## Rules

- All strategy claims must cite dossier metrics or trade_uids.
