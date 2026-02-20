# SPEC-0007 — Audit Coverage CLI

## Overview

`audit-coverage` is a read-only CLI command that produces an accuracy and trust
sanity report for a user's latest (or specified) scan run.  It reads artifact
files from disk only — no ClickHouse, RAG, or network calls required — making
it suitable for use on a travel laptop with no running infrastructure.

---

## CLI Interface

```
python -m polytool audit-coverage --user "@example" [OPTIONS]
```

### Required arguments

| Flag     | Type   | Description                                     |
|----------|--------|-------------------------------------------------|
| `--user` | string | Target user handle (with or without `@`).       |

### Optional flags

| Flag        | Type   | Default | Description                                             |
|-------------|--------|---------|---------------------------------------------------------|
| `--sample`  | int    | —       | Number of positions to include. **Omit = all positions (default).** |
| `--seed`    | int    | 1337    | Random seed (used only when `--sample` is provided).    |
| `--run-id`  | string | —       | Pin to a specific run_id; default = latest scan run.    |
| `--output`  | path   | —       | Override output file path; default = `<run_root>/audit_coverage_report.md`. |
| `--format`  | choice | `md`    | `md` (default) or `json`.                              |

### Exit codes

| Code | Meaning                                                         |
|------|-----------------------------------------------------------------|
| 0    | Report written; output path printed to stdout.                  |
| 1    | Error (no scan run found, invalid args, etc.).                  |

---

## Run Discovery

1. If `--run-id` is specified: locate the `run_manifest.json` under
   `artifacts/dossiers/users/<slug>/` whose `run_id` field matches.
   Returns an error if not found.

2. Otherwise: scan all `run_manifest.json` files under the user's artifact
   directory.  Prefer those with `command_name = "scan"`.  Among candidates,
   select the one with the latest `started_at` timestamp (falling back to
   file mtime).

3. If no `run_manifest.json` exists at all, return a helpful error and exit 1.

---

## Input Artifacts (read from `run_root`)

All files are read from `run_root` — no mutation of existing artifacts.

| File                                    | Required | Description                               |
|-----------------------------------------|----------|-------------------------------------------|
| `run_manifest.json`                     | Yes      | Provenance; supplies `run_id`, `wallet`.  |
| `dossier.json`                          | Optional | Source for position records.              |
| `coverage_reconciliation_report.json`   | Optional | Source for Quick Stats and Red Flags.     |
| `segment_analysis.json`                 | Optional | Source for unknown-rate segment stats.    |
| `resolution_parity_debug.json`          | Not used | Reserved for future phases.               |

When a file is absent its section shows a graceful "not found" note.

---

## Output Artifact

Default path:

```
artifacts/dossiers/users/<slug>/<wallet>/<YYYY-MM-DD>/<run_id>/audit_coverage_report.md
```

This path is identical to `run_root` — the report is co-located with the scan
artifacts it audits.  When `--output` is specified the report is written to
that path instead.

If `--format json`, the default extension becomes `.json`.

---

## Sampling Rules

Positions are sampled deterministically using the following algorithm:

1. **Stable sort** positions by `(token_id | resolved_token_id, condition_id, created_at)`.
2. **Partition** into two lists:
   `resolved` = positions where `resolution_outcome` ∈ {WIN, LOSS, PROFIT_EXIT, LOSS_EXIT}
   `unresolved` = all others (PENDING, UNKNOWN_RESOLUTION, absent).
3. **Concatenate** `resolved + unresolved` to form the pool.
4. If `len(pool) ≤ N`, return the entire pool.
5. Otherwise, seed `random.Random(seed)` and call `rng.sample(range(len(pool)), N)`.
   Sort the selected indices and return those positions.

This guarantees that:
- The same `(positions, N, seed)` triple always returns the same sample.
- Resolved positions are preferentially represented.

---

## Report Schema (Markdown)

### Header

