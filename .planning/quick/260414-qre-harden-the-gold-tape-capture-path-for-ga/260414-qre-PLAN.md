---
phase: quick-260414-qre
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - tools/cli/simtrader.py
  - packages/polymarket/simtrader/tape_validator.py
  - tests/test_gold_capture_hardening.py
  - docs/dev_logs/2026-04-14_gold_capture_hardening.md
autonomous: true
requirements: [GATE2-GOLD-CAPTURE-HARDENING]
must_haves:
  truths:
    - "Shadow capture writes tapes to artifacts/tapes/shadow/ by default, visible to corpus_audit default roots"
    - "Immediately after shadow capture, operator sees PASS/BLOCKED/WARN verdict with specific reason"
    - "Price-only tapes (no L2 book events) are flagged BLOCKED before operator ever runs corpus_audit"
    - "Tapes with real L2 book events and sufficient effective_events show PASS"
    - "No benchmark_v1 manifests are modified"
  artifacts:
    - path: "packages/polymarket/simtrader/tape_validator.py"
      provides: "Post-capture tape validation logic"
      exports: ["validate_captured_tape", "TapeValidationResult"]
    - path: "tests/test_gold_capture_hardening.py"
      provides: "Deterministic tests for path fix and tape validation"
      min_lines: 80
  key_links:
    - from: "tools/cli/simtrader.py"
      to: "packages/polymarket/simtrader/tape_validator.py"
      via: "import and call after shadow run completes"
      pattern: "validate_captured_tape"
    - from: "tools/cli/simtrader.py"
      to: "artifacts/tapes/shadow/"
      via: "DEFAULT_SHADOW_TAPE_DIR constant replacing DEFAULT_ARTIFACTS_DIR / tapes"
      pattern: "artifacts/tapes/shadow"
---

<objective>
Harden the Gold tape capture path so that new shadow captures (1) land in the
canonical artifacts location visible to corpus_audit/capture_status by default,
(2) are immediately validated for real L2 fidelity, and (3) give the operator a
clear PASS/BLOCKED/WARN verdict at capture time instead of letting unusable
tapes accumulate silently.

Purpose: Eliminate the path drift and silent quality gap that caused 96 tapes
to be invisible to corpus audit (dev log 2026-03-28) and Silver tapes to fail
Gate 2 with zero fills (dev log 2026-04-14).

Output: Fixed shadow write path, tape_validator module, wired CLI output,
deterministic tests, dev log.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@docs/PLAN_OF_RECORD.md
@docs/CURRENT_STATE.md
@docs/specs/SPEC-0014-gate2-eligible-tape-acquisition.md
@docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md
@docs/dev_logs/2026-04-14_gate2_fill_diagnosis.md
@docs/dev_logs/2026-04-14_gate2_corpus_visibility_and_ranking.md
@docs/dev_logs/2026-03-28_gold_capture_campaign.md

<interfaces>
<!-- Key types and paths the executor needs -->

From tools/cli/simtrader.py (line 45):
```python
DEFAULT_ARTIFACTS_DIR = Path("artifacts/simtrader")
```
Shadow tape write path (line 2348-2349):
```python
if record_tape:
    tape_dir = DEFAULT_ARTIFACTS_DIR / "tapes" / run_id
```
This resolves to `artifacts/simtrader/tapes/<run_id>` -- NOT in corpus audit
default roots.

Shadow CLI output (line 2443-2444) ALREADY prints the wrong path:
```python
if tape_dir is not None:
    print(f"  Tape dir   : artifacts/tapes/shadow/{tape_dir.name}/")
```
The display says `artifacts/tapes/shadow/` but the actual write is to
`artifacts/simtrader/tapes/`. This is the path drift bug.

From tools/gates/corpus_audit.py (line 40-43):
```python
DEFAULT_TAPE_ROOTS: list[str] = [
    "artifacts/tapes/gold",
    "artifacts/tapes/silver",
    "artifacts/tapes",
]
```

From tools/gates/mm_sweep.py (line 778):
```python
def _count_effective_events(events_path: Path) -> tuple[int, int, int]:
    # returns (parsed_events, tracked_asset_count, effective_events)
```

