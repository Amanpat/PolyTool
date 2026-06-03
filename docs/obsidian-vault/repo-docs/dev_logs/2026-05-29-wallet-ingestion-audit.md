---
title: Wallet Ingestion Audit
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-29_wallet-ingestion-audit.md
last_synced: '2026-06-03T02:26:56Z'
lifecycle: reviewed
generator: repo-sync
---

# Wallet-Ingestion Built-State Forensic Audit

Date: 2026-05-29
Scope: READ ONLY forensic audit of target-user / wallet ingestion, discovery, dossier, RIS ingestion, scheduling, storage, mirror, Grafana, and Discord wiring.

Method: documentation, roadmap text, filenames, and docstrings were treated as unverified claims. Status below is based on traceable code, call-site wiring, DDL, and tests. No code, tests, dependencies, live bot, order placement, on-chain code, or trading commands were run or modified.

## Summary Table

| Component | Status | Evidence | Gap |
|---|---:|---|---|
| `python -m polytool` command dispatch | BUILT | `polytool/__main__.py :: _run_command`, lines 14-28; `polytool/__main__.py :: _COMMAND_HANDLER_NAMES`, lines 107-180; `polytool/__main__.py :: main`, lines 328-398 | Command tree is centralized and includes discovery, wallet-scan, alpha-distill, scan, research-scheduler, and research-dossier-extract. |
| Actual wallet discovery package paths | PARTIAL | `packages/polymarket/discovery/leaderboard_fetcher.py :: fetch_leaderboard`, lines 24-92; `packages/polymarket/discovery/mvf.py :: compute_mvf`, lines 377-492 | `packages/polymarket/metrics/` was not present (`Test-Path packages\polymarket\metrics` returned `False`). MVF lives under discovery. |
| Loop A leaderboard fetch and snapshots | PARTIAL | `packages/polymarket/discovery/leaderboard_fetcher.py :: fetch_leaderboard`, lines 24-92; `packages/polymarket/discovery/loop_a.py :: run_loop_a`, lines 109-162; `packages/polymarket/discovery/clickhouse_writer.py :: write_leaderboard_snapshot_rows`, lines 139-168; `tests/test_wallet_discovery_integrated.py :: test_run_loop_a_dry_run_fetches_100_entries`, lines 576-613 | Paginates top-N and writes snapshots when not dry-run. Rate handling is retries/backoff through the HTTP client path, not an explicit data-api quota throttle. |
| Loop A churn detection | BUILT | `packages/polymarket/discovery/churn_detector.py :: detect_churn`, lines 24-73; `packages/polymarket/discovery/loop_a.py :: run_loop_a`, lines 135-153; `tests/test_wallet_discovery_integrated.py :: churn integration tests`, lines 294-332 | Compares current vs prior snapshots and returns new, dropped, persisting, and rising wallets. |
| `scan_queue` storage and semantics | PARTIAL | `infra/clickhouse/initdb/27_wallet_discovery.sql :: scan_queue DDL`, lines 76-101; `packages/polymarket/discovery/scan_queue.py :: ScanQueueManager.enqueue`, lines 40-87; `ScanQueueManager.lease`, lines 89-116; `ScanQueueManager.requeue_expired_leases`, lines 176-199; `tests/test_wallet_discovery.py :: scan queue tests`, lines 427-456 | In-memory enqueue/lease/dedup exists and DDL exists. No queue consumer that executes scans was found. ClickHouse load reads rows ordered by dedup key but does not collapse ReplacingMergeTree versions. |
| Scan staleness threshold / rescan trigger | CANNOT VERIFY | Searched `packages/polymarket/discovery`, `tools/cli/discovery.py`, and discovery tests for `stale`, `staleness`, `rescan`, and `14`; no constant or trigger was found. | Claimed default around 14 days is not confirmed in code. |
| Discovery CLI runner | PARTIAL | `tools/cli/discovery.py :: main`, lines 16-83; `tools/cli/discovery.py :: _run_loop_a`, lines 90-149; `packages/polymarket/discovery/loop_a.py :: run_loop_a`, lines 48-203 | Runs fetch -> churn -> snapshot write -> enqueue new wallets -> watchlist insert. It does not consume the queue or run scans end to end. |
| Watchlist storage and human gate | BUILT | `infra/clickhouse/initdb/27_wallet_discovery.sql :: watchlist DDL`, lines 12-40; `packages/polymarket/discovery/models.py :: VALID_TRANSITIONS`, lines 56-69; `packages/polymarket/discovery/models.py :: validate_transition`, lines 100-125; `tests/test_wallet_discovery.py :: lifecycle transition tests`, lines 64-136 | Code enforces `reviewed -> promoted` only with `review_status=approved`. |
| Watchlist auto-promotion / tiers / locks | NOT BUILT | `packages/polymarket/discovery/loop_a.py :: run_loop_a`, lines 174-194; `infra/clickhouse/initdb/27_wallet_discovery.sql :: watchlist DDL`, lines 12-40 | Loop A inserts `lifecycle_state=discovered`, `review_status=pending`. No tier, locked, manual-vs-auto, or auto-promote fields were found in DDL. |
| `scan --quick` | PARTIAL | `tools/cli/scan.py :: apply_scan_defaults`, lines 1708-1728; `tools/cli/scan.py :: build_config`, lines 2009-2037; `tools/cli/scan.py :: run_scan`, lines 2281-2410 | Quick profile disables non-lite stages and computes MVF, but scan depends on API endpoints and is not an offline wallet-ingestion worker. |
| `wallet-scan --extract-dossier` | PARTIAL | `tools/cli/wallet_scan.py :: _make_dossier_extractor`, lines 74-102; `tools/cli/wallet_scan.py :: _default_scan_callable`, lines 181-224; `tools/cli/wallet_scan.py :: WalletScanner.run`, lines 451-548; `tools/cli/wallet_scan.py :: main`, lines 595-640 | `--extract-dossier` wires post-scan RIS ingestion. Raw wallet path passes `--wallet` to `scan`, but `scan` parser accepts `--user` only, so raw wallet scans are not wired correctly unless tests inject a custom scan callable. |
| MVF fingerprint | PARTIAL | `packages/polymarket/discovery/mvf.py :: compute_mvf`, lines 377-492; `tests/test_mvf.py :: dimension count tests`, lines 133-153; `tests/test_wallet_discovery_integrated.py :: quick scan MVF tests`, lines 400-514 | Code computes 11 dimensions, not 12. Several claimed inputs are unavailable or mismatched in scan output, especially maker/taker and cancel/fill data. |
| Dossier artifacts | BUILT | `packages/polymarket/llm_research_packets.py :: build_dossier_dir`, lines 70-86; `packages/polymarket/llm_research_packets.py :: export_user_dossier`, lines 820-827 and 1679-1704 | Reruns write fresh `<user>/<wallet>/<date>/<uuid>/` directories; no overwrite except UUID collision. |
| Dossier -> RIS ingestion | BUILT | `packages/research/integration/dossier_extractor.py :: extract_dossier_findings`, lines 368-399; `packages/research/integration/dossier_extractor.py :: ingest_dossier_findings`, lines 447-551; `tools/cli/research_dossier_extract.py :: main`, lines 27-151; `tests/test_wallet_scan_dossier_integration.py :: ingest tests`, lines 106-126 and 233-250 | Ingestion exists and is CLI-wired. |
| Changed-content dossier re-ingest lifecycle | NOT BUILT | `packages/research/integration/dossier_extractor.py :: ingest_dossier_findings`, lines 481-516; `packages/polymarket/rag/knowledge_store.py :: add_source_document`, lines 248-281; `packages/polymarket/rag/knowledge_store.py :: _init_schema`, lines 139-167 | Byte-identical findings are skipped by content hash. Changed content creates a new source document and new active claims. No source-document lifecycle, supersede, retire, or version replacement branch exists. |
| Derived claims extraction | BUILT | `packages/research/ingestion/claim_extractor.py :: module contract`, lines 3-23; `packages/research/ingestion/claim_extractor.py :: extract_claims_from_document`, lines 424-538 | Rule-based / heuristic extraction. No LLM call in this claim extractor. |
| Knowledge-store lifecycle/freshness | PARTIAL | `packages/polymarket/rag/knowledge_store.py :: _init_schema`, lines 139-185; `packages/polymarket/rag/knowledge_store.py :: query_claims`, lines 508-610; `packages/polymarket/rag/freshness.py :: load_freshness_config`, lines 27-55; `config/freshness_decay.json :: source_family config`, lines 1-19 | `derived_claims` has lifecycle/superseded fields; `source_documents` does not. `dossier_report` is not in freshness config, so it falls through to timeless/no-penalty behavior. |
| Alpha-distill | BUILT | `tools/cli/alpha_distill.py :: distill`, lines 452-555; `tools/cli/alpha_distill.py :: main`, lines 564-629; `tests/test_alpha_distill.py :: deterministic/offline tests`, lines 412-443 | Deterministic JSON output to `alpha_candidates.json`; no LLM. |
| Insider scoring | NOT BUILT | Searched `packages`, `tools`, and `tests` for `insider_score`, `class Insider`, and `def *insider`; no implementation was found. Data availability checks: `infra/clickhouse/initdb/02_tables.sql :: user_trades DDL`, lines 22-38; `infra/clickhouse/initdb/22_jon_becker_trades.sql :: jb_trades DDL`, lines 6-23; `packages/polymarket/silver_reconstructor.py :: _build_jon_fill_event`, lines 542-572 | No `insider_score.py`. Current ClickHouse scan/trade tables do not preserve maker/taker wallet attribution or cancel/fill fields. |
| Exemplar selector | NOT BUILT | Searched `packages`, `tools`, and `tests` for `exemplar`, `selector`, and `hypothesis selector`; only unrelated selectors/tests were found. | No implemented selector for LLM hypothesis exemplars was found. |
| LLM hypothesis generation | PARTIAL | `packages/research/synthesis/report.py :: module contract`, lines 1-7; `packages/research/synthesis/report.py :: ReportSynthesizer`, lines 190-245; `packages/research/integration/hypothesis_bridge.py :: brief_to_candidate`, lines 85-145; `packages/research/integration/hypothesis_bridge.py :: precheck_to_candidate`, lines 152-216 | Hypothesis synthesis/bridging is deterministic. LLM provider paths exist for evaluation/precheck/HyDE, not as an autonomous wallet-hypothesis generator. |
| Cloud LLM provider plumbing | PARTIAL | `packages/research/evaluation/providers.py :: get_provider`, lines 736-787; `packages/research/evaluation/providers.py :: DeepSeekV3Provider`, lines 459-490; `packages/research/evaluation/providers.py :: GeminiFlashProvider`, lines 501-582; `tools/cli/research_eval.py :: cloud guard`, lines 544-566 | Gemini/DeepSeek plumbing exists but is disabled by default unless `RIS_ENABLE_CLOUD_PROVIDERS=1` / `--enable-cloud` is used. |
| Loop B Alchemy monitoring | PARTIAL | `packages/polymarket/discovery/loop_b_probe.py :: module contract`, lines 1-24; `packages/polymarket/discovery/loop_b_probe.py :: check_historical_maker_taker`, lines 370-411; `packages/polymarket/discovery/loop_b_probe.py :: describe_dynamic_subscription_behavior`, lines 487-539; `tests/test_loop_b_probe.py :: offline probe tests`, lines 429-528 | Feasibility probes exist. No production Alchemy WebSocket Loop B client/runner was found. |
| Loop D / CLOB managed subscription | PARTIAL | `packages/polymarket/discovery/loop_d_probe.py :: module contract`, lines 1-14; `packages/polymarket/discovery/loop_d_probe.py :: audit_clob_stream_gaps`, lines 92-205; `packages/polymarket/crypto_pairs/clob_stream.py :: ClobStreamClient.subscribe`, lines 40-103; `packages/polymarket/crypto_pairs/clob_stream.py :: _ws_loop`, lines 221-267 | Existing CLOB client subscribes fixed token IDs at connect; runtime adds wait for reconnect. Probe flags missing PING keepalive, dynamic subscription, lifecycle parsing, and backfill. |
| Discovery scheduler | NOT BUILT | `tools/cli/discovery.py :: main`, lines 16-83; `tools/cli/discovery.py :: _run_loop_a`, lines 90-149. Searched `packages/research/scheduling`, `tools/cli/research_scheduler.py`, `infra/n8n`, and Grafana configs for discovery scheduler references; no Loop A cadence found. | Discovery is manual-invoke only today. |
| RIS scheduler | BUILT | `packages/research/scheduling/scheduler.py :: JOB_REGISTRY`, lines 54-103; `packages/research/scheduling/scheduler.py :: start_research_scheduler`, lines 314-410; `tools/cli/research_scheduler.py :: _cmd_start`, lines 56-96; `docker-compose.yml :: ris-scheduler services`, lines 132-176 | Scheduler code and Docker services exist. This audit did not run `docker compose ps`, so current runtime state was not verified. |
| ClickHouse wallet/RIS DDL | PARTIAL | `infra/clickhouse/initdb/27_wallet_discovery.sql :: wallet discovery DDL`, lines 12-101; `infra/clickhouse/initdb/15_llm_research_packets.sql :: user_dossier_exports DDL`, lines 3-33; `infra/clickhouse/initdb/02_tables.sql :: user/user_trades DDL`, lines 6-38; `infra/clickhouse/initdb/22_jon_becker_trades.sql :: jb_trades DDL`, lines 6-23 | Core tables exist. No `insider_scores` DDL was found. |
| DuckDB historical archive reads | BUILT | `packages/polymarket/duckdb_helper.py :: module contract`, lines 1-8; `packages/polymarket/duckdb_helper.py :: scan_parquet`, lines 174-215; `packages/polymarket/historical_import/validators.py :: validate_pmxt_layout`, lines 36-82; `packages/polymarket/historical_import/validators.py :: validate_jon_becker_layout`, lines 85-148; `packages/polymarket/silver_reconstructor.py :: _real_fetch_jon_fills`, lines 375-455 | DuckDB reads historical Parquet/CSV. Imported ClickHouse projections drop some raw maker/taker attribution. |
| Knowledge SQLite / Chroma names | PARTIAL | `packages/polymarket/rag/knowledge_store.py :: DEFAULT_KNOWLEDGE_DB_PATH`, line 57; `packages/polymarket/rag/defaults.py :: defaults`, lines 7-8; `packages/research/synthesis/academic_query.py :: collection access`, lines 308-341 | SQLite default is `kb/rag/knowledge/knowledge.sqlite3`; default Chroma collection is `polytool_rag`, not claimed `polytool_brain`; academic path also uses `academic_papers`. |
| RIS Obsidian mirror | PARTIAL | `docs/scripts/sync-ris-mirror.py :: module partition map`, lines 1-13; `docs/scripts/sync-ris-mirror.py :: ALL_PARTITIONS`, lines 62-69; `docs/scripts/sync-ris-mirror.py :: sync_external_knowledge`, lines 387-517; `docs/scripts/sync-ris-mirror.py :: sync_user_data`, lines 786-862; `docs/scripts/sync-ris-mirror.py :: main`, lines 1039-1058 | Mirrors four partitions, not only external_knowledge + signals. Dossier KS rows are not excluded, but they mirror through generic source_documents/derived_claims, not a dedicated dossier/user_data path. |
| Grafana RIS monitoring | BUILT | `infra/grafana/dashboards/ris-pipeline-health.json :: RIS dashboard queries`, lines 111-115, 218-222, 322-326, 460-485 | RIS pipeline health dashboard exists and reads `polytool.n8n_execution_metrics`. |
| Grafana wallet discovery dashboard | NOT BUILT | Searched `infra/grafana` for `wallet-discovery`, `watchlist`, `leaderboard_snapshots`, and `scan_queue`; no dashboard references were found. | No wallet-discovery dashboard found. |
| Discord notifications | PARTIAL | `packages/polymarket/notifications/discord.py :: module contract`, lines 1-21; `packages/polymarket/notifications/discord.py :: post_message`, lines 55-77; `packages/research/monitoring/alert_sink.py :: WebhookSink`, lines 79-116; `tests/test_discord_notifications.py :: webhook tests`, lines 88-115 | Outbound webhook notifications exist. No two-way bot, button, gateway, or interaction handling was found. |

