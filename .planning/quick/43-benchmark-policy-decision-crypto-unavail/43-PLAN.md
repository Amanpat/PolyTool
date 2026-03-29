---
phase: quick
plan: 43
type: execute
wave: 1
depends_on: []
files_modified:
  - docs/specs/ADR-benchmark-versioning-and-crypto-unavailability.md
  - docs/CURRENT_STATE.md
  - CLAUDE.md
  - docs/dev_logs/2026-03-29_crypto_benchmark_policy_decision.md
autonomous: true
requirements: []
must_haves:
  truths:
    - "A written policy exists answering: wait vs benchmark_v2 escalation criteria"
    - "CURRENT_STATE.md next-step section is unambiguous and consistent with the policy"
    - "CLAUDE.md tells future agents not to mutate benchmark_v1 or improvise around the crypto blocker"
    - "The policy document states the current repo posture (WAIT_FOR_CRYPTO or PREPARE_BENCHMARK_V2_CONTINGENCY)"
  artifacts:
    - path: "docs/specs/ADR-benchmark-versioning-and-crypto-unavailability.md"
      provides: "Policy decision and escalation criteria"
    - path: "docs/dev_logs/2026-03-29_crypto_benchmark_policy_decision.md"
      provides: "Mandatory dev log"
  key_links:
    - from: "CLAUDE.md"
      to: "ADR-benchmark-versioning-and-crypto-unavailability.md"
      via: "cross-reference in crypto-blocker guardrail section"
---

<objective>
Resolve the benchmark policy conflict created by the crypto bucket being unavailable.
The recovery corpus is at 40/50 qualifying tapes; only the crypto=10 bucket is blocked
because Polymarket has no active BTC/ETH/SOL 5m/15m binary pair markets.

The current docs say "continue polling" but provide no written policy for:
- How long to wait before escalating
- What evidence triggers a benchmark_v2 contingency
- What files change in a benchmark_v2 work packet

Purpose: Write the policy down so the next work packet is obvious and future agents
do not improvise or accidentally mutate benchmark_v1.

Output: ADR doc, updated CURRENT_STATE.md next-step, CLAUDE.md guardrail, dev log.
No code changes, no manifest edits, no benchmark_v1 mutation.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/docs/CURRENT_STATE.md
@D:/Coding Projects/Polymarket/PolyTool/CLAUDE.md
@D:/Coding Projects/Polymarket/PolyTool/docs/specs/SPEC-phase1b-corpus-recovery-v1.md
@D:/Coding Projects/Polymarket/PolyTool/docs/specs/SPEC-phase1b-gold-capture-campaign.md
@D:/Coding Projects/Polymarket/PolyTool/docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md
@D:/Coding Projects/Polymarket/PolyTool/docs/dev_logs/2026-03-28_gold_capture_campaign.md
@D:/Coding Projects/Polymarket/PolyTool/docs/dev_logs/2026-03-29_gold_capture_wave2.md

Key facts established by pre-planning research:

CORPUS STATE (2026-03-29):
- Recovery corpus: 40/50 qualifying tapes
- Only crypto=10 bucket is blocked (sports/politics/new_market/near_resolution all complete)
- Polymarket has no active BTC/ETH/SOL 5m/15m binary pair markets as of 2026-03-29
- benchmark_v1 is IMMUTABLE (per SPEC-phase1b-corpus-recovery-v1.md)
- Gate 2 runs against config/recovery_corpus_v1.tape_manifest (NOT benchmark_v1)

DOCUMENT PRIORITY (highest wins):
1. docs/PLAN_OF_RECORD.md
2. docs/ARCHITECTURE.md
3. docs/STRATEGY_PLAYBOOK.md
4. docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md
5. docs/CURRENT_STATE.md

GOVERNING ROADMAP QUOTE (POLYTOOL_MASTER_ROADMAP_v5_1.md, Benchmark Tape Set section):
"Never changes mid-experiment-series. When the benchmark needs updating, increment
to benchmark_v2.tape_manifest and reset the experiment ledger for the new series.
Human decision to bump version. Driven by: significant market regime change, major
tape quality improvement (e.g., 3 months of Gold tapes replacing Silver), or strategy
overhaul."

