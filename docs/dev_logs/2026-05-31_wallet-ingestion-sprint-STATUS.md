# Wallet-Ingestion v1 Sprint — Running STATUS Log

Orchestrator-maintained. One paragraph per packet as it lands. Execution order:
WI-1 → WI-2 → WI-3 → WI-4 → WI-5 (spine, sequential); WI-6 independent/parallel.

Hard stop gates: WI-2 (before applying schema migration), WI-5 (Discord bot token must be
in `.env`), and any failing acceptance gate/test.

---

## WI-1 — Queue Consumer + Arg-Seam Fix — ✅ COMPLETE (2026-05-31)

**Files changed:** created `packages/polymarket/discovery/scan_worker.py` (`ScanWorker` +
`make_clickhouse_watchlist_advancer`), `tests/test_scan_worker.py` (13 tests),
`docs/dev_logs/2026-05-31_wi-1-queue-consumer.md`; modified `tools/cli/discovery.py`
(`run-worker` subparser + `_run_worker`), `tools/cli/wallet_scan.py` (arg-seam: `--wallet`→`--user`),
`packages/polymarket/discovery/scan_queue.py` (`load_from_clickhouse` → `FINAL ORDER BY dedup_key, updated_at`),
`packages/polymarket/data_api.py` (maker/taker TODO marker), `docs/CURRENT_STATE.md`.

**Tests:** 142 passed, 0 failed, 0 skipped (test_wallet_discovery, _integrated, _integration,
_scan_dossier_integration, test_wallet_scan, test_scan_worker). CLI loads; `run-worker` registered;
fail-fast on missing `CLICKHOUSE_PASSWORD`.

**Live smoke (operator-required, #1):** PASS against running API (:8000) + ClickHouse. Raw address
`0x84cfffc3f16dcc353094de30d4a45226eccd2f63` resolved through `--user` as a **wallet** (not handle);
queue pending→leased→done; dossier run_root materialized; KnowledgeStore +2 `dossier_report` docs / +2
claims; watchlist `lifecycle_state=scanned`. Enqueued via sanctioned `ScanQueueManager.enqueue` +
`flush_to_clickhouse` (no hand-INSERT).

**Operator checks resolved:** #1 raw-0x resolution code-confirmed in `GammaClient.resolve` + live-proven.
#2 discovered→scanned was NOT in the reused path → added by the worker (in scope, no tiers). #3
single-worker lease assumption documented (module docstring + dev log) for WP-3. #4 RMT version column
confirmed `ReplacingMergeTree(updated_at)`; collapse on it. #5 no ceiling existed in `ScanQueueManager`
→ worker adds `max_attempts=5` dead-letter to `dropped`.

**maker/taker:** ABSENT from Data API `/trades` (`side` only); deferred to raw-Jon-parquet/DuckDB path;
no on-chain code added. **Denylist:** untouched.

**Non-blocking note for operator:** scan emitted warnings that `POLYGON_RPC_URL` /
`POLYMARKET_SUBGRAPH_URL` are unset, so on-chain/subgraph resolution providers were skipped (242
outcomes stayed PENDING/UNKNOWN). Environment-config gap in the resolution cascade, NOT a worker/queue
bug; out of WI-1 scope. Flagged, not fixed.

**Infra note:** the `api` compose service was down at smoke time; orchestrator built+started it
(`docker compose up -d api`, now healthy) to run the live smoke.

---

## WI-2 — Dossier Supersede + Schema — ✅ COMPLETE (2026-05-31)

**Files changed:** `packages/polymarket/rag/knowledge_store.py` (lifecycle columns + idempotent
`_upgrade_source_document_lifecycle`, `deferred_transaction`, `supersede_dossier_run`,
`list_source_documents`, live-DB pytest guard), `packages/research/integration/dossier_extractor.py`
(wallet-level supersede-on-new-run, `_normalize_wallet`, `_retain_prior_runs`),
`config/freshness_decay.json` (`dossier_report: 4`), `docs/scripts/sync-ris-mirror.py` (mirror excludes
superseded/archived), `tests/test_ris_dossier_supersede.py` (14 tests),
`docs/dev_logs/2026-05-31_wi-2-dossier-supersede.md`, `docs/CURRENT_STATE.md`. Commits `ef82b10` + hardening.

**Tests:** touched surface 94 passed; focused guard+CLI run 81 passed; broader RIS regression 971 passed,
3 failed (PRE-EXISTING — verified on clean tree at `c249ff5` via git stash; unrelated to WI-2).

**Design (operator-settled):** wallet-level supersede gated on new-run success (sections are conditional:
Detectors unconditional, Candidates/Memo conditional — (wallet,section) would orphan dropped sections).
Wallet normalized lowercase on write+match. Single new-first transaction, rollback-on-failure (no zero/two
active sets). Stable `document_type` enum from constants. Mirror sync filters superseded. `dossier_report: 4`
months (<sibling `wallet_analysis: 6` deliberately — un-rescanned dossiers should decay faster); confirmed
LIVE knob via `query_claims`→`compute_freshness_modifier`. Retention success-gated, prior dir from superseded
docs' `metadata_json.dossier_path`.

**⚠️ Hard-stop gate incident — operator decision "Accept, but harden first":** the gated `source_documents`
ALTER auto-applied to the live `knowledge.sqlite3` (a bare `KnowledgeStore()` opened during an ad-hoc run;
`_ensure_schema` auto-upgrades on open) WITHOUT the planned second-go/quiesce/pre-backup. Verified clean:
additive only, 151 docs / 4893 claims all `lifecycle='active'`, 0 superseded, no data loss, DB gitignored.
Backup taken: `kb/rag/knowledge/knowledge.sqlite3.pre-wi2.2026-05-31.bak` (sha `e15c8397…`). **Hardening
applied:** `KnowledgeStore.__init__` refuses the live `DEFAULT_KNOWLEDGE_DB_PATH` under pytest
(`POLYTOOL_ALLOW_LIVE_KB=1` override) + 4 guard tests; existing tests already use tmp/:memory: (non-breaking).
Root cause = bare-default constructor; the auto-upgrade-on-open is correct for production, so no production
behavior changed.

---

## WI-3 — Discovery + Rescan Scheduler — ⏳ NEXT (depends on WI-1 + WI-2, both ✅)
