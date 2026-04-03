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

## Status as of 2026-03-29 (Phase 1B — Gate 2 FAILED, 7/50 positive at 14%)

Track A / SimTrader plumbing is implemented. Phase 1B Gate 2 has been run
against the full 50-tape recovery corpus and FAILED. The corpus is complete
(50/50 tapes qualify). The gate failure is a strategy profitability issue
on low-frequency tapes, not a corpus gap. The repo's current execution status is:

- Gate 1: PASSED
- Gate 2: **FAILED** (2026-03-29) — 7/50 positive tapes (14%), gate threshold is 70%.
  Corpus is complete (50/50): politics=10, sports=15, crypto=10, near_resolution=10,
  new_market=5. Gate artifact: `artifacts/gates/mm_sweep_gate/gate_failed.json`.
  Recovery corpus manifest: `config/recovery_corpus_v1.tape_manifest` (50 entries).
  Sweep driver: `tools/gates/run_recovery_corpus_sweep.py`.
  **Root cause:** silver tapes (10) produce zero fills — no tick density for MM orders.
  Non-crypto shadow tapes (30) produce mostly negative or zero PnL on low-frequency
  politics/sports markets. Crypto 5m shadow tapes (10) are 7/10 positive.
  **Crypto-positive tapes:** btc-updown (4/5 positive), eth-updown (2/2 positive),
  sol-updown (1/3 positive). PnL range: +$4.67 to +$297.25.
  **Path forward options (documented in dev log):**
  (1) Crypto-only corpus subset test: run sweep on 10 crypto tapes only (7/10 = 70%,
  would pass threshold but requires spec change); (2) Strategy improvement for
  low-frequency markets; (3) Focus on Track 2 (crypto pair bot) while Gate 2 research
  continues in background. Authoritative dev log:
  `docs/dev_logs/2026-03-29_crypto_watch_and_capture.md`.
  **Path drift fix (quick-045):** Shadow tapes migrated from `artifacts/simtrader/tapes/`
  to `artifacts/tapes/shadow/` canonical path. `config/recovery_corpus_v1.tape_manifest`
  written with all 50 qualifying paths.
- **Artifacts directory restructure** (quick-036, 2026-03-28): All tapes unified under
  `artifacts/tapes/{gold,silver,shadow,crypto}/` hierarchy. 18 Python path constants
  updated. Canonical layout documented in CLAUDE.md. See dev log
  `docs/dev_logs/2026-03-28_artifacts_restructure.md`.
- **Market Selection Engine** (quick-037, 2026-03-28): Seven-factor scorer
  (category_edge, spread_opportunity, volume, competition, reward_apr, adverse_selection,
  time_gaussian) with NegRisk penalty and longshot bonus. CLI:
  `python -m polytool market-scan`. Artifacts written to `artifacts/market_selection/`.
  2728 tests passing. See dev log `docs/dev_logs/2026-03-28_market_selection_engine.md`.

- **Live execution wiring** (quick-040, 2026-03-28): `PolymarketClobOrderClient` via
  py-clob-client 0.34.6 with deferred import; `_log_trade_event()` JSONL logging per
  place/cancel; `Dockerfile.bot` + docker-compose `pair-bot-paper`/`pair-bot-live`
  services under isolated profiles; 6 new offline tests; 2734 passing.
  See dev log `docs/dev_logs/2026-03-28_crypto_pair_live_docker.md`.

**Next executable step**: Gate 2 FAILED (7/50 = 14%, need 70%). Three path-forward
options are documented in `docs/dev_logs/2026-03-29_crypto_watch_and_capture.md`:

1. **Crypto-only corpus subset** — Re-run sweep on 10 crypto 5m tapes only (7/10 = 70%).
   Passes the threshold but requires a spec change to redefine Gate 2 scope. Requires
   operator authorization (spec change = architectural decision).
2. **Strategy improvement** — Improve market_maker_v1 profitability on low-frequency
   politics/sports tapes. Research path; timeline uncertain.
3. **Track 2 focus** — Run crypto pair bot (Track 2) independently while Gate 2
   research continues. Track 2 does NOT wait for Gate 2 (CLAUDE.md rule: standalone).

Re-run sweep command (after any corpus/strategy change):
```
python tools/gates/run_recovery_corpus_sweep.py \
  --manifest config/recovery_corpus_v1.tape_manifest \
  --out artifacts/gates/mm_sweep_gate \
  --threshold 0.70
```

