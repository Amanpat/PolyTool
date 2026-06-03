---
title: Live Notify Evidence Verification
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-06-02_live-notify-evidence-verification.md
last_synced: '2026-06-03T02:26:56Z'
lifecycle: reviewed
generator: repo-sync
---

# 2026-06-02 Live notify + evidence verification

## Scope

Independent live verification of wallet-ingestion pending notifications and
display-time evidence using real ClickHouse and the existing real scan artifacts
for:

- `0x84cfffc3f16dcc353094de30d4a45226eccd2f63`
- `0xcf609d3256f0f37f0595e5dc64012fa3a8fea6f5`

No approve or deny command was run.

## Files changed and why

- `docs/dev_logs/2026-06-02_live-notify-evidence-verification.md` - this
  verification handoff.

Runtime state changed:

- `polytool.watchlist` - inserted newer `candidate/scanned/pending` versions for
  the two target wallets so the live notify path could be re-tested.
- `artifacts/watchlists/approvals_notified.json` - created by the successful
  notify pass with both target wallets recorded for dedup.

## Commands run

Startup checks:

```powershell
git status --short
git log --oneline -5
python -m polytool --help
```

Relevant output:

```text
Worktree was already dirty before this run, including tools/cli/discovery.py,
packages/polymarket/discovery/pending_notify.py, tests/test_wallet_ingestion_notify.py,
and many docs/vault files. No pre-existing worktree changes were reverted.

373623b fix(ris): WI-5 - move Vera approvals skill to profile dir (external_dirs not surfaced)
f998a55 fix(ris): WI-5 - approvals skill uses python3 (Vera env has no `python`)
d98f21d fix(ris): WI-5 - register Vera approvals skill via repo external_dirs (load fix)
496bdc9 feat(ris): WI-5 PolyTool emit surface - discovery review --list-pending + approval bridge
dfef21d docs(ris): live two-pass supersede validation PASS + closeout

PolyTool - Polymarket analysis toolchain
Usage: polytool <command> [options]
...
```

ClickHouse startup/reachability:

```powershell
docker compose up -d clickhouse
```

Output:

```text
Container polytool-clickhouse  Starting
Container polytool-clickhouse  Started
```

```powershell
docker ps --format "table {{.Names}}`t{{.Status}}`t{{.Ports}}"
```

Output:

```text
NAMES                        STATUS                    PORTS
polytool-ris-scheduler-gpu   Up 15 minutes
polytool-clickhouse          Up 14 seconds (healthy)   0.0.0.0:8123->8123/tcp, [::]:8123->8123/tcp, 0.0.0.0:9000->9000/tcp, [::]:9000->9000/tcp
```

Required infrastructure smoke after starting ClickHouse:

```powershell
docker compose ps
```

Output:

```text
NAME                         IMAGE                                 COMMAND                  SERVICE             CREATED       STATUS                   PORTS
polytool-clickhouse          clickhouse/clickhouse-server:latest   "/entrypoint.sh"         clickhouse          2 weeks ago   Up 4 minutes (healthy)   0.0.0.0:8123->8123/tcp, [::]:8123->8123/tcp, 0.0.0.0:9000->9000/tcp, [::]:9000->9000/tcp
polytool-ris-scheduler-gpu   polytool-ris-scheduler-gpu            "python -m polytool ..." ris-scheduler-gpu   2 weeks ago   Up 19 minutes
```

ClickHouse/password/queue probe, with `.env` loaded silently and password not
printed:

```text
password_loaded=True
clickhouse_select_1={"ok":1}
pending_queue={"pending":0}
```

Reset the two rows to pending by writing fresh watchlist versions. Output:

```json
{
  "ok": true,
  "rows_written": 2,
  "after": [
    {
      "wallet_address": "0x84cfffc3f16dcc353094de30d4a45226eccd2f63",
      "lifecycle_state": "scanned",
      "review_status": "pending",
      "tier": "candidate",
      "locked": 0,
      "reason": "scan-worker drained scan_queue and produced a dossier",
      "last_scan_run_id": "e6392b72-4f17-4b3f-92b6-2012c8b3e6f9"
    },
    {
      "wallet_address": "0xcf609d3256f0f37f0595e5dc64012fa3a8fea6f5",
      "lifecycle_state": "scanned",
      "review_status": "pending",
      "tier": "candidate",
      "locked": 0,
      "reason": "scan-worker drained scan_queue and produced a dossier",
      "last_scan_run_id": "ae7ffe57-3a3d-4b09-8994-fca9fe90ec99"
    }
  ],
  "notified_file_exists": false,
  "notified_wallets": []
}
```

Literal requested command:

```powershell
python3 -m polytool discovery review --list-pending --json
```

Output:

```text
ModuleNotFoundError: No module named 'requests'
```

The Windows `python3` interpreter in this session did not have project
dependencies. Verification continued with the repo-working `python` interpreter
already used by the startup smoke check.

Evidence command:

```powershell
python -m polytool discovery review --list-pending --json
```

Output:

```json
[{"wallet_address": "0x84cfffc3f16dcc353094de30d4a45226eccd2f63", "evidence": "+$0 PnL, 0 trades, CLV 42%", "request_text": "Pending candidate: 0x84cfffc3f16dcc353094de30d4a45226eccd2f63\nEvidence: +$0 PnL, 0 trades, CLV 42%\nReply to approve/deny:\napprove 0x84cfffc3f16dcc353094de30d4a45226eccd2f63\ndeny 0x84cfffc3f16dcc353094de30d4a45226eccd2f63", "lifecycle_state": "scanned"}, {"wallet_address": "0xcf609d3256f0f37f0595e5dc64012fa3a8fea6f5", "evidence": "+$124.0k PnL, 0 trades, CLV 94%", "request_text": "Pending candidate: 0xcf609d3256f0f37f0595e5dc64012fa3a8fea6f5\nEvidence: +$124.0k PnL, 0 trades, CLV 94%\nReply to approve/deny:\napprove 0xcf609d3256f0f37f0595e5dc64012fa3a8fea6f5\ndeny 0xcf609d3256f0f37f0595e5dc64012fa3a8fea6f5", "lifecycle_state": "scanned"}]
```

Branch classifier:

```json
[
  {
    "wallet_address": "0x84cfffc3f16dcc353094de30d4a45226eccd2f63",
    "stored_reason": "scan-worker drained scan_queue and produced a dossier",
    "computed_summary": "+$0 PnL, 0 trades, CLV 42%",
    "display_evidence": "+$0 PnL, 0 trades, CLV 42%",
    "branch": "computed",
    "run_id": "e6392b72-4f17-4b3f-92b6-2012c8b3e6f9"
  },
  {
    "wallet_address": "0xcf609d3256f0f37f0595e5dc64012fa3a8fea6f5",
    "stored_reason": "scan-worker drained scan_queue and produced a dossier",
    "computed_summary": "+$124.0k PnL, 0 trades, CLV 94%",
    "display_evidence": "+$124.0k PnL, 0 trades, CLV 94%",
    "branch": "computed",
    "run_id": "ae7ffe57-3a3d-4b09-8994-fca9fe90ec99"
  }
]
```

First worker notify pass, with no `--no-notify`:

```powershell
python -m polytool discovery run-worker --max-items 1
```

Output:

```text
clickhouse_password_loaded=True
discord_webhook_loaded=True
Scan worker: loaded=2 rows, pending=0, max_items=1, dry_run=False

--- Scan Worker Result ---
  requeued    : 0
  leased      : 0
  completed   : 0
  failed      : 0
  dropped     : 0
  skipped     : 0
  flushed_ch  : True
  notified    : 2 (deduped 0, failed 0)
```

Dedup state after first pass:

