---
phase: quick
plan: 260414-rez
type: execute
wave: 1
depends_on: []
files_modified:
  - docs/dev_logs/2026-04-14_gate2_next_step_packet.md
  - docs/CURRENT_STATE.md
  - CLAUDE.md
autonomous: true
requirements: []
must_haves:
  truths:
    - "Crypto market availability is checked via crypto-pair-watch --one-shot on 2026-04-14"
    - "Exactly ONE of two verdict paths is produced: RESUME_CRYPTO_CAPTURE or BENCHMARK_V2_DECISION_PRECONDITIONS_MET"
    - "If verdict is RESUME_CRYPTO_CAPTURE: a capture execution packet exists with exact commands"
    - "If verdict is BENCHMARK_V2_DECISION_PRECONDITIONS_MET: a human-decision evidence packet exists with all ADR-required evidence fields"
    - "No benchmark_v2 config files are created in either path"
    - "No benchmark_v1 artifacts are modified"
    - "CLAUDE.md Gate 2 status reflects FAILED (not the stale NOT_RUN)"
  artifacts:
    - path: "docs/dev_logs/2026-04-14_gate2_next_step_packet.md"
      provides: "Dev log with verdict, evidence, and next-step packet"
    - path: "CLAUDE.md"
      provides: "Truth-synced Gate 2 status and escalation deadline note"
  key_links:
    - from: "docs/specs/ADR-benchmark-versioning-and-crypto-unavailability.md"
      to: "docs/dev_logs/2026-04-14_gate2_next_step_packet.md"
      via: "escalation criteria referenced by evidence packet"
      pattern: "ADR.*escalation"
---

<objective>
Produce the correct Gate 2 next-step packet based on live crypto market availability.

Purpose: The ADR escalation deadline (2026-04-12) has passed. Today is 2026-04-14. The executor
must check crypto market status and produce one of two outcomes:
  (A) If crypto 5m markets are active: a capture execution packet with exact operator commands
  (B) If crypto 5m markets are NOT active: a benchmark_v2 human-decision evidence packet
      documenting all ADR-required evidence, halting for operator review, with NO autonomous
      policy action and NO v2 config files.

Additionally, CLAUDE.md contains a stale Gate 2 status ("currently NOT_RUN") that must be
corrected to FAILED (7/50 = 14%) to match the authoritative CURRENT_STATE.md.

Output: Dev log with verdict + packet, truth-synced CLAUDE.md, optionally updated CURRENT_STATE.md
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@docs/CURRENT_STATE.md
@docs/specs/ADR-benchmark-versioning-and-crypto-unavailability.md
@docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md
@docs/dev_logs/2026-04-14_gate2_fill_diagnosis.md
@docs/dev_logs/2026-04-14_gate2_corpus_visibility_and_ranking.md
@docs/dev_logs/2026-04-14_post_capture_qualification_workflow.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Check crypto market availability and produce verdict-appropriate packet</name>
  <files>docs/dev_logs/2026-04-14_gate2_next_step_packet.md</files>
  <action>
Step 1 -- Check crypto market availability:

```bash
python -m polytool crypto-pair-watch --one-shot
```

Capture the output. This tells us whether BTC/ETH/SOL 5m/15m binary pair markets
are currently active on Polymarket.

Step 2 -- Determine verdict:

IF crypto markets ARE active (crypto-pair-watch reports one or more active markets):
  verdict = RESUME_CRYPTO_CAPTURE

IF crypto markets are NOT active:
  Check: today (2026-04-14) is past the ADR escalation deadline (2026-04-12).
  verdict = BENCHMARK_V2_DECISION_PRECONDITIONS_MET

Step 3 -- Write the dev log with the appropriate packet:

Create `docs/dev_logs/2026-04-14_gate2_next_step_packet.md` with this structure:

