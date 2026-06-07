---
title: "Work Packet — Username Display Convention + Run-Readiness Diagnosis"
type: work_packet
status: active
source_zone: claude_memory
last_updated: 2026-06-04
lifecycle: draft
tags: [work-packet, wallet-discovery, username, display, clickhouse-auth, run-readiness, diagnose-first]
target_agent: claude-code
acceptance_criteria:
  - See Definition of Done
---
# Work Packet — Username Display Convention + Run-Readiness Diagnosis

**Status: DRAFT — ready. STEP 0 GATES the 200-wallet run. The run is NOT "ready" until the operator resolves any ClickHouse auth failure STEP 0 finds — that fix is OPERATOR-ONLY (secrets / data volume), out of agent scope.**

## Why this packet exists
The 5-wallet live run (session-note UPDATE #5) completed but exposed: (1) ClickHouse auth failing on every wallet (`polytool_admin: Authentication failed` at `localhost:8123`), (2) realized PnL = 0.0 for all five (incl. rank-1, $507k on the leaderboard), (3) `Username` = the wallet address and `slug=unknown` for every wallet. The Loop-A `to_snapshot_rows` fix already lands username on the discovery path; this packet fixes the **wallet-scan path** username + a global display convention, and first DIAGNOSES the CH-auth / PnL blocker so the run is genuinely usable.

Operator display rule: **store both username and wallet ID everywhere; for display prefer the username, fall back to the wallet ID.**

---

## STEP 0 — Run-readiness diagnosis (GATING; report, do NOT fix secrets)
Run from repo root / via docker. Capture all output into the dev log. **Do NOT** modify `.env`, run `docker compose down -v`, or set/alter any password — the auth fix is operator-only.

1. **CH auth scope.** Identify the clickhouse container (`docker compose ps`). Then:
   - `clickhouse-client -q "SELECT name FROM system.users"` — does `polytool_admin` exist?
   - `clickhouse-client -q "SELECT database, name, total_rows FROM system.tables WHERE database NOT IN ('system','INFORMATION_SCHEMA','information_schema') ORDER BY total_rows DESC LIMIT 30"` — do `user_trades`, `user_pnl_bucket`, `leaderboard_snapshots`, positions have rows?
   - Compare the creds the CLI/`.env` expects vs what the container was provisioned with (note: CH only provisions users on a fresh data dir, so a `.env` change after the `clickhouse_data` volume existed leaves stale creds).
2. **Deliverable quality.** Read the 5-wallet `leaderboard.json` (`artifacts/research/wallet_scan/2026-06-04/e2d340a3-074b-4311-bedb-2e838e3dc1d6/leaderboard.json`): is `realized_net_pnl` differentiated across the 5 or all zero?
3. **PnL=0 attribution.** Determine whether realized PnL=0 is **CH-auth-caused** (`user_trades_resolved` unreadable → 0) or **resolution-provider-caused** (`POLYGON_RPC_URL` / `POLYMARKET_SUBGRAPH_URL` unset → positions never resolve) or both.
4. **REPORT** findings in the dev log + a concise summary. Recommend the CH-auth fix (e.g., align `.env` to provisioned creds, or recreate the user via SQL, or a deliberate volume reset) but DO NOT execute it — flag for operator. **Gate:** if CH auth is dead, CH-side verification of STEP 1 is blocked; verify STEP 1 on the disk/handoff path and note CH verification as pending the operator's auth fix.

---

## STEP 1 — Username display convention (implement)
Canonical identifier = `wallet_id` (the `0x` address). `username` is a DISPLAY field. **Never** use username as a primary key, join key, or directory slug.

1. **Carry username through the export→scan handoff.** `export-leaderboard` already fetches `userName` from the API but writes addresses only. Emit username alongside the address (e.g. a CSV/JSONL or a sidecar `address→username` map) so `wallet-scan` receives it. **Keep backward compatibility:** a plain bare-address input file must still work (username simply absent → display falls back to wallet ID).
2. **Persist username on the wallet-scan path.** `wallet-scan` consumes the username when present, stores it in the dossier (and the CH user tables when reachable). Stop defaulting `Username`→address. Keep dossier directories keyed by `wallet_id` (canonical); record username as metadata — do NOT rename dirs to username.
3. **Single display helper.** Add one `display_name(username, wallet_id)` used everywhere user identity is shown. Returns the username when it's a real handle; falls back to the (truncated) wallet ID when username is empty/null OR is an auto-generated address-like name (e.g. equals the address, or matches `0x…-<digits>`). Apply it to: the scan's `Username:` log line, `leaderboard.md`, any Grafana display field that shows identity, and reserve it for the DR-3 status card.
4. **Status card stays two columns.** Per Decision #5, the DR-3 `/status` card keeps wallet ID and username as SEPARATE columns — this convention supplies the username column; do not collapse them there. (DR-3 itself is deferred; just don't regress its spec.)

## Steps
1. STEP 0 diagnosis + report (gating).
2. Export handoff: emit username; keep bare-address inputs working.
3. wallet-scan: persist username; wallet_id stays the key; slug no longer "unknown" when a username exists (but dirs stay wallet-keyed).
4. `display_name` helper + apply at all identity display points.
5. Tests: handoff carries username; bare-address input still works; `display_name` fallback covers empty/null/auto-generated/real-handle; wallet_id remains canonical. Dev log + CURRENT_STATE.

## Definition of Done
- [ ] STEP 0 findings reported (CH user/table state, leaderboard.json quality, PnL=0 attribution); CH-auth fix recommended and flagged operator-only.
- [ ] Username carried export→scan→dossier; bare-address inputs still work.
- [ ] wallet-scan persists username; wallet_id remains canonical key/slug; no "unknown" when username exists.
- [ ] `display_name(username, wallet_id)` helper exists and is applied at every identity display point; fallback handles empty/null/auto-generated.
- [ ] Tests + dev log + CURRENT_STATE written. **Explicitly state the run is gated on the operator's CH-auth fix.**

## Acceptance Gates
1. **wallet_id is canonical.** Username is never a key, join, or slug.
2. **Backward-compatible inputs.** A bare-address `--input` file must still scan.
3. **Diagnose, don't fix secrets.** STEP 0 reports; no `.env`/password/volume changes by the agent.
4. **No false readiness.** Done ≠ run-ready; the DoD must say so.
5. **Denylist untouched** (kill switch, signing, order/price paths, risk manager).

## Non-Goals
No ClickHouse auth fix (operator); no Grafana dashboard rebuild (its own packet, still gated on data); no DR-3 `/status` build (deferred — match the screenshot when built); no resolution-provider setup (operator decision once STEP 0 attributes the cause).

## Dependencies
STEP 0 is independent. STEP 1 disk/handoff path is independent; STEP 1 CH-side verification depends on the operator's auth fix.

## Sequencing note
Single Claude Code session, no sub-agents. STEP 0 first (gates the run); STEP 1 follows. The 200-wallet run waits on the operator's CH-auth resolution, not on this packet's code.

## Cross-References
- [[claude-memory/work-packets/work-packet-loop-a-snapshot-wallet-field-fix]] — discovery-path username (done); this is the wallet-scan-path twin + display convention
- [[claude-memory/work-packets/work-packet-grafana-user-info-diagnosis]] — consumes username; gated on data + CH auth
- [[claude-memory/work-packets/work-packet-dr-3-discord-status]] — wallet ID + username as separate columns (Decision #5)
- [[claude-memory/session-notes/2026-06-04-scan-day-run-readiness-scoping]] — UPDATE #5 (the three defects)

## Connections
- [[claude-memory/work-packets/_index]]
- [[index|Vault Home]]
