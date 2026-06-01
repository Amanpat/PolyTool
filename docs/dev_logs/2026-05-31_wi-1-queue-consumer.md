# 2026-05-31 — WI-1 Queue Consumer + Arg-Seam Fix

Work packet: `docs/obsidian-vault/claude-memory/work-packets/work-packet-wi-1-queue-consumer.md`
Audit basis: `docs/obsidian-vault/claude-memory/session-notes/2026-05-29-wallet-ingestion-audit-results.md`

## Objective

Build the consumer that drains `scan_queue` -> scan -> dossier -> RIS ingest ->
complete/fail, fix the discovery->scan `--wallet`/`--user` arg mismatch, collapse
ReplacingMergeTree to latest state on queue load, and handle the operator's five
folded-in checks. Research-side only; no DENYLIST files touched.

## What changed

### 1. Arg-seam fix (`tools/cli/wallet_scan.py`)
`_default_scan_callable` previously built `["--wallet", identifier]` for raw
addresses, but `scan.py`'s parser defines only `--user`, so argparse raised
"unrecognized arguments: --wallet" and the discovery->scan handoff was broken.
Now raw addresses are passed via `--user` (a comment documents why). A
regression test asserts the argv shape and that the real scan parser accepts it.

### 2. Queue consumer (`packages/polymarket/discovery/scan_worker.py`, NEW)
`ScanWorker` loop per the packet contract:
`requeue_expired_leases() -> get_pending() -> lease() -> scan callable ->
dossier extract + ingest -> advance watchlist -> complete()`; on exception ->
`fail()`. Dependencies (scan callable, post-scan extractor, watchlist advancer)
are injected so tests run fully offline with a mock. Reuses the existing
scan->dossier->ingest path (`wallet_scan._default_scan_callable`,
`_make_dossier_extractor`, `_read_wallet_from_dossier`) — did not reinvent it.
Bounded run only (`--once` / `--max-items`); no scheduling loop (WP-3).

### 3. CLI (`tools/cli/discovery.py`)
Added a `run-worker` subparser + `_run_worker(args)` dispatch, separate from
`run-loop-a`. Same fail-fast `CLICKHOUSE_PASSWORD` handling (arg > env > exit 1).
Hydrates the queue from ClickHouse, runs the bounded drain, flushes state back.
`--dry-run` reports pending items without scanning/writing.

### 4. RMT latest-state collapse (`packages/polymarket/discovery/scan_queue.py`)
`load_from_clickhouse` now issues `SELECT ... FROM polytool.scan_queue FINAL
ORDER BY dedup_key ASC, updated_at ASC`. Previously it ordered by `dedup_key`
only, so an arbitrary (possibly stale) RMT version could win the in-memory
`self._items[dedup_key] = row` assignment.

### 5. maker/taker rider (`packages/polymarket/data_api.py`)
Documented finding + TODO marker only. No DDL change, no on-chain code.

## Five-check findings

### #1 (BLOCKING) — raw 0x resolution through `--user` + manual smoke
**Resolution path confirmed at code level.** `scan.py::build_config` puts
`args.user` verbatim into `config["user"]`, which is sent as
`{"input": config["user"]}` to `POST /api/resolve` (`run_scan`, scan.py:2320).
scan.py does NOT itself parse 0x-vs-@handle — resolution is server-side.
`services/api/main.py::resolve_user` (line 689) calls
`gamma_client.resolve(request.input)`. `GammaClient.resolve` (gamma.py:255-290)
explicitly detects `input_value.startswith("0x") and len >= 40`, searches by
wallet, and falls back to a minimal `UserProfile(proxy_wallet=input_value)` even
when no Gamma profile exists. So a raw 0x address DOES resolve correctly through
`--user`. The arg fix is sound.

**Manual live smoke: BLOCKED (DoD box left unticked).** The real scan callable
requires the PolyTool API at `http://localhost:8000`. Probe results in this
environment:
- ClickHouse (`localhost:8123`): UP (responded; auth via `.env` password).
- PolyTool API (`localhost:8000/docs`): connection refused (`http_code=000`).
- `docker compose ps`: only `polytool-clickhouse` and `polytool-ris-scheduler-gpu`
  are up; the `api` service (defined in docker-compose.yml:48) is NOT running.

