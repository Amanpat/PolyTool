# DR-1 One-Command On/Off Toggle

Date: 2026-06-04
Packet: `docs/obsidian-vault/claude-memory/work-packets/work-packet-dr-1-onoff-toggle.md`
Depends on: DR-0 (graceful SIGTERM stop + verified ClickHouse named volume `clickhouse_data`) — DONE in this same session (`docs/dev_logs/2026-06-04_dr-0-start-stop-safety.md`).
Scope: research-side day-run ergonomics only. Denylist (kill switch / EIP-712 / order execution / risk-manager / live bot) untouched. No edits to `docker-compose.yml`, `tools/cli/discovery.py`, `docs/CURRENT_STATE.md`, or `docs/CURRENT_DEVELOPMENT.md` (owned by DR-0/DR-2/orchestrator).

Codex review: SKIP per project policy — this packet is shell/CLI wrapper + a read-only status helper; no execution/signing/risk/kill-switch files touched.

---

## Canonical interface

`scripts/scan.sh {on|off|status}` is the canonical documented interface (chosen over a Makefile because the repo already standardizes on `scripts/*.sh`, e.g. `docker-start.sh`). A small Python helper `scripts/scan_status.py` backs `status` by importing the existing ClickHouse readers (no new SQL).

```text
bash scripts/scan.sh on      -> docker compose up -d clickhouse api discovery-scheduler
bash scripts/scan.sh off     -> docker compose stop discovery-scheduler
bash scripts/scan.sh status  -> docker compose ps + ClickHouse reads (existing readers)
```

---

## DoD 1 — `scan-on` brings up clickhouse+api+scheduler; idempotent

**Status: DONE (deterministic test evidence; live up BLOCKED — see Live Smoke).**

`scan.sh on` runs exactly `docker compose up -d clickhouse api discovery-scheduler`. `docker compose up -d` is idempotent by design (no-op for already-running services, starts only what is down). The exact three-service command string is asserted by test.

Evidence — `tests/test_scan_toggle.py`:

```text
test_on_emits_exact_up_command   PASSED
```

`SERVICES=(clickhouse api discovery-scheduler)` + `docker compose up -d "${SERVICES[@]}"` in `scripts/scan.sh`.

---

## DoD 2 — `scan-off` stops only the scheduler; ClickHouse + API remain up

**Status: DONE (deterministic test evidence).**

`scan.sh off` runs exactly `docker compose stop discovery-scheduler` — and ONLY that service. ClickHouse and API are never named in any stop line, so the data store and query/Grafana/`/status` surfaces stay up. `docker compose stop` (not `kill`) delivers SIGTERM, which the DR-0 graceful handler traps and exits 0 within the grace window — clean stop, no data risk.

Evidence — `tests/test_scan_toggle.py`:

```text
test_off_emits_exact_stop_command         PASSED
test_off_does_not_stop_clickhouse_or_api  PASSED
```

`test_off_does_not_stop_clickhouse_or_api` parses every executable `docker compose stop` line and asserts it targets `SCHEDULER_SERVICE` only and contains neither `clickhouse` nor `api`.

---

## DoD 3 — `scan-status` prints service states + queue depth + pending count

**Status: DONE (helper runs end-to-end; live ClickHouse counts BLOCKED on no running stack/creds).**

`scripts/scan_status.py` prints, in order: (1) `docker compose ps` for the three services, (2) scan-queue depth, (3) watchlist pending count. It REUSES existing readers — no new SQL:

- queue depth: `ScanQueueManager.load_from_clickhouse()` + `get_pending()` (the same readers `discovery run-worker` uses — `tools/cli/discovery.py:410-411`).
- pending count: `clickhouse_writer.read_pending_candidates()` (the same reader the Discord notify path uses — `packages/polymarket/discovery/clickhouse_writer.py:291-355`).

Live run (Docker present in this env, stack down, no creds) — proves wiring + ASCII-only output + fail-soft on missing creds:

```text
PolyTool scan status (DR-1) -- READ ONLY

== Services (docker compose ps) ==
  NAME      IMAGE     COMMAND   SERVICE   CREATED   STATUS    PORTS

== ClickHouse reads ==
  CLICKHOUSE_PASSWORD not set -- skipping queue/pending reads.
  (set CLICKHOUSE_PASSWORD to see scan-queue depth + pending count)

exit=0
```

Evidence — `tests/test_scan_toggle.py`:

```text
test_status_reader_reuses_existing_functions      PASSED   (asserts the exact imports; no hand-rolled SQL)
test_status_reader_imports_and_runs_without_creds PASSED   (no-creds path returns 0, never raises)
```

**BLOCKED sub-item:** the actual integer queue-depth / pending-count values require a running ClickHouse with data + `CLICKHOUSE_PASSWORD`. Not available in this environment. Operator confirms by exporting `CLICKHOUSE_PASSWORD` and running `bash scripts/scan.sh status` against the live stack.

---

## DoD 4 — Canonical interface documented; `down`/`-v` cannot be triggered through the wrapper

**Status: DONE (header comment + active refusal + live + test evidence).**

The wrapper carries a header-comment block stating the hard rule, plus an active `refuse_teardown()` guard that refuses any of `down -v --volumes --remove-orphans rm kill` (whether passed as the action or as an extra arg) and exits non-zero. By inspection, **the wrapper contains no executable `docker compose down` and never passes `-v`/`--volumes`** — the only forbidden-token occurrences are in the documentation/usage text and the refusal case pattern.

