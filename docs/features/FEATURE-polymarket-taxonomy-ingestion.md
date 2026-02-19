# Feature: Polymarket Category Taxonomy Ingestion

**Status:** Implemented (Roadmap 4.6)
**Related:** SPEC-0006, ADR-0009, SPEC-0007

---

## Summary

Wires Polymarket's `category` field (e.g. `"Sports"`, `"Politics"`, `"Crypto"`) from
the local `polymarket_tokens` ClickHouse table into every dossier position so that
`category_coverage` and `segment_analysis.by_category` report real values rather than
`0%` / all-`Unknown`.

---

## User-Visible Changes

- **`coverage_reconciliation_report.json`**: `category_coverage.coverage_rate` is
  non-zero when the market backfill has been run. `segment_analysis.by_category`
  shows real category labels (e.g. `"Sports": { count: 87, ... }`).

- **`audit_coverage_report.md`**: Sample position blocks now show
  `category: Sports` (or the actual label) instead of `Unknown`. `fees_estimated`
  and `realized_pnl_net_estimated_fees` are derived values, consistent with the
  Quick Stats header counts.

- **Warning suppression**: When backfill has populated `polymarket_tokens`, the
  `>20% category missing` warning disappears from `coverage_reconciliation_report.json`.

---

## How It Works

1. **Storage**: `polymarket_tokens.category` (ClickHouse) holds the Polymarket
   label for each token. Populated once by `packages/polymarket/backfill.py`.

2. **Dossier build**: `packages/polymarket/llm_research_packets.py` LEFT JOINs
   `polymarket_tokens` in both lifecycle queries, appending `category` as the last
   column. Gracefully falls back to `""` if the table is unpopulated.

3. **Coverage**: `polytool/reports/coverage.py` already handled `category` via
   `backfill_market_metadata()` and `_build_category_coverage()`. No changes
   needed there — the fix was purely in the dossier build step.

4. **Audit enrichment**: `tools/cli/audit_coverage.py` applies
   `_enrich_position_for_audit()` before sampling, mirroring the same field
   derivations (`league`, `sport`, `market_type`, `entry_price_tier`,
   `fees_estimated`) that the coverage report uses.

---

## Operator Checklist

To get non-zero category coverage:

```bash
# 1. Run the market backfill to populate polymarket_tokens
python -m polytool backfill-markets

# 2. Re-run scan to regenerate dossier with category wired in
python -m polytool scan --user "@handle"

# 3. Check audit report
python -m polytool audit-coverage --user "@handle"
```

If `polymarket_tokens` is empty, `category_coverage.coverage_rate` will be `0.0`
and a `>20%` warning will appear — that is the expected, correct diagnostic signal.

---

## Debugging

See `docs/debug/DEBUG-category-coverage-zero.md` for the full root-cause analysis
and before/after fix details.
