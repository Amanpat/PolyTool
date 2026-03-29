# ADR: Benchmark Versioning Policy and Crypto Market Unavailability

**Status:** Active
**Date:** 2026-03-29
**Scope:** config/recovery_corpus_v1 tape capture, benchmark versioning policy
**Does NOT modify:** config/benchmark_v1.tape_manifest, config/benchmark_v1.lock.json, config/benchmark_v1.audit.json

---

## Context

The recovery corpus is the live-capture tape set that Gate 2 runs against. It is distinct from
benchmark_v1, which is immutable and closed as of 2026-03-21.

Key facts as of 2026-03-29:

- **benchmark_v1 is immutable.** Per `docs/specs/SPEC-phase1b-corpus-recovery-v1.md` section 2,
  `config/benchmark_v1.tape_manifest`, `config/benchmark_v1.lock.json`, and
  `config/benchmark_v1.audit.json` must never be modified. They are the permanent experiment
  baseline.
- **Gate 2 runs against `config/recovery_corpus_v1.tape_manifest`** (the live-capture recovery
  corpus), not against benchmark_v1. This was established when the Gate 2 diagnostic revealed
  that benchmark_v1's 10/50 qualifying tapes were insufficient and a Gold capture campaign was
  needed.
- **Recovery corpus is at 40/50 qualifying tapes.** Four of five buckets are complete:
  - politics = 10/10 (complete)
  - sports = 15/15 (complete)
  - near_resolution = 10/10 (complete)
  - new_market = 5/5 (complete)
  - crypto = 0/10 (blocked)
- **Polymarket has no active BTC/ETH/SOL 5m/15m binary pair markets as of 2026-03-29.**
  The crypto=10 bucket requires 10 qualifying Gold tapes from these markets. The markets are
  temporarily unavailable; they rotate on a schedule.
- No gate-core, strategy, or code changes are required to resolve the crypto bucket shortage.
  This is purely a market availability scheduling gap.

---

## Doc Conflict Identified

Before this ADR, there was a gap in the governing documentation:

- `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md` says: "continue polling with
  `crypto-pair-watch --watch`." This is correct but open-ended.
- No document defined: how long to wait before escalating, what evidence triggers a benchmark_v2
  contingency, or what files a benchmark_v2 work packet would change.
- `docs/CURRENT_STATE.md` next-step was accurate about the immediate action but did not
  reference a policy decision or escalation threshold.

This ADR resolves that gap without modifying any higher-priority governing documents.

---

## Decision: CURRENT POLICY = WAIT_FOR_CRYPTO

The current repo posture is **WAIT_FOR_CRYPTO**.

### Rationale

1. **Crypto pair markets rotate on a schedule.** BTC/ETH/SOL 5m/15m up/down binary pair
   markets on Polymarket are a recurring fixture, not a discontinued product category. Temporary
   absence of a few days to approximately two weeks is the expected pattern for this market type,
   not a platform-level regime change.

2. **The governing roadmap requires a human decision to bump benchmark version.** From
   `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md`, Benchmark Tape Set section:
   > "Never changes mid-experiment-series. When the benchmark needs updating, increment to
   > benchmark_v2.tape_manifest and reset the experiment ledger for the new series. Human
   > decision to bump version. Driven by: significant market regime change, major tape quality
   > improvement (e.g., 3 months of Gold tapes replacing Silver), or strategy overhaul."
   A scheduling gap in one bucket satisfies none of these criteria.

3. **benchmark_v2 carries significant overhead for a transient gap.** A benchmark_v2 work
   packet requires: new tape manifest curation, new audit baseline, and resetting the experiment
   ledger. This overhead is not justified while the platform is expected to re-list these markets.

4. **Gate 2 is NOT_RUN, not FAILED.** The strategy and gate tooling are fully implemented and
   correct. The gate has not been invalidated by a strategy problem or a code defect. It is
   simply waiting for corpus completion.

5. **The crypto-pair-watch tool was built for exactly this scenario.** The polling infrastructure
   already exists. The correct action is to use it.

---

## Escalation Criteria: When to Authorize benchmark_v2

The operator MUST initiate a benchmark_v2 decision if ANY of the following conditions are met:

1. **Time threshold (primary trigger):** Crypto markets remain absent for >= 14 calendar days
   from 2026-03-29, i.e., by **2026-04-12**, AND no concrete Polymarket announcement indicates
   they will return within a further 7-day window.

