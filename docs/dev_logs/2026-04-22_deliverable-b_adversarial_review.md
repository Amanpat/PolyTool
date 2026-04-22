# 2026-04-22 Deliverable B Adversarial Review

## Objective

Adversarial-review PMXT Deliverable B implementation for:

- `sports_momentum`
- `sports_favorite`
- `sports_vwap`
- registry wiring in `packages/polymarket/simtrader/strategy/facade.py`
- tests in `tests/test_sports_strategies.py`

Review goal: determine whether the shipped sports strategies are merge-ready,
behavior-correct, registry-correct, and clean-room enough to merge.

## Files Changed

| File | Why |
| --- | --- |
| `docs/dev_logs/2026-04-22_deliverable-b_adversarial_review.md` | Record this review work unit, commands, findings, and blockers |

No implementation files were modified.

## Files Inspected

- `packages/polymarket/simtrader/strategies/sports_momentum.py`
- `packages/polymarket/simtrader/strategies/sports_favorite.py`
- `packages/polymarket/simtrader/strategies/sports_vwap.py`
- `packages/polymarket/simtrader/strategy/facade.py`
- `tests/test_sports_strategies.py`
- `docs/dev_logs/2026-04-21_deliverable-b_context-fetch.md`
- `docs/dev_logs/2026-04-21_deliverable-b_reference-extract.md`
- `docs/dev_logs/2026-04-22_deliverable-b_validation-pack.md`
- `packages/polymarket/simtrader/strategy/base.py`
- `packages/polymarket/simtrader/strategy/runner.py`
- `packages/polymarket/simtrader/broker/sim_broker.py`
- `packages/polymarket/simtrader/broker/fill_engine.py`
- `tools/cli/simtrader.py`
- `docs/dev_logs/2026-04-21_deliverable-b_impl.md`

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
?? docs/dev_logs/2026-04-22_deliverable-b_validation-pack.md
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

### Targeted test run

Command:

```powershell
pytest -q tests/test_sports_strategies.py
```

Output:

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 9 items

tests\test_sports_strategies.py .........                                [100%]

============================== 9 passed in 0.47s ==============================
```

### Registry contract check against documented config keys

Command:

```powershell
@'
from packages.polymarket.simtrader.strategy.facade import _build_strategy
for name, cfg in [
    ('sports_momentum', {'market_close_time_ns': 120000000000, 'final_period_minutes': 1}),
    ('sports_favorite', {'activation_start_time_ns': 60000000000, 'market_close_time_ns': 120000000000}),
]:
    try:
        _build_strategy(name, cfg)
        print(name + ': ok')
    except Exception as exc:
        print(name + ': ' + type(exc).__name__ + ': ' + str(exc))
'@ | python -
```

Output:

```text
sports_momentum: StrategyRunConfigError: invalid strategy config for 'sports_momentum': SportsMomentum.__init__() got an unexpected keyword argument 'market_close_time_ns'
sports_favorite: StrategyRunConfigError: invalid strategy config for 'sports_favorite': SportsFavorite.__init__() got an unexpected keyword argument 'activation_start_time_ns'
```

### Validation-pack VWAP warm-up sanity check

Command:

```powershell
@'
import json
import tempfile
from decimal import Decimal
from pathlib import Path
from packages.polymarket.simtrader.strategy.runner import StrategyRunner
from packages.polymarket.simtrader.strategies.sports_vwap import SportsVWAP

events = [
    {"parser_version":1,"seq":0,"ts_recv":0.0,"event_type":"book","asset_id":"test-asset-001","bids":[{"price":"0.49","size":"100"}],"asks":[{"price":"0.51","size":"100"}]},
    {"parser_version":1,"seq":1,"ts_recv":1.0,"event_type":"last_trade_price","asset_id":"test-asset-001","price":"0.60","size":"10"},
    {"parser_version":1,"seq":2,"ts_recv":2.0,"event_type":"last_trade_price","asset_id":"test-asset-001","price":"0.61","size":"20"},
    {"parser_version":1,"seq":3,"ts_recv":3.0,"event_type":"last_trade_price","asset_id":"test-asset-001","price":"0.60","size":"100"},
    {"parser_version":1,"seq":4,"ts_recv":4.0,"event_type":"last_trade_price","asset_id":"test-asset-001","price":"0.61","size":"100"},
    {"parser_version":1,"seq":5,"ts_recv":5.0,"event_type":"last_trade_price","asset_id":"test-asset-001","price":"0.60","size":"100"},
    {"parser_version":1,"seq":6,"ts_recv":6.0,"event_type":"last_trade_price","asset_id":"test-asset-001","price":"0.50","size":"100"},
]
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    tape = td / 'events.jsonl'
    run_dir = td / 'run'
    with tape.open('w', encoding='utf-8') as fh:
        for e in events:
            fh.write(json.dumps(e) + '\n')
    strategy = SportsVWAP(
        trade_size=10,
        vwap_window=3,
        entry_threshold=0.05,
        exit_threshold=0.01,
        min_tick_size=50,
        take_profit=0.10,
        stop_loss=0.10,
    )
    StrategyRunner(
        events_path=tape,
        run_dir=run_dir,
        strategy=strategy,
        starting_cash=Decimal('1000'),
    ).run()
    decisions_path = run_dir / 'decisions.jsonl'
    decisions = decisions_path.read_text().splitlines() if decisions_path.exists() else []
    print('decisions_count=' + str(len(decisions)))
