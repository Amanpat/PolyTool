# Current State / What We Built

This repo is a local-first toolchain for Polymarket analysis: data ingestion,
ClickHouse analytics, Grafana dashboards, private evidence exports, and a local
RAG workflow that never calls external LLM APIs.

Master Roadmap v5 (`docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md`) is the
governing roadmap document as of 2026-03-21 and supersedes v4.2. This file
records implemented repo truth; do not infer v5 phase completion from strategic
roadmap language alone.

## Roadmap Items Not Yet Implemented (v5 framing)

- The v4 control plane is not shipped: no n8n orchestration layer, no broad
  FastAPI wrapper surface, no Discord approval system, and no automated
  feedback loop.
- The v4 research expansion is not shipped: `candidate-scan`, research
  scraper, news/signals ingest, and signal-linked market workflows are not
  current repo features.
- The v4 UI rebuild is not shipped: existing Studio/Grafana surfaces remain
  the current operator UI, not the Phase 7 Next.js rebuild.
- The v4 live-bot path remains incomplete: Gate 2 is not passed, Gate 3 is
  blocked, and Stage 0/Stage 1 live promotion are not complete.

## Status as of 2026-03-27 (Phase 1B — Gate 2 NOT_RUN, corpus insufficient)

Track A / SimTrader plumbing is implemented. Phase 1B Gate 2 has been run
and returned NOT_RUN (not FAILED). The gate code previously wrote
`gate_failed.json` for sub-threshold corpora; this was incorrect per spec.
The corpus problem and the strategy have been separated by the diagnostic.
The repo's current execution status is:

- Gate 1: PASSED
- Gate 2: **NOT_RUN** (2026-03-27) — 10/50 tapes meet min_events=50 threshold;
  41 skipped as too short. Corpus insufficient for a valid Gate 2 verdict.
  Root cause: benchmark tapes have insufficient effective_events. The 9
  qualifying tapes all show RAN_ZERO_PROFIT / no_touch — the strategy does
  quote but spreads are never crossed on these near_resolution silver tapes.
  See dev log `docs/dev_logs/2026-03-26_phase1b_recovery_root_cause.md`
  and `artifacts/gates/mm_sweep_gate/diagnostic/diagnostic_report.md`.
- Gate 3: **BLOCKED** — Gate 2 must PASS first
- Gate 4: PASSED
- **Primary Gate 2 path**: DuckDB reads pmxt and Jon-Becker Parquet
  files directly — no ClickHouse import step required. Silver tape reconstruction
  from those files + 2-min price history → Gate 2 scenario sweep. ClickHouse
  bulk import (SPEC-0018) is off the critical path; see
  `docs/runbooks/BULK_HISTORICAL_IMPORT_V0.md` (now legacy/optional).
- **pmxt raw files**: exist locally. Full ClickHouse import (78,264,878 rows,
  2026-03-15) is complete but is legacy under v4.2. DuckDB reads the Parquet
  files directly. Artifact: `artifacts/imports/pmxt_full_batch1.json`
- **Jon-Becker raw files**: exist locally. Sample ClickHouse import confirmed
  (1,000 rows, 2026-03-16); full ClickHouse import is not required under v4.2.
  DuckDB reads the Parquet files directly.
  Artifacts: `artifacts/imports/jon_dry_run.json`, `artifacts/imports/jon_sample_run.json`
- **price_2min** (canonical live-updating ClickHouse series): table created
  (`infra/clickhouse/initdb/24_price_2min.sql`), `fetch-price-2min` CLI
  shipped. Naming conflict resolved: `price_2min` = live CH series (this path);
  `price_history_2min` = legacy local-file bulk import (SPEC-0018, off critical
  path). See dev log `docs/dev_logs/2026-03-16_price_2min_clickhouse_v0.md`.
  CLI: `python -m polytool fetch-price-2min --token-id <ID> [--dry-run]`.
- **Silver tape reconstruction**: foundation v0 shipped 2026-03-16; operational
  v1 shipped 2026-03-16. Single-market CLI (`reconstruct-silver`) and batch CLI
  (`batch-reconstruct-silver`) are operational. `tape_metadata` ClickHouse table
  defined (`infra/clickhouse/initdb/25_tape_metadata.sql`). Batch manifest
  (`silver_batch_manifest_v1`) written after each run. Metadata persists to
  ClickHouse with JSONL fallback. DuckDB + real dataset integration pending.
  See dev logs `2026-03-16_silver_reconstructor_foundation_v0.md` and
  `2026-03-16_silver_reconstructor_operational_v1.md`.
- **Benchmark v1 manifest curation**: `benchmark-manifest` CLI shipped
  2026-03-16. It audits canonical local tape roots and either writes
  `config/benchmark_v1.tape_manifest` + `config/benchmark_v1.audit.json`, or
  writes `config/benchmark_v1.gap_report.json` and exits non-zero when quotas
  are not satisfiable.
  **Bucket classification fix (2026-03-21)**: `silver_meta.json` contains no
  market text, so `_classify_candidate()` could not assign politics/sports/crypto
  labels to Silver tapes — all three keyword-driven buckets showed 0 candidates
  despite 120 tapes on disk. Fix: `market_meta.json` (schema
  `silver_market_meta_v1`) now written alongside Silver tapes containing `slug`,
  `category` (= bucket), `market_id`, `platform`, `token_id`, and
  `benchmark_bucket`. `_load_metadata()` reads `market_meta.json` first.
  `write_market_meta()` and `backfill_market_meta_from_targets()` added to
  `batch_reconstruct_silver.py`. `--backfill-market-meta` CLI flag triggers
  backfill-only mode (no reconstruction, no credential check). Backfill run:
  120 tape dirs updated, 0 errors. Latest gap report
  (`config/benchmark_v1.gap_report.json`, `2026-03-21T19:42:42+00:00`):
  `inventory_by_tier gold=13, silver=118`, `selected_total=45`,
  shortages `politics=0, sports=0, crypto=0, near_resolution=0, new_market=5`.
  Only `new_market=5` remains. No `config/benchmark_v1.tape_manifest` exists
  yet (blocked by new_market shortage only). A resumed real-shell Phase 1
  closure attempt earlier on 2026-03-21 set `CLICKHOUSE_PASSWORD`, brought
  Docker up, and ran `python -m polytool new-market-capture`, which wrote 300
  live targets (`generated_at 2026-03-21T20:05:03Z`). The follow-up
  `capture-new-market-tapes --benchmark-refresh` run then created 0 tapes and
  skipped all 300 targets because every `resolve_slug` call failed with
  `MarketPicker.__init__() missing 2 required positional arguments:
  'gamma_client' and 'clob_client'`. Refreshed gap report
  (`config/benchmark_v1.gap_report.json`, `2026-03-21T20:05:05+00:00`) still
  shows `new_market.candidate_count=0` and shortage `new_market=5`. That
  constructor bug is now fixed. A later final Phase 1 retry on 2026-03-21 used
  the corrected CLI flags and passed dry-run
  (`targets_attempted=300`, `tapes_created=231`, `failure_count=0`,
  `skip_count=69`). The follow-up live command
  `python -m polytool capture-new-market-tapes --targets-manifest config/benchmark_v1_new_market_capture.targets.json --out-root artifacts/tapes/new_market --benchmark-refresh`
  recorded new Gold tapes under `artifacts/tapes/new_market/` but appeared to
  hang past the five-tape quota. Finalization check on 2026-03-21 then stopped
  PID `9660`, confirmed the relevant tape dirs on disk (`sol`, `xrp`, `bnb`,
  `hype`, `eth`, `doge`) all had `raw_ws.jsonl`, `events.jsonl`, `meta.json`,
  and `watch_meta.json`, and also found a previously unlisted
  `btc-updown-5m-1774209300/` dir with `raw_ws.jsonl`, `events.jsonl`, and
  `watch_meta.json` but no `meta.json`. Running plain
  `python -m polytool benchmark-manifest` still wrote a gap report because the
  default `inventory_roots` were only `artifacts/simtrader/tapes` and
  `artifacts/silver`, so none of the `artifacts/tapes/new_market/*` tapes were
  discovered. Re-running with explicit roots
  `--root artifacts/simtrader/tapes --root artifacts/silver --root artifacts/tapes/new_market`
  immediately wrote `config/benchmark_v1.tape_manifest`,
  `config/benchmark_v1.audit.json`, and `config/benchmark_v1.lock.json`.
  Validation passed with bucket counts
  `politics=10, sports=15, crypto=10, near_resolution=10, new_market=5`.
  Audit selected five `new_market` tapes:
  `xrp-updown-5m-1774209300`, `sol-updown-5m-1774209300`,
  `btc-updown-5m-1774209300`, `bnb-updown-5m-1774209300`, and
  `hype-updown-5m-1774209300`. `benchmark_v1` is now closed. See dev logs
  `docs/dev_logs/2026-03-21_benchmark_curation_bucket_fix.md`,
  `docs/dev_logs/2026-03-21_phase1_new_market_closure_attempt.md`,
  `docs/dev_logs/2026-03-21_phase1_final_new_market_execution_retry.md`, and
  `docs/dev_logs/2026-03-21_phase1_finalization_check.md`.