```json
{
  "notified": [
    "0x84cfffc3f16dcc353094de30d4a45226eccd2f63",
    "0xcf609d3256f0f37f0595e5dc64012fa3a8fea6f5"
  ]
}
```

Second worker notify pass:

```powershell
python -m polytool discovery run-worker --max-items 1
```

Output:

```text
Scan worker: loaded=2 rows, pending=0, max_items=1, dry_run=False

--- Scan Worker Result ---
  requeued    : 0
  leased      : 0
  completed   : 0
  failed      : 0
  dropped     : 0
  skipped     : 0
  flushed_ch  : True
  notified    : 0 (deduped 2, failed 0)
```

Final pending list still shows both wallets pending; no approve/deny was run:

```json
[{"wallet_address": "0x84cfffc3f16dcc353094de30d4a45226eccd2f63", "evidence": "+$0 PnL, 0 trades, CLV 42%", "request_text": "Pending candidate: 0x84cfffc3f16dcc353094de30d4a45226eccd2f63\nEvidence: +$0 PnL, 0 trades, CLV 42%\nReply to approve/deny:\napprove 0x84cfffc3f16dcc353094de30d4a45226eccd2f63\ndeny 0x84cfffc3f16dcc353094de30d4a45226eccd2f63", "lifecycle_state": "scanned"}, {"wallet_address": "0xcf609d3256f0f37f0595e5dc64012fa3a8fea6f5", "evidence": "+$124.0k PnL, 0 trades, CLV 94%", "request_text": "Pending candidate: 0xcf609d3256f0f37f0595e5dc64012fa3a8fea6f5\nEvidence: +$124.0k PnL, 0 trades, CLV 94%\nReply to approve/deny:\napprove 0xcf609d3256f0f37f0595e5dc64012fa3a8fea6f5\ndeny 0xcf609d3256f0f37f0595e5dc64012fa3a8fea6f5", "lifecycle_state": "scanned"}]
```

## Exact notify payloads

`0x84cfffc3f16dcc353094de30d4a45226eccd2f63`:

```text
New pending candidate for review
wallet: 0x84cfffc3f16dcc353094de30d4a45226eccd2f63
evidence: +$0 PnL, 0 trades, CLV 42%
Approve or deny via CLI:
python3 -m polytool discovery review --approve 0x84cfffc3f16dcc353094de30d4a45226eccd2f63
python3 -m polytool discovery review --deny 0x84cfffc3f16dcc353094de30d4a45226eccd2f63
```

`0xcf609d3256f0f37f0595e5dc64012fa3a8fea6f5`:

```text
New pending candidate for review
wallet: 0xcf609d3256f0f37f0595e5dc64012fa3a8fea6f5
evidence: +$124.0k PnL, 0 trades, CLV 94%
Approve or deny via CLI:
python3 -m polytool discovery review --approve 0xcf609d3256f0f37f0595e5dc64012fa3a8fea6f5
python3 -m polytool discovery review --deny 0xcf609d3256f0f37f0595e5dc64012fa3a8fea6f5
```

## Decisions made

- Used the current dirty worktree as the subject under test because this was a
  live verification of the existing notify/evidence implementation. No
  pre-existing file changes were reverted.
- Started only the `clickhouse` compose service needed for real ClickHouse
  verification.
- Used `python` instead of literal `python3` after `python3` failed before
  command execution due missing `requests` in that interpreter.
- Channel-level Discord readback was not available in this Codex session. The
  live confirmation is therefore based on the worker's successful webhook post
  count (`notified 2`, `failed 0`), exact deterministic payload generation, and
  dedup state plus second-pass suppression.

## Open questions or blockers

- No code blocker found.
- Residual verification limit: without a Discord readback connector or bot token,
  this run cannot independently list the channel and count visible messages. It
  did verify live webhook acceptance and dedup behavior.

## Codex review summary

Not a code review. Live verification only.
