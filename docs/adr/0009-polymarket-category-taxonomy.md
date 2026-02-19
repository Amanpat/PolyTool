# ADR-0009: Use Polymarket Category Taxonomy As-Is

**Date:** 2026-02-17
**Status:** Accepted
**Roadmap:** 4.5 — Category Segmentation

---

## Context

Polymarket market metadata includes a `category` field that classifies markets
(e.g., `"Sports"`, `"Politics"`, `"Crypto"`, `"Science"`). When building segment
analysis for position attribution, we needed to decide how to group positions by topic.

Two approaches were considered:

1. **Heuristic taxonomy** — detect sport/category from market slug prefix patterns
   (the approach used for `by_league` / `by_sport`).
2. **Polymarket labels as-is** — use the `category` field from Polymarket metadata
   directly, falling back to `"Unknown"` when absent.

---

## Decision

Use **Polymarket's `category` field verbatim** for the `by_category` segment.

- `category_key = (category or "").strip()` → empty/absent → `"Unknown"`
- No heuristic mapping layer between the raw label and the bucket key.
- `"Unknown"` is always an explicit, reported bucket.

---

## Rationale

1. **Source of truth**: Polymarket's own taxonomy is authoritative. Any heuristic
   we invent risks drift when new market types are introduced.

2. **Explicitness**: An `"Unknown"` bucket that is measurable and reportable is
   more useful for diagnosing data gaps than silently absorbing positions into a
   heuristic catch-all.

3. **Simplicity**: No mapping table to maintain. When Polymarket adds a new
   category, the segmentation automatically picks it up.

4. **Orthogonality**: The existing `by_league` / `by_sport` segments use slug-prefix
   heuristics and cover sports-specific sub-classification. `by_category` operates at
   a higher, cross-domain level and serves a different purpose.

---

## Consequences

- **Positive**: Zero maintenance cost for new Polymarket categories.
- **Positive**: `category_coverage` gives an explicit missing-rate metric so operators
  know when to enrich their `market_metadata_map`.
- **Negative**: Category labels depend on Polymarket's naming conventions (e.g.,
  possible inconsistencies between `"sports"` vs `"Sports"`). Callers should ensure
  their metadata pipeline preserves the raw label without case normalization.
- **Mitigation**: The coverage report's `top_unmappable` list surfaces positions
  that lack a category, enabling targeted enrichment.

---

## Alternatives Rejected

**Heuristic category detection from question/slug text** — rejected because it would
need continuous maintenance as Polymarket expands into new domains, and any
heuristic will have edge cases that generate incorrect classifications.

---

## Amendment — Roadmap 4.6: Ingestion & Offline Guarantees

**Date:** 2026-02-18

### Problem Identified

After Roadmap 4.5 shipped the `by_category` segment, `category_coverage` reported
`0.0` despite `market_metadata_coverage` reporting `1.0`. Root cause: the ClickHouse
lifecycle views (`user_trade_lifecycle`, `user_trade_lifecycle_enriched`) do not
include a `category` column. Dossier positions were built from these views without
any join to the table that stores category — so every position was written with
`category: ""`. The self-referential metadata map had nothing to fill.

### Decision

Wire `category` into the dossier build by LEFT JOINing `polymarket_tokens` in the
lifecycle queries inside `packages/polymarket/llm_research_packets.py`.

```sql
LEFT JOIN (
    SELECT token_id, any(category) AS category
    FROM polymarket_tokens
    GROUP BY token_id
) t ON l.resolved_token_id = t.token_id
```

`COALESCE(t.category, '') AS category` is added as the last selected column. When
`polymarket_tokens` has not been populated (i.e., the market backfill pipeline has
never run), `category` gracefully falls back to `""` and coverage reports a high
missing rate with a `>20%` warning.

### Offline Guarantee

`category` is stored locally in ClickHouse (`polymarket_tokens.category`). Populated
once by the market backfill pipeline (`packages/polymarket/backfill.py`), it requires
no network call at scan time or audit time. The dossier `json` carries the category
value directly, so `audit-coverage` and all coverage logic work fully offline.

### Audit Sample Enrichment

A secondary fix in `tools/cli/audit_coverage.py`: audit samples are now enriched with
`_enrich_position_for_audit()` before rendering, applying the same
`normalize_fee_fields()` and derived-field helpers (`_detect_league`, `_detect_sport`,
`_detect_market_type`, `_classify_entry_price_tier`) that the coverage report uses.
This ensures audit samples show the same values the Quick Stats section is computed
from (e.g., `fees_estimated > 0` for positions with `gross_pnl > 0`).
