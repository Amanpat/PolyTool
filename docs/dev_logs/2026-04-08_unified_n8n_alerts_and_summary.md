# Unified n8n Alerts and Summary

## Files changed and why

- `workflows/n8n/ris-unified-dev.json`
  Added the minimum operator-facing alert and summary behavior to the canonical RIS pilot workflow. Health now emits compact RED or actionable YELLOW alerts, ingest failures emit compact failure alerts, and the daily summary path emits one concise RIS summary message. The workflow now uses one shared optional webhook sender instead of duplicated notification nodes.
- `infra/n8n/import_workflows.py`
  Added a small string-replacement step so the canonical workflow can receive an optional operator webhook URL at import time from `DISCORD_WEBHOOK_URL` in the shell environment or local `.env`.
- `infra/n8n/README.md`
  Documented the optional alert setup, required env/config, and the operator-facing way to trigger the daily summary path.
- `workflows/n8n/README.md`
  Updated the canonical workflow description to reflect the shared optional webhook sender and daily summary behavior.
- `docs/dev_logs/2026-04-08_unified_n8n_alerts_and_summary.md`
  Recorded implementation details, commands run, test results, operator setup, trigger steps, and deferred work.

## Commands run + output

1. `python -m json.tool workflows/n8n/ris-unified-dev.json > $null`
   Result: passed.
   Output summary: no output; canonical workflow JSON remained valid.

2. `python -m py_compile infra/n8n/import_workflows.py`
   Result: passed.
   Output summary: no output; importer remained syntactically valid.

3. `docker exec polytool-ris-scheduler python -m polytool research-health --json`
   Result: passed.
   Output summary: emitted structured health JSON to stdout and a `[RIS ALERT]` line to stderr because current local health status was actionable `YELLOW`.

4. `docker exec polytool-ris-scheduler python -m polytool research-stats summary --json`
   Result: passed.
   Output summary: emitted structured RIS stats JSON including run count, document count, family counts, precheck counts, and ingest error totals.

5. `docker exec polytool-n8n sh -lc "wget -qO- --post-data='x=1' http://host.docker.internal:8765/notify"`
   Result: passed.
   Output summary: local test receiver returned `ok`, confirming the n8n container could reach the configured webhook endpoint.

6. `$env:DISCORD_WEBHOOK_URL='http://host.docker.internal:8765/notify'; python infra/n8n/import_workflows.py`
   Result: passed.
   Output:
   - `ris-unified-dev.json: B34eBaBPIvLb8SYj (updated + already-active)`
   - `ris-health-webhook.json: MJo9jcBCfxmyMwcc (updated + already-active)`

7. `docker exec polytool-n8n sh -lc 'N8N_RUNNERS_BROKER_PORT=5680 n8n execute --id B34eBaBPIvLb8SYj --rawOutput'`
   Result: passed.
   Output summary: executed the canonical workflow's first manual trigger (`Health: Manual`) and reached `Operator: Send Webhook`.

8. `Get-Content '.tmp/n8n_notify.log'`
   Result: passed.
   Output:
   - `{"content":"RIS health YELLOW | runs=43 | docs=15 | claims=0 | new=5 | cached=3 | ingest_errors=4\n- YELLOW pipeline_failed: Current pipeline issues: reddit_polymarket blocked: Reddit live ingestion is not configured for \`reddit_polymarket\`: install \`praw\` in the RIS runtime; set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT. Job target: https://www.reddit.com/r/polymarket/.\nfamilies: academic=6, github=4, manual=3"}`

9. Temporary summary-path verification:
   - Imported a temporary workflow composed only of the current `Summary:*` nodes plus the shared notification nodes.
   - Executed it with `docker exec polytool-n8n sh -lc 'N8N_RUNNERS_BROKER_PORT=5680 n8n execute --id Jl4WuIiXUuShxyvt --rawOutput'`
   Result: passed.
   Output captured in `.tmp/n8n_notify.log`:
   - `{"content":"RIS daily summary | health=YELLOW | runs=43 | docs=15 | claims=0 | new=5 | cached=3 | ingest_errors=4\nactionable: pipeline_failed=YELLOW\nfamilies: academic=6, github=4, manual=3\nprechecks: GO=0, CAUTION=1, STOP=0"}`

