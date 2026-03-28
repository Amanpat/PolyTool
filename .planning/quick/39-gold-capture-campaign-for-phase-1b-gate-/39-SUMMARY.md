---
phase: quick
plan: 39
subsystem: corpus
tags: [gate2, gold-capture, shadow-recording, tape-corpus, path-drift]

# Dependency graph
requires:
  - phase: quick-027
    provides: corpus_audit.py tooling and capture runbook
  - phase: quick-036
    provides: artifacts directory restructure (canonical tape paths)

provides:
  - 17 new qualifying Gold tapes (10 sports, 6 politics, 1 near_resolution)
  - Corpus advanced from 10/50 to 27/50 qualifying tapes
  - Path drift root cause documented (shadow tapes wrote to artifacts/simtrader/tapes/ not artifacts/tapes/shadow/)
  - 96 tape directories migrated to canonical artifacts/tapes/shadow/ path
  - Updated shortage_report.md reflecting post-campaign state
  - Dev log at docs/dev_logs/2026-03-28_gold_capture_campaign.md

affects: [gate2-corpus, corpus-audit, shadow-capture, gate2-readiness]

# Tech tracking
tech-stack:
  patterns:
    - Shadow capture: simtrader shadow --record-tape writes events.jsonl to tape dir
    - corpus_audit.py: scans --tape-roots, counts effective_events, classifies by bucket
    - Effective events for binary markets: raw_count // 2 (YES+NO tokens counted separately)
    - Min threshold: 50 effective events (= 100+ raw events for binary markets)

key-files:
  modified:
    - artifacts/tapes/shadow/ (96 tape dirs migrated from artifacts/simtrader/tapes/)
    - artifacts/corpus_audit/shortage_report.md (regenerated post-migration)
  created:
    - docs/dev_logs/2026-03-28_gold_capture_campaign.md

key-decisions:
  - "Path drift fix: moved all 96 shadow tape dirs from artifacts/simtrader/tapes/ to artifacts/tapes/shadow/ so corpus_audit default roots pick them up"
  - "No code changes made — capture, migration, and audit used existing CLI/scripts only"
  - "crypto and new_market buckets remain at 0 due to market unavailability (Polymarket has no active BTC/ETH/SOL pair markets)"

# Metrics
duration: ~3h (capture sessions + migration + audit)
completed: 2026-03-28
---

# Quick Task 39: Gold Capture Campaign for Phase 1B Gate 2 — Summary

**Campaign advanced corpus from 10/50 to 27/50 qualifying tapes. Decision: MORE_GOLD_NEEDED (23 tapes still required).**

## Performance

- **Duration:** ~3h
- **Completed:** 2026-03-28
- **Sessions run:** ~96 shadow recording sessions
- **Tapes migrated:** 96 directories moved to canonical path

## Accomplishments

- **17 new qualifying Gold tapes** captured across sports (10) and politics (6), plus 1 near_resolution
- **Path drift root cause identified and resolved:** `simtrader shadow` CLI was writing to `artifacts/simtrader/tapes/` (the `DEFAULT_ARTIFACTS_DIR` default), but `corpus_audit.py` default roots only scan `artifacts/tapes/{gold,silver}`. All 96 captured tape directories were migrated to `artifacts/tapes/shadow/` so the default audit picks them up.
- **near_resolution bucket: COMPLETE** (10/10 — the 9 Silver tapes from reconstruction + 1 new Gold)
- **Shortage report updated** in `artifacts/corpus_audit/shortage_report.md`

## Pre-Campaign vs Post-Campaign

| Bucket         | Before | After | Gained |
|----------------|-------:|------:|-------:|
| sports         |      0 |    10 |    +10 |
| politics       |      1 |     7 |     +6 |
| crypto         |      0 |     0 |      0 |
| new_market     |      0 |     0 |      0 |
| near_resolution|      9 |    10 |     +1 |
| **Total**      |     10 |    27 |    +17 |

## Final Decision: MORE_GOLD_NEEDED

27/50 qualify. 23 more tapes needed:

| Bucket     | Still Needed | Blocker |
|------------|-------------:|---------|
| crypto     |           10 | No active BTC/ETH/SOL pair markets on Polymarket |
| sports     |            5 | Need active game fixtures |
| new_market |            5 | Need recently listed markets (<7 days) |
| politics   |            3 | Need active US political markets |

## Next Command

```bash
# Check current shortage
python tools/gates/capture_status.py

# Poll for crypto markets (when available)
python -m polytool crypto-pair-watch --one-shot

# Capture remaining buckets (sports, new_market, politics)
python -m polytool simtrader shadow --market <SLUG> --strategy market_maker_v1 --duration 600 --record-tape

# When capture_status exits 0, run Gate 2:
python tools/gates/close_mm_sweep_gate.py \
    --benchmark-manifest config/recovery_corpus_v1.tape_manifest \
    --out artifacts/gates/gate2_sweep
```

## Open Items

1. **Crypto bucket blocked:** Polymarket has no active BTC/ETH/SOL 5m/15m binary markets as of 2026-03-25. 10 tapes blocked until market schedule rotates them back. Monitor with `crypto-pair-watch --watch`.
2. **Shadow path drift (future cleanup):** `DEFAULT_ARTIFACTS_DIR` in `tools/cli/simtrader.py` still points to `artifacts/simtrader`. A future quick task could update the default to `artifacts/tapes/shadow/` to prevent recurrence.

---
*Phase: quick*
*Completed: 2026-03-28*
