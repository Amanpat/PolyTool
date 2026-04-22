# Deliverable B Context Fetch

**Date:** 2026-04-21
**Type:** Read-only context fetch
**Status:** Complete — no code changed

---

## Objective

Map the exact repo surfaces needed to implement Deliverable B (Sports Strategy Foundations):
`sports_momentum`, `sports_favorite`, `sports_vwap`, registry wiring, Pydantic configs,
replay CLI support, and tests.

---

## Files Inspected

| File | Purpose |
|------|---------|
| `AGENTS.md` | Session rules |
| `docs/CURRENT_DEVELOPMENT.md` | Active features, Paused state of Deliverable B |
| `docs/features/simtrader_fee_model_v2.md` | Deliverable A (complete); pattern reference |
| `docs/obsidian-vault/12-Ideas/Work-Packet - Unified Open Source Integration Sprint.md` | Full Deliverable B spec |
| `packages/polymarket/simtrader/strategy/base.py` | Strategy base class |
| `packages/polymarket/simtrader/strategy/facade.py` | STRATEGY_REGISTRY + run_strategy() |
| `packages/polymarket/simtrader/strategy/runner.py` | (glob confirmed, not read) |
| `packages/polymarket/simtrader/config_loader.py` | load_fee_config helper; existing patterns |
| `packages/polymarket/simtrader/strategies/market_maker_v0.py` | MMConfig (frozen dataclass) pattern |
| `packages/polymarket/simtrader/strategies/market_maker_v1.py` | LogitAS inherits V0 |
| `packages/polymarket/simtrader/strategies/binary_complement_arb.py` | Raw kwargs constructor |
| `tools/cli/simtrader.py` | `_run`, `_replay` handlers; `--strategy` flag wiring |
| `tests/test_simtrader_strategy.py` | TAPE_EVENTS, _write_tape, StrategyRunner helpers |
| `pyproject.toml` | Dependency manifest — Pydantic status |

---

## Commands Run

Read-only file reads and greps only. No shell commands issued that modify state.

---

## Surface 1: Strategy Base Class

**Path:** `packages/polymarket/simtrader/strategy/base.py`

```python
class Strategy:
    def on_start(self, asset_id: str, starting_cash: Decimal) -> None: ...
    def on_event(self, event, seq, ts_recv, best_bid, best_ask, open_orders) -> list[OrderIntent]: ...
    def on_fill(self, order_id, asset_id, side, fill_price, fill_size, fill_status, seq, ts_recv) -> None: ...
    def on_finish(self) -> None: ...

@dataclass
class OrderIntent:
    action: str          # "submit" | "cancel"
    asset_id: Optional[str]
    side: Optional[str]  # "BUY" | "SELL"
    limit_price: Optional[Decimal]
    size: Optional[Decimal]
    order_id: Optional[str]
    reason: Optional[str]
    meta: dict[str, Any]
```

All three sports strategies must subclass `Strategy` and implement the four lifecycle methods.

---

## Surface 2: Strategy Registry

**Path:** `packages/polymarket/simtrader/strategy/facade.py`

```python
STRATEGY_REGISTRY: dict[str, str] = {
    "copy_wallet_replay":      "packages.polymarket.simtrader.strategies.copy_wallet_replay.CopyWalletReplay",
    "binary_complement_arb":   "packages.polymarket.simtrader.strategies.binary_complement_arb.BinaryComplementArb",
    "market_maker_v0":         "packages.polymarket.simtrader.strategies.market_maker_v0.MarketMakerV0",
    "market_maker_v1":         "packages.polymarket.simtrader.strategies.market_maker_v1.MarketMakerV1",
}
```

Registration mechanism: add three entries to this dict. The `_build_strategy()` function
does `importlib.import_module(module_path)` then `getattr(module, class_name)` then
`strategy_cls(**constructor_config)`. **All keys of strategy_config dict are forwarded
verbatim as kwargs to the constructor** (after adverse_selection is stripped). So
constructor parameter names must exactly match strategy_config JSON keys.

---

## Surface 3: CLI Strategy Selection

**Path:** `tools/cli/simtrader.py`

The strategy-execution command is `simtrader run`, NOT `simtrader replay`.

