# RIS Report Persistence and Catalog

**Status:** Implemented (quick-260402-xbt, 2026-04-02)
**Spec relationship:** Completes the persistence/catalog side of RIS_05 Synthesis Engine.

---

## What It Does

Provides a local-first persistence and retrieval layer for RIS synthesis outputs:

1. **Report persistence** — Save any markdown-format report as an artifact file under
   `artifacts/research/reports/`. Files are named `{YYYY-MM-DD}_{report_id}.md`.

2. **JSONL index** — A lightweight append-only index at
   `artifacts/research/reports/report_index.jsonl` enables list and search operations
   without requiring ClickHouse.

3. **Weekly digest generation** — A CLI command that aggregates precheck runs, eval
   artifacts, and previously generated reports from a configurable time window into a
   single markdown digest artifact.

---

## Storage Layout

```
artifacts/research/reports/
  report_index.jsonl          # Append-only JSONL index (one entry per report)
  2026-04-01_abc123def456.md  # Markdown artifact files ({date}_{report_id}.md)
  2026-04-02_xyz789aaa111.md
  ...
```

The `report_index.jsonl` format (one JSON line per report):

```json
{
  "report_id": "abc123def456",
  "title": "Market Edge Analysis",
  "report_type": "precheck_summary",
  "created_at": "2026-04-01T10:00:00+00:00",
  "artifact_path": "artifacts/research/reports/2026-04-01_abc123def456.md",
  "source_window": "7d",
  "summary_line": "Market maker spread opportunities observed in BTC/ETH pairs",
  "tags": ["market-maker", "crypto"],
  "metadata": {},
  "schema_version": "report_ledger_v1"
}
```

---

## CLI Commands

### Save a report

```bash
# From inline body
python -m polytool research-report save \
  --title "Market Edge Analysis" \
  --body "Report content here..." \
  --type precheck_summary \
  --tags market-maker crypto

# From a file
python -m polytool research-report save \
  --title "My Report" \
  --body-file /path/to/report.md

# Machine-readable output
python -m polytool research-report save \
  --title "My Report" \
  --body "Content..." \
  --json
```

### List past reports

```bash
# Last 7 days (default 30d)
python -m polytool research-report list --window 7d

# All time, up to 50 results
python -m polytool research-report list --window all --limit 50

# JSON output for scripting
python -m polytool research-report list --window 30d --json
```

### Search past reports

```bash
# Keyword search across title, summary, and tags
python -m polytool research-report search --query "market maker"
python -m polytool research-report search --query "crypto" --json
```

### Generate a weekly digest

```bash
# Default 7-day window
python -m polytool research-report digest

# Custom window
python -m polytool research-report digest --window 30

# Custom ledger / eval artifacts paths
python -m polytool research-report digest \
  --window 7 \
  --precheck-ledger artifacts/research/prechecks/precheck_ledger.jsonl \
  --eval-artifacts-dir artifacts/research/eval_artifacts

# JSON output
python -m polytool research-report digest --window 7 --json
```

---

## Report Types

| Type               | Description                                  |
|--------------------|----------------------------------------------|
| `precheck_summary` | Summary of precheck run results              |
| `eval_summary`     | Summary of document evaluation results       |
| `weekly_digest`    | Automated digest across all RIS data sources |
| `custom`           | Operator-authored or ad-hoc report           |

---

## Architecture

### Local-first JSONL (no ClickHouse in this pass)

The operator scale for RIS reports is low (tens to hundreds per week), so a JSONL
append-only index is sufficient. ClickHouse indexing is explicitly deferred.

Advantages:
- Zero infrastructure dependencies for read/write operations
- Instant grep-style search without a running database
- Index file is human-readable and inspectable
- Matches the existing pattern from `precheck_ledger.py`

### Python library

`packages/research/synthesis/report_ledger.py` — core logic:

- `ReportEntry` — dataclass for index entries
- `persist_report()` — write markdown file + append to JSONL index
- `list_reports()` — read index with optional time window filter
- `search_reports()` — case-insensitive substring search on title/summary/tags
- `generate_digest()` — aggregate precheck + eval data into a digest report

### CLI entrypoint

`tools/cli/research_report.py` — thin argument-parsing layer over the library.
Registered in `polytool/__main__.py` as `research-report`.

---

## Digest Generation Detail

The `digest` subcommand aggregates three data sources:

1. **Precheck runs** from `precheck_ledger.jsonl` (filtered to time window)
   - Count by recommendation (GO / CAUTION / STOP)
   - Flag stale warnings and operator overrides
   - List each idea evaluated

2. **Eval artifacts** from `eval_artifacts.jsonl` (filtered by timestamp)
   - Count by gate decision (ACCEPT / REVIEW / REJECT)

3. **Previous reports** from `report_index.jsonl` (filtered to time window)
   - List report titles with type and date

Output is a markdown document with sections: Prechecks, Evaluations, Reports Generated,
Key Observations.

---

## Deferred Items

The following are explicitly out of scope for this implementation and deferred to
later work items:

1. **ClickHouse report indexing** — When report volume grows or cross-query analytics
   are needed, a `ris_reports` ClickHouse table can be added. For current operator
   scale, JSONL is sufficient.

2. **APScheduler / n8n automated digest scheduling** — The `digest` command is manual
   in this pass. Automated weekly scheduling belongs in RIS_06. Do not add cron
   integration here.

3. **RAG indexing of reports** — Reports are operator-facing artifacts, not truth sources.
   They are explicitly excluded from RAG ingestion to avoid circular evidence injection.
   Reports live under `artifacts/` (gitignored), not under `kb/` or the knowledge store.

4. **Full-text search** — The current substring match is sufficient. Full-text indexing
   (e.g., with SQLite FTS or DuckDB) is deferred until search performance becomes a
   bottleneck.

---

## Tests

21 deterministic offline tests in `tests/test_ris_report_catalog.py`:

- `TestReportPersistence` (7 tests) — file creation, field validation, window filtering,
  empty-index behavior, report_id determinism, multi-append correctness
- `TestReportSearch` (4 tests) — title/tag/summary matching, no-match path
- `TestDigestGeneration` (4 tests) — digest creation, empty ledger handling,
  section structure, precheck count inclusion
- `TestCLI` (6 tests) — save/list/search/digest routing, JSON output, --help

All tests use `tmp_path` and have no network calls or external dependencies.

---

## Relationship to RIS_05

RIS_05 Synthesis Engine spec covers:
- Query planner (separate work item)
- Synthesis engine / report generation logic (separate work item)
- **Report persistence and catalog** — this plan

This plan completes the persistence and catalog side. The query planner and
synthesizer logic that _produces_ the markdown content are separate work items.
