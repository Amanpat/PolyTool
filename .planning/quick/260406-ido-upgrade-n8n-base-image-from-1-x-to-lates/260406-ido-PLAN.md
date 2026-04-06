---
phase: quick-260406-ido
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - infra/n8n/Dockerfile
  - docker-compose.yml
  - docs/adr/0013-ris-n8n-pilot-scoped.md
  - docs/CURRENT_STATE.md
  - docs/RIS_OPERATOR_GUIDE.md
  - docs/dev_logs/2026-04-06_n8n_2x_instance_mcp_upgrade.md
autonomous: false
requirements: []
must_haves:
  truths:
    - "n8n container runs a 2.x Docker image tag (not 1.x, not floating latest)"
    - "Custom polytool-n8n image builds successfully with docker-cli installed"
    - "n8n container starts and healthz returns {status: ok}"
    - "docker-cli works inside the n8n container (docker exec bridge pattern preserved)"
    - "11 existing workflow templates still import successfully"
    - "All docs (ADR-0013, CURRENT_STATE, RIS_OPERATOR_GUIDE) reflect the 2.x version and MCP capability"
  artifacts:
    - path: "infra/n8n/Dockerfile"
      provides: "n8n 2.x base image with docker-cli"
      contains: "FROM n8nio/n8n:2."
    - path: "docs/dev_logs/2026-04-06_n8n_2x_instance_mcp_upgrade.md"
      provides: "Dev log documenting the 2.x migration"
      min_lines: 50
  key_links:
    - from: "infra/n8n/Dockerfile"
      to: "docker-compose.yml n8n service"
      via: "build context ./infra/n8n"
      pattern: "build.*context.*infra/n8n"
    - from: "docker-compose.yml"
      to: "n8n 2.x MCP environment"
      via: "N8N_MCP_BEARER_TOKEN env var"
      pattern: "N8N_MCP_BEARER_TOKEN"
---

<objective>
Upgrade the pinned n8n Docker base image from 1.123.28 (latest 1.x) to the latest
published 2.x Docker image tag to unlock instance-level MCP support.

Purpose: n8n 2.x provides instance-level MCP and workflow build/edit MCP tooling
(available from v2.13+). Claude Code can connect via HTTP to /mcp-server/http with
bearer token auth. The previous 1.x->1.123.28 bump (quick-260405-vbn) explicitly
deferred 2.x; this task now explicitly authorizes the 2.x migration.

Output: Working n8n 2.x container with docker-cli, updated docs, dev log.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@docker-compose.yml
@infra/n8n/Dockerfile
@docs/adr/0013-ris-n8n-pilot-scoped.md
@docs/RIS_OPERATOR_GUIDE.md
@docs/dev_logs/2026-04-05_n8n_version_bump.md

<interfaces>
<!-- Current Dockerfile (the primary file to change): -->
```dockerfile
# infra/n8n/Dockerfile
FROM n8nio/n8n:1.123.28
USER root
RUN wget -q -O /tmp/docker.tgz https://download.docker.com/linux/static/stable/x86_64/docker-29.3.1.tgz \
    && tar -xz -f /tmp/docker.tgz -C /tmp \
    && mv /tmp/docker/docker /usr/local/bin/docker \
    && chmod +x /usr/local/bin/docker \
    && rm -rf /tmp/docker /tmp/docker.tgz
USER node
```

<!-- docker-compose.yml n8n service (lines 186-215): -->
```yaml
n8n:
  build:
    context: ./infra/n8n
    dockerfile: Dockerfile
  image: polytool-n8n:latest
  container_name: polytool-n8n
  profiles:
    - ris-n8n
  ports:
    - "${N8N_PORT:-5678}:5678"
  environment:
    - N8N_BASIC_AUTH_ACTIVE=true
    - N8N_BASIC_AUTH_USER=${N8N_BASIC_AUTH_USER:-admin}
    - N8N_BASIC_AUTH_PASSWORD=${N8N_BASIC_AUTH_PASSWORD:-changeme}
    - N8N_ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY:-changeme_32chars_min_replace_this}
    - GENERIC_TIMEZONE=${GENERIC_TIMEZONE:-UTC}
    - TZ=${GENERIC_TIMEZONE:-UTC}
    - N8N_RUNNERS_ENABLED=true
    - N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true
    - N8N_MCP_BEARER_TOKEN=${N8N_MCP_BEARER_TOKEN:-replace_with_mcp_bearer_token}
    - POLYTOOL_HOST=http://host.docker.internal:${MCP_PORT:-8001}
    - N8N_EXEC_CONTAINER=${N8N_EXEC_CONTAINER:-polytool-ris-scheduler}
  group_add:
    - "0"
  volumes:
    - n8n_data:/home/node/.n8n
    - /var/run/docker.sock:/var/run/docker.sock
  networks:
    - polytool
  restart: unless-stopped
```