The live scan also needs live Polymarket Data API access + a real wallet with
trade history to produce a genuine dossier. I did NOT start an ad-hoc API or
fabricate a smoke result. **The live-resolution smoke is therefore environmentally
blocked and the corresponding DoD line is left unticked.** Re-run after
`docker compose up -d api` with a real address, e.g.:
`python -m polytool discovery run-worker --once` (with the wallet enqueued).

**Offline structural smoke: PASSED.** To prove the worker wiring end-to-end
(minus live resolution), an offline smoke ran the worker against a real
in-memory `KnowledgeStore` with the scan callable stubbed to a prebuilt scan
run_root (coverage report + dossier.json). Result:
lease -> (stub) scan -> dossier extract -> RIS ingest (1 source_document +
1 derived_claim) -> watchlist advance to `scanned` -> queue row `done`. This
confirms the connective tissue; it does NOT substitute for the live-resolution
smoke above.

### #2 (BLOCKING) — watchlist lifecycle advance (discovered -> scanned)
**Finding: NOT advanced anywhere before WI-1.** Loop A writes
`lifecycle_state=discovered` for new wallets (`loop_a.py:179`). The reused
`PostScanExtractor` path only writes dossier findings to the KnowledgeStore — it
never touches the watchlist. So without WI-1 a scanned wallet stayed
`discovered`, and WI-4's review gate would have nothing to promote.

**Added by WI-1.** On a successful scan the worker calls a `WatchlistAdvancer`.
The default (`make_clickhouse_watchlist_advancer` in `scan_worker.py`) writes a
fresh `WatchlistRow` with `lifecycle_state=scanned`, `last_scan_run_id`,
`last_scanned_at`, and a newer `updated_at`; the watchlist is
`ReplacingMergeTree(updated_at)` keyed on `wallet_address`, so this collapses to
`scanned`. Stays in WI-1 scope: no tiers/locks (WP-4), no promotion (still
behind the existing human review gate). `--no-advance-watchlist` disables it.

### #3 (document-only) — lease atomicity
Single-worker assumption documented in the `scan_worker.py` module docstring
("SINGLE-WORKER ASSUMPTION") and here: the in-memory lease is not an atomic
CAS against ClickHouse, so `get_pending -> lease` across two workers can
double-grab a row (TOCTOU). WI-1's bounded single-process `--once`/`--max-items`
never triggers it. WP-3's continuous/multi-worker mode must consciously add real
lease atomicity. Not fixed here (out of scope).

### #4 — RMT collapse parity (actual version column)
**Actual version column = `updated_at`.** `infra/clickhouse/initdb/27_wallet_discovery.sql`
line 100: `ENGINE = ReplacingMergeTree(updated_at) ORDER BY (dedup_key)`.
`updated_at` exists and IS the RMT version column, so `max(updated_at)` per
dedup_key equals what `FINAL` returns. Collapsed on `updated_at` (via
`FINAL` + `ORDER BY dedup_key, updated_at ASC`). Verified by
`test_latest_updated_at_version_wins`.

### #5 — poison-pill ceiling
**Finding: `ScanQueueManager` itself has NO attempt ceiling.** `fail()` and
`requeue_expired_leases()` increment `attempt_count` but never cap it; the
`dropped` terminal state exists in the enum but nothing set it. In a continuous
drain a wallet that errors every time would requeue forever.
**Decision: minimal ceiling added in the worker (not the manager).** The
`ScanWorker` dead-letters a pending row whose `attempt_count >= max_attempts`
(default 5) to `dropped` and skips it, so a bounded drain can never loop on one
poison pill. Continuous-mode cadence + operator dead-letter reporting remain
WP-3. Verified by `test_row_over_ceiling_is_dead_lettered` and
`test_dropped_row_stays_terminal`.

## maker/taker investigation outcome
**ABSENT.** The Polymarket Data API `/trades` response (parsed by
`packages/polymarket/data_api.py::Trade.from_api_response`) carries only `side`
(BUY/SELL) — there is no per-fill maker/taker liquidity flag. The `Trade`
dataclass has no maker/taker field, `infra/clickhouse/initdb/02_tables.sql`
`user_trades` has no maker/taker columns, and the `llm_research_packets.py`
position export (lines 1599-1639) aggregates per-position (no per-fill flag
could survive). Per the audit, maker/taker is recoverable only from the raw
Jon-Becker parquet via DuckDB. Per the packet (absent -> document + TODO, add NO
on-chain code): added a clearly-marked TODO comment in `data_api.py` referencing
the deferred insider/on-chain path. No DDL column added, no Alchemy/log code.