- **Benchmark v1 gap-fill planner**: `packages/polymarket/benchmark_gap_fill_planner.py`
  shipped 2026-03-17. Queries pmxt_archive + Jon-Becker Parquet via DuckDB to
  discover Silver reconstruction targets for the shortage buckets. Real-data
  probe (2026-03-17): 9,249 markets matched; 2,052 politics / 2,049 sports /
  279 crypto / 272 near_resolution candidates found — all four buckets coverable
  via Silver reconstruction. new_market bucket remains INSUFFICIENT (0
  candidates; JB snapshot ~2026-02-03, 40 days stale). Target manifest written
  to `config/benchmark_v1_gap_fill.targets.json` (120 targets; 9+11+10+9
  priority-1 + overflow); insufficiency report at
  `config/benchmark_v1_gap_fill.insufficiency.json`.
  See spec `docs/specs/SPEC-benchmark-gap-fill-planner-v1.md` and dev log
  `docs/dev_logs/2026-03-17_benchmark_gap_fill_planner.md`.
  A constrained live probe on 2026-03-19 confirmed that three priority-1
  targets (politics / sports / crypto) reconstruct successfully without hard
  failures, but all three degrade to low-confidence, price_2min-only Silver
  tapes because pmxt anchors and Jon-Becker fills are absent in-window. A full
  direct live run completed on 2026-03-20 under
  `artifacts/silver/manual_gap_fill_full_20260319_213841/`: all 120 manifest
  targets wrote a `benchmark_gap_fill_run_v1` artifact, but benchmark refresh
  still blocked with shortages `politics=9`, `sports=11`, `crypto=10`,
  `near_resolution=0`, `new_market=5`. The benchmark is therefore not reduced
  to `new_market` only.
- **Benchmark v1 gap-fill execution**: `batch-reconstruct-silver` extended with
  `--targets-manifest` mode (Mode 2) 2026-03-17. Accepts `benchmark_gap_fill_v1`
  targets manifest; each target provides its own window. Per-target skip/failure
  without aborting the batch. `--benchmark-refresh` re-runs benchmark curation after
  the batch. Emits `benchmark_gap_fill_run_v1` result artifact. 40 new tests; dry-run
  smoke with 120-target real manifest: all parsed and dispatched correctly.
  A real-shell probe run on 2026-03-19 wrote
  `artifacts/silver/manual_gap_fill_probe3_20260319_190329/gap_fill_run.json`
  for three priority-1 targets (politics / sports / crypto):
  `targets_attempted=3`, `tapes_created=3`, `failure_count=0`, `skip_count=0`,
  metadata writes `clickhouse=3`. All three outcomes are `status=success` with
  `reconstruction_confidence=low`, `fill_count=0`, and
  `price_2min_count=event_count`, with shared warnings
  `pmxt_anchor_missing` and `jon_fills_missing`. A full-manifest direct live
  execution then completed on 2026-03-20 at
  `artifacts/silver/manual_gap_fill_full_20260319_213841/gap_fill_run.json`:
  `targets_attempted=120`, `tapes_created=120`, `failure_count=0`,
  `skip_count=0`, metadata writes `clickhouse=120`. Success classes were 40
  `confidence=low, price_2min_only` outcomes and 80 `confidence=none,
  empty_tape` outcomes; warnings were `pmxt_anchor_missing=120`,
  `jon_fills_missing=120`, `price_2min_missing=80`. Benchmark refresh updated
  `config/benchmark_v1.gap_report.json` but still blocked with shortages
  `politics=9`, `sports=11`, `crypto=10`, `near_resolution=0`,
  `new_market=5`. See dev logs
  `docs/dev_logs/2026-03-19_silver_probe3_diagnosis.md` and
  `docs/dev_logs/2026-03-20_silver_gap_fill_full_run.md`.
  A resumed orchestrated live closure run on 2026-03-20 after the full-target
  prefetch fix wrote
  `artifacts/benchmark_closure/2026-03-20/bf64af3f-17bc-429f-ac09-8fbf05ad66ad/benchmark_closure_run_v1.json`:
  Stage 2 prefetched 118 unique token IDs across all 120 targets, fetched and
  inserted 450,327 `price_2min` rows, and `batch_reconstruct` again created 120
  tapes with `failure_count=0` and `skip_count=0`. The refreshed gap report did
  raise `inventory_by_tier.silver` from 38 to 118 and `near_resolution`
  `candidate_count` from 21 to 81, but shortages remained `politics=9`,
  `sports=11`, `crypto=10`, `near_resolution=0`, `new_market=5`, so
  `benchmark_v1` is still not reduced to `new_market` only.
  See spec `docs/specs/SPEC-benchmark-gap-fill-execution-v1.md` and dev log
  `docs/dev_logs/2026-03-17_benchmark_gap_fill_execution.md`.
- **New-market capture planner**: `packages/polymarket/new_market_capture_planner.py`
  shipped 2026-03-17. Discovers newly listed Polymarket candidates (<48h old) via
  the live Gamma API, ranks them conservatively (age ascending, volume desc, slug
  asc), deduplicates by token_id, and writes
  `config/benchmark_v1_new_market_capture.targets.json` (if candidates exist) and/or
  `config/benchmark_v1_new_market_capture.insufficiency.json` (if < 5 candidates).
  CLI: `python -m polytool new-market-capture [--dry-run] [--limit 300]`.
  `fetch_recent_markets()` added to `market_selection/api_client.py` (returns
  `condition_id` + `market_id` in addition to standard fields). 42 offline tests;
  no live network calls in tests.
  See spec `docs/specs/SPEC-new-market-capture-planner-v1.md` and dev log
  `docs/dev_logs/2026-03-17_new_market_capture_planner.md`.
- **New-market capture execution**: `tools/cli/capture_new_market_tapes.py` shipped
  2026-03-17. Consumes `config/benchmark_v1_new_market_capture.targets.json`
  (schema `benchmark_new_market_capture_v1`), resolves YES/NO token IDs via
  `MarketPicker.resolve_slug()`, records Gold tapes via `TapeRecorder` for each
  target's `record_duration_seconds`, writes `watch_meta.json` with
  `regime="new_market"`, persists `tape_metadata` row (tier="gold") to ClickHouse
  with JSONL fallback. `--benchmark-refresh` re-runs benchmark curation after the
  batch. Emits `benchmark_new_market_capture_run_v1` result artifact. Per-target
  failures do not abort the batch. 45 offline tests; no live network calls in tests.
  CLI: `python -m polytool capture-new-market-tapes [--dry-run] [--benchmark-refresh]`.
  A real live attempt ran on 2026-03-21 after `CLICKHOUSE_PASSWORD` and Docker
  were confirmed. Planner output contained 300 viable new-market targets, but
  capture artifact `artifacts/simtrader/tapes/new_market_capture/capture_run_558b6d88.json`
  shows `targets_attempted=300`, `tapes_created=0`, `failure_count=0`,
  `skip_count=300`. Every target was skipped at slug resolution because
  `MarketPicker.__init__()` was called without required `gamma_client` and
  `clob_client` arguments, so no Gold tapes were recorded and benchmark refresh
  remained blocked with `new_market=5`.
  **MarketPicker constructor fix (2026-03-21)**: `resolve_both_token_ids()` in
  `capture_new_market_tapes.py` was calling `MarketPicker()` with no arguments.
  Fixed to `MarketPicker(GammaClient(), ClobClient())` matching every other CLI
  entrypoint (`simtrader.py`, `prepare_gate2.py`, `watch_arb_candidates.py`).
  Regression test `test_default_path_constructs_picker_with_clients` added.
  46 tests pass in `test_capture_new_market_tapes.py`. Constructor bug no longer
  skips all 300 targets. A corrected dry-run on 2026-03-21 passed
  (`targets_attempted=300`, `tapes_created=231`, `skip_count=69`). The
  corrected live capture with `--benchmark-refresh` then recorded at least six
  Gold tapes under `artifacts/tapes/new_market/`, but never emitted a new
  `capture_run_*.json` or benchmark refresh. As of
  `2026-03-21T19:36:26-04:00`, PID `9660` was still writing
  `doge-updown-5m-1774209300/raw_ws.jsonl`, proving the live path continues
  past the required five-tape quota instead of terminating cleanly.
  See spec `docs/specs/SPEC-new-market-capture-execution-v1.md` and dev log
  `docs/dev_logs/2026-03-17_new_market_capture_execution.md`, plus run logs
  `docs/dev_logs/2026-03-21_phase1_new_market_closure_attempt.md` and
  `docs/dev_logs/2026-03-21_new_market_capture_marketpicker_fix.md`.
