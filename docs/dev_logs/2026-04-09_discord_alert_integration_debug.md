# 2026-04-09 Discord Alert Integration Debug

## Root cause

Primary root cause:

- `infra/n8n/import_workflows.py` was not injecting `DISCORD_WEBHOOK_URL` into the canonical workflow JSON before import.
- The live unified workflow in n8n still contained the literal placeholder `__RIS_OPERATOR_WEBHOOK_URL__`.
- Because the workflow code does `notifyEnabled = webhookUrl.length > 0`, the placeholder never qualified as a valid `http://` or `https://` URL, so the alert sender branch was skipped.

Secondary runtime observation after the fix:

- The first forced alert after re-import hit a transient outbound resolution failure in n8n: `getaddrinfo EAI_AGAIN discord.com`.
- A second forced alert succeeded through the same workflow path without further code changes.

## Files changed and why

- `infra/n8n/import_workflows.py`
  - Added import-time placeholder replacement for `__RIS_OPERATOR_WEBHOOK_URL__` from `DISCORD_WEBHOOK_URL`.
  - Added env-source resolution (`environment` first, then `.env`).
  - Added JS single-quoted string escaping so the injected webhook URL is safe inside the workflow's embedded JS code.
  - Added import-time diagnostics so the CLI prints whether `DISCORD_WEBHOOK_URL` was configured and from which source.

- `docs/dev_logs/2026-04-09_discord_alert_integration_debug.md`
  - Required investigation record for this debugging session.

No canonical workflow JSON changes were required.

## Commands run and output

### 1. Verify local env presence

Command:

```powershell
$envLines = Get-Content .env
$discord = $envLines | Where-Object { $_ -match '^DISCORD_WEBHOOK_URL=' } | Select-Object -First 1
$n8n = $envLines | Where-Object { $_ -match '^N8N_API_KEY=' } | Select-Object -First 1
[pscustomobject]@{
  DISCORD_WEBHOOK_URL_present = [bool]$discord
  DISCORD_WEBHOOK_URL_prefix = if ($discord) { (($discord -split '=',2)[1]).Substring(0,[Math]::Min(8,(($discord -split '=',2)[1]).Length)) + '...' } else { $null }
  N8N_API_KEY_present = [bool]$n8n
} | ConvertTo-Json -Compress
```

Output:

```json
{"DISCORD_WEBHOOK_URL_present":true,"DISCORD_WEBHOOK_URL_prefix":"https://...","N8N_API_KEY_present":true}
```

### 2. Prove the live imported workflow was still wrong before the fix

Command:

```powershell
# Query current unified workflow from n8n REST API and inspect alert-format node code
```

Output:

```json
{"workflowId":"B34eBaBPIvLb8SYj","workflowName":"RIS — Research Intelligence System","active":true,"sendWebhookUrl":"={{ $json.webhookUrl }}","formatAlertContainsPlaceholder":true,"formatAlertSnippet":"rawWebhookUrl = '__RIS_OPERATOR_WEBHOOK_URL__'; ..."}
```

This proved the importer had not injected the Discord webhook into the live workflow.

### 3. Re-import canonical workflows after patching the importer

Command:

```powershell
python infra/n8n/import_workflows.py
```

Output:

```text
Importing canonical workflows into http://localhost:5678 ...
  DISCORD_WEBHOOK_URL: configured (.env)
  ris-unified-dev.json: B34eBaBPIvLb8SYj (updated + already-active)
  ris-health-webhook.json: MJo9jcBCfxmyMwcc (updated + already-active)
Import complete.
```

### 4. Verify the live workflow now contains the injected Discord webhook

Command:

```powershell
# Query current unified workflow from n8n REST API again
```

Output:

```json
{"workflowId":"B34eBaBPIvLb8SYj","placeholderStillPresent":0,"healthAlertWebhookPrefix":"https://discord.com/api/webhooks/1481047...","ingestFailWebhookPrefix":"https://discord.com/api/webhooks/1481047..."}
```

This proved the imported workflow was updated correctly.

### 5. Force a real alert path

Trigger used:

- POST to the active unified workflow webhook: `http://localhost:5678/webhook/ris-ingest`
- Body:

```json
{"url":"http://127.0.0.1:9/unreachable","source_family":"blog"}
```

Observed response from the workflow:

```json
{"status":"failed","url":"http://127.0.0.1:9/unreachable","source_family":"blog","error":"Unknown error","timestamp":"2026-04-09T19:42:40.504Z","content":"RIS ingest failed | family=blog | exit=n/a\nurl: http://127.0.0.1:9/unreachable\nerror: Unknown error","webhookUrl":"https://discord.com/api/webhooks/1481047...REDACTED","notifyEnabled":true}
```

Important facts:

- The alert branch ran.
- `notifyEnabled` was `true`.
- The workflow now carried a real Discord webhook URL instead of an empty/placeholder value.

## Re-import evidence

- Pre-fix live workflow: placeholder present.
- Post-fix live workflow: placeholder count `0`.
- Re-import CLI output explicitly reported `DISCORD_WEBHOOK_URL: configured (.env)`.

