---
phase: quick-260410-izh
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - tools/cli/tape_manifest.py
  - tools/cli/scan_gate2_candidates.py
  - tests/test_gate2_corpus_visibility.py
  - docs/dev_logs/2026-04-10_gate2_corpus_visibility_and_ranking.md
autonomous: true
requirements: []

must_haves:
  truths:
    - "tape-manifest table shows per-tape event density (events_scanned, ticks_with_both_bbo) so the operator sees HOW thin each tape is"
    - "tape-manifest table shows a confidence class per tape (GOLD/SILVER/BRONZE/UNKNOWN) derived from recorded_by + events density so the operator knows tape fidelity at a glance"
    - "tape-manifest table shows the ineligibility breakdown status code (NO_DEPTH_NO_EDGE, DEPTH_ONLY, EDGE_ONLY, NO_OVERLAP, NO_EVENTS, NO_ASSETS) rather than a truncated reason string"
    - "tape-manifest JSON evidence block includes max_depth_yes, max_depth_no, min_sum_ask, and best_edge_gap proxy fields for every tape that has BBO data"
    - "scan-gate2-candidates tape mode includes per-tape event density and confidence class in output"
    - "All new diagnostic logic has deterministic tests that run offline"
  artifacts:
    - path: "tools/cli/tape_manifest.py"
      provides: "Enhanced TapeRecord with diagnostic fields and improved table output"
    - path: "tools/cli/scan_gate2_candidates.py"
      provides: "Enhanced tape-mode output with event density and confidence class"
    - path: "tests/test_gate2_corpus_visibility.py"
      provides: "Deterministic tests for new diagnostic classification logic"
    - path: "docs/dev_logs/2026-04-10_gate2_corpus_visibility_and_ranking.md"
      provides: "Dev log documenting changes and rationale"
  key_links:
    - from: "tools/cli/tape_manifest.py"
      to: "packages/polymarket/simtrader/sweeps/eligibility.py"
      via: "check_binary_arb_tape_eligibility returns EligibilityResult.stats dict"
      pattern: "result\\.stats"
    - from: "tools/cli/tape_manifest.py"
      to: "packages/polymarket/market_selection/regime_policy.py"
      via: "derive_tape_regime for regime integrity"
      pattern: "derive_tape_regime"
    - from: "tests/test_gate2_corpus_visibility.py"
      to: "tools/cli/tape_manifest.py"
      via: "imports classify_tape_confidence, classify_reject_code, enrich_tape_diagnostics"
      pattern: "from tools\\.cli\\.tape_manifest import"
---

<objective>
Improve Gate 2 corpus visibility so the operator can immediately understand WHY each tape
is or is not actionable, HOW close near-miss tapes are to eligibility, and WHICH capture
strategies would yield the highest-value next tapes.

Currently the tape-manifest table shows: Slug | Regime | Status | ExecTicks | Detail.
The "Detail" column shows a truncated reject_reason string for ineligible tapes and the
tape_dir path for eligible ones. The operator cannot tell from this output whether a tape
failed because of thin Silver reconstruction (30 events, no BBO), insufficient depth on
one leg, or depth+edge that never overlap. The evidence dict in the JSON manifest has
this data, but the table and JSON lack derived diagnostic fields that turn raw stats into
actionable classifications.

Purpose: Enable the operator to triage Gate 2 blockers without manually inspecting
per-tape JSON evidence blocks. Surface event density, confidence class, structured
reject codes, and fill-opportunity proxies in both CLI table output and manifest JSON.

Output:
  - Enhanced `print_manifest_table()` with diagnostic columns
  - New helper functions: `classify_tape_confidence()`, `classify_reject_code()`, `enrich_tape_diagnostics()`
  - Enhanced `TapeRecord` with optional diagnostic fields
  - Enhanced `scan_gate2_candidates.py` tape-mode output
  - Deterministic test file
  - Dev log
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@tools/cli/tape_manifest.py
@tools/cli/scan_gate2_candidates.py
@packages/polymarket/simtrader/sweeps/eligibility.py
@tests/test_gate2_eligible_tape_acquisition.py
@tests/test_gate2_candidate_ranking.py
@docs/specs/SPEC-0014-gate2-eligible-tape-acquisition.md
@docs/specs/SPEC-0017-phase1-gate2-candidate-ranking.md