- **Benchmark closure orchestrator v0**: `tools/cli/close_benchmark_v1.py`
  shipped 2026-03-17. Orchestrates preflight + Silver gap-fill + new-market
  capture + benchmark curation in sequence. CLI:
  `python -m polytool close-benchmark-v1 [--dry-run] [--skip-silver]
  [--skip-new-market] [--out PATH] [--pmxt-root PATH] [--jon-root PATH]`.
  Writes canonical run artifact `benchmark_closure_run_v1` to
  `artifacts/benchmark_closure/<YYYY-MM-DD>/<run_id>/`.  Exit 0 =
  manifest_created, exit 1 = blocked, exit 2 = preflight blocked.  23 offline
  tests (all passing). Real dry-run confirmed: preflight passes, 39 priority-1
  tokens identified, 5-bucket shortage correctly surfaced from real gap report.
  **Prefetch scope fix (2026-03-20)**: `run_silver_gap_fill_stage()` previously
  called `_priority1_token_ids()` for the `fetch-price-2min` argv, covering only
  39 of 120 targets. The remaining 81 overflow (priority≥2) targets had no
  `price_2min` rows in ClickHouse, causing the Silver reconstructor to degrade
  them to `confidence=none` (root cause of `price_2min_missing=80` in the
  2026-03-20 full run). Fixed by adding `_all_unique_token_ids()` (order-
  preserving dedup via `dict.fromkeys`) and switching the fetch argv to use all
  unique token IDs across all priorities. `fetch_outcome` now records both
  `token_count` (all) and `priority1_count` for traceability. 10 new regression
  tests added (5 in `TestHelpers`, 5 in `TestFullTargetPricePrefetch`); 40 tests
  pass in `test_close_benchmark_v1.py` (57 across both closure test files).
  See spec `docs/specs/SPEC-benchmark-closure-orchestrator-v1.md` and dev logs
  `docs/dev_logs/2026-03-17_benchmark_closure_orchestrator_v0.md` and
  `docs/dev_logs/2026-03-20_full_target_price2min_prefetch_fix.md`.
  Real-shell validation followed immediately on 2026-03-20: the fixed closure
  path prefetched all 118 unique target token IDs (39 priority-1 entries across
  120 manifest targets), refreshed the gap report, and wrote run artifact
  `artifacts/benchmark_closure/2026-03-20/bf64af3f-17bc-429f-ac09-8fbf05ad66ad/benchmark_closure_run_v1.json`.
  The closure still ended `final_status=blocked`, proving the prefetch scope bug
  is fixed but is no longer the limiting factor; the remaining shortages are
  still `politics=9`, `sports=11`, `crypto=10`, and `new_market=5`.
- **Benchmark closure operator readiness v0**: Shipped 2026-03-17.
  Added `--status` and `--export-tokens` operator helpers to `close_benchmark_v1.py`.
  `--status` prints a human-readable closure progress table (manifest, gap-fill
  targets, token export, latest run, residual blockers, suggested next step).
  `--export-tokens` materialises the 39 priority-1 token IDs from the gap-fill
  targets manifest to `config/benchmark_v1_priority1_tokens.txt` (one per line)
  and `config/benchmark_v1_priority1_tokens.json`. Both flags are read-only,
  idempotent, and safe without Docker/ClickHouse. Token export confirmed: 39
  tokens written. Canonical operator runbook:
  `docs/runbooks/BENCHMARK_CLOSURE_RUNBOOK.md` (7 resumable steps).
  17 new offline tests (all passing). See spec
  `docs/specs/SPEC-benchmark-closure-operator-readiness-v0.md` and dev log
  `docs/dev_logs/2026-03-17_benchmark_closure_operator_readiness_v0.md`.
  Real operator attempt executed on 2026-03-17 from branch `phase-1`.
  Docker came up successfully enough for `polytool-clickhouse` to report
  healthy, and `--status` confirmed `config/benchmark_v1_new_market_capture.targets.json`
  already exists locally. The first live attempt stopped at
  `python -m polytool fetch-price-2min --token-file config/benchmark_v1_priority1_tokens.txt`
  with Windows stdout `UnicodeEncodeError` on `\\u2192`; that console bug is
  fixed and regression-tested (`test_stdout_encodable_as_cp1252`). Resumed live
  attempt artifact root:
  `artifacts/benchmark_closure/live_attempt_resume_2026-03-17_210038`.
  The resumed live fetch succeeded for the priority-1 export, processing 38
  unique token IDs from the 39-line file (one duplicated token) and inserting
  `149626` rows into `polytool.price_2min`. The next real blocker is
  downstream in the Silver closure / refresh path:
  `python -m polytool close-benchmark-v1 --skip-new-market ...` ended blocked,
  `config/benchmark_v1.tape_manifest` was not created, and stderr recorded
  repeated `price_2min: ClickHouse query failed: 400 ...` plus
  `jon: missing required columns. token_col=None ts_col=timestamp ...` while
  refresh fell back to `config/benchmark_v1.gap_report.json`.
  See `docs/dev_logs/2026-03-17_benchmark_closure_live_attempt.md`,
  `docs/dev_logs/2026-03-17_benchmark_closure_live_attempt_resume.md`, and
  `docs/dev_logs/2026-03-17_fetch_price_2min_windows_stdout_fix.md`.
- **Silver input compatibility fix** (2026-03-18): Two root-cause bugs in
  `packages/polymarket/silver_reconstructor.py` that blocked the Silver closure
  path are now fixed: (1) `_real_fetch_price_2min()` was calling
  `toDateTime('{ISO string}')` which ClickHouse rejects with HTTP 400 —
  replaced with `toDateTime({int(epoch)})`. (2) `_real_fetch_jon_fills()` used
  `_JON_TOKEN_CANDIDATES = ["asset_id", ...]` which does not match the real
  Jon-Becker maker/taker dataset schema (`maker_asset_id` + `taker_asset_id`);
  now detects the maker/taker pair and issues an OR query. 13 new regression
  tests added in `tests/test_silver_input_compatibility.py`. 145 existing Silver
  tests still pass. Two resumed live closure attempts were then tried on
  2026-03-18, followed by a Docker Desktop recovery/verification pass on
  2026-03-18/2026-03-19. The in-sandbox Codex account
  (`desktop-6l73imi\\codexsandboxoffline`) saw `docker version`,
  `docker info`, `docker compose ps`, `wsl --status`, and `wsl -l -v` fail
  with access denied, which initially looked like a local Docker Desktop
  outage. A second verification outside the sandbox as the real Windows user
  (`desktop-6l73imi\\patel`) showed Docker Desktop healthy: `docker version`
  returned both client and server, `docker info` reported Docker Desktop
  4.52.0 / Engine 29.0.1, `wsl --status` reported default distro
  `docker-desktop`, and `wsl -l -v` showed `docker-desktop` running under
  WSL2. `docker compose ps` succeeded but showed no running compose services,
  and read-only `python -m polytool close-benchmark-v1 --status` still reports
  residual shortages in `politics` (9), `sports` (11), `crypto` (10),
  `near_resolution` (9), and `new_market` (5), with
  `config/benchmark_v1.tape_manifest` still missing. This establishes that the
  earlier Docker failure was a Codex sandbox permissions boundary, not a broken
  Docker Desktop installation or WSL backend. See
  `docs/dev_logs/2026-03-18_silver_input_compatibility_fix.md`,
  `docs/dev_logs/2026-03-18_benchmark_closure_resume_after_silver_fix.md`,
  `docs/dev_logs/2026-03-18_benchmark_closure_after_docker_recovery.md`, and
  `docs/dev_logs/2026-03-18_docker_desktop_engine_recovery_attempt.md`.
- **ClickHouse auth propagation fix — Stage 2 complete** (2026-03-18 +
  2026-03-19): The `AUTHENTICATION_FAILED` (HTTP 516) bug that blocked Stage 2
  Silver gap-fill has been fully resolved across all Stage 2 CLI entrypoints.
  The 2026-03-18 patch fixed `close_benchmark_v1.main()` and
  `batch_reconstruct_silver.main()` but missed `fetch_price_2min.main()`,
  which still silently fell back to `"polytool_admin"` as the ClickHouse
  password when neither `--clickhouse-password` nor `CLICKHOUSE_PASSWORD` env
  was set (via `os.environ.get("CLICKHOUSE_PASSWORD", "polytool_admin")`).
  The 2026-03-19 follow-up: (1) removed the `"polytool_admin"` fallback from
  `fetch_price_2min.main()` — now fail-fast with `if not ch_password`; (2)
  strengthened the existing fail-fast guards in `close_benchmark_v1.main()`
  and `batch_reconstruct_silver.main()` from `if ch_password is None` to
  `if not ch_password` to catch empty-string exports (`CLICKHOUSE_PASSWORD=""`).
  Four new regression tests in `test_fetch_price_2min.py`
  (`TestFetchPrice2MinAuthFailFast`) and one each in `test_close_benchmark_v1.py`
  and `test_batch_silver.py` (`test_empty_string_password_returns_1`). All
  six new tests pass; 113 tests across the three affected files pass with no
  regressions. See dev logs
  `docs/dev_logs/2026-03-18_clickhouse_auth_propagation_fix.md` and
  `docs/dev_logs/2026-03-19_clickhouse_auth_stage2_fix.md`.
- **Silver stage read-auth fix** (2026-03-19): Two remaining structural gaps in the
  benchmark closure orchestrator are now fixed. (1) `_check_clickhouse` now sends
  `Authorization: Basic <base64(user:password)>` with every probe request, so
  preflight no longer reports CH unavailable on a healthy credential-protected instance.
  (2) `run_preflight` now accepts and forwards `clickhouse_user`/`clickhouse_password`
  to `_check_clickhouse`, making the preflight CH probe structurally consistent with
  Stage 2's authenticated access. (3) `run_silver_gap_fill_stage` now bubbles per-target
  failure details (`token_id`, `bucket`, `slug`, `error`) from `run_batch_from_targets`
  outcomes into `batch_reconstruct["failed_targets"]` in the orchestrator artifact for
  direct triage without digging into the full batch artifact. Three new regression tests
  added (`TestPreflightCredentialConsistency`): auth header sent, credentials forwarded,
  failed targets surfaced. 116 tests across the three affected files pass.
  See dev log `docs/dev_logs/2026-03-19_silver_stage_read_auth_fix.md`.