From packages/polymarket/simtrader/sweeps/eligibility.py:
```python
def check_binary_arb_tape_eligibility(
    events_path: Path,
    strategy_config: dict[str, Any],
) -> EligibilityResult:
```

Existing test fixture pattern (tests/test_corpus_audit.py):
```python
def _make_tape_dir(tmp_path, *, slug, effective_events=60, bucket="sports",
                   tier="silver", yes_asset_id="1234567890") -> Path:
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix shadow write path and create tape_validator module</name>
  <files>
    tools/cli/simtrader.py
    packages/polymarket/simtrader/tape_validator.py
  </files>
  <action>
TWO changes in this task:

**A. Fix the shadow tape write path in tools/cli/simtrader.py**

Add a new constant near line 45:
```python
DEFAULT_SHADOW_TAPE_DIR = Path("artifacts/tapes/shadow")
```

In the `_shadow()` function (around line 2348), change:
```python
tape_dir = DEFAULT_ARTIFACTS_DIR / "tapes" / run_id
```
to:
```python
tape_dir = DEFAULT_SHADOW_TAPE_DIR / run_id
```

This makes the actual write path match what the CLI already prints AND places
tapes under `artifacts/tapes/` which is in corpus_audit's DEFAULT_TAPE_ROOTS.

Do NOT change `DEFAULT_ARTIFACTS_DIR` itself -- it is used by runs, sweeps,
shadow_runs, and other non-tape artifacts. Only the tape_dir assignment in the
shadow function changes.

Also verify: the `run_dir` (line 2343) stays at `DEFAULT_ARTIFACTS_DIR /
"shadow_runs" / run_id`. Only tape_dir moves.

**B. Create packages/polymarket/simtrader/tape_validator.py**

A focused module that validates a newly captured tape directory for Gate 2
structural fitness. It does NOT run arb eligibility checks (those require
strategy config). It checks the prerequisites that must be true for ANY
fill-based Gate 2 evaluation.

Create a dataclass `TapeValidationResult`:
```python
@dataclass
class TapeValidationResult:
    tape_dir: str
    verdict: str          # "PASS", "BLOCKED", "WARN"
    reason: str           # human-readable explanation
    events_total: int     # raw parsed event count
    effective_events: int # events // asset_count
    asset_count: int
    has_l2_book: bool     # at least one event_type == "book"
    has_price_change: bool  # at least one event_type == "price_change"
    has_watch_meta: bool
    has_meta_json: bool
    event_type_counts: dict  # {event_type: count}
