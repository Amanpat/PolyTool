# Feature: Notional / Size in Audit Coverage Report

## Summary

Before this change, the audit coverage report showed `size/notional: N/A` for every position,
even when the underlying data contained the relevant numbers. The fix wires the existing
dossier.json lifecycle fields (`total_bought`, `total_cost`) through to the audit renderer
under canonical names (`position_size`, `position_notional_usd`). When neither direct field
is available, the notional is derived from `abs(size) × entry_price` and labelled as derived.
When no data exists at all, the report now says `N/A (MISSING_UPSTREAM_FIELDS)` instead of a
silent `N/A`, so analysts know the gap is upstream rather than a rendering bug.

---

## What Appears Where

### In `audit_coverage_report.md` — Position blocks

Each position block now shows:

```
  **entry_price**: 0.55 | **size/notional**: 100.0 shs / 55.0 USD
```

Or, when the notional was derived:

```
  **entry_price**: 0.40 | **size/notional**: 50.0 shs / 20.0 (derived_from_size_price) USD
```

Or, when no upstream data is available:

```
  **entry_price**: N/A | **size/notional**: N/A / N/A (MISSING_UPSTREAM_FIELDS) USD
```

### In `audit_coverage_report.md` — Quick Stats section

A new **Size / Notional Coverage** block is added after Fee Stats:

```markdown
**Size / Notional Coverage**
- notional_missing_count: 0
- notional_derived_count: 2 (estimated from size × entry_price)
```

When `notional_missing_count > 0`, a `⚠` warning marker is shown inline.

### In `audit_coverage_report.json` — `quick_stats` object

Two new integer fields are added to the `quick_stats` object:

```json
{
  "notional_missing_count": 0,
  "notional_derived_count": 2
}
```

---

## Fallback Order for `position_notional_usd`

| Priority | Source field | Label |
|----------|-------------|-------|
| 1 | `position_notional_usd` (already canonical) | `direct` |
| 2 | `initialValue` | `direct` |
| 3 | `total_cost` | `direct` |
| 4 | `abs(position_size) × entry_price` | `derived_from_size_price` |
| 5 | None available | `null` + `notional_missing_reason = MISSING_UPSTREAM_FIELDS` |

## Fallback Order for `position_size`

| Priority | Source field |
|----------|-------------|
| 1 | `position_size` (already canonical) |
| 2 | `total_bought` (lifecycle dossier field) |
| 3 | `size` (trade-level or legacy field) |

---

## Implementation

All enrichment is performed in `_enrich_size_notional(pos)` inside
`tools/cli/audit_coverage.py`, called from `_enrich_position_for_audit()`.
No dossier schema is modified — the canonical fields are computed at read time.

The enrichment is entirely offline and requires no ClickHouse or network access.

---

## Tests

Three offline unit tests in `tests/test_audit_coverage.py`:

| Test | Fixture | Expected |
|------|---------|---------|
| `test_size_notional_case_a_total_bought_total_cost` | `total_bought=100`, `total_cost=55` | size=100.0 shs, notional=55.0 USD, no derivation |
| `test_size_notional_case_b_size_entry_price_derived` | `size=50`, `entry_price=0.40` | size=50.0 shs, notional=20.0 (derived_from_size_price) USD |
| `test_size_notional_case_c_missing_fields` | no size/cost/price | MISSING_UPSTREAM_FIELDS in report |
