---
title: "Wallet-Ingestion v1 — Sprint Completion + Migration Lesson"
type: session_note
status: active
source_zone: claude_memory
last_updated: 2026-05-31
lifecycle: reviewed
session_date: 2026-05-31
participants: [operator, claude, claude-code, codex]
tags: [session-note, wallet-discovery, ingestion, sprint-completion, lesson]
---
# Wallet-Ingestion v1 — Sprint Completion + Migration Lesson

## Outcome
5 of 6 packets shipped to main. **Pipeline runs end-to-end:** discover → enqueue → drain/scan → dossier → RIS ingest (with supersede) → two-tier watchlist → scheduler cadence. Human gate intact, no auto-promote. WI-5 (Discord two-way approval) blocked at the planned hard stop, awaiting the operator-provided bot token.

- **WI-1** — ScanWorker drains queue→scan→dossier→RIS→watchlist `scanned`; `--user` arg fix; RMT collapse; live smoke PASS. maker/taker confirmed absent from the scan API → deferred (no on-chain code added).
- **WI-2** — Chose **wallet-level supersede-on-new-run** (the robust model — avoids orphaned-section staleness); lifecycle columns; `dossier_report` decay knob; mirror lifecycle filter; success-gated retention.
- **WI-3** — Reuses RIS `JOB_REGISTRY`; single-tick drain (sidesteps the ClickHouse lease-atomicity race); config cadences; compose service.
- **WI-4** — tier/locked columns; candidate auto-population; locked immutability proven; `summarize_evidence()` as the WI-5 contract; `discovery review` over the enforced gate; live ClickHouse DDL applied + verified.
- **WI-6** — all 3 degraded MVF dims now compute on real values (`late_entry_rate` via existing `start_date_iso`); count corrected to 11.

## Lesson — init-wired migrations cannot be manually gated
The WI-2 hard stop ("stop before applying the migration") was **architecturally unenforceable**: the migration is called from `_ensure_schema`, which runs on every store init, so it auto-applied the moment WI-2 code touched the store. Operator response: "accept but harden." Resolution: `_backup_before_schema_migration()` (auto-backup before mutating a populated on-disk DB) + idempotent `table_info`-guarded ALTER. Backup at `…pre-wi2.2026-05-31.bak`.

**Durable principle:** for *additive* migrations, auto-backup + idempotent guard is the correct control (a manual gate is illusory when the migration runs at init). For any future *destructive* migration, it must be a **separate explicit command, not init-triggered**, so it can actually be gated. Scope future schema packets with this in mind.

