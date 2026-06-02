---
tags: [decision]
date: 2026-04-09
status: accepted
---
# Decision — RIS n8n Pilot Scope

## Context
The RIS pipeline needed webhook-triggered ingestion and structured Discord alerting. Full n8n orchestration (replacing APScheduler project-wide) is a Phase 3 deliverable. ADR 0013 defined a scoped pilot boundary.

## Decision
Ship a scoped n8n sidecar for RIS ingestion workflows only. Keep APScheduler as the project-wide default scheduler.

Key boundaries:
- **Scope:** RIS health checks, ingestion webhooks, pipeline error alerts, daily summary. Nothing else.
- **Canonical workflow home:** `infra/n8n/workflows/` (migrated from `workflows/n8n/` on 2026-04-09)
- **Canonical import command:** `python infra/n8n/import_workflows.py`
- **Activation:** opt-in via `docker compose --profile ris-n8n up -d n8n`
- **Scheduling default:** APScheduler. n8n schedule triggers are disabled in committed workflow JSON.
- **Discord alerting:** n8n webhook nodes send structured embeds (separate path from `packages/polymarket/notifications/discord.py`)

## Why infra/n8n/workflows/ (not workflows/n8n/)
The original `workflows/n8n/` location mixed pilot templates with infrastructure config. The migration to `infra/n8n/workflows/` aligns with the repo convention that infrastructure lives under `infra/`. Legacy files (11 pilot templates, 7 multi-workflow rebuild artifacts) were deleted. `workflows/n8n/` now contains a stub README pointing to the canonical location.

## Alternatives Considered
- Broad n8n replacing APScheduler now: premature, Phase 3 deliverable
- n8n owning scheduling: disabled in committed JSON to avoid double-scheduling with APScheduler
- Keeping workflows in workflows/n8n/: creates confusion about what is infrastructure vs. code

## Impact
- Operators use `python infra/n8n/import_workflows.py` for all workflow management
- APScheduler jobs remain the default recurring execution path
- n8n adds webhook-triggered and Discord-alerting capabilities that APScheduler cannot provide
- Phase 3 can expand n8n scope without retroactive migration

See [[RIS]], [[Phase-3-Hybrid-RAG-Kalshi-n8n]], `docs/adr/0013-ris-n8n-pilot-scoped.md`
