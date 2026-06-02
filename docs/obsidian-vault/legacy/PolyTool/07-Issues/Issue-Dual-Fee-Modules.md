---
type: issue
severity: medium
status: open
tags: [issue, fees, status/open]
created: 2026-04-08
---

# Issue: Dual Fee Calculation Modules

Source: audit Section 7.1.

Two separate implementations of the same Polymarket fee formula exist in the codebase.

---

## Affected Files

| Module | Location | Implementation | Precision |
|--------|----------|----------------|-----------|
| `fees.py` | `packages/polymarket/fees.py` | Float-based quadratic fee curve | `float` |
| `fees.py` | `packages/polymarket/simtrader/portfolio/fees.py` | Decimal-based quadratic fee curve | `Decimal` |

---

## Formula

Both implement: `fee = fee_rate × notional × (1 - notional × fee_rate)` (quadratic curve).

---

## Risk

If the fee model changes (e.g., Polymarket adjusts their fee structure), both files must be updated in sync. A drift between them would cause replay PnL to disagree with live fee computation.

The `Decimal`-based SimTrader version is more precise for financial calculations, but the float version in the core library is used by `pnl.py` and other non-SimTrader paths.

---

## Resolution Options

1. Consolidate into a single module with both float and Decimal APIs
2. Have `packages/polymarket/fees.py` delegate to `simtrader/portfolio/fees.py` with precision parameter
3. Document the split formally as intentional (float for speed, Decimal for accuracy)

---

## Cross-References

- [[Core-Library]] — `fees.py` in core library
- [[SimTrader]] — `simtrader/portfolio/fees.py`

