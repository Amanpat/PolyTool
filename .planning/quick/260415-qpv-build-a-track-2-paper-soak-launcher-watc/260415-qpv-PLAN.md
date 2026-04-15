---
phase: quick-260415-qpv
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/polymarket/crypto_pairs/await_soak.py
  - tools/cli/crypto_pair_await_soak.py
  - tests/test_crypto_pair_await_soak.py
  - docs/dev_logs/2026-04-15_track2_soak_launcher_watchdog.md
autonomous: true
requirements: ["TRACK2-SOAK-LAUNCHER"]

must_haves:
  truths:
    - "Operator runs one command to wait-for-markets-then-launch a full 24h paper soak with validated defaults"
    - "Launch plan includes --auto-report, --sink-enabled, --heartbeat-minutes 30 and correct 24h duration"
    - "Prerequisite validation checks kill switch file is clear before launch"
    - "CLI output after child exit points to verdict.json path and artifact directory"
    - "No strategy semantics are changed; only launcher/watchdog surfaces touched"
  artifacts:
    - path: "packages/polymarket/crypto_pairs/await_soak.py"
      provides: "Hardened soak launch plan builder + preflight validation + verdict path extraction"
    - path: "tools/cli/crypto_pair_await_soak.py"
      provides: "CLI flags for --auto-report, --sink-enabled, --heartbeat-minutes, --max-capital-window-usdc"
    - path: "tests/test_crypto_pair_await_soak.py"
      provides: "Deterministic tests for hardened launcher behavior"
    - path: "docs/dev_logs/2026-04-15_track2_soak_launcher_watchdog.md"
      provides: "Mandatory dev log"
  key_links:
    - from: "tools/cli/crypto_pair_await_soak.py"
      to: "packages/polymarket/crypto_pairs/await_soak.py"
      via: "run_crypto_pair_await_soak() and build_coinbase_smoke_soak_launch_plan()"
      pattern: "from packages\\.polymarket\\.crypto_pairs\\.await_soak import"
    - from: "packages/polymarket/crypto_pairs/await_soak.py"
      to: "tools/cli/crypto_pair_run.py"
      via: "subprocess launch with constructed argv"
      pattern: "crypto-pair-run"
---

<objective>
Harden the Track 2 `crypto-pair-await-soak` into a single safe entrypoint for launching
a 24h paper soak with validated defaults, prerequisite checks, and clear verdict output.

Purpose: The existing `await_soak` launcher builds a bare-bones command missing critical
soak flags (--auto-report, --sink-enabled, proper 24h duration, 30-min heartbeat). An
operator must manually remember to add these flags or risk an incomplete soak. This plan
upgrades the launcher to produce the full "runbook-grade" paper soak command by default,
validate that the kill switch is clear before launching, and surface the verdict.json
path in the post-run output so the operator can immediately triage the result.

Output: Hardened await_soak module, updated CLI, deterministic tests, dev log.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/CLAUDE.md
@D:/Coding Projects/Polymarket/PolyTool/docs/runbooks/TRACK2_OPERATOR_RUNBOOK.md

<interfaces>
<!-- Key types and contracts the executor needs. Extracted from codebase. -->
<!-- Executor should use these directly -- no codebase exploration needed. -->

