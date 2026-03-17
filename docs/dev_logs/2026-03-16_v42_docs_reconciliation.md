# v4.2 Docs Reconciliation

**Date**: 2026-03-16
**Branch**: phase-1

---

## Summary

Reconciled all live docs to Master Roadmap v4.2. The v4.2 pivot changes
where historical Parquet data lives: DuckDB reads it directly from files
on disk; ClickHouse is reserved for live streaming writes only. This made
the ClickHouse bulk import path (SPEC-0018) off the critical path.

---

## Conflict Resolved

**v4.1 stated**: bulk historical import (pmxt + Jon-Becker + price_history_2min
into ClickHouse tables) was the primary Gate 2 path.

**v4.2 states**: DuckDB queries pmxt and Jon-Becker Parquet files directly
from `/data/raw/` — no ClickHouse import step required. Silver reconstruction
runs via DuckDB. ClickHouse handles live/live-updating writes only.

The v4.1 import work (pmxt full batch: 78,264,878 rows; Jon-Becker sample: 1,000
rows) was completed but is now classified as legacy/optional cache-index tooling.
It does not need to be undone — the data is in ClickHouse and may be useful as
an index — but it is not the blocker for Gate 2.

---

## Architecture Wording Adopted

From `docs/reference/POLYTOOL_MASTER_ROADMAP_v4.2.md` (Database Architecture):

> **ClickHouse handles all live streaming writes. DuckDB handles all historical
> Parquet reads.** They never share data, they never communicate.

This exact split is now reflected in `docs/ARCHITECTURE.md` under the new
"Database Architecture — v4.2 Rule" section.

---

## Files Changed

| File | Change |
|------|--------|
| `docs/ARCHITECTURE.md` | Added "Database Architecture — v4.2 Rule" section with the one-sentence rule and table. Updated authority table to v4.2 + added database split row. Updated data flow diagram to show DuckDB path. Changed governing roadmap ref to v4.2. |
| `docs/PLAN_OF_RECORD.md` | Changed governing roadmap ref to v4.2. Updated Gate 2 primary path row in authority table: DuckDB-first, ClickHouse import off critical path. Updated track alignment section. Updated cross-reference. |
| `docs/ROADMAP.md` | Changed governing roadmap ref to v4.2. Updated authority table to include database split row. Changed Track A "current next step" from bulk import to DuckDB setup. Relabeled BULK_HISTORICAL_IMPORT_V0.md as legacy/optional. |
| `docs/CURRENT_STATE.md` | Changed governing roadmap ref to v4.2. Reclassified "Primary Gate 2 path" label from v4.1 to v4.2. Reframed ClickHouse imports as legacy; noted raw files exist locally for DuckDB. Changed "next immediate step" to DuckDB setup. Noted Silver reconstruction is blocked on DuckDB, not more imports. Updated operator focus and gate status blocks. Updated Track A execution layer section. |
| `docs/runbooks/BULK_HISTORICAL_IMPORT_V0.md` | Added v4.2 legacy/optional notice at top. Updated Status and Purpose to reflect off-critical-path status. Updated Next Steps section to v4.2 DuckDB-first path. |

---

## What Was Downgraded from Primary Path to Optional Legacy Tooling

**SPEC-0018 / BULK_HISTORICAL_IMPORT_V0.md** (ClickHouse bulk import of pmxt,
Jon-Becker, and price_history_2min):

- Was: primary Gate 2 path under v4.1
- Now: optional cache/index layer; not required for Silver reconstruction or
  Gate 2 passage under v4.2
- Retained: all content preserved; runbook remains useful if an operator wants
  a ClickHouse cache of historical data
- Completed work preserved: pmxt full import (78,264,878 rows) and Jon-Becker
  sample import artifacts remain in `artifacts/imports/`; these are still valid
  provenance records

---

## Open Naming Question: price_history_2min vs price_2min

Two names appear in the codebase and docs for what seems to be the same
underlying data series (2-minute Polymarket price history from polymarket-apis):

| Name | Location | Context |
|------|----------|---------|
| `price_history_2min` | SPEC-0018, migration `23_price_history_2min.sql`, `--source-kind price_history_2min` CLI flag, BULK_HISTORICAL_IMPORT_V0.md | ClickHouse table and import tooling |
| `price_2min` | ARCHITECTURE.md (live series column), CURRENT_STATE.md (pending section) | ClickHouse live-updating series |

**Interpretation under v4.2**:
- `price_history_2min` (SPEC-0018): one-time historical download of 2-min
  price data via polymarket-apis, stored as JSONL/Parquet in `/data/raw/`.
  Under v4.2, DuckDB queries this directly; no ClickHouse import needed.
- `price_2min` (live series): a ClickHouse table that receives ongoing 2-min
  price updates from the live polymarket-apis feed. This is in-scope for
  ClickHouse under v4.2 (live writes). Not yet started.

**Resolution**: these are two different use cases for the same API:
- Historical bulk (one-time): DuckDB path, query raw files directly
- Live-updating series: ClickHouse path, write as new data arrives

The naming mismatch is not a code bug today because `price_2min` (live table)
has not been implemented yet. When Silver reconstruction is built, it should
clearly distinguish which path it uses (DuckDB historical vs ClickHouse live).

**Action needed**: when implementing Silver reconstruction, confirm whether it
reads the historical Parquet files (DuckDB) or the live ClickHouse table, and
name variables accordingly. Update SPEC-0018 or create a new spec for the
DuckDB-based reconstruction path.

---

## Commands Run

```bash
# No code changes; docs only
git diff -- docs/PLAN_OF_RECORD.md docs/ARCHITECTURE.md docs/ROADMAP.md \
  docs/CURRENT_STATE.md docs/runbooks/BULK_HISTORICAL_IMPORT_V0.md
```

---

## Test Results

Expected: all five touched docs consistently reflect v4.2 with no claim that
historical ClickHouse bulk import is required for Gate 2.

Verified by review:
- `docs/ARCHITECTURE.md`: new "Database Architecture — v4.2 Rule" section; data
  flow shows DuckDB path; no claim that CH import is required for Gate 2.
- `docs/PLAN_OF_RECORD.md`: Gate 2 row says "ClickHouse bulk import is off the
  critical path under v4.2."
- `docs/ROADMAP.md`: next step is DuckDB; BULK_HISTORICAL_IMPORT_V0.md
  relabeled legacy/optional.
- `docs/CURRENT_STATE.md`: pmxt and Jon-Becker ClickHouse rows labeled legacy;
  Silver reconstruction blocked on DuckDB, not imports; next step is DuckDB.
- `docs/runbooks/BULK_HISTORICAL_IMPORT_V0.md`: v4.2 legacy/optional notice at
  top; Next Steps section updated to DuckDB-first.

No doc claims Gate 2 is closed. No hypothesis validation work reopened.
No Silver reconstruction started. No code files touched.
