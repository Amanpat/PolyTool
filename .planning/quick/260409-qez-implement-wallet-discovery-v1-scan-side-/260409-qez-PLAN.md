---
phase: quick-260409-qez
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/polymarket/discovery/__init__.py
  - packages/polymarket/discovery/mvf.py
  - tools/cli/scan.py
  - tests/test_mvf.py
  - tests/test_scan_quick_mode.py
autonomous: true
requirements: [SPEC-wallet-discovery-v1-c, SPEC-wallet-discovery-v1-d, AT-06, AT-07]
must_haves:
  truths:
    - "python -m polytool scan <address> --quick completes with zero cloud LLM HTTP calls"
    - "MVF computation produces an 11-dimension vector from a fixture of 50 positions"
    - "MVF output includes metadata block with wallet_address, computation_timestamp, input_trade_count"
    - "Running MVF twice on the same input produces identical output (determinism)"
    - "maker_taker_ratio is null when maker/taker data is unavailable, not fabricated"
    - "Existing scan tests still pass"
  artifacts:
    - path: "packages/polymarket/discovery/mvf.py"
      provides: "MVF 11-dimension fingerprint computation"
      exports: ["compute_mvf", "MvfResult"]
    - path: "packages/polymarket/discovery/__init__.py"
      provides: "Package init for discovery module"
    - path: "tests/test_mvf.py"
      provides: "AT-07 deterministic MVF output shape tests"
    - path: "tests/test_scan_quick_mode.py"
      provides: "AT-06 no-LLM guarantee tests for --quick flag"
  key_links:
    - from: "tools/cli/scan.py"
      to: "packages/polymarket/discovery/mvf.py"
      via: "import compute_mvf; call after dossier positions loaded"
      pattern: "from packages\\.polymarket\\.discovery\\.mvf import compute_mvf"
    - from: "tools/cli/scan.py --quick path"
      to: "run_scan skips API stages"
      via: "--quick flag sets lite pipeline + disables LLM-touching stages"
      pattern: "config\\[.quick.\\]"
---

<objective>
Implement the scan-side changes for Wallet Discovery v1: add a `--quick` flag to the
`scan` CLI command that guarantees zero cloud LLM calls, create the MVF (Multi-Variate
Fingerprint) computation module, append MVF output to dossier artifacts when `--quick`
is used, and prove correctness with deterministic tests.

Purpose: Enable fast, offline wallet fingerprinting as the foundation for the discovery
pipeline. The `--quick` path is the primary scan mode for Loop A queue processing.

Output: Working `--quick` flag, MVF module, and passing AT-06/AT-07 acceptance tests.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@docs/specs/SPEC-wallet-discovery-v1.md
@docs/features/wallet-discovery-v1.md
@tools/cli/scan.py
@polytool/reports/coverage.py (for _extract_positions_payload, extract_position_notional_usd patterns)
@tests/test_scan_trust_artifacts.py (for scan test fixtures and monkeypatch patterns)

<interfaces>
<!-- Key functions and types the executor needs from the existing scan module -->

From tools/cli/scan.py:
```python
def build_parser() -> argparse.ArgumentParser  # Add --quick here
def build_config(args: argparse.Namespace) -> Dict[str, Any]  # Wire quick into config
def apply_scan_defaults(args: argparse.Namespace, argv: list[str]) -> argparse.Namespace
def run_scan(config: Dict[str, Any], argv=None, started_at=None) -> Dict[str, str]

# Existing stage profiles for reference:
LITE_PIPELINE_STAGE_ATTRS = ("ingest_positions", "compute_pnl", "enrich_resolutions", "compute_clv")
FULL_PIPELINE_STAGE_ATTRS = tuple(SCAN_STAGE_FLAG_TO_ATTR.values())

# Dossier loading helpers already available:
def _load_dossier_positions(dossier_root: Path) -> list[dict[str, Any]]
def _load_dossier_json(dossier_root: Path) -> Dict[str, Any]
def _write_dossier_json(dossier_root: Path, dossier: Dict[str, Any]) -> None
def _extract_positions_payload(dossier: Dict[str, Any]) -> list[dict[str, Any]]
```

