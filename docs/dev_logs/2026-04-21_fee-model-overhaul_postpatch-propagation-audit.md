# Dev Log — Fee Model Overhaul: Post-Patch Propagation Audit

**Date:** 2026-04-21
**Branch:** main
**Type:** Read-only audit (no code changes)
**Work packet:** Unified Open Source Integration Sprint — Deliverable A follow-on

---

## Objective

Confirm whether the fee model patch (Deliverable A) actually reaches Gate 2 / shadow / Studio / runner execution paths, or whether those paths still use the legacy exponent-2/taker-only formula.

---

## Files Inspected

| File | What Was Checked |
|---|---|
| `packages/polymarket/simtrader/portfolio/fees.py` | New two-path dispatch: category-aware (exp-1) vs. legacy (exp-2) |
| `packages/polymarket/simtrader/portfolio/ledger.py` | New `fee_category`, `fee_role` params on `PortfolioLedger.__init__` and `_on_fill` |
| `packages/polymarket/simtrader/strategy/runner.py` | `StrategyRunner.__init__` signature; `PortfolioLedger(...)` construction at line 291 |
| `packages/polymarket/simtrader/strategy/facade.py` | `StrategyRunParams` dataclass; `run_strategy()` → `StrategyRunner(...)` call at line 240 |
| `packages/polymarket/simtrader/shadow/runner.py` | `PortfolioLedger(...)` construction at line 292 |
| `packages/polymarket/simtrader/sweeps/runner.py` | `SweepRunParams`; `_ALLOWED_OVERRIDE_KEYS`; `run_strategy()` call chain |
| `packages/polymarket/simtrader/batch/runner.py` | `BatchRunParams`; delegates to `run_sweep()` |
| `packages/polymarket/simtrader/studio/ondemand.py` | 5 separate `PortfolioLedger(...)` constructions |
| `packages/polymarket/simtrader/studio/app.py` | HTTP request parsing; delegates to ondemand |
| `packages/polymarket/simtrader/config_loader.py` | New `load_fee_config()` helper |
| `tools/gates/mm_sweep.py` | `run_strategy()` call with `fee_rate_bps` only |
| `tools/gates/mm_sweep_diagnostic.py` | Same pattern as mm_sweep.py |
| `tools/gates/run_recovery_corpus_sweep.py` | Same pattern as mm_sweep.py |
| `tools/gates/close_mm_sweep_gate.py` | Delegates to mm_sweep / run_sweep |
| `packages/polymarket/simtrader/strategies/binary_complement_arb.py` | Fee references; arb edge detection logic |

---

## Propagation Trace

### Full call chain for Gate 2 reruns

```
tools/gates/mm_sweep.py
  └─ StrategyRunParams(fee_rate_bps=X)          ← no fee_category, no fee_role
       └─ strategy/facade.py:run_strategy()
            └─ StrategyRunner(fee_rate_bps=X)    ← no fee_category, no fee_role
                 └─ PortfolioLedger(             ← LEGACY EXPONENT-2 PATH
                        starting_cash=...,
                        fee_rate_bps=...,         ← category=None → legacy dispatch
                        mark_method=...,
                    )
```

### Full call chain for shadow runs

```
shadow/runner.py:ShadowRunner.run()
  └─ PortfolioLedger(                           ← LEGACY EXPONENT-2 PATH
         starting_cash=...,
         fee_rate_bps=...,
         mark_method=...,
     )
```

### Full call chain for Studio OnDemand sessions

```
studio/app.py  (parses fee_rate_bps from HTTP body; no fee_category field)
  └─ studio/ondemand.py:OnDemandSession(fee_rate_bps=...)
       └─ PortfolioLedger(...)   ← 5 construction sites, all legacy path
```

---

## Entry-Point Table

| Entry Point | File:Line(s) | fee_category | fee_role | Fee Path |
|---|---|---|---|---|
| `StrategyRunner.run()` | `strategy/runner.py:291-295` | ❌ Missing | ❌ Missing | Legacy exponent-2 |
| `ShadowRunner.run()` | `shadow/runner.py:292-296` | ❌ Missing | ❌ Missing | Legacy exponent-2 |
| `OnDemandSession` (batch end) | `studio/ondemand.py:339-343` | ❌ Missing | ❌ Missing | Legacy exponent-2 |
| `OnDemandSession` (streaming init) | `studio/ondemand.py:382-386` | ❌ Missing | ❌ Missing | Legacy exponent-2 |
| `OnDemandSession` (rerun) | `studio/ondemand.py:561-565` | ❌ Missing | ❌ Missing | Legacy exponent-2 |
| `OnDemandSession` (seek) | `studio/ondemand.py:694-698` | ❌ Missing | ❌ Missing | Legacy exponent-2 |
| `OnDemandSession` (checkpoint restore) | `studio/ondemand.py:803-807` | ❌ Missing | ❌ Missing | Legacy exponent-2 |
| `StrategyRunParams` (facade) | `strategy/facade.py:168-185` | ❌ Not in dataclass | ❌ Not in dataclass | Inherits runner's legacy path |
| `SweepRunParams` | `sweeps/runner.py:58-62` | ❌ Not in dataclass | ❌ Not in dataclass | Inherits facade's legacy path |
| `BatchRunParams` | `batch/runner.py:64-66` | ❌ Not in dataclass | ❌ Not in dataclass | Inherits sweep's legacy path |
| `mm_sweep.run_mm_sweep()` | `tools/gates/mm_sweep.py:99-167` | ❌ Missing | ❌ Missing | Legacy exponent-2 |
| `run_tape_diagnostics()` | `tools/gates/mm_sweep_diagnostic.py:316-355` | ❌ Missing | ❌ Missing | Legacy exponent-2 |
| `run_recovery_corpus_sweep()` | `tools/gates/run_recovery_corpus_sweep.py:151-235` | ❌ Missing | ❌ Missing | Legacy exponent-2 |
| `close_mm_sweep_gate.main()` | `tools/gates/close_mm_sweep_gate.py:110-116` | ❌ Missing | ❌ Missing | Legacy exponent-2 |

