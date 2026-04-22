# 2026-04-22 Deliverable B Validation Pack

## Scope

Read-only validation pack for PMXT Deliverable B full implementation.

This pack uses only:

- `docs/dev_logs/2026-04-21_deliverable-b_reference-extract.md`
- `docs/dev_logs/2026-04-21_deliverable-b_context-fetch.md`
- local SimTrader strategy/test interfaces

It does not depend on upstream source expression, helper layout, or class
structure. No implementation or test files were changed.

## Repo State

`git status --short` at session start:

```text
 M packages/polymarket/simtrader/strategy/facade.py
?? docs/dev_logs/2026-04-21_deliverable-b_context-fetch.md
?? docs/dev_logs/2026-04-21_deliverable-b_impl.md
?? docs/dev_logs/2026-04-21_deliverable-b_reference-extract.md
?? packages/polymarket/simtrader/strategies/sports_favorite.py
?? packages/polymarket/simtrader/strategies/sports_momentum.py
?? packages/polymarket/simtrader/strategies/sports_vwap.py
?? tests/test_sports_strategies.py
```

These changes were treated as pre-existing and were not modified by this work
unit.

## Files Inspected

- `AGENTS.md`
- `docs/dev_logs/2026-04-21_deliverable-b_reference-extract.md`
- `docs/dev_logs/2026-04-21_deliverable-b_context-fetch.md`
- `tests/test_simtrader_strategy.py`
- `packages/polymarket/simtrader/strategy/base.py`
- `packages/polymarket/simtrader/strategy/runner.py`
- `packages/polymarket/simtrader/orderbook/l2book.py`
- `packages/polymarket/simtrader/tape/schema.py`
- `packages/polymarket/silver_reconstructor.py`
- `tests/test_market_maker_v1.py`

## Commands Run

### Workspace safety checks

Command:

```powershell
git status --short
```

Output:

```text
 M packages/polymarket/simtrader/strategy/facade.py
?? docs/dev_logs/2026-04-21_deliverable-b_context-fetch.md
?? docs/dev_logs/2026-04-21_deliverable-b_impl.md
?? docs/dev_logs/2026-04-21_deliverable-b_reference-extract.md
?? packages/polymarket/simtrader/strategies/sports_favorite.py
?? packages/polymarket/simtrader/strategies/sports_momentum.py
?? packages/polymarket/simtrader/strategies/sports_vwap.py
?? tests/test_sports_strategies.py
```

Command:

```powershell
git log --oneline -5
```

Output:

```text
504e7b7 Fee Model Overhaul
42d9985 docs: add AGENTS.md and CURRENT_DEVELOPMENT.md for workflow refresh
2dc03a7 docs(quick-260415-rdy): complete Loop D feasibility -- add plan artifact and update STATE.md
b01c80a docs(quick-260415-rdp): complete Loop B phase 0 feasibility -- add plan artifact and update STATE.md
9f09690 docs(quick-260415-rdy): complete Loop D feasibility plan -- add SUMMARY and update STATE.md
```

Command:

```powershell
python -m polytool --help
```

Output excerpt:

```text
PolyTool - Polymarket analysis toolchain

Usage: polytool <command> [options]
       python -m polytool <command> [options]
```

Exit status: `0`

### Read-only context fetch commands

Commands used were read-only `Get-Content` and `Select-String` calls against the
files listed above. No tests were run and no implementation files were edited.

## Validation Conventions

- `ASSET_ID = "test-asset-001"`
- Call `strategy.on_start(ASSET_ID, Decimal("1000"))` before the event sequence.
- Quote-driven scenarios use the midpoint of the current best bid / best ask as
  the signal value.
- Tape timestamps are local normalized `ts_recv` seconds; time-window config
  values remain nanoseconds.
- Event dicts below follow the local normalized tape schema used by
  `StrategyRunner`.
- Exit scenarios can be validated two ways:
  - end-to-end with `StrategyRunner`, where the entry fill should occur against
    the visible book if the implementation uses the expected executable order
    semantics
  - direct strategy-unit testing, where a synthetic `on_fill(...)` is injected
    after the BUY decision before the exit-driving event is processed

## sports_momentum

### Synthetic scenarios

#### M1 - True threshold cross inside final window

Config overrides:

```json
{
  "trade_size": 25,
  "market_close_time_ns": 120000000000,
  "final_period_minutes": 1,
  "entry_price": 0.80,
  "take_profit_price": 0.92,
  "stop_loss_price": 0.50
}
```

Event sequence:

```json
{"parser_version":1,"seq":0,"ts_recv":59.0,"event_type":"book","asset_id":"test-asset-001","bids":[{"price":"0.78","size":"100"}],"asks":[{"price":"0.80","size":"100"}]}
{"parser_version":1,"seq":1,"ts_recv":60.0,"event_type":"price_change","asset_id":"test-asset-001","changes":[{"side":"BUY","price":"0.79","size":"100"},{"side":"SELL","price":"0.80","size":"0"},{"side":"SELL","price":"0.83","size":"100"}]}
{"parser_version":1,"seq":2,"ts_recv":61.0,"event_type":"price_change","asset_id":"test-asset-001","changes":[{"side":"SELL","price":"0.83","size":"0"},{"side":"SELL","price":"0.84","size":"100"}]}
```

Signal path:

```text
seq 0 midpoint = 0.79   (below threshold, outside final window)
seq 1 midpoint = 0.81   (cross above threshold at window open)
seq 2 midpoint = 0.815  (still above threshold)
```

#### M2 - Already above threshold must not count as an entry

Config overrides: same as `M1`.

Event sequence:

```json
{"parser_version":1,"seq":0,"ts_recv":60.0,"event_type":"book","asset_id":"test-asset-001","bids":[{"price":"0.79","size":"100"}],"asks":[{"price":"0.83","size":"100"}]}
{"parser_version":1,"seq":1,"ts_recv":61.0,"event_type":"price_change","asset_id":"test-asset-001","changes":[{"side":"BUY","price":"0.79","size":"0"},{"side":"BUY","price":"0.77","size":"100"},{"side":"SELL","price":"0.83","size":"0"},{"side":"SELL","price":"0.81","size":"100"}]}
{"parser_version":1,"seq":2,"ts_recv":62.0,"event_type":"price_change","asset_id":"test-asset-001","changes":[{"side":"BUY","price":"0.77","size":"0"},{"side":"BUY","price":"0.80","size":"100"},{"side":"SELL","price":"0.81","size":"0"},{"side":"SELL","price":"0.82","size":"100"}]}
```

Signal path:

```text
seq 0 midpoint = 0.81   (first eligible observation is already above)
seq 1 midpoint = 0.79   (moves below threshold)
seq 2 midpoint = 0.81   (true below-to-above cross)
```

#### M3 - Exit at market close after a filled entry

Config overrides: same as `M1`.

Event sequence:

```json
{"parser_version":1,"seq":0,"ts_recv":59.0,"event_type":"book","asset_id":"test-asset-001","bids":[{"price":"0.78","size":"100"}],"asks":[{"price":"0.80","size":"100"}]}
{"parser_version":1,"seq":1,"ts_recv":60.0,"event_type":"price_change","asset_id":"test-asset-001","changes":[{"side":"BUY","price":"0.79","size":"100"},{"side":"SELL","price":"0.80","size":"0"},{"side":"SELL","price":"0.83","size":"100"}]}
{"parser_version":1,"seq":2,"ts_recv":120.0,"event_type":"price_change","asset_id":"test-asset-001","changes":[{"side":"BUY","price":"0.80","size":"100"},{"side":"SELL","price":"0.83","size":"0"},{"side":"SELL","price":"0.84","size":"100"}]}
```

Validation note:

```text
After the BUY submit at seq 1, validate the exit branch either by:
1) running through StrategyRunner and allowing the entry order to fill, or
2) injecting a synthetic BUY fill before seq 2 in a direct strategy-unit test.
```

#### M4 - market_close_time_ns <= 0 disables activation completely

Config overrides:

```json
{
  "trade_size": 25,
  "market_close_time_ns": 0,
  "final_period_minutes": 1,
  "entry_price": 0.80,
  "take_profit_price": 0.92,
  "stop_loss_price": 0.50
}
```

Event sequence:

```json
{"parser_version":1,"seq":0,"ts_recv":10.0,"event_type":"book","asset_id":"test-asset-001","bids":[{"price":"0.78","size":"100"}],"asks":[{"price":"0.80","size":"100"}]}
{"parser_version":1,"seq":1,"ts_recv":11.0,"event_type":"price_change","asset_id":"test-asset-001","changes":[{"side":"BUY","price":"0.79","size":"100"},{"side":"SELL","price":"0.80","size":"0"},{"side":"SELL","price":"0.83","size":"100"}]}
```

### Expected assertions

- `M1`: `seq=0` returns `[]`; `seq=1` returns exactly one BUY submit; `seq=2`
  returns `[]`. Total decisions: `1 BUY`, `0 SELL`, `0 cancel`.
- `M2`: `seq=0` returns `[]` even though midpoint is already above
  `entry_price`; `seq=1` returns `[]`; `seq=2` returns exactly one BUY submit.
  This is the key crossing-vs-already-above distinction.
- `M3`: after the entry is filled, the first event at or after
  `market_close_time_ns` should emit exactly one SELL submit. No second BUY is
  allowed before that close-based exit.
- `M4`: no decisions at any step. A no-close-time config must not activate on a
  threshold cross.

## sports_favorite

### Synthetic scenarios

#### F1 - First eligible quote already at threshold should enter immediately

Config overrides:

```json
{
  "trade_size": 25,
  "activation_start_time_ns": 60000000000,
  "market_close_time_ns": 120000000000,
  "entry_price": 0.90
}
```

Event sequence:

```json
{"parser_version":1,"seq":0,"ts_recv":60.0,"event_type":"book","asset_id":"test-asset-001","bids":[{"price":"0.89","size":"100"}],"asks":[{"price":"0.91","size":"100"}]}
{"parser_version":1,"seq":1,"ts_recv":61.0,"event_type":"price_change","asset_id":"test-asset-001","changes":[{"side":"BUY","price":"0.89","size":"0"},{"side":"BUY","price":"0.90","size":"100"},{"side":"SELL","price":"0.91","size":"0"},{"side":"SELL","price":"0.92","size":"100"}]}
```

Signal path:

```text
seq 0 midpoint = 0.90  (equal-to-threshold should qualify)
seq 1 midpoint = 0.91  (still above threshold)
```

#### F2 - Above-threshold signal before activation window must be ignored

Config overrides: same as `F1`.

Event sequence:

```json
{"parser_version":1,"seq":0,"ts_recv":59.0,"event_type":"book","asset_id":"test-asset-001","bids":[{"price":"0.91","size":"100"}],"asks":[{"price":"0.93","size":"100"}]}
{"parser_version":1,"seq":1,"ts_recv":60.0,"event_type":"price_change","asset_id":"test-asset-001","changes":[{"side":"BUY","price":"0.91","size":"0"},{"side":"BUY","price":"0.92","size":"100"},{"side":"SELL","price":"0.93","size":"0"},{"side":"SELL","price":"0.94","size":"100"}]}
```

Signal path:

```text
seq 0 midpoint = 0.92  (too early)
seq 1 midpoint = 0.93  (first eligible observation)
```

#### F3 - Above-threshold quote after market close must be ignored

Config overrides: same as `F1`.

Event sequence:

```json
{"parser_version":1,"seq":0,"ts_recv":119.0,"event_type":"book","asset_id":"test-asset-001","bids":[{"price":"0.88","size":"100"}],"asks":[{"price":"0.90","size":"100"}]}
{"parser_version":1,"seq":1,"ts_recv":121.0,"event_type":"price_change","asset_id":"test-asset-001","changes":[{"side":"BUY","price":"0.88","size":"0"},{"side":"BUY","price":"0.91","size":"100"},{"side":"SELL","price":"0.90","size":"0"},{"side":"SELL","price":"0.93","size":"100"}]}
```

Signal path:

```text
seq 0 midpoint = 0.89  (below threshold)
seq 1 midpoint = 0.92  (above threshold, but too late)
```

#### F4 - No in-strategy exit after a filled buy

Config overrides: same as `F1`.

Event sequence:

```json
{"parser_version":1,"seq":0,"ts_recv":60.0,"event_type":"book","asset_id":"test-asset-001","bids":[{"price":"0.91","size":"100"}],"asks":[{"price":"0.93","size":"100"}]}
{"parser_version":1,"seq":1,"ts_recv":90.0,"event_type":"price_change","asset_id":"test-asset-001","changes":[{"side":"BUY","price":"0.91","size":"0"},{"side":"BUY","price":"0.39","size":"100"},{"side":"SELL","price":"0.93","size":"0"},{"side":"SELL","price":"0.41","size":"100"}]}
{"parser_version":1,"seq":2,"ts_recv":130.0,"event_type":"price_change","asset_id":"test-asset-001","changes":[{"side":"BUY","price":"0.39","size":"0"},{"side":"BUY","price":"0.34","size":"100"},{"side":"SELL","price":"0.41","size":"0"},{"side":"SELL","price":"0.36","size":"100"}]}
```

Validation note:

```text
After the BUY submit at seq 0, validate the hold behavior either by:
1) running through StrategyRunner and allowing the limit buy to fill, or
2) injecting a synthetic BUY fill before seq 1 in a direct strategy-unit test.
```

### Expected assertions

- `F1`: `seq=0` returns exactly one BUY submit even though there is no crossing
  event; `>= entry_price` is sufficient. `seq=1` returns `[]`; total decisions
  remain `1 BUY`.
- `F2`: `seq=0` returns `[]` because the signal is above threshold but outside
  the activation window; `seq=1` returns exactly one BUY submit.
- `F3`: no decisions at either step. A post-close quote must not open a new
  position.
- `F4`: once long, later adverse prices and later-than-close timestamps still
  produce `0 SELL` and `0 cancel` decisions. The only valid in-strategy action
  is the original BUY.

## sports_vwap

### Synthetic scenarios

#### V1 - Warm-up counts only accepted ticks; min_tick_size filters the rest

Config overrides:

```json
{
  "trade_size": 10,
  "vwap_window": 3,
  "entry_threshold": 0.05,
  "exit_threshold": 0.01,
  "min_tick_size": 50,
  "take_profit": 0.10,
  "stop_loss": 0.10
}
```

Event sequence:

```json
{"parser_version":1,"seq":0,"ts_recv":0.0,"event_type":"book","asset_id":"test-asset-001","bids":[{"price":"0.49","size":"100"}],"asks":[{"price":"0.51","size":"100"}]}
{"parser_version":1,"seq":1,"ts_recv":1.0,"event_type":"last_trade_price","asset_id":"test-asset-001","price":"0.60","size":"10"}
{"parser_version":1,"seq":2,"ts_recv":2.0,"event_type":"last_trade_price","asset_id":"test-asset-001","price":"0.61","size":"20"}
{"parser_version":1,"seq":3,"ts_recv":3.0,"event_type":"last_trade_price","asset_id":"test-asset-001","price":"0.60","size":"100"}
{"parser_version":1,"seq":4,"ts_recv":4.0,"event_type":"last_trade_price","asset_id":"test-asset-001","price":"0.61","size":"100"}
{"parser_version":1,"seq":5,"ts_recv":5.0,"event_type":"last_trade_price","asset_id":"test-asset-001","price":"0.60","size":"100"}
{"parser_version":1,"seq":6,"ts_recv":6.0,"event_type":"last_trade_price","asset_id":"test-asset-001","price":"0.50","size":"100"}
```

Warm-up interpretation:

```text
seq 1 size=10  -> ignored
seq 2 size=20  -> ignored
seq 3 size=100 -> accepted #1
seq 4 size=100 -> accepted #2
seq 5 size=100 -> accepted #3 (window finally warm)
seq 6 size=100 -> accepted #4, entry candidate
```

#### V2 - VWAP reversion exit after long entry

Config overrides:

```json
{
  "trade_size": 10,
  "vwap_window": 3,
  "entry_threshold": 0.05,
  "exit_threshold": 0.01,
  "min_tick_size": 0,
  "take_profit": 0.20,
  "stop_loss": 0.20
}
```

Event sequence:

```json
{"parser_version":1,"seq":0,"ts_recv":0.0,"event_type":"book","asset_id":"test-asset-001","bids":[{"price":"0.49","size":"100"}],"asks":[{"price":"0.51","size":"100"}]}
{"parser_version":1,"seq":1,"ts_recv":1.0,"event_type":"last_trade_price","asset_id":"test-asset-001","price":"0.60","size":"100"}
{"parser_version":1,"seq":2,"ts_recv":2.0,"event_type":"last_trade_price","asset_id":"test-asset-001","price":"0.61","size":"100"}
{"parser_version":1,"seq":3,"ts_recv":3.0,"event_type":"last_trade_price","asset_id":"test-asset-001","price":"0.60","size":"100"}
{"parser_version":1,"seq":4,"ts_recv":4.0,"event_type":"last_trade_price","asset_id":"test-asset-001","price":"0.50","size":"100"}
{"parser_version":1,"seq":5,"ts_recv":5.0,"event_type":"last_trade_price","asset_id":"test-asset-001","price":"0.56","size":"100"}
```

Reference math:

```text
seq 4 entry check:
  prior-or-current rolling VWAP remains well above 0.55
  current price = 0.50
  price is at least 0.05 below VWAP -> BUY should trigger

seq 5 reversion check (current-inclusive window shown):
  VWAP = (0.60 + 0.50 + 0.56) / 3 = 0.553333...
  VWAP - exit_threshold = 0.543333...
  current price = 0.56 >= 0.543333... -> SELL should trigger
```

#### V3 - Take-profit branch

Config overrides:

```json
{
  "trade_size": 10,
  "vwap_window": 3,
  "entry_threshold": 0.05,
  "exit_threshold": 0.01,
  "min_tick_size": 0,
  "take_profit": 0.01,
  "stop_loss": 0.20
}
```

Event sequence:

```json
{"parser_version":1,"seq":0,"ts_recv":0.0,"event_type":"book","asset_id":"test-asset-001","bids":[{"price":"0.50","size":"100"}],"asks":[{"price":"0.51","size":"100"}]}
{"parser_version":1,"seq":1,"ts_recv":1.0,"event_type":"last_trade_price","asset_id":"test-asset-001","price":"0.60","size":"100"}
{"parser_version":1,"seq":2,"ts_recv":2.0,"event_type":"last_trade_price","asset_id":"test-asset-001","price":"0.61","size":"100"}
{"parser_version":1,"seq":3,"ts_recv":3.0,"event_type":"last_trade_price","asset_id":"test-asset-001","price":"0.60","size":"100"}
{"parser_version":1,"seq":4,"ts_recv":4.0,"event_type":"last_trade_price","asset_id":"test-asset-001","price":"0.50","size":"100"}
{"parser_version":1,"seq":5,"ts_recv":5.0,"event_type":"last_trade_price","asset_id":"test-asset-001","price":"0.52","size":"100"}
```

Reference math:

```text
If the entry fill occurs near the visible ask (0.51), then:
  take-profit trigger = 0.52

At seq 5 (current-inclusive window shown):
  VWAP = (0.60 + 0.50 + 0.52) / 3 = 0.54
  VWAP - exit_threshold = 0.53
  current price = 0.52 < 0.53 -> not a reversion exit
  current price = 0.52 >= fill_price + 0.01 -> take-profit exit
```

#### V4 - Stop-loss branch

Config overrides:

```json
{
  "trade_size": 10,
  "vwap_window": 3,
  "entry_threshold": 0.05,
  "exit_threshold": 0.01,
  "min_tick_size": 0,
  "take_profit": 0.20,
  "stop_loss": 0.02
}
```

Event sequence:

```json
{"parser_version":1,"seq":0,"ts_recv":0.0,"event_type":"book","asset_id":"test-asset-001","bids":[{"price":"0.49","size":"100"}],"asks":[{"price":"0.51","size":"100"}]}
{"parser_version":1,"seq":1,"ts_recv":1.0,"event_type":"last_trade_price","asset_id":"test-asset-001","price":"0.60","size":"100"}
{"parser_version":1,"seq":2,"ts_recv":2.0,"event_type":"last_trade_price","asset_id":"test-asset-001","price":"0.61","size":"100"}
{"parser_version":1,"seq":3,"ts_recv":3.0,"event_type":"last_trade_price","asset_id":"test-asset-001","price":"0.60","size":"100"}
{"parser_version":1,"seq":4,"ts_recv":4.0,"event_type":"last_trade_price","asset_id":"test-asset-001","price":"0.50","size":"100"}
{"parser_version":1,"seq":5,"ts_recv":5.0,"event_type":"last_trade_price","asset_id":"test-asset-001","price":"0.48","size":"100"}
```

Reference math:

```text
If the entry fill occurs near the visible ask (0.51), then:
  stop-loss trigger = 0.49

At seq 5 (current-inclusive window shown):
  VWAP = (0.60 + 0.50 + 0.48) / 3 = 0.526666...
  VWAP - exit_threshold = 0.516666...
  current price = 0.48 < 0.516666... -> not a reversion exit
  current price = 0.48 <= fill_price - 0.02 -> stop-loss exit
```

### Expected assertions

- `V1`: no BUY before `seq=6`. The `size < min_tick_size` trades at `seq=1` and
  `seq=2` must not count toward warm-up and must not distort the rolling VWAP.
- `V2`: `seq=4` emits exactly one BUY submit. After the long entry is filled,
  `seq=5` emits exactly one SELL submit due to price reversion toward VWAP.
- `V3`: `seq=4` emits exactly one BUY submit. After the long entry is filled,
  `seq=5` emits exactly one SELL submit via the take-profit branch. If the
  implementation records exit reasons in `reason` or `meta`, that label should
  indicate take-profit rather than VWAP reversion.
- `V4`: `seq=4` emits exactly one BUY submit. After the long entry is filled,
  `seq=5` emits exactly one SELL submit via the stop-loss branch. If the
  implementation records exit reasons in `reason` or `meta`, that label should
  indicate stop-loss rather than VWAP reversion.

## Review Checklist

### Parameter semantics to preserve

- `market_close_time_ns` and `activation_start_time_ns` are nanoseconds, while
  tape `ts_recv` arrives in seconds. Any comparison must convert units
  consistently.
- `sports_momentum` requires a true below-to-above crossing event; a first
  observation that is already above threshold is not an entry.
- `sports_favorite` triggers on `signal_price >= entry_price` with no crossing
  requirement.
- `sports_favorite` is a hold-to-stop strategy. There is no in-strategy
  profit-taking, stop-loss, or timed exit.
- `sports_vwap` warm-up is based on accepted observations only. Filtered ticks
  do not count toward `vwap_window`.
- `sports_vwap` uses a size-weighted VWAP when trade sizes are available.
- `sports_vwap` take-profit and stop-loss are measured from the filled entry
  price, not from the signal price and not from VWAP.
- `sports_vwap` should check take-profit / stop-loss before falling back to the
  VWAP reversion exit.

### Common mistakes to avoid

- Treating "already above threshold" as a valid momentum entry.
- Comparing nanosecond config values directly to raw `ts_recv` seconds.
- Interpreting `final_period_minutes` as seconds or otherwise shifting the
  momentum activation window.
- Adding an automatic close-time exit to `sports_favorite`.
- Allowing `sports_favorite` to re-submit buys on every above-threshold tick
  after it already has an open entry order or position.
- Counting filtered small `last_trade_price` events toward VWAP warm-up.
- Computing an unweighted arithmetic mean when trade sizes are present.
- Evaluating VWAP reversion before take-profit / stop-loss in the VWAP strategy.
- Measuring take-profit / stop-loss from the latest signal price rather than the
  actual filled entry price.

### Signs of accidental upstream structural copying

- Local code recreates upstream variant-specific class splits or config class
  names (`Bar...Config`, `TradeTick...Config`, `QuoteTick...Config`) even though
  the local surface only needs the single strategy names requested here.
- Helper names, method ordering, or docstrings track the upstream LGPL-covered
  files too closely instead of following PolyTool's existing `Strategy` style.
- Comment wording or parameter blocks mirror the extracted upstream text rather
  than being written in local repo language.
- A shared execution helper layout appears to be a one-to-one port of the
  upstream `core.py` structure.
- The implementation introduces upstream-specific scaffolding that is not
  required by the local `Strategy` / `StrategyRunner` interfaces.

## Local Repo Change Summary

- Added this dev log only.
- No implementation files changed.
- No tests were modified.
- No code was executed beyond read-only inspection and workspace safety checks.

## Open Questions / Blockers

- None for this read-only validation-pack task.
- If the implementation review wants a single mandatory harness style, choose
  one explicitly: direct strategy-unit tests with synthetic `on_fill(...)`, or
  end-to-end `StrategyRunner` tests with executable entry books.

## Codex Review Summary

- Tier: not applicable
- Issues found: not applicable
- Issues addressed: not applicable
