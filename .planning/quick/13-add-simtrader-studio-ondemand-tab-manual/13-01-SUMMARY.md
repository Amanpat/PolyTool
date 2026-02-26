---
phase: 13-add-simtrader-studio-ondemand-tab-manual
plan: "01"
subsystem: simtrader-studio
tags: [simtrader, studio, ondemand, fastapi, l2book, broker]
dependency_graph:
  requires:
    - packages/polymarket/simtrader/orderbook/l2book.py
    - packages/polymarket/simtrader/broker/sim_broker.py
    - packages/polymarket/simtrader/portfolio/ledger.py
    - packages/polymarket/simtrader/studio/app.py
  provides:
    - OnDemandSession tape-playback engine
    - OnDemandSessionManager in-memory registry
    - 8 /api/ondemand/* FastAPI routes
    - L2Book.top_bids(n) / L2Book.top_asks(n) depth methods
  affects:
    - packages/polymarket/simtrader/studio/app.py
    - packages/polymarket/simtrader/orderbook/l2book.py
tech_stack:
  added: []
  patterns:
    - Factory-pattern FastAPI app with closure-scoped session manager
    - Fresh PortfolioLedger per get_state() call (snapshot pattern)
    - ZERO_LATENCY SimBroker for interactive manual order submission
key_files:
  created:
    - packages/polymarket/simtrader/studio/ondemand.py
  modified:
    - packages/polymarket/simtrader/orderbook/l2book.py
    - packages/polymarket/simtrader/studio/app.py
decisions:
  - PortfolioLedger re-instantiated on every get_state() for live snapshot (O(events) acceptable for interactive sessions)
  - OnDemandSessionManager stored as closure variable in create_app() (not on app.state) for simplicity
  - ZERO_LATENCY broker so submitted orders are immediately eligible for fills on next step()
  - limit_price validated in (0, 1] at API boundary for Polymarket binary market constraint
metrics:
  duration: "346s"
  completed: "2026-02-26"
  tasks_completed: 3
  files_modified: 3
---

# Phase 13 Plan 01: OnDemand Engine Backend Summary

**One-liner:** Tape-playback OnDemand engine with SimBroker/L2Book/PortfolioLedger wiring and 8 FastAPI routes for interactive session management.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Add top_bids/top_asks to L2Book | 4fb6af4 | l2book.py |
| 2 | Implement OnDemandSession and session manager | 646b503 | studio/ondemand.py (new) |
| 3 | Add OnDemand API routes to app.py | c2a6218 | studio/app.py |

## What Was Built

### L2Book depth methods (Task 1)

Two new public methods added after `best_ask` property in `L2Book`:

- `top_bids(n=5)`: returns top N bid levels sorted by price descending (best bid first), each as `{"price": float, "size": float}`.
- `top_asks(n=5)`: returns top N ask levels sorted by price ascending (best ask first), same shape.
- Both return empty list when the book has no levels (before any snapshot arrives).

### OnDemandSession class (Task 2)

`packages/polymarket/simtrader/studio/ondemand.py` — complete new module:

- `__init__`: loads `events.jsonl` from tape_path, sorts by seq, detects all asset_ids, creates one `L2Book` per asset, instantiates `SimBroker(ZERO_LATENCY)`.
- `step(n)`: advances cursor by n events, applies L2Books (both legacy `price_change` and batched `price_changes[]`), calls `broker.step()`, tracks `last_trade_price`, appends timeline rows for portfolio ledger.
- `submit_order(asset_id, side, limit_price, size)`: calls broker at current seq, logs wall-clock user_action, returns (order_id, state).
- `cancel_order(order_id)`: calls broker cancel, logs action, returns state.
- `get_state()`: returns `{session_id, cursor, total_events, done, seq, ts_recv, bbo, depth, last_trade_price, open_orders, portfolio_snapshot}`.
- `save_artifacts(session_dir)`: writes 6 files: `user_actions.jsonl`, `orders.jsonl`, `fills.jsonl`, `ledger.jsonl`, `equity_curve.jsonl`, `run_manifest.json`.
- `OnDemandSessionManager`: create/get/delete registry (KeyError on missing get, silent on missing delete).

### FastAPI routes (Task 3)

8 new routes added inside `create_app()` after the existing `/api/run` route:

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/ondemand/new` | Create session from tape_path + config |
| GET | `/api/ondemand/{id}/state` | Get current session state |
| POST | `/api/ondemand/{id}/step` | Advance cursor by n_steps (1-1000) |
| POST | `/api/ondemand/{id}/play` | Advance cursor by n_steps (1-500, default 50) |
| POST | `/api/ondemand/{id}/order` | Submit limit order with validation |
| POST | `/api/ondemand/{id}/cancel` | Cancel open order |
| POST | `/api/ondemand/{id}/save` | Write artifacts to disk |
| DELETE | `/api/ondemand/{id}` | Remove session from registry |

`OnDemandSessionManager` is stored as a closure variable in `create_app()`.

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

- `python -m pytest tests/test_simtrader_arb.py tests/test_simtrader_strategy.py -x -q` — 68 passed, 0 failures (no regressions).
- `python -c "from packages.polymarket.simtrader.studio.app import create_app; app = create_app(); print('app OK')"` — imports clean.
- L2Book `top_bids(2)` returns `[{price:0.52,...}, {price:0.51,...}]` and `top_asks(2)` returns `[{price:0.53,...}, {price:0.54,...}]` — correct sorted order.
- All 8 `/api/ondemand/*` routes confirmed registered in route list.

## Self-Check: PASSED

Files created/modified:
- FOUND: packages/polymarket/simtrader/orderbook/l2book.py (modified)
- FOUND: packages/polymarket/simtrader/studio/ondemand.py (created)
- FOUND: packages/polymarket/simtrader/studio/app.py (modified)

Commits confirmed:
- 4fb6af4: feat(13-01): add top_bids/top_asks depth methods to L2Book
- 646b503: feat(13-01): implement OnDemandSession and OnDemandSessionManager
- c2a6218: feat(13-01): add 8 /api/ondemand/* routes to SimTrader Studio
