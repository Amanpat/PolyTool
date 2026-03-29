---
phase: quick-052
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/polymarket/crypto_pairs/paper_runner.py
  - tools/cli/crypto_pair_run.py
  - tests/test_crypto_pair_run.py
autonomous: true
requirements:
  - QUICK-052
must_haves:
  truths:
    - "Running paper mode prints a startup header once with symbol/feed/cycle/market-count/start-time info"
    - "In --verbose mode, each cycle prints one status line per market with YES/NO prices, pair cost, ref price, pct change, signal"
    - "Signals and intents are highlighted visually regardless of --verbose setting"
    - "In non-verbose mode (default), only the stats summary line prints every 10 seconds plus any signal/intent lines"
    - "The run stops cleanly when wall-clock elapsed >= duration_seconds (not based on pre-computed cycle count)"
    - "The stats line includes Remaining time"
    - "JSONL observation files are unaffected by dashboard output"
  artifacts:
    - path: "packages/polymarket/crypto_pairs/paper_runner.py"
      provides: "dashboard printing logic + duration bug fix"
    - path: "tools/cli/crypto_pair_run.py"
      provides: "--verbose flag wired through"
    - path: "tests/test_crypto_pair_run.py"
      provides: "tests for dashboard output and duration fix"
  key_links:
    - from: "tools/cli/crypto_pair_run.py"
      to: "CryptoPairPaperRunner"
      via: "verbose flag passed as constructor param"
    - from: "CryptoPairPaperRunner.run()"
      to: "dashboard print functions"
      via: "called per-cycle with opportunity data"
---

<objective>
Add a live terminal dashboard to the crypto pair bot paper mode runner and fix
the duration timer bug.

Purpose: Give operators real-time visibility into what the bot is observing
each cycle — prices, signals, intents — without changing any strategy logic
or JSONL artifact output.

Output:
- Startup header printed once at launch
- Per-cycle market status lines (verbose mode) or signals/intents only (default)
- Stats summary line every 10 seconds showing cycles/observations/signals/intents/elapsed/remaining
- Duration bug fixed: run stops when wall-clock elapsed >= duration_seconds
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/.planning/STATE.md
@D:/Coding Projects/Polymarket/PolyTool/CLAUDE.md

Key files:
- packages/polymarket/crypto_pairs/paper_runner.py — runner loop, _process_opportunity, heartbeat
- tools/cli/crypto_pair_run.py — CLI entrypoint, build_parser(), run_crypto_pair_runner()
- tests/test_crypto_pair_run.py — existing tests to extend

<interfaces>
From packages/polymarket/crypto_pairs/paper_runner.py:

class CryptoPairRunnerSettings (frozen dataclass):
    duration_seconds: int
    cycle_interval_seconds: float = 0.5
    heartbeat_interval_seconds: int = 0
    # ... other fields

class CryptoPairPaperRunner:
    def __init__(self, settings, *, gamma_client=None, clob_client=None,
                 reference_feed=None, store=None, execution_adapter=None,
                 sink=None, heartbeat_callback=None, now_fn=utc_now,
                 sleep_fn=time.sleep, discovery_fn=..., scan_fn=..., rank_fn=...): ...
    def run(self) -> dict[str, Any]: ...
    def _process_opportunity(self, opportunity: PairOpportunity, *, cycle: int) -> None: ...

def cycle_count_from_settings(settings) -> int:
    # BUG: returns math.ceil(duration_seconds / cycle_interval_seconds)
    # cycles are wall-clock longer than cycle_interval_seconds due to discovery/scan time

class PairOpportunity (dataclass):
    slug: str
    symbol: str       # "BTC", "ETH", "SOL"
    duration_min: int # 5 or 15
    condition_id: str
    yes_token_id: str
    no_token_id: str
    yes_ask: Optional[float]  # None if no quote
    no_ask: Optional[float]   # None if no quote
    book_status: str  # "ok" | "missing_yes" | "missing_no" | "fetch_error"