<interfaces>
<!-- Key types and contracts the executor needs. Extracted from codebase. -->

From tools/cli/tape_manifest.py:
```python
@dataclass
class TapeRecord:
    tape_dir: str
    slug: str
    regime: str
    recorded_by: str             # watch-arb-candidates | prepare-gate2 | simtrader-* | unknown
    eligible: bool
    executable_ticks: int
    reject_reason: str
    evidence: dict[str, Any] = field(default_factory=dict)
    derived_regime: str = ""
    operator_regime: str = ""
    final_regime: str = ""
    regime_source: str = ""
    regime_mismatch: bool = False

@dataclass
class CorpusSummary:
    total_tapes: int
    eligible_count: int
    ineligible_count: int
    by_regime: dict[str, dict[str, int]]
    mixed_regime_eligible: bool
    gate2_eligible_tapes: list[str]
    generated_at: str
    corpus_note: str = ""
    regime_coverage: dict = field(default_factory=dict)
```

From packages/polymarket/simtrader/sweeps/eligibility.py:
```python
@dataclass
class EligibilityResult:
    eligible: bool
    reason: str = ""
    stats: dict[str, Any] = field(default_factory=dict)
    # stats keys: events_scanned, ticks_with_both_bbo, ticks_with_depth_ok,
    #   ticks_with_edge_ok, ticks_with_depth_and_edge,
    #   min_yes_ask_size_seen, min_no_ask_size_seen, min_sum_ask_seen,
    #   required_depth, required_edge_threshold
```

