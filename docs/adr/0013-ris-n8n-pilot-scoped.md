# ADR-0013: n8n as Scoped RIS-Only Pilot

**Date:** 2026-04-05
**Status:** Accepted

## Context

The repo is in Phase 0/1 per Roadmap V5. Gate 2 has NOT been passed (benchmark
corpus is below minimum qualifying tape count; WAIT_FOR_CRYPTO policy is in effect).
The primary workflow is CLI-first; no custom frontend or broad automation is justified
pre-profit.

Master Roadmap V5 defers n8n to Phase 3 as part of a broad automation and orchestration
layer. Phase 3 was conceived as the post-profit expansion phase after live capital
strategies are validated and running.

Two forces create pressure to consider n8n earlier than Phase 3:

1. **RIS operational friction.** The Research Intelligence System (RIS) has 8 background
   ingestion jobs (academic_ingest, reddit_polymarket, reddit_others, blog_ingest,
   youtube_ingest, github_ingest, freshness_refresh, weekly_digest). These are currently
   run by an APScheduler-based service (`ris-scheduler` container). The operator has no
   visibility dashboard, no per-job execution log in a UI, and no webhook-triggered ad-hoc
   ingestion path.

2. **Authority drift.** Bringing n8n forward for ALL of Phase 3 automation would be
   premature. The risk is scope creep: once n8n is installed, the temptation exists to
   wire strategy logic, gate logic, or risk policy through it — areas that are explicitly
   out of scope until Phase 3.

This ADR resolves the tension by explicitly scoping n8n to a narrow RIS pilot. It does
NOT move the repo to Phase 3. It does NOT unlock broad automation. The repo remains
Phase 0/1, CLI-first.

## Decision

n8n is approved as a **scoped pilot** for RIS CLI job orchestration only.

### Allowed scope (RIS only)

The following CLI surfaces may be called from n8n workflows:

- `python -m polytool research-acquire ...`
- `python -m polytool research-ingest ...`
- `python -m polytool research-health`
- `python -m polytool research-scheduler status`
- `python -m polytool research-scheduler run-job <job_id>`
- `python -m polytool research-stats summary`

### Hard out-of-scope boundaries

n8n workflows MUST NOT orchestrate:

- Strategy logic (crypto-pair-run, market-maker, any strategy entrypoint)
- Gate logic (close-benchmark-v1, gate sweeps, benchmark-manifest)
- Risk policy (kill_switch, risk_manager, live executor)
- Live capital operations (any --live flag, CLOB order placement)
- FastAPI endpoints (no n8n → polytool API routing)
- SimTrader replay or shadow runs

Violating these boundaries requires a new ADR and explicit human approval.

### Deployment model

- n8n is added to `docker-compose.yml` under compose profile `ris-n8n`.
- Operator starts n8n with: `bash scripts/docker-start.sh --with-n8n`
- The n8n service is NOT in the default compose stack.
- The default stack always starts the `ris-scheduler` (APScheduler) service.

### Scheduler mutual exclusion

APScheduler (`ris-scheduler` container) and n8n are mutually exclusive schedulers for
RIS background jobs. They serve the same function via different implementations.

**Mutual exclusion is operator responsibility**, not a code-level lock. The mechanism is:

1. `ris-scheduler` has no compose profile — it starts in the default stack.
2. n8n is behind the `ris-n8n` profile — opt-in only.
3. If an operator starts `--with-n8n` while `ris-scheduler` is also running, double-
   scheduling occurs (each RIS job runs twice per period). This is an operator error;
   the system does not auto-prevent it.

To switch from APScheduler to n8n:
```bash
docker compose stop ris-scheduler
bash scripts/docker-start.sh --with-n8n
```

An env var `RIS_SCHEDULER_BACKEND` (values: `apscheduler` | `n8n`) documents the active
choice in `.env`. It is informational only — no code reads this variable.

### Image and versioning

- Custom image: `polytool-n8n:1.88.0` (built from `infra/n8n/Dockerfile`)
- Base: `n8nio/n8n:1.88.0` + `docker-cli` (alpine `apk add docker-cli`)
- Pinned base tag: MUST NOT be `latest`.
- To upgrade: update the base tag in `infra/n8n/Dockerfile`, rebuild (`docker compose --profile ris-n8n build n8n`), commit.
- Runtime pattern: **docker-beside-docker** -- n8n mounts `/var/run/docker.sock` and
  routes all Execute Command nodes through `docker exec polytool-ris-scheduler python -m polytool ...`