```

Create function `validate_captured_tape(tape_dir: Path, min_effective_events: int = 50) -> TapeValidationResult`:

1. Check `events.jsonl` exists. If not: BLOCKED "no events.jsonl found".
2. Read events.jsonl line by line (same pattern as `_count_effective_events`).
   Count total events, track asset_ids, count by event_type.
3. Compute effective_events = parsed // max(1, len(asset_ids)).
4. Check for `meta.json` presence, `watch_meta.json` presence.
5. Determine verdict:
   - BLOCKED if no events.jsonl
   - BLOCKED if has_l2_book is False (reason: "price-only tape -- no L2 book
     events, fill engine will reject all orders with book_not_initialized")
   - BLOCKED if effective_events == 0 (reason: "empty tape -- no parseable events")
   - WARN if effective_events < min_effective_events (reason: "tape has only
     {N} effective events, need >= {min} for Gate 2 corpus admission")
   - WARN if has_watch_meta is False (reason: "missing watch_meta.json --
     corpus audit may not assign a bucket label")
   - PASS otherwise (reason: "tape has {N} effective events with L2 book data")
6. Priority: BLOCKED checks first (any one blocks), then WARN checks, then PASS.
   If multiple WARN conditions, combine reasons with "; ".
7. This function MUST NOT: modify any file, touch benchmark manifests, call
   network APIs, or import heavy dependencies. Keep it lightweight -- it runs
   inline after every shadow capture.

Do NOT import or depend on `check_binary_arb_tape_eligibility` (that requires
strategy config and is a heavier check). This validator is a fast structural
pre-check.
  </action>
  <verify>
    <automated>rtk python -c "from packages.polymarket.simtrader.tape_validator import validate_captured_tape, TapeValidationResult; print('import ok')"</automated>
  </verify>
  <done>
    - DEFAULT_SHADOW_TAPE_DIR exists and points to artifacts/tapes/shadow
    - Shadow tape_dir assignment uses DEFAULT_SHADOW_TAPE_DIR
    - tape_validator.py exports validate_captured_tape and TapeValidationResult
    - validate_captured_tape returns BLOCKED for missing events.jsonl
    - validate_captured_tape returns BLOCKED for price-only (no book events)
    - validate_captured_tape returns PASS for tapes with L2 book data and enough events
    - validate_captured_tape returns WARN for low event count or missing watch_meta
  </done>
</task>

<task type="auto">
  <name>Task 2: Wire validator into shadow CLI output and write tests</name>
  <files>
    tools/cli/simtrader.py
    tests/test_gold_capture_hardening.py
    docs/dev_logs/2026-04-14_gold_capture_hardening.md
  </files>
  <action>
**A. Wire validator into shadow CLI (tools/cli/simtrader.py)**

In the `_shadow()` function, after the shadow run completes and the
"Shadow run complete" output block (around line 2437-2464), add a tape
validation step when `tape_dir is not None`:

```python
if tape_dir is not None and tape_dir.exists():
    from packages.polymarket.simtrader.tape_validator import validate_captured_tape
    vr = validate_captured_tape(tape_dir, min_effective_events=50)
    # Print a clear verdict block
    print()
    print("--- Tape Quality Check ---")
    if vr.verdict == "PASS":
        print(f"  Result     : PASS")
        print(f"  {vr.reason}")
    elif vr.verdict == "WARN":
        print(f"  Result     : WARN")
        print(f"  {vr.reason}")
    elif vr.verdict == "BLOCKED":
        print(f"  Result     : BLOCKED")
        print(f"  {vr.reason}")
    print(f"  L2 book    : {'yes' if vr.has_l2_book else 'NO'}")
    print(f"  Events     : {vr.events_total} raw, {vr.effective_events} effective ({vr.asset_count} assets)")
    if vr.event_type_counts:
        top_types = sorted(vr.event_type_counts.items(), key=lambda x: -x[1])[:5]
        print(f"  Event types: {', '.join(f'{k}={v}' for k, v in top_types)}")
    print("--------------------------")
