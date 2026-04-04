---
phase: quick-260404-jfz
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - Dockerfile
  - docker-compose.yml
  - .env.example
  - scripts/docker-start.sh
  - scripts/docker-run.sh
  - docs/dev_logs/2026-04-04_docker-full-stack.md
autonomous: true
requirements: []
must_haves:
  truths:
    - "docker compose up -d --build starts ClickHouse, Grafana, RIS scheduler, and pair bots without errors"
    - "docker compose run --rm polytool python -m polytool --help executes the polytool CLI inside the container"
    - "ris-scheduler service starts research-scheduler inside the universal image"
    - "pair-bot-paper and pair-bot-live build from root Dockerfile instead of Dockerfile.bot"
  artifacts:
    - path: "Dockerfile"
      provides: "Universal polytool image with all extras installed"
      contains: "pip install.*all,ris"
    - path: "docker-compose.yml"
      provides: "Full-stack compose with ris-scheduler and updated polytool service"
      contains: "ris-scheduler"
    - path: ".env.example"
      provides: "Environment template with RIS scheduler vars"
      contains: "RIS_"
    - path: "scripts/docker-start.sh"
      provides: "Convenience startup script"
    - path: "scripts/docker-run.sh"
      provides: "Convenience CLI run script"
    - path: "docs/dev_logs/2026-04-04_docker-full-stack.md"
      provides: "Dev log documenting the changes"
  key_links:
    - from: "docker-compose.yml"
      to: "Dockerfile"
      via: "build context for polytool, ris-scheduler, pair-bot-paper, pair-bot-live"
      pattern: "dockerfile: Dockerfile"
    - from: "docker-compose.yml"
      to: ".env"
      via: "env_file reference"
      pattern: "env_file"
---

<objective>
Unify PolyTool Docker infrastructure into a single universal image and full-stack
docker-compose.yml so that `docker compose up -d --build` starts the entire stack:
ClickHouse, Grafana, RIS scheduler, and pair bots.

Purpose: Eliminate partial containerization. One command brings up the full PolyTool
operational environment. ClickHouse and Grafana services already exist and only need
minor adjustments. The main work is creating a universal Dockerfile, adding the
ris-scheduler service, converting pair-bot services to the universal image, and
making the polytool service a general-purpose CLI runner.

Output: Updated Dockerfile, docker-compose.yml, .env.example, two convenience scripts,
and a dev log.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@Dockerfile (existing — python:3.11-slim, installs simtrader+studio only)
@Dockerfile.bot (existing — python:3.12-slim, installs live+simtrader, has ENTRYPOINT for crypto-pair-run)
@docker-compose.yml (existing — has clickhouse, grafana, api, migrate, polytool [studio], pair-bot-paper, pair-bot-live)
@.env.example (existing — has CH, Grafana, API, resolution, PnL, scan, live execution vars)
@pyproject.toml (extras: rag, mcp, simtrader, studio, dev, historical, historical-import, live, ris, all)

<interfaces>
<!-- pyproject.toml optional-dependencies that the Dockerfile must install -->
all = ["polytool[rag,mcp,simtrader,studio,dev,historical,historical-import,live]"]
ris = ["apscheduler>=3.10.0,<4.0"]
<!-- NOTE: "all" does NOT include "ris" — must install both ".[all,ris]" -->

<!-- Existing Dockerfile installs: simtrader, studio + ad-hoc pytest/numpy/chromadb -->
<!-- Existing Dockerfile.bot installs: live, simtrader -->

<!-- docker-compose.yml existing services -->
clickhouse: image clickhouse/clickhouse-server:latest, ports 8123/9000, volume clickhouse_data, healthcheck, network polytool
grafana: image grafana/grafana:11.4.0, port 3000, volume grafana_data, depends_on clickhouse healthy, network polytool
api: builds from services/api/Dockerfile, port 8000, depends_on clickhouse healthy
migrate: runs CH migrations from infra/clickhouse/initdb/
polytool: builds from root Dockerfile, container polytool-simtrader-studio, runs "simtrader studio", port 8765, mounts .:/workspace
pair-bot-paper: builds from Dockerfile.bot, profile pair-bot, restart "no"
pair-bot-live: builds from Dockerfile.bot, restart unless-stopped

<!-- RIS scheduler CLI command -->
python -m polytool research-scheduler start
<!-- (verify exact subcommand name — may be "scheduler-start" or "research-scheduler start") -->
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create universal Dockerfile and update docker-compose.yml</name>
  <files>Dockerfile, docker-compose.yml</files>
  <action>
