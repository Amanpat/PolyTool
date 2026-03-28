# 2026-03-28 Phase 1B Truth Sync -- Roadmap Checkbox Update (quick-038)

## Summary

Doc-only session. No implementation code changed. Synced roadmap v5_1 checkbox states to
repo artifact truth, reconciled CURRENT_STATE.md and CLAUDE.md drift from quick-036 and
quick-037, and added a clear "next executable step" note to CURRENT_STATE.md.

## Checkboxes Flipped ([ ] -> [x])

| Item | Phase | Evidence |
|------|-------|----------|
| Rebuild CLAUDE.md | Phase 0 | CLAUDE.md is 416 lines with all required sections |
| Write docs/OPERATOR_SETUP_GUIDE.md | Phase 0 | File exists at docs/OPERATOR_SETUP_GUIDE.md |
| MarketMakerV1 -- Logit A-S upgrade | Phase 1B | packages/polymarket/simtrader/strategies/market_maker_v1.py; canonical per SPEC-0012 update (quick-026) |
| Benchmark tape set -- benchmark_v1 | Phase 1B | config/benchmark_v1.tape_manifest + .lock.json + .audit.json; 50 tapes, 5 buckets, closed 2026-03-21 |
| Market Selection Engine | Phase 1B | seven-factor scorer + NegRisk penalty + longshot bonus; market-scan CLI; 2728 tests (quick-037) |
| Discord alert system -- Phase 1 (outbound only) | Phase 1B | packages/polymarket/notifications/discord.py; 7 functions; gate hooks integrated; 29 tests |

## Items Left Unchecked (and why)

| Item | Reason |
|------|--------|
| Document external data paths in CLAUDE.md | External paths (D:/polymarket_data/...) are absent from CLAUDE.md |
| Complete Silver tape generation end-to-end | All 120 gap-fill tapes were confidence=low or confidence=none; pmxt/JB fills absent |
| Universal Market Discovery (NegRisk + Events + Sports) | fetch_top_events not implemented; api_client uses createdAt order, not volume24hr; no positional fallback in _identify_yes_index |
| Pass Gate 2 | NOT_RUN -- corpus is 10/50 qualifying tapes |

## Doc Drift Reconciled

**CURRENT_STATE.md**: Updated status header to 2026-03-28. Added artifacts restructure
(quick-036) and Market Selection Engine (quick-037) bullets. Added "Next executable step"
sentence pointing to CORPUS_GOLD_CAPTURE_RUNBOOK.md.

**CLAUDE.md**: Changed document-priority item 4 from v5 to v5_1. Added MarketMakerV1 to
SimTrader what-is-built. Added Market Selection Engine subsection. Appended Gate 2
NOT_RUN corpus note to existing Gate 2 paragraph.

## Current Phase 1B Status After Sync

- Gate 2: **NOT_RUN** -- 10/50 qualifying tapes; corpus shortfall by bucket:
  sports=15, politics=9, crypto=10, new_market=5, near_resolution=1 (as of 2026-03-27)
- Gate 3: BLOCKED pending Gate 2 PASS
- Market Selection Engine: SHIPPED (seven-factor scorer, market-scan CLI, 2728 tests)
- MarketMakerV1: SHIPPED (logit A-S, canonical Phase 1 strategy)
- Benchmark v1 manifest: CLOSED (50 tapes, 2026-03-21)

## Next Executable Step

Run `python tools/gates/capture_status.py` to see current shortage, then follow
`docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md` to record live Gold tapes until the
corpus reaches 50 qualifying tapes and Gate 2 can be re-run.

## Tests

After docs-only edits: run `pytest -q tests/test_market_scorer.py tests/test_mm_sweep_gate.py
tests/test_mm_sweep_diagnostic.py` to confirm no regressions.
