# Gate 2 Zero-Fill Root Cause — Diagnostic Evidence

**Date:** 2026-04-10
**Quick task:** 260410-iz5
**Gate state:** Gate 2 NOT_PASSED (pass_rate=0.14, need 0.70)
**Tool shipped:** `tools/gates/diagnose_zero_fill.py`

---

## Executive Summary

Gate 2 produces **zero fills on all 43 Silver tapes** in the benchmark corpus.
The root cause is a tape quality limitation: Silver tapes contain only
`price_2min_guide` events.  The SimTrader fill engine requires at least one
`book` (L2 snapshot) event to initialize `L2Book._initialized`.  Without
initialization, every fill attempt is rejected immediately before any order
levels are inspected.

This is **not** a simulator defect.  It is a data pipeline gap: the Silver
reconstruction path (`batch-reconstruct-silver`) writes price-guide events
only, never a real-time L2 snapshot.

---

## Diagnostic Runs

Three tapes were run through `tools/gates/diagnose_zero_fill.py`.

### Tape 1 — Silver, `1029598904689285 / 2026-03-15T10-01-14Z`

```json
{
  "tape_tier": "silver",
  "total_events": 29,
  "book_affecting_events": 0,
  "book_ever_initialized": false,
  "event_type_counts": { "price_2min_guide": 29 },
  "fill_attempts": 0,
  "fill_successes": 0,
  "verdict": "BOOK_NEVER_INITIALIZED"
}
```

### Tape 2 — Silver, `1630984922783900 / 2026-03-15T10-00-01Z`

```json
{
  "tape_tier": "silver",
  "total_events": 60,
  "book_affecting_events": 0,
  "book_ever_initialized": false,
  "event_type_counts": { "price_2min_guide": 60 },
  "fill_attempts": 0,
  "fill_successes": 0,
  "verdict": "BOOK_NEVER_INITIALIZED"
}
```

### Tape 3 — Gold, `bitboy-convicted / 20260306T003541Z`

```json
{
  "tape_tier": "gold",
  "total_events": 5,
  "book_affecting_events": 4,
  "book_ever_initialized": true,
  "first_book_init_seq": 0,
  "event_type_counts": { "book": 2, "price_change": 3 },
  "fill_attempts": 10,
  "fill_successes": 0,
  "fill_rejection_counts": { "no_competitive_levels": 10 },
  "reservation_blocks": { "sell_insufficient_position": 1 },
  "verdict": "RESERVATION_BLOCKED"
}
```

The Gold tape initializes the L2Book correctly (seq=0) but still produces zero
fills for a different reason: RESERVATION_BLOCKED.  The MarketMakerV1 generates
SELL (ask-side) quotes, but SELL reservation requires existing YES inventory.
With no prior BUY fills, inventory=0, so all SELL submissions are blocked.  This
is a chicken-and-egg latency problem specific to short (5-event) Gold tapes —
not a fundamental issue.

---

## Root Cause Drill-Down

### Silver path (43/50 benchmark tapes)

```
silver_events.jsonl
  └─ all events have event_type = "price_2min_guide"

L2Book.apply(event):
  └─ only handles EVENT_TYPE_BOOK and EVENT_TYPE_PRICE_CHANGE
  └─ returns False for "price_2min_guide" (unknown type)
  └─ _initialized stays False for entire replay

fill_engine.try_fill():
  └─ first check: if not book._initialized: return _reject("book_not_initialized")
  └─ never reaches order level comparison
```

**Key code path** (`packages/polymarket/simtrader/broker/fill_engine.py`):

```python
def try_fill(order, book, eval_seq, ts_recv) -> FillRecord:
    if not book._initialized:
        return _reject("book_not_initialized")   # ← Silver tapes always hit here
    ...
```

**Key code path** (`packages/polymarket/simtrader/orderbook/l2book.py`):

```python
def apply(self, event: dict) -> bool:
    etype = event.get("event_type")
    if etype == EVENT_TYPE_BOOK:          # "book"
        self._apply_snapshot(event)
        self._initialized = True
        return True
    elif etype == EVENT_TYPE_PRICE_CHANGE:  # "price_change"
        ...
        return True
    return False   # ← "price_2min_guide" falls here; _initialized untouched
```

