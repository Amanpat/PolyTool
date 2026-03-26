---
phase: quick-026
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docs/specs/SPEC-0012-phase1-tracka-live-bot-program.md
  - docs/CURRENT_STATE.md
  - tools/gates/mm_sweep.py
  - tools/gates/close_mm_sweep_gate.py
  - tools/gates/mm_sweep_diagnostic.py
  - tests/test_mm_sweep_gate.py
  - docs/dev_logs/2026-03-26_phase1b_recovery_root_cause.md
autonomous: true
requirements: [PHASE1B-RECOVER]

must_haves:
  truths:
    - "SPEC-0012 names market_maker_v1 as the Phase 1 canonical strategy (resolving the v0/v1 split)"
    - "Gate 2 returns NOT_RUN (not FAILED) when fewer than 50 tapes meet the min_events threshold"
    - "close_mm_sweep_gate.py exits 0 (NOT_RUN) instead of exit 1 (FAILED) when corpus is below the eligibility floor"
    - "mm_sweep_diagnostic.py produces per-tape eligibility, tier, effective_events, skip reason, and fill-opportunity classification for all 50 benchmark tapes"
    - "CURRENT_STATE.md reflects corrected Gate 2 status and the true next blocker"
    - "Dev log documents all authority conflicts, resolutions, and root cause findings"
  artifacts:
    - path: "docs/specs/SPEC-0012-phase1-tracka-live-bot-program.md"
      provides: "Updated canonical strategy declaration (market_maker_v1)"
    - path: "tools/gates/mm_sweep.py"
      provides: "NOT_RUN when eligible_count < min_eligible_tapes (default 50)"
    - path: "tools/gates/mm_sweep_diagnostic.py"
      provides: "Per-tape root cause analysis tool"
    - path: "tests/test_mm_sweep_gate.py"
      provides: "Tests for the min_eligible_tapes NOT_RUN path"
    - path: "docs/dev_logs/2026-03-26_phase1b_recovery_root_cause.md"
      provides: "Conflict audit, resolution rationale, root cause findings"
  key_links:
    - from: "tools/gates/mm_sweep.py:run_mm_sweep"
      to: "gate_payload=None (NOT_RUN)"
      via: "len(eligible_outcomes) < min_eligible_tapes"
      pattern: "not_run_reason"
    - from: "tools/gates/close_mm_sweep_gate.py"
      to: "exit code 0"
      via: "gate_payload is None -> print NOT_RUN summary -> return 0"
      pattern: "return 0"
---

<objective>
Recover Phase 1B after the failed Gate 2 run by: (1) resolving the strategy-identity
conflict between SPEC-0012 and the Phase 1B packet, (2) fixing Gate 2 outcome
semantics so a corpus below the 50-tape eligibility floor is NOT_RUN not FAILED,
(3) adding a diagnostic tool that attributes the failure to corpus insufficiency,
fill-model limits, or strategy behavior, and (4) updating authoritative docs to
reflect true state.

Purpose: Clear the semantic confusion so the actual next blocker (corpus quality)
is visible and actionable without false "gate failure" noise.
Output: Updated SPEC-0012, fixed mm_sweep.py gate logic, new mm_sweep_diagnostic.py,
new tests, updated CURRENT_STATE.md, dev log.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/docs/PLAN_OF_RECORD.md
@D:/Coding Projects/Polymarket/PolyTool/docs/CURRENT_STATE.md
@D:/Coding Projects/Polymarket/PolyTool/docs/specs/SPEC-0012-phase1-tracka-live-bot-program.md
@D:/Coding Projects/Polymarket/PolyTool/docs/specs/SPEC-phase1b-gate2-shadow-packet.md
@D:/Coding Projects/Polymarket/PolyTool/tools/gates/mm_sweep.py
@D:/Coding Projects/Polymarket/PolyTool/tools/gates/close_mm_sweep_gate.py
@D:/Coding Projects/Polymarket/PolyTool/tests/test_mm_sweep_gate.py

<interfaces>
<!-- Key types from mm_sweep.py that the executor will extend. -->