10. `Set-Content -Path '.tmp/n8n_notify.log' -Value ''; Invoke-RestMethod -ContentType 'application/json' -Uri 'http://localhost:5678/webhook/ris-ingest' -Method POST -Body '{"url":"not-a-valid-url","source_family":"academic"}'`
    Result: passed as a failure-path test.
    Output:
    - `{"status":"failed","url":"not-a-valid-url","source_family":"academic","error":"Unknown error","timestamp":"2026-04-08T20:15:03.125Z","content":"RIS ingest failed | family=academic | exit=n/a\nurl: not-a-valid-url\nerror: Unknown error","webhookUrl":"http://host.docker.internal:8765/notify","notifyEnabled":true}`

11. `Get-Content '.tmp/n8n_notify.log'`
    Result: passed.
    Output:
    - `{"content":"RIS ingest failed | family=academic | exit=n/a\nurl: not-a-valid-url\nerror: Unknown error"}`

## Import and test results

- Canonical workflow JSON remained valid after the alert and summary changes.
- Importer remained valid and successfully injected the optional webhook URL during workflow import.
- Re-import of the canonical workflow succeeded and preserved the active workflow state.
- Health path test passed and produced one compact operator-facing alert payload.
- Ingest failure path test passed and produced one compact operator-facing failure payload without regressing the existing `/webhook/ris-ingest` response.
- Daily summary path logic passed and produced one compact operator-facing summary payload.
- Existing health and ingest webhook endpoints remained reachable and functional.

## Exact operator setup needed for alerts

1. Set `DISCORD_WEBHOOK_URL` before importing the canonical workflow.
   - Example shell setup:
     - `$env:DISCORD_WEBHOOK_URL='https://discord.com/api/webhooks/.../...'`
   - The importer also reads the value from the local repo `.env` if present.
2. Re-run `python infra/n8n/import_workflows.py`.
   - The importer replaces the canonical workflow placeholder with the configured webhook URL during import.
3. Keep the value unset if alerts should stay off.
   - In that state the workflow still runs normally; it just routes to `Operator: Notification Skipped` instead of sending a webhook.

Notification contract:

- The workflow sends one JSON payload to the configured webhook endpoint in the form `{"content":"..."}`.
- Health alerts fire only for `RED` or actionable `YELLOW`.
- Ingest failure alerts fire when the ingest command path fails.
- The daily summary path sends one concise RIS summary message when manually triggered or when its schedule is enabled.

## Exact way to trigger the summary path

Manual trigger:

1. Import the canonical workflow.
2. Open `ris-unified-dev` in the n8n editor.
3. Use the `Summary: Manual` trigger to execute the summary branch.

Scheduled trigger:

1. Open `ris-unified-dev` in the n8n editor.
2. Enable the disabled `Summary: Schedule` node.
3. Save the workflow active.
4. The current schedule is one daily run at `08:00`.

Note:

- `n8n execute --id ...` on this multi-trigger workflow only executes the first manual trigger, so CLI execution was sufficient for the health-path test but not for the summary branch test. The summary logic itself was therefore verified via a temporary workflow containing the current `Summary:*` nodes and shared sender nodes.

## Intentionally deferred work

- No broad monitoring platform was added inside n8n.
- No additional notification channels were added beyond the single webhook-based operator path.
- No APScheduler, provider/eval, ClickHouse, or Grafana behavior was changed.
- No default-on summary schedule was introduced beyond the existing disabled summary schedule node.
- No dashboarding, escalation policies, deduplication, retries, or alert history persistence were added in this pass.
