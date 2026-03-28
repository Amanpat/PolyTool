---
phase: quick-037
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/polymarket/market_selection/__init__.py
  - packages/polymarket/market_selection/config.py
  - packages/polymarket/market_selection/filters.py
  - packages/polymarket/market_selection/scorer.py
  - tools/cli/market_scan.py
  - tests/test_market_scorer.py
  - docs/dev_logs/2026-03-28_market_selection_engine.md
autonomous: true
requirements:
  - MARKET-SELECTION-ENGINE-001
must_haves:
  truths:
    - "python -m polytool market-scan --top 20 runs without import errors"
    - "Eleven offline tests in test_market_scorer.py all pass"
    - "SevenFactorScore composite is deterministic for fixed inputs"
    - "passes_gates rejects markets below volume/spread/days thresholds"
    - "NegRisk markets receive a 0.85 penalty multiplier on composite"
    - "artifacts/market_selection/ directory is created and JSON artifact written on run"
  artifacts:
    - path: "packages/polymarket/market_selection/config.py"
      provides: "FACTOR_WEIGHTS, CATEGORY_EDGE, ADVERSE_SELECTION_PRIOR, gate thresholds"
    - path: "packages/polymarket/market_selection/filters.py"
      provides: "passes_gates() alongside existing passes_filters()"
    - path: "packages/polymarket/market_selection/scorer.py"
      provides: "SevenFactorScore dataclass and MarketScorer class; existing Gate2RankScore unchanged"
    - path: "tools/cli/market_scan.py"
      provides: "market-scan CLI with --top, --all, --include-failing, --skip-events, --max-fetch, --output, --json flags"
    - path: "tests/test_market_scorer.py"
      provides: "11 offline tests for seven-factor scoring engine"
  key_links:
    - from: "tools/cli/market_scan.py"
      to: "packages/polymarket/market_selection/scorer.py"
      via: "MarketScorer.score_universe()"
      pattern: "MarketScorer"
    - from: "tools/cli/market_scan.py"
      to: "packages/polymarket/market_selection/filters.py"
      via: "passes_gates()"
      pattern: "passes_gates"
    - from: "packages/polymarket/market_selection/scorer.py"
      to: "packages/polymarket/market_selection/config.py"
      via: "FACTOR_WEIGHTS, CATEGORY_EDGE"
      pattern: "from .config import"
---

<objective>
Implement the Market Selection Engine: a seven-factor composite scorer that ranks
every active Polymarket market by opportunity quality, exposed via
`python -m polytool market-scan --top 20`.

Purpose: Give the operator a ranked shortlist of the best markets to trade or
capture for Gate 2, replacing the existing 5-factor scorer with a richer model
grounded in the Jon-Becker 72.1M trade analysis.

Output:
- `packages/polymarket/market_selection/config.py` — weights, priors, thresholds
- `packages/polymarket/market_selection/filters.py` — `passes_gates()` added alongside existing `passes_filters()`
- `packages/polymarket/market_selection/scorer.py` — `SevenFactorScore` + `MarketScorer` added; existing `MarketScore`/`Gate2RankScore` untouched
- `packages/polymarket/market_selection/__init__.py` — updated docstring
- `tools/cli/market_scan.py` — rewritten to use seven-factor path
- `tests/test_market_scorer.py` — 11 offline tests
- `docs/dev_logs/2026-03-28_market_selection_engine.md` — design decisions
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/CLAUDE.md
@D:/Coding Projects/Polymarket/PolyTool/.planning/STATE.md

<interfaces>
<!-- Existing market_selection package — do NOT break these exports. -->

From packages/polymarket/market_selection/scorer.py (existing, keep untouched):
```python
# These symbols are imported by scan_gate2_candidates.py — do NOT remove or rename:
class MarketScore:  # 5-factor frozen dataclass; fields: market_slug, reward_apr_est, spread_score, fill_score, competition_score, age_hours, composite
def score_market(market: dict, orderbook: dict, reward_config: dict) -> MarketScore: ...
class Gate2RankScore: ...  # imported by scan_gate2_candidates
def score_gate2_candidate(...) -> Gate2RankScore: ...
def rank_gate2_candidates(...) -> list[Gate2RankScore]: ...
```