- **Direct Silver gap-fill diagnosis, resumed with a 3-target probe**
  (2026-03-19): The first same-day real-shell attempt was blocked before Docker
  startup because `CLICKHOUSE_PASSWORD` was empty in the shell environment; see
  `docs/dev_logs/2026-03-19_silver_gap_fill_direct_diagnosis.md`. After
  re-supplying the password, a constrained 3-target follow-up probe ran under
  `artifacts/silver/manual_gap_fill_probe3_20260319_190329/` and wrote a real
  `gap_fill_run.json`. Politics
  (`100-tariff-on-canada-in-effect-by-june-30`), sports
  (`2025-2026-epl-winner-more-than-90-points`), and crypto
  (`another-crypto-hack-over-100m-before-2027`) all finished with
  `status=success`, but all three share the same degraded success class:
  `reconstruction_confidence=low`, `fill_count=0`, and event tapes comprised
  only `price_2min_guide` entries because no pmxt anchor snapshot and no
  Jon-Becker fills were found for their windows. This clears the "hard failure"
  hypothesis for the sampled politics / sports / crypto buckets, but it does
  not yet prove that `benchmark_v1` is blocked only by `new_market`; the full
  gap-fill manifest and the `near_resolution` bucket still need live
  confirmation. See dev log
  `docs/dev_logs/2026-03-19_silver_probe3_diagnosis.md`.
- **Gap-fill summarizer** (2026-03-20): Read-only diagnostic CLI
  `summarize-gap-fill` shipped. Loads any `benchmark_gap_fill_run_v1` artifact
  and prints totals, per-bucket breakdown (success/failure/skip + confidence
  distribution), normalized warning and error classes, success class
  classification (price_2min_only vs. has_fills, etc.), metadata write summary,
  benchmark refresh outcome, and artifact paths. `--json` flag emits
  machine-readable output. No network, no ClickHouse, no writes.
  Smoke-tested against both the probe-3 (3-target) and full (120-target) real
  artifacts. Key findings from full-manifest run:
  all 4 non-new-market buckets produced tapes with 0 hard failures;
  80/120 tapes are `confidence=none` (empty, `price_2min_missing` +
  `pmxt_anchor_missing` + `jon_fills_missing`); 40/120 are `confidence=low`
  (price_2min_only). CLI: `python -m polytool summarize-gap-fill --path <path>`.
  35 offline tests passing.
  See spec `docs/specs/SPEC-summarize-gap-fill-v0.md` and dev log
  `docs/dev_logs/2026-03-20_gap_fill_summarizer_v0.md`.
- Gate 2 is not closed, but benchmark_v1 is now closed as of 2026-03-21.
  After the same-day new-market capture retries, a finalization check stopped
  the hanging live process, confirmed the recorded `artifacts/tapes/new_market`
  tapes on disk, and showed why plain `benchmark-manifest` still blocked:
  default `inventory_roots` excluded `artifacts/tapes/new_market`. Re-running
  `benchmark-manifest` with explicit roots for `artifacts/simtrader/tapes`,
  `artifacts/silver`, and `artifacts/tapes/new_market` wrote
  `config/benchmark_v1.tape_manifest` and `config/benchmark_v1.lock.json`.
  Validation passed with bucket counts
  `politics=10, sports=15, crypto=10, near_resolution=10, new_market=5`, so
  the benchmark is closed and the next work can move to Gate 2 scenario sweep.
- Opportunity Radar: deferred until after the first clean Gate 2 -> Gate 3
  progression

## Phase 1B — Gate 2 Benchmark Sweep Tooling Complete (2026-03-26)

Gate 2 sweep tooling is now complete. The following changes landed on
2026-03-26:

- **`tools/gates/mm_sweep.py`** — extended `_build_tape_candidate` with full
  metadata fallback chain for YES asset ID extraction:
  `prep_meta.json` → `meta.json` context extraction → `watch_meta.json`
  (`yes_asset_id`) → `market_meta.json` (`token_id`) → `silver_meta.json`
  (`token_id`). Bucket derivation reads `watch_meta.bucket` or
  `market_meta.benchmark_bucket`. All 50 benchmark_v1 tapes (Gold new_market
  + Silver buckets) can now be swept without YES-token lookup failures.
  Added `bucket` field to `TapeCandidate` dataclass.
  Added `bucket_breakdown` dict to gate JSON payload when bucket metadata is
  present.
  Added `gate_summary.md` Markdown artifact alongside `gate_passed.json` /
  `gate_failed.json`, with per-bucket table and per-tape verdict rows.

- **`tools/gates/close_mm_sweep_gate.py`** — added `--benchmark-manifest`
  flag. When passed, overrides `--tapes-dir` and `--manifest` and runs the
  full 50-tape sweep. Command:
  `python tools/gates/close_mm_sweep_gate.py --benchmark-manifest config/benchmark_v1.tape_manifest --out artifacts/gates/mm_sweep_gate`

- **`tests/test_mm_sweep_gate.py`** — 7 new tests covering `watch_meta`,
  `market_meta`, `silver_meta` fallbacks, `bucket_breakdown` presence and
  absence, CLI `--benchmark-manifest` flag, and Markdown summary writing.
  12 total tests pass (0.43s); 0 failed.

- **`docs/specs/SPEC-phase1b-gate2-shadow-packet.md`** — Phase 1B spec:
  Gate 2 criteria (>= 70%), artifact contract (bucket_breakdown schema),
  Gate 3 criteria and promotion path.

- **`docs/runbooks/GATE3_SHADOW_RUNBOOK.md`** — full Gate 3 operator runbook:
  prerequisites, safety invariants, shadow session commands, artifact checks,
  gate_passed.json authoring, abort criteria.

**Gate 2 execution result (2026-03-26): NOT_RUN — corpus insufficient**

Gate 2 was run on 2026-03-26 against `config/benchmark_v1.tape_manifest`.
Verdict: **NOT_RUN** — only 10/50 tapes meet `min_events=50` threshold;
41 tapes skipped as SKIPPED_TOO_SHORT. Gate requires at least 50 eligible
tapes to compute a valid verdict. `gate_failed.json` has been cleared.

Diagnostic run on 2026-03-26 confirms:
- 41/50 tapes: SKIPPED_TOO_SHORT (effective_events < 50)
- 9/50 tapes: RAN_ZERO_PROFIT / no_touch — strategy does quote but spreads
  are never crossed on these near_resolution Silver tapes
- 0 fills across all 9 qualifying tapes
- Fill opportunity classification: all 9 are "no_touch" (strategy quoted,
  market never crossed the spread in replay)

Root cause of NOT_RUN: the benchmark_v1 corpus consists primarily of
short Silver tapes (reconstructed from price_2min only, no pmxt/JB fills)
with insufficient event density. The 5 Gold new_market tapes have 1-3
effective events each after deduplication.

Code changes included in this session (2026-03-26):
- **`tools/gates/mm_sweep.py`** — added `min_eligible_tapes` parameter
  (default=50); NOT_RUN branch returns `gate_payload=None` and clears old
  artifacts when eligible tape count is below threshold.
- **`tools/gates/close_mm_sweep_gate.py`** — NOT_RUN exits 0 (not 1);
  added `--min-eligible-tapes` CLI argument.
- **`tools/cli/simtrader.py`** — NOT_RUN exits 0; added `--min-eligible-tapes`.
- **`tools/gates/mm_sweep_diagnostic.py`** — new per-tape root cause diagnostic
  tool. Run with `--benchmark-manifest config/benchmark_v1.tape_manifest`.
- **`docs/specs/SPEC-0012`** — updated §2 to declare `market_maker_v1` as
  canonical Phase 1 strategy (authority conflict resolved).
- **`docs/ARCHITECTURE.md`** — updated 3 occurrences from `market_maker_v0`
  to `market_maker_v1`.

Gate 2 artifacts:
- `artifacts/gates/mm_sweep_gate/diagnostic/diagnostic_report.md` — per-tape
  breakdown (50 tapes: 41 SKIPPED_TOO_SHORT, 9 RAN_ZERO_PROFIT, all no_touch)
- No `gate_failed.json` or `gate_passed.json` (NOT_RUN clears old artifacts)

**Gate 3**: NOT RUN. Gate 2 must PASS first per spec.

**Next action**: Acquire longer, higher-quality tapes to meet the 50-tape
eligible corpus requirement. Options: (a) lower `min_events` threshold with
justification, (b) record longer Gold tapes via shadow mode, (c) reconstruct
Silver tapes with pmxt+JB data for buckets that have historical coverage.
See dev log `docs/dev_logs/2026-03-26_phase1b_recovery_root_cause.md`
and `artifacts/gates/mm_sweep_gate/diagnostic/diagnostic_report.md`.

## Phase 1B — Corpus Recovery Tooling (2026-03-26)

