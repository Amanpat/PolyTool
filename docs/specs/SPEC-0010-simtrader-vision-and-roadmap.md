# SPEC-0010: SimTrader – Vision, Architecture, and Phased Roadmap

**Status:** Accepted
**Created:** 2026-02-22
**Authors:** PolyTool Contributors
**Package:** `packages/polymarket/simtrader/`
**CLI entry:** `python -m polytool simtrader`

---

## Table of Contents

1. [Purpose and Motivation](#1-purpose-and-motivation)
2. [What SimTrader Is Not](#2-what-simtrader-is-not)
3. [Core Architectural Concepts](#3-core-architectural-concepts)
4. [Realism Constraints](#4-realism-constraints)
5. [Target Strategy Classes](#5-target-strategy-classes)
6. [Scenario Sweeps and Fault Injection](#6-scenario-sweeps-and-fault-injection)
7. [Research Integration: RAG and Evidence Flow](#7-research-integration-rag-and-evidence-flow)
8. [Optional Future: Signals Store](#8-optional-future-signals-store)
9. [Phased Roadmap](#9-phased-roadmap)
10. [File and Artifact Layout](#10-file-and-artifact-layout)
11. [Constraints and Kill Conditions](#11-constraints-and-kill-conditions)

---

## 1. Purpose and Motivation

PolyTool is a research and reverse-engineering toolchain. Its job is to help understand *how* a
trader behaves — what they buy, when, at what prices, and whether it worked. The existing scan/
dossier pipeline answers those questions retrospectively from the HTTP API.

**SimTrader adds the time-dimension missing from that picture.**

The Polymarket CLOB publishes a live WebSocket feed (the "Market Channel") that carries every
book snapshot and every level-2 delta as it happens. SimTrader taps that feed, persists it as
an immutable local tape, and lets you replay it — as many times as you like, with any
hypothetical order-placement logic applied on top — in a fully deterministic environment.

### Why realism-first?

Prediction-market microstructure is thin and mean-reverting. A simulated strategy that ignores
queue position, partial fills, and tick-level rounding will generate wildly optimistic PnL
figures that cannot survive contact with live data. SimTrader makes conservative assumptions
the **default**, not an option you opt into. Every estimate that could be wrong skews toward
unfavorable (back of queue, worst fill price, full fees).

### Why replay-first, not live-first?

Building against a live WS stream requires infrastructure (reconnection, latency tracking,
clock sync) that distracts from the core validation question: *does this strategy have any
edge at all?* Replay on a recorded tape is zero-latency, zero-risk, and perfectly repeatable.
Shadow mode (live feed, simulated orders, no real trades) comes later, once the book
reconstruction and broker fill model are validated on tape data.

---

## 2. What SimTrader Is Not

| Not | Why excluded |
|-----|-------------|
| A live trading system | No order submission to any exchange. Local-only. |
| An alpha-claim generator | Results are evidence for research, not trading recommendations. |
| A general backtester | Scope is Polymarket binary CLOB only; no options, no futures, no multi-leg. |
| A real-time monitor | Shadow mode will come later; MVP is offline tape only. |
| A multi-asset portfolio optimizer | Single-market scope until MVP3 is shipped and validated. |
| A news/social signal consumer | Optional future (Section 8); not in core scope. |

---

## 3. Core Architectural Concepts

### 3.1 The pipeline

```
WS Market Channel feed
        │
        ▼
  ┌─────────────┐    raw_ws.jsonl    ┌─────────────────────────┐
  │  Recorder   │ ─────────────────► │  artifacts/simtrader/   │
  │ (tape/      │    events.jsonl    │  tapes/<id>/            │
  │  recorder)  │ ─────────────────► │                         │
  └─────────────┘                    └─────────────────────────┘
                                                │
                                         events.jsonl
                                                │
                                                ▼
                                       ┌─────────────┐
                                       │  L2 Book    │  ◄── book snapshot
                                       │ (orderbook/ │  ◄── price_change deltas
                                       │  l2book)    │
                                       └─────────────┘
                                                │
                                         best_bid / best_ask
                                                │
                                                ▼
                                       ┌─────────────┐
                                       │   Broker    │  ◄── strategy order requests
                                       │  (fill sim) │       (limit price, side, size)
                                       └─────────────┘
                                                │
                                        fill / no-fill
                                                │
                                                ▼
                                       ┌─────────────┐
                                       │  Portfolio  │  ◄── fill events
                                       │  (positions │
                                       │   + PnL)    │
                                       └─────────────┘
                                                │
                                        timeline artifacts
                                                │
                                                ▼
                                    artifacts/simtrader/runs/<id>/
                                    ├── best_bid_ask.jsonl
                                    ├── fills.jsonl
                                    ├── portfolio_timeline.jsonl
                                    ├── pnl_summary.json
                                    └── meta.json
```

### 3.2 Component responsibilities

| Component | Module | Responsibility |
|-----------|--------|---------------|
| **Recorder** | `tape/recorder.py` | Connect to WS, write raw frames + normalized events |
| **L2 Book** | `orderbook/l2book.py` | Pure state machine; apply `book`/`price_change` events |
| **Replay Runner** | `replay/runner.py` | Drive L2 Book from events.jsonl; emit best_bid_ask timeline |
| **Broker** (MVP1) | `broker/fills.py` | Simulate limit-order fill probability given L2 state |
| **Portfolio** (MVP2) | `portfolio/state.py` | Track positions, cash, realized + unrealized PnL |
| **Strategy** (MVP3) | `strategies/` | Pluggable logic: decide what orders to place each tick |
| **Sweep Runner** (MVP4) | `sweep/runner.py` | Parameter grid search across strategy configs |

### 3.3 Tape file contract

The tape is the ground truth. Two files, never mutated after writing:

| File | Content | Future-proof? |
|------|---------|---------------|
| `raw_ws.jsonl` | Exact WS frame strings + `frame_seq` + `ts_recv` | Yes — raw bytes never change meaning |
| `events.jsonl` | Normalized events + `parser_version` + `seq` | Yes — `parser_version` guards schema changes |

The `seq` counter in `events.jsonl` is per-event (not per frame). When one WS frame contains
an array of N events, they receive seqs N, N+1, …, N+k-1 in arrival order. This ensures
deterministic ordering even if timestamps collide.

### 3.4 Replay-first, shadow-mode-later

```
Phase today:  tape → replay → fills (simulated, fully offline)
Phase later:  live WS → replay in real-time → shadow fills → artifacts
```

The core L2 Book and Broker components are designed so that the *same code* runs in both
modes. The only difference is the event source: a file iterator vs. a live WS connection.

---

## 4. Realism Constraints

These are defaults, not options. They can be overridden for exploratory experiments but the
override must be explicit and will be flagged in `meta.json` as `realism_mode: relaxed`.

### 4.1 L2 queue position

Polymarket CLOB uses price-time priority. A simulated limit order at a price that already has
resting size is assumed to be **at the back of the queue**. Fill probability is:

```
fill_prob = 0  if best_bid < order_price  (buy order not competitive)
fill_prob = 0  if available_size_at_price < order_size  (queue consumes it first)
fill_prob = 1  if available_size_at_price >= order_size AND price is competitive
               (conservative: we assume we are last in queue, so we need the entire
                resting size plus our size to be consumed)
```

The conservative default means **fills are always underestimated**, never overestimated.

### 4.2 Fill model for IOC (immediate-or-cancel)

IOC orders attempt to match against the current best. Size not immediately fillable is
cancelled. No sweeping through multiple price levels in MVP1 (single-level fill only).
Multi-level sweep comes in MVP1.1.

### 4.3 Price tick rounding

All prices are rounded to the market's current tick size (from `tick_size_change` events or
the snapshot's implied tick). Orders placed at non-tick-aligned prices are rejected by the
broker sim with `reject_reason: tick_misaligned`.

### 4.4 Fees

Default fee model: **2 % on gross profit** (matching PolyTool's existing fee heuristic from
`SPEC-0004`). Configurable via `broker_config.fee_rate_bps`. Fees are deducted from
realized PnL at position close.

### 4.5 Slippage conservatism

When the order book is thin, the simulated broker does NOT assume infinite liquidity at the
best price. It uses the actual `size` field from the L2 snapshot. If the desired trade size
exceeds available size at the best price, the fill is either partial or rejected (depending on
order type).

### 4.6 Clock and latency

Tapes record `ts_recv` (wall-clock time of local receipt). All replay is driven by `seq`
order (not by `ts_recv`) to guarantee determinism. In shadow mode, latency will be estimated
from the `ts_recv` delta between subscribe and first `book` event.

---

## 5. Target Strategy Classes

These are the two initial strategy implementations planned for MVP3. They are chosen because
they are testable with observable, public market data and do not rely on private signals.

### 5.1 Single-market binary complement arb

**Hypothesis:** In binary markets (YES/NO), the sum of the best_ask for YES and the best_ask
for NO occasionally drops below 1.0 − fees. Buying both tokens for combined cost C < 1.0
locks in a guaranteed profit of 1.0 − C at resolution, regardless of outcome.

```
arb_opportunity = best_ask(YES) + best_ask(NO) < 1.0 - fee_threshold
profit_if_filled = 1.0 - (fill_price_YES + fill_price_NO) - fees
```

**Why interesting:** This tests whether the L2 book reconstruction is accurate enough to
identify real mispricing windows, and whether the fill model correctly discards apparent
opportunities that disappear before both legs can be filled.

**Realism notes:**
- Both legs must fill (or neither counts). If one leg fills and the other does not, the
  position is a net loss — the broker sim must handle the leg-cancel case explicitly.
- Slippage from our own order moving the market is not modeled in MVP3 (thin-market caveat
  added to `meta.json`).

**Done means for MVP3:**
- `strategies/complement_arb.py` generates `BUY YES` + `BUY NO` order pairs whenever the
  arb condition triggers.
- Broker sim fills, partially fills, or rejects each leg independently.
- PnL accounts for: fill prices + fees + resolution value (1.0 if held to close).

### 5.2 Copy-wallet strategy

**Hypothesis:** A watched wallet's trades, replayed at the prices visible in the L2 book at
the time those trades were broadcast, would produce a PnL that reveals whether the wallet has
observable execution edge (buying at better-than-market prices) or just good market selection.

```
for each observed trade (from scan/dossier):
    look up events.jsonl at the trade timestamp
    determine best_bid/best_ask at that moment
    compare observed trade price to best available price
    simulate: what would a copy-order at that moment have filled at?
```

**Why interesting:** This bridges the existing scan/dossier pipeline with SimTrader. A dossier
tells us *that* a trader bought YES at 0.55; SimTrader tells us *whether 0.55 was obtainable*
from the public book at that moment.

**Realism notes:**
- The tape must cover the same time window as the trade history. If the tape predates or
  postdates the trades, copy-wallet outputs an `insufficient_tape_coverage` warning.
- Trades from the HTTP API have second-level timestamps; the tape has sub-second `ts_recv`.
  The strategy uses the first event at-or-after the trade timestamp as the reference point.

---

## 6. Scenario Sweeps and Fault Injection

### 6.1 Parameter sweeps (MVP4)

The sweep runner takes a strategy config and a parameter grid and runs the full replay
pipeline for each combination, collecting PnL summaries into a single leaderboard artifact.

```
sweep_config:
  strategy: complement_arb
  params:
    fee_threshold: [0.005, 0.010, 0.015, 0.020]
    max_position_size: [50, 100, 200]
  tape: artifacts/simtrader/tapes/20260222T120000Z_abc123/events.jsonl
```

Output: `artifacts/simtrader/sweeps/<sweep_id>/leaderboard.json` + one `runs/<id>/` per
parameter combination.

### 6.2 Fault injection

Fault injection lets you stress-test a strategy's robustness by introducing artificial
failures into the replay:

| Fault type | Description |
|------------|-------------|
| `delayed_fill` | Delay fill confirmation by N events (simulates latency) |
| `partial_fill` | Cap fill size at X% of requested size |
| `missed_fill` | Drop fill entirely with probability P |
| `gap_injection` | Insert a synthetic gap in the tape (no events for T seconds) |
| `stale_book` | Freeze the L2 book state for N events (simulates WS reconnect) |

Faults are specified in the run config and recorded in `meta.json` under `fault_config`.
A run with any active faults has `realism_mode: fault_injected`.

### 6.3 Run quality labels

Every run's `meta.json` carries a `run_quality` field:

| Quality | Meaning |
|---------|---------|
| `ok` | No events skipped; all fills resolved cleanly |
| `warnings` | Some events skipped (schema drift, missing fields) or fills had issues |
| `degraded` | More than 5% of events were skipped or out-of-order |
| `invalid` | Missing initial book snapshot; results should not be trusted |

Sweeps automatically filter `invalid` runs from the leaderboard.

---

## 7. Research Integration: RAG and Evidence Flow

SimTrader results are **evidence for research, not conclusions**. They feed into the existing
PolyTool RAG pipeline exactly like dossier artifacts: as private, local files that the RAG
index can retrieve when answering questions.

### 7.1 Artifacts as RAG inputs

The files under `artifacts/simtrader/runs/<id>/` are gitignored (per existing `.gitignore`
rule `/artifacts/**`). Once a run completes, you can index its artifacts:

```bash
polytool rag-index --roots "kb,artifacts" --rebuild
```

The RAG index will then surface replay results when queried for relevant topics
(e.g. "complement arb feasibility", "copy wallet execution quality").

### 7.2 Evidence framing

SimTrader outputs must be framed as evidence, not as proof. The recommended pattern for
feeding a SimTrader result into an LLM bundle is to include:

1. `pnl_summary.json` — numbers only, no interpretation
2. `meta.json` — run quality, fault config, realism mode
3. A brief human annotation: tape date range, strategy config, and caveats

The LLM bundle template (from `LLM_BUNDLE_WORKFLOW.md`) will eventually grow a
`simtrader_context` section to formalize this framing.

### 7.3 No trading signals

SimTrader results, like all PolyTool outputs, carry the same `no trading signals` constraint
from `PLAN_OF_RECORD.md` Section 1. A SimTrader run that shows positive simulated PnL on a
historical tape does **not** imply that the same strategy will be profitable live. The
realism constraints (Section 4) are designed to make the simulation conservative, not
prescriptive.

---

## 8. Optional Future: Signals Store

This section describes a possible future extension and is explicitly **out of scope** for all
current milestones. It is documented here to ensure the core architecture does not
inadvertently block it.

### 8.1 What it is

A separate, optional ingest path that captures news and social signals (prediction market
resolution news, social media volume, macro event calendars) and stores them in a time-indexed
local store alongside the WS tape.

```
signals_store/
  <date>/<market_id>/
    news.jsonl        # structured news items with publish_ts
    social.jsonl      # social volume/sentiment snapshots
    calendar.jsonl    # scheduled events (game starts, election days)
```

### 8.2 Relationship to SimTrader

In a signals-aware strategy, the strategy function receives two inputs per tick:
- The current L2 book state (from WS tape replay)
- The current signal state (from signals store, keyed by ts_recv)

This lets you test hypotheses like: "does buying YES 30 minutes before a scheduled event
start outperform random entry timing?"

### 8.3 Relationship to research RAG

News and social signals, once ingested, would be indexed into the local RAG alongside
dossier artifacts, letting the research query path surface signal-correlated events when
reviewing a strategy's historical performance.

### 8.4 Decision point

Build the signals store only if:
- Shadow mode (MVP5) is shipped and validated.
- At least one strategy in MVP3 shows evidence of a timing edge that signals data could
  explain or exploit.
- The additional ingest complexity is justified by research value.

---

## 9. Phased Roadmap

### Overview

| Phase | Name | Status |
|-------|------|--------|
| SimTrader-0 | Tape + Replay Core | **COMPLETE** |
| SimTrader-1 | Broker Fill Simulation | NOT STARTED |
| SimTrader-2 | Portfolio and PnL | NOT STARTED |
| SimTrader-3 | Arb and Copy-Wallet Strategies | NOT STARTED |
| SimTrader-4 | Scenario Sweeps + Fault Injection | NOT STARTED |
| SimTrader-5 | Shadow Mode | NOT STARTED |
| SimTrader-6 | Signals Store Integration | OPTIONAL / FUTURE |

---

### SimTrader-0: Tape + Replay Core [COMPLETE]

**Goal:** Record WS Market Channel data to an immutable tape; replay it deterministically to
reconstruct best bid/ask over time. No strategies, no fills, no PnL.

**Deliverables:**
- [x] `packages/polymarket/simtrader/tape/` — `schema.py` + `recorder.py`
- [x] `packages/polymarket/simtrader/orderbook/l2book.py` — pure L2 state machine
- [x] `packages/polymarket/simtrader/replay/runner.py` — events.jsonl → best_bid_ask timeline
- [x] `tools/cli/simtrader.py` — `record` + `replay` subcommands
- [x] `tests/test_simtrader_replay.py` — 27 tests, all passing
- [x] `packages/polymarket/simtrader/README.md`
- [x] CLI wired into `polytool/__main__.py`
- [x] `artifacts/simtrader/**` confirmed gitignored

**Acceptance criteria:**
1. `pytest -k simtrader` passes with 0 failures.
2. `python -m polytool simtrader record --asset-id <ID> --duration 10` writes
   `raw_ws.jsonl` and `events.jsonl` under `artifacts/simtrader/tapes/`.
3. `python -m polytool simtrader replay --tape <path>/events.jsonl` writes
   `best_bid_ask.jsonl` and `meta.json` under `artifacts/simtrader/runs/<id>/`.
4. Running replay twice on the same tape produces byte-identical output files.
5. `meta.json` `run_quality` is `"ok"` for a clean tape.

**Kill condition:** If Polymarket changes the WS Market Channel protocol in a way that breaks
normalization, increment `PARSER_VERSION` in `tape/schema.py`, add a migration path, and
document in an ADR.

---

### SimTrader-1: Broker Fill Simulation

**Goal:** Simulate whether a hypothetical limit order would fill, given the L2 book state at
each point in the replay. Conservative defaults throughout (Section 4).

**Deliverables:**
- [ ] `packages/polymarket/simtrader/broker/fills.py` — `BrokerFillSim` class
- [ ] `packages/polymarket/simtrader/broker/order.py` — `Order`, `Fill`, `Rejection` dataclasses
- [ ] `packages/polymarket/simtrader/replay/runner.py` updated to accept optional strategy hook
- [ ] `artifacts/simtrader/runs/<id>/fills.jsonl` — emitted when broker is active
- [ ] `tests/test_simtrader_broker.py`

**Fill model (conservative):**
```
For a BUY limit order at price P, size S:
  if P < best_ask:        → no fill (not competitive)
  if P >= best_ask:       → check available size at best_ask
    if available_size < S: → partial fill or no fill (queue position: last)
    if available_size >= S: → full fill at best_ask
```

**Fill event schema:**
```jsonc
{
  "seq": 42,
  "ts_recv": 1708620001.3,
  "order_id": "o-001",
  "asset_id": "...",
  "side": "BUY",
  "requested_price": 0.57,
  "requested_size": 100.0,
  "fill_price": 0.57,
  "fill_size": 100.0,
  "fill_status": "full",   // "full" | "partial" | "rejected"
  "reject_reason": null    // null | "not_competitive" | "tick_misaligned" | "insufficient_size"
}
```

**Acceptance criteria:**
1. `pytest -k broker` passes with 0 failures.
2. A buy order at a price strictly below best_ask produces `fill_status: rejected`.
3. A buy order larger than available size produces `fill_status: partial` (or `rejected`
   if IOC and size < requested).
4. A competitive buy order with sufficient book size produces `fill_status: full` at
   `fill_price == best_ask`.
5. All fills are deterministic: same tape + same strategy config → same fills.jsonl.

**Kill condition:** If the L2 book's `size` field is systematically missing or zero (data
quality issue), document the gap and fall back to a "price-only" fill model with a warning
in meta.json.

---

### SimTrader-2: Portfolio and PnL

**Goal:** Track positions opened/closed by broker fills; compute realized and unrealized PnL
at each book-affecting event.

**Deliverables:**
- [ ] `packages/polymarket/simtrader/portfolio/state.py` — `Portfolio`, `Position` dataclasses
- [ ] `packages/polymarket/simtrader/portfolio/pnl.py` — FIFO realized PnL + MTM unrealized
- [ ] `artifacts/simtrader/runs/<id>/portfolio_timeline.jsonl` — portfolio snapshot per event
- [ ] `artifacts/simtrader/runs/<id>/pnl_summary.json` — end-of-run PnL summary
- [ ] `tests/test_simtrader_portfolio.py`

**Portfolio timeline row schema:**
```jsonc
{
  "seq": 100,
  "ts_recv": 1708620010.0,
  "event_type": "price_change",
  "cash_usdc": 450.0,
  "positions": {
    "<asset_id>": {
      "side": "BUY",
      "size": 100.0,
      "avg_entry_price": 0.57,
      "current_best_bid": 0.58,
      "unrealized_pnl": 1.00
    }
  },
  "realized_pnl": 0.0,
  "total_fees_paid": 0.0
}
```

**Acceptance criteria:**
1. `pytest -k portfolio` passes with 0 failures.
2. Buying 100 YES at 0.57, held to resolution (price → 1.0), shows
   `realized_pnl ≈ 43.0 − fees`.
3. Buying 100 YES at 0.57 and selling at 0.60 shows `realized_pnl ≈ 3.0 − fees`.
4. Portfolio timeline is deterministic: same fills.jsonl → same portfolio_timeline.jsonl.
5. `pnl_summary.json` matches the final row of `portfolio_timeline.jsonl`.

**Kill condition:** If resolution data (needed to close positions at 0.0 or 1.0) is
unavailable for the replayed period, positions remain `PENDING` in the summary. Document
the rate of PENDING closures in `meta.json`.

---

### SimTrader-3: Arb and Copy-Wallet Strategies

**Goal:** Ship the two initial strategy implementations (Section 5) and validate them against
real recorded tapes.

**Deliverables:**
- [ ] `packages/polymarket/simtrader/strategies/__init__.py` — `Strategy` protocol / ABC
- [ ] `packages/polymarket/simtrader/strategies/complement_arb.py` — binary complement arb
- [ ] `packages/polymarket/simtrader/strategies/copy_wallet.py` — copy-wallet replay
- [ ] CLI flags: `python -m polytool simtrader replay --strategy complement_arb --strategy-config <yaml>`
- [ ] `tests/test_simtrader_strategies.py`

**Complement arb parameters (configurable):**
```yaml
strategy: complement_arb
params:
  fee_threshold: 0.010     # minimum net profit after fees to trigger
  max_leg_size_usdc: 100.0 # maximum notional per leg
  cancel_on_partial: true  # cancel surviving leg if partner leg partially fills
```

**Copy-wallet parameters (configurable):**
```yaml
strategy: copy_wallet
params:
  trade_source: artifacts/dossiers/users/<slug>/.../positions.json
  price_tolerance: 0.005   # max price deviation from observed trade price
  size_scale: 1.0          # fraction of observed size to copy
```

**Acceptance criteria:**
1. `pytest -k strategies` passes with 0 failures.
2. On a synthetic tape where YES=0.44 and NO=0.54 (sum=0.98), complement arb fires with
   `fee_threshold=0.010` and generates a pair of BUY orders.
3. On the same tape where YES=0.55 and NO=0.48 (sum=1.03), arb does NOT fire.
4. Copy-wallet strategy replays a known dossier's trades with no crashes and produces
   a valid `pnl_summary.json`.
5. All strategy outputs are deterministic.

**Kill condition:** If no real tape captures a complement arb opportunity after 10+ hours of
recording on liquid markets, document the finding as a research result and defer further
development.

---

### SimTrader-4: Scenario Sweeps and Fault Injection

**Goal:** Run parameter grid searches and inject synthetic faults to test strategy robustness.

**Deliverables:**
- [ ] `packages/polymarket/simtrader/sweep/runner.py` — `SweepRunner`
- [ ] `packages/polymarket/simtrader/sweep/fault.py` — fault injection middleware
- [ ] `tools/cli/simtrader.py` updated with `sweep` subcommand
- [ ] `artifacts/simtrader/sweeps/<sweep_id>/leaderboard.json`
- [ ] `tests/test_simtrader_sweep.py`

**Acceptance criteria:**
1. `python -m polytool simtrader sweep --config <sweep.yaml>` produces one `runs/<id>/` per
   parameter combination and a `leaderboard.json` sorted by `realized_pnl`.
2. `invalid`-quality runs are excluded from the leaderboard automatically.
3. Fault injection (`delayed_fill: 5`) produces detectably different fill counts than the
   same run without faults.
4. Sweep is parallelizable via `--workers N` (same `--workers` pattern as `batch-run`).
5. Leaderboard is deterministic for the same tape and config.

**Kill condition:** If parameter sweeps show that no parameter combination produces
consistent positive PnL on at least 3 distinct tapes, document as a research finding.

---

### SimTrader-5: Shadow Mode

**Goal:** Run the full replay pipeline against a live WS feed in real-time (no real orders
placed). Emit shadow fills and portfolio updates as they would happen live.

**Deliverables:**
- [ ] `packages/polymarket/simtrader/shadow/runner.py` — `ShadowRunner` (live event source)
- [ ] `tools/cli/simtrader.py` updated with `shadow` subcommand
- [ ] Reconnection handling and gap detection
- [ ] `artifacts/simtrader/shadow/<session_id>/` — live output (same schema as replay runs)
- [ ] `tests/test_simtrader_shadow.py` — using mock WS server

**Shadow subcommand:**
```bash
python -m polytool simtrader shadow \
  --asset-id <TOKEN_ID> \
  --strategy complement_arb \
  --strategy-config <yaml> \
  --duration 3600
```

**Acceptance criteria:**
1. `shadow` subcommand starts without errors and connects to WS.
2. Reconnection on WS drop produces a `gap_injection` fault event in `meta.json`.
3. First `book` event initializes the L2 book; `price_change` events update it correctly.
4. Shadow fills match what a tape replay of the same period would produce
   (within timestamp alignment tolerance).
5. Ctrl-C stops the session cleanly and writes `meta.json` with final `run_quality`.

**Kill condition:** If WS connectivity is too unstable to maintain a clean book state for
>80% of a 1-hour session, document the gap rate and defer shadow mode.

---

### SimTrader-6: Signals Store Integration (Optional/Future)

**Goal:** Ingest external time-indexed signals (news, social, calendar) and make them
available to strategy functions as a second input alongside the L2 book state.

See Section 8 for details and the decision criteria that must be met before starting this phase.

**Acceptance criteria (if built):**
1. `signals_store/` ingest pipeline writes structured JSONL with `publish_ts` + `market_id`.
2. Strategy function signature extended to accept `signals_context: dict | None`.
3. At least one test demonstrating a signal-aware strategy variant.
4. Signals indexed into local RAG alongside tape artifacts.

---

## 10. File and Artifact Layout

### Source layout

```
packages/polymarket/simtrader/
  __init__.py
  tape/
    __init__.py
    schema.py          # PARSER_VERSION, event type constants
    recorder.py        # TapeRecorder (WS → raw_ws.jsonl + events.jsonl)
  orderbook/
    __init__.py
    l2book.py          # L2Book state machine
  replay/
    __init__.py
    runner.py          # ReplayRunner (events.jsonl → timeline)
  broker/              # (MVP1)
    __init__.py
    order.py           # Order, Fill, Rejection dataclasses
    fills.py           # BrokerFillSim
  portfolio/           # (MVP2)
    __init__.py
    state.py           # Portfolio, Position
    pnl.py             # FIFO realized PnL, MTM unrealized
  strategies/          # (MVP3)
    __init__.py
    complement_arb.py
    copy_wallet.py
  sweep/               # (MVP4)
    __init__.py
    runner.py          # SweepRunner
    fault.py           # Fault injection middleware
  shadow/              # (MVP5)
    __init__.py
    runner.py          # ShadowRunner (live WS event source)
  README.md
```

### Artifact layout

```
artifacts/simtrader/               # gitignored via /artifacts/**
  tapes/
    <timestamp>_<asset_prefix>/
      raw_ws.jsonl                 # immutable raw frames
      events.jsonl                 # immutable normalized events
  runs/
    <run_id>/
      best_bid_ask.jsonl           # or .csv
      fills.jsonl                  # (MVP1+)
      portfolio_timeline.jsonl     # (MVP2+)
      pnl_summary.json             # (MVP2+)
      meta.json                    # always present
  sweeps/
    <sweep_id>/
      leaderboard.json
      runs/<run_id>/               # one per parameter combination
  shadow/
    <session_id>/                  # (MVP5+)
      ...same as runs/<id>/
```

---

## 11. Constraints and Kill Conditions

### Global constraints (SimTrader scope)

| Constraint | Rationale |
|------------|-----------|
| **No live order submission** | SimTrader is a research tool only; no exchange connectivity |
| **No claims of alpha** | Positive simulated PnL is evidence for further research, not a trading signal |
| **Local-first** | All tapes and artifacts stay on the operator's machine; gitignored |
| **Realism-first defaults** | Conservative fill model; `realism_mode: relaxed` must be explicit |
| **No multi-exchange** | Polymarket CLOB only; no cross-venue arb in scope |
| **No ClickHouse in replay** | Replay is offline-only; no DB dependency |

### Stop conditions

- Do not start SimTrader-1 until SimTrader-0 acceptance criteria are fully verified against
  a real recorded tape (not just synthetic test data).
- Do not start SimTrader-3 (strategies) until SimTrader-2 (portfolio PnL) is verified.
- Do not start SimTrader-5 (shadow mode) until at least one strategy in SimTrader-3 has been
  tested against a real tape of >= 30 minutes duration.
- If any phase produces `run_quality: invalid` on > 50% of real tapes, stop and fix the
  book reconstruction or schema normalization before proceeding.

### Integration with main PolyTool roadmap

SimTrader phases are independent of the main PolyTool roadmap (milestones 0–10). They can
proceed in parallel. The copy-wallet strategy (MVP3) creates a natural integration point with
the scan/dossier pipeline, but that integration is optional and additive — SimTrader does not
require ClickHouse and the scan/dossier pipeline does not require SimTrader.

---

## References

- `packages/polymarket/simtrader/README.md` — quick-start and tape format reference
- `docs/ARCHITECTURE.md` — PolyTool system architecture
- `docs/PLAN_OF_RECORD.md` — mission, constraints, no-trading-signals policy
- `docs/STRATEGY_PLAYBOOK.md` — hypothesis falsification framework
- `docs/specs/SPEC-0004-fee-estimation-heuristic.md` — fee model used by broker sim
- `tools/cli/simtrader.py` — CLI entry point
- `tests/test_simtrader_replay.py` — SimTrader-0 test suite