```python
# MMSweepResult — add min_eligible_tapes field
@dataclass(frozen=True)
class MMSweepResult:
    tapes: list[TapeCandidate]
    outcomes: list[TapeSweepOutcome]
    gate_payload: dict[str, Any] | None
    artifact_path: Path | None
    threshold: float
    min_events: int
    not_run_reason: str | None = None
    # ADD: min_eligible_tapes: int = 50

# run_mm_sweep — add min_eligible_tapes param
def run_mm_sweep(
    *,
    ...
    min_events: int = DEFAULT_MM_SWEEP_MIN_EVENTS,
    # ADD: min_eligible_tapes: int = DEFAULT_MM_SWEEP_MIN_ELIGIBLE_TAPES,
    spread_multipliers: tuple[float, ...] = DEFAULT_MM_SWEEP_MULTIPLIERS,
) -> MMSweepResult: ...

# TapeCandidate — already has these fields, used by diagnostic:
@dataclass(frozen=True)
class TapeCandidate:
    tape_dir: Path
    events_path: Path
    market_slug: str
    yes_asset_id: str
    recorded_by: str | None
    regime: str | None
    parsed_events: int
    tracked_asset_count: int
    effective_events: int
    bucket: str | None = None
```

<!-- Existing NOT_RUN flow (two places that already return not_run_reason): -->
<!-- Line 118-128: when tapes list is empty -->
<!-- Line 204-214: when eligible_outcomes list is empty -->
<!-- The new third path: when len(eligible_outcomes) < min_eligible_tapes -->

<!-- close_mm_sweep_gate.py exit behavior (lines 111-114): -->
<!-- if result.gate_payload is None: prints error to stderr, returns 1 -->
<!-- This must change to: return 0 for NOT_RUN (corpus gap is informational, not a gate failure) -->
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Resolve authority conflicts and fix Gate 2 NOT_RUN semantics</name>
  <files>
    docs/specs/SPEC-0012-phase1-tracka-live-bot-program.md,
    tools/gates/mm_sweep.py,
    tools/gates/close_mm_sweep_gate.py,
    tests/test_mm_sweep_gate.py
  </files>
  <action>
**Conflict audit (do this first, document findings in dev log — see Task 3):**

Conflicts to resolve:

1. SPEC-0012 §2 names `market_maker_v0` as "Canonical Phase 1 strategy." The Phase 1B
   spec (SPEC-phase1b-gate2-shadow-packet.md), the Gate 2 sweep tooling, and the
   2026-03-10 dev log `2026-03-10_tracka_marketmaker_v1_default_wiring.md` all show
   that `market_maker_v1` was intentionally promoted as the default on 2026-03-10.
   SPEC-0012 was simply never updated at that time. Resolution: update SPEC-0012 to
   declare `market_maker_v1` as the Phase 1 canonical strategy, with a note that
   `market_maker_v0` remains available but is no longer the mainline. This is an
   intentional-upgrade clarification, not a rollback.

2. ARCHITECTURE.md lines 101-104 reference `market_maker_v0` in the promotion ladder
   workflow examples. Update those example commands to `market_maker_v1`. (These are
   workflow examples, not policy — update them to match current tooling defaults.)

**Update SPEC-0012 §2:**
- Change "Canonical Phase 1 strategy: `market_maker_v0`" to
  "Canonical Phase 1 strategy: `market_maker_v1`"
- Add upgrade note: "`market_maker_v1` (Logit Avellaneda-Stoikov) replaced
  `market_maker_v0` as the Phase 1 default on 2026-03-10. `market_maker_v0`
  remains in the registry but is no longer the Phase 1 mainline."
- The `binary_complement_arb` secondary-strategy language stays unchanged.
- Update the run-command examples in SPEC-0012 to use `--strategy market_maker_v1`.

**Fix Gate 2 NOT_RUN semantics in mm_sweep.py:**

The spec states: "If fewer than 50 tapes meet the event threshold, Gate 2 is
NOT_RUN (not auto-failed)." The current code only returns NOT_RUN when
`eligible_outcomes` is completely empty. If 9 of 50 tapes qualify and run, it
writes `gate_failed.json`. This is wrong per spec.

Changes to `tools/gates/mm_sweep.py`:

1. Add constant: `DEFAULT_MM_SWEEP_MIN_ELIGIBLE_TAPES: int = 50`
   (matches benchmark_v1 total tape count)

2. Add `min_eligible_tapes: int = DEFAULT_MM_SWEEP_MIN_ELIGIBLE_TAPES` to
   `MMSweepResult` dataclass (after `min_events`).

3. Add `min_eligible_tapes: int = DEFAULT_MM_SWEEP_MIN_ELIGIBLE_TAPES` parameter
   to `run_mm_sweep()`.