From packages/polymarket/crypto_pairs/await_soak.py:
```python
DEFAULT_AWAIT_SOAK_ARTIFACTS_DIR = Path("artifacts/crypto_pairs/await_soak")
DEFAULT_TIMEOUT_SECONDS = 3600
DEFAULT_POLL_INTERVAL_SECONDS = 60
DEFAULT_DURATION_SECONDS = 1800
DEFAULT_HEARTBEAT_SECONDS = 60
DEFAULT_REFERENCE_FEED_PROVIDER = "coinbase"
AWAIT_SOAK_SCHEMA_VERSION = "crypto_pair_await_soak_v0"

@dataclass(frozen=True)
class AwaitSoakLaunchPlan:
    argv: tuple[str, ...]
    display_argv: tuple[str, ...]
    display_command: str
    duration_seconds: int
    heartbeat_seconds: int
    reference_feed_provider: str

@dataclass(frozen=True)
class AwaitSoakLaunchResult:
    exit_code: int
    output_text: str = ""
    launched_run_artifact_dir: Optional[str] = None
    launched_run_manifest_path: Optional[str] = None
    launched_run_summary_path: Optional[str] = None

def build_coinbase_smoke_soak_launch_plan(
    *, duration_seconds: int = DEFAULT_DURATION_SECONDS,
    heartbeat_seconds: int = DEFAULT_HEARTBEAT_SECONDS,
    python_executable: Optional[str] = None,
) -> AwaitSoakLaunchPlan:

def run_crypto_pair_await_soak(
    *, timeout_seconds, poll_interval_seconds, duration_seconds,
    heartbeat_seconds, output_base, gamma_client, python_executable,
    _watch_fn, _launcher_fn, _sleep_fn, _check_fn, _print_fn,
) -> dict[str, Any]:

def _extract_cli_value(output_lines: list[str], field_name: str) -> Optional[str]:
```

From packages/polymarket/crypto_pairs/paper_runner.py:
```python
DEFAULT_KILL_SWITCH_PATH = Path("artifacts/crypto_pairs/kill_switch.txt")
```

From tools/cli/crypto_pair_await_soak.py:
```python
def build_parser() -> argparse.ArgumentParser:
def main(argv: Optional[list[str]] = None) -> int:
```

CLI output fields extractable via _extract_cli_value (from crypto_pair_run.py main()):
- "artifact_dir", "manifest_path", "run_summary", "report_json", "report_md", "report_verdict"
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Harden await_soak launch plan and add preflight validation</name>
  <files>
    packages/polymarket/crypto_pairs/await_soak.py
    tools/cli/crypto_pair_await_soak.py
  </files>
  <action>
Modify `packages/polymarket/crypto_pairs/await_soak.py`:

1. **Update defaults** for full soak (not smoke test):
   - Change `DEFAULT_DURATION_SECONDS = 1800` to `DEFAULT_SOAK_DURATION_SECONDS = 86400` (24h).
     Keep the old `DEFAULT_DURATION_SECONDS = 1800` as `DEFAULT_SMOKE_DURATION_SECONDS` for
     backward compat. The `build_coinbase_smoke_soak_launch_plan` default parameter should
     switch to `DEFAULT_SOAK_DURATION_SECONDS`.
   - Change `DEFAULT_HEARTBEAT_SECONDS = 60` to `DEFAULT_SOAK_HEARTBEAT_SECONDS = 1800` (30min).
     Keep old constant for backward compat.

2. **Expand `AwaitSoakLaunchPlan`** with new fields (backward-compatible frozen dataclass):
   - `auto_report: bool = True`
   - `sink_enabled: bool = False`
   - `max_capital_window_usdc: Optional[float] = None`

3. **Expand `build_coinbase_smoke_soak_launch_plan()`** to accept:
   - `auto_report: bool = True`
   - `sink_enabled: bool = False`
   - `max_capital_window_usdc: Optional[float] = None`
   Then conditionally append these to the argv/display_argv tuples:
   - If `auto_report`: append `"--auto-report"`
   - If `sink_enabled`: append `"--sink-enabled"`
   - If `max_capital_window_usdc` is not None: append `"--max-capital-window-usdc", str(value)`
   Use `"--heartbeat-seconds"` for the heartbeat as already done.

