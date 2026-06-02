---
type: module
status: done
tags: [module, status/done, market-selection]
lines: ~800
test-coverage: partial
created: 2026-04-08
---

# Market Selection Engine

Source: audit Section 1.1 — `packages/polymarket/market_selection/` (3+ files, ~800 lines).

Seven-factor composite scorer. Output written to `artifacts/market_selection/YYYY-MM-DD.json`.

---

## Scoring Factors

| Factor | Description | Source |
|--------|-------------|--------|
| `category_edge` | Per-category maker edge from Jon-Becker 72.1M trades | Jon-Becker dataset |
| `spread_opportunity` | Current bid-ask spread attractiveness | Live CLOB |
| `volume` | Log-scaled 24h volume | Live CLOB |
| `competition` | Estimated number of competing market makers | Live CLOB |
| `reward_apr` | LP reward APR if applicable | Gamma API |
| `adverse_selection` | Adverse selection risk score | Derived |
| `time_gaussian` | Time-to-resolution Gaussian decay | Gamma API |

**Adjustments:**
- NegRisk penalty: x0.85 multiplier
- Longshot bonus: +0.15 max for extreme-probability markets

---

## CLI

```bash
python -m polytool market-scan --top 20
```

---

## Cross-References

- [[Core-Library]] — `market_selection/` lives under `packages/polymarket/`
- [[Track-1B-Market-Maker]] — Market Selection Engine used to pick quoting candidates
- [[Database-Rules]] — Jon-Becker data accessed via DuckDB Parquet reads

