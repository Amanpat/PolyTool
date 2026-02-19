# PDR: Roadmap 4 Wrap-Up

**Product Design Record**
**Status:** Complete
**Branch:** `roadmap4.6`
**Date:** 2026-02-18

---

## Overview

Roadmap 4 extended the trust-artifact pipeline with segment analysis, category
coverage, an offline audit CLI, and several data-quality improvements.  Every
feature was delivered via `python -m polytool scan` and the new
`python -m polytool audit-coverage` command — no new infrastructure required.

---

## What Shipped

### 4.1 — Segment Analysis Foundation
- Coverage report gains `segment_analysis` with breakdowns by `entry_price_tier`,
  `market_type`, `league`, `sport`.
- Separate `segment_analysis.json` artifact written alongside
  `coverage_reconciliation_report.json`.
- `run_manifest.json` includes `output_paths.segment_analysis_json`.
- Spec: `docs/specs/SPEC-0003-segment-analysis.md`
- ADR: `docs/adr/0006-position-derived-classification.md`

### 4.2 — YAML-Configurable Entry Price Tiers
- `polytool.yaml` / `polytool.yml` `segment_config.entry_price_tiers` lets
  operators override the four built-in tiers (`deep_underdog`, `underdog`,
  `coinflip`, `favorite`).
- Fee estimation configurable via `fee_config.profit_fee_rate` (default 2 %).
- ADR: `docs/adr/0007-fee-estimation-2pct-profit.md`
- Feature: `docs/features/FEATURE-fee-estimation.md`

### 4.3 — Market Metadata Backfill
- Self-referential backfill: positions that already carry
  `market_slug`/`question`/`outcome_name` fill in siblings that don't, using
  the same dossier payload — no network call needed.
- Coverage report includes `market_metadata_coverage` section with
  `present_count`, `missing_count`, `coverage_rate`, `source_counts`,
  `top_unmappable`.
- Warning emitted when missing rate exceeds 20 %.
- Spec: `docs/specs/SPEC-0005-market-metadata-backfill.md`
- Feature: `docs/features/FEATURE-market-metadata-backfill.md`

### 4.4 — Market Metadata Coverage Metrics
- Coverage report `market_metadata_coverage` field (added to schema `1.4.0`).
- `segment_analysis.by_market_slug.top_by_total_pnl_net` and
  `top_by_count` sub-sections.

### 4.5 — Category Segmentation
- Coverage report gains `category_coverage` section (present/missing/rate).
- `segment_analysis.by_category` breakdown.
- Uses Polymarket's own `category` field verbatim; unknown → `"Unknown"` bucket.
- ADR: `docs/adr/0009-polymarket-category-taxonomy.md`
- Spec: `docs/specs/SPEC-0006-category-segmentation.md`
- Feature: `docs/features/FEATURE-category-segmentation.md`

### 4.6 — Category Fix, Audit Coverage CLI, Scan Auto-Audit, Defaults

**Category ingestion fix (category_coverage was always 0)**
- Root cause: lifecycle views (`user_trade_lifecycle*`) had no `category`
  column.  Fix: LEFT JOIN `polymarket_tokens` in the lifecycle query inside
  `packages/polymarket/llm_research_packets.py`.
- Amendment documented in `docs/adr/0009-polymarket-category-taxonomy.md`.
- Debug: `docs/debug/DEBUG-category-coverage-zero.md`
- Feature: `docs/features/FEATURE-polymarket-taxonomy-ingestion.md`

**`audit-coverage` CLI** (`python -m polytool audit-coverage`)
- Offline trust sanity report — no ClickHouse, no network, no RAG required.
- Reads `run_manifest.json` + `dossier.json` from the latest (or specified) run.
- Spec: `docs/specs/SPEC-0007-audit-coverage-cli.md`
- Feature: `docs/features/FEATURE-audit-coverage-cli.md`

**Scan auto-audit** (scan always emits `audit_coverage_report.md`)
- Every `scan` run writes the audit report into the run root unconditionally.
- `run_manifest.json` always includes `output_paths.audit_coverage_report_md`.
- Fee-sanity hardening: `positive_pnl_with_zero_fee_count` in quick stats;
  red flag when non-zero.
