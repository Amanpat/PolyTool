---
phase: quick-260405-jle
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - Dockerfile
  - Dockerfile.bot
  - docker-compose.yml
  - docs/dev_logs/2026-04-05_docker_image_slimming.md
autonomous: true
requirements: [docker-slim]

must_haves:
  truths:
    - "Root Dockerfile uses multi-stage build: gcc/libffi-dev exist only in builder stage, not in runtime image"
    - "pair-bot-paper and pair-bot-live compose services build from Dockerfile.bot with [live,simtrader] extras instead of the full [all,ris] root image"
    - "Dockerfile.bot is modernized with BuildKit header, cache mounts, selective COPY, python:3.11-slim, no COPY . ."
    - "All compose services still build and start correctly (docker compose config validates)"
    - "Profile gating unchanged: pair-bot services still require --profile pair-bot"
  artifacts:
    - path: "Dockerfile"
      provides: "Multi-stage root image (builder + runtime)"
      contains: "FROM python:3.11-slim AS builder"
    - path: "Dockerfile.bot"
      provides: "Lean pair-bot image with only [live,simtrader] deps"
      contains: "FROM python:3.11-slim"
    - path: "docker-compose.yml"
      provides: "pair-bot services pointed to Dockerfile.bot"
      contains: "dockerfile: Dockerfile.bot"
    - path: "docs/dev_logs/2026-04-05_docker_image_slimming.md"
      provides: "Dev log with before/after analysis"
  key_links:
    - from: "docker-compose.yml"
      to: "Dockerfile.bot"
      via: "build.dockerfile for pair-bot-paper and pair-bot-live"
      pattern: "dockerfile: Dockerfile.bot"
    - from: "docker-compose.yml"
      to: "Dockerfile"
      via: "build.dockerfile for polytool, ris-scheduler"
      pattern: "dockerfile: Dockerfile"
---

<objective>
Slim active Docker images and reduce duplicate image churn by: (1) converting the root
Dockerfile to multi-stage so build tools (gcc, libffi-dev) are excluded from runtime
images, (2) modernizing Dockerfile.bot and pointing pair-bot compose services to it so
they install only [live,simtrader] deps instead of the full [all,ris] stack, and
(3) documenting everything in a dev log.

Purpose: The root image currently carries gcc/libffi-dev into every runtime container,
and pair-bot services install ~15 unnecessary packages (sentence-transformers, chromadb,
duckdb, apscheduler, pytest, etc.) they never use. Fixing both meaningfully reduces
image size and build time for pair-bot rebuilds.

Output: Updated Dockerfile (multi-stage), modernized Dockerfile.bot, updated
docker-compose.yml (pair-bot build targets), dev log.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@docker-compose.yml
@Dockerfile
@Dockerfile.bot
@services/api/Dockerfile
@.dockerignore
@pyproject.toml (lines 1-65 for extras definitions)
@docs/dev_logs/2026-04-05_docker_perf_hygiene.md (prior Docker hygiene work, same day)
@docs/dev_logs/2026-04-05_docker_build_matrix_closeout.md (build matrix baseline)

<interfaces>
<!-- Key understanding for executor: current Dockerfile structure and compose service mapping -->

Current compose service -> Dockerfile mapping:
  api           -> services/api/Dockerfile   (already lean, DO NOT TOUCH)
  polytool      -> Dockerfile                (root, profile: cli)
  ris-scheduler -> Dockerfile                (root, default stack)
  pair-bot-paper -> Dockerfile               (root, profile: pair-bot) -- CHANGE TO Dockerfile.bot
  pair-bot-live  -> Dockerfile               (root, profile: pair-bot) -- CHANGE TO Dockerfile.bot
  n8n           -> infra/n8n/Dockerfile       (already minimal, DO NOT TOUCH)
  clickhouse    -> pre-built image            (DO NOT TOUCH)
  grafana       -> pre-built image            (DO NOT TOUCH)
  migrate       -> pre-built image            (DO NOT TOUCH)

pyproject.toml extras relevant to pair-bot:
  [live]       = py-clob-client>=0.17
  [simtrader]  = websocket-client>=1.6
  Base deps    = requests, clickhouse-connect, jsonschema

pyproject.toml extras in [all,ris] NOT needed by pair-bot:
  [rag]        = sentence-transformers, chromadb          (HEAVY -- ~500MB+)
  [mcp]        = mcp
  [studio]     = fastapi, uvicorn
  [dev]        = pytest, pytest-cov
  [historical] = duckdb
  [historical-import] = pyarrow
  [ris]        = apscheduler
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Multi-stage root Dockerfile + modernize Dockerfile.bot</name>
  <files>Dockerfile, Dockerfile.bot</files>
  <action>
