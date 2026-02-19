# FEATURE: Segment Analysis in Scan Trust Artifacts

**Shipped**: 2026-02-16  
**Roadmap**: 4.2

Scan reports now show performance slices in a way that is easier to review quickly: how results break down by entry price tier, market type, league, and sport, including explicit unknown buckets so missing metadata is visible instead of hidden.

## What shipped

- `coverage_reconciliation_report.json` now includes top-level `segment_analysis` with:
  - `by_entry_price_tier`
  - `by_market_type`
  - `by_league`
  - `by_sport`
- New run artifact: `segment_analysis.json`
- `run_manifest.json` now includes `output_paths.segment_analysis_json`
- `coverage_reconciliation_report.md` now includes a **Segment Highlights** section:
  - top 3 segments by `total_pnl_net`
  - bottom 3 segments by `total_pnl_net`
  - unknown-rate callouts for league/sport/market_type when rate > 20%

## Classification behavior

- League is inferred from `market_slug` prefix token only (known code list).
- Sport is mapped from league.
- Market type uses a conservative heuristic (`spread`/`handicap`, else `Will .* win`).
- Entry price tiers come from local `polytool.yaml` and fall back to default buckets.
- Unknown segments are always emitted.

## Related docs

- `docs/specs/SPEC-0003-segment-analysis.md`
- `docs/adr/0006-position-derived-classification.md`
- `docs/STRATEGY_PLAYBOOK.md`

