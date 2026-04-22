---
tags: [session-note, research, integration]
date: 2026-04-10
status: complete
topics: [open-source-repos, fee-model, sports-strategies, expected-changes, final-review]
---

# 2026-04-10 Final Review — Open Source Repo Integration

## What You Will Actually See After Implementation

### Sub-Task A (Fee Model Rewrite) — The Only Deliverable Right Now

**This is an internal accuracy fix, not a feature.** Think of it like recalibrating a scale — the scale looks the same, but now it reads correctly.

#### Changes you WILL see:

1. **Different PnL numbers in ALL SimTrader outputs.** Every replay, every sweep, every shadow run will report different fees and net PnL. Specifically:
   - Maker fills (virtually all of our A-S market maker and crypto pair bot fills) go from being charged ~0.0625 USDC per 100 shares at midprice → **0.00 USDC** (makers pay zero)
   - Taker fills (if any exist from `force_taker` strategies) use the corrected formula with category-specific rates instead of the old universal 200bps with wrong exponent
   - Net effect on existing Gate 2 results: crypto bucket PnL should IMPROVE (no longer penalized with phantom fees on maker fills). Politics/sports zero-fills problem remains unchanged.

2. **New `fees` section in strategy config JSON.** You'll see `market_category` and `platform` fields when configuring strategies. Example:
   ```json
   { "fees": { "platform": "polymarket", "market_category": "crypto" } }
   ```

3. **Gate 2 re-run produces different numbers.** After the fix lands, re-running the Gate 2 sweep on benchmark_v1 will show different PnL for every tape that produced fills. This is expected and correct — the old numbers were wrong.

4. **Updated test suite.** Existing `test_simtrader_portfolio.py` expected values will change (formula is different). At least 12 new test cases added.

5. **New dev log.** `docs/dev_logs/YYYY-MM-DD_fee-model-rewrite.md`

6. **New KalshiFeeModel class.** Ready for Phase 3 but not actively used until Kalshi integration.

#### Changes you will NOT see:

- **No new UI.** SimTrader Studio already exists (`studio/app.py`, 1422 lines) as a browser-based replay UI. This work packet doesn't touch it.
- **No new CLI commands.** Existing commands produce different fee numbers, but no new commands are added.
- **No new Grafana dashboards.** Fee accuracy is internal to SimTrader replay, not live monitoring.
- **No new strategies.** We're fixing the accounting, not adding trading logic.
- **No visual changes to Studio.** The replay charts will show different fee breakdowns in the PnL panel, but the interface itself is unchanged.

**The value is trust:** After this lands, every backtest number you see is computed with the formula Polymarket actually uses. Before this, every number was computed with the wrong formula, wrong rates, and wrong maker/taker treatment.

---

## Final Re-Review: Are We Getting Everything From These Repos?

### evan-kolberg/prediction-market-backtesting — FINAL PASS

**Already captured (confirmed complete):**
- Fee model architecture → Sub-Task A ✅
- Sports strategies (3 signals with verified parameters) → Sub-Task B ✅
- Fill engine comparison (walk-the-book identical, book mutation gap documented) ✅
- PMXT relay (confirmed mirror-only, skip) ✅
- Licensing (LGPL boundary clear, reimplementation safe) ✅

**Items reviewed and deliberately NOT included:**

| Item | Why Excluded | Revisit When |
|------|-------------|-------------|
| `calibration_arb.py` strategy | Phase 5 (Favorite-Longshot). Parameters not extracted yet. | Phase 5 activation |
| `polymarket_spread_capture` strategy | We have MarketMakerV0/V1 already. Their quoter is simpler, not better. | If Gate 2 continues failing |
| `polymarket_simple_quoter` strategy | Same — our Logit A-S is more sophisticated. | Never (superseded by our V1) |
| `polymarket_panic_fade` strategy | Phase 5 (Information Advantage). Needs News Governor first. | Phase 5 activation |
| `deep_value_resolution_hold` strategy | Phase 5 (Favorite-Longshot). Thesis captured in Sub-Task B calibration analysis. | Phase 5 activation |
| 16-worker concurrent pmxt fetch | Useful pattern but we're deferring pmxt adoption to Phase 3. | Phase 3 pmxt decision |
| Charting code (equity curves, Brier advantage) | Our Studio already has replay charts. Their Brier advantage metric is interesting for Track 1C calibration but not urgent. | Track 1C calibration work |
| Legacy engine as Bronze backtester | Our SimTrader handles Bronze-compatible trade-level replay via existing feed adapters. Adding a second engine creates maintenance burden. | Only if SimTrader can't handle a specific Bronze-tier use case |
| Pydantic Config pattern | Deferred to Sub-Task B per architect decision. Not a project-wide convention yet. | Sub-Task B activation |

