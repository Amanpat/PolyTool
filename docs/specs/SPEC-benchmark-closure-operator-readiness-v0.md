# SPEC: Benchmark Closure Operator Readiness v0

**Spec ID:** SPEC-benchmark-closure-operator-readiness-v0
**Status:** Implemented (v0)
**Date:** 2026-03-17
**Parent spec:** SPEC-benchmark-closure-orchestrator-v1
**CLI surface:** `python -m polytool close-benchmark-v1 --status | --export-tokens`
**Module:** `tools/cli/close_benchmark_v1.py`

---

## Purpose

Extend the benchmark closure orchestrator with two operator-facing helper
surfaces that reduce friction for the real closure run:

1. **`--status`** — single-command progress snapshot showing what exists, what
   is missing, residual blockers, and the suggested next command.
2. **`--export-tokens`** — deterministic export of the 39 priority-1 token IDs
   needed for the Silver price-fetch step.

These are read-only surfaces. Neither mutates any data or runs any orchestration
stage; they only read existing config files and artifacts.

---

## New CLI Flags

### `--status`

```
python -m polytool close-benchmark-v1 --status
```

Prints a human-readable closure status table. Always exits 0 (informational).

**Output contract:**

```
========================================================================
  benchmark_v1 closure status  (<ISO timestamp>Z)
========================================================================

  Manifest:             [CREATED | MISSING]  config/benchmark_v1.tape_manifest
  Gap-fill targets:     [FOUND | MISSING]    config/benchmark_v1_gap_fill.targets.json  (N targets, M priority-1)
  Token export (.txt):  [FOUND | MISSING]    config/benchmark_v1_priority1_tokens.txt
  Token export (.json): [FOUND | MISSING]    config/benchmark_v1_priority1_tokens.json
  New-market targets:   [FOUND | MISSING]    config/benchmark_v1_new_market_capture.targets.json
  Latest run:           <date>  <run_dir>  [<status>, dry_run=<bool>]

  Residual blockers (from config/benchmark_v1.gap_report.json):
    • bucket '<name>': shortage=<N>
    ...

  Suggested next step:
    <one-line or multi-line guidance>
========================================================================
```

- If manifest exists: shows `*** benchmark_v1 is CLOSED ***` and suggests Gate 2.
- Residual blockers are read from `config/benchmark_v1.gap_report.json`.
- Latest run is found by scanning `artifacts/benchmark_closure/**/*.json`.
- New-market insufficiency is surfaced if
  `config/benchmark_v1_new_market_capture.insufficiency.json` exists.

### `--export-tokens`

```
python -m polytool close-benchmark-v1 --export-tokens
```

Reads `config/benchmark_v1_gap_fill.targets.json` and extracts token IDs where
`priority == 1`. Writes:

| File | Format |
|------|--------|
| `config/benchmark_v1_priority1_tokens.txt` | One token ID per line |
| `config/benchmark_v1_priority1_tokens.json` | JSON array of strings |

**Exit codes:**
- 0 — export written successfully
- 1 — gap-fill targets manifest missing or unreadable

**Properties:**
- **Deterministic**: always produces the same output for the same input manifest.
- **Idempotent**: safe to run multiple times; overwrites prior export.
- **Priority filter**: only `priority == 1` entries included; priority-2 overflow
  entries excluded.

---

## New Path Constants

Added to `tools/cli/close_benchmark_v1.py`:

```python
PRIORITY1_TOKENS_TXT  = Path("config/benchmark_v1_priority1_tokens.txt")
PRIORITY1_TOKENS_JSON = Path("config/benchmark_v1_priority1_tokens.json")
```

---

## New Functions

| Function | Purpose |
|----------|---------|
| `run_export_tokens(*, out_txt, out_json) -> int` | Export priority-1 token IDs |
| `run_status() -> int` | Print human-readable closure status |
| `_find_latest_run_artifact() -> Optional[Path]` | Find newest closure run artifact |

All three are pure read-only helpers. They do not call any downstream CLIs or
modify any config files.

---

## Ordering in `main()`

`--status` and `--export-tokens` are checked before any orchestration logic:

```python
if args.status:
    return run_status()

if args.export_tokens:
    return run_export_tokens()

# ... full run_closure() below
```

This ensures they are always fast and safe even when called without Docker/CH.

---

## Canonical Runbook

The operator runbook lives at:
```
docs/runbooks/BENCHMARK_CLOSURE_RUNBOOK.md
```

It provides exact commands and "if already done, skip to" guidance for each
of the 7 closure steps (Docker up → export tokens → fetch price_2min → Silver
run → new-market capture → full closure → manifest validation).

---

## Tests

New test file: `tests/test_benchmark_closure_operator.py` (17 offline tests).

Coverage:
- `run_export_tokens()`: success path, missing manifest, idempotent re-export,
  empty priority-1 list
- `run_status()`: returns 0, all-missing state, gap-fill targets found, already
  closed, shows blockers, token export found, latest run surfaced
- `_find_latest_run_artifact()`: returns None when no dir, returns latest path
- `main(--status)`, `main(--export-tokens)`: routing smoke, failure propagation