**Escalation deadline:** ADR-benchmark-versioning-and-crypto-unavailability.md escalation
criteria for benchmark_v2 remains at 2026-04-12. No AI agent should autonomously trigger
benchmark_v2. Do NOT modify config/benchmark_v1.* files under any circumstance.

- Gate 3: **BLOCKED** — Gate 2 must PASS first
- Gate 4: PASSED
- **Tape integrity audit** (quick-050, 2026-03-29): All 4 tape roots scanned
  (314 tapes: gold=8, silver=118, shadow=181, crypto_new=7). Verdict: **SAFE_TO_USE**.
  Zero YES/NO token-ID mapping bugs, zero quote-stream duplicates, zero structural
  corruption. Details: `artifacts/debug/tape_integrity_audit_report.md`.
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

**Strategy pivot history:** Original pair-cost accumulation thesis (quick-019)
was replaced by per-leg target_bid gate in quick-046, then fully rebuilt as
directional momentum strategy (quick-049) based on gabagool22 wallet analysis
(quick-048). The accumulation_engine.py module now implements MomentumConfig and
evaluate_directional_entry() rather than a pair-cost ceiling check.

- **Accumulation engine** (`packages/polymarket/crypto_pairs/accumulation_engine.py`):
  Originally: YES + NO pair accumulation below pair-cost ceiling (pre-quick-046
  behavior, now superseded). Current strategy: directional momentum entries via
  evaluate_directional_entry() (quick-049). Favorite leg fills at ask <=
  max_favorite_entry (0.75); hedge leg fills only if ask <= max_hedge_price (0.20).
  Momentum trigger: 0.3% price move in 30s Coinbase reference window.
  Kill switch, daily loss cap, max open pairs, max unpaired exposure window remain.
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

**Track 2 paper soak: BLOCKED — awaiting active markets and full soak**
(status as of 2026-03-29, updated quick-053).

Quick-047 audit declared the pre-quick-049 strategy ready for paper soak.
That status is superseded by the quick-049 pivot to directional momentum. The 10-min paper soak run in quick-049 returned 0
intents because no active BTC/ETH/SOL 5m/15m markets exist on Polymarket as of
2026-03-29 and static market prices did not clear the 0.3% momentum threshold.
A full 24h soak with real momentum signals has not been run and the rubric has
not been applied.

BTC/ETH/SOL 5m markets were briefly confirmed active 2026-03-29 during Gate 2
capture (quick-045); use `python -m polytool crypto-pair-watch --one-shot` to
verify current availability before any run.

Coinbase feed confirmed working (quick-023/026). Binance is geo-restricted per
quick-022; use `--reference-feed-provider coinbase` for this machine.

**Live deployment blockers (as of 2026-03-29):**
1. No active BTC/ETH/SOL 5m/15m markets on Polymarket. Use
   `python -m polytool crypto-pair-watch --one-shot` to check.
2. No full paper soak with real momentum signals. Must complete a 24h soak
   on a live market and pass the promote rubric
   (`docs/specs/SPEC-crypto-pair-paper-soak-rubric-v0.md`) before considering live.
3. Oracle mismatch concern: Polymarket's bracket resolution uses the Chainlink
   oracle (on-chain), while the reference feed uses Coinbase WebSocket prices.
   Divergence between the two sources on short 5m brackets has not been measured
   or validated.
4. Deployment environment: home internet latency assumptions from earlier
   development are not confirmed adequate for maker-fill timing. EU VPS is
   the likely deployment target; infra not yet set up.
5. In-memory cooldown: `_entered_brackets` resets on runner restart.
   Acceptable for paper mode; must be reviewed before live capital.

(Command valid once blockers above are cleared.)

Definitive 24h paper soak launch command:

```powershell
$env:CLICKHOUSE_PASSWORD = "polytool_admin"
python -m polytool crypto-pair-run `
  --duration-hours 24 `
  --cycle-interval-seconds 30 `
  --reference-feed-provider coinbase `
  --heartbeat-minutes 30 `
  --auto-report `
  --sink-enabled
```

Artifacts land in `artifacts/tapes/crypto/paper_runs/`. Runbook:
`docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md`. After the run finalizes,
open the Grafana dashboard at `http://localhost:3000/d/polytool-crypto-pair-paper-soak`
and apply the promote / rerun / reject rubric from
`docs/specs/SPEC-crypto-pair-paper-soak-rubric-v0.md`.