## A. Discovery (Loop A)

### CLI and command tree

`python -m polytool` dispatch is real. The module-level dispatcher imports handler modules dynamically and invokes `main()` (`polytool/__main__.py :: _run_command`, lines 14-28). Commands include `wallet-scan`, `alpha-distill`, `scan`, `research-dossier-extract`, `research-scheduler`, and `discovery` (`polytool/__main__.py :: _COMMAND_HANDLER_NAMES`, lines 107-180), and `main()` performs command dispatch (`polytool/__main__.py :: main`, lines 328-398).

### Actual package paths

The relevant code is under `packages/polymarket/discovery/`, `packages/polymarket/rag/`, `packages/polymarket/notifications/`, and `packages/research/`. A claimed `packages/polymarket/metrics/` package was not present; MVF code is in `packages/polymarket/discovery/mvf.py :: compute_mvf`, lines 377-492.

### Leaderboard fetch

Status: PARTIAL.

`fetch_leaderboard()` calls `https://data-api.polymarket.com/v1/leaderboard`, paginates with `limit` and `offset`, stops on empty pages or non-200 status, and sorts entries by rank (`packages/polymarket/discovery/leaderboard_fetcher.py :: fetch_leaderboard`, lines 24-92). `to_snapshot_rows()` transforms fetched entries into snapshot rows and computes `is_new` from prior wallets (`packages/polymarket/discovery/leaderboard_fetcher.py :: to_snapshot_rows`, lines 96-146).