```

This prints immediately after every shadow capture, giving the operator
instant feedback. The operator never has to wait for corpus_audit to learn
the tape is unusable.

**B. Write deterministic tests (tests/test_gold_capture_hardening.py)**

Create a test file with the following test classes and methods. Use `tmp_path`
pytest fixture throughout. Follow the fixture pattern from
`tests/test_corpus_audit.py` (create tape dirs with events.jsonl and metadata).

**TestCanonicalShadowPath** (2 tests):
- `test_shadow_tape_dir_uses_canonical_path`: Import `DEFAULT_SHADOW_TAPE_DIR`
  from `tools.cli.simtrader`. Assert it equals `Path("artifacts/tapes/shadow")`.
  This catches any regression that moves the path back to `artifacts/simtrader/tapes/`.
- `test_shadow_tape_dir_under_corpus_audit_roots`: Import `DEFAULT_TAPE_ROOTS`
  from `tools.gates.corpus_audit`. Assert that `str(DEFAULT_SHADOW_TAPE_DIR)`
  starts with at least one of the roots (specifically, `artifacts/tapes` is a
  root and `artifacts/tapes/shadow` is under it). This ensures tapes written to
  the shadow dir are discoverable by default corpus audit scan.

**TestTapeValidatorBlocked** (3 tests):
- `test_blocked_no_events_file`: Create a tape dir with no events.jsonl.
  validate_captured_tape returns verdict="BLOCKED", "no events.jsonl" in reason.
- `test_blocked_price_only_tape`: Create events.jsonl with 60 lines of
  `{"event_type": "price_2min_guide", "asset_id": "AAA", "seq": i}`. Validator
  returns verdict="BLOCKED", has_l2_book=False, "price-only" in reason.
- `test_blocked_empty_events_file`: Create an empty events.jsonl (0 bytes).
  Validator returns verdict="BLOCKED".

**TestTapeValidatorPass** (2 tests):
- `test_pass_gold_tape_with_l2`: Create events.jsonl with 60 events: first
  event is `{"event_type": "book", "asset_id": "AAA", "bids": [...], "asks": [...]}`,
  remaining 59 are `{"event_type": "price_change", "asset_id": "AAA", ...}`.
  Also create meta.json and watch_meta.json. Validator returns verdict="PASS",
  has_l2_book=True, effective_events=60.
- `test_pass_binary_tape_effective_events`: Create 120 events alternating
  between asset_id "AAA" and "BBB", all with event_type "price_change" plus
  one "book" event per asset. effective_events should be ~60 (120 // 2).
  Verdict should be PASS (>= 50 effective).

**TestTapeValidatorWarn** (2 tests):
- `test_warn_low_event_count`: Create events.jsonl with 30 events including
  one book event. Validator returns verdict="WARN", "need >= 50" in reason.
- `test_warn_missing_watch_meta`: Create events.jsonl with 60 events including
  book events, and meta.json, but NO watch_meta.json. Validator returns
  verdict="WARN", "missing watch_meta.json" in reason.

**TestOperatorOutput** (1 test):
- `test_verdict_block_contains_actionable_message`: For a BLOCKED result,
  assert that reason contains "book_not_initialized" or "price-only" or
  "no events.jsonl" -- i.e., the operator can grep the output for the
  failure mode without reading code.

All tests must be offline, deterministic, and use tmp_path.

**C. Write dev log (docs/dev_logs/2026-04-14_gold_capture_hardening.md)**

Standard dev log format:
- Summary: what changed and why
- Files changed table
- Root cause reference (link to fill diagnosis dev log)
- Test results (exact command and counts)
- What was NOT changed (scope discipline section)
  </action>
  <verify>
    <automated>rtk python -m pytest tests/test_gold_capture_hardening.py -v --tb=short</automated>
  </verify>
  <done>
    - All 10 tests in test_gold_capture_hardening.py pass
    - Shadow CLI prints "--- Tape Quality Check ---" block after capture
    - BLOCKED verdict printed for price-only tapes
    - PASS verdict printed for Gold tapes with L2 data
    - Dev log exists at docs/dev_logs/2026-04-14_gold_capture_hardening.md
    - Existing test suite still passes (no regressions)
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Tape filesystem -> validator | Untrusted tape content read from disk |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-qre-01 | T (Tampering) | tape_validator.py | accept | Validator reads tape files as-is. Tampering with local tapes is an operator-level action, not a threat in this context. |
| T-qre-02 | I (Info Disclosure) | simtrader.py | accept | Tape paths printed to stdout contain no secrets -- only artifact directory names and event counts. |
| T-qre-03 | D (Denial of Service) | tape_validator.py | mitigate | Validator reads events.jsonl line-by-line (streaming), never loads full file into memory. Handles malformed JSON lines with try/except continue. |
</threat_model>

<verification>
1. `python -m pytest tests/test_gold_capture_hardening.py -v` -- all 10 tests pass
2. `python -m pytest tests/ -x -q --tb=short` -- no regressions in full suite
3. `python -c "from tools.cli.simtrader import DEFAULT_SHADOW_TAPE_DIR; print(DEFAULT_SHADOW_TAPE_DIR)"` prints `artifacts/tapes/shadow`
4. `python -c "from packages.polymarket.simtrader.tape_validator import validate_captured_tape; print('ok')"` succeeds
5. Confirm no modifications to `config/benchmark_v1.*` files
</verification>

<success_criteria>
- Shadow capture tapes land at `artifacts/tapes/shadow/<run_id>/` by default
- This path is within corpus_audit DEFAULT_TAPE_ROOTS scan
- Post-capture output includes PASS/BLOCKED/WARN verdict with specific reason
- Price-only tapes (Silver-style) are flagged BLOCKED with "no L2 book" reason
- Gold tapes with book events and >= 50 effective events show PASS
- 10 deterministic tests cover path, BLOCKED, PASS, WARN, and output cases
- No benchmark_v1 manifests touched
- Existing tests pass without regression
</success_criteria>

<output>
After completion, create `.planning/quick/260414-qre-harden-the-gold-tape-capture-path-for-ga/260414-qre-SUMMARY.md`
</output>
