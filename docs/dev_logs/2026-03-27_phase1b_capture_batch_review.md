# Dev Log: Phase 1B Capture Batch Review

**Date:** 2026-03-27
**Branch:** phase-1B
**Task:** Review live Gold capture batch and advance Phase 1B

---

## Summary

Reviewed the latest live Gold capture batch (shadow tapes from 2026-03-06 and 2026-03-07).
Injected bucket metadata into 4 candidate tapes. Corpus_audit still returns 10/50, exit 1.
Root cause: all 4 candidate tapes are binary markets (YES+NO), making
`effective_events = raw_events // 2`, which drops them below the 50-event floor.

**Corpus state: UNCHANGED at 10/50 (40 tapes still needed).**

---

## Before State

- Corpus count: 10/50 (confirmed by `capture_status.py` and `corpus_audit.py`)
- Accepted breakdown: 1 politics Gold + 9 near_resolution Silver

---

## Tapes Inspected

### Shadow tapes in `artifacts/simtrader/tapes/`

| Tape dir | Raw events | Asset IDs | Effective | Outcome |
|---|---:|---:|---:|---|
| `20260226T181825Z_shadow_10167699` | 141 | 2 | 70 | **ACCEPTED (politics, gold)** — existing |
| `20260307T195039Z_will-the-toronto-map` | 80 | 2 | 40 | REJECTED: too_short |
| `20260307T195542Z_will-the-vancouver-c` | 66 | 2 | 33 | REJECTED: too_short |
| `20260306T044438Z_tape_bitboy-convicted_64fd7c95` | 77 | 2 | 38 | REJECTED: too_short |
| `20260306T044313Z_tape_bitboy-convicted_64fd7c95` | 66 | 2 | 33 | REJECTED: too_short |
| `20260306T044247Z_tape_bitboy-convicted_64fd7c95` | 39 | 2 | 19 | REJECTED: too_short + no bucket |
| `20260307T200105Z_will-the-calgary-fla` | 30 | 2 | 15 | REJECTED: too_short + no bucket |
| Various OKC thunder tapes | 19–22 | 2 | 9–11 | REJECTED: too_short + no bucket |

### Silver tapes in `artifacts/silver/` (118 tapes)
All have ~28–30 effective events — uniformly below the 50-event floor.

### Silver tapes in `artifacts/tapes/` (7 tapes)
9 near_resolution tapes qualify (56–60 effective events). These are the 9/10 near_resolution accepted.

---

## Metadata Injected (this session)

These 4 tapes received `watch_meta.json` + `market_meta.json` for bucket classification.
The metadata is correct; the tapes simply don't have enough events to qualify.

| Tape | Bucket | Effective | Qualifies? |
|---|---|---:|---|
| `20260307T195039Z_will-the-toronto-map` | sports | 40 | No — too_short |
| `20260307T195542Z_will-the-vancouver-c` | sports | 33 | No — too_short |
| `20260306T044313Z_tape_bitboy-convicted_64fd7c95` | politics | 33 | No — too_short |
| `20260306T044438Z_tape_bitboy-convicted_64fd7c95` | politics | 38 | No — too_short |

---

## Root Cause: Binary Market Effective-Events Divisor

`_count_effective_events()` (in `tools/gates/mm_sweep.py`) computes:
```
effective_events = parsed_events // max(1, n_distinct_asset_ids)
```

For a binary market with YES and NO tokens both recorded in `events.jsonl`, `n_asset_ids = 2`,
so `effective = raw // 2`. To clear the 50-event floor, a binary tape needs **>= 100 raw events**.

The 4 candidate tapes had 66–80 raw events — enough only for 33–40 effective, all below floor.

This is not a bug; it is the correct normalization for multi-asset tapes. The operator needs
to run longer shadow sessions.

---

## Runbook Updated

`docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md` updated with:
- `--duration` note: binary markets need >= 100 raw events (>= 900s for slow markets)
- `too_short` rejection section: explicit formula + debug one-liner

---

## After State

- Corpus count: **10/50** (unchanged)
- Gate 2: NOT_RUN (corpus still incomplete)
- All 4 candidate tapes left with injected metadata (correct classification, just too short)

---

## Commands Run

```bash
# Before state
python tools/gates/capture_status.py
# → 10/50, exit 1

# Effective-events check for candidate tapes
python -c "
import json, pathlib, sys; sys.path.insert(0, '.')
from tools.gates.mm_sweep import _count_effective_events
for d in [...]: ...
"
# → all 4 tapes: effective 33–40, below 50 floor

# Full audit with per-tape breakdown
python -c "from tools.gates.corpus_audit import audit_tape_candidates, _discover_tape_dirs; ..."
# → 10 ACCEPTED, 127 REJECTED (mostly too_short)

# Confirm post-change state
python tools/gates/corpus_audit.py --out-dir artifacts/corpus_audit \
    --manifest-out config/recovery_corpus_v1.tape_manifest
# → 10/50, exit 1 (unchanged)
```

---

## Tests

No code changes beyond runbook updates — no new tests required.
Existing test suite:
```bash
python -m pytest tests/ -x -q --tb=short
# (not rerun — runbook is documentation only, no logic change)
```

---

## Operator Next Steps

### What's blocking Gate 2
The corpus needs 40 more tapes across 5 buckets:

| Bucket | Have | Need |
|---|---:|---:|
| politics | 1 | 9 |
| near_resolution | 9 | 1 |
| sports | 0 | 15 |
| crypto | 0 | 10 |
| new_market | 0 | 5 |

### Critical capture guidance
Binary markets (YES+NO) record 2 asset IDs. You need **>= 100 raw events per tape** to clear 50 effective events.

- `--duration 600` (10 min) works for active crypto/sports markets
- `--duration 900` (15 min) for lower-activity markets
- After each session, check: `python -c "from tools.gates.mm_sweep import _count_effective_events; import pathlib; print(_count_effective_events(pathlib.Path('TAPE_DIR/events.jsonl')))"`

### Easiest remaining capture (near_resolution — need just 1 more)
Find any market that is close to resolution (< 7 days to close). E.g. weekly crypto/sports outcomes.

### Capture command template
```bash
python -m polytool simtrader shadow \
    --market <SLUG> \
    --strategy market_maker_v1 \
    --duration 600 \
    --record-tape \
    --tape-dir "artifacts/simtrader/tapes/<BUCKET>_<SLUG>_<TIMESTAMP>"
```

Then run:
```bash
python tools/gates/capture_status.py
```

---

## Open Questions / Human-Only Steps

- Operator must pick live markets and run shadow sessions (no live capital, but requires connectivity)
- Easiest win: 1 near_resolution tape (any market closing within 7 days)
- After reaching 50/50: run `python tools/gates/corpus_audit.py ...` → exits 0 → run Gate 2