The run loop (paper_runner.py ~line 648):
    total_cycles = cycle_count_from_settings(self.settings)  # <-- pre-computed
    for cycle_index in range(total_cycles):
        ...
        for opportunity in ranked:
            self._process_opportunity(opportunity, cycle=completed_cycles)
        ...

rationale dict keys (from evaluate_directional_entry):
    "reference_price": float or None
    "price_change_pct": float or None
    "signal_direction": "NONE" | "UP" | "DOWN"
    "favorite_leg": "YES" | "NO" | None
    "hedge_leg": "YES" | "NO" | None

The accumulation result has:
    accumulation.action: "accumulate" | "freeze" | "no_action"
    accumulation.rationale: dict (as above)
    accumulation.legs: tuple[str, ...]   # selected legs if accumulate

From tools/cli/crypto_pair_run.py:

def run_crypto_pair_runner(..., verbose: bool = False, ...) -> dict[str, Any]:
    # Does not yet have verbose param — add it
    runner = CryptoPairPaperRunner(settings, ..., verbose=verbose, ...)

build_parser() returns argparse.ArgumentParser — add --verbose flag here
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Fix duration timer bug and implement dashboard module in paper_runner.py</name>
  <files>packages/polymarket/crypto_pairs/paper_runner.py</files>
  <behavior>
    - Duration fix: After loop body (after sleep), check if wall-clock elapsed >= duration_seconds and break. The pre-computed total_cycles can remain as a safety upper-bound, but the loop must also check elapsed time each cycle.
    - Test: runner with cycle_limit=5, now_fn that advances 100s per cycle, duration_seconds=30 — stops before cycle 5
    - Test: runner with cycle_limit=5, now_fn that advances 1s per cycle, duration_seconds=30 — runs all 5
  </behavior>
  <action>
**Duration bug fix (paper_runner.py run() method, ~line 695 after sleep call):**

After `self.sleep_fn(self.settings.cycle_interval_seconds)`, add a wall-clock elapsed check:

```python
# Wall-clock guard: stop if elapsed >= duration_seconds regardless of cycle count
_elapsed = (self.now_fn() - self.store.started_at).total_seconds()
if self.settings.duration_seconds > 0 and _elapsed >= self.settings.duration_seconds:
    break
```

This check goes at the end of the cycle body, after sleep, before the next iteration. The existing `cycle_count_from_settings` remains as an upper bound (keeps existing behavior when discovery is fast).

**Dashboard implementation — add these functions near the top of the class methods section (or as module-level helpers after `format_elapsed_runtime`):**

