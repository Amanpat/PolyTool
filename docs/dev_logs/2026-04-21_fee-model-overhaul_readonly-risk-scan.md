---
date: 2026-04-21
slug: fee-model-overhaul_readonly-risk-scan
type: read-only risk scan
feature: SimTrader Fee Model Overhaul (PMXT Deliverable A)
author: Claude Code (read-only terminal)
---

# Fee Model Overhaul — Read-Only Risk Scan

**Purpose:** Pre-implementation truth pass for Feature 2 (Active) in `CURRENT_DEVELOPMENT.md`.
No files were changed. This log is the handoff to the write terminal.

---

## Files Inspected

| File | Role |
|---|---|
| `packages/polymarket/simtrader/portfolio/fees.py` | **Primary overhaul target** — Decimal fee math |
| `packages/polymarket/simtrader/portfolio/ledger.py` | Single direct call site of `compute_fill_fee` |
| `packages/polymarket/simtrader/broker/sim_broker.py` | Confirmed: no fee coupling |
| `packages/polymarket/simtrader/broker/rules.py` | Confirmed: `FillRecord` has no fee field |
| `packages/polymarket/simtrader/config_loader.py` | Confirmed: no fee coupling |
| `packages/polymarket/fees.py` | Legacy float module — **NOT the overhaul target** |
| `packages/polymarket/arb.py` | Caller of legacy module (lines 18, 312) |
| `packages/polymarket/simtrader/strategies/binary_complement_arb.py` | Hardcoded `fee_rate_bps=Decimal("200")` at line 80 |
| `packages/polymarket/simtrader/strategy/runner.py` | Propagates `fee_rate_bps` to `PortfolioLedger` (line 293) |
| `packages/polymarket/simtrader/shadow/runner.py` | Same pattern (line 294) |
| `packages/polymarket/simtrader/sweeps/runner.py` | `SweepRunParams.fee_rate_bps: Optional[Decimal]` |
| `packages/polymarket/simtrader/batch/runner.py` | `fee_rate_bps: Optional[Decimal]`; line 486 defaults to None |
| `packages/polymarket/simtrader/studio/ondemand.py` | 5 call sites passing `self._fee_rate_bps` |
| `packages/polymarket/simtrader/studio/app.py` | Parses `fee_rate_bps` from HTTP POST body |
| `packages/polymarket/simtrader/strategy/facade.py` | `StrategyRunParams.fee_rate_bps: Optional[Decimal]`; validates `>= 0` |
| `tools/gates/mm_sweep.py` | `DEFAULT_MM_SWEEP_FEE_RATE_BPS = Decimal("200")`; no role/category |
| `tools/gates/close_mm_sweep_gate.py` | CLI default from `DEFAULT_MM_SWEEP_FEE_RATE_BPS` |
| `tools/gates/mm_sweep_diagnostic.py` | Passes `fee_rate_bps` scalar |
| `tools/gates/run_recovery_corpus_sweep.py` | Passes `fee_rate_bps` scalar |
| `tests/test_simtrader_portfolio.py` | 9 `TestComputeFillFee` tests; encodes exponent=2 implicitly |
| `docs/CURRENT_DEVELOPMENT.md` | Feature 2 DoD (Active) |
| `AGENTS.md` | Review tier and smoke-test obligations |

**Work packet not found on disk:** `12-Ideas/Work-Packet - Unified Open Source Integration Sprint.md`
This was the referenced spec source. Either gitignored, untracked, or path changed. Write terminal
must locate or reconstruct open questions (FEE_CURVE_EXPONENT, maker rebate Option A vs B) from
context before implementing.

---

## Formula Confirmed

**`packages/polymarket/simtrader/portfolio/fees.py:36`**
```python
_CURVE_EXPONENT = 2  # integer so Decimal ** int works exactly
DEFAULT_FEE_RATE_BPS: Decimal = Decimal("200")
```

**`packages/polymarket/fees.py:19`** (legacy, not the target)
```python
FEE_CURVE_EXPONENT = 2.0  # float
```

Both repos use exponent=2. The open question from the work packet is whether research says
exponent=1 for the actual Polymarket `/fee-rate` endpoint. Write terminal must verify via
live endpoint before locking the value.

Current formula (Decimal path):
```
rate = fee_rate_bps / 10000
curve_factor = (price * (1 - price)) ** 2
fee = size * price * rate * curve_factor
```

---

## Caller Map

### Direct call site (the only one)

```
ledger.py:443
    fee = compute_fill_fee(fill_size, fill_price, self._fee_rate_bps)
```

### Propagation chain (fee_rate_bps scalar travels this path)