**Root Dockerfile -- convert to multi-stage build:**

Rewrite `Dockerfile` with two stages:

```
Stage 1 "builder" (FROM python:3.11-slim AS builder):
  - Install gcc, libffi-dev (build tools for C extensions)
  - COPY pyproject.toml
  - pip install ".[all,ris]" (with BuildKit cache mount)
  - COPY source dirs (polytool/, packages/, tools/, services/)
  - pip install --no-deps ".[all,ris]" (metadata/entrypoints)

Stage 2 "runtime" (FROM python:3.11-slim):
  - Install ONLY curl (for healthchecks, no gcc/libffi-dev)
  - COPY --from=builder /usr/local/lib/python3.11/site-packages
  - COPY --from=builder /usr/local/bin (for entry point scripts like uvicorn, polytool)
  - COPY source dirs (polytool/, packages/, tools/, services/)
  - Create polytool user, chown, USER polytool
```

Keep the `# syntax=docker/dockerfile:1` header. Keep BuildKit cache mounts on
the builder stage pip install steps. The runtime stage does NOT need cache mounts
because it only copies pre-built artifacts.

Keep `ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1`
in the runtime stage.

Do NOT add ENTRYPOINT or CMD (compose services set their own).

**Dockerfile.bot -- modernize for pair-bot services:**

Rewrite `Dockerfile.bot` as a lean, modern Dockerfile:

```
# syntax=docker/dockerfile:1
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends gcc libffi-dev

WORKDIR /app
COPY pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && pip install ".[live,simtrader]"

COPY polytool/ ./polytool/
COPY packages/ ./packages/
COPY tools/ ./tools/

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-deps ".[live,simtrader]"

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY polytool/ ./polytool/
COPY packages/ ./packages/
COPY tools/ ./tools/

RUN groupadd -r botuser && useradd -r -g botuser -m botuser
RUN chown -R botuser:botuser /app
USER botuser
```

Key differences from old Dockerfile.bot:
  - Python 3.11-slim (matches root, was 3.12)
  - Multi-stage (gcc only in builder)
  - BuildKit header + cache mounts
  - Selective COPY (not COPY . .)
  - Installs ONLY [live,simtrader] extras (py-clob-client + websocket-client + base deps)
  - NO ENTRYPOINT/CMD (compose services set command)
  - Does NOT copy services/ (pair-bot does not need the API service code)

Note: The old Dockerfile.bot had `ENTRYPOINT ["python", "-m", "polytool", "crypto-pair-run"]`
and default CMD args. Remove these -- the compose services already specify their full
command arrays. Having no ENTRYPOINT/CMD keeps parity with the root Dockerfile pattern
and avoids confusion between compose command and Dockerfile ENTRYPOINT.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && docker compose config --quiet 2>&1 && echo "COMPOSE_CONFIG: PASS" || echo "COMPOSE_CONFIG: FAIL"</automated>
  </verify>
  <done>
  - Root Dockerfile has two stages: builder (with gcc/libffi-dev) and runtime (without)
  - Dockerfile.bot has two stages with only [live,simtrader] deps
  - Both use BuildKit header and cache mounts
  - Neither has COPY . . (selective COPY only)
  - Python version aligned at 3.11-slim across both
  </done>
</task>

<task type="auto">
  <name>Task 2: Point pair-bot compose services to Dockerfile.bot + verify</name>
  <files>docker-compose.yml, docs/dev_logs/2026-04-05_docker_image_slimming.md</files>
  <action>
**docker-compose.yml changes:**

Update the `pair-bot-paper` and `pair-bot-live` service definitions to build from
`Dockerfile.bot` instead of `Dockerfile`. Change only the `dockerfile:` line under
`build:` for each.

Before (both services):
```yaml
    build:
      context: .
      dockerfile: Dockerfile
```

After (both services):
```yaml
    build:
      context: .
      dockerfile: Dockerfile.bot
```

Do NOT change anything else in these service definitions: profiles, env_file, command,
volumes, restart, container_name all stay the same. Profile gating (`profiles: ["pair-bot"]`)
must remain intact.

**Verification steps (run all):**

