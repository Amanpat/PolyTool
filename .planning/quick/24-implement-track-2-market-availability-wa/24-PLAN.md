---
phase: quick-24
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/polymarket/crypto_pairs/market_watch.py
  - tools/cli/crypto_pair_watch.py
  - polytool/__main__.py
  - tests/test_crypto_pair_watch.py
  - docs/features/FEATURE-crypto-pair-watch-v0.md
  - docs/dev_logs/2026-03-25_phase1a_crypto_pair_watch_v0.md
autonomous: true
requirements: [QUICK-24]

must_haves:
  truths:
    - "`python -m polytool crypto-pair-watch --help` exits 0 and shows usage"
    - "One-shot mode prints eligible_now yes/no, per-symbol/per-duration counts, and next-action suggestion, then exits 0"
    - "Watch mode polls until timeout and exits 1 when no markets found within timeout"
    - "Watch mode exits 0 with first eligible slugs printed when markets appear during polling"
    - "All artifact files are written deterministically under artifacts/crypto_pairs/watch/<date>/<run_id>/"
    - "All tests in test_crypto_pair_watch.py pass with no network calls"
    - "Existing test_crypto_pair_scan.py continues to pass"
  artifacts:
    - path: "packages/polymarket/crypto_pairs/market_watch.py"
      provides: "MarketAvailabilityWatcher core logic, injectable gamma_client"
      exports: ["AvailabilitySummary", "run_availability_check", "run_watch_loop"]
    - path: "tools/cli/crypto_pair_watch.py"
      provides: "CLI entrypoint: one-shot and watch modes, artifact writes"
      exports: ["main", "build_parser", "run_crypto_pair_watch"]
    - path: "tests/test_crypto_pair_watch.py"
      provides: "Offline tests: no-eligible, eligible-present, mixed, watch-timeout, artifact determinism"
    - path: "docs/dev_logs/2026-03-25_phase1a_crypto_pair_watch_v0.md"
      provides: "Dev log"
  key_links:
    - from: "tools/cli/crypto_pair_watch.py"
      to: "packages/polymarket/crypto_pairs/market_watch.py"
      via: "from packages.polymarket.crypto_pairs.market_watch import run_availability_check, run_watch_loop"
    - from: "tools/cli/crypto_pair_watch.py"
      to: "packages/polymarket/crypto_pairs/market_discovery.py"
      via: "reused discover_crypto_pair_markets (no fork)"
    - from: "polytool/__main__.py"
      to: "tools/cli/crypto_pair_watch.py"
      via: "crypto_pair_watch_main = _command_entrypoint(...); _COMMAND_HANDLER_NAMES['crypto-pair-watch']"
---

<objective>
Implement the Track 2 market-availability watcher for the crypto pair bot.

Purpose: The immediate blocker is that Polymarket has zero active BTC/ETH/SOL 5m/15m markets.
This command gives the operator a lightweight, artifact-producing tool to check and poll for
eligible markets without running the full paper runner. When markets appear, the operator will
know immediately which slugs are eligible and what to do next.

Output:
- packages/polymarket/crypto_pairs/market_watch.py — core availability evaluator
- tools/cli/crypto_pair_watch.py — CLI with one-shot and watch modes
- polytool/__main__.py — crypto-pair-watch command registration
- tests/test_crypto_pair_watch.py — 8+ offline tests
- docs/features/FEATURE-crypto-pair-watch-v0.md — feature doc
- docs/dev_logs/2026-03-25_phase1a_crypto_pair_watch_v0.md — dev log
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/CLAUDE.md
@D:/Coding Projects/Polymarket/PolyTool/packages/polymarket/crypto_pairs/market_discovery.py
@D:/Coding Projects/Polymarket/PolyTool/tools/cli/crypto_pair_scan.py
@D:/Coding Projects/Polymarket/PolyTool/polytool/__main__.py

<interfaces>
<!-- Key types and contracts the executor needs. -->

From packages/polymarket/crypto_pairs/market_discovery.py:
```python
@dataclass
class CryptoPairMarket:
    slug: str
    condition_id: str
    question: str
    symbol: str           # BTC | ETH | SOL
    duration_min: int     # 5 | 15
    yes_token_id: str
    no_token_id: str
    end_date_iso: Optional[str] = None
    active: bool = True
    accepting_orders: Optional[bool] = None

def discover_crypto_pair_markets(
    gamma_client=None,
    max_pages: int = 5,
    page_size: int = 100,
) -> list[CryptoPairMarket]:
    """Returns active BTC/ETH/SOL 5m/15m binary markets from Gamma API."""
```