From packages/polymarket/market_selection/filters.py (existing, keep untouched):
```python
# passes_filters is imported by existing market_scan.py — keep it for backward compat
def passes_filters(market: dict, reward_config: dict) -> tuple[bool, str]: ...
```

From packages/polymarket/market_selection/api_client.py (existing, read-only):
```python
def fetch_active_markets(min_volume: float = 5000, limit: int = 50) -> list[dict]: ...
def fetch_reward_config(market_slug: str) -> dict | None: ...
def fetch_orderbook(token_id: str) -> dict: ...
```

From polytool/__main__.py (existing, do NOT modify):
# market-scan is already registered:
#   market_scan_main = _command_entrypoint("tools.cli.market_scan")
#   "market-scan": "market_scan_main"
# No changes needed to __main__.py.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add config.py and extend filters.py + scorer.py with seven-factor engine</name>
  <files>
    packages/polymarket/market_selection/__init__.py
    packages/polymarket/market_selection/config.py
    packages/polymarket/market_selection/filters.py
    packages/polymarket/market_selection/scorer.py
  </files>
  <behavior>
    - test_category_edge_lookup: CATEGORY_EDGE["Crypto"] == 0.70; unknown key returns CATEGORY_EDGE_DEFAULT (0.50)
    - test_spread_normalization: spread 0.03 scores higher than spread 0.005; spread at MAX_SPREAD_REFERENCE (0.10) clips to 1.0
    - test_volume_log_scaling: log10(50000) normalized higher than log10(500); volume below MIN_VOLUME_24H gates out
    - test_competition_inverse: 0 orders above threshold → competition factor 1.0; 9 orders → 0.1
    - test_time_gaussian: days_to_resolution == TIME_SCORE_CENTER_DAYS (14) → peak score; 0 days or very large → lower score
    - test_longshot_bonus: mid_price=0.10 gets LONGSHOT_BONUS_MAX bonus; mid_price=0.50 gets 0 bonus
    - test_passes_gates_reject_volume: volume=100 → rejected "volume_below_min"
    - test_passes_gates_reject_spread: spread=0.001 → rejected "spread_below_min"
    - test_passes_gates_pass: all valid inputs → (True, "")
    - test_negrisk_penalty: market with neg_risk=True has composite * NEGRISK_PENALTY (0.85) vs same market without
    - test_composite_ordering: market with all high factors scores above market with all low factors
  </behavior>
  <action>
    1. Create `packages/polymarket/market_selection/config.py` with the exact content from the task spec:
       - FACTOR_WEIGHTS dict (7 keys, must sum to 1.0)
       - CATEGORY_EDGE dict (11 categories)
       - CATEGORY_EDGE_DEFAULT = 0.50
       - ADVERSE_SELECTION_PRIOR dict (11 categories)
       - ADVERSE_SELECTION_DEFAULT = 0.60
       - Gate thresholds: MIN_VOLUME_24H=500.0, MIN_SPREAD=0.005, MIN_DAYS_TO_RESOLUTION=1.0, MAX_SPREAD_REFERENCE=0.10
       - Scoring params: LONGSHOT_BONUS_MAX=0.15, LONGSHOT_THRESHOLD=0.35, TIME_SCORE_CENTER_DAYS=14.0
       - COMPETITION_SPREAD_THRESHOLD=0.03, TARGET_REWARD_APR=1.0, NEGRISK_PENALTY=0.85

    2. Append `passes_gates()` to `packages/polymarket/market_selection/filters.py` — do NOT remove or alter the existing `passes_filters()` function. The new function has this exact signature:
       ```python
       def passes_gates(
           *,
           volume_24h: float,
           spread: Optional[float],
           days_to_resolution: Optional[float],
           accepting_orders: Optional[bool],
           enable_order_book: Optional[bool],
       ) -> tuple[bool, str]:
       ```
       Logic (using config constants, not hardcoded values):
       - accepting_orders is False → (False, "not_accepting_orders")
       - enable_order_book is False → (False, "orderbook_disabled")
       - volume_24h < MIN_VOLUME_24H → (False, f"volume_below_min ({volume_24h:.0f} < {MIN_VOLUME_24H})")
       - spread is not None and spread < MIN_SPREAD → (False, f"spread_below_min ({spread:.4f} < {MIN_SPREAD})")
       - days_to_resolution is not None and days_to_resolution < MIN_DAYS_TO_RESOLUTION → (False, f"resolving_soon ({days_to_resolution:.1f}d < {MIN_DAYS_TO_RESOLUTION}d)")
       - else (True, "")
       Import from `.config` at top of file.

    3. Append the seven-factor engine to `packages/polymarket/market_selection/scorer.py` — do NOT modify any existing classes or functions. Add after the last existing line:

       a. Import config constants at the top of the new section (use a comment delimiter):
          `from .config import (FACTOR_WEIGHTS, CATEGORY_EDGE, CATEGORY_EDGE_DEFAULT, ...)`
          Use a try/except ImportError guard if needed to avoid breaking existing imports.
          Better: use a local import inside the new classes.

       b. `SevenFactorScore` frozen dataclass fields:
          market_slug: str, category: str, spread_score: float, volume_score: float,
          competition_score: float, reward_apr_score: float, adverse_selection_score: float,
          time_score: float, category_edge_score: float, longshot_bonus: float,
          composite: float, gate_passed: bool, gate_reason: str, neg_risk: bool

       c. `MarketScorer` class with:
          - `__init__(self, *, now: Optional[datetime] = None)` — stores reference time
          - `score_universe(self, markets: list[dict]) -> list[SevenFactorScore]` — scores all, returns sorted descending by composite
          - `_score_single(self, market: dict) -> SevenFactorScore` — scores one market dict

          Factor implementations in `_score_single`:
          - **spread_score**: spread = best_ask - best_bid (from market dict keys best_bid/best_ask). Clamp: min(spread / MAX_SPREAD_REFERENCE, 1.0). If no BBO, spread_score=0.
          - **volume_score**: log10(max(volume_24h, 1)) / log10(100_000). Clamp to [0, 1].
          - **competition_score**: count bids where price*size >= COMPETITION_SPREAD_THRESHOLD*100 (proxy for non-trivial orders). factor = 1 / (count + 1). If no orderbook key, default 0.5.
          - **reward_apr_score**: reward_rate from market dict key "reward_rate" or 0. min(reward_rate * 365 / TARGET_REWARD_APR, 1.0). Clamp [0, 1].
          - **adverse_selection_score**: lookup category in ADVERSE_SELECTION_PRIOR (default ADVERSE_SELECTION_DEFAULT). Score = prior (already in [0,1]).
          - **time_score**: Gaussian centered at TIME_SCORE_CENTER_DAYS. days = days_to_resolution from market dict. score = exp(-((days - TIME_SCORE_CENTER_DAYS)**2) / (2 * TIME_SCORE_CENTER_DAYS**2)). Clamp [0, 1]. If days unavailable, default 0.5.
          - **category_edge_score**: lookup category in CATEGORY_EDGE (default CATEGORY_EDGE_DEFAULT).
          - **longshot_bonus**: mid_price = (best_bid + best_ask) / 2. If mid_price <= LONGSHOT_THRESHOLD, bonus = LONGSHOT_BONUS_MAX * (1 - mid_price / LONGSHOT_THRESHOLD). Else 0. If no BBO, 0.

          composite = sum of factor * weight for each factor in FACTOR_WEIGHTS + longshot_bonus.
          If neg_risk field is True in market dict, composite *= NEGRISK_PENALTY.
          Clamp final composite to [0, 1].

          gate_passed / gate_reason: call passes_gates() with the market's fields. The market dict keys to extract:
          - volume_24h: market.get("volume_24h") or 0
          - spread: best_ask - best_bid if both present, else None
          - days_to_resolution: compute from end_date_iso field if present
          - accepting_orders: market.get("accepting_orders")
          - enable_order_book: market.get("enable_order_book")

       d. `score_universe` filters to only gate_passed=True markets UNLESS the caller
          passes `include_failing=True`. Sort descending by composite. Deduplicate by market_slug
          (keep highest composite).

    4. Update `packages/polymarket/market_selection/__init__.py` docstring to:
       `"""Market selection engine: score and rank Polymarket markets by opportunity quality."""`
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -c "from packages.polymarket.market_selection.config import FACTOR_WEIGHTS; assert abs(sum(FACTOR_WEIGHTS.values()) - 1.0) < 1e-9, 'weights must sum to 1'" && python -c "from packages.polymarket.market_selection.filters import passes_gates, passes_filters; print('filters ok')" && python -c "from packages.polymarket.market_selection.scorer import MarketScore, Gate2RankScore, SevenFactorScore, MarketScorer; print('scorer ok')"</automated>
  </verify>
  <done>
    config.py exists with FACTOR_WEIGHTS summing to 1.0.
    passes_gates() and passes_filters() both importable from filters.py.
    SevenFactorScore, MarketScorer, MarketScore, Gate2RankScore all importable from scorer.py.
    No existing imports in scan_gate2_candidates.py or benchmark_manifest.py are broken.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Write 11 offline tests and rewrite market_scan.py CLI</name>
  <files>
    tests/test_market_scorer.py
    tools/cli/market_scan.py
  </files>
  <behavior>
    All 11 tests listed in Task 1 behavior block pass offline (no network).
    `python -m polytool market-scan --help` exits 0 and shows --top, --all, --include-failing, --skip-events, --max-fetch, --output, --json flags.
    `python -m pytest tests/test_market_scorer.py -x -q` shows 11 passed, 0 failed.
  </behavior>
  <action>
    1. Write `tests/test_market_scorer.py` with 11 offline tests. Use only stdlib + project code; no network calls. Each test creates minimal market dicts and calls the scoring functions directly.

       Test structure — one test per behavior from Task 1:
       ```python
       """Offline unit tests for the seven-factor Market Selection Engine."""
       from __future__ import annotations
       import math
       import pytest
       from packages.polymarket.market_selection.config import (
           CATEGORY_EDGE, CATEGORY_EDGE_DEFAULT, FACTOR_WEIGHTS,
           NEGRISK_PENALTY, LONGSHOT_BONUS_MAX, LONGSHOT_THRESHOLD,
           TIME_SCORE_CENTER_DAYS, MAX_SPREAD_REFERENCE, MIN_VOLUME_24H, MIN_SPREAD,
       )
       from packages.polymarket.market_selection.filters import passes_gates
       from packages.polymarket.market_selection.scorer import MarketScorer, SevenFactorScore
       ```

       Helper: `_market(**kwargs)` builds a minimal valid market dict with sensible defaults:
       ```python
       def _market(**kwargs):
           base = {
               "slug": "test-market", "best_bid": 0.45, "best_ask": 0.55,
               "volume_24h": 10_000.0, "category": "Sports",
               "end_date_iso": "2026-04-15T00:00:00+00:00",
               "accepting_orders": True, "enable_order_book": True,
               "neg_risk": False,
           }
           base.update(kwargs)
           return base
       ```

       Write each of the 11 tests:
       1. `test_category_edge_lookup`: assert CATEGORY_EDGE["Crypto"] == 0.70; unknown = CATEGORY_EDGE_DEFAULT
       2. `test_spread_normalization`: score _market(best_bid=0.47, best_ask=0.53) vs _market(best_bid=0.49, best_ask=0.51). Wider spread → higher spread_score. Also assert spread at MAX_SPREAD_REFERENCE or beyond → spread_score == 1.0.
       3. `test_volume_log_scaling`: score _market(volume_24h=50_000) vs _market(volume_24h=500). Higher volume → higher volume_score. volume_24h below MIN_VOLUME_24H gates out (gate_passed=False).
       4. `test_competition_inverse`: use scorer._score_single with market dict containing no orderbook bids → competition defaults. Build market dict with many large bids vs no bids and verify direction.
       5. `test_time_gaussian`: score market with days_to_resolution=14 vs days_to_resolution=1 and days_to_resolution=90. Day 14 should have highest time_score.
       6. `test_longshot_bonus`: mid_price=0.10 → longshot_bonus == LONGSHOT_BONUS_MAX * (1 - 0.10/LONGSHOT_THRESHOLD). mid_price=0.50 → longshot_bonus == 0.
       7. `test_passes_gates_reject_volume`: passes_gates(volume_24h=100.0, spread=0.02, days_to_resolution=10.0, accepting_orders=True, enable_order_book=True) → (False, contains "volume_below_min")
       8. `test_passes_gates_reject_spread`: passes_gates(volume_24h=10_000.0, spread=0.001, ...) → (False, contains "spread_below_min")
       9. `test_passes_gates_pass`: valid inputs → (True, "")
       10. `test_negrisk_penalty`: score two identical markets except neg_risk=True vs False. neg_risk=True composite == neg_risk=False composite * NEGRISK_PENALTY (approximately, allow float tolerance).
       11. `test_composite_ordering`: score_universe with one high-signal market and one low-signal market; high ranks first.

       Compute days_to_resolution inside tests by passing "end_date_iso" that is N days from a fixed reference date. The scorer uses `now` parameter for determinism:
       ```python
       from datetime import datetime, timezone, timedelta
       REF_NOW = datetime(2026, 3, 28, 12, 0, 0, tzinfo=timezone.utc)
       scorer = MarketScorer(now=REF_NOW)
       ```
       Pass end_date_iso as `(REF_NOW + timedelta(days=N)).isoformat()` for precise control.

    2. Rewrite `tools/cli/market_scan.py` to use the seven-factor engine. The file already exists — replace it entirely. Key design points:

       Imports (keep only what is needed for the new implementation):
       ```python
       from packages.polymarket.market_selection.api_client import fetch_active_markets, fetch_reward_config, fetch_orderbook
       from packages.polymarket.market_selection.scorer import MarketScorer, SevenFactorScore
       ```
       Note: passes_gates is called internally by MarketScorer — no direct import needed in CLI.

       CLI flags (argparse):
       - `--top N` (int, default=20): print top N rows
       - `--all` (store_true): print all passing markets, ignoring --top
       - `--include-failing` (store_true): include gate-failed markets in output JSON (but not table)
       - `--skip-events` (store_true): skip the live reward/orderbook fetches (faster dry run, no reward_rate or orderbook data)
       - `--max-fetch N` (int, default=200): max markets to fetch from Gamma API
       - `--output PATH` (str, default=None): override default JSON output path
       - `--json` (store_true): print JSON to stdout instead of table

       Core flow in `run_market_scan()`:
       1. Fetch markets via `fetch_active_markets(limit=max_fetch)` (no min_volume filter at fetch time)
       2. For each market, unless --skip-events:
          - Fetch `fetch_reward_config(market_slug)` and attach as `reward_rate` key
          - Fetch `fetch_orderbook(token_id)` and attach bids/asks to market dict
       3. Build `MarketScorer(now=utcnow())` and call `score_universe(markets, include_failing=args.include_failing)`
       4. Sort by composite descending (score_universe already does this)
       5. Write JSON artifact to `artifacts/market_selection/YYYY-MM-DD.json`
       6. Print table (unless --json flag; if --json, print JSON to stdout)

       Table format (same column header as existing implementation):
       ```
       rank slug                           composite  cat_edge  spread   vol  comp   time
       ```
       Show top N rows (or all if --all).

       JSON artifact schema:
       ```json
       {
         "generated_at": "ISO timestamp",
         "max_fetch": N,
         "include_failing": bool,
         "results": [ {all SevenFactorScore fields as dict} ],
         "gate_failed": [ {"market_slug": ..., "gate_reason": ...} ]
       }
       ```
       "gate_failed" only populated when --include-failing is set.

       `main(argv)` signature matches existing pattern: `def main(argv: Optional[list[str]] = None) -> int:`
       Return 0 on success, 1 on error. Wrap execution in try/except and print error to stderr.

       Do NOT import or reference the old `passes_filters` function from the new CLI.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m pytest tests/test_market_scorer.py -x -q --tb=short 2>&1 | tail -5</automated>
  </verify>
  <done>
    11 tests pass (0 failed, 0 errors).
    `python -m polytool market-scan --help` exits 0 and shows all listed flags.
    `python -m polytool --help` still loads without error (market-scan remains registered).
    Existing tests still pass: `python -m pytest tests/ -x -q --tb=short -k "not test_market_scorer" 2>&1 | tail -3` shows same count as before (2717 passing).
  </done>
