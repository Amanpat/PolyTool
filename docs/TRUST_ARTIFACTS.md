# Trust Artifacts (Roadmap 2)

Roadmap 2 made `python -m polytool scan` the canonical trust-artifact producer.
The two public trust artifacts are:

- `coverage_reconciliation_report.json` (optional `coverage_reconciliation_report.md`)
- `run_manifest.json`

Both are written into the scan run root:

`artifacts/dossiers/users/<slug>/<wallet>/<YYYY-MM-DD>/<run_id>/`

`examine` is legacy orchestration. For canonical trust-artifact validation,
use runs where `run_manifest.json` has `command_name = "scan"`.

## Canonical Commands

```powershell
python -m polytool scan --user "@example"
python -m polytool scan --user "@example" --debug-export
```

`--debug-export` prints wallet, endpoint, and hydration diagnostics that help
explain empty or low-coverage exports.

## Artifact Summary

- `coverage_reconciliation_report.json`:
  machine-readable trust report for outcome coverage, UID coverage, PnL/fees
  sanity checks, resolution coverage, and warnings.
- `coverage_reconciliation_report.md`:
  optional human-readable rendering of the same report.
- `run_manifest.json`:
  run provenance/reproducibility metadata and output paths.

## coverage_reconciliation_report.json

### Practical schema

- Top-level identity/provenance:
  `report_version`, `generated_at`, `run_id`, `user_slug`, `wallet`,
  `proxy_wallet`
- Totals:
  `totals.positions_total`
- Outcome distribution:
  `outcome_counts`, `outcome_percentages`
- UID coverage:
  `deterministic_trade_uid_coverage`, `fallback_uid_coverage`
- PnL sanity:
  `pnl.realized_pnl_net_total`,
  `pnl.realized_pnl_net_by_outcome`,
  `pnl.missing_realized_pnl_count`
- Fee sourcing sanity:
  `fees.fees_source_counts`,
  `fees.fees_actual_present_count`,
  `fees.fees_estimated_present_count`
- Resolution coverage:
  `resolution_coverage.resolved_total`,
  `resolution_coverage.unknown_resolution_total`,
  `resolution_coverage.unknown_resolution_rate`,
  `resolution_coverage.held_to_resolution_total`,
  `resolution_coverage.win_loss_covered_rate`
- Warnings:
  `warnings` (list of actionable strings)

### Outcomes

`outcome_counts`/`outcome_percentages` cover these buckets:

- `WIN`
- `LOSS`
- `PROFIT_EXIT`
- `LOSS_EXIT`
- `PENDING`
- `UNKNOWN_RESOLUTION`

Any unrecognized outcome value is normalized into `UNKNOWN_RESOLUTION`.

### deterministic_trade_uid_coverage vs fallback_uid_coverage

- `deterministic_trade_uid_coverage`:
  strict coverage from deterministic `trade_uid` only.
  Includes duplicate detection (`duplicate_trade_uid_count`,
  `duplicate_sample`).
- `fallback_uid_coverage`:
  coverage from fallback identifiers only
  (`resolved_token_id`, then `token_id`, then `condition_id`).
  Includes `fallback_only_count` for rows lacking deterministic `trade_uid`.

Interpretation rule of thumb:

- High deterministic coverage is best.
- High fallback-only coverage means data is still usable, but less strict for
  dedupe/auditing than deterministic `trade_uid`.

### Warning rules of thumb

Warnings are emitted when these conditions occur:

- duplicate deterministic UIDs exist
- `UNKNOWN_RESOLUTION` rate is above 5%
- one or more rows are missing `realized_pnl_net`
- all rows have `fees_source=unknown`

Scan adds an extra warning when `positions_total = 0` that includes wallet and
endpoint context plus next checks (wallet mapping, lookback/history coverage).

## run_manifest.json

### Practical schema

- Run identity/timing:
  `manifest_version`, `run_id`, `started_at`, `finished_at`,
  `duration_seconds`
- Invocation:
  `command_name`, `argv`
- Resolved identity context:
  `user_input`, `user_slug`, `wallets`
- Outputs:
  `output_paths` (includes `run_root`,
  `coverage_reconciliation_report_json`, and optional markdown path)
- Reproducibility metadata:
  `effective_config_hash_sha256`, `polytool_version`, `git_commit`

For canonical Roadmap 2 runs, `command_name` is `scan`.

### Config hash behavior + secret redaction

`effective_config_hash_sha256` is SHA-256 of deterministic JSON serialization
(`sort_keys=True`, stable separators) of the effective config after recursive
secret redaction.

Redaction rule: any config key containing one of these substrings
(case-insensitive) is replaced with `<REDACTED>` before hashing:

- `password`
- `secret`
- `token`
- `key`
- `api_key`

Implications:

- Same non-secret effective config => same hash across runs.
- Different secret values alone do not change the hash.
- If no effective config is passed, the hash is an empty string.

### What makes runs reproducible

When comparing two runs, the most useful fields are:

- `command_name` + `argv`
- `effective_config_hash_sha256`
- `user_slug` + `wallets`
- `polytool_version` + `git_commit`
- `output_paths.run_root` for exact artifact location

## Empty-Export Triage (`--debug-export`)

Use `--debug-export` when trust artifacts look empty or unexpectedly sparse.
The debug stream reports:

- wallet used for export/hydration
- endpoints used:
  `/api/export/user_dossier`, `/api/export/user_dossier/history`
- counts from export and hydrated payloads (positions/trades)
- whether history hydration replaced an empty latest export

If `positions_total = 0`, validate:

1. handle/wallet mapping for the target user
2. export/history endpoint rows for that wallet
3. lookback/history coverage for the target period
