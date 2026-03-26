# Phase 1B Corpus Recovery — Dev Log

**Date:** 2026-03-26
**Branch:** phase-1B
**Quick task:** 027 — recover-phase-1b-corpus-recovery-spec-ta
**Author:** Claude Code

---

## Objective

Build the tooling and spec to create a recovery corpus separate from the
finalized `benchmark_v1`, quantify the current shortage, and direct the
operator to the correct next action (Gold shadow tape capture).

---

## Files Changed and Why

| File | Action | Reason |
|------|--------|--------|
| `docs/specs/SPEC-phase1b-corpus-recovery-v1.md` | Created | Authoritative contract for recovery corpus admission rules, manifest versioning, Gate 2 rerun preconditions |
| `tools/gates/corpus_audit.py` | Created | Scans tape inventory, applies admission rules, writes recovery manifest or shortage report |
| `tests/test_corpus_audit.py` | Created | 6 TDD tests covering all admission rule paths |
| `artifacts/corpus_audit/shortage_report.md` | Created (by tool) | Quantifies exact shortage per bucket for operator action |
| `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md` | Created | Step-by-step operator guide for capturing Gold shadow tapes |
| `docs/CURRENT_STATE.md` | Updated | Gate 2 section updated with recovery tooling references |
| `.planning/STATE.md` | Updated | quick-027 row added, blocker updated |

---

## Commands Run and Output

### Corpus Audit Execution

```
python tools/gates/corpus_audit.py \
    --tape-roots artifacts/simtrader/tapes \
    --tape-roots artifacts/silver \
    --tape-roots artifacts/tapes \
    --out-dir artifacts/corpus_audit \
    --manifest-out config/recovery_corpus_v1.tape_manifest
```

**Output:**
```
============================================================
Corpus Audit Summary
============================================================
Total scanned:   137
Total accepted:  9 / 50 needed
Total rejected:  128

Accepted by bucket:
  crypto               0 / 10  NEED 10 more
  near_resolution      9 / 10  NEED 1 more
  new_market           0 / 5  NEED 5 more
  politics             0 / 10  NEED 10 more
  sports               0 / 15  NEED 15 more

Verdict: SHORTAGE (exit 1)
============================================================
```

**Exit code:** 1 (shortage)

### Gate Status

```
python tools/gates/gate_status.py
```

Gate 2 shows FAILED (pre-existing from prior run). `mm_sweep_gate` sub-gate
shows NOT_RUN. Gate 2 was NOT rerun in this task because the corpus is
insufficient.

---

## Tests Run and Pass/Fail Counts

### Targeted test run (corpus_audit)

```
python -m pytest tests/test_corpus_audit.py -x -q --tb=short
```

**Result:** 6 passed, 0 failed

### Full regression suite

```
python -m pytest tests/ -x -q --tb=short
```

**Result:** 2662 passed, 0 failed, 25 warnings

No regressions introduced.

---

## benchmark_v1 Preservation Decision

**benchmark_v1 lock/audit/manifest were NOT modified.**

The following files were verified to be unchanged:
- `config/benchmark_v1.tape_manifest`
- `config/benchmark_v1.lock.json`
- `config/benchmark_v1.audit.json`

This is explicitly confirmed by code design: `corpus_audit.py` only writes to
`config/recovery_corpus_v1.tape_manifest` and `artifacts/corpus_audit/`, and
never reads or writes the `benchmark_v1` files.

---

## Recovery Manifest Path vs Shortage Report Path

**Branch taken: SHORTAGE**

- `config/recovery_corpus_v1.tape_manifest` — **NOT written** (corpus insufficient)
- `artifacts/corpus_audit/shortage_report.md` — **WRITTEN** with exact counts

---

## Qualified Tape Counts by Bucket and Tier

| Bucket          | Quota | Qualified | Tier     | Shortage |
|-----------------|------:|----------:|----------|----------|
| politics        |    10 |         0 | -        | 10       |
| sports          |    15 |         0 | -        | 15       |
| crypto          |    10 |         0 | -        | 10       |
| near_resolution |    10 |         9 | Silver   | 1        |
| new_market      |     5 |         0 | -        | 5        |
| **Total**       |**50** |     **9** |          | **41**   |

All 9 qualifying tapes are Silver, in the `near_resolution` bucket. They have
>= 50 effective events. No Gold tapes currently qualify.

The 128 rejected tapes break down as follows:
- 119 tapes: `too_short` (effective_events < 50)
- 9 tapes: `no_bucket_label` (no metadata yielding a valid bucket label)

---

## Whether Gate 2 Was Rerun

**Gate 2 was NOT rerun.**

The corpus is insufficient (9/50 tapes qualify, all 5 buckets must be
represented). Attempting Gate 2 rerun on this corpus would produce another
NOT_RUN verdict. The shortage must be resolved first.

---

## Exact Blocker for Next Phase

**Blocker:** Corpus has only 9 qualifying tapes (need 50). Specifically:
- `near_resolution`: 9/10 — needs 1 more tape with >= 50 effective events
- `crypto`: 0/10 — needs 10 tapes (best captured from BTC/ETH/SOL 5m markets)
- `new_market`: 0/5 — needs 5 tapes (newly listed markets)
- `politics`: 0/10 — needs 10 tapes (election/political markets)
- `sports`: 0/15 — needs 15 tapes (NHL/NBA/NFL/soccer)

**Resolution path:**
1. Use `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md` to capture Gold shadow
   tapes for each shortage bucket.
2. Re-run `corpus_audit.py` after each batch to check progress.
3. When `corpus_audit.py` exits 0, `config/recovery_corpus_v1.tape_manifest`
   is written and Gate 2 rerun is unblocked.

Track 2 (crypto pair bot) market availability remains a separate blocker:
no active BTC/ETH/SOL 5m/15m binary pair markets on Polymarket as of 2026-03-25.
Use `crypto-pair-watch --watch` to poll.
