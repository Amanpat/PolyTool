---
phase: 260414-qrt
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - tools/gates/qualify_gold_batch.py
  - tests/test_qualify_gold_batch.py
  - docs/dev_logs/2026-04-14_post_capture_qualification_workflow.md
autonomous: true
requirements: []
must_haves:
  truths:
    - "Operator can pass one or more tape directories and see per-tape qualification verdict"
    - "Operator sees before/after shortage delta showing which bucket shortages the batch reduces"
    - "Operator sees which exact tapes are ready to feed the Gate 2 recovery-corpus workflow"
    - "Tool is read-only -- never writes files, never mutates tape data or manifests"
  artifacts:
    - path: "tools/gates/qualify_gold_batch.py"
      provides: "Post-capture qualification CLI tool"
      exports: ["qualify_batch", "main"]
    - path: "tests/test_qualify_gold_batch.py"
      provides: "Deterministic offline tests for qualify_gold_batch"
    - path: "docs/dev_logs/2026-04-14_post_capture_qualification_workflow.md"
      provides: "Dev log documenting the work"
  key_links:
    - from: "tools/gates/qualify_gold_batch.py"
      to: "tools/gates/corpus_audit.py"
      via: "imports audit_tape_candidates, _discover_tape_dirs, _BUCKET_QUOTAS, DEFAULT_MIN_EVENTS, DEFAULT_TAPE_ROOTS, _detect_tier, _detect_bucket"
      pattern: "from tools\\.gates\\.corpus_audit import"
    - from: "tools/gates/qualify_gold_batch.py"
      to: "tools/gates/capture_status.py"
      via: "imports compute_status for before-snapshot"
      pattern: "from tools\\.gates\\.capture_status import compute_status"
---

<objective>
Build a post-capture qualification and promotion workflow for Gold tapes.

Purpose: After an operator captures a batch of Gold tapes via `simtrader shadow`, there is
currently no single command that answers: "which of these new tapes qualify, which bucket
shortages do they reduce, and which are ready for Gate 2?" The operator must run the full
corpus_audit.py (which scans everything and writes files) then manually read
shortage_report.md. This plan creates a focused, read-only CLI tool that takes a set of
newly captured tape directories and produces a clear, actionable qualification report.

Output: `tools/gates/qualify_gold_batch.py` -- a read-only CLI that accepts `--tape-dirs`
(batch tape directories) and `--tape-roots` (existing corpus roots for baseline comparison),
qualifies each batch tape, computes before/after shortage delta, and prints a clear report
showing per-tape verdicts, bucket impact, and which tapes are ready for Gate 2 recovery-corpus.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/CLAUDE.md
@D:/Coding Projects/Polymarket/PolyTool/docs/CURRENT_STATE.md
@D:/Coding Projects/Polymarket/PolyTool/docs/PLAN_OF_RECORD.md

@D:/Coding Projects/Polymarket/PolyTool/tools/gates/corpus_audit.py
@D:/Coding Projects/Polymarket/PolyTool/tools/gates/capture_status.py
@D:/Coding Projects/Polymarket/PolyTool/tests/test_capture_status.py

@D:/Coding Projects/Polymarket/PolyTool/docs/specs/SPEC-phase1b-corpus-recovery-v1.md
@D:/Coding Projects/Polymarket/PolyTool/docs/specs/SPEC-phase1b-gold-capture-campaign.md
@D:/Coding Projects/Polymarket/PolyTool/docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md
@D:/Coding Projects/Polymarket/PolyTool/docs/dev_logs/2026-04-14_gate2_fill_diagnosis.md

<interfaces>
<!-- Key types and contracts the executor needs from existing tooling. -->

From tools/gates/corpus_audit.py:
```python
# Constants
_VALID_BUCKETS = frozenset({"politics", "sports", "crypto", "near_resolution", "new_market"})
_BUCKET_QUOTAS: dict[str, int] = {
    "politics": 10, "sports": 15, "crypto": 10, "near_resolution": 10, "new_market": 5,
}
_TOTAL_QUOTA = 50
DEFAULT_TAPE_ROOTS: list[str] = [
    "artifacts/tapes/gold", "artifacts/tapes/silver", "artifacts/tapes",
]
DEFAULT_MIN_EVENTS = 50

# Core functions
def _detect_tier(tape_dir: Path) -> str:
    """Returns "gold" | "silver" | "unknown"."""

def _detect_bucket(tape_dir: Path, *, meta, watch_meta, market_meta, silver_meta) -> str | None:
    """Returns bucket label or None."""

def _discover_tape_dirs(root: Path) -> list[Path]:
    """Walks up to 4 levels deep looking for events.jsonl or silver_events.jsonl."""

def audit_tape_candidates(tape_dirs: list[Path], *, min_events: int = 50) -> list[dict]:
    """Returns list of dicts with keys: tape_dir, events_path, bucket, tier,
    effective_events, status ("ACCEPTED"|"REJECTED"), reject_reason."""

def _get_events_path(tape_dir: Path) -> Path | None:
    """Returns events.jsonl path or None."""
```

