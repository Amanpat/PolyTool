---
phase: quick-019
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/polymarket/crypto_pairs/backtest_harness.py
  - tools/cli/crypto_pair_backtest.py
  - tests/test_crypto_pair_backtest.py
  - docs/features/FEATURE-crypto-pair-backtest-v0.md
  - docs/dev_logs/2026-03-23_phase1a_crypto_pair_backtest_v0.md
  - polytool/__main__.py
autonomous: true
requirements: [PHASE-1A-BACKTEST]

must_haves:
  truths:
    - "`python -m polytool crypto-pair-backtest --help` exits 0 and shows usage"
    - "Running with a synthetic JSONL input produces a manifest, summary.json, and report.md under artifacts/crypto_pairs/backtests/<date>/<run_id>/"
    - "Stale-feed observations produce feed_stale_skips > 0 in the summary"
    - "Observations where YES_ask + NO_ask > 0.97 produce hard_rule_skips > 0 in the summary"
    - "Observations passing all gates produce intents_generated > 0 and reflect in completed_pairs"
    - "All offline tests pass deterministically with no network calls"
  artifacts:
    - path: "packages/polymarket/crypto_pairs/backtest_harness.py"
      provides: "BacktestHarness class — pure-function replay loop over observation records"
      exports: ["BacktestHarness", "BacktestObservation", "BacktestResult"]
    - path: "tools/cli/crypto_pair_backtest.py"
      provides: "CLI entrypoint with build_parser() and main(argv)"
    - path: "tests/test_crypto_pair_backtest.py"
      provides: "Offline deterministic test suite"
    - path: "docs/features/FEATURE-crypto-pair-backtest-v0.md"
      provides: "Feature doc with input contract and metrics definition"
  key_links:
    - from: "tools/cli/crypto_pair_backtest.py"
      to: "packages/polymarket/crypto_pairs/backtest_harness.py"
      via: "BacktestHarness.run(observations)"
    - from: "polytool/__main__.py"
      to: "tools/cli/crypto_pair_backtest.py"
      via: "crypto_pair_backtest_main registered in _COMMAND_HANDLER_NAMES"
    - from: "backtest_harness.py"
      to: "accumulation_engine.evaluate_accumulation"
      via: "called per observation with constructed PairMarketState"
    - from: "backtest_harness.py"
      to: "fair_value.estimate_fair_value"
      via: "called per observation when threshold and remaining_seconds are provided"
---

<objective>
Add a deterministic backtest/history harness for the Phase 1A crypto-pair bot.

Purpose: Allow offline replay of historical or synthetic quote snapshots through the existing fair-value and accumulation logic to measure how the strategy would have behaved — opportunities observed, intents generated, completed pairs, pair costs, partial-leg incidence, and feed/safety skip rates. This is the pre-requisite evaluation artifact before a 24-48h paper soak.

Output:
- `packages/polymarket/crypto_pairs/backtest_harness.py` — pure replay engine
- `tools/cli/crypto_pair_backtest.py` — CLI entrypoint (`crypto-pair-backtest`)
- `tests/test_crypto_pair_backtest.py` — offline test suite
- `docs/features/FEATURE-crypto-pair-backtest-v0.md` — feature doc
- `docs/dev_logs/2026-03-23_phase1a_crypto_pair_backtest_v0.md` — dev log
- `polytool/__main__.py` updated to register the new command
- Artifacts written to `artifacts/crypto_pairs/backtests/<YYYY-MM-DD>/<run_id>/`
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/CLAUDE.md
@D:/Coding Projects/Polymarket/PolyTool/packages/polymarket/crypto_pairs/accumulation_engine.py
@D:/Coding Projects/Polymarket/PolyTool/packages/polymarket/crypto_pairs/fair_value.py
@D:/Coding Projects/Polymarket/PolyTool/packages/polymarket/crypto_pairs/reference_feed.py
@D:/Coding Projects/Polymarket/PolyTool/packages/polymarket/crypto_pairs/paper_runner.py
@D:/Coding Projects/Polymarket/PolyTool/packages/polymarket/crypto_pairs/position_store.py
@D:/Coding Projects/Polymarket/PolyTool/tools/cli/crypto_pair_run.py
@D:/Coding Projects/Polymarket/PolyTool/polytool/__main__.py
@D:/Coding Projects/Polymarket/PolyTool/tests/test_crypto_pair_accumulation_engine.py

<interfaces>
<!-- Key types the executor must use. Extracted from existing source files. -->

