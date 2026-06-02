---
type: strategy
track: 1C
tags: [strategy, sports, status/todo]
created: 2026-04-08
---

# Track 1C — Sports Directional Model

Source: CLAUDE.md "Track 3 — Sports Directional Model" + roadmap Phase 1C.

**Purpose:** Medium-term model-driven revenue track. Runs in parallel with 1A/1B from the start. No capital needed initially — just model training and paper prediction tracking.

---

## Strategy Description

Uses freely available sports data and probability modeling to find disagreements between model probability and Polymarket prices.

- Download NBA data via `nba_api`, NFL via `nfl_data_py`
- Train probability model (logistic regression or gradient boosted trees)
- Compare model output to Polymarket prices
- Log signals where model disagrees by threshold (e.g., model 65%, market 55%)
- Build paper prediction track record before capital deployment

---

## Current Status

**SimTrader strategy foundations shipped (PMXT Deliverable B, 2026-04-22).** Three sports strategies are live in SimTrader:

- `SportsMomentum` — Final period momentum (entry ≥0.80, TP 0.92, SL 0.50, final 30 min)
- `SportsFavorite` — Late favorite limit hold (entry ≥0.90, hold to resolution)
- `SportsVWAP` — VWAP reversion (80-tick rolling window, entry 0.8¢ below VWAP)

All three registered in `STRATEGY_REGISTRY`. 20 tests passing. Feature doc: `docs/features/simtrader_sports_strategies_v1.md`.

**Broader Phase 1C pipeline (data ingestion, logistic regression model, paper tracker, Grafana) is NOT yet built.** These strategies provide SimTrader replay foundations — they do not constitute live-deployment readiness for Track 1C. Sports category data exists in the Jon-Becker dataset (2.23pp maker edge for sports), which provides useful priors.

---

## Phase 1C Checklist (from roadmap)

- [ ] Historical sports data ingestion (NBA, NFL)
- [ ] Probability model v1 — NBA (logistic regression or gradient boosted trees)
- [ ] Polymarket price comparison (model vs market signal logging)
- [ ] Paper prediction tracker (ClickHouse log with outcomes)
- [ ] Grafana sports model dashboard
- [ ] Live deployment after paper validation ($200 capital, Kelly-fraction sizing)

---

## Requirements for Live Deployment

- Paper track record showing consistent edge over 2+ weeks
- Kelly-fraction sizing applied to all position sizes
- ClickHouse `resolution_signatures` data for risk manager

---

## Cross-References

- [[Risk-Framework]] — Capital progression and validation requirements
- [[Phase-1C-Sports-Model]] — Phase checklist detail
