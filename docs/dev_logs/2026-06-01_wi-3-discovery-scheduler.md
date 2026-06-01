# WI-3 — Discovery + Rescan Scheduler

Date: 2026-06-01
Sprint: Wallet-Ingestion v1
Packet: `docs/obsidian-vault/claude-memory/work-packets/work-packet-wi-3-discovery-scheduler.md`
Agent: Claude Code (ran in parallel with WI-6 / MVF — strictly disjoint files)

## Objective

Run discovery, queue drain, and watchlist rescans on a cadence by reusing the
existing RIS APScheduler pattern. Add tier-aware skip-if-recent and scan-queue
priority by tier so the queue drains locked → candidate → discovered → rest.

## Jobs added

New parallel registry `DISCOVERY_JOB_REGISTRY` in
`packages/research/scheduling/discovery_scheduler.py` (same dict shape as the RIS
`JOB_REGISTRY`: `id` / `name` / `trigger_description` / `callable_name`):

| Job id | Cadence (config default) | What it does |
|---|---|---|
| `discovery_loop_a` | every 6h | invokes `run_loop_a()` (leaderboard fetch → churn → enqueue new wallets) |
| `watchlist_rescan` | daily 01:00 + 13:00 | reads watchlist, applies tier-aware skip-if-recent, enqueues stale wallets at tier-correct priority |
| `queue_drain` | every 15 min | runs ONE bounded `ScanWorker.run(max_items=N)` tick, then flushes queue state to ClickHouse |

## Gate 1 — reuse, don't reinvent (evidence)

The new module is a structural mirror of `packages/research/scheduling/scheduler.py`:
- `DISCOVERY_JOB_REGISTRY` (list of dicts) mirrors `JOB_REGISTRY`.
- `_JOB_CALLABLE_MAP` / `_JOB_FN_MAP` lookups mirror the RIS module.
- `run_discovery_job(job_id) -> int` mirrors `run_job(job_id) -> int`.
- `start_discovery_scheduler(..., _scheduler_factory=, _job_runner=, exclude_job_ids=)`
  mirrors `start_research_scheduler` exactly — same guarded APScheduler import,
  same injectable fake-scheduler test seam, same late-binding closure capture,
  same `exclude_job_ids` skip path.

No second scheduler framework introduced. APScheduler `BackgroundScheduler` +
`CronTrigger` only, imported lazily inside the start function so the registry is
importable without APScheduler installed (same as RIS).

## Gate 2 — no RIS regression

The RIS `JOB_REGISTRY` (8 jobs), `start_research_scheduler`, and
`tools/cli/research_scheduler.py` were NOT touched. WI-3 lives in its own module
+ its own CLI subcommand group (`discovery scheduler ...`). Test
`TestNoRisRegression` asserts the RIS registry is still 8 jobs and that the
discovery job ids are disjoint from the RIS ids. RIS scheduler test files
(`test_ris_scheduler.py` 38, `test_ris_scheduler_split.py` 5) all still pass.

## Drain model chosen: single bounded tick (not long-lived)

`queue_drain` runs a single `ScanWorker.run(max_items=N)` per scheduler fire and
exits. Rationale: WI-1's `scan_worker.py` explicitly documents a SINGLE-WORKER
assumption — ClickHouse is OLAP and the in-memory lease is not an atomic
compare-and-set, so two concurrent drainers can TOCTOU-double-grab a dedup_key
and double-scan a wallet. A scheduled single tick means exactly one drainer is
alive at any moment, which stays inside WI-1's safety envelope without inventing
lease atomicity. The `restart: unless-stopped` compose service runs the
*scheduler*, not a continuous worker; the scheduler fires one bounded drain per
interval. If continuous/multi-worker drain is ever needed, real lease atomicity
(CAS guard or transactional store) must be added first — that remains a future
concern, not WI-3.

## Last-scan timestamp source for skip-if-recent