4. **Add `validate_soak_prerequisites()` function**:
   ```python
   def validate_soak_prerequisites(
       *,
       kill_switch_path: Path = DEFAULT_KILL_SWITCH_PATH,
   ) -> list[str]:
       """Return a list of blocking issues. Empty list = all clear."""
       issues: list[str] = []
       if kill_switch_path.exists():
           content = kill_switch_path.read_text(encoding="utf-8").strip().lower()
           if content in ("1", "true", "yes", "on"):
               issues.append(
                   f"Kill switch is tripped ({kill_switch_path}). "
                   "Clear it before launching: rm {kill_switch_path}"
               )
       return issues
   ```
   Import `DEFAULT_KILL_SWITCH_PATH` from `.paper_runner`.

5. **Call `validate_soak_prerequisites()` in `run_crypto_pair_await_soak()`** right after
   `found=True` (before building the launch plan). Accept a new keyword param
   `kill_switch_path: Optional[Path] = None` and
   `_validate_fn: Optional[Callable] = None` for test injection. If issues are non-empty,
   set `status="preflight_failed"`, write the issues to the manifest `launch.preflight_issues`
   field, print them, write launcher artifacts, and return exit_code=1 without launching.

6. **Extract verdict path from child output**: After the child finishes, call
   `_extract_cli_value(output_lines, "report_verdict")` (already exists in the output).
   Add `launched_run_verdict` to `AwaitSoakLaunchResult` (Optional[str], default None).
   Populate from `_extract_cli_value(output_lines, "report_verdict")`.
   In `run_crypto_pair_await_soak`, after launch: extract verdict and print it:
   ```
   [crypto-pair-await-soak] verdict       : PROMOTE TO MICRO LIVE CANDIDATE
   [crypto-pair-await-soak] verdict_json  : artifacts/tapes/crypto/.../paper_soak_verdict.json
   ```
   The verdict_json path is derivable: `launched_run_artifact_dir + "/paper_soak_verdict.json"`.
   Also add `launched_run_verdict` and `launched_run_verdict_json_path` to the
   `manifest["launch"]` dict.

Modify `tools/cli/crypto_pair_await_soak.py`:

7. **Add CLI flags** to `build_parser()`:
   - `--auto-report` (store_true, default True via `set_defaults(auto_report=True)` pattern;
     add `--no-auto-report` to opt out)
   - `--sink-enabled` (store_true, default False)
   - `--heartbeat-minutes` (int, default 30, mapped to seconds when calling the core)
   - `--kill-switch` (str, default from `DEFAULT_KILL_SWITCH_PATH`)
   - `--max-capital-window-usdc` (float, optional)

8. **Wire new flags** in `main()`:
   - Pass `auto_report`, `sink_enabled`, `max_capital_window_usdc` to
     `build_coinbase_smoke_soak_launch_plan` via `run_crypto_pair_await_soak`.
   - `heartbeat_seconds = args.heartbeat_minutes * 60`
   - `kill_switch_path = Path(args.kill_switch)`
   - `run_crypto_pair_await_soak()` needs these params wired through. Add `auto_report`,
     `sink_enabled`, `max_capital_window_usdc`, `kill_switch_path` params to
     `run_crypto_pair_await_soak()`.

IMPORTANT: Do NOT change any strategy logic, paper_runner.py run loop, risk controls,
reporting.py, or any existing behavior of `crypto-pair-run` itself. All changes are
confined to the await_soak launcher module and its CLI.
  </action>
  <verify>
    <automated>python -m pytest tests/test_crypto_pair_await_soak.py -x -v --tb=short</automated>
  </verify>
  <done>
    - build_coinbase_smoke_soak_launch_plan() with no overrides produces command with
      --auto-report, --duration-seconds 86400, --heartbeat-seconds 1800, coinbase feed
    - validate_soak_prerequisites() returns blocking issue when kill switch is tripped
    - run_crypto_pair_await_soak() refuses to launch when kill switch is tripped
    - Verdict path extracted from child output and printed + written to manifest
    - Existing tests still pass (backward compat)
  </done>
</task>

<task type="auto">
  <name>Task 2: Add deterministic tests for hardened launcher behavior</name>
  <files>
    tests/test_crypto_pair_await_soak.py
  </files>
  <action>
