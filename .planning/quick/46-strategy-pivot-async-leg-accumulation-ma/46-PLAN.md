---
phase: quick-046
plan: 46
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/polymarket/crypto_pairs/config_models.py
  - packages/polymarket/crypto_pairs/accumulation_engine.py
  - packages/polymarket/crypto_pairs/paper_runner.py
  - packages/polymarket/crypto_pairs/paper_ledger.py
  - packages/polymarket/crypto_pairs/dev_seed.py
  - tests/test_crypto_pair_accumulation_engine.py
  - tests/test_crypto_pair_backtest.py
  - tests/test_crypto_pair_paper_ledger.py
  - tests/test_crypto_pair_runner_events.py
  - tests/test_crypto_pair_clickhouse_sink.py
  - tests/test_crypto_pair_report.py
autonomous: true
requirements: [QUICK-046]

must_haves:
  truths:
    - "evaluate_accumulation() produces ACTION_ACCUMULATE when yes_ask <= target_bid_yes OR no_ask <= target_bid_no"
    - "target_bid defaults to Decimal('0.5') - edge_buffer_per_leg when fair value is unavailable (which is always in paper mode due to missing threshold/remaining_seconds)"
    - "config_models.py loads without error when given a dict with old 'target_pair_cost_threshold' key (backward compat)"
    - "paper runner emits 'target_bid_computed' event each cycle with fair_value_yes/no, target_bid_yes/no, yes_ask_meets_target/no_ask_meets_target fields"
    - "generate_order_intent() uses target bids as intended prices instead of quote prices"
    - "All tests pass after changes"
  artifacts:
    - path: "packages/polymarket/crypto_pairs/config_models.py"
      provides: "Three new config fields: edge_buffer_per_leg, max_pair_completion_pct, min_projected_profit"
    - path: "packages/polymarket/crypto_pairs/accumulation_engine.py"
      provides: "Target-bid gate replacing pair-cost gate + soft fair-value gate"
    - path: "packages/polymarket/crypto_pairs/paper_runner.py"
      provides: "Fair value attempt + target_bid_computed event + updated validation"
    - path: "packages/polymarket/crypto_pairs/paper_ledger.py"
      provides: "target_yes_bid/target_no_bid fields in PaperOpportunityObservation; generate_order_intent uses them"
  key_links:
    - from: "paper_runner.py _process_opportunity()"
      to: "accumulation_engine.evaluate_accumulation()"
      via: "PairMarketState.fair_value_yes/no set from target bid computation"
    - from: "paper_ledger.generate_order_intent()"
      to: "PaperOrderIntent.intended_yes_price/no_price"
      via: "observation.target_yes_bid / observation.target_no_bid"
---

<objective>
Pivot the crypto pair bot from a snapshot pair-cost gate to a per-leg target-bid fill simulation.

Root cause: Gate 3 checks `YES_ask + NO_ask <= target_pair_cost_threshold (0.97)`. Real
markets always quote sum >= 0.99, so Gate 3 always fails and the strategy generates 0 intents
every cycle.

New approach: compute `target_bid = fair_value - edge_buffer` per leg. The engine accumulates
a leg when `best_ask <= target_bid` — i.e., the market has come to our maker bid price. Both
legs are tracked independently. In practice, fair value will always fall back to 0.5 because
`PairOpportunity` carries no `threshold` (resolution price level) or `remaining_seconds`, which
`estimate_fair_value()` requires. Default target_bid = 0.46 (0.5 - 0.04).

Purpose: Unblock intent generation. The strategy was generating 0 intents per cycle.
Output: Reworked config, engine, runner, ledger, and all affected tests.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/packages/polymarket/crypto_pairs/config_models.py
@D:/Coding Projects/Polymarket/PolyTool/packages/polymarket/crypto_pairs/accumulation_engine.py
@D:/Coding Projects/Polymarket/PolyTool/packages/polymarket/crypto_pairs/paper_runner.py
@D:/Coding Projects/Polymarket/PolyTool/packages/polymarket/crypto_pairs/paper_ledger.py
@D:/Coding Projects/Polymarket/PolyTool/packages/polymarket/crypto_pairs/dev_seed.py
@D:/Coding Projects/Polymarket/PolyTool/packages/polymarket/crypto_pairs/fair_value.py
@D:/Coding Projects/Polymarket/PolyTool/tests/test_crypto_pair_accumulation_engine.py
@D:/Coding Projects/Polymarket/PolyTool/tests/test_crypto_pair_backtest.py
@D:/Coding Projects/Polymarket/PolyTool/tests/test_crypto_pair_paper_ledger.py
@D:/Coding Projects/Polymarket/PolyTool/tests/test_crypto_pair_runner_events.py
@D:/Coding Projects/Polymarket/PolyTool/tests/test_crypto_pair_clickhouse_sink.py
@D:/Coding Projects/Polymarket/PolyTool/tests/test_crypto_pair_report.py

