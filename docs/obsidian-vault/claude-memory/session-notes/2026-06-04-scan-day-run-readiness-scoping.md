---
title: "Scan Day-Run Readiness — Scoping + Decisions"
type: session_note
status: active
source_zone: claude_memory
last_updated: 2026-06-04
lifecycle: reviewed
session_date: 2026-06-04
participants: [operator, claude, codex]
tags: [session-note, wallet-discovery, ingestion, day-run, scheduler, discord, scoping]
---
# Scan Day-Run Readiness — Scoping + Decisions

## Goal
Get the user-scanner layer into a state where it can run ~a day and accumulate a large corpus of scans/dossiers on the top-PnL wallets. LLM "reports" are produced **manually, offline**: operator sorts scanned wallets by realized PnL and hands the top performers to Claude Code / Desktop / ChatGPT / Codex by hand. No automated wallet-LLM analysis in scope (no top-tier API key) — so the pipeline's job is data accumulation + a clean ranked export, not LLM generation.

## Pre-scoping audit (guess-nothing)
Codex read-only forensic audit run before scoping. Full report: repo `docs/dev_logs/2026-06-04_day-run-readiness-audit.md`. Focused test subset green (335 passed). Key findings:

1. **Scheduler exists + is docker-wired** (`discovery-scheduler` compose service, `docker-compose.yml:159-176`; blocking `while True: sleep(60)` in `tools/cli/discovery.py:814-833`). Jobs: `discovery_loop_a` */6h, `watchlist_rescan` 01:00/13:00, `queue_drain` */15min bounded to `max_items=10`, `lease_seconds=300` (`packages/research/scheduling/discovery_scheduler.py:244-263`, `config/discovery_scheduler.json`). Can run 24h unattended given Compose + ClickHouse + creds + API + upstream reachable. **Drain is a bounded cron tick, not a continuous worker.**
2. **No no-resurrect guard.** Rejected scanned wallets can be re-enqueued after freshness expiry (336h discovered-tier window) or re-surfaced by Loop A churn (Loop A ignores watchlist state); a successful drain rewrites them to `review_status=pending`.
3. **PnL-sorted export already exists** via `wallet-scan` → `leaderboard.json`/`leaderboard.md` sorted desc by `realized_net_pnl` (`tools/cli/wallet_scan.py:573-661`). NOT emitted by the scheduler — it's the batch command's artifact.
4. **No retention cap.** Supersede marks old docs/claims superseded (not deleted); prior raw runs gzip to `.tar.gz`; ClickHouse versions, snapshots, KS rows, archives all grow unbounded over sustained runs.
5. **Discord notify gap.** Manual `discovery run-worker` auto-notifies (unless `--no-notify`); the scheduled `queue_drain` does **not** notify at all. Evidence path itself is correct (uses `summarize_evidence()` via `_row_evidence()` when metrics exist).
6. **Rate limiting.** Retry/backoff for 429/server/network exists (`HttpClient`); NO steady-state throttle / per-page sleep. Fine at gentle scheduler cadence; NOT fine for aggressive bulk (e.g. 200-wallet batch).
7. **Tree dirty**, ahead of origin by 12, nothing pushed; WP-1/2/3 display work uncommitted.

## Key reframe
- The **scheduler is the trickle layer** (catches new leaderboard churn over time); the **batch `wallet-scan` is the firehose** (scans a given top-N now AND natively emits the ranked leaderboard for the manual LLM handoff). Batch-seed first is the fastest route to the actual goal.
- **Correction to a prior claim:** retention is NOT the day-1 gate. For a single run it's survivable (supersede keeps retrieval clean; one day's growth is tolerable). It's needed before *sustained* running, not before the first run.
- Real day-1 gaps are narrow: (a) scheduled path is silent on Discord, (b) volume isn't automatic from the scheduler.

## Start/stop safety
Protective already: dossier ingest is all-or-nothing per wallet (killed scan rolls back, no half-write — 6/1 fix, commit ae4947d); 5-min queue leases re-queue interrupted scans; RAG SQLite (`./kb`) + raw dossiers (`./artifacts`) are host-mounted and survive restarts. A stop mid-scan does not corrupt data — worst case is a re-scan + an orphan dossier folder.

