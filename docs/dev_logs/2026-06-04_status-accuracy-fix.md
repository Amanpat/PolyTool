# `/status` Top-N Accuracy Fix (DR-3 follow-up)

Date: 2026-06-04
Packet: `work-packet-dr-3-discord-status` (contents fix, not layout)
Mode: fix. Read-only `/status` → no Codex adversarial review; denylist untouched;
no git add/commit.

## Objective

The DR-3 `/status` card layout was correct, but its **contents** were wrong:
blank usernames, `$0` realized PnL, and "1 pos" for every wallet. Fix the
contents (against fresh data, not the stale pre-username-fix run), keep the
layout, single session, no sub-agents.

## STEP 0 — Fresh data first

Ran (with `.env` loaded so `CLICKHOUSE_PASSWORD` + resolution vars are present):

```
python -m polytool wallet-scan --input artifacts/watchlists/top5.txt --extract-dossier
```

Completed clean (exit 0), 5/5 wallets, dossiers extracted. **No "CLV cache 516"
warning.** Fresh `leaderboard.json` written to
`artifacts/research/wallet_scan/2026-06-04/0a3043a9-f1fd-4bde-96ef-86c9f32e82c1/`.

## STEP 1 — Diagnosis (against fresh data)

| Symptom | Root cause (confirmed) | Verdict |
|---|---|---|
| **Username blank** | `/status` joined `leaderboard_snapshots` for the username — **0 rows** for these 5 (that table is fed only by Loop-A discovery, never by `wallet-scan --input`). The `users` / `user_dossier_exports_latest` rows that wallet-scan *does* write also carry **empty username**, because the scan's `/api/resolve` returns no handle for these wallets. The real handles (Countryside, JewishNinja, downtownfee, Tiger200) exist only on the live `/v1/leaderboard` API and in nothing `/status` reads. | wrong read-source **+** write-path gap |
| **`$0` PnL** | `_top_wallets` used `argMax(realized_pnl, computed_at)` over `user_pnl_bucket` day buckets = the latest bucket = **0**. **Summing buckets does NOT recover lifetime PnL** either (sum = `0/0/2446/3969/0` vs leaderboard `+885k/+193k/-477k/-698k/-1.8M`). The bucket table is a 30-day orderbook-priced estimate (LOW confidence) — a *different computation* from the resolved lifetime PnL the leaderboard ranks on. | fix = read the source leaderboard.json uses |
| **"1 pos" for all** | Same query: `argMax(open_position_tokens)` = 1 for everyone. Real counts (`positions_total` = `5/4/50/50/50`) live in `leaderboard.json`. | fix alongside PnL |
| **Counters all 0** | `scan_queue` and `watchlist` are empty. `wallet-scan --input` is a manual batch path that does not enqueue or write the watchlist (that's the scheduler's path). 0 is a truthful read of empty scheduler tables. | **correct, not a bug — left as-is** |

Conclusion: the correct, differentiated Top-N data (lifetime PnL, positions,
ranking, username) lives in `leaderboard.json`, which is mounted **read-only**
into the bot (`docker-compose.yml`: `./artifacts:/app/artifacts:ro`; container
WORKDIR `/app`). This is exactly the packet's authorized PnL fix ("the same
source leaderboard.json uses") and matches the verification bar ("matches
leaderboard.json ordering").

## STEP 2 — Fix (confirmed bugs only)

`packages/polymarket/discord_bot/status_window.py`:

- **New `load_top_wallets_from_leaderboard(top_n, *, artifacts_root=None)`** —
  finds the newest `research/wallet_scan/*/*/leaderboard.json` by mtime and maps
  each ranked entry → `TopWallet(wallet_address=identifier, username=raw,
  realized_pnl=realized_net_pnl, open_positions=positions_total)`. Best-effort:
  returns `None` (degraded "topN") on missing/unreadable file, never raises.
  Artifacts root defaults to `artifacts` (CWD-relative; container `/app/artifacts`),
  overridable via `POLYTOOL_ARTIFACTS_ROOT`.
