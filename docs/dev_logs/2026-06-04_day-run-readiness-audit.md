# Wallet-Ingestion Day-Run Readiness Audit

Date: 2026-06-04
Mode: read-only forensic audit, except for this requested report file.

Rules applied:

- Docs, comments, filenames, and named paths were treated as unverified until code, DDL, tests, or command output supported them.
- No code, config, migration, or pipeline command was modified or run.
- The only file write was this report.

## 1. Scheduler Runtime

Answer: there is a wallet-discovery scheduler entry point that can run unattended as a blocking process, but the queue drain is not continuous; it is a recurring APScheduler cron job that runs one bounded worker tick per fire.

Entry point:

- `python -m polytool discovery scheduler start` is the compose command for the wallet-discovery scheduler service, in `docker-compose.yml:159-167`.
- The CLI registers `discovery scheduler start` as "Start the discovery background scheduler loop (blocking)" in `tools/cli/discovery.py:187-189`.
- `_scheduler_start()` starts the scheduler, prints "Discovery scheduler started", and then blocks in `while True: time.sleep(60)` until Ctrl-C in `tools/cli/discovery.py:814-833`.
- `start_discovery_scheduler()` creates a `BackgroundScheduler`, adds jobs, starts it, and returns the scheduler in `packages/research/scheduling/discovery_scheduler.py:549-595`.

Registered jobs and cadences:

- `DISCOVERY_JOB_REGISTRY` has exactly three jobs: `discovery_loop_a`, `watchlist_rescan`, and `queue_drain` in `packages/research/scheduling/discovery_scheduler.py:244-263`.
- The config cadences are `discovery_loop_a: {"hour": "*/6"}`, `watchlist_rescan: {"hour": "1,13"}`, and `queue_drain: {"minute": "*/15"}` in `config/discovery_scheduler.json:4-9`.
- The scheduler loads those cadences and passes them into `CronTrigger(**trigger_kwargs)` before `scheduler.add_job(...)` in `packages/research/scheduling/discovery_scheduler.py:546-592`.

Queue drain behavior:

- The queue drain callable loads the scan queue from ClickHouse, constructs one `ScanWorker`, calls `worker.run(max_items=...)`, then flushes the queue back to ClickHouse in `packages/research/scheduling/discovery_scheduler.py:461-485`.
- `ScanWorker.run()` is explicitly bounded by `max_items` and returns after one pass through current candidates in `packages/polymarket/discovery/scan_worker.py:163-247`.
- Config sets the scheduler drain bound to `max_items: 10`, `max_attempts: 5`, `lease_seconds: 300`, owner `discovery-scheduler` in `config/discovery_scheduler.json:27-33`.

Docker Compose service definition:

```yaml
  discovery-scheduler:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: polytool-discovery-scheduler
    env_file:
      - .env
    command: ["python", "-m", "polytool", "discovery", "scheduler", "start"]
    restart: unless-stopped
    volumes:
      - ./config:/app/config:ro
      - ./kb:/app/kb
      - ./artifacts:/app/artifacts
    depends_on:
      clickhouse:
        condition: service_healthy
    networks:
      - polytool
```

Source: `docker-compose.yml:159-176`.

24h unattended verdict: yes, the scheduler process can stay up for 24h if Docker Compose is running the `discovery-scheduler` service, ClickHouse is healthy, `.env` provides `CLICKHOUSE_PASSWORD`, the local API used by `scan.py` is reachable, and upstream Polymarket APIs are reachable. The yes is qualified: it is not a continuous worker; it is scheduled Loop A every 6h, watchlist rescan at 01:00/13:00, and a single bounded queue drain every 15 minutes. The password is required by `_scheduler_start()` in `tools/cli/discovery.py:795-807` and by `_ch_password()` in `packages/research/scheduling/discovery_scheduler.py:397-406`. The scan worker's real scan callable calls `scan.run_scan(...)` through `tools/cli/wallet_scan.py:368-394`, and `run_scan()` sends local API requests through `api_base_url` in `tools/cli/scan.py:2307-2419`.

## 2. No-Resurrect

Answer: no no-resurrection rule exists for `review_status='rejected'` rows. A rejected `lifecycle_state='scanned'` wallet is not immediately re-enqueued by the tier-aware rescan job if its `last_scanned_at` is still inside the freshness window, but it can be re-enqueued after the freshness window, and a successful drain overwrites it back to `review_status='pending'`.

