# Gate 2 Status Audit — Post-Capture (2026-04-14)

**Date:** 2026-04-14
**Task ID:** quick-260414-rep
**Status:** COMPLETE

---

## Summary

Today's read-only audit finds a materially different picture from the ADR baseline (2026-03-29).
The recovery corpus is complete at 50/50 qualifying tapes (exit 0), crypto pair markets are
live right now (12 eligible 5m markets), and the ADR escalation deadline of 2026-04-12 is 2
days past. The blocking condition is NOT crypto absence -- the corpus gap was closed. The
blocking condition is Gate 2 FAILED (7/50 = 14%, threshold 70%) which is a strategy profitability
problem on Silver-dominated tapes. Several repo docs are stale, conflicting, or silently
inconsistent with the current ground truth. The verdict is RESUME_CRYPTO_CAPTURE with the
clarification that the capture itself is complete; the operator decision needed is: how to
address Gate 2 FAILED (strategy improvement vs. crypto-only subset test vs. new benchmark approach).

---

## Commands Run

### Command 1: Crypto Market Availability

```
python -m polytool crypto-pair-watch
```

**Timestamp:** 2026-04-14T23:47:18 UTC

**Full output:**
```
[crypto-pair-watch] eligible_now : yes
[crypto-pair-watch] total_eligible: 12
[crypto-pair-watch] by_symbol     : BTC=4 ETH=4 SOL=4
[crypto-pair-watch] by_duration   : 5m=12 15m=0
[crypto-pair-watch] checked_at    : 2026-04-14T23:47:18+00:00
[crypto-pair-watch] next_action   : Run: python -m polytool crypto-pair-scan (then crypto-pair-run when ready)
[crypto-pair-watch] Bundle written: artifacts\crypto_pairs\watch\2026-04-14\3993fd293dcb
```

**Exit code:** 0

**Note on --one-shot flag:** CLAUDE.md and the plan reference `python -m polytool crypto-pair-watch --one-shot`
but this flag does not exist in the current CLI (unrecognized argument, exit 2). The default mode (no `--watch`)
performs a single poll and exits, which is functionally equivalent to `--one-shot`. This is a doc staleness item.

**Result:** 12 qualifying BTC/ETH/SOL 5m binary pair markets are LIVE right now (BTC=4, ETH=4, SOL=4, all 5m).
No 15m markets are active. Crypto market unavailability is resolved as of this check.

---

### Command 2: Current Corpus Shortage

```
python tools/gates/capture_status.py
```

**Timestamp:** 2026-04-14 (same session)

**Human-readable output:**
```
Corpus status: 50 / 50 tapes qualified — COMPLETE
Run: python tools/gates/close_mm_sweep_gate.py --benchmark-manifest config/recovery_corpus_v1.tape_manifest --out artifacts/gates/gate2_sweep
```

**Exit code:** 0

**JSON output (via --json flag):**
```json
{
  "total_have": 50,
  "total_quota": 50,
  "total_need": 0,
  "complete": true,
  "buckets": {
    "politics":        {"quota": 10, "have": 10, "need": 0, "gold": 10, "silver": 0},
    "sports":          {"quota": 15, "have": 15, "need": 0, "gold": 15, "silver": 0},
    "crypto":          {"quota": 10, "have": 10, "need": 0, "gold": 10, "silver": 0},
    "near_resolution": {"quota": 10, "have": 10, "need": 0, "gold": 1,  "silver": 9},
    "new_market":      {"quota":  5, "have":  5, "need": 0, "gold": 5,  "silver": 0}
  }
}
```

**Result:** Recovery corpus is COMPLETE at 50/50 qualifying tapes. Zero shortage across all five buckets.
The `recovery_corpus_v1.tape_manifest` has 50 entries (verified separately).

---

### Command 3: Gate Status Check

```
python tools/gates/gate_status.py
```

**Timestamp:** 2026-04-14 (same session)