- `simtrader replay` (`_replay` at line 241): raw tape replay via `ReplayRunner`. **Does not accept `--strategy`.** No strategy is involved.
- `simtrader run` (`_run` at line 1064): strategy run via `run_strategy(StrategyRunParams(...))`. Accepts `--strategy NAME`.

Usage:
```
python -m polytool simtrader run \
  --tape <PATH/events.jsonl> \
  --strategy sports_momentum \
  --strategy-config-json '{"final_period_minutes":30,"entry_price":0.80,...}'
```

`--strategy` is defined at CLI line ~3225:
```python
run_p.add_argument("--strategy", default=DEFAULT_TRACK_A_STRATEGY, metavar="NAME", ...)
```

Adding the three new strategies to `STRATEGY_REGISTRY` is **the only CLI change required**.
No new argument parsing needed — the existing `--strategy NAME` + `--strategy-config-json`
flow handles them automatically.

---

## Surface 4: Config Patterns

**Current pattern in simtrader strategies:** Raw `**kwargs` to constructor or frozen dataclass.

| Strategy | Config Pattern |
|----------|---------------|
| `BinaryComplementArb` | Raw `**kwargs` — constructor params = JSON keys |
| `CopyWalletReplay` | Raw `**kwargs` |
| `MarketMakerV0` | Internal frozen `@dataclass MMConfig` built inside constructor |

**Pydantic status: NOT installed.** `pyproject.toml` has zero mention of pydantic.
Pydantic is not an existing dependency of any optional group (`rag`, `mcp`, `dev`, `all`).

The work packet says "Each strategy uses Pydantic config models (NOT raw JSON dicts)" but
this would introduce Pydantic as a brand-new dependency. See Risks section below.

`config_loader.py` has `load_fee_config(config)` which shows the current idiom for
optional config blocks: `fees_block.get("platform")` — plain dict access, no validation.

---

## Surface 5: Indicator Utility Patterns

No dedicated indicator utility module exists in `packages/polymarket/simtrader/`.
Existing rolling-window logic lives inline in each strategy:
- `MarketMakerV1`: `deque` for `_trade_arrival_ts` and `_mid_history`
- `MarketMakerV0`: `deque` for `_mid_history`

For the VWAP rolling window (`sports_vwap`), the same `collections.deque(maxlen=N)` pattern
should be used — no shared utility module needed, consistent with existing style.

---

## Surface 6: Replay Test Helpers

**Best source:** `tests/test_simtrader_strategy.py`

```python
# Synthetic tape constants
ASSET_ID = "test-asset-001"
TAPE_EVENTS = [...]  # book snapshot + price_change events

# Helpers
def _write_tape(path: Path) -> None: ...         # writes TAPE_EVENTS as jsonl
def _write_binary_tape(path: Path) -> None: ...  # YES/NO dual-asset tape
def _write_trades(path: Path, trades) -> None: ...
def _read_decisions(run_dir: Path) -> list[dict]: ...
def _read_summary(run_dir: Path) -> dict: ...
def _read_manifest(run_dir: Path) -> dict: ...
```

Test pattern:
```python
def test_my_strategy(tmp_path):
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner
    tape_path = tmp_path / "events.jsonl"
    _write_tape(tape_path)  # or custom event list
    run_dir = tmp_path / "run"
    strategy = MyStrategy(param=value)
    runner = StrategyRunner(events_path=tape_path, run_dir=run_dir, strategy=strategy, starting_cash=Decimal("1000"))
    runner.run()
    decisions = _read_decisions(run_dir)
    assert len(decisions) >= 1
```

For sports strategies that need `last_trade_price` events (for VWAP) or need to simulate
market close (for momentum/favorite), extend TAPE_EVENTS with those event types:

```python
{"event_type": "last_trade_price", "asset_id": ASSET_ID, "price": "0.82", "seq": 6, "ts_recv": 6.0}
```

---

## Implementation Map

### Files to CREATE (new)

| File | Description |
|------|-------------|
| `packages/polymarket/simtrader/strategies/sports_momentum.py` | Final Period Momentum strategy |
| `packages/polymarket/simtrader/strategies/sports_favorite.py` | Late Favorite Limit Hold strategy |
| `packages/polymarket/simtrader/strategies/sports_vwap.py` | VWAP Reversion strategy |
| `tests/test_sports_strategies.py` | Test suite (≥6 cases, 2 per strategy) |

