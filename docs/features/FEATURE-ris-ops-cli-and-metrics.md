# FEATURE: RIS Operator CLI and Metrics Export

**Status:** Shipped (2026-04-03)
**Requirement IDs:** RIS_06_ops_cli, RIS_06_metrics_export
**Source task:** quick-260403-1sg

---

## What Ships

Two new artifacts:

1. `packages/research/metrics.py` -- Pure aggregation module, no network, no ClickHouse.
2. `tools/cli/research_stats.py` -- `research-stats` CLI with `summary` and `export` subcommands.

Registered in `polytool/__main__.py` as `research-stats`.

---

## Data Sources Read

The metrics module reads only from local artifacts using stdlib and existing module interfaces:

| Source | What it counts |
|---|---|
| `kb/rag/knowledge/knowledge.sqlite3` | Documents by source_family; derived_claims total |
| `artifacts/research/eval_artifacts/eval_artifacts.jsonl` | Gate decisions (ACCEPT/REVIEW/REJECT) and ingestion by source family |
| `artifacts/research/prechecks/precheck_ledger.jsonl` | Precheck recommendations (GO/CAUTION/STOP); only `event_type=precheck_run` events |
| `artifacts/research/reports/report_index.jsonl` | Report counts by type |
| `artifacts/research/acquisition_reviews/acquisition_review.jsonl` | New/cached dedup counts; error counts |

No ClickHouse queries. No network calls. The module reads local disk only.

---

## Operator Usage

```bash
# Human-readable snapshot
python -m polytool research-stats summary

# JSON output (pipe-friendly)
python -m polytool research-stats summary --json

# Export snapshot for Grafana
python -m polytool research-stats export
# -> writes artifacts/research/metrics_snapshot.json

# Export to custom path
python -m polytool research-stats export --out /path/to/snapshot.json

# Override individual artifact paths (for testing or multi-environment setups)
python -m polytool research-stats summary \
    --db /alt/knowledge.sqlite3 \
    --eval-artifacts-dir /alt/eval \
    --precheck-ledger /alt/precheck_ledger.jsonl \
    --report-dir /alt/reports \
    --acquisition-review-dir /alt/reviews
```

### Expected output shape (summary)

```
=== RIS Metrics Snapshot ===
Generated: 2026-04-03T05:26:09+00:00

[Knowledge Store]
  Documents : 5  (by family: academic=1  book=1  manual=3)
  Claims    : 0

[Eval Gate]
  ACCEPT=0  REVIEW=0  REJECT=0

[Prechecks]
  GO=0  CAUTION=1  STOP=0

[Reports]
  Total=0

[Acquisition]
  New=0  Cached=0  Errors=0
```

---

## Grafana Integration Note

The `export` subcommand writes a JSON file to `artifacts/research/metrics_snapshot.json`.
This file can be polled by the Grafana Infinity plugin (JSON file data source) to populate
panels showing document counts, gate splits, and precheck decisions.

Setup steps (when Grafana is available):
1. Configure Grafana Infinity data source pointing to the exported JSON path.
2. Schedule `python -m polytool research-stats export` as a cron job or APScheduler task
   (RIS_06 v2 scheduler integration) to keep the file fresh.

ClickHouse integration (writing a `ris_metrics` table) and a pre-built Grafana dashboard
JSON are explicitly deferred to RIS_06 v2.

---

## What Is Deferred

| Item | Deferred to |
|---|---|
| ClickHouse write path for RIS metrics | RIS_06 v2 |
| APScheduler / cron integration for auto-export | RIS_06 v2 scheduler integration |
| Pre-built Grafana dashboard JSON | RIS_06 v2 |
| Trend tracking (historical snapshots, delta) | RIS_06 v2 |

---

## Module Interface

```python
from packages.research.metrics import (
    RisMetricsSnapshot,   # dataclass
    collect_ris_metrics,  # -> RisMetricsSnapshot
    format_metrics_summary,  # RisMetricsSnapshot -> str
)

snapshot = collect_ris_metrics()
print(format_metrics_summary(snapshot))
# or
import json
print(json.dumps(snapshot.to_dict(), indent=2))
```

### RisMetricsSnapshot fields

| Field | Type | Description |
|---|---|---|
| `generated_at` | str | ISO-8601 UTC timestamp |
| `total_docs` | int | Total documents in KnowledgeStore |
| `total_claims` | int | Total derived claims in KnowledgeStore |
| `docs_by_family` | dict | Document count by source_family |
| `gate_distribution` | dict | Eval gate counts: ACCEPT/REVIEW/REJECT |
| `ingestion_by_family` | dict | Eval artifact count by source_family |
| `precheck_decisions` | dict | Precheck decision counts: GO/CAUTION/STOP |
| `reports_by_type` | dict | Report count by report_type |
| `total_reports` | int | Total reports in index |
| `acquisition_new` | int | New acquisitions (non-error) |
| `acquisition_cached` | int | Cached/duplicate acquisitions (non-error) |
| `acquisition_errors` | int | Acquisition attempts that had errors |

---

## Tests

15 offline deterministic tests in `tests/test_ris_ops_metrics.py`. All pass.
No network, no ClickHouse, no LLM dependencies.