Loop A wires this into a real call path: it fetches the leaderboard, optionally reads the latest snapshot, computes churn, writes snapshots, enqueues new wallets, and inserts discovered watchlist rows (`packages/polymarket/discovery/loop_a.py :: run_loop_a`, lines 48-203). The CLI calls that orchestrator (`tools/cli/discovery.py :: _run_loop_a`, lines 90-149). Dry-run integration tests exercise the path with a mocked fetcher (`tests/test_wallet_discovery_integrated.py :: test_run_loop_a_dry_run_fetches_100_entries`, lines 576-613).

Gap: no explicit rate-limit throttle was found. The fetcher uses a retrying HTTP client, but code evidence does not show a leaderboard-specific quota/rate limiter.

### Churn detection

Status: BUILT.

`detect_churn()` compares current and prior rank maps and returns `new_wallets`, `dropped_wallets`, `persisting_wallets`, and `rising_wallets` (`packages/polymarket/discovery/churn_detector.py :: detect_churn`, lines 24-73). Loop A calls it after fetching current and prior snapshots (`packages/polymarket/discovery/loop_a.py :: run_loop_a`, lines 135-153). Integrated tests cover churn behavior (`tests/test_wallet_discovery_integrated.py :: churn integration tests`, lines 294-332).

Gap: churn is used to enqueue new wallets. I did not find a code path where rank movement alone triggers an automatic rescan of an existing wallet.

### `scan_queue`

Status: PARTIAL.

ClickHouse DDL exists for `polytool.scan_queue` with dedup key, priority, state, lease owner, lease expiry, attempts, and timestamps (`infra/clickhouse/initdb/27_wallet_discovery.sql :: scan_queue DDL`, lines 76-101). The in-memory `ScanQueueManager` implements deduped `enqueue()`, leasing, complete/fail, pending selection, and expired lease requeue (`packages/polymarket/discovery/scan_queue.py :: ScanQueueManager.enqueue`, lines 40-87; `ScanQueueManager.lease`, lines 89-116; `ScanQueueManager.complete`, lines 118-133; `ScanQueueManager.fail`, lines 135-153; `ScanQueueManager.get_pending`, lines 155-174; `ScanQueueManager.requeue_expired_leases`, lines 176-199). Tests cover dedup, lease, and expiry semantics (`tests/test_wallet_discovery.py :: scan queue tests`, lines 427-456).

Gap: I found queue creation and Loop A enqueue, but no consumer that leases queued rows and runs `wallet-scan` or `scan`. The loader reads `polytool.scan_queue` ordered by dedup key (`packages/polymarket/discovery/scan_queue.py :: load_from_clickhouse`, lines 218-294), but no code path was found that collapses ReplacingMergeTree versions into latest state.

### Staleness threshold

Status: CANNOT VERIFY.

The claimed default around 14 days could not be verified. I searched `packages/polymarket/discovery`, `tools/cli/discovery.py`, and discovery tests for `stale`, `staleness`, `rescan`, `14 days`, `timedelta(days=14)`, and equivalent patterns. No constant or rescan trigger was found.

### Discovery CLI runner

Status: PARTIAL.

`tools/cli/discovery.py` defines only `run-loop-a` (`tools/cli/discovery.py :: main`, lines 16-83). It fail-fast checks ClickHouse credentials unless dry-run, calls `run_loop_a()`, and prints counts (`tools/cli/discovery.py :: _run_loop_a`, lines 90-149).

Gap: this is not end-to-end discovery-to-dossier ingestion. It stops after leaderboard/churn/snapshot/enqueue/watchlist insert; it does not consume the queue or run scans.

### Watchlist

Status: BUILT for storage and human gate; NOT BUILT for auto-promotion/tier/lock semantics.

Watchlist DDL stores wallet address, lifecycle state, review status, priority, source, reason, last scan run ID, scan/activity timestamps, metadata JSON, and update time (`infra/clickhouse/initdb/27_wallet_discovery.sql :: watchlist DDL`, lines 12-40). State definitions and allowed transitions exist (`packages/polymarket/discovery/models.py :: LifecycleState/ReviewStatus/QueueState`, lines 21-45; `packages/polymarket/discovery/models.py :: VALID_TRANSITIONS`, lines 56-69). The validator rejects direct promotion shortcuts and requires `review_status=approved` for `reviewed -> promoted` (`packages/polymarket/discovery/models.py :: validate_transition`, lines 100-125). Tests cover allowed and rejected transitions (`tests/test_wallet_discovery.py :: lifecycle transition tests`, lines 64-136).