Live refusal:

```text
$ bash scripts/scan.sh down
REFUSED: 'down' is a teardown/volume-destroying operation.
scripts/scan.sh never runs 'docker compose down' or passes '-v'.
To pause scanning use: bash scripts/scan.sh off
ClickHouse data lives on the persistent named volume 'clickhouse_data';
only 'docker compose down -v' destroys it and this wrapper forbids that.
exit=2

$ bash scripts/scan.sh -v        -> same REFUSED block, exit=2
```

Evidence — `tests/test_scan_toggle.py`:

```text
test_wrapper_never_executes_compose_down   PASSED   (no executable `docker compose down`)
test_wrapper_never_executes_volume_flag    PASSED   (no executable `-v` / `--volumes`)
test_refusal_branch_lists_teardown_tokens  PASSED
test_teardown_token_is_refused_live[down]      PASSED  (invokes wrapper under bash, asserts non-zero)
test_teardown_token_is_refused_live[-v]        PASSED
test_teardown_token_is_refused_live[--volumes] PASSED
test_unknown_command_exits_nonzero             PASSED
```

**Explicit confirmation:** the wrapper cannot trigger `docker compose down` or `-v`/`--volumes`. Verified by (a) source inspection — no executable line invokes them; (b) the static no-down / no-`-v` tests over the wrapper's executable lines; (c) the live refusal tests that actually execute the script and assert a non-zero exit with the `REFUSED` message.

Documentation: `docs/runbooks/WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md` gains a "Day-Run On/Off Toggle (DR-1)" section with the canonical commands, the under-the-hood compose table, Windows usage, and the "never `down -v`" hard rule.

---

## DoD 5 — Smoke verified; dev log written

**Status: PARTIAL — wrapper logic smoke DONE; full on->status->off live smoke BLOCKED (no running stack).**

- DONE: `bash scripts/scan.sh help` and `bash scripts/scan.sh status` run cleanly end-to-end (output above); the teardown refusal runs live (output above). The exact `up`/`stop` command strings are asserted deterministically.
- BLOCKED: the full lifecycle smoke (on -> status shows scheduler running -> off -> status shows scheduler stopped while ClickHouse/API stay Up) needs a running ClickHouse + API + a built `discovery-scheduler` image, which are not available here. Dev log written (this file).

**Operator steps to close the BLOCKED live smoke** (host with the stack/`.env`):

```bash
export CLICKHOUSE_PASSWORD=...                 # from .env
bash scripts/scan.sh on                        # expect: all 3 services Up
bash scripts/scan.sh status                    # expect: discovery-scheduler Up; queue depth + pending count printed
bash scripts/scan.sh off                       # expect: only discovery-scheduler stops
bash scripts/scan.sh status                    # expect: clickhouse + api still Up; discovery-scheduler Exited/stopped
docker compose ps clickhouse api               # confirm data-store services survived 'off'
```

---

## Tests

New file `tests/test_scan_toggle.py` — 12 tests:

```text
python -m pytest tests/test_scan_toggle.py -v
=> 12 passed in 0.44s   (0 failed, 0 skipped — bash present, live-refusal tests ran)
```

Focused regression subset (new + reused discovery/notify):

```text
python -m pytest tests/test_scan_toggle.py tests/test_wallet_ingestion_notify.py \
  tests/test_discovery_scheduler.py tests/test_wallet_discovery_two_tier.py -q
=> 147 passed   (0 failed, 0 skipped)
```

CLI still loads: `python -m polytool --help` -> CLI_OK (no import errors). `tools/cli/discovery.py` NOT touched (DR-2 owns it; `scan-status` is a standalone helper that imports readers, not a discovery subparser).

No new pre-existing-RIS-academic failures surfaced (those suites were not in this packet's focused run).

---

## Files changed (all uncommitted)

- `scripts/scan.sh` — NEW: canonical `{on|off|status}` wrapper; header-comment hard rule; `refuse_teardown()` guard; ASCII-only.
- `scripts/scan_status.py` — NEW: read-only status helper reusing `ScanQueueManager.load_from_clickhouse`/`get_pending` + `read_pending_candidates`; fail-soft on missing creds; ASCII-only.
- `tests/test_scan_toggle.py` — NEW: 12 deterministic tests (exact compose command strings, no-down/no-`-v` over executable lines, live teardown refusal, status reader reuse).
- `docs/runbooks/WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md` — added "Day-Run On/Off Toggle (DR-1)" operator section.
- `docs/dev_logs/2026-06-04_dr-1-onoff-toggle.md` — this dev log.

## Acceptance Gates

1. **Depends on DR-0** — SATISFIED: `scan.sh off` uses `docker compose stop` (SIGTERM), which DR-0's graceful handler traps for a clean exit; ClickHouse persistence verified by DR-0 on named volume `clickhouse_data`.
2. **Data store survives off** — SATISFIED: `off` stops only `discovery-scheduler`; tests assert clickhouse/api are never in a stop line.
3. **No `-v`, ever** — SATISFIED: verified by inspection + tests over executable lines + a live refusal that blocks `down`/`-v`/`--volumes`.

## Open items / blockers

- Full live on->status->off smoke is BLOCKED (no running stack/Docker image in this env) — operator steps provided above.
- Live integer queue-depth / pending-count values BLOCKED on a running ClickHouse + `CLICKHOUSE_PASSWORD`.