POLICY DETERMINATION:
The current repo posture is WAIT_FOR_CRYPTO. Rationale:
- Crypto pair markets on Polymarket rotate on a schedule (5m/15m BTC/ETH/SOL)
- Temporary unavailability (days to ~2 weeks) does not constitute a "regime change"
- No strategy overhaul is underway
- benchmark_v2 requires a human decision per the roadmap
- Gate 2 is NOT blocked by a code or strategy problem; it is blocked by market schedule
- The existing crypto-pair-watch tool exists precisely for this polling scenario
- A benchmark_v2 transition would require writing new config files, a new audit baseline,
  and resetting the experiment ledger -- significant overhead for a transient scheduling gap
Benchmark_v2 contingency is the FALLBACK if markets remain absent beyond an operator-defined
threshold (proposed: 14 calendar days from 2026-03-29).

NO IMPLEMENTATION CHANGES ARE MADE IN THIS TASK.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Write ADR — benchmark versioning and crypto unavailability policy</name>
  <files>docs/specs/ADR-benchmark-versioning-and-crypto-unavailability.md</files>
  <action>
Create a new ADR (Architecture Decision Record) at docs/specs/ADR-benchmark-versioning-and-crypto-unavailability.md.

The document must answer all five questions from the task spec:

1. What is the governing rule if a required benchmark bucket is temporarily unavailable live?
2. Under what conditions do we keep waiting versus authorize a benchmark_v2 contingency?
3. Who/what evidence triggers that decision?
4. What exact files would change in a future benchmark_v2 work packet?
5. What is the CURRENT POLICY?

CURRENT POLICY = WAIT_FOR_CRYPTO

Structure the document as follows:

---
# ADR: Benchmark Versioning Policy and Crypto Market Unavailability

**Status:** Active
**Date:** 2026-03-29
**Scope:** config/recovery_corpus_v1 tape capture, benchmark versioning policy
**Does NOT modify:** config/benchmark_v1.tape_manifest, config/benchmark_v1.lock.json, config/benchmark_v1.audit.json

---

## Context

Summarize the situation:
- benchmark_v1 is immutable (SPEC-phase1b-corpus-recovery-v1.md §2)
- Gate 2 runs against config/recovery_corpus_v1.tape_manifest (the recovery corpus), not benchmark_v1
- Recovery corpus is at 40/50; crypto=10 is the only blocker
- Polymarket has no active BTC/ETH/SOL 5m/15m binary pair markets as of 2026-03-29
- All other buckets (sports=15, politics=10, new_market=5, near_resolution=10) are complete
- No gate-core, strategy, or code changes are required; this is purely a market availability gap

## Doc Conflict Identified

Surface the conflict explicitly per document priority rules:
- CORPUS_GOLD_CAPTURE_RUNBOOK.md says: "continue polling with crypto-pair-watch --watch"
- No document defines: how long to wait, what triggers escalation, what benchmark_v2 entails
- This ADR resolves that gap without modifying any higher-priority docs

## Decision: CURRENT POLICY = WAIT_FOR_CRYPTO

State the decision clearly.

Rationale:
- Crypto pair markets on Polymarket (BTC/ETH/SOL 5m/15m up/down pairs) rotate on a schedule.
  Temporary unavailability of a few days to ~2 weeks is the expected pattern, not a
  platform-level regime change.
- The governing roadmap (POLYTOOL_MASTER_ROADMAP_v5_1.md §Benchmark Tape Set) states that
  a benchmark version bump is a "human decision" triggered by "significant market regime
  change, major tape quality improvement, or strategy overhaul." A scheduling gap in one
  bucket does not satisfy any of these criteria.
- benchmark_v2 would require: new tape manifest curation, new audit baseline, and resetting
  the experiment ledger. This overhead is not justified for a transient gap.
- Gate 2 is NOT_RUN (not FAILED). The strategy and gate tooling are unaffected.
- The crypto-pair-watch tool was built specifically for this polling scenario.

## Escalation Criteria: When to Authorize benchmark_v2

Define the threshold explicitly. The operator MUST authorize benchmark_v2 if ANY of:

1. Crypto markets remain absent for >= 14 calendar days from 2026-03-29 (by 2026-04-12),
   AND no concrete Polymarket announcement indicates they will return.
2. Polymarket permanently removes or restructures 5m/15m crypto binary pair format.
3. A strategy overhaul (new MarketMakerV2 or architecture change) requires a fresh baseline.
4. A major tape quality improvement makes the current Silver/Gold mix obsolete
   (e.g., 3+ months of exclusively Gold tapes available for all buckets).

