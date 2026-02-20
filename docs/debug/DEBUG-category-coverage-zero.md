# DEBUG: category_coverage = 0% Despite market_metadata_coverage = 100%

**Date:** 2026-02-18
**Status:** Resolved (Roadmap 4.6, regression hardening 2026-02-19)
**Symptom:** `coverage_reconciliation_report.json` showed `category_coverage.coverage_rate = 0.0` (all positions missing category) while `market_metadata_coverage.coverage_rate = 1.0`.

---

## Root Cause

The position records in `dossier.json` were built from the `user_trade_lifecycle_enriched` ClickHouse view. That view joins `user_trade_lifecycle` with `market_resolutions`, but **neither view includes the `category` column**.

The `category` field is stored in the `polymarket_tokens` table (populated by the market backfill pipeline via `packages/polymarket/backfill.py`). However, the lifecycle query in `packages/polymarket/llm_research_packets.py` did not join `polymarket_tokens`, so every position in the dossier was written with `category: ""`.

At scan time, `_build_metadata_map_from_positions()` builds a self-referential metadata map from positions that already carry metadata. Since no positions had `category` set, the map contained no category values. `backfill_market_metadata()` therefore had nothing to fill, and `_build_category_coverage()` correctly (but misleadingly) reported `present_count=0`.

The `market_metadata_coverage` showed 100% because `market_slug`, `question`, and `outcome_name` **were** coming from the lifecycle view (via `user_trades_resolved` columns). Category was the only field not wired.

---

## Fix Applied

**`packages/polymarket/llm_research_packets.py`** — both lifecycle queries (`positions_lifecycle_enriched_query` and `positions_lifecycle_fallback_query`) now LEFT JOIN with a subquery on `polymarket_tokens`:

```sql
LEFT JOIN (
    SELECT token_id, any(category) AS category
    FROM polymarket_tokens
    GROUP BY token_id
) t ON l.resolved_token_id = t.token_id
```

`COALESCE(t.category, '') AS category` is added as the last selected column (index 26 for enriched, 17 for fallback). The `position_row` dict now includes `"category": category_val`.

When `polymarket_tokens` has not been backfilled yet, `category` gracefully falls back to `""`, and coverage reports correctly show a high missing rate with a `>20%` warning, prompting operators to run the market backfill.

---

## Regression (2026-02-19): global-nonempty table selection can still yield 0% for a run

This was a second-order regression after the initial missing-join fix.

The category source selector chose a table using a **global non-empty check**
(`countIf(category != '')` over the whole table). That can still fail for a
specific run:

- `polymarket_tokens` may have category rows globally, but none for the run's
  token IDs.
- `market_tokens` may have run-relevant category rows.
- Global non-empty preference still picks `polymarket_tokens`, causing all run
  rows to join empty categories and collapse to `Unknown`.

### Step-0 reproduction evidence

Latest DrPufferfish run:
`artifacts/dossiers/users/drpufferfish/0xdb27bf2ac5d428a9c63dbc914611036855a6c56e/2026-02-19/27aa1a2c-843d-4e27-8acb-92d86583ffbb`

- `coverage_reconciliation_report.json`: `category_coverage.coverage_rate = 0.0`
- Run token sample extracted from `dossier.json`: `token_ids_count=50`

Run-scoped probes (for those token IDs):

```sql
SELECT countIf(category != '') AS non_empty_for_run
FROM polymarket_tokens
WHERE token_id IN {tokens:Array(String)}
```

Output: table missing in this local DB (`exists=False`).

```sql
SELECT countIf(category != '') AS non_empty_for_run
FROM market_tokens
WHERE token_id IN {tokens:Array(String)}
```

Output: `run_non_empty_count=0`.

```sql
SELECT countIf(category != '') AS non_empty_global
FROM market_tokens
```

Output: `global_non_empty_count=0`.

### Regression fix

- Category selection is now **run-scoped** in
  `packages/polymarket/llm_research_packets.py`:
  - gather up to 200 unique `resolved_token_id` values for the current wallet/run
    from lifecycle tables,
  - probe both candidate tables for non-empty categories on those token IDs,
  - choose the table with the higher run-scoped count.
- Tie/zero behavior keeps deterministic fallback, but now records a clear reason
  code in dossier coverage:
  - `category_source` (e.g. `run_scoped_best_coverage`, `none_available`)
  - `category_source_table`
  - `category_source_run_non_empty_counts`
  - `category_source_run_probe_token_count`

### Regression tests

- `tests/test_llm_research_packets.py::ResearchPacketExportTests::test_export_lifecycle_query_includes_category_join`
- `tests/test_llm_research_packets.py::ResearchPacketExportTests::test_export_prefers_market_tokens_when_polymarket_tokens_empty`
- `tests/test_llm_research_packets.py::ResearchPacketExportTests::test_export_prefers_market_tokens_when_run_scope_coverage_is_higher`
- `tests/test_coverage_report.py::TestCategoryCoverage::test_category_backfill_updates_position_and_by_category_bucket`