<interfaces>
<!-- Key contracts extracted from codebase. Executor should use these directly. -->

From packages/polymarket/crypto_pairs/accumulation_engine.py (current Gate 3/4 to replace):
```python
# Current Gate 3 (lines ~227-243) — REPLACE THIS:
threshold = config.target_pair_cost_threshold
hard_rule_passed = projected_pair_cost <= threshold
rationale["hard_rule_passed"] = hard_rule_passed
rationale["projected_pair_cost"] = str(projected_pair_cost)
rationale["threshold"] = str(threshold)
if not hard_rule_passed:
    rationale["skip_reason"] = "hard_rule_failed"
    return AccumulationIntent(action=ACTION_SKIP, ...)

# Current Gate 4 _soft_rule_passes() — REMOVE THIS FUNCTION
# Current _select_legs() — uses soft_yes/soft_no booleans from _soft_rule_passes()

# AccumulationIntent fields to KEEP (API compat):
hard_rule_passed: bool
soft_rule_yes_passed: bool
soft_rule_no_passed: bool
projected_pair_cost: Optional[Decimal]
```

From packages/polymarket/crypto_pairs/config_models.py (CryptoPairPaperModeConfig):
```python
# CURRENT field to REMOVE:
target_pair_cost_threshold: Decimal = Decimal("0.99")

# NEW fields to ADD (with these exact defaults):
edge_buffer_per_leg: Decimal = Decimal("0.04")
max_pair_completion_pct: Decimal = Decimal("0.80")
min_projected_profit: Decimal = Decimal("0.03")

# from_dict() must silently ignore "target_pair_cost_threshold" key (backward compat)
# to_dict() must include the three new fields
# __post_init__ validation: edge_buffer > 0 and < 0.5; max_pair_completion_pct in (0, 1]; min_projected_profit > 0
```

From packages/polymarket/crypto_pairs/paper_ledger.py (fields to update):
```python
# PaperOpportunityObservation — current REQUIRED field to REPLACE:
target_pair_cost_threshold: Decimal  # remove this

# NEW optional fields to ADD to PaperOpportunityObservation:
target_yes_bid: Optional[Decimal] = None
target_no_bid: Optional[Decimal] = None

# PaperOrderIntent — current REQUIRED field to REPLACE:
target_pair_cost_threshold: Decimal  # remove this

# generate_order_intent() currently uses (lines ~1071-1072):
intended_yes_price=observation.yes_quote_price,
intended_no_price=observation.no_quote_price,
# CHANGE TO:
intended_yes_price=observation.target_yes_bid or observation.yes_quote_price,
intended_no_price=observation.target_no_bid or observation.no_quote_price,
```

From packages/polymarket/crypto_pairs/paper_runner.py (key constants/functions):
```python
# Line 64 — REMOVE:
_OPERATOR_MAX_PAIR_COST = Decimal("0.97")

# build_default_paper_mode_config() — CHANGE:
# Remove: "target_pair_cost_threshold": str(_OPERATOR_MAX_PAIR_COST)
# Add: "edge_buffer_per_leg": "0.04", "max_pair_completion_pct": "0.80", "min_projected_profit": "0.03"

# CryptoPairRunnerSettings.__post_init__ validation (lines ~204-214) — CHANGE:
# Remove: target_pair_cost_threshold > _OPERATOR_MAX_PAIR_COST check
# Add: edge_buffer_per_leg >= Decimal("0.01") check

# build_runner_settings() key list (lines ~272-282) — CHANGE:
# Remove "target_pair_cost_threshold" from extracted keys
# Add "edge_buffer_per_leg", "max_pair_completion_pct", "min_projected_profit"

# build_observation() (lines ~465-488) — CHANGE:
# Remove: target_pair_cost_threshold parameter and pass-through
# Add: target_yes_bid, target_no_bid parameters

# _process_opportunity() (lines ~810-1000) — ADD:
# After getting yes_ask/no_ask, compute:
#   edge_buffer = config.edge_buffer_per_leg
#   target_yes_bid = (fair_value_yes - edge_buffer) if fair_value_yes else (Decimal("0.5") - edge_buffer)
#   target_no_bid = (fair_value_no - edge_buffer) if fair_value_no else (Decimal("0.5") - edge_buffer)
# Emit "target_bid_computed" event with fields:
#   fair_value_yes, fair_value_no, target_bid_yes, target_bid_no,
#   yes_ask, no_ask, yes_ask_meets_target (bool), no_ask_meets_target (bool)
# Pass target_yes_bid/target_no_bid to build_observation()
```

