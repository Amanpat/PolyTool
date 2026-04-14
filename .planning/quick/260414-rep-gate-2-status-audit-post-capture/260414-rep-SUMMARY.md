---
phase: quick-260414-rep
plan: "01"
subsystem: gate2-corpus
tags: [gate2, corpus, audit, crypto, status]
dependency_graph:
  requires: []
  provides: [gate2-status-audit]
  affects: [gate2-corpus, crypto-pair-bot, benchmark-policy]
tech_stack:
  added: []
  patterns: [read-only-audit, evidence-pack]
key_files:
  created:
    - docs/dev_logs/2026-04-14_gate2_status_audit_post_capture.md
  modified: []
decisions:
  - "Verdict RESUME_CRYPTO_CAPTURE: crypto markets are live (12 eligible 5m markets), corpus is complete 50/50, ADR WAIT_FOR_CRYPTO waiting period ended -- Gate 2 FAILED is now the active blocker"
  - "crypto-pair-watch --one-shot does not exist in current CLI; default invocation is functionally equivalent (single poll, exits)"
  - "CLAUDE.md benchmark policy lock section is stale: says corpus 10/50 NOT_RUN; truth is 50/50 COMPLETE and Gate 2 FAILED"
metrics:
  duration: "~10 minutes"
  completed_date: "2026-04-14"
  tasks_completed: 1
  tasks_total: 1
  files_created: 1
  files_modified: 0
---

# Phase quick-260414-rep Plan 01: Gate 2 Status Audit Post-Capture Summary

**One-liner:** Read-only Gate 2 evidence audit finding corpus complete (50/50), crypto markets live (12 5m markets), ADR deadline passed, and Gate 2 FAILED (7/50) as the active blocker requiring operator decision.

---

## Objective

Answer four questions from authoritative repo tools: (1) Are qualifying crypto pair markets live? (2) What is the current corpus shortage? (3) Is recovery_corpus_v1 blocked only by crypto? (4) Which docs are stale or conflicting?

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Read-only status commands and dev log | e594b1d | docs/dev_logs/2026-04-14_gate2_status_audit_post_capture.md |

---

## Key Findings

### Q1: Are qualifying BTC/ETH/SOL 5m/15m crypto pair markets live right now?

**YES.** 12 eligible 5m markets active as of 2026-04-14T23:47 UTC (BTC=4, ETH=4, SOL=4). No 15m markets. `crypto-pair-watch` exits 0.

### Q2: Current recovery corpus shortage by bucket?

**NONE -- corpus is COMPLETE (50/50, exit 0).** All five buckets filled: politics=10, sports=15, crypto=10, near_resolution=10, new_market=5. 41 Gold tapes, 9 Silver tapes (all in near_resolution).

### Q3: Is recovery_corpus_v1 blocked only by crypto or has other issues?

**Not blocked by crypto (bucket complete). Has a structural Silver tape issue.** The near_resolution bucket has 9/10 Silver tapes. Silver tapes produce zero fills (no L2 book data, confirmed by gate2_fill_diagnosis). Gate 2 re-sweep will again see near-zero fills on these 9 tapes. This is NOT a corpus count problem -- it is a data quality problem within the corpus that cannot be fixed without recapturing 9 near_resolution tapes as Gold.

### Q4: Which repo docs are stale or conflicting about Gate 2 state/policy?

**Multiple stale docs identified:**
- **CLAUDE.md** (benchmark policy lock section): says "corpus has only 10/50 qualifying tapes", "Gate 2 is currently NOT_RUN". Truth: 50/50 COMPLETE and Gate 2 FAILED.
- **CLAUDE.md**: references `--one-shot` flag that does not exist in current `crypto-pair-watch` CLI.
- **CLAUDE.md**: Silver tier described as "good for Gate 2" -- contradicts confirmed zero-fill behavior.
- **CORPUS_GOLD_CAPTURE_RUNBOOK.md**: shadow tape path `artifacts/simtrader/tapes/` is stale (changed to `artifacts/tapes/shadow/` in quick-260414-qre).
- **SPEC-phase1b-gold-capture-campaign.md** corpus_audit call includes `--tape-roots artifacts/simtrader/tapes` (stale path).

**Currently accurate:**
- `docs/CURRENT_STATE.md` § "Status as of 2026-03-29": Gate 2 FAILED, 7/50, 14% -- still the last run result.
- ADR: historical snapshot accurate for 2026-03-29. The ADR is a decision record, not a living doc.

---

## Verdict

**RESUME_CRYPTO_CAPTURE**

Crypto markets are live. The recovery corpus is complete. The ADR WAIT_FOR_CRYPTO waiting period ended when markets returned. The crypto absence escalation scenario (benchmark_v2 for market unavailability) did NOT trigger in practice. The current active blocker is Gate 2 FAILED (7/50 = 14%) which requires an operator path decision:

1. Re-run Gate 2 sweep with full 50-tape corpus (not done yet with complete corpus)
2. Crypto-only subset test (7/10 = 70%; needs spec change)
3. Defer Gate 2; focus on Track 2 crypto pair bot (now unblocked from market availability perspective)

---

## Deviations from Plan

### Auto-noted issues

**1. [Rule 2 - Missing Doc Fact] `--one-shot` flag does not exist**
- **Found during:** Task 1 (running crypto-pair-watch)
- **Issue:** CLAUDE.md and plan template reference `python -m polytool crypto-pair-watch --one-shot` but this flag does not exist (exit 2: unrecognized arguments). The default invocation (no `--watch`) performs a single poll and exits -- functionally equivalent.
- **Action:** Documented in dev log. Not fixed (read-only audit; doc fix deferred to recommended next packet).
- **Commit:** n/a (no code change)

**2. [Rule 2 - Clarification] Verdict label selection**
- The plan defines three possible verdicts. The precise BENCHMARK_V2_DECISION_PRECONDITIONS_MET label was considered (deadline passed, crypto markets absent for >14 days from ADR baseline). However, markets returned before action was taken, making the primary ADR escalation criterion moot. RESUME_CRYPTO_CAPTURE was selected because it reflects the forward signal: markets are live, corpus is done, waiting period is over. The dev log notes this interpretation explicitly.

---

## Self-Check: PASSED

- [x] `docs/dev_logs/2026-04-14_gate2_status_audit_post_capture.md` -- EXISTS
- [x] Commit e594b1d exists in git log
- [x] No code changes, no benchmark files touched, no benchmark_v2 created
- [x] Verdict label present in dev log (RESUME_CRYPTO_CAPTURE)
- [x] All three commands run with exact output recorded
- [x] ADR deadline analysis (2026-04-12) present