The freshness comparison uses the watchlist `last_scanned_at` column. This is the
most reliable source: WI-1's `make_clickhouse_watchlist_advancer` writes a fresh
watchlist row with `lifecycle_state='scanned'` and `last_scanned_at=now()` after
every successful drain (it also sets `last_scan_run_id`). The watchlist is
`ReplacingMergeTree(updated_at)` keyed on `wallet_address`, so `SELECT * FINAL`
returns the latest `last_scanned_at` per wallet. A wallet with `last_scanned_at IS
NULL` (never scanned) is treated as NOT recent → eligible for enqueue.

## Forward-compatible tier resolution (pre-WI-4 fallback)

CRITICAL constraint honored: **no watchlist DDL was changed.** The watchlist still
has only `lifecycle_state` / `review_status` / `source` (plus the human gate) —
WI-4 owns the `tier` / `locked` columns and runs AFTER WI-3.

`resolve_tier(row: dict) -> {locked|candidate|discovered|rest}` is column-presence
guarded:
1. If a `locked` column is present and truthy → `locked` (WI-4 path).
2. Else if a `tier` column holds a known tier string → that tier (WI-4 path).
3. Else fall back to existing fields (pre-WI-4):
   - `lifecycle_state in {promoted, watched}` → `locked` (operator-approved,
     actively tracked = highest value)
   - `lifecycle_state == reviewed` OR `review_status == approved` OR
     `source == manual` → `candidate`
   - `lifecycle_state in {discovered, queued, scanned, stale}` → `discovered`
   - anything else / unknown → `rest`

Because the row is read via `SELECT * FINAL` (no hardcoded column list), WI-4 can
add + populate `tier`/`locked` and the SAME resolver starts honoring them with
ZERO rework here — only steps 1–2 begin firing. A code comment in
`resolve_tier` documents this; tests `test_wi4_locked_column_wins` /
`test_wi4_tier_column_wins` lock in the forward-compat behavior, and
`test_fallback_does_not_error_without_tier_columns` proves a current-DDL row
resolves without error.

**Full locked-vs-candidate tiering activates once WI-4 lands.** Pre-WI-4 behavior
uses the fallback mapping above.

## Priority mapping

`tier → scan_queue.priority` (1=highest .. 5=lowest), config-driven:
`locked → 1`, `candidate → 2`, `discovered → 3`, `rest → 4`. The WI-1 worker
already sorts `get_pending()` by `(priority, created_at)`, so setting priority at
enqueue time is sufficient to make the queue drain locked → candidate →
discovered → rest. `plan_rescan_enqueues` also sorts its output by priority so
that, if the per-fire `max_enqueue` cap bites, the highest-value wallets are
enqueued first.

## Config knobs + defaults

`config/discovery_scheduler.json` (loaded defensively — missing file/key falls
back to module defaults that mirror the file):
- `cadences.{discovery_loop_a,watchlist_rescan,queue_drain}` — APScheduler
  CronTrigger kwargs.
- `skip_if_recent.{locked_hours=6, candidate_hours=24, discovered_hours=336(14d),
  rest_hours=720(30d)}`.
- `tier_priority.{locked=1, candidate=2, discovered=3, rest=4}`.
- `queue_drain.{max_items=10, max_attempts=5, lease_seconds=300, owner}`.
- `rescan.{max_enqueue=200, source=loop_a}`.

All thresholds/cadences are CONFIG, not hardcoded constants (global guard).
`_comment` keys are stripped before use and before being handed to CronTrigger.

## Compose service

`discovery-scheduler` added to `docker-compose.yml`, mirroring `ris-scheduler`:
`build` from `Dockerfile`, `env_file: .env`, `restart: unless-stopped`,
`depends_on: clickhouse healthy`, mounts `./config:ro`, `./kb`, `./artifacts`.
Command: `python -m polytool discovery scheduler start`. Reads
`CLICKHOUSE_PASSWORD` from `.env` (fail-fast per CLAUDE.md auth rule — the CLI
errors out if it is unset for a live start). Existing services untouched (YAML
validated; `ris-scheduler` + `discovery-scheduler` both present).

## WP-2 dependency note (acceptance gate 3)