Recovery corpus tooling is now complete. The following changes landed on
2026-03-26 as quick-027:

- **`docs/specs/SPEC-phase1b-corpus-recovery-v1.md`** — Authoritative contract
  for the recovery corpus. Defines admission rules (min_events=50, tier
  preference Gold>Silver, 5-bucket quotas: politics=10, sports=15, crypto=10,
  near_resolution=10, new_market=5), manifest versioning policy, Gate 2 rerun
  preconditions, and success/failure artifact contracts. benchmark_v1 files
  are explicitly preserved as immutable.

- **`tools/gates/corpus_audit.py`** — Scans tape inventory across configurable
  tape roots, applies admission rules, and writes either
  `config/recovery_corpus_v1.tape_manifest` (exit 0, corpus qualified) or
  `artifacts/corpus_audit/shortage_report.md` (exit 1, corpus insufficient).
  CLI: `python tools/gates/corpus_audit.py --tape-roots <dir> --out-dir
  artifacts/corpus_audit --manifest-out config/recovery_corpus_v1.tape_manifest`

- **`tests/test_corpus_audit.py`** — 6 TDD tests covering all admission rule
  paths: accepted tape, too_short rejection, no_bucket_label rejection, quota
  cap enforcement, shortage report writing on insufficient corpus, manifest
  writing on qualified corpus. All 6 pass; full suite 2662 passed.

- **`artifacts/corpus_audit/shortage_report.md`** — Current shortage: 10/50
  tapes qualify (1 politics Gold + 9 near_resolution Silver). Exact need per bucket:
  crypto=10, near_resolution=1, new_market=5, politics=9, sports=15.

- **`artifacts/corpus_audit/phase1b_residual_shortage_v1.md`** — Definitive
  operator guide (quick-028): corpus state table, why live capture is the only path,
  exact shadow capture commands per bucket (sports=15, politics=9, crypto=10,
  new_market=5, near_resolution=1), resume instructions, Gate 2/3 command reference.

- **`docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md`** — Step-by-step operator
  guide: prerequisites, shortage check, shadow capture command (600s minimum,
  market_maker_v1 strategy, --record-tape), post-capture validation,
  resumability workflow, bucket targeting guide, stopping condition.

**Gate 2 recovery path status (2026-03-27): corpus 10/50 — SHORTAGE**

Recovery corpus audit: 137 tapes scanned, 10 accepted (1 politics Gold +
9 near_resolution Silver), 127 rejected. All 5 buckets must be covered.
Gate 2 rerun is blocked until corpus_audit.py exits 0.

quick-028 (2026-03-27): salvaged 1 politics Gold tape by injecting
`market_meta.json` and `watch_meta.json` into
`artifacts/simtrader/tapes/20260226T181825Z_shadow_10167699/`. Silver
reconstruction is exhausted; all remaining 40 tapes require live Gold
shadow captures.

**Definitive shortage packet**: `artifacts/corpus_audit/phase1b_residual_shortage_v1.md`
— exact capture commands per bucket, resume instructions, Gate 2/3 reference.

**Next action**: Capture Gold shadow tapes using
`docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md`. Remaining shortage:
sports=15, politics=9, crypto=10, new_market=5, near_resolution=1
(total 40 tapes). When corpus_audit exits 0, manifest is written and
Gate 2 rerun is unblocked:
`python tools/gates/close_mm_sweep_gate.py --benchmark-manifest config/recovery_corpus_v1.tape_manifest --out artifacts/gates/mm_sweep_gate`

benchmark_v1 files (tape_manifest, lock.json, audit.json) are unchanged.

## Track 2 / Phase 1A — Crypto Pair Bot (2026-03-23)

Phase 1A (Track 2, crypto pair bot) code and infrastructure are shipped as of
2026-03-23. The primary deliverables:

- **Accumulation engine** (`packages/polymarket/crypto_pairs/accumulation_engine.py`):
  YES + NO pair accumulation below pair-cost ceiling. Kill switch, daily loss
  cap, max open pairs, max unpaired exposure window.
- **Reference feed** (`packages/polymarket/crypto_pairs/reference_feed.py`):
  BTC/ETH/SOL price feed with injectable provider selection. Supports Binance
  WebSocket (`BinanceFeed`), Coinbase WebSocket (`CoinbaseFeed`), and automatic
  fallback (`AutoReferenceFeed`: Binance primary, Coinbase fallback). Provider
  selected via `--reference-feed-provider binance|coinbase|auto`. Safety state
  machine: `CONNECTED`, `DISCONNECTED`, `NEVER_CONNECTED`; stale threshold 15s.
- **Fair value** (`packages/polymarket/crypto_pairs/fair_value.py`):
  Pair-cost calculation and threshold evaluation.
- **Live execution** (`packages/polymarket/crypto_pairs/live_execution.py`):
  Order routing and fill simulation (paper mode).
- **Live runner** (`packages/polymarket/crypto_pairs/live_runner.py`):
  Main run loop; emits Track 2 event objects; writes JSONL artifacts and
  ClickHouse events on finalization.
- **Event models** (`packages/polymarket/crypto_pairs/event_models.py`):
  7 Track 2 event types, ClickHouse projection contract.
- **ClickHouse sink** (`packages/polymarket/crypto_pairs/clickhouse_sink.py`):
  Optional projection target; disabled by default; enabled with `--sink-enabled`.
- **ClickHouse table** (`infra/clickhouse/initdb/26_crypto_pair_events.sql`):
  `polytool.crypto_pair_events` — `ReplacingMergeTree`, `ORDER BY (run_id,
  event_type, event_ts, event_id)`. `grafana_ro` SELECT grant already present.
- **CLI**: `python -m polytool crypto-pair-run --duration-seconds 86400 --sink-enabled`
- **Reporting CLI**: `python -m polytool crypto-pair-report` (artifact analysis)
- **Grafana dashboard** (`infra/grafana/dashboards/polyttool_crypto_pair_paper_soak.json`):
  12 panels matching the paper-soak runbook. Auto-provisioned at
  `docker compose up -d`. UID: `polytool-crypto-pair-paper-soak`.
  Datasource: `ClickHouse` (UID `clickhouse-polytool`). Default range: `now-7d`.
  Panels: Paper Soak Scorecard, Run Summary Funnel, Maker Fill Rate Floor,
  Partial-Leg Incidence, Active Pairs, Pair Cost Distribution, Estimated Profit
  Per Completed Pair, Net Profit Per Settlement, Cumulative Net PnL, Daily
  Trade Count, Feed State Transition Counts, Recent Feed Safety Events.
- **Paper soak runbook**: `docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md`
- **Rubric spec**: `docs/specs/SPEC-crypto-pair-paper-soak-rubric-v0.md`
- **Feature docs**: `docs/features/FEATURE-crypto-pair-runner-v0.md`,
  `docs/features/FEATURE-crypto-pair-clickhouse-sink-v0.md`,
  `docs/features/FEATURE-crypto-pair-grafana-panels-v0.md` (query pack),
  `docs/features/FEATURE-crypto-pair-grafana-panels-v1.md` (provisioned dashboard)

**Blocker resolved (2026-03-26): Coinbase fallback feed implemented.**

A smoke soak on 2026-03-25 (run ID `603e0ef17ff2`) confirmed the Binance HTTP
451 geo-restriction: `markets_seen=0`, zero opportunities. The Coinbase fallback
feed was implemented 2026-03-26 and resolves this blocker.

- `CoinbaseFeed` streams `BTC-USD`, `ETH-USD`, `SOL-USD` via Coinbase Advanced
  Trade WebSocket (`wss://advanced-trade-api.coinbase.com/ws`).
- `AutoReferenceFeed` wraps both feeds: uses Binance when usable, falls back to
  Coinbase automatically.
- CLI flag: `--reference-feed-provider binance|coinbase|auto` (default: `binance`).
- 55 new offline tests in `tests/test_crypto_pair_reference_feed.py` — all passing.
- No geo-restriction on Coinbase — unblocks the 24h paper soak on this machine.

See dev log `docs/dev_logs/2026-03-26_phase1a_coinbase_feed_fallback.md`.

The next operator action is the 24h paper soak using Coinbase or auto feed:

```powershell
$env:CLICKHOUSE_PASSWORD = "polytool_admin"
python -m polytool crypto-pair-run --duration-seconds 86400 --sink-enabled --reference-feed-provider coinbase
# or auto (tries Binance first, falls back to Coinbase):
python -m polytool crypto-pair-run --duration-seconds 86400 --sink-enabled --reference-feed-provider auto
```

After the run finalizes, open the Grafana dashboard at
`http://localhost:3000/d/polytool-crypto-pair-paper-soak` and apply the
promote / rerun / reject rubric.

---

## Historical checkpoint: 2026-03-05 Track A code complete

Track A code is shipped and tested. Sprint-end validation was 1188 passing
tests with no reported regressions, but Stage 1 live capital remains blocked
until the remaining gates are closed and Stage 0 paper-live completes cleanly.

