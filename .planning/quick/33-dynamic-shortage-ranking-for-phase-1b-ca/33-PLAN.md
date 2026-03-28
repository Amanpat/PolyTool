---
phase: quick-033
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/polymarket/simtrader/candidate_discovery.py
  - tools/cli/simtrader.py
  - tests/test_simtrader_candidate_discovery.py
  - docs/dev_logs/2026-03-27_phase1b_dynamic_shortage_ranking.md
autonomous: true
requirements: []
must_haves:
  truths:
    - "quickrun --list-candidates reads current corpus shortage from tape directories automatically"
    - "shortage_source is printed so the operator knows whether live or fallback data was used"
    - "when no tapes exist (offline/CI), a documented fallback prevents hard failure"
    - "all existing tests pass after the change"
  artifacts:
    - path: "packages/polymarket/simtrader/candidate_discovery.py"
      provides: "load_live_shortage() function + updated CandidateDiscovery default"
      exports: ["load_live_shortage", "CandidateDiscovery", "DiscoveryResult", "infer_bucket", "score_for_capture"]
    - path: "tools/cli/simtrader.py"
      provides: "live shortage wired into --list-candidates; source label printed"
    - path: "tests/test_simtrader_candidate_discovery.py"
      provides: "tests: live state available, fallback path, shortage-change ranking"
    - path: "docs/dev_logs/2026-03-27_phase1b_dynamic_shortage_ranking.md"
      provides: "dev log with files changed, commands run, test results"
  key_links:
    - from: "tools/cli/simtrader.py"
      to: "packages/polymarket/simtrader/candidate_discovery.py"
      via: "load_live_shortage() called before CandidateDiscovery(picker, shortage=...)"
    - from: "packages/polymarket/simtrader/candidate_discovery.py"
      to: "tools/gates/capture_status.compute_status()"
      via: "import inside load_live_shortage() (guarded try/except)"
---

<objective>
Replace hardcoded Phase 1B shortage constants in candidate discovery with live corpus
state read from tape directories via capture_status.compute_status().

Purpose: After each tape capture batch the corpus shortage changes, but the hardcoded
dict in simtrader.py (and _DEFAULT_SHORTAGE in candidate_discovery.py) requires a manual
edit to stay accurate. CandidateDiscovery should reflect current truth automatically.

Output: load_live_shortage() in candidate_discovery.py, live wiring in simtrader.py,
fallback to _DEFAULT_SHORTAGE when no tape dirs exist, source label in CLI output.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/packages/polymarket/simtrader/candidate_discovery.py
@D:/Coding Projects/Polymarket/PolyTool/tools/cli/simtrader.py
@D:/Coding Projects/Polymarket/PolyTool/tools/gates/capture_status.py

<interfaces>
<!-- Key contracts the executor needs. -->

From tools/gates/capture_status.py:
```python
from tools.gates.corpus_audit import DEFAULT_TAPE_ROOTS  # list[str]

def compute_status(
    tape_roots: list[Path],
    *,
    min_events: int = DEFAULT_MIN_EVENTS,
) -> dict[str, Any]:
    """Returns: {total_have, total_quota, total_need, complete, buckets}
    where buckets = {bucket: {"quota": Q, "have": H, "need": N, "gold": G, "silver": S}}
    """
```

From packages/polymarket/simtrader/candidate_discovery.py:
```python
_DEFAULT_SHORTAGE: dict[str, int] = {
    "sports": 15, "politics": 9, "crypto": 10,
    "new_market": 5, "near_resolution": 1, "other": 0,
}

class CandidateDiscovery:
    def __init__(self, picker: Any, shortage: Optional[dict[str, int]] = None) -> None:
        self._shortage = dict(shortage) if shortage else dict(_DEFAULT_SHORTAGE)
```

