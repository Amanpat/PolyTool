---
phase: quick
plan: 43
subsystem: docs
tags: [benchmark, policy, adr, crypto-blocker, gate2]
dependency_graph:
  requires: [quick-041]
  provides: [benchmark-policy-lock, adr-benchmark-versioning]
  affects: [CURRENT_STATE.md, CLAUDE.md]
tech_stack:
  added: []
  patterns: [ADR, policy-lock, escalation-criteria]
key_files:
  created:
    - docs/specs/ADR-benchmark-versioning-and-crypto-unavailability.md
    - docs/dev_logs/2026-03-29_crypto_benchmark_policy_decision.md
  modified:
    - docs/CURRENT_STATE.md
    - CLAUDE.md
decisions:
  - "WAIT_FOR_CRYPTO: crypto pair market absence is a scheduling gap, not a regime change; benchmark_v2 requires human decision per POLYTOOL_MASTER_ROADMAP_v5_1.md"
  - "Escalation deadline 2026-04-12: 14 calendar days from 2026-03-29"
  - "benchmark_v1 config files are permanently immutable; no AI agent may autonomously trigger benchmark_v2"
metrics:
  duration: "~10 minutes"
  completed_date: "2026-03-29"
  tasks_completed: 3
  files_changed: 4
---

# Phase quick Plan 43: Benchmark Policy Decision -- WAIT_FOR_CRYPTO Summary

## One-liner

Policy ADR written establishing WAIT_FOR_CRYPTO posture with 2026-04-12 escalation deadline; CLAUDE.md and CURRENT_STATE.md updated with benchmark policy lock guardrail.

## What Was Done

This was a docs-only task. No code, no manifest edits, no config/benchmark_v1.* mutations.

### Task 1: ADR Created

`docs/specs/ADR-benchmark-versioning-and-crypto-unavailability.md` — a full Architecture
Decision Record answering the five open policy questions:

1. Governing rule when a required bucket is temporarily unavailable: WAIT_FOR_CRYPTO.
2. Escalation condition: >= 14 calendar days absence by 2026-04-12, or format change, strategy
   overhaul, or major tape quality improvement.
3. Evidence required before benchmark_v2: last confirmed slug+timestamp, current date, no
   announcement of return, applicable criterion documented by operator.
4. Exact file list for a future benchmark_v2 work packet (docs-only reference, not active).
5. Current policy is unambiguous: WAIT_FOR_CRYPTO.

### Task 2: CURRENT_STATE.md and CLAUDE.md Updated

- `docs/CURRENT_STATE.md`: "Next executable step" block replaced with WAIT_FOR_CRYPTO policy
  statement, ADR cross-reference, poll commands, and 2026-04-12 escalation deadline. Corpus
  count (40/50) unchanged.
- `CLAUDE.md`: "Benchmark policy lock" guardrail added after the benchmark pipeline section.
  Lists six prohibited improvisation actions and the escalation deadline. All existing content
  preserved.

### Task 3: Dev Log Created

`docs/dev_logs/2026-03-29_crypto_benchmark_policy_decision.md` — records why the task was
executed, the doc conflict found, the policy decision made, escalation criteria summary,
files changed, files NOT changed (benchmark_v1.* confirmed untouched), and next work packet.

---

## Decision Made

**CURRENT POLICY = WAIT_FOR_CRYPTO**

Rationale: Crypto pair market absence is a scheduling gap, not a platform regime change.
The governing roadmap (POLYTOOL_MASTER_ROADMAP_v5_1.md) requires a human decision to bump
benchmark version, triggered by significant market regime change, major tape quality improvement,
or strategy overhaul. A temporary scheduling gap satisfies none of these.

**Escalation deadline: 2026-04-12** (14 calendar days from 2026-03-29).

---

## Files Created

| File | Purpose |
|---|---|
| `docs/specs/ADR-benchmark-versioning-and-crypto-unavailability.md` | Policy ADR — full decision record |
| `docs/dev_logs/2026-03-29_crypto_benchmark_policy_decision.md` | Mandatory dev log / audit trail |

## Files Updated

| File | Change |
|---|---|
| `docs/CURRENT_STATE.md` | Next-step updated with WAIT_FOR_CRYPTO policy, ADR reference, escalation deadline |
| `CLAUDE.md` | Benchmark policy lock guardrail added (prohibited actions + deadline) |

## Files NOT Touched

| File | Status |
|---|---|
| `config/benchmark_v1.tape_manifest` | IMMUTABLE — not touched |
| `config/benchmark_v1.lock.json` | IMMUTABLE — not touched |
| `config/benchmark_v1.audit.json` | IMMUTABLE — not touched |
| `config/recovery_corpus_v1.tape_manifest` | Not touched |
| All gate tool logic | Not touched |
| All roadmap prose | Not touched |
| All strategy code | Not touched |

---

## Next Work Packet

1. Monitor: `python -m polytool crypto-pair-watch --one-shot`
2. When BTC/ETH/SOL 5m/15m pair markets appear: capture 12-15 sessions per CORPUS_GOLD_CAPTURE_RUNBOOK.md
3. Verify: `python tools/gates/capture_status.py` then `corpus_audit.py`
4. Run Gate 2: `python tools/gates/close_mm_sweep_gate.py --benchmark-manifest config/recovery_corpus_v1.tape_manifest --out artifacts/gates/gate2_sweep`
5. If still absent by 2026-04-12: operator reviews ADR escalation criteria for benchmark_v2 decision

---

## Deviations from Plan

None — plan executed exactly as written. CLAUDE.md did not have a "Crypto bucket blocked" note
prior to this task (it was only in CURRENT_STATE.md), so the guardrail was placed at the end of
the benchmark pipeline section in CLAUDE.md, which is the logical anchor point. The "Crypto
bucket blocked" note was also added to CLAUDE.md for completeness, matching the existing
CURRENT_STATE.md phrasing.

---

## Self-Check: PASSED

- `docs/specs/ADR-benchmark-versioning-and-crypto-unavailability.md` — created, contains "CURRENT POLICY = WAIT_FOR_CRYPTO", "2026-04-12", "Human decision required"
- `docs/CURRENT_STATE.md` — contains "POLICY = WAIT_FOR_CRYPTO", "2026-04-12", "ADR-benchmark-versioning-and-crypto-unavailability", corpus count still 40/50
- `CLAUDE.md` — contains "Benchmark policy lock", "Do NOT: modify", "2026-04-12"
- `docs/dev_logs/2026-03-29_crypto_benchmark_policy_decision.md` — created, contains "WAIT_FOR_CRYPTO", "2026-04-12", "Files NOT Changed" table
- config/benchmark_v1.* files: not mentioned as modified in any of the above