From packages/polymarket/crypto_pairs/fair_value.py:
```python
def estimate_fair_value(
    symbol: str,
    duration_min: int,
    side: str,   # "YES" or "NO"
    underlying_price: float,
    threshold: float,   # resolution price level — NOT in PairOpportunity
    remaining_seconds: float,
    *,
    annual_vol: Optional[float] = None,
) -> FairValueEstimate:
    ...

@dataclass
class FairValueEstimate:
    fair_prob: float   # key output
    ...
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Replace target_pair_cost_threshold in config_models.py and paper_ledger.py</name>
  <files>
    packages/polymarket/crypto_pairs/config_models.py,
    packages/polymarket/crypto_pairs/paper_ledger.py,
    packages/polymarket/crypto_pairs/dev_seed.py,
    tests/test_crypto_pair_paper_ledger.py,
    tests/test_crypto_pair_clickhouse_sink.py,
    tests/test_crypto_pair_report.py
  </files>
  <behavior>
    - CryptoPairPaperModeConfig no longer has target_pair_cost_threshold field
    - CryptoPairPaperModeConfig.from_dict() silently ignores "target_pair_cost_threshold" key if present (backward compat)
    - CryptoPairPaperModeConfig has three new fields: edge_buffer_per_leg, max_pair_completion_pct, min_projected_profit with correct defaults
    - CryptoPairPaperModeConfig.to_dict() includes all three new fields
    - PaperOpportunityObservation no longer has target_pair_cost_threshold field; has optional target_yes_bid, target_no_bid
    - PaperOrderIntent no longer has target_pair_cost_threshold field
    - dev_seed._demo_config() uses new config keys instead of target_pair_cost_threshold
    - test_crypto_pair_paper_ledger.py _config() and _observation() helpers use new fields
    - test_crypto_pair_clickhouse_sink.py uses new config fields
    - test_crypto_pair_report.py uses new config fields
  </behavior>
  <action>
**config_models.py changes:**

1. Remove `target_pair_cost_threshold: Decimal = Decimal("0.99")` from `CryptoPairPaperModeConfig` dataclass.
2. Add three fields after `fees` and before `safety`:
   ```python
   edge_buffer_per_leg: Decimal = Decimal("0.04")
   max_pair_completion_pct: Decimal = Decimal("0.80")
   min_projected_profit: Decimal = Decimal("0.03")
   ```
3. In `__post_init__`, replace `target_pair_cost_threshold` validation with:
   - `edge_buffer_per_leg > 0 and edge_buffer_per_leg < Decimal("0.5")` (else raise ValueError with field name)
   - `max_pair_completion_pct > 0 and max_pair_completion_pct <= 1` (else raise ValueError)
   - `min_projected_profit > 0` (else raise ValueError)
4. In `to_dict()`, remove `target_pair_cost_threshold` key; add three new keys with `str()` conversion.
5. In `from_dict()`, add the three new field extractions. Where `target_pair_cost_threshold` was read, replace. At the END of from_dict(), after building the dict to pass to constructor, silently drop `target_pair_cost_threshold` from incoming `d` if present (i.e., the key is simply ignored).

**paper_ledger.py changes:**

1. `PaperOpportunityObservation` (frozen dataclass): Remove `target_pair_cost_threshold: Decimal` required field. Add two optional fields:
   ```python
   target_yes_bid: Optional[Decimal] = None
   target_no_bid: Optional[Decimal] = None
   ```
   Update `__post_init__` to remove target_pair_cost_threshold validation. Add validation: if target_yes_bid is not None, must be > 0 and < 1; same for target_no_bid.
2. `PaperOrderIntent` (frozen dataclass): Remove `target_pair_cost_threshold: Decimal` required field. No replacement needed here — the intent doesn't need to store it.
3. `generate_order_intent()`: Change intended price assignment:
   - `intended_yes_price = observation.target_yes_bid if observation.target_yes_bid is not None else observation.yes_quote_price`
   - `intended_no_price = observation.target_no_bid if observation.target_no_bid is not None else observation.no_quote_price`
   Remove any read of `config.target_pair_cost_threshold` in this function.
4. Any other function in paper_ledger.py that reads `observation.target_pair_cost_threshold` or `intent.target_pair_cost_threshold` must be updated (search the file thoroughly).

**dev_seed.py changes:**

In `_demo_config()`, replace:
```python
"target_pair_cost_threshold": "0.97",
```
with:
```python
"edge_buffer_per_leg": "0.04",
"max_pair_completion_pct": "0.80",
"min_projected_profit": "0.03",
```

In `_build_observation()`, remove the `target_pair_cost_threshold="0.97"` argument. The observation call must not pass that field.

**Test file changes:**

`tests/test_crypto_pair_paper_ledger.py`:
- In `_config()` helper: replace `target_pair_cost_threshold: str = "0.97"` param and usages with the three new fields (keep similar helper signature for tests that vary config, but use new field names).
- In `_observation()` helper: remove `target_pair_cost_threshold` param. Add optional `target_yes_bid` and `target_no_bid` params defaulting to None.
- Update all test calls to use new helper signatures.
- Tests that specifically tested `target_pair_cost_threshold` validation errors must be rewritten to test `edge_buffer_per_leg` validation (e.g., test that `edge_buffer_per_leg=0` raises ValueError).

`tests/test_crypto_pair_clickhouse_sink.py`:
- Replace `"target_pair_cost_threshold": "0.97"` in config dicts with three new keys.
- Replace `target_pair_cost_threshold="0.97"` in observation constructor calls; observations now just omit the field or use defaults.
- Line 365 asserts `"target_pair_cost_threshold"` is present in some schema/dict — change to assert `"edge_buffer_per_leg"` instead.

`tests/test_crypto_pair_report.py`:
- Replace `"target_pair_cost_threshold": "0.97"` in config dicts with three new keys.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m pytest tests/test_crypto_pair_paper_ledger.py tests/test_crypto_pair_clickhouse_sink.py tests/test_crypto_pair_report.py -x -q --tb=short 2>&1 | tail -20</automated>
  </verify>
  <done>
    - CryptoPairPaperModeConfig instantiates with new fields and rejects target_pair_cost_threshold validation errors on new fields
    - CryptoPairPaperModeConfig.from_dict({"target_pair_cost_threshold": "0.97", ...}) does not raise (legacy key silently ignored)
    - PaperOpportunityObservation and PaperOrderIntent instantiate without target_pair_cost_threshold
    - generate_order_intent() uses target bids as intended prices when provided
    - dev_seed.build_demo_seed_batch() runs without error
    - Named test files pass
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Rewrite Gates 3+4 in accumulation_engine.py with target-bid gate</name>
  <files>
    packages/polymarket/crypto_pairs/accumulation_engine.py,
    tests/test_crypto_pair_accumulation_engine.py,
    tests/test_crypto_pair_backtest.py
  </files>
  <behavior>
    - Gate 3 now checks whether each leg's ask <= target_bid (ask meets target), not pair cost vs threshold
    - target_bid_yes = (fair_value_yes - edge_buffer) if fair_value_yes else (0.5 - edge_buffer)
    - target_bid_no  = (fair_value_no  - edge_buffer) if fair_value_no  else (0.5 - edge_buffer)
    - Gate 3 PASSES (hard_rule_passed=True) always; the logic just computes which legs meet target
    - Gate 4 is removed; _soft_rule_passes() helper is deleted
    - _select_legs() uses target_met booleans, not soft_rule booleans
    - If neither leg meets target: ACTION_SKIP with skip_reason="no_leg_meets_target_bid"
    - If at least one leg meets target: ACTION_ACCUMULATE with only the qualifying leg(s)
    - soft_rule_yes_passed = yes_ask_meets_target; soft_rule_no_passed = no_ask_meets_target (reuse field names)
    - rationale includes: target_bid_yes, target_bid_no, yes_ask_meets_target, no_ask_meets_target
    - projected_pair_cost still computed (sum of asks for selected legs); kept for downstream compat
    - hard_rule_passed is always True (kept for API compat) — the field is set before returning
    - BacktestResult.hard_rule_skips counter now counts "no_leg_meets_target_bid" skips
    - BacktestResult.soft_rule_skips is removed or always 0 — use hard_rule_skips for target-bid failures
  </behavior>
  <action>
**accumulation_engine.py Gate 3 replacement:**

Replace the entire current Gate 3 block (pair cost vs threshold) and Gate 4 block (_soft_rule_passes call) with the following logic. Keep the projected_pair_cost computation for all quotes (sum of yes_ask + no_ask), then:

```python
# Gate 3 — Target-bid gate (replaces pair-cost gate and soft-fair-value gate)
edge_buffer = config.edge_buffer_per_leg
_HALF = Decimal("0.5")