```python
def _dashboard_header(settings: CryptoPairRunnerSettings, market_count: int, started_at_str: str) -> str:
    symbols = sorted(set(settings.symbol_filters) if settings.symbol_filters else {"BTC", "ETH", "SOL"})
    cycle_ms = settings.cycle_interval_seconds
    threshold_pct = "?"  # paper_config.momentum.threshold_pct if available
    try:
        threshold_pct = f"{settings.paper_config.momentum.momentum_threshold_pct * 100:.1f}%"
    except Exception:
        pass
    lines = [
        "=== Crypto Pair Bot — Paper Mode ===",
        f"Symbols: {', '.join(symbols)} | Feed: {settings.reference_feed_provider} | Cycle: {cycle_ms}s | Threshold: {threshold_pct}",
        f"Markets found: {market_count} | Started: {started_at_str}",
        "\u2500" * 60,
    ]
    return "\n".join(lines)


def _dashboard_market_line(
    *,
    ts: str,
    opportunity: "PairOpportunity",
    ref_price: Optional[float],
    price_change_pct: Optional[float],
    signal_direction: str,
    action: str,
    intent=None,
) -> str:
    yes_str = f"${opportunity.yes_ask:.2f}" if opportunity.yes_ask is not None else "N/A"
    no_str = f"${opportunity.no_ask:.2f}" if opportunity.no_ask is not None else "N/A"
    pair_str = "N/A"
    if opportunity.yes_ask is not None and opportunity.no_ask is not None:
        pair_str = f"${opportunity.yes_ask + opportunity.no_ask:.2f}"
    ref_str = "N/A"
    if ref_price is not None:
        ref_str = f"${ref_price:,.0f}"
    chg_str = "N/A"
    if price_change_pct is not None:
        sign = "+" if price_change_pct >= 0 else ""
        chg_str = f"{sign}{price_change_pct * 100:.2f}%"
    label = opportunity.slug  # e.g. "BTC-5m-1774815900"
    base = f"[{ts}] {label} | YES {yes_str} NO {no_str} | Pair {pair_str} | Ref {ref_str} | Chg {chg_str}"
    if action == ACTION_ACCUMULATE and signal_direction != "NONE":
        # Signal fired
        fav_yes = opportunity.yes_ask if signal_direction == "UP" else opportunity.no_ask
        fav_side = "YES" if signal_direction == "UP" else "NO"
        fav_str = f"${fav_yes:.2f}" if fav_yes is not None else "N/A"
        return f"{base} | >>> SIGNAL: {signal_direction} - BUY {fav_side} @ {fav_str} <<<"
    return f"{base} | Signal: {signal_direction if signal_direction else 'NONE'}"


def _dashboard_intent_line(*, ts: str, intent) -> str:
    fav_leg = intent.favorite_leg if hasattr(intent, "favorite_leg") else "?"
    hedge_leg = intent.hedge_leg if hasattr(intent, "hedge_leg") else "?"
    fav_price = intent.intended_yes_price if fav_leg == "YES" else intent.intended_no_price
    hedge_price = intent.intended_no_price if fav_leg == "YES" else intent.intended_yes_price
    pair_cost = float(fav_price) + float(hedge_price)
    fav_notional = float(fav_price) * float(intent.pair_size)
    hedge_notional = float(hedge_price) * float(intent.pair_size)
    return (
        f"[{ts}] *** INTENT: {intent.slug} | "
        f"FAV: {fav_leg} @ ${float(fav_price):.2f} (${fav_notional:.0f}) | "
        f"HEDGE: {hedge_leg} @ ${float(hedge_price):.2f} (${hedge_notional:.0f}) | "
        f"Pair cost: ${pair_cost:.2f} ***"
    )


def _dashboard_stats_line(
    *,
    cycle: int,
    observations: int,
    signals: int,
    intents: int,
    elapsed_seconds: int,
    duration_seconds: int,
) -> str:
    elapsed_str = format_elapsed_runtime(elapsed_seconds)
    remaining = max(0, duration_seconds - elapsed_seconds)
    remaining_str = format_elapsed_runtime(remaining)
    # Convert to human-friendly Xm Ys format for stats
    def _fmt(secs: int) -> str:
        m, s = divmod(max(0, secs), 60)
        if m:
            return f"{m}m {s}s"
        return f"{s}s"
    return (
        f"[STATS] Cycles: {cycle} | Observations: {observations} | "
        f"Signals: {signals} | Intents: {intents} | "
        f"Duration: {_fmt(elapsed_seconds)} | Remaining: {_fmt(remaining)}"
    )
```

**Wire dashboard into CryptoPairPaperRunner:**

Add `verbose: bool = False` to `__init__` signature and store as `self._verbose = verbose`.

Add `self._dashboard_signal_count = 0` and `self._dashboard_last_stats_at = 0` to `__init__`.

In `run()`, after the reference feed connects but before the loop, print the startup header:

```python
started_at_str = iso_utc(self.store.started_at)[:19].replace("T", " ")
# Get initial market count from a discovery call (or 0 if not yet run)
# Print header immediately — market count will be 0 until first discovery
print(_dashboard_header(self.settings, market_count=0, started_at_str=started_at_str), flush=True)
self._dashboard_markets_found = 0
```

