---
phase: quick-047
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md
  - docs/features/FEATURE-crypto-pair-runner-v0.md
  - docs/CURRENT_STATE.md
  - docs/dev_logs/2026-03-29_track2_paper_mode_readiness.md
autonomous: true
requirements: []

must_haves:
  truths:
    - "Operator can copy-paste one command and start a 24h paper soak"
    - "Runbook artifact paths match the actual code defaults (post quick-036 restructure)"
    - "Quick-046 strategy pivot (edge_buffer_per_leg gate) is documented"
    - "Required env vars for paper mode are clearly listed (only CLICKHOUSE_PASSWORD needed, and only if --sink-enabled)"
    - "Success metrics for a 24-48h soak verdict are visible in one place"
  artifacts:
    - path: "docs/dev_logs/2026-03-29_track2_paper_mode_readiness.md"
      provides: "Audit findings + launch commands + metrics"
    - path: "docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md"
      provides: "Corrected step-by-step operator launch path"
  key_links:
    - from: "docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md"
      to: "artifacts/tapes/crypto/paper_runs/"
      via: "artifact path reference"
      pattern: "artifacts/tapes/crypto/paper_runs"
---

<objective>
Audit Track 2 paper mode readiness after the quick-046 strategy pivot, correct stale
documentation, and produce a single clean operator launch path for a 24-48h paper soak.

Purpose: Track 2 (crypto pair bot) is standalone per CLAUDE.md and ready to run
independently of Gate 2. The implementation exists but the runbook contains stale
artifact paths from before the quick-036 artifacts restructure, is missing key CLI
flags (--reference-feed-provider coinbase, --heartbeat-minutes, --auto-report), and
has no documentation of the quick-046 strategy pivot (edge_buffer_per_leg gate). This
task fixes those gaps without touching benchmark policy, Track 1, or live capital.

Output: Updated runbook, dev log recording audit findings, CURRENT_STATE.md Track 2
section reflecting readiness, and one definitive 24h launch command the operator can
run immediately.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/docs/CURRENT_STATE.md
@D:/Coding Projects/Polymarket/PolyTool/docs/PLAN_OF_RECORD.md
@D:/Coding Projects/Polymarket/PolyTool/docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md
@D:/Coding Projects/Polymarket/PolyTool/tools/cli/crypto_pair_run.py
@D:/Coding Projects/Polymarket/PolyTool/packages/polymarket/crypto_pairs/paper_runner.py
@D:/Coding Projects/Polymarket/PolyTool/packages/polymarket/crypto_pairs/accumulation_engine.py
@D:/Coding Projects/Polymarket/PolyTool/packages/polymarket/crypto_pairs/config_models.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Audit paper mode and record findings in dev log</name>
  <files>docs/dev_logs/2026-03-29_track2_paper_mode_readiness.md</files>
  <action>
Read the following files before writing the dev log. Do not guess — verify each answer
against actual code:

1. `tools/cli/crypto_pair_run.py` — build_parser() for all CLI flags.
2. `packages/polymarket/crypto_pairs/paper_runner.py` — DEFAULT_PAPER_ARTIFACTS_DIR
   and DEFAULT_KILL_SWITCH_PATH constants.
3. `packages/polymarket/crypto_pairs/accumulation_engine.py` — the target_bid gate
   logic introduced in quick-046.
4. `packages/polymarket/crypto_pairs/config_models.py` — CryptoPairPaperModeConfig
   new fields (edge_buffer_per_leg, max_pair_completion_pct, min_projected_profit).
5. `docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md` — current artifact path references.

Questions to answer in the dev log:

Q1. Is "python -m polytool crypto-pair-run" the correct base command for paper mode?
    (There is no --paper flag; paper is the default when --live is absent.)
Q2. What is the exact 24h launch command the operator should use? Derive from CLI
    parser: include --duration-hours 24, --cycle-interval-seconds 30 (matches Docker
    service), --reference-feed-provider coinbase (Binance is geo-restricted per
    quick-022/023 findings), --heartbeat-minutes 30 for operator visibility,
    --auto-report for post-run report, --sink-enabled for Grafana review.
Q3. What env vars are required? Paper mode needs no Polymarket credentials. Gamma API
    is used (GammaClient default url from GAMMA_API_BASE which has a default in env).
    CLICKHOUSE_PASSWORD is required only if --sink-enabled.
Q4. Where do artifacts land? DEFAULT_PAPER_ARTIFACTS_DIR in paper_runner.py is
    "artifacts/tapes/crypto/paper_runs" (post quick-036 restructure). The run dir
    is artifacts/tapes/crypto/paper_runs/YYYY-MM-DD/{run_id}/.
Q5. Kill switch: file at DEFAULT_KILL_SWITCH_PATH = "artifacts/crypto_pairs/kill_switch.txt".
    Create the file to trip: `touch artifacts/crypto_pairs/kill_switch.txt`
