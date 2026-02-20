# PDR: Roadmap 5 Wrap-Up

**Product Design Record**
**Status:** Complete
**Branch:** `roadmap5`
**Date:** 2026-02-20

---

## Overview

Roadmap 5 extended the scan pipeline with CLV (Closing Line Value) signals and a
batch-run harness for multi-user hypothesis leaderboards. The CLV capture
infrastructure was built and wired end-to-end, but live CLV coverage measured 0%
in verification runs due to missing close timestamps and API failures — triggering
the roadmap kill condition. The batch-run harness and hypothesis leaderboard shipped
fully. Several data-quality prerequisites (moneyline default rule, notional
normalization, hypothesis candidates artifact) were also delivered as quick tasks
before CLV work began.

---

## What Shipped

### 5.0 — Prerequisites

Delivered as quick tasks on the roadmap5 branch before CLV work began.

**Moneyline default rule**
- `vs`-matchup markets now default to `market_type = "moneyline"` instead of
  `"unknown"`.
- Reduced `by_market_type.unknown` from 25 to 1 in verification run
  (2026-02-19 prereqs PDR).
- Reference commit: `e5705ad`.
- Category coverage regression guards added to tests.

**Category coverage regression fix**
- ROOT: lifecycle views lacked a `category` column; fixed with a LEFT JOIN on
  `polymarket_tokens` inside `packages/polymarket/llm_research_packets.py`.
- Commit: `e5e04f0` ("prefer populated category metadata table").
- Code fix is correct; runtime coverage remains 0% because the Polymarket API
  does not populate `category`/`subcategory` for the test user's token set
  (upstream data gap — see Known Limitations).

**Notional surface end-to-end**
- `position_notional_usd` injected into scan enrichment from the API payload.
- `notional_weight_debug.json` artifact emitted alongside existing debug artifacts.
- String coercion for notional values arriving as strings from the API.
- `audit_coverage_report.md` shows `notional_missing_count = 0`.
- Quick-005, commit `1e47f3a`.

---

### 5.1 — CLV Capture (infrastructure shipped; coverage kill condition triggered)

- `--compute-clv` enrichment stage added to `scan`.
- `market_price_snapshots` ClickHouse table for closing price storage
  (`infra/clickhouse/initdb/20_clv_price_snapshots.sql`).
- Per-position CLV fields in dossier: `close_ts`, `close_ts_source`,
  `closing_price`, `closing_ts_observed`, `clv`, `clv_pct`, `beat_close`,
  `clv_source`, `clv_missing_reason`.
- CLV coverage section in `coverage_reconciliation_report.json` / `.md`.
- Per-position CLV rendering in `audit_coverage_report.md`.
- Explicit missingness: positions without closing-price data report `clv: null`
  plus a `clv_missing_reason` (e.g. `OFFLINE`, `NO_CLOSE_TS`).
- Commit: `76b75c7` ("CLV complete").
- Spec: `docs/specs/` (CLV + price context spec).
- ADR: closing price ADR, commit `e54a61b`.
- Verification: PDR-ROADMAP5-CLV-VERIFY.md. Live run measured 0.0% CLV coverage
  (0/50 positions), triggering the roadmap kill condition (< 30% after 3 scan runs).

---

### 5.5 — Batch-Run Harness + Hypothesis Leaderboard (shipped fully)

- `python -m polytool batch-run` CLI with multi-user input file (`--users users.txt`).
- Leaderboard artifacts: `hypothesis_leaderboard.json` + `hypothesis_leaderboard.md`.
- `batch_manifest.json` trust artifact with per-user run-root traceability.
- Notional-weighted and count-weighted segment aggregation across users.
- Deterministic ordering: metric descending, `segment_key` ascending tiebreak.
- Offline-safe via injectable `BatchRunner(scan_callable=...)`.
- Tests: `tests/test_batch_run.py` (no network, no ClickHouse).
- Feature: `docs/features/FEATURE-batch-run-hypothesis-leaderboard.md`.

---

### Quick Tasks Shipped on roadmap5 Branch

- **quick-004**: `hypothesis_candidates.json` artifact emitted per scan run; Hypothesis
  Candidates markdown section added to `coverage_reconciliation_report.md`. Commit `eaa39f2`.
- **quick-005**: Notional-weight normalization — normalize `position_notional_usd` in
  `scan.py`; emit `notional_weight_debug.json`; string coercion for API values. Commit `1e47f3a`.
- **quick-006**: Dual CLV variants — `clv_settlement` (resolved positions, `onchain_resolved_at`
  only) and `clv_pre_event` (gamma `closedTime`/`endDate`/`umaEndDate`); hypothesis ranking
  cascade: pre_event notional-weighted > settlement notional-weighted > combined >
  count-weighted fallback. Commit `37f404a`.

---

## Canonical Commands

### CLV scan (infrastructure present; coverage 0% in current environment)

```bash
python -m polytool scan \
  --user "@handle" \
  --ingest-positions \
  --compute-pnl \
  --enrich-resolutions \
  --compute-clv \
  --debug-export
```

### Batch run with leaderboard

```bash
python -m polytool batch-run \
  --users users.txt \
  --api-base-url "http://127.0.0.1:8000" \
  --ingest-positions \
  --compute-pnl \
  --enrich-resolutions \
  --compute-clv \
  --debug-export
```

---

## Trust Artifacts Added in Roadmap 5

| File | Description |
|------|-------------|
| `hypothesis_candidates.json` | Per-user segment hypothesis candidates with CLV, beat-close, and notional weights |
| `notional_weight_debug.json` | Debug artifact showing notional normalization inputs and outputs |
| Batch: `batch_manifest.json` | Batch run provenance: attempted/succeeded/failed, per-user run roots |
| Batch: `hypothesis_leaderboard.json` | Multi-user aggregated segment leaderboard |
| Batch: `hypothesis_leaderboard.md` | Human-readable leaderboard rendering |
| Batch: `per_user_results.json` | Per-user scan status and top candidates |

---

## Known Limitations / Deferred

- **CLV coverage is 0% in current environment.** The snapshot cache table
  (`market_price_snapshots`) is empty because the Gamma `/prices-history`
  endpoint returned HTTP 400 in all verification runs and most positions lack
  `close_ts` (43 of 50 reported `OFFLINE`, 7 of 50 `NO_CLOSE_TS`). The roadmap
  kill condition (< 30% coverage after 3 scan runs) was triggered. CLV
  infrastructure remains in the codebase but is dormant pending a reliable
  closing-price source.
- **Category coverage remains 0% in this environment.** The ingestion code path is
  correct (`e5e04f0`), but the Polymarket API does not populate `category` /
  `subcategory` fields for the test user's token set. Global `market_tokens` has
  11 008 rows with 0 non-empty `category` values. No upstream fix is available.
- **Roadmap 5.2 (Time/Price Context — price trajectory over hold period) deferred.**
  Kill condition on 5.1 CLV coverage means no reliable foundation for 5.2.
- **`datetime.utcnow()` deprecation warnings** throughout (`examine.py`,
  `backfill.py`, `mcp_server.py`, `services/api/main.py`) — migration to
  `datetime.now(timezone.utc)` deferred.

---

## Evidence

- PDR-ROADMAP5-CLV-VERIFY.md — CLV operational verification, 2026-02-19
- PDR-ROADMAP5-PREREQS-VERIFY.md — category + market-type prereq check, 2026-02-19
- PDR-ROADMAP5-CATEGORY-INGEST-VERIFY.md — category ingest check, 2026-02-19
- See `docs/ROADMAP.md` Roadmap 5 section.
