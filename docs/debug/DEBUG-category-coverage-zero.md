# DEBUG: category_coverage = 0% Despite market_metadata_coverage = 100%

**Date:** 2026-02-18
**Status:** Resolved (Roadmap 4.6)
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

## Audit Report Mismatch (secondary fix)

A secondary issue was that `audit_coverage_report.md` sample rows showed raw dossier values (e.g., `fees_estimated: 0.0`) while `coverage_reconciliation_report.json` showed derived values (e.g., `fees_estimated_present_count: 5`). This was because:

1. The ClickHouse `user_trade_lifecycle_enriched` view defines `fees_estimated` as `0.0 AS fees_estimated` (a placeholder).
2. `build_coverage_report()` in `scan.py` calls `normalize_fee_fields()` on each position, computing `fees_estimated = gross_pnl * 0.02` when `gross_pnl > 0`. These mutated positions are used for the coverage report but **not written back to `dossier.json`**.
3. `audit_coverage.py` reads raw `dossier.json` positions, so it showed the placeholder `0.0`.

**Fix:** `audit_coverage.py` now calls `_enrich_position_for_audit()` on every position before sampling. This function applies `normalize_fee_fields` and derives `league`, `sport`, `market_type`, `entry_price_tier` using the same shared helpers from `coverage.py`. Samples are now consistent with coverage stats.

---

## Verification

After the fix:
- `category_coverage.coverage_rate` is non-zero when `polymarket_tokens` has been backfilled.
- Audit sample rows show `fees_estimated > 0` for positions with `gross_pnl > 0`.
- Audit sample rows show derived `league/sport/market_type/entry_price_tier`.
- `pytest -q` is green (348 tests passing).