</task>

<task type="auto">
  <name>Task 3: Write dev log and run full smoke test</name>
  <files>
    docs/dev_logs/2026-03-28_market_selection_engine.md
  </files>
  <action>
    Write `docs/dev_logs/2026-03-28_market_selection_engine.md` documenting:

    ## Summary
    Shipped the seven-factor Market Selection Engine as `python -m polytool market-scan`.

    ## Seven Factors and Weights
    | Factor | Weight | Description |
    |--------|--------|-------------|
    | category_edge | 0.20 | Empirical prior from Jon-Becker 72.1M trade analysis |
    | spread_opportunity | 0.20 | Normalized spread width as maker profitability proxy |
    | volume | 0.15 | Log-scaled 24h volume as fill quality proxy |
    | competition | 0.15 | Inverse active-order count as crowding proxy |
    | reward_apr | 0.15 | Annualized reward rate vs TARGET_REWARD_APR=1.0 |
    | adverse_selection | 0.10 | Category-level informed-trading prior |
    | time_to_resolution | 0.05 | Gaussian centered at 14 days |

    ## Design Decisions
    - Seven-factor model extends existing 5-factor scorer without breaking Gate2RankScore or passes_filters — all existing CLI tools unaffected.
    - config.py separates all learnable constants; Phase 4+ EWA updates will tune FACTOR_WEIGHTS via live PnL.
    - NegRisk markets receive a 0.85 composite penalty because multi-outcome books have structural adverse selection not captured by the binary model.
    - Longshot bonus (up to +0.15) rewards markets with mid < 0.35 where maker spread income is structurally wider.
    - Deduplication by market_slug prevents duplicate market entries from corrupting rankings.

    ## Files Changed
    - packages/polymarket/market_selection/config.py (new)
    - packages/polymarket/market_selection/filters.py (passes_gates added)
    - packages/polymarket/market_selection/scorer.py (SevenFactorScore + MarketScorer added)
    - packages/polymarket/market_selection/__init__.py (docstring updated)
    - tools/cli/market_scan.py (rewritten to use seven-factor path)
    - tests/test_market_scorer.py (new, 11 offline tests)

    ## Test Results
    Record exact output of:
    `python -m pytest tests/test_market_scorer.py -v --tb=short`
    `python -m pytest tests/ -x -q --tb=short | tail -3`

    Then run:
    `python -m polytool --help`
    to confirm CLI loads without import errors. Record the output line for market-scan.

    Write whatever actual test results were observed, not placeholder text.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m polytool --help 2>&1 | grep "market-scan"</automated>
  </verify>
  <done>
    Dev log exists at docs/dev_logs/2026-03-28_market_selection_engine.md.
    `python -m polytool --help` mentions "market-scan".
    Full regression suite passes at same count as before this work packet (2717 + 11 = 2728 expected).
  </done>
