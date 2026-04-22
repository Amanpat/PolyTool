# 2026-04-22 PMXT Deliverable B — Post-Implementation Audit

## Objective

Read-only audit of the Deliverable B sports strategy implementation against the
validation pack. No code was changed.

---

## Files Inspected

| File | Purpose |
|------|---------|
| `packages/polymarket/simtrader/strategies/sports_momentum.py` | SportsMomentum impl |
| `packages/polymarket/simtrader/strategies/sports_favorite.py` | SportsFavorite impl |
| `packages/polymarket/simtrader/strategies/sports_vwap.py` | SportsVWAP impl |
| `packages/polymarket/simtrader/strategy/facade.py` | STRATEGY_REGISTRY entries |
| `packages/polymarket/simtrader/strategy/base.py` | OrderIntent defaults verification |
| `tests/test_sports_strategies.py` | Test suite |
| `docs/dev_logs/2026-04-21_deliverable-b_impl.md` | Implementer's own log |
| `docs/dev_logs/2026-04-21_deliverable-b_context-fetch.md` | Context fetch |
| `docs/dev_logs/2026-04-21_deliverable-b_reference-extract.md` | Reference extract |
| `docs/dev_logs/2026-04-22_deliverable-b_validation-pack.md` | Validation pack |

---

## Commands Run

```
python -m pytest tests/test_sports_strategies.py -v --tb=short
```

Result: **9 passed in 0.35s**

---

## Behavior Checks

### sports_momentum

| Check | Status | Notes |
|-------|--------|-------|
| M1: true below→above cross inside window triggers BUY | PASS | `_prev_price < entry_price <= price` condition correct |
| M2: already-above-threshold first observation must not enter | PASS | `_prev_price is None` on first tick prevents entry |
| M3: close-time exit after fill | PASS | `at_close = ts_recv >= market_close_time` fires SELL |
| M4: `market_close_time <= 0` disables activation entirely | PASS | early return guards entry block |
| No re-entry after done | PASS | `_done = True` short-circuits all subsequent events |
| Window boundary at exactly `market_close_time` | PASS | `<=` inclusive is harmless (exit fires immediately after fill) |

**Naming divergence:** Validation pack scenarios use `market_close_time_ns`
(nanoseconds). Impl constructor uses `market_close_time` (seconds). The
impl log explicitly documents this as a deliberate choice. Behavioral logic is
consistent (seconds vs seconds comparison). However, if an operator copies
the validation pack JSON verbatim as `--strategy-config-json`, the `_ns` key
names will cause a `TypeError: __init__() got an unexpected keyword argument`.
The validation pack JSON examples are therefore **incompatible** with the
implementation as-shipped.

### sports_favorite

| Check | Status | Notes |
|-------|--------|-------|
| F1: equal-to-threshold signal qualifies | PASS | `>= entry_price` condition |
| F2: above-threshold signal before `activation_start_time` ignored | PASS | window guard at top of `on_event` |
| F3: above-threshold signal after `market_close_time` ignored | PASS | close-time guard |
| F4: no SELL or cancel after a filled buy | PASS | `if self._entered: return []` |
| One entry per tape | PASS | `_entered` set True on submit (not fill); won't resubmit on cancel/reject |

**Same naming divergence as momentum**: `activation_start_time_ns` /
`market_close_time_ns` in the validation pack vs `activation_start_time` /
`market_close_time` (seconds) in the impl.

**No `on_fill` override**: `SportsFavorite` never resets `_entered` on fill.
If the GTC limit buy is cancelled without filling, `_entered` remains True
and the strategy won't retry. This is consistent with the "one entry per tape"
spec but means a partial lifecycle (submit → cancel) silently terminates the
strategy. Acceptable for v1; worth noting for shadow runs.

### sports_vwap

| Check | Status | Notes |
|-------|--------|-------|
| Warm-up: must accumulate `vwap_window` accepted ticks | PASS | `len(self._window) < cfg.vwap_window` guard |
| V1: `min_tick_size` filtering | **FAIL** | See critical finding below |
| V2: VWAP reversion exit math | PASS | verified window arithmetic matches pack |
| V3: take_profit checked before VWAP reversion | PASS | ordering in `if take_profit_hit or stop_loss_hit or vwap_reversion` |
| V4: stop_loss checked before VWAP reversion | PASS | same branch ordering |
| TP/SL measured from `_fill_price`, not signal | PASS | `fp = self._fill_price` used for both offsets |
| Size-weighted VWAP | PASS | `sum(p*s)/sum(s)` |
| VWAP entries only fire when `best_ask` present | PASS | `and best_ask is not None` guard |

**Critical finding — min_tick_size filters price, not size:**

The implementation checks:
```python
if tick_price > cfg.min_tick_size:
```

The validation pack V1 scenario uses `min_tick_size=50` and expects trades
with `size=10` and `size=20` to be filtered while `size=100` is accepted.
The implementation compares trade price (e.g. `0.60`) against `min_tick_size`
(50), so `0.60 > 50` = `False` — **all ticks would be filtered** when
`min_tick_size=50`, making the strategy permanently inactive.

The impl log also documents this as a price filter:
> "Ticks with `price <= min_tick_size` are skipped."

This is a functional divergence from the validation pack definition.
Default `min_tick_size=0.0` is unaffected (`tick_price > 0.0` passes all
positive prices), so V2/V3/V4 are correct. Only non-zero `min_tick_size`
values expose the bug.