From tools/cli/simtrader.py (lines 1613-1628):
```python
# Phase 1B campaign shortage defaults (update after each capture batch):
_DEFAULT_SHORTAGE = {
    "sports": 15, "politics": 9, "crypto": 10,
    "new_market": 5, "near_resolution": 1, "other": 0,
}
...
discovery = CandidateDiscovery(picker, shortage=_DEFAULT_SHORTAGE)
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add load_live_shortage() to candidate_discovery.py and wire CLI</name>
  <files>
    packages/polymarket/simtrader/candidate_discovery.py,
    tools/cli/simtrader.py
  </files>
  <action>
**In packages/polymarket/simtrader/candidate_discovery.py:**

Add a new exported function `load_live_shortage()` immediately after the `_DEFAULT_SHORTAGE`
block (around line 53). The function signature:

```python
def load_live_shortage(
    tape_roots: Optional[list[str]] = None,
) -> tuple[dict[str, int], str]:
    """Load current corpus shortage from tape directories.

    Returns (shortage_dict, source_label) where source_label is one of:
      "live (N tapes scanned)"  -- compute_status ran and found tapes
      "fallback (no tapes found)"  -- compute_status ran but found 0 tapes
      "fallback (import error)"  -- capture_status module unavailable
      "fallback (read error)"  -- unexpected exception during scan

    The shortage_dict always has entries for all 6 buckets including "other".
    Falls back to _DEFAULT_SHORTAGE on any failure.
    """
