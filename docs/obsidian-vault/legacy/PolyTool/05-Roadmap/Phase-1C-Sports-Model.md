---
type: phase
phase: 1C
status: todo
tags: [phase, status/todo, sports]
created: 2026-04-08
---

# Phase 1C — Track 3: Sports Directional Model (Foundation)

Source: roadmap v5.1 Phase 1C + CLAUDE.md Track 3.

**Runs in parallel with 1A/1B from the start. No capital needed initially — just model training and paper prediction tracking.**

**SimTrader foundations shipped 2026-04-22 (PMXT Deliverable B):** SportsMomentum, SportsFavorite, and SportsVWAP strategies are in STRATEGY_REGISTRY with 20 tests. See `docs/features/simtrader_sports_strategies_v1.md`.

**Data ingestion, logistic regression model, paper tracker, and Grafana dashboard (checklist items 1–5 below) are NOT yet built.** The SimTrader strategies are simulation tools — full Track 1C deployment readiness requires the pipeline items below.

---

## Checklist

- [ ] Historical sports data ingestion (NBA via `nba_api`, NFL via `nfl_data_py`, stored in DuckDB)
- [ ] Probability model v1 — NBA (logistic regression or gradient boosted trees; features: team records, home/away, recent form, rest days)
- [ ] Polymarket price comparison (model vs market signal logging for disagreements)
- [ ] Paper prediction tracker (log every prediction + Polymarket price + actual outcome to ClickHouse)
- [ ] Grafana sports model dashboard (model vs market scatter, cumulative paper PnL, calibration curve)
- [ ] Live deployment after paper validation ($200 capital, Kelly-fraction sizing)

---

## Requirements for Live Deployment

- Paper track record showing consistent edge over 2+ weeks
- Kelly-fraction sizing applied to all position sizes
- ClickHouse `resolution_signatures` data for risk manager

---

## Cross-References

- [[Track-1C-Sports-Directional]] — Strategy description
- [[Risk-Framework]] — Capital progression and validation requirements

