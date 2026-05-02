# RIS L3 Pre-fetch Relevance Filter — v0 Close-out

**Date:** 2026-05-02
**Work packet:** L3 Pre-fetch Relevance Filter — Codex re-review close-out
**Author:** operator + Claude Code
**Codex review:** PASS WITH FIXES — see `docs/dev_logs/2026-05-02_codex-rereview-ris-prefetch-filter-v0.md`

---

## Summary

Codex re-review returned PASS WITH FIXES. All original FAIL blockers from the initial
review were resolved in commit `1520e18`. This session closes out the v0 feature with
the completion protocol: feature doc, INDEX update, and CURRENT_DEVELOPMENT move.

v0 ships as **dry-run-ready**. Reject-only enforce is mechanically safe but experimental.
Full enforce-ready status is deferred pending: Scenario A/B policy documentation,
enforce fail-closed behavior, and deeper simulation CLI tests.

---

## Codex Re-review Verdict

| Item | Result |
|------|--------|
| DB-backed Scenario B < 10% | **PASS** — 5.88%, prints `Target <10%: YES` |
| Golden QA false negatives = 0 | **PASS** — DB replay QA REJECT = 0 |
| research-acquire off/dry-run/enforce flags, default off | **PASS** |
| Dry-run logs but does not block; enforce skips only REJECT | **PASS** |
| Audit fields: score, raw_score, thresholds, matched_terms, reason codes | **PASS** |
| No heavy ML deps (no SPECTER2/SVM/sklearn) | **PASS** |
| Docs no longer overclaim title-only 6.25% | **PASS WITH FIXES** |
| Full enforce-ready | **NOT YET** — Scenario A = 20.0%; enforce fails open on scoring errors |

Overall: **PASS WITH FIXES** (4 "Fix Before Full Enforcement" items remain; none block dry-run ship).

---

## Status Changes

| Item | Before | After |
|------|--------|-------|
| Work packet `status` | `active` | `shipped` |
| Work packet "What ships in v0" modes | "Default mode: dry-run / audit; `--enforce-relevance-filter`" | "Default mode: off; `--prefetch-filter-mode {off,dry-run,enforce}`" |
| Work packet "Scope guards" flag | `--enforce-relevance-filter` | `--prefetch-filter-mode enforce` |
| Work packet "Acceptance gates" gate 5/6 | old flag names | corrected flag names + Scenario A/B note |
| Work packet cross-references | activation log only | all 4 L3 dev logs + shipped note |
| CURRENT_DEVELOPMENT Feature 3 | Active (stale wording) | Moved to Recently Completed |
| CURRENT_DEVELOPMENT Notes for Architect | ACTIVE entry with stale flags | COMPLETE entry with correct flags and enforcement readiness |
| Current-Focus L3 row | active — Prompt A next | shipped (dry-run-ready); reject-only enforce experimental |
| Current-Focus session context | 2026-05-01 activation only | 2026-05-02 closeout added |
| INDEX.md Features | no L3 feature doc row | L3 feature doc row added |
| INDEX.md Recent Dev Logs | missing activation + Codex review/re-review logs | 4 missing rows added |

---

## Final Metrics (DB-backed, v1.1 thresholds)

| Metric | Value |
|--------|-------|
| Filter config version | v1.1 (allow_threshold=0.80, review_threshold=0.35) |
| Corpus | 23 papers (L5 v0) |
| ALLOW / REVIEW / REJECT | 17 / 3 / 3 |
| Baseline off_topic_rate | 30.43% (7/23) |
| Scenario A (reject-only enforcement) | 20.0% (4/20 off-topic) |
| Scenario B (allow-only simulation) | **5.88%** (1/17 off-topic) |
| Target <10% met (Scenario B) | **YES** |
| QA papers in REJECT | **0** (false negatives = 0) |
| QA papers in REVIEW | 1 (borderline; not blocked in any mode) |
| Tests | 113 passed, 0 failed |

---

## Title-Only Overclaim Correction

The initial cold-start dev log (`2026-05-02_ris-prefetch-filter-coldstart.md`) estimated
Scenario B = 6.25% based on title-only scoring. The actual DB-backed run (first Codex FAIL)
returned 20.0% because broad positive terms like `financial market`, `microstructure`,
and `liquidity` pushed borderline off-topic papers above the 0.55 threshold via abstracts.

