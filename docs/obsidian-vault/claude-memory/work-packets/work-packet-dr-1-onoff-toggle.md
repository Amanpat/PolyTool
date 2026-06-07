---
title: "Work Packet — DR-1 One-Command On/Off Toggle"
type: work_packet
status: active
source_zone: claude_memory
last_updated: 2026-06-04
lifecycle: draft
tags: [work-packet, wallet-discovery, day-run, ease-of-use, docker]
target_agent: claude-code
acceptance_criteria:
  - See Definition of Done
---
# Work Packet — DR-1 One-Command On/Off Toggle

**Status: DRAFT — pending architect review.**

## Goal
One command turns scanning on, one turns it off — safely, with the data store always available. Honors the ease-of-use standard: simple to run, hard to break.

## Context (audit evidence)
- Scanner service is `discovery-scheduler` (`docker-compose.yml:159-176`); it `depends_on` healthy ClickHouse and reaches the local API for scans (`tools/cli/wallet_scan.py:368-394` → `scan.run_scan` → `api_base_url`).
- ClickHouse + API must be up for scans; they should STAY up when scans are off (so Grafana/queries/`/status` keep working).
- `docker compose down -v` wipes volumes → forbidden as a toggle.

## Scope
1. **`scan-on`** — bring up exactly `clickhouse`, `api`, `discovery-scheduler` (`docker compose up -d <those services>`). Idempotent (safe to run when already up).
2. **`scan-off`** — `docker compose stop discovery-scheduler` only. Leaves ClickHouse + API running.
3. **`scan-status`** (quick CLI) — print container state for the three services + current scan-queue depth and watchlist pending count (ClickHouse reads). This is the terminal complement to the Discord `/status` card.
4. **Wrapper surface** — expose all three as `make scan-on` / `make scan-off` / `make scan-status` (or a single `scripts/scan.sh {on|off|status}`). Pick one and document it as the canonical interface.
5. **Guardrail** — the wrapper must never invoke `down` or `-v`. Add a short header comment + a refusal if someone passes a teardown flag through it.

## Steps
1. Add the Make targets (or script) wrapping the compose commands above.
2. Implement `scan-status` reads (queue depth, pending count) reusing existing ClickHouse readers.
3. Document the canonical on/off/status commands + the `-v` prohibition in the operator quickstart / README section.
4. Smoke: on → status shows running → off → status shows scheduler stopped, ClickHouse/API still up.
5. Dev log + CURRENT_STATE.

## Definition of Done
- [ ] `scan-on` brings up clickhouse+api+scheduler; idempotent.
- [ ] `scan-off` stops only the scheduler; ClickHouse + API remain up.
- [ ] `scan-status` prints service states + queue depth + pending count.
- [ ] Canonical interface documented; `down`/`-v` cannot be triggered through the wrapper.
- [ ] Smoke verified; dev log written.

## Acceptance Gates
1. **Depends on DR-0** — clean stop must already be in place (no hard-kill data risk).
2. **Data store survives off.** Turning scans off never stops ClickHouse or the API.
3. **No `-v`, ever.** Verified by inspecting the wrapper.

## Non-Goals
No systemd/cron auto-start (operator runs the command); no full-stack toggle; no UI.

## Dependencies
DR-0 (graceful stop + verified ClickHouse persistence).

## Cross-References
- [[claude-memory/work-packets/work-packet-scan-day-run-sprint]]
- [[claude-memory/work-packets/work-packet-dr-0-start-stop-safety]]

## Connections
- [[claude-memory/work-packets/_index]]
- [[index|Vault Home]]