<!-- ADR-0013 version references (lines 94-99): -->
```
- Custom image: `polytool-n8n:1.123.28` (built from `infra/n8n/Dockerfile`)
- Base: `n8nio/n8n:1.123.28` + `docker-cli` (alpine `apk add docker-cli`)
- Pinned base tag: MUST NOT be `latest`.
- To upgrade: update the base tag in `infra/n8n/Dockerfile`, rebuild, commit.
```

<!-- CURRENT_STATE.md n8n version references (lines 1510-1511, 1544-1549): -->
```
- Custom n8n image: `polytool-n8n:1.123.28` ...
- Pinned n8n base image updated from `n8nio/n8n:1.88.0` to `n8nio/n8n:1.123.28` ...
```

<!-- RIS_OPERATOR_GUIDE.md MCP section (lines 599-628): -->
```
The polytool MCP server uses **stdio transport only** (not HTTP). It is designed for
Claude Desktop integration via a stdio pipe -- not for HTTP access from n8n or other
network-connected services.
...
**N8N_MCP_BEARER_TOKEN** in `.env.example` is not operative. HTTP transport for MCP is
not implemented.
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Discover latest 2.x tag, update Dockerfile and docker-compose.yml</name>
  <files>infra/n8n/Dockerfile, docker-compose.yml</files>
  <action>
1. Query Docker Hub for the latest published n8n 2.x tag. Use one of:
   - `curl -s "https://hub.docker.com/v2/repositories/n8nio/n8n/tags/?page_size=25&ordering=last_updated" | python3 -c "import json,sys; tags=json.load(sys.stdin)['results']; [print(t['name'],t['last_updated']) for t in tags if t['name'].startswith('2.')]"`
   - Or check GitHub releases: `gh api repos/n8n-io/n8n/releases --paginate -q '.[] | select(.tag_name | startswith("n8n@2.")) | [.tag_name, .prerelease, .published_at] | @tsv' | head -10`
   Record the exact tag (e.g., `2.15.1`) and its publication date. Do NOT use `latest` or any 1.x tag.
   If the latest published tag is marked prerelease=True on GitHub, use the latest NON-prerelease 2.x tag instead.

2. Update `infra/n8n/Dockerfile`:
   - Change `FROM n8nio/n8n:1.123.28` to `FROM n8nio/n8n:<chosen_2x_tag>`.
   - Keep the Docker static binary install approach for docker-cli (DHI images lack apk).
     The 2.x images may also be DHI-based. If `wget` is missing, try `curl` as fallback.
     The existing pattern (wget + tar + mv) should still work if wget is present.
   - Keep `USER root` / `USER node` bracketing.
   - Update the comment at the top to say `n8nio/n8n:<chosen_2x_tag>` and note "2.x for instance-level MCP".

3. Check docker-compose.yml n8n service environment:
   - `N8N_BASIC_AUTH_ACTIVE` / `N8N_BASIC_AUTH_USER` / `N8N_BASIC_AUTH_PASSWORD`:
     n8n 2.x may have changed auth config. If these env vars are deprecated in 2.x,
     replace with the 2.x equivalent. Check n8n 2.x migration notes. If no change
     needed, leave as-is.
   - Ensure `N8N_MCP_BEARER_TOKEN` is still passed (this becomes operative in 2.x for
     /mcp-server/http bearer auth).
   - If n8n 2.x requires new env vars for MCP (e.g., enabling MCP server), add them.
   - `N8N_RUNNERS_ENABLED=true` and `N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true`:
     verify these still apply in 2.x. If renamed, update.

4. Run `docker compose config --quiet` to validate YAML syntax.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && rtk docker compose config --quiet && echo "compose config: OK" && grep -E "FROM n8nio/n8n:2\." infra/n8n/Dockerfile && echo "Dockerfile: 2.x tag confirmed"</automated>
  </verify>
  <done>
- infra/n8n/Dockerfile FROM line references a specific 2.x tag (not 1.x, not latest)
- docker-compose.yml passes syntactic validation
- All n8n environment variables are compatible with the chosen 2.x version
  </done>
</task>

<task type="auto">
  <name>Task 2: Build, start, verify n8n 2.x container end-to-end</name>
  <files>infra/n8n/Dockerfile</files>
  <action>
1. Build the custom image:
   `docker compose --profile ris-n8n build n8n`
   If the build fails (e.g., wget missing in 2.x DHI, different base OS), fix the
   Dockerfile. Possible fixes:
   - If wget is missing: use `curl -fsSL` instead.
   - If tar is missing: use busybox tar or install tar.
   - If the USER is different in 2.x: adjust USER lines.

2. Start the container:
   `docker compose --profile ris-n8n up -d n8n`

3. Verify container is running:
   `docker compose --profile ris-n8n ps`
   Confirm status is "Up" and port 5678 is mapped.

4. Health check:
   `curl -s http://localhost:5678/healthz`
   Expected: `{"status":"ok"}`