Add new test cases to `tests/test_crypto_pair_await_soak.py`. All tests must be fully
offline (no network, no ClickHouse, no filesystem side-effects outside tmp_path).
Use the existing test patterns and fixtures already in the file.

New tests to add:

1. **`test_default_launch_plan_includes_auto_report_and_24h_duration`**:
   Call `build_coinbase_smoke_soak_launch_plan()` with no args. Assert:
   - `"--auto-report"` in `plan.display_argv`
   - `"--duration-seconds"` followed by `"86400"` in `plan.display_argv`
   - `"--heartbeat-seconds"` followed by `"1800"` in `plan.display_argv`
   - `plan.auto_report is True`
   - `plan.duration_seconds == 86400`

2. **`test_launch_plan_with_sink_enabled`**:
   Call with `sink_enabled=True`. Assert `"--sink-enabled"` in `plan.display_argv`.

3. **`test_launch_plan_with_capital_window`**:
   Call with `max_capital_window_usdc=25.0`. Assert `"--max-capital-window-usdc"` and
   `"25.0"` appear consecutively in `plan.display_argv`.

4. **`test_launch_plan_without_auto_report`**:
   Call with `auto_report=False`. Assert `"--auto-report"` NOT in `plan.display_argv`.

5. **`test_preflight_blocks_on_tripped_kill_switch`** (tmp_path):
   Create a kill switch file with content `"1\n"`. Call `validate_soak_prerequisites(
   kill_switch_path=tmp_path/"kill_switch.txt")`. Assert returned list is non-empty
   and contains "Kill switch is tripped".

6. **`test_preflight_passes_when_kill_switch_absent`** (tmp_path):
   Do NOT create the file. Call `validate_soak_prerequisites(
   kill_switch_path=tmp_path/"kill_switch.txt")`. Assert returned list is empty.

7. **`test_preflight_passes_when_kill_switch_file_empty`** (tmp_path):
   Create file with empty content. Assert returned list is empty.

8. **`test_await_soak_refuses_launch_on_tripped_kill_switch`** (tmp_path):
   Create tripped kill switch. Call `run_crypto_pair_await_soak()` with `_watch_fn` that
   returns `(True, _eligible_summary())` and `kill_switch_path` pointing to the tripped
   file. Assert `manifest["status"] == "preflight_failed"` and
   `manifest["exit_code"] == 1` and `manifest["launch"]["launched"] is False`.

9. **`test_verdict_extracted_from_child_output`** (tmp_path):
   Call `run_crypto_pair_await_soak()` with a `_launcher_fn` that returns an
   `AwaitSoakLaunchResult` with `output_text` containing a line like
   `"[crypto-pair-run] report_verdict: PROMOTE TO MICRO LIVE CANDIDATE\n"` and
   `launched_run_artifact_dir="some/path"`.
   Assert `manifest["launch"]["launched_run_verdict"]` contains "PROMOTE" and
   `manifest["launch"]["launched_run_verdict_json_path"]` ends with
   `"paper_soak_verdict.json"`.

10. **`test_no_live_flag_in_hardened_launch_command`**:
    Call `build_coinbase_smoke_soak_launch_plan()` with `auto_report=True,
    sink_enabled=True`. Assert `"--live"` not in `plan.argv` and `"--live"` not in
    `plan.display_argv`.

Also update existing tests if their assertions are broken by the new defaults (e.g.,
`test_launch_command_construction_uses_standard_coinbase_smoke_soak_defaults` now expects
`--duration-seconds 86400` not `1800`, and `--auto-report` in the argv). Fix these
assertions to match the new defaults.
  </action>
  <verify>
    <automated>python -m pytest tests/test_crypto_pair_await_soak.py -x -v --tb=short</automated>
  </verify>
  <done>
    - All new tests pass covering: default soak flags, sink flag, capital window flag,
      opt-out of auto-report, kill switch preflight (tripped/absent/empty), launch refusal
      on tripped kill switch, verdict extraction, no --live flag
    - Existing tests updated for new defaults and still pass
    - Total test count in file: >= 17 (7 original + 10 new)
  </done>