</task>

</tasks>

<verification>
After all tasks complete:

1. Import smoke: `python -c "from packages.polymarket.market_selection.scorer import SevenFactorScore, MarketScorer, MarketScore, Gate2RankScore; print('ok')"`
2. Test suite: `python -m pytest tests/test_market_scorer.py -v --tb=short` — 11 passed
3. Regression: `python -m pytest tests/ -x -q --tb=short | tail -3` — 2728+ passed, 0 failed
4. CLI help: `python -m polytool market-scan --help` — exits 0, shows all flags
5. Existing imports: `python -c "from tools.cli.scan_gate2_candidates import *" 2>&1 | head -3` — no ImportError
</verification>

<success_criteria>
- `python -m pytest tests/test_market_scorer.py` passes all 11 tests
- `python -m pytest tests/ -x -q` passes all existing tests plus 11 new ones
- `python -m polytool market-scan --help` exits 0 and shows --top, --all, --include-failing, --skip-events, --max-fetch, --output, --json
- `packages/polymarket/market_selection/config.py` exists with FACTOR_WEIGHTS summing to 1.0
- `SevenFactorScore` and `MarketScorer` importable from scorer.py alongside existing `Gate2RankScore`
- Dev log written at docs/dev_logs/2026-03-28_market_selection_engine.md
- No regressions in existing tests
</success_criteria>

<output>
After completion, create `.planning/quick/37-market-selection-engine-seven-factor-com/037-SUMMARY.md`
</output>
