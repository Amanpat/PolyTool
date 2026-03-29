# Dev Log: Crypto Benchmark Policy Decision

**Date:** 2026-03-29
**Quick task:** quick-043
**Branch:** phase-1B
**Decision:** WAIT_FOR_CRYPTO

---

## 1. Why This Was Executed

Wave 2 of the Gold capture campaign (quick-041, 2026-03-29) completed three additional buckets:
sports (15/15), politics (10/10), and new_market (5/5). The recovery corpus reached 40/50
qualifying tapes. The only remaining shortage is the crypto=10 bucket.

However, Polymarket has no active BTC/ETH/SOL 5m/15m binary pair markets as of 2026-03-29.
The crypto bucket cannot be filled until these markets reappear.

No written policy existed for:
- How long to wait before escalating
- What evidence triggers a benchmark_v2 contingency
- What exact files a benchmark_v2 work packet would change

This task writes that policy down to prevent future agents from improvising or accidentally
mutating benchmark_v1 config files.

---

## 2. Doc Conflict Found

Before this task, there was an ambiguity gap across the following documents:

- **`docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md`**: States "continue polling with
  `crypto-pair-watch --watch`." This is correct but open-ended — no escalation timeline.
- **No document** defined: escalation criteria, benchmark_v2 trigger conditions, or the
  specific files that a benchmark_v2 work packet would require.
- **`docs/CURRENT_STATE.md` next-step block**: Was accurate about the immediate polling action
  but did not reference a policy decision or a deadline.

Resolution: ADR written at `docs/specs/ADR-benchmark-versioning-and-crypto-unavailability.md`.
This ADR resolves the gap without modifying any higher-priority governing documents.

---

## 3. Policy Decision Made

**CURRENT POLICY = WAIT_FOR_CRYPTO**

Rationale:

- Crypto pair market absence on Polymarket is a scheduling gap, not a platform regime change.
  BTC/ETH/SOL 5m/15m binary pair markets rotate on a schedule and have appeared before.
- The governing authority is `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md`, Benchmark Tape
  Set section:
  > "Never changes mid-experiment-series. When the benchmark needs updating, increment to
  > benchmark_v2.tape_manifest and reset the experiment ledger for the new series. Human
  > decision to bump version. Driven by: significant market regime change, major tape quality
  > improvement (e.g., 3 months of Gold tapes replacing Silver), or strategy overhaul."
- A scheduling gap in one bucket satisfies none of the above criteria.
- Gate 2 is NOT_RUN (not FAILED). The strategy and gate tooling are unaffected.
- benchmark_v2 requires operator authorization, not agent judgment. An AI agent must not
  autonomously trigger benchmark_v2 even if escalation criteria are observed.

---

## 4. Escalation Criteria Written (summary)

Full criteria are documented in the ADR. Key threshold:

**>= 14 calendar days absence = escalation deadline 2026-04-12**

Before triggering benchmark_v2, the operator must document:
1. Last confirmed market slug and timestamp (when a qualifying market was last seen active)
2. Current date confirming the >= 14-day gap (or another criterion applies)
3. Confirmation that no Polymarket announcement indicates near-term return
4. Which of the four escalation criteria (time threshold, format change, strategy overhaul,
   tape quality improvement) applies

See `docs/specs/ADR-benchmark-versioning-and-crypto-unavailability.md` for complete criteria
and the file list for a future benchmark_v2 work packet.

---

## 5. Files Changed

| File | Change |
|---|---|
| `docs/specs/ADR-benchmark-versioning-and-crypto-unavailability.md` | Created — full policy ADR with decision, rationale, escalation criteria, evidence requirements, and benchmark_v2 file list |
| `docs/CURRENT_STATE.md` | Next-step block updated: references ADR, states WAIT_FOR_CRYPTO policy, adds escalation deadline 2026-04-12 |
| `CLAUDE.md` | Added "Benchmark policy lock" guardrail after benchmark pipeline section; lists prohibited improvisation actions and escalation deadline |
| `docs/dev_logs/2026-03-29_crypto_benchmark_policy_decision.md` | This file — mandatory audit trail |

---

## 6. Files NOT Changed (Verification)

These files were not touched and must remain in their current state:

| File | Status |
|---|---|
| `config/benchmark_v1.tape_manifest` | NOT TOUCHED |
| `config/benchmark_v1.lock.json` | NOT TOUCHED |
| `config/benchmark_v1.audit.json` | NOT TOUCHED |
| Any gate tool logic (`tools/gates/*`) | NOT TOUCHED |
| Any roadmap prose (`docs/reference/*`) | NOT TOUCHED |
| Any strategy code (`packages/polymarket/simtrader/strategies/*`) | NOT TOUCHED |
| `config/recovery_corpus_v1.tape_manifest` | NOT TOUCHED |

---

## 7. Next Work Packet

Monitor crypto market availability using the existing polling tool:

```bash
python -m polytool crypto-pair-watch --one-shot   # check once
python -m polytool crypto-pair-watch --watch      # poll continuously
```

When BTC/ETH/SOL 5m/15m pair markets reappear:

1. Capture 12-15 shadow sessions per `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md`
2. Verify corpus: `python tools/gates/capture_status.py`
3. Run corpus audit: `python tools/gates/corpus_audit.py ...` (must exit 0 for 50/50)
4. Run Gate 2: `python tools/gates/close_mm_sweep_gate.py --benchmark-manifest config/recovery_corpus_v1.tape_manifest --out artifacts/gates/gate2_sweep`

If crypto markets remain absent by **2026-04-12**: the operator should review the ADR
escalation criteria and make a benchmark_v2 decision. No agent should act autonomously
at that point.