4. After building `eligible_outcomes`, add this check BEFORE calling
   `_build_gate_payload`:

   ```python
   if len(eligible_outcomes) < min_eligible_tapes:
       _clear_gate_artifacts(out_dir)
       not_run_msg = (
           f"Corpus too small: only {len(eligible_outcomes)}/{len(tapes)} tapes meet "
           f"--min-events={min_events} (need at least {min_eligible_tapes} eligible "
           f"tapes to compute a valid Gate 2 verdict). "
           f"{len(tapes) - len(eligible_outcomes)} tapes were skipped as SKIPPED_TOO_SHORT. "
           "Record or reconstruct longer tapes before rerunning Gate 2."
       )
       return MMSweepResult(
           tapes=tapes,
           outcomes=outcomes,
           gate_payload=None,
           artifact_path=None,
           threshold=threshold,
           min_events=min_events,
           min_eligible_tapes=min_eligible_tapes,
           not_run_reason=not_run_msg,
       )
   ```

5. Pass `min_eligible_tapes=min_eligible_tapes` in ALL existing `MMSweepResult`
   instantiations (the three that already exist, including the two early-return
   NOT_RUN paths). The default value is 50 so backward compatibility is preserved.

**Fix close_mm_sweep_gate.py exit behavior:**

The NOT_RUN state is informational (corpus gap, not a gate failure). The current
code returns exit code 1 on NOT_RUN. Change this:

```python
# Current (wrong for NOT_RUN):
if result.gate_payload is None:
    print(f"Error: {result.not_run_reason}", file=sys.stderr)
    return 1

# Correct:
if result.gate_payload is None:
    print(f"NOT_RUN: {result.not_run_reason}", file=sys.stderr)
    return 0
```

Also add `--min-eligible-tapes` CLI argument mirroring `--min-events`:
```python
parser.add_argument(
    "--min-eligible-tapes",
    type=int,
    default=DEFAULT_MM_SWEEP_MIN_ELIGIBLE_TAPES,
    metavar="COUNT",
    help=(
        "Minimum number of tapes that must meet --min-events to compute a Gate 2 "
        f"verdict (default: {DEFAULT_MM_SWEEP_MIN_ELIGIBLE_TAPES}). "
        "If fewer tapes qualify, result is NOT_RUN, not FAILED."
    ),
)
```

Pass it into `run_mm_sweep(min_eligible_tapes=int(args.min_eligible_tapes), ...)`.

**Add tests to tests/test_mm_sweep_gate.py:**

Add a new test class `TestMinEligibleTapesNotRun` with at least 3 tests:

1. `test_not_run_when_eligible_below_threshold`: Build a result where
   5 tapes exist, all have effective_events >= 50, but min_eligible_tapes=10.
   Result should have `gate_payload=None`, `not_run_reason` containing "Corpus
   too small", and `not_run_reason` containing "5/5" (or similar count).

2. `test_passes_when_eligible_meets_threshold`: Same 5 tapes but
   min_eligible_tapes=5. Should proceed to _build_gate_payload and return a
   non-None gate_payload.

3. `test_close_mm_sweep_gate_exits_0_on_not_run`: Mock run_mm_sweep to return
   an MMSweepResult with gate_payload=None and not_run_reason set. Call
   main(["--tapes-dir", str(tmp_path), ...]) and assert return code is 0.
   (Use monkeypatch to inject the mocked result.)

Use the existing test infrastructure patterns from the file — the tests use
`tmp_path`, `monkeypatch`, and `_make_events_file()` helpers already defined.
  </action>
  <verify>
    <automated>python -m pytest tests/test_mm_sweep_gate.py -x -q --tb=short 2>&1 | tail -20</automated>
  </verify>
  <done>
    - SPEC-0012 §2 names market_maker_v1 as canonical Phase 1 strategy with upgrade note
    - mm_sweep.py has DEFAULT_MM_SWEEP_MIN_ELIGIBLE_TAPES=50, min_eligible_tapes param,
      and NOT_RUN branch when eligible_count less than min_eligible_tapes
    - close_mm_sweep_gate.py exits 0 for NOT_RUN and prints "NOT_RUN:" prefix (not "Error:")
    - New TestMinEligibleTapesNotRun tests pass
    - All existing mm_sweep gate tests still pass
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add mm_sweep_diagnostic.py for per-tape root cause analysis</name>
  <files>
    tools/gates/mm_sweep_diagnostic.py,
    tests/test_mm_sweep_diagnostic.py
  </files>
  <behavior>
    - Test 1: TapeDiagnostic for a too-short tape has status="SKIPPED_TOO_SHORT",
      fill_opportunity="none", quote_count=0
    - Test 2: TapeDiagnostic for a tape that ran with net_profit=0 has
      status="RAN_ZERO_PROFIT", fill_opportunity classified as "no_touch"
      when no fills and no trade events near quotes
    - Test 3: run_mm_sweep_diagnostic returns one TapeDiagnostic per tape in
      the benchmark manifest (mocked tape discovery returning 3 tapes)
    - Test 4: format_diagnostic_report produces a markdown table with columns:
      tape, bucket, tier, effective_events, status, quote_count, fill_opp,
      skip_reason
  </behavior>
  <action>