2. **Format change:** Polymarket permanently removes or restructures the 5m/15m crypto binary
   pair market format such that no equivalent replacement markets exist.

3. **Strategy overhaul:** A new MarketMakerV2 or equivalent architecture change requires a
   fresh baseline that is incompatible with the recovery_corpus_v1 design.

4. **Major tape quality improvement:** Three or more months of exclusively Gold-tier tapes
   become available for all five buckets, making the current Silver/Gold mixed corpus obsolete.

**The operator (human) makes this call.** An AI agent must NOT autonomously trigger benchmark_v2
under any circumstance, even if escalation criteria are met. The agent should document the
observation and halt for operator review.

---

## Evidence Required to Trigger benchmark_v2

Before authorizing a benchmark_v2 work packet, the operator must document:

1. **Last confirmed market slug and timestamp** — the most recent date a qualifying
   BTC/ETH/SOL 5m/15m pair market was seen active on Polymarket.
2. **Current date confirmation** — confirms that >= 14 calendar days have elapsed since
   that last observation (or that another escalation criterion applies).
3. **No pending return announcement** — a brief check of:
   - https://polymarket.com/activity (active markets list)
   - Polymarket Discord / Twitter for announcements
   - A `crypto-pair-watch --one-shot` run confirming no markets are live
4. **Applicable escalation criterion** — state which of the four criteria above is met.

This evidence should be recorded in the benchmark_v2 work packet spec before any config files
are created.

---

## What Changes in a benchmark_v2 Work Packet

The following files would be created or updated in a benchmark_v2 work packet. None of these
files exist or are modified as part of this ADR — this is a reference list only.

### New files to create (docs-only reference, not active)

| File | Purpose |
|---|---|
| `config/benchmark_v2_gap_fill.targets.json` | New gap-fill targets for v2 corpus |
| `config/benchmark_v2.tape_manifest` | New tape manifest (replaces recovery_corpus_v1 as Gate 2 input) |
| `config/benchmark_v2.lock.json` | Immutability lock for v2 manifest |
| `config/benchmark_v2.audit.json` | Audit record for v2 manifest |
| `docs/specs/SPEC-phase1b-corpus-recovery-v2.md` | Updated corpus recovery spec |

### Files that would need updates

| File | Change needed |
|---|---|
| `docs/CURRENT_STATE.md` | Update Gate 2 manifest reference from recovery_corpus_v1 to benchmark_v2 |
| `CLAUDE.md` | Add benchmark_v2 context and update benchmark policy lock |
| `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md` | Reference v2 manifest path |
| `tools/gates/*` | Update any hardcoded benchmark_v1 or recovery_corpus_v1 manifest references |

### Files that MUST NOT change under any benchmark_v2 work

These three files are permanently immutable and must never be modified under any circumstance:

- `config/benchmark_v1.tape_manifest`
- `config/benchmark_v1.lock.json`
- `config/benchmark_v1.audit.json`

---

## Current Action: Continue Polling

The authoritative next step is to poll for crypto market availability using the existing tool:

```bash
python -m polytool crypto-pair-watch --one-shot   # check once
python -m polytool crypto-pair-watch --watch      # poll continuously until markets appear
```

When crypto pair markets reappear, capture 12-15 shadow sessions per
`docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md`, then verify corpus completion:

```bash
python tools/gates/capture_status.py              # check current shortage
python tools/gates/corpus_audit.py ...            # full audit; exits 0 when 50/50
```

When `corpus_audit.py` exits 0 (50/50 qualifying tapes), proceed to Gate 2:

```bash
python tools/gates/close_mm_sweep_gate.py \
  --benchmark-manifest config/recovery_corpus_v1.tape_manifest \
  --out artifacts/gates/gate2_sweep
```

**Escalation deadline:** 2026-04-12 (14 calendar days from 2026-03-29). If crypto markets have
not returned by that date, the operator should initiate the benchmark_v2 decision per the
escalation criteria above. No AI agent should make this call autonomously.

---

## References

- `docs/specs/SPEC-phase1b-corpus-recovery-v1.md` — recovery corpus contract (immutability rule)
- `docs/specs/SPEC-phase1b-gold-capture-campaign.md` — Gold capture campaign spec
- `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md` — capture runbook and polling instructions
- `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md` §Benchmark Tape Set — versioning policy and
  human-decision requirement
- `docs/CURRENT_STATE.md` — live corpus count (40/50) and next-step (updated to reference this ADR)