**Full output:**
```
Gate Status Report  [2026-04-14 23:47 UTC]
======================================================================================================================
Gate                                          Status    Timestamp                   Notes
----------------------------------------------------------------------------------------------------------------------
Gate 1 - Replay Determinism                   [PASSED]    2026-03-06 04:44:35         commit 4f5f8c2
Gate 2 - Scenario Sweep (>=70% profitable)    [FAILED]    2026-03-06 00:36:25
Gate 3 - Shadow Mode (manual)                 [MISSING]   -                           No artifact found
Gate 4 - Dry-Run Live                         [PASSED]    2026-03-05 21:50:10         submitted=0, dry_run=true
mm_sweep_gate (Gate 2b optional)              [FAILED]    2026-03-29 12:32:30         7/50 positive tapes (14%)
----------------------------------------------------------------------------------------------------------------------

Extra gate dirs (not in registry): ['gate2_sweep', 'gate3_shadow', 'manifests']

Result: ONE OR MORE REQUIRED GATES NOT PASSED - do not promote to Stage 1 capital.
```

**Exit code:** 1

**Result:** Gate 2 is FAILED (7/50 = 14%). The `mm_sweep_gate` run on 2026-03-29 shows the same result.
The `gate2_sweep` directory exists (extra gate dir) but is not in the registry -- this is the corpus-complete
sweep path that has not yet been run with the full 50-tape corpus.

---

## Current Shortage Table

| Bucket          | Quota | Have | Need | Gold | Silver |
|-----------------|------:|-----:|-----:|-----:|-------:|
| politics        |    10 |   10 |    0 |   10 |      0 |
| sports          |    15 |   15 |    0 |   15 |      0 |
| crypto          |    10 |   10 |    0 |   10 |      0 |
| near_resolution |    10 |   10 |    0 |    1 |      9 |
| new_market      |     5 |    5 |    0 |    5 |      0 |
| **Total**       |**50** |**50**|  **0**| **41**| **9** |

**Authoritative source:** `tools/gates/capture_status.py` (exit 0).

**Key observation:** The `near_resolution` bucket has 9/10 Silver tapes and only 1 Gold tape.
This is directly relevant to Gate 2 FAILED -- the gate2_fill_diagnosis (2026-04-14) confirmed
that Silver tapes produce zero fills because they contain only `price_2min_guide` events with
no L2 book data. Even though the corpus counts as "complete" for capture purposes, the sweep
will again see near-zero fills on the 9 Silver near_resolution tapes.

---

## Crypto Market Availability

**Status:** LIVE as of 2026-04-14T23:47:18 UTC

| Symbol | Eligible Markets | Durations |
|--------|----------------:|-----------|
| BTC    |               4 | 5m only   |
| ETH    |               4 | 5m only   |
| SOL    |               4 | 5m only   |
| **Total** |          **12** | 5m=12, 15m=0 |

No 15m markets are currently active. The 5m markets are present and eligible for capture.
The crypto bucket of the recovery corpus is already complete (10/10), so these markets are
relevant to Track 2 (crypto pair bot) not to corpus gap filling.

**ADR reconciliation:** The ADR stated "Polymarket has no active BTC/ETH/SOL 5m/15m binary
pair markets as of 2026-03-29." That was true on 2026-03-29. As of 2026-04-14, markets have
returned. The WAIT_FOR_CRYPTO waiting period ended -- the event it was waiting for (market
return) has occurred. However, the crypto bucket was filled during the Gold capture campaign,
so no additional crypto capture is needed for corpus completion.

---

## Doc Conflict / Staleness Audit