```
CLI / Gate tools
  └─ SweepRunParams.fee_rate_bps / StrategyRunParams.fee_rate_bps
       └─ StrategyRunner.__init__ (runner.py:293)  /  ShadowRunner (shadow/runner.py:294)
            └─ PortfolioLedger.__init__(fee_rate_bps=...)
                 └─ ledger.py:443  compute_fill_fee(fill_size, fill_price, self._fee_rate_bps)
```

### Strategy-level hardcode (will NOT inherit overhaul automatically)

```
binary_complement_arb.py:80
    fee_rate_bps=Decimal("200")
```

This is a strategy-internal default that bypasses the runner-propagated value. Write terminal
must decide: (a) remove the hardcode and require caller to pass role/category, or (b) keep as
taker-only default since arb strategies always take liquidity.

---

## Taker Assumptions Encoded Throughout

Every call site that passes `fee_rate_bps` treats it as a single scalar with no role or category
distinction. The following assumptions are baked in:

| Assumption | Where |
|---|---|
| Always taker | `PortfolioLedger.__init__` docstring: "Taker fee rate in basis points" |
| Always taker | `mm_sweep.py` `DEFAULT_MM_SWEEP_FEE_RATE_BPS` — one rate for all scenarios |
| Always taker | `facade.py` `StrategyRunParams` doc |
| Always positive | `facade.py:220` validates `fee_rate_bps >= 0` (zero is allowed, negative is not) |
| Always bps-based | All callers divide by 10000 to get rate |
| Single category | No category param anywhere in the chain |

---

## Zero-Fee Safety Analysis (maker fee = 0)

**Verdict: No ledger breakage when fee = Decimal("0").**

When `compute_fill_fee` returns `Decimal("0")`:
- BUY: `actual_cost = fill_price * fill_size + 0` — correct
- SELL: `proceeds = fill_price * fill_size - 0` — correct
- `self._total_fees += Decimal("0")` — harmless
- `effective_fee_rate` in `summary()` — still computes; if total fills > 0 the ratio is just 0.0

The *structural* risk is signature change, not arithmetic. When `compute_fill_fee` gains required
`role` and `category` params, every call site breaks at import time. The ledger's line 443 is
the critical fix point.

---

## Hidden Coupling Found

### 1. `report.py` output format
`packages/polymarket/simtrader/simtrader_report.py` reads `fee_rate_bps` as a single value from
the summary dict. If the overhaul introduces separate maker/taker rates or per-category rates in
the summary output, the report rendering logic will need updating. **Not a blocker for Deliverable A
if summary dict keeps a backward-compatible single `fee_rate_bps` field**, but write terminal
should check what `summary()` returns after the overhaul.

### 2. Gate 2 sweep tools carry taker-only assumption
`mm_sweep.py`, `close_mm_sweep_gate.py`, `mm_sweep_diagnostic.py`, and `run_recovery_corpus_sweep.py`
all pass a single `fee_rate_bps` scalar. Gate 2 Option 4 re-run only produces correct results if
the sweep is updated to pass `role` information (e.g., maker orders get `role="maker"` → fee=0).
**This is out of scope for Deliverable A** (which targets `fees.py` + `KalshiFeeModel` + tests),
but the write terminal should note this in the Deliverable A dev log as a Gate 2 follow-on.

### 3. `binary_complement_arb.py` hardcode
Line 80: `fee_rate_bps=Decimal("200")`. This bypasses any role/category system unless the call
site is updated. Write terminal must decide scope: fix in Deliverable A or create follow-on ticket.

### 4. `batch/runner.py:486` hardcodes `fee_rate_bps=None`
Currently falls through to `DEFAULT_FEE_RATE_BPS`. After overhaul, `None` for `fee_rate_bps` +
`role="taker"` should still work if the signature uses sensible defaults. Write terminal should
verify this call site does not need an explicit `role`.

### 5. `KalshiFeeModel` — no existing infrastructure
There is no Kalshi fee module anywhere in the repo. The write terminal is building from scratch.
No hidden coupling to worry about, but there are no patterns to copy either. Recommended: mirror
the Polymarket class structure and register via the same factory pattern (if one exists).

---

## Tests: What Breaks and What's Missing

### Tests that will break on signature change

| Test | Why it breaks |
|---|---|
| All 9 `TestComputeFillFee` tests | Call `compute_fill_fee(size, price, bps)` — breaks when `role` becomes required |
| `TestLedgerReconciliation.test_total_fees_reconciles_to_sum_of_fill_fees` | Calls `compute_fill_fee` directly with old signature |

### Test fragile on exponent value