```markdown
# Gate 2 Next-Step Packet

**Date:** 2026-04-14
**Task:** quick-260414-rez
**Status:** COMPLETE

---

## Verdict: {RESUME_CRYPTO_CAPTURE | BENCHMARK_V2_DECISION_PRECONDITIONS_MET}

### Evidence

1. **crypto-pair-watch --one-shot output (2026-04-14):**
   {paste exact output}

2. **Current corpus status:**
   - Recovery corpus: 40/50 qualifying tapes (crypto = 0/10 blocked)
   - Gate 2 last run: FAILED (7/50 = 14%) on 2026-03-29 against 50-tape corpus
   - Root cause: Silver tapes produce zero fills (no L2 book data);
     crypto 5m Gold tapes were 7/10 positive (strongest bucket)
   - See: docs/dev_logs/2026-04-14_gate2_fill_diagnosis.md

3. **ADR escalation deadline status:**
   - Deadline: 2026-04-12 (14 calendar days from 2026-03-29)
   - Today: 2026-04-14 (2 days past deadline)
   - ADR: docs/specs/ADR-benchmark-versioning-and-crypto-unavailability.md

{THEN include exactly ONE of the two sections below}
```

--- PATH A: RESUME_CRYPTO_CAPTURE ---

If verdict is RESUME_CRYPTO_CAPTURE, include this section:

```markdown
## Execution Packet: Resume Crypto Gold Capture

Crypto 5m markets are active. Resume the Gold capture campaign to fill the
crypto=10 bucket shortage.

### Prerequisites

Confirm before capture:
- Docker running: `docker compose ps`
- ClickHouse accessible: `curl "http://localhost:8123/?query=SELECT%201"`
- CLICKHOUSE_PASSWORD set: `echo $CLICKHOUSE_PASSWORD`
- CLI loads: `python -m polytool --help`

### Capture Commands

For each active crypto 5m market slug reported by crypto-pair-watch:

```bash
# Check which crypto markets are live
python -m polytool crypto-pair-watch --one-shot

# Capture one tape per active market (repeat for 10+ sessions)
python -m polytool simtrader shadow \
    --market <SLUG> \
    --strategy market_maker_v1 \
    --duration 600 \
    --record-tape \
    --tape-dir "artifacts/simtrader/tapes/crypto_<SLUG>_$(date -u +%Y%m%dT%H%M%SZ)"
```

### Post-Capture Validation

After each batch:
```bash
# Quick batch qualification check
python tools/gates/qualify_gold_batch.py \
    --tape-dirs artifacts/simtrader/tapes/crypto_*

# Full corpus audit (when batch looks good)
python tools/gates/corpus_audit.py \
    --tape-roots artifacts/simtrader/tapes \
    --tape-roots artifacts/silver \
    --tape-roots artifacts/tapes \
    --out-dir artifacts/corpus_audit \
    --manifest-out config/recovery_corpus_v1.tape_manifest
```

### Stopping Condition

When corpus_audit.py exits 0 (50/50 qualifying tapes including crypto=10),
run Gate 2:

```bash
python tools/gates/close_mm_sweep_gate.py \
    --benchmark-manifest config/recovery_corpus_v1.tape_manifest \
    --out artifacts/gates/gate2_sweep
```

### ADR Deadline Note

The ADR escalation deadline (2026-04-12) has passed, but crypto markets are
now active, so WAIT_FOR_CRYPTO policy remains appropriate. Capture should proceed.
If markets go offline again before 10 crypto tapes are captured, re-evaluate
for benchmark_v2 at that point.
```

--- PATH B: BENCHMARK_V2_DECISION_PRECONDITIONS_MET ---

If verdict is BENCHMARK_V2_DECISION_PRECONDITIONS_MET, include this section:

```markdown
## Human-Decision Packet: benchmark_v2 Preconditions Met

The ADR escalation deadline has passed and crypto markets remain unavailable.
Per ADR-benchmark-versioning-and-crypto-unavailability.md section "Escalation
Criteria", the operator MUST now make a decision about benchmark_v2.

**This packet presents evidence. It does NOT create any config files or
change any policy. The human operator must make the call.**

### ADR-Required Evidence (all four fields)

1. **Last confirmed market slug and timestamp:**
   BTC/ETH/SOL 5m/15m markets were last confirmed active on 2026-03-29
   during quick-045 crypto capture session. Slugs used at that time included
   btc-updown and eth-updown 5m pair markets.

2. **Current date confirmation:**
   2026-04-14. That is 16 calendar days since last observation (2026-03-29),
   exceeding the ADR's 14-day threshold by 2 days.

3. **No pending return announcement:**
   - crypto-pair-watch --one-shot output: {paste output showing no markets}
   - Operator should also check:
     - https://polymarket.com/activity (crypto pair markets section)
     - Polymarket Discord / Twitter for upcoming market announcements
   - If any announcement indicates markets returning within 7 days,
     the escalation can be deferred per ADR criterion #1.

4. **Applicable escalation criterion:**
   Criterion #1 (time threshold): >= 14 calendar days without crypto markets
   and no concrete announcement of return within 7 days.

### Operator Decision Options

**Option A: Authorize benchmark_v2**
- Create benchmark_v2 work packet per ADR section "What Changes in a
  benchmark_v2 Work Packet"
- This requires: new tape manifest, new audit baseline, experiment ledger reset
- Consider: modify crypto bucket to use different market types, or drop
  crypto bucket entirely and run Gate 2 on 40/50 non-crypto tapes

**Option B: Extend WAIT_FOR_CRYPTO**
- If operator believes crypto 5m markets will return soon
- Update the ADR deadline to a new date
- Document the rationale for extension

**Option C: Redefine Gate 2 scope**
- Run Gate 2 on the 40/50 non-crypto tapes that already exist
- Crypto bucket (10 tapes) excluded or replaced with different market type
- Requires spec change to SPEC-phase1b-corpus-recovery-v1.md
- Note: crypto 5m tapes were the strongest bucket (7/10 positive) so excluding
  them weakens the overall pass rate

### What This Packet Does NOT Do

- Does NOT create config/benchmark_v2.* files
- Does NOT modify config/benchmark_v1.* files
- Does NOT modify config/recovery_corpus_v1.* files
- Does NOT change any gate thresholds or pass criteria
- Does NOT autonomously select an option -- human decision required
```

--- End of path-specific sections ---

Both paths end with:

```markdown
## Open Questions

1. Should CURRENT_STATE.md Gate 2 section be updated to reflect the current
   verdict and date? (Answer: yes, Task 2 handles this.)

## Files Changed

| File | Action |
|------|--------|
| docs/dev_logs/2026-04-14_gate2_next_step_packet.md | Created -- this file |

## Codex Review

Tier: Skip (docs-only, no execution paths).
```
  </action>
  <verify>
    <automated>python -c "import pathlib; p=pathlib.Path('docs/dev_logs/2026-04-14_gate2_next_step_packet.md'); assert p.exists(), 'dev log missing'; text=p.read_text(); assert 'Verdict:' in text, 'no verdict'; assert 'RESUME_CRYPTO_CAPTURE' in text or 'BENCHMARK_V2_DECISION_PRECONDITIONS_MET' in text, 'no verdict type'; assert 'benchmark_v2' not in str(list(pathlib.Path('config').glob('benchmark_v2*'))), 'v2 config created'; print('PASS')"</automated>
  </verify>
  <done>
    - Dev log exists at docs/dev_logs/2026-04-14_gate2_next_step_packet.md
    - Contains exactly one of two verdicts: RESUME_CRYPTO_CAPTURE or BENCHMARK_V2_DECISION_PRECONDITIONS_MET
    - If RESUME_CRYPTO_CAPTURE: contains exact capture commands, prerequisites, stopping condition
    - If BENCHMARK_V2_DECISION_PRECONDITIONS_MET: contains all four ADR-required evidence fields, three operator options, explicit "does NOT do" guardrails
    - No config/benchmark_v2.* files exist
    - No config/benchmark_v1.* files modified
  </done>
</task>

<task type="auto">
  <name>Task 2: Truth-sync CLAUDE.md and CURRENT_STATE.md Gate 2 wording</name>
  <files>CLAUDE.md, docs/CURRENT_STATE.md</files>
  <action>
CLAUDE.md has three stale statements that need surgical correction:

1. **Line ~157**: "Gate 2 is currently NOT_RUN (not FAILED): the corpus has only 10/50 qualifying tapes."
   REPLACE WITH: "Gate 2 was run on 2026-03-29 and FAILED (7/50 = 14%, threshold 70%). Root cause:
   Silver tapes produce zero fills (no L2 book data); crypto 5m Gold tapes were the strongest
   bucket at 7/10 positive. See docs/dev_logs/2026-04-14_gate2_fill_diagnosis.md."

