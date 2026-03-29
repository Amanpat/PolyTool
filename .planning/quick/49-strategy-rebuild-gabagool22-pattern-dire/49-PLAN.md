---
phase: quick-049
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/polymarket/crypto_pairs/accumulation_engine.py
  - packages/polymarket/crypto_pairs/config_models.py
  - packages/polymarket/crypto_pairs/paper_ledger.py
  - packages/polymarket/crypto_pairs/paper_runner.py
autonomous: true
requirements: [QUICK-049]

must_haves:
  truths:
    - "Momentum signal fires when abs(btc_price_change) > 0.003 over 30s window"
    - "Signal=UP causes favorite=YES taker entry + hedge=NO maker entry at <=0.20"
    - "Signal=DOWN causes favorite=NO taker entry + hedge=YES maker entry at <=0.20"
    - "Each bracket_id entered at most once (cooldown enforced)"
    - "favorite_leg_size_usdc=8 and hedge_leg_size_usdc=2 by default"
    - "Paper mode simulates: favorite fills at ask, hedge fills only if ask <= hedge limit"
    - "Observation log records reference_price, price_change_pct, signal_direction each cycle"
    - "All existing tests still pass after changes"
  artifacts:
    - path: "packages/polymarket/crypto_pairs/accumulation_engine.py"
      provides: "Directional momentum signal + favorite/hedge entry logic"
      contains: "MomentumSignal"
    - path: "packages/polymarket/crypto_pairs/config_models.py"
      provides: "New config params: momentum_window_seconds, momentum_threshold, max_favorite_entry, max_hedge_price, favorite_leg_size_usdc, hedge_leg_size_usdc"
  key_links:
    - from: "paper_runner.py run loop"
      to: "accumulation_engine.evaluate_directional_entry()"
      via: "reference feed snapshot price history"
    - from: "accumulation_engine momentum signal"
      to: "CryptoPairPaperModeConfig"
      via: "config.momentum_threshold, config.max_favorite_entry, config.max_hedge_price"
---

<objective>
Replace the per-leg target-bid accumulation gate with a directional momentum strategy
modeled on gabagool22's actual pattern: read BTC/ETH momentum from the reference feed,
buy the FAVORITE leg as taker when momentum signals, buy the HEDGE leg as a cheap maker.

Purpose: The current strategy (target_bid = 0.5 - edge_buffer) never fires because 5m
crypto markets price the favorite at 0.70+ (well above 0.46). Gabagool22 wins by reading
momentum correctly and accepting asymmetric sizing ($8 favorite / $2 hedge), not by finding
pair-cost arbitrage. This rebuild aligns the bot with the observed winning pattern.

Output: Updated accumulation_engine.py with momentum signal + directional entry logic,
updated config_models.py with new params, minimal changes to paper_ledger.py for new
observation fields, wired into paper_runner.py. All existing tests preserved.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@packages/polymarket/crypto_pairs/accumulation_engine.py
@packages/polymarket/crypto_pairs/config_models.py
@packages/polymarket/crypto_pairs/paper_ledger.py
@packages/polymarket/crypto_pairs/paper_runner.py
@packages/polymarket/crypto_pairs/reference_feed.py

<interfaces>
<!-- Key contracts the executor needs. Do NOT change these external signatures. -->

From reference_feed.py:
```python
@dataclass(frozen=True)
class ReferencePriceSnapshot:
    symbol: str
    price: Optional[float]      # spot price in USD; None if not yet received
    observed_at_s: Optional[float]
    connection_state: FeedConnectionState
    is_stale: bool
    is_usable: bool             # property: price is not None, not stale, CONNECTED

feed.get_snapshot(symbol: str) -> ReferencePriceSnapshot
```

