# SPEC-0011: Live Execution Layer (Optional, Gated)

**Status:** Accepted
**Created:** 2026-03-05
**Authors:** PolyTool Contributors

---

## 1. Purpose and scope

Define an optional execution layer for PolyTool that can run validated
operator-supplied strategies with strict risk controls.

Scope includes:
- A dry-run-first execution runner.
- Explicit risk and kill-switch interfaces.
- Gated promotion from replay to controlled live capital stages.

Scope excludes strategy discovery and alpha generation. Research outputs remain
research evidence, not trading signals.

---

## 2. Gate model (hard order)

Required order:

`replay -> scenario sweeps -> shadow -> dry-run live`

Hard rule:
- No live capital before all gates above are passed and documented.

Promotion rules:
1. Replay gate: deterministic results, no schema/logic drift.
2. Scenario sweep gate: strategy survives friction and latency stress cases.
3. Shadow gate: live feed + simulated fills runs cleanly under disconnect/reconnect events.
4. Dry-run live gate: full runner path is stable with zero order submission.
5. Capital stage gate: operator explicitly enables the next stage.

---

## 3. Interfaces

### 3.1 `LiveExecutor`

Execution adapter used by the runner for order lifecycle actions.

Responsibilities:
- Submit/cancel limit intents (no market orders).
- Record acknowledgements, rejects, and fills.
- Emit structured execution events for audit.

### 3.2 `RiskManager`

Pre-trade and runtime guard layer.

Responsibilities:
- Enforce notional, inventory, and daily loss caps.
- Enforce per-market and global rate limits.
- Reject orders that violate policy before submission.

### 3.3 `KillSwitch`

Emergency stop primitive with immediate effect.

Responsibilities:
- Cancel open orders.
- Block new order submission.
- Mark session state as halted with reason and timestamp.

### 3.4 `LiveRunner` (dry-run default)

Top-level orchestrator that wires strategy + risk + executor.

Responsibilities:
- Default to dry-run mode.
- Run gate-aware startup checks.
- Persist run artifacts for audit and reconciliation.

### 3.5 `OrderManager` (Week 2)

Order lifecycle reconciliation between the strategy's desired quotes and the
current open-order set.

Responsibilities:
- Diff `desired_orders` vs `open_orders` by `(asset_id, side)` slot.
- Cancel stale orders (wrong price), subject to min-order-lifetime guard.
- Place new orders for unfilled desired slots.
- Enforce `max_cancels_per_minute` and `max_places_per_minute` via a
  sliding 60-second window; excess actions are skipped and counted.
- Return an `ActionPlan` (pure, no side effects); caller drives execution.

### 3.6 Strategy selection

The `simtrader live` CLI accepts `--strategy <name>` to select from the
`STRATEGY_REGISTRY` in `strategy/facade.py`. Available strategies as of
Week 2:

- `market_maker_v0`: conservative two-sided quoting; default for dry-run live.

Strategy-specific flags on `simtrader live`:
- `--best-bid`, `--best-ask`: current BBO snapshot (required for market_maker_v0)
- `--asset-id`: token ID to quote
- `--inventory-units`: current net inventory (operator-supplied; not persisted across invocations)
- `--mm-tick-size`, `--mm-order-size`: quoting parameters

---

## 4. Non-goals

- No market orders.
- No alpha logic or strategy generation.
- No live execution by default.

---

## 5. Friction checklist (hard requirements)

The following are mandatory before any capital stage:

1. Fees are modeled and logged on every fill path.
2. Spread and slippage are logged per order attempt and per fill.
3. Queue handling is conservative (back-of-queue assumption).
4. Rate limits are enforced with explicit backoff and reject accounting.
5. Latency scenarios are covered in scenario sweeps.
6. WS disconnect/reconnect handling is tested and fails safe.
7. Kill switch can halt order flow immediately.
8. Daily loss cap is enforced by `RiskManager`.
9. Inventory limits are enforced by `RiskManager`.
10. Capital stages are explicit, operator-enabled, and reversible.

---

## 6. Capital stages

- Stage 0: dry-run only (default, no capital).
- Stage 1: minimal live capital cap (operator opt-in).
- Stage 2+: incremental caps only after prior-stage review.

Each stage requires a manual operator enable step and a documented rollback
condition.

---

## 7. Policy alignment

- Research outputs are not signals.
- Execution runs only operator-supplied strategies that passed all required
  gates and risk checks.

---

## References

- `docs/PLAN_OF_RECORD.md`
- `docs/ARCHITECTURE.md`
- `docs/ROADMAP.md`
- `docs/specs/SPEC-0010-simtrader-vision-and-roadmap.md`
