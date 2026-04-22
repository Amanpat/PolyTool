---
title: "SimTrader Known Limitations (Verified)"
freshness_tier: CURRENT
confidence_tier: PRACTITIONER
validation_status: UNTESTED
source_family: external_knowledge
source_quality_caution: >
  Composite document. Section A limitations were verified directly against the
  PolyTool SimTrader codebase. Section B limitations were corroborated by external
  backtesting repo analysis (hermes-pmxt / poly-backtesting-oss). Do not attribute
  all claims to a single source.
---

# SimTrader Known Limitations (Verified)

## Purpose

This document defines the execution-model boundary conditions of PolyTool's
SimTrader. Its purpose is realism boundary-setting for strategy evaluation, not
criticism of the simulator architecture. Knowing the limits prevents over-interpreting
replay results. Key limitations covered include: fills do not deplete the book within
a snapshot, the SimTrader queue position model is absent (no time-priority queue
for passive orders), latency is configurable but not stochastic, and no L3 data or
endogenous market impact is modeled.

---

## Section A — Verified Against PolyTool SimTrader Codebase

These limitations were confirmed by direct inspection of the local SimTrader
implementation.

### 1. Fills Do Not Deplete the Book Within a Snapshot

Walk-the-book matching logic exists in BrokerSim. However, within a single
event snapshot (one L2 book update), fills against available depth do not
consume that depth for subsequent orders in the same tick. If two orders are
submitted in the same event cycle, both may fill against the same resting
liquidity without depletion.

**Impact**: Most significant for multi-order strategies or scenarios with
concurrent fills in a single event. Single-order strategies are largely unaffected.

### 2. No Passive-Order Queue Position Modeling

The SimTrader queue position model is absent: a limit order at the best bid
is treated as having instantaneous fill eligibility once price reaches it,
without accounting for orders ahead of it in time priority.

**Impact**: Replay fill rates for passive maker strategies are systematically
optimistic. Gate 2 pass rates for market-maker scenarios should be interpreted
with this in mind.

### 3. Latency Handling Is Present But Not Realistic

The PolyTool SimTrader includes configurable latency parameters. However, the
behavior differs from zero-latency assumptions in some external repos. The exact
latency model (single-value offset vs. stochastic) should be confirmed against
`replay_runner.py` for any specific strategy evaluation.

---

## Section B — Corroborated by External Backtesting Repo Analysis

These limitations were identified in external backtesting repo notes and are
consistent with (or implied by) the PolyTool architecture.

### 4. No L3 Order-Book Data

Only aggregated depth (L2 book) is available. Individual order additions,
cancellations, and modifications at the order level are not visible in replay.
This means order-flow imbalance signals, hidden order detection, and
cancellation-rate analysis cannot be faithfully replicated.

### 5. No Endogenous Market Impact

SimTrader does not model price impact from the strategy's own orders. Large
fills in replay do not move the book against subsequent orders. In live markets,
even modest-size fills in thin prediction markets can shift the best bid/ask.

### 6. No Alpha Decay or Behavioral Response

Participant behavior in response to the strategy's activity is not modeled.
In live markets, systematic quoting patterns attract adversarial order flow;
this effect is absent in replay.

---

## Materiality by Strategy Type

| Strategy Type | Most Affected Limitations |
|---------------|--------------------------|
| High-frequency passive market-maker | 1 (depletion), 2 (queue position) |
| Single-order directional | Largely unaffected by 1–2 |
| Large-size entries in thin markets | 5 (impact), 4 (L3 signals) |
| Copy-wallet replay | 6 (behavioral response) |

---

## Retrieval Keywords

`SimTrader queue position`, `no L3 data`, `no market impact`,
`fills do not deplete book`, `latency modeling`, `execution modeling limitations`,
`walk-the-book`, `alpha decay`
