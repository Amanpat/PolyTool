---
phase: quick-23
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docs/dev_logs/2026-03-25_phase1a_coinbase_smoke_soak_rerun.md
  - artifacts/crypto_pairs/paper_runs/*  # new run directory produced by runner
autonomous: true
requirements:
  - TRACK2-SMOKE-COINBASE
must_haves:
  truths:
    - "Coinbase feed delivers non-zero price observations during the run (markets_seen > 0)"
    - "Runner exits with stopped_reason = completed after 20-30 minutes"
    - "crypto-pair-report produces paper_soak_summary.json and paper_soak_summary.md"
    - "A dev log records the outcome, artifact path, run_summary values, and verdict"
    - "Operator can determine whether Track 2 is unblocked for the first 24h soak"
  artifacts:
    - path: "artifacts/crypto_pairs/paper_runs/<YYYY-MM-DD>/<run_id>/run_manifest.json"
      provides: "Run metadata confirming stopped_reason and feed provider used"
    - path: "artifacts/crypto_pairs/paper_runs/<YYYY-MM-DD>/<run_id>/paper_soak_summary.json"
      provides: "Rubric verdict from crypto-pair-report"
    - path: "docs/dev_logs/2026-03-25_phase1a_coinbase_smoke_soak_rerun.md"
      provides: "Evidence record and operator verdict"
  key_links:
    - from: "CLI --reference-feed-provider coinbase"
      to: "CoinbaseFeed._ws_loop"
      via: "normalize_reference_feed_provider + build_runner_settings"
      pattern: "reference_feed_provider.*coinbase"
    - from: "run_manifest.json"
      to: "paper_soak_summary.json"
      via: "crypto-pair-report --run <dir>"
      pattern: "crypto-pair-report"
---

<objective>
Execute the Coinbase-based rerun smoke soak for Phase 1A Track 2 and produce the
evidence bundle needed to determine whether the track is unblocked.

Purpose: The previous smoke soak (quick-022) was fully blocked by Binance HTTP 451.
Coinbase fallback feed (implemented by Codex on 2026-03-25) is the intended unblock
path. This task runs the soak, generates the report, and records the verdict.

Output:
- A 20-30 minute paper smoke soak run using --reference-feed-provider coinbase
- Full artifact bundle under artifacts/crypto_pairs/paper_runs/<date>/<run_id>/
- Report artifacts from crypto-pair-report
- Dev log with outcome classification: PASS / BLOCKED / THIN BUT VALID
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md
@D:/Coding Projects/Polymarket/PolyTool/docs/specs/SPEC-crypto-pair-paper-soak-rubric-v0.md
@D:/Coding Projects/Polymarket/PolyTool/docs/features/FEATURE-crypto-pair-reference-feed-v1.md
@D:/Coding Projects/Polymarket/PolyTool/docs/dev_logs/2026-03-25_phase1a_first_real_paper_soak.md
@D:/Coding Projects/Polymarket/PolyTool/docs/dev_logs/2026-03-25_phase1a_reference_feed_fallback_v1.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Preflight, visibility check, and smoke soak execution</name>
  <files>
    artifacts/crypto_pairs/paper_runs/&lt;date&gt;/&lt;run_id&gt;/run_manifest.json
    artifacts/crypto_pairs/paper_runs/&lt;date&gt;/&lt;run_id&gt;/run_summary.json
    artifacts/crypto_pairs/paper_runs/&lt;date&gt;/&lt;run_id&gt;/runtime_events.jsonl
    artifacts/crypto_pairs/paper_runs/&lt;date&gt;/&lt;run_id&gt;/config_snapshot.json
  </files>
  <action>
Run in this exact order. Do not skip steps. Do not modify any code.

**A. Preflight (branch + CLI)**

```bash
rtk git status
python -m polytool --help
python -m polytool crypto-pair-run --help
python -m polytool crypto-pair-report --help
```

Confirm:
- `--reference-feed-provider {binance,coinbase,auto}` is present in crypto-pair-run --help
- Branch is phase-1A (per CLAUDE.md policy)
- No uncommitted changes that would alter the run

**B. Visibility stack check**

```bash
docker compose ps
curl "http://localhost:8123/?query=SELECT%201"
```

If Docker/ClickHouse is healthy AND CLICKHOUSE_PASSWORD is set in the environment:
- Use sink mode: add `--sink-enabled --sink-streaming` to the run command below

If Docker/ClickHouse is unavailable:
- Run artifact-only (omit `--sink-enabled`)
- Note this in the dev log

**C. Smoke soak execution**

Run with Coinbase feed, paper mode, 20 minutes (1200 seconds), heartbeat enabled,
NO --live flag:

With sink (if ClickHouse available):
```bash
python -m polytool crypto-pair-run \
  --reference-feed-provider coinbase \
  --duration-seconds 1200 \
  --heartbeat-interval-seconds 60 \
  --sink-enabled \
  --sink-streaming
```

Without sink (artifact-only fallback):
```bash
python -m polytool crypto-pair-run \
  --reference-feed-provider coinbase \
  --duration-seconds 1200 \
  --heartbeat-interval-seconds 60
```

STOP if:
- `--reference-feed-provider coinbase` is not accepted by the CLI (document as BLOCKED)
- The run exits immediately with a non-zero exit code before any cycles complete

**D. Verify run completion and record artifact path**

After the runner exits, locate the run directory:
```bash
ls -t artifacts/crypto_pairs/paper_runs/ | head -5
```

Inspect run_manifest.json and confirm:
- `stopped_reason` = "completed"
- `config_snapshot.reference_feed_provider` = "coinbase" (or equivalent field)
- `counts.runtime_events` > 0

Inspect run_summary.json and note:
- `markets_seen`
- `opportunities_observed`
- `order_intents_generated`
- `paired_exposure_count`
- `settled_pair_count`

Inspect config_snapshot.json and confirm:
- symbols include BTC, ETH, SOL
- duration_filters include 5 and 15 (minutes)

If stopped_reason is NOT "completed", note the actual reason and classify as BLOCKED.
  </action>
  <verify>
    <automated>
      python -m polytool crypto-pair-run --help 2>&amp;1 | grep -q "coinbase" &amp;&amp; echo "CLI_OK" || echo "CLI_MISSING_COINBASE"
    </automated>
  </verify>
  <done>
    Runner exited. Artifact directory exists with run_manifest.json, run_summary.json,
    runtime_events.jsonl, and config_snapshot.json. stopped_reason and feed provider
    are confirmed from the manifest. markets_seen value is known (may be 0 if Coinbase
    also fails, but the fact is recorded).
  </done>
</task>

<task type="auto">
  <name>Task 2: Generate report and write dev log with verdict</name>
  <files>
    artifacts/crypto_pairs/paper_runs/&lt;date&gt;/&lt;run_id&gt;/paper_soak_summary.json
    artifacts/crypto_pairs/paper_runs/&lt;date&gt;/&lt;run_id&gt;/paper_soak_summary.md
    docs/dev_logs/2026-03-25_phase1a_coinbase_smoke_soak_rerun.md
  </files>
  <action>
**A. Run crypto-pair-report**

Replace &lt;run_dir&gt; with the actual path found in Task 1:

```bash
python -m polytool crypto-pair-report --run &lt;run_dir&gt;
```

Record the exact CLI output lines:
- `verdict`
- `rubric_pass`
- `safety_count`
- `summary_json` path
- `summary_md` path

**B. Determine outcome classification**

Apply this logic:

- PASS: Coinbase feed delivered data (markets_seen &gt; 0) AND run completed AND
  no safety violations. Sufficient to justify proceeding to 24h soak.

- THIN BUT VALID: Run completed AND markets_seen &gt; 0 AND order_intents_generated
  may be 0 or low (smoke soak is only 20min — rubric floor requires 30 intents over
  24h, so low counts here are expected and acceptable). Still good enough to justify
  24h soak. This is the expected outcome for a healthy short smoke.

- BLOCKED: Coinbase feed failed (markets_seen = 0 AND runtime_events only show
  lifecycle events AND no feed_source = "coinbase" in observations). Document the
  actual error if visible in logs.

Note: Low economic activity (zero intents in 20min) is NOT a blocker for a smoke
soak. The smoke soak only needs to confirm the feed delivers price data. Economic
evidence comes from the 24h soak.

**C. Write dev log**

Write `docs/dev_logs/2026-03-25_phase1a_coinbase_smoke_soak_rerun.md` with this structure:

```markdown
# 2026-03-25 Phase 1A Coinbase Smoke Soak Rerun

**Work unit**: Phase 1A / Track 2 Coinbase smoke soak rerun
**Author**: operator + Claude Code
**Status**: CLOSED — &lt;PASS | THIN BUT VALID | BLOCKED&gt;

## Summary

&lt;1-2 sentence outcome summary&gt;

## Smoke Soak Command

&lt;exact command used&gt;

## Artifact Path

&lt;exact path&gt;

## Run Summary Values

| Field | Value |
|-------|-------|
| stopped_reason | &lt;value&gt; |
| markets_seen | &lt;value&gt; |
| opportunities_observed | &lt;value&gt; |
| order_intents_generated | &lt;value&gt; |
| paired_exposure_count | &lt;value&gt; |
| settled_pair_count | &lt;value&gt; |
| runtime_events (total) | &lt;value&gt; |
| reference_feed_provider | coinbase |
| sink_enabled | &lt;yes/no&gt; |

## Rubric Report Output

&lt;paste exact crypto-pair-report CLI output&gt;

## Outcome Classification

**Verdict: &lt;PASS | THIN BUT VALID | BLOCKED&gt;**

&lt;reason — 2-4 sentences&gt;

## Track 2 Status

&lt;One of:&gt;
- "UNBLOCKED — proceed to 24h soak using --reference-feed-provider coinbase"
- "STILL BLOCKED — see blocker details below"

&lt;If blocked: describe what failed and what the next step should be&gt;

## Next Step

&lt;Exact command for 24h soak if unblocked, or blocker resolution path if blocked&gt;
```

Fill all placeholders with actual values from the run. Do not leave any &lt;...&gt;
tokens in the written file.
  </action>
  <verify>
    <automated>
      python -c "import json, pathlib; p=sorted(pathlib.Path('artifacts/crypto_pairs/paper_runs').rglob('paper_soak_summary.json')); print('REPORT_EXISTS' if p else 'REPORT_MISSING')"
    </automated>
  </verify>
  <done>
    paper_soak_summary.json and paper_soak_summary.md exist in the run directory.
    Dev log exists at docs/dev_logs/2026-03-25_phase1a_coinbase_smoke_soak_rerun.md
    with all placeholder values filled. Verdict is one of PASS / THIN BUT VALID /
    BLOCKED. Track 2 status line explicitly states whether the 24h soak is unblocked.
  </done>
</task>

</tasks>

<verification>
After both tasks complete, verify:

1. Run manifest confirms `stopped_reason = "completed"` (or documents why not)
2. `config_snapshot.json` confirms `reference_feed_provider = "coinbase"`
3. `paper_soak_summary.json` exists (produced by crypto-pair-report)
4. Dev log exists and contains the verdict and Track 2 status line
5. No code changes were made (git diff should be clean except for new artifact files and dev log)

```bash
rtk git diff --name-only
```

Expected changed files: docs/dev_logs/2026-03-25_phase1a_coinbase_smoke_soak_rerun.md only.
Artifact files under artifacts/ are gitignored and should not appear.
</verification>

<success_criteria>
- Coinbase smoke soak executed to completion (or blocker documented cleanly)
- Artifact bundle present with run_manifest.json, run_summary.json, config_snapshot.json,
  paper_soak_summary.json, paper_soak_summary.md
- Outcome classified as PASS, THIN BUT VALID, or BLOCKED with documented evidence
- Track 2 unblock status explicitly recorded in dev log
- No code changes, no live orders, no Gate 2 files touched
</success_criteria>

<output>
After completion, create `.planning/quick/23-execute-the-coinbase-based-rerun-smoke-s/23-SUMMARY.md`
with the standard summary format recording: run artifact path, verdict, markets_seen,
runtime_events count, Track 2 status (unblocked / still blocked), and the dev log path.
</output>