5. Verify docker-cli inside container:
   `docker exec polytool-n8n docker --version`
   Expected: Docker version 29.3.1 or similar.

6. Test workflow import (if container is running and workflows exist):
   `bash infra/n8n/import-workflows.sh`
   Expected: 11 succeeded, 0 failed.
   If import fails due to 2.x schema changes (e.g., workflow JSON format changes),
   note the specific error but do NOT modify workflow JSON semantics. Document
   the failure in the dev log and stop at the import step.

7. Check if MCP endpoint is available (informational, not a blocker):
   `curl -s -H "Authorization: Bearer test" http://localhost:5678/mcp-server/http`
   Document the response (may be 401/403 with wrong token, or 404 if MCP needs
   additional config). Any non-connection-refused response indicates the MCP
   server path exists.

8. Stop the container:
   `docker compose --profile ris-n8n stop n8n`

9. Verify polytool CLI still loads:
   `python -m polytool --help`
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m polytool --help > /dev/null 2>&1 && echo "polytool CLI: OK"</automated>
  </verify>
  <done>
- Custom polytool-n8n image builds successfully from 2.x base
- Container starts and healthz returns {"status":"ok"}
- docker-cli works inside the container
- 11/11 workflow templates import (or failure is documented with evidence)
- MCP endpoint status documented
- polytool CLI unaffected
  </done>
</task>

<task type="auto">
  <name>Task 3: Update docs (ADR-0013, CURRENT_STATE, RIS_OPERATOR_GUIDE, dev log)</name>
  <files>docs/adr/0013-ris-n8n-pilot-scoped.md, docs/CURRENT_STATE.md, docs/RIS_OPERATOR_GUIDE.md, docs/dev_logs/2026-04-06_n8n_2x_instance_mcp_upgrade.md</files>
  <action>
1. **docs/adr/0013-ris-n8n-pilot-scoped.md** (Image and versioning section, lines 94-99):
   - Update `polytool-n8n:1.123.28` to `polytool-n8n:<chosen_2x_tag>`.
   - Update `n8nio/n8n:1.123.28` to `n8nio/n8n:<chosen_2x_tag>`.
   - Update the `apk add docker-cli` note to reflect the actual install method
     (Docker static binary, same as current Dockerfile).
   - Add a sentence noting this is a 2.x image providing instance-level MCP support.

2. **docs/CURRENT_STATE.md**:
   - Update the 4 version references found at lines 1510-1511 (custom image version,
     base image version).
   - Add a new section at the end documenting the 2.x migration, following the pattern
     of the existing "n8n Version Bump: 1.88.0 -> 1.123.28" section. Title it:
     `## n8n 2.x Migration: 1.123.28 -> <chosen_2x_tag> (quick-260406-ido, 2026-04-06)`
   - Include: version evidence, motivation (instance-level MCP), files changed,
     compatibility notes, verification results.