Q6. What does quick-046 change for the paper soak? The old target_pair_cost_threshold
    gate (YES_ask + NO_ask <= 0.99) always fired because asks were mispriced. The new
    gate checks each leg: ask <= 0.5 - edge_buffer_per_leg (default 0.04, so ask <= 0.46).
    This means the bot now looks for markets where YES or NO is trading at or below
    0.46 -- reasonable for crypto 5m up/down markets near 50/50.
Q7. Is there a --duration flag for multi-hour soaks? Yes: --duration-hours 24 or 48.
Q8. Where does Grafana data come from? --sink-enabled writes events to
    polytool.crypto_pair_events in ClickHouse at run finalization (batch mode default)
    or incrementally (--sink-streaming mode). Grafana reads from ClickHouse.
Q9. What files land in the run directory?
    - run_manifest.json (metadata, stopped_reason, sink_write_result)
    - run_summary.json (metrics: intents, pairs, pnl)
    - runtime_events.jsonl (per-cycle event stream for mid-run liveness)
    - config_snapshot.json (settings used for the run)
Q10. Blockers as of 2026-03-29: BTC/ETH/SOL 5m markets were active 2026-03-29 (quick-045
     confirmed). No code blockers. Runbook has stale path. Quick-046 not documented.

Write a dev log at `docs/dev_logs/2026-03-29_track2_paper_mode_readiness.md` with:

## Summary section
- Brief: audit purpose, date, quick task number

## Findings section
- Q1-Q10 answered concisely

## Definitive 24h Launch Command section
Exact bash command block:
```bash
# Ensure ClickHouse is running if using --sink-enabled
docker compose up -d

# Set password if using sink
export CLICKHOUSE_PASSWORD="polytool_admin"  # or your value

# Launch 24h paper soak
python -m polytool crypto-pair-run \
  --duration-hours 24 \
  --cycle-interval-seconds 30 \
  --reference-feed-provider coinbase \
  --heartbeat-minutes 30 \
  --auto-report \
  --sink-enabled

# Trip kill switch to stop early
touch artifacts/crypto_pairs/kill_switch.txt
```

## Success Metrics (24-48h verdict) section
Reproduce the rubric from SPEC-crypto-pair-paper-soak-rubric-v0.md concisely:
- PROMOTE if all: stopped_reason=completed, intents>=30, paired_exposure>=20,
  settled_pair_count>=20, pair_completion_rate>=0.90, avg_pair_cost<=0.965,
  estimated_profit_per_pair>=0.035, maker_fill_rate>=0.95, partial_leg_incidence<=0.10,
  net_pnl_usdc>0, no safety violations
- RERUN (48h): clean run but evidence floor thin, or feed entered stale but recovered
- REJECT: any safety violation or metric in reject band

## Stale Docs Identified section
- CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md: artifact path `artifacts/crypto_pairs/paper_runs/`
  should be `artifacts/tapes/crypto/paper_runs/`
- FEATURE-crypto-pair-runner-v0.md: same stale path
- Quick-046 pivot (edge_buffer_per_leg gate): not documented anywhere in docs/

## Open Items section
- Whether --sink-streaming should be recommended for 24h+ soaks for live Grafana visibility
- Whether Grafana dashboard needs panel updates for quick-046 metric names
</action>
  <verify>
    <automated>test -f "D:/Coding Projects/Polymarket/PolyTool/docs/dev_logs/2026-03-29_track2_paper_mode_readiness.md" && echo "dev log exists"</automated>
  </verify>
  <done>Dev log exists with definitive launch command block, 10 answered questions, success
  metrics, and a stale-docs list. No guessing — all facts traced to actual code.</done>
</task>

<task type="auto">
  <name>Task 2: Fix runbook stale paths and add missing flags; update feature doc and CURRENT_STATE.md</name>
  <files>
    docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md,
    docs/features/FEATURE-crypto-pair-runner-v0.md,
    docs/CURRENT_STATE.md
  </files>
  <action>
Make targeted edits to three files. Do not rewrite them wholesale.

--- CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md ---

Corrections required (search and replace — do not rewrite surrounding content):

1. Replace the stale artifact path reference:
   OLD: `artifacts/crypto_pairs/paper_runs/<YYYY-MM-DD>/<run_id>/`
   NEW: `artifacts/tapes/crypto/paper_runs/<YYYY-MM-DD>/<run_id>/`

2. Replace the stale PowerShell directory scan path:
   OLD: `Get-ChildItem artifacts/crypto_pairs/paper_runs -Recurse -Directory`
   NEW: `Get-ChildItem artifacts/tapes/crypto/paper_runs -Recurse -Directory`

3. Replace the Step 2 launch command block with the corrected version that:
   - Adds --reference-feed-provider coinbase (Binance is geo-restricted, per quick-022/023)
   - Adds --heartbeat-minutes 30 for operator heartbeat during the soak
   - Adds --auto-report for automatic post-run report generation
   NEW command block:
   ```powershell
   python -m polytool crypto-pair-run `
     --duration-seconds 86400 `
     --cycle-interval-seconds 30 `
     --reference-feed-provider coinbase `
     --heartbeat-minutes 30 `
     --auto-report `
     --sink-enabled
   ```
   (48h variant uses --duration-seconds 172800, keep the existing 48h command below it)

