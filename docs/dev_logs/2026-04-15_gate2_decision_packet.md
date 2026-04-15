# Gate 2 Decision Packet: Three Path-Forward Options

**Date:** 2026-04-15
**Task:** quick-260415-owj
**Type:** Decision Packet (Director approval required)
**Status:** AWAITING DIRECTOR DECISION

---

## Evidence Summary

Gate 2 has FAILED twice against the same 50-tape corpus, producing identical results:

| Run Date   | Tapes | Positive | Pass Rate | Threshold | Verdict |
|------------|------:|---------:|----------:|----------:|---------|
| 2026-03-29 |    50 |        7 |     14.0% |     70.0% | FAIL    |
| 2026-04-14 |    50 |        7 |     14.0% |     70.0% | FAIL    |

The result is reproducible. Gate 2 failure is not a fluke or a tooling issue.

### Bucket Breakdown (both runs identical)

| Bucket          | Tapes | Positive | Pass Rate | Notes                           |
|-----------------|------:|---------:|----------:|---------------------------------|
| crypto          |    10 |        7 |     70.0% | All 7 positives are from here   |
| near_resolution |    10 |        0 |      0.0% | Low tick rate; includes Silver  |
| new_market      |     5 |        0 |      0.0% | Low tick rate                   |
| politics        |    10 |        0 |      0.0% | Low tick rate; some Silver      |
| sports          |    15 |        0 |      0.0% | Low tick rate                   |
| **TOTAL**       |**50** |    **7** | **14.0%** |                                 |

### Root Cause (confirmed, not a gate design flaw)

Two independent failure modes, both confirmed by code-path analysis
(dev log: `docs/dev_logs/2026-04-14_gate2_fill_diagnosis.md`):

**Failure Mode A — Silver tapes (9 of 50, 0% positive):**
Silver tapes contain only `price_2min_guide` events — no L2 order book snapshots
(`book`) and no incremental book deltas (`price_change`). `L2Book._initialized` remains
`False` throughout replay. `fill_engine.try_fill()` returns `book_not_initialized` before
any quote comparison occurs. The strategy emits zero order intents. This is correct behavior
given the input — the simulator is not defective, the tape tier is structurally incompatible
with L2-dependent fill evaluation.

**Failure Mode B — Non-crypto shadow tapes (31 of 50, 0% positive):**
Politics, sports, near_resolution, and new_market markets have low tick rates (sparse
`price_change` events). MarketMakerV1 requires frequent bid/ask crossing to generate
positive net PnL over a session. On sparse tapes, fees outpace capture. This is a fundamental
microstructure mismatch, not a parameter calibration issue that can be tuned away cheaply.

**Crypto-only signal:** Crypto 5m BTC/ETH/SOL markets have sufficient tick density. 7/10
positive in the crypto bucket alone meets the 70% threshold. The three negative crypto tapes
(btc-1774771800, sol-1774768800, sol-1774771500) reflect genuine adverse-selection sessions,
not systematic strategy failure.

### Timeline Context

- 2026-03-29: Gate 2 first run — FAILED
- 2026-04-12: ADR escalation deadline for benchmark_v2 consideration — PASSED
- 2026-04-14: Crypto markets returned (12 active 5m markets: BTC=4, ETH=4, SOL=4)
- 2026-04-14: Gate 2 re-sweep (authoritative) — FAILED (identical result)
- 2026-04-15: THIS DECISION PACKET

---

## Three Options Comparison

| | Option 1 | Option 2 | Option 3 |
|---|---|---|---|
| **Name** | Crypto-only Gate 2 | Strategy improvement | Track 2 focus |
| **Description** | Redefine Gate 2 scope to require only the crypto bucket (10 tapes). 7/10 = 70% already passes. | Improve MarketMakerV1 to fill profitably on low-frequency politics/sports tapes. | Deprioritize Gate 2. Execute Track 2 (crypto pair bot) with 12 active 5m markets now live. |
| **ROI / Time to first dollar** | Fast (no engineering work), but Gate 3 scope also narrows to crypto only. Does not accelerate revenue — Gate 3 shadow run still required after. | Slow and uncertain. Research-grade timeline: 2-4+ weeks minimum per iteration, outcome unknown. | Fastest. Track 2 infrastructure substantially built. 12 active markets confirmed on 2026-04-14. |
| **Risk** | Validates MM only on crypto markets. If crypto 5m markets disappear again (as they did from ~2026-03-06 to 2026-04-14), Track 1 has no fallback corpus. | May never work. Low-frequency prediction markets have different microstructure. Investment could be wasted. | Track 1 stalls without active investment. Gate 2 remains FAILED indefinitely. Acceptable: Track 2 is a fully independent revenue path. |
| **Weakens validation gates?** | YES — scope narrowed by removing 40 of 50 tapes from the Gate 2 pass criterion. | No | No |
| **Doc conflict** | HIGH — see detail below | None | Low — no spec changes, no gate weakening |
| **Engineering scope** | Minimal code (crypto-only manifest subset). Heavy docs (5+ files). | Heavy: strategy research, implementation, sweep, iterate. Multiple cycles. | Moderate for Track 2 (paper soak, oracle check, EU VPS eval). Zero for Gate 2. |

### Option 1 Doc Conflict Detail

This is a material spec change. Files requiring update if Option 1 is chosen:

1. `CLAUDE.md` — Gate 2 definition and benchmark policy lock
2. `docs/CURRENT_STATE.md` — Gate 2 scope and corpus composition
3. `docs/specs/ADR-benchmark-versioning-and-crypto-unavailability.md` — WAIT_FOR_CRYPTO scope
4. `docs/PLAN_OF_RECORD.md` — Gate 2 primary path
5. `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md` — benchmark tape set section

This would also require a new crypto-only tape manifest, creating a versioning question
around whether `recovery_corpus_v1.tape_manifest` remains authoritative or is superseded.

---

## Recommendation: Option 3 (Track 2 Focus)

**Recommended action:** Deprioritize Gate 2. Execute Track 2 (crypto pair bot) as the
active revenue path. Continue Track 1 research in background with no timeline pressure.

### Rationale

1. **CLAUDE.md principle alignment:** Non-negotiable principle #2 is "First dollar before
   perfect system." Principle #1 is "Simple path first." Option 3 is the only choice that
   advances both.

2. **Triple-track strategy model:** CLAUDE.md explicitly requires maintaining optionality
   across all three tracks. Collapsing effort into Gate 2 / Track 1 only violates this
   model. Track 2 is explicitly designated STANDALONE — it does not wait for Gate 2 or
   Gate 3. Track 3 (sports directional) can continue at low priority.

3. **No gate weakening:** Option 3 does not modify gate definitions, thresholds, corpus
   composition, or policy documents. The 70% Gate 2 threshold remains intact. If Gate 2
   is eventually closed, it will be on honest terms.

4. **Immediately actionable:** 12 active crypto 5m markets confirmed on 2026-04-14.
   Track 2 infrastructure (pair engine, reference feed, Docker services, paper-run
   framework) is substantially built per CLAUDE.md.

5. **No bridge burned:** Gate 2 research can resume at any time. The failure anatomy is
   fully documented. Gold tape capture for the crypto bucket remains the quickest re-entry
   path if the team returns to Track 1.

6. **Option 1 deferred, not rejected:** Crypto-only scope redefinition could be revisited
   as a Phase 1B gate checkpoint IF Track 2 paper soaks prove that MarketMakerV1 has a
   real edge in crypto 5m markets. Collecting that evidence first is the right order.

---

## If Approved: Doc Changes Required Under Option 3

Minimal. No gate language or policy documents change.

| File | Change |
|------|--------|
| `docs/CURRENT_STATE.md` | Update "Next executable step" to state Track 2 is the active priority; Gate 2 is background research |
| `docs/PLAN_OF_RECORD.md` | Add a note in section 0 that Track 2 is the active revenue path per Director decision; Gate 2 is deprioritized, not abandoned |

**Not changing:** `CLAUDE.md` (Track 2 already documented as STANDALONE), ADR (no policy
change), benchmark manifests (immutable), gate thresholds (not weakened).

---

## If Rejected: Alternative Actions Required

### If Director prefers Option 1 (Crypto-only Gate 2)

1. Draft a Gate 2 scope amendment ADR documenting the redefinition rationale and
   corpus narrowing decision.
2. Create a crypto-only manifest (`config/crypto_corpus_v1.tape_manifest`, 10 entries).
3. Update the 5 governing docs listed above under "Option 1 Doc Conflict Detail."
4. Re-run Gate 2 sweep against the crypto-only manifest (`run_recovery_corpus_sweep.py
   --manifest config/crypto_corpus_v1.tape_manifest`). Result will be 7/10 = 70% PASS.
5. Proceed to Gate 3 (shadow) — scoped to crypto markets only.

Timeline: 1-2 days for docs; Gate 3 shadow requires additional live market session time.

### If Director prefers Option 2 (Strategy improvement)

1. Initiate a MM strategy research sprint — define a specific profitability hypothesis
   for low-frequency markets (e.g., wider spreads + inventory limits + skip-near-resolution).
2. Define concrete success criteria: target pass rate on politics/sports tapes (e.g.,
   >= 50% of non-crypto tapes must show positive PnL before returning to Gate 2 sweep).
3. Estimate minimum 2-4 weeks per iteration cycle (implement, sweep, analyze, iterate).
4. No doc changes needed upfront; documents update when Gate 2 eventually passes.

Timeline: indeterminate. Risk of never converging is real.

---

## Open Decision Points

1. **ADR WAIT_FOR_CRYPTO formal closure:** The ADR was written when Gate 2 was NOT_RUN
   and crypto markets were absent. Gate 2 has now been run twice and FAILED. Crypto markets
   have returned. Should the ADR status be updated from "Active" to reflect that the
   wait-for-crypto blocker is resolved but Gate 2 is now a strategy question, not a data
   availability question? Human decision required before any agent touches that ADR.

2. **50-tape corpus preservation:** Regardless of which option is chosen, the
   `config/recovery_corpus_v1.tape_manifest` (50 entries) and all gate artifacts should
   be preserved as-is for future benchmarking. No option above requires destroying them.

3. **SOL adverse selection:** Three of ten crypto tapes are SOL tapes with heavily negative
   PnL (-$492, -$35, -$20). If Track 2 is the path, should SOL markets be filtered from
   the crypto pair bot's eligible universe pending further adverse-selection analysis?
   This is a Track 2 design question, not a Gate 2 question, but it surfaces here.

---

## Files Changed

| File | Action |
|------|--------|
| `docs/dev_logs/2026-04-15_gate2_decision_packet.md` | Created — this file |

## Commands Run

None. This is a docs-only analysis packet.

## Codex Review

Tier: Skip (docs-only, no execution paths, no live-capital logic).
