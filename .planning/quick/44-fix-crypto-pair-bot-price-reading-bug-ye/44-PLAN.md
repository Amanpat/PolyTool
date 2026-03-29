---
quick: "044"
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/polymarket/clob.py
  - packages/polymarket/crypto_pairs/opportunity_scan.py
  - tests/test_clob.py
autonomous: true
---

## Goal

Fix the crypto pair bot bug where `get_best_bid_ask()` always returns ~$0.99 for every
token, causing `paired_cost` to read $1.98 every cycle. Root cause: the Polymarket CLOB
`/book` endpoint returns `asks` sorted descending (highest first), so `asks[0]` is the
worst ask (most expensive), not the best ask (cheapest). The fix replaces the index-zero
lookup with a `min()` over all ask price levels.

---

## Tasks

### Task 1 — Fix `get_best_bid_ask()` in `packages/polymarket/clob.py`

**File:** `packages/polymarket/clob.py` (line ~229)

**Action:**

Replace the single-line ask extraction inside `get_best_bid_ask()`:

```python
# BEFORE (bug: asks[0] = worst ask when sorted DESC)
best_ask = _extract_price(asks[0]) if asks else None

# AFTER (correct: cheapest ask = minimum price across all levels)
best_ask = (
    min(
        (p for a in asks if (p := _extract_price(a)) is not None),
        default=None,
    )
    if asks
    else None
)
```

Leave `best_bid` unchanged — bids are also sorted DESC so `bids[0]` is already the
highest (best) bid for a seller, which is what the buyer comparison needs.

No other logic in this function changes.

---

### Task 2 — Add debug logging in `packages/polymarket/crypto_pairs/opportunity_scan.py`

**File:** `packages/polymarket/crypto_pairs/opportunity_scan.py`

**Action:**

In `compute_pair_opportunity()`, immediately after line 111
(`opp.paired_cost = round(...)`), insert one `logger.debug` call:

```python
logger.debug(
    "pair_price_check market=%s yes_ask=%.4f no_ask=%.4f sum=%.4f",
    market.market_slug,
    opp.yes_ask,
    opp.no_ask,
    opp.paired_cost,
)
```

No other changes to this file. The `logger` object is already present at module scope.

---

### Task 3 — Add `get_best_bid_ask` tests to `tests/test_clob.py`

**File:** `tests/test_clob.py`

**Action:**

Append a new test class `TestGetBestBidAsk` at the end of the file. The class must
mock `ClobClient.fetch_book` (via `monkeypatch`) so no network calls are made.

Required test cases:

1. **asks sorted DESC** — `asks=[{"price":"0.99"},{"price":"0.55"},{"price":"0.54"}]`,
   `bids=[{"price":"0.52"},{"price":"0.50"}]`.
   Assert `best_ask == 0.54` (minimum) and `best_bid == 0.52` (bids[0], max).

2. **asks sorted ASC** — `asks=[{"price":"0.54"},{"price":"0.55"},{"price":"0.99"}]`,
   `bids=[{"price":"0.52"}]`.
   Assert `best_ask == 0.54` (min still correct regardless of sort order).

3. **empty asks** — `asks=[]`, `bids=[{"price":"0.50"}]`.
   Assert `best_ask is None` and `best_bid == 0.50`.

4. **empty bids** — `asks=[{"price":"0.60"}]`, `bids=[]`.
   Assert `best_ask == 0.60` and `best_bid is None`.

Use `monkeypatch.setattr(clob, "fetch_book", lambda token_id: mock_book)` pattern
consistent with the existing `_CaptureHttpClient` style in the file (no `unittest.mock`
import needed — use monkeypatch fixture).

---

## Success Criteria

- `python -m pytest tests/test_clob.py -v --tb=short` passes all new tests (4 added,
  existing 4 unchanged).
- `python -m pytest tests/ -x -q --tb=short` passes with no regressions.
- Manual sanity: `python -m polytool crypto-pair-watch --one-shot` (or equivalent pair
  scan command) no longer reports `paired_cost` near $1.98 for all markets — values
  will vary and most will be above $0.99 (no current entry opportunity), but they will
  reflect real market prices.
- `grep -n "best_ask" packages/polymarket/clob.py` shows the `min(...)` form, not
  `asks[0]`.
