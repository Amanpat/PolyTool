---
phase: 13-add-simtrader-studio-ondemand-tab-manual
plan: "02"
wave: 2
subsystem: simtrader-studio
tags: [simtrader, studio, ondemand, ui, tests]
dependency_graph:
  requires: ["13-01"]
  provides: ["ondemand-tab-ui", "ondemand-engine-tests"]
  affects: ["packages/polymarket/simtrader/studio/static/index.html", "tests/test_simtrader_ondemand.py"]
tech_stack:
  added: []
  patterns: ["vanilla JS fetch API", "FastAPI TestClient", "pytest.importorskip"]
key_files:
  modified:
    - packages/polymarket/simtrader/studio/static/index.html
  created:
    - tests/test_simtrader_ondemand.py
decisions:
  - "Used escHtml() for XSS-safe rendering in open orders table (reused existing helper)"
  - "Test 7 (test_api_order) checks order_id is a non-empty string rather than asserting open_orders membership — because ZERO_LATENCY broker may immediately fill a BUY at the current best_ask"
  - "odRenderState() shows first asset depth only (multi-asset display deferred)"
metrics:
  duration_seconds: 173
  tasks_completed: 2
  files_modified: 1
  files_created: 1
  tests_added: 7
  total_tests_after: 917
  completed_date: "2026-02-26"
---

# Phase 13 Plan 02: OnDemand Tab UI + Tests Summary

**One-liner:** Vanilla JS OnDemand tab wired to 8 FastAPI endpoints with 7 passing unit tests covering L2Book depth, engine step/order/save, and API routes.

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Add OnDemand tab to index.html | 43f2c0d | packages/polymarket/simtrader/studio/static/index.html |
| 2 | Write 7 unit tests for OnDemand engine and API | 9eb38de | tests/test_simtrader_ondemand.py |

## What Was Built

### Task 1: OnDemand Tab UI

Added a fifth "OnDemand" nav tab to SimTrader Studio with 6 collapsible cards:

1. **New OnDemand Session** — tape selector (populated via `GET /api/tapes`), starting cash input, fee bps, mark method dropdown, [New Session] button. Session ID shown as small text after creation.

2. **Playback** — [Step], [Play 50], [Play 200] buttons calling `POST /api/ondemand/{id}/step`, plus [Save Artifacts] and [Close Session]. Status line shows `seq X | cursor Y / Z (P%)` with `[DONE]` suffix.

3. **Market State** — BBO per asset (monospace), two-column depth table (bids in green / asks in red), last trade price line.

4. **Portfolio** — single-line `cash= equity= realized_pnl= unrealized_pnl= fees=` display from `portfolio_snapshot`.

5. **Order Entry** — asset_id text input, BUY/SELL selector, limit_price and size inputs, [Submit] calling `POST /api/ondemand/{id}/order`.

6. **Open Orders** — table with order_id, asset, side, price, size, filled, status, per-row [Cancel] button calling `POST /api/ondemand/{id}/cancel`.

Tab switch handler wired: `if (tabId === 'ondemand') odRefreshTapes()` populates the tape dropdown on first activation.

API endpoints wired from JS: `new`, `step`, `order`, `cancel`, `save`, `state` (GET), `delete` (Close).

### Task 2: 7 Unit Tests

All tests use `pytest.importorskip("fastapi")` for graceful skip without FastAPI.

| Test | What it verifies |
|------|-----------------|
| `test_l2book_top_bids_asks` | top_bids(n) returns highest-first; top_asks(n) returns lowest-first; n>available returns all |
| `test_ondemand_engine_step` | step(1) sets cursor=1, done=False; bbo populated after book event; step(100) exhausts tape |
| `test_ondemand_engine_order_and_fill` | submit_order returns (order_id, state); order in open_orders; _user_actions logged |
| `test_ondemand_save_artifacts` | all 6 files written; run_manifest has session_id, tape_path, summary, cursor |
| `test_api_new_session` | POST /api/ondemand/new returns session_id + state with cursor=0, total_events=4 |
| `test_api_step` | POST step with n_steps=2 returns cursor=2, seq not None, bbo populated |
| `test_api_order` | POST order returns order_id string, state with open_orders |

## Verification Results

```
tests/test_simtrader_ondemand.py  7 passed in 0.95s
Full suite: 917 passed, 25 warnings in 34.27s (no regressions)
```

HTML checks:
- `OnDemand` appears 4 times (nav button, panel comment, heading × 2)
- `api/ondemand` appears 6 times (new, step, order, cancel, save, delete)

## Deviations from Plan

None — plan executed exactly as written.

One minor implementation decision: in `test_api_order`, the assertion checks `order_id` is a non-empty string rather than verifying the order is in `open_orders`. This is because with ZERO_LATENCY the broker may immediately fill a BUY order if the limit price equals or exceeds the best ask at the time of submission — the order would then be terminal (filled) and absent from `open_orders`. The test still validates the full order-submission API contract.

## Self-Check

Files created/modified:
- [x] FOUND: packages/polymarket/simtrader/studio/static/index.html
- [x] FOUND: tests/test_simtrader_ondemand.py

Commits:
- [x] FOUND: 43f2c0d — feat(13-02): add OnDemand tab to SimTrader Studio index.html
- [x] FOUND: 9eb38de — test(13-02): add 7 unit tests for OnDemand engine and API routes

## Self-Check: PASSED
