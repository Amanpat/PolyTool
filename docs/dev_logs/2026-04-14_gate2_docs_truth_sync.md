# Gate 2 Docs Truth Sync (2026-04-14)

**Date:** 2026-04-14
**Task ID:** quick-260414-rr3
**Status:** COMPLETE

---

## Summary

Docs-only truth-sync pass correcting four staleness categories found by the
quick-260414-rep status audit. No code, tests, manifests, or benchmark files
were touched.

---

## Files Changed

| File | Change |
|------|--------|
| `CLAUDE.md` | Silver tier description: removed "good for Gate 2"; added explicit Gate 2 unsuitability warning |
| `docs/specs/SPEC-phase1b-gold-capture-campaign.md` | Section 4 corpus_audit path + Section 5 prose: `artifacts/simtrader/tapes` → `artifacts/tapes/shadow` |
| `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md` | Sections 3, 4 (x3 occurrences), and 5: `artifacts/simtrader/tapes` → `artifacts/tapes/shadow` |

---

## Per-File Change Details

### CLAUDE.md — Tape Tiers section (line ~232)

**Stale text removed:**
```
- **Silver**: reconstructed tapes from pmxt + Jon-Becker + polymarket-apis, good for Gate 2 and autoresearch.
```

**Correct text added:**
```
- **Silver**: reconstructed tapes from pmxt + Jon-Becker + polymarket-apis, useful for autoresearch and price history; NOT suitable for Gate 2 sweep (no L2 book data — fills will be zero).
```

**Rationale:** gate2_fill_diagnosis (2026-04-14) confirmed Silver tapes contain
only `price_2min_guide` events. `L2Book` never initializes. Fill engine returns
`book_not_initialized` on every tick. The phrase "good for Gate 2" was factually
incorrect; this change prevents future sessions from treating Silver as Gate 2 viable.

---

### SPEC-phase1b-gold-capture-campaign.md — Section 4, Step 3

**Stale text removed:**
```
   python tools/gates/corpus_audit.py \
       --tape-roots artifacts/simtrader/tapes \
```

**Correct text added:**
```
   python tools/gates/corpus_audit.py \
       --tape-roots artifacts/tapes/shadow \
```

**Rationale:** gold_capture_hardening (quick-260414-qre, 2026-04-14) changed the
default shadow tape write path from `artifacts/simtrader/tapes/` to
`artifacts/tapes/shadow/`. The old root was absent from corpus_audit's scan,
causing captured tapes to be invisible to the audit tool.

---

### SPEC-phase1b-gold-capture-campaign.md — Section 5, first paragraph

**Stale text removed:**
```
Each shadow session writes to a new timestamped tape directory under
`artifacts/simtrader/tapes/`. No prior capture session is overwritten.
```

**Correct text added:**
```
Each shadow session writes to a new timestamped tape directory under
`artifacts/tapes/shadow/`. No prior capture session is overwritten.
```

---

### CORPUS_GOLD_CAPTURE_RUNBOOK.md — Section 3 corpus_audit call

**Stale `--tape-roots` argument:**
```
    --tape-roots artifacts/simtrader/tapes \
```

**Correct:**
```
    --tape-roots artifacts/tapes/shadow \
```

---

### CORPUS_GOLD_CAPTURE_RUNBOOK.md — Section 4 shadow capture command template

**Stale `--tape-dir` template:**
```
    --tape-dir artifacts/simtrader/tapes/<BUCKET>_<SLUG>_<YYYYMMDDTHHMMSSZ>
```

**Correct:**
```
    --tape-dir artifacts/tapes/shadow/<BUCKET>_<SLUG>_<YYYYMMDDTHHMMSSZ>
```

---

### CORPUS_GOLD_CAPTURE_RUNBOOK.md — Section 4 `--tape-dir` required arguments bullet

**Stale:**
```
- `--tape-dir ...`: Timestamped dir under `artifacts/simtrader/tapes/`
```

**Correct:**
```
- `--tape-dir ...`: Timestamped dir under `artifacts/tapes/shadow/` (omit to use auto-routed default)
```

---

### CORPUS_GOLD_CAPTURE_RUNBOOK.md — Section 4 example command

**Stale `--tape-dir` value:**
```
    --tape-dir "artifacts/simtrader/tapes/crypto_will-btc-be-above-100k_20260326T210000Z"
```

**Correct:**
```
    --tape-dir "artifacts/tapes/shadow/crypto_will-btc-be-above-100k_20260326T210000Z"
```

---

### CORPUS_GOLD_CAPTURE_RUNBOOK.md — Section 5 post-capture corpus_audit call

**Stale `--tape-roots` argument:**
```
    --tape-roots artifacts/simtrader/tapes \
```

**Correct:**
```
    --tape-roots artifacts/tapes/shadow \
```

---

## Verification Commands and Output

```
grep "NOT suitable for Gate 2" CLAUDE.md
```
Output: `- **Silver**: ... NOT suitable for Gate 2 sweep (no L2 book data — fills will be zero).`

```
grep "artifacts/tapes/shadow" docs/specs/SPEC-phase1b-gold-capture-campaign.md
```
Output: 2 matching lines (Section 4 corpus_audit arg, Section 5 prose).

```
grep -c "artifacts/tapes/shadow" docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md
```
Output: `5`

```
! grep "artifacts/simtrader/tapes" docs/specs/SPEC-phase1b-gold-capture-campaign.md
```
Output: exit 0 (no stale paths remain in SPEC).

```
! grep "artifacts/simtrader/tapes" docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md
```
Output: exit 0 (no stale paths remain in RUNBOOK).

```
! grep "good for Gate 2" CLAUDE.md
```
Output: exit 0 (phrase no longer present).

---

## Known Ambiguities Left for Operator / Post-Re-Sweep Resolution

**1. SPEC Section 1 "Gate 2 is in NOT_RUN state"**

SPEC Section 1 still reads: "Gate 2 is in NOT_RUN state (corpus gap is informational,
not a gate failure)." This is historical context describing the campaign's starting
condition (2026-03-27). It is accurate for what the SPEC governs (the capture campaign
itself). The live gate status is owned by `docs/CURRENT_STATE.md` and `gate_status.py`,
not by the SPEC. This is not a staleness bug.

**2. ADR-benchmark-versioning-and-crypto-unavailability.md escalation deadline note**

The ADR records the decision made on 2026-03-29 including an escalation deadline of
2026-04-12. That deadline has now passed (2026-04-14) and crypto markets returned before
operator action was taken. The ADR is a historical decision record — annotating it with
a post-deadline addendum is an operator decision, not a mechanical doc sync. The
quick-260414-rep audit (Status Audit) already documents the ADR reconciliation analysis
in full. No change to the ADR is made in this pass.

**3. CLAUDE.md `--one-shot` flag reference**

`python -m polytool crypto-pair-watch --one-shot` is referenced in CLAUDE.md but the
flag does not exist in the current CLI (unrecognized argument, exit 2). This is a
separate staleness item from this pass's scope. Flagged for a future targeted fix.

---

## Commit

- Task 1 commit: `43a2664` — docs(260414-rr3-01): fix Silver Gate 2 warning and stale shadow tape paths

---

## Codex Review

Tier: Skip (docs only — no execution logic, no order placement, no ClickHouse writes,
no kill-switch or risk manager changes).
