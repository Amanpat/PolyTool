---
type: issue
severity: low
status: open
tags: [issue, stub, status/open]
created: 2026-04-08
---

# Issue: Dead Opportunities Stub

Source: audit Section 7.7 and Core-Library note.

`packages/polymarket/opportunities.py` is a 22-line stub dataclass that is unused.

---

## Details

| File | Lines | Content | Usage |
|------|-------|---------|-------|
| `packages/polymarket/opportunities.py` | 22 | `Opportunity` dataclass only | UNUSED |

---

## Overlap

The stub `Opportunity` class overlaps conceptually with:
- `packages/polymarket/arb.py` — `ArbOpportunity` (active, 601 lines)
- `packages/polymarket/crypto_pairs/opportunity_scan.py` — crypto-specific opportunities (active, 198 lines)

---

## Risk

Low — unused stub doesn't cause bugs. Risk is future confusion if someone imports `Opportunity` expecting real logic.

---

## Resolution

Either:
1. Remove the stub and delete `opportunities.py`
2. Consolidate under `arb.py` as `ArbOpportunity` (already exists)
3. Wire actual opportunity aggregation logic if there's a future use case

---

## Cross-References

- [[Core-Library]] — `opportunities.py` listed as STUBBED
- [[Crypto-Pairs]] — `opportunity_scan.py` (active alternative)