- `packages/polymarket/simtrader/execution/wallet.py`: new wallet helper that reads `PK`, builds a real `ClobClient`, and supports one-time credential derivation.
- `packages/polymarket/simtrader/execution/live_executor.py`: upgraded executor that routes create/cancel calls to an injected real client when `dry_run=False`.
- `packages/polymarket/simtrader/execution/risk_manager.py`: patched risk layer with `inventory_skew_limit_usd`, fill-price tracking, and net inventory notional checks.
- `packages/polymarket/simtrader/strategies/market_maker_v0.py`: upgraded strategy with Avellaneda-Stoikov quotes, microprice inputs, volatility estimation, and bounded spread guards.
- `packages/polymarket/market_selection/`: new market selection package with scorer, filters, Gamma API client, and `python -m polytool market-scan`.
- `tools/gates/close_replay_gate.py`: Gate 1 replay determinism closure script.
- `tools/gates/close_sweep_gate.py`: Gate 2 scenario sweep closure script.
- `tools/gates/run_dry_run_gate.py`: Gate 4 dry-run live closure script.
- `tools/gates/gate_status.py`: gate status reporter that exits 0 only when all four gate artifacts pass.
- `tools/gates/shadow_gate_checklist.md`: Gate 3 manual operator checklist and artifact contract.
- `tools/cli/simtrader.py`: live CLI upgrade with `--live`, gate checks, wallet loading, USD risk flags, and `simtrader kill`.
- `docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md`: one-page operator runbook for Stage 1 live deployment.

## What exists today

- A local CLI (`polytool`) that drives ingestion and exports.
- A data pipeline that writes to ClickHouse and visualizes in Grafana.
- Private dossier exports with resolution outcomes and PnL enrichment.
- Local RAG indexing + retrieval over private content (`kb/` + `artifacts/`).
- `rag-refresh` command (alias for `rag-index --rebuild`): one-command path to rebuild the full index.
- Evidence bundle generation with standardized prompt templates.
- LLM report retention with automatic LLM_notes for RAG surfacing.
- MCP server integration for Claude Desktop.
- Batch wallet scan with deterministic leaderboard (`wallet-scan`).
- Cross-user segment edge distillation into ranked candidates (`alpha-distill`).
- Offline hypothesis registry + experiment skeleton (`hypothesis-register`, `hypothesis-status`, `experiment-init`, `experiment-run`).
- Offline hypothesis registry + experiment skeleton plus Hypothesis Validation Loop v0 (`hypothesis-register`, `hypothesis-status`, `experiment-init`, `experiment-run`, `hypothesis-validate`, `hypothesis-diff`, `hypothesis-summary`).
- Track A gate harness under `tools/gates/`, with Gate 1 and Gate 4 passed,
  Gate 2 tooling shipped, and Gate 3 blocked behind Gate 2.
- Bounded Gate 2 capture tooling: `scan-gate2-candidates`, `prepare-gate2`,
  presweep eligibility checks, `watch-arb-candidates`, and `--watchlist-file`
  ingest.
- Gated execution surface via `simtrader live` (dry-run default; `--live` exists but is still gate-blocked).
- Grouped CLI help: `python -m polytool --help` now presents commands in 5 categories (Research Loop, Analysis & Evidence, RAG & Knowledge, SimTrader / Execution, Integrations & Utilities).
- SimTrader Studio Dashboard tab includes Grafana deep-link cards (User Trades, PnL, Strategy Detectors, Arb Feasibility, and others); requires `docker compose up -d`.

---

## Validation Pipeline (Canonical)

The canonical operator validation pipeline is:

1. Replay Validation -> Gate 1
2. Sweep Validation -> Gate 2
3. Shadow Validation -> Gate 3
4. Dry Run -> Gate 4
5. Stage 0 -> 72 hour paper-live run
6. Stage 1 -> live trading with capital

Historical note: older planning language may refer to a "30-day shadow
validation." That wording is obsolete. The current process is Gate 3 shadow
validation, then Gate 4 dry-run live, then a separate 72 hour Stage 0
paper-live run before Stage 1 capital is allowed.

---

## Recently completed (Track B foundation + registry + validation loop)

Status (2026-03-12): Track B foundation, hypothesis registry v0, and
Hypothesis Validation Loop v0 are complete. This does not mean Master Roadmap
v4.1 Phase 2 is complete.

### Wallet-Scan v0

A research-only batch scan workflow.

- **CLI**: `python -m polytool wallet-scan --input wallets.txt [--profile lite|full]`
- **Input**: plain-text file with one Polymarket handle (`@name`) or wallet address (`0x...`) per line
- **Output**: `artifacts/research/wallet_scan/<YYYY-MM-DD>/<run_id>/`
  - `wallet_scan_manifest.json` - run metadata
  - `per_user_results.jsonl` - per-entry scan outcome, PnL, CLV coverage, outcome counts
  - `leaderboard.json` - deterministic ranking by net PnL (desc), tiebreak by slug (asc)
  - `leaderboard.md` - human-readable top-20 table
- Failures are isolated per entry; batch continues on error by default.
- Spec: [docs/specs/SPEC-wallet-scan-v0.md](specs/SPEC-wallet-scan-v0.md)
- Feature doc: [docs/features/wallet-scan-v0.md](features/wallet-scan-v0.md)

### Alpha-Distill v0

Cross-user segment edge distillation into ranked hypothesis candidates. No LLM,
no black-box scores.

- **CLI**: `python -m polytool alpha-distill --wallet-scan-run <path> [--min-sample 30] [--fee-adj 0.02]`
- **Input**: a `wallet-scan` run root + each user's `segment_analysis.json`
- **Output**: `alpha_candidates.json` - ranked candidates with persistence metrics, friction flags, `next_test`, `stop_condition`
- Ranking prioritizes **multi-user persistence** (~1000x weight) over count or raw edge.
- Every candidate includes a `stop_condition` to guard against over-fitting.
- Spec: [docs/specs/SPEC-alpha-distill-v0.md](specs/SPEC-alpha-distill-v0.md)
- Feature doc: [docs/features/alpha-distill-v0.md](features/alpha-distill-v0.md)

### RAG reliability improvements

- **Centralized default collection**: all CLI tools (`rag-index`, `rag-query`, `llm-bundle`, `rag-run`) default to `polytool_rag` via a shared `packages/polymarket/rag/defaults.py`; fixes legacy `polyttool_rag` double-t mismatches.
- **`rag-index` progress + file filters**: progress callbacks with file/chunk counters; binary/oversized file skip list; `--max-bytes`, `--progress-every-files`, `--progress-every-chunks` CLI flags; improved `--rebuild` on Windows.
- **`rag-run` CLI**: re-executes stored `rag_queries.json` queries against the current index without rebuilding the bundle; writes results back in place.
- **LLM bundle excerpt de-noising**: prior bundle artifacts (`rag_queries.json`, `bundle.md`, `prompt.txt`) are filtered from RAG results before selection to prevent circular evidence.
- **LLM bundle report stub**: `llm-bundle` now writes a blank `kb/users/<slug>/reports/<date>/<run_id>_report.md` with pre-formatted section headings; operator pastes the LLM's output there.
- **`rag_queries.json` execution status**: every entry carries `execution_status` (`executed`/`not_executed`/`error`) and `execution_reason`; no more silent empty-list behavior.

### Hypothesis Registry v0 + Experiment Skeleton

Offline-only lifecycle tracking for post-`alpha-distill` candidates.

- **CLI**: `python -m polytool hypothesis-register --candidate-file alpha_candidates.json --rank 1 --registry artifacts/research/hypothesis_registry/registry.jsonl`
- **CLI**: `python -m polytool hypothesis-status --id <hypothesis_id> --status testing --reason "manual review" --registry artifacts/research/hypothesis_registry/registry.jsonl`
- **CLI**: `python -m polytool experiment-init --id <hypothesis_id> --registry artifacts/research/hypothesis_registry/registry.jsonl --outdir artifacts/research/experiments/<hypothesis_id>/<experiment_id>`
- **CLI**: `python -m polytool experiment-run --id <hypothesis_id> --registry artifacts/research/hypothesis_registry/registry.jsonl --outdir artifacts/research/experiments/<hypothesis_id>`
- **Registry**: append-only JSONL with deterministic `hypothesis_id` and lifecycle statuses `proposed | testing | validated | rejected | parked`
- **Experiment artifact**: `experiment.json` skeleton with registry snapshot, candidate provenance, and planned execution placeholders
- Spec: [docs/specs/SPEC-hypothesis-registry-v0.md](specs/SPEC-hypothesis-registry-v0.md)
- Feature doc: [docs/features/FEATURE-hypothesis-registry-v0.md](features/FEATURE-hypothesis-registry-v0.md)

---

## Primary research loop (today)

```text
wallets.txt (handles + wallet addresses)
  -> python -m polytool wallet-scan --input wallets.txt
  -> artifacts/research/wallet_scan/<date>/<run_id>/
      leaderboard.json + per_user_results.jsonl

  -> python -m polytool alpha-distill --wallet-scan-run <path>
  -> alpha_candidates.json (ranked edge hypothesis candidates)

  -> python -m polytool hypothesis-register --candidate-file <path>/alpha_candidates.json --rank 1 --registry artifacts/research/hypothesis_registry/registry.jsonl
  -> registry.jsonl append + printed hypothesis_id

  -> python -m polytool experiment-run --id <hypothesis_id> --registry artifacts/research/hypothesis_registry/registry.jsonl --outdir artifacts/research/experiments/<hypothesis_id>
  -> exp-YYYYMMDDTHHMMSSZ/experiment.json skeleton for manual validation
     (use experiment-init for an explicit directory name)

  -> manual review / evidence gathering
     python -m polytool hypothesis-status --id <hypothesis_id> --status testing --reason "manual review"
     python -m polytool llm-bundle -> paste into LLM UI -> python -m polytool llm-save --hypothesis-path hypothesis.json
```