From packages/polymarket/crypto_pairs/accumulation_engine.py:
```python
# Input model
@dataclass(frozen=True)
class BestQuote:
    leg: str        # "YES" | "NO"
    token_id: str
    ask_price: Decimal

@dataclass(frozen=True)
class PairMarketState:
    symbol: str
    duration_min: int
    market_id: str
    yes_quote: Optional[BestQuote]
    no_quote: Optional[BestQuote]
    yes_accumulated_size: Decimal = Decimal("0")
    no_accumulated_size: Decimal = Decimal("0")
    fair_value_yes: Optional[float] = None
    fair_value_no: Optional[float] = None
    feed_snapshot: Optional[ReferencePriceSnapshot] = None

# Output model
@dataclass(frozen=True)
class AccumulationIntent:
    action: str    # ACTION_ACCUMULATE | ACTION_SKIP | ACTION_FREEZE
    legs: tuple[str, ...]
    rationale: dict[str, Any]
    projected_pair_cost: Optional[Decimal]
    hard_rule_passed: bool
    soft_rule_yes_passed: bool
    soft_rule_no_passed: bool

# Constants
ACTION_ACCUMULATE = "accumulate"
ACTION_SKIP = "skip"
ACTION_FREEZE = "freeze"
LEG_YES = "YES"
LEG_NO = "NO"

# Core function
def evaluate_accumulation(state: PairMarketState, config: CryptoPairPaperModeConfig) -> AccumulationIntent: ...
```

From packages/polymarket/crypto_pairs/fair_value.py:
```python
def estimate_fair_value(
    symbol: str,
    duration_min: int,
    side: str,          # "YES" or "NO"
    underlying_price: float,
    threshold: float,
    remaining_seconds: float,
    *,
    annual_vol: Optional[float] = None,
) -> FairValueEstimate:
    # Returns FairValueEstimate with .fair_prob in (0.005, 0.995)
    ...
```

From packages/polymarket/crypto_pairs/reference_feed.py:
```python
@dataclass(frozen=True)
class ReferencePriceSnapshot:
    symbol: str
    price: Optional[float]
    observed_at_s: Optional[float]
    connection_state: FeedConnectionState
    is_stale: bool
    stale_threshold_s: float
    feed_source: str
    # .is_usable → True when connected, fresh, price not None

class FeedConnectionState(str, Enum):
    NEVER_CONNECTED = "never_connected"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"

# Test helper — build a fresh, usable snapshot directly:
# ReferencePriceSnapshot(symbol="BTC", price=60000.0, observed_at_s=1000.0,
#   connection_state=FeedConnectionState.CONNECTED, is_stale=False,
#   stale_threshold_s=15.0, feed_source="binance")
```

From packages/polymarket/crypto_pairs/paper_runner.py:
```python
# Config builder (reuse for backtest defaults)
def build_default_paper_mode_config() -> CryptoPairPaperModeConfig:
    # Returns config with target_pair_cost_threshold=0.97, maker_rebate_bps=20

# Operator hard limits — backtest MUST respect these:
_OPERATOR_MAX_PAIR_COST = Decimal("0.97")
```

From position_store.py — artifact directory pattern:
```python
# run_dir = artifact_base_dir / started_at.date().isoformat() / run_id
# e.g. artifacts/crypto_pairs/backtests/2026-03-23/abc123def456/
```