### Workflow templates

Eleven version-controlled workflow JSON templates are provided in `infra/n8n/workflows/`:

| File | CLI command | Trigger |
|------|-------------|---------|
| `ris_health_check.json` | `research-health` | Manual + cron (every 6h) |
| `ris_scheduler_status.json` | `research-scheduler status` | Manual |
| `ris_manual_acquire.json` | `research-acquire --url ...` | Webhook (POST) |
| `ris_academic_ingest.json` | `research-scheduler run-job academic_ingest` | Manual + cron (every 12h) |
| `ris_blog_ingest.json` | `research-scheduler run-job blog_ingest` | Manual + cron (every 4h) |
| `ris_reddit_polymarket.json` | `research-scheduler run-job reddit_polymarket` | Manual + cron (every 6h) |
| `ris_reddit_others.json` | `research-scheduler run-job reddit_others` | Manual + cron (daily 03:00) |
| `ris_youtube_ingest.json` | `research-scheduler run-job youtube_ingest` | Manual + cron (Mon 04:00) |
| `ris_github_ingest.json` | `research-scheduler run-job github_ingest` | Manual + cron (Wed 04:00) |
| `ris_freshness_refresh.json` | `research-scheduler run-job freshness_refresh` | Manual + cron (Sun 02:00) |
| `ris_weekly_digest.json` | `research-scheduler run-job weekly_digest` | Manual + cron (Sun 08:00) |

All templates ship with `"active": false`. Operator activates manually from the n8n UI
after import and verification.

Import all 11 with: `bash infra/n8n/import-workflows.sh [container_name]`

## Consequences

### Positive

- Operators gain a visual execution log and UI for RIS ingestion jobs.
- Webhook-triggered ad-hoc URL ingestion becomes possible without CLI access.
- Workflow templates are version-controlled and importable via the import helper script.
- Scope boundaries are explicitly documented, reducing drift risk.

### Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Operator runs both APScheduler and n8n simultaneously | ADR and operator guide document the mutual exclusion procedure. docker-start.sh prints a warning when --with-n8n is used. |
| Workflow scope creep (strategy/gate logic added to n8n) | This ADR documents hard boundaries. Any violation requires a new ADR and human approval. |
| n8n image update pulling in breaking changes | Tag is pinned. Updates require explicit commit. |
| Webhook URL treated as a non-secret | Operator docs note that the webhook URL path contains an n8n-generated token and must be treated as a secret. |
| Docker socket mount grants n8n full Docker daemon access | The socket mount (`/var/run/docker.sock`) allows `docker exec` into any running container, not just `polytool-ris-scheduler`. This is the standard docker-beside-docker tradeoff. Accepted because: (a) n8n runs on the local/trusted network only (not internet-exposed), (b) workflow scope is enforced by ADR boundaries and code review, (c) alternative (installing Python+PolyTool into the n8n image) couples release cycles and bloats the image. On Docker Desktop/WSL2, `group_add: ["0"]` is required because the socket is owned by root:root. On production Linux, use `group_add: ["<docker-gid>"]` where docker-gid matches the host docker group. |

### What this ADR does NOT do

- Does NOT move the repo to Phase 3 automation.
- Does NOT activate n8n workflows by default.
- Does NOT remove APScheduler or the ris-scheduler service.
- Does NOT grant n8n access to strategy, gate, risk, or live capital surfaces.
- Does NOT change Gate 2 pass conditions or benchmark policies.

## Alternatives Rejected

1. **Use n8n for all Phase 3 automation now.**
   Rejected: Gate 2 not passed. No validated strategies in live capital. Phase 3 scope
   is premature and would introduce scope creep risk.

2. **Keep APScheduler only, improve operator visibility via Grafana.**
   Rejected: APScheduler has no visual execution log. Grafana dashboards for RIS are
   not implemented (deferred per PLANNED items). n8n provides immediate visibility at
   lower cost than building Grafana panels.

3. **Webhook-only n8n (no cron triggers).**
   Rejected: cron triggers for research-health checks are the core value. Webhook-only
   misses the primary use case.