if state.fair_value_yes is not None:
    target_bid_yes = Decimal(str(state.fair_value_yes)) - edge_buffer
else:
    target_bid_yes = _HALF - edge_buffer

if state.fair_value_no is not None:
    target_bid_no = Decimal(str(state.fair_value_no)) - edge_buffer
else:
    target_bid_no = _HALF - edge_buffer

# Clamp to sane range [0.01, 0.99]
_CLAMP_LO = Decimal("0.01")
_CLAMP_HI = Decimal("0.99")
target_bid_yes = max(_CLAMP_LO, min(_CLAMP_HI, target_bid_yes))
target_bid_no  = max(_CLAMP_LO, min(_CLAMP_HI, target_bid_no))

yes_ask_meets_target = (state.yes_quote is not None and
                        state.yes_quote.ask_price <= target_bid_yes)
no_ask_meets_target  = (state.no_quote is not None and
                        state.no_quote.ask_price <= target_bid_no)

rationale["hard_rule_passed"] = True  # always True now (API compat)
rationale["target_bid_yes"] = str(target_bid_yes)
rationale["target_bid_no"] = str(target_bid_no)
rationale["yes_ask_meets_target"] = yes_ask_meets_target
rationale["no_ask_meets_target"] = no_ask_meets_target
rationale["soft_rule_yes"] = {"meets_target": yes_ask_meets_target}  # compat key
rationale["soft_rule_no"] = {"meets_target": no_ask_meets_target}    # compat key