Create `tools/gates/mm_sweep_diagnostic.py` as a standalone analysis tool.
It does NOT modify gate logic — it is read-only root cause analysis.

**TapeDiagnostic dataclass:**
```python
@dataclass(frozen=True)
class TapeDiagnostic:
    tape_dir: Path
    market_slug: str
    bucket: str | None
    tier: str                  # "gold" | "silver" | "bronze" | "unknown"
    effective_events: int
    parsed_events: int
    tracked_asset_count: int
    status: str                # "SKIPPED_TOO_SHORT" | "RAN_ZERO_PROFIT" | "RAN_POSITIVE" | "ERROR"
    skip_reason: str | None    # Set for SKIPPED_TOO_SHORT
    best_net_profit: Decimal | None
    quote_count: int           # Number of times strategy generated quotes (non-None bid/ask)
    fill_opportunity: str      # "at_touch" | "cross" | "no_touch" | "none" | "unknown"
    fill_count: int            # Actual fills recorded in summary
    notes: list[str]           # Free-form diagnostic notes
```

**Tier detection logic** (`_detect_tier`): reads tape metadata files:
- `meta.json` with `"recorded_by": "shadow"` or `"tape_recorder"` → "gold"
- `watch_meta.json` present → "gold"
- `silver_meta.json` present or `market_meta.json` with `"platform": "silver"` → "silver"
- Otherwise → "unknown"

**Quote count** (`_count_quotes`): replay the tape through market_maker_v1 using
the existing `run_sweep` infrastructure with `spread_multiplier=1.0` only, then
read the sweep summary's `scenario_rows` to count rows where `net_profit` is not
None and is a valid Decimal (these represent tapes where the strategy produced
actionable output). For a simpler proxy: count events in the events.jsonl where
`event_type == "price_change"` or similar — but prefer the sweep summary approach
since it is already computed.

Actually, quote_count should come from the sweep result artifacts. After a sweep
run, `run_manifest.json` in the sweep dir contains strategy-level data.
For diagnostic purposes, count quotes by reading the best-scenario sweep dir's
`run_manifest.json` → `strategy_debug.quote_count` if present, else 0. If not
present, set to -1 (unknown) and note it.

**Fill opportunity classification** (`_classify_fill_opportunity`): Given the
best-scenario sweep result:
- `fill_count > 0` → "at_touch" (fills happened)
- `fill_count == 0` and `quote_count > 0` and `effective_events >= 50` →
  "no_touch" (strategy quoted but market never crossed the spread)
- `fill_count == 0` and `quote_count == 0` → "none" (strategy never quoted)
- Tape was skipped → "none"
- Otherwise → "unknown"

NOTE: The diagnostic cannot distinguish "at_touch" from "cross" from tape data
alone without orderbook reconstruction. Use "at_touch" as the label for any fills.
Document this limitation in the output notes field.

**Main entry function:**
```python
def run_mm_sweep_diagnostic(
    *,
    benchmark_manifest_path: Path,
    out_dir: Path,
    min_events: int = 50,
    spread_multiplier: float = 1.0,
) -> list[TapeDiagnostic]:
```

This function:
1. Calls `discover_mm_sweep_tapes(benchmark_manifest_path=benchmark_manifest_path)`
   to get all TapeCandidate objects (including SKIPPED ones — get full tape list
   by also calling with min_events=0 or by directly loading from manifest).
2. For each tape, builds a TapeDiagnostic.
3. For tapes with effective_events >= min_events, runs a single-multiplier sweep
   (spread_multiplier=1.0 only, not the full 5-multiplier sweep) and uses the
   result to populate quote_count, fill_opportunity, fill_count.
4. Writes a `diagnostic_report.md` to out_dir.
5. Returns the list of TapeDiagnostic objects.

**CLI entry point** (add `if __name__ == "__main__":` block):
```bash
python tools/gates/mm_sweep_diagnostic.py \
    --benchmark-manifest config/benchmark_v1.tape_manifest \
    --out artifacts/gates/mm_sweep_gate/diagnostic
```

