# PDR: Roadmap 5 Prereqs Verification

We ran an end-to-end verification pass for the recent category-coverage and market-type fixes using local tests and a real scan run for `@DrPufferfish`. The market-type behavior improved in live artifacts (fewer `unknown` matchup rows), and size/notional rendering is present. Category coverage remained unresolved in runtime output and needs an operational parity check.

## Commands run

- `pytest -q`
- `python -m polytool scan --user "@DrPufferfish" --api-base-url "http://127.0.0.1:8000" --ingest-positions --compute-pnl --enrich-resolutions --debug-export`

Also executed in an isolated worktree for merge verification:

- `git pull --ff-only` on latest `main`
- merged `fix/category-coverage`
- merged `feat/moneyline-default-market-type`

## Observed metrics

Run root:

`artifacts/dossiers/users/drpufferfish/0xdb27bf2ac5d428a9c63dbc914611036855a6c56e/2026-02-19/fa988495-6e17-48e6-9141-e606a3552582`

`coverage_reconciliation_report.json`:

- `positions_total`: `50`
- `category_coverage.coverage_rate`: `0.0` (`0/50`)
- `category_coverage.source_counts`: `ingested=0`, `backfilled=0`, `unknown=50`
- `segment_analysis.by_market_type`:
  - `moneyline=32`
  - `spread=17`
  - `total=0`
  - `unknown=1`

Comparison to prior run (`2026-02-18/68bba9fd-...`):

- `by_market_type.unknown`: `25 -> 1`

`audit_coverage_report.md`:

- `Size / Notional Coverage` shows `notional_missing_count=0`
- per-position rows include explicit `size/notional` values

## Any remaining gaps

- Category still missing at runtime (`100% missing`) despite merged fix branches.
- Next operational checks:
  - ensure the API serving `127.0.0.1:8000` is running the latest merged code path;
  - verify category-populated token metadata is available to that runtime (table/data parity).