Loop A writes new wallets as `lifecycle_state=discovered` and `review_status=pending` (`packages/polymarket/discovery/loop_a.py :: run_loop_a`, lines 174-194). No auto-promote code path was found. The DDL has no tier, locked, or manual-vs-auto columns (`infra/clickhouse/initdb/27_wallet_discovery.sql :: watchlist DDL`, lines 12-40).

## B. Scan -> Dossier

### `scan` and `wallet-scan`

`scan` is API-backed. It calls endpoints to ingest markets/activity/positions/snapshot, resolve and ingest trades, optionally run detectors/PnL/opportunity/resolution enrichment, export a dossier, and emit trust artifacts (`tools/cli/scan.py :: run_scan`, lines 2281-2410). `--quick` applies `LITE_PIPELINE_STAGE_SET` and disables stages not enabled for lite mode (`tools/cli/scan.py :: apply_scan_defaults`, lines 1708-1728; `tools/cli/scan.py :: build_config`, lines 2009-2037).

`wallet-scan` batches entries, creates a run root under `<out>/<YYYY-MM-DD>/<run_id>`, runs the scan callable for each entry, optionally extracts dossier findings, and writes `per_user_results.jsonl`, `leaderboard.json`, `leaderboard.md`, and `wallet_scan_manifest.json` (`tools/cli/wallet_scan.py :: WalletScanner.run`, lines 451-548). `--extract-dossier` creates a post-scan extractor that opens the KnowledgeStore and calls `ingest_dossier_findings(..., post_extract_claims=True)` (`tools/cli/wallet_scan.py :: _make_dossier_extractor`, lines 74-102; `tools/cli/wallet_scan.py :: main`, lines 595-640).

Gap: raw wallet wiring is inconsistent. `_default_scan_callable()` passes `--wallet` for raw wallet IDs (`tools/cli/wallet_scan.py :: _default_scan_callable`, lines 181-190), but `scan` defines `--user` and not `--wallet` (`tools/cli/scan.py :: main parser`, lines 1731-1772). That means raw wallet entries are not reliably wired through the default scan path.

### MVF dimensions

Status: PARTIAL.

`compute_mvf()` emits 11 dimensions (`packages/polymarket/discovery/mvf.py :: compute_mvf`, lines 377-492). Tests assert 11 dimensions, including maker/taker null when data is missing (`tests/test_mvf.py :: dimension count and missing-data tests`, lines 133-183; `tests/test_wallet_discovery_integrated.py :: quick scan MVF tests`, lines 400-514).

Computed dimensions and required inputs:

| Dimension | Code evidence | Required input | Availability from scan dossier |
|---|---|---|---|
| `win_rate` | `packages/polymarket/discovery/mvf.py :: _compute_win_rate`, lines 104-118 | `resolution_outcome` | Dossier positions include resolution outcome fields (`packages/polymarket/llm_research_packets.py :: export position rows`, lines 1600-1639). |
| `avg_hold_duration_hours` | `packages/polymarket/discovery/mvf.py :: _compute_avg_hold_duration_hours`, lines 121-149 | `first_trade_timestamp`/`last_trade_timestamp` or open/close aliases | Scan output uses `entry_ts`/`exit_ts`; this helper does not consume those names (`packages/polymarket/llm_research_packets.py :: position query and rows`, lines 1374-1437 and 1600-1639). |
| `median_entry_price` | `packages/polymarket/discovery/mvf.py :: _compute_median_entry_price`, lines 152-161 | `entry_price` | Present in position rows (`packages/polymarket/llm_research_packets.py :: export position rows`, lines 1600-1639). |
| `market_concentration` | `packages/polymarket/discovery/mvf.py :: _compute_market_concentration`, lines 164-178 | `market_slug` | Present in position rows (`packages/polymarket/llm_research_packets.py :: export position rows`, lines 1600-1639). |
| `category_entropy` | `packages/polymarket/discovery/mvf.py :: _compute_category_entropy`, lines 181-199 | `category` | Present in position rows (`packages/polymarket/llm_research_packets.py :: export position rows`, lines 1600-1639). |
| `avg_position_size_usdc` | `packages/polymarket/discovery/mvf.py :: _compute_avg_position_size_usdc`, lines 202-228 | `position_notional_usd`, `total_cost`, or `size * entry_price` | Partly present through position cost/size fields (`packages/polymarket/llm_research_packets.py :: export position rows`, lines 1600-1639). |
| `trade_frequency_per_day` | `packages/polymarket/discovery/mvf.py :: _compute_trade_frequency_per_day`, lines 231-260 | first/last timestamp aliases | Same naming mismatch as hold duration; fallback may reduce this to count-per-one-day. |
| `late_entry_rate` | `packages/polymarket/discovery/mvf.py :: _compute_late_entry_rate`, lines 263-320 | entry timestamp plus market open/create and close/end timestamp | Scan output has entry/exit and market end/close fields, but not `market_open_ts`/`market_created_at` under the helper's expected names (`packages/polymarket/llm_research_packets.py :: position query and rows`, lines 1374-1437 and 1600-1639). |
| `dca_score` | `packages/polymarket/discovery/mvf.py :: _compute_dca_score`, lines 323-333 | repeated `market_slug` positions | Present. |
| `resolution_coverage_rate` | `packages/polymarket/discovery/mvf.py :: _compute_resolution_coverage_rate`, lines 336-346 | `resolution_outcome` | Present for resolved-enriched positions. |
| `maker_taker_ratio` | `packages/polymarket/discovery/mvf.py :: _compute_maker_taker_ratio`, lines 349-373 | `maker` or `side_type` | Not available in current scan dossier position rows (`packages/polymarket/llm_research_packets.py :: export position rows`, lines 1600-1639). |

Gap: the claimed 12th dimension is not present in `compute_mvf()`. Cancel/fill style inputs are not present in scan output.

### Dossier artifacts

Status: BUILT.

`build_dossier_dir()` produces `artifacts/dossiers/users/<username_slug>/<proxy_wallet>/<YYYY-MM-DD>/<run_id>` (`packages/polymarket/llm_research_packets.py :: build_dossier_dir`, lines 70-86). `export_user_dossier()` generates a UUID export/run ID, writes `dossier.json`, `memo.md`, and `manifest.json`, inserts a ClickHouse `user_dossier_exports` row, and returns artifact paths (`packages/polymarket/llm_research_packets.py :: export_user_dossier`, lines 820-827 and 1679-1795). Reruns therefore write fresh dated UUID directories.

## C. Dossier -> RIS Ingestion

### Ingestion function

Status: BUILT.

The ingestion function is `ingest_dossier_findings()` (`packages/research/integration/dossier_extractor.py :: ingest_dossier_findings`, lines 447-551). `extract_dossier_findings()` reads `dossier.json`, optional `memo.md`, and optional `hypothesis_candidates.json`, then returns structured finding documents (`packages/research/integration/dossier_extractor.py :: extract_dossier_findings`, lines 368-399). The CLI imports those functions and calls ingestion unless `--dry-run` is used (`tools/cli/research_dossier_extract.py :: main`, lines 27-151).

### Dedup

Status: BUILT but narrow.

