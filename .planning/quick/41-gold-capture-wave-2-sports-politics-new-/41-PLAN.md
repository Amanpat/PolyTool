---
phase: quick-041
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - artifacts/tapes/shadow/
  - docs/CURRENT_STATE.md
  - docs/dev_logs/2026-03-29_gold_capture_wave2.md
autonomous: false
requirements: [PHASE1B-CORPUS]

must_haves:
  truths:
    - "capture_status.py before/after counts are recorded"
    - "New qualifying tapes written to artifacts/tapes/shadow/"
    - "Shadow tapes not left in artifacts/simtrader/tapes/ (path drift fix applied)"
    - "Residual shortage table produced (before/after/remaining/Gate2 status)"
    - "docs/CURRENT_STATE.md updated with new corpus count and next step"
    - "Dev log at docs/dev_logs/2026-03-29_gold_capture_wave2.md written"
  artifacts:
    - path: "docs/dev_logs/2026-03-29_gold_capture_wave2.md"
      provides: "Mandatory audit trail with commands, before/after counts, residual table, GATE2_READY or MORE_GOLD_NEEDED verdict"
    - path: "docs/CURRENT_STATE.md"
      provides: "Updated corpus count and next executable step"
  key_links:
    - from: "simtrader shadow --record-tape"
      to: "artifacts/tapes/shadow/"
      via: "manual mv after capture"
      pattern: "mv artifacts/simtrader/tapes/ artifacts/tapes/shadow/"
---

<objective>
Push Phase 1B corpus coverage using sports, politics, and new_market buckets.
Crypto is blocked (no active BTC/ETH/SOL markets). Starting from 27/50 qualifying
tapes, capture as many of the remaining 13 reachable tapes as possible (sports=5,
politics=3, new_market=5) using live shadow recording.

Purpose: Advance corpus toward the 50-tape Gate 2 threshold. Every qualifying tape
captured brings Gate 2 (scenario sweep) closer to runnable.

Output: New Gold tapes in artifacts/tapes/shadow/, updated CURRENT_STATE.md, dev log
with exact residual counts, and a GATE2_READY or MORE_GOLD_NEEDED verdict.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@docs/CURRENT_STATE.md
@docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md
@docs/dev_logs/2026-03-28_gold_capture_campaign.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Pre-capture snapshot and targeted shadow capture</name>
  <files>artifacts/tapes/shadow/</files>
  <action>
Run pre-capture snapshot, then execute targeted capture for sports, politics, and new_market
buckets. Path drift fix is mandatory after every session.

Step 1 — Pre-capture snapshot (record exact numbers):
```bash
python tools/gates/capture_status.py
```
Record the full table output. This is the "before" baseline.

Step 2 — Find capture targets per bucket:
```bash
# See shortage-ranked candidates (new_market and shortage buckets surface first)
python -m polytool simtrader quickrun --list-candidates 20
```
Use this output to identify slugs for sports, politics, and new_market.

For new_market specifically, browse Polymarket for markets listed in the past 7 days
(recency matters — a market is only new_market-qualified for a short window).

Step 3 — Capture loop. For each target market, run:
```bash
python -m polytool simtrader shadow \
    --market <SLUG> \
    --strategy market_maker_v1 \
    --duration 600 \
    --record-tape
```
If the market is low-activity or the tape comes back too_short, rerun with --duration 900.

Bucket-to-market mapping (from runbook):
- sports: NHL, NBA, EPL, NCAA match markets (active game day fixtures preferred)
- politics: US/international election or policy outcome markets
- new_market: anything on Polymarket front page listed within the past 7 days

Aim to run enough sessions to fill remaining quotas:
- sports: need 5 more (capture 7-10 sessions to account for too_short rejects)
- politics: need 3 more (capture 5-6 sessions)
- new_market: need 5 more (capture 7-8 sessions; recency makes these time-sensitive)

Step 4 — Path drift fix (REQUIRED after every capture session):
```bash
for dir in artifacts/simtrader/tapes/*/; do
    dirname=$(basename "$dir")
    mv "$dir" "artifacts/tapes/shadow/$dirname"
done
```
If artifacts/simtrader/tapes/ is empty, the fix already applied or no tapes were written
to the default path — that is fine.