</task>

<task type="auto">
  <name>Task 3: Write dev log and run regression</name>
  <files>
    docs/dev_logs/2026-04-15_track2_soak_launcher_watchdog.md
  </files>
  <action>
1. Run the targeted test suite:
   ```
   python -m pytest tests/test_crypto_pair_await_soak.py -v --tb=short
   ```

2. Run the crypto-pair regression slice:
   ```
   python -m pytest tests/test_crypto_pair_await_soak.py tests/test_crypto_pair_soak_workflow.py tests/test_crypto_pair_run.py tests/test_crypto_pair_risk_controls.py tests/test_crypto_pair_report.py -v --tb=short
   ```

3. Run the CLI smoke test:
   ```
   python -m polytool --help
   ```

4. Create `docs/dev_logs/2026-04-15_track2_soak_launcher_watchdog.md` with:
   - Summary of what was built
   - Files changed and why (packages/polymarket/crypto_pairs/await_soak.py,
     tools/cli/crypto_pair_await_soak.py, tests/test_crypto_pair_await_soak.py)
   - Exact commands run and output (test counts, pass/fail)
   - What operator friction was removed (one command replaces manual flag assembly;
     kill switch checked automatically; verdict surfaced without manual artifact inspection)
   - Remaining gaps before live use (EU VPS, oracle mismatch, micro-live scaffold,
     SOL adverse selection review -- unchanged from prior dev logs)
   - Codex review note (skip per policy -- no execution/risk/order-placement code touched)
  </action>
  <verify>
    <automated>python -m pytest tests/test_crypto_pair_await_soak.py tests/test_crypto_pair_soak_workflow.py tests/test_crypto_pair_run.py -x -v --tb=short</automated>
  </verify>
  <done>
    - All targeted crypto-pair tests pass with zero regressions
    - CLI loads without import errors
    - Dev log exists at docs/dev_logs/2026-04-15_track2_soak_launcher_watchdog.md
    - Dev log contains file list, commands, test counts, friction removal, remaining gaps
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Operator -> CLI | Operator provides CLI args; validated by argparse + settings validation |
| CLI -> subprocess | await_soak spawns crypto-pair-run as child process |
| Kill switch file -> launcher | File read to check truthy content before launch |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-qpv-01 | Tampering | kill_switch.txt | accept | File is operator-controlled; encoding is utf-8; only truthy values ("1","true","yes","on") trip it; empty/missing = clear |
| T-qpv-02 | Denial of Service | subprocess launch | accept | Child process inherits os.environ; no new env vars introduced; timeout controlled by --duration-seconds |
| T-qpv-03 | Information Disclosure | child stdout parsing | accept | _extract_cli_value only reads prefixed lines from own child process output; no secrets in output |
</threat_model>

<verification>
1. `python -m pytest tests/test_crypto_pair_await_soak.py -v --tb=short` -- all pass
2. `python -m pytest tests/test_crypto_pair_soak_workflow.py tests/test_crypto_pair_run.py -v --tb=short` -- no regressions
3. `python -m polytool --help` -- CLI loads, crypto-pair-await-soak listed
4. `python -m polytool crypto-pair-await-soak --help` -- new flags visible
</verification>

<success_criteria>
- Operator can run `python -m polytool crypto-pair-await-soak` with no extra flags
  and get a full 24h paper soak with auto-report, 30-min heartbeat, and coinbase feed
- Kill switch preflight blocks launch if file is tripped
- Post-run output includes verdict text and verdict.json path
- No strategy, risk control, or reporting logic changed
- All existing tests pass, 10+ new tests added
</success_criteria>

<output>
After completion, create `.planning/quick/260415-qpv-build-a-track-2-paper-soak-launcher-watc/260415-qpv-SUMMARY.md`
</output>
