# PDR: Roadmap 5 Category Ingest Verification

## Summary

A fresh scan with market ingest/backfill was executed for `@drpufferfish` on 2026-02-19, then global and run-scoped category counts were checked in ClickHouse. In this environment, category/subcategory remain unpopulated (`0` non-empty rows), and the resulting run still reports `category_coverage.coverage_rate = 0.0`.

## Commands

```bash
python -m polytool scan --user "@drpufferfish" --ingest-markets --ingest-activity --ingest-positions --compute-pnl --snapshot-books --debug-export
```

```sql
SELECT count() AS total_rows, countIf(category != '') AS category_non_empty FROM market_tokens;
SELECT countIf(subcategory != '') AS subcategory_non_empty FROM market_tokens;
SELECT countIf(category != '') AS run_category_non_empty
FROM market_tokens
WHERE token_id IN {tokens:Array(String)};
```

## Observed metrics

- run_id: `e3959865-fcc4-4146-9246-ffb693200061`
- run_root: `artifacts/dossiers/users/drpufferfish/0xdb27bf2ac5d428a9c63dbc914611036855a6c56e/2026-02-19/e3959865-fcc4-4146-9246-ffb693200061`
- global `market_tokens` rows: `11008`
- global non-empty `category`: `0`
- global non-empty `subcategory`: `0`
- run-scoped non-empty `category`: `0` (50 run token IDs)
- `category_coverage.coverage_rate`: `0.0`

## Outcome

- Verification workflow executed successfully.
- Positive-coverage condition was not observed because run-scoped category count remained `0`.
