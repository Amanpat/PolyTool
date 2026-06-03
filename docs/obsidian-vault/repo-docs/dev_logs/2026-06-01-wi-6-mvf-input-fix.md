---
title: Wi 6 Mvf Input Fix
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-06-01_wi-6-mvf-input-fix.md
last_synced: '2026-06-03T02:26:56Z'
lifecycle: reviewed
generator: repo-sync
---

# WI-6 — MVF Input Fix

**Date:** 2026-06-01
**Sprint:** Wallet-Ingestion v1
**Packet:** WI-6 (MVF Input Fix) — runs parallel to WI-3 (scheduler)
**Scope:** `packages/polymarket/discovery/mvf.py`, `tests/test_mvf.py`, docs. Position
export in `packages/polymarket/llm_research_packets.py` inspected (read-only — no schema
change needed; the fix lives entirely on the MVF helper side, per packet preference).

## Problem (from 2026-05-29 wallet-ingestion audit, §B)

Three MVF dimensions silently degraded because the MVF helpers looked up field names
that the live scan dossier never emits. Confirmed against current code before editing:

- The scan path computes MVF in `tools/cli/scan.py:1409` from `positions =
  _load_dossier_positions(output_dir)`, which reads `dossier.json` →
  `_extract_positions_payload` → the position rows built by
  `llm_research_packets.normalize_position_for_export` (`llm_research_packets.py:1599-1639`,
  `:458-510`).
- Those rows use `entry_ts` / `exit_ts` (ISO-8601), a precomputed
  `hold_duration_seconds`, `resolved_at`, and Gamma close fallbacks
  (`gamma_close_date_iso`, `close_date_iso`, `gamma_end_date_iso`, `end_date_iso`,
  `gamma_uma_end_date`, `uma_end_date`). They carry **no** market-open timestamp.
- The MVF helpers, by contrast, looked for `first_trade_timestamp` /
  `last_trade_timestamp` (+ `open_timestamp`/`created_at`/`close_timestamp`/`closed_at`)
  and, for late-entry, `market_open_ts` / `market_created_at` and
  `gamma_close_time` / `end_date_ts`. None of these match real scan output.

Result on real input: `avg_hold_duration_hours` → null; `trade_frequency_per_day` →
degraded fallback `float(len(positions))` (count-per-one-day); `late_entry_rate` → null.

## Expected ↔ Actual field map (the 3 degraded dims)

| Dimension | Helper expected (pre-WI-6) | Actual scan field(s) | Fix |
|---|---|---|---|
| `avg_hold_duration_hours` | `first_trade_timestamp` / `last_trade_timestamp` (+ open/close aliases) | `entry_ts`, `exit_ts`, `resolved_at`, **`hold_duration_seconds`** (precomputed) | Added `_entry_timestamp` / `_exit_timestamp` resolvers covering scan + legacy names; added a fast path that uses the precomputed `hold_duration_seconds` when present. |
| `trade_frequency_per_day` | `first_trade_timestamp` / `last_trade_timestamp` (+ aliases) | `entry_ts`, `exit_ts`, `resolved_at` | Window now built from the same `_entry_timestamp` / `_exit_timestamp` resolvers instead of the legacy-only name list. |
| `late_entry_rate` | entry via `first_trade_timestamp`…; close via `close_timestamp`/`closed_at`/`gamma_close_time`/`end_date_ts`; **start** via `market_open_ts`/`market_created_at` | entry = `entry_ts`; close = `gamma_close_date_iso`/`close_date_iso`/`gamma_end_date_iso`/`end_date_iso`/`gamma_uma_end_date`/`uma_end_date`; **start = ABSENT** | Added `_market_close_timestamp` resolver (covers Gamma close names); entry uses `_entry_timestamp`. Market-open is genuinely absent from the dossier, so the dim stays null **by design** with an honest note (see below). |

## Before → after on a real-scan-shaped sample

Fixture `_REAL_SCAN_POSITIONS` (3 positions, real field names — `tests/test_mvf.py`):
A entry 11-14T00:00Z / exit 11-15T00:00Z (24h); B entry 11-14T00:00Z +
`hold_duration_seconds=43200` (12h); C entry 11-16T00:00Z / `resolved_at` 11-16T06:00Z (6h).

