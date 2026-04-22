# SimTrader Fee Model v2

## Scope

Deliverable A of the Unified Open Source Integration Sprint.  Fixes three bugs in
`packages/polymarket/simtrader/portfolio/fees.py` without touching the execution
stack, live fee APIs, or Pydantic config.

## What Changed

### 1. Taker-only assumption removed — maker fees now modeled

Polymarket charges makers **zero fees**.  The new `role` keyword argument on
`compute_fill_fee` makes this explicit:

```python
compute_fill_fee(fill_size, fill_price, role="maker")   # → Decimal("0")
compute_fill_fee(fill_size, fill_price, role="taker")   # → fee via formula
```

The `PortfolioLedger` accepts `fee_role="taker"|"maker"` and forwards it to
every fill.  Default remains `"taker"` so all existing callers are unaffected.

No rebate estimator was added (Option A decision, locked by Director).

### 2. Category-aware fee rate (exponent-1 path)

Supplying `category=` activates the corrected Polymarket formula:

```
fee_usdc = shares × category_rate × price × (1 − price)
```

Category rates (fractional, not bps):

| Category | Rate |
|---|---|
| crypto | 0.072 |
| sports | 0.030 |
| politics / finance / mentions / tech | 0.040 |
| economics / culture / weather / other | 0.050 |
| geopolitics | 0 (free) |

Acceptance criteria verified:
- `compute_fill_fee(100, 0.50, category="sports")` → `0.75`
- `compute_fill_fee(100, 0.50, category="crypto")` → `1.80`
- `compute_fill_fee(100, 0.50, category="geopolitics")` → `0`

### 3. Legacy path preserved (exponent-2, backward-compatible)

When `category` is **not** supplied, the original exponent-2 formula is used
unchanged:

```
fee_usdc = shares × price × (fee_rate_bps / 10 000) × (price × (1−price))²
```

All 64 pre-existing `test_simtrader_portfolio.py` tests continue to pass
without modification because they do not supply `category`.

### 4. Kalshi fee model added

`KalshiFeeModel.compute_fee(contracts, price)` implements the Kalshi taker fee:

```
fee_usdc = ceil(0.07 × contracts × price × (1 − price))
```

Rounded up to the nearest cent using `Decimal.quantize(ROUND_CEILING)`.

Acceptance criteria: `KalshiFeeModel.compute_fee(10, 0.60)` → `Decimal("0.17")`.

Attribution: derived from evan-kolberg/prediction-market-backtesting (MIT License).

### 5. Supporting changes

**`PortfolioLedger`** — two new constructor params:
- `fee_category: Optional[str] = None` — activates category path when set
- `fee_role: str = "taker"` — forwarded to every fill

**`Order` dataclass** (`broker/rules.py`) — two new optional fields:
- `force_taker: bool = False`
- `market_category: Optional[str] = None`

**`config_loader.py`** — new `load_fee_config(config)` helper that extracts
`fees.platform`, `fees.market_category`, `fees.force_taker` from a strategy
config dict.

### 6. Runtime propagation — all 12 entry points wired

`fee_category` and `fee_role` are forwarded to `PortfolioLedger` at every production
execution path. Completed across two passes (propagation pass + finish pass):

| Entry Point | File |
|---|---|
| `StrategyRunner` | `strategy/runner.py` |
| `ShadowRunner` | `shadow/runner.py` |
| `run_strategy()` facade | `strategy/facade.py` |
| `SweepRunParams` | `sweeps/runner.py` |
| `OnDemandSession` (all 5 call sites) | `studio/ondemand.py` |
| Studio HTTP handler | `studio/app.py` |
| Gate 2 sweep tool | `tools/gates/mm_sweep.py` |
| CLI `_run()` | `tools/cli/simtrader.py` |
| CLI `_sweep()` | `tools/cli/simtrader.py` |
| CLI quickrun sweep | `tools/cli/simtrader.py` |
| CLI quickrun single-run | `tools/cli/simtrader.py` |
| CLI `_shadow()` | `tools/cli/simtrader.py` |

### 7. CLI truthfulness — category-aware fee label

`simtrader run` and `simtrader sweep` now emit a truthful operator-facing fee label:

- `fee_category` set → `"category-aware ({category}/taker)"`
- `fee_rate_bps` set (no category) → bps value as string
- neither set → `"null (ledger default)"`

Previously both commands always printed `"default (200)"` even when category-aware
routing was in effect.

### 8. Manifest truthfulness

All `run_manifest.json` files now record `fee_rate_bps: null` (not the misleading
string `"default(200)"`) when no explicit bps is configured, and include explicit
`fee_category` and `fee_role` fields:

```json
"portfolio_config": {
  "starting_cash": "1000",
  "fee_rate_bps": null,
  "fee_category": "sports",
  "fee_role": "taker",
  "mark_method": "bid"
}
```

## Known Non-Goals (Deliverable A)

- Rebate estimator for maker fills — deferred
- Per-fill taker/maker role detection from live book state — deferred (Deliverable B)
- Pydantic config migration — deferred
- `packages/polymarket/fees.py` (float-based) truth-sync — later pass
- Docs truth-sync for SPEC-0004 and ARCHITECTURE — later pass
- Kalshi integration wiring — Deliverable C
- Studio UI `fee_category`/`fee_role` form inputs — deferred
- `mm_sweep_diagnostic.py`, `run_recovery_corpus_sweep.py`, `close_mm_sweep_gate.py` propagation — deferred (safe follow-up)

## Test Coverage

32 new test cases across three test files:

**`tests/test_simtrader_portfolio.py`** (+23):
- 15 in `TestComputeFillFeeCategories` (all categories, role=maker, boundary
  conditions, case-insensitivity, unknown-category fallback)
- 8 in `TestKalshiFeeModel` (acceptance criteria, rounding, boundaries,
  symmetric price, Decimal inputs)

**`tests/test_simtrader_shadow.py`** (+4, `TestShadowFeeCategory`):
- `test_manifest_includes_fee_category_and_role`
- `test_manifest_fee_rate_bps_is_null_for_category_run`
- `test_manifest_no_default_200_string`
- `test_manifest_legacy_run_fee_category_is_null`

**`tests/test_simtrader_strategy.py`** (+5):
- `test_run_manifest_portfolio_config_includes_fee_category`
- `test_run_manifest_fee_rate_bps_null_not_default_string`
- `test_run_manifest_fee_category_null_when_not_set`
- `test_cli_run_fee_label_category_aware`
- `test_cli_sweep_fee_label_category_aware`

Targeted suite (3 files): **200 passed**.
Full suite: **2606 passed**, 1 pre-existing failure unrelated to this feature
(`test_ris_phase2_cloud_provider_routing.py::test_gemini_provider_success` —
`AttributeError: providers._post_json`).