Discovery -> enqueue -> watchlist insert:

- Loop A reads only the latest leaderboard snapshot, not watchlist state, before churn detection: `prior_rows = read_latest_snapshot(...)` in `packages/polymarket/discovery/loop_a.py:120-129`.
- Loop A computes `prior_wallet_set` from the prior leaderboard rows and calls `detect_churn(...)` in `packages/polymarket/discovery/loop_a.py:135-146`.
- `detect_churn()` defines new wallets as `current_set - prior_set`; it does not inspect watchlist lifecycle or review status in `packages/polymarket/discovery/churn_detector.py:39-54`.
- Loop A enqueues every `churn.new_wallets` wallet with `source="loop_a"` and `priority=3` in `packages/polymarket/discovery/loop_a.py:163-170`.
- Loop A writes every `churn.new_wallets` wallet to watchlist as `lifecycle_state=discovered`, `review_status=pending` in `packages/polymarket/discovery/loop_a.py:174-192`.

Queue manager:

- `ScanQueueManager.enqueue()` deduplicates only against its current in-memory `_items`, and only when an existing item is not terminal in `packages/polymarket/discovery/scan_queue.py:61-87`.
- The scheduler `watchlist_rescan` creates a fresh `ScanQueueManager()` and does not hydrate existing queue state before enqueueing plans in `packages/research/scheduling/discovery_scheduler.py:446-454`.

Watchlist rescan:

- `_read_watchlist_rows()` selects all `polytool.watchlist FINAL` rows where `lifecycle_state != 'retired'`; there is no `review_status != 'rejected'` filter in `packages/research/scheduling/discovery_scheduler.py:292-295`.
- `plan_rescan_enqueues()` loops over every row, resolves tier, checks only `last_scanned_at` freshness, then appends an enqueue plan; it has no rejected-status skip in `packages/research/scheduling/discovery_scheduler.py:357-377`.
- `resolve_tier()` maps `lifecycle_state in ("discovered", "queued", "scanned", "stale")` to `discovered`, regardless of `review_status='rejected'`, in `packages/research/scheduling/discovery_scheduler.py:191-202`.
- The default discovered-tier freshness window is 336 hours in `packages/research/scheduling/discovery_scheduler.py:85-90` and `config/discovery_scheduler.json:11-17`.

Worker watchlist advance:

- On successful scan and ingest, `make_clickhouse_watchlist_advancer()` writes a new `WatchlistRow` with `lifecycle_state=scanned`, `review_status=pending`, `tier=candidate`, `locked=0` in `packages/polymarket/discovery/scan_worker.py:315-333`.
- The only immutability guard is `locked`; it reads `locked,tier` from the existing watchlist row and skips only if `is_locked_row(lock_state)` is true in `packages/polymarket/discovery/scan_worker.py:302-313`.
- `is_locked_row()` checks only `locked` and `tier == "locked"`; it does not check `review_status` in `packages/polymarket/discovery/candidate_population.py:65-82`.

DDL:

- `watchlist.review_status` allows `pending`, `approved`, and `rejected`, but the DDL defines no constraint preventing a later `pending` row for the same wallet in `infra/clickhouse/initdb/27_wallet_discovery.sql:23-56`.
- `watchlist` is `ReplacingMergeTree(updated_at) ORDER BY (wallet_address)`, so a later row for the same wallet becomes the current row logically in `infra/clickhouse/initdb/27_wallet_discovery.sql:55-56`.

Plain result: rejected scanned wallets can be resurrected as pending. The next scheduled `watchlist_rescan` will skip them only while their `last_scanned_at` is recent for the resolved tier; after that window, it can re-enqueue them. Loop A can also re-surface them as discovered/pending if they are "new" relative to the previous leaderboard snapshot, because Loop A does not read watchlist state.

## 3. PnL-Sorted Export

Answer: yes. `wallet-scan` outputs a scanned-wallet leaderboard sorted by realized net PnL.

CLI and output artifacts:

- The module header says `wallet-scan` batch scans wallets/handles and writes `leaderboard.json` and `leaderboard.md` in `tools/cli/wallet_scan.py:1-10`.
- `polytool.__main__` registers `wallet-scan` to `tools.cli.wallet_scan` in `polytool/__main__.py:44` and `polytool/__main__.py:136`.
- The parser requires `--input`, supports `--profile`, `--out`, `--run-id`, `--max-entries`, and `--extract-dossier` in `tools/cli/wallet_scan.py:798-855`.
- CLI success prints `Run root`, `Manifest`, `Leaderboard JSON`, `Leaderboard Markdown`, and `Per-user results` in `tools/cli/wallet_scan.py:896-901`.

Sort key and output shape:

- `_extract_user_metrics()` reads `coverage_reconciliation_report.json` and extracts realized net PnL from `pnl.realized_pnl_net_estimated_fees_total` falling back to `pnl.realized_pnl_net_total` in `tools/cli/wallet_scan.py:421-448`.
- `_sort_key_for_leaderboard()` sorts descending by `realized_net_pnl`, nulls last, tie-breaking by slug in `tools/cli/wallet_scan.py:573-579`.
- `_build_leaderboard()` writes `ranked` entries containing `rank`, `slug`, `identifier`, `realized_net_pnl`, `gross_pnl`, `positions_total`, `clv_coverage_rate`, `unknown_resolution_pct`, and `run_root` in `tools/cli/wallet_scan.py:582-621`.
- `_build_leaderboard_md()` renders a table headed `Top 20 by Realized Net PnL` with columns `Rank`, `Slug`, `Identifier`, `Net PnL`, `Gross PnL`, `Positions`, `CLV Cov%`, and `Unk Res%` in `tools/cli/wallet_scan.py:624-661`.
- `WalletScanner.run()` writes `per_user_results.jsonl`, `leaderboard.json`, `leaderboard.md`, and `wallet_scan_manifest.json` in `tools/cli/wallet_scan.py:751-790`.

Persistence a ranked export could also read:

- Scan-level PnL is persisted in `coverage_reconciliation_report.json` under the `pnl` object, read at `tools/cli/wallet_scan.py:421-448`.
- ClickHouse also has `polytool.user_pnl_bucket.realized_pnl` in `infra/clickhouse/initdb/06_pnl_tables.sql:4-17`, and Grafana queries use `argMax(realized_pnl, computed_at)` from that table in `infra/grafana/dashboards/polyttool_user_overview.json:402`.

## 4. Retention

Answer: there is no wallet-ingestion retention cap today. Supersede changes lifecycle state in SQLite; raw prior dossier directories are compressed into `.tar.gz` archives; nothing caps table rows, KnowledgeStore rows, archives, or leaderboard snapshots.

Supersede:

- `KnowledgeStore` creates `source_documents` with `lifecycle`, `superseded_by`, and `superseded_at`, and `derived_claims` with `lifecycle` and `superseded_by`, in `packages/polymarket/rag/knowledge_store.py:148-180`.
- `supersede_dossier_run()` finds prior active `dossier_report` source docs for the same normalized wallet, excluding the current run doc ids, in `packages/polymarket/rag/knowledge_store.py:489-497`.
- It updates prior source docs to `lifecycle='superseded'` and updates active derived claims for those docs to `lifecycle='superseded'` in `packages/polymarket/rag/knowledge_store.py:500-518`.
- It returns superseded doc ids and superseded claim count, but does not delete rows, in `packages/polymarket/rag/knowledge_store.py:520-523`.
- Default source document listing excludes superseded and archived rows only by WHERE conditions, not deletion, in `packages/polymarket/rag/knowledge_store.py:425-442`.

Raw dossier archive/gzip:

- Dossier run layout is `{base}/users/{user_slug}/{wallet}/{date}/{run_id}/` in `packages/research/integration/dossier_extractor.py:16-24`.
- `extract_dossier_findings()` produces 1-3 documents per dossier run: detector classification, hypothesis candidates if present, and memo if present in `packages/research/integration/dossier_extractor.py:243-368`.
- `ingest_dossier_findings()` runs supersede after all current wallet findings are ingested in `packages/research/integration/dossier_extractor.py:612-617`.
- After successful supersede with nonempty `superseded_doc_ids`, `_retain_prior_runs()` is called in `packages/research/integration/dossier_extractor.py:645-654`.
- `_retain_prior_runs()` copies a prior memo into the new run directory as `previous-results.md` if available in `packages/research/integration/dossier_extractor.py:708-727`.
- `_retain_prior_runs()` writes `prior_run_dir.tar.gz` with `tarfile.open(..., "w:gz")` and then removes the original prior directory with `shutil.rmtree(...)` in `packages/research/integration/dossier_extractor.py:729-740`.