After `pair_markets` is fetched in the loop, update: `self._dashboard_markets_found = len(pair_markets)`.

In `_process_opportunity()`, after `accumulation = evaluate_directional_entry(...)`:

```python
# Dashboard output — capture rationale before any early returns
_rationale = accumulation.rationale
_signal_dir = _rationale.get("signal_direction", "NONE") or "NONE"
_ref_price = _rationale.get("reference_price")
_price_chg = _rationale.get("price_change_pct")
_is_signal = accumulation.action == ACTION_ACCUMULATE and _signal_dir != "NONE"
if _is_signal:
    self._dashboard_signal_count += 1

_ts = iso_utc(self.now_fn())[11:19]  # HH:MM:SS portion
if self._verbose or _is_signal:
    _line = _dashboard_market_line(
        ts=_ts,
        opportunity=opportunity,
        ref_price=_ref_price,
        price_change_pct=_price_chg,
        signal_direction=_signal_dir,
        action=accumulation.action,
    )
    print(_line, flush=True)
```

After `generate_order_intent(...)` (near end of _process_opportunity), print intent line:

```python
print(_dashboard_intent_line(ts=_ts, intent=intent), flush=True)
```

In `run()`, after `self._emit_heartbeat_if_due(...)` (end of cycle):

```python
# Stats line every 10 seconds
_now_elapsed = int((self.now_fn() - self.store.started_at).total_seconds())
if _now_elapsed - self._dashboard_last_stats_at >= 10:
    self._dashboard_last_stats_at = _now_elapsed
    _stats = _dashboard_stats_line(
        cycle=completed_cycles,
        observations=len(self.store.observations),
        signals=self._dashboard_signal_count,
        intents=len(self.store.intents),
        elapsed_seconds=_now_elapsed,
        duration_seconds=self.settings.duration_seconds,
    )
    print(_stats, flush=True)
```

**IMPORTANT constraints:**
- Do NOT modify self.store.record_observation(), record_runtime_event(), or any JSONL write paths
- Do NOT modify accumulation logic, strategy logic, or opportunity ranking
- All print() calls use flush=True
- The `_verbose` attribute defaults to False
- The intent line prints regardless of verbose (intents are always important)
- Limit displayed markets: when verbose=True, skip market lines after the 8th unique market in a cycle (reset counter each cycle). Track with a per-cycle counter reset at the start of the ranked-opportunities loop.
</action>
  <verify>
    <automated>python -m pytest tests/test_crypto_pair_run.py -x -q --tb=short 2>&1 | tail -20</automated>
  </verify>
  <done>
    - Duration bug: runner with fast-advancing now_fn stops when elapsed >= duration_seconds mid-cycle-range
    - Dashboard functions exist as module-level helpers (testable in isolation)
    - All existing tests in test_crypto_pair_run.py still pass
    - No JSONL write logic changed
  </done>
</task>

<task type="auto">
  <name>Task 2: Wire --verbose flag through CLI and add tests</name>
  <files>
    tools/cli/crypto_pair_run.py
    tests/test_crypto_pair_run.py
  </files>
  <action>
**In tools/cli/crypto_pair_run.py:**

Add `--verbose` flag to `build_parser()`:

```python
parser.add_argument(
    "--verbose",
    action="store_true",
    default=False,
    help=(
        "Show all market status lines every cycle. "
        "Default (off): show only stats every 10s and any signals/intents."
    ),
)
```

Add `verbose: bool = False` parameter to `run_crypto_pair_runner()` signature. Pass it through to `CryptoPairPaperRunner`:

```python
runner = CryptoPairPaperRunner(
    settings,
    ...,
    verbose=verbose,        # <-- add this
)
```