4. Add a new note after "Default operator caps" block explaining the quick-046 strategy
   change:
   ```
   **Strategy gate (updated quick-046):** Each leg must have ask_price <=
   target_bid, where target_bid = 0.5 - edge_buffer_per_leg (default 0.04,
   so target_bid = 0.46). Both legs meeting the target enables accumulation
   for that pair. A single-leg meeting the target enables completion of the
   open partial leg. This replaces the prior sum-cost threshold gate.
   ```

5. Add a kill-switch section after the Step 2 block (before Step 3):
   ```
   ### Kill Switch
   To stop the run cleanly before the duration expires, create the kill switch
   file. The runner checks it every cycle and exits with stopped_reason=kill_switch.

   PowerShell:
   ```powershell
   New-Item artifacts/crypto_pairs/kill_switch.txt -Force
   ```
   Bash:
   ```bash
   touch artifacts/crypto_pairs/kill_switch.txt
   ```
   ```

--- FEATURE-crypto-pair-runner-v0.md ---

Search for the stale artifact path and replace:
   OLD: `artifacts/crypto_pairs/paper_runs/<YYYY-MM-DD>/<run_id>/`
   NEW: `artifacts/tapes/crypto/paper_runs/<YYYY-MM-DD>/<run_id>/`

If this path appears multiple times in the file, fix all occurrences.

--- docs/CURRENT_STATE.md ---

Find the "Track 2 market availability" bullet under Blockers/Concerns (or the Track 2
section nearest the top). Update it to reflect readiness status as of 2026-03-29:

OLD text (approximate):
"Track 2 market availability: BTC/ETH/SOL 5m markets were active 2026-03-29..."

REPLACE with:
"Track 2 paper soak: READY TO EXECUTE. BTC/ETH/SOL 5m markets confirmed active
2026-03-29 (quick-045). Quick-046 strategy pivot (edge_buffer_per_leg gate) is in
place as of 2026-03-29. Paper soak launch command:
`python -m polytool crypto-pair-run --duration-hours 24 --cycle-interval-seconds 30
--reference-feed-provider coinbase --heartbeat-minutes 30 --auto-report --sink-enabled`
Artifacts land in artifacts/tapes/crypto/paper_runs/. Runbook:
docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md."

Also add a row to the Quick Tasks Completed table at the bottom (if that table exists
in the file — check before adding):
| 047 | Track 2 paper mode readiness audit: stale runbook paths corrected, quick-046 pivot documented, 24h launch command produced | 2026-03-29 | (pending) | quick/47-track-2-paper-mode-readiness-audit-minim/ |
</action>
  <verify>
    <automated>python -c "
import pathlib
rb = pathlib.Path('D:/Coding Projects/Polymarket/PolyTool/docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md').read_text(encoding='utf-8')
assert 'artifacts/tapes/crypto/paper_runs' in rb, 'stale path still present in runbook'
assert 'crypto_pairs/paper_runs' not in rb, 'old path not fully removed'
assert 'coinbase' in rb, 'reference-feed-provider coinbase not added'
assert 'edge_buffer_per_leg' in rb, 'quick-046 strategy note not added'
print('runbook OK')
"
</automated>
  </verify>
  <done>
    - CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md: artifact path corrected, coinbase flag added,
      heartbeat + auto-report flags added, quick-046 strategy note added, kill switch
      section added.
    - FEATURE-crypto-pair-runner-v0.md: stale artifact path corrected.
    - docs/CURRENT_STATE.md: Track 2 section updated to READY with launch command.
  </done>
</task>

</tasks>

<verification>
After both tasks complete, run the regression suite to confirm no code was accidentally
changed:

```bash
python -m pytest tests/ -x -q --tb=short
```

Expected: 2755 passed (same as quick-046 baseline), 0 failed.

Also smoke-test the CLI help to confirm paper mode flags are intact:

```bash
python -m polytool crypto-pair-run --help
```

Expected: shows --duration-hours, --reference-feed-provider, --heartbeat-minutes,
--auto-report, --sink-enabled flags with no import errors.
</verification>

<success_criteria>
- Dev log exists at docs/dev_logs/2026-03-29_track2_paper_mode_readiness.md with all
  10 audit questions answered.
- CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md has `artifacts/tapes/crypto/paper_runs` (not the
  stale `artifacts/crypto_pairs/paper_runs`), includes --reference-feed-provider coinbase,
  --heartbeat-minutes, --auto-report flags, quick-046 strategy gate note, and a kill
  switch section.
- FEATURE-crypto-pair-runner-v0.md has the corrected artifact path.
- docs/CURRENT_STATE.md Track 2 section says READY TO EXECUTE with the definitive command.
- All 2755 tests still pass.
- Operator can open the runbook and start a 24h paper soak with zero additional research.
</success_criteria>

<output>
After completion, create `.planning/quick/47-track-2-paper-mode-readiness-audit-minim/47-SUMMARY.md`
following the summary template at:
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</output>