CLI registration pattern from polytool/__main__.py:
```python
# 1. Add entrypoint variable at module level (line ~66 area):
crypto_pair_backtest_main = _command_entrypoint("tools.cli.crypto_pair_backtest")

# 2. Add to _COMMAND_HANDLER_NAMES dict:
"crypto-pair-backtest": "crypto_pair_backtest_main",

# 3. Add to print_usage() under the Crypto Pair Bot section:
print("  crypto-pair-backtest  Replay historical/synthetic pair observations, emit eval artifacts")
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement backtest_harness.py — pure replay engine</name>
  <files>
    packages/polymarket/crypto_pairs/backtest_harness.py
    tests/test_crypto_pair_backtest.py
  </files>
  <behavior>
    Input contract — BacktestObservation (each record in the JSONL/list):
      - symbol: str ("BTC", "ETH", "SOL")
      - duration_min: int (5 or 15)
      - market_id: str
      - yes_ask: Optional[float]  — None triggers quote-missing skip
      - no_ask: Optional[float]   — None triggers quote-missing skip
      - underlying_price: Optional[float]  — used for fair-value; None → no fair-value filter
      - threshold: Optional[float]         — market resolution threshold
      - remaining_seconds: Optional[float] — time to expiry; None → no fair-value filter
      - feed_is_stale: bool (default False) — when True, forces FREEZE, counted as feed_stale_skip
      - timestamp_iso: Optional[str]        — preserved in output records, not used for logic

    BacktestHarness.run(observations: list[BacktestObservation]) → BacktestResult:
      For each observation:
        1. Build ReferencePriceSnapshot: if feed_is_stale=True → is_stale=True (FREEZE path);
           else build a fresh connected snapshot using observation.underlying_price (or price=0.0 if None, still connected/fresh so logic proceeds to quote/hard-cost gates)
        2. Compute fair values if underlying_price, threshold, and remaining_seconds are all present
        3. Build PairMarketState and call evaluate_accumulation(state, config)
        4. Classify outcome into one of: feed_stale_skip, quote_skip, hard_rule_skip, soft_rule_skip, accumulate_intent
        5. Track partial-leg incidence: count observations where action=ACCUMULATE but legs != (YES, NO)

    BacktestResult fields:
      - run_id: str
      - observations_total: int
      - feed_stale_skips: int      — FREEZE actions
      - safety_skips: int          — reserved for future safety checks (always 0 in v0)
      - quote_skips: int           — SKIP due to missing quotes
      - hard_rule_skips: int       — SKIP due to pair cost > threshold
      - soft_rule_skips: int       — SKIP due to soft fair-value filter
      - intents_generated: int     — ACTION_ACCUMULATE count
      - partial_leg_intents: int   — intents where legs != both YES and NO
      - completed_pairs_simulated: int  — intents where both YES and NO legs included (both_legs intent)
      - avg_completed_pair_cost: Optional[float]  — mean projected_pair_cost for completed-pair intents; None if 0
      - est_profit_per_completed_pair: Optional[float]  — mean (1.0 - projected_pair_cost) for completed-pair intents; None if 0
      - config_snapshot: dict  — the CryptoPairPaperModeConfig used, serialized

    Test cases to implement first (RED before GREEN):
      test_empty_observations_returns_zero_counts
      test_stale_feed_counts_as_feed_stale_skip
      test_missing_yes_quote_counts_as_quote_skip
      test_missing_no_quote_counts_as_quote_skip
      test_hard_rule_exceeded_counts_as_hard_rule_skip (yes+no ask >= 0.98)
      test_soft_rule_blocks_all_legs_counts_as_soft_rule_skip
      test_clean_observation_below_threshold_generates_intent
      test_completed_pair_both_legs_counted_in_completed_pairs_simulated
      test_partial_leg_intent_counted_in_partial_leg_intents (yes_only soft-blocked for no)
      test_avg_pair_cost_correct_for_single_completed_pair
      test_est_profit_correct_for_single_completed_pair (1.0 - pair_cost)
      test_deterministic_repeated_run_same_input_same_output
      test_result_to_dict_is_json_serializable
  </behavior>
  <action>
    Write tests first in tests/test_crypto_pair_backtest.py (all RED), then implement
    packages/polymarket/crypto_pairs/backtest_harness.py until all tests pass.

    Implementation notes:
    - BacktestObservation is a frozen dataclass. Use `feed_is_stale: bool = False` as default.
    - BacktestHarness.__init__ accepts optional `config: CryptoPairPaperModeConfig = None`; if None,
      use `build_default_paper_mode_config()` from paper_runner.py.
    - Use `Decimal(str(obs.yes_ask))` when constructing BestQuote to avoid float precision issues.
    - For the feed snapshot when feed_is_stale=False and underlying_price is not None: build a
      ReferencePriceSnapshot with is_stale=False, connection_state=CONNECTED, price=underlying_price,
      observed_at_s=1000.0 (sentinel), stale_threshold_s=15.0, feed_source="backtest".
    - For the feed snapshot when feed_is_stale=False and underlying_price is None: build a snapshot
      with price=1.0 (placeholder — feed gate will still pass; the engine only uses the snapshot
      for the freeze gate, not for price computation).
    - For the feed snapshot when feed_is_stale=True: build a snapshot with is_stale=True so
      evaluate_accumulation returns ACTION_FREEZE.
    - Compute fair values only when obs.underlying_price is not None AND obs.threshold is not None
      AND obs.remaining_seconds is not None. Use estimate_fair_value from fair_value.py.
    - partial_leg_intents: an ACCUMULATE where legs is (YES,) or (NO,) only — one leg partial.
    - completed_pairs_simulated: ACCUMULATE where both LEG_YES and LEG_NO are in legs.
    - avg_completed_pair_cost and est_profit_per_completed_pair are float averages over
      completed_pairs_simulated intents. Use Python `float(Decimal(...))` for the averages.
    - BacktestResult.to_dict() must produce JSON-serializable output (no Decimal, no datetime).
    - Do NOT import from live_runner, live_execution, or any ClickHouse layer.
    - No network calls, no filesystem writes in the harness itself (filesystem is the CLI's job).
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m pytest tests/test_crypto_pair_backtest.py -q --tb=short</automated>
  </verify>
  <done>
    All test_crypto_pair_backtest.py tests pass. BacktestHarness.run() returns a BacktestResult
    with correct counts for all skip categories, intents_generated, partial_leg_intents,
    completed_pairs_simulated, avg_completed_pair_cost, and est_profit_per_completed_pair.
    BacktestResult.to_dict() is JSON-serializable.
  </done>
</task>

<task type="auto">
  <name>Task 2: Implement CLI entrypoint, register command, write artifacts, and create docs</name>
  <files>
    tools/cli/crypto_pair_backtest.py
    polytool/__main__.py
    docs/features/FEATURE-crypto-pair-backtest-v0.md
    docs/dev_logs/2026-03-23_phase1a_crypto_pair_backtest_v0.md
  </files>
  <action>
    --- tools/cli/crypto_pair_backtest.py ---

    Implement build_parser() and main(argv) following the same conventions as
    tools/cli/crypto_pair_run.py.

    CLI arguments:
      --input PATH      (required) Path to JSONL file where each line is a BacktestObservation
                        JSON object. Fields: symbol, duration_min, market_id, yes_ask (float or null),
                        no_ask (float or null), underlying_price (float or null), threshold (float or null),
                        remaining_seconds (float or null), feed_is_stale (bool, default false),
                        timestamp_iso (str, optional).
      --output PATH     Base artifact directory (default: artifacts/crypto_pairs/backtests)
      --symbol BTC/ETH/SOL  (append, optional) Filter observations to these symbols only.
      --market-duration 5/15 (append, optional) Filter to these durations only.
      --run-id STR      Optional explicit run_id (default: auto uuid hex[:12])

    Execution flow in main():
      1. Parse args; validate --input file exists.
      2. Load observations from JSONL (one JSON object per line; skip blank lines).
         Apply symbol and market-duration filters if specified.
      3. Instantiate BacktestHarness() and call run(observations).
      4. Build artifact dir: output_base / date_str / run_id (using datetime.now(UTC).date().isoformat())
         where run_id comes from BacktestResult.run_id.
         Create the directory with mkdir(parents=True, exist_ok=True).
      5. Write artifacts:
         a. manifest.json — contains run_id, input_path, observations_total, filters_applied,
            generated_at (ISO UTC), artifact_dir, and the full BacktestResult.to_dict()
         b. summary.json — BacktestResult.to_dict() only (machine-readable)
         c. report.md — human-readable Markdown report with:
            - Header: "# Crypto Pair Backtest Report"
            - Run metadata: run_id, input file, generated_at
            - Metrics table:
              | Metric | Value |
              with rows for: observations_total, feed_stale_skips, quote_skips,
              hard_rule_skips, soft_rule_skips, soft_rule_skips, intents_generated,
              partial_leg_intents, completed_pairs_simulated,
              avg_completed_pair_cost (4 decimal places or "N/A"),
              est_profit_per_completed_pair (4 decimal places or "N/A")
            - Config section showing target_pair_cost_threshold
            - Footer note: "Conservative paper-style fill assumptions. No network calls."
      6. Print to stdout:
         [crypto-pair-backtest] run_id        : <run_id>
         [crypto-pair-backtest] observations  : <n>
         [crypto-pair-backtest] intents        : <n>
         [crypto-pair-backtest] completed_pairs: <n>
         [crypto-pair-backtest] artifact_dir  : <path>
      7. Return 0 on success; print error to stderr and return 1 on failure.

    Error cases to handle:
      - Input file not found → print error, return 1
      - Invalid JSON on a line → skip that line, print warning to stderr, continue
      - No observations after filtering → still write empty artifacts (all zeros), return 0

    --- polytool/__main__.py ---

    Add these three changes:
    1. After the `crypto_pair_run_main` line, add:
       `crypto_pair_backtest_main = _command_entrypoint("tools.cli.crypto_pair_backtest")`
    2. In _COMMAND_HANDLER_NAMES, after "crypto-pair-run" entry, add:
       `"crypto-pair-backtest": "crypto_pair_backtest_main",`
    3. In print_usage() under the Crypto Pair Bot section, add the line:
       `print("  crypto-pair-backtest  Replay historical/synthetic pair observations, emit eval artifacts")`

    --- docs/features/FEATURE-crypto-pair-backtest-v0.md ---

    Write a concise feature doc covering:
    - Purpose and scope (pre-paper-soak evaluation harness)
    - Input contract: JSONL schema with all BacktestObservation fields and their types/defaults
    - Output artifacts: manifest.json, summary.json, report.md and what each contains
    - Metrics definitions: what each counter means (especially feed_stale_skips vs quote_skips)
    - Constraints: no network, no ClickHouse, conservative paper assumptions only
    - Example CLI invocation
    - Known limitations / v0 scope boundaries

    --- docs/dev_logs/2026-03-23_phase1a_crypto_pair_backtest_v0.md ---

    Write the mandatory dev log per CLAUDE.md conventions covering:
    - Objective
    - What was built (4 files + __main__.py update)
    - Design decisions (input contract, metric definitions, artifact layout)
    - Test results: exact pytest command and pass count
    - Open questions / next steps (e.g., feeding real scanner JSONL outputs)
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m polytool crypto-pair-backtest --help</automated>
  </verify>
  <done>
    `python -m polytool crypto-pair-backtest --help` exits 0 and shows --input, --output, --symbol, --market-duration, --run-id arguments.
    Running with a synthetic JSONL input (constructable from test data) writes manifest.json, summary.json, and report.md to the expected artifact directory.
    All existing tests still pass: `python -m pytest tests/test_crypto_pair_backtest.py tests/test_crypto_pair_accumulation_engine.py tests/test_crypto_pair_fair_value.py -q` shows 0 failures.
  </done>
</task>

</tasks>

<verification>
Run the full regression suite scoped to the crypto-pair test files:

```
cd "D:/Coding Projects/Polymarket/PolyTool"
python -m pytest tests/test_crypto_pair_scan.py tests/test_crypto_pair_paper_ledger.py tests/test_crypto_pair_run.py tests/test_crypto_pair_live_safety.py tests/test_crypto_pair_reference_feed.py tests/test_crypto_pair_fair_value.py tests/test_crypto_pair_accumulation_engine.py tests/test_crypto_pair_backtest.py -q --tb=short
```

Expected: 0 failures, no regressions, new backtest tests passing.

Smoke test the CLI:
```
python -m polytool crypto-pair-backtest --help
python -m polytool --help | grep crypto-pair-backtest
```

Spot-check artifact output by constructing a minimal 3-observation JSONL and running it:
```
echo '{"symbol":"BTC","duration_min":5,"market_id":"mkt-btc-5m","yes_ask":0.47,"no_ask":0.48,"underlying_price":60000,"threshold":60000,"remaining_seconds":300,"feed_is_stale":false}' > /tmp/test_obs.jsonl
echo '{"symbol":"BTC","duration_min":5,"market_id":"mkt-btc-5m","yes_ask":0.51,"no_ask":0.51,"feed_is_stale":false}' >> /tmp/test_obs.jsonl
echo '{"symbol":"BTC","duration_min":5,"market_id":"mkt-btc-5m","yes_ask":0.47,"no_ask":0.48,"feed_is_stale":true}' >> /tmp/test_obs.jsonl
python -m polytool crypto-pair-backtest --input /tmp/test_obs.jsonl --output /tmp/bt_test
```
Expected: 1 hard_rule_skip (0.51+0.51=1.02), 1 feed_stale_skip, 1 intent generated.
Verify manifest.json, summary.json, report.md exist in the artifact directory.
</verification>

<success_criteria>
- `python -m polytool crypto-pair-backtest --help` exits 0
- All 13+ tests in test_crypto_pair_backtest.py pass
- Full crypto-pair test suite shows 0 failures
- BacktestHarness is a pure function with no network calls or filesystem writes
- CLI writes manifest.json, summary.json, and report.md with correct metric counts
- feed_stale_skips, quote_skips, hard_rule_skips, soft_rule_skips, intents_generated, completed_pairs_simulated, avg_completed_pair_cost, est_profit_per_completed_pair all populated correctly from synthetic inputs
- No imports from live_runner, live_execution, or ClickHouse layer in backtest_harness.py
- Dev log exists at docs/dev_logs/2026-03-23_phase1a_crypto_pair_backtest_v0.md
</success_criteria>

<output>
After completion, create `.planning/quick/19-add-phase-1a-backtest-history-harness-fo/19-SUMMARY.md`
with run_id, files created/modified, test results (exact counts), and the artifact path pattern used.
</output>