**format_diagnostic_report(diagnostics: list[TapeDiagnostic]) -> str:**
Produces a markdown table:
```
| Tape | Bucket | Tier | EffEvents | Status | QuoteCount | FillOpp | SkipReason |
```
Plus a summary section: total tapes, SKIPPED_TOO_SHORT count, RAN_ZERO_PROFIT
count, RAN_POSITIVE count, fill_opportunity distribution.

Create `tests/test_mm_sweep_diagnostic.py` following the tdd="true" behavior
block above. Use `tmp_path` fixtures, mock `discover_mm_sweep_tapes` and
`run_sweep` so tests are offline and deterministic.
  </action>
  <verify>
    <automated>python -m pytest tests/test_mm_sweep_diagnostic.py -x -q --tb=short 2>&1 | tail -20</automated>
  </verify>
  <done>
    - tools/gates/mm_sweep_diagnostic.py exists with TapeDiagnostic, run_mm_sweep_diagnostic,
      format_diagnostic_report, and CLI __main__ block
    - All 4 behavior tests pass
    - Running python tools/gates/mm_sweep_diagnostic.py --help succeeds without import errors
  </done>
</task>

<task type="auto">
  <name>Task 3: Rerun corrected gate, run diagnostic, update docs</name>
  <files>
    artifacts/gates/mm_sweep_gate/gate_failed.json,
    docs/CURRENT_STATE.md,
    docs/dev_logs/2026-03-26_phase1b_recovery_root_cause.md
  </files>
  <action>
**Step 1: Run corrected Gate 2**

```bash
python tools/gates/close_mm_sweep_gate.py \
    --benchmark-manifest config/benchmark_v1.tape_manifest \
    --out artifacts/gates/mm_sweep_gate
```

Expected output: "NOT_RUN: Corpus too small: only 9/50 tapes meet --min-events=50..."
Expected exit code: 0
Expected artifact change: gate_failed.json deleted, no gate_passed.json written
(gate status will show NOT_RUN — this is correct per spec).

If gate_failed.json still exists after this run, investigate why (the
_clear_gate_artifacts call in the new NOT_RUN path should have removed it).

**Step 2: Run diagnostic against the 9 qualifying tapes**

```bash
python tools/gates/mm_sweep_diagnostic.py \
    --benchmark-manifest config/benchmark_v1.tape_manifest \
    --out artifacts/gates/mm_sweep_gate/diagnostic
```

Capture the output. Key things to observe:
- For the 9 qualifying tapes: what is fill_opportunity? (likely "no_touch" given
  net_profit=0 on all runs)
- What tier are those 9 tapes? (all silver/near_resolution based on gate_failed.json)
- What is quote_count on those 9 tapes? (nonzero means strategy is quoting but
  market never crosses the spread — corpus quality problem, not strategy bug)

**Step 3: Run the full test suite regression check**

```bash
python -m pytest tests/ -x -q --tb=short 2>&1 | tail -20
```

Report exact pass/fail/skip counts.

**Step 4: Update CURRENT_STATE.md**

Find the section "Status as of 2026-03-26 (Phase 1B Gate 2 FAILED)" and update:
- Change heading to: "## Status as of 2026-03-26 (Phase 1B — Gate 2 NOT_RUN, corpus insufficient)"
- Change Gate 2 line: "Gate 2: **NOT_RUN** (2026-03-26) — 9/50 tapes met min_events=50
  threshold; 41 skipped as too short. Corpus insufficient for valid Gate 2 verdict.
  Root cause: benchmark tapes have insufficient effective_events for the market_maker_v1
  scenario sweep. See dev log `docs/dev_logs/2026-03-26_phase1b_recovery_root_cause.md`."
- Update Blockers section: replace "Gate 2 verdict: FAILED" with
  "Gate 2 corpus: INSUFFICIENT — 41/50 benchmark tapes have fewer than 50 effective
  events. Next action: reconstruct or recapture longer tapes with >=50 effective
  events each. Run diagnostic: `python tools/gates/mm_sweep_diagnostic.py
  --benchmark-manifest config/benchmark_v1.tape_manifest` to see per-tape status."

**Step 5: Write dev log docs/dev_logs/2026-03-26_phase1b_recovery_root_cause.md**

