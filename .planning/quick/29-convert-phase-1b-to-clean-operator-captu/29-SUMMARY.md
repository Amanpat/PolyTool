---
phase: quick
plan: "029"
subsystem: phase-1b-corpus-campaign
tags: [corpus, gate2, capture, tooling, docs]
dependency_graph:
  requires: [quick-027, quick-028]
  provides: [capture_status_tool, capture_campaign_spec]
  affects: [CORPUS_GOLD_CAPTURE_RUNBOOK, CURRENT_STATE, STATE]
tech_stack:
  added: []
  patterns: [read-only-helper, tdd-red-green]
key_files:
  created:
    - tools/gates/capture_status.py
    - tests/test_capture_status.py
    - docs/specs/SPEC-phase1b-gold-capture-campaign.md
    - docs/dev_logs/2026-03-27_phase1b_gold_capture_campaign_packet.md
  modified:
    - docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md
    - docs/CURRENT_STATE.md
    - .planning/STATE.md
decisions:
  - capture_status.py is read-only (reuses corpus_audit internals, never calls run_corpus_audit)
  - main(argv) entry point pattern for direct import in tests (no subprocess)
  - Runbook v1.1 removes stale hard-coded counts; delegates to capture_status.py
metrics:
  duration: "~25 minutes"
  completed: "2026-03-27"
  tasks_completed: 3
  files_changed: 7
---

# Phase quick Plan 029: Phase 1B Gold Capture Campaign Packet Summary

**One-liner:** Read-only `capture_status.py` shortage table helper (exit 0/1) + authoritative campaign spec + tightened runbook + CURRENT_STATE.md updated for no-gate-core-changes-needed status.

---

## What Was Built

### Task 2 — capture_status.py + tests (commit be2a56b)

`tools/gates/capture_status.py` is a read-only corpus quota status helper. It:
- Reuses `_discover_tape_dirs` + `audit_tape_candidates` from `corpus_audit.py`
- Never calls `run_corpus_audit()` (which writes files) — read-only by design
- Prints a compact bucket shortage table to stdout (default)
- Prints machine-readable JSON on `--json`
- Exits 0 when corpus is complete (total_need == 0), exits 1 when shortage exists
- Accepts `--tape-roots PATH` (repeatable, same defaults as corpus_audit.py)

`tests/test_capture_status.py` has 4 TDD tests:
1. `test_shortage_table` — 1 politics tape → exit 1, table shows bucket data
2. `test_complete_state` — 50 tapes across all buckets → exit 0, "COMPLETE"
3. `test_json_mode` — --json output is valid JSON with expected fields
4. `test_empty_roots` — empty root → exit 1, total_have=0

### Task 1 — Campaign spec + runbook tightening (commit 2030c8d)

`docs/specs/SPEC-phase1b-gold-capture-campaign.md` is the authoritative Phase 1B
campaign spec containing:
- Context: benchmark_v1 immutable, 10/50 qualify, 40 needed
- Starting shortage table (verbatim from shortage_report.md)
- Bucket quotas and immutable constraints (min_events=50, >=70% Gate 2 threshold)
- Numbered campaign loop (check → capture → re-audit → repeat → Gate 2)
- Resumability rules
- Success artifacts (corpus_audit exits 0, manifest written)
- Failure artifacts (shortage_report.md written)
- Constraints section (no live capital, no tuning, benchmark_v1 immutable)
- Tool reference table

`docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md` updated (v1.0 → v1.1):
- Added Section 0: Quick Status Check with one-liner command
- Section 7: replaced stale hard-coded counts with dynamic reference to capture_status.py
- Reference block: added campaign spec + quick status tool

### Task 3 — CURRENT_STATE.md + dev log + STATE.md (commit 9e6168a)

`docs/CURRENT_STATE.md`:
- Status header updated to "awaiting live Gold capture"
- Gate 2 bullet rewritten: "no gate-core or strategy changes required", links to
  capture_status.py, runbook, and campaign spec

`docs/dev_logs/2026-03-27_phase1b_gold_capture_campaign_packet.md`: complete dev log
with files changed, commands + output, test results, friction reduction summary,
next operator actions, and open questions.

`.planning/STATE.md`:
- Blockers/Concerns: updated Track 1 Gate 2 corpus bullet
- Last activity: updated to quick-029
- Quick Tasks table: added row 029

---

## Key Artifacts

| Artifact | Path | Purpose |
|----------|------|---------|
| Quick status helper | `tools/gates/capture_status.py` | One command to see shortage |
| Campaign spec | `docs/specs/SPEC-phase1b-gold-capture-campaign.md` | Authoritative campaign authority |
| Runbook (updated) | `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md` | Capture commands + quick status |
| Dev log | `docs/dev_logs/2026-03-27_phase1b_gold_capture_campaign_packet.md` | Transition record |

---

## Test Results

- `tests/test_capture_status.py`: 4 / 4 tests passing
- Full regression suite: **2666 passed, 0 failed**, 25 warnings (pre-existing deprecation warnings only)

---

## Deviations from Plan

None — plan executed exactly as written. Task execution order was Task 2 → Task 1 → Task 3 as specified.

---

## Operator Next Steps

```bash
# Check current shortage
python tools/gates/capture_status.py

# Capture a sports tape (replace SLUG and timestamp)
python -m polytool simtrader shadow \
    --market <SLUG> \
    --strategy market_maker_v1 \
    --duration 600 \
    --record-tape \
    --tape-dir "artifacts/simtrader/tapes/sports_<SLUG>_<YYYYMMDDTHHMMSSZ>"

# After each batch, re-audit
python tools/gates/corpus_audit.py \
    --tape-roots artifacts/simtrader/tapes \
    --tape-roots artifacts/silver \
    --tape-roots artifacts/tapes \
    --out-dir artifacts/corpus_audit \
    --manifest-out config/recovery_corpus_v1.tape_manifest

# When corpus_audit exits 0, run Gate 2
python tools/gates/close_mm_sweep_gate.py \
    --benchmark-manifest config/recovery_corpus_v1.tape_manifest \
    --out artifacts/gates/mm_sweep_gate
```

Full campaign loop is documented in `docs/specs/SPEC-phase1b-gold-capture-campaign.md`.
Capture commands are in `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md`.

---

## Known Stubs

None. All tools are fully wired. `capture_status.py` reads real tape inventory and
produces live shortage counts.

---

## Self-Check

Checking created files and commits:

- FOUND: tools/gates/capture_status.py
- FOUND: tests/test_capture_status.py
- FOUND: docs/specs/SPEC-phase1b-gold-capture-campaign.md
- FOUND: docs/dev_logs/2026-03-27_phase1b_gold_capture_campaign_packet.md
- FOUND: .planning/quick/29-convert-phase-1b-to-clean-operator-captu/29-SUMMARY.md
- Commit be2a56b: feat(quick-029): add capture_status.py quota-status helper with tests
- Commit 2030c8d: docs(quick-029): add gold capture campaign spec and tighten runbook
- Commit 9e6168a: docs(quick-029): update CURRENT_STATE.md and write dev log for campaign packet

## Self-Check: PASSED