3. **docs/RIS_OPERATOR_GUIDE.md**:
   - Update "Last verified" date to 2026-04-06.
   - Update the "Claude Code MCP connection" section (lines 599-628):
     - n8n 2.x now provides an HTTP MCP server at /mcp-server/http.
     - N8N_MCP_BEARER_TOKEN is now OPERATIVE for bearer auth on that endpoint.
     - Update the [PLANNED] note about HTTP transport to reflect it is now available
       via n8n's built-in MCP server (not the polytool MCP server).
     - Keep the polytool MCP server stdio-only note (that has not changed).
     - Clearly distinguish: polytool MCP = stdio only (for Claude Desktop);
       n8n MCP = HTTP /mcp-server/http (for Claude Code, available from 2.x).
   - Update the import-workflows.sh runtime verification note to reflect the new version.

4. **docs/dev_logs/2026-04-06_n8n_2x_instance_mcp_upgrade.md** (new file):
   Follow the exact pattern of docs/dev_logs/2026-04-05_n8n_version_bump.md:
   - Title: "n8n 2.x Migration: 1.123.28 -> <chosen_tag>"
   - Date, quick task ID
   - Summary (why: instance-level MCP)
   - Version evidence (Docker Hub tags, GitHub releases)
   - Decision: upgrade to 2.x (authorized by task description)
   - Files changed table
   - Any compatibility issues found and fixed
   - Full verification commands and verbatim output (build, start, ps, healthz,
     docker-cli, workflow import, MCP endpoint probe)
   - MCP capability notes (what endpoint exists, how to connect)
   - Codex review tier: Skip (Dockerfile/docs change)
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && grep -c "2\." docs/adr/0013-ris-n8n-pilot-scoped.md > /dev/null && test -f docs/dev_logs/2026-04-06_n8n_2x_instance_mcp_upgrade.md && echo "docs: OK"</automated>
  </verify>
  <done>
- ADR-0013 version references updated to 2.x tag
- CURRENT_STATE.md has new section documenting 2.x migration
- RIS_OPERATOR_GUIDE.md MCP section updated to reflect n8n 2.x MCP capability
- Dev log created with full version evidence and verification output
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| n8n MCP HTTP endpoint | Network-accessible MCP server inside n8n container, authenticated via bearer token |
| Docker socket mount | n8n container has full Docker daemon access via socket |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-quick-01 | Spoofing | /mcp-server/http | mitigate | Bearer token auth via N8N_MCP_BEARER_TOKEN env var; operator must set a strong token (documented in .env.example and RIS_OPERATOR_GUIDE) |
| T-quick-02 | Information Disclosure | n8n MCP server | accept | n8n runs on local/trusted network only (not internet-exposed per ADR-0013); MCP endpoint exposes workflow metadata only, not secrets |
| T-quick-03 | Elevation of Privilege | Docker socket mount | accept | Pre-existing risk from 1.x (documented in ADR-0013 risk table); scope boundaries enforced by ADR, not by Docker permissions |
</threat_model>

<verification>
1. `grep -E "FROM n8nio/n8n:2\." infra/n8n/Dockerfile` -- confirms 2.x tag in Dockerfile
2. `docker compose config --quiet` -- validates compose YAML
3. `docker compose --profile ris-n8n build n8n` -- image builds
4. `docker compose --profile ris-n8n up -d n8n && curl -s http://localhost:5678/healthz` -- container runs
5. `docker exec polytool-n8n docker --version` -- docker-cli present
6. `bash infra/n8n/import-workflows.sh` -- 11/11 imports succeed
7. `python -m polytool --help` -- CLI unaffected
8. `test -f docs/dev_logs/2026-04-06_n8n_2x_instance_mcp_upgrade.md` -- dev log exists
</verification>

<success_criteria>
- n8n Dockerfile pins a specific 2.x tag (not 1.x, not `latest`)
- Custom image builds, container starts, healthz OK
- docker-cli works inside container (docker-beside-docker preserved)
- 11/11 workflow templates import successfully
- MCP endpoint presence documented (even if further config needed)
- ADR-0013, CURRENT_STATE.md, RIS_OPERATOR_GUIDE.md all reference the 2.x version
- Dev log at docs/dev_logs/2026-04-06_n8n_2x_instance_mcp_upgrade.md with full evidence
- polytool CLI still loads (`python -m polytool --help`)
</success_criteria>

<output>
After completion, create `.planning/quick/260406-ido-upgrade-n8n-base-image-from-1-x-to-lates/260406-ido-SUMMARY.md`
</output>