From tools/cli/crypto_pair_scan.py (patterns to follow):
```python
# Artifact helpers pattern
def _utcnow() -> datetime: ...
def _iso_utc(dt: datetime) -> str: ...
def _run_dir(base: Path, date_str: str, run_id: str) -> Path: ...
def _write_json(path: Path, payload: Any) -> None: ...  # mkdir + json.dumps indent=2 sort_keys=True

# Core function pattern (injectable for tests)
def run_crypto_pair_scan(
    *,
    output_base: Optional[Path] = None,
    gamma_client=None,     # injected for offline tests
    ...
) -> dict[str, Any]:
    ...  # returns manifest dict
```

From polytool/__main__.py (registration pattern):
```python
# Add near line 66:
crypto_pair_watch_main = _command_entrypoint("tools.cli.crypto_pair_watch")

# Add to _COMMAND_HANDLER_NAMES dict:
"crypto-pair-watch": "crypto_pair_watch_main",

# Add to print_usage() Crypto Pair Bot section:
print("  crypto-pair-watch     Check whether eligible BTC/ETH/SOL 5m/15m markets exist; optionally poll until they appear")
```

From tests/test_crypto_pair_scan.py (test pattern):
```python
# Mock helpers used in existing tests
def _make_mock_market(slug, question, clob_token_ids, outcomes, active=True, accepting_orders=True) -> MagicMock:
    m = MagicMock()
    m.market_slug = slug; m.question = question; m.clob_token_ids = clob_token_ids
    m.outcomes = outcomes; m.active = active; m.accepting_orders = accepting_orders
    m.condition_id = f"cond_{slug}"; m.end_date_iso = None
    return m

def _make_gamma_client(markets: list) -> MagicMock:
    result = MagicMock(); result.markets = markets
    client = MagicMock(); client.fetch_all_markets.return_value = result
    return client
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Implement market_watch.py core availability evaluator</name>
  <files>packages/polymarket/crypto_pairs/market_watch.py</files>
  <action>
Create packages/polymarket/crypto_pairs/market_watch.py. This module wraps discover_crypto_pair_markets
with availability evaluation logic. It must NOT fork the classifier — call discover_crypto_pair_markets
directly.

Define a dataclass AvailabilitySummary with fields:
  - eligible_now: bool
  - total_eligible: int
  - by_symbol: dict[str, int]  (e.g. {"BTC": 0, "ETH": 0, "SOL": 0})
  - by_duration: dict[str, int]  (e.g. {"5m": 0, "15m": 0})
  - first_eligible_slugs: list[str]  (up to 5 slugs, empty if none)
  - rejection_reason: Optional[str]  (human-readable explanation when eligible_now=False)
  - checked_at: str  (ISO UTC timestamp)

Implement run_availability_check(gamma_client=None, max_pages=5, page_size=100) -> AvailabilitySummary:
  - Calls discover_crypto_pair_markets(gamma_client=gamma_client, max_pages=max_pages, page_size=page_size)
  - Populates AvailabilitySummary from results
  - eligible_now = True when total_eligible > 0
  - rejection_reason = "No active BTC/ETH/SOL 5m/15m binary pair markets found" when eligible_now=False, else None
  - first_eligible_slugs = [m.slug for m in markets[:5]]
  - checked_at = current UTC ISO timestamp

Implement run_watch_loop(
    *,
    poll_interval_seconds: int = 60,
    timeout_seconds: int = 3600,
    gamma_client=None,
    _sleep_fn=None,         # injectable for tests (replaces time.sleep)
    _check_fn=None,         # injectable for tests (replaces run_availability_check)
) -> tuple[bool, AvailabilitySummary]:
  - Returns (found: bool, last_summary: AvailabilitySummary)
  - Polls run_availability_check every poll_interval_seconds
  - Returns (True, summary) immediately when eligible_now=True
  - Returns (False, last_summary) when timeout_seconds elapsed with no eligible markets
  - Uses _sleep_fn (defaults to time.sleep) and _check_fn (defaults to run_availability_check)
  - This enables full offline testing without real time.sleep
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -c "from packages.polymarket.crypto_pairs.market_watch import AvailabilitySummary, run_availability_check, run_watch_loop; print('OK')"</automated>
  </verify>
  <done>market_watch.py imports cleanly; AvailabilitySummary, run_availability_check, and run_watch_loop are all importable</done>
</task>

<task type="auto">
  <name>Task 2: Implement CLI, register command, write tests and docs</name>
  <files>
    tools/cli/crypto_pair_watch.py,
    polytool/__main__.py,
    tests/test_crypto_pair_watch.py,
    docs/features/FEATURE-crypto-pair-watch-v0.md,
    docs/dev_logs/2026-03-25_phase1a_crypto_pair_watch_v0.md
  </files>
  <action>
--- tools/cli/crypto_pair_watch.py ---
Follow the exact same module layout as tools/cli/crypto_pair_scan.py.

build_parser() -> argparse.ArgumentParser:
  - --symbol: choices=[BTC, ETH, SOL], default=None (kept for future filter support; passed to gamma but discovery always returns all — OK for v0)
  - --duration: type=int, choices=[5, 15], default=None
  - --watch: store_true; if set, enter watch mode (poll until eligible or timeout)
  - --poll-interval: type=int, default=60, help="Seconds between polls in watch mode"
  - --timeout: type=int, default=3600, help="Watch mode timeout in seconds"
  - --output: default=None, help="Base artifact directory (default: artifacts/crypto_pairs/watch)"

run_crypto_pair_watch(
    *,
    watch_mode: bool = False,
    poll_interval_seconds: int = 60,
    timeout_seconds: int = 3600,
    output_base: Optional[Path] = None,
    gamma_client=None,
    _check_fn=None,      # injectable for tests
    _sleep_fn=None,      # injectable for tests
) -> dict[str, Any]:
  Generates run_id and date_str. run_dir = artifacts/crypto_pairs/watch/<date>/<run_id>/.

  One-shot mode (watch_mode=False):
    - Call run_availability_check(gamma_client=gamma_client)
    - Print structured output (see below)
    - Write artifacts and return watch_manifest dict

  Watch mode (watch_mode=True):
    - Print "[crypto-pair-watch] Entering watch mode (poll every {N}s, timeout {M}s)..."
    - Call run_watch_loop(poll_interval_seconds, timeout_seconds, gamma_client, _sleep_fn, _check_fn)
    - Print each poll result as it happens (do not buffer)
    - On found=True: print eligible slugs and "Next action: run crypto-pair-scan then crypto-pair-run"
    - On timeout: print "Watch mode timed out after {N}s. No eligible markets found."
    - Write artifacts from final summary

  Printed operator output (one-shot):
    [crypto-pair-watch] eligible_now : yes/no
    [crypto-pair-watch] total_eligible: N
    [crypto-pair-watch] by_symbol     : BTC=N ETH=N SOL=N
    [crypto-pair-watch] by_duration   : 5m=N 15m=N
    [crypto-pair-watch] checked_at    : <ISO>
    [crypto-pair-watch] next_action   : <suggestion>

  next_action suggestion:
    - If eligible_now: "Run: python -m polytool crypto-pair-scan (then crypto-pair-run when ready)"
    - If not eligible_now: "Markets unavailable. Re-run later or use --watch --timeout 3600"

  Artifacts written to run_dir/:
    watch_manifest.json — {run_id, generated_at, mode, summary_ref, artifact_dir}
    availability_summary.json — full AvailabilitySummary as dict (use dataclasses.asdict)
    availability_summary.md — Markdown report with all fields, next_action, and assumptions note

  main(argv) -> int:
    - Parse args, call run_crypto_pair_watch
    - In watch mode: return 0 if found, 1 if timed out
    - In one-shot: return 0 always (even when no eligible markets; this is informational)
    - Wrap in try/except, print error to stderr, return 1 on exception

--- polytool/__main__.py ---
Add near line 67 (after crypto_pair_report_main):
  crypto_pair_watch_main = _command_entrypoint("tools.cli.crypto_pair_watch")

Add to _COMMAND_HANDLER_NAMES dict (keep alphabetical order within the crypto-pair block):
  "crypto-pair-watch": "crypto_pair_watch_main",

Add to print_usage() Crypto Pair Bot section:
  print("  crypto-pair-watch     Check whether eligible BTC/ETH/SOL 5m/15m markets exist; poll with --watch")

--- tests/test_crypto_pair_watch.py ---
Write at minimum 8 offline tests. No network calls. Use _make_mock_market and _make_gamma_client
helpers (copy from test_crypto_pair_scan.py pattern).

Required test cases:
1. test_no_eligible_markets — gamma returns markets but none match BTC/ETH/SOL 5m/15m; eligible_now=False, total=0
2. test_eligible_markets_present — gamma returns 2 valid BTC 5m markets; eligible_now=True, total=2, by_symbol={"BTC":2,...}
3. test_mixed_markets_irrelevant_filtered — mix of eligible and non-eligible; counts only eligible
4. test_availability_summary_fields_populated — all AvailabilitySummary fields are non-None/correct types
5. test_watch_mode_finds_markets_immediately — _check_fn returns eligible on first call; returns (True, summary)
6. test_watch_mode_timeout — _check_fn always returns not-eligible; _sleep_fn counted; returns (False, summary) after timeout
7. test_artifacts_written — run_crypto_pair_watch writes watch_manifest.json, availability_summary.json, availability_summary.md in tmpdir
8. test_cli_oneshot_help — build_parser().parse_args(["--help"]) raises SystemExit(0)
9. test_cli_oneshot_no_markets_exits_0 — main(["--output", tmpdir]) returns 0 even with no eligible markets
10. test_cli_watch_timeout_exits_1 — main(["--watch", "--timeout", "1", "--output", tmpdir]) returns 1 on timeout (inject fast _sleep and _check)

For tests 7/9/10: inject output_base via a tempfile.mkdtemp() path. Pass gamma_client stub via
monkeypatching run_crypto_pair_watch or by calling the function directly with injectable args.

For test 6 (watch timeout): _sleep_fn=lambda n: None (no real sleep), _check_fn returns
AvailabilitySummary(eligible_now=False, ...) on every call; timeout_seconds=1, poll_interval_seconds=1
so loop exits after 1 iteration.

--- docs/features/FEATURE-crypto-pair-watch-v0.md ---
Write a concise feature doc (100-150 lines):
  - Purpose: market availability watcher for Track 2 operator workflow
  - CLI usage examples (one-shot, watch mode, --symbol, --timeout)
  - Artifact schema for watch_manifest.json and availability_summary.json
  - next_action guidance
  - Limitations (v0: no per-symbol/duration filter wiring to gamma, informational only)

--- docs/dev_logs/2026-03-25_phase1a_crypto_pair_watch_v0.md ---
Write a standard dev log:
  - Date: 2026-03-25
  - Context: Coinbase soak confirmed working (quick-023); Polymarket has zero active BTC/ETH/SOL
    5m/15m markets; this watch command closes the operational gap while waiting for markets to rotate in
  - What was built (files, key design decisions)
  - How to verify (test commands, expected results)
  - Open questions / next steps (check periodically, run crypto-pair-scan when eligible_now=yes)
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m polytool crypto-pair-watch --help && python -m pytest tests/test_crypto_pair_watch.py tests/test_crypto_pair_scan.py -q --tb=short</automated>
  </verify>
  <done>
- `python -m polytool crypto-pair-watch --help` exits 0 and shows usage
- All tests in test_crypto_pair_watch.py pass (minimum 8 tests)
- test_crypto_pair_scan.py continues to pass
- watch_manifest.json, availability_summary.json, availability_summary.md are written to run_dir
- Feature doc and dev log both exist
  </done>
</task>

</tasks>

<verification>
After both tasks complete, run the full smoke test:

```bash
cd "D:/Coding Projects/Polymarket/PolyTool"
python -m polytool --help | grep crypto-pair-watch
python -m polytool crypto-pair-watch --help
python -m pytest tests/test_crypto_pair_watch.py tests/test_crypto_pair_scan.py -q --tb=short
python -m pytest tests/ -x -q --tb=short
```

Expected: `--help` shows the new command, all watch tests pass, full suite has 0 failures.
</verification>

<success_criteria>
- `python -m polytool crypto-pair-watch` is a working CLI command (registered in __main__.py)
- One-shot mode: prints eligible_now, counts, next-action suggestion, exits 0
- Watch mode: polls at interval, exits 0 when found, exits 1 on timeout
- Artifacts written deterministically: watch_manifest.json, availability_summary.json, availability_summary.md
- 8+ offline tests in test_crypto_pair_watch.py — all pass, zero network calls
- Existing test_crypto_pair_scan.py tests continue to pass
- market_watch.py wraps discover_crypto_pair_markets — no fork of classifier logic
- Feature doc and dev log both written
</success_criteria>

<output>
After completion, update STATE.md to note quick-024 complete and that the market-availability watcher
is now operational. No SUMMARY.md is required for quick tasks.
</output>
