# SPEC-0006: Category Segmentation via Polymarket Taxonomy

**Status:** Implemented (Roadmap 4.5)
**Report Version:** 1.4.0

---

## 1. Purpose

Use Polymarket's own `category` field — sourced from local market metadata — to produce
category-level segmentation in the coverage report and segment analysis.
No heuristic taxonomy is invented; Polymarket labels are used as-is.

---

## 2. Category Key Semantics

```
category_key = (position.get("category") or "").strip()
if not category_key:
    category_key = "Unknown"
```

- Labels are taken verbatim from Polymarket metadata (e.g., `"Sports"`, `"Politics"`,
  `"Crypto"`).
- Empty or absent `category` maps to the explicit `"Unknown"` bucket.
- The `"Unknown"` bucket is always present in `by_category`, even when all positions
  carry a category (count = 0 in that case).

---

## 3. Backfill Rules

The `backfill_market_metadata` function is extended to also fill `category`.

| Lookup key       | Can fill `category`? | Notes |
|------------------|----------------------|-------|
| `token_id`       | Yes                  | token-level identifier |
| `resolved_token_id` | Yes               | token-level identifier |
| `condition_id`   | Yes                  | market-level; safe because category is also market-level |

**Invariant:** Backfill never overwrites an existing non-empty `category` value.

### market_metadata_map schema extension

```json
{
  "<token_id or condition_id>": {
    "market_slug": "...",
    "question": "...",
    "outcome_name": "...",
    "category": "Sports"
  }
}
```

The `category` field is optional in the map — positions without it simply remain
unmappable for category purposes.

---

## 4. Coverage Report: `category_coverage` Section

Added in `report_version = "1.4.0"` as a **new top-level key** alongside
`market_metadata_coverage` (which is unchanged).

```json
"category_coverage": {
  "present_count": 142,
  "missing_count": 8,
  "coverage_rate": 0.946667,
  "source_counts": {
    "ingested": 130,
    "backfilled": 12,
    "unknown": 8
  },
  "top_unmappable": [
    {
      "token_id": "<hex>",
      "count": 3,
      "example": {"token_id": "...", "resolution_outcome": "PENDING"}
    }
  ]
}
```

When the best available identifier is market-level only, entries use
`"condition_id"` instead of `"token_id"`.

### Source classification

| source      | Meaning |
|-------------|---------|
| `ingested`  | Position had non-empty `category` before backfill ran |
| `backfilled`| `category` was empty before backfill but filled from `market_metadata_map` |
| `unknown`   | No `category` after backfill (map missing or identifier absent) |

### Warnings

A warning is emitted in `coverage_report.warnings[]` when:

```
category_coverage missing rate > 20%
```

---

## 5. Segment Analysis: `by_category`

Added to `segment_analysis` as a parallel segment alongside `by_league`, `by_sport`, etc.

```json
"by_category": {
  "Sports": {
    "count": 87,
    "wins": 45,
    "losses": 30,
    "profit_exits": 8,
    "loss_exits": 4,
    "win_rate": 0.622642,
    "total_pnl_gross": 142.0,
    "total_pnl_net": 139.16
  },
  "Politics": { "...": "..." },
  "Unknown": { "count": 8, "..." : "..." }
}
```

- `Unknown` bucket is always last.
- All other categories are sorted alphabetically before `Unknown`.
- Win rate denominator excludes `PENDING` and `UNKNOWN_RESOLUTION` (consistent with other segments).

---

## 6. Segment Analysis: `by_market_slug`

Added to `segment_analysis` to support market-level attribution.

```json
"by_market_slug": {
  "top_by_total_pnl_net": [
    {"market_slug": "nfl-kc-buf-2026", "count": 3, "wins": 2, "total_pnl_net": 8.4, "...": "..."}
  ],
  "top_by_count": [
    {"market_slug": "nba-lal-bos-2026", "count": 7, "wins": 4, "total_pnl_net": 5.1, "...": "..."}
  ]
}
```

- `top_by_total_pnl_net`: top 10 markets by net PnL (desc), tie-broken by slug (asc).
- `top_by_count`: top 10 markets by position count (desc), tie-broken by slug (asc).
- Both lists are deterministically ordered.

---

## 7. Markdown Report Extensions

Added in `write_coverage_report` when `write_markdown=True`:

| Section | Description |
|---------|-------------|
| `## Category Coverage` | Coverage rate, source breakdown, unmappable callout |
| `## Top Categories` | Table: top 10 by total_pnl_net with count + win_rate |
| `## Top Markets` | Table: top 10 by total_pnl_net with count + win_rate |

A `> **Warning:**` blockquote is rendered in `## Category Coverage` when missing rate > 20%.

---

## 8. Constraints

- **Local-first**: no network calls. Category comes from positions or `market_metadata_map`.
- **Deterministic**: output ordering is stable across runs with the same input.
- **Non-destructive**: existing `market_metadata_coverage` section is unchanged.
- **Unknown is explicit**: always present, never silently dropped.

---

## 9. Ingestion & Storage (Roadmap 4.6)

### Source table

Category labels are stored in the local ClickHouse table `polymarket_tokens`
(`category String DEFAULT ''`). This table is populated by the market backfill
pipeline in `packages/polymarket/backfill.py` via the Gamma API. No network call
is required at scan time or audit time once the table has been populated.

### Wiring into dossier positions

Both lifecycle queries in `packages/polymarket/llm_research_packets.py` LEFT JOIN
`polymarket_tokens` to pull `category` at dossier-build time:

```sql
LEFT JOIN (
    SELECT token_id, any(category) AS category
    FROM polymarket_tokens
    GROUP BY token_id
) t ON l.resolved_token_id = t.token_id
```

`COALESCE(t.category, '') AS category` is appended as the last selected column
(index 26 in the enriched path, index 17 in the fallback path). The resulting
`position_row` dict includes `"category": category_val`.

### Graceful degradation

When `polymarket_tokens` has never been backfilled (all rows absent), `category`
falls back to `""` for all positions. Coverage reports correctly show a high missing
rate and emit a `>20%` warning, prompting operators to run the market backfill.

### Offline guarantee

Because `category` is written into `dossier.json` at scan time, `audit-coverage`
and all downstream coverage logic operate fully offline with no ClickHouse queries.

### Audit sample enrichment

`tools/cli/audit_coverage.py` applies `_enrich_position_for_audit()` to every
position before sampling. This function mirrors the enrichment that `build_coverage_report()`
applies at scan time:

- Derives `league`, `sport`, `market_type`, `entry_price_tier` via shared helpers
  from `polytool.reports.coverage`
- Calls `normalize_fee_fields()` to compute `fees_estimated` and
  `realized_pnl_net_estimated_fees` from `gross_pnl`

This ensures audit sample rows show the same derived values that Quick Stats
counts are based on, eliminating the historical mismatch between header counts
and per-sample display.