---

## Ingestion gap (2026-02-19): 0% can also occur when category metadata is never stored

Even with correct lifecycle joins and run-scoped table selection, category
coverage will stay at 0% if local metadata tables never persist taxonomy
fields.

Observed local failure mode:

- `market_tokens` existed but `countIf(category != '') = 0`
- `polymarket_tokens` table was absent in the same environment
- result: every joined row produced empty category and reports collapsed to
  `Unknown`

Verification queries:

```sql
SELECT
    count() AS total_rows,
    countIf(category != '') AS category_non_empty_rows,
    countIf(subcategory != '') AS subcategory_non_empty_rows
FROM market_tokens;
```

```sql
SELECT countIf(category != '') AS category_non_empty_for_run
FROM market_tokens
WHERE token_id IN {tokens:Array(String)};
```

If both counts are zero while upstream Gamma payloads include category labels,
the issue is ingestion/storage, not coverage math.

---

## Categories never stored because ingest-markets path dropped fields (2026-02-19)

Follow-up diagnosis on **2026-02-19** found two combined issues in the ingest path:

1. `services/api/main.py` `/api/ingest/markets` writer had a stale `market_tokens` insert column list that did not include `subcategory` (and had no source-marker fields).
2. In live payload samples, Gamma `/markets` and embedded `events[0]` were often returning `null` for `category/subcategory`, so empty values were written end-to-end.

What was changed:

- Added scan debug artifact `gamma_markets_sample.json` (run root, emitted when `--debug-export` is enabled) with:
  - request URL and params used for `/markets`
  - first 10 raw markets with `id`, `slug`, `conditionId`, `clobTokenIds`, top-level `category`, and `events[0]` category/subcategory
- Updated ingestion and backfill mapping to persist:
  - `category`, `subcategory`
  - `category_source` (`market|event|none`)
  - `subcategory_source` (`event|none`)
- Added event fallback logic:
  - use `events[0].category/subcategory` when present
  - else bounded `/events` lookups by referenced event ids/slugs
- Added non-overwrite behavior in ingest writer: only fill empty taxonomy fields.

### How to verify

1. Run:

```bash
python -m polytool scan --user "@drpufferfish" --ingest-markets --debug-export
```

2. Inspect run artifact:

```text
artifacts/dossiers/users/<user>/<wallet>/<date>/<run_id>/gamma_markets_sample.json
```

3. Check whether raw payload includes category labels:
   - if `category` or `events_0_category`/`events_0_subcategory` is non-empty in sample rows, ingestion should persist non-empty taxonomy.
   - if sample rows are null/empty, storage stays empty without guessing.

4. Confirm ClickHouse counts:

```sql
SELECT
    count() AS total_rows,
    countIf(category != '') AS category_non_empty_rows,
    countIf(subcategory != '') AS subcategory_non_empty_rows
FROM market_tokens;
```

```sql
SELECT countIf(category != '') AS category_non_empty_for_run
FROM market_tokens
WHERE token_id IN {tokens:Array(String)};
```

---

## Audit Report Mismatch (secondary fix)

A secondary issue was that `audit_coverage_report.md` sample rows showed raw dossier values (e.g., `fees_estimated: 0.0`) while `coverage_reconciliation_report.json` showed derived values (e.g., `fees_estimated_present_count: 5`). This was because:

1. The ClickHouse `user_trade_lifecycle_enriched` view defines `fees_estimated` as `0.0 AS fees_estimated` (a placeholder).
2. `build_coverage_report()` in `scan.py` calls `normalize_fee_fields()` on each position, computing `fees_estimated = gross_pnl * 0.02` when `gross_pnl > 0`. These mutated positions are used for the coverage report but **not written back to `dossier.json`**.
3. `audit_coverage.py` reads raw `dossier.json` positions, so it showed the placeholder `0.0`.

**Fix:** `audit_coverage.py` now calls `_enrich_position_for_audit()` on every position before sampling. This function applies `normalize_fee_fields` and derives `league`, `sport`, `market_type`, `entry_price_tier` using the same shared helpers from `coverage.py`. Samples are now consistent with coverage stats.

---

## Verification

After the fix:
- `category_coverage.coverage_rate` is non-zero when category metadata has been backfilled into a joined token table (for example `market_tokens`).
- Audit sample rows show `fees_estimated > 0` for positions with `gross_pnl > 0`.
- Audit sample rows show derived `league/sport/market_type/entry_price_tier`.
- `pytest -q` is green (`365 passed, 2 skipped`).