From accumulation_engine.py (current public interface — keep backward compat):
```python
ACTION_ACCUMULATE = "accumulate"
ACTION_SKIP = "skip"
ACTION_FREEZE = "freeze"

@dataclass(frozen=True)
class AccumulationIntent:
    action: str
    legs: tuple[str, ...]
    rationale: dict[str, Any]
    projected_pair_cost: Optional[Decimal]
    hard_rule_passed: bool
    soft_rule_yes_passed: bool
    soft_rule_no_passed: bool

def evaluate_accumulation(state: PairMarketState, config: CryptoPairPaperModeConfig) -> AccumulationIntent
```

From config_models.py (current fields — do not remove):
```python
@dataclass(frozen=True)
class CryptoPairPaperModeConfig:
    filters: CryptoPairFilterConfig
    max_capital_per_market_usdc: Decimal    # default 250
    max_open_paired_notional_usdc: Decimal  # default 500
    edge_buffer_per_leg: Decimal            # default 0.04 (kept for backward compat)
    max_pair_completion_pct: Decimal        # default 0.80
    min_projected_profit: Decimal           # default 0.03
    fees: CryptoPairFeeAssumptionConfig
    safety: CryptoPairSafetyConfig
```

From paper_ledger.py (frozen dataclass — add fields with defaults to preserve compat):
```python
@dataclass(frozen=True)
class PaperOpportunityObservation:
    opportunity_id, run_id, observed_at, market_id, condition_id,
    slug, symbol, duration_min, yes_token_id, no_token_id,
    yes_quote_price: Decimal, no_quote_price: Decimal,
    quote_age_seconds: int = 0,
    source: str = "scanner",
    assumptions: tuple[str, ...] = ()
```