Footguns to patch:
1. `docker compose down -v` would wipe ClickHouse → on/off must be `start`/`stop` of the scanner service; `-v` forbidden. ClickHouse volume persistence is UNVERIFIED in the audit → confirm.
2. No graceful-shutdown handler (blocking sleep loop) → `stop` hard-kills an in-flight scan (integrity holds, but orphan folder + 5-min lease wait). Add a SIGTERM handler.
3. Lease atomicity is not CAS-safe → never run a manual `run-worker` while the scheduler is on (the one real way to duplicate work). Toggle = single entry point.

## Decisions (2026-06-04)
1. **Batch-seed first, scheduler second.** First corpus from `wallet-scan` over the current top-N; scheduler then runs for ongoing capture.
2. **Batch-seed size = top 200.**
3. **On/off = scanner-service toggle only.** ON: `up -d clickhouse api discovery-scheduler`; OFF: `stop discovery-scheduler` (ClickHouse + API stay up so Grafana/queries work). Wrapped as one command. `down -v` forbidden.
4. **Discord `/status` = read-only, on-demand, over the Vera gateway, author-guarded** (operator-only invokes; output public — channel is a private server with only operator + partner). Reuses the shipped Phase-B author-guard pattern (commit c66f375).
5. **Status card layout:** wallet ID and username as SEPARATE columns; plus queue depth, scanned today, pending review, failed, top-N by realized PnL, throughput, RIS docs added. Data from ClickHouse (queue, watchlist counts, `user_pnl_bucket`).
6. **LLM reports = manual/offline, out of scope.** Source artifact = `wallet-scan` `leaderboard.json`.
7. **Retention cap + no-resurrect guard = fast-follow** (after first run / before sustained running).
8. **Grafana dashboard cleanup = fast-follow** after the run produces real data to design against. Grafana-in-Discord rejected as overengineering (the `/status` card covers the "alive + producing" need in-channel).

## Sprint — packets to get ready for a scan
- **DR-0 — Start/stop safety (verify + patch).** ClickHouse volume persistence; SIGTERM graceful shutdown; interrupted-scan lease recovery test.
- **DR-1 — One-command on/off toggle.** `make scan-on` / `make scan-off` wrapping the scanner-service start/stop; forbidden-command guard; quick CLI `scan-status`.
- **DR-2 — Batch-seed top-200 corpus.** Export current top-200 leaderboard → `wallet-scan --extract-dossier`; add per-page pacing for the bulk path; output = ranked `leaderboard.json`/`md`.
- **DR-3 — Discord `/status` window.** Read-only author-guarded slash command over the gateway; the layout above.

Fast-follow (out of this sprint): DR no-resurrect guard, DR retention cap, Grafana cleanup.

## Open before production (final-thoughts discussion)
Commit + push a clean baseline (tree dirty, 12 ahead, nothing pushed). Pick suggested order: DR-2 (corpus + ranked list, the actual goal) → DR-0 → DR-1 → DR-3.

## Cross-References
- repo `docs/dev_logs/2026-06-04_day-run-readiness-audit.md` — Codex audit (source of truth)
- [[claude-memory/session-notes/2026-05-31-wallet-ingestion-sprint-completion]] — v1 completion + verification
- [[claude-memory/session-notes/2026-05-29-wallet-ingestion-audit-results]] — pre-v1 build state
- [[claude-memory/work-packets/work-packet-scan-day-run-sprint]] — this sprint's packets

## Connections
- [[claude-memory/session-notes/_index]]
- [[index|Vault Home]]


---

## UPDATE (2026-06-04) — DR-0 Codex review + fix packet; run tiers clarified

Sprint build shipped (4 packets, evidence-gated, BLOCKED items honestly marked). Codex adversarial pass on DR-0 (repo `docs/dev_logs/2026-06-04_dr-0-codex-adversarial-review.md`) found **5 BLOCKING + 8 should-fix** — all in the scheduler/lock path; the build's 451 green tests were theater on the safety paths (signal test sets an event directly; kill tests just raise; lock tests sequential). Codex cleared 5 false concerns (subparser coexistence, wait-loop timeout, double-SIGTERM, shared lock path).

