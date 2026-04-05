---
phase: quick-260405-gef
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docker-compose.yml
  - docs/dev_logs/2026-04-05_docker_build_matrix_closeout.md
  - docs/CURRENT_STATE.md
  - .env.example
autonomous: true
requirements: []
must_haves:
  truths:
    - "docker compose up -d --build starts only infrastructure + default services (clickhouse, grafana, api, migrate, ris-scheduler) — no live trading bots"
    - "docker compose --profile pair-bot up -d --build adds pair-bot-paper and pair-bot-live"
    - "docker compose --profile ris-n8n up -d --build adds n8n"
    - "docker compose config validates cleanly for every profile combination"
    - "pair-bot-live is NOT in the default stack (requires explicit profile activation)"
  artifacts:
    - path: "docker-compose.yml"
      provides: "Fixed compose file with correct profile boundaries"
    - path: "docs/dev_logs/2026-04-05_docker_build_matrix_closeout.md"
      provides: "Build matrix documentation with exact commands and results"
  key_links:
    - from: "docker-compose.yml"
      to: "Dockerfile"
      via: "build context for polytool, ris-scheduler, pair-bot-paper, pair-bot-live"
    - from: "docker-compose.yml"
      to: "infra/n8n/Dockerfile"
      via: "build context for n8n service"
    - from: "docker-compose.yml"
      to: "services/api/Dockerfile"
      via: "build context for api service"
---

<objective>
Verify and fix every Docker Compose build/start path so all intended profiles build cleanly,
no unintended services start in the default stack, and a build matrix is documented.

Purpose: The compose file has a known safety issue (pair-bot-live in default stack without a
profile gate) and the full matrix has never been systematically verified across all paths.

Output: Fixed docker-compose.yml, build matrix dev log, updated CURRENT_STATE.md.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@docker-compose.yml
@Dockerfile
@services/api/Dockerfile
@infra/n8n/Dockerfile
@scripts/docker-start.sh
@.env.example
@docs/RIS_OPERATOR_GUIDE.md

<interfaces>
<!-- Key compose services and their profile assignments (current state) -->

Default stack (no profile required):
  - clickhouse (image: clickhouse/clickhouse-server:latest)
  - grafana (image: grafana/grafana:11.4.0, depends_on: clickhouse)
  - api (build: services/api/Dockerfile, depends_on: clickhouse)
  - migrate (image: clickhouse/clickhouse-server:latest, depends_on: clickhouse)
  - ris-scheduler (build: Dockerfile, depends_on: clickhouse)
  - pair-bot-live (build: Dockerfile) ← BUG: NO profile, live trading bot in default stack

Profile-gated:
  - polytool (profile: cli, build: Dockerfile)
  - pair-bot-paper (profile: pair-bot, build: Dockerfile)
  - n8n (profile: ris-n8n, build: infra/n8n/Dockerfile)

KNOWN BUG: pair-bot-live is MISSING a profiles: key. It starts on every
`docker compose up -d --build`. This is a live trading bot with --live --confirm CONFIRM.
Per CLAUDE.md human-approval rules, live capital deployment must not auto-start.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix pair-bot-live profile and verify compose config</name>
  <files>docker-compose.yml, .env.example</files>
  <action>
1. Fix the critical safety bug: add `profiles: ["pair-bot"]` to the `pair-bot-live` service
   in docker-compose.yml. This service runs `crypto-pair-run --live --confirm CONFIRM` and
   must NEVER be in the default stack. It should be gated behind the same `pair-bot` profile
   as `pair-bot-paper`, consistent with how `scripts/docker-start.sh --with-bots` activates
   the `pair-bot` profile.

2. Verify no other services are incorrectly placed. The expected default stack (no profile):
   - clickhouse, grafana, api, migrate, ris-scheduler
   The expected opt-in profiles:
   - cli: polytool
   - pair-bot: pair-bot-paper, pair-bot-live
   - ris-n8n: n8n

3. Run `docker compose config` (no profiles) and verify pair-bot-live is NOT listed in the
   resolved services. Then run with each profile and verify the expected services appear.

4. Check .env.example: if there is no mention of the pair-bot profile or its env vars, add
   a brief comment section noting the pair-bot profile exists and what it starts. This is
   informational only — pair-bot services use env_file: .env so they inherit existing vars.

5. Do NOT touch n8n configuration, RIS scheduler, or any strategy/business logic.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && docker compose config --services 2>&1 | sort</automated>
  </verify>
  <done>
- pair-bot-live has `profiles: ["pair-bot"]` in docker-compose.yml
- `docker compose config --services` (no profiles) lists exactly: api, clickhouse, grafana, migrate, ris-scheduler (NO pair-bot-live, NO pair-bot-paper, NO polytool, NO n8n)
- `docker compose --profile pair-bot config --services` includes pair-bot-paper AND pair-bot-live
- `docker compose --profile ris-n8n config --services` includes n8n
- `docker compose --profile cli config --services` includes polytool
  </done>
</task>