`DossierAdapter` uses `sha256(body)` as `content_hash` if one is not already provided (`packages/research/ingestion/adapters.py :: DossierAdapter.adapt`, lines 599-640). `ingest_dossier_findings()` checks `source_documents.content_hash` before ingestion (`packages/research/integration/dossier_extractor.py :: ingest_dossier_findings`, lines 481-488). If a row exists, it appends a synthetic success result with `chunk_count=0` and skips the pipeline (`packages/research/integration/dossier_extractor.py :: ingest_dossier_findings`, lines 489-498).

### Key question: changed-content re-ingest

Status: NOT BUILT for supersede/lifecycle. Actual behavior is accumulation.

Precise trace:

1. Byte-identical content: `content_hash` matches an existing `source_documents` row, so ingestion skips the finding (`packages/research/integration/dossier_extractor.py :: ingest_dossier_findings`, lines 481-498).
2. Changed content for the same wallet/dossier source: body hash changes, so the duplicate branch does not fire (`packages/research/integration/dossier_extractor.py :: ingest_dossier_findings`, lines 481-498).
3. The changed document is passed into `pipeline.ingest()` with `source_type="dossier"` and `source_family="dossier_report"` (`packages/research/integration/dossier_extractor.py :: ingest_dossier_findings`, lines 506-516).
4. `KnowledgeStore.add_source_document()` derives `doc_id` from `source_url` plus `content_hash` and uses `INSERT OR IGNORE` (`packages/polymarket/rag/knowledge_store.py :: add_source_document`, lines 248-281). Same source URL plus different content hash becomes a different document ID.
5. `source_documents` schema has no lifecycle, archived, superseded, or superseded_by fields (`packages/polymarket/rag/knowledge_store.py :: _init_schema`, lines 139-149).
6. If claim extraction is enabled, new claims are extracted from the new source document and inserted with `lifecycle="active"` (`packages/research/ingestion/claim_extractor.py :: extract_claims_from_document`, lines 424-538; `packages/polymarket/rag/knowledge_store.py :: _init_schema`, lines 151-167).

Conclusion: same-content re-ingest is skip-by-content-hash. Changed-content re-ingest creates a new `source_document` and new active claims. There is no supersede/retire branch for prior source documents or prior claims.

### Derived claims

Status: BUILT, heuristic/rule-based.

The claim extractor explicitly states it is deterministic, local, and has no network/LLM calls (`packages/research/ingestion/claim_extractor.py :: module contract`, lines 3-23). Extraction uses rule-based sentence/chunk processing and stores claims/evidence (`packages/research/ingestion/claim_extractor.py :: extract_claims_from_document`, lines 424-538).

### Knowledge store schema and freshness

Status: PARTIAL.

Tables include `source_documents`, `derived_claims`, `claim_evidence`, and `claim_relations` (`packages/polymarket/rag/knowledge_store.py :: _init_schema`, lines 139-185). `derived_claims` has `validation_status`, `lifecycle`, and `superseded_by`; `source_documents` does not (`packages/polymarket/rag/knowledge_store.py :: _init_schema`, lines 139-167). Querying excludes archived/superseded claims by default and applies freshness modifiers (`packages/polymarket/rag/knowledge_store.py :: query_claims`, lines 508-610).

Freshness config is loaded from `config/freshness_decay.json` (`packages/polymarket/rag/freshness.py :: load_freshness_config`, lines 27-55; `config/freshness_decay.json :: source_family config`, lines 1-19). `dossier_report` is not in that config, so it falls through to default/timeless behavior (`packages/polymarket/rag/freshness.py :: compute_freshness_modifier`, lines 58-126).

## D. Edge Analysis

### Alpha-distill

Status: BUILT.

`alpha-distill` is deterministic and offline. It loads wallet-scan outputs, aggregates segment analysis across successful users, filters by `min_sample`, scores candidates, sorts deterministically, and returns a JSON payload (`tools/cli/alpha_distill.py :: distill`, lines 452-555). CLI output defaults to `<wallet-scan-run>/alpha_candidates.json` (`tools/cli/alpha_distill.py :: main`, lines 564-629). Tests cover deterministic/offline behavior (`tests/test_alpha_distill.py :: deterministic/offline tests`, lines 412-443).

### Insider scoring

Status: NOT BUILT.

No `insider_score.py` or insider scoring implementation was found after searching `packages`, `tools`, and `tests` for `insider_score`, `class Insider`, and `def *insider`.

Data availability:

- Current scan/dossier position output does not include maker/taker wallet attribution or cancel/fill fields (`packages/polymarket/llm_research_packets.py :: position query`, lines 1374-1437; `packages/polymarket/llm_research_packets.py :: export position rows`, lines 1600-1639).
- ClickHouse `user_trades` has `proxy_wallet`, trade UID, timestamp, token/condition IDs, outcome, side, size, price, tx hash, raw JSON, and ingest time; no maker/taker/cancel/fill columns (`infra/clickhouse/initdb/02_tables.sql :: user_trades DDL`, lines 22-38).
- ClickHouse `jb_trades` has timestamp, platform, market/token IDs, price, size, `taker_side`, resolution/category, source file, import run, and import time; no maker/taker wallet columns (`infra/clickhouse/initdb/22_jon_becker_trades.sql :: jb_trades DDL`, lines 6-23).
- Raw Jon-Becker compatibility code recognizes real maker/taker parquet fields (`packages/polymarket/silver_reconstructor.py :: _real_fetch_jon_fills`, lines 375-455; `tests/test_silver_input_compatibility.py :: maker/taker schema fixture`, lines 151-208), but the Silver event builder collapses those rows to price/size/side and does not preserve maker/taker wallet attribution (`packages/polymarket/silver_reconstructor.py :: _build_jon_fill_event`, lines 542-572).

Read-only DuckDB schema inspection confirmed local raw Jon trade columns:

```text
['block_number','transaction_hash','log_index','order_hash','maker','taker','maker_asset_id','taker_asset_id','maker_amount','taker_amount','fee','timestamp','_fetched_at','_contract']
```

Conclusion: insider math requiring maker/taker wallet attribution is feasible only from raw Jon/on-chain-style archives today, not from current scan output or ClickHouse imported trade tables.

### Exemplar selector

Status: NOT BUILT.

Searches for `exemplar`, `selector`, and hypothesis selector terms under `packages`, `tools`, and `tests` found no implemented exemplar selector for LLM hypotheses.

## E. Loop C (LLM Hypotheses)

### Hypothesis generation

Status: PARTIAL.

`ReportSynthesizer` is deterministic and explicitly does not use an LLM (`packages/research/synthesis/report.py :: module contract`, lines 1-7; `packages/research/synthesis/report.py :: ReportSynthesizer`, lines 190-245). The hypothesis bridge converts existing report briefs or precheck results into candidate JSON deterministically (`packages/research/integration/hypothesis_bridge.py :: brief_to_candidate`, lines 85-145; `packages/research/integration/hypothesis_bridge.py :: precheck_to_candidate`, lines 152-216).

LLM call paths exist elsewhere, but not as an autonomous wallet-hypothesis generator. HyDE and precheck can use provider scoring when a provider is selected (`packages/research/synthesis/hyde.py :: run_hyde_query`, lines 109-173; `packages/research/synthesis/precheck.py :: run_precheck`, lines 325-370).

### Cloud provider plumbing

Status: PARTIAL.