1. `docker compose config --quiet` -- validates YAML parses correctly
2. Confirm pair-bot services now reference Dockerfile.bot in config output:
   `docker compose config | grep -A3 "pair-bot-paper" | grep dockerfile`
   Should show `Dockerfile.bot`
3. If Docker Desktop is available:
   - `DOCKER_BUILDKIT=1 docker compose build polytool` -- root image multi-stage build
   - `DOCKER_BUILDKIT=1 docker compose build pair-bot-paper` -- bot image build
   - `docker images | grep polytool` -- check image sizes
   - `docker compose up -d --build` -- default stack (should NOT start pair-bot)
   - `docker compose ps` -- verify healthy
   - `docker compose down`
4. `python -m polytool --help` -- Python regression check (no Python changes)

**Dev log:**

Create `docs/dev_logs/2026-04-05_docker_image_slimming.md` with:

- Date, task ID (quick-260405-jle), branch
- Summary: what was done and why
- Before/after table:
  | Service | Before (Dockerfile) | Before (extras) | After (Dockerfile) | After (extras) |
  | polytool, ris-scheduler | Dockerfile (single-stage) | [all,ris] | Dockerfile (multi-stage) | [all,ris] |
  | pair-bot-paper/live | Dockerfile (single-stage) | [all,ris] | Dockerfile.bot (multi-stage) | [live,simtrader] |
- What multi-stage removes from runtime: gcc (~100MB), libffi-dev (~5MB)
- What pair-bot image no longer installs: sentence-transformers, chromadb, duckdb, pyarrow, apscheduler, pytest, mcp, fastapi, uvicorn (estimated ~500MB+ of unnecessary deps)
- Build matrix results (whatever was verifiable)
- Files changed table
- Codex review tier: Skip (Dockerfile and compose changes only)
- Note: services/api/Dockerfile and infra/n8n/Dockerfile were NOT changed (already appropriately scoped)
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && docker compose config --quiet 2>&1 && docker compose config 2>/dev/null | grep -c "Dockerfile.bot" | xargs -I{} test {} -ge 2 && echo "BOT_DOCKERFILE_REFS: PASS (>=2)" || echo "BOT_DOCKERFILE_REFS: CHECK MANUALLY"</automated>
  </verify>
  <done>
  - pair-bot-paper and pair-bot-live build from Dockerfile.bot in compose
  - docker compose config validates without errors
  - Profile gating intact (pair-bot services still require --profile pair-bot)
  - Dev log written at docs/dev_logs/2026-04-05_docker_image_slimming.md
  - If Docker available: images build and services start correctly
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Build context -> image | .dockerignore gates what enters build context (unchanged from prior task) |
| Builder stage -> runtime stage | Only /usr/local/lib and /usr/local/bin copied; no build tools leak |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-quick-01 | Tampering | COPY --from=builder | accept | Standard Docker multi-stage pattern; builder is local, not external. No supply-chain risk beyond base image. |
| T-quick-02 | Information Disclosure | Dockerfile.bot extras | mitigate | Dockerfile.bot installs only [live,simtrader] -- py-clob-client is required for trading. Secrets still come from env_file, not baked into image. |
| T-quick-03 | Elevation of Privilege | Runtime user | mitigate | Both Dockerfiles create non-root users (polytool / botuser) and run as non-root via USER directive. |
</threat_model>

<verification>
1. `docker compose config --quiet` exits 0
2. `docker compose config` shows pair-bot-paper and pair-bot-live using Dockerfile.bot
3. Root Dockerfile has `FROM python:3.11-slim AS builder` and a second `FROM python:3.11-slim` (runtime)
4. Dockerfile.bot has `FROM python:3.11-slim AS builder` and installs `".[live,simtrader]"` (not `[all,ris]`)
5. Neither Dockerfile contains `COPY . .`
6. Profile gating: pair-bot services still have `profiles: ["pair-bot"]`
7. `python -m polytool --help` still works (no Python changes)
8. If Docker available: `docker compose up -d --build` starts default stack healthy
</verification>

<success_criteria>
- Root Dockerfile is multi-stage: build tools (gcc, libffi-dev) only in builder, not in runtime image
- Dockerfile.bot is modernized: multi-stage, python:3.11-slim, [live,simtrader] only, BuildKit, selective COPY
- pair-bot compose services build from Dockerfile.bot
- All other compose services unchanged
- docker compose config validates
- Dev log written
- No Python business logic changes
</success_criteria>

<output>
After completion, create `.planning/quick/260405-jle-docker-image-slimming-multi-stage-builds/260405-jle-SUMMARY.md`
</output>