if not yes_ask_meets_target and not no_ask_meets_target:
    rationale["skip_reason"] = "no_leg_meets_target_bid"
    return AccumulationIntent(
        action=ACTION_SKIP,
        hard_rule_passed=True,
        soft_rule_yes_passed=False,
        soft_rule_no_passed=False,
        rationale=rationale,
        projected_pair_cost=projected_pair_cost,
    )
```

Delete the `_soft_rule_passes()` helper function entirely.

Update `_select_legs()` to accept `yes_target_met` and `no_target_met` booleans instead of `soft_yes`/`soft_no`, and use those to determine which legs to include. The partial-pair-state logic (yes_only → only NO leg, no_only → only YES leg) stays the same.

After the gate, call `_select_legs()` with the new booleans. The `AccumulationIntent` returned for the ACCUMULATE case sets:
- `soft_rule_yes_passed = yes_ask_meets_target`
- `soft_rule_no_passed = no_ask_meets_target`
- `hard_rule_passed = True`

**tests/test_crypto_pair_accumulation_engine.py changes:**

1. Update `_config()` helper: replace `target_pair_cost_threshold="0.97"` with `edge_buffer_per_leg="0.04"` (and add `max_pair_completion_pct="0.80"`, `min_projected_profit="0.03"` if needed by from_dict).

2. Rewrite `TestHardRule` class — rename to `TestTargetBidGate`:
   - Test: `test_skip_when_neither_leg_meets_target` — set yes_price="0.50", no_price="0.50" with default edge_buffer=0.04 → target_bid=0.46 → neither meets → ACTION_SKIP, skip_reason="no_leg_meets_target_bid"
   - Test: `test_hard_rule_passed_always_true` — hard_rule_passed is True even on skip
   - Test: `test_accumulate_when_yes_meets_target` — yes_price="0.45", no_price="0.50" → yes meets (0.45 <= 0.46), no doesn't → ACCUMULATE with YES only
   - Test: `test_accumulate_when_no_meets_target` — yes_price="0.50", no_price="0.45" → no meets → ACCUMULATE with NO only
   - Test: `test_accumulate_when_both_legs_meet_target` — yes_price="0.45", no_price="0.44" → both meet → ACCUMULATE with both
   - Test: `test_rationale_has_target_bid_keys` — rationale contains "target_bid_yes", "target_bid_no", "yes_ask_meets_target", "no_ask_meets_target"
   - Test: `test_custom_edge_buffer_respected` — edge_buffer=0.10 → target_bid=0.40 → price 0.45 should NOT meet → SKIP
   - Remove `test_custom_threshold_respected` and other old threshold-based tests

3. Rewrite `TestSoftRule` class — rename to `TestTargetBidLegSelection`:
   - Test: `test_vacuous_pass_when_no_fair_values` — no fair values → target_bid = 0.46 → with prices 0.47/0.48, neither meets → SKIP (NOT accumulate). Note: this inverts the old behavior.
   - Test: `test_yes_leg_meets_target_when_ask_below_target_bid` — yes_ask=0.45 <= target_bid_yes=0.46 (no fair value, default 0.5-0.04) → soft_rule_yes_passed=True
   - Test: `test_no_leg_fails_when_ask_above_target_bid` — no_ask=0.50 > target_bid_no=0.46 → soft_rule_no_passed=False
   - Test: `test_skip_when_both_legs_fail_target` — both asks above target → ACTION_SKIP, skip_reason="no_leg_meets_target_bid"
   - Test: `test_soft_rule_compat_keys_in_rationale` — rationale has "soft_rule_yes" and "soft_rule_no" keys

4. Update `TestAccumulateAction`:
   - `test_accumulate_when_all_gates_pass`: change prices to yes_price="0.45", no_price="0.44" (both must meet target_bid=0.46)
   - `test_accumulate_includes_both_legs_when_no_partial`: same price adjustment
   - `test_projected_cost_is_populated_on_accumulate`: use yes=0.45, no=0.44 → projected_pair_cost=0.89
   - `test_accumulate_only_yes_when_no_blocked`: set yes_price="0.45" (meets), no_price="0.50" (doesn't meet) — no fair values, just relying on target_bid=0.46
   - `test_accumulate_only_no_when_yes_blocked`: set yes_price="0.50" (doesn't meet), no_price="0.44" (meets)

5. Update `TestPartialPairLogic`:
   - `test_yes_only_focuses_on_no_leg`: default prices — set no_price="0.44" so NO meets target. yes_accumulated="5".
   - `test_no_only_focuses_on_yes_leg`: set yes_price="0.44" so YES meets target. no_accumulated="5".
   - `test_yes_only_skip_when_soft_blocks_no`: set no_price="0.50" (doesn't meet target) with yes_accumulated="5" → SKIP
   - `test_no_only_skip_when_soft_blocks_yes`: set yes_price="0.50" (doesn't meet target) with no_accumulated="5" → SKIP
   - Remove fair_value_yes/fair_value_no from these tests unless specifically testing fair-value path

**tests/test_crypto_pair_backtest.py changes:**

1. Replace `_config()` helper `"target_pair_cost_threshold": "0.97"` with three new fields.
2. `test_config_snapshot_has_target_pair_cost_threshold()` — rename/rewrite to `test_config_snapshot_has_edge_buffer_per_leg()`, assert `"edge_buffer_per_leg"` in result.config_snapshot.
3. Tests that assert `result.hard_rule_skips == 1` when pair cost was 1.00: these used prices 0.50+0.50. In new logic, 0.50 > 0.46 target_bid for both legs → neither meets → skip counted as `hard_rule_skips`. Verify the backtest harness's `_classify()` maps `skip_reason="no_leg_meets_target_bid"` to `result.hard_rule_skips`. Update `backtest_harness.py` `_classify()` method: map `skip_reason == "no_leg_meets_target_bid"` to `result.hard_rule_skips += 1`.
4. Tests that assert `result.soft_rule_skips == 1` — these used prices that passed old pair cost but failed soft fair-value. With new logic, soft_rule_skips should always be 0. Update these tests: reclassify what they're testing. If the test observation used both asks above target_bid, it's a hard_rule_skip now. Adjust prices and assertions accordingly.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m pytest tests/test_crypto_pair_accumulation_engine.py tests/test_crypto_pair_backtest.py -x -q --tb=short 2>&1 | tail -25</automated>
  </verify>
  <done>
    - evaluate_accumulation() returns ACTION_ACCUMULATE when at least one leg's ask <= target_bid
    - evaluate_accumulation() returns ACTION_SKIP with skip_reason="no_leg_meets_target_bid" when no leg meets target
    - hard_rule_passed is always True
    - soft_rule_yes_passed / soft_rule_no_passed reflect per-leg target-met status
    - _soft_rule_passes() function no longer exists in accumulation_engine.py
    - backtest_harness._classify() maps "no_leg_meets_target_bid" to hard_rule_skips
    - Both test files pass
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Wire target-bid computation in paper_runner.py and update runner events test</name>
  <files>
    packages/polymarket/crypto_pairs/paper_runner.py,
    tests/test_crypto_pair_runner_events.py
  </files>
  <behavior>
    - build_default_paper_mode_config() uses new three-field config (no target_pair_cost_threshold)
    - CryptoPairRunnerSettings.__post_init__ validates edge_buffer_per_leg >= 0.01 instead of target_pair_cost_threshold
    - build_runner_settings() extracts new config keys from payload
    - build_observation() accepts and passes target_yes_bid, target_no_bid parameters
    - _process_opportunity() computes target bids (falls back to 0.5 - edge_buffer when fair value unavailable)
    - _process_opportunity() emits "target_bid_computed" runtime event each cycle
    - The fair value attempt is wrapped in try/except; failure means None → fallback target_bid used
    - test_crypto_pair_runner_events.py updated to use new config
  </behavior>
  <action>
**paper_runner.py changes:**

1. Remove `_OPERATOR_MAX_PAIR_COST = Decimal("0.97")` constant.

2. `build_default_paper_mode_config()`: Replace `"target_pair_cost_threshold": str(_OPERATOR_MAX_PAIR_COST)` with:
   ```python
   "edge_buffer_per_leg": "0.04",
   "max_pair_completion_pct": "0.80",
   "min_projected_profit": "0.03",
   ```

3. `CryptoPairRunnerSettings.__post_init__`: Replace the validation block that checks `paper_config.target_pair_cost_threshold > _OPERATOR_MAX_PAIR_COST` with:
   ```python
   if paper_config.edge_buffer_per_leg < Decimal("0.01"):
       raise ValueError(
           f"edge_buffer_per_leg={paper_config.edge_buffer_per_leg} is below minimum 0.01"
       )
   ```
   Remove the `_OPERATOR_MAX_PAIR_COST` reference and any profit-threshold check that referenced the old field.

4. `build_runner_settings()` key extraction list (lines ~272-282): Remove `"target_pair_cost_threshold"` from the list of keys extracted from payload. Add `"edge_buffer_per_leg"`, `"max_pair_completion_pct"`, `"min_projected_profit"` to the list.

5. `build_observation()` signature: Remove `target_pair_cost_threshold` parameter. Add `target_yes_bid: Optional[Decimal] = None` and `target_no_bid: Optional[Decimal] = None` parameters. Pass them through to `PaperOpportunityObservation(...)` constructor.

6. `_process_opportunity()`: After obtaining `yes_ask` and `no_ask` from the live quotes (or wherever they're currently extracted), add a target-bid computation block:

   ```python
   # Attempt fair value (will always be None in practice — PairOpportunity has no threshold/remaining_seconds)
   fair_value_yes: Optional[Decimal] = None
   fair_value_no: Optional[Decimal] = None
   try:
       from .fair_value import estimate_fair_value
       # opp (PairOpportunity) has no threshold or remaining_seconds — this block will always except
       fv_yes = estimate_fair_value(
           symbol=opp.symbol,
           duration_min=opp.duration_min,
           side="YES",
           underlying_price=float(opp.underlying_price),  # may not exist — will raise AttributeError
           threshold=float(opp.threshold),
           remaining_seconds=float(opp.remaining_seconds),
       )
       fair_value_yes = Decimal(str(fv_yes.fair_prob))
       fv_no = estimate_fair_value(
           symbol=opp.symbol,
           duration_min=opp.duration_min,
           side="NO",
           underlying_price=float(opp.underlying_price),
           threshold=float(opp.threshold),
           remaining_seconds=float(opp.remaining_seconds),
       )
       fair_value_no = Decimal(str(fv_no.fair_prob))
   except Exception:
       pass  # PairOpportunity has no threshold/remaining_seconds — fallback to 0.5

   edge_buffer = paper_config.edge_buffer_per_leg
   _HALF = Decimal("0.5")
   target_yes_bid = (fair_value_yes - edge_buffer) if fair_value_yes is not None else (_HALF - edge_buffer)
   target_no_bid  = (fair_value_no  - edge_buffer) if fair_value_no  is not None else (_HALF - edge_buffer)

   # Emit target_bid_computed event
   _emit_runtime_event(  # use whatever runtime event emission pattern exists in this file
       event_type="target_bid_computed",
       run_id=run_id,
       data={
           "fair_value_yes": str(fair_value_yes) if fair_value_yes is not None else None,
           "fair_value_no":  str(fair_value_no)  if fair_value_no  is not None else None,
           "target_bid_yes": str(target_yes_bid),
           "target_bid_no":  str(target_no_bid),
           "yes_ask":  str(yes_ask) if yes_ask is not None else None,
           "no_ask":   str(no_ask)  if no_ask  is not None else None,
           "yes_ask_meets_target": (yes_ask is not None and yes_ask <= target_yes_bid),
           "no_ask_meets_target":  (no_ask  is not None and no_ask  <= target_no_bid),
       },
   )
   ```

   Note: Look at how other runtime events are emitted in _process_opportunity() and follow the same pattern exactly. Do not invent a new emission mechanism.

   Then pass `target_yes_bid` and `target_no_bid` to `build_observation()`.

   Also pass `fair_value_yes` and `fair_value_no` to the `PairMarketState` constructor (these are already accepted per the existing engine interface — the engine uses them for fallback in the new target-bid computation, but in practice they'll be None since paper_runner can't compute them).

**tests/test_crypto_pair_runner_events.py changes:**

Line 161: Replace `target_pair_cost_threshold="0.97"` with the three new config fields. If line 161 is in a config dict, update accordingly. If it's a direct constructor call to `PaperOpportunityObservation`, remove the field (now optional/removed).

Run the test file after changes to confirm it passes.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m pytest tests/test_crypto_pair_runner_events.py -x -q --tb=short 2>&1 | tail -20</automated>
  </verify>
  <done>
    - build_default_paper_mode_config() returns config with edge_buffer_per_leg="0.04" (not target_pair_cost_threshold)
    - CryptoPairRunnerSettings raises ValueError when edge_buffer_per_leg < 0.01
    - _process_opportunity() computes target_yes_bid = 0.46, target_no_bid = 0.46 (fallback path, 0.5 - 0.04)
    - "target_bid_computed" runtime event is emitted each cycle with the expected fields
    - test_crypto_pair_runner_events.py passes
    - python -m polytool --help loads without error
  </done>
</task>

<task type="auto">
  <name>Task 4: Full regression run and smoke test</name>
  <files>
    (no new files — verification only)
  </files>
  <action>
Run the full affected test suite plus the smoke test. Fix any remaining breakage that surfaces.

The most common remaining failures will be:
- Any test that still constructs `PaperOpportunityObservation` with `target_pair_cost_threshold` that was missed in Task 1
- Any test that checks rationale keys like `"soft_rule_yes": {"reason": "underpriced"}` (old soft-rule format) — these must check new format `"soft_rule_yes": {"meets_target": True/False}`
- Any test in test_crypto_pair_backtest.py that expects `result.soft_rule_skips > 0` — soft_rule_skips should always be 0 now; reclassify the skip as hard_rule_skips if that makes sense, or update the test to reflect new behavior
- Any import of `_soft_rule_passes` from accumulation_engine

After all test fixes, run:
```bash
python -m pytest tests/test_crypto_pair_accumulation_engine.py tests/test_crypto_pair_backtest.py tests/test_crypto_pair_paper_ledger.py tests/test_crypto_pair_runner_events.py tests/test_crypto_pair_clickhouse_sink.py tests/test_crypto_pair_report.py -x -q --tb=short
```

Then run the full suite:
```bash
python -m pytest tests/ -x -q --tb=short
```

Then verify the CLI loads:
```bash
python -m polytool --help
```

Then do a quick behavioral smoke: instantiate CryptoPairPaperModeConfig with the new fields and verify it serializes/deserializes correctly:
```python
from packages.polymarket.crypto_pairs.config_models import CryptoPairPaperModeConfig
cfg = CryptoPairPaperModeConfig.from_dict({"max_capital_per_market_usdc": "25", "max_open_paired_notional_usdc": "50", "edge_buffer_per_leg": "0.04", "max_pair_completion_pct": "0.80", "min_projected_profit": "0.03", "fees": {"maker_rebate_bps": "20", "maker_fee_bps": "0", "taker_fee_bps": "0"}, "safety": {"stale_quote_timeout_seconds": 15, "max_unpaired_exposure_seconds": 120, "block_new_intents_with_open_unpaired": True, "require_fresh_quotes": True}})
assert cfg.edge_buffer_per_leg == Decimal("0.04")