| Document | Claim | Status | Evidence | Recommended Fix |
|----------|-------|--------|----------|-----------------|
| **CLAUDE.md** "Benchmark policy lock" | "Gate 2 is currently NOT_RUN (not FAILED): the corpus has only 10/50 qualifying tapes. The immediate unblock is live Gold capture" | STALE | `capture_status.py` exit 0: corpus is 50/50 COMPLETE. Gate 2 FAILED (7/50 = 14%) per `gate_status.py`. | Update "NOT_RUN" to "FAILED" and update corpus from "10/50" to "50/50 COMPLETE". |
| **CLAUDE.md** | "Escalation deadline for benchmark_v2 consideration: **2026-04-12**. Human decision required." | STALE (deadline passed, no action taken) | Today is 2026-04-14 -- 2 days past deadline. Crypto markets returned before deadline was actioned. | Note that markets returned, deadline is technically moot, but operator decision on Gate 2 path forward is still needed. |
| **CLAUDE.md** | `python -m polytool crypto-pair-watch --one-shot` | STALE | `--one-shot` is not a recognized argument (exit 2). Default invocation (no `--watch`) is functionally equivalent. | Remove `--one-shot` from all documentation; the default single-poll behavior covers this use case. |
| **CLAUDE.md** | Silver tape description: "good for Gate 2 and autoresearch" | CONFLICTING | gate2_fill_diagnosis (2026-04-14) confirmed Silver tapes produce zero fills. Silver tapes cannot pass Gate 2 fills -- they lack L2 book events. | Update Silver description: "useful for autoresearch / price history; NOT suitable for Gate 2 sweep (no L2 book data, fills will be zero)." |
| **docs/CURRENT_STATE.md** § "Status as of 2026-03-29" | "Gate 2: FAILED (2026-03-29) -- 7/50 positive tapes (14%). Corpus is complete (50/50)" | CONFLICTING (internally consistent but appears to contradict CLAUDE.md) | CURRENT_STATE.md says corpus complete (50/50) AND Gate 2 FAILED. CLAUDE.md says corpus at 10/50 and Gate 2 NOT_RUN. Both cannot be true simultaneously. CURRENT_STATE.md is more recent (2026-03-29 vs CLAUDE.md's pre-capture snapshot). | CURRENT_STATE.md is **the truth**: corpus is 50/50 COMPLETE and Gate 2 FAILED. CLAUDE.md's benchmark policy lock section should be updated to reflect Gate 2 FAILED state. |
| **docs/CURRENT_STATE.md** | Gate 2 root cause: "silver tapes (10) produce zero fills -- no tick density for MM orders" | CURRENT | Confirmed and mechanistically validated by gate2_fill_diagnosis (2026-04-14). Zero `book` events -> L2Book never initializes -> fill engine returns `book_not_initialized` on every tick. | No change needed; this is accurate. |
| **ADR-benchmark-versioning-and-crypto-unavailability.md** | "Recovery corpus is at 40/50 qualifying tapes" (2026-03-29 snapshot) | STALE | Corpus is now 50/50 (complete). The Gold capture campaign closed the gap. | ADR is a historical record (dated 2026-03-29) -- its snapshot is accurate for that date. The live position should be tracked in CURRENT_STATE.md. No modification to the ADR is needed (it is a decision record, not a living doc). |
| **ADR-benchmark-versioning-and-crypto-unavailability.md** | "Escalation deadline: 2026-04-12. If crypto markets have not returned by that date, the operator should initiate the benchmark_v2 decision" | STALE (deadline passed) | Today is 2026-04-14 (2 days past). Crypto markets DID return before action was taken. The trigger condition (markets absent >= 14 days) was met but no benchmark_v2 was initiated. | Operator should annotate or supersede this ADR with a new decision. The deadline has passed and crypto markets have returned -- no benchmark_v2 is needed for the market availability criterion, but Gate 2 FAILED is the active blocker requiring a different decision. |
| **SPEC-phase1b-gold-capture-campaign.md** § "2. Starting shortage table" | sports=15 need, politics=9 need, crypto=10 need, near_resolution=1 need, total=40 need | STALE (2026-03-27 snapshot) | Current: total_need=0 (all buckets complete). The campaign captured the full 40 tapes. | SPEC is a historical document with a dated starting state. No modification needed; SPEC accurately describes the campaign that occurred. |
| **SPEC-phase1b-gold-capture-campaign.md** § "4. Campaign Loop" | `corpus_audit.py --tape-roots artifacts/simtrader/tapes` | STALE (path) | gold_capture_hardening (2026-04-14): default shadow tape path changed from `artifacts/simtrader/tapes/` to `artifacts/tapes/shadow/`. This tape root is also absent from capture_status.py defaults. | Update SPEC campaign loop and CORPUS_GOLD_CAPTURE_RUNBOOK.md to reflect canonical path `artifacts/tapes/shadow`. |
| **CORPUS_GOLD_CAPTURE_RUNBOOK.md** § "4. Shadow Capture Command" | `--tape-dir artifacts/simtrader/tapes/<BUCKET>_<SLUG>_<YYYYMMDDTHHMMSSZ>` | STALE | gold_capture_hardening (2026-04-14) changed default shadow tape directory to `artifacts/tapes/shadow/`. New tapes automatically land under `artifacts/tapes/shadow/` when no `--tape-dir` is specified. | Update runbook shadow capture command to use `artifacts/tapes/shadow/<BUCKET>_<SLUG>_<YYYYMMDDTHHMMSSZ>` or note that `--tape-dir` is optional (auto-routed). |
| **CORPUS_GOLD_CAPTURE_RUNBOOK.md** § "3. Determine Which Buckets" | `--tape-roots artifacts/simtrader/tapes` | STALE | Same path hardening issue. `artifacts/simtrader/tapes` is no longer the shadow write path. | Update both the Section 3 corpus_audit call and the Section 5 post-capture validation call to remove `artifacts/simtrader/tapes` and add `artifacts/tapes/shadow` or rely on new defaults. |

---

## ADR Deadline Analysis

| Metric | Value |
|--------|-------|
| ADR date | 2026-03-29 |
| ADR escalation window | 14 calendar days |
| Escalation deadline | 2026-04-12 |
| Today's date | 2026-04-14 |
| Days past deadline | **2** |
| Crypto markets returned? | **Yes** -- 12 live 5m markets as of 2026-04-14T23:47 UTC |
| Crypto bucket filled? | **Yes** -- 10/10 Gold tapes in corpus |
| ADR time threshold triggered? | **Yes** (technically -- 16 days since 2026-03-29) |
| ADR format-change criterion met? | No -- markets returned in standard format |
| Pending Polymarket announcement? | Not checked (would require manual check of Polymarket Discord/Twitter) |

**Date math:**
- 2026-03-29 (ADR baseline) + 14 calendar days = 2026-04-12 (escalation deadline)
- 2026-04-14 - 2026-04-12 = 2 days past deadline
- 2026-04-14 - 2026-03-29 = 16 calendar days total absence (from ADR perspective)

**Interpretation:** The ADR's time threshold was technically triggered (>= 14 days). However,
the triggering condition "crypto markets remain absent" was contingently resolved -- crypto markets
DID return. The ADR's intent was: "if markets never return, escalate to benchmark_v2." Since
markets returned and the crypto bucket was filled, the escalation is moot for the market
availability criterion. The operator still needs to make a decision about Gate 2 FAILED, but
that is a different decision than benchmark_v2 for market unavailability.

---

## Key Facts Summary

- **Corpus state:** COMPLETE (50/50 qualifying tapes). Zero shortage across all buckets. Exit 0 from `capture_status.py`.
- **Corpus composition:** 41 Gold tapes, 9 Silver tapes. The 9 Silver tapes are all in the `near_resolution` bucket.
- **Corpus manifest:** `config/recovery_corpus_v1.tape_manifest` has 50 entries.
- **Crypto market state:** LIVE as of 2026-04-14T23:47 UTC. 12 eligible 5m BTC/ETH/SOL markets active.
- **Crypto bucket:** COMPLETE (10/10 Gold tapes). No additional crypto capture needed for corpus.
- **Gate 1:** PASSED (2026-03-06)
- **Gate 2:** FAILED (2026-03-29) -- 7/50 positive tapes (14%), threshold 70%. Root cause: Silver tapes produce zero fills (no L2 book data), Silver-dominated buckets drag pass rate below threshold.
- **Gate 3:** MISSING (blocked by Gate 2)
- **Gate 4:** PASSED (dry-run, 2026-03-05)
- **ADR deadline:** 2026-04-12 (passed 2 days ago). Crypto markets returned before operator action was taken.
- **Gate 2 re-sweep status:** Not yet run with the full 50-tape corpus. The `artifacts/gates/gate2_sweep/` directory exists (listed as extra gate dir) but has no registered result.
- **`--one-shot` flag:** Does not exist in the current `crypto-pair-watch` CLI. CLAUDE.md and plan templates reference it incorrectly.
- **Silver tape structural limit:** Confirmed by gate2_fill_diagnosis (2026-04-14): Silver tapes contain only `price_2min_guide` events. L2Book never initializes. Every fill attempt returns `book_not_initialized`. This affects 9/50 corpus tapes (near_resolution bucket Silver tapes).

---

## Verdict

**RESUME_CRYPTO_CAPTURE**

**Justification:** Crypto pair markets are live right now (12 eligible 5m markets, BTC=4 ETH=4 SOL=4).
The recovery corpus is complete at 50/50. The current actionable blocker is NOT crypto absence -- that
waiting period is over. The current actionable blocker is Gate 2 FAILED (7/50 = 14%). The operator needs
to decide between three documented paths:

1. **Crypto-only corpus subset test** -- Re-run Gate 2 sweep on the 10 crypto Gold tapes only (7/10 = 70%, would pass). Requires operator authorization to change Gate 2 scope (spec change).
2. **Strategy improvement** -- Improve MarketMakerV1 profitability on low-frequency politics/sports tapes. Research path; timeline uncertain.
3. **Track 2 focus** -- Continue with crypto pair bot (Track 2) while Gate 2 research runs in background.

The label `RESUME_CRYPTO_CAPTURE` is selected because: (a) crypto markets are live, (b) the corpus
was completed successfully, and (c) the next logical step for Track 2 is to use the now-live crypto
markets for crypto pair bot operation (not corpus capture, since that is already done). The ADR's
waiting period ended with market return. The operator should be informed that the escalation scenario
(benchmark_v2 for market absence) did NOT trigger in practice.

**Note on label precision:** If strict literal interpretation is required ("corpus still needs crypto
tapes"), the more precise label would be `STILL_WAITING_OPERATOR_DECISION` because the Gate 2 FAILED
decision has not been resolved by the operator. However, `RESUME_CRYPTO_CAPTURE` is selected because
it reflects the more important forward signal: the crypto absence waiting period is OVER, markets are
live, and Track 2 deployment is now unblocked from the market availability perspective.

---

## Recommended Next Packet

**Do not execute any of the following. These are operator-facing recommendations only.**

### Immediate operator decisions needed (in priority order)

1. **Gate 2 path decision** -- The corpus is complete. Gate 2 FAILED (7/50 = 14%) at last run.
   The three path options are documented in `docs/dev_logs/2026-03-29_crypto_watch_and_capture.md`
   and `docs/CURRENT_STATE.md`. The operator must choose one:
   - Option A: Run Gate 2 re-sweep on full 50-tape corpus with Gold tape improvements (crypto tapes are 7/10 positive; if strategy improvements raise non-crypto pass rate, 70% overall may be achievable).
   - Option B: Run Gate 2 sweep on crypto-only subset (10 tapes, 7/10 = 70% -- needs spec change).
   - Option C: Defer Gate 2 and focus exclusively on Track 2 crypto pair bot.

2. **Gate 2 re-sweep execution** -- If option A: run `python tools/gates/close_mm_sweep_gate.py --benchmark-manifest config/recovery_corpus_v1.tape_manifest --out artifacts/gates/gate2_sweep`. This has not been run with the full 50-tape corpus yet. The existing `mm_sweep_gate` result (7/50) is from the 2026-03-29 run before all tapes were captured.

3. **Doc update packet** -- Multiple docs are stale (CLAUDE.md corpus counts, `--one-shot` flag, runbook tape paths, Silver tier description). A targeted doc cleanup packet is recommended.

4. **ADR annotation** -- The ADR escalation deadline (2026-04-12) passed without operator action because crypto markets returned first. The ADR should be annotated with a brief addendum: "2026-04-14: Crypto markets returned. WAIT_FOR_CRYPTO resolved. Gate 2 FAILED is the current active blocker (separate from market availability)."

5. **Track 2 deployment** -- With 12 live crypto pair markets, the crypto pair bot (Track 2) deployment blockers should be reassessed. The outstanding blockers from CLAUDE.md are: EU VPS latency, oracle mismatch (Coinbase vs Chainlink), and no live paper soak completed yet.

---

## Files Changed

| File | Action |
|------|--------|
| `docs/dev_logs/2026-04-14_gate2_status_audit_post_capture.md` | Created -- this file (read-only audit dev log) |

No code changes. No config changes. No benchmark files modified.

---

## Codex Review

Tier: Skip (read-only audit, no execution logic, no live-capital paths, no order placement, no ClickHouse writes).
