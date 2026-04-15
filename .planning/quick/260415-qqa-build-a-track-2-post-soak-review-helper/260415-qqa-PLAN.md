---
phase: quick-260415-qqa
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/polymarket/crypto_pairs/reporting.py
  - tools/cli/crypto_pair_review.py
  - polytool/__main__.py
  - tests/test_crypto_pair_review.py
  - docs/dev_logs/2026-04-15_track2_post_soak_review_helper.md
autonomous: true
requirements: ["quick-260415-qqa"]
must_haves:
  truths:
    - "Operator can run `python -m polytool crypto-pair-review --run <path>` on a completed paper soak directory and get a concise one-screen summary"
    - "Review output shows verdict (promote/rerun/reject) with decision reasons"
    - "Review output shows realized paper PnL and key distribution stats (pair cost, profit per pair)"
    - "Review output shows counts: opportunities, intents, pairs, settled pairs"
    - "Review output shows symbols/markets covered"
    - "Review output shows whether any risk controls triggered and which ones"
    - "Review output shows promote-band fit for each rubric metric (pass/rerun/reject per metric)"
    - "Existing tests continue to pass"
  artifacts:
    - path: "packages/polymarket/crypto_pairs/reporting.py"
      provides: "format_post_soak_review() function that reads a report dict and returns a formatted terminal string"
      exports: ["format_post_soak_review"]
    - path: "tools/cli/crypto_pair_review.py"
      provides: "CLI entrypoint for crypto-pair-review command"
      exports: ["main", "build_parser"]
    - path: "polytool/__main__.py"
      provides: "Registers crypto-pair-review command"
    - path: "tests/test_crypto_pair_review.py"
      provides: "Deterministic offline tests for review formatting and CLI"
  key_links:
    - from: "tools/cli/crypto_pair_review.py"
      to: "packages/polymarket/crypto_pairs/reporting.py"
      via: "imports format_post_soak_review and load/generate functions"
      pattern: "from packages.polymarket.crypto_pairs.reporting import"
    - from: "polytool/__main__.py"
      to: "tools/cli/crypto_pair_review.py"
      via: "_command_entrypoint lazy loader"
      pattern: "crypto.pair.review.*_command_entrypoint"
---

<objective>
Build a `crypto-pair-review` CLI command that reads existing paper soak artifacts and prints a concise, operator-readable one-screen summary. The operator should be able to review a completed 24h paper soak with one command and immediately understand: verdict, key metrics, triggered risk controls, and promote-band fit -- without manually reading raw JSON logs.

Purpose: Close the operator workflow gap between "paper soak completed, artifacts written" and "operator understands the outcome." Currently `crypto-pair-report` writes the artifacts but its terminal output is only 6 lines with no metric detail. The review helper fills the last-mile readability gap.

Output: New CLI command `crypto-pair-review`, new `format_post_soak_review()` in reporting.py, deterministic tests, dev log.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/CLAUDE.md
@D:/Coding Projects/Polymarket/PolyTool/packages/polymarket/crypto_pairs/reporting.py
@D:/Coding Projects/Polymarket/PolyTool/tools/cli/crypto_pair_report.py
@D:/Coding Projects/Polymarket/PolyTool/tests/test_crypto_pair_report.py
@D:/Coding Projects/Polymarket/PolyTool/polytool/__main__.py
@D:/Coding Projects/Polymarket/PolyTool/docs/runbooks/TRACK2_OPERATOR_RUNBOOK.md

<interfaces>
<!-- Key types and contracts the executor needs. Extracted from codebase. -->