<task type="auto">
  <name>Task 2: Run full build matrix, fix failures, document results</name>
  <files>docker-compose.yml, Dockerfile, services/api/Dockerfile, infra/n8n/Dockerfile, docs/dev_logs/2026-04-05_docker_build_matrix_closeout.md, docs/CURRENT_STATE.md</files>
  <action>
Run each build path in sequence. For each, capture the exact command and outcome.
Fix any Docker/compose/build/startup failures encountered. After fixes, rerun until green.

**Build matrix to execute:**

Path 1 — Default stack:
```
docker compose up -d --build
docker compose ps
```
Expected services: clickhouse, grafana, api, migrate, ris-scheduler.
Verify healthchecks pass (clickhouse healthy, grafana healthy, api healthy).

Path 2 — With pair-bot profile:
```
docker compose --profile pair-bot up -d --build
docker compose --profile pair-bot ps
```
Expected: default stack + pair-bot-paper + pair-bot-live.
Note: pair-bot services may fail if no active crypto markets exist — that is expected
and NOT a build failure. Build/start success is what matters.

Path 3 — With ris-n8n profile:
```
docker compose --profile ris-n8n up -d --build
docker compose --profile ris-n8n ps
```
Expected: default stack + n8n.
Verify n8n healthcheck or curl http://localhost:5678/healthz returns ok.

Path 4 — With cli profile:
```
docker compose --profile cli run --rm polytool python -m polytool --help
```
Expected: CLI help output, exit 0.

Path 5 — Full combo (all profiles):
```
docker compose --profile pair-bot --profile ris-n8n --profile cli up -d --build
docker compose --profile pair-bot --profile ris-n8n --profile cli ps
```
Expected: all services running.

**After each path, tear down cleanly:**
```
docker compose --profile pair-bot --profile ris-n8n --profile cli down
```

**Fix rules:**
- Only fix Docker/compose/build/startup issues (Dockerfiles, compose config, mount paths,
  env wiring, build contexts, permissions).
- Do NOT fix strategy logic, API business logic, or workflow semantics.
- If a Dockerfile fails to build, fix the Dockerfile.
- If a service fails healthcheck due to missing env var, document the required env var.
- If a service exits because a CLI command does not exist or arguments are wrong, fix the
  command or document it as a known limitation.

**After all paths are green, create the dev log:**

Create `docs/dev_logs/2026-04-05_docker_build_matrix_closeout.md` with:
- Build matrix table: command | services started | result (PASS/FAIL) | notes
- Files changed and why
- Exact commands run with key output excerpts
- Required env vars for startup (CLICKHOUSE_PASSWORD is mandatory; others optional)
- Profile boundary documentation
- Open questions if any

**Update docs/CURRENT_STATE.md:**
Add a brief entry under the appropriate section noting:
- pair-bot-live profile fix (was in default stack, now requires --profile pair-bot)
- Build matrix verified date
- Which profiles are supported

**Run Python smoke test to confirm no regressions:**
```
python -m polytool --help
python -m pytest tests/ -x -q --tb=short
```
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && docker compose config --services 2>&1 | sort && docker compose --profile pair-bot --profile ris-n8n --profile cli config --services 2>&1 | sort && python -m polytool --help > /dev/null 2>&1 && echo "CLI OK"</automated>
  </verify>
  <done>
- All 5 build paths documented with PASS/FAIL in dev log
- Default stack starts without pair-bot-live (safety fix confirmed)
- Each profile path builds and starts its expected services
- Dev log exists at docs/dev_logs/2026-04-05_docker_build_matrix_closeout.md
- docs/CURRENT_STATE.md updated with build matrix verification record
- python -m polytool --help still works
- No strategy/business logic files were modified
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| compose profile gate | Profile boundary prevents live trading bots from starting in default stack |
| docker socket mount | n8n has docker.sock access (documented in ADR-0013, accepted risk) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-quick-01 | Elevation of Privilege | pair-bot-live in default stack | mitigate | Add `profiles: ["pair-bot"]` so live trading requires explicit `--profile pair-bot` activation |
| T-quick-02 | Tampering | docker.sock mount on n8n | accept | Documented in ADR-0013; n8n is opt-in via ris-n8n profile; only RIS commands are in workflow templates |
</threat_model>

<verification>
1. `docker compose config --services` (no profiles) must NOT include pair-bot-live or pair-bot-paper
2. `docker compose --profile pair-bot config --services` must include both pair-bot services
3. `docker compose --profile ris-n8n config --services` must include n8n
4. All builds complete without error
5. Dev log documents the full matrix
6. `python -m polytool --help` returns 0
</verification>

<success_criteria>
- pair-bot-live is behind the pair-bot profile (safety fix)
- Default `docker compose up -d --build` starts only: clickhouse, grafana, api, migrate, ris-scheduler
- Every supported profile path builds and starts cleanly
- Build matrix documented in dev log with exact commands and results
- CURRENT_STATE.md updated
- No Python test regressions
</success_criteria>

<output>
After completion, create `.planning/quick/260405-gef-docker-compose-build-matrix-verification/260405-gef-SUMMARY.md`
</output>
