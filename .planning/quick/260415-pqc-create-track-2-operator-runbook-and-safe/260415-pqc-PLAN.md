---
phase: quick-260415-pqc
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docs/runbooks/TRACK2_OPERATOR_RUNBOOK.md
  - docs/dev_logs/2026-04-15_track2_operator_runbook.md
autonomous: true
requirements: [track-2-runbook]
must_haves:
  truths:
    - "Operator can determine whether Track 2 markets are available right now using one command"
    - "Operator can run a complete Track 2 paper soak from the runbook without referencing any other document"
    - "Operator knows exactly when to stop a run and what constitutes a safety violation"
    - "Operator understands what Track 2 approval means and does NOT mean about Gate 2"
    - "Every command in the runbook runs without error when copy-pasted"
  artifacts:
    - path: "docs/runbooks/TRACK2_OPERATOR_RUNBOOK.md"
      provides: "Complete Track 2 operator runbook with safety checklist"
      min_lines: 150
    - path: "docs/dev_logs/2026-04-15_track2_operator_runbook.md"
      provides: "Dev log documenting runbook creation"
      min_lines: 30
  key_links:
    - from: "docs/runbooks/TRACK2_OPERATOR_RUNBOOK.md"
      to: "docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md"
      via: "cross-reference for verdict rubric"
      pattern: "CRYPTO_PAIR_PAPER_SOAK_RUNBOOK"
    - from: "docs/runbooks/TRACK2_OPERATOR_RUNBOOK.md"
      to: "docs/specs/SPEC-crypto-pair-paper-soak-rubric-v0.md"
      via: "cross-reference for promote/rerun/reject"
      pattern: "SPEC-crypto-pair-paper-soak-rubric"
---

<objective>
Create the operator-facing Track 2 (crypto pair bot) runbook and safety checklist. This is the single
doc a human needs to run the approved Track 2 lane end-to-end: preflight checks, market availability,
scan, paper soak, safety gates, stop conditions, kill switch, troubleshooting, and what Track 2 does
and does NOT imply about Gate 2 status.

Purpose: Option 3 (Track 2 focus) is approved per the Gate 2 decision packet (2026-04-15). The operator
needs a concise, copy-paste-ready runbook to execute Track 2 without hunting across 30+ feature docs
and dev logs. This doc is the single operational entrypoint.

Output: `docs/runbooks/TRACK2_OPERATOR_RUNBOOK.md` + dev log
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/CLAUDE.md
@D:/Coding Projects/Polymarket/PolyTool/docs/dev_logs/2026-04-15_gate2_decision_packet.md
@D:/Coding Projects/Polymarket/PolyTool/docs/dev_logs/2026-03-29_track2_paper_mode_readiness.md
@D:/Coding Projects/Polymarket/PolyTool/docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md
@D:/Coding Projects/Polymarket/PolyTool/docs/specs/SPEC-crypto-pair-paper-soak-rubric-v0.md

<interfaces>
<!-- Track 2 CLI surface (verified 2026-04-15 against `python -m polytool --help`) -->

crypto-pair-watch:
  - --symbol {BTC,ETH,SOL}  (filter, v0 not wired)
  - --duration {5,15}       (filter, v0 not wired)
  - --watch                 (poll mode until markets appear or timeout)
  - --poll-interval N       (default 60s)
  - --timeout N             (default 3600s)
  - --output PATH           (default artifacts/crypto_pairs/watch)

crypto-pair-scan:
  - --top N                 (default 20)
  - --symbol {BTC,ETH,SOL}
  - --duration {5,15}
  - --output PATH           (default artifacts/crypto_pairs/scan)

crypto-pair-run:
  - --duration-seconds / --duration-minutes / --duration-hours  (additive)
  - --cycle-interval-seconds N  (default from config or 0.5)
  - --symbol {BTC,ETH,SOL}
  - --market-duration {5,15}
  - --reference-feed-provider {binance,coinbase,auto}
  - --heartbeat-minutes N
  - --auto-report
  - --sink-enabled / --sink-streaming
  - --kill-switch PATH      (default artifacts/crypto_pairs/kill_switch.txt)
  - --live + --confirm CONFIRM  (live scaffold; NOT used in paper mode)
  - --verbose

crypto-pair-backtest:
  - --input OBSERVATIONS_JSONL

crypto-pair-report:
  - summarizes one completed paper run

crypto-pair-await-soak:
  - waits for eligible markets, then launches standard Coinbase paper smoke soak

Artifact paths (canonical post-restructure):
  - Paper runs: artifacts/tapes/crypto/paper_runs/<YYYY-MM-DD>/<run_id>/
  - Kill switch: artifacts/crypto_pairs/kill_switch.txt
  - Watch output: artifacts/crypto_pairs/watch/
  - Scan output: artifacts/crypto_pairs/scan/
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create Track 2 operator runbook</name>
  <files>docs/runbooks/TRACK2_OPERATOR_RUNBOOK.md</files>
  <action>
Create `docs/runbooks/TRACK2_OPERATOR_RUNBOOK.md` with the following sections. All commands must be
verified against actual CLI --help output before writing. Use both bash and PowerShell variants where
they differ.