In `main()`, pass `verbose=args.verbose` to `run_crypto_pair_runner()`.

**In tests/test_crypto_pair_run.py — add these tests:**

Test group A: Duration fix
- `test_duration_stops_on_elapsed_time`: Build a runner with cycle_limit=20, duration_seconds=3.
  Use a now_fn that advances 2 seconds per call (so after 2 cycles, elapsed=4 > 3). Verify
  completed_cycles < 20. Use existing minimal stub pattern from existing tests (stub gamma/clob clients,
  stub discovery_fn returning [], stub scan_fn returning []).

Test group B: Dashboard output
- `test_dashboard_header_format`: Call `_dashboard_header(settings, market_count=12, started_at_str="2026-03-29 20:29:33")` and assert: starts with "=== Crypto Pair Bot", contains "Markets found: 12", contains "Started: 2026-03-29 20:29:33", contains the separator line.
- `test_dashboard_market_line_no_signal`: Call `_dashboard_market_line(ts="20:30:05", opportunity=mock_opp, ref_price=66641.0, price_change_pct=-0.0005, signal_direction="NONE", action="no_action")` and assert line contains "Signal: NONE", does not contain ">>>".
- `test_dashboard_market_line_signal`: Call with signal_direction="UP", action="accumulate". Assert line contains ">>> SIGNAL: UP", contains "BUY YES".
- `test_dashboard_stats_line`: Call `_dashboard_stats_line(cycle=120, observations=2848, signals=0, intents=0, elapsed_seconds=150, duration_seconds=900)`. Assert contains "Cycles: 120", "Observations: 2848", "Remaining: 12m 30s".
- `test_verbose_flag_parsed`: Build parser, parse `["--verbose"]`, assert `args.verbose is True`.
- `test_verbose_flag_default_false`: Build parser, parse `[]`, assert `args.verbose is False`.

Import `_dashboard_header`, `_dashboard_market_line`, `_dashboard_stats_line` from `packages.polymarket.crypto_pairs.paper_runner` at the top of the test file.

Use `from tools.cli.crypto_pair_run import build_parser` for CLI tests.

For the duration test, use the same stub/mock pattern already present in test_crypto_pair_run.py
(look for existing `_make_*` helpers or minimal runner construction patterns).
Do not duplicate heavy fixture infrastructure — reuse what exists.
  </action>
  <verify>
    <automated>python -m pytest tests/test_crypto_pair_run.py -x -q --tb=short 2>&1 | tail -20</automated>
  </verify>
  <done>
    - `python -m polytool crypto-pair-run --help` shows --verbose flag
    - All new tests pass
    - Total test count increases by at least 7 (duration test + 5 dashboard unit tests + 2 CLI flag tests)
    - `python -m pytest tests/ -x -q --tb=short` shows no regressions
  </done>
</task>

</tasks>

<verification>
Run the full test suite after both tasks:

```bash
python -m pytest tests/ -x -q --tb=short 2>&1 | tail -10
```

Smoke test CLI still loads:

```bash
python -m polytool --help
python -m polytool crypto-pair-run --help | grep -E "verbose|duration"
```

Manual inspection (no live markets needed): verify `--verbose` appears in help output.
</verification>

<success_criteria>
- Duration bug fixed: run stops when wall-clock elapsed >= duration_seconds, not just when cycle count exhausted
- `--verbose` flag added to CLI: default off shows only stats/signals/intents; on shows all market lines
- Startup header printed once at launch
- Stats line includes "Remaining: Xm Ys"
- Signal lines highlight with ">>>"
- Intent lines print unconditionally
- All existing tests pass (baseline: 2767)
- At least 7 new tests added covering duration fix + dashboard formatting
- No changes to JSONL write paths, strategy logic, or observation recording
</success_criteria>

<output>
After completion, create `.planning/quick/52-add-live-terminal-dashboard-to-crypto-pa/52-SUMMARY.md`
</output>