**Dockerfile** — Rewrite the root Dockerfile to be the universal polytool image:
- Base: `python:3.11-slim` (keep current base)
- Install system deps: `apt-get update && apt-get install -y --no-install-recommends gcc libffi-dev curl && rm -rf /var/lib/apt/lists/*` (add curl for healthchecks)
- Create non-root user: `groupadd -r polytool && useradd -r -g polytool -m polytool`
- WORKDIR `/app`
- COPY `pyproject.toml` first for layer caching
- `pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir py-clob-client` (cached layer, same pattern as Dockerfile.bot)
- COPY full project: `COPY . .`
- `pip install --no-cache-dir ".[all,ris]"` — this installs ALL extras including rag, mcp, simtrader, studio, dev, historical, historical-import, live, AND ris (apscheduler). The "all" extra does NOT include ris, so both must be listed.
- `chown -R polytool:polytool /app`
- `USER polytool`
- No ENTRYPOINT or CMD — each compose service sets its own command
- EXPOSE nothing — compose handles port mapping

**docker-compose.yml** — Update the existing file. Preserve ALL existing services (clickhouse, grafana, api, migrate) exactly as they are. Modify three existing services and add one new service:

1. **polytool** service (UPDATE): Change from SimTrader Studio dedicated service to general CLI runner.
   - container_name: `polytool-cli`
   - Remove the hardcoded `command` for simtrader studio
   - Remove `ports` (CLI doesn't listen)
   - Add `profiles: ["cli"]` so it only starts when explicitly invoked via `docker compose run`
   - Keep `env_file: [.env]`
   - Volumes: `./artifacts:/app/artifacts`, `./config:/app/config:ro`, `./kb:/app/kb`, `./kill_switch.json:/app/kill_switch.json:ro` (mount artifacts read-write, config and kill_switch read-only, kb read-write for RAG)
   - Add `depends_on: clickhouse: condition: service_healthy`
   - Keep network `polytool`

2. **ris-scheduler** service (NEW):
   - `build: context: . ; dockerfile: Dockerfile`
   - container_name: `polytool-ris-scheduler`
   - env_file: [.env]
   - command: `["python", "-m", "polytool", "research-scheduler", "start"]`
   - restart: `unless-stopped`
   - volumes: `./kb:/app/kb`, `./artifacts:/app/artifacts`
   - depends_on: clickhouse healthy
   - network: polytool
   - No ports (scheduler is internal)

3. **pair-bot-paper** (UPDATE): Change `dockerfile: Dockerfile.bot` to `dockerfile: Dockerfile`. Keep everything else (command, volumes, profiles, restart). Update volume mount from `/app/artifacts` to match universal image WORKDIR (`/app/artifacts` — same, since universal image also uses /app). Add `env_file: [.env]` if not present. Remove `ENTRYPOINT` dependency — the compose `command` already specifies the full command.

4. **pair-bot-live** (UPDATE): Same dockerfile change as pair-bot-paper. Keep all other settings.

Do NOT modify: clickhouse, grafana, api, migrate services. They stay exactly as they are.
Do NOT remove Dockerfile.bot — keep it as a fallback. The pair-bot services just stop referencing it.
  </action>
  <verify>
    <automated>docker compose config --quiet 2>&1 && echo "compose config valid"</automated>
  </verify>
  <done>
- Dockerfile installs all extras (all + ris) on python:3.11-slim with non-root user
- docker-compose.yml has ris-scheduler service, updated polytool as CLI profile, pair-bot-* using root Dockerfile
- `docker compose config` validates without errors
  </done>
</task>

<task type="auto">
  <name>Task 2: Update .env.example, create convenience scripts, write dev log</name>
  <files>.env.example, scripts/docker-start.sh, scripts/docker-run.sh, docs/dev_logs/2026-04-04_docker-full-stack.md</files>
  <action>
**.env.example** — Append a new section after the existing "Optional tooling overrides" block:

```
# RIS (Research Intelligence System) Scheduler
# Uncomment to enable the research scheduler in Docker
# RIS_SCHEDULE_INTERVAL_HOURS=6
# RIS_MAX_CONCURRENT_JOBS=2
# RIS_LOG_LEVEL=INFO

# Discord notifications (optional)
# DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN
```

Do NOT modify any existing lines in .env.example. Only append.

**scripts/docker-start.sh** — New file. Convenience wrapper for bringing up the full stack:

```bash
#!/usr/bin/env bash
# Start the full PolyTool stack via Docker Compose.
# Usage: bash scripts/docker-start.sh [--with-bots]
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "ERROR: .env file not found. Copy .env.example to .env and fill in secrets first."
  exit 1
fi

PROFILES=""
if [[ "${1:-}" == "--with-bots" ]]; then
  PROFILES="--profile pair-bot"
  echo "Starting full stack with pair bots..."
else
  echo "Starting full stack (ClickHouse, Grafana, API, RIS scheduler)..."
  echo "  Add --with-bots to also start pair-bot services."
fi

docker compose $PROFILES up -d --build

echo ""
echo "Services:"
echo "  ClickHouse:  http://localhost:${CLICKHOUSE_HTTP_PORT:-8123}"
echo "  Grafana:     http://localhost:${GRAFANA_PORT:-3000}"
echo "  API:         http://localhost:${API_PORT:-8000}"
echo ""
echo "CLI usage:     docker compose run --rm polytool python -m polytool --help"
echo "Stop:          docker compose down"
echo ""
```

**scripts/docker-run.sh** — New file. Convenience wrapper for running polytool CLI commands inside the container:

```bash
#!/usr/bin/env bash
# Run a polytool CLI command inside Docker.
# Usage: bash scripts/docker-run.sh <command> [args...]
# Example: bash scripts/docker-run.sh wallet-scan --user @example_user
set -euo pipefail
cd "$(dirname "$0")/.."

if [ $# -eq 0 ]; then
  echo "Usage: bash scripts/docker-run.sh <polytool-command> [args...]"
  echo "Example: bash scripts/docker-run.sh research-health"
  echo "         bash scripts/docker-run.sh wallet-scan --user @example_user"
  exit 1
fi

docker compose run --rm polytool python -m polytool "$@"
```

Make both scripts executable (they should have `#!/usr/bin/env bash` shebang).

**docs/dev_logs/2026-04-04_docker-full-stack.md** — New dev log:

Title: Docker Full-Stack Containerization
Content should document:
- What changed: universal Dockerfile replaces per-service images, ris-scheduler added, polytool becomes CLI runner, pair-bots switch to universal image
- Why: single `docker compose up -d --build` brings up everything
- Services overview: list all services and their roles
- Scope guard: no Python source changes, no n8n, Chroma runs embedded
- Dockerfile.bot preserved as fallback but no longer referenced by compose
- Open items: verify `research-scheduler start` is the exact CLI subcommand, test full stack on fresh machine, consider .dockerignore for build speed
  </action>
  <verify>
    <automated>bash -c "test -f 'D:/Coding Projects/Polymarket/PolyTool/.env.example' && test -f 'D:/Coding Projects/Polymarket/PolyTool/scripts/docker-start.sh' && test -f 'D:/Coding Projects/Polymarket/PolyTool/scripts/docker-run.sh' && test -f 'D:/Coding Projects/Polymarket/PolyTool/docs/dev_logs/2026-04-04_docker-full-stack.md' && echo 'All files exist'"</automated>
  </verify>
  <done>
- .env.example has RIS scheduler and Discord webhook sections appended
- scripts/docker-start.sh exists with --with-bots flag support and .env check
- scripts/docker-run.sh exists as polytool CLI convenience wrapper
- Dev log documents all changes, rationale, and open items
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Host -> Container | Volumes mount host paths into containers; secrets via .env |
| Container -> ClickHouse | polytool, ris-scheduler, pair-bots connect to CH with password |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-quick-01 | I (Info Disclosure) | .env file | mitigate | .env.example uses placeholders only; .env is gitignored; CLICKHOUSE_PASSWORD uses :? required syntax in compose |
| T-quick-02 | E (Elevation) | Dockerfile USER | mitigate | Universal Dockerfile runs as non-root `polytool` user; no --privileged in compose |
| T-quick-03 | T (Tampering) | Volume mounts | accept | Config and kill_switch mounted read-only (:ro); artifacts and kb are read-write by design |
| T-quick-04 | S (Spoofing) | ClickHouse auth | mitigate | All services use CLICKHOUSE_PASSWORD env var with fail-fast :? syntax; no hardcoded fallback per CLAUDE.md rule |
</threat_model>

<verification>
After both tasks complete:
1. `docker compose config` validates the compose file without errors
2. All 6 new/modified files exist at their expected paths
3. Dockerfile installs `.[all,ris]` extras
4. docker-compose.yml includes ris-scheduler service
5. pair-bot-paper and pair-bot-live reference `Dockerfile` not `Dockerfile.bot`
6. polytool service has `profiles: ["cli"]` for on-demand invocation
</verification>

<success_criteria>
- `docker compose config` passes
- Universal Dockerfile installs all pyproject.toml extras
- ris-scheduler service defined and configured
- pair-bot services migrated to universal Dockerfile
- polytool service configured as CLI runner with profile
- .env.example documents all new environment variables
- Convenience scripts exist and are functional
- Dev log committed
- NO Python source code modified
- Dockerfile.bot preserved (not deleted)
</success_criteria>

<output>
After completion, create `.planning/quick/260404-jfz-polytool-docker-readiness-full-stack-con/260404-jfz-SUMMARY.md`
</output>