From tools/cli/scan_gate2_candidates.py:
```python
@dataclass
class CandidateResult:
    slug: str
    total_ticks: int
    depth_ok_ticks: int
    edge_ok_ticks: int
    executable_ticks: int
    best_edge: float
    max_depth_yes: float
    max_depth_no: float
    source: str = "live"
    market_meta: Optional[dict] = field(default=None)
    ranking_orderbook: Optional[dict] = field(default=None)
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add diagnostic classification helpers and enrich tape-manifest output</name>
  <files>tools/cli/tape_manifest.py, tests/test_gate2_corpus_visibility.py</files>
  <behavior>
    - classify_tape_confidence("watch-arb-candidates", events_scanned=500, ticks_with_both_bbo=200) => "GOLD"
    - classify_tape_confidence("simtrader-shadow", events_scanned=500, ticks_with_both_bbo=200) => "GOLD"
    - classify_tape_confidence("simtrader-quickrun", events_scanned=80, ticks_with_both_bbo=40) => "SILVER"
    - classify_tape_confidence("prepare-gate2", events_scanned=30, ticks_with_both_bbo=10) => "SILVER"
    - classify_tape_confidence("unknown", events_scanned=0, ticks_with_both_bbo=0) => "UNKNOWN"
    - classify_tape_confidence("watch-arb-candidates", events_scanned=15, ticks_with_both_bbo=5) => "BRONZE" (Gold source but too few events)
    - classify_reject_code(evidence={"ticks_with_depth_ok": 0, "ticks_with_edge_ok": 0, ...}) => "NO_DEPTH_NO_EDGE"
    - classify_reject_code(evidence={"ticks_with_depth_ok": 5, "ticks_with_edge_ok": 0, ...}) => "DEPTH_ONLY"
    - classify_reject_code(evidence={"ticks_with_depth_ok": 0, "ticks_with_edge_ok": 3, ...}) => "EDGE_ONLY"
    - classify_reject_code(evidence={"ticks_with_depth_ok": 4, "ticks_with_edge_ok": 2, "ticks_with_depth_and_edge": 0}) => "NO_OVERLAP"
    - classify_reject_code(evidence={}) on tape with reject_reason containing "no events" => "NO_EVENTS"
    - classify_reject_code(evidence={}) on tape with reject_reason containing "asset IDs" => "NO_ASSETS"
    - enrich_tape_diagnostics(TapeRecord) => adds confidence_class, reject_code, events_scanned, ticks_with_bbo, best_edge_gap, max_depth_yes, max_depth_no to TapeRecord.diagnostics dict
    - print_manifest_table outputs columns: Slug | Regime | Conf | Status | Code | Events | BBO | ExecTicks | BestEdge | MaxDepth | Detail
    - Existing tests in test_gate2_eligible_tape_acquisition.py still pass unchanged
  </behavior>
  <action>
1. Create `tests/test_gate2_corpus_visibility.py` with tests for the three new functions
   FIRST (RED phase). Tests import from `tools.cli.tape_manifest`. Each test constructs
   a TapeRecord or evidence dict directly -- no file I/O, no network.

2. Add three new functions to `tools/cli/tape_manifest.py`:

   a) `classify_tape_confidence(recorded_by: str, events_scanned: int, ticks_with_both_bbo: int) -> str`:
      - "GOLD": recorded_by in ("watch-arb-candidates", "simtrader-shadow") AND events_scanned >= 50 AND ticks_with_both_bbo >= 20
      - "SILVER": events_scanned >= 50 OR (recorded_by in ("prepare-gate2", "simtrader-quickrun") AND events_scanned >= 20)
      - "BRONZE": events_scanned > 0 AND ticks_with_both_bbo > 0
      - "UNKNOWN": otherwise (no events data, or events_scanned == 0)

   b) `classify_reject_code(evidence: dict, reject_reason: str = "") -> str`:
      - If evidence is empty or has no scan stats: check reject_reason for known substrings
        ("no events" => "NO_EVENTS", "asset IDs" => "NO_ASSETS", else "UNKNOWN")
      - If ticks_with_depth_and_edge > 0: "ELIGIBLE" (should not happen for rejected tapes, but defensive)
      - If ticks_with_depth_ok > 0 AND ticks_with_edge_ok > 0: "NO_OVERLAP"
      - If ticks_with_depth_ok > 0 AND ticks_with_edge_ok == 0: "DEPTH_ONLY"
      - If ticks_with_depth_ok == 0 AND ticks_with_edge_ok > 0: "EDGE_ONLY"
      - If ticks_with_depth_ok == 0 AND ticks_with_edge_ok == 0: "NO_DEPTH_NO_EDGE"

   c) `enrich_tape_diagnostics(record: TapeRecord) -> dict`:
      Returns a diagnostics dict with:
      - confidence_class: from classify_tape_confidence
      - reject_code: from classify_reject_code (or "ELIGIBLE" for eligible tapes)
      - events_scanned: from evidence.get("events_scanned", 0)
      - ticks_with_bbo: from evidence.get("ticks_with_both_bbo", 0)
      - best_edge_gap: compute as `float(evidence["required_edge_threshold"]) - float(evidence["min_sum_ask_seen"])` when both exist and min_sum_ask_seen != "none", else None
      - max_depth_yes: from evidence.get("min_yes_ask_size_seen") parsed to float (this is actually peak depth seen, rename in display)
      - max_depth_no: from evidence.get("min_no_ask_size_seen") parsed to float

3. Add a `diagnostics: dict` optional field to TapeRecord dataclass (default_factory=dict).

4. Update `scan_one_tape()`: after building the TapeRecord, call `enrich_tape_diagnostics()`
   and set `record.diagnostics = enrich_tape_diagnostics(record)`.

5. Update `print_manifest_table()` to show enhanced columns:
   ```
   Slug | Regime | Conf | Status | Code | Events | BBO | ExecTicks | BestEdge | MaxDepth | Detail
   ```
   - Conf: confidence_class (4 chars: GOLD/SILV/BRNZ/UNKN)
   - Code: reject_code (max 18 chars)
   - Events: events_scanned (int)
   - BBO: ticks_with_bbo (int)
   - BestEdge: best_edge_gap formatted as signed float or "N/A"
   - MaxDepth: "YES/NO" format showing peak ask sizes
   - Detail: For ineligible, show truncated reject_reason. For eligible, show tape_dir.
   Keep the separator line and footer summary unchanged in structure.

6. Update `manifest_to_dict()`: add the diagnostics dict to each tape entry in the
   JSON output (under key "diagnostics").

7. Run tests (GREEN phase). Ensure all existing tests in test_gate2_eligible_tape_acquisition.py
   still pass. The new diagnostics field is optional with default_factory=dict, so existing
   TapeRecord constructions in tests are unaffected.

IMPORTANT: Do NOT modify `eligibility.py` or any file under `packages/`. All changes are
in `tools/cli/tape_manifest.py` (CLI output layer) and the new test file. The eligibility
stats dict keys (`events_scanned`, `ticks_with_both_bbo`, `ticks_with_depth_ok`,
`ticks_with_edge_ok`, `ticks_with_depth_and_edge`, `min_sum_ask_seen`,
`min_yes_ask_size_seen`, `min_no_ask_size_seen`, `required_edge_threshold`,
`required_depth`) are already populated by `check_binary_arb_tape_eligibility` -- the new
code just reads and classifies them.
  </action>
  <verify>
    <automated>python -m pytest tests/test_gate2_corpus_visibility.py tests/test_gate2_eligible_tape_acquisition.py -x -q --tb=short</automated>
  </verify>
  <done>
    - classify_tape_confidence returns correct class for all source/density combinations
    - classify_reject_code returns correct structured code for all failure modes
    - enrich_tape_diagnostics populates the full diagnostics dict from evidence stats
    - print_manifest_table renders the enhanced column layout
    - manifest_to_dict includes diagnostics in JSON output
    - All existing tape_manifest tests still pass
    - New test file has at least 12 test cases covering all classification branches
  </done>
</task>

<task type="auto">
  <name>Task 2: Enhance scan-gate2-candidates tape-mode output with density and confidence</name>
  <files>tools/cli/scan_gate2_candidates.py, tests/test_gate2_corpus_visibility.py</files>
  <action>
1. In `tools/cli/scan_gate2_candidates.py`, enhance the `CandidateResult` dataclass:
   - Add optional field `events_scanned: int = 0`
   - Add optional field `confidence_class: str = ""`
   - Add optional field `recorded_by: str = ""`

2. In `scan_tapes()` (around line 350-476), after the replay loop completes for each tape:
   - Count total events (the `events` list length is already available after loading)
   - Read `recorded_by` using the same logic as tape_manifest (check for watch_meta.json,
     prep_meta.json, meta.json) -- import `_read_recorded_by` from `tools.cli.tape_manifest`
   - Import `classify_tape_confidence` from `tools.cli.tape_manifest`
   - Compute `confidence_class = classify_tape_confidence(recorded_by, len(events), total_ticks)`
   - Set these fields on the CandidateResult before appending

3. Update `print_table()` to add Events and Conf columns between Market and Exec:
   ```
   Market | Events | Conf | Exec | Edge | Depth | BestEdge | MaxDepth YES/NO
   ```
   - Events column: `events_scanned` (6 chars wide)
   - Conf column: confidence_class abbreviated to 4 chars (GOLD/SILV/BRNZ/UNKN), 4 chars wide

4. Update `print_ranked_table()` similarly: add Events and Conf columns after Market:
   ```
   Market | Events | Conf | Status | Score | Exec | BestEdge | MaxDepth YES/NO | New? | Age | RegSrc | Regime
   ```

5. Add 2-3 tests to `tests/test_gate2_corpus_visibility.py` that verify:
   - CandidateResult can be constructed with the new optional fields
   - print_table output (capture stdout) includes "Events" and "Conf" in the header
   - print_ranked_table output includes "Events" and "Conf" in the header

IMPORTANT: Only modify output formatting and the CandidateResult dataclass. Do NOT change
the scan_live_markets() function signature or its return behavior. The live mode will show
0/empty for events_scanned and confidence_class since live snapshots have no tape-level
event density -- this is correct and expected.
  </action>
  <verify>
    <automated>python -m pytest tests/test_gate2_corpus_visibility.py tests/test_gate2_candidate_ranking.py -x -q --tb=short</automated>
  </verify>
  <done>
    - CandidateResult has events_scanned, confidence_class, recorded_by fields
    - scan_tapes populates event count and confidence class per tape
    - print_table includes Events and Conf columns in tape mode
    - print_ranked_table includes Events and Conf columns
    - All existing candidate ranking tests still pass
    - New tests verify column presence in output headers
  </done>
</task>

<task type="auto">
  <name>Task 3: Write dev log and run full regression</name>
  <files>docs/dev_logs/2026-04-10_gate2_corpus_visibility_and_ranking.md</files>
  <action>
1. Create `docs/dev_logs/2026-04-10_gate2_corpus_visibility_and_ranking.md` with:
   - **Objective**: Improve Gate 2 actionable-corpus visibility and operator diagnostics
   - **Problem**: tape-manifest and scan-gate2-candidates output does not surface enough
     diagnostic detail about WHY tapes fail. The operator must manually inspect per-tape
     JSON evidence to understand whether a tape failed from thin Silver reconstruction
     (30 events, no BBO), insufficient depth on one leg, or depth+edge that never overlap.
     Gate 2 FAILED at 7/50 (14%) on 2026-03-29; 41/50 tapes skipped for <50 events, 9
     qualifying tapes all had 0 fills.
   - **Changes made**:
     - Added `classify_tape_confidence()` -- maps recorded_by source + event density to
       GOLD/SILVER/BRONZE/UNKNOWN tiers
     - Added `classify_reject_code()` -- maps eligibility evidence stats to structured
       status codes: NO_DEPTH_NO_EDGE, DEPTH_ONLY, EDGE_ONLY, NO_OVERLAP, NO_EVENTS, NO_ASSETS
     - Added `enrich_tape_diagnostics()` -- computes diagnostics dict with confidence class,
       reject code, event density, BBO ticks, edge gap proxy, and depth proxies
     - Enhanced `print_manifest_table()` -- now shows Conf, Code, Events, BBO, BestEdge, MaxDepth columns
     - Enhanced `manifest_to_dict()` -- includes diagnostics in JSON output per tape
     - Enhanced `CandidateResult` in scan_gate2_candidates.py with events_scanned,
       confidence_class, recorded_by fields
     - Enhanced `print_table()` and `print_ranked_table()` with Events and Conf columns
   - **Files touched**: list all modified files
   - **Tests**: list test file, count of new tests, note that existing tests unaffected
   - **What this enables**: Operator can now see at a glance which tapes are thin Silver
     reconstructions vs Gold live recordings, exactly why each tape fails eligibility, and
     how close near-miss tapes are to the depth/edge thresholds. This directly supports
     the Gate 2 corpus assembly workflow by making the "next best tape to capture" decision
     data-driven rather than guess-work.

2. Run full regression suite:
   ```
   python -m polytool --help
   python -m pytest tests/ -x -q --tb=short
   ```
   Record exact pass/fail counts in the dev log.
  </action>
  <verify>
    <automated>python -m pytest tests/ -x -q --tb=short</automated>
  </verify>
  <done>
    - Dev log exists at docs/dev_logs/2026-04-10_gate2_corpus_visibility_and_ranking.md
    - Dev log documents problem, changes, files touched, test results
    - Full regression suite passes with zero failures
    - python -m polytool --help still loads without import errors
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

No new trust boundaries introduced. All changes are in CLI output formatting and
classification logic operating on already-validated data from the eligibility scanner.

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-izh-01 | I (Info Disclosure) | tape_manifest diagnostic output | accept | Diagnostics expose event counts and depth/edge stats that are already in the evidence dict. No secrets, no PII. Operator-only CLI tool. |
| T-izh-02 | T (Tampering) | classify_reject_code | accept | Read-only classification of existing stats dict. Does not modify eligibility verdicts. The hard invariant (eligible iff executable_ticks > 0) is unchanged and enforced in scan_one_tape. |
</threat_model>

<verification>
1. `python -m pytest tests/test_gate2_corpus_visibility.py -x -q --tb=short` -- all new tests pass
2. `python -m pytest tests/test_gate2_eligible_tape_acquisition.py -x -q --tb=short` -- existing tests still pass
3. `python -m pytest tests/test_gate2_candidate_ranking.py -x -q --tb=short` -- existing tests still pass
4. `python -m pytest tests/ -x -q --tb=short` -- full regression clean
5. `python -m polytool --help` -- CLI loads without import errors
</verification>

<success_criteria>
- tape-manifest table output shows confidence class, structured reject code, event density, BBO ticks, edge gap, and depth per tape
- tape-manifest JSON includes diagnostics dict per tape entry
- scan-gate2-candidates tape mode shows event density and confidence class
- All classification logic is tested with deterministic offline tests
- Zero regressions in existing test suite
- Dev log documents all changes
</success_criteria>

<output>
After completion, create `.planning/quick/260410-izh-improve-gate-2-actionable-corpus-visibil/260410-izh-SUMMARY.md`
</output>
