# Dev Log: RIS n8n Pilot Roadmap Closeout

**Date:** 2026-04-05
**Slug:** ris_n8n_roadmap_closeout
**Task:** quick-260404-sb4
**Branch:** feat/ws-clob-feed

---

## Summary

- Added 8 n8n workflow JSON templates covering every job in the JOB_REGISTRY, completing the RIS n8n pilot to roadmap-complete status.
- All workflows use `research-scheduler run-job <id>` as the CLI surface (not reconstructed raw `research-acquire` args), ensuring n8n and APScheduler invoke identical job logic.
- Updated `infra/n8n/import-workflows.sh` comment to reflect the full 11-workflow set.
- Updated `docs/RIS_OPERATOR_GUIDE.md` with an 8-row scheduler job matrix and mutual exclusion/runtime verification notes.
- Updated `docs/CURRENT_STATE.md` to record pilot completion without overstating phase completion.

Previous task (quick-260404-rtv) shipped: ADR 0013, n8n compose service, 3 workflow templates (health check, scheduler status, manual acquire), and the `import-workflows.sh` helper. This task closes the gap for all 8 scheduled ingestion jobs.

---

## Work Done

### Scheduler Job Coverage Matrix

| Job ID | n8n Workflow File | CLI Command | Cron Schedule | Caveats |
|--------|------------------|-------------|---------------|---------|
| academic_ingest | ris_academic_ingest.json | `research-scheduler run-job academic_ingest` | every 12h | ArXiv only |
| reddit_polymarket | ris_reddit_polymarket.json | `research-scheduler run-job reddit_polymarket` | every 6h | Requires praw + Reddit API creds |
| reddit_others | ris_reddit_others.json | `research-scheduler run-job reddit_others` | daily 03:00 | Requires praw + Reddit API creds |
| blog_ingest | ris_blog_ingest.json | `research-scheduler run-job blog_ingest` | every 4h | None |
| youtube_ingest | ris_youtube_ingest.json | `research-scheduler run-job youtube_ingest` | Mondays 04:00 | Requires yt-dlp |
| github_ingest | ris_github_ingest.json | `research-scheduler run-job github_ingest` | Wednesdays 04:00 | Optional: GITHUB_TOKEN for rate limits |
| freshness_refresh | ris_freshness_refresh.json | `research-scheduler run-job freshness_refresh` | Sundays 02:00 | Re-scans ArXiv only |
| weekly_digest | ris_weekly_digest.json | `research-scheduler run-job weekly_digest` | Sundays 08:00 | Internally calls research-report digest --window 7 |

### CLI Commands Verified as Existing

The following CLI surfaces were confirmed to exist before writing any workflow JSON:

```
python -m polytool research-scheduler run-job --help
```
Output confirms: `research-scheduler run-job` is a valid subcommand with a `job_id` positional argument.
Source: `tools/cli/research_scheduler.py` — `_cmd_run_job()` function.

```
python -m polytool research-scheduler status
```
Output lists all 8 registered jobs with their schedules and names. Confirmed job IDs:
`academic_ingest`, `reddit_polymarket`, `reddit_others`, `blog_ingest`, `youtube_ingest`,
`github_ingest`, `freshness_refresh`, `weekly_digest`.
Source: `packages/research/scheduling/scheduler.py` — `JOB_REGISTRY`.

```
python -m polytool research-report --help
```
Output confirms `digest` is a valid subcommand.
Source: `tools/cli/research_report.py` — `_cmd_digest()` function.

```
python -m polytool --help
```
CLI loads cleanly, no import errors, all expected commands listed.

### Why All Workflows Use the run-job Surface

The `research-scheduler run-job <id>` surface was chosen over reconstructing raw `research-acquire` args for these reasons:

1. **No logic duplication.** Each scheduler job encapsulates its own fetch targets, adapters, and error handling. Replicating those in n8n `Execute Command` nodes would create a maintenance divergence point.
2. **Single source of truth.** If a job's internal behavior changes (new subreddits added, different ArXiv topics), the n8n workflow remains valid without modification.
3. **Consistent exit codes.** The `run-job` surface handles internal errors and returns standardized exit codes. Raw `research-acquire` calls would require n8n to handle partial failures differently per job.
4. **Explicit interface contract.** `run-job` is a documented CLI surface (`tools/cli/research_scheduler.py`). The internal job functions are not public interfaces.