Per-rescan growth:

- For a successful scanned wallet, the worker writes one new current-version watchlist row as `scanned/pending/candidate` in `packages/polymarket/discovery/scan_worker.py:315-333`; the table is `ReplacingMergeTree(updated_at)` keyed by `wallet_address`, so physical versions accumulate unless ClickHouse parts are merged, in `infra/clickhouse/initdb/27_wallet_discovery.sql:55-56`.
- For watchlist rescan enqueue, the scheduler writes one scan_queue row per enqueue plan in `packages/research/scheduling/discovery_scheduler.py:446-454`; `scan_queue` is `ReplacingMergeTree(updated_at)` keyed by `dedup_key`, in `infra/clickhouse/initdb/27_wallet_discovery.sql:100-125`.
- For queue drain, the scheduler loads the whole queue and then flushes all in-memory items back to ClickHouse after one bounded worker run in `packages/research/scheduling/discovery_scheduler.py:473-485`; `flush_to_clickhouse()` writes all `self._items.values()` in `packages/polymarket/discovery/scan_queue.py:201-215`, so each drain can append versions for loaded queue rows.
- For Loop A, each discovery fetch appends one row per fetched leaderboard entry to `leaderboard_snapshots` via `write_leaderboard_snapshot_rows(...)` in `packages/polymarket/discovery/loop_a.py:157-160`; `leaderboard_snapshots` is a plain `MergeTree()` with no TTL in `infra/clickhouse/initdb/27_wallet_discovery.sql:74-90`.
- For a new Loop A wallet, Loop A writes one queue row and one discovered/pending watchlist row in `packages/polymarket/discovery/loop_a.py:163-192`.
- For each dossier ingest, `IngestPipeline.ingest()` chunks the document body and stores a source document in `packages/research/ingestion/pipeline.py:168-184`; `KnowledgeStore.add_source_document()` inserts into `source_documents` with `INSERT OR IGNORE` in `packages/polymarket/rag/knowledge_store.py:371-405`.
- With `post_extract_claims=True`, dossier ingestion calls `extract_and_link(store, result.doc_id)` in `packages/research/integration/dossier_extractor.py:606-610`; the extractor inserts claims via `store.add_claim(...)` and evidence via `store.add_evidence(...)` in `packages/research/ingestion/claim_extractor.py:510-540`.
- `KnowledgeStore.add_claim()` inserts into `derived_claims` in `packages/polymarket/rag/knowledge_store.py:529-567`; `KnowledgeStore.add_evidence()` inserts into `claim_evidence` in `packages/polymarket/rag/knowledge_store.py:625-643`.
- On disk, each new scan creates a new run directory under the dossier layout and, on a successful rescan that supersedes prior docs, can add `previous-results.md` in the new run directory and one `.tar.gz` archive beside each prior run directory, while removing the prior uncompressed directory in `packages/research/integration/dossier_extractor.py:708-740`.

Prune/vacuum:

- NOT FOUND in wallet-discovery DDL: `infra/clickhouse/initdb/27_wallet_discovery.sql` defines no `TTL`.
- NOT FOUND in PnL DDL: `infra/clickhouse/initdb/06_pnl_tables.sql` defines no `TTL`.
- NOT FOUND in relevant wallet-ingestion modules for `DELETE FROM`, `VACUUM`, `prune`, or retention cap; the only relevant deletion found is `shutil.rmtree(p, ignore_errors=True)` after the `.tar.gz` archive is created in `packages/research/integration/dossier_extractor.py:729-740`.

## 5. Discord Notify Trigger

Answer: a pending-wallet notification is automatic only for the manual `discovery run-worker` CLI path, not for the scheduled `queue_drain` job. The scheduled drain does not call the notification pass.

Automatic in manual worker:

- `run-worker` has a `--no-notify` flag that skips the post-drain Discord notification pass in `tools/cli/discovery.py:140-145`.
- After a manual worker run and queue flush, `_run_worker()` reads pending candidates and calls `notify_pending_candidates(pending_rows)` if `--no-notify` was not passed in `tools/cli/discovery.py:469-488`.
- `read_pending_candidates()` selects `tier='candidate'`, `review_status='pending'`, `locked=0`, and `lifecycle_state='scanned'` in `packages/polymarket/discovery/clickhouse_writer.py:291-355`.

Not automatic in scheduled drain:

- `_job_run_queue_drain()` loads queue, runs `worker.run(...)`, and flushes to ClickHouse; it has no `read_pending_candidates` or `notify_pending_candidates` call in `packages/research/scheduling/discovery_scheduler.py:461-485`.
- Therefore a `docker-compose` day run using only `discovery-scheduler` drains scans without automatic Discord notification from the scheduler path.

Manual listing:

- `discovery review --list-pending` reads pending candidates and calls `compute_row_evidence(row)` for display in `tools/cli/discovery.py:536-595`.

Card evidence source:

- `_row_evidence()` calls the metrics reader, builds an `Evidence` object, and if substantive evidence exists calls `summarize_evidence(ev)` in `packages/polymarket/discovery/pending_notify.py:236-255`.
- `notify_pending_candidates()` calls `_row_evidence(row, metrics_reader=...)` before building a single card or digest in `packages/polymarket/discovery/pending_notify.py:734-745`.
- `notify_pending_candidate()` receives structured `Evidence` and passes it to `build_pending_embed(full, evidence)` in `packages/polymarket/discovery/pending_notify.py:655-685`.
- `build_pending_embed()` builds the display fields from the `Evidence` object in `packages/polymarket/discovery/pending_notify.py:498-586`.

Plain result: display-time evidence uses `summarize_evidence()` through `_row_evidence()` when metrics are available; it does not display only the generic worker reason unless metrics are unavailable.

## 6. Rate Limiting

Answer: there is retry/backoff on network errors, 429s, and server errors through `HttpClient`, plus local CLI retry/backoff for local API network exceptions. NOT FOUND: an explicit steady-state request-rate throttle between leaderboard pages, data-api trade pages, activity pages, or position fetches.

Leaderboard fetch:

- `fetch_leaderboard()` creates `HttpClient(base_url=https://data-api.polymarket.com, timeout=20.0, max_retries=3, backoff_factor=1.0)` in `packages/polymarket/discovery/leaderboard_fetcher.py:46-53`.
- It loops `for page_num in range(max_pages)` and calls `http_client.get(...)` per page, with no sleep between successful pages in `packages/polymarket/discovery/leaderboard_fetcher.py:55-88`.
- `HttpClient.get()` sleeps on HTTP 429 using `Retry-After` plus jitter in `packages/polymarket/http_client.py:100-110`.
- `HttpClient.get()` sleeps on retryable server errors using exponential backoff plus jitter in `packages/polymarket/http_client.py:112-122`.
- `HttpClient.get()` sleeps on timeout and connection errors with exponential backoff plus jitter in `packages/polymarket/http_client.py:126-142`.

Polymarket data-api scan path:

- The FastAPI service constructs `data_api_client = DataApiClient(base_url=DATA_API_BASE, timeout=HTTP_TIMEOUT_SECONDS)` in `services/api/main.py:105-108`.
- `DataApiClient.__init__()` constructs `HttpClient(base_url=..., timeout=...)` with default retries/backoff in `packages/polymarket/data_api.py:330-346`.
- `/api/ingest/trades` calls `data_api_client.fetch_all_trades(...)` in `services/api/main.py:725-753`.
- `fetch_all_trades()` loops over pages and calls `fetch_trades_page(...)`, incrementing offset with no successful-page sleep in `packages/polymarket/data_api.py:540-607`.
- `/api/ingest/activity` calls `data_api_client.fetch_all_activity(...)` in `services/api/main.py:834-856`.
- `fetch_all_activity()` loops over pages and calls `fetch_activity_page(...)`, incrementing offset with no successful-page sleep in `packages/polymarket/data_api.py:429-494`.
- `/api/ingest/positions` calls `data_api_client.fetch_positions(...)` in `services/api/main.py:926-945`.
- `fetch_positions()` performs a single `self.client.get_json("/positions", params={"user": proxy_wallet})` call, with no explicit throttle in `packages/polymarket/data_api.py:496-538`.

