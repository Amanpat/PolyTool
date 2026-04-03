# Dev Log: RIS R4 -- Operator CLI and Metrics Export

**Date:** 2026-04-03
**Task:** quick-260403-1sg
**Objective:** Implement the RIS_06 operator stats surface: `packages/research/metrics.py` aggregation module + `research-stats` CLI.

---

## Files Created / Modified

| File | Role | Action |
|---|---|---|
| `packages/research/metrics.py` | Core aggregation module | Created (~195 lines) |
| `tools/cli/research_stats.py` | CLI entrypoint | Created (~130 lines) |
| `polytool/__main__.py` | CLI router | Modified (3-point edit) |
| `tests/test_ris_ops_metrics.py` | Offline deterministic tests | Created (~280 lines) |
| `docs/features/FEATURE-ris-ops-cli-and-metrics.md` | Feature documentation | Created |
| `docs/dev_logs/2026-04-03_ris_r4_ops_cli_and_metrics.md` | This dev log | Created |
| `docs/CURRENT_STATE.md` | Project state tracking | Updated |

---

## Commands Run

### RED phase (failing tests)

```
python -m pytest tests/test_ris_ops_metrics.py -x -q --tb=short
```

Result: ERROR (collection failure) -- `ModuleNotFoundError: No module named 'packages.research.metrics'`. Confirmed RED.

### GREEN phase (implementation)

```
python -m pytest tests/test_ris_ops_metrics.py -x -q --tb=short
```

First attempt: 7 passed, 1 failed (test_acquisition_review_counts: acquisition_new=4, expected 3).

Root cause: acquisition records with errors were being counted in both acquisition_new AND acquisition_errors. Fixed the logic to exclude errored records from new/cached counts (error records are counted exclusively in acquisition_errors).

Second attempt: 15 passed, 0 failed. GREEN confirmed.

### CLI smoke tests

```
python -m polytool research-stats summary
```
Result: PASS -- printed full metrics snapshot with all 5 section headers, exited 0.

```
python -m polytool research-stats summary --json
```
Result: PASS -- printed valid JSON with all 12 expected keys.

```
python -m polytool research-stats export --out artifacts/research/metrics_snapshot.json
```
Result: PASS -- wrote file, printed confirmation.

```
python -c "import json; d=json.load(open('artifacts/research/metrics_snapshot.json')); print(list(d.keys()))"
```
Result: PASS -- all 12 keys present.

```
python -m polytool --help | grep research-stats
```
Result: PASS -- "research-stats" visible in RIS section.

### Regression suite

```
python -m pytest tests/ -q --tb=line
```

Result to be confirmed in final verification step (see below).

---

## Key Design Decisions

### 1. Local-first, no ClickHouse in this pass

The plan explicitly defers ClickHouse. The metrics module reads only:
- SQLite (stdlib `sqlite3`)
- JSONL files (stdlib `json`, inline `_iter_jsonl()` helper)
- `load_eval_artifacts()` from `packages/research/evaluation/artifacts.py`
- `AcquisitionReviewWriter.read_reviews()` from `packages/research/ingestion/acquisition_review.py`

No ClickHouse connection, no network calls, no LLM.

### 2. Inline `_iter_jsonl()` to avoid circular imports

The plan explicitly required this. Instead of importing `_iter_events` from `precheck_ledger.py` or `_iter_index` from `report_ledger.py`, `metrics.py` inlines its own `_iter_jsonl()` helper. This prevents circular import chains through the synthesis package tree.

### 3. event_type check: "precheck_run" not "precheck"

The plan mentioned `event_type == "precheck"` but the actual `precheck_ledger.py` writes `event_type: "precheck_run"`. The implementation handles both values (`"precheck_run"` and `"precheck"`) for forward compatibility. Tests use `"precheck_run"` to match the real ledger format.

### 4. Acquisition error counting is exclusive

Records with a non-None `error` field are counted only in `acquisition_errors`, not in `acquisition_new` or `acquisition_cached`. This gives cleaner semantics: new/cached counts reflect successful dedup outcomes; errors are a separate signal.

### 5. Three-point edit to `__main__.py`

The plan specified exactly three insertion points:
1. `research_stats_main = _command_entrypoint(...)` after `research_scheduler_main`
2. `"research-stats": "research_stats_main"` in `_COMMAND_HANDLER_NAMES`
3. A usage line in `print_usage()` in the RIS section

No other changes to `__main__.py`.

---

## What Is Deferred

- ClickHouse write path for RIS metrics (RIS_06 v2)
- APScheduler/cron integration for periodic auto-export (RIS_06 v2)
- Pre-built Grafana dashboard JSON for RIS metrics (RIS_06 v2)
- Trend tracking / historical snapshot deltas (RIS_06 v2)

---

## Codex Review Tier

**Skip** -- no execution/trading code, no ClickHouse write paths, no live order placement.
Files: docs, CLI formatting, read-only stats aggregation.
