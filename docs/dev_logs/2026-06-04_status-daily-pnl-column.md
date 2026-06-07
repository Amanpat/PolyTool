# Status Daily PnL Column

Date: 2026-06-04
Agent: Codex
Scope: Add a Daily PnL column to Vera `/status` and verify the existing scan
tiles still read from ClickHouse.

## Files Changed

- `packages/polymarket/discord_bot/status_window.py` - added best-effort Daily
  PnL enrichment for the Top-N leaderboard rows from
  `polytool.user_pnl_bucket` (`bucket_type='day'`, `toDate(bucket_start)=today()`),
  rendered `Daily PnL` before lifetime `Net PnL`, and made the optional
  `ris_documents` footer probe check `system.tables` first so an absent optional
  table does not log a false ClickHouse error.
- `tests/test_status_window.py` - covered Daily PnL enrichment, render ordering,
  and failure behavior (`dailyPnL` degrades without hiding the Top-N).
- `docs/CURRENT_STATE.md` - recorded the Daily PnL follow-up under the DR-3
  `/status` state.
- `docs/dev_logs/2026-06-04_status-daily-pnl-column.md` - this handoff log.

## Behavior

The ranked Top-N still comes from the latest
`artifacts/research/wallet_scan/<date>/<run>/leaderboard.json`, preserving the
lifetime resolved `realized_net_pnl` ordering and positions. The new Daily PnL
column is an additive read from `polytool.user_pnl_bucket` for the same wallet
addresses already in the leaderboard. If that query fails, `/status` records
`dailyPnL` in the degraded notes and renders em-dashes for Daily PnL while the
leaderboard, usernames, and Net PnL still render.

The four tiles continue to use the existing ClickHouse readers:

- `In queue`: `polytool.scan_queue FINAL`, states `pending` + `leased`.
- `Failed`: `polytool.scan_queue FINAL`, state `failed`.
- `Scanned today`: `polytool.watchlist FINAL`, `lifecycle_state='scanned'` and
  `toDate(last_scanned_at)=today()`.
- `Pending review`: `polytool.watchlist FINAL`, candidate/pending/scanned filter
  with the pre-migration fallback still intact.

Live direct ClickHouse checks returned no rows for `scan_queue` or `watchlist`, so
the screenshot's zero tile values are the current DB state, not hardcoded values.

## Live Deployment Verification

Rebuilt and recreated only `vera-bot`:

```text
docker compose build vera-bot
...
polytool-vera-bot  Built
```

```text
docker compose up -d vera-bot
Container polytool-vera-bot  Recreate
Container polytool-vera-bot  Recreated
Container polytool-vera-bot  Started
```

Service state:

```text
docker compose ps vera-bot
NAME                IMAGE               COMMAND                  SERVICE    CREATED          STATUS          PORTS
polytool-vera-bot   polytool-vera-bot   "python -m packages.…"   vera-bot   15 seconds ago   Up 12 seconds
```

Running-container `/status` payload check:

```text
snap_none False
tiles {'in_queue': 0, 'scanned_today': 0, 'pending_review': 0, 'failed': 0, 'degraded': []}
```

Top-N fields returned by the deployed reader:

```json
[
  {
    "name": "Wallet ID",
    "value": "`0xf883…cd1f`\n`0xa380…21ff`\n`0xbddf…c684`\n`0x6211…b89e`\n`0xbee5…a636`",
    "inline": true
  },
  {
    "name": "Username",
    "value": "Inaccuratestake\nJewishNinja\nCountryside\nTiger200\ndowntownfee",
    "inline": true
  },
  {
    "name": "Daily PnL",
    "value": "+$0\n+$0\n+$0\n+$0\n+$0",
    "inline": true
  },
  {
    "name": "Net PnL",
    "value": "+$1.3m · 27 pos\n+$885.5k · 5 pos\n-$146.6k · 50 pos\n-$894.6k · 50 pos\n-$1.8m · 50 pos",
    "inline": true
  }
]
```

Bot logs after the final rebuild:

```text
2026-06-04 20:38:11,873 INFO vera.bot: Slash commands synced to guild 1411788462142783551 (instant).
2026-06-04 20:38:12,404 INFO discord.gateway: Shard ID None has connected to Gateway (Session ID: d8690637f2177363bd0054007ea4f3cc).
2026-06-04 20:38:14,417 INFO vera.bot: Vera is online as VERA#2261 (id=1497296971130474566).
```

The prior optional `ris_documents` 404 was gone after the `system.tables` guard.

## Commands Run

- `python -m pytest tests/test_status_window.py -q` - RC 0,
  `19 passed, 1 warning`.
- `docker compose build vera-bot` - RC 0, `polytool-vera-bot  Built`.
- `docker compose up -d vera-bot` - RC 0, `polytool-vera-bot  Started`.
- `docker exec polytool-vera-bot ... read_status_snapshot ...` - RC 0,
  `snap_none False`, `degraded=[]`, tiles all `0`, Daily PnL column present before
  Net PnL.
- `docker exec polytool-clickhouse clickhouse-client --query "SELECT queue_state, count() ... scan_queue ..."` -
  RC 0, empty output (no queue rows).
- `docker exec polytool-clickhouse clickhouse-client --query "SELECT lifecycle_state, review_status, tier, locked, count() ... watchlist ..."` -
  RC 0, empty output (no watchlist rows).
- `python -m polytool --help` - RC 0, CLI loaded.
- `python -m pytest tests/ -x -q --tb=short` - RC 1,
  stopped at `tests/test_ris_phase4_source_acquisition.py::TestEndToEnd::test_ingest_external_arxiv_fixture`;
  result before stop: `1 failed, 3522 passed, 1 skipped, 3 deselected, 22 warnings`.
  Failure was unrelated to `/status`: `academic_marker_gate` rejected an arXiv
  fixture because `body_source='abstract'` and `body_length=0`.

## Decisions

- Daily PnL is displayed from `user_pnl_bucket` but does not affect leaderboard
  ordering. Lifetime Net PnL remains sourced from `leaderboard.json`.
- Kept `/status` read-only: new queries are SELECTs only; no writer/import/action
  path added.
- Did not touch denylist, kill switch, signing, order/price, risk manager, or
  rate limiter logic.
- Did not commit.

## Open Questions / Blockers

- Final Discord-client visual confirmation still requires the operator to invoke
  `/status`; the deployed container payload has already been verified.
- Full-suite smoke is blocked by the unrelated RIS Phase 4 fixture failure noted
  above.

## Codex Review Summary

Tier: recommended for `/status` correctness; no Mandatory review files touched.
Issues found/addressed: Daily PnL missing from the status card; added as a
best-effort read-only enrichment with targeted tests. Optional RIS-docs table
absence caused noisy logs; guarded with a read-only `system.tables` check.