### Optional execution path (gated, Track A)

```text
  -> python -m polytool market-scan --top 5
     (rank active markets before any live-session candidate is chosen)

  -> python -m polytool simtrader run --tape <events.jsonl> --strategy market_maker_v0
     (replay: deterministic strategy evaluation on recorded tape)

  -> python -m polytool simtrader quickrun --sweep quick --strategy market_maker_v0
     (scenario sweeps: friction + latency stress)

  -> python -m polytool simtrader shadow --market <slug> --strategy market_maker_v0
     (shadow: live WS feed, simulated fills, no real orders)

  -> python -m polytool simtrader live --strategy market_maker_v0 --asset-id <TOKEN_ID>
     (dry-run live: default; prints WOULD PLACE lines, no submission)

  -> Stage 0 paper-live
     (72 hour zero-capital soak after all four gates pass)

  -> Stage 1 live capital
     (only after Stage 0 completes cleanly)
```

Validation order is fixed:
`replay -> scenario sweeps -> shadow -> dry-run live -> Stage 0 paper-live -> Stage 1 capital`.
No live capital is allowed before all four gates are complete and Stage 0 is clean.

---

## Known limitations (as of 2026-03-05)

- **Category coverage**: depends on market metadata backfill having run; newly ingested markets may show `"Unknown"`.
- **Liquidity snapshots**: CLV data is only available for markets that had a snapshot taken before resolution; coverage varies by run timing.
- **Multi-window persistence**: `alpha-distill` cross-user aggregation covers a single wallet-scan run; no time-series comparison across multiple scan dates yet.
- **Sequential execution**: `wallet-scan` scans identifiers one at a time (no parallelism).
- **Fee estimates only**: all fee adjustments are quadratic-curve estimates; actual per-trade fees may differ.
- **Track A promotion remains blocked**: Gate 2 still lacks an eligible tape,
  Gate 3 is blocked behind Gate 2, and Stage 0 cannot start until all four
  gates pass.

## Track A execution layer (optional, gated)

Track A code is complete as of 2026-03-05. Gate 2 plumbing is implemented and
working. The Gate 2 path no longer requires ClickHouse bulk import.
DuckDB reads pmxt and Jon-Becker Parquet files directly from `/data/raw/`,
producing Silver-tier reconstructed tapes for the scenario sweep. Silver tapes
are sufficient for Gate 2; Gate 3 requires Gold tapes from live recording.
See `docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md` (Database Architecture).

### Current operator focus (2026-03-21 — Phase 1 benchmark complete)

Gate 2 path uses DuckDB-first approach (v4.2 rule, carried into v5). Gate 1 and Gate 4 remain passed.

**Completed (ClickHouse import — now legacy)**:
- `import-historical` subcommands (validate-layout, show-manifest, import) are
  shipped and operational (Packet 1 + Packet 2); these are off the critical
  path under v4.2.
- pmxt archive: full batch 1 (78,264,878 rows, 2026-03-15) imported to CH.
  Raw Parquet files exist locally and are the primary v4.2 source via DuckDB.
- Jon-Becker dataset: dry-run (68,646 files discovered, 2026-03-15) and sample
  (1,000 rows, 40,454 files, 2026-03-16) complete. Full ClickHouse import is
  not required; DuckDB reads the Parquet files directly.

**Pending (v5 primary path)**:
- Docker / ClickHouse availability for the next live closure rerun: Docker
  Desktop itself was verified healthy on 2026-03-18/2026-03-19 when checked
  outside the Codex sandbox as `desktop-6l73imi\\patel` (`docker version`,
  `docker info`, `wsl --status`, and `wsl -l -v` all succeeded, with
  `docker-desktop` running under WSL2). The earlier access-denied failures were
  limited to the Codex sandbox account
  (`desktop-6l73imi\\codexsandboxoffline`), which cannot access Docker named
  pipes or WSL enumeration. `docker compose ps` now succeeds but shows no
  running compose services, so the operator still needs `docker compose up -d`
  before the next Silver rerun.
- price_2min population: the priority-1 export succeeded on 2026-03-17
  (`149626` rows inserted for `38` unique tokens). This was only 38 of ~118
  unique tokens across all 120 gap-fill targets. The prefetch scope bug
  (2026-03-20 fix) means the next orchestrator run will fetch `price_2min`
  for all ~118 unique token IDs, eliminating the `price_2min_missing=80`
  outcome seen in the 2026-03-20 full run. The original Silver input blockers
  were fixed on 2026-03-18; the next live verification is pending compose
  startup and rerun from a real-user shell.
- Silver tape validation with real DuckDB data (infrastructure complete: `reconstruct-silver`,
  `batch-reconstruct-silver`, `tape_metadata` CH table)
- **Benchmark_v1 inventory: CLOSED as of 2026-03-21.** All five bucket
  quotas satisfied (`politics=10, sports=15, crypto=10, near_resolution=10,
  new_market=5`). `config/benchmark_v1.tape_manifest`,
  `config/benchmark_v1.lock.json`, and `config/benchmark_v1.audit.json`
  exist and are validated. Phase 1 is complete.
  **Inventory-root nuance**: closure required explicit `--root` flags —
  default `benchmark-manifest` roots do not include
  `artifacts/tapes/new_market`. The finalization command was:
  `python -m polytool benchmark-manifest --root artifacts/simtrader/tapes --root artifacts/silver --root artifacts/tapes/new_market`.
  Future benchmark refreshes must include all three roots.
- Gate 2 scenario sweep: `benchmark_v1.tape_manifest` now exists (50 tapes,
  5 buckets). Running the scenario sweep against this manifest is the Phase 2
  starting point.

**Not in scope for current work**:
- Opportunity Radar: deferred until after first clean Gate 2 → Gate 3 progression
- Live dislocation capture remains a fallback path only; no qualifying tapes
  produced from prior live watcher runs

### Phase 2 starting point

Phase 1 benchmark closure is complete. The next chat should start Phase 2
with Gate 2 scenario sweep:

1. Run `python tools/gates/close_sweep_gate.py` (or equivalent sweep CLI)
   against `config/benchmark_v1.tape_manifest`.
2. Gate 2 passes when ≥ 70% of tapes show positive net PnL under realistic
   fill and fee assumptions.
3. Gate 3 (shadow) unlocks after Gate 2 passes.

Do not reopen Phase 1 tasks. The manifest, lock, and audit artifacts are
finalized. If the benchmark ever needs refreshing, use all three
`--root` flags: `artifacts/simtrader/tapes`, `artifacts/silver`, and
`artifacts/tapes/new_market`.

### Current shipped surfaces

- `wallet.py` now exists under `packages/polymarket/simtrader/execution/` and enables real CLOB client injection through `LiveExecutor`.
- `market_maker_v0.py` now uses an Avellaneda-Stoikov quoting model with microprice, rolling variance, resolution guard, and spread/quote clamps.
- `packages/polymarket/market_selection/` now provides the market scoring, filters, and Gamma API client used by `python -m polytool market-scan`.
- `tools/gates/` now holds the replay, sweep, shadow, and dry-run gate harness;
  Gate 1 and Gate 4 are currently PASSED.
- `tools/cli/scan_gate2_candidates.py`, `tools/cli/prepare_gate2.py`, and
  `tools/cli/watch_arb_candidates.py` provide the current Gate 2 scouting,
  capture, and bounded watch loop.
- `tools/cli/simtrader.py` now exposes `simtrader live --live`, loads wallet credentials, enforces all gate artifacts, requires `CONFIRM`, and includes `simtrader kill`.

### Gate status (2026-03-16)

- Gate 1 (Replay Determinism): **PASSED** - artifact at
  `artifacts/gates/replay_gate/gate_passed.json`.
- Gate 2 (Scenario Sweep >=70%): **NOT PASSED**.
  - Tooling is implemented and working: `scan-gate2-candidates`,
    `prepare-gate2`, presweep eligibility checks, `watch-arb-candidates`, and
    `--watchlist-file` ingest.
  - Under v4.2: pmxt and Jon-Becker raw Parquet files exist locally; DuckDB
    reads them directly (no further ClickHouse import required).
  - price_2min for the priority-1 benchmark tokens was fetched successfully on
    2026-03-17 (`149626` rows inserted for `38` unique token IDs from the
    39-line export; one token is duplicated). The Windows stdout encoding bug
    is fixed, and the Silver input compatibility bugs in
    `silver_reconstructor.py` were fixed on 2026-03-18.
  - Latest Docker diagnostic (2026-03-18/2026-03-19) established that the
    apparent Docker failure was account-scoped. Inside the Codex sandbox
    account, `docker version`, `docker info`, `docker compose ps`,
    `wsl --status`, and `wsl -l -v` fail with access denied. Outside the
    sandbox as `desktop-6l73imi\\patel`, those same checks succeed, with
    Docker Desktop healthy and `docker-desktop` running under WSL2.
    `docker compose ps` currently shows no services running. 
  `config/benchmark_v1.tape_manifest` now exists. The earlier 2026-03-21
  new-market blockers were all execution-path issues, not lack of usable tape
  inventory: (1) `MarketPicker` constructor wiring was fixed, (2) dry-run flag
  mismatch was corrected, and (3) the hanging live process was stopped during
  finalization check. The decisive issue was manifest discovery scope:
  default `benchmark-manifest` roots excluded `artifacts/tapes/new_market`, so
  the newly recorded Gold tapes were invisible until the finalization check
  reran `benchmark-manifest` with `--root artifacts/tapes/new_market` added.
  That explicit-root run created and validated `benchmark_v1`.
