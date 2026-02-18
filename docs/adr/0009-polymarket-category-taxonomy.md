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