Gemini and DeepSeek providers exist (`packages/research/evaluation/providers.py :: DeepSeekV3Provider`, lines 459-490; `packages/research/evaluation/providers.py :: GeminiFlashProvider`, lines 501-582). `get_provider()` defaults to manual/local behavior and rejects cloud providers unless `RIS_ENABLE_CLOUD_PROVIDERS=1` is set (`packages/research/evaluation/providers.py :: get_provider`, lines 736-787). The research eval CLI exposes `--enable-cloud` and enforces the same guard (`tools/cli/research_eval.py :: cloud guard`, lines 544-566).

Conclusion: cloud LLM plumbing is present, gated, and disabled by default. Loop C wallet hypothesis generation remains deterministic/manual rather than an LLM generation loop.

## F. Loops B / D

### Loop B: Alchemy WebSocket

Status: PARTIAL.

`loop_b_probe.py` is a feasibility probe and explicitly defers production network-bound Loop B functionality (`packages/polymarket/discovery/loop_b_probe.py :: module contract`, lines 1-24). It can check historical maker/taker availability and documents that `user_trades`/`jb_trades` do not provide maker/taker wallet attribution (`packages/polymarket/discovery/loop_b_probe.py :: check_historical_maker_taker`, lines 370-411). It also estimates Alchemy CU and describes dynamic subscription behavior (`packages/polymarket/discovery/loop_b_probe.py :: estimate_alchemy_cu`, lines 421-479; `packages/polymarket/discovery/loop_b_probe.py :: describe_dynamic_subscription_behavior`, lines 487-539). Offline probe tests exist (`tests/test_loop_b_probe.py :: offline probe tests`, lines 429-528).

Gap: no production Alchemy WebSocket client/runner was found.

### Loop D: CLOB stream

Status: PARTIAL.

`loop_d_probe.py` explicitly says it does not implement Loop D (`packages/polymarket/discovery/loop_d_probe.py :: module contract`, lines 1-14). It returns a blocker catalog covering missing PING keepalive, missing dynamic runtime subscribe/unsubscribe, missing new-market/resolved lifecycle parsing, fixed token set, and no reconnect backfill (`packages/polymarket/discovery/loop_d_probe.py :: audit_clob_stream_gaps`, lines 92-205). It also states CLOB trade events are insufficient for wallet attribution without Alchemy/on-chain logs (`packages/polymarket/discovery/loop_d_probe.py :: assess_trade_event_sufficiency`, lines 239-287).

An actual `ClobStreamClient` exists in the crypto-pair area. It sends subscription messages on connect, accepts `book` and `price_change`, and adding subscriptions while running waits for reconnect (`packages/polymarket/crypto_pairs/clob_stream.py :: ClobStreamClient.subscribe`, lines 40-103; `packages/polymarket/crypto_pairs/clob_stream.py :: _ws_loop`, lines 221-267; `packages/polymarket/crypto_pairs/clob_stream.py :: _apply_message`, lines 276-294).

Conclusion: there is CLOB streaming infrastructure, but not a completed Loop D managed subscription system.

## G. Scheduling

### Discovery scheduler

Status: NOT BUILT.

I found manual CLI wiring only (`tools/cli/discovery.py :: main`, lines 16-83; `tools/cli/discovery.py :: _run_loop_a`, lines 90-149). Searches under `packages/research/scheduling`, `tools/cli/research_scheduler.py`, `infra/n8n`, and Grafana configs found no scheduled Loop A or scheduled wallet rescan path.

Conclusion: discovery runs are manual-invoke only today.

### RIS scheduler

Status: BUILT, current runtime not verified.

The RIS scheduler registry defines cron-style jobs: `academic_ingest`, `reddit_polymarket`, `reddit_others`, `blog_ingest`, `youtube_ingest`, `github_ingest`, `freshness_refresh`, and `weekly_digest` (`packages/research/scheduling/scheduler.py :: JOB_REGISTRY`, lines 54-103). `start_research_scheduler()` creates an APScheduler `BackgroundScheduler`, registers jobs, and starts it (`packages/research/scheduling/scheduler.py :: start_research_scheduler`, lines 314-410). The CLI `start` command blocks in a sleep loop after starting the scheduler (`tools/cli/research_scheduler.py :: _cmd_start`, lines 56-96).

Docker Compose defines `ris-scheduler` with `python -m polytool research-scheduler start --exclude-jobs academic_ingest` and `restart: unless-stopped`, plus a GPU scheduler variant (`docker-compose.yml :: ris-scheduler services`, lines 132-176). n8n workflows also call `research-scheduler run-job ...` inside `polytool-ris-scheduler` (`infra/n8n/workflows/ris-unified-dev.json :: run-job commands`, lines 204, 359, 514, 669, 824, 979).

This audit did not run `docker compose ps`; current runtime state is CANNOT VERIFY.

## H. Storage Wiring

### ClickHouse

Status: PARTIAL.

Wallet discovery DDL exists:

- `polytool.watchlist` (`infra/clickhouse/initdb/27_wallet_discovery.sql :: watchlist DDL`, lines 12-40)
- `polytool.leaderboard_snapshots` (`infra/clickhouse/initdb/27_wallet_discovery.sql :: leaderboard_snapshots DDL`, lines 50-66)
- `polytool.scan_queue` (`infra/clickhouse/initdb/27_wallet_discovery.sql :: scan_queue DDL`, lines 76-101)

Scan/RIS adjacent DDL exists:

- `polytool.user_dossier_exports` (`infra/clickhouse/initdb/15_llm_research_packets.sql :: user_dossier_exports DDL`, lines 3-33)
- `polytool.users` and `polytool.user_trades` (`infra/clickhouse/initdb/02_tables.sql :: users/user_trades DDL`, lines 6-38)
- `polytool.pmxt_l2_snapshots` (`infra/clickhouse/initdb/21_pmxt_archive.sql :: pmxt_l2_snapshots DDL`, lines 6-23)
- `polytool.jb_trades` (`infra/clickhouse/initdb/22_jon_becker_trades.sql :: jb_trades DDL`, lines 6-23)

No `insider_scores` table DDL was found.

### DuckDB / historical archives

Status: BUILT.

DuckDB is used for historical Parquet/CSV reads (`packages/polymarket/duckdb_helper.py :: module contract`, lines 1-8). Helpers inspect and scan parquet/csv files (`packages/polymarket/duckdb_helper.py :: _parquet_columns/_csv_columns`, lines 116-139; `packages/polymarket/duckdb_helper.py :: scan_parquet`, lines 174-215). Historical validators check pmxt and Jon-Becker layouts (`packages/polymarket/historical_import/validators.py :: validate_pmxt_layout`, lines 36-82; `packages/polymarket/historical_import/validators.py :: validate_jon_becker_layout`, lines 85-148). Silver reconstruction reads raw Jon fills with maker/taker-compatible fields but does not preserve wallet attribution in emitted fill events (`packages/polymarket/silver_reconstructor.py :: _real_fetch_jon_fills`, lines 375-455; `packages/polymarket/silver_reconstructor.py :: _build_jon_fill_event`, lines 542-572).

Read-only local schema inspection found:

```text
Jon trades columns:
['block_number','transaction_hash','log_index','order_hash','maker','taker','maker_asset_id','taker_asset_id','maker_amount','taker_amount','fee','timestamp','_fetched_at','_contract']

PMXT orderbook columns:
['timestamp_received','timestamp_created_at','market_id','update_type','data']

Jon markets columns:
['id','condition_id','question','slug','outcomes','outcome_prices','clob_token_ids','volume','liquidity','active','closed','end_date','created_at','market_maker_address','_fetched_at']
```