Step 5 — Check after each batch:
```bash
python tools/gates/capture_status.py
```
Continue capturing until quotas are filled or no more reachable markets are available.
  </action>
  <verify>
    <automated>python tools/gates/capture_status.py</automated>
  </verify>
  <done>
capture_status.py shows increased counts for sports and/or politics and/or new_market
compared to the before baseline. No tapes remain in artifacts/simtrader/tapes/ (path
drift fix confirmed applied).
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>
Shadow capture sessions for sports, politics, and new_market buckets. Path drift fix applied.
capture_status.py has been re-run and shows updated counts.
  </what-built>
  <how-to-verify>
1. Run: python tools/gates/capture_status.py
   Confirm counts for sports, politics, new_market are higher than the pre-capture baseline.
2. Run: ls artifacts/simtrader/tapes/ 2>/dev/null
   Should be empty (or directory absent) — no tapes left in the wrong location.
3. Confirm the total qualifying count. If it is 50 or more, Gate 2 is runnable.
4. If any bucket still has a shortage, note the remaining Need values — these become the
   residual in the dev log.
  </how-to-verify>
  <resume-signal>
Type "approved" after verifying counts and confirming no path drift remains. Include the
final capture_status.py table in your reply (copy-paste the output). If any sessions failed
or produced too_short tapes, describe what happened so the dev log reflects it accurately.
  </resume-signal>
</task>

<task type="auto">
  <name>Task 3: Update CURRENT_STATE.md and write dev log</name>
  <files>docs/CURRENT_STATE.md, docs/dev_logs/2026-03-29_gold_capture_wave2.md</files>
  <action>
After the human-verify checkpoint provides the final capture_status.py output:

Step 1 — Write dev log at docs/dev_logs/2026-03-29_gold_capture_wave2.md.

Dev log must include:
- Why this wave was run (continuation from quick-039, 27/50 baseline, sports/politics/new_market reachable)
- Commands run in order (verbatim, with actual slugs used)
- Before/after qualifying counts (full table each)
- New artifacts written (list each tape directory created)
- Remaining shortage by bucket (exact Need column from post-capture capture_status.py)
- Final verdict: GATE2_READY (if total >= 50) or MORE_GOLD_NEEDED (if total < 50)
- Exact next command or work packet

Step 2 — Update docs/CURRENT_STATE.md:
- Find the current corpus count line (e.g., "27/50 qualifying tapes after Gold capture campaign")
- Update it to reflect the new post-wave-2 count
- Update the shortage breakdown: sports=X, politics=X, new_market=X, crypto=10
- Update the "next step" sentence to reflect the residual gap or, if corpus is complete, the Gate 2 run command
- Update last activity date to 2026-03-29

Do NOT touch: ROADMAP.md, benchmark_v1 files, Gate 2 logic, config/benchmark_v1.*, crypto strategy code.
  </action>
  <verify>
    <automated>python -m pytest tests/ -x -q --tb=short 2>&1 | tail -5</automated>
  </verify>
  <done>
docs/dev_logs/2026-03-29_gold_capture_wave2.md exists with all required sections.
docs/CURRENT_STATE.md shows the updated corpus count matching post-capture capture_status.py output.
Test suite passes (no regressions — only doc changes in this task).
  </done>
</task>

</tasks>

<verification>
After Task 3 completes:
1. python tools/gates/capture_status.py  -- shows final corpus state
2. cat docs/dev_logs/2026-03-29_gold_capture_wave2.md  -- verify required sections present
3. grep -n "corpus\|qualifying\|tapes" docs/CURRENT_STATE.md  -- confirm count updated
4. ls artifacts/simtrader/tapes/ 2>/dev/null  -- confirm empty (no path drift)
</verification>

<success_criteria>
- capture_status.py before/after tables exist in dev log
- New tapes in artifacts/tapes/shadow/ (none left in artifacts/simtrader/tapes/)
- docs/CURRENT_STATE.md corpus count updated to match post-capture reality
- Dev log verdict is GATE2_READY or MORE_GOLD_NEEDED with exact residual per bucket
- All existing tests pass (no regressions)
</success_criteria>

<output>
After completion, create .planning/quick/41-gold-capture-wave-2-sports-politics-new-/41-SUMMARY.md
</output>