**Corrected record:**
- Title-only estimate (v1, allow=0.55): Scenario B ≈ 6.25% (never DB-confirmed)
- DB-backed v1 (allow=0.55): Scenario B = 20.0% — Codex FAIL
- DB-backed v1.1 (allow=0.80): Scenario B = 5.88% — Codex PASS

The cold-start dev log has a NOTE block (added in the fix pass) documenting this.
The INDEX dev log rows distinguish the two runs.

---

## Filter Mode Correction (stale wording in docs)

The original work packet and CURRENT_DEVELOPMENT said "default dry-run/audit" and
`--enforce-relevance-filter`. The actual shipped behavior is:

| Wording | Old (stale) | Correct |
|---------|-------------|---------|
| Default mode | `dry-run / audit` | `off` (filter not invoked) |
| Blocking flag | `--enforce-relevance-filter` | `--prefetch-filter-mode enforce` |
| Audit-only flag | (not named) | `--prefetch-filter-mode dry-run` |

All stale references updated in this closeout pass.

---

## Enforcement Readiness Record

| Mode | Status | Evidence |
|------|--------|----------|
| `dry-run` | Safe now | Codex confirmed; logs decisions; no blocking |
| `enforce` (reject-only) | Mechanically safe — experimental | DB: QA REJECT=0; corresponds to Scenario A (20.0%); not the <10% gate |
| Full enforce-ready | Not yet | Scenario A ≠ Scenario B; enforce fails open on scoring/config errors |

**Do not claim reject-only enforcement achieves the <10% gate.** The correct framing is:
"v1.1 meets the allow-only simulation target (Scenario B 5.88%); reject-only enforcement
removes only the 3 clear negatives (Scenario A 20.0%)."

---

## Deferred Items (non-blocking at close-out)

| Item | Status | Path |
|------|--------|------|
| Label store empty file | Deferred | `artifacts/research/svm_filter_labels/labels.jsonl` |
| research-health label_count | Deferred | `tools/cli/research_health.py` |
| Enforce fail-closed on scoring errors | Open question | `tools/cli/research_acquire.py` |
| Deeper simulation CLI output assertions | Non-blocking | `tests/test_ris_eval_benchmark.py` |

---

## Files Updated (this close-out pass)

| File | Change |
|------|--------|
| `docs/features/FEATURE-ris-prefetch-relevance-filter-v0.md` | **Created** — full feature doc with DB-backed results, enforcement readiness, deferred items |
| `docs/dev_logs/2026-05-02_ris-prefetch-filter-v0-closeout.md` | **This file** |
| `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Pre-fetch SVM Topic Filter.md` | Updated: status shipped; corrected filter mode wording; added shipped results section; added enforcement readiness note; updated cross-references |
| `docs/CURRENT_DEVELOPMENT.md` | Feature 3 moved to Recently Completed; Notes updated with COMPLETE status, correct flags, enforcement readiness |
| `docs/obsidian-vault/Claude Desktop/Current-Focus.md` | L3 row updated to shipped; session context for 2026-05-02 added; date bumped |
| `docs/INDEX.md` | Feature doc row added; 4 missing dev log rows added |

---

## Open Questions for Operator

1. **Enforce mode policy**: Should `--prefetch-filter-mode enforce` fail closed when the
   filter config is missing or scoring throws? Currently fails open (warning + proceeds).
   Low risk pre-production but worth deciding before enabling enforce in daily ingest.

2. **REVIEW routing in enforce mode**: Currently REVIEW papers are ingested with an audit
   flag but proceed normally. Should they instead route to the operator YELLOW queue for
   manual accept/reject? This would be the clean v1 design but adds workflow overhead.

3. **v1 trigger timing**: The v1 upgrade to SPECTER2/SVM requires ≥30 accept + ≥30 reject
   labels. Run `--prefetch-filter-mode dry-run` on new ingest sessions to begin accumulating
   audit data toward this threshold.

---

## Next Recommended Packet

With L3 v0 shipped:
- L4 (Multi-source Academic Harvesters) is now unblocked in principle (activation gated
  on L1 production + L3 working — L3 is now working in dry-run mode).
- However, CURRENT_DEVELOPMENT max-3 Active rule still applies.
- Recommendation: run L3 in dry-run for several ingest sessions to accumulate filter
  audit data, then evaluate whether to promote to enforce or proceed to L4.

No new Active feature until Feature 1 or Feature 2 slot clears.