From paper_runner.py (CryptoPairRunnerSettings — keep existing fields):
```python
@dataclass(frozen=True)
class CryptoPairRunnerSettings:
    paper_config: CryptoPairPaperModeConfig
    artifact_base_dir, kill_switch_path, duration_seconds, cycle_interval_seconds,
    max_open_pairs, daily_loss_cap_usdc, min_profit_threshold_usdc,
    symbol_filters, duration_filters, reference_feed_provider,
    cycle_limit, heartbeat_interval_seconds, sink_flush_mode
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add momentum config params and directional accumulation engine</name>
  <files>
    packages/polymarket/crypto_pairs/config_models.py
    packages/polymarket/crypto_pairs/accumulation_engine.py
    tests/test_crypto_pair_momentum.py
  </files>
  <behavior>
    - Test 1: MomentumConfig default values are momentum_window_seconds=30, momentum_threshold=0.003, max_favorite_entry=0.75, max_hedge_price=0.20, favorite_leg_size_usdc=8.0, hedge_leg_size_usdc=2.0
    - Test 2: CryptoPairPaperModeConfig.from_dict() with no momentum keys uses defaults (backward compat)
    - Test 3: CryptoPairPaperModeConfig.from_dict({"momentum": {"momentum_threshold": 0.005}}) sets threshold=0.005
    - Test 4: evaluate_directional_entry() with no price history returns action=SKIP, signal_direction=NONE
    - Test 5: evaluate_directional_entry() with feed frozen (is_usable=False) returns action=FREEZE
    - Test 6: price history [100.0, 100.0, 100.3] with threshold=0.003 fires signal=UP (0.3% change)
    - Test 7: signal=UP, yes_ask=0.72 (<=0.75), no_ask=0.28 -> favorite=YES taker, hedge=NO maker at 0.20
    - Test 8: signal=DOWN, no_ask=0.70 (<=0.75), yes_ask=0.30 -> favorite=NO taker, hedge=YES maker at 0.20
    - Test 9: signal=UP, yes_ask=0.80 (>0.75 max_favorite_entry) -> action=SKIP (favorite too expensive)
    - Test 10: bracket_id already in cooldown_brackets set -> action=SKIP, reason="bracket_cooldown"
    - Test 11: AccumulationIntent.to_dict() includes signal_direction, price_change_pct, reference_price fields
    - Test 12: favorite_leg_size from config.momentum.favorite_leg_size_usdc, hedge from hedge_leg_size_usdc
  </behavior>
  <action>
    1. In config_models.py, add a new frozen dataclass MomentumConfig with fields:
       - momentum_window_seconds: int = 30
       - momentum_threshold: float = 0.003  (0.3% move triggers signal)
       - max_favorite_entry: float = 0.75   (don't buy favorite above this price)
       - max_hedge_price: float = 0.20      (max price for hedge leg limit order)
       - favorite_leg_size_usdc: float = 8.0
       - hedge_leg_size_usdc: float = 2.0
       Add from_dict() and to_dict() with validation (threshold > 0, leg sizes > 0,
       max_favorite_entry in (0,1), max_hedge_price in (0,1)).

    2. Add momentum: MomentumConfig field to CryptoPairPaperModeConfig with
       default_factory=MomentumConfig. Update __post_init__ to handle Mapping -> MomentumConfig
       coercion (same pattern as existing filters/fees/safety). Update to_dict() and from_dict()
       to include "momentum" key. Keep all existing fields intact — do not remove or rename them.

    3. In accumulation_engine.py, add:
       a. New dataclass MomentumSignal(signal_direction: str, price_change_pct: float,
          reference_price: float, baseline_price: float). signal_direction in ("UP", "DOWN", "NONE").
       b. New function compute_momentum_signal(price_history: list[float],
          threshold: float) -> MomentumSignal:
          - price_history is newest-last (append-only deque flattened to list)
          - baseline = price_history[0], current = price_history[-1]
          - if len < 2: return NONE signal
          - pct_change = (current - baseline) / baseline
          - if pct_change > threshold: UP, elif pct_change < -threshold: DOWN, else NONE
       c. Extended PairMarketState: add cooldown_brackets: frozenset[str] = field(default=frozenset())
          and price_history: tuple[float, ...] = () to carry rolling feed prices into the engine.
          Both new fields have defaults so all existing call sites stay valid.
       d. New function evaluate_directional_entry(state: PairMarketState,
          config: CryptoPairPaperModeConfig) -> AccumulationIntent:
          - Gate 1: feed usable check (same as existing _feed_is_usable) -> FREEZE if not
          - Gate 2: quote availability check -> SKIP if missing
          - Gate 3: compute_momentum_signal(list(state.price_history), config.momentum.momentum_threshold)
            If signal.signal_direction == "NONE": SKIP with reason="no_momentum_signal"
          - Gate 4: cooldown check — if state.market_id in state.cooldown_brackets: SKIP, reason="bracket_cooldown"
          - Gate 5: favorite selection based on signal direction
            * signal=UP: favorite_leg=YES, hedge_leg=NO
            * signal=DOWN: favorite_leg=NO, hedge_leg=YES
          - Gate 6: favorite price check — if favorite_ask > config.momentum.max_favorite_entry: SKIP, reason="favorite_too_expensive"
          - Entry: return ACTION_ACCUMULATE, legs=(favorite_leg, hedge_leg)
          - rationale dict must include: signal_direction, price_change_pct, reference_price,
            favorite_leg, favorite_price, hedge_leg, hedge_price (= config.momentum.max_hedge_price),
            favorite_leg_size_usdc, hedge_leg_size_usdc
          - Preserve all existing AccumulationIntent fields for backward compat;
            hard_rule_passed=True on ACCUMULATE, False otherwise.
            soft_rule_yes_passed = (favorite_leg == "YES"), soft_rule_no_passed = (favorite_leg == "NO")

    4. Keep existing evaluate_accumulation() function untouched. The new function
       evaluate_directional_entry() is additive. paper_runner.py will call the new one.

    5. Create tests/test_crypto_pair_momentum.py with the 12 behaviors above.
       Use only offline inputs (no network). Inject mock ReferencePriceSnapshot instances.
  </action>
  <verify>
    <automated>python -m pytest tests/test_crypto_pair_momentum.py -x -q --tb=short</automated>
  </verify>
  <done>
    All 12 tests pass. MomentumConfig is importable from config_models. evaluate_directional_entry
    is importable from accumulation_engine. CryptoPairPaperModeConfig.from_dict() with no
    "momentum" key still constructs successfully (backward compat confirmed).
  </done>
</task>

<task type="auto">
  <name>Task 2: Wire directional engine into paper runner and extend observation logging</name>
  <files>
    packages/polymarket/crypto_pairs/paper_runner.py
    packages/polymarket/crypto_pairs/paper_ledger.py
  </files>
  <action>
    1. In paper_ledger.py, add optional fields to PaperOpportunityObservation with defaults
       (so all existing test fixtures continue to work):
       - reference_price: Optional[float] = None
       - price_change_pct: Optional[float] = None
       - signal_direction: str = "NONE"      # "UP", "DOWN", or "NONE"
       - favorite_side: Optional[str] = None # "YES" or "NO"
       - hedge_side: Optional[str] = None
       - entry_timing_seconds: Optional[int] = None   # seconds elapsed in the bracket
       Update to_dict() to include these fields.

    2. In paper_runner.py, make these targeted changes only — touch nothing else:

       a. Add a per-symbol rolling price buffer: a collections.deque of floats
          per symbol, max length = config.momentum.momentum_window_seconds (default 30).
          Initialize in the run-loop setup area as `_price_history: dict[str, deque] = {}`.

       b. Each cycle, after getting the feed snapshot for a market's symbol, if
          snapshot.is_usable and snapshot.price is not None:
          append snapshot.price to _price_history[symbol].

       c. Replace the call to evaluate_accumulation() with evaluate_directional_entry().
          Build PairMarketState with:
          - price_history=tuple(_price_history.get(state.symbol, deque()))
          - cooldown_brackets=frozenset(_entered_brackets)  (new set, see below)
          All other existing fields stay the same.

       d. Add _entered_brackets: set[str] = set() in run-loop setup.
          After a successful ACTION_ACCUMULATE, add state.market_id to _entered_brackets.
          This enforces one entry per bracket window maximum.

       e. When building PaperOpportunityObservation (in build_observation or inline),
          populate the new fields from the AccumulationIntent rationale dict:
          - reference_price = rationale.get("reference_price")
          - price_change_pct = rationale.get("price_change_pct")
          - signal_direction = rationale.get("signal_direction", "NONE")
          - favorite_side = rationale.get("favorite_leg")
          - hedge_side = rationale.get("hedge_leg")
          Only populate if the new fields exist on the observation dataclass (guard with hasattr).

       f. For paper fill simulation: favorite leg fills at current best ask (existing
          DeterministicPaperExecutionAdapter behavior is correct for taker). Hedge leg should
          simulate: fill only if best ask <= config.momentum.max_hedge_price. To implement this
          WITHOUT breaking DeterministicPaperExecutionAdapter, add a new adapter class
          DirectionalPaperExecutionAdapter that overrides simulate_fills():
          - For the favorite leg: fill at ask_price (same as before)
          - For the hedge leg: fill at max_hedge_price ONLY if current ask <= max_hedge_price,
            otherwise return no fill for that leg (omit from fills list)
          Use DirectionalPaperExecutionAdapter when evaluate_directional_entry is active.
          Keep DeterministicPaperExecutionAdapter for any path that still uses evaluate_accumulation.

       g. Update build_default_paper_mode_config() to pass through any momentum overrides
          from the config payload. The config already handles this via CryptoPairPaperModeConfig.from_dict().

    3. DO NOT modify: reference_feed.py, market_discovery.py, opportunity_scan.py, clickhouse_sink.py,
       event_models.py, live_runner.py, live_execution.py, clob_order_client.py, position_store.py,
       reporting.py, config_models schema_version, or any tests outside test_crypto_pair_momentum.py.

    4. Verify existing tests still pass with:
       python -m pytest tests/ -x -q --tb=short -k "crypto_pair"
  </action>
  <verify>
    <automated>python -m pytest tests/ -x -q --tb=short -k "crypto_pair"</automated>
  </verify>
  <done>
    All crypto_pair tests pass. evaluate_directional_entry is called in the paper runner
    run loop. Price history deque is populated each cycle. _entered_brackets cooldown
    is enforced. New observation fields (reference_price, price_change_pct, signal_direction,
    favorite_side, hedge_side) are logged when signal fires.
  </done>
</task>

<task type="auto">
  <name>Task 3: 10-minute paper soak and dev log</name>
  <files>
    docs/dev_logs/2026-03-29_gabagool_strategy_rebuild.md
  </files>
  <action>
    1. Run the smoke test to confirm the CLI still loads cleanly:
       python -m polytool --help

    2. Run a 10-minute paper soak:
       python -m polytool crypto-pair-run --duration-minutes 10 --symbol BTC --symbol ETH \
         --auto-report --reference-feed-provider coinbase

       Capture the terminal output. Find and read the paper_soak_summary.json and any
       runtime_events files from the most recent run directory under
       artifacts/tapes/crypto/paper_runs/.

    3. Report from the soak output:
       - How many momentum signals fired in 10 minutes
       - How many entries were made (favorite + hedge leg pairs)
       - Entry prices (favorite_price, hedge_price)
       - Signal directions observed (UP vs DOWN split)
       - Whether any brackets settled during the run (and if so, outcome)
       - Whether hedge fills occurred (asks dropped below 0.20)

    4. Write dev log at docs/dev_logs/2026-03-29_gabagool_strategy_rebuild.md including:
       - Summary of what changed (3 paragraphs max): old strategy vs new strategy,
         config params added, files touched
       - Paste the paper_soak_summary.json verbatim
       - Paste representative runtime_events lines showing signal fires and entries (first 20 lines max)
       - Note any unexpected behavior or blockers
       - Open questions for next packet (e.g., hedge fill rate too low? signal fires too rarely?)

    5. Run full regression suite and record the count:
       python -m pytest tests/ -x -q --tb=short
       Report exact counts: "N passed, M failed, K skipped."
  </action>
  <verify>
    <automated>python -m pytest tests/ -q --tb=short 2>&1 | tail -5</automated>
  </verify>
  <done>
    Dev log exists at docs/dev_logs/2026-03-29_gabagool_strategy_rebuild.md.
    Soak ran for 10 minutes without crash. paper_soak_summary.json is in dev log.
    Full regression suite reports 0 failures. Any new test count difference from
    pre-task baseline is due to test_crypto_pair_momentum.py additions only.
  </done>
</task>

</tasks>

<verification>
After all tasks complete:
1. python -m polytool --help loads without import errors
2. python -m pytest tests/ -q --tb=short shows 0 failures
3. evaluate_directional_entry is exported from accumulation_engine
4. MomentumConfig is exported from config_models
5. CryptoPairPaperModeConfig.from_dict({}) still works (no "momentum" key required)
6. Dev log exists with soak results
</verification>

<success_criteria>
- Strategy uses directional momentum signal (reference feed price change over 30s window)
  instead of pair-cost threshold gate
- Signal=UP -> buy YES as taker ($8), place NO maker limit at max_hedge_price ($2)
- Signal=DOWN -> buy NO as taker ($8), place YES maker limit at max_hedge_price ($2)
- One entry per bracket_id (cooldown enforced)
- Paper soak ran 10 minutes with no crash; signal fires logged; entries logged
- All existing crypto_pair tests pass; no files outside crypto_pairs/ modified
</success_criteria>

<output>
After completion, create .planning/quick/49-strategy-rebuild-gabagool22-pattern-dire/49-SUMMARY.md
</output>
