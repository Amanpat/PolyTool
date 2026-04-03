# Dev Log: RIS Report Persistence and Catalog

**Date:** 2026-04-02
**Plan reference:** quick-260402-xbt
**Status:** Complete

---

## Objective

Complete the report persistence/catalog side of RIS_05 Synthesis Engine. Operator
needed a way to persist synthesis outputs as markdown artifacts, list and search past
reports via CLI, and generate manual weekly-digest summaries -- all without requiring
RIS_06 automation infrastructure.

---

## Files Changed

| File | Action | Why |
|------|--------|-----|
| `packages/research/synthesis/report_ledger.py` | Created | Core library: ReportEntry, persist_report, list_reports, search_reports, generate_digest |
| `packages/research/synthesis/__init__.py` | Updated | Add report_ledger exports to synthesis package |
| `tools/cli/research_report.py` | Created | CLI entrypoint: save/list/search/digest subcommands |
| `polytool/__main__.py` | Updated | Register research-report command in CLI router |
| `tests/test_ris_report_catalog.py` | Created | 21 deterministic offline tests |
| `docs/features/FEATURE-ris-report-persistence.md` | Created | Feature documentation |
| `docs/dev_logs/2026-04-02_ris_r3_report_storage_and_catalog.md` | Created | This dev log |
| `docs/CURRENT_STATE.md` | Updated | New RIS Report Persistence section appended |

---

## Design Decisions

### Storage: JSONL local-first (ClickHouse deferred)

Report volume for RIS is low (tens to hundreds per week). A JSONL append-only index
at `artifacts/research/reports/report_index.jsonl` is sufficient and matches the
existing pattern from `precheck_ledger.py`. ClickHouse indexing adds dependency
complexity with no current benefit.

Decision: JSONL for now. ClickHouse indexing documented as a deferred item in the
feature doc. Escalation trigger: if report volume exceeds ~10k entries or cross-report
analytics are needed.

### No RAG indexing of reports

Reports are operator-facing artifacts, not evidence sources. Indexing them into the
knowledge store would create circular evidence injection (reports summarize knowledge
store content; feeding reports back in as sources creates feedback loops). Reports
live under `artifacts/` (gitignored), not under `kb/`.

### Digest aggregates three sources

The `generate_digest` function combines precheck ledger data, eval artifacts, and
previously saved reports within the time window. This gives operators a single-command
weekly summary without requiring any external services.

---

## Commands Run + Output

```bash
# Import verification
python -c "from packages.research.synthesis.report_ledger import persist_report, list_reports, search_reports, generate_digest, ReportEntry; print('imports OK')"
# OUTPUT: imports OK

python -c "from tools.cli.research_report import main; print('CLI import OK')"
# OUTPUT: CLI import OK

python -m polytool --help | grep "research-report"
# OUTPUT:   research-report           Save, list, search reports and generate weekly digests
```

---

## Test Results

```bash
python -m pytest tests/test_ris_report_catalog.py -v --tb=short
```

```
21 passed in 0.31s
```

```bash
python -m pytest tests/ -q --tb=short -k "not live"
```

```
3334 passed, 143 deselected, 25 warnings in 93.57s (0:01:33)
```

**Result:** 21 new tests, 0 failures, 0 regressions.

---

## RIS_05 Completion Status

| Component | Status |
|-----------|--------|
| Report persistence (persist_report, list_reports, search_reports) | **Complete** |
| Weekly digest generation (generate_digest) | **Complete** |
| CLI: save/list/search/digest subcommands | **Complete** |
| JSONL report index | **Complete** |
| Query planner | Separate work item |
| Synthesis engine / report content generation | Separate work item |
| ClickHouse report indexing | Deferred (RIS_06 or later) |
| APScheduler automated digest scheduling | Deferred (RIS_06) |

---

## Commits

| Hash | Message |
|------|---------|
| 056ba37 | feat(quick-260402-xbt-01): report ledger library and CLI entrypoint |
| b37e476 | test(quick-260402-xbt-02): 21 deterministic offline tests for report catalog |

---

## Codex Review

Not triggered (no execution/risk files modified; docs, CLI, and tests only).
