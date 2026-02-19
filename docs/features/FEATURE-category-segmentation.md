# Feature: Category Segmentation

Roadmap 4.5 adds category-level segmentation to the coverage report, using Polymarket's own `category` field from local market metadata. This lets you see your PnL and win rate broken down by topic (Sports, Politics, Crypto, etc.) without any invented taxonomy — the labels come directly from Polymarket and fall back to `"Unknown"` when absent.

---

## What changed

### 1. Report version bumped to 1.4.0

`coverage_reconciliation_report.json` now carries `"report_version": "1.4.0"`.

### 2. Category backfill

`backfill_market_metadata` now also fills the `category` field from the
`market_metadata_map`. The same priority order applies:
`token_id` → `resolved_token_id` → `condition_id`.

Unlike `outcome_name`, `category` is market-level and is safe to fill from
`condition_id` lookups.

Backfill never overwrites an existing non-empty `category`.

### 3. New `category_coverage` top-level section

```json
"category_coverage": {
  "present_count": 142,
  "missing_count": 8,
  "coverage_rate": 0.946667,
  "source_counts": {"ingested": 130, "backfilled": 12, "unknown": 8},
  "top_unmappable": [...]
}
```

`top_unmappable` entries use `token_id` for token-level rows and
`condition_id` when only market-level identifiers are available.

A warning is added to `coverage_report.warnings[]` when missing rate exceeds 20%.

### 4. `segment_analysis.by_category`

New segment in `segment_analysis` grouping positions by Polymarket category:

```json
"by_category": {
  "Politics": {"count": 42, "wins": 20, "win_rate": 0.512820, "total_pnl_net": 31.2},
  "Sports":   {"count": 87, "wins": 45, "win_rate": 0.622642, "total_pnl_net": 62.4},
  "Unknown":  {"count": 8,  "wins": 2,  "win_rate": 0.5,      "total_pnl_net": -3.1}
}
```

`"Unknown"` is always present and always last. All other categories are alphabetically sorted.

### 5. `segment_analysis.by_market_slug`

Top-N market attribution tables:

```json
"by_market_slug": {
  "top_by_total_pnl_net": [...],
  "top_by_count": [...]
}
```

Each list contains up to 10 entries with the full segment bucket metrics plus `market_slug`.

### 6. Markdown report extensions

Three new sections are rendered when `write_coverage_report(..., write_markdown=True)`:

- **`## Category Coverage`** — coverage rate, source breakdown, unmappable callout
- **`## Top Categories`** — table of top 10 categories by total_pnl_net
- **`## Top Markets`** — table of top 10 markets by total_pnl_net

A `> **Warning:**` blockquote is rendered in Category Coverage when missing rate > 20%.

---

## How to use

### Include `category` in your market_metadata_map

When building a map for backfill, add `category` alongside slug/question/outcome_name:

```python
market_metadata_map = {
    "tok-abc123": {
        "market_slug": "nfl-kc-buf-2026-01-19",
        "question": "Will Kansas City Chiefs win?",
        "outcome_name": "Yes",
        "category": "Sports",
    }
}
```

### Self-referential backfill (scan pipeline)

In `python -m polytool scan`, the map is built automatically from positions that already
carry metadata. If some positions include `category`, their values will fill sibling
positions sharing the same identifier.

### Reading the report

```python
report = json.loads(Path("coverage_reconciliation_report.json").read_text())

# Category coverage
cc = report["category_coverage"]
print(f"Category coverage: {cc['coverage_rate']:.1%}")
print(f"Unknown: {cc['source_counts']['unknown']} positions")

# Category segment
by_cat = report["segment_analysis"]["by_category"]
for cat, metrics in by_cat.items():
    print(f"{cat}: count={metrics['count']}, win_rate={metrics['win_rate']:.1%}")
```

---

## Constraints

- Local-first: no network calls. Category comes from positions or `market_metadata_map`.
- Deterministic: output ordering is stable across runs with the same input.
- Non-destructive: `market_metadata_coverage` is unchanged.