| Dimension | Before (degraded) | After (real values) |
|---|---|---|
| `avg_hold_duration_hours` | `None` (no matching ts fields) | `14.0` = (24+12+6)/3 |
| `trade_frequency_per_day` | `3.0` (fallback `float(len)`) | `1.333…` = 3 / 2.25-day window |
| `late_entry_rate` | `None` (field-name miss) | `None` (close fields now read, but market-open genuinely absent — honest null + note) |

`late_entry_rate` is additionally proven correct when a caller supplies `market_open_ts`:
a 2-position fixture (one entered at 9/10 of market life, one at 1/10) computes `0.5`,
confirming the reconciled close-field map works end-to-end.

## Dimension-count decision: corrected to **11** (not 12)

The code has always emitted 11 dimensions; only some stale docs/roadmap text claimed 12.
Decision: **formally correct to 11.** Rationale: there is no clean, data-backed 12th
dimension available. The would-be 12th (`maker_taker_ratio`) has no input on the live path
(see below), and inventing a weak dimension purely to hit 12 is explicitly disallowed by
the packet and would violate the "no MVF algorithm redesign" gate.

Doc surface checked: all authoritative repo docs/specs/tests already say "11"
(`docs/specs/SPEC-wallet-discovery-v1.md`, `docs/features/wallet-discovery-v1.md`,
`docs/CURRENT_STATE.md`, `docs/runbooks/WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md`,
`tests/test_wallet_discovery_integrated.py` asserts `== 11`). The only live "12-Dimension"
string is in an **auto-generated** Obsidian smart-connections cache
(`docs/obsidian-vault/.smart-env/multi/08-Research_02-Metrics-Engine-MVF_md.ajson`) that
points at a research note already deleted in the working tree. That cache is machine-written
and out of WI-6's file scope, so it was left untouched. The correction is recorded
authoritatively in the `mvf.py` module docstring.

## maker_taker_ratio disposition: null + documented

Per WI-1: maker/taker attribution is **absent from the Polymarket Data API** (`/trades`
carries `side` only; no per-fill maker/taker). Therefore `maker_taker_ratio` is left **null
and documented** on the live scan path — NOT wired, no new data source added. The helper
`_compute_maker_taker_ratio` is retained unchanged: it still computes a value if a caller
supplies an explicit `maker`/`side_type` field (e.g. archive backfill from raw-Jon parquet
via DuckDB), so the dimension is not removed. The module docstring now states this
explicitly. The existing TODO marker in `packages/polymarket/data_api.py` was left in place.

## Tests

Added `TestRealScanFieldReconciliation` to `tests/test_mvf.py` (6 tests): asserts the exact
computed values `avg_hold_duration_hours == 14.0` and `trade_frequency_per_day == 3/2.25`
(and that it is NOT the `3.0` fallback), the honest `late_entry_rate` null + note, the
`late_entry_rate == 0.5` case when market-open is supplied, no degradation note for hold
duration, and determinism on reversed input.

```
python -m pytest tests/test_mvf.py -q --tb=short
=> 43 passed in 0.41s   (was 37; +6 new)

python -m pytest tests/test_wallet_discovery_integrated.py -q --tb=short
=> 12 passed in 5.83s   (count assertion `== 11` unchanged, still green)
```

## Acceptance gates

- **Determinism** — same scan input → same MVF vector. Verified by
  `test_determinism_on_real_shaped_input` and existing determinism suite.
- **No redesign / no new data source** — only field-name resolvers added; algorithm
  unchanged; no external source wired. `late_entry_rate` and `maker_taker_ratio` stay null
  by design where inputs are genuinely absent.
- **Regression** — all existing MVF tests pass; count assertions remain 11.

## Codex review

`mvf.py` is research-side (not in the execution/kill-switch/signing denylist) →
**Recommended** tier per repo Codex policy; not blocking. No mandatory-tier files touched.

## Open items / honest caveats

- `late_entry_rate` will remain null on the live scan path until a market-open (market
  creation/start) timestamp is added to the dossier export. That is a deliberate
  out-of-scope deferral (new data source), now documented in both code and this log.

---

## late_entry_rate completion (2026-06-01, follow-up)