```markdown
# Audit Coverage Report

[file_path: <run_root_posix>]

**User:** @example
**Slug:** example
**Wallet:** 0xabc...
**Run ID:** abc123
**Generated at:** 2026-02-18T12:00:00+00:00
```

### Quick Stats

Sourced from `coverage_reconciliation_report.json`:

- `positions_total`
- `resolved_count` (sum of WIN + LOSS + PROFIT_EXIT + LOSS_EXIT)
- `pending_count`
- `category_coverage.coverage_rate` and `missing_count`
- `market_metadata_coverage.coverage_rate` and `metadata_conflicts_count`
- `unknown_league_rate`, `unknown_sport_rate`, `unknown_market_type_rate`
  (computed from `segment_analysis.json` if present)
- `fees_estimated_present_count`, `fees_source_counts`

### Red Flags

Deterministic checks — flags fire when:

| Condition                                     | Flag label                        |
|-----------------------------------------------|-----------------------------------|
| `category_missing_rate > 20%`                 | `category_missing_rate=X%`        |
| `market_metadata_conflicts_count > 0`         | `market_metadata_conflicts_count` |
| All positions are PENDING                     | all-PENDING warning               |
| `resolved_count = 0` (non-zero positions)     | `resolved_count=0`                |
| `unknown_league_rate > 20%`                   | `unknown_league_rate=X%`          |
| `unknown_sport_rate > 20%`                    | `unknown_sport_rate=X%`           |
| `unknown_market_type_rate > 20%`              | `unknown_market_type_rate=X%`     |

When no flags fire, the section reads: `- No red flags detected.`

### All Positions (N) / Samples (N)

When `--sample` is omitted the heading is `## All Positions (N)` and all
positions are printed in stable-sorted order.  When `--sample N` is provided
the heading is `## Samples (N)` and a deterministic subset is printed.

One block per position, showing:
- `market_slug`, `question` (truncated to 80 chars), `outcome_name`
- `category`, `league`, `sport`, `market_type`, `entry_price_tier`
- `entry_price`, `size/notional`
- `resolution_outcome`
- `gross_pnl`, `fees_estimated`, `net_estimated_fees`

All fields default to `"Unknown"` if absent in the position record.

---

## Report Schema (JSON)

When `--format json` the report is written as a structured object:

```json
{
  "report_type": "audit_coverage",
  "user_input": "@example",
  "user_slug": "example",
  "wallet": "0xabc...",
  "run_id": "abc123",
  "generated_at": "2026-02-18T12:00:00+00:00",
  "run_root": "artifacts/dossiers/users/example/0xabc/2026-02-18/abc123",
  "quick_stats": { ... },
  "red_flags": ["...", "..."],
  "samples": {
    "n_requested": null,
    "all_mode": true,
    "n_returned": 20,
    "seed": 1337,
    "positions": [{ ... }, ...]
  }
}
```

---

## Constraints

- No ClickHouse, RAG, or network calls.
- Does not modify existing report schemas.
- Does not re-compute coverage from raw positions — reads the pre-built
  `coverage_reconciliation_report.json` for summary stats.

---

## Amendment — Canonical size/notional field names (2026-02-19)

The `size/notional` field in position blocks is resolved via a prioritised fallback chain.
The implementation stores results in two canonical fields before rendering:

| Canonical field | Meaning | Upstream sources (in order) |
|-----------------|---------|------------------------------|
| `position_size` | Shares held | `position_size` → `total_bought` → `size` |
| `position_notional_usd` | USD cost basis | `position_notional_usd` → `initialValue` → `total_cost` → derived |

When `position_notional_usd` cannot be sourced directly, it is derived as
`abs(position_size) × entry_price` and the position block shows the source flag
`(derived_from_size_price)`.  When no data exists at all, the position block shows
`N/A (MISSING_UPSTREAM_FIELDS)` — never a silent `N/A`.

The Quick Stats section gains a **Size / Notional Coverage** block reporting
`notional_missing_count` and `notional_derived_count` across all positions in the run.
These two fields are also added to the `quick_stats` object in JSON output.
