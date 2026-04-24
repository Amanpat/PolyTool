# WP4-B Activation Plumbing

**Date:** 2026-04-23
**Work packet:** WP4-B activation follow-up (operationalization pass)
**Depends on:** WP4-B (`infra/n8n/workflows/ris-n8n-metrics-collector.json`)

---

## What Changed and Why

WP4-B created the metrics collector workflow but left two activation prerequisites
explicitly out of scope. This pass closes them so the collector can be imported and
activated without any out-of-band manual steps beyond generating the n8n API key.

### 1. `docker-compose.yml` — n8n service environment (lines 219-222)

Added two env vars to the `n8n` service `environment:` block:

```yaml
- CLICKHOUSE_PASSWORD=${CLICKHOUSE_PASSWORD}
- N8N_API_KEY=${N8N_API_KEY:-}
```

**Why:** The metrics collector workflow reads both at runtime via `$env.*`. Without
these entries the n8n container environment is blind to both secrets even if they
are set in `.env`.

- `CLICKHOUSE_PASSWORD` is already required by the ClickHouse service (`:?` guard there).
  Passed through with a plain `${CLICKHOUSE_PASSWORD}` — no default needed.
- `N8N_API_KEY` is generated post-first-login from the n8n UI, so it may not exist
  at initial stack start. Used `${N8N_API_KEY:-}` (empty default) to avoid compose
  startup failure before the key is generated.

### 2. `infra/n8n/import_workflows.py` — `CANONICAL_WORKFLOWS`

Added:

```python
("METRICS_COLLECTOR_ID", "ris-n8n-metrics-collector.json"),
```

**Why:** The import script iterates `CANONICAL_WORKFLOWS` to decide which workflows to
push. Without this entry `python infra/n8n/import_workflows.py --no-activate` silently
skips the metrics collector, leaving it unmanaged by the importer.

### 3. `.env.example` — n8n section

Added `N8N_API_KEY=replace_with_api_key_from_n8n_ui` with a comment explaining where
to generate it and why it is needed (import script + n8n container runtime).

---

## Files Changed

| File | Change |
|------|--------|
| `docker-compose.yml` | Added `CLICKHOUSE_PASSWORD` and `N8N_API_KEY` to n8n service environment |
| `infra/n8n/import_workflows.py` | Added `METRICS_COLLECTOR_ID` to `CANONICAL_WORKFLOWS` |
| `.env.example` | Added `N8N_API_KEY` placeholder in n8n section |

---

## Commands Run / Validation Results

```
python -m polytool --help
```
**Result:** CLI loads cleanly. No import errors.

```python
# AST parse of CANONICAL_WORKFLOWS
CANONICAL_WORKFLOWS: [
  ('UNIFIED_DEV_ID', 'ris-unified-dev.json'),
  ('HEALTH_WEBHOOK_ID', 'ris-health-webhook.json'),
  ('METRICS_COLLECTOR_ID', 'ris-n8n-metrics-collector.json'),
]
```
**Result:** New entry confirmed present.

```
python infra/n8n/import_workflows.py --help
```
**Result:** Script parses and prints help cleanly. No import errors.

```
grep -n "CLICKHOUSE_PASSWORD\|N8N_API_KEY" docker-compose.yml
```
**Result:** Both vars appear at lines 221-222 inside the n8n service block.

---

## Activation Prerequisites — Status After This Pass

| Prerequisite | Status |
|---|---|
| `CLICKHOUSE_PASSWORD` available in n8n container | **Wired** — env passthrough in docker-compose.yml |
| `N8N_API_KEY` available in n8n container | **Wired** — env passthrough with empty-default guard |
| Metrics collector in canonical import list | **Wired** — `CANONICAL_WORKFLOWS` entry added |
| WP4-A DDL applied (`polytool.n8n_execution_metrics`) | Pre-existing; applied via initdb SQL `28_n8n_execution_metrics.sql` |

---

## Remaining Manual Operator Step

One step cannot be automated from the repo side:

1. Start the n8n container: `docker compose --profile ris-n8n up -d n8n`
2. Complete the n8n owner setup wizard at `http://localhost:5678/setup`
3. Generate an API key: n8n UI → Settings → API → Create API Key
4. Add the key to `.env`: `N8N_API_KEY=<generated_key>`
5. Restart the n8n container so the env var is injected: `docker compose --profile ris-n8n up -d n8n`
6. Run the importer (imports all three canonical workflows, collector imported but not activated):
   ```
   python infra/n8n/import_workflows.py --no-activate
   ```
7. Activate the metrics collector from the n8n UI after confirming env vars are present.

---

**Codex review tier:** Skip (infra config + import registry list — matches repo Codex policy exclusion).