## n8n execution evidence

### Execution 54: first post-fix attempt

Execution summary:

```json
{"id":"54","finished":true,"mode":"webhook","status":"success","startedAt":"2026-04-09T19:42:39.671Z","stoppedAt":"2026-04-09T19:42:45.581Z","workflowId":"B34eBaBPIvLb8SYj"}
```

Raw `Operator: Send Webhook` node output:

```json
{"executionStatus":"success","data":{"main":[[{"json":{"error":{"message":"getaddrinfo EAI_AGAIN discord.com","name":"Error","code":"EAI_AGAIN"}}}]]}}
```

Interpretation:

- `continueOnFail` kept the workflow execution itself green.
- The sender node still recorded a concrete outbound failure.
- This was not an injection problem anymore; it was a transient outbound DNS resolution failure while contacting Discord.

### DNS verification after execution 54

Commands:

```powershell
docker exec polytool-n8n node -e "require('dns').lookup('discord.com',(err,address,family)=>{console.log(JSON.stringify({code:err&&err.code,message:err&&err.message,address,family}))})"
Resolve-DnsName discord.com | Select-Object -First 5 Name,Type,IPAddress | ConvertTo-Json -Compress
docker exec polytool-n8n cat /etc/resolv.conf
```

Outputs:

```json
{"code":null,"message":null,"address":"162.159.128.233","family":4}
```

```json
[{"Name":"discord.com","Type":1,"IPAddress":"162.159.128.233"},{"Name":"discord.com","Type":1,"IPAddress":"162.159.135.232"},{"Name":"discord.com","Type":1,"IPAddress":"162.159.137.232"},{"Name":"discord.com","Type":1,"IPAddress":"162.159.136.232"},{"Name":"discord.com","Type":1,"IPAddress":"162.159.138.232"}]
```

```text
# Generated by Docker Engine.
nameserver 127.0.0.11
options ndots:0
```

Interpretation:

- Host and container DNS resolution both worked when tested directly.
- The earlier `EAI_AGAIN` was therefore transient/intermittent, not a permanent configuration problem in the workflow.

### Execution 55: retry through the same alert path

Trigger body:

```json
{"url":"http://127.0.0.1:9/codex-discord-retry-1775763866","source_family":"blog"}
```

Observed webhook response summary:

```json
{"statusCode":200,"body":"{\"status\":\"failed\",\"url\":\"http://127.0.0.1:9/codex-discord-retry-1775763866\",\"source_family\":\"blog\",\"error\":\"Unknown error\",\"timestamp\":\"2026-04-09T19:44:27.443Z\",\"content\":\"RIS ingest failed | family=blog | exit=n/a\\nurl: http://127.0.0.1:9/codex-discord-retry-1775763866\\nerror: Unknown error\",\"webhookUrl\":\"https://discord.com/api/webhooks/1481047...REDACTED\",\"notifyEnabled\":true}"}
```

Execution summary:

```json
{"executionId":"55","sendExecutionStatus":"success","sendOutput":{},"notifyEnabled":true,"formattedUrl":"http://127.0.0.1:9/codex-discord-retry-1775763866"}
```

Interpretation:

- The forced alert path ran again.
- `Operator: Send Webhook` executed successfully.
- The sender node stored no `json.error`.
- The output was an empty object, which is consistent with Discord webhook success for an empty response body.

## Alert trigger used

- Active workflow: `RIS — Research Intelligence System` (`B34eBaBPIvLb8SYj`)
- Trigger path: unified ingest webhook failure path
- Endpoint: `POST /webhook/ris-ingest`
- Failure stimulus: unreachable URL on `127.0.0.1:9`
- Purpose: force `Ingest: Format Fail` -> `Operator: Notify Enabled?` -> `Operator: Send Webhook`

## Final result

Working.

What is now proven:

- `DISCORD_WEBHOOK_URL` exists in `.env`.
- The importer process now reads it and injects it at import time.
- The live imported workflow in n8n now contains the webhook value, not the placeholder.
- A real alert branch was forced.
- The sender node executed with `notifyEnabled=true`.
- One execution showed a transient Discord DNS lookup error (`EAI_AGAIN`).
- A retry succeeded through the same workflow path with no sender-node error.

## Exact operator steps required after fix

1. Keep `DISCORD_WEBHOOK_URL` set in the repo-root `.env`.
2. Run:

```powershell
python infra/n8n/import_workflows.py
```

3. To smoke-test Discord alerting on demand, run:

```powershell
Invoke-WebRequest -Uri 'http://localhost:5678/webhook/ris-ingest' `
  -Method POST `
  -ContentType 'application/json' `
  -Body '{"url":"http://127.0.0.1:9/discord-smoke-test","source_family":"blog"}'
```

4. Inspect the latest unified workflow execution in n8n. Success criteria:
   - `Ingest: Format Fail` shows `notifyEnabled=true`
   - `Operator: Send Webhook` ran
   - `Operator: Send Webhook` contains no `json.error`

5. If a future run shows `json.error.code = "EAI_AGAIN"`, treat it as outbound DNS/egress instability and retry once before changing workflow code.