**Section structure:**

1. **What Track 2 Is (and Is Not)**
   - Track 2 = crypto pair bot, Phase 1A, STANDALONE per CLAUDE.md
   - Approved as the active revenue path per Gate 2 decision packet (2026-04-15, Option 3)
   - Does NOT close Gate 2. Gate 2 remains FAILED (7/50=14%, threshold 70%). Gate 2 is
     deprioritized, not abandoned. No gate thresholds or benchmark manifests are changed.
   - Track 1 (market maker) and Track 3 (sports directional) continue at background priority
   - Strategy: directional momentum entries on BTC/ETH/SOL 5m up/down markets. Per-leg
     target-bid gate (ask <= 0.46), not sum-cost accumulation (quick-046 pivot)

2. **Prerequisites / Environment Checks**
   Preflight checklist with exact commands:
   - `python -m polytool --help` loads without import errors
   - Docker services: `docker compose ps` + ClickHouse health check
   - CLICKHOUSE_PASSWORD set (fail-fast; never use hardcoded fallback per CLAUDE.md rule)
   - No Polymarket private keys or CLOB credentials needed for paper mode
   - Network access to Coinbase reference feed (Binance geo-restricted per quick-022/023)

3. **Step 1: Check Market Availability**
   - Command: `python -m polytool crypto-pair-watch`
   - One-shot check vs `--watch` poll mode
   - What "eligible" means: BTC/ETH/SOL 5m/15m binary markets active on Polymarket
   - As of 2026-04-14: 12 active 5m markets confirmed (BTC=4, ETH=4, SOL=4)
   - If no markets found: wait; crypto 5m markets rotate daily. Use `--watch --timeout 7200`

4. **Step 2: Dry-Run Scan**
   - Command: `python -m polytool crypto-pair-scan`
   - Reads market universe, computes edge estimates, no orders submitted
   - Review output: look for markets with favorable ask prices (below 0.46 per-leg gate)

5. **Step 3: Paper Soak (24h)**
   - Full launch command (bash + PowerShell) with all flags explained:
     `python -m polytool crypto-pair-run --duration-hours 24 --cycle-interval-seconds 30
      --reference-feed-provider coinbase --heartbeat-minutes 30 --auto-report --sink-enabled`
   - What each flag does (one-liner per flag)
   - Where artifacts land: `artifacts/tapes/crypto/paper_runs/<YYYY-MM-DD>/<run_id>/`
   - Mid-run monitoring: tail `runtime_events.jsonl`
   - For live Grafana during soak: add `--sink-streaming`
   - Cross-reference: full verdict rubric in `docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md`

6. **Safety Checklist (operator must verify)**
   Numbered checklist, each item with pass/fail criteria:
   - [ ] `stopped_reason` is `completed` (not crash/kill_switch)
   - [ ] `has_open_unpaired_exposure_final` is false
   - [ ] Sink wrote rows successfully (`sink_write_result.written_rows > 0`)
   - [ ] No `kill_switch_tripped` events in runtime log
   - [ ] No `daily_loss_cap_reached` events in runtime log
   - [ ] No intents created during feed freeze (check `paper_new_intents_frozen` / recovery sequence)
   - [ ] Net PnL is positive
   - [ ] Evidence floor met: intents >= 30, paired >= 20, settled >= 20

7. **Stop Conditions / Kill Switch**
   - When to stop: safety violation, daily loss cap repeatedly hit, feed permanently disconnected
   - How to stop (graceful): write truthy value to `artifacts/crypto_pairs/kill_switch.txt`
     - Bash: `printf '1\n' > artifacts/crypto_pairs/kill_switch.txt`
     - PowerShell: `Set-Content -Path artifacts/crypto_pairs/kill_switch.txt -Value 1`
   - Runner checks kill file every cycle; exits with `stopped_reason=kill_switch`
   - Ctrl+C also works but `--auto-report` may not fire

8. **What Success Looks Like**
   - Paper soak passes all safety checklist items
   - Net PnL is positive across 24h
   - Pair completion rate >= 0.90
   - Next step: promote to micro-live candidate per rubric
   - Full promote/rerun/reject rubric: `docs/specs/SPEC-crypto-pair-paper-soak-rubric-v0.md`

9. **Troubleshooting**
   - "No eligible markets found": crypto 5m markets rotate daily; use `crypto-pair-watch --watch`
   - "ClickHouse connection refused": `docker compose up -d`, verify `curl localhost:8123`
   - "CLICKHOUSE_PASSWORD not set": export from .env, never hardcode
   - "Binance feed error": use `--reference-feed-provider coinbase` (Binance geo-restricted)
   - "Zero intents generated": markets may not have asks below 0.46 target; wait for rotation
   - "Feed freeze events": check if recovery was clean; if intents created during freeze, REJECT
   - "Run stopped early": check kill switch file, daily loss cap, or feed timeout

