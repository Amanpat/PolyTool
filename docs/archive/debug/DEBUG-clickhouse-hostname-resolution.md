# DEBUG: ClickHouse Hostname Resolution Failure on Windows Host

Date: 2026-02-16

## Symptom

Running `python -m polytool export-dossier --user "@example"` on a Windows host
produced a connection error:

```
clickhouse_connect.driver.exceptions.OperationalError:
  HTTPDriver for http://clickhouse:8123 ... Name or service not known
```

## Root Cause

`tools/cli/export_dossier.py` hard-coded `DEFAULT_CLICKHOUSE_HOST = "clickhouse"` --
the Docker Compose service name. This hostname only resolves inside the Docker bridge
network. On the Windows host, DNS cannot resolve `clickhouse`.

## Fix

Added a `_running_in_docker()` helper that checks:
1. `POLYTOOL_IN_DOCKER=1` env var (explicit override).
2. `/.dockerenv` file existence (standard Docker indicator).

The `_resolve_clickhouse_host()` function returns `"clickhouse"` when inside Docker
and `"localhost"` when on the host. `CLICKHOUSE_HOST` env var always takes priority.

Applied to all three CLI files that create ClickHouse clients:
- `tools/cli/export_dossier.py`
- `tools/cli/export_clickhouse.py`
- `tools/cli/examine.py`

## Verification

```powershell
# Host mode (no Docker, no env vars) -> connects to localhost:8123
pytest tests/test_clickhouse_host_resolution.py -v

# Manual: with Docker Compose running on default ports
docker compose up -d
python -m polytool export-dossier --user "@example" --days 30
```

See ADR: `docs/adr/0004-clickhouse-host-defaults.md`.
