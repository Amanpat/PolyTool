# Dev Log: RIS R4 -- CLI Truth Alignment and Coverage Gaps

**Date:** 2026-04-03
**Task:** quick-260403-2p9
**Objective:** Close RIS_06 doc-to-code truth drift and add missing CLI test coverage.

---

## Files Modified

| File | Role | Action |
|---|---|---|
| docs/reference/RAGfiles/RIS_06_INFRASTRUCTURE.md | RIS_06 spec | Updated CLI examples to match shipped commands |
| tests/test_ris_ops_metrics.py | CLI + metrics tests | Added 6 CLI-level tests for research-stats |
| docs/dev_logs/2026-04-03_ris_r4_cli_truth_alignment.md | This dev log | Created |

---

## Gaps Fixed

### 1. Doc truth: `research scheduler-status` -> `research-scheduler status`

RIS_06 spec said `polytool research scheduler-status`. Shipped CLI is `python -m polytool research-scheduler status`.
Updated spec to match shipped reality with full subcommand examples (status, status --json, start --dry-run).
Zero occurrences of the old command name remain.

### 2. Doc truth: `research stats` -> `research-stats summary`

RIS_06 spec said `polytool research stats [--days N]`. Shipped CLI is `python -m polytool research-stats summary [--json]`
and `python -m polytool research-stats export [--out PATH]`.
Updated spec to match shipped reality with both subcommands shown.

### 3. APScheduler optional install behavior

Added note to RIS_06 spec documenting that APScheduler is an optional dependency (`pip install 'polytool[ris]'`),
JOB_REGISTRY imports without it, and `status`/`run-job` subcommands work without it.
This matches the shipped behavior documented in FEATURE-ris-scheduler-v1.md.

### 4. research-stats CLI test coverage

Added 6 new tests in `TestResearchStatsCLI` class to `tests/test_ris_ops_metrics.py`:

| Test | What it covers |
|------|----------------|
| `test_cli_summary_returns_0` | main(["summary"]) with path overrides returns 0, prints "Knowledge Store" |
| `test_cli_summary_json_returns_valid_json` | main(["summary", "--json"]) returns 0, stdout is valid JSON with required keys |
| `test_cli_export_writes_file` | main(["export", "--out", PATH]) returns 0, creates valid JSON file |
| `test_cli_missing_subcommand_returns_1` | main([]) returns exit code 1 |
| `test_cli_export_creates_parent_dirs` | Nested export path: parent directories created automatically |
| `test_cli_summary_with_populated_data` | Pre-populated KS + eval artifacts: --json output has total_docs > 0 |

All tests use path-override CLI flags to avoid touching default artifact paths.

---

## Gaps Explicitly Deferred

- ClickHouse write path for RIS metrics (RIS_06 v2)
- APScheduler integration tests with real scheduler (requires APScheduler installed; existing injectable tests are sufficient)
- research-health CLI test expansion (already has 6 tests in test_ris_monitoring.py)

---

## Commands Run

```
# Task 1 verification
grep -n "research-scheduler status" docs/reference/RAGfiles/RIS_06_INFRASTRUCTURE.md  -> 3 matches (lines 120, 245, 246)
grep -n "research-stats summary" docs/reference/RAGfiles/RIS_06_INFRASTRUCTURE.md    -> 1 match (line 211)
grep -n "scheduler-status" docs/reference/RAGfiles/RIS_06_INFRASTRUCTURE.md          -> 0 matches (exit 1)

# Task 2 test run
python -m pytest tests/test_ris_ops_metrics.py -x -q --tb=short
Result: 21 passed in 0.81s

# Task 3 full RIS test run
python -m pytest tests/test_ris_ops_metrics.py tests/test_ris_scheduler.py tests/test_ris_monitoring.py -v --tb=short
Result: 92 passed in 1.10s

# Smoke test
python -m polytool --help | grep "research-"
Result: research-scheduler, research-stats, research-health all present

# Full regression
python -m pytest tests/ -x -q --tb=short
Result: 3566 passed, 3 deselected, 25 warnings in 93.26s
```

---

## Codex Review Tier

**Skip** -- docs and tests only, no execution/trading code.
