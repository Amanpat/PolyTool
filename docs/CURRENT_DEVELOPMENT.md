---
status: active
last_verified: 2026-04-21
type: living-state-doc
---

# Current Development

This file tracks what is actively being built in PolyTool. It is the Director-level gate on feature scope. The Architect reads this file at the top of every chat and refuses to design prompts for features not listed as Active without Director acknowledgment.

## Rules

1. **Max 3 Active features.** A 4th triggers Architect refusal with a "which Active item pauses or completes first?" prompt.
2. **Staleness limit: 7 days.** Active features without a `last_updated` bump for 7+ days get refreshed or moved to Paused.
3. **Completion protocol** (all three required):
   - Create `docs/features/<slug>.md`
   - Update `docs/INDEX.md`
   - Move entry to Recently Completed
4. **No silent scope changes.** DoD edits require a one-line reason. Enlarging scope triggers a Director conversation.
5. **Blockers are first-class.** Active with external blockers is OK if the feature is otherwise ready. Move to Paused only when work cannot meaningfully continue.
6. **"Awaiting Decision" is its own state.** Work that is complete-but-pending-a-decision does not occupy an Active slot.

## Awaiting Director Decision

### Gate 2 Path Forward

- **Context:** Gate 2 swept 2026-03-29 and re-swept 2026-04-14. Both: 7/50 positive (14%), threshold 70%. Crypto bucket alone: 7/10 (70%).
- **Known Decision Options (from `docs/dev_logs/2026-04-15_gate2_decision_packet.md`):**
  1. Adopt crypto-only subset (spec change; technically passes)
  2. Improve strategy for low-frequency markets (research-heavy, open-ended)
  3. Pivot focus to Track 2 (de facto chosen per 2026-04-15 operator runbook; not formally logged)
- **Added Option 4 (from PMXT work packet 2026-04-10):** Land the SimTrader Fee Model Overhaul first, then re-run Gate 2 with correct maker/taker + category-specific fees. Current Gate 2 FAIL used taker-only + single fee rate — systematically pessimistic for maker strategies.
- **Option 4 blocker resolved 2026-04-21:** Fee Model Overhaul (Deliverable A) is complete. Category-aware fees, maker=0, Kalshi baseline, and full runtime propagation are shipped. Re-running Gate 2 under the corrected fee model is now unblocked.
- **Next action:** Director decides whether to re-run Gate 2 now (Option 4) or commit to one of Options 1–3.

## Active Features (max 3)

### Feature 1: Track 2 Paper Soak — 24h Run

- **Track:** 1A (crypto pair bot)
- **Status:** Infrastructure hardened 2026-04-15 across 6 work packets. Ready to launch.
- **Started:** 2026-04-15 (hardening phase complete); soak itself not yet started
- **Last updated:** 2026-04-21
- **Owner:** Aman + partner
- **Current step:** Launch 24h paper soak per `docs/runbooks/TRACK2_OPERATOR_RUNBOOK.md`
- **Blockers:** None. 12 active 5m markets confirmed (BTC×4, ETH×4, SOL×4).
- **Next action:** Kick off soak on partner machine.
- **Note on fee accuracy:** Soak will run with current (incorrect) fee model. Results may be mildly pessimistic. If Fee Model Overhaul lands before soak completes, may re-run with correct fees. Not a blocker.
- **Definition of done:**
  - [ ] 24h paper soak completes without unhandled errors
  - [ ] `paper_soak_verdict.json` produced with promote/rerun/reject outcome
  - [ ] `crypto-pair-review` output captured in dev log
  - [ ] `docs/features/track2_paper_soak_24h_v1.md` created
  - [ ] CURRENT_STATE.md Track 2 section updated

### Feature 2: [empty slot]

### Feature 3: [empty slot]

Not filled. Reserve intentionally left open until one of the Active features has genuine forward motion. Adding a third right now would repeat the parallel-stall pattern.

## Completion-Doc Debt (tracked, not Active)

Four items shipped 2026-04-14/15 without feature docs. Backfill as consolidated docs where sensible:

- [ ] `docs/features/track2_soak_infrastructure.md` — covers all 6 `2026-04-15_track2_*` dev logs
- [ ] `docs/features/gate2_gold_capture_hardening.md` — covers 2026-04-14 path fix + `tape_validator.py`
- [ ] `docs/features/gate2_post_capture_qualification.md` — covers the qualification workflow
- [ ] Verify `docs/features/crypto-pair-reference-feed-v1.md` accurately covers Coinbase fallback

Estimated 2 hours of Claude Code time. Can be done in one session. Not an Active feature — completion protocol enforcement going forward.

