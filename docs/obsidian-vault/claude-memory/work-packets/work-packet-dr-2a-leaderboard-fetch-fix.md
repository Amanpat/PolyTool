---
title: "Work Packet — DR-2a Leaderboard Fetch Zero-Results Fix"
type: work_packet
status: active
source_zone: claude_memory
last_updated: 2026-06-04
lifecycle: draft
tags: [work-packet, wallet-discovery, day-run, leaderboard, data-api, bugfix, diagnose-first]
target_agent: claude-code
acceptance_criteria:
  - See Definition of Done
---
# Work Packet — DR-2a Leaderboard Fetch Zero-Results Fix

**Status: DRAFT — ready to run. Prerequisite for [[claude-memory/work-packets/work-packet-dr-2-batch-seed-top200]] (DR-2 assumed `fetch_leaderboard()` works; it returns 0).**

## Goal
Make `discovery export-leaderboard` return real wallet addresses again. Today it writes **0 addresses** with a soft warning, which blocks the entire scan (no seed list → no corpus). Diagnose the true cause before fixing — the first guess this session (params) was already disproven by curl.

## Context — verified live this session (guess-nothing evidence)
- `curl -i https://data-api.polymarket.com/` → **200 OK** `{"data":"OK"}`. Host reachable from the operator's machine. **Not geo-blocked** (kills the Canadian-machine pivot).
- `curl "…/v1/leaderboard?order_by=PNL&time_period=DAY&limit=50&offset=0"` → **200, `list 50`**. Base URL, path (`/v1/leaderboard`), and the code's exact param set are all CORRECT.
- Server **ignores** `order_by`, `time_period`, `offset`; honors only `limit`, **capped at 50/page**. Bare call → 25 (default), already sorted `pnl` descending.
- `…?limit=50&offset=50` pagination behavior was the open question at packet-write time — STEP 1 re-confirms it.
- Yet `python -m polytool discovery export-leaderboard --top 5` writes **0 addresses** ("leaderboard API returned no entries"). So the failure is **downstream of the URL** — in `HttpClient`, response handling, or the DR-2 export CLI. Not the endpoint.
- Response address field = `proxyWallet`. `rank` is a **string** (`"1".."50"`).
- Leading (UNCONFIRMED) hypothesis: **Cloudflare serves 200 to curl but 403-challenges the default `python-requests` User-Agent**, so `resp.status_code != 200` → fetcher breaks → returns `[]`. Consistent with the 403 seen against data-api in the build sandbox earlier. **If true, this also breaks every wallet scan** (the scan path hits the same `data-api` host via the same client) — so the fix unblocks the whole pipeline, not just the leaderboard.

## Files in scope
- `packages/polymarket/discovery/leaderboard_fetcher.py` (fetch + sort)
- `packages/polymarket/http_client.py` (only if STEP 1 proves a 403/User-Agent block)
- The DR-2 `export-leaderboard` CLI (only if STEP 1 proves the fetcher is fine)

## STEP 1 — DIAGNOSE (capture evidence; fix nothing yet)
From repo root, venv active, run and record the exact output:
```
python -c "import logging; logging.basicConfig(level=logging.DEBUG); from packages.polymarket.discovery.leaderboard_fetcher import fetch_leaderboard; r=fetch_leaderboard(); print('RESULT', type(r).__name__, len(r))"
```
Decide which is true:
- **(a)** Logs a non-200 status (e.g. 403) → Cloudflare / User-Agent block on `python-requests`.
- **(b)** Logs an exception / traceback → read it.
- **(c)** Returns ~50 fine → the bug is in the **DR-2 export CLI**, not the fetcher; trace how `export-leaderboard` calls the fetcher and extracts/writes addresses.

Also confirm pagination: `curl -s "https://data-api.polymarket.com/v1/leaderboard?limit=50&offset=50"` → first entry rank `"51"` (offset works) or `"1"` (offset IGNORED).

## STEP 2 — FIX (apply only what STEP 1 supports)
- **If (a):** add a default desktop-browser `User-Agent` header in `http_client.py` so every data-api request carries it. **ADDITIVE only** — do NOT change timeout / retry / backoff semantics; keep per-call header overrides working. This is the precondition for the whole scan, not just the leaderboard.
- **If (b):** minimal fix per the traceback.
- **If (c):** fix the export CLI extraction to read `proxyWallet`.
- **ALWAYS:** fix the rank sort in `leaderboard_fetcher.py` — replace `key=lambda e: e.get("rank", 0)` with `key=lambda e: int(e.get("rank") or 0)`. String ranks currently sort lexicographically (1, 10, 11, …, 2), so "top 5" returns the wrong five.
- **PAGINATION:** if STEP 1 shows `offset` is IGNORED, the existing multi-page loop refetches the same 50 rows → duplicates. Dedupe by `proxyWallet`, return only unique wallets, and surface the true unique count so `--top 200` cannot silently write 50. If offset works, leave paging alone.

## STEP 3 — TEST (evidence-gated; paste outputs into the dev log)
- `export-leaderboard --top 5 --out artifacts/watchlists/top5.txt` → assert exactly **5 distinct `0x` addresses**; cat the file.
- If offset works: `--top 200 --out artifacts/watchlists/top200.txt` → assert ~200 distinct. If offset ignored: document the unique cap, write that many, **no silent padding**.

## STEP 4 — DEV LOG
`docs/dev_logs/2026-06-04_leaderboard-fetch-fix.md`: actual root cause (with captured status/log), diff summary, before/after counts, offset/pagination finding.

## Definition of Done
- [ ] STEP 1 diagnosis recorded (which of a/b/c, plus offset behavior).
- [ ] Matching fix applied; rank sort fixed in all cases.
- [ ] `export-leaderboard --top 5` writes 5 distinct addresses (verified by cat).
- [ ] Pagination correct (or unique cap documented; no silent padding).
- [ ] Dev log written; `CURRENT_STATE.md` touched.

## Acceptance Gates
1. **Diagnose before fixing.** No fix lands without STEP 1 evidence in the dev log.
2. **Additive infra change.** If `HttpClient` is touched, retry/timeout/backoff behavior is unchanged and existing tests still pass.
3. **No silent corpus shrink.** `--top 200` must never quietly return 50.
4. **Denylist untouched** (kill switch, signing, order/price paths, risk manager).

## Non-Goals
No scheduler work; no Discord; no Grafana; no pacing redesign (DR-2 owns pacing); no new dependencies.

## Dependencies
None hard (data-api + venv). Runs first, before DR-2's batch run.

## Sequencing note
Single Claude Code session. **No sub-agents** — this is one short diagnose→fix→test loop, not parallelizable. Read-path discovery code → full Codex adversarial review not required; a quick `/codex:review` is optional insurance only because the fix may touch the shared `HttpClient` (blast radius on other data-api callers).

## Cross-References
- [[claude-memory/work-packets/work-packet-dr-2-batch-seed-top200]] — the batch run this unblocks
- [[claude-memory/work-packets/work-packet-scan-day-run-sprint]] — sprint overview
- [[claude-memory/session-notes/2026-06-04-scan-day-run-readiness-scoping]] — scoping + decisions
- repo `docs/dev_logs/2026-06-04_day-run-readiness-audit.md`

## Connections
- [[claude-memory/work-packets/_index]]
- [[index|Vault Home]]