**Result:** Every production execution path still constructs `PortfolioLedger` without
`fee_category` or `fee_role`. All runs use the legacy exponent-2, taker-only formula.

---

## Additional Finding: `load_fee_config()` is Orphaned

`config_loader.load_fee_config()` (added in Deliverable A) correctly extracts
`market_category` and `force_taker` from a strategy config `fees:` block, but
no runner, gate, or CLI command currently calls it. The helper exists but has
no callers wiring its output to `PortfolioLedger`.

---

## `binary_complement_arb.py` Assessment

`BinaryComplementArb` does **NOT** independently compute fees or call `compute_fill_fee`.
Its arb-edge detection uses raw ask prices (`sum_ask < 1 − buffer`) and tracks
`fee_kills_edge` as a rejection counter when edge is below threshold — but actual
fee accounting for fills goes entirely through `PortfolioLedger` via `StrategyRunner`.

**Verdict:** Not a correctness bypass. The arb strategy correctly delegates fee
computation to the ledger. However, since `StrategyRunner` never passes `fee_category`,
fills for arb trades still use exponent-2 / taker-only fees, which over-estimates
costs and artificially depresses reported arb profitability.

---

## Report/Summary Consumer Safety

`ledger.summary()` now emits `fee_category` and `fee_role` keys in `summary.json`.
Since no caller supplies those params, every produced `summary.json` will contain:

```json
"fee_category": null,
"fee_role": "taker"
```

This is **safe** for existing consumers — the keys are present and JSON-valid.
Downstream readers that check for key existence won't break. Readers that compare
`fee_category` to a category string to make decisions will correctly see `null`
(no category configured).

---

## Blocker List

### Must-fix before merge (if Deliverable A is meant to affect Gate 2 reruns)

1. **`packages/polymarket/simtrader/strategy/runner.py`**
   Add `fee_category: Optional[str] = None` and `fee_role: str = "taker"` to
   `StrategyRunner.__init__`. Store them on `self`. At line 291-295, pass both
   to `PortfolioLedger(...)`.

2. **`packages/polymarket/simtrader/strategy/facade.py`**
   Add `fee_category: Optional[str] = None` and `fee_role: str = "taker"` to
   `StrategyRunParams` (frozen dataclass). Pass both through in the `StrategyRunner(...)`
   construction call at line 240.

3. **`tools/gates/mm_sweep.py`**
   Accept `fee_category` as a parameter on `run_mm_sweep()`. Look up category
   per tape from tape metadata or manifest, and pass it into `StrategyRunParams`.
   Without this, Gate 2 reruns on crypto tapes still use 200 bps exponent-2
   rather than the correct 7.2% exponent-1 crypto rate.

### Safe follow-ups (do not block merge of fees.py / ledger.py fixes)

4. `packages/polymarket/simtrader/shadow/runner.py` — Propagate `fee_category` / `fee_role`
   to `PortfolioLedger`. Shadow runs currently use the wrong formula.

5. `packages/polymarket/simtrader/studio/ondemand.py` — Propagate to all 5 `PortfolioLedger`
   constructions. Studio PnL displays will show over-estimated fees until fixed.

6. `packages/polymarket/simtrader/studio/app.py` — Accept `fee_category` in HTTP request
   body parser and pass to `ondemand.create()`.

7. `packages/polymarket/simtrader/sweeps/runner.py` — Add `fee_category` to `SweepRunParams`
   and to `_ALLOWED_OVERRIDE_KEYS` so scenario sweeps can vary category.

8. `packages/polymarket/simtrader/batch/runner.py` — Add `fee_category` to `BatchRunParams`.

9. `tools/gates/mm_sweep_diagnostic.py` — Propagate `fee_category`.

10. `tools/gates/run_recovery_corpus_sweep.py` — Propagate `fee_category`.

11. `tools/gates/close_mm_sweep_gate.py` — Propagate `fee_category`.

12. Wire `config_loader.load_fee_config()` to at least one caller (e.g., CLI `simtrader run`
    reads `fees.market_category` from strategy config and passes it to `StrategyRunParams`).

---

## Recommendation

**Do not merge Deliverable A under the assumption that Gate 2 reruns or shadow runs
will reflect the corrected fee formula.** The patch correctly fixes `fees.py` and
`ledger.py` — the math and the `PortfolioLedger` interface are right — but the
propagation chain is entirely unconnected. Every runner, gate tool, sweep, and Studio
session that runs after the merge will still compute exponent-2, taker-only fees
because they never supply `fee_category` or `fee_role` to `PortfolioLedger`.

If the goal is to ship `fees.py` + `ledger.py` + tests as a contained foundation
(Deliverable A only, with propagation as Deliverable B), that is acceptable — but
the scope should be documented explicitly so no one reruns Gate 2 expecting
category-aware fees and interprets the identical numbers as "working correctly."

Minimum propagation fix required before Gate 2 reruns reflect the overhaul:
files 1–3 in the Must-fix list above (`strategy/runner.py`, `strategy/facade.py`,
`tools/gates/mm_sweep.py`).