The earlier deferral ("needs a new data source — market-open timestamp absent from
the export") was **wrong**. The market-open timestamp was already available in an
already-joined ClickHouse table; it had simply never been selected into the export.
This follow-up plumbs it through so `late_entry_rate` computes on real values, matching
the other two reconciled dimensions. **NOT a new data source** — only an existing column
on an already-joined table.

### Source column

- `markets_enriched.start_date_iso` (`Nullable(DateTime)`).
- `markets_enriched` is a `CREATE OR REPLACE VIEW ... SELECT * FROM polytool.markets`
  (`infra/clickhouse/initdb/05_packet4_tables.sql:49`); `polytool.markets` carries
  `start_date_iso` (defined at `03_packet3_tables.sql:42`, also added via
  `ALTER TABLE ... ADD COLUMN IF NOT EXISTS start_date_iso` at `05_packet4_tables.sql:44`).
- Note: `market_tokens` has NO start column (only `end_date_iso`), so the market-open
  value comes solely from `markets_enriched` — exactly the same subquery (`me_close`)
  that already supplies `close_date_iso`. No new JOIN was added.

### JOIN / field plumbing (`packages/polymarket/llm_research_packets.py`)

1. `_build_close_ts_join_sql`: added a 4th select slot
   `"NULL AS gamma_start_date_iso"`, set to `"me_close.start_date_iso AS gamma_start_date_iso"`
   when `market_tokens` + `markets_enriched` both exist. Added
   `any(start_date_iso) AS start_date_iso` to the existing `me_close` subquery's SELECT
   (same `condition_id` join, same `_table_exists` guards). Stays NULL-safe when the
   table/column is absent.
2. Lifecycle row unpacking: enriched view column count 30 → 31, fallback 21 → 22; both
   now bind `gamma_start_date_iso_raw` as the trailing column.
3. Position dict: populated `gamma_start_date_iso` and `start_date_iso`
   (both `_optional_isoformat(gamma_start_date_iso_raw)`), mirroring the close-ts
   fallback pattern. These pass through `normalize_position_for_export` unchanged
   (same handling as the close fields).

### MVF helper field the export feeds (`packages/polymarket/discovery/mvf.py`)

- New resolver `_market_open_timestamp(pos)` reads (in order):
  `market_open_ts` → `market_created_at` → `market_start_ts` → `gamma_start_date_iso`
  → `start_date_iso`. The live scan path supplies `start_date_iso` / `gamma_start_date_iso`;
  the explicit `market_open_ts` aliases remain for synthetic callers.
- `_compute_late_entry_rate` now calls `_market_open_timestamp` for the market-START
  reference; the obsolete "would require a new data source" comment and data note were
  replaced with an honest "start_date_iso is NULL for these markets" note (fires only
  when the column is genuinely null per-row).

### Before → after on a sample

Scan-shaped position `entry_ts=2023-11-19`, `gamma_close_date_iso=2023-11-20`:

- **BEFORE** (no `start_date_iso`): `late_entry_rate = None` (degraded/null).
- **AFTER** (`start_date_iso=2023-11-10` plumbed from `markets_enriched`):
  `late_entry_rate = 1.0` — entry is 9/10 of the way through the market window → late.

Dimension count stays **11**. `maker_taker_ratio` unchanged (still null/documented).

### Tests

- `tests/test_mvf.py`: `_REAL_SCAN_POSITIONS` fixture gained `start_date_iso` on all three
  rows; replaced the old "null by design" late-entry test with
  `test_late_entry_rate_computes_on_real_scan_fields` (asserts real `0.0`, non-null) +
  `test_late_entry_rate_no_degradation_note` + `test_late_entry_rate_detects_late_entries_via_start_date_iso`
  (0.5) + `test_late_entry_rate_null_when_start_date_genuinely_absent` (honest null path).
- `tests/test_llm_research_packets.py`: `_position_to_lifecycle_row` extended with the
  31st column (`gamma_start_date_iso`/`start_date_iso`) so the fake matches the new SELECT.
- Results: `tests/test_mvf.py tests/test_wallet_discovery_integrated.py` → **57 passed**
  (incl. the `== 11` dimension assertion). `tests/test_llm_research_packets.py
  tests/test_clv.py tests/test_export_schema_guard.py` → **49 passed**.