## Recently Completed (rolling 30 days)

| Feature                                                       | Completed  | Track    | Completion doc                                                     |
| ------------------------------------------------------------- | ---------- | -------- | ------------------------------------------------------------------ |
| SimTrader Fee Model Overhaul (PMXT Deliverable A)             | 2026-04-21 | Cross-cutting | `docs/features/simtrader_fee_model_v2.md` — category-aware taker fees, maker=0, Kalshi baseline, full 12-entry-point propagation, 32 new tests, MERGE-READY per Codex gate |
| Wallet Discovery v1 (Loop A + watchlist + unified scan + MVF) | 2026-04-10 | Research | `docs/features/wallet-discovery-v1.md`                             |
| Track 2 paper-soak hardening (6 items)                        | 2026-04-15 | 1A       | ⚠️ debt — see above                                                |
| Gate 2 post-capture qualification workflow                    | 2026-04-14 | 1B       | ⚠️ debt — see above                                                |
| Gold capture hardening (path fix + validator)                 | 2026-04-14 | 1B       | ⚠️ debt — see above                                                |
| benchmark_v1 closure                                          | 2026-03-21 | 1B       | verify doc exists                                                  |
| Coinbase reference feed fallback                              | 2026-03-26 | 1A       | `docs/features/crypto-pair-reference-feed-v1.md` (verify accurate) |

## Paused / Deferred

| Feature                                                | Paused         | Reason                                                                            | Resume trigger                                                |
| ------------------------------------------------------ | -------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| Crypto Gold Tape Resumption                            | 2026-04-21     | Director paused pending Gate 2 decision                                           | Gate 2 Option 1 or 4 chosen                                   |
| Wallet Discovery Loop B (Alchemy watched-wallet)       | 2026-04-15     | Feasibility probe complete; implementation not started                            | Alchemy key + Track 2 soak result known                       |
| Wallet Discovery Loop D (managed CLOB + anomaly)       | 2026-04-15     | Feasibility probe complete; ClobStreamClient blockers open                        | ClobStreamClient PING keepalive + dynamic subscription landed |
| Wallet Discovery Loop C / insider detection            | pre-2026-04-09 | Out-of-scope per "Decision - Roadmap Narrowed to V1"                              | Phase 1 revenue path clear                                    |
| RIS Phase 2 audit follow-up (cloud providers, R0 seed) | 2026-04-09     | RIS conditionally closed with audit findings open; repo pivoted to Gate 2/Track 2 | Track 2 ships first dollar OR explicit Director decision      |
| PMXT Deliverable B (Sports Strategy Foundations)       | 2026-04-10     | Draft work packet; Deliverable A must land first                                  | Deliverable A complete AND Track 1C activation decided        |
| PMXT Deliverable C (RIS Knowledge Seeding)             | 2026-04-10     | Draft work packet; RIS Phase 2 audit gaps are prerequisite                        | RIS audit gaps resolved                                       |
| pmxt Sidecar Architecture                              | 2026-04-10     | Parked per `12-Ideas/Idea - pmxt Sidecar Architecture Evaluation.md`              | Phase 3 activation                                            |
| Phase 1A WebSocket CLOB migration                      | pre-2026-04-15 | Deferred to post-paper-soak                                                       | Paper soak promote verdict                                    |
| Phase 1C sports directional model                      | N/A            | Not yet started                                                                   | After Track 2 ships OR Gate 2 passes                          |

## Notes for the Architect

- Document priority in CLAUDE.md still applies. This file is below those docs in authority but above Architect prompts for _scoping_ ("should we work on this?"), not _technical content_ ("how should we build this?").
- If the Director describes work that doesn't map to any Active feature, your first response must be: "This doesn't match current Active features [list]. (a) Pause one and add new, (b) extend an existing Active feature, or (c) confirm this is a quick one-off?"
- **"Awaiting Decision" items are not Active.** Do not design prompts that advance Gate 2 work until the Director records a decision in this file.
- **Feasibility probes are not Active.** If the Director asks to implement Loop B or Loop D, cite this file's Paused section and resume trigger.
- **PMXT Deliverable A is COMPLETE (2026-04-21).** Category-aware fees, maker=0, Kalshi baseline, and full runtime propagation are shipped. Deliverables B and C remain Paused — see Paused/Deferred table.
- **Completion-doc debt is tracked.** When a future feature crosses DoD, your NEXT STEP must include the three-step completion protocol explicitly.
- When Active count hits 3, stop offering architectural next-moves that would create a 4th. Redirect to "which Active feature needs a next step?"