# Legacy backward compat test
cfg2 = CryptoPairPaperModeConfig.from_dict({"max_capital_per_market_usdc": "25", "max_open_paired_notional_usdc": "50", "target_pair_cost_threshold": "0.97", "edge_buffer_per_leg": "0.04", "max_pair_completion_pct": "0.80", "min_projected_profit": "0.03", "fees": {"maker_rebate_bps": "20", "maker_fee_bps": "0", "taker_fee_bps": "0"}, "safety": {"stale_quote_timeout_seconds": 15, "max_unpaired_exposure_seconds": 120, "block_new_intents_with_open_unpaired": True, "require_fresh_quotes": True}})
assert cfg2.edge_buffer_per_leg == Decimal("0.04")
print("Backward compat: PASS")
```
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m pytest tests/test_crypto_pair_accumulation_engine.py tests/test_crypto_pair_backtest.py tests/test_crypto_pair_paper_ledger.py tests/test_crypto_pair_runner_events.py tests/test_crypto_pair_clickhouse_sink.py tests/test_crypto_pair_report.py -q --tb=short 2>&1 | tail -15</automated>
  </verify>
  <done>
    - All 6 named test files pass
    - Full test suite (tests/) shows no new regressions vs baseline
    - python -m polytool --help loads cleanly
    - CryptoPairPaperModeConfig backward compat confirmed: old "target_pair_cost_threshold" key silently ignored
    - evaluate_accumulation() generates ACTION_ACCUMULATE when ask prices fall at or below target_bid (e.g., yes_ask=0.45 with edge_buffer=0.04)
  </done>
</task>

</tasks>

<verification>
After all tasks, confirm the strategy pivot is end-to-end coherent:

1. `python -c "from packages.polymarket.crypto_pairs.config_models import CryptoPairPaperModeConfig; cfg = CryptoPairPaperModeConfig(); print(cfg.edge_buffer_per_leg)"` prints `0.04`
2. `python -c "from packages.polymarket.crypto_pairs.accumulation_engine import evaluate_accumulation, PairMarketState, BestQuote, LEG_YES, LEG_NO, ACTION_ACCUMULATE; from packages.polymarket.crypto_pairs.config_models import CryptoPairPaperModeConfig; from decimal import Decimal; st = PairMarketState(symbol='BTC', duration_min=5, market_id='test', yes_quote=BestQuote(leg=LEG_YES, token_id='yes-test', ask_price=Decimal('0.45')), no_quote=BestQuote(leg=LEG_NO, token_id='no-test', ask_price=Decimal('0.50'))); cfg = CryptoPairPaperModeConfig(); r = evaluate_accumulation(st, cfg); print(r.action, r.hard_rule_passed, LEG_YES in r.legs)"` prints `accumulate True True`
3. `python -m pytest tests/ -q --tb=short` — report exact counts, 0 failures
</verification>

<success_criteria>
- evaluate_accumulation() generates ACTION_ACCUMULATE for real market prices (e.g., yes_ask=0.45 with default edge_buffer=0.04 → target_bid=0.46 → ask meets target)
- "no_leg_meets_target_bid" is the skip_reason when neither leg meets target (replaces "hard_rule_failed")
- CryptoPairPaperModeConfig accepts legacy "target_pair_cost_threshold" in from_dict() without error
- paper_runner emits "target_bid_computed" runtime events
- generate_order_intent() uses target bids as intended order prices
- Full test suite passes with 0 regressions
</success_criteria>

<output>
After completion, create `.planning/quick/46-strategy-pivot-async-leg-accumulation-ma/46-SUMMARY.md` following the summary template.
</output>