### Knowledge store SQLite and Chroma

Status: PARTIAL.

Default KnowledgeStore SQLite path is `kb/rag/knowledge/knowledge.sqlite3` (`packages/polymarket/rag/knowledge_store.py :: DEFAULT_KNOWLEDGE_DB_PATH`, line 57). RAG defaults use Chroma persist path `kb/rag/index` and collection `polytool_rag` (`packages/polymarket/rag/defaults.py :: defaults`, lines 7-8). Academic query code separately checks for an `academic_papers` collection (`packages/research/synthesis/academic_query.py :: collection access`, lines 308-341).

The claimed `polytool_brain` collection name is not the default used by code.

## I. RIS Obsidian Mirror

Status: PARTIAL.

`docs/scripts/sync-ris-mirror.py` documents four partition families: `external_knowledge`, `research`, `signals`, and `user_data` (`docs/scripts/sync-ris-mirror.py :: module partition map`, lines 1-13; `docs/scripts/sync-ris-mirror.py :: ALL_PARTITIONS`, lines 62-69). `main()` dispatches all partitions unless filtered (`docs/scripts/sync-ris-mirror.py :: main`, lines 1039-1058).

Mirror scope:

- `sync_external_knowledge()` mirrors all KnowledgeStore `source_documents` without a `source_family` exclusion, then mirrors Chroma `academic_papers` (`docs/scripts/sync-ris-mirror.py :: sync_external_knowledge`, lines 387-517).
- `sync_research()` mirrors `derived_claims` grouped by source document (`docs/scripts/sync-ris-mirror.py :: sync_research`, lines 538-599).
- `sync_user_data()` opens Chroma `polytool_rag` and writes only a summary document, not per-chunk user-data docs (`docs/scripts/sync-ris-mirror.py :: sync_user_data`, lines 786-862).

Conclusion: the mirror is not limited to external_knowledge + signals. Dossier findings ingested into KnowledgeStore are not excluded; they would be mirrored through generic `source_documents` / `derived_claims`, not through a dedicated dossier partition.

## J. Grafana

### Existing dashboards

Status: BUILT for RIS monitoring and existing trading/user dashboards.

Grafana dashboards found under `infra/grafana/dashboards/`:

- `ris-pipeline-health.json`
- `polyttool_user_trades.json`
- `polyttool_user_overview.json`
- `polyttool_strategy_detectors.json`
- `polyttool_pnl.json`
- `polyttool_liquidity_snapshots.json`
- `polyttool_infra_smoke.json`
- `polyttool_crypto_pair_paper_soak.json`
- `polyttool_arb_feasibility.json`

The RIS health dashboard reads `polytool.n8n_execution_metrics FINAL` for success rate, duration, failures, and latest run status (`infra/grafana/dashboards/ris-pipeline-health.json :: RIS dashboard queries`, lines 111-115, 218-222, 322-326, 460-485).

Existing user/trading dashboards read tables such as `polytool.user_trades`, `polytool.user_activity`, `polytool.user_activity_resolved`, `polytool.user_positions_resolved`, `polytool.user_trades_resolved`, `polytool.token_orderbook_snapshots`, `polytool.arb_feasibility_bucket`, `polytool.orderbook_snapshots_enriched`, `polytool.user_opportunities_bucket`, `polytool.detector_results`, and `polytool.user_bucket_features` (`infra/grafana/dashboards/polyttool_user_trades.json :: queries`, lines 109, 222, 285, 348, 411, 474, 564, 669, 774, 839, 921; `infra/grafana/dashboards/polyttool_user_overview.json :: dashboard`, lines 2920-2921; `infra/grafana/dashboards/polyttool_strategy_detectors.json :: dashboard`, lines 952-953).

### Wallet discovery dashboard

Status: NOT BUILT.

Searches in `infra/grafana` for `wallet-discovery`, `watchlist`, `leaderboard_snapshots`, and `scan_queue` found no dashboard references.

## K. Discord

Status: PARTIAL.

Outbound webhook notifications exist. `packages/polymarket/notifications/discord.py` is a webhook-only transport using `DISCORD_WEBHOOK_URL`, with no global state/background threads/retries (`packages/polymarket/notifications/discord.py :: module contract`, lines 1-21). `post_message()` sends JSON `{"content": text}` to the webhook and returns a boolean while swallowing exceptions (`packages/polymarket/notifications/discord.py :: post_message`, lines 55-77). Typed helpers cover gate/session/error/kill-switch/risk alerts (`packages/polymarket/notifications/discord.py :: notify helpers`, lines 85-257). RIS monitoring also has a generic outbound `WebhookSink` (`packages/research/monitoring/alert_sink.py :: WebhookSink`, lines 79-116).

No two-way Discord bot, gateway connection, button component, slash-command receiver, or interaction handler was found. Tests cover outbound webhook behavior only (`tests/test_discord_notifications.py :: webhook tests`, lines 88-115).

## Doc-vs-Reality Discrepancies

1. Claimed `packages/polymarket/metrics/` package: not present. MVF code is under `packages/polymarket/discovery/mvf.py :: compute_mvf`, lines 377-492.
2. Claimed Loop A end-to-end discovery: actual CLI runs fetch/churn/snapshot/enqueue/watchlist only (`tools/cli/discovery.py :: _run_loop_a`, lines 90-149; `packages/polymarket/discovery/loop_a.py :: run_loop_a`, lines 48-203). No scan queue consumer was found.
3. Claimed staleness threshold around 14 days: CANNOT VERIFY. No constant or rescan trigger found in discovery code/tests.
4. Claimed watchlist auto-promotion: not supported. Loop A inserts `discovered/pending` (`packages/polymarket/discovery/loop_a.py :: run_loop_a`, lines 174-194), while promotion requires approved human review (`packages/polymarket/discovery/models.py :: validate_transition`, lines 117-125).
5. Claimed watchlist tier/locked/manual-vs-auto distinction: not supported by watchlist DDL (`infra/clickhouse/initdb/27_wallet_discovery.sql :: watchlist DDL`, lines 12-40).
6. Claimed 12 MVF dimensions: code computes and tests 11 dimensions (`packages/polymarket/discovery/mvf.py :: compute_mvf`, lines 377-492; `tests/test_mvf.py :: dimension count tests`, lines 133-153).
7. Claimed wallet scan handles raw wallets cleanly: default raw-wallet call uses `--wallet` (`tools/cli/wallet_scan.py :: _default_scan_callable`, lines 181-190), but `scan` accepts `--user` only (`tools/cli/scan.py :: main parser`, lines 1731-1772).
8. Claimed robust dossier lifecycle/dedup: actual dedup is skip-if-content-hash-identical only (`packages/research/integration/dossier_extractor.py :: ingest_dossier_findings`, lines 481-498). Changed content creates a new source document (`packages/polymarket/rag/knowledge_store.py :: add_source_document`, lines 248-281) and no source-document lifecycle exists (`packages/polymarket/rag/knowledge_store.py :: _init_schema`, lines 139-149).
9. Claimed `polytool_brain` Chroma collection: code defaults to `polytool_rag` (`packages/polymarket/rag/defaults.py :: defaults`, lines 7-8) and separately uses `academic_papers` (`packages/research/synthesis/academic_query.py :: collection access`, lines 308-341).
10. Claimed insider scoring: no `insider_score.py` or insider implementation found; current scan and ClickHouse projections lack maker/taker wallet and cancel/fill inputs (`infra/clickhouse/initdb/02_tables.sql :: user_trades DDL`, lines 22-38; `infra/clickhouse/initdb/22_jon_becker_trades.sql :: jb_trades DDL`, lines 6-23).
11. Claimed exemplar selector: no implementation found under `packages`, `tools`, or `tests`.
12. Claimed LLM hypothesis generation loop: current report/hypothesis bridge code is deterministic (`packages/research/synthesis/report.py :: ReportSynthesizer`, lines 190-245; `packages/research/integration/hypothesis_bridge.py :: brief_to_candidate`, lines 85-145).
13. Claimed Loop B live monitoring: feasibility probe exists, production Alchemy WebSocket Loop B was not found (`packages/polymarket/discovery/loop_b_probe.py :: module contract`, lines 1-24).
14. Claimed Loop D managed CLOB subscription: probe explicitly does not implement Loop D and lists missing PING/dynamic-subscription/lifecycle/backfill features (`packages/polymarket/discovery/loop_d_probe.py :: module contract`, lines 1-14; `packages/polymarket/discovery/loop_d_probe.py :: audit_clob_stream_gaps`, lines 92-205).
15. Claimed discovery scheduler: no scheduled discovery cadence found; only manual CLI (`tools/cli/discovery.py :: main`, lines 16-83).
16. Claimed mirror scope external_knowledge + signals only: mirror code defines and runs four partitions (`docs/scripts/sync-ris-mirror.py :: ALL_PARTITIONS`, lines 62-69; `docs/scripts/sync-ris-mirror.py :: main`, lines 1039-1058).
17. Claimed wallet-discovery Grafana dashboard: no references to wallet discovery tables were found in `infra/grafana`; RIS health dashboard reads n8n metrics instead (`infra/grafana/dashboards/ris-pipeline-health.json :: RIS dashboard queries`, lines 111-115, 218-222, 322-326, 460-485).
18. Claimed Discord two-way handling: only outbound webhook code found (`packages/polymarket/notifications/discord.py :: post_message`, lines 55-77).