From tools/gates/capture_status.py:
```python
def compute_status(tape_roots: list[Path], *, min_events: int = 50) -> dict:
    """Returns {total_have, total_quota, total_need, complete, buckets}.
    buckets = {bucket: {quota, have, need, gold, silver}}."""
```

From tools/gates/mm_sweep.py (used by corpus_audit):
```python
def _count_effective_events(events_path: Path) -> tuple[int, int, int]:
    """Returns (raw_count, n_asset_ids, effective_events)."""

def _read_json_object(path: Path) -> dict:
    """Reads a JSON file, returns {} on any error."""
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Create qualify_gold_batch.py and tests</name>
  <files>tools/gates/qualify_gold_batch.py, tests/test_qualify_gold_batch.py</files>
  <behavior>
    - Test 1 (single_tape_qualifies): One Gold tape with 60 events and bucket="sports" in an empty corpus -> per-tape verdict shows QUALIFIED, shortage delta shows sports need reduced by 1, tape listed as gate2-ready.
    - Test 2 (tape_too_short): One Gold tape with 30 events -> per-tape verdict shows REJECTED with reason "too_short", shortage delta unchanged, no tapes listed as gate2-ready.
    - Test 3 (tape_no_bucket): One Gold tape with 60 events but no watch_meta bucket field -> per-tape verdict shows REJECTED with reason "no_bucket_label".
    - Test 4 (batch_mixed): Three tapes -- one qualifying sports, one too-short politics, one qualifying politics -> report shows 2 QUALIFIED / 1 REJECTED, shortage delta shows sports -1 and politics -1.
    - Test 5 (over_quota_detection): 11 politics tapes submitted against an empty corpus (quota=10) -> 10 QUALIFIED, 1 REJECTED with reason "over_quota", shortage delta shows politics fully satisfied.
    - Test 6 (baseline_awareness): Pre-existing corpus has 8 politics tapes, batch adds 3 more politics -> only 2 reduce the shortage (need drops from 2 to 0), third is over_quota.
    - Test 7 (json_output): Same as Test 1 but with --json flag -> output is valid JSON dict with keys "batch_results", "shortage_delta", "gate2_ready".
    - Test 8 (empty_batch): No tape dirs provided -> exit 1, stderr contains usage hint.
    - Test 9 (gate2_ready_list): Batch of 3 qualifying tapes -> gate2_ready list contains exactly those 3 tape_dir paths.
  </behavior>
  <action>
**Write tests first (RED), then implement (GREEN).**

Create `tests/test_qualify_gold_batch.py`:
- Use the same `_make_gold_tape()` helper pattern from `tests/test_capture_status.py` (create tmp_path gold tape dirs with watch_meta.json and events.jsonl).
- For Test 6, create a pre-existing corpus in a separate tmp_path subdirectory and pass it via `--tape-roots`.
- All tests call `qualify_gold_batch.main(argv)` and capture stdout via `capsys`.
- JSON tests parse stdout and assert on dict structure.

Create `tools/gates/qualify_gold_batch.py`:

**Module structure:**
```
"""Post-capture qualification tool for Gold tape batches.

Read-only. Accepts batch tape directories, qualifies each tape against
Gate 2 admission rules, computes before/after shortage delta against
the existing corpus, and reports which tapes are ready for Gate 2.

Exit codes:
  0 -- at least one tape in the batch qualifies and reduces a shortage
  1 -- no tape qualifies or no batch dirs provided
"""
```

**Core function: `qualify_batch()`**
```python
def qualify_batch(
    batch_dirs: list[Path],
    tape_roots: list[Path],
    *,
    min_events: int = DEFAULT_MIN_EVENTS,
) -> dict:
```

Logic:
1. Compute "before" snapshot using `capture_status.compute_status(tape_roots)`.
2. For each batch_dir, resolve to absolute path. Use `_get_events_path()` to confirm it is a tape dir (skip with warning if not). Use `_count_effective_events()` for event count, `_detect_tier()` for tier, load metadata files, use `_detect_bucket()` for bucket.
3. Apply admission rules in order: (a) effective_events < min_events -> REJECTED/too_short, (b) no valid bucket -> REJECTED/no_bucket_label, (c) otherwise QUALIFIED (pre-quota).
4. Compute "after" snapshot: take the "before" bucket counts and add each QUALIFIED batch tape. Apply per-bucket quota caps -- if adding a QUALIFIED tape would exceed quota, mark it REJECTED/over_quota instead.
5. Build shortage_delta: for each bucket, `{"before": before_need, "after": after_need, "delta": before_need - after_need}`. Only include buckets where delta != 0 OR the batch has tapes in that bucket.
6. Build gate2_ready list: all QUALIFIED tapes that actually reduce a shortage (not over_quota).
7. Return dict:
```python
{
    "batch_results": [
        {
            "tape_dir": str,
            "bucket": str | None,
            "tier": str,
            "effective_events": int,
            "status": "QUALIFIED" | "REJECTED",
            "reject_reason": str | None,  # "too_short" | "no_bucket_label" | "over_quota" | None
        },
        ...
    ],
    "shortage_delta": {
        bucket: {"before": int, "after": int, "delta": int},
        ...
    },
    "gate2_ready": [str, ...],  # tape_dir paths of tapes that reduce a shortage
    "summary": {
        "total_in_batch": int,
        "qualified": int,
        "rejected": int,
        "shortages_reduced": int,  # count of buckets where delta > 0
    },
}
```

**CLI interface (`main()`):**
```
python tools/gates/qualify_gold_batch.py --tape-dirs DIR [DIR ...]
    [--tape-roots PATH ...]  # defaults to DEFAULT_TAPE_ROOTS
    [--json]                 # machine-readable JSON output
