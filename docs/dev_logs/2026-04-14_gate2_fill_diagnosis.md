# Gate 2 Zero-Fill Diagnosis

**Date:** 2026-04-14
**Task:** quick-260414-q9i
**Status:** COMPLETE -- root cause confirmed, next actions documented

---

## Summary

Gate 2 currently shows 0 fills across all 9 qualifying benchmark tapes at every
spread multiplier (0.50x through 3.00x). This investigation identifies the precise
root cause, verifies simulator correctness, and documents the unblock path.

**Root cause: H1 confirmed.** Silver tapes contain only `price_2min_guide` events.
The L2 order book never initializes. The fill engine rejects every fill attempt with
`book_not_initialized` before any quote comparison occurs. The simulator and strategy
are both behaving correctly -- the input data is insufficient for fill-based evaluation.

---

## Hypotheses Tested

Three hypotheses were defined before running the diagnostic:

| # | Hypothesis | Verdict |
|---|-----------|---------|
| H1 | Silver tapes have no L2 book data -- L2Book never initializes | **CONFIRMED (primary)** |
| H2 | Strategy quotes too wide due to resolution guard (2.5x spread when mid < 0.10 or > 0.90) | **SECONDARY -- untestable while H1 active** |
| H3 | Chicken-and-egg: no BUY fills -> no inventory -> no SELL submissions | **CONSEQUENCE of H1, not independent cause** |

---

## Diagnostic Evidence

### Tape corpus state

All 50 entries in `config/benchmark_v1.tape_manifest` reference paths under
`artifacts/silver/` (without the `tapes/` infix). Actual Silver tapes are at
`artifacts/tapes/silver/`. The diagnostic script detects this path mismatch and
falls back to scanning `artifacts/tapes/silver/` directly.

```
Tapes discovered : 118
  Qualifying (>= 50 effective events): 9
  Skipped (too short)               : 109
```

All 9 qualifying tapes are Silver tapes. The benchmark manifest crypto bucket
tapes are not on disk (blocked per ADR-benchmark-versioning-and-crypto-unavailability).

### Event-type survey (all 9 qualifying tapes)

```
  price_2min_guide  :  528
```

Zero `book` events. Zero `price_change` events. 528 `price_2min_guide` events across
all 9 tapes -- the only event type present.

### Per-tape diagnostic at 1.0x spread multiplier

| Tape ID | Events | BuyInts | WldFill | NoInit | NoCmpLvl | AvgAskDpth | MidRange | Guard |
|---------|--------|---------|---------|--------|----------|-----------|----------|-------|
| 1087420583993938 | 58 | 0 | 0 | 0 | 0 | 0.00 | 0.0105-0.0110 | YES |
| 1630984922783900 | 60 | 0 | 0 | 0 | 0 | 0.00 | 0.2100-0.2400 | no |
| 2090391531341838 | 58 | 0 | 0 | 0 | 0 | 0.00 | 0.9920-0.9950 | YES |
| 3056182873566198 | 56 | 0 | 0 | 0 | 0 | 0.00 | 0.6900-0.6900 | no |
| 3579436527663349 | 58 | 0 | 0 | 0 | 0 | 0.00 | 0.5215-0.5390 | no |
| 3734545609023866 | 58 | 0 | 0 | 0 | 0 | 0.00 | 0.0005-0.0005 | YES |
| 3912826062982768 | 60 | 0 | 0 | 0 | 0 | 0.00 | 0.0140-0.0155 | YES |
| 6423837128216218 | 60 | 0 | 0 | 0 | 0 | 0.00 | 0.0050-0.0055 | YES |
| 9819820479786057 | 60 | 0 | 0 | 0 | 0 | 0.00 | 0.1600-0.1800 | no |

**Columns:** BuyInts = BUY order intents from strategy; WldFill = intents that
would have crossed book levels; NoInit = intents rejected before any comparison
(book_not_initialized); NoCmpLvl = intents where book initialized but no competitive
ask existed; AvgAskDpth = average number of ask levels at time of BUY intent;
Guard = resolution guard active (mid < 0.10 or > 0.90).

Key observations:
- BuyInts = 0 on all tapes. The strategy never generates an OrderIntent because
  `best_bid` and `best_ask` are always `None` (book never initializes).
- AvgAskDpth = 0.00 on all tapes. No ask levels exist at any point.
- 5/9 tapes have resolution guard active (near-resolution markets, consistent with
  the benchmark near_resolution bucket).

### Tightest-spread check (0.50x multiplier)

Identical results -- zero fills, zero buy intents, zero book initialization.
Spreading tighter makes no difference when H1 is the blocker; the fill engine
never reaches the quote comparison stage.

### Cross-tape aggregate

```
Total qualifying tapes          : 9
Tapes where book initialized    : 0/9
Total BUY intents across tapes  : 0
BUY intents that would fill     : 0
Overall fill opportunity rate   : N/A
```

---

## Mechanism: The Exact Code Path

The failure chain has four steps. Each step is confirmed by reading the relevant
source file directly.

**Step 1 -- Silver tape event content**

Silver tapes are reconstructed from `price_2min` guide data. The reconstructor writes
events with `event_type='price_2min_guide'`. This event type carries a price midpoint
observation but no L2 order book state.

**Step 2 -- L2Book.apply() ignores price_2min_guide**

`packages/polymarket/simtrader/orderbook/l2book.py`:

