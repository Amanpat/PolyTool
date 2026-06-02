# 2026-06-02 Wallet Ingestion Approval Gate Verification

## Files changed and why

- `docs/dev_logs/2026-06-02_wallet-ingestion-approval-gate-verification.md` - recorded the independent CLI-only verification run and observed outputs.

No application code, tests, schemas, risk controls, or gate code were modified.

## Commands run and outputs

Initial repo checks:

```powershell
git status --short
```

Output: worktree was already dirty with existing docs/vault/research changes and many untracked dev logs; none were reverted or modified by this verification except this file.

```powershell
git log --oneline -5
```

Output:

```text
373623b fix(ris): WI-5 - move Vera approvals skill to profile dir (external_dirs not surfaced)
f998a55 fix(ris): WI-5 - approvals skill uses python3 (Vera env has no `python`)
d98f21d fix(ris): WI-5 - register Vera approvals skill via repo external_dirs (load fix)
496bdc9 feat(ris): WI-5 PolyTool emit surface - discovery review --list-pending + approval bridge
dfef21d docs(ris): live two-pass supersede validation PASS + closeout
```

```powershell
python -m polytool --help
```

Output: CLI loaded successfully and listed commands, including `discovery`.

WSL availability check:

```powershell
wsl -e bash -lc 'cd "/mnt/d/Coding Projects/Polymarket/PolyTool" && pwd && git rev-parse --show-toplevel && python3 --version'
```

Output:

```text
Windows Subsystem for Linux has no installed distributions.
Use 'wsl.exe --list --online' to list available distributions
and 'wsl.exe --install <Distro>' to install.
```

Fallback instance checks:

```powershell
docker ps --format "table {{.Names}}`t{{.Ports}}"
```

Output:

```text
NAMES                        PORTS
polytool-ris-scheduler-gpu
polytool-clickhouse          0.0.0.0:8123->8123/tcp, [::]:8123->8123/tcp, 0.0.0.0:9000->9000/tcp, [::]:9000->9000/tcp
```

```powershell
Test-Path .env
```

Output:

```text
True
```

Before each ClickHouse-backed CLI command, `.env` was loaded silently into the process environment. `CLICKHOUSE_PASSWORD` was not printed, echoed, logged, hardcoded, or typed literally into the shell.

Read-only pending list:

```powershell
python -m polytool discovery review --list-pending --json
```

Output:

```json
[{"wallet_address": "0x84cfffc3f16dcc353094de30d4a45226eccd2f63", "evidence": "scan-worker drained scan_queue and produced a dossier", "request_text": "Pending candidate: 0x84cfffc3f16dcc353094de30d4a45226eccd2f63\nEvidence: scan-worker drained scan_queue and produced a dossier\nReply to approve/deny:\napprove 0x84cfffc3f16dcc353094de30d4a45226eccd2f63\ndeny 0x84cfffc3f16dcc353094de30d4a45226eccd2f63", "lifecycle_state": "scanned"}, {"wallet_address": "0xcf609d3256f0f37f0595e5dc64012fa3a8fea6f5", "evidence": "scan-worker drained scan_queue and produced a dossier", "request_text": "Pending candidate: 0xcf609d3256f0f37f0595e5dc64012fa3a8fea6f5\nEvidence: scan-worker drained scan_queue and produced a dossier\nReply to approve/deny:\napprove 0xcf609d3256f0f37f0595e5dc64012fa3a8fea6f5\ndeny 0xcf609d3256f0f37f0595e5dc64012fa3a8fea6f5", "lifecycle_state": "scanned"}]
```

Approve one full address:

```powershell
python -m polytool discovery review --approve 0x84cfffc3f16dcc353094de30d4a45226eccd2f63 --json
```

Output:

```json
{"wallet": "0x84cfffc3f16dcc353094de30d4a45226eccd2f63", "ok": true, "from_lifecycle": "scanned", "to_lifecycle": "reviewed", "review_status": "approved", "note": "approved: review_status set to 'approved'"}
```

Deny the other full address:

```powershell
python -m polytool discovery review --deny 0xcf609d3256f0f37f0595e5dc64012fa3a8fea6f5 --json
```

Output:

```json
{"wallet": "0xcf609d3256f0f37f0595e5dc64012fa3a8fea6f5", "ok": true, "from_lifecycle": "scanned", "to_lifecycle": "scanned", "review_status": "rejected", "note": "denied: review_status set to 'rejected'; lifecycle unchanged"}
```

Negative truncated-address attempt:

```powershell
python -m polytool discovery review --approve 0xcf60... --json
```

Output:

```text
Error: a full wallet address is required (got '0xcf60...'); truncated/ambiguous identifiers are rejected.
```

Exit code: 1.

Final read-only pending list:

```powershell
python -m polytool discovery review --list-pending --json
```

Output:

```json
[]
```

## Decisions made

- WSL verification could not be used because the available Windows environment reports no installed WSL distributions.
- Per operator fallback instruction, verification continued from Windows only after confirming `.env` exists, Docker exposes `polytool-clickhouse` on `8123`, and the read-only CLI pending list returned exactly the two expected candidates.
- The before `review_status` for both candidates is `pending`, inferred from the enforced pending-list query contract (`tier='candidate' AND review_status='pending' AND locked=0 AND lifecycle_state='scanned'`) and the fact both rows appeared in `--list-pending`.

## Gate and bypass assessment

- PASS: Approve/deny operations were performed only via `python -m polytool discovery review`.
- PASS: The CLI source path for mutations is `read_watchlist_row -> plan_review -> validate_transition -> write_watchlist_rows`; no direct DB write command was used.
- PASS: The truncated address was rejected by the full-address guard before any ClickHouse mutation path.
- PASS: Final pending list was empty after the approved/rejected statuses were applied.

## Open questions or blockers

- None for this verification run.

## Codex review summary

- Not a code review. No issues filed.