```

**Human-readable output format (when not --json):**
```
=== Batch Qualification Report ===

Per-tape results:
  [QUALIFIED] artifacts/tapes/gold/slug1  bucket=sports  tier=gold  events=87
  [REJECTED]  artifacts/tapes/gold/slug2  bucket=politics  tier=gold  events=30  reason=too_short
  [QUALIFIED] artifacts/tapes/gold/slug3  bucket=politics  tier=gold  events=62

Shortage delta:
  Bucket           Before  After  Delta
  ---------------  ------  -----  -----
  sports               15     14     -1
  politics              9      8     -1

Summary: 2 qualified, 1 rejected, 2 bucket shortages reduced

Gate 2 ready tapes (feed to corpus_audit.py):
  artifacts/tapes/gold/slug1
  artifacts/tapes/gold/slug3
```

If no tapes qualify, print: "No tapes in this batch qualify for Gate 2."
If no batch dirs provided (empty --tape-dirs), print usage hint to stderr and exit 1.

**Important constraints:**
- Read-only: never write any file. Never mutate tape data or manifests.
- Use "QUALIFIED" / "REJECTED" as status strings (not "ACCEPTED" like corpus_audit) to distinguish batch-level qualification from corpus-level acceptance.
- Import from corpus_audit: `_BUCKET_QUOTAS`, `_VALID_BUCKETS`, `DEFAULT_MIN_EVENTS`, `DEFAULT_TAPE_ROOTS`, `_detect_tier`, `_detect_bucket`, `_get_events_path`, `_read_json_object` (via mm_sweep import in corpus_audit, or import directly from mm_sweep).
- Import from capture_status: `compute_status`.
- Import from mm_sweep: `_count_effective_events`, `_read_json_object`.
- Follow the same `_REPO_ROOT` / `sys.path` pattern from corpus_audit.py.
- Use `argparse` for CLI. Require `--tape-dirs` with `nargs="+"`. Optional `--tape-roots` with `action="append"`.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m pytest tests/test_qualify_gold_batch.py -v --tb=short -x</automated>
  </verify>
  <done>
    - All 9 tests pass.
    - `python tools/gates/qualify_gold_batch.py --help` prints usage without error.
    - qualify_batch() returns the documented dict structure.
    - CLI human-readable output shows per-tape verdicts, shortage delta table, and gate2-ready list.
    - CLI --json output is valid JSON with keys batch_results, shortage_delta, gate2_ready, summary.
    - Tool is fully read-only (no file writes, no manifest mutations).
  </done>
</task>

<task type="auto">
  <name>Task 2: Write dev log</name>
  <files>docs/dev_logs/2026-04-14_post_capture_qualification_workflow.md</files>
  <action>
Create `docs/dev_logs/2026-04-14_post_capture_qualification_workflow.md` with the standard dev log format:

```markdown
# Post-Capture Qualification Workflow