Frequent (sub-daily) rescan — specifically the locked-tier 6h window — assumes
WP-2 (dossier supersede) is merged so re-scanning a wallet supersedes its prior
dossier rather than duplicating it. WP-2 is MERGED (WI-2 in this sprint). Defaults
are kept sane: locked 6h is the only sub-daily window; candidate/discovered/rest
are daily-or-slower. Do NOT lower these below WP-2 assumptions without operator
sign-off (documented in the config `_comment`).

## CLI

`tools/cli/discovery.py` gains a `scheduler` subcommand group:
- `discovery scheduler status [--json]` — list the 3 jobs (no scheduler started).
- `discovery scheduler start [--dry-run] [--exclude-jobs ...]` — start the loop
  (blocking; Ctrl-C to stop). `--dry-run` prints the schedule + resolved cron
  without starting. Live start requires `CLICKHOUSE_PASSWORD` (fail-fast).
- `discovery scheduler run-job <id> [--json]` — fire one job immediately.

## Acceptance gate 4 — no real-time

No Alchemy / WebSocket / live monitoring added. Discovery is cadence-driven only.
Loop B remains deferred.

## Tests + results

New: `tests/test_discovery_scheduler.py` — 39 tests covering:
- registry shape + RIS-disjointness (gates 1 & 2),
- tier-resolution fallback (no tier columns → no error) + WI-4 column override,
- skip-if-recent (never-scanned / within-window / outside-window per tier),
- `plan_rescan_enqueues` (recent skipped, stale enqueued, never-scanned enqueued,
  priority ordering locked→candidate→discovered→rest, max_enqueue cap keeps
  highest priority),
- tier→priority mapping,
- defensive config load (missing file, partial merge, repo config),
- `start_discovery_scheduler` injectable (3 jobs registered, exclude, job_id
  routing, no fire at start),
- `run_discovery_job` (unknown id, success, exception, missing-password
  fail-fast),
- CLI status/status-json/start-dry-run/run-job-unknown.

Commands run (exact results):
- `python -m polytool --help` → loads, no import errors (MAIN_HELP_OK).
- `python -m polytool discovery --help` → shows `scheduler` subcommand.
- `python -m pytest tests/test_discovery_scheduler.py tests/test_ris_scheduler.py
  tests/test_ris_scheduler_split.py -q` → **82 passed** (39 new + 38 RIS + 5
  RIS-split). RIS scheduler tests unaffected.
- `python -m pytest tests/ -k "discovery or scan_worker or scan_queue or loop_a"`
  → **273 passed, 5048 deselected**. No discovery-pipeline regressions.

## Codex review tier

Recommended tier (research-side scheduler). Per the project Codex policy, the
mandatory tier covers `execution/`, kill switch, risk manager, signing, order
placement — none of which WI-3 touches. `scan_worker.py` / `scan_queue.py` /
execution code were NOT modified (the scheduler only *calls* the existing WI-1
worker). Background review recommended; not run inline in this packet.

## Files

Created:
- `config/discovery_scheduler.json`
- `packages/research/scheduling/discovery_scheduler.py`
- `tests/test_discovery_scheduler.py`
- `docs/dev_logs/2026-06-01_wi-3-discovery-scheduler.md`

Modified:
- `tools/cli/discovery.py` (added `scheduler` subcommand group + `_add_ch_args`)
- `docker-compose.yml` (added `discovery-scheduler` service)
- `docs/CURRENT_STATE.md` (minimal append)

## Open risks / not done

- Live end-to-end (real ClickHouse + APScheduler firing) not exercised — all
  tests are offline by packet mandate. The job callables' ClickHouse I/O is
  reused unchanged from WI-1/Loop A, which are independently tested.
- `watchlist_rescan` reads the whole non-retired watchlist per fire via
  `SELECT * FINAL`; fine at current scale, may need server-side filtering on
  `last_scanned_at` once the watchlist grows large (future optimization, not a
  correctness issue).
- Full tiering is inert until WI-4 populates `tier`/`locked`; pre-WI-4 the
  fallback mapping is authoritative (by design).
