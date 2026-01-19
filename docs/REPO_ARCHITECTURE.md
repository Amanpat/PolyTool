# PolyTool Repo Architecture Proposal

Goal: A future-proof monorepo that supports multiple Polymarket tools while keeping the MVP small.

## Proposed monorepo layout

```
PolyTool/
  apps/
    web/                   # Web UI (dashboard + reports)
  services/
    api/                   # Public API (FastAPI or Node)
    worker/                # Ingestion + detector runs
  packages/
    polymarket/            # Public API clients (Gamma, Data API, CLOB)
    detectors/             # Heuristic detector library
    data-model/            # DB models + migrations
    utils/                 # Shared helpers
  tools/
    cli/                   # CLI entrypoints (smoke script, backfill, export)
  infra/
    docker/                # Local docker-compose, DB, optional queue
  docs/                    # Specs and system docs
  .env.example
  README.md
```

## MVP subset (keep it small)

For the first tool (Reverse Engineer) you can ship with:
- `services/api` (identity resolution, ingestion trigger, read API)
- `packages/polymarket` (Gamma, Data API, CLOB clients)
- `packages/detectors` (heuristics + evidence output)
- `apps/web` (user search + overview + detector results)
- `tools/cli` (smoke script and backfill)
- `docs` (specs and runbooks)

## Data storage choices

MVP:
- SQLite or DuckDB for local-only ingestion and analysis.
- Store raw JSON plus normalized columns for key fields.

Scale-up path:
- Postgres for transactional reads and writes.
- Optional ClickHouse for heavy analytics (time-series + joins).

## Dependency boundaries

- `packages/polymarket` owns all public API integration and request throttling.
- `services/worker` does ingestion and detector runs; it depends on `packages/polymarket`
  and `packages/detectors` only.
- `services/api` serves read endpoints; it should not call Polymarket directly.
- `apps/web` consumes only `services/api`.

## Notes for future tools

- Add new tools as separate pages or subapps under `apps/`.
- Keep detector logic tool-agnostic so other tools can reuse it.
- Maintain a shared data model and ingestion cache to avoid refetching.