Previous blocker records: Binance HTTP 451 geo-restriction unblocked via
Coinbase fallback feed (quick-026, dev log
`docs/dev_logs/2026-03-26_phase1a_coinbase_feed_fallback.md`).

---


---

> **Historical details** (pre-Phase-1 implementation records) moved to `docs/archive/CURRENT_STATE_HISTORY.md`.

## RIS v1 Data Foundation (quick-055, 2026-04-01)

Lightweight SQLite persistence layer for `external_knowledge` RAG partition shipped.
Modules: `packages/polymarket/rag/knowledge_store.py`, `packages/polymarket/rag/freshness.py`.
Config: `config/freshness_decay.json`. Tests: `tests/test_knowledge_store.py`.

**Authority conflict (unresolved):** Roadmap v5.1 LLM Policy allows Tier 1 free
cloud APIs (DeepSeek V3/R1, Gemini 2.5 Flash). PLAN_OF_RECORD Section 0 states
"Current toolchain policy remains no external LLM API calls." The knowledge store
includes a provider abstraction (`_llm_provider`) but cloud execution is disabled
by default. Operator decision required before enabling cloud LLM calls for claim
extraction or scraper evaluation.

This is a data-plane addition. It does not change live trading, SimTrader, gates,
or benchmark artifacts.

## RIS Phase 2 — Corpus Seeding and Extractor Benchmark (quick-260401-nzz, 2026-04-01)

Manifest-driven batch seeder and extractor benchmark harness added to the RIS v1 pipeline.

**New modules:**
- `packages/research/ingestion/seed.py` — `SeedEntry`, `SeedManifest`, `SeedResult`,
  `load_seed_manifest()`, `run_seed()`. Seeds knowledge store from JSON manifest with stable
  deterministic IDs and authoritative `source_family` tagging.
- `packages/research/ingestion/benchmark.py` — `ExtractorMetric`, `BenchmarkResult`,
  `run_extractor_benchmark()`. Compares extractor outputs on a fixture set, writes
  `benchmark_results.json` artifact.

**Extended modules:**
- `packages/research/ingestion/extractors.py` — added `MarkdownExtractor` (delegates to
  PlainTextExtractor), `StubPDFExtractor` (raises NotImplementedError; docling/marker/pymupdf4llm),
  `StubDocxExtractor` (raises NotImplementedError; python-docx), `EXTRACTOR_REGISTRY`,
  `get_extractor()` factory.
- `packages/research/ingestion/__init__.py` — exports all new symbols.

**New CLIs:**
- `python -m polytool research-seed --manifest config/seed_manifest.json --db :memory: --no-eval`
- `python -m polytool research-benchmark --fixtures-dir tests/fixtures/ris_seed_corpus --extractors plain_text,markdown --json`

**Seed manifest:** `config/seed_manifest.json` — 11 entries (8 RAGfiles + 3 roadmap docs),
all `source_family="book_foundational"` (null half-life). Smoke test confirmed 11/11 ingested.

**Tests:** 52 new tests (18 seed + 34 extractor/benchmark). 3012 total passing, 0 failed.

**Fixture:** `tests/fixtures/ris_seed_corpus/sample_structured.pdf.txt` (prediction market fee
structures reference text for benchmark determinism).

**Not changed:** live execution, SimTrader, OMS, risk manager, ClickHouse schema, gate files,
benchmark manifests. PDF/DOCX extraction remains stubbed — no external lib added.

See `docs/features/FEATURE-ris-v2-seed-and-benchmark.md` and
`docs/dev_logs/2026-04-01_ris_phase2_seed_and_extractor_benchmark.md`.

## RIS Phase 2 — Operator Feedback Loop and Richer Query Integration (260401-o1q, 2026-04-01)

Lifecycle event recording, enriched knowledge store queries, and CLI subcommands added.

**Ledger schema v2** (`packages/research/synthesis/precheck_ledger.py`):
- Schema bumped to `precheck_ledger_v2`. Old v0/v1 entries remain readable.
- `append_override(precheck_id, override_reason, ledger_path)` — records `event_type="override"`
- `append_outcome(precheck_id, outcome_label, outcome_date, ledger_path)` — records `event_type="outcome"`, labels: `successful/failed/partial/not_tried`
- `get_precheck_history(precheck_id, ledger_path)` — all events for a precheck ID sorted ascending
- `list_prechecks_by_window(start_iso, end_iso, ledger_path)` — events within a time window