From polytool/reports/coverage.py:
```python
def extract_position_notional_usd(pos: Dict[str, Any]) -> Optional[float]
# Position fields available: resolution_outcome, entry_price, market_slug,
# category, token_id, size, position_notional_usd, gross_pnl, position_remaining,
# trade_uid, resolved_token_id, condition_id
```

From packages/polymarket/resolution.py:
```python
class ResolutionOutcome(str, Enum):
    WIN = "WIN"
    LOSS = "LOSS"
    PROFIT_EXIT = "PROFIT_EXIT"
    LOSS_EXIT = "LOSS_EXIT"
    PENDING = "PENDING"
    UNKNOWN_RESOLUTION = "UNKNOWN_RESOLUTION"
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Create MVF computation module with deterministic tests (AT-07)</name>
  <files>
    packages/polymarket/discovery/__init__.py,
    packages/polymarket/discovery/mvf.py,
    tests/test_mvf.py
  </files>
  <behavior>
    - Test 1 (output shape): Given 50 synthetic positions with known fields (resolution_outcome, entry_price, market_slug, category, size, timestamps), compute_mvf returns an MvfResult with all 11 dimensions present. Dimensions 1-10 are non-null floats. Dimension 11 (maker_taker_ratio) is null because fixture has no maker/taker data.
    - Test 2 (determinism): Running compute_mvf twice on the same fixture produces byte-identical JSON output.
    - Test 3 (win_rate correctness): Fixture has 25 WIN + 5 PROFIT_EXIT + 10 LOSS + 5 LOSS_EXIT + 5 PENDING = 50 positions. Win rate = (25+5)/(25+5+10+5) = 30/45. PENDING excluded from denominator.
    - Test 4 (empty input): compute_mvf([]) returns MvfResult with all dimensions null and input_trade_count=0.
    - Test 5 (metadata block): Output includes wallet_address, computation_timestamp (ISO-8601), and input_trade_count matching the input length.
    - Test 6 (maker_taker_ratio explicit null): When no position has a maker/taker indicator, maker_taker_ratio is null with a metadata note "maker_taker_data_unavailable".
    - Test 7 (range validation): Each non-null dimension falls within its documented range (win_rate in [0,1], market_concentration in [0,1], category_entropy >= 0, etc.).
  </behavior>
  <action>
    Create `packages/polymarket/discovery/__init__.py` as an empty package init.

    Create `packages/polymarket/discovery/mvf.py` implementing:

    1. A `MvfResult` dataclass (or TypedDict) with fields:
       - `dimensions`: dict mapping dimension name to float or None
       - `metadata`: dict with `wallet_address`, `computation_timestamp`, `input_trade_count`, and `data_notes` (list of strings for missing data explanations)

    2. A `compute_mvf(positions: list[dict], wallet_address: str) -> MvfResult` function computing all 11 dimensions per SPEC-wallet-discovery-v1.md section "MVF Dimensions (v1 definition)":
       - `win_rate` — fraction of resolved positions (excluding PENDING, UNKNOWN_RESOLUTION) that are WIN or PROFIT_EXIT
       - `avg_hold_duration_hours` — mean hold time. Compute from `first_trade_timestamp` / `last_trade_timestamp` fields if present; if these fields are absent, set to null with a data note
       - `median_entry_price` — median of `entry_price` across all positions with valid entry_price
       - `market_concentration` — Herfindahl index over `market_slug` values: sum of (share_per_slug)^2. 1.0 = all one market, approaches 0 for fully diversified
       - `category_entropy` — Shannon entropy of `category` distribution. Use natural log. Handle single-category (entropy=0) and empty/Unknown categories
       - `avg_position_size_usdc` — mean of `position_notional_usd` or `size * entry_price` (use `extract_position_notional_usd` pattern from coverage.py)
       - `trade_frequency_per_day` — total positions / observation window in days. Window = max timestamp - min timestamp across all positions. If window < 1 day, use 1 day as floor
       - `late_entry_rate` — fraction of positions entered in the final 20% of a market's life. Since market end time is not reliably available (Gap E), compute from resolution_outcome: positions with PENDING resolution are excluded; among resolved positions, use available timing data if present, else set to null with a data note
       - `dca_score` — fraction of distinct market_slugs where >1 position exists (multiple entries into same market)
       - `resolution_coverage_rate` — fraction of positions with resolution_outcome NOT in (UNKNOWN_RESOLUTION, PENDING)
       - `maker_taker_ratio` — null with metadata note "maker_taker_data_unavailable" when no maker/taker field is present on positions. If a `side_type` or `maker` field is found, compute fraction that are maker. Do NOT fabricate this value.

    3. A `mvf_to_dict(result: MvfResult) -> dict` serializer for JSON output.

    Constraints:
    - Pure Python math only. No numpy, no pandas, no external deps beyond stdlib.
    - No cloud LLM calls. No network calls. No imports of request libraries.
    - All division operations must guard against ZeroDivisionError.
    - Use `math.log` for entropy, `statistics.median` for median.
    - Deterministic: same input always produces same output. Avoid sets/dicts where iteration order matters in computation (sort keys before iterating).

    Create `tests/test_mvf.py` implementing AT-07 and the behaviors above. The fixture of 50 positions must be defined once and pinned (not generated randomly). Include positions with varying: resolution_outcome (WIN, LOSS, PROFIT_EXIT, LOSS_EXIT, PENDING), entry_price (spread across 0.1-0.9), market_slug (5-8 distinct slugs), category (3-4 distinct categories), and size values.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && rtk python -m pytest tests/test_mvf.py -x -v --tb=short</automated>
  </verify>
  <done>
    - packages/polymarket/discovery/mvf.py exists with compute_mvf and MvfResult exported
    - All 7+ tests in tests/test_mvf.py pass
    - MVF computation is fully deterministic and offline
    - maker_taker_ratio is explicitly null (not fabricated) when data unavailable
    - Each dimension has documented range and the test validates it
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add --quick flag to scan CLI, wire MVF into dossier output, tests (AT-06)</name>
  <files>
    tools/cli/scan.py,
    tests/test_scan_quick_mode.py
  </files>
  <behavior>
    - Test 1 (no-LLM guarantee): Invoking scan with --quick and a mocked API fixture makes zero HTTP calls to any cloud LLM endpoint. Verified by intercepting requests.post/requests.get and asserting no call to gemini/deepseek/openai/anthropic domains.
    - Test 2 (MVF in output): After --quick scan completes, dossier.json at the run root contains an "mvf" top-level key with dimensions dict and metadata dict.
    - Test 3 (--quick implies lite stages): --quick enables only ingest_positions + compute_pnl + enrich_resolutions + compute_clv (same as --lite) and explicitly disables ingest_markets, ingest_activity, compute_opportunities, snapshot_books, warm_clv_cache.
    - Test 4 (--quick without --user errors): --quick still requires --user; missing it prints usage error.
    - Test 5 (existing scan unaffected): Running scan without --quick does NOT add MVF block (no behavior change to existing path).
  </behavior>
  <action>
    Modify `tools/cli/scan.py`:

    1. In `build_parser()`, add a `--quick` argument:
       ```python
       parser.add_argument(
           "--quick",
           action="store_true",
           default=False,
           help=(
               "Fast discovery scan: no LLM calls, no expensive stages. "
               "Produces MVF fingerprint + existing detectors + PnL data. "
               "Hard guarantee: zero cloud LLM endpoint calls under any condition."
           ),
       )
       ```

    2. In `apply_scan_defaults()`, handle `--quick` before `--full` and `--lite`:
       ```python
       if bool(getattr(args, "quick", False)):
           _apply_stage_profile(args, LITE_PIPELINE_STAGE_SET, disable_non_enabled=True)
           return args
       ```
       This makes `--quick` behave like `--lite` for stage selection, ensuring no expensive stages run.

    3. In `build_config()`, propagate `quick` flag:
       ```python
       config["quick"] = bool(getattr(args, "quick", False))
       ```

    4. In `_emit_trust_artifacts()`, after the CLV enrichment block and before the
       coverage report generation (approximately line ~1500), add MVF computation
       when `config.get("quick")` is True:
       ```python
       if bool(config.get("quick", False)):
           from packages.polymarket.discovery.mvf import compute_mvf, mvf_to_dict
           mvf_result = compute_mvf(positions, proxy_wallet)
           dossier = _load_dossier_json(output_dir)
           dossier["mvf"] = mvf_to_dict(mvf_result)
           _write_dossier_json(output_dir, dossier)
       ```
       Use lazy import to avoid loading the discovery module on non-quick paths.

    5. Update the help text in `print_usage()` to document the --quick flag on the
       scan command line: change the scan description to note `[--quick]` option.

    Create `tests/test_scan_quick_mode.py` implementing AT-06:

    - Use the same monkeypatch pattern as `test_scan_trust_artifacts.py` (mock `post_json`, create temp dossier.json with positions fixture).
    - Create a fixture with at least 10 positions having resolution_outcome, entry_price, market_slug, category, and size fields.
    - Mock `post_json` to return appropriate responses for resolve, ingest/trades, run/detectors, and export/user_dossier.
    - For the no-LLM guarantee test: monkeypatch `requests.Session.send` (or `requests.post` and `requests.get`) to record all outbound URLs. After scan completes, assert no URL contains gemini, deepseek, openai, anthropic, or any other LLM provider domain. This is a request-intercepting test, not inspection-only.
    - Assert that config["quick"] is True and that the stages match LITE_PIPELINE_STAGE_SET.
    - Assert dossier.json contains `mvf` key with `dimensions` and `metadata` sub-keys.
    - Assert `mvf.metadata.input_trade_count` matches the position count in the fixture.

    Constraints:
    - Do NOT modify existing test files or change existing behavior for non-quick scans.
    - The `--quick` flag must be mutually exclusive in practice with `--full` (quick takes precedence if both specified, matching the apply_scan_defaults priority order).
    - No changes to the FastAPI server or any API endpoint.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && rtk python -m pytest tests/test_scan_quick_mode.py tests/test_scan_trust_artifacts.py -x -v --tb=short</automated>
  </verify>
  <done>
    - `python -m polytool scan --user @someone --quick` runs with no LLM calls
    - --quick produces MVF block in dossier.json output
    - All new tests in test_scan_quick_mode.py pass
    - All existing tests in test_scan_trust_artifacts.py still pass (no regression)
    - Full test suite: `python -m pytest tests/ -x -q --tb=short` passes with no regressions
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| scan CLI -> PolyTool API | Existing boundary; --quick does not change trust model |
| MVF computation -> dossier.json | Pure offline computation; no new external inputs |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-qez-01 | Information Disclosure | MVF output in dossier.json | accept | MVF data is derived from already-exported dossier positions; no new PII or secrets introduced. Dossier artifacts are already gitignored under artifacts/ |
| T-qez-02 | Tampering | --quick flag bypass | mitigate | AT-06 test uses request-intercepting fixtures to prove zero LLM calls. The flag is handled before --full/--lite in apply_scan_defaults, so it cannot be overridden by combining flags |
| T-qez-03 | Denial of Service | Large position set in MVF | accept | MVF uses O(n) computation with stdlib only; positions are already bounded by scan's MAX_TRADES and page limits |
</threat_model>

<verification>
1. `python -m pytest tests/test_mvf.py -x -v` -- all MVF tests pass
2. `python -m pytest tests/test_scan_quick_mode.py -x -v` -- all AT-06 quick mode tests pass
3. `python -m pytest tests/test_scan_trust_artifacts.py -x -v` -- existing scan tests still pass
4. `python -m pytest tests/ -x -q --tb=short` -- full suite passes with no regressions
5. `python -m polytool --help` -- CLI loads without import errors, scan command shows --quick
</verification>

<success_criteria>
- `--quick` flag accepted by scan CLI parser
- `--quick` guarantees zero cloud LLM HTTP calls (proven by request-intercepting test)
- MVF produces 11-dimension fingerprint from dossier positions
- MVF is deterministic (same input -> same output, proven by test)
- maker_taker_ratio is explicitly null when data unavailable (not fabricated)
- MVF block appended to dossier.json only when `--quick` is used
- All existing tests pass without modification
</success_criteria>

<output>
After completion, create `.planning/quick/260409-qez-implement-wallet-discovery-v1-scan-side-/260409-qez-SUMMARY.md`
</output>