- **`assemble_status(..., leaderboard_loader=None)`** — injectable loader (default
  the above) replaces the `user_pnl_bucket` + `leaderboard_snapshots` Top-N query.
  Tiles/health still read ClickHouse (`scan_queue`, `watchlist`).
- **Embed Username column** now renders `polytool.user_context.display_name(
  username, wallet_address)` → real handle when present, else a truncated wallet
  ID, **never blank**.
- Removed the old CH `_top_wallets` query. Module read-only contract preserved
  (the only change is a plain file read for Top-N; no write surface).

Tiles/counter logic was **not** changed — 0 is the correct read of the empty
scheduler tables after a manual batch scan.

## STEP 3 — Verification

- `tests/test_status_window.py`: updated Top-N tests to inject a fake
  `leaderboard_loader`; adjusted the username-column assertion for the
  `display_name` fallback (truncated wallet, never em-dash); added
  `test_load_top_wallets_from_leaderboard` (tmp-file artifact: field mapping,
  newest-by-mtime selection, blank-username → wallet fallback) and
  `test_load_top_wallets_missing_leaderboard_returns_none`. **18 passed.**
- Related suites: `test_status_window` + `test_user_context` +
  `test_vera_discord_bot` + `test_vera_approvals` → **115 passed**.
- Full repo (non-RIS): `pytest tests/ -k "not ris and not fetch_pdf and not
  fetch_url"` → **3781 passed, 0 failed, 1889 deselected** (exit 0, 120s).
  - The 1889 deselected = the RIS subsystem. The full `pytest tests/` run cannot
    complete in this environment: **pre-existing native segfaults** (Windows
    "access violation", exit 139) in `test_ris_fetchers.py` and in a
    `transformers`/`torch` `from_pretrained` model load during a later RIS test —
    both crash the interpreter, both unrelated to this change (a pure-Python
    Discord status assembler doing file reads + SQL SELECTs). Every non-RIS test
    in the repo passes.
- **Live render against fresh real data** (`read_status_snapshot` → real
  ClickHouse + real `leaderboard.json`):
  - PnL: `+$885.5k / +$193.1k / -$477.1k / -$698.8k / -$1.8m` — non-zero,
    differentiated, **matches leaderboard.json ordering exactly**.
  - Positions: `5 / 4 / 50 / 50 / 50` — matches `positions_total`.
  - Username: truncated-wallet fallback for all 5 (their scan-resolved username
    is empty), never blank.
  - Tiles: `0` (correct — empty scheduler queue/watchlist).

## Open items / known gaps (operator-gated)

- **Real-handle write-path gap.** The 5 top wallets DO have handles on
  `/v1/leaderboard` (Countryside / JewishNinja / downtownfee / Tiger200; dc71 is
  a genuine auto-generated handle), but the scan's `/api/resolve` returns none, so
  `users` / `user_dossier_exports_latest` store blank usernames and the card falls
  back to truncated wallet IDs. Closing this is a separate write-path change:
  generate the `<input>.usernames.json` sidecar via `export-leaderboard` (the
  designed mechanism) before scanning, or run a Loop-A leaderboard snapshot so the
  handles are captured. Not done here (out of the "fix the card contents" scope;
  needs operator direction on which mechanism to wire in).
- **Live `/status` channel verification** still pending a running gateway with
  `DISCORD_BOT_TOKEN` (unchanged from DR-3).

## Files touched

- `packages/polymarket/discord_bot/status_window.py` (Top-N source + display fallback)
- `tests/test_status_window.py` (loader injection + new loader tests)
- `docs/CURRENT_STATE.md` (DR-3 Top-N accuracy note)
- `docs/dev_logs/2026-06-04_status-accuracy-fix.md` (this log)

No commit (per packet).