**Blockers:** unbounded SIGTERM shutdown; drain tick not bounded to Docker grace (120s scan timeout); live scheduler lock auto-expires at 30m → manual worker double-drain; non-atomic check-then-write lock; fail-open lock. Worst: the 30m live-lock expiry (silent, time-delayed double-drain).

**Fix packet written:** [[claude-memory/work-packets/work-packet-dr-0-fix-shutdown-lock]] — bounded cooperative shutdown + heartbeat-based lock staleness + atomic `O_EXCL` + fail-closed + `--force` stale-only + real tests. Mandatory Codex re-review.

**Key unblock — three run tiers, not two:**
1. **5-wallet live check** — first real execution of the live path (sandbox got 403, so export→scan→dossier→RIS→leaderboard has NEVER run live). Confirms 403 is sandbox-not-geo + artifacts land.
2. **Top-200 batch** — WATCHED foreground `wallet-scan`, scheduler OFF. The actual corpus + ranked-list goal. **Independent of DR-0** (batch path doesn't touch scheduler/lock/SIGTERM). Run with ClickHouse + API up only.
3. **Unattended scheduler "day run"** — the trickle/ongoing layer. **Gated on DR-0-FIX.**

Sequence: confirm 403/geo → 5-wallet check → 200 watched batch (goal hit) → DR-0-FIX (+ Codex re-review) → unattended scheduler. "First data before perfect system" — the corpus does not wait on the DR-0 fix.


---

## UPDATE (2026-06-04, #2) — DR-0-FIX re-review; FIX-2 scoped; batch-seed greenlit

DR-0-FIX shipped with REAL tests (subprocess SIGTERM, 12-thread O_EXCL race, real heartbeat) — the theater is gone. Codex re-review (repo `docs/dev_logs/2026-06-04_dr-0-fix-codex-rereview.md`) confirmed probes A + B as **2 BLOCKING**: (A) `should_stop` only between wallets → one failing endpoint = 4×15+7 = 67s > 60s grace; (B) unsupervised heartbeat thread → live-holder reclaim on a ~180s fuse. Plus 2 should-fix (process-level lock test; clock skew — low risk, same-host shares kernel clock) + 2 nits.

**DR-0-FIX-2 scoped:** [[claude-memory/work-packets/work-packet-dr-0-fix-2-cancel-heartbeat]] — request-granularity cancel + heartbeat-from-main-loop. Mandatory Codex pass 3. Runs in a parallel session.

**Decision — corpus does NOT wait on DR-0.** DR-0 is now 1 build + 2 reviews + a 2nd fix pass deep and is NOT on the path to the goal. The top-200 corpus runs via the foreground `wallet-scan` batch (no scheduler/lock/SIGTERM). The bigger untested unknown is the live scan path itself (never run — sandbox 403). Greenlit: 5-wallet live check (ClickHouse + API up, scheduler OFF) → confirm 403 is sandbox-not-geo + artifacts land → 200 watched batch = the corpus. DR-0-FIX-2 + pass-3 re-review + live `docker stop` test gate only the later unattended scheduler phase. DR-0 will be logged as done only when it actually clears.


---

## DECISION + CLOSEOUT (2026-06-04) — scheduler machinery shelved; foreground + Ctrl+C model

**Decision (operator):** Drop the unattended-scheduler complexity. The scan is run as a **foreground command, stopped with Ctrl+C.** Ctrl+C is data-safe via the existing per-wallet all-or-nothing ingest + lease expiry (the same safeguards Codex confirmed hold on a hard SIGKILL across all DR-0 passes); SIGINT is gentler than SIGKILL (cleanup runs). Worst case on interrupt = the in-flight wallet leaves an orphan folder + re-scans, and a mid-batch interrupt yields no end-of-run leaderboard. No corruption.

**Why:** DR-0 (graceful SIGTERM + worker lock + heartbeat) went 1 build + 3 Codex passes, blockers 5→2→3, with pass 3 finding a regression the fix itself introduced (wait=False releasing the lock before the drain job finished) plus deeper layers of the same class (cancel hook not reaching CLV's HttpClient retries; heartbeat stale during one long wallet). Classic whack-a-mole on machinery that was over-engineered for the actual threat model. The only hard requirement — "a stop can't corrupt data" — is already met without any of it. The double-drain the lock guards against only occurs if two drainers run; the foreground model has one. Aligns with the project's own "first data before perfect system" + "avoid overengineering" principles.

**Status of the DR-0 lane:**
- [[claude-memory/work-packets/work-packet-dr-0-start-stop-safety]], [[claude-memory/work-packets/work-packet-dr-0-fix-shutdown-lock]], [[claude-memory/work-packets/work-packet-dr-0-fix-2-cancel-heartbeat]] — **SHELVED.** Not needed for the foreground model. If a true always-on scheduler is ever wanted, rebuild it SIMPLE (bounded grace → SIGKILL backstop; dumb PID-liveness lock + single-entry-point rule), not as the bolt-on it became.
- [[claude-memory/work-packets/work-packet-dr-1-onoff-toggle]] — reduced to "bring up ClickHouse + API + run the foreground scan."
- [[claude-memory/work-packets/work-packet-dr-2-batch-seed-top200]] — **this is the live path.** export-leaderboard + --pace + wallet-scan --extract-dossier. Foreground wallet-scan verified byte-for-byte unchanged by the DR-0 edits (cancel hook off unless `should_stop` set), so running from the current dirty tree is safe.
- [[claude-memory/work-packets/work-packet-dr-3-discord-status]] — optional, deferred (terminal output suffices for a watched run).

**Verification folded into the run:** the 5-wallet check doubles as the Ctrl+C-safety proof — interrupt mid-run, confirm the knowledge store has no half-written wallet.

**Go sequence (active):** confirm 403 is sandbox-not-geo (`export-leaderboard --top 5`) → 5-wallet scan + a deliberate Ctrl+C check → 200 watched batch → ranked `leaderboard.json` = the corpus deliverable handed to an LLM offline. Commit the DR-2 corpus tooling after; the shelved DR-0 changes are inert for the foreground path.


---

## UPDATE (2026-06-04, #3) — Leaderboard fetch returns 0; fix packet (DR-2a); Grafana held as fast-follow

**Live blocker hit:** `export-leaderboard --top 5` wrote **0 addresses**. Diagnosed by curl, guess-nothing:
- `data-api.polymarket.com/` → 200 OK → **not geo-blocked** (Canadian-machine pivot off the table).
- `…/v1/leaderboard?order_by=PNL&time_period=DAY&limit=50&offset=0` → 200, 50 rows. Base/path/params all correct. Server ignores `order_by`/`time_period`/`offset`, honors only `limit` (cap 50/page). First guess (params) **disproven**.
- Failure is therefore **downstream of the URL** — `HttpClient`, response handling, or the DR-2 export CLI. Leading unconfirmed hypothesis: **Cloudflare 403s the default `python-requests` User-Agent** (curl allowed, requests challenged) → `status != 200` → fetcher returns `[]`. If true it also breaks every wallet scan (same host, same client), so the fix unblocks the whole pipeline.
- Latent bug found: `leaderboard_fetcher.py` sorts `rank` (a **string**) lexicographically → "top 5" returns ranks 1,10,11,12,13. Fix to `int(rank)`.

**Packet written:** [[claude-memory/work-packets/work-packet-dr-2a-leaderboard-fetch-fix]] — diagnose→fix→test→log, single session, no sub-agents. Prerequisite for DR-2's batch run.

**Grafana ("dashboards don't show user information") — held, not bundled.** This is the predicted symptom of **empty tables**: fetch=0 → no scan → `user_pnl_bucket` / `leaderboard_snapshots` empty → nothing to render. Writing a blind Grafana fix now = designing against empty tables (the DR-0 over-engineering failure mode). Consistent with **Decision #8** (Grafana = fast-follow, after real data exists). Wrote a **gated diagnosis packet** instead: [[claude-memory/work-packets/work-packet-grafana-user-info-diagnosis]] — BLOCKED until a corpus scan populates ClickHouse; ordered cause-check (data present? `userName` persisted? schema drift? datasource/time range?); fix only the confirmed cause. Flagged the most likely *real* cause if data exists but names don't: the scan may persist only the `0x` address and drop `userName` — which would also starve the future DR-3 status card.

**Rejected:** "complete everything in one go + spin up agents." The three stages (fetch fix → corpus scan → Grafana) are a **dependency chain**, not parallel work. Agents would diagnose empty tables and fix non-bugs.

**Sequence (active):** DR-2a fetch fix → `export-leaderboard --top 5` returns addresses → 5-wallet `wallet-scan --extract-dossier --pace` + deliberate Ctrl+C check → top-200 watched batch (the corpus) → THEN unblock the Grafana diagnosis packet against real data. Build-packaging fix (`discord_bot` egg_info) only needed if the `api` container is actually required; foreground scan likely needs ClickHouse only.


---

## UPDATE (2026-06-04, #4) — DR-2a done + verified; sibling snapshot bug found; corpus unblocked

**DR-2a complete, verified live.** Diagnosis was **case (c)**, not the User-Agent hypothesis: fetcher returns 250 rows at HTTP 200, no 403, no Cloudflare block — so `http_client.py` was correctly NOT touched (diagnosis-first earned its keep). Real causes: (1) export read snake_case `proxy_wallet` from a camelCase `proxyWallet` response → every wallet empty → 0 written; (2) string-rank lexicographic sort. Fixes: camelCase-first read with snake fallback (additive); `int(rank)` sort; regression test on the live shape. Offset pagination works (250 distinct). Tests: 21 (DR-2) + 59 (combined) green; live `--top 5` → 5 distinct, `--top 200` → 200 distinct, no silent shrink. Dev log `docs/dev_logs/2026-06-04_leaderboard-fetch-fix.md`; `CURRENT_STATE.md` corrected (stale sandbox-403 note removed). Tree left unstaged.

**Sibling bug found (by inspection, not fixed in DR-2a — correct scoping):** `to_snapshot_rows` (Loop A → ClickHouse `leaderboard_snapshots`) has the SAME camelCase mismatch → would write empty wallets / zero volume. New packet: [[claude-memory/work-packets/work-packet-loop-a-snapshot-wallet-field-fix]]. This is the **leading suspect for the Grafana "no user information" symptom**; the Grafana packet was updated to start from it and to first determine which table the panels read (`leaderboard_snapshots` vs `user_pnl_bucket`).

**Status of new packets:** DR-2a done; Loop-A-snapshot fix = ready, independent of the corpus run; Grafana diagnosis = still gated on real data, now with a named suspect.

**Corpus is UNBLOCKED.** `export-leaderboard` returns addresses. Next operator action = the foreground run (5-wallet check + Ctrl+C safety proof → top-200 batch → ranked `leaderboard.json`). The snapshot fix and Grafana do NOT block the corpus and are not on its critical path.


---

## UPDATE (2026-06-04, #5) — 5-wallet run completed but exposed 3 defects; 200 run PAUSED

Live 5-wallet `wallet-scan --extract-dossier` ran to completion. **What worked:** per-wallet dossiers written to disk (`artifacts/dossiers/users/unknown/<wallet>/…`) and RAG SQLite ingest (3/3 findings each). The disk + knowledge-store corpus path is sound.

**Three defects surfaced — scaling to 200 is paused until resolved:**

1. **ClickHouse auth failing on every wallet.** `Code: 516 … polytool_admin: Authentication failed: password is incorrect, or there is no user with such name (for url http://localhost:8123)`. ClickHouse is UP (port responds) — this is a **credential mismatch**, not connectivity. Most likely the `clickhouse_data` named volume was first-initialized with different creds than the current `.env` (ClickHouse only provisions users on a fresh data dir), or `polytool_admin` was never provisioned. If this breaks the whole CH read/write layer, it explains Grafana-empty AND defect 2.

2. **Realized PnL = 0.0 for all 5** — including rank-1 Countryside ($507k pnl on the leaderboard). `mtm`/`exposure` are non-zero (API/live path), only `realized` is 0. Realized PnL needs resolved closed trades from CH (`user_trades_resolved`); if CH auth is dead, that table reads empty → realized = 0. Compounded by `POLYGON_RPC_URL` and `POLYMARKET_SUBGRAPH_URL` both unset (resolution providers skipped). **The ranked `leaderboard.json` deliverable may be sorting on all-zeros — must verify.**

3. **Username = proxy address, slug = "unknown" for every wallet.** `export-leaderboard` wrote addresses only (dropped `userName`); the scan then defaults Username→address. No human-readable user info flows end-to-end. Same cluster as the `to_snapshot_rows` camelCase bug, plus an export→scan handoff gap. Starves the future DR-3 status card too.

**Unifying hypothesis (UNCONFIRMED):** ClickHouse auth misconfig is the dominant root cause — one broken layer producing both the Grafana-empty symptom and realized-PnL=0. camelCase/username are real but secondary.

**Decision:** do NOT run the 200 batch until CH auth + PnL=0 are understood. Next diagnostics: (a) confirm CH scope — does `polytool_admin` exist, do `user_trades`/`user_pnl_bucket`/`leaderboard_snapshots` have rows; (b) inspect `leaderboard.json` to see if `realized_net_pnl` is differentiated or degenerate. Note: Ctrl+C safety proof was NOT exercised this run (all 5 completed) — still outstanding.


---

## UPDATE (2026-06-04, #6) — Loop-A snapshot fix done; username-convention packet (incl. CH-auth diagnosis gate)

**Loop-A `to_snapshot_rows` fix DONE + verified** (CC): mapped every camelCase field (`proxyWallet→proxy_wallet`, `userName→username`, `vol→volume`, `pnl` coerced, `rank` int-coerced), additive, 2 regression tests, 89 targeted tests pass, live one-shot = 5/5 rows with real wallet + username + non-zero vol/pnl. A full-suite segfault was correctly triaged as a pre-existing torch crash in `tests/test_ris_fetchers.py` (RIS PDF extraction), unrelated to the pure-transform change.

**That fixes the discovery path only.** The 5-wallet run used the **wallet-scan path**, which reads addresses-only from `top5.txt`, never gets `userName`, and defaults `Username`→address (`slug=unknown`). New packet: [[claude-memory/work-packets/work-packet-username-display-convention]].

**Operator display rule captured:** store both username + wallet ID; **display prefers username, falls back to wallet ID.** Nuance locked into the packet: wallet_id stays the canonical key/slug/join; username is display-only (usernames are mutable, non-unique, and often auto-generated address-like names).

**CH-auth + PnL=0 still the real run gate.** The username packet's STEP 0 makes CC run the A/B diagnostics (CH users/table rows; leaderboard.json quality; attribute PnL=0 to CH-auth vs unset resolution providers) and REPORT — the auth fix itself is operator-only (secrets/volume). DoD explicitly states code-done ≠ run-ready until the operator resolves CH auth.

**Note:** the operator referenced a `/status` screenshot but no image came through — DR-3 stays deferred; match the card to the screenshot when it's built. Ctrl+C safety proof still outstanding.


---

## UPDATE (2026-06-04, #7) — CORRECTION to #5: blocker is host env-propagation, not a credential/volume mismatch; username convention done

**Correcting UPDATE #5 (it was over-called).** CC's STEP 0 diagnosis (dev log `docs/dev_logs/2026-06-04_username-display-convention.md`) with direct evidence:
- `polytool_admin` **exists and authenticates** with the `.env` password — NOT a stale-volume mismatch. The provisioned password already matches `.env`.
- **Real root cause:** the **host shell never loaded `.env`**, so the host CLI process has no `CLICKHOUSE_PASSWORD` (nor `POLYGON_RPC_URL`/`POLYMARKET_SUBGRAPH_URL`) → it falls back to a forbidden hardcoded `"polytool_admin"` default → Code 516 on the CLV-cache path. Inside the `discovery-scheduler` container (compose injects `.env`) it works.
- **Data IS landing:** user_trades=1654, user_pnl_bucket=740, users=5, user_dossier_exports=5, market_resolutions=211; resolved view readable (129).
- **`leaderboard.json` is NOT degenerate:** `realized_net_pnl` fully differentiated, `unknown_resolution_pct=0`. The console `PnL latest bucket: realized=0.0` line was the host CLV-failed / latest-bucket display — not the ranked deliverable.
- **PnL=0 attribution:** env-propagation, NOT resolution providers (those are set in `.env`).
- The misdiagnosis was masked by the **silent password fallback** — the code should fail-fast, not fall back to a wrong default (CLAUDE.md rule). Follow-up below.

**Operator fix (trivial, operator-only — not executed):** load `.env` into the host shell (fixes CH password AND the resolution-provider warnings in one step), or run the scan in-container, or pass `--clickhouse-password`. No `down -v`, no password change, no volume reset.

**Code follow-up (recommended, NOT yet written):** remove the hardcoded `"polytool_admin"` password fallback in scan.py/export_dossier.py/export_clickhouse.py/examine.py; fail fast with a clear error if `CLICKHOUSE_PASSWORD` is unset. This silent fallback directly caused the #5 misdiagnosis.

**Username convention DONE** ([[claude-memory/work-packets/work-packet-username-display-convention]]): `display_name` + `is_autogenerated_username` + `truncate_wallet` in `polytool/user_context.py`; falls back to truncated ASCII-safe wallet ID for empty/null/auto-generated (`0x…-<digits>`) names. Applied at scan summary, `leaderboard.md` (separate User + Wallet ID columns, never collapsed), wallet-scan artifacts. Handoff: `export-leaderboard` writes additive `<input>.usernames.json` sidecar; `wallet-scan` auto-loads; bare-address inputs still scan. `wallet_id` stays canonical key/slug; username display-only. 139 targeted tests pass (29 new); full suite 5526 pass / 3 pre-existing RIS Marker-torch fails / 1 skipped torch segfault. Zero regressions.

**Revised run-readiness:**
- The **corpus deliverable** (dossiers + RAG + ranked `leaderboard.json`) already works — it's disk/API-based, independent of the host CH path.
- **Grafana / status** need the env fix so the HOST scan writes CH. Existing CH rows predate the username fix (no usernames); a fresh run with the fixes will carry usernames.
- The Grafana diagnosis packet's gate ("tables non-empty") now PASSES — it's un-gated, best run after a fresh username-carrying scan.

**Next:** load `.env` → re-run 5-wallet → confirm the CLV-cache warning is gone, host run writes CH, usernames populate → 200 batch.


---

## UPDATE (2026-06-04, #8) — Drift check: only DR-2a blocked the corpus; /status blanks are stale data; DECISION = run 200 now

**Operator flagged drift — correct, and here's the precise version.** Of everything touched this session, exactly ONE thing was a true corpus blocker: the DR-2a export camelCase bug (`export-leaderboard` returned 0). Everything after — host-env propagation, `to_snapshot_rows`, the username convention, `/status` — is dashboard/discovery-side polish that does NOT block "a real-world leaderboard run for data." After DR-2a + a loaded `.env`, the corpus was runnable.

**`/status` blank usernames are NOT a regression.** The card (screenshot, 2:05 PM) shows the FIRST run's 5 wallets (0x6211/bee5/dc71/bddf/a380) — scanned before the username convention and with the broken host env, so usernames were never persisted on that run. `+$0 · 1 pos` = `/status` reading the **latest-bucket** realized PnL (0) via `argMax(realized_pnl, computed_at)`, NOT lifetime; `leaderboard.json` has the real differentiated PnL. The plumbing works (card rendered, read CH, found the 5) — it's pointed at stale data, and the fixes haven't been exercised by a fresh run.

**DECISION:** run the 200 now for the corpus (dossiers + RAG + ranked `leaderboard.json` — already working, disk/API-based). Defer `/status` username persistence + the latest-vs-lifetime PnL field to the **fast-follow the operator already scoped** (Decision #5/#8: Grafana/status cleanup after real data). Open question for that fast-follow: does the wallet-scan path write `username` to the CH table `/status` reads, or only to the dossier/leaderboard.md? (The convention covered display + sidecar handoff + dossier stamp; the CH-users write may be uncovered.) Not a corpus blocker — do not fix before the 200.


---

## UPDATE (2026-06-04, #9) — /status fixed; key data-model finding; PnL-divergence caveat; GO for 200

**/status accuracy fix DONE** (CC, read-only, no commit, dev log `docs/dev_logs/2026-06-04_status-accuracy-fix.md`). Top-N now reads the latest `leaderboard.json` (mounted read-only into the bot at `/app/artifacts`) for `realized_net_pnl`/`positions_total`/`identifier`; tiles/health stay on ClickHouse. Username column uses `display_name()` → real handle if present, else truncated wallet ID (never blank). Live render: PnL +885.5k/+193.1k/-477.1k/-698.8k/-1.8m (non-zero, matches leaderboard.json order), positions 5/4/50/50/50, tiles 0. 18 + 115 targeted tests pass; full non-RIS 3781 pass (RIS skipped — pre-existing native torch segfaults).

**Key data-model finding (corrects earlier assumptions):** `user_pnl_bucket` is a **30-day orderbook PnL estimate**, NOT the resolved lifetime PnL the leaderboard ranks on. My "latest-bucket vs lifetime / sum the buckets" hypothesis was WRONG — summing buckets (0/0/2446/3969/0) doesn't match leaderboard's figures. The diagnose-first prompt caught it. The resolved lifetime realized PnL lives in `leaderboard.json` (the wallet-scan artifact), which is now the Top-N source.

**⚠️ PnL-divergence caveat (corpus quality — flagged, NOT a blocker):** wallet-scan's `realized_net_pnl` diverges HARD from Polymarket's own `/v1/leaderboard` `pnl` — e.g. rank-5 wallet shows **-1.8m** in our computation vs Polymarket's **+199k**; Countryside +885k vs Polymarket +507k. Likely resolution gaps (first run had unresolved=35, 75 tokens with no resolved row) and/or a different metric (resolved realized vs realized+MTM). Implication: do NOT treat our `realized_net_pnl` as ground-truth profitability without validation. **But it does NOT block the corpus:** WHO gets scanned is selected by Polymarket's leaderboard ranking (the export), so the 200 are still Polymarket's top-200; our realized PnL is only a secondary re-rank of that set. PnL-accuracy validation = future work, not now.

**Username real-handle gap (cosmetic):** real handles exist on `/v1/leaderboard` but the scan's `/api/resolve` returns none, so the card shows truncated wallet IDs. The fix mechanism already exists — the username convention's `<input>.usernames.json` sidecar written by `export-leaderboard`. The top-5 showed IDs because the input wasn't regenerated with the current export. **For the 200: regenerate the input via current `export-leaderboard --top 200` so the sidecar is written and handles flow.** Truncated IDs are fully usable regardless (wallet_id is canonical).

**DECISION: GO for the 200.** The /status gate the operator set is met. Sequence: load `.env` → `export-leaderboard --top 200` (writes sidecar) → `wallet-scan --input top200.txt --extract-dossier --pace`. Commit the clean baseline (DR-2a + snapshot + username + status) before the long run for isolation.


---

## UPDATE (2026-06-04, #10) — /status still wrong = DEPLOY gap, not a code bug; process lesson

Screenshot 3:59 PM (after re-running top-5) still shows blank usernames + $0 PnL. **This is a deployment gap, not a code defect.** Two tells the running Vera bot is executing the OLD `status_window.py`: (1) Username = `—` (blank), but CC's fix renders `display_name()` → truncated wallet ID, NEVER blank; (2) PnL = $0, but CC's new code reads `leaderboard.json` (+885k…−1.8m). New code would show truncated IDs + non-zero PnL. It shows neither → the bot never picked up the fix.

**Process lesson:** CC's verification was unit tests + a direct assembler render ("live render"), NOT the deployed Discord bot. The fix was real but never deployed. Future /status (and any bot) verification MUST be against the live bot output, not a test harness.

**Real fix = deploy + data, not more code:** (a) rebuild/restart the bot so it loads current `status_window.py`; if the rebuild hits the deferred `discord_bot` pyproject egg_info break, that packaging fix finally comes due; (b) ensure the bot reads the LATEST `leaderboard.json`; (c) handles: regenerate the input via current `export-leaderboard` so the `<input>.usernames.json` sidecar is written and the handle flows sidecar → wallet-scan → `leaderboard.json` → bot (confirm wallet-scan actually writes the handle into `leaderboard.json`).

**Strategic note (unchanged):** /status is the fast-follow the operator deferred in Decision #5/#8 and is NOT on the critical path to the 200 run. The corpus run reads neither the bot nor `/status`. Cleanest order is **data-then-display**: run the 200 (sidecar input) → it produces a `leaderboard.json` with handles + real PnL → one bot redeploy makes `/status` correct. Fixing `/status` against top-5 data now is overwritten by the 200 anyway. Codex prompt written for the deploy/sidecar/verify-on-live-bot path.
