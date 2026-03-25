---
phase: quick-22
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docs/dev_logs/2026-03-23_phase1a_first_real_paper_soak.md
  - artifacts/crypto_pairs/paper_runs/*
autonomous: false
requirements:
  - PHASE1A-PAPER-SOAK-01
user_setup: []

must_haves:
  truths:
    - "Smoke soak (15-30 min) starts cleanly, heartbeats, finalizes artifacts without crash"
    - "24-hour paper soak completes or records a clean blocker with exact cause"
    - "crypto-pair-report runs on the final run directory and produces paper_soak_summary.json and paper_soak_summary.md"
    - "Dev log records exact commands, run path, sink availability, and rubric verdict"
    - "Verdict is unambiguously one of PROMOTE / RERUN / REJECT per the rubric spec"
  artifacts:
    - path: "artifacts/crypto_pairs/paper_runs/<date>/<run_id>/run_manifest.json"
      provides: "Final run state: stopped_reason, sink_write_result, open exposure flag"
    - path: "artifacts/crypto_pairs/paper_runs/<date>/<run_id>/run_summary.json"
      provides: "Rubric metric values: order_intents_generated, paired/partial counts, net PnL"
    - path: "artifacts/crypto_pairs/paper_runs/<date>/<run_id>/paper_soak_summary.json"
      provides: "Machine-readable rubric verdict from crypto-pair-report"
    - path: "artifacts/crypto_pairs/paper_runs/<date>/<run_id>/paper_soak_summary.md"
      provides: "Human-readable report with metric table and verdict"
    - path: "docs/dev_logs/2026-03-23_phase1a_first_real_paper_soak.md"
      provides: "Evidence bundle: commands, run path, sink state, rubric outcome"
  key_links:
    - from: "crypto-pair-run (paper mode)"
      to: "artifacts/crypto_pairs/paper_runs/<run_id>/"
      via: "DEFAULT_PAPER_ARTIFACTS_DIR"
      pattern: "stopped_reason.*completed"
    - from: "crypto-pair-report --run <run_dir>"
      to: "paper_soak_summary.json + paper_soak_summary.md"
      via: "generate_crypto_pair_paper_report()"
      pattern: "verdict"
---

<objective>
Execute the first real Phase 1A crypto pair paper soak end-to-end and produce
the evidence bundle required for the promote / rerun / reject decision.

Purpose: Phase 1A (Track 2 crypto pair bot) is code-complete and has been
validated by backtest. The next required step before any live capital decision
is a completed 24-hour paper soak against real market data, audited against the
rubric in SPEC-crypto-pair-paper-soak-rubric-v0.md. This packet is purely
execution — no code changes, no live orders.

Output: A completed run directory, a crypto-pair-report output, and a dev log
capturing the exact command trail and rubric verdict.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/CLAUDE.md
@D:/Coding Projects/Polymarket/PolyTool/docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md
@D:/Coding Projects/Polymarket/PolyTool/docs/specs/SPEC-crypto-pair-paper-soak-rubric-v0.md
@D:/Coding Projects/Polymarket/PolyTool/tools/cli/crypto_pair_run.py
@D:/Coding Projects/Polymarket/PolyTool/tools/cli/crypto_pair_report.py

<interfaces>
<!-- Key CLI flags confirmed from crypto_pair_run.py build_parser() -->

crypto-pair-run flags relevant to this soak:
  --duration-seconds INT     combined with --duration-minutes / --duration-hours
  --symbol BTC|ETH|SOL       repeatable; narrows market universe
  --market-duration 5|15     repeatable; narrows to 5m or 15m markets
  --heartbeat-seconds INT    emits operator status every N seconds
  --auto-report              on graceful exit, auto-runs crypto-pair-report
  --sink-enabled             opt-in ClickHouse sink; requires CLICKHOUSE_PASSWORD env var
  --sink-streaming           incremental per-event writes (requires --sink-enabled)
  --live                     NOT USED in this packet
  --confirm                  NOT USED in this packet

crypto-pair-report flags:
  --run PATH                 path to completed paper-run directory (required)

Default paper artifact root:
  artifacts/crypto_pairs/paper_runs/<YYYY-MM-DD>/<run_id>/

Key manifest fields to inspect post-run:
  stopped_reason             must be "completed" (not "kill_switch" etc.)
  has_open_unpaired_exposure_final  must be false
  sink_write_result.enabled  true if --sink-enabled was used
  sink_write_result.error    must be empty/null
  sink_write_result.written_rows  must be > 0 if sink was enabled

Key summary fields for rubric:
  order_intents_generated    evidence floor >= 30
  paired_exposure_count      evidence floor >= 20
  partial_exposure_count     for partial-leg incidence calculation
  settled_pair_count         evidence floor >= 20
  gross_pnl_usdc
  net_pnl_usdc               must be positive for PROMOTE

Safety reject triggers (automatic reject on any single occurrence):
  runtime_events.jsonl contains "kill_switch_tripped"
  runtime_events.jsonl contains order_intent_blocked with block_reason="daily_loss_cap_reached"
  order_intent_created while feed is in frozen/stale/disconnected window
  sink write failure when sink was enabled
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Preflight, smoke soak, and infrastructure check</name>
  <files>
    artifacts/crypto_pairs/paper_runs/* (generated by runner)
  </files>
  <action>
    **Step 1 — Preflight checks (record all output verbatim for dev log)**

    Run each of the following and capture output:

    ```bash
    rtk git status
    python -m polytool --help | grep -i crypto
    python -m polytool crypto-pair-run --help
    python -m polytool crypto-pair-report --help
    ```

    **Step 2 — Infrastructure availability check**

    Check Docker/ClickHouse/Grafana:
    ```bash
    docker compose ps
    curl "http://localhost:8123/?query=SELECT%201"
    ```

    Determine sink mode:
    - If CLICKHOUSE_PASSWORD env var is set AND ClickHouse returns "1" → plan to use --sink-enabled --sink-streaming
    - Otherwise → artifact-only mode; record the exact reason (which service was unavailable or which env var was missing)

    **Step 3 — Smoke soak (15-30 minutes)**

    Scope is locked to BTC/ETH/SOL, 5m and 15m only. Use --symbol and --market-duration flags to enforce this.

    Run the smoke soak:

    If sink is healthy:
    ```bash
    python -m polytool crypto-pair-run \
      --duration-minutes 20 \
      --symbol BTC --symbol ETH --symbol SOL \
      --market-duration 5 --market-duration 15 \
      --heartbeat-minutes 5 \
      --sink-enabled \
      --sink-streaming
    ```

    If sink is NOT healthy (artifact-only fallback):
    ```bash
    python -m polytool crypto-pair-run \
      --duration-minutes 20 \
      --symbol BTC --symbol ETH --symbol SOL \
      --market-duration 5 --market-duration 15 \
      --heartbeat-minutes 5
    ```

    **Step 4 — Smoke soak pass/fail check**

    After the smoke process exits, find the run directory:
    ```bash
    ls -t artifacts/crypto_pairs/paper_runs/
    ```

    Inspect run_manifest.json. The smoke soak PASSES only if:
    - stopped_reason == "completed" (or the expected timeout-completed value)
    - No crash/exception output during execution
    - At least one heartbeat was emitted
    - If sink was used: sink_write_result.error is null/empty

    If smoke soak FAILS: stop here. Record the exact error output. Do NOT proceed to the 24h run. Do NOT fix any code.

    If smoke soak PASSES: proceed to Task 2.
  </action>
  <verify>
    <automated>
      python -m polytool crypto-pair-run --help > /dev/null 2>&1 && echo "CLI_OK" || echo "CLI_FAIL"
    </automated>
    Smoke run directory exists under artifacts/crypto_pairs/paper_runs/ with run_manifest.json present.
  </verify>
  <done>
    CLI help loads without import errors. Smoke soak of 15-30 minutes completes: run_manifest.json exists, stopped_reason is present, no unhandled exception was printed, and at least one heartbeat appeared in console output. Infrastructure availability (sink on or off) is determined and recorded.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>
    Preflight checks and a 20-minute smoke soak against real BTC/ETH/SOL 5m/15m markets in paper mode. The run directory exists under artifacts/crypto_pairs/paper_runs/. Manifest and summary artifacts are written.
  </what-built>
  <how-to-verify>
    1. Confirm the smoke soak run directory exists and contains run_manifest.json, run_summary.json, runtime_events.jsonl.
    2. Open run_manifest.json. Verify stopped_reason is "completed" (not a crash or kill-switch value).
    3. Scan runtime_events.jsonl for "kill_switch_tripped" or "daily_loss_cap_reached" — expect none.
    4. Confirm heartbeats appeared in console output during the run.
    5. If sink was enabled: check sink_write_result.written_rows > 0 and sink_write_result.error is empty.
    6. Confirm NO live-order flags were used (no --live, no --confirm).
  </how-to-verify>
  <resume-signal>
    Type "smoke-pass" to proceed to the 24-hour paper soak.
    Type "smoke-fail: [describe blocker]" to stop and move directly to dev log writing (Task 3).
  </resume-signal>
</task>

<task type="auto">
  <name>Task 2: 24-hour paper soak with auto-report and finalization</name>
  <files>
    artifacts/crypto_pairs/paper_runs/* (generated by runner)
  </files>
  <action>
    **This task only runs if the smoke soak checkpoint returned "smoke-pass".**

    **Step 1 — Launch 24-hour paper soak**

    Use --auto-report so crypto-pair-report runs automatically on graceful exit.
    Use the same scope flags confirmed during the smoke soak.

    If sink is healthy:
    ```bash
    python -m polytool crypto-pair-run \
      --duration-hours 24 \
      --symbol BTC --symbol ETH --symbol SOL \
      --market-duration 5 --market-duration 15 \
      --heartbeat-minutes 30 \
      --auto-report \
      --sink-enabled \
      --sink-streaming
    ```

    If artifact-only (no sink):
    ```bash
    python -m polytool crypto-pair-run \
      --duration-hours 24 \
      --symbol BTC --symbol ETH --symbol SOL \
      --market-duration 5 --market-duration 15 \
      --heartbeat-minutes 30 \
      --auto-report
    ```

    Record the full run path printed by the CLI at startup.

    **Step 2 — Post-run artifact audit (after process exits)**

    Run directory: look for the most recent directory under artifacts/crypto_pairs/paper_runs/<date>/<run_id>/

    Inspect run_manifest.json:
    - stopped_reason (expect "completed")
    - has_open_unpaired_exposure_final (expect false)
    - If sink enabled: sink_write_result.enabled, sink_write_result.error, sink_write_result.written_rows

    Inspect run_summary.json and record:
    - order_intents_generated
    - paired_exposure_count
    - partial_exposure_count
    - settled_pair_count
    - gross_pnl_usdc
    - net_pnl_usdc

    Scan runtime_events.jsonl for safety violations:
    ```bash
    grep -E "kill_switch_tripped|daily_loss_cap_reached|paper_new_intents_frozen|order_intent_created|sink_write_result" \
      artifacts/crypto_pairs/paper_runs/<date>/<run_id>/runtime_events.jsonl
    ```

    **Step 3 — Run crypto-pair-report if auto-report did not fire**

    If auto-report fired and paper_soak_summary.json already exists, skip this step.

    Otherwise run manually:
    ```bash
    python -m polytool crypto-pair-report --run artifacts/crypto_pairs/paper_runs/<date>/<run_id>/
    ```

    Record the verdict line printed to stdout (PROMOTE / RERUN / REJECT).

    **Step 4 — Apply rubric manually to confirm verdict**

    Evidence floor check (all three required for PROMOTE consideration):
    - order_intents_generated >= 30
    - paired_exposure_count >= 20
    - settled_pair_count >= 20

    Metric band evaluation (from paper_soak_summary.json or run_summary.json):
    - Pair completion rate = paired_exposure_count / order_intents_generated → pass >= 0.90
    - Partial-leg incidence = partial_exposure_count / order_intents_generated → pass <= 0.10
    - net_pnl_usdc > 0 required for PROMOTE
    - Safety violations = 0 required for PROMOTE

    Final verdict: PROMOTE / RERUN / REJECT (per the spec decision logic in Section 8).

    If the run did not complete (process crashed, killed, or blocker appeared): record exact blocker and move verdict to RERUN or REJECT as appropriate.
  </action>
  <verify>
    <automated>
      ls artifacts/crypto_pairs/paper_runs/ 2>/dev/null | head -5
    </automated>
    paper_soak_summary.json and paper_soak_summary.md exist in the run directory. crypto-pair-report exited 0.
  </verify>
  <done>
    24-hour paper soak has either completed or recorded a clean blocker. paper_soak_summary.json and paper_soak_summary.md exist. Rubric verdict (PROMOTE / RERUN / REJECT) is determined with supporting metric values. All artifact paths are recorded.
  </done>
</task>

<task type="auto">
  <name>Task 3: Write dev log evidence bundle</name>
  <files>
    docs/dev_logs/2026-03-23_phase1a_first_real_paper_soak.md
  </files>
  <action>
    Write the dev log to docs/dev_logs/2026-03-23_phase1a_first_real_paper_soak.md.

    **This task runs regardless of whether the 24h soak passed, failed, or hit a blocker.**

    Structure the dev log as follows:

    ```markdown
    # Phase 1A First Real Paper Soak

    **Date**: 2026-03-25
    **Track**: Track 2 / Phase 1A — Crypto Pair Bot
    **Related spec**: docs/specs/SPEC-crypto-pair-paper-soak-rubric-v0.md
    **Runbook**: docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md

    ## Preflight

    ### Branch and git status
    [paste git status output]

    ### CLI version check
    [paste `python -m polytool crypto-pair-run --help` first line or description line]

    ### Infrastructure availability
    - Docker: [UP/DOWN or not checked]
    - ClickHouse: [reachable/unreachable + exact response]
    - Grafana: [reachable/unreachable]
    - CLICKHOUSE_PASSWORD: [set/not set]
    - Sink mode: [enabled+streaming / artifact-only]
    - Reason if artifact-only: [exact reason]

    ## Smoke Soak (20 minutes)

    ### Command used
    ```
    [exact command]
    ```

    ### Outcome
    - stopped_reason: [value]
    - Crash/exception: [none / describe]
    - Heartbeats observed: [yes/no]
    - run directory: [full path]

    ### Smoke verdict
    [PASS / FAIL — if FAIL, describe blocker and stop here]

    ## 24-Hour Paper Soak

    ### Command used
    ```
    [exact command]
    ```

    ### Run directory
    [full path to run directory]

    ### run_manifest.json key fields
    - stopped_reason: [value]
    - has_open_unpaired_exposure_final: [true/false]
    - sink_write_result.enabled: [true/false]
    - sink_write_result.error: [empty / error text]
    - sink_write_result.written_rows: [N]

    ### run_summary.json key fields
    - order_intents_generated: [N]
    - paired_exposure_count: [N]
    - partial_exposure_count: [N]
    - settled_pair_count: [N]
    - gross_pnl_usdc: [value]
    - net_pnl_usdc: [value]

    ### Safety audit (runtime_events.jsonl)
    - kill_switch_tripped: [none found / N occurrences]
    - daily_loss_cap_reached blocks: [none found / N occurrences]
    - Feed freeze windows with intent violations: [none / describe]

    ## Rubric Evaluation

    ### Evidence floor
    - order_intents_generated >= 30: [PASS/FAIL — actual: N]
    - paired_exposure_count >= 20: [PASS/FAIL — actual: N]
    - settled_pair_count >= 20: [PASS/FAIL — actual: N]
    - Floor met: [yes/no]

    ### Metric bands
    | Metric | Value | Band |
    |--------|-------|------|
    | Pair completion rate | X.XX | PASS/RERUN/REJECT |
    | Partial-leg incidence | X.XX | PASS/RERUN/REJECT |
    | net_pnl_usdc > 0 | yes/no | PASS/REJECT |
    | Safety violations | N | PASS/REJECT |

    ### crypto-pair-report verdict
    [PROMOTE TO MICRO LIVE CANDIDATE / RERUN PAPER SOAK / REJECT CURRENT CONFIG]

    ### Operator verdict confirmation
    [PROMOTE / RERUN / REJECT — with rationale if different from auto-report]

    ## Dashboard Observations (if sink enabled)
    [Record any Grafana panel observations here, or "Sink not enabled — no Grafana review"]

    ## Open Questions / Blockers
    [List any issues for the next session]

    ## Next Step
    [If PROMOTE: micro-live candidate setup]
    [If RERUN: 48h rerun command and schedule]
    [If REJECT: exact trigger and remediation path]
    ```

    After writing the dev log, run a final smoke test to confirm no import regressions were introduced:
    ```bash
    python -m polytool --help
    python -m pytest tests/ -x -q --tb=short 2>&1 | tail -5
    ```

    Note the test count in the dev log open questions section. If the pre-existing test failure appears, confirm it is the known pre-existing failure and record it as such.
  </action>
  <verify>
    <automated>
      test -f "D:/Coding Projects/Polymarket/PolyTool/docs/dev_logs/2026-03-23_phase1a_first_real_paper_soak.md" && echo "DEV_LOG_EXISTS" || echo "DEV_LOG_MISSING"
    </automated>
  </verify>
  <done>
    docs/dev_logs/2026-03-23_phase1a_first_real_paper_soak.md exists and contains: exact commands, run directory path, manifest key fields, summary metric values, rubric evaluation table, and unambiguous verdict (PROMOTE / RERUN / REJECT). No code was modified during this packet.
  </done>
</task>

</tasks>

<verification>
Final state verification:

1. Run directory exists: artifacts/crypto_pairs/paper_runs/<date>/<run_id>/
2. All core artifacts present: run_manifest.json, run_summary.json, runtime_events.jsonl
3. Report artifacts present: paper_soak_summary.json, paper_soak_summary.md
4. Dev log exists: docs/dev_logs/2026-03-23_phase1a_first_real_paper_soak.md
5. No --live flag was used at any point
6. No code files were modified
7. Verdict is one of: PROMOTE TO MICRO LIVE CANDIDATE / RERUN PAPER SOAK / REJECT CURRENT CONFIG

If the smoke soak failed and the 24h run never started, items 3 and 7 still apply — the dev log must record the exact blocker and the resulting verdict (RERUN or REJECT).
</verification>

<success_criteria>
- Smoke soak of 15-30 minutes completes cleanly or records exact blocker
- 24-hour paper soak completes (or records exact blocker preventing completion)
- crypto-pair-report runs on the final run directory and writes paper_soak_summary.json + paper_soak_summary.md
- Dev log at docs/dev_logs/2026-03-23_phase1a_first_real_paper_soak.md contains the full evidence trail
- Verdict is unambiguous: PROMOTE / RERUN / REJECT with metric values cited
- No code was changed, no live flags were used
</success_criteria>

<output>
After completion, create `.planning/quick/22-execute-the-first-real-phase-1a-crypto-p/22-SUMMARY.md`
</output>