**Date:** 2026-04-14
**Task:** quick-260414-qrt
**Status:** COMPLETE

---

## Summary

[1-2 paragraphs: what was built, why, and how it fits the Gold capture campaign loop]

---

## Problem Statement

After capturing Gold tapes via `simtrader shadow`, the operator had no single command to
answer: "which tapes qualify, which bucket shortages do they reduce, and which are ready
for Gate 2?" The existing `corpus_audit.py` does full-corpus scanning and writes files.
The existing `capture_status.py` shows current status but not what changed. The gap is a
focused batch-level qualification report with before/after delta.

---

## Solution: qualify_gold_batch.py

[Document the tool: CLI interface, core function, output format, how it integrates
with the capture campaign loop from SPEC-phase1b-gold-capture-campaign.md]

### Usage

[Show the exact commands an operator would use in the capture loop:
1. Capture tapes via simtrader shadow
2. Run qualify_gold_batch.py --tape-dirs <captured_dirs>
3. Read the report
4. Feed gate2_ready tapes to corpus_audit.py for promotion]

---

## What Was NOT Changed (Scope Discipline)

- No fill-model changes
- No benchmark_v1 manifest modifications
- No policy or gate threshold changes
- No changes to corpus_audit.py or capture_status.py (read-only consumer)
- No wallet discovery
- No cloud LLM routing

---

## Test Results

[Exact pytest output: N passed in X.XXs]
[Full regression suite: N passed, N failed (pre-existing), N deselected, N warnings]

---

## Files Changed

| File | Action |
|------|--------|
| `tools/gates/qualify_gold_batch.py` | Created -- post-capture batch qualification tool |
| `tests/test_qualify_gold_batch.py` | Created -- 9 deterministic offline tests |
| `docs/dev_logs/2026-04-14_post_capture_qualification_workflow.md` | Created -- this file |

## Codex Review

Tier: Skip (read-only reporting tool, no execution paths, no order placement, no live-capital logic).
```

Fill in the bracketed sections with actual results from Task 1 execution. Include the exact
test counts and regression suite output.
  </action>
  <verify>
    <automated>test -f "D:/Coding Projects/Polymarket/PolyTool/docs/dev_logs/2026-04-14_post_capture_qualification_workflow.md" && echo "EXISTS" || echo "MISSING"</automated>
  </verify>
  <done>Dev log exists at docs/dev_logs/2026-04-14_post_capture_qualification_workflow.md with all bracketed sections filled in from actual Task 1 results.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

No trust boundaries apply. This tool is read-only, runs locally, processes only
local tape files, and never writes output files or connects to external services.

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-qrt-01 | T (Tampering) | tape metadata files | accept | Tool is read-only consumer; if metadata is tampered the qualification result is wrong but no state is mutated. Operator reviews output before acting. |
| T-qrt-02 | I (Information Disclosure) | CLI output | accept | Output contains tape paths and bucket labels only -- no secrets, no PII, no credentials. |
</threat_model>

<verification>
```bash
# 1. Unit tests pass
cd "D:/Coding Projects/Polymarket/PolyTool" && python -m pytest tests/test_qualify_gold_batch.py -v --tb=short

# 2. CLI loads without error
python tools/gates/qualify_gold_batch.py --help

# 3. Dev log exists
test -f docs/dev_logs/2026-04-14_post_capture_qualification_workflow.md

# 4. Quick smoke test (no regressions)
python -m polytool --help
python -m pytest tests/ -x -q --tb=short 2>&1 | tail -5
```
</verification>

<success_criteria>
1. `python tools/gates/qualify_gold_batch.py --tape-dirs <dirs>` produces a clear per-tape qualification report with QUALIFIED/REJECTED verdicts.
2. Shortage delta shows before/after/delta per bucket, making it immediately obvious which shortages the batch reduces.
3. Gate 2 ready list shows exactly which tape paths can be fed to the recovery-corpus workflow.
4. `--json` flag emits machine-readable JSON with keys batch_results, shortage_delta, gate2_ready, summary.
5. Tool is fully read-only -- never writes files.
6. All 9 unit tests pass. No regressions in the full test suite.
7. Dev log documents the work following project conventions.
</success_criteria>

<output>
After completion, create `.planning/quick/260414-qrt-build-a-post-capture-qualification-and-p/260414-qrt-SUMMARY.md`
</output>