- Spec: `docs/specs/SPEC-0008-scan-auto-audit.md`
- Feature: `docs/features/FEATURE-scan-auto-audit.md`

**Audit default: all positions** (ADR-0011)
- `audit-coverage` defaults to ALL positions (was fixed 25-position sample).
- `scan` always emits audit with all positions (was only with `--audit-sample`).
- Pass `--sample N` / `--audit-sample N` to limit to a deterministic sample.
- ADR: `docs/adr/0011-audit-default-all-positions.md`
- Feature: `docs/features/FEATURE-audit-default-all.md`

**History position-count fallback** (ADR-0010)
- When history row reports `positions_count=0` but dossier body contains rows,
  use the body rows and emit an explicit warning.
- ADR: `docs/adr/0010-history-zero-position-count-fallback.md`
- Debug: `docs/debug/DEBUG-history-export-empty-positions.md`

**README runbook**
- Root `README.md` written with the canonical Roadmap 4 quickstart runbook.
- Feature: `docs/features/FEATURE-readme-roadmap4-runbook.md`

---

## Canonical Commands

### Full scan (trust artifacts + audit)
```bash
python -m polytool scan \
  --user "@DrPufferfish" \
  --ingest-positions \
  --compute-pnl \
  --enrich-resolutions \
  --debug-export
```
Emits (all in run root `artifacts/dossiers/users/<slug>/<wallet>/<date>/<run_id>/`):
- `run_manifest.json`
- `dossier.json`
- `coverage_reconciliation_report.json` / `.md`
- `segment_analysis.json`
- `resolution_parity_debug.json`
- `audit_coverage_report.md`  ← always emitted; includes all positions

### Audit only (offline, no network/ClickHouse)
```bash
# All positions (default):
python -m polytool audit-coverage --user "@DrPufferfish"

# Limit to N positions:
python -m polytool audit-coverage --user "@DrPufferfish" --sample 25 --seed 1337

# JSON format:
python -m polytool audit-coverage --user "@DrPufferfish" --format json
```

### LLM evidence bundle
```bash
python -m polytool llm-bundle --user "@DrPufferfish"
```
Works without RAG; if RAG is not indexed the `## RAG excerpts` section is omitted.

---

## Trust Artifacts (full list)

| File | Description |
|------|-------------|
| `run_manifest.json` | Run provenance: command, argv, timestamps, config hash, output paths |
| `dossier.json` | Raw position/trade export from the API |
| `coverage_reconciliation_report.json` | Machine-readable trust report (v1.4.0) |
| `coverage_reconciliation_report.md` | Human-readable rendering of the same |
| `segment_analysis.json` | Segment breakdown by tier/type/league/sport/category |
| `resolution_parity_debug.json` | Cross-run resolution enrichment diagnostics |
| `audit_coverage_report.md` | Offline accuracy + trust sanity; all positions by default |

Schema version: `report_version = "1.4.0"`.
Full schema reference: `docs/TRUST_ARTIFACTS.md`.

---

## ADRs Produced in Roadmap 4

| ADR | Topic |
|-----|-------|
| 0006 | Position-derived classification (league / sport / market type) |
| 0007 | Fee estimation: 2 % on gross profit |
| 0009 | Use Polymarket category taxonomy as-is + Roadmap 4.6 amendment |
| 0010 | History position-count / body mismatch fallback |
| 0011 | Audit default: all positions |

Note: ADR-0008 was skipped (no ADR was issued between 0007 and 0009).

---

## Known Limitations / Deferred to Roadmap 5

- **CLV (Closing Line Value) capture** — not yet implemented; positions lack
  pre-resolution market probability snapshots.
- **Hypothesis validation loop** — `llm-save` schema enforcement, hypothesis
  diff, and falsification harness are deferred (see `docs/ROADMAP.md` Roadmap 5+).
- **`datetime.utcnow()` deprecation warnings** — present in several modules
  (`examine.py`, `backfill.py`, `mcp_server.py`, `services/api/main.py`);
  migration to `datetime.now(timezone.utc)` deferred.
- **ADR-0001 naming inconsistency** — `docs/adr/ADR-0001-cli-and-module-rename.md`
  uses an `ADR-` prefix; all other ADRs use the bare `NNNN-description.md`
  convention.  Renaming would require updating five cross-references; deferred.