**One item worth flagging for future extraction:**
- **Brier score / cumulative Brier advantage metric** from their charting code. This is a calibration measurement that directly applies to Track 1C sports model validation. Not urgent now, but when we build the sports model calibration pipeline, reference their `plotting.py` for the Brier advantage computation. This is MIT-licensed and a clean extraction target.

### hermes-pmxt — FINAL PASS

**Already captured (confirmed complete):**
- LEARNINGS.md gotchas → RIS seeding ✅
- Jaccard arb matching pattern → Phase 3 decision ✅
- Metaculus as signal source → parked idea ✅
- Cross-platform divergence as RIS signal → parked idea ✅

**Items reviewed and deliberately NOT included:**

| Item | Why Excluded | Revisit When |
|------|-------------|-------------|
| SKILL.md agent prompt | Couldn't fetch content. Our RIS has its own evaluation gate. | If we adopt Hermes agent framework (unlikely) |
| Tool wrapper functions | Trivial pmxt SDK calls, no novel logic | Never |
| `pmxt_ohlcv` / `pmxt_order_book` patterns | Simple wrappers, useful only if we adopt pmxt | Phase 3 pmxt decision |

**Nothing missed.** This repo's value was always the LEARNINGS.md and the architectural insight about price divergence as intelligence signal. Both captured.

### realfishsam/Polymarket-Copy-Trader — FINAL PASS

**Confirmed skip.** Our 4-loop wallet monitoring architecture is dramatically ahead. The only output from this deep dive was the pmxt sidecar concern, which is already recorded as a parked decision.

**One thing worth noting that I didn't explicitly call out before:** The QuickNode guide for building a Polymarket copy trading bot (found during research) has a more robust architecture than this repo — WebSocket + REST dual detection, position multiplier sizing, per-market notional caps, retry logic with error classification. If we ever need copy-trade EXECUTION (not just monitoring), that guide is a better reference than this repo. But our roadmap positions copy-trading as "after Loop B is proven" — so this is deep future.

### calibrated.fyi — NOT DEEP-DIVED

**Status:** Deferred. Source credibility scoring for RIS Pipeline B (Reddit/Twitter/blogs). The idea was to use Calibrated scores to weight document credibility — a well-calibrated pundit's claims get a confidence boost.

**Should we add this to the work packet?** No. It's Phase 3+ (RIS Pipeline B adds the research scraper for Reddit/blogs, which is where source credibility matters). Adding it now would be premature — we don't have the scraper yet.

**Revisit trigger:** When RIS Pipeline B (LLM-assisted research scraper) is built and we need a way to differentiate signal from noise in community sources.

---

## Summary: Value Extraction Is Complete For Current Phases

| Repo | Value Extracted | Value Remaining | When To Revisit |
|------|----------------|-----------------|-----------------|
| evan-kolberg/backtesting | Fee model (A), sports strategies (B), fill engine comparison | `calibration_arb`, `panic_fade`, `deep_value_hold`, Brier metric | Phase 5, Track 1C calibration |
| hermes-pmxt | LEARNINGS.md (C), arb matching pattern (D), divergence signal (D) | SKILL.md prompt patterns, Metaculus integration | Phase 3 pmxt decision |
| realfishsam/Copy-Trader | pmxt sidecar concern (D) | QuickNode guide for execution (deep future) | After Loop B proven |
| calibrated.fyi | Concept noted | Full deep-dive | Phase 3 RIS Pipeline B |

**For the current development sequence (wallet discovery → fee model → RIS → sports signals), we are extracting everything these repos have to offer.** The remaining value is Phase 3+ and Phase 5+ material that would be premature to build now.
