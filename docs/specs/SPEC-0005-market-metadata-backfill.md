# SPEC-0005 — Market Metadata Backfill

**Status:** Implemented (Roadmap 4.4)
**Author:** PolyTool Contributors
**Date:** 2026-02-17

---

## 1. Purpose

Many position lifecycle records arrive from the dossier export without
`market_slug`, `question`, or `outcome_name` populated.  These fields are
required by the segment-analysis and coverage-quality layers.  This spec
defines a deterministic, local-only backfill step that fills those gaps before
coverage statistics are computed.

---

## 2. Scope

- **In scope:** Backfill of `market_slug`, `question`, `outcome_name` from a
  caller-supplied token/condition mapping.  Reporting of backfill coverage in
  `coverage_reconciliation_report.json` and `.md`.
- **Out of scope:** Network-based metadata fetch, ClickHouse dependency at
  coverage-build time, and any mutation of the dossier artifact on disk.

---

## 3. Definitions

| Term | Meaning |
|------|---------|
| **market metadata fields** | `market_slug`, `question`, `outcome_name` |
| **present** | At least one of the three fields is non-empty after backfill |
| **missing** | All three fields are empty after backfill |
| **backfilled** | One or more fields were absent and filled from the map |
| **ingested** | All present fields were already populated before backfill |
| **unknown** | Fields are still empty after backfill (no mapping found) |
| **unmappable** | A position that is `unknown` but has a token/condition identifier |

---

## 4. Mapping key priority

When looking up a position in the `market_metadata_map`, the identifier is
resolved in this order:

1. `token_id`
2. `resolved_token_id`
3. `condition_id`

The first non-empty value is used as the lookup key.  Positions without any of
these identifiers are skipped silently.

---

## 5. Backfill rules

```
for each position:
    if market_slug AND question AND outcome_name are all non-empty:
        skip (already fully populated)
    identifier = first of (token_id, resolved_token_id, condition_id) that is non-empty
    if identifier is absent:
        skip
    mapping = market_metadata_map.get(identifier)
    if mapping is None:
        skip (unmappable)
    for each of (market_slug, question, outcome_name):
        if field is currently empty AND mapping[field] is non-empty:
            position[field] = mapping[field]
```

Key invariants:

- **Never overwrites** a field that already has a value.
- **Never guesses** — if the map has no entry, the field is left empty.
- **Deterministic** — same map + same positions always produces the same result.
- **No network calls** — the map is provided by the caller from local artifacts.

---

## 6. Coverage section: `market_metadata_coverage`

Added to `coverage_reconciliation_report.json` as a new top-level key.

```json
"market_metadata_coverage": {
    "present_count": 42,
    "missing_count": 8,
    "coverage_rate": 0.84,
    "source_counts": {
        "ingested": 30,
        "backfilled": 12,
        "unknown": 8
    },
    "top_unmappable": [
        {
            "token_id": "0xabc...",
            "count": 3,
            "example": {
                "token_id": "0xabc...",
                "resolved_token_id": null,
                "condition_id": "0xdef...",
                "resolution_outcome": "PENDING"
            }
        }
    ]
}
```

### Field definitions

| Field | Type | Description |
|-------|------|-------------|
| `present_count` | int | Positions with at least one metadata field present |
| `missing_count` | int | Positions where all three fields remain empty |
| `coverage_rate` | float | `present_count / total` (0.0 if no positions) |
| `source_counts.ingested` | int | Present before any backfill was applied |
| `source_counts.backfilled` | int | Present only after backfill filled missing fields |
| `source_counts.unknown` | int | Still missing after backfill (unmappable) |
| `top_unmappable` | list | Up to 10 token/condition IDs with the most unmapped occurrences |

---

## 7. Warning rule

If `missing_rate > 0.20` and `total > 0`, a warning is appended to `warnings`:

```
market_metadata_coverage missing rate is XX.X%
(N/M positions lack market_slug/question/outcome_name).
Consider running with --ingest-markets or providing a market_metadata_map.
```

The same threshold is surfaced in the Markdown report as a callout block.

---

## 8. Report version

`REPORT_VERSION` is bumped to `"1.3.0"` to signal the addition of the
`market_metadata_coverage` section.

---

## 9. Self-referential backfill in scan

`tools/cli/scan.py` builds a `market_metadata_map` from the loaded dossier
positions themselves: any position that already carries at least one metadata
field contributes its identifier → metadata entry to the map.  This allows
sibling records that share a `token_id` or `condition_id` to fill each other's
gaps without any external data source.

This strategy is opt-in via the existing `backfill` config flag (`DEFAULT_BACKFILL = True`).
Pass `--no-backfill` to disable.