'@ | python -
```

Output:

```text
decisions_count=0
```

## Decisions Made During The Session

- Use `docs/dev_logs/2026-04-21_deliverable-b_reference-extract.md` and
  `docs/dev_logs/2026-04-22_deliverable-b_validation-pack.md` as the behavioral
  source of truth for the review.
- Treat the current 9 passing tests as necessary but not sufficient evidence.
- Validate registry correctness through the actual `_build_strategy()` path,
  because `simtrader run --strategy NAME` forwards JSON kwargs directly to the
  strategy constructor.
- Run one focused synthetic VWAP scenario from the validation pack to confirm
  the `min_tick_size` interpretation issue in executable behavior, not just by
  source inspection.

## Findings

### Blocking

1. `sports_momentum` and `sports_favorite` do not implement the documented
   constructor contract from the reference extract / validation pack.
   The docs define `market_close_time_ns` and `activation_start_time_ns` in
   nanoseconds, but the shipped constructors only accept second-based
   `market_close_time` / `activation_start_time`. The real loader path rejects
   the documented keys with `StrategyRunConfigError`.

2. `sports_vwap` misinterprets `min_tick_size`.
   The validation pack expects small trade sizes to be filtered from warm-up,
   but the implementation filters on trade price (`tick_price > min_tick_size`).
   The focused V1-style run with `min_tick_size=50` produced `decisions_count=0`
   because all prices were below 50, which is incompatible with the documented
   behavior.

3. The module attribution text is not license-accurate.
   Each new strategy file says the logic is derived from the upstream repository
   under "MIT License", but the reference extract explicitly records these
   upstream strategy files and `strategies/core.py` as LGPL-covered.
   That is a clean-room / compliance blocker even if the local implementation is
   independently authored.

### Non-blocking but important

1. The test suite misses several validation-pack scenarios:
   - momentum: true crossing-vs-already-above (`M2`)
   - momentum: close-time exit after a filled entry (`M3`)
   - momentum: disabled activation when close time is non-positive (`M4`)
   - favorite: above-threshold before activation, then first eligible entry (`F2`)
   - favorite: post-close signal ignored (`F3`)
   - favorite: no in-strategy exit after a filled buy (`F4`)
   - vwap: warm-up counts only accepted ticks (`V1`)
   - vwap: take-profit branch (`V3`)
   - vwap: stop-loss branch (`V4`)
   - vwap: size-weighted VWAP with unequal sizes

2. Several tests assert only that BUY and SELL both appear, not that the number
   of decisions is exact or that the correct exit branch fired. That makes them
   vulnerable to false positives.

3. The implementation appears structurally clean-room enough in shape:
   no variant-specific class split, no visible port of upstream `core.py`, and
   no one-to-one helper layout. The main clean-room problem is the incorrect
   license labeling, not obvious structural copying.

## Verdict

`NOT MERGE-READY`

## Open Questions / Blockers For The Next Work Unit

- Resolve the public config contract:
  either adopt the documented `*_ns` field names and unit conversions, or
  update the validation-pack / reference contract and all CLI examples
  consistently. Current state is split.
- Decide whether the Deliverable B local contract must preserve any of the
  upstream position-sizing semantics documented in the reference extract
  (visible-liquidity cap, affordability cap, fee-aware affordability).
  The shipped code uses raw `trade_size` directly.
- Fix the attribution text so it accurately reflects the mixed-license upstream
  context recorded in the reference extract.

## Codex Review Summary

- Tier: Recommended / adversarial review of strategy files
- Issues found: 3 blocking, 3 non-blocking clusters
- Issues addressed: none in code; review only
