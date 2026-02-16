# ADR 0004: ClickHouse Host Defaults for Windows Host vs Docker

Date: 2026-02-16
Status: Accepted

## Context

Running `python -m polytool export-dossier` on a Windows host failed to connect to
ClickHouse because the CLI defaulted to `host="clickhouse"` -- the Docker service name,
which only resolves inside the Docker network. Windows users had to manually set
`CLICKHOUSE_HOST=localhost` every time.

Additionally, docker-compose mapped ClickHouse to non-standard host ports (18123/19000),
requiring extra `.env` configuration before the standard `curl localhost:8123` would work.

## Decision

1. **Port mappings**: Change docker-compose defaults from `18123:8123` / `19000:9000` to
   `8123:8123` / `9000:9000`. Still overridable via `CLICKHOUSE_HTTP_PORT` /
   `CLICKHOUSE_NATIVE_PORT` env vars.

2. **Host resolution**: CLI tools auto-detect Docker vs host environment:
   - If `CLICKHOUSE_HOST` is set, use it (explicit always wins).
   - Else if running inside Docker (`/.dockerenv` exists or `POLYTOOL_IN_DOCKER=1`),
     default to `"clickhouse"` (Docker service name).
   - Else default to `"localhost"` (host machine).

3. **Port fallback chain**: `CLICKHOUSE_PORT` -> `CLICKHOUSE_HTTP_PORT` -> `8123`.

4. **Database fallback chain**: `CLICKHOUSE_DATABASE` -> `CLICKHOUSE_DB` -> `"polyttool"`.

## Consequences

- `python -m polytool export-dossier` works on Windows host without extra env vars.
- Existing Docker-internal services (API container) still use `CLICKHOUSE_HOST=clickhouse`
  set explicitly in docker-compose.yml, unaffected by this change.
- Users who previously set `CLICKHOUSE_HTTP_PORT=8123` in `.env` need no changes; the
  default now matches.