## Tests

Command: `python -m pytest tests/test_wallet_discovery.py
tests/test_wallet_discovery_integrated.py tests/test_wallet_integration.py
tests/test_wallet_scan_dossier_integration.py tests/test_wallet_scan.py
tests/test_scan_worker.py -q`

Result: **142 passed, 0 failed, 0 skipped.**

New `tests/test_scan_worker.py` (13 tests): happy path (lease->scan->ingest->
complete), watchlist advance called, scan-only mode, failure->fail+attempt
increment, ingest-failure-does-not-fail-the-row, expired-lease requeue,
idempotency (run twice no double-scan), already-leased-not-double-grabbed,
poison-pill dead-letter (x2), bounded multi-item, RMT collapse, arg-seam
regression.

Adjacent spot-check: `tests/test_scan_quick_mode.py tests/test_loop_b_probe.py`
= 51 passed (no breakage from the `data_api.py` / `discovery.py` edits).

CLI smoke: `python -m polytool --help` loads; `python -m polytool discovery
--help` shows `run-worker`; `run-worker` fail-fast returns exit 1 with no
`CLICKHOUSE_PASSWORD`.

## Codex review note
Per CLAUDE.md Codex policy, `scan_worker.py` / `scan_queue.py` are research-side
(not in the mandatory adversarial-review denylist: no execution/kill-switch/
signing/order-placement code). Tier: **Recommended**. Not run in this session;
flagged for an optional `--background` review.

## DoD status
- [x] Raw wallet address scans through the default path (code-confirmed; arg fix + parser-accepts test).
- [x] Consumer leases -> scan -> dossier -> RIS ingest -> complete (offline structural smoke + tests).
- [x] Failure path marks `fail`; expired leases requeue within attempt limits.
- [x] Queue read returns latest RMT state per dedup_key.
- [x] maker/taker documented as unavailable + deferred (TODO marker).
- [x] `discovery run-worker` exists, separate from `run-loop-a`.
- [x] **Manual LIVE smoke — PASSED 2026-05-31** (PolyTool API back up + healthy).
  See "Manual Live Smoke (2026-05-31)" below.

## Manual Live Smoke (2026-05-31)

**Verdict: PASS.** The previously-blocked live end-to-end smoke was re-run against
the live stack (PolyTool API `localhost:8000` reported `{"status":"healthy"}`;
`polytool-clickhouse` and `polytool-api` containers both healthy). A raw 0x wallet
address flowed all the way through the worker: lease -> live scan (raw address
resolved via `--user`, NOT a handle) -> dossier produced -> findings ingested into
the KnowledgeStore -> watchlist advanced to `scanned` -> queue row `complete`.

### Wallet used
- **Raw address:** `0x84cfffc3f16dcc353094de30d4a45226eccd2f63`
- **Why:** top wallet by 7-day volume on the live Polymarket leaderboard
  (`userName=mooseborzoi`, ~$2.18M weekly volume) — a real, highly-active wallet
  with deep trade history. Pulled from the live leaderboard via
  `packages.polymarket.discovery.leaderboard_fetcher.fetch_leaderboard(order_by="VOL", time_period="WEEK")`.
- **Raw-address resolution confirmed:** the scan emitted
  `Proxy wallet: 0x84cfffc3f16dcc353094de30d4a45226eccd2f63` and ingested
  `pages=4, fetched=4000, written=4000, distinct=3931` real trades. The
  identifier was passed through `--user` (the only flag scan.py defines); a raw
  0x address — not an @handle — was resolved server-side to a wallet. This is the
  exact point the smoke had to prove.

### Enqueue path
Used the **sanctioned queue API** — `ScanQueueManager.enqueue(...)` +
`flush_to_clickhouse(...)` — NOT a hand-written `INSERT`. (Loop A's churn-driven
enqueue was not used because, with no prior leaderboard snapshot for the
PNL/DAY/OVERALL key, its dry-run reported `new_wallets=0`, so it would not have
deterministically populated the queue. The queue's own enqueue+flush path is the
same API Loop A itself calls — `loop_a.py:165-170` — so this exercises the real
persistence seam.) Enqueued with `source="manual", priority=1,
source_ref="WI-1 live smoke 2026-05-31"`.

