---
phase: quick-260415-owc
plan: 01
subsystem: gates/analysis
tags: [gate2, failure-anatomy, decision-grade, partition, recommendation-matrix]
dependency_graph:
  requires: [artifacts/gates/gate2_sweep/gate_failed.json, artifacts/gates/gate2_sweep/sweeps]
  provides: [tools/gates/gate2_failure_anatomy.py, artifacts/gates/gate2_sweep/failure_anatomy.json, artifacts/gates/gate2_sweep/failure_anatomy.md, docs/dev_logs/2026-04-15_gate2_failure_anatomy.md]
  affects: [Gate 2 decision, Track 1 path-forward, Track 2 activation]
tech_stack:
  added: []
  patterns: [stdlib-only analysis script, Decimal-safe PnL comparison, per-tape aggregate JSON merging]
key_files:
  created:
    - tools/gates/gate2_failure_anatomy.py
    - tests/test_gate2_failure_anatomy.py
    - docs/dev_logs/2026-04-15_gate2_failure_anatomy.md
  modified: []
decisions:
  - "Use agg_total_fills+agg_total_orders from sweep_summary.json aggregate field (not best_net_profit alone) to distinguish structural-zero-fill from executable-break-even"
  - "gate_failed.json uses 'best_scenarios' key (not 'tapes'); load_sweep_results supports both for forward compatibility"
  - "Decimal string comparison for PnL (not float) to avoid precision artifacts from high-precision benchmark values"
  - "Three partition classes: structural-zero-fill (9), executable-negative-or-flat (34), executable-positive (7)"
metrics:
  duration_minutes: ~15
  completed_date: 2026-04-15
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 0
---

# Phase quick-260415-owc Plan 01: Gate 2 Failure Anatomy Summary

**One-liner:** Partition classifier that splits 50-tape Gate 2 corpus into structural-zero-fill (Silver, 9), executable-negative-or-flat (Shadow non-crypto, 34), and executable-positive (Shadow crypto, 7), with evidence-scored recommendation matrix for three path-forward options.

## Tasks Completed

| Task | Name | Commit | Files |
|---|---|---|---|
| 1 | Build partition classifier and report generator | d838218 | tools/gates/gate2_failure_anatomy.py, tests/test_gate2_failure_anatomy.py |
| 2 | Run anatomy analysis and write dev log | 48120e8 | docs/dev_logs/2026-04-15_gate2_failure_anatomy.md |

## Key Findings

The 7/50 = 14% Gate 2 pass rate conflates two structurally different failure modes:

1. **Silver tapes (9 tapes, all near_resolution):** Data-tier incompatibility.  No L2 book data means zero fills regardless of strategy parameters.  These tapes are not strategy failures.

2. **Shadow non-crypto tapes (34 tapes):** Strategy-market mismatch.  Fills were generated (42,247 total) but spread capture could not overcome fees and adverse inventory accumulation on low-frequency, extreme-probability markets.  Importantly, many "$0 best_net_profit" tapes in gate_failed.json are NOT zero-fill -- they are break-even-at-best with actual trade activity.

3. **Shadow crypto tapes (7 positive out of 10 total):** Optimal operating regime.  7/10 = 70% -- exactly the Gate 2 pass threshold.

## Recommendation Matrix (summary)

| Option | Gate-2 Closure | Time-to-Revenue | Risk |
|---|---|---|---|
| Crypto-only corpus subset | HIGH (7/10=70% today) | FAST | LOW |
| Track 2 focus (standalone) | N/A | MEDIUM | MEDIUM |
| Low-frequency strategy improvement | LOW (no evidence of fix path) | SLOW | HIGH |

Options 1 and 2 are not mutually exclusive under the triple-track model.  No gate thresholds were changed; no benchmark manifests modified; no strategy parameters altered.

## Verification Results

- `python -m pytest tests/test_gate2_failure_anatomy.py`: **25 passed, 0 failed**
- `python tools/gates/gate2_failure_anatomy.py`: Ran cleanly, 50 tapes classified
- Partition assertion: `sum(counts) == 50` -- PASS
- Dev log exists at `docs/dev_logs/2026-04-15_gate2_failure_anatomy.md` -- PASS
- Full regression: **2504 passed, 1 pre-existing failure** (`test_gemini_provider_success` in `test_ris_phase2_cloud_provider_routing.py` -- AttributeError on non-existent module attribute, unrelated to this task)

## Deviations from Plan

**1. [Rule 1 - Bug] gate_failed.json uses 'best_scenarios' not 'tapes' key**
- **Found during:** Task 1 implementation
- **Issue:** Plan's interface doc showed the key as `tapes` but the actual file uses `best_scenarios`
- **Fix:** `load_sweep_results` reads `best_scenarios` first with fallback to `tapes` for forward compatibility
- **Files modified:** tools/gates/gate2_failure_anatomy.py
- **Commit:** d838218

**2. [Rule 2 - Missing detail] Dev log per-tape table populated with actual sweep data**
- **Found during:** Task 2
- **Issue:** Plan did not specify exact per-tape fill numbers for the dev log tables; populated from real artifact data after running the script
- **Fix:** Ran the script first, then used actual numbers in the dev log (not placeholders)
- **Files modified:** docs/dev_logs/2026-04-15_gate2_failure_anatomy.md
- **Commit:** 48120e8

## Known Stubs

None. All data is sourced from real artifact files (gate_failed.json, sweep_summary.json). The script is fully reproducible.

## Threat Flags

None. Analysis reads only gitignored artifact files; no new network endpoints, auth paths, or schema changes introduced.

## Self-Check: PASSED

- `tools/gates/gate2_failure_anatomy.py` -- FOUND
- `tests/test_gate2_failure_anatomy.py` -- FOUND
- `docs/dev_logs/2026-04-15_gate2_failure_anatomy.md` -- FOUND
- `artifacts/gates/gate2_sweep/failure_anatomy.json` -- FOUND (gitignored artifact)
- `artifacts/gates/gate2_sweep/failure_anatomy.md` -- FOUND (gitignored artifact)
- Commit d838218 -- FOUND
- Commit 48120e8 -- FOUND