Local scan CLI retry:

- `scan.py` wraps POST requests to the local API with `request_with_retry()`, defaulting to `retries=3` and `backoff_seconds=1.0` in `tools/cli/scan.py:302-338`.
- `request_with_retry()` catches `requests.exceptions.RequestException`, prints a retry message, and sleeps `backoff_seconds * (2**attempt)` before retrying in `tools/cli/scan.py:310-326`.
- `get_json()` has the same network-exception retry/sleep behavior for GET calls in `tools/cli/scan.py:352-386`.

NOT FOUND: no token bucket, fixed QPS limiter, per-page delay, or central rate budget on the leaderboard/data-api scan path in the inspected files.

## 7. Tree State

Command output, not file-backed evidence.

Command: `git status --short --branch`

```text
## main...origin/main [ahead 12]
 M docs/obsidian-vault/.obsidian/app.json
 M docs/obsidian-vault/.obsidian/community-plugins.json
 M docs/obsidian-vault/.obsidian/graph.json
 M docs/obsidian-vault/.obsidian/workspace.json
 M docs/obsidian-vault/claude-memory/session-notes/2026-05-31-wallet-ingestion-sprint-completion.md
 M packages/polymarket/discovery/evidence_summary.py
 M packages/polymarket/discovery/pending_notify.py
 M packages/polymarket/notifications/discord.py
 M tests/test_discord_notifications.py
 M tests/test_vera_approvals.py
 M tests/test_wallet_discovery_two_tier.py
 M tests/test_wallet_ingestion_notify.py
 M tests/test_wallet_scan.py
 M tools/cli/scan.py
 M tools/cli/wallet_scan.py
?? docs/dev_logs/2026-06-02_pending_review_embed_card_wp2.md
?? docs/dev_logs/2026-06-02_pending_review_fields_wp1.md
?? docs/dev_logs/2026-06-03_pending_review_card_final_wp3.md
?? docs/obsidian-vault/claude-memory/decisions/decision-retire-hermes-build-vera-bot.md
```

Command: `git log --oneline -10`

```text
a2ea5be docs(vault): sync Hermes retirement + Discord notification/bot system
2d16394 docs(vera): Phase B live-verified — approve+deny end-to-end through the gate
c66f375 feat(vera): make /pending cards public (operator-requested), keep author-guard
88e2205 docs(vera): Phase B approve/deny — dev log, feature doc, INDEX, CURRENT_DEVELOPMENT
02120ae fix(vera): make approve/deny reservation fail-safe (Codex re-review)
cc66272 fix(vera): close approve/deny double-write race (Codex blocking finding)
00a9bdd feat(vera): Phase B /pending + approve/deny buttons (first write surface)
97efe50 docs(vera): Phase A /ping confirmed live by operator
4e24d30 fix(vera): buildable Dockerfile.vera + enable non-privileged guilds intent
19aa1aa docs(vera): fix vera-bot compose comment (env passthrough, not env_file)
```

Branch: `main`

HEAD: `a2ea5be060256ad8bd6b37386360847b272374a0`

WP-1/WP-2/WP-3 commit status: NOT FOUND as explicit commit labels in the last 10 commits. The branch is dirty and ahead of origin by 12 commits. The dirty files include WP-related wallet-ingestion code and tests, so the audited tree is not a clean committed baseline.

Note: after this report is written, `docs/dev_logs/2026-06-04_day-run-readiness-audit.md` will also be untracked/modified until committed by the operator.

## 8. Test Baseline

Command output, not file-backed evidence.

Command run:

```text
pytest -q tests/test_wallet_discovery.py tests/test_wallet_discovery_two_tier.py tests/test_wallet_ingestion_notify.py tests/test_discovery_scheduler.py tests/test_wallet_scan.py tests/test_mvf.py tests/test_ris_dossier_extractor.py tests/test_ris_dossier_supersede.py --tb=short
```

Exact result:

```text
collected 335 items

tests\test_wallet_discovery.py ......................................... [ 12%]
.............                                                            [ 16%]
tests\test_wallet_discovery_two_tier.py ................................ [ 25%]
......                                                                   [ 27%]
tests\test_wallet_ingestion_notify.py .................................. [ 37%]
........................                                                 [ 44%]
tests\test_discovery_scheduler.py ...................................... [ 56%]
.                                                                        [ 56%]
tests\test_wallet_scan.py .............................................. [ 70%]
.........                                                                [ 72%]
tests\test_mvf.py .............................................          [ 86%]
tests\test_ris_dossier_extractor.py ...............................      [ 95%]
tests\test_ris_dossier_supersede.py ...............                      [100%]

335 passed in 3.26s
```

Pass/fail count: 335 passed, 0 failed.

Failures: none.

Known-pre-existing vs new: no failures to classify. Because no code was modified before running tests, any failure would have been baseline in the existing dirty tree; none occurred.

## Digest Per Question

1. Scheduler runtime: a Docker Compose `discovery-scheduler` service exists and can run unattended as a blocking APScheduler process, with `discovery_loop_a` every 6h, `watchlist_rescan` at 01:00/13:00, and `queue_drain` every 15 minutes. The drain is a recurring single bounded worker tick, not a continuous worker, so 24h unattended requires Compose, ClickHouse, `CLICKHOUSE_PASSWORD`, the API service, and upstream Polymarket APIs.

2. No-resurrect: NOT FOUND for a rejected-wallet exclusion. Loop A ignores watchlist state, watchlist rescan filters only `lifecycle_state != 'retired'` plus freshness, and the worker writes successful scans back as `scanned/pending/candidate`, so rejected scanned wallets can be resurrected after freshness expiry or by leaderboard churn.

3. PnL-sorted export: yes, `wallet-scan` writes `leaderboard.json` and `leaderboard.md` sorted descending by `realized_net_pnl`, with ranked fields for slug, identifier, net/gross PnL, positions, CLV coverage, unknown resolution percent, and run root.

4. Retention: no wallet-ingestion retention cap was found. KnowledgeStore supersedes prior dossier docs/claims by lifecycle update, not deletion; prior raw run dirs are tar-gzipped and removed only after archive creation; leaderboard snapshots, watchlist/queue versions, KnowledgeStore rows, claims/evidence, current run dirs, and archives can keep growing.

5. Discord notify trigger: manual `discovery run-worker` automatically runs a pending-candidate notification pass unless `--no-notify`; scheduled `queue_drain` does not call notification code. The notification/listing path recomputes display-time evidence through `_row_evidence()` and `summarize_evidence()` when scan metrics are available, falling back to stored reason only when metrics are absent.

6. Rate limiting: explicit retry/backoff exists through `HttpClient` for 429/server/timeout/connection failures and through `scan.py` for local API network exceptions. NOT FOUND for a steady-state rate throttle, token bucket, or sleep between successful leaderboard/data-api pages.

7. Tree state: branch is `main`, HEAD is `a2ea5be060256ad8bd6b37386360847b272374a0`, and `main` is ahead of `origin/main` by 12. The working tree is dirty with modified wallet-ingestion/notification files, tests, Obsidian files, and untracked dev logs/vault note; WP-1/WP-2/WP-3 were NOT FOUND as explicit labels in the last 10 commits.

8. Test baseline: focused wallet-ingestion/discovery subset passed cleanly: 335 passed, 0 failed. No failures exist to classify as known-pre-existing or new.

## Six-Line Readiness Verdict

1. BLOCKING: scheduler `queue_drain` does not notify pending wallets automatically from the scheduled path; unattended scan accumulation can create pending review items silently unless another notify surface is run.
2. BLOCKING: no no-resurrect guard for `review_status='rejected'`; rejected scanned wallets can be re-enqueued and rewritten as pending.
3. DEGRADED-BUT-OK: scheduler can run 24h, but it is bounded cron ticks and depends on Compose, ClickHouse creds, API service, and upstream API availability.
4. DEGRADED-BUT-OK: PnL-sorted export exists via `wallet-scan`, but the scheduled discovery pipeline itself does not emit a day-run ranked export artifact.
5. DEGRADED-BUT-OK: no retention cap; supersede keeps active retrieval sane, but ClickHouse versions, snapshots, KnowledgeStore rows, claims/evidence, and archives grow without a prune/vacuum policy.
6. FINE: retry/backoff exists for 429/server/network failures; however no steady-state throttle was found, so this is fine only for modest current cadences, not aggressive bulk scans.