| Test | Sensitivity |
|---|---|
| `test_curve_factor_symmetric_around_half` | Asserts `fee(0.7)/fee(0.3) == 0.7/0.3` — holds only when exponent=2 makes curve factors equal at symmetric prices. If exponent changes to 1, this assertion fails because `curve_factor(0.7) = 0.21 ≠ curve_factor(0.3) = 0.21` — wait, actually at exponent=1: `0.7*(1-0.7)=0.21` and `0.3*(1-0.3)=0.21`. They ARE equal. The ratio `fee(0.7)/fee(0.3) = (0.7 * 0.21) / (0.3 * 0.21) = 0.7/0.3`. So this test would PASS at exponent=1 too. **Not a fragility risk for exponent change.** |

### Tests that will still pass after overhaul (if defaults handled correctly)

- `test_zero_fee_rate_returns_zero` — zero rate → zero fee regardless of role
- `test_price_at_boundary_returns_zero` — price=1.0 guard still fires
- `TestLedgerRealizedPnL.test_fees_tracked_separately_from_realized_pnl` — passes with taker role

### Required new tests (DoD: ≥12 new test cases)

Write terminal should add at minimum:

1. `test_maker_role_returns_zero_fee` — `compute_fill_fee(size, price, bps, role="maker") == 0`
2. `test_taker_role_returns_nonzero_fee` — same as current behavior with explicit role
3. `test_role_defaults_to_taker_when_omitted` — backward compat if role is optional
4. `test_category_crypto_uses_correct_rate` — crypto bucket fee formula
5. `test_category_politics_uses_correct_rate` — politics bucket fee formula
6. `test_category_sports_uses_correct_rate` — sports bucket fee formula
7. `test_category_default_uses_fallback_rate` — unknown category falls back safely
8. `test_kalshi_fee_model_basic` — `KalshiFeeModel.compute(size, price) → Decimal`
9. `test_kalshi_fee_model_zero_at_boundary` — price=0 or price=1 returns 0
10. `test_kalshi_fee_model_maker_zero` — if Kalshi also has maker/taker
11. `test_ledger_maker_fill_accrues_zero_fee` — end-to-end via ledger with `role="maker"`
12. `test_ledger_taker_fill_accrues_correct_fee` — regression on current behavior with new sig
13. (bonus) `test_fee_curve_exponent_value` — assert `_CURVE_EXPONENT == N` where N is verified value

---

## Smoke/Review Obligations (from CLAUDE.md + AGENTS.md)

### Smoke test (mandatory after any code change)

```bash
python -m polytool --help
python -m pytest tests/ -x -q --tb=short
```

Report exact counts: e.g., "142 passed, 0 failed, 3 skipped."

### Targeted test run for this feature

```bash
python -m pytest tests/test_simtrader_portfolio.py -v --tb=short
```

### Codex review tier

Feature 2 DoD in `CURRENT_DEVELOPMENT.md` explicitly requires:
> "Mandatory adversarial Codex review on `fees.py` changes"

This overrides the AGENTS.md "Recommended" tier for SimTrader core files.
Write terminal must run `/codex:adversarial-review` on `fees.py` before declaring done.

---

## Open Questions for Write Terminal

1. **FEE_CURVE_EXPONENT**: Repo has `2`. Work packet says research may indicate `1`. Verify
   against live Polymarket `/fee-rate` endpoint before locking. Command pattern:
   `curl https://clob.polymarket.com/fee-rate` (check auth requirements first).

2. **Maker rebate Option A vs B**: Work packet described two options for modeling maker rebates.
   The packet file was not found on disk — write terminal must reconstruct from
   `11-Prompt-Archive/2026-04-10 GLM5 - Unified Gap Fill Open Source Integration.md` or
   `08-Research/07-Backtesting-Repo-Deep-Dive.md`.

3. **`binary_complement_arb.py:80` hardcode**: Fix in Deliverable A scope, or create follow-on?

4. **Gate 2 sweep propagation**: Out of scope for Deliverable A per current DoD. Write terminal
   should confirm this boundary with Director before implementing.

5. **`KalshiFeeModel` placement**: New file `packages/polymarket/simtrader/portfolio/kalshi_fees.py`
   or extend `fees.py`? Recommend separate file to keep concerns isolated.

6. **`role` parameter — required or optional?**: If optional with default `"taker"`, backward
   compat is preserved for all existing call sites with no change. If required, all 9+
   existing fee tests plus the ledger reconciliation test break immediately. Recommend
   optional with default.

---

## Decisions Made This Session

- None. Read-only session.

---

## Blockers

- Work packet file missing from disk. Open questions 1 and 2 cannot be resolved without it
  or its referenced docs. This is the only meaningful blocker for the write terminal.