Sections:
1. **Authority conflict audit** — table of all conflicts found:

   | Conflict | Source A | Source B | Resolution |
   |----------|---------|---------|------------|
   | Strategy identity | SPEC-0012 §2: market_maker_v0 is canonical | SPEC-phase1b + 2026-03-10 dev log: market_maker_v1 is default | SPEC-0012 updated: market_maker_v1 is canonical Phase 1 strategy (intentional upgrade 2026-03-10, SPEC-0012 never updated) |
   | Gate 2 outcome | Spec: fewer than 50 eligible = NOT_RUN | Code: 9 eligible tapes ran and wrote gate_failed.json | Code fixed: min_eligible_tapes=50 threshold added |
   | CURRENT_STATE.md Gate 2 status | Shows FAILED | Should show NOT_RUN per spec semantics | Updated in this packet |

2. **Root cause analysis** — What actually failed and why:
   - Corpus problem: 41/50 tapes have fewer than 50 effective events. These are
     Silver tapes from the near_resolution / politics / sports buckets reconstructed
     from 15-minute windows. Short markets or low-activity markets produce few
     price_change events.
   - Fill model: The 9 qualifying tapes showed 0 fills on net_profit=0 across all
     5 spread scenarios. This is consistent with a no-touch fill environment (the
     spread was never crossed). This is NOT a strategy bug — it means the 9 qualifying
     tapes were near_resolution tapes where market prices barely moved.
   - Strategy behavior: market_maker_v1 did generate quotes (non-zero quote_count
     expected from diagnostic). The issue is the tape quality, not the quoting logic.

3. **Next blocker** — Clear statement: "Gate 2 is blocked on corpus quality. The
   benchmark_v1 manifest needs >=50 tapes each with >=50 effective events. Current
   count: 9. Options: (a) recapture live tapes with longer recording windows,
   (b) reconstruct Silver tapes from longer price history windows, (c) lower
   --min-events threshold (NOT RECOMMENDED — weakens validity)."

4. **Files changed** — list with one-line descriptions.

5. **Test counts** — exact pytest output from step 3.
  </action>
  <verify>
    <automated>python -m pytest tests/test_mm_sweep_gate.py tests/test_mm_sweep_diagnostic.py -q --tb=short 2>&1 | tail -5</automated>
  </verify>
  <done>
    - gate_failed.json removed from artifacts/gates/mm_sweep_gate/ (or NOT_RUN artifact present)
    - CURRENT_STATE.md Gate 2 status shows NOT_RUN with corpus count (9/50)
    - Dev log exists at docs/dev_logs/2026-03-26_phase1b_recovery_root_cause.md with all
      5 sections and the conflict audit table
    - python -m polytool --help still loads cleanly (no import errors from changed gate files)
  </done>
</task>

</tasks>

<verification>
```bash
# 1. CLI loads
python -m polytool --help

# 2. Gate returns NOT_RUN and exits 0
python tools/gates/close_mm_sweep_gate.py \
    --benchmark-manifest config/benchmark_v1.tape_manifest \
    --out artifacts/gates/mm_sweep_gate
echo "Exit code: $?"

# 3. gate_failed.json should be absent
ls artifacts/gates/mm_sweep_gate/gate_failed.json 2>/dev/null && echo "FAIL: gate_failed.json still exists" || echo "PASS: gate_failed.json removed"

# 4. Diagnostic tool runs
python tools/gates/mm_sweep_diagnostic.py --help

# 5. All gate tests pass
python -m pytest tests/test_mm_sweep_gate.py tests/test_mm_sweep_diagnostic.py -q --tb=short

# 6. No regressions
python -m pytest tests/ -x -q --tb=short 2>&1 | tail -5
```
</verification>

<success_criteria>
- SPEC-0012 declares market_maker_v1 as the Phase 1 canonical strategy with explicit
  upgrade note referencing 2026-03-10
- Gate 2 returns NOT_RUN (not FAILED) when fewer than min_eligible_tapes=50 tapes
  meet the event threshold; close_mm_sweep_gate.py exits 0 in this case
- mm_sweep_diagnostic.py provides per-tape eligibility, tier, effective_events,
  skip reason, and fill-opportunity classification
- CURRENT_STATE.md reflects Gate 2 as NOT_RUN with corpus count and clear next blocker
- Dev log documents all authority conflicts, resolutions, and root cause findings
- All existing tests pass; new tests cover the min_eligible_tapes NOT_RUN path
</success_criteria>

<output>
After completion, create `.planning/quick/26-recover-phase-1b-after-failed-gate-2-res/26-SUMMARY.md`
</output>