From packages/polymarket/crypto_pairs/reporting.py:
```python
PAPER_SOAK_SUMMARY_JSON = "paper_soak_summary.json"
PAPER_SOAK_VERDICT_JSON = "paper_soak_verdict.json"

@dataclass(frozen=True)
class LoadedPaperRun:
    run_dir: Path
    manifest: dict[str, Any]
    run_summary: dict[str, Any]
    runtime_events: list[dict[str, Any]]
    # ... other fields

@dataclass(frozen=True)
class CryptoPairReportResult:
    report: dict[str, Any]
    json_path: Path
    markdown_path: Path
    verdict_path: Path

def load_paper_run(run_path: Path | str) -> LoadedPaperRun: ...
def build_paper_soak_summary(loaded_run: LoadedPaperRun) -> dict[str, Any]: ...
def generate_crypto_pair_paper_report(run_path: Path | str) -> CryptoPairReportResult: ...
def render_paper_soak_summary_markdown(report: Mapping[str, Any]) -> str: ...
def build_report_artifact_paths(result: CryptoPairReportResult) -> dict[str, str]: ...
```

The report dict returned by build_paper_soak_summary has this shape:
```python
{
    "schema_version": str,
    "generated_at": str,
    "run_id": str,
    "run_dir": str,
    "metrics": {
        "soak_duration_hours": float | None,
        "opportunities_observed": int,
        "intents_generated": int,
        "completed_pairs": int,
        "paired_exposure_count": int,
        "settled_pair_count": int,
        "pair_completion_rate": float | None,
        "average_completed_pair_cost": float | None,
        "estimated_profit_per_completed_pair": float | None,
        "maker_fill_rate_floor": float | None,
        "partial_leg_incidence": float | None,
        "stale_count": int,
        "disconnect_count": int,
        "net_pnl_usdc": float,
        "safety_violation_count": int,
    },
    "evidence_floor": {"met": bool, "checks": dict},
    "rubric": {
        "decision": str,  # "promote" | "rerun" | "reject"
        "verdict": str,
        "rubric_pass": bool,
        "decision_reasons": list[str],
        "metric_bands": {
            "pair_completion_rate": {"value": float, "band": str, "rule": str},
            "average_completed_pair_cost": {"value": float, "band": str, "rule": str},
            "estimated_profit_per_completed_pair": {"value": float, "band": str, "rule": str},
            "maker_fill_rate_floor": {"value": float, "band": str, "rule": str},
            "partial_leg_incidence": {"value": float, "band": str, "rule": str},
            "feed_state_transitions": {"value": dict, "band": str, "rule": str},
            "safety_violations": {"value": int, "band": str, "rule": str},
            "net_pnl_positive": {"value": float, "band": str, "rule": str},
        },
    },
    "safety_violations": list[{"code": str, "count": int, "details": list[str]}],
    "operational_context": {
        "cycles_completed": int | None,
        "symbols_included": list[str],
        "markets_observed_count": int,
        "markets_by_symbol": dict[str, int],
    },
    "notes": list[str],
}
```

From polytool/__main__.py (registration pattern):
```python
crypto_pair_report_main = _command_entrypoint("tools.cli.crypto_pair_report")
# ...
_COMMANDS = {
    # ...
    "crypto-pair-report": "crypto_pair_report_main",
    # ...
}
```