### import-workflows.sh Update

The existing `for wf in "$WORKFLOW_DIR"/*.json` glob loop already handles any new `.json` files automatically. No functional change was made to the script. Only the comment on line 8 was updated from:

```
# Scope: RIS pilot workflows only (health check, scheduler status, manual acquire).
```

to:

```
# Scope: RIS pilot workflows only -- all RIS pilot workflows (11 total).
# Includes: health check, scheduler status, manual acquire, and 8 scheduler job templates
# (academic_ingest, reddit_polymarket, reddit_others, blog_ingest, youtube_ingest,
#  github_ingest, freshness_refresh, weekly_digest).
```

### Workflow JSON Structure

Each workflow follows the structure established in `ris_health_check.json`:

- Two trigger nodes: Manual Trigger (for on-demand runs) + Schedule Trigger (cron)
- One Execute Command node calling `python -m polytool research-scheduler run-job <job_id>`
- `"active": false` — all workflows ship inactive; operator activates from n8n UI
- `"settings": {"executionOrder": "v1"}`
- `"meta": {"instanceId": "polytool-ris-pilot", "templateCredsSetupCompleted": true}`
- `"tags": ["ris", "scheduler", "<job_id>"]`
- `"notes"` field includes: scope boundary sentence, CLI command, optional dependency caveats (where applicable), mutual exclusion reminder, ADR 0013 reference

Interval-based schedules (every Nh) use the `rule.interval` array form with `field: "hours"` and `hoursInterval: N`. Specific-time schedules (daily at 03:00, weekly on Mon/Wed/Sun) use `rule.cronExpression` string form.

---

## Runtime Test Coverage

**NOT runtime-verified.** The following CLI checks were run to confirm CLI surfaces exist and the Python module loads cleanly:

```bash
python -m polytool research-scheduler status          # lists 8 jobs
python -m polytool research-scheduler run-job --help  # subcommand exists; positional job_id arg confirmed
python -m polytool research-report --help             # digest subcommand listed
python -m polytool --help                             # CLI loads, no import errors
```

End-to-end workflow execution via the n8n UI requires Docker and a running n8n container. Template JSON validity is not auto-checked by n8n outside a live instance. To run a live smoke test:

```bash
# 1. Start n8n
bash scripts/docker-start.sh --with-n8n

# 2. Import workflows
bash infra/n8n/import-workflows.sh

# 3. Open http://localhost:5678
#    Log in with N8N_BASIC_AUTH_USER / N8N_BASIC_AUTH_PASSWORD from .env

# 4. Open any imported workflow (e.g., "RIS Academic Ingest")
#    Click "Execute workflow" (manual trigger)
#    Verify Execute Command node shows exit code 0 and research-scheduler output

# 5. For cron validation:
#    Activate the workflow from the UI (toggle "Active" switch)
#    Wait for the next scheduled fire (or temporarily set a short interval for testing)
#    Check the Executions tab for output and exit code
```

---

## Open Items

1. **Cron trigger parsing:** The cron trigger times in workflow templates use scheduling rules from `JOB_REGISTRY` but are not validated against n8n's `scheduleTrigger` `typeVersion 1` cron parsing at runtime. If n8n rejects a `cronExpression`, it will show an error on workflow activation. The operator should verify each activated workflow fires as expected.

2. **Optional dependency failures:** Reddit (`reddit_polymarket`, `reddit_others`) and YouTube (`youtube_ingest`) workflows will fail gracefully if `praw` or `yt-dlp` are not installed. The job exits non-zero but does not crash n8n. n8n will log the failure in the Executions tab. This is expected behavior.

3. **No Grafana panels for n8n execution metrics:** There are no Grafana dashboard panels showing n8n workflow execution counts, success rates, or job durations. This is a deferred item — the current visibility path is the n8n Executions tab. Adding Grafana panels would require either n8n webhook notifications or a log scraping approach.

4. **github_ingest rate limits without token:** The `github_ingest` workflow will succeed but may hit GitHub anonymous API rate limits (60 req/hour). Set `GITHUB_TOKEN` in `.env` for 5000 req/hour.

---

## Codex Review

Skipped. No strategy, execution, risk, or gate files touched. All changes are docs, config (JSON workflow templates), and a shell script comment. Per CLAUDE.md Codex Review Policy: "Skip -- no review: Docs, config, tests, Grafana JSON, CLI formatting, artifacts."