The operator (human) makes this call. An AI agent must NOT autonomously trigger benchmark_v2.

## Evidence Required to Trigger benchmark_v2

Before writing a benchmark_v2 work packet, the operator must document:
- Date crypto markets were last seen active (last confirmed market slug + timestamp)
- Current date - confirms >= 14 calendar day gap, or other criteria met above
- A statement that no Polymarket announcement indicates near-term return
  (check https://polymarket.com/activity and Polymarket Discord/Twitter)

## What Changes in a benchmark_v2 Work Packet

List exactly the files that would change (none of these exist or are modified NOW):

New files to create (all docs-only until authorized):
- config/benchmark_v2_gap_fill.targets.json — new gap-fill targets
- config/benchmark_v2.tape_manifest — new tape manifest (replaces recovery corpus as Gate 2 input)
- config/benchmark_v2.lock.json — immutability lock
- config/benchmark_v2.audit.json — audit record
- docs/specs/SPEC-phase1b-corpus-recovery-v2.md — updated corpus spec

Files that would need updates:
- docs/CURRENT_STATE.md — update Gate 2 manifest reference
- CLAUDE.md — add benchmark_v2 context
- CORPUS_GOLD_CAPTURE_RUNBOOK.md — reference v2 manifest path
- tools/gates/* — any hardcoded benchmark_v1 manifest references

Files that MUST NOT change under any benchmark_v2 work:
- config/benchmark_v1.tape_manifest
- config/benchmark_v1.lock.json
- config/benchmark_v1.audit.json

## Current Action: Continue Polling

The authoritative next command remains:
  python -m polytool crypto-pair-watch --one-shot  # check once
  python -m polytool crypto-pair-watch --watch     # poll until found

When crypto markets appear, capture 12-15 shadow sessions per
docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md, then run:
  python tools/gates/capture_status.py
  python tools/gates/corpus_audit.py ...

When corpus_audit exits 0, proceed to Gate 2:
  python tools/gates/close_mm_sweep_gate.py --benchmark-manifest config/recovery_corpus_v1.tape_manifest ...

Escalation deadline: 2026-04-12 (14 calendar days). If crypto markets have not returned
by then, the operator should initiate the benchmark_v2 decision per criteria above.

## References

- docs/specs/SPEC-phase1b-corpus-recovery-v1.md — recovery corpus contract
- docs/specs/SPEC-phase1b-gold-capture-campaign.md — Gold capture campaign spec
- docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md — capture runbook
- docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md §Benchmark Tape Set — versioning policy
- docs/CURRENT_STATE.md — live corpus count and next-step
---
  </action>
  <verify>File exists at docs/specs/ADR-benchmark-versioning-and-crypto-unavailability.md with sections: Context, Doc Conflict Identified, Decision (WAIT_FOR_CRYPTO), Escalation Criteria, Evidence Required, What Changes in benchmark_v2, Current Action, References. File contains "CURRENT POLICY = WAIT_FOR_CRYPTO".</verify>
  <done>ADR exists. Policy is unambiguous. Escalation criteria and evidence requirements are written. benchmark_v2 file list is documented. No implementation files are touched.</done>
</task>

<task type="auto">
  <name>Task 2: Update CURRENT_STATE.md and CLAUDE.md with policy anchor</name>
  <files>docs/CURRENT_STATE.md, CLAUDE.md</files>
  <action>
Make two targeted doc edits. No code changes. No benchmark_v1 file changes.

### Edit 1: docs/CURRENT_STATE.md

Find the "Next executable step" block near the top of the file (currently around line 67-72).
Replace the current next-step paragraph with a version that:
1. Is unambiguous about the current policy (WAIT_FOR_CRYPTO)
2. Cites the ADR by filename
3. States the escalation deadline
4. Does NOT change the corpus count (40/50) or any other facts in the file

Replace the current next-step block:
  **Next executable step**: Capture remaining 10 crypto Gold tapes (bucket blocked on market
  availability). Use `python -m polytool crypto-pair-watch --watch` to poll for BTC/ETH/SOL
  5m/15m binary pair markets. Once active, capture 12-15 sessions per
  `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md` and verify with
  `python tools/gates/capture_status.py`. Gate 2 unblocks when corpus_audit exits 0 (50/50).
  When ready: `python tools/gates/close_mm_sweep_gate.py --benchmark-manifest config/recovery_corpus_v1.tape_manifest --out artifacts/gates/gate2_sweep`.

With this replacement:
  **Next executable step**: Wait for crypto markets — POLICY = WAIT_FOR_CRYPTO (see
  `docs/specs/ADR-benchmark-versioning-and-crypto-unavailability.md`). The crypto=10 bucket
  is blocked because Polymarket has no active BTC/ETH/SOL 5m/15m binary pair markets as of
  2026-03-29. All other buckets are complete (40/50).

  Poll for market return:
  ```
  python -m polytool crypto-pair-watch --one-shot  # check once
  python -m polytool crypto-pair-watch --watch     # poll continuously
  ```
  When markets appear, capture 12-15 shadow sessions (per
  `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md`) and verify with
  `python tools/gates/capture_status.py`. Gate 2 unblocks when `corpus_audit.py` exits 0 (50/50).
  Gate 2 command (when ready):
  `python tools/gates/close_mm_sweep_gate.py --benchmark-manifest config/recovery_corpus_v1.tape_manifest --out artifacts/gates/gate2_sweep`

  **Escalation deadline:** If crypto markets remain absent by 2026-04-12 (14 days), the operator
  must review the ADR escalation criteria for benchmark_v2. No AI agent should autonomously
  trigger benchmark_v2. Do NOT modify config/benchmark_v1.* files under any circumstance.

### Edit 2: CLAUDE.md

Find the Gate 2 section in CLAUDE.md. It currently reads (near the section on Gate 2):
  "Gate 2: NOT_RUN (2026-03-29) — 40/50 tapes qualify after Gold capture waves 1+2..."
  and ends with "Use `python -m polytool crypto-pair-watch --one-shot` to check."

After that existing "Crypto bucket blocked:" note, add a new note:
  **Benchmark policy lock:** WAIT_FOR_CRYPTO is the current policy (ADR:
  `docs/specs/ADR-benchmark-versioning-and-crypto-unavailability.md`).
  Do NOT: modify config/benchmark_v1.tape_manifest, config/benchmark_v1.lock.json, or
  config/benchmark_v1.audit.json. Do NOT improvise around the crypto blocker by:
  - Lowering the min_events=50 threshold
  - Relaxing the Gate 2 >= 70% pass condition
  - Substituting non-crypto tapes into the crypto bucket
  - Treating Gate 2 NOT_RUN as a gate failure
  - Autonomously triggering benchmark_v2
  Escalation deadline for benchmark_v2 consideration: 2026-04-12. Human decision required.

IMPORTANT: Only add/modify the specific sections described above. Do not reformat or
restructure other parts of CURRENT_STATE.md or CLAUDE.md. Preserve all existing content.
Read the files first, make surgical edits, write the result.
  </action>
  <verify>
1. docs/CURRENT_STATE.md contains "POLICY = WAIT_FOR_CRYPTO" and "2026-04-12" and "ADR-benchmark-versioning-and-crypto-unavailability". Corpus count still reads 40/50. benchmark_v1 files not mentioned as needing modification.
2. CLAUDE.md contains "Benchmark policy lock" guardrail text with "Do NOT modify config/benchmark_v1" and "2026-04-12".
3. Neither file has its benchmark_v1 config lines changed.
  </verify>
  <done>Both files updated. Next-step in CURRENT_STATE.md is unambiguous. CLAUDE.md prevents future agent improvisation around the crypto blocker.</done>
</task>

<task type="auto">
  <name>Task 3: Write mandatory dev log</name>
  <files>docs/dev_logs/2026-03-29_crypto_benchmark_policy_decision.md</files>
  <action>
Create docs/dev_logs/2026-03-29_crypto_benchmark_policy_decision.md.

The dev log should document:

**Header:**
- Date: 2026-03-29
- Quick task: quick-043
- Branch: phase-1B
- Decision: WAIT_FOR_CRYPTO

**Sections:**

1. Why This Was Executed
   - Wave 2 Gold capture (quick-041) completed sports/politics/new_market buckets
   - Only crypto=10 remains; Polymarket has no active 5m/15m pair markets
   - No written policy existed for: how long to wait, escalation criteria, benchmark_v2 trigger
   - This task writes the policy down

2. Doc Conflict Found
   - CORPUS_GOLD_CAPTURE_RUNBOOK.md: "continue polling" (correct but open-ended)
   - No doc defined escalation criteria or benchmark_v2 trigger conditions
   - CURRENT_STATE.md next-step was accurate but did not reference a policy decision
   - Resolution: ADR written at docs/specs/ADR-benchmark-versioning-and-crypto-unavailability.md

3. Policy Decision Made
   - CURRENT POLICY = WAIT_FOR_CRYPTO
   - Rationale: crypto pair market absence is a scheduling gap, not a platform regime change
   - Governing authority: POLYTOOL_MASTER_ROADMAP_v5_1.md §Benchmark Tape Set — "Human
     decision to bump version. Driven by: significant market regime change..."
   - benchmark_v2 requires operator authorization, not agent judgment

4. Escalation Criteria Written (summary)
   - See full criteria in ADR
   - Key threshold: >= 14 calendar days absence (2026-04-12 deadline)
   - Required evidence before triggering benchmark_v2

5. Files Changed
   | File | Change |
   |---|---|
   | docs/specs/ADR-benchmark-versioning-and-crypto-unavailability.md | Created — policy ADR |
   | docs/CURRENT_STATE.md | Next-step updated with policy reference and escalation deadline |
   | CLAUDE.md | Added benchmark policy lock guardrail |
   | docs/dev_logs/2026-03-29_crypto_benchmark_policy_decision.md | This file |

6. Files NOT Changed (Verification)
   - config/benchmark_v1.tape_manifest — NOT TOUCHED
   - config/benchmark_v1.lock.json — NOT TOUCHED
   - config/benchmark_v1.audit.json — NOT TOUCHED
   - Any gate tool logic — NOT TOUCHED
   - Any roadmap prose — NOT TOUCHED
   - Any strategy code — NOT TOUCHED

7. Next Work Packet
   Monitor crypto market availability:
   ```
   python -m polytool crypto-pair-watch --one-shot
   python -m polytool crypto-pair-watch --watch
   ```
   When markets appear: capture 12-15 sessions, verify corpus (capture_status.py), run Gate 2.
   If still absent by 2026-04-12: operator reviews ADR escalation criteria for benchmark_v2.
  </action>
  <verify>File exists at docs/dev_logs/2026-03-29_crypto_benchmark_policy_decision.md. Contains "WAIT_FOR_CRYPTO", "2026-04-12", "Files NOT Changed" table confirming no benchmark_v1 mutations.</verify>
  <done>Dev log exists. Audit trail is complete. The task is documented.</done>
</task>

</tasks>

<verification>
After all three tasks:

1. docs/specs/ADR-benchmark-versioning-and-crypto-unavailability.md exists and contains:
   - "CURRENT POLICY = WAIT_FOR_CRYPTO"
   - Escalation criteria with "2026-04-12"
   - Exact file list for a future benchmark_v2 work packet
   - "Human decision required" — no autonomous benchmark_v2

2. docs/CURRENT_STATE.md:
   - Still shows corpus count = 40/50
   - Next-step references ADR file by name
   - Contains escalation deadline
   - config/benchmark_v1.* files not modified

3. CLAUDE.md:
   - Contains "Benchmark policy lock" section
   - Lists prohibited improvisation actions
   - Contains escalation deadline 2026-04-12

4. docs/dev_logs/2026-03-29_crypto_benchmark_policy_decision.md exists

5. No code files touched. No config/benchmark_v1.* files touched.
</verification>

<success_criteria>
- Any future agent reading CLAUDE.md knows: do not touch benchmark_v1, do not improvise around crypto blocker, WAIT_FOR_CRYPTO policy is in effect.
- Any future agent reading CURRENT_STATE.md knows the exact next step and when to escalate.
- The policy ADR gives the operator clear criteria for when and how to authorize benchmark_v2.
- The dev log provides an audit trail.
- Zero implementation or manifest changes in this task.
</success_criteria>

<output>
After completion, create `.planning/quick/43-benchmark-policy-decision-crypto-unavail/43-SUMMARY.md` with:
- Decision made: WAIT_FOR_CRYPTO
- Escalation deadline: 2026-04-12
- Files created: ADR, dev log
- Files updated: CURRENT_STATE.md, CLAUDE.md
- Files NOT touched: all config/benchmark_v1.* files, all gate tools, all strategy code
- Next work packet: monitor crypto-pair-watch; capture when markets return; escalate to benchmark_v2 review if still absent by 2026-04-12
</output>