2. **Line ~177**: "Escalation deadline for benchmark_v2 consideration: **2026-04-12**. Human decision required."
   REPLACE WITH: "Escalation deadline for benchmark_v2 consideration: **2026-04-12** (PASSED as of 2026-04-14).
   Human decision required. See docs/dev_logs/2026-04-14_gate2_next_step_packet.md for evidence packet."

3. **Line ~175**: "Treating Gate 2 NOT_RUN as a gate failure"
   This line is in the "Do NOT" list under benchmark policy lock. It should be updated to:
   "Treating Gate 2 FAILED as justification to weaken gate thresholds"
   (Because Gate 2 is no longer NOT_RUN -- it is FAILED. The original intent was to prevent
   premature action on incomplete data, but the data is now complete and the gate has been run.)

ALSO check CURRENT_STATE.md for any wording that conflicts with the verdict from Task 1.
Specifically:
- The "Next executable step" section (~line 174) references Gate 2 FAILED with three options.
  Add a line noting the ADR escalation deadline has passed and pointing to the new dev log.
- The "Escalation deadline" line (~line 193-195) should note deadline PASSED.

IMPORTANT CONSTRAINTS:
- Do NOT rewrite large sections. Make surgical line-level edits only.
- Do NOT change any gate thresholds, pass criteria, or policy language.
- Do NOT remove any items from the "Do NOT" list -- only update outdated factual claims.
- Do NOT touch config/benchmark_v1.* files.
  </action>
  <verify>
    <automated>python -c "text=open('CLAUDE.md').read(); assert 'NOT_RUN (not FAILED)' not in text, 'stale NOT_RUN still in CLAUDE.md'; assert 'FAILED' in text, 'FAILED not in CLAUDE.md'; print('CLAUDE.md: PASS'); text2=open('docs/CURRENT_STATE.md').read(); assert 'Escalation' in text2, 'no escalation ref in CURRENT_STATE'; print('CURRENT_STATE.md: PASS')"</automated>
  </verify>
  <done>
    - CLAUDE.md no longer says "Gate 2 is currently NOT_RUN"
    - CLAUDE.md says Gate 2 FAILED (7/50 = 14%) with root cause reference
    - CLAUDE.md escalation deadline line notes "PASSED as of 2026-04-14"
    - CURRENT_STATE.md escalation deadline section updated
    - No gate thresholds, pass criteria, or policy language weakened
    - No config files touched
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| crypto-pair-watch output | Network call to Polymarket API; output may change between runs |
| ADR policy interpretation | AI interprets escalation criteria but must NOT act on them |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-rez-01 | T (Tampering) | benchmark_v1 config files | mitigate | Plan explicitly prohibits touching config/benchmark_v1.* -- verify block in Task 1 |
| T-rez-02 | E (Elevation) | benchmark_v2 autonomous creation | mitigate | Plan explicitly prohibits creating config/benchmark_v2.* -- verify block in Task 1; human-decision packet presents options without acting |
| T-rez-03 | T (Tampering) | Gate threshold weakening | accept | No code files touched; docs-only plan. Gate thresholds live in code, not docs. |
</threat_model>

<verification>
1. `docs/dev_logs/2026-04-14_gate2_next_step_packet.md` exists and contains a verdict
2. No `config/benchmark_v2.*` files exist
3. No `config/benchmark_v1.*` files were modified (check git diff)
4. CLAUDE.md no longer contains "NOT_RUN (not FAILED)"
5. CLAUDE.md contains "FAILED" for Gate 2
6. CURRENT_STATE.md references the escalation deadline status
</verification>

<success_criteria>
- Operator has a clear, actionable next-step document for Gate 2
- If crypto markets are live: operator can immediately start capturing with copy-paste commands
- If crypto markets are not live: operator has a complete evidence packet to make the benchmark_v2 decision, with no AI having made that decision for them
- CLAUDE.md and CURRENT_STATE.md reflect ground truth as of 2026-04-14
- Zero config files created or modified
</success_criteria>

<output>
After completion, create `.planning/quick/260414-rez-gate-2-next-step-packet-crypto-capture-r/260414-rez-SUMMARY.md`
</output>
