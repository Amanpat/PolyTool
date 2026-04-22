# 2026-04-22 PMXT Deliverable B — Docs Close-out

## Objective

Docs-only close-out for PMXT Deliverable B. All implementation was complete and
committed (`efb6f01`) before this session. This pass fulfills the three-step
completion protocol required by `CURRENT_DEVELOPMENT.md`.

---

## Files Changed

| File | Change |
|---|---|
| `docs/features/simtrader_sports_strategies_v1.md` | Created — full feature doc for three sports strategies |
| `docs/INDEX.md` | Added feature row in Features table; added 7 Deliverable B dev log rows in Recent Dev Logs |
| `docs/CURRENT_DEVELOPMENT.md` | Removed Deliverable B from Paused/Deferred; added to Recently Completed; updated Architect notes |
| `docs/dev_logs/2026-04-22_deliverable-b_closeout.md` | This file |

---

## Completion Protocol Checklist

- [x] `docs/features/simtrader_sports_strategies_v1.md` created
- [x] `docs/INDEX.md` updated (Features table + Recent Dev Logs)
- [x] `docs/CURRENT_DEVELOPMENT.md` — Deliverable B moved to Recently Completed

---

## What Shipped (summary)

Three sports-specific SimTrader strategies committed in `efb6f01`:

| Strategy | Registry Key | Signal |
|---|---|---|
| `SportsMomentum` | `sports_momentum` | Below-to-above crossing in final window |
| `SportsFavorite` | `sports_favorite` | Midpoint at-or-above threshold in activation window |
| `SportsVWAP` | `sports_vwap` | Price below rolling VWAP; exit on reversion or limit |

Supporting changes:
- `facade.py`: three new `STRATEGY_REGISTRY` entries
- `tests/test_sports_strategies.py`: 20 tests (11 new + 4 tightened + 5 baseline)

Test results at commit:
- `tests/test_sports_strategies.py`: 20 passed
- Regression suite (`test_simtrader_strategy`, `test_simtrader_portfolio`, `test_market_maker_v1`): 186 passed

---

## Deferred Items (carried into feature doc)

1. Position-size guard before live/shadow use
2. `SportsFavorite` open-position handling at tape end — downstream PnL tool verification
3. Gold tape requirement for meaningful VWAP validation (80-tick window)
4. Optional: `*_ns` precedence test proving ns field beats seconds field when both > 0
5. Track 1C activation decision remains with Director

---

## Sanity Checks

- `docs/features/simtrader_sports_strategies_v1.md` — file exists, links to all 7 dev logs
- `docs/INDEX.md` Features table — new row present after `simtrader_fee_model_v2.md`
- `docs/INDEX.md` Recent Dev Logs — 7 Deliverable B rows present above fee model rows
- `docs/CURRENT_DEVELOPMENT.md` — Deliverable B absent from Paused/Deferred; present in Recently Completed
- No implementation code touched in this session

---

## Codex Review Summary

- Tier: Skip (docs-only)
- Issues found: 0
- Issues addressed: N/A