### Exact commands run
```powershell
# (CLICKHOUSE_PASSWORD loaded from .env into the env the fail-fast way; never printed)

# 1. Pre-state baseline (both queue + watchlist empty; KS totals recorded)
#    scan_queue FINAL = 0 rows; watchlist FINAL = 0 rows
#    KS source_documents = 149; derived_claims = 4891; wallet-specific SD = 0

# 2. Enqueue the real wallet via the sanctioned queue API
python -  <<  (ScanQueueManager().enqueue("0x84cf...2f63", source="manual",
             priority=1, source_ref="WI-1 live smoke 2026-05-31")
             then .flush_to_clickhouse(host=localhost, port=8123,
             user=polytool_admin, password=$CLICKHOUSE_PASSWORD))
# -> ENQUEUED dedup_key=manual:0x84cf...2f63 state=pending; FLUSHED: True

# 3. Run the bounded worker once against the live stack
python -m polytool discovery run-worker --once
```

### Per-stage evidence

| Stage | Evidence | Result |
|-------|----------|--------|
| Queue lifecycle | `scan_queue FINAL`: `dedup_key=manual:0x84cf...2f63 queue_state=done lease_owner=scan-worker attempt_count=0 last_error=NULL`. Pre-run it was `pending`; the worker reported `leased=1, completed=1, failed=0`. | pending -> leased -> **done** |
| Worker summary | `requeued=0 leased=1 completed=1 failed=0 dropped=0 skipped=0 flushed_ch=True` | PASS |
| Live raw-0x resolution | Scan output `Proxy wallet: 0x84cfffc3f16dcc353094de30d4a45226eccd2f63`; 4000 trades fetched/written, 3931 distinct; detector + PnL sections emitted. Resolved via `--user` (not a handle). | PASS |
| Dossier produced | Run root `artifacts/dossiers/users/unknown/0x84cfffc3f16dcc353094de30d4a45226eccd2f63/2026-05-31/e6392b72-4f17-4b3f-92b6-2012c8b3e6f9/` — `dossier.json` (304 KB), `coverage_reconciliation_report.json`, `segment_analysis.json`, `hypothesis_candidates.json`, `run_manifest.json`, etc. all present on disk. | PASS |
| RIS ingest (KnowledgeStore) | KS `kb/rag/knowledge/knowledge.sqlite3`: `source_documents` 149 -> **151** (+2), `derived_claims` 4891 -> **4893** (+2). The 2 new docs both `source_family=dossier_report` for this wallet: "Dossier Detectors: 0x84cf...2f63" and "Dossier Hypothesis Candidates: 0x84cf...2f63", each with 1 derived claim. | PASS |
| Watchlist lifecycle | `watchlist FINAL`: `wallet=0x84cf...2f63 lifecycle_state=scanned review_status=pending last_scan_run_id=e6392b72-4f17-4b3f-92b6-2012c8b3e6f9 last_scanned_at=2026-05-31 21:34:44`. `last_scan_run_id` matches the dossier run root name. | discovered/queued -> **scanned** |

### Notes / caveats (no implementation changed)
- The dossier wrote under `users/unknown/...` because no Gamma username resolved
  for this wallet — expected and harmless; the `GammaClient.resolve` minimal-
  profile fallback (`proxy_wallet=input`) is exactly the raw-0x path. The worker
  reads the wallet back from the dossier via `_read_wallet_from_dossier` and the
  watchlist row keys on `wallet_address`, so resolution is correct regardless of
  the display slug.
- Scan emitted non-fatal warnings: `POLYGON_RPC_URL`/`POLYMARKET_SUBGRAPH_URL`
  not set (on-chain + subgraph resolution providers skipped, 242 outcomes remain
  PENDING/UNKNOWN). This is an environment-config gap in the resolution cascade,
  NOT a worker/queue bug — the scan still completed, produced a dossier, and the
  queue row completed cleanly. Out of WI-1 scope.
- No implementation code was modified for this smoke; only the dev log was updated.

## Files
- `packages/polymarket/discovery/scan_worker.py` (new)
- `tools/cli/discovery.py` (run-worker subparser + `_run_worker`)
- `tools/cli/wallet_scan.py` (arg-seam fix)
- `packages/polymarket/discovery/scan_queue.py` (RMT collapse on load)
- `packages/polymarket/data_api.py` (maker/taker TODO marker)
- `tests/test_scan_worker.py` (new, 13 tests)
- `docs/CURRENT_STATE.md` (WI-1 section)