```

Implementation notes:
- Import `capture_status` inside the function body (guarded `try/except ImportError`) to
  avoid a hard dependency at module import time. Use:
  `from tools.gates.capture_status import compute_status, _REPO_ROOT` and
  `from tools.gates.corpus_audit import DEFAULT_TAPE_ROOTS`
- Build `tape_roots` Path list: if argument is None, use DEFAULT_TAPE_ROOTS resolved against
  _REPO_ROOT (same logic as capture_status.main()).
- Call `compute_status(tape_roots)` and extract `status["buckets"]` mapping.
- Build result dict: for each bucket in _DEFAULT_SHORTAGE.keys(), set value to
  `status["buckets"].get(bucket, {}).get("need", 0)`. Set "other" to 0 always (not in corpus).
- If total_have == 0 and total_need == 0: return fallback with label "fallback (no tapes found)".
- Wrap the entire compute_status call in `try/except Exception` to produce
  "fallback (read error: {exc})" label, returning _DEFAULT_SHORTAGE copy.

**In tools/cli/simtrader.py:**

Replace the hardcoded local `_DEFAULT_SHORTAGE` dict (lines 1614-1621) and the static
`CandidateDiscovery(picker, shortage=_DEFAULT_SHORTAGE)` call (line 1628) with:

```python
# Load live corpus shortage from tape directories (falls back gracefully)
from packages.polymarket.simtrader.candidate_discovery import (  # noqa: PLC0415
    CandidateDiscovery,
    load_live_shortage,
)
_live_shortage, _shortage_source = load_live_shortage()
```

Then pass `_live_shortage` to CandidateDiscovery:
```python
discovery = CandidateDiscovery(picker, shortage=_live_shortage)
```

After printing candidates, add one line showing the shortage source (before the
"Listed N candidates." line):
```python
print(f"[shortage] source : {_shortage_source}")
```

Note: The existing `from packages.polymarket.simtrader.candidate_discovery import CandidateDiscovery`
import at line 1623 should be removed (it is now handled above with load_live_shortage).

Also remove the now-redundant `_DEFAULT_SHORTAGE` comment block and the stale comment
"Phase 1B campaign shortage defaults (update after each capture batch):".

Do NOT change the module-level `_DEFAULT_SHORTAGE` in candidate_discovery.py — it remains
as the documented fallback that load_live_shortage() returns on failure.
  </action>
  <verify>
    <automated>python -m pytest tests/test_simtrader_candidate_discovery.py -q -x --tb=short 2>&1 | tail -5</automated>
  </verify>
  <done>
    - load_live_shortage() exists in candidate_discovery.py and is importable
    - simtrader.py --list-candidates block no longer contains a hardcoded shortage dict
    - quickrun --list-candidates output includes a "[shortage] source : ..." line
    - All existing candidate_discovery tests pass
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add targeted tests for live/fallback shortage paths</name>
  <files>tests/test_simtrader_candidate_discovery.py</files>
  <behavior>
    - Test 1 (live state): mock compute_status to return buckets with known need counts;
      assert load_live_shortage() returns matching dict and source label contains "live"
    - Test 2 (fallback — no tapes): mock compute_status to return total_have=0, total_need=0,
      complete=True (empty corpus); assert source label contains "no tapes found" and
      shortage dict equals _DEFAULT_SHORTAGE
    - Test 3 (fallback — import error): patch the import of capture_status inside
      load_live_shortage() to raise ImportError; assert source label contains "import error"
      and shortage dict equals _DEFAULT_SHORTAGE
    - Test 4 (fallback — read error): mock compute_status to raise RuntimeError;
      assert source label contains "read error" and shortage dict equals _DEFAULT_SHORTAGE
    - Test 5 (ranking changes with shortage): call score_for_capture with high shortage for
      bucket A and zero shortage for bucket B; assert bucket A scores higher than bucket B
      with identical depth/probe/spread inputs (validates shortage-driven ranking changes)
  </behavior>
  <action>
Append a new test class `TestLoadLiveShortage` to tests/test_simtrader_candidate_discovery.py
with 5 test methods covering the behaviors above. All tests must be offline (mock
compute_status or patch the import — no real file system scanning). Use
`unittest.mock.patch` and `MagicMock`.

For Test 3, patch the import using `unittest.mock.patch.dict(sys.modules, ...)` to
simulate ImportError for the capture_status module when load_live_shortage() tries to
import it.

For Test 5, use the existing `score_for_capture` directly (already tested in the file).
Create two mock BookValidation objects with identical valid/depth/bid/ask but different
bucket strings, pass shortage dicts with high vs zero need, and assert ordering.
  </action>
  <verify>
    <automated>python -m pytest tests/test_simtrader_candidate_discovery.py -q -x --tb=short -k "TestLoadLiveShortage" 2>&1 | tail -8</automated>
  </verify>
  <done>
    - 5 new tests in TestLoadLiveShortage all pass
    - Tests cover: live path, no-tapes fallback, import-error fallback, read-error fallback,
      shortage-driven ranking change
    - No network calls in any test
  </done>
</task>

<task type="auto">
  <name>Task 3: Full regression + dev log</name>
  <files>docs/dev_logs/2026-03-27_phase1b_dynamic_shortage_ranking.md</files>
  <action>
1. Run the full test suite: `python -m pytest tests/ -q -x --tb=short`
   Capture and record exact pass/fail counts.

2. Create docs/dev_logs/2026-03-27_phase1b_dynamic_shortage_ranking.md containing:

   ## Summary
   One-paragraph description of the change.

   ## Files Changed
   - packages/polymarket/simtrader/candidate_discovery.py — added load_live_shortage()
   - tools/cli/simtrader.py — replaced hardcoded shortage dict with load_live_shortage() call

   ## Previous Behavior
   Describe the two hardcoded shortage dicts and the manual-update requirement.

   ## New Live-Shortage Behavior
   Describe load_live_shortage(): reads tape dirs via capture_status.compute_status(),
   returns (dict, source_label), 4 source label cases, fallback guarantee.

   ## Fallback Behavior
   When it triggers (no tape dirs, import unavailable, read error).
   Default values used (copy of _DEFAULT_SHORTAGE).

   ## Commands Run
   Include the pytest invocations and outputs with exact pass counts.

   ## Example Output
   Show what quickrun --list-candidates output looks like with the new
   "[shortage] source : ..." line (can be fabricated for illustration).

   ## Test Results
   Exact counts: "N passed, 0 failed, M skipped"
  </action>
  <verify>
    <automated>python -m pytest tests/ -q --tb=short 2>&1 | tail -3</automated>
  </verify>
  <done>
    - All existing tests pass (no regressions)
    - Dev log exists at docs/dev_logs/2026-03-27_phase1b_dynamic_shortage_ranking.md
    - Dev log contains file change list, behavior description, test results, and example output
  </done>
</task>

</tasks>

<verification>
1. python -m pytest tests/test_simtrader_candidate_discovery.py -q --tb=short — all pass including 5 new TestLoadLiveShortage tests
2. python -m pytest tests/ -q -x --tb=short — no regressions
3. grep -n "_DEFAULT_SHORTAGE\s*=" tools/cli/simtrader.py — should return no match (hardcoded dict removed)
4. grep -n "load_live_shortage" packages/polymarket/simtrader/candidate_discovery.py — confirms function exists
5. grep -n "shortage_source\|_shortage_source\|\[shortage\]" tools/cli/simtrader.py — confirms source label in output
</verification>

<success_criteria>
- load_live_shortage() exported from candidate_discovery.py; reads live tape state; returns (dict, str)
- simtrader.py --list-candidates no longer contains any hardcoded shortage dict
- CLI output includes "[shortage] source : ..." line on every --list-candidates run
- 5 new offline tests covering live/fallback paths all pass
- Full test suite passes with no regressions
- Dev log created
</success_criteria>

<output>
After completion, create .planning/quick/33-dynamic-shortage-ranking-for-phase-1b-ca/33-SUMMARY.md
</output>
