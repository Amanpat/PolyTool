# Dev Log: Adverse-Selection Truth Gap Resolution

**Date:** 2026-03-10
**Branch:** simtrader
**Scope:** adverse_selection module + focused tests only. No MarketMakerV1 math, session-pack, scanner, API/UI, or broad docs touched.

---

## Problem

The `OFISignal` class was labeled "Order-Flow Imbalance (VPIN proxy)" in the module docstring and the OFI class docstring.  Calling a tick-rule mid-price direction signal a "VPIN proxy" conflates two distinct concepts:

| Concept | What it needs | What we have |
|---|---|---|
| **True VPIN** | Trade-tick volume + aggressor-side label per trade | `last_trade_price` events — price only, no volume, no direction |
| **OFI (tick rule)** | Mid-price direction per book update | Available via `price_change` events on `best_bid` / `best_ask` |

The existing code was already correct mechanically, but the "(VPIN proxy)" label obscured the distinction and made audit logs ambiguous.  There was also no explicit sentinel that would surface "VPIN unavailable" in operator dashboards when someone reaches for it.

---

## Decision: data path audit

Event types available in the current tape format:

| Event | Fields | Useful for |
|---|---|---|
| `book` | asset_id, bids[], asks[], seq, ts_recv | L2 snapshot → OFI, MMWithdrawal |
| `price_change` | asset_id / price_changes[], seq, ts_recv | Mid-price direction → OFI |
| `last_trade_price` | **price only** | Trade price history — NOT sufficient for VPIN |
| `tick_size_change` | asset_id, tick_size, seq, ts_recv | Tick sizing only |

`last_trade_price` carries no `size` or `side` field.  True VPIN requires volume-bucketed buy/sell imbalance where each bucket boundary is crossed by a fixed volume of trades — impossible without per-trade volume and aggressor-side label.

**Conclusion: true VPIN is not implementable with current data.  OFI remains OFI.**

---

## Changes

### 1. `packages/polymarket/simtrader/execution/adverse_selection.py`

- **Module docstring**: Removed "(VPIN proxy)" from `OFISignal` entry.  Added `VPINSignal` entry explaining permanent unavailability.
- **`OFISignal` class docstring**: Removed VPIN association.  Added explicit note that it is NOT VPIN and points to `VPINSignal` for the sentinel.
- **New class `VPINSignal`**: Explicit unavailability sentinel.
  - `on_book_update(*args, **kwargs)` — no-op (accepts anything without raising)
  - `check()` → `SignalResult(triggered=False, reason="", metadata={"signal": "vpin", "status": "unavailable", "reason": "..."})`
  - The `reason` field names both missing data dimensions: trade volume and aggressor-side labels.

### 2. `tests/test_adverse_selection.py`

Four new tests added (34 total, all passing):

| Test | What it proves |
|---|---|
| `test_vpin_signal_always_unavailable` | `check()` never triggers; status is "unavailable" |
| `test_vpin_signal_on_book_update_is_noop` | Accepts None, empty, or valid book without raising |
| `test_vpin_unavailability_metadata_explains_data_gap` | metadata.reason contains "volume" and "aggressor" |
| `test_ofi_signal_metadata_is_ofi_not_vpin` | OFISignal metadata signal name is "ofi", not "vpin" |

---

## What was NOT changed

- `OFISignal` logic — unchanged; tick-rule imbalance is a valid and useful OFI signal
- `MMWithdrawalSignal` — unchanged; no concrete bug found
- `AdverseSelectionGuard` — unchanged; still wraps OFI + MMWithdrawal
- `RiskManager`, `LiveRunner` — unchanged
- MarketMakerV1 math, session-pack, watcher, scanner, API/UI — out of scope

---

## Status: true VPIN is NOT implemented

True VPIN remains unavailable.  `VPINSignal` is an explicit sentinel, not a real implementation.  When the tape format is enriched with per-trade volume and aggressor-side labels, replace `VPINSignal` with a real rolling-bucket VPIN (Lee-Ready or bulk-volume classification).

---

## Manual verification

```bash
# All adverse-selection tests (34 tests)
python -m pytest tests/test_adverse_selection.py -v

# Smoke: VPINSignal importable, always unavailable
python -c "
from packages.polymarket.simtrader.execution.adverse_selection import VPINSignal, OFISignal
v = VPINSignal()
r = v.check()
print('VPIN status:', r.metadata['status'])
print('VPIN triggered:', r.triggered)
o = OFISignal()
r2 = o.check()
print('OFI signal name:', r2.metadata['signal'])
"

# Full test suite sanity check
python -m pytest tests/ -x -q --tb=short 2>&1 | tail -5
```