(CC's first hardening attempt — refuse the live DB under pytest — was wrong: pytest already chdir-isolates, so it broke ~12 RIS tests without addressing the real vector (ad-hoc CLI runs). CC caught and reverted it; the "pre-existing failures" the WI-4 subagent reported were that guard, not a real regression.)

## Open items
1. **WI-5 blocked** — needs operator to create a Discord bot (gateway-intents recommended) and set `DISCORD_BOT_TOKEN` + `DISCORD_APPROVAL_CHANNEL_ID` in `.env`. Upstream deps done; WI-4 `summarize_evidence()` is the ready contract.
2. **Live supersede validation pending** — the smoke was single-pass; supersede-on-rescan has unit tests but has NOT been exercised by a real second scan of the same wallet through the live pipeline. Run a two-pass cycle before trusting v1.
3. **3 pre-existing failures** in `test_ris_phase4_source_acquisition` (academic arxiv ingest) — unrelated to this sprint; confirm the ~12 guard-induced failures are restored post-revert and only these 3 remain. Backlog the 3.
4. **Stray `api` docker service** still running from the WI-1 smoke — stop it (not needed for a gateway-intents WI-5).

## Cross-References
- [[claude-memory/session-notes/2026-05-29-wallet-ingestion-audit-results]] — verified pre-sprint state
- [[claude-memory/work-packets/work-packet-wallet-ingestion-v1-sprint]] — sprint overview (per-packet DoD ticks)
- Repo running record: `docs/dev_logs/2026-05-31_wallet-ingestion-sprint-STATUS.md`

## Connections
- [[claude-memory/session-notes/_index]]
- [[index|Vault Home]]


---

## CORRECTION (2026-05-31, post-validation) — e2e claim suspended

The two-pass live validation found the "pipeline runs end-to-end" claim above is a **false positive for realistic wallets.** For wallet `0xcf60…`, the worker reported `completed=1`, wrote a 3-finding dossier to disk, and advanced the watchlist to `scanned` — but **0 docs/claims persisted to the knowledge store.**

**Root cause — two interacting defects:**
1. **Pre-existing (not this sprint):** `PlainTextExtractor.extract` (extractors.py:163-165) treats any raw text containing `/` or `\` as a file path → `FileNotFoundError`. Dossier memo bodies contain `/` → throw. (Confirmed untouched by the sprint via git.)
2. **WI-2 amplification:** `ingest_dossier_findings` wraps a wallet's findings in one transaction with a broad `except: rollback-all` that swallows the error non-fatally → the memo's exception rolls back the *whole* wallet (incl. good Detectors/Candidates), and the worker reports success on zero persisted.

**Why it was missed:** WI-1's smoke wallet had no substantive memo (only slash-free findings); WI-2 unit tests used slash-free synthetic bodies. **Lesson (durable): validation data must be representative — degenerate/synthetic-clean inputs give false green.** This is precisely why a real-wallet two-pass run was required and a "smoke PASS" was not sufficient.

**Decision (operator, 2026-05-31):**
- **Defect 1 → Option A via an explicit `raw_text=True` bypass** in the dossier ingest's extractor call — NOT the temp-file workaround (a kludge), because the explicit flag is the first increment of the correct design. Shared extractor heuristic left untouched this sprint.
- **Option B (remove the `/`→path content-sniffing heuristic across all callers) → tracked as a separate follow-up packet**, done deliberately with a full caller audit, not rushed mid-sprint. Honors "fix root causes" without expanding this sprint into a risky cross-cutting refactor.
- **Defect 2 hardening (mandatory):** ingest/worker must never report success on zero persisted (zero/error = failure → mark queue failed, do NOT advance lifecycle to `scanned`); no silent swallow (log loud + propagate); keep all-or-nothing per wallet to preserve the supersede "one complete set" invariant, but make failures loud (best-effort-per-section rejected — it breaks the invariant).

**State:** no corruption (rollback left KS unchanged). One inconsistency to clean: `0xcf60`'s watchlist row says `scanned` while RIS holds no dossier. Fix + full two-pass re-validation pending before WI-5. The "Outcome" section above stands corrected: v1 e2e is **not** confirmed until re-validation passes on a real memo-bearing wallet.


---

## CLOSURE (2026-06-01) — e2e CONFIRMED on real data

The validation break is fixed (commit ae4947d) and the two-pass supersede re-validation **PASSES all four invariants** on the previously-broken real wallet `0xcf60…`:
- (a) one active set: 3 active (run ae7ffe57) / 3 superseded (run 6353dc1c)
- (b) prior superseded + linked + cascade: 3 docs `superseded_by`→active + `superseded_at`; claims 17 superseded / 17 active (active claims tie only to active docs — no dangling refs)
- (c) mirror shows only active: 3 active doc-ids present, 3 superseded removed from the vault by sync
- (d) disk retention: `previous-results.md` (47 KB) in new run dir; prior raw gzipped (`.tar.gz`), archived not deleted

**Fix detail:** Defect 1 = explicit `raw_text=True` bypass on `PlainTextExtractor.extract` (shared `/`→path heuristic untouched). Defect 2 = ingest logs rollback loudly + raises on 0/N persisted; worker marks the queue item failed and does NOT advance lifecycle to `scanned` on zero-ingest; kept all-or-nothing per wallet. Regression tests added (memo-with-`/` ingests all 3; worker fails + skips advance on zero-persist). `0xcf60`'s lying `scanned`/no-dossier row reset to `queued` and re-driven.

**Baseline:** full suite 5355 passed / 1 skipped / 3 failed — the 3 are exactly the pre-existing `test_ris_phase4_source_acquisition` academic failures (backlogged). Guard-induced failures gone; fix added none. `api` docker service stopped. Closeout commit dfef21d. Dev log `docs/dev_logs/2026-06-01_wi-validation-fix.md`.

**v1 status:** ingestion pipeline e2e CONFIRMED on real data (the corrected "Outcome" claim now holds). **WI-5 (Discord) is the only remaining v1 packet**, parked on the operator-provided bot token.

**New backlog (tracked):** (1) Option B — remove the `/`→path content-sniffing heuristic across all callers, with a full caller audit. (2) The 3 pre-existing academic-ingest failures.

**Forward operational concern (raised 2026-06-01):** wallet-level supersede-on-new-run + success-gated archive means every re-scan creates a new run, supersedes the prior, gzips the prior raw, and accumulates superseded KS rows (≈3 docs + ~17 claims per re-scan per wallet). Under the scheduler's frequent watchlist re-scans this grows **without bound** on disk (archived `.tar.gz`) and in SQLite (superseded rows). Before running the scheduler hot for extended periods, add a retention cap (keep last N archives per wallet / prune beyond a window) + periodic prune/vacuum of superseded rows. Not a v1 blocker; plan it soon.


---

## VERIFICATION (2026-06-02) — approval gate independently confirmed; Discord descoped

Codex (independent of CC, the builder) ran a CLI-only e2e of the approval gate — **PASS on all steps:**
- `--list-pending --json` → exactly the 2 expected candidates (`0x84cf…2f63`, `0xcf60…a6f5`).
- Approve `0x84cf…`: review_status `pending`→`approved`; lifecycle `scanned`→`reviewed`.
- Deny `0xcf60…`: review_status `pending`→`rejected`; lifecycle `scanned`→`scanned`.
- Truncated approve (`0xcf60…`) **rejected**: "truncated/ambiguous identifiers are rejected", exit 1, no DB mutation path reached.
- Final `--list-pending` → `[]`.
- **No gate bypass:** only mutations via `discovery review --approve/--deny`; source-confirmed path is read row → `plan_review` → `validate_transition` → `write_watchlist_rows`. No direct ClickHouse writes.
- Run log: `docs/dev_logs/2026-06-02_wallet-ingestion-approval-gate-verification.md`.
- (Ran on Windows fallback — `wsl` reports no distro installed; Windows reached `polytool-clickhouse:8123`; `CLICKHOUSE_PASSWORD` loaded from `.env`, never printed.)

**Significance:** pipeline e2e confirmed 2026-06-01 + approval gate e2e confirmed 2026-06-02 → **wallet-ingestion v1 is functionally complete and independently verified, with no dependency on Discord.** The CLI gate is the real mechanism.

**Discord/Vera — descoped from v1 (operator ratification pending at time of write).** The two-way approval via the Vera Hermes agent hit a long chain of environment failures, none of which touched PolyTool code:
1. Vera's fallback LLM `google/gemini-2.0-flash-001` → 404 "no endpoints found" (Gemini 2.0 Flash retired ~Mar–Jun 2026; replace with a current model e.g. `gemini-2.5-flash-lite`).
2. Skill `polytool-approvals` not loaded — the running gateway's model is served `.skills_prompt_snapshot.json`, which only tracks **profile-dir + builtin** skills, NOT repo `external_dirs` skills. Move-to-external_dirs was the wrong call; reverted to profile dir.
3. `python` vs `python3` — Vera's WSL env has only `python3`; all skill invocations flipped.
4. Stale snapshot — a plain gateway restart does NOT regenerate the snapshot; must force a re-index.
5. **Root of the whole loop:** the gateway is a **systemd user service** (`hermes-gateway.service`, detached) — no foreground terminal existed, so the "restart" everyone assumed was happening never did; stale state served for hours. Restart via `systemctl --user restart`.

**Recommended v1-complete shape:** notifications via the existing shipped webhook (`packages/polymarket/notifications/discord.py` → `post_message`, `DISCORD_WEBHOOK_URL`, Vera-free, 29 tests) + approvals via the CLI gate. Vera two-way approval revisited only if reply-from-phone proves necessary.

**New forward items:**
- **Rich evidence before real promotions:** pending candidates currently display the generic worker reason ("scan-worker drained scan_queue"), not `summarize_evidence()`. Wire `summarize_evidence()` at list-pending/display time before approving real wallets.
- **Deny lifecycle edge:** deny leaves lifecycle at `scanned` with review_status `rejected`. Filtering by review_status works (rejected dropped from pending), but confirm the scheduler's re-scan won't resurrect a rejected wallet as `pending` before running the scheduler hot.
- (Retention cap for unbounded archive/superseded growth — tracked above — remains the hardening item before long scheduler runs.)