```python
def apply(self, event: dict) -> bool:
    event_type = event.get("event_type")
    if event_type == EVENT_TYPE_BOOK:       # 'book' snapshot
        ...
    elif event_type == EVENT_TYPE_PRICE_CHANGE:  # 'price_change' delta
        ...
    else:
        return False   # <-- price_2min_guide hits this branch
```

`L2Book._initialized` starts as `False` and is only set to `True` after processing
the first `book` snapshot. Silver tapes never provide one, so `_initialized` stays
`False` for the entire replay.

**Step 3 -- fill_engine.try_fill() rejects immediately**

`packages/polymarket/simtrader/broker/fill_engine.py`:

```python
def try_fill(book: L2Book, order: Order, ...) -> FillResult:
    if not book._initialized:
        return _reject("book_not_initialized")   # <-- returned here, every time
    ...
```

The book check is the first guard in `try_fill()`. Quote comparison never occurs.

**Step 4 -- MarketMakerV1 emits zero intents**

`packages/polymarket/simtrader/strategies/market_maker_v0.py` (inherited by V1):

```python
def compute_quotes(self, best_bid, best_ask, ...):
    if best_bid is None or best_ask is None:
        return []   # <-- returns empty, every tick
```

Since the book never initializes, `best_bid` and `best_ask` are always `None` when
the strategy's `on_event()` is called. The strategy correctly returns zero intents.
This means BuyInts = 0 in the per-tape table, which is why NoInit is also 0 (there
are no intents to reject -- the rejection happens before the strategy is even asked
for quotes).

---

## What Was Not the Root Cause

**H2 (resolution guard):** Five of the nine qualifying tapes have mid prices outside
`[0.10, 0.90]` (mid range as low as 0.0005). The resolution guard would apply 2.5x
spread widening on these tapes. However, H2 cannot be evaluated while H1 is active.
Even if the strategy emitted tight quotes, the fill engine would return
`book_not_initialized` before comparing them to any book level. H2 investigation is
deferred until Gold tapes are available.

**H3 (inventory chicken-and-egg):** The `"Insufficient position to reserve SELL order"`
warning observed in prior mm_sweep runs comes from `portfolio/ledger.py` (~line 419).
This warning is logged but does NOT block order submission. It occurs because BUY fills
never happen (due to H1), so the ledger has no YES position to sell. This is a symptom
of H1, not a contributing cause.

**Simulator bug:** The fill engine is behaving exactly as designed. Refusing to invent
fills from an uninitialized book is correct behavior. This is not a Gate 2 simulator bug.

---

## Manifest Path Mismatch (side finding)

`config/benchmark_v1.tape_manifest` stores paths as:

```
artifacts/silver/TOKEN_ID/DATE/silver_events.jsonl
```

Actual on-disk layout is:

```
artifacts/tapes/silver/TOKEN_ID/DATE/silver_events.jsonl
```

The missing `tapes/` infix causes all 50 manifest entries to fail path resolution.
The diagnostic script handles this with a fallback to `artifacts/tapes/silver/` scan.
The manifest itself should not be modified (WAIT_FOR_CRYPTO policy per
`docs/specs/ADR-benchmark-versioning-and-crypto-unavailability.md`), but the path
discrepancy should be noted if any future tool directly consumes the manifest for
non-benchmark purposes.

---

## Recommended Next Actions

### 1. PRIMARY UNBLOCK -- Gold tape capture

Gold tapes (recorded from live WebSocket) contain full L2 book snapshots
(`event_type='book'`) and incremental deltas (`event_type='price_change'`). These are
the only tape tier that will allow `L2Book._initialized` to become `True` during replay.

Run the Gold capture runbook:
```
docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md
```

Gate 2 requires 50 qualifying Gold tapes (>= 50 effective events each). The tape
recorder command is:
```
python -m polytool simtrader shadow --market <slug> --duration 300
```

### 2. SECONDARY INVESTIGATION -- H2 diagnostic with Gold tapes

Once Gold tapes exist, re-run:
```
python tools/gates/gate2_fill_diagnostic.py --tapes-dir artifacts/tapes/gold
```

This will determine whether the A-S resolution guard (2.5x spread widening for
near_resolution markets) prevents fills even when the book is populated. The answer
matters for strategy parameter tuning but cannot be known until H1 is resolved.

### 3. Do not weaken gates or modify fill logic

The fill engine is correct. The gate thresholds (>= 70% positive net PnL, >= 50
effective events) are correct. The tape eligibility criteria are correct. The problem
is data quality, not validation logic. Fix the data, not the validator.

---

## Files Changed

| File | Action |
|------|--------|
| `tools/gates/gate2_fill_diagnostic.py` | Created -- 797-line diagnostic script |
| `docs/dev_logs/2026-04-14_gate2_fill_diagnosis.md` | Created -- this file |

## Codex Review

Tier: Skip (diagnostic script, no execution logic, no live-capital paths).

---

## Open Questions

1. **H2 severity:** After Gold tape capture, will the resolution guard prevent fills on
   near_resolution markets even with a populated book? If yes, the A-S parameter sweep
   range for `min_spread`/`max_spread` may need adjustment for that bucket. This is a
   Gate 2 parameter question, not a gate threshold question.

2. **Manifest path:** Should `config/benchmark_v1.tape_manifest` be corrected to use
   `artifacts/tapes/silver/` paths? Modifying the manifest requires operator decision
   (it is a locked file per benchmark policy). Raise if any tool breaks due to the mismatch.
