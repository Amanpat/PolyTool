# Trust Artifacts (Roadmap 2)

This document defines the trust artifacts emitted by the canonical scan workflow.

## Canonical Command

Use scan as the canonical workflow entrypoint:

```powershell
python -m polytool scan --user "@example"
```

For export diagnostics (wallet, endpoints, response counts):

```powershell
python -m polytool scan --user "@example" --debug-export
```

`examine` is a legacy orchestration path. Trust artifacts should be validated from
scan runs where `run_manifest.json` has `command_name = "scan"`.

## Run Root Concept

Each scan writes a run root under:

`artifacts/dossiers/users/<slug>/<wallet>/<YYYY-MM-DD>/<run_id>/`

Typical files in the run root:

- `dossier.json` (exported dossier payload used for trust artifact computation)
- `memo.md` (if available from export hydration)
- `coverage_reconciliation_report.json` (canonical machine-readable trust report)
- `coverage_reconciliation_report.md` (optional human-readable rendering)
- `run_manifest.json` (canonical run metadata + output paths)

## coverage_reconciliation_report.json

Main sections and how to interpret them:

- `report_version`, `generated_at`, `run_id`, `user_slug`, `wallet`, `proxy_wallet`:
  identity and provenance metadata.
- `totals.positions_total`: number of position records used to compute this report.
- `outcome_counts` / `outcome_percentages`:
  distribution of `WIN`, `LOSS`, `PROFIT_EXIT`, `LOSS_EXIT`, `PENDING`,
  `UNKNOWN_RESOLUTION`.
- `deterministic_trade_uid_coverage`:
  strict trade UID coverage from deterministic `trade_uid` values only.
- `fallback_uid_coverage`:
  non-deterministic fallback identifiers (`resolved_token_id`, `token_id`,
  `condition_id`) tracked separately from deterministic coverage.
- `pnl`:
  realized net PnL totals and `missing_realized_pnl_count`.
- `fees`:
  fee sourcing diagnostics including `fees_source_counts` and actual/estimated
  presence counts.
- `resolution_coverage`:
  resolved/unknown totals and rates, plus held-to-resolution diagnostics.
- `warnings`:
  actionable data quality or coverage warnings for this run.

### Interpreting Common "Low Quality" Patterns

These are expected in Roadmap 2 outputs and are not by themselves a bug:

- High `UNKNOWN_RESOLUTION`
- High `missing_realized_pnl_count`
- High `fees_source = unknown`
- Low deterministic trade UID coverage

Roadmap 3 owns reducing `UNKNOWN_RESOLUTION` and improving outcome coverage/data
quality. Use warnings plus raw dossier/export context to triage what is data
availability vs parser/schema mismatch.

## run_manifest.json

`run_manifest.json` is the canonical execution metadata for a scan run.

Key fields:

- `command_name`: should be `scan` for canonical trust artifact runs.
- `argv`: command arguments used for this run.
- `run_id`, `started_at`, `finished_at`, `duration_seconds`:
  run timing and identity.
- `user_input`, `user_slug`, `wallets`:
  resolved identity context.
- `output_paths`:
  canonical references to run outputs, including
  `coverage_reconciliation_report_json` and `run_root`.
- `effective_config_hash_sha256`:
  reproducibility hook for effective runtime config.

## Debug Export Guidance

Run with `--debug-export` when diagnosing empty or unexpected coverage.

Expected diagnostics include:

- wallet used for export/hydration
- endpoints used (`/api/export/user_dossier`, `/api/export/user_dossier/history`)
- counts returned (positions/trades and local/hydrated lengths)
- hydration decision (whether history replaced an empty export payload)

If `positions_total = 0`, validate:

1. user handle to wallet mapping is correct
2. export endpoints returned non-empty positions for that wallet
3. lookback window/history coverage is sufficient for the target period