### Files to EDIT (minimal targeted changes)

| File | Change |
|------|--------|
| `packages/polymarket/simtrader/strategy/facade.py` | Add 3 entries to `STRATEGY_REGISTRY` |

### Files NOT touched

- `tools/cli/simtrader.py` — no change needed; `--strategy NAME` already routes via registry
- `packages/polymarket/simtrader/portfolio/fees.py` — Deliverable A handled this
- All execution, kill-switch, risk manager files — out of scope

---

## Risks / Gotchas

### RISK 1 (HIGH): Pydantic is not a dependency

The work packet says "Each strategy uses Pydantic config models." Pydantic does NOT appear
in `pyproject.toml` (grep returned zero matches). Adding Pydantic would be a new optional
or core dependency. Options:
- **A (Recommended):** Use frozen `@dataclass` pattern matching `MMConfig` — consistent with
  existing code, zero new dependency.
- **B:** Add `pydantic>=2.0` to a new optional group (e.g., `[sports]`) and document it.
- **C:** Ask Director whether Pydantic adoption is desired project-wide before adding.

Decision needed before implementation starts.

### RISK 2 (MEDIUM): Work packet CLI command is wrong

The packet says: `python -m polytool simtrader replay --strategy sports_momentum --tape <path>`

This is incorrect. `simtrader replay` (`_replay` handler, line 241) does NOT accept
`--strategy`. The correct command is:

```
python -m polytool simtrader run --strategy sports_momentum --tape <path>
```

Adding sports strategies to the registry is sufficient for full CLI support via `run`.
No `replay` subcommand changes are needed or correct.

### RISK 3 (MEDIUM): market_close_time not in on_start signature

`sports_momentum` and `sports_favorite` need `market_close_time` (Unix seconds) to know
when the "final period" window begins. The `on_start(asset_id, starting_cash)` signature
does NOT provide market metadata. Resolution: accept `market_close_time` as a **constructor
parameter** in strategy_config JSON, not as runtime data. This is the correct pattern
(same as `BinaryComplementArb` accepts `yes_asset_id`/`no_asset_id` as constructor args).

### RISK 4 (LOW): Silver tapes insufficient for VWAP

`sports_vwap` requires `last_trade_price` events for the rolling 80-tick VWAP. Silver tapes
are ~2min resolution and may not produce enough trade ticks for a meaningful VWAP window.
Gold tapes or live shadow mode are required for real validation. Synthetic test tapes can
simulate this for unit testing.

### RISK 5 (LOW): Deliverable B is currently PAUSED

Per `docs/CURRENT_DEVELOPMENT.md` (Paused/Deferred table):
- "PMXT Deliverable B (Sports Strategy Foundations)" — Paused 2026-04-10
- Resume trigger: "Deliverable A complete AND Track 1C activation decided"
- Deliverable A IS complete (2026-04-21) but Track 1C activation has NOT been formally decided.

The Director has described this context fetch as permitted (read-only). Any implementation
requires a Director decision recorded in CURRENT_DEVELOPMENT.md before code is written.

### RISK 6 (LOW): _split_strategy_config rejects adverse_selection for non-market_maker_v1

The `_split_strategy_config` function in facade.py raises `StrategyRunConfigError` if
`adverse_selection` key appears in config for any strategy other than `market_maker_v1`.
Sports strategies must not include `adverse_selection` in their config dicts.

---

## Summary

- Base class: `packages/polymarket/simtrader/strategy/base.py` — `Strategy` + `OrderIntent`
- Registry: `packages/polymarket/simtrader/strategy/facade.py` — `STRATEGY_REGISTRY`
- CLI entry point: `simtrader run --strategy NAME` (NOT `simtrader replay`)
- Config pattern: frozen `@dataclass` OR raw `**kwargs` — Pydantic NOT installed
- Test helpers: `tests/test_simtrader_strategy.py` — `TAPE_EVENTS`, `_write_tape`, `StrategyRunner`
- Three new files + one registry edit + one test file = minimal scope
- Director decision on Track 1C activation required before implementation proceeds