From tools/cli/crypto_pair_report.py (existing CLI pattern):
```python
def build_parser() -> argparse.ArgumentParser: ...
def main(argv: Optional[list[str]] = None) -> int: ...
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add format_post_soak_review() to reporting.py and create crypto-pair-review CLI</name>
  <files>
    packages/polymarket/crypto_pairs/reporting.py
    tools/cli/crypto_pair_review.py
    polytool/__main__.py
  </files>
  <action>
**In `packages/polymarket/crypto_pairs/reporting.py`**, add a new public function `format_post_soak_review(report: Mapping[str, Any]) -> str` that takes the report dict (same shape as returned by `build_paper_soak_summary`) and returns a concise, terminal-friendly formatted string. The function must produce output that fits on one screen (~40-50 lines max). Structure the output as follows:

1. **Header block** (3 lines):
   - `=== TRACK 2 POST-SOAK REVIEW ===`
   - `Run: {run_id}  |  Duration: {soak_duration_hours}h  |  Generated: {generated_at}`
   - Blank separator line

2. **Verdict block** (3-5 lines):
   - `VERDICT: {verdict}` (the full verdict string like "PROMOTE TO MICRO LIVE CANDIDATE")
   - `Decision: {decision}` (promote/rerun/reject)
   - `Reasons:` followed by each decision_reason as `  - {reason}`
   - Blank separator line

3. **Key Metrics block** (~8 lines):
   - `--- Key Metrics ---`
   - `Net PnL:           {net_pnl_usdc} USDC`
   - `Opportunities:     {opportunities_observed}`
   - `Intents generated:  {intents_generated}`
   - `Completed pairs:   {completed_pairs}`
   - `Settled pairs:     {settled_pair_count}`
   - `Symbols:           {comma-joined symbols_included} ({markets_by_symbol formatted as BTC=N, ETH=N, SOL=N})`
   - `Cycles completed:  {cycles_completed}`
   - Blank separator line

4. **Promote-Band Fit table** (~12 lines):
   - `--- Promote-Band Fit ---`
   - For each of the 8 rubric metric_bands keys (pair_completion_rate, average_completed_pair_cost, estimated_profit_per_completed_pair, maker_fill_rate_floor, partial_leg_incidence, feed_state_transitions, safety_violations, net_pnl_positive), print one line:
     `  {metric_name:40s}  {value:>10s}  [{band}]`
   - Use `_fmt_metric()` (already in the module) for value formatting. For feed_state_transitions, show "stale={N}, disconnect={N}" as the value string. For safety_violations, show the integer count. Use 4 decimal places for rate metrics.
   - Blank separator line

5. **Risk Controls block** (2-5 lines):
   - `--- Risk Controls ---`
   - If `safety_violations` list is empty: `  No risk controls triggered.`
   - If non-empty: for each violation, print `  {code} x{count}: {details[0] if details else ""}` (same format as the markdown renderer already uses)
   - Blank separator line

6. **Evidence Floor block** (2-6 lines):
   - `--- Evidence Floor ---`
   - `Overall: {"MET" if met else "NOT MET"}`
   - For each check in evidence_floor.checks that FAILED (passed=False), print:
     `  FAIL: {check_name} (actual={actual}, required={required})`
   - If all passed, print `  All checks passed.`

7. **Notes block** (only if notes list is non-empty):
   - `--- Notes ---`
   - Each note as `  - {note}`

Format all numeric values using the existing `_fmt_metric()` helper. Use plain ASCII only (no Unicode symbols) per CLAUDE.md Windows gotchas.

Also add a convenience function `load_or_generate_report(run_path: Path) -> dict[str, Any]` that:
- First checks if `paper_soak_summary.json` already exists in the run directory. If yes, reads and returns it (avoids re-computing).
- If not, calls `generate_crypto_pair_paper_report(run_path)` and returns `result.report`.
This allows `crypto-pair-review` to work on runs that already have reports AND on runs that have not been reported yet.

**Create `tools/cli/crypto_pair_review.py`** following the exact pattern of `tools/cli/crypto_pair_report.py`:
- `build_parser()` returns an ArgumentParser with description "Review a completed crypto-pair paper soak. Reads existing report artifacts (or generates them) and prints a concise one-screen operator summary."
- `--run PATH` required argument (same as crypto-pair-report)
- `--json` optional flag: if set, instead of the formatted review, print the paper_soak_summary.json content to stdout (for piping/scripting)
- `main(argv)` function:
  1. Parse args
  2. Call `load_or_generate_report(Path(args.run))`
  3. If `--json`: print the report as formatted JSON and return 0
  4. Otherwise: call `format_post_soak_review(report)` and print the result
  5. Return 0 on success, 1 on CryptoPairReportError or OSError (with error message to stderr)
- `_PREFIX = "[crypto-pair-review]"` for error messages

**In `polytool/__main__.py`**, register the new command:
- Add `crypto_pair_review_main = _command_entrypoint("tools.cli.crypto_pair_review")` near the existing `crypto_pair_report_main` line
- Add `"crypto-pair-review": "crypto_pair_review_main"` to the `_COMMANDS` dict (near crypto-pair-report)
- Add a help line in the Track 2 print block: `print("  crypto-pair-review    One-screen post-soak review: verdict, metrics, risk controls, promote-band fit")`
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m polytool --help 2>&1 | grep -c "crypto-pair-review" && python -c "from packages.polymarket.crypto_pairs.reporting import format_post_soak_review, load_or_generate_report; print('imports OK')"</automated>
  </verify>
  <done>
    - `format_post_soak_review()` exists in reporting.py and returns a formatted string from a report dict
    - `load_or_generate_report()` exists and can read existing summary JSON or generate on the fly
    - `crypto-pair-review` CLI command is registered and appears in `--help`
    - CLI accepts `--run PATH` and optional `--json` flag
    - No existing tests broken
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add deterministic tests for post-soak review helper</name>
  <files>
    tests/test_crypto_pair_review.py
  </files>
  <behavior>
    - Test 1: format_post_soak_review on a promote-verdict report contains all required sections (header, verdict, key metrics, promote-band fit, risk controls, evidence floor)
    - Test 2: format_post_soak_review on a reject-verdict report shows REJECT verdict and triggered risk control details
    - Test 3: format_post_soak_review on a rerun-verdict report shows RERUN verdict and failed evidence floor checks
    - Test 4: format_post_soak_review shows symbols and markets_by_symbol correctly for multi-symbol runs
    - Test 5: load_or_generate_report reads existing paper_soak_summary.json without regenerating
    - Test 6: load_or_generate_report generates report when paper_soak_summary.json does not exist
    - Test 7: CLI main() with --run prints formatted review to stdout (contains VERDICT and Promote-Band Fit)
    - Test 8: CLI main() with --run --json prints valid JSON to stdout
  </behavior>
  <action>
Create `tests/test_crypto_pair_review.py`. Import the `_write_fixture_run` helper and related fixture builders from `tests/test_crypto_pair_report` (they are module-level functions, not class methods, so direct import works). Also import `format_post_soak_review`, `load_or_generate_report`, `build_paper_soak_summary`, `load_paper_run` from `packages.polymarket.crypto_pairs.reporting` and `main as crypto_pair_review_main` from `tools.cli.crypto_pair_review`.

All tests use `tmp_path` fixture and `_write_fixture_run()` to create deterministic paper run directories. No network, no ClickHouse, no external dependencies.

Test structure:

1. `test_review_promote_contains_all_sections` -- Create a promote-passing fixture (30 opps, 30 intents, 30 pairs, 30 settled). Build report via `build_paper_soak_summary(load_paper_run(run_dir))`. Call `format_post_soak_review(report)`. Assert the output contains: "TRACK 2 POST-SOAK REVIEW", "VERDICT:", "PROMOTE TO MICRO LIVE CANDIDATE", "Key Metrics", "Promote-Band Fit", "Risk Controls", "Evidence Floor", "pair_completion_rate", "net_pnl_usdc" or "Net PnL".

2. `test_review_reject_shows_triggered_controls` -- Create a fixture with `stopped_reason="crash"`. Build report, call format_post_soak_review. Assert output contains "REJECT", "stopped_reason_not_completed" in the risk controls section.

3. `test_review_rerun_shows_failed_evidence_floor` -- Create a fixture with only 5 opps/intents/pairs/settled. Build report, call format_post_soak_review. Assert output contains "RERUN", "NOT MET" in evidence floor section, at least one "FAIL:" line.

4. `test_review_multi_symbol_display` -- Create a fixture with `symbol_cycle=["BTC"]*10 + ["ETH"]*10 + ["SOL"]*10`. Build report, call format_post_soak_review. Assert "BTC, ETH, SOL" appears in the output, and "BTC=10" and "ETH=10" and "SOL=10" appear.

5. `test_load_or_generate_reads_existing_summary` -- Create a fixture, manually write a paper_soak_summary.json with a known marker field (e.g. `"test_marker": "preexisting"`). Call `load_or_generate_report(run_dir)`. Assert the returned dict contains `"test_marker": "preexisting"` (proving it read the file, not regenerated).

6. `test_load_or_generate_generates_when_missing` -- Create a fixture but do NOT write paper_soak_summary.json (the fixture helper writes it to run_summary.json which is different). Actually _write_fixture_run does not write paper_soak_summary.json -- it writes run_summary.json. So just call `load_or_generate_report(run_dir)` directly. Assert the returned dict has keys "schema_version", "rubric", "metrics" (proving it generated a full report).

7. `test_cli_review_prints_formatted_output` -- Create a fixture. Call `crypto_pair_review_main(["--run", str(run_dir)])` with `capsys`. Assert captured stdout contains "TRACK 2 POST-SOAK REVIEW" and "Promote-Band Fit".

8. `test_cli_review_json_flag_prints_valid_json` -- Create a fixture. Call `crypto_pair_review_main(["--run", str(run_dir), "--json"])` with `capsys`. Parse captured stdout as JSON. Assert it has "rubric" and "metrics" keys.

Run: `python -m pytest tests/test_crypto_pair_review.py -v --tb=short`
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m pytest tests/test_crypto_pair_review.py -v --tb=short</automated>
  </verify>
  <done>
    - 8 deterministic tests in tests/test_crypto_pair_review.py, all passing
    - Tests cover: promote/reject/rerun verdicts, multi-symbol display, load-or-generate logic, CLI formatted output, CLI --json output
    - No network or ClickHouse dependencies
  </done>
</task>

<task type="auto">
  <name>Task 3: Regression check and dev log</name>
  <files>
    docs/dev_logs/2026-04-15_track2_post_soak_review_helper.md
  </files>
  <action>
Run the full test suite: `python -m pytest tests/ -x -q --tb=short`. Verify zero new failures (the pre-existing `test_gemini_provider_success` failure is known and acceptable).

Run the existing crypto-pair report tests to confirm no breakage: `python -m pytest tests/test_crypto_pair_report.py -v --tb=short`

Run CLI smoke test: `python -m polytool --help`

Create dev log at `docs/dev_logs/2026-04-15_track2_post_soak_review_helper.md` documenting:
- Summary: what was built and why
- Files changed (table: file, action, why)
- What changed in reporting.py (format_post_soak_review, load_or_generate_report)
- What the new CLI command does, with example usage
- Test results (exact counts)
- Codex review note: Skip per CLAUDE.md policy (reporting module only, no execution/risk/signing code)
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m pytest tests/test_crypto_pair_report.py tests/test_crypto_pair_review.py -v --tb=short && python -m polytool --help 2>&1 | grep "crypto-pair-review"</automated>
  </verify>
  <done>
    - Full regression suite shows zero new failures
    - Existing test_crypto_pair_report.py tests (13) still pass
    - New test_crypto_pair_review.py tests (8) pass
    - Dev log written to docs/dev_logs/
    - CLI --help shows crypto-pair-review
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Local filesystem -> review helper | Reads JSON artifacts from disk; no network involved |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-qqa-01 | T (Tampering) | paper_soak_summary.json | accept | Artifacts are local-only, operator-controlled. No integrity verification needed for a review display tool. |
| T-qqa-02 | I (Information Disclosure) | format_post_soak_review | accept | Output is printed to terminal for the operator only. No secrets in paper soak metrics. |
</threat_model>

<verification>
1. `python -m polytool crypto-pair-review --run <any_completed_paper_run_dir>` prints a one-screen summary
2. `python -m polytool crypto-pair-review --run <path> --json` prints valid JSON
3. `python -m pytest tests/test_crypto_pair_review.py -v` -- all 8 tests pass
4. `python -m pytest tests/test_crypto_pair_report.py -v` -- all 13 existing tests still pass
5. `python -m pytest tests/ -x -q --tb=short` -- zero new failures
</verification>

<success_criteria>
- Operator can review a completed paper soak with one command: `python -m polytool crypto-pair-review --run <path>`
- Output fits on one screen and shows verdict, PnL, counts, symbols, risk controls, and promote-band fit
- 8 new deterministic tests pass; 13 existing report tests unbroken
- Dev log documents the work
</success_criteria>

<output>
After completion, create `.planning/quick/260415-qqa-build-a-track-2-post-soak-review-helper/260415-qqa-SUMMARY.md`
</output>