10. **Reference Links**
    - Paper soak verdict rubric: `docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md`
    - Paper soak spec: `docs/specs/SPEC-crypto-pair-paper-soak-rubric-v0.md`
    - Strategy pivot (quick-046): `docs/dev_logs/2026-03-29_track2_paper_mode_readiness.md`
    - Gate 2 decision packet: `docs/dev_logs/2026-04-15_gate2_decision_packet.md`
    - Feature docs: `docs/features/FEATURE-crypto-pair-*.md`

**Style rules:**
- Copy-paste ready commands (no placeholders where avoidable)
- Both bash and PowerShell for platform-dependent commands
- Operator-first language (imperative, not descriptive)
- No policy changes; no Gate 2 threshold edits
- Keep under 350 lines

Before writing, verify each CLI command against actual `--help` output to ensure flag names and
defaults are correct. The commands to verify:
```
python -m polytool crypto-pair-watch --help
python -m polytool crypto-pair-scan --help
python -m polytool crypto-pair-run --help
python -m polytool crypto-pair-report --help
```
  </action>
  <verify>
    <automated>python -m polytool crypto-pair-watch --help && python -m polytool crypto-pair-scan --help && python -m polytool crypto-pair-run --help && echo "CLI commands verified"</automated>
  </verify>
  <done>
TRACK2_OPERATOR_RUNBOOK.md exists under docs/runbooks/ with all 10 sections. Every CLI command
in the doc matches actual --help output. Both bash and PowerShell variants provided where needed.
Safety checklist has concrete pass/fail criteria. Stop conditions and kill switch procedure are
documented. Gate 2 relationship is explicitly stated (deprioritized, not abandoned, no threshold
changes).
  </done>
</task>

<task type="auto">
  <name>Task 2: Create dev log and run smoke verification</name>
  <files>docs/dev_logs/2026-04-15_track2_operator_runbook.md</files>
  <action>
Run smoke verification commands referenced in the runbook to confirm they work:

1. `python -m polytool --help` -- CLI loads
2. `python -m polytool crypto-pair-watch --help` -- Track 2 watch command exists
3. `python -m polytool crypto-pair-scan --help` -- Track 2 scan command exists
4. `python -m polytool crypto-pair-run --help` -- Track 2 run command exists

Capture output snippets from each.

Then create `docs/dev_logs/2026-04-15_track2_operator_runbook.md` with:
- **Summary:** Created Track 2 operator runbook covering the full paper-soak lifecycle
- **Files changed:** `docs/runbooks/TRACK2_OPERATOR_RUNBOOK.md` (created)
- **Context:** Option 3 approved per Gate 2 decision packet. Operator needed a single
  doc to run Track 2 without hunting across 30+ feature docs.
- **Commands run + output:** Paste the smoke verification output
- **What the runbook enables:** Operator can now run the full Track 2 paper soak from
  one document: market check, scan, 24h soak, safety audit, promote/reject decision
- **What it does NOT do:** Does not change Gate 2 thresholds, does not edit shared
  truth files (CLAUDE.md, CURRENT_STATE.md, STATE.md), does not touch benchmark
  manifests or corpus tooling
- **Remaining operator gaps:** Live deployment path (EU VPS, oracle mismatch
  validation, micro-live scaffold) is not covered by this runbook -- those are future
  work items gated behind a successful paper soak promote verdict
- **Codex review:** Tier: Skip (docs-only, no execution layer code)
  </action>
  <verify>
    <automated>python -m polytool --help > /dev/null 2>&1 && test -f docs/dev_logs/2026-04-15_track2_operator_runbook.md && echo "Dev log exists and CLI loads"</automated>
  </verify>
  <done>
Dev log exists at docs/dev_logs/2026-04-15_track2_operator_runbook.md with all required sections.
Smoke verification commands ran successfully and outputs are recorded.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Docs only | No execution paths, no live-capital logic, no API calls |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-pqc-01 | Information Disclosure | Runbook commands | accept | Commands are paper-mode only; no private keys or CLOB credentials involved. CLICKHOUSE_PASSWORD sourced from .env, not hardcoded. |
| T-pqc-02 | Elevation of Privilege | --live flag | mitigate | Runbook explicitly states "Do not add --live" and explains the live scaffold is behind --live + --confirm CONFIRM. Paper mode is the default. |
</threat_model>

<verification>
1. `docs/runbooks/TRACK2_OPERATOR_RUNBOOK.md` exists and has all 10 sections
2. Every CLI command in the runbook matches actual `--help` output
3. Dev log exists with smoke verification outputs
4. No shared truth files (CLAUDE.md, CURRENT_STATE.md, STATE.md) were modified
5. No Gate 2 thresholds, benchmark manifests, or policy documents were changed
</verification>

<success_criteria>
- Operator can follow the runbook from Step 0 through Step 8 without referencing any other document
- All CLI commands in the runbook are copy-paste ready and verified against live --help
- Safety checklist has concrete, binary pass/fail criteria
- Gate 2 relationship is explicitly documented (deprioritized, not abandoned)
- Dev log records what was created and why
</success_criteria>

<output>
After completion, create `.planning/quick/260415-pqc-create-track-2-operator-runbook-and-safe/260415-pqc-SUMMARY.md`
</output>