**PrecheckResult lifecycle fields** (`packages/research/synthesis/precheck.py`):
- Added `was_overridden`, `override_reason`, `outcome_label`, `outcome_date` with defaults.
- Not populated by `run_precheck()` — for downstream hydration from ledger history.

**Enriched query output** (`packages/research/ingestion/retriever.py`):
- `query_knowledge_store_enriched()` — returns claims augmented with `provenance_docs`,
  `contradiction_summary`, `is_contradicted`, `staleness_note`, `lifecycle`
- `format_enriched_report()` — structured multi-line report string per claim

**CLI subcommands** (`tools/cli/research_precheck.py`):
- Refactored to argparse subparsers: `run` (backward compat), `override`, `outcome`, `history`, `inspect`
- Backward compat: `research-precheck --idea "..."` (no subcommand) still works

CLI usage examples:
```
python -m polytool research-precheck --idea "test"  # backward compat
python -m polytool research-precheck run --idea "test" --no-ledger
python -m polytool research-precheck override --precheck-id abc123 --reason "changed approach"
python -m polytool research-precheck outcome --precheck-id abc123 --label successful
python -m polytool research-precheck history --precheck-id abc123 --json
python -m polytool research-precheck inspect --top-k 5
```

Tests: 26 new offline tests in `tests/test_ris_phase2_operator_loop.py`. 3012 total passing.

## RIS Phase 2 — Query Spine Wiring (quick-260402-ivb, 2026-04-02)

KnowledgeStore is now wired into the canonical `rag-query --hybrid` retrieval path as a
third RRF source alongside Chroma vector search and FTS5 lexical search. This closes the
"Chroma wiring" gap that was deferred in the RIS v1 data foundation plan.

**Architecture:** Three-way `reciprocal_rank_fusion_multi()` merges ranked results from:
1. Chroma vector search (`top_k_vector`, default 25 candidates)
2. SQLite FTS5 lexical search (`top_k_lexical`, default 25 candidates)
3. KnowledgeStore claims (`top_k_knowledge`, default 25 candidates)

KS claims are pre-filtered by case-insensitive substring match on the query text before
entering RRF. Claims with `freshness_modifier < min_freshness` are excluded. Contradicted
claims carry a 0.5x `effective_score` penalty and rank lower in fusion.

**New CLI flags on `rag-query`:**
- `--knowledge-store PATH` — activate KS as third source; `default` resolves to `kb/rag/knowledge/knowledge.sqlite3`
- `--source-family NAME` — filter KS claims by source family (e.g. `book_foundational`)
- `--min-freshness FLOAT` — exclude KS claims below freshness threshold [0,1]
- `--evidence-mode` — promote provenance/contradiction annotations to top-level keys in output
- `--top-k-knowledge N` — KS candidate count for RRF (default 25)

**Canonical query path:**
```
python -m polytool rag-query --question "..." --hybrid --knowledge-store default --evidence-mode
```

**Evidence-mode fields** promoted to top-level for KS-sourced results:
`provenance_docs`, `contradiction_summary`, `staleness_note`, `lifecycle`, `is_contradicted`

Files changed: `packages/polymarket/rag/lexical.py` (added `reciprocal_rank_fusion_multi`),
`packages/polymarket/rag/query.py` (KS params + three-way fusion path),
`packages/research/ingestion/retriever.py` (added `query_knowledge_store_for_rrf`),
`tools/cli/rag_query.py` (5 new flags + evidence-mode logic).

Tests: 25 new offline tests in `tests/test_ris_query_spine.py`. 3037 total passing.

## RIS Phase 3 — Real Extractor Integration and Corpus Backfill (quick-260402-m6p, 2026-04-02)

Stub extractors replaced with real implementations; structure-aware Markdown extractor
added; benchmark harness enhanced with quality proxy metrics; reseed workflow wired.

**StructuredMarkdownExtractor** (key: `"structured_markdown"`) is the primary extractor
for the `docs/reference/` corpus. It parses heading structure, tables, and fenced code
blocks and stores the counts in `ExtractedDocument.metadata`:

| Metadata key      | What it captures                                            |
|-------------------|-------------------------------------------------------------|
| `sections`        | List of heading text strings (H1-H6)                        |
| `section_count`   | Total heading count                                         |
| `header_count`    | Same as section_count                                       |
| `table_count`     | Pipe-delimited table blocks detected                        |
| `code_block_count`| Fenced code block pairs (``` or ~~~)                        |

Body text is returned unchanged — Markdown is preserved, not stripped.

**PDFExtractor** (key: `"pdf"`) and **DocxExtractor** (key: `"docx"`) are real
implementations using optional deps `pdfplumber` and `python-docx`. Both raise
`ImportError` with `pip install` instructions at call-time when the dep is absent.
No PDF or DOCX files exist in the corpus yet; extractors are wired for when they arrive.

**StubPDFExtractor** and **StubDocxExtractor** are retained for backward compatibility
but are no longer registered in `EXTRACTOR_REGISTRY`.

**Seed manifest v3** (`config/seed_manifest.json`): all 11 entries have
`"extractor": "structured_markdown"`. Auto-detect for `.md` files also resolves to
`"structured_markdown"` by default.

**Reseed CLI flag**: `python -m polytool research-seed --reseed` deletes existing
docs by `source_url` before re-ingesting, allowing re-extraction with improved
extractors without creating duplicates. Without `--reseed`, the seeder is idempotent
(INSERT OR IGNORE semantics).

**Benchmark quality proxy delta on real corpus** (8 files in `docs/reference/RAGfiles/`):

| Extractor             | avg_section_count | avg_header_count | total_table_count |
|-----------------------|-------------------|------------------|-------------------|
| `plain_text`          | 0.0               | 0.0              | 0                 |
| `structured_markdown` | 28.5              | 28.5             | 23                |

Files changed: `packages/research/ingestion/extractors.py`,
`packages/research/ingestion/benchmark.py`, `packages/research/ingestion/seed.py`,
`packages/research/ingestion/__init__.py`, `config/seed_manifest.json`,
`tools/cli/research_seed.py`.

Tests: 42 new offline tests in `tests/test_ris_real_extractors.py`. 3110 total passing.
Feature doc: `docs/features/FEATURE-ris-v3-real-extractors.md`.
Dev log: `docs/dev_logs/2026-04-02_ris_phase3_real_extractor_and_backfill.md`.

## RIS Phase 3 — Evaluation Gate Hardening (quick-260402-m6t, 2026-04-02)

Deterministic pre-scoring layer added to the RIS evaluation gate. The pipeline is now:
`hard_stops -> near_duplicate_check -> feature_extraction -> LLM_scoring -> artifact_persistence`.
LLM scoring is still the primary quality signal; Phase 3 adds local-first guardrails and
observability on top — without replacing or weakening it.

**Feature extraction** (`packages/research/evaluation/feature_extraction.py`): per-family
deterministic extractors using pure regex/text (no network). Families and key features:
- `academic`: `has_doi`, `has_arxiv_id`, `has_ssrn_id`, `methodology_cues` count, `has_known_author`, `has_publish_date`
- `github`: `stars`, `forks`, `has_readme_mention`, `has_license_mention`, `commit_recency`
- `blog`/`news`: `has_byline`, `has_date`, `heading_count`, `paragraph_count`, `has_blockquote`
- `forum_social`: `has_screenshot`, `has_data_mention`, `reply_count`, `specificity_markers`
- `manual`/default: `body_length`, `word_count`, `has_url`

**Near-duplicate detection** (`packages/research/evaluation/dedup.py`): two-pass — SHA256
of normalized body for exact matches, then word 5-gram Jaccard similarity (threshold 0.85)
for near-duplicates. Near-duplicates rejected before LLM scoring (no API tokens consumed).

**Eval artifact persistence** (`packages/research/evaluation/artifacts.py`): opt-in JSONL
artifact writer (`DocumentEvaluator(artifacts_dir=Path(...))`). One record per eval:
gate, hard_stop_result, near_duplicate_result, family_features, scores, source metadata.
CLI flag: `python -m polytool research-eval --artifacts-dir PATH --json`

**Enhanced calibration analytics** (`packages/research/synthesis/calibration.py`):
`compute_eval_artifact_summary()` returns gate_distribution, hard_stop_distribution,
family_gate_distribution, dedup_stats, avg_features_by_family.
`format_calibration_report()` gains "Hard-Stop Causes" and "Family Gate Distribution" sections.

**SOURCE_FAMILY_OFFSETS hook** (`packages/research/evaluation/types.py`): empty dict;
the designated future extension point for data-driven per-family credibility adjustments.
Do not populate until >= 50 eval artifacts span >= 3 source families.

Fully backward compatible: without new constructor params, evaluator behavior is identical
to Phase 2.

Tests: 47 new offline tests in `tests/test_ris_phase3_features.py`. 3111 total passing,
4 pre-existing failures (require gitignored local dossier artifact files — unrelated to
Phase 3 changes).

See `docs/features/FEATURE-ris-phase3-gate-hardening.md` and
`docs/dev_logs/2026-04-02_ris_phase3_gate_hardening.md`.

## RIS Phase 4 — External Source Acquisition (quick-260402-ogu, 2026-04-02)

Raw-source caching, adapter boundaries for three source families (academic/preprint,
GitHub/repo, blog/news/article), metadata normalization with canonical IDs, and a
CLI/callable path wiring fixture-backed external sources through the full adapter ->
cache -> normalize -> eval -> store pipeline.

**Core modules:**
- `packages/research/ingestion/source_cache.py` — RawSourceCache with deterministic
  SHA-256 source IDs; envelope format `{source_id, source_family, cached_at, payload}`;
  disk layout `{cache_dir}/{family}/{source_id}.json`
- `packages/research/ingestion/normalize.py` — NormalizedMetadata dataclass, URL
  canonicalization, canonical ID extraction (DOI/arXiv/SSRN/GitHub repo), family-specific
  normalize_metadata()
- `packages/research/ingestion/adapters.py` — SourceAdapter ABC, AcademicAdapter,
  GithubAdapter, BlogNewsAdapter, ADAPTER_REGISTRY, get_adapter()
- `packages/research/ingestion/pipeline.py` — IngestPipeline.ingest_external() wires
  adapter output into standard hard-stop -> eval gate -> chunk -> store pipeline

**CLI extension:**
```bash
python -m polytool research-ingest \
  --from-adapter tests/fixtures/ris_external_sources/arxiv_sample.json \
  --source-family academic --no-eval --json
```

**Source families covered:** academic (arxiv/ssrn/book), github, blog, news.

**Canonical IDs extracted:** doi, arxiv_id, ssrn_id, repo_url.

**Fixtures:** `tests/fixtures/ris_external_sources/{arxiv,github,blog}_sample.json`

Tests: 49 new offline tests in `tests/test_ris_phase4_source_acquisition.py`.
2009 total passing, 1 pre-existing failure (unrelated claim_extractor work).

See `docs/features/FEATURE-ris-phase4-source-acquisition.md` and
`docs/dev_logs/2026-04-02_ris_phase4_source_acquisition.md`.

## RIS Phase 4 — Claim Extraction and Evidence Linking (quick-260402-ogq, 2026-04-02)

Heuristic claim extraction pipeline that populates `derived_claims`, `claim_evidence`,
and `claim_relations` tables from already-ingested source documents. No LLM calls.

**New modules:**
- `packages/research/ingestion/claim_extractor.py` — `HeuristicClaimExtractor`,
  `extract_claims_from_document()`, `build_intra_doc_relations()`, `extract_and_link()`
- `tools/cli/research_extract_claims.py` — `research-extract-claims` CLI

**Key design decisions:**
- Idempotent via `_deterministic_created_at()`: claim IDs are stable across re-runs
  by deriving `created_at` from `SHA-256(doc_id + sentence + chunk_id + extractor_id)`
- Empirical regex requires 3+ digit numbers (`\b\d{3,}\b`) to avoid 2-digit numbers
  (e.g., "20 bps") stealing priority from normative keyword classification
- Evidence deduplication: checks for existing `(claim_id, source_document_id)` before
  inserting (KnowledgeStore `add_evidence()` has no INSERT OR IGNORE)
- `post_ingest_extract=True` on `IngestPipeline.ingest()` enables single-pass
  ingest + extraction; failure is non-fatal

**CLI usage:**
```bash
python -m polytool research-extract-claims --doc-id <DOC_ID>
python -m polytool research-extract-claims --all
python -m polytool research-extract-claims --all --dry-run
python -m polytool research-extract-claims --all --json
python -m polytool research-extract-claims --all --db-path artifacts/ris/knowledge.sqlite3
```

Tests: 56 new offline tests in `tests/test_ris_claim_extraction.py`. 3262 total passing, 0 failed.

See `docs/features/FEATURE-ris-v1-data-foundation.md` (Phase 4 section) and
`docs/dev_logs/2026-04-02_ris_phase4_claim_extraction.md`.

## RIS Social Ingestion v1 -- Reddit + YouTube (quick-260402-wj9, 2026-04-02)

- Adds `RedditAdapter`, `YouTubeAdapter` to `ADAPTER_REGISTRY` in `packages/research/ingestion/adapters.py`
- Adds `LiveRedditFetcher`, `LiveYouTubeFetcher`, `clean_transcript()` to `packages/research/ingestion/fetchers.py`
- Both fetchers support offline `fetch_raw()` mode -- no PRAW or yt-dlp needed for tests
- `research-acquire` CLI now accepts `--source-family reddit` and `--source-family youtube`
- Twitter/X explicitly marked DEFERRED (no implementation, no implied support)
  - Reason: $100/month API not justified pre-profit; free alternatives unreliable
- 30 new offline tests in `tests/test_ris_social_ingestion.py` (all passing)
- Total test count: 3405 passing, 0 failed, 3 deselected
- See `docs/features/FEATURE-ris-social-ingestion-v1.md` for coverage table and setup notes

## RIS_01 Academic Ingestion — Practical v1 Closure (quick-260402-wj3, 2026-04-02)

- `LiveAcademicFetcher.search_by_topic(query, max_results=5)` — ArXiv Atom search API,
  injectable `_http_fn`, returns `list[dict]`; accessible via `research-acquire --search`
- `BookAdapter` added to `ADAPTER_REGISTRY["book"]` — stable canonical URL
  `internal://book/{book_id}/{slug}` for curated book chapter ingestion
- `canonicalize_url()` guard added for non-HTTP schemes (`internal://` now passes through
  unchanged); fixes normalization crash on book canonical URLs
- `IngestPipeline.ingest_external()` now accepts `post_ingest_extract=False` kwarg (same
  non-fatal pattern as `ingest()`)
- Both `research-ingest` and `research-acquire` CLIs expose `--extract-claims` flag
- `research-acquire` exposes `--search QUERY` + `--max-results N` for ArXiv topic search
- SSRN status documented truthfully as deferred (live scraper not implemented; URL-pattern
  detection works when operator provides pre-built raw_source via `--from-adapter`)
- 26 new offline tests in `tests/test_ris_academic_ingest_v1.py` (all passing)
- See `docs/features/FEATURE-ris-academic-ingest-v1.md` and
  `docs/dev_logs/2026-04-02_ris_r1_academic_ingestion_completion.md`

## RIS Report Persistence and Catalog (quick-260402-xbt, 2026-04-02)

Report persistence layer for the RIS synthesis engine. Reports are saved as
markdown artifacts under `artifacts/research/reports/` with a JSONL index for
list/search. Manual weekly-digest command generates summary digests from precheck
and eval artifact data.

- `packages/research/synthesis/report_ledger.py` -- ReportEntry, persist_report,
  list_reports, search_reports, generate_digest
- `tools/cli/research_report.py` -- save/list/search/digest subcommands
- Storage: local-first JSONL index at `artifacts/research/reports/report_index.jsonl`
- ClickHouse indexing: deferred (JSONL is sufficient for current operator scale)
- APScheduler/n8n automation: deferred to RIS_06

CLI:

```
python -m polytool research-report save --title "Market Edge Analysis" --body "Report content..."
python -m polytool research-report list --window 7d
python -m polytool research-report search --query "market maker"
python -m polytool research-report digest --window 7
```

Tests: 21 new offline tests in `tests/test_ris_report_catalog.py`. 3334 total passing,
0 failed.

See `docs/features/FEATURE-ris-report-persistence.md` and
`docs/dev_logs/2026-04-02_ris_r3_report_storage_and_catalog.md`.

## RIS Query Planner, HyDE Expansion, and Combined Retrieval (quick-260402-xbj, 2026-04-03)

Query-planning side of RIS_05 Synthesis Engine. Three new modules in
`packages/research/synthesis/` enable multi-angle evidence retrieval for research
briefs and prechecks.

**New modules:**
- `packages/research/synthesis/query_planner.py` — `QueryPlan` dataclass, `plan_queries()`:
  topic -> 3-5 diverse retrieval queries via ANGLE_PREFIXES (deterministic) or LLM (Ollama).
  Supports `include_step_back=True` for broader contextual query. Falls back to deterministic
  when LLM returns unparseable JSON or raises.
- `packages/research/synthesis/hyde.py` — `HydeResult` dataclass, `expand_hyde()`:
  query -> hypothetical document passage (HyDE technique). Deterministic template fallback.
- `packages/research/synthesis/retrieval.py` — `RetrievalPlan` dataclass, `retrieve_for_research()`:
  multi-angle retrieval through existing `query_index()` RRF spine. Merges by chunk_id (highest
  score), tracks `result_sources` dict, falls back to empty results if Chroma unavailable.

**All three modules follow the existing provider pattern** (same as `precheck.py`):
uses `get_provider()` with `was_fallback` tracking. Local providers (manual, ollama) work offline.

**Key design note:** `get_provider` imported at module level so that `unittest.mock.patch`
can intercept it in tests. Retrieval module uses a thin `query_index` wrapper at module level
to defer Chroma import while remaining patchable.

**Deferred:** semantic query dedup, parallel sub-query execution, multi-hop reasoning,
cloud provider HyDE (RIS v2 deliverable).

27 offline tests in `tests/test_ris_query_planner.py`. 3474 total passing, 0 failed.

See `docs/features/FEATURE-ris-query-planner.md` and
`docs/dev_logs/2026-04-03_ris_query_planner.md`.

## RIS_05 Synthesis Engine v1 -- Deterministic Report and Precheck Synthesis (quick-260402-xbo, 2026-04-03)

The deterministic synthesis layer for RIS_05 is shipped. `ReportSynthesizer` takes
enriched claims from `query_knowledge_store_enriched()` and produces structured,
cited research artifacts -- no LLM calls. LLM-based synthesis (DeepSeek V3) is deferred to v2.

**New module:** `packages/research/synthesis/report.py`

- `CitedEvidence` -- single cited evidence item with source attribution (source_doc_id,
  source_title, source_type, trust_tier, confidence, freshness_note, provenance_url)
- `ResearchBrief` -- structured report matching RIS_05 format with all sections:
  summary, key_findings, contradictions, actionability, knowledge_gaps, cited_sources
- `EnhancedPrecheck` -- parallel to PrecheckResult; GO/CAUTION/STOP with cited evidence
  lists (supporting, contradicting), risk_factors, stale_warning, evidence_gap
- `ReportSynthesizer.synthesize_brief(topic, claims)` -- sorts by effective_score,
  top non-contradicted claims -> key_findings, contradicted -> contradictions section,
  stale -> knowledge_gaps, strategy keywords -> actionability
- `ReportSynthesizer.synthesize_precheck(idea, claims)` -- keyword-filters claims by
  idea relevance, separates supporting vs contradicting, applies GO/CAUTION/STOP rules
- `format_citation()`, `format_research_brief()`, `format_enhanced_precheck()` -- markdown renderers

**Exports added to `packages/research/synthesis/__init__.py`:**
`CitedEvidence`, `EnhancedPrecheck`, `ResearchBrief`, `ReportSynthesizer`,
`format_citation`, `format_enhanced_precheck`, `format_research_brief`

**Deferred (v2):** LLM-based synthesis (DeepSeek V3), multi-model citation verification,
iterative orchestrator loop, weekly digest, CLI commands for report generation,
report storage/catalog, ClickHouse report indexing, past failures search.

21 offline tests in `tests/test_ris_report_synthesis.py`. 3474 total passing, 0 failed.

See `docs/features/FEATURE-ris-synthesis-engine-v1.md` and
`docs/dev_logs/2026-04-03_ris_r3_report_and_precheck_synthesis.md`.

## RIS Operator Stats and Metrics Export (quick-260403-1sg, 2026-04-03)

Operator metrics surface for the RIS pipeline. `research-stats summary` and `research-stats export` are now operational.

**New module:** `packages/research/metrics.py`

- `RisMetricsSnapshot` dataclass -- all counts in one view (docs, claims, gate split, precheck decisions, reports, acquisition)
- `collect_ris_metrics(...)` -- reads from KS SQLite, eval_artifacts.jsonl, precheck_ledger.jsonl, report_index.jsonl, acquisition_review.jsonl; no network, no ClickHouse
- `format_metrics_summary(snapshot)` -- human-readable multi-line string with sections: Knowledge Store, Eval Gate, Prechecks, Reports, Acquisition

**New CLI:** `research-stats`

- `research-stats summary` -- print metrics snapshot (or --json for raw JSON)
- `research-stats export` -- write `artifacts/research/metrics_snapshot.json` for Grafana Infinity plugin polling

**Deferred:** ClickHouse write path, APScheduler integration for periodic export, pre-built Grafana dashboard JSON.

15 offline deterministic tests in `tests/test_ris_ops_metrics.py`. 3489 total passing, 0 failed.

See `docs/features/FEATURE-ris-ops-cli-and-metrics.md` and
`docs/dev_logs/2026-04-03_ris_r4_ops_cli_and_metrics.md`.