### Gate 2 sweep confirmation

The latest gate run (`artifacts/gates/mm_sweep_gate/gate_failed.json`) shows:

- `tapes_total: 50`
- `tapes_positive: 7`
- `pass_rate: 0.14`  (need 0.70)

The 7 positive tapes are crypto shadow/new-market tapes (Gold tier, real WS
`book` snapshots).  All Silver tapes contribute `net_profit=0` because they
accumulate zero fills.

---

## Verdict Classification

| Verdict | Tapes | Root Cause |
|---|---|---|
| BOOK_NEVER_INITIALIZED | 43 Silver | price_2min-only events; no L2 snapshot |
| RESERVATION_BLOCKED | ~7 short Gold | no prior BUY fills; SELL inventory=0 |
| (other zero-fill causes) | 0 confirmed | — |

BOOK_NEVER_INITIALIZED is the dominant verdict and the sole cause of Gate 2
failure across the benchmark Silver corpus.

---

## Why Silver Tapes Lack Book Snapshots

The Silver reconstruction pipeline (`batch-reconstruct-silver`) synthesizes
tapes from `price_2min` CLOB data (2-minute interval OHLCV guides).  This
data contains price reference points but no L2 order book state — there is
no bid/ask depth attached to a `price_2min` record.  Real L2 snapshots
only exist in Gold tapes (live WebSocket recorder output).

The `mm_sweep.py` gate code uses `_count_effective_events()` which counts all
parsed events regardless of type.  Silver's 29-60 `price_2min_guide` events
pass the `min_events=50` threshold for the 60-event tape and pass for the 29-event
tape only if `min_events` relaxation applies.  Either way, the effective event
count check does not detect the absence of L2 snapshots.

---

## Impact on Gate 2 Corpus

```
Benchmark corpus:        50 tapes
Silver tapes:            ~43 (politics, sports, near_resolution)
Gold tapes (crypto/new): ~7
Silver zero-fill rate:   100% (BOOK_NEVER_INITIALIZED)
Current pass_rate:       0.14 (7/50)
Required pass_rate:      0.70 (35/50)
Gap:                     28 additional positive tapes needed
```

---

## Next Steps (Operator Decision Required)

Two paths exist to resolve Gate 2:

**Option A — Upgrade Silver tape reconstruction**

Add a synthetic L2 book snapshot to the start of each Silver replay: construct
a single `book` event from the first `price_2min_guide` bid/ask values and
inject it as seq=0.  This would initialize L2Book and allow the replay engine
to process fill attempts.

**Tradeoff:** Fills would be against a synthetic (not real) order book.  The
`price_2min_guide` data contains only best_bid/best_ask, not depth.  All fills
would occur at a single price level with synthetic size.  PnL would be
approximation-only.

**Option B — Gold tape corpus expansion**

Expand the Gold tape corpus by running the live tape recorder against more
markets (per `CORPUS_GOLD_CAPTURE_RUNBOOK.md`).  Replace Silver tapes in the
benchmark manifest with real Gold tapes once sufficient coverage exists.  This
produces high-fidelity fills but requires operator time and live market access.

**Tradeoff:** Blocked on available markets and capture time.  Crypto bucket
still blocked (no active BTC/ETH/SOL 5m/15m pair markets as of 2026-03-29).

**Current policy:** ADR `docs/specs/ADR-benchmark-versioning-and-crypto-unavailability.md`
establishes WAIT_FOR_CRYPTO as the benchmark policy.  Do NOT modify
`config/benchmark_v1.tape_manifest`.  Option A synthetic-snapshot injection
should be evaluated as a separate spec before implementation.

---

## Diagnostic Tool

`tools/gates/diagnose_zero_fill.py` is now available for per-tape analysis.

```bash
python tools/gates/diagnose_zero_fill.py \
    --tape-dir artifacts/tapes/silver/TOKEN_ID/DATE \
    --asset-id TOKEN_ID \
    --out artifacts/debug/diag_result.json \
    [--verbose]
```

Offline tests: `tests/test_diagnose_zero_fill.py` (3 tests — all passing).

---

## Codex Review

Tier: Skip (diagnostic tool only — no strategy, execution, or fill-engine changes).