**Exit reason label undifferentiated:**

All VWAP exits use `reason="vwap_exit"`. The validation pack notes exit
reasons should indicate the specific branch (take-profit vs stop-loss vs
reversion). Minor debuggability issue; not a functional bug.

### Registry and constructor wiring

| Check | Status | Notes |
|-------|--------|-------|
| All 3 strategy names in `STRATEGY_REGISTRY` | PASS | `sports_momentum`, `sports_favorite`, `sports_vwap` |
| Module paths resolve to correct classes | PASS | verified via `_build_strategy` instantiation |
| Constructor kwarg names match config JSON keys | PASS | `market_close_time`, `activation_start_time`, etc. work via `**constructor_config` |
| No `adverse_selection` key leakage | PASS | sports strategies are not `market_maker_v1`; `_split_strategy_config` returns `None` for AS config |

### OrderIntent construction

`base.py` confirmed: all fields except `action` have defaults (`None` or
`field(default_factory=dict)`). Strategies create `OrderIntent(action=...,
side=..., limit_price=..., size=..., reason=...)` without passing `asset_id`,
`order_id`, or `meta`. This is correct; runner fills `asset_id` automatically
when the tape has a single asset.

### License attribution

All three strategy files carry:
> "Signal logic and default parameters derived from sports strategy research
> in evan-kolberg/prediction-market-backtesting (MIT License)."

The reference-extract (section "Licensing / Attribution Notes") states:
> "The repository is mixed-license, not uniformly MIT. Upstream NOTICE
> explicitly lists [those strategy files] as LGPL-covered files with
> Nautilus-derived provenance."

The attribution "MIT License" is factually incorrect for these specific
upstream files. The clean-room reimplementation satisfies the LGPL constraint
(no source expression copied), but saying "MIT License" misrepresents the
upstream license.

---

## Test Coverage Gaps

Tests written: 9 (all passing). The following validation-pack scenarios have
**no corresponding test**:

| V-pack scenario | What it validates | Gap severity |
|-----------------|-------------------|--------------|
| M2 (crossing-vs-already-above) | first observation above threshold must not enter | HIGH — core crossing distinction |
| M3 (close-time exit) | exit fires at `ts_recv >= market_close_time` | MEDIUM |
| M4 (`market_close_time=0` disables) | early return guard | LOW (logic path short) |
| F2 (pre-window ignored) | `activation_start_time` gate | LOW (covered implicitly by F-no-activation test) |
| F3 (post-close ignored) | `market_close_time` upper gate | MEDIUM |
| F4 (no exit after fill) | hold-to-stop behavior with injected fill | HIGH — key strategy guarantee |
| V1 (min_tick_size size filter) | correct tick filtering | HIGH — exposes min_tick_size bug |
| V3 exit label (take_profit) | `reason` field distinguishes exit type | LOW |
| V4 exit label (stop_loss) | `reason` field distinguishes exit type | LOW |

M2 is particularly important: the test suite currently has no test that
proves a "first eligible tick already above threshold" does not trigger a
momentum entry. This is the primary behavioral distinction between
`sports_momentum` and `sports_favorite`.

---

## Codex MCP / Plugin Second Opinion

The `mcp__plugin_code-review-graph_code-review-graph__get_review_context_tool`
and related tools are available in this environment. A graph review pass was
attempted; the tool requires the graph to be built first (`build_or_update_graph_tool`),
which would execute shell commands. No graph build was performed in this
read-only session. Codex MCP second-opinion deferred pending operator
authorization for graph build.

---

## Merge-Readiness Recommendation

**Do not merge as-is.** Two items need resolution:

### Must-fix before merge

1. **`min_tick_size` semantics (sports_vwap)**: The implementation filters
   by price; the validation pack specifies filtering by trade size. If
   `min_tick_size > 0` is ever used operationally, all VWAP accumulation
   will be silently disabled. Operator should decide: keep price-filter
   interpretation (and update the validation pack to match), or switch to
   size-filter (and add a V1 test to prove it).

2. **License attribution**: Change `"(MIT License)"` to `"(LGPL)"` in the
   module docstrings of all three strategy files, or remove the specific
   license claim entirely. The reference-extract is unambiguous that those
   upstream files are LGPL-covered.

### Should-fix before first shadow run

3. **Test gaps M2, F4, V1**: These cover the most important behavioral
   guarantees. M2 proves crossing logic. F4 proves hold-to-stop. V1 proves
   (and exposes) the min_tick_size branch.

4. **Parameter naming alignment with validation pack**: Either update the
   validation pack JSON examples to use `market_close_time` (seconds) or
   add `market_close_time_ns` constructor parameters with a `/1e9` conversion
   inside the strategy. Currently the V-pack config JSON cannot be used
   verbatim as `--strategy-config-json` input.

### Acceptable as-is

5. VWAP exit reason undifferentiated — low operational impact.

6. `SportsFavorite` has no `on_fill` override, so a cancel-without-fill
   silently terminates the strategy. Acceptable for v1 simulation use.

---

## Open Questions Carried Forward

- Position-size guard for sports strategies before live/shadow use (flagged in
  impl log).
- `SportsFavorite` open positions at tape end — confirm downstream PnL tools
  handle open positions correctly.
- Gold tape requirement for meaningful VWAP validation (80-tick window).