## Critical Unknowns For Work-Packet Scoping

1. Re-ingest / supersede behavior: not unknown anymore; the code path is clear. Same-content dossier findings are skipped by content hash, while changed-content findings create new source documents and new active claims. There is no supersede/retire lifecycle branch (`packages/research/integration/dossier_extractor.py :: ingest_dossier_findings`, lines 481-516; `packages/polymarket/rag/knowledge_store.py :: add_source_document`, lines 248-281; `packages/polymarket/rag/knowledge_store.py :: _init_schema`, lines 139-167).
2. Insider-data availability: raw Jon archives appear to contain maker/taker fields, but current scan output and ClickHouse imported trade tables do not preserve enough attribution for insider scoring (`packages/polymarket/llm_research_packets.py :: export position rows`, lines 1600-1639; `infra/clickhouse/initdb/02_tables.sql :: user_trades DDL`, lines 22-38; `infra/clickhouse/initdb/22_jon_becker_trades.sql :: jb_trades DDL`, lines 6-23; `packages/polymarket/silver_reconstructor.py :: _build_jon_fill_event`, lines 542-572).
3. Mirror scope: code mirrors all four partitions and does not exclude dossier KnowledgeStore rows from generic source/claim mirroring. It does not provide a dedicated dossier/user_data mirror path (`docs/scripts/sync-ris-mirror.py :: ALL_PARTITIONS`, lines 62-69; `docs/scripts/sync-ris-mirror.py :: sync_external_knowledge`, lines 387-517; `docs/scripts/sync-ris-mirror.py :: sync_user_data`, lines 786-862).
4. Scheduler state: RIS scheduler code and Docker services are built, but current runtime state was not verified. Discovery scheduling is not built (`packages/research/scheduling/scheduler.py :: start_research_scheduler`, lines 314-410; `docker-compose.yml :: ris-scheduler services`, lines 132-176; `tools/cli/discovery.py :: main`, lines 16-83).

## Test Coverage Note

Audited components with tests:

- Discovery state model, scan queue, and Loop A dry-run behavior: `tests/test_wallet_discovery.py`, lines 64-136 and 427-456; `tests/test_wallet_discovery_integrated.py`, lines 294-332 and 576-613.
- MVF and quick-scan MVF integration: `tests/test_mvf.py`, lines 133-220; `tests/test_wallet_discovery_integrated.py`, lines 400-514.
- Dossier extractor / ingestion idempotency and claim extraction: `tests/test_ris_dossier_extractor.py`, lines 340-511; `tests/test_wallet_scan_dossier_integration.py`, lines 106-126, 233-250, 328-351, and 429-447.
- Alpha-distill deterministic behavior: `tests/test_alpha_distill.py`, lines 412-443.
- Loop B and Loop D feasibility probes: `tests/test_loop_b_probe.py`, lines 429-528; `tests/test_loop_d_probe.py`.
- RIS scheduler: `tests/test_ris_scheduler.py`, lines 89-169 and 451-500; `tests/test_ris_scheduler_split.py`, lines 3-43.
- Discord outbound notifications: `tests/test_discord_notifications.py`, lines 88-115.

Audited components with no direct implementation tests found:

- Discovery queue consumer / automated wallet rescan scheduler: no implementation found.
- Insider scoring: no implementation found.
- Exemplar selector: no implementation found.
- Dossier changed-content supersede/retire behavior: no implementation found; existing tests cover identical-content idempotency but not changed-content lifecycle.
- Wallet-discovery Grafana dashboard: no implementation found.
- Two-way Discord bot/interactions: no implementation found.

## Commands Run

Read-only commands were used for inspection. No package installation, dependency change, live bot, order placement, on-chain command, code modification, or test modification was run.

Session-start checks:

```text
git log --oneline -5
c249ff5 docs(ris): operator-path simplicity test — 9 runbook corrections, readiness verdict
b921857 fix(ris): L2.1 one-paper acceptance repair — Chroma embed, span strip, NTFS fallback
7fc6bf2 fix(ris): L2.1 Deliverable B — offline-safe semantic fallback, resolves Codex BLOCK
15ef471 docs(ris): repo hygiene before L2.1 Deliverable A — closeout log
3348e79 feat(ris): L2.1 Deliverable C — display-only snippet sanitation
```

```text
python -m polytool --help
Exit code: 0
Observed commands included wallet-scan, alpha-distill, scan, research-dossier-extract,
research-scheduler, and discovery -> run-loop-a.
```

```text
git status --short
Exit code: 0
Result: dirty worktree before audit with many pre-existing modified/deleted/untracked
docs, vault, and research files. No existing file was reverted or overwritten.
```

Targeted path checks:

```text
Test-Path packages\polymarket\metrics
False

Test-Path docs/dev_logs/2026-05-29_wallet-ingestion-audit.md
False
```

Absence searches:

```text
rg stale/staleness/rescan/14-day patterns in discovery code and tests
Exit code: 1
No staleness threshold or scheduled rescan constant found.

rg insider_score / class Insider / def *insider under packages, tools, tests
No insider scoring implementation found.

rg wallet-discovery / watchlist / leaderboard_snapshots / scan_queue under infra/grafana
No wallet discovery dashboard references found.
```

No full test suite was run because this was a read-only audit and the only permitted write was this report. The required CLI smoke check `python -m polytool --help` passed with exit code 0.
