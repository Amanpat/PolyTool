---
phase: 1B
plan: gate2-shadow-packet
subsystem: gates/sweep
tags: [gate2, benchmark-sweep, shadow-mode, market-maker-v1, metadata-fallback]
dependency_graph:
  requires: [benchmark_v1_manifest_closed, market_maker_v1]
  provides: [gate2_sweep_tooling_complete, gate3_runbook]
  affects: [mm_sweep_gate, shadow_gate, gate_status]
tech_stack:
  added: []
  patterns: [metadata-fallback-chain, monkeypatch-namespace-binding]
key_files:
  created:
    - docs/specs/SPEC-phase1b-gate2-shadow-packet.md
    - docs/runbooks/GATE3_SHADOW_RUNBOOK.md
    - docs/dev_logs/2026-03-26_phase1b_gate2_shadow_packet.md
  modified:
    - tools/gates/mm_sweep.py
    - tools/gates/close_mm_sweep_gate.py
    - tests/test_mm_sweep_gate.py
    - docs/CURRENT_STATE.md
decisions:
  - Tape metadata fallback chain: 5-level priority (prep_meta -> meta -> watch_meta -> market_meta -> silver_meta)
  - bucket_breakdown only present in gate payload when at least one tape has bucket metadata
  - gate_summary.md written unconditionally alongside gate JSON artifact
  - Monkeypatch target must be the importing module namespace, not the source module
metrics:
  duration: ~90 minutes
  completed: 2026-03-26
  tasks_completed: 9
  files_changed: 7
  tests_added: 7
  tests_total: 2648
---

# Phase 1B: Gate 2 + Shadow Packet Summary

**One-liner:** Extended mm_sweep YES-asset-ID fallback chain to cover Gold new_market (watch_meta) and Silver (market_meta, silver_meta) tapes, added bucket diagnostics and gate_summary.md artifact, wired --benchmark-manifest CLI flag, and wrote Gate 3 operator runbook.

---

## What Was Built

### Gate 2 sweep tooling gaps closed

`_build_tape_candidate` in `tools/gates/mm_sweep.py` previously could only
extract the YES asset ID from `prep_meta.json` and the `meta.json` context
dicts (quickrun_context/shadow_context). This covered only a subset of the
50 `benchmark_v1` tapes:

- Gold new_market tapes (5 tapes) use `watch_meta.json` with `yes_asset_id`
- Silver tapes (many of the remaining 45) use `market_meta.json` (field:
  `token_id`) and `silver_meta.json` (field: `token_id`)

Without these, running the sweep against `benchmark_v1.tape_manifest` would
raise `ValueError` on a significant fraction of tapes, making Gate 2 un-runnable.

The fallback chain is now 5 levels:
1. `prep_meta.json` → `yes_asset_id` / `yes_token_id`
2. `meta.json` → context dict extraction
3. `watch_meta.json` → `yes_asset_id` / `yes_token_id`
4. `market_meta.json` → `token_id`
5. `silver_meta.json` → `token_id`

Bucket metadata is now also extracted per tape and exposed as:
- `bucket` field on `TapeCandidate`
- `bucket_breakdown` dict in gate JSON payload (per-bucket total/positive/pass_rate)
- Per-bucket table in `gate_summary.md` Markdown artifact

### Gate 2 CLI flag

`close_mm_sweep_gate.py` gained `--benchmark-manifest PATH`. This is the
canonical way to run Gate 2 against all 50 tapes:

```bash
python tools/gates/close_mm_sweep_gate.py \
    --benchmark-manifest config/benchmark_v1.tape_manifest \
    --out artifacts/gates/mm_sweep_gate
```

### Gate 3 runbook

`docs/runbooks/GATE3_SHADOW_RUNBOOK.md` documents the full operator procedure
for the shadow session: prerequisites, safety invariants, market selection,
session execution, artifact review, manual sign-off, and gate verification.

---

## Commits

| Hash | Type | Description |
|------|------|-------------|
| d26e163 | feat | fix benchmark sweep gaps — metadata fallbacks, --benchmark-manifest CLI flag, bucket diagnostics |
| caee34f | docs | add Phase 1B spec and Gate 3 shadow runbook |
| 1a68950 | docs | update CURRENT_STATE.md — Phase 1B gate tooling complete |
| 071ab51 | docs | add dev log for Phase 1B gate2+shadow packet |

---

## Test Results

- **test_mm_sweep_gate.py**: 12 passed, 0 failed (7 new tests)
- **Full suite**: 2648 passed, 0 failed, 25 warnings (73.78s)

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Monkeypatch namespace fix for CLI test**

- **Found during:** Task 7 (test_close_mm_sweep_gate_cli_accepts_benchmark_manifest_flag)
- **Issue:** `monkeypatch.setattr(mm_sweep, "run_mm_sweep", ...)` had no effect because `close_mm_sweep_gate.py` imported `run_mm_sweep` via `from tools.gates.mm_sweep import ...` at load time. The name was bound in `close_gate`'s own namespace. Patching the source module left the bound name in `close_gate` unchanged; the real `run_mm_sweep` was called, which invoked `validate_benchmark_manifest` on the empty test manifest and raised `BenchmarkManifestValidationError`.
- **Fix:** Changed to `monkeypatch.setattr(close_gate, "run_mm_sweep", ...)` and `monkeypatch.setattr(close_gate, "format_mm_sweep_summary", ...)`.
- **Files modified:** `tests/test_mm_sweep_gate.py`

---

## Known Stubs

None. Gate 2 verdict is NOT YET RUN (requires operator shell access to run against live artifacts), but no code stub blocks correctness — the tooling is complete.

---

## Next Actions (Operator)

1. **Run Gate 2:**
   ```bash
   python tools/gates/close_mm_sweep_gate.py \
       --benchmark-manifest config/benchmark_v1.tape_manifest \
       --out artifacts/gates/mm_sweep_gate
   python tools/gates/gate_status.py
   ```
   Gate 2 passes at `>= 0.70` (35 of 50 tapes positive, after 200 bps fees, bid mark).

2. **Run Gate 3** (after Gate 2 PASS):
   See `docs/runbooks/GATE3_SHADOW_RUNBOOK.md`. 5-minute shadow session
   against a live market, then manually write `artifacts/gates/shadow_gate/gate_passed.json`.

3. **Verify all gates:**
   ```bash
   python tools/gates/gate_status.py
   # Expected: ALL REQUIRED GATES PASSED - Track A promotion criteria met.
   ```

4. Proceed to Stage 0 (paper live dry-run).

---

## Self-Check: PASSED