- Gate 3 (Shadow Mode): Blocked behind Gate 2.
- Gate 4 (Dry-Run Live): **PASSED** - artifact at
  `artifacts/gates/dry_run_gate/gate_passed.json`.

### Historical gate status snapshot (2026-03-06)

Archive note: this snapshot is retained for history only. Use the 2026-03-16
gate status block above for current operator guidance.

- Gate 1 (Replay Determinism): **PASSED** - artifact at `artifacts/gates/replay_gate/gate_passed.json`.
- Gate 2 (Scenario Sweep >=70%): In progress — tooling complete; needs a live tape with `executable_ticks > 0`.
  - `scan-gate2-candidates`: ranks live markets by Gate 2 executability.
  - `prepare-gate2`: scan -> record -> check eligibility orchestrator (30 tests, all passing).
  - `sweeps/eligibility.py`: pre-sweep fast-fail guard (29 tests, all passing).
- Gate 3 (Shadow Mode): Blocked — waiting on Gate 2 clean progression.
- Gate 4 (Dry-Run Live): **PASSED** - artifact at `artifacts/gates/dry_run_gate/gate_passed.json`.

### Safety defaults

- **Dry-run default**: `simtrader live` never submits orders unless `--live` is passed.
- **Kill switch checked always**: checked before every place/cancel action even in dry-run mode.
- **No market orders**: limit orders only.
- **USD risk caps**: order, position, daily-loss, and inventory skew limits are enforced by `RiskManager`.
- **Spec**: [docs/specs/SPEC-0011-live-execution-layer.md](specs/SPEC-0011-live-execution-layer.md)
- **Feature doc**: [docs/features/FEATURE-trackA-live-clob-wiring.md](features/FEATURE-trackA-live-clob-wiring.md)

## SimTrader (replay-first + shadow mode)

SimTrader is a realism-first simulated trader for Polymarket CLOB markets. It
records the Market Channel WS into deterministic tapes and supports both offline
replay and live simulated shadow runs.

What exists today:
- One-shot runner: `simtrader quickrun` (auto market pick/validate -> record -> run or sweep)
- Scenario sweeps (`--sweep quick` / `quick_small`) and batch leaderboard (`simtrader batch`)
- Shadow mode: `simtrader shadow` (live WS -> strategy -> BrokerSim fills; optional tape recording)
- Activeness probe: `--activeness-probe-seconds` / `--require-active` on `quickrun` measures live WS update rate before committing to a market
- Artifact management: `simtrader clean` (safe dry-run deletion of artifact folders) and `simtrader diff` (side-by-side comparison of two run directories, writes `diff_summary.json`)
- Local UI: `simtrader report` generates self-contained `report.html` for run/sweep/batch/shadow artifacts; `simtrader browse --open` opens newest results
- Explainability: `strategy_debug.rejection_counts`, sweep/batch aggregates, and audited JSONL artifacts

Start here:
- `docs/README_SIMTRADER.md`
- `docs/specs/SPEC-0010-simtrader-vision-and-roadmap.md`

---

## Pipeline (text)

```text
scan -> canonical workflow entrypoint:
  -> ClickHouse + Grafana refresh
  -> trust artifacts in artifacts/dossiers/.../coverage_reconciliation_report.* + run_manifest.json

Individual steps:
  export-dossier -> artifacts/dossiers/.../memo.md + dossier.json + manifest.json
  export-clickhouse -> kb/users/<slug>/exports/<YYYY-MM-DD>/
  llm-bundle -> kb/users/<slug>/llm_bundles/<YYYY-MM-DD>/<run_id>/bundle.md + prompt.txt
  llm-save -> kb/users/<slug>/llm_reports/ + kb/users/<slug>/notes/LLM_notes/
  rag-index -> kb/rag/*
  rag-query -> evidence snippets
  market-scan -> ranked active market candidates
  simtrader -> replay, sweeps, shadow, and gated live execution
  cache-source -> kb/sources/
  examine -> legacy orchestrator wrapper (non-canonical)
  mcp -> Claude Desktop integration
```

## CLI commands (plain language)

- `scan`: run a one-shot ingestion via the local API to pull user data into ClickHouse (with optional activity, positions, and PnL flags), and emit trust artifacts (`coverage_reconciliation_report.*`, `run_manifest.json`) per run.
- `examine`: legacy orchestrator (scan -> dossier -> bundle -> prompt) kept for compatibility and golden-case operations.
- `export-dossier`: build a private, point-in-time evidence package for one user (memo + JSON + manifest) under `artifacts/`. Now includes resolution outcomes and position lifecycle data.
- `export-clickhouse`: export recent ClickHouse datasets for one user into the private KB under `kb/users/<slug>/exports/<YYYY-MM-DD>/`.
- `rag-refresh`: one-command alias for `rag-index --rebuild`. Use this after any scan, wallet-scan, or llm-save to make new content immediately searchable.
- `rag-index`: build or rebuild the local RAG index over `kb/` + `artifacts/`. Outputs live in `kb/rag/`. Use `rag-refresh` for the simple path; `rag-index` for incremental or advanced options.
- `rag-query`: retrieve relevant evidence snippets from the local index with optional scoping by user, doc type, or date.
- `rag-eval`: run retrieval quality checks and write reports to `kb/rag/eval/reports/<timestamp>/`.
- `llm-bundle`: assemble a short evidence bundle from dossier data and curated RAG excerpts into `bundle.md` for offline reporting.
- `llm-save`: store LLM report runs (report + manifest) into `llm_reports/` and write a summary note to `notes/LLM_notes/` for RAG surfacing.
- `market-scan`: score and filter active markets for operator review before any Track A live candidate is chosen.
- `scan-gate2-candidates`: rank live markets (or local tapes) by Gate 2 binary_complement_arb executability (depth + complement edge).
- `prepare-gate2`: Gate 2 prep orchestrator — scan candidates, record tapes, check eligibility, print verdict in one command.
- `watch-arb-candidates`: run a bounded live dislocation watch and auto-record
  near-edge tapes from `--markets` or `--watchlist-file`.
- `simtrader`: replay, sweep, shadow, dry-run live, and gated `--live` execution surfaces.
- `cache-source`: cache trusted web sources for RAG indexing (allowlist enforced).
- `mcp`: start the MCP server for Claude Desktop integration.

## User identity routing

User identity is resolved canonically via `polytool/user_context.py`:

- **Handle-first (strict)**: `--user "@DrPufferfish"` always routes to `drpufferfish/` folders
- **Strict mapping**: in `--user` mode, wallet must resolve; no fallback to `unknown/` or wallet-prefix slugs
- **Wallet-to-slug mapping**: when wallet is known with a handle, the mapping is persisted to `kb/users/<slug>/profile.json`
- **Wallet mode**: wallet-first flows can use `--wallet`; when no mapping exists, fallback is `wallet_<first8>`
- **Consistent paths**: all CLI commands and MCP tools use the same resolver

This ensures outputs like dossiers, bundles, and reports always land in the
same user folder for handle-first workflows.

## Resolution outcomes

Each position now includes a `resolution_outcome` field:
- `WIN` / `LOSS`: held to resolution
- `PROFIT_EXIT` / `LOSS_EXIT`: exited before resolution
- `PENDING`: market not yet resolved
- `UNKNOWN_RESOLUTION`: resolution data unavailable

## Common pitfalls

- **User scoping**: quote `--user "@name"` in PowerShell and keep user vs wallet inputs consistent across commands.
- **Private-only defaults**: `rag-query` searches private content by default; public docs are excluded unless `--public-only` is set.
- **Model downloads/caching**: the first vector or rerank run downloads models into `kb/rag/models/`.
- **FTS5 availability**: lexical or hybrid search requires SQLite with FTS5; if missing, use vector-only retrieval.
- **Index freshness**: after adding dossiers or LLM reports, rerun `rag-index` so the new files are searchable.
- **CLI**: use `python -m polytool` for canonical docs and scripts.

## Developer Notes

- **Canonical commands**: always use `python -m polytool <command>` in docs, scripts, and runbooks. The `polytool` console script also works.
- **Manual workflow is default**: the manual examination workflow (scan -> export/bundle -> paste -> llm-save) is the primary path. See `docs/RUNBOOK_MANUAL_EXAMINE.md`.
- **MCP is optional**: the MCP server (`python -m polytool mcp`) provides Claude Desktop integration but is not required for the core workflow. It is tracked separately in the roadmap.
- **double-t shim removed**: the old `polyttool` backward-compatibility shim has been removed. See [ADR-0001](adr/ADR-0001-cli-and-module-rename.md).
