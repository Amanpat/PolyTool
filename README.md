# PolyTool

Local-first toolbox for analysing Polymarket trading activity.
Everything runs on your laptop â€” no cloud accounts, no hosted databases.

---

## What it does

- **Scan** a user's trade history via the local API and write trust artifacts to disk.
- **Audit** coverage quality offline â€” works on a travel laptop with no ClickHouse.
- **Bundle** evidence for pasting into an LLM (works without RAG; excerpts are omitted if RAG is not indexed).
- **Analyse** outcomes, PnL, fees, and category coverage through Grafana dashboards.

---

## Quickstart (Local)

### 1 â€” Start infrastructure

```bash
docker compose up -d
```

Verify ClickHouse is responding:

```bash
curl "http://localhost:8123/?query=SELECT%201"
# expected: 1
```

Check all services are healthy:

```bash
docker compose ps
# polyttool-clickhouse   Up (healthy)
# polyttool-grafana      Up (healthy)
# polyttool-api          Up (healthy)
```

Grafana: <http://localhost:3000> (admin / admin)
API docs: <http://localhost:8000/docs>

---

### 2 â€" Run a scan

The canonical Roadmap 4 scan command - ingests positions, computes PnL, enriches
resolution outcomes, writes trust artifacts, and always emits an audit report in
the same run root:
```bash
python -m polytool scan \
  --user "@DrPufferfish" \
  --ingest-positions \
  --compute-pnl \
  --enrich-resolutions \
  --debug-export
```

By default the audit report includes **all** positions.  To limit to a deterministic
sample, pass `--audit-sample N` (and optionally `--audit-seed SEED`):

```bash
python -m polytool scan \
  --user "@DrPufferfish" \
  --ingest-positions \
  --compute-pnl \
  --enrich-resolutions \
  --audit-sample 25 \
  --audit-seed 1337
```

`--debug-export` prints wallet, endpoints, and hydration diagnostics â€" useful when
coverage looks sparse or `positions_total = 0`.

The scan prints a summary and emits a **run root** directory:

```
artifacts/dossiers/users/drpufferfish/0xdb27.../2026-02-18/<run_id>/
```

---

### 3 - Optional: re-run audit coverage offline

No ClickHouse, no network - reads the scan artifacts written in step 2.
By default includes **all** positions.  Use `--sample N` to limit:

```bash
# All positions (default)
python -m polytool audit-coverage --user "@DrPufferfish"

# Limit to 25 positions
python -m polytool audit-coverage --user "@DrPufferfish" --sample 25 --seed 1337
```

Outputs a markdown report at the run root.  To get a machine-readable copy:

```bash
python -m polytool audit-coverage --user "@DrPufferfish" --format json
```

---

### 4 â€” Build an LLM evidence bundle

```bash
python -m polytool llm-bundle --user "@DrPufferfish"
```

**Note:** works without RAG installed.  If the RAG index has not been built,
the `## RAG excerpts` section is omitted and the command still exits 0.

---

## Outputs / Where files go

All scan and audit artifacts live under a **run root**:

```
artifacts/dossiers/users/<slug>/<wallet>/<YYYY-MM-DD>/<run_id>/
```

| File | Description |
|------|-------------|
| `run_manifest.json` | Run provenance: command, argv, timestamps, config hash, output paths |
| `dossier.json` | Raw position/trade export from the API |
| `coverage_reconciliation_report.json` | Machine-readable trust report (outcomes, UID coverage, PnL, fees, resolution, segment analysis) |
| `coverage_reconciliation_report.md` | Optional human-readable rendering of the same report |
| `segment_analysis.json` | Segment breakdown by entry price tier, market type, league, sport, category |
| `resolution_parity_debug.json` | Cross-run resolution enrichment diagnostics |
| `audit_coverage_report.md` | Offline accuracy + trust sanity report; always emitted by `scan` (or by `audit-coverage`). Includes all positions by default; use `--audit-sample N` / `--sample N` to limit. |

LLM bundles are written to a separate private path:

```
kb/users/<slug>/llm_bundles/<YYYY-MM-DD>/<run_id>/bundle.md
```

---

## Configuration

PolyTool reads `polytool.yaml` (or `polytool.yml`) from the current working
directory.  All keys are optional.

### Entry price tiers

```yaml
segment_config:
  entry_price_tiers:
    - name: deep_underdog
      max: 0.30
    - name: underdog
      min: 0.30
      max: 0.45
    - name: coinflip
      min: 0.45
      max: 0.55
    - name: favorite
      min: 0.55
```

If omitted, the built-in defaults above are used.

### Fee configuration

```yaml
fee_config:
  profit_fee_rate: 0.02   # 2 % estimated fee on winning positions
  source_label: estimated # label written into the coverage report
```

`profit_fee_rate` must be a non-negative float.  The default is `0.02`.

---

## Troubleshooting (Windows)

### ClickHouse: `localhost` vs `127.0.0.1`

On Windows, `localhost` can resolve to `::1` (IPv6) before `127.0.0.1` (IPv4),
which causes connection-refused errors on port 8123.

**Fix:** use `127.0.0.1` explicitly in your `.env`:

```env
# .env
API_BASE_URL=http://127.0.0.1:8000
```

Or pass it directly:

```bash
python -m polytool scan --user "@example" --api-base-url http://127.0.0.1:8000
```

### Ports

| Service | HTTP port | Native/TCP port |
|---------|-----------|-----------------|
| ClickHouse | `8123` (HTTP) | `9000` (native client) |
| API | `8000` | â€” |
| Grafana | `3000` | â€” |

The scan CLI only uses the **API on port 8000** (not ClickHouse directly).
ClickHouse ports are used by Grafana and ClickHouse native client tools.

### `positions_total = 0` after a scan

1. Re-run with `--debug-export` to see which wallet and endpoint was used.
2. Confirm the handle resolves to a real proxy wallet
   (`/api/resolve` endpoint in the Swagger UI).
3. Try `--ingest-positions` to force a fresh positions snapshot before scanning.
4. If the export is consistently empty, check the history endpoint:
   `/api/export/user_dossier/history?user=@example&limit=5`.

---

## Repository layout

```
services/api/         FastAPI service (ingest, compute, export)
infra/clickhouse/     ClickHouse schemas and init SQL
infra/grafana/        Grafana dashboards and provisioning
packages/polymarket/  Shared clients + analytics (resolution, RAG, etc.)
tools/cli/            Local CLI utilities
polytool/             CLI entry point + reports
docs/                 Public truth source and ADRs
kb/                   Private local data (gitignored)
artifacts/            Scan + dossier outputs (gitignored)
```

See `docs/ARCHITECTURE.md` for the full data-flow diagram.
See `docs/TRUST_ARTIFACTS.md` for the trust artifact schema reference.
See `docs/LOCAL_RAG_WORKFLOW.md` for RAG indexing and querying.

---

## Database access

| Role | User | Password | Access |
|------|------|----------|--------|
| Admin | `polyttool_admin` | `polyttool_admin` | Full |
| Grafana | `grafana_ro` | `grafana_readonly_local` | SELECT only |

---

## Infrastructure commands

```bash
# Start all services
docker compose up -d

# Check status
docker compose ps

# View logs for a service
docker compose logs -f api

# Stop without removing volumes
docker compose down

# Full reset (destroys all data)
docker compose down -v && docker compose up -d
```
