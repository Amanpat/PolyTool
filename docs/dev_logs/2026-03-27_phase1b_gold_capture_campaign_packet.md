# Dev Log — Phase 1B Gold Capture Campaign Packet

**Date:** 2026-03-27
**Quick task:** 029 — convert-phase-1b-to-clean-operator-captu
**Branch:** phase-1B

---

## What Was Done

Converted Phase 1B from ambiguous blocker state into a clean, documented operator
capture campaign. No code changes to gate logic, strategy, or benchmark_v1.

### Deliverables

1. `docs/specs/SPEC-phase1b-gold-capture-campaign.md` — authoritative campaign spec
   with starting shortage state, bucket quotas, campaign loop, resumability rules,
   and success/failure artifact contracts.

2. `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md` — updated to add Section 0 quick
   status check, remove stale hard-coded counts from Section 7, and add campaign spec
   to reference block. Version bumped to v1.1.

3. `tools/gates/capture_status.py` — read-only quota-status helper. Prints compact
   shortage table (or JSON). Exit 0 when complete, exit 1 when shortage. One command
   to check progress without running the full audit.

4. `tests/test_capture_status.py` — 4 offline deterministic tests.

5. `docs/CURRENT_STATE.md` — updated status header and Gate 2 bullet to reflect
   no-gate-core-changes-needed status and link to campaign packet tools.

### Starting State (as of this task)

- 10/50 tapes qualify for Gate 2
- sports=15 shortage, politics=9, crypto=10, new_market=5, near_resolution=1
- All Silver reconstruction routes exhausted
- Next: operator live Gold shadow capture per CORPUS_GOLD_CAPTURE_RUNBOOK.md

### What Was NOT Changed

- Gate 2 threshold (>= 70%) — unchanged
- min_events=50 — unchanged
- benchmark_v1 artifacts — immutable, untouched
- Strategy (market_maker_v1) — no changes
- Gate 3, Stage 0, Stage 1, Track 2 — not touched

---

## Files Changed

| File | Action | Why |
|------|--------|-----|
| `tools/gates/capture_status.py` | Created | Read-only shortage table helper |
| `tests/test_capture_status.py` | Created | 4 TDD tests for capture_status |
| `docs/specs/SPEC-phase1b-gold-capture-campaign.md` | Created | Authoritative campaign spec |
| `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md` | Updated | Section 0, Section 7 tightening, reference block |
| `docs/CURRENT_STATE.md` | Updated | Status header + Gate 2 bullet |
| `.planning/STATE.md` | Updated | Blockers, last activity, quick tasks table |

---

## Commands Run and Output

### capture_status.py smoke test

```
$ python tools/gates/capture_status.py --tape-roots artifacts/simtrader/tapes --tape-roots artifacts/silver --tape-roots artifacts/tapes

Corpus status: 10 / 50 tapes qualified (40 needed)

Bucket            Quota    Have    Need    Gold  Silver
---------------  ------  ------  ------  ------  ------
sports               15       0      15       0       0
politics             10       1       9       1       0
crypto               10       0      10       0       0
new_market            5       0       5       0       0
near_resolution      10       9       1       0       9
---------------  ------  ------  ------  ------  ------
Total                50      10      40       1       9

Next: run corpus_audit.py after capturing tapes. Gate 2 unblocks at exit 0.
```

Exit code: 1 (shortage)

---

## Tests

- `tests/test_capture_status.py`: 4 tests, all passing
- Full suite regression: 2666 passed, 0 failed, 25 warnings

---

## What Operator Friction Was Reduced

Before this task:
- No single quick-check command existed; operator had to run the full corpus_audit
  (which writes files) just to see current shortage counts
- Section 7 of the runbook had hard-coded shortage numbers from 2026-03-26 that would
  become stale as tapes were captured
- No single-file campaign spec existed; the operator had to piece together guidance
  from multiple documents

After this task:
- One command shows current status: `python tools/gates/capture_status.py`
- Runbook Section 7 always shows current counts (delegates to capture_status.py)
- One authoritative spec (`SPEC-phase1b-gold-capture-campaign.md`) covers the full campaign

---

## Next Operator Action

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

---

## Open Questions / Remaining Human-Only Steps

1. **Market selection**: The operator must browse Polymarket or use
   `python -m polytool simtrader quickrun --list-candidates 10` to identify
   active markets in shortage buckets (sports, politics, crypto, new_market).
   No automation exists for this yet.

2. **sports markets**: Sports tape capture works best during live matches
   (evening/weekend). Timing is operator-determined.

3. **crypto markets**: BTC/ETH/SOL 5m/15m binary pairs are not always active.
   Use `python -m polytool crypto-pair-watch --watch` to detect availability.

4. **Gate 2 outcome**: Gate 2 has not been run against any recovery corpus.
   It will only be attempted after corpus_audit.py exits 0. The outcome
   (PASS/FAIL) is unknown until then.
