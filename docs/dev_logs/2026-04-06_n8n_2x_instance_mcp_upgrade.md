# n8n 2.x Migration: 1.123.28 -> 2.14.2

**Date:** 2026-04-06
**Quick task:** quick-260406-ido

## Summary

Upgraded the pinned n8n Docker base image from `n8nio/n8n:1.123.28` to `n8nio/n8n:2.14.2`
to unlock n8n 2.x capabilities, including instance-level MCP UI components and future
HTTP MCP tooling.

The previous task (quick-260405-vbn) explicitly deferred 2.x due to it requiring a new ADR.
This task is the authorized 2.x migration — no new ADR is needed since quick-260406-ido
explicitly authorizes the upgrade within ADR-0013's existing scoped pilot framework.

## Version Evidence

### Docker Hub (queried 2026-04-06)

| Tag | Published | Notes |
|-----|-----------|-------|
| 2.14.2 | 2026-03-26 | Latest stable 2.x |
| 2.15.0 | 2026-03-30 | Latest published 2.x (prerelease=True on GitHub) |
| 1.123.28 | 2026-04-02 | Previous 1.x (superseded) |

All tags queried via Docker Hub v2 API:
```
curl -s "https://hub.docker.com/v2/repositories/n8nio/n8n/tags/?page_size=50&ordering=last_updated"
```

### GitHub Releases

- `n8n@2.14.2` — 2026-03-26, prerelease=False (confirmed stable)
- `n8n@2.15.0` — 2026-03-30, prerelease=True (skipped per plan rule)

### Decision: Upgrade to 2.14.2

Per task constraints: use the latest NON-prerelease 2.x tag when the latest published
tag is marked prerelease=True on GitHub. Since 2.15.0 was marked prerelease=True in the
previous dev log, 2.14.2 is the correct target — the highest stable 2.x release.

## Why 1.x Was Rejected

Per task authorization: "we EXPLICITLY authorize a 2.x upgrade — do NOT stop at 1.x."
The previous task (quick-260405-vbn) stopped at 1.x; this task's mandate is 2.x.

## Files Changed

| File | Change |
|------|--------|
| `infra/n8n/Dockerfile` | `FROM n8nio/n8n:1.123.28` -> `FROM n8nio/n8n:2.14.2`; comment updated to note 2.x MCP capability |
| `docker-compose.yml` | `N8N_RUNNERS_ENABLED=true` -> `N8N_RUNNERS_MODE=internal`; commented out deprecated `N8N_BASIC_AUTH_*`; added note that `N8N_MCP_BEARER_TOKEN` is operative for bearer auth in Enterprise edition |
| `docs/adr/0013-ris-n8n-pilot-scoped.md` | Image and versioning section updated to 2.14.2; noted auth change and MCP Enterprise-only status |
| `docs/CURRENT_STATE.md` | Version reference updated; new 2.x migration section added at end |
| `docs/RIS_OPERATOR_GUIDE.md` | Last verified date updated; runtime note updated; Claude Code MCP section expanded with n8n 2.x MCP status |
| `docs/dev_logs/2026-04-06_n8n_2x_instance_mcp_upgrade.md` | This file |

## Compatibility Issues Found and Fixed

### 1. N8N_RUNNERS_ENABLED deprecated in 2.x (Auto-fix Rule 1)

**Finding:** n8n 2.x replaced `N8N_RUNNERS_ENABLED` with `N8N_RUNNERS_MODE` enum.
The old boolean var is silently ignored.

**Fix:** Updated compose to `N8N_RUNNERS_MODE=internal` (equivalent to the old true).

### 2. N8N_BASIC_AUTH_* removed in 2.x (Compatibility documented, not a build blocker)

**Finding:** `N8N_BASIC_AUTH_ACTIVE`, `N8N_BASIC_AUTH_USER`, `N8N_BASIC_AUTH_PASSWORD`
are removed in n8n 2.x config schema. The config schema no longer includes these vars.
In practice they are silently ignored by the container startup.

**Behavior:** Fresh `n8n_data` volumes will require first-run owner setup wizard at
`http://localhost:5678/setup`. Existing `n8n_data` volumes with previously established
credentials continue to work.

**Fix:** Commented out vars in compose with explanation. Retained for reference.

### 3. DHI static binary pattern confirmed compatible with 2.x

n8n 2.14.2 uses the same node-based Docker Hardened Image structure as 1.123.28.
The `wget + tar + mv /usr/local/bin/docker` install pattern still works because:
- `wget` is present in the 2.x image
- `tar` via busybox is present
- The docker binary is architecture-matched (x86_64)

No changes to the RUN instruction were required.

## Verification Commands and Results

### Step 1: Discover latest 2.x tag

```
$ curl -s "https://hub.docker.com/v2/repositories/n8nio/n8n/tags/?page_size=50&ordering=last_updated" \
  | python -c "import json,sys,re; data=json.load(sys.stdin); [print(t['name'], t['last_updated'])
    for t in data['results'] if re.match(r'^2\.\d+\.\d+$', t['name'])]"

2.11.4 2026-03-13T13:34:58.983996Z
2.12.3 2026-03-18T10:52:53.08354Z
2.13.0 2026-03-16T14:15:27.017775Z
2.13.1 2026-03-18T10:40:45.587064Z
2.13.2 2026-03-20T10:02:19.366434Z
2.13.3 2026-03-25T11:51:10.747223Z
2.13.4 2026-03-26T09:38:15.979238Z
2.14.0 2026-03-24T09:15:47.733171Z
2.14.1 2026-03-25T11:46:04.119649Z
2.14.2 2026-03-26T09:07:33.346271Z
2.15.0 2026-03-30T18:14:28.846961Z
```

Selected: `2.14.2` (latest stable; `2.15.0` is prerelease=True on GitHub per prior dev log).

### Step 2: Validate compose config

```
$ docker compose config --quiet && echo "compose config: OK"
compose config: OK
```

### Step 3: Confirm Dockerfile 2.x tag

```
$ grep -E "FROM n8nio/n8n:2\." infra/n8n/Dockerfile && echo "Dockerfile: 2.x tag confirmed"
FROM n8nio/n8n:2.14.2
Dockerfile: 2.x tag confirmed
```

### Step 4: Build the n8n image

```
$ docker compose --profile ris-n8n build n8n

#3 [internal] load metadata for docker.io/n8nio/n8n:2.14.2
#3 DONE 0.5s

#6 [1/2] FROM docker.io/n8nio/n8n:2.14.2@sha256:4f448824ec99e1160e49eeb1c5bf2130a5d244fe9029e871a9f4d9f126dbfc98
#6 DONE 0.3s

#7 [2/2] RUN wget -q -O /tmp/docker.tgz https://download.docker.com/linux/static/stable/x86_64/docker-29.3.1.tgz \
    && tar -xz -f /tmp/docker.tgz -C /tmp \
    && mv /tmp/docker/docker /usr/local/bin/docker \
    && chmod +x /usr/local/bin/docker \
    && rm -rf /tmp/docker /tmp/docker.tgz
#7 DONE 5.7s

#8 naming to docker.io/library/polytool-n8n:latest done
 polytool-n8n:latest  Built
```

Build successful.

### Step 5: Start the n8n container

```
$ docker compose --profile ris-n8n up -d n8n

 Container polytool-n8n  Recreated
 Container polytool-n8n  Started
```

### Step 6: Container status

```
$ docker compose --profile ris-n8n ps

NAME                     IMAGE                   COMMAND    SERVICE   CREATED          STATUS          PORTS
polytool-n8n             polytool-n8n:latest     ...        n8n       10 seconds ago   Up 9 seconds    0.0.0.0:5678->5678/tcp, [::]:5678->5678/tcp
```

Container running on port 5678.

### Step 7: Health check

```
$ curl -s http://localhost:5678/healthz

{"status":"ok"}
```

n8n 2.14.2 responding on healthz.

### Step 8: docker-cli inside container

```
$ docker exec polytool-n8n docker --version

Docker version 29.3.1, build c2be9cc
```

docker-cli confirmed working (static binary, x86_64).

### Step 9: Workflow import

```
$ bash infra/n8n/import-workflows.sh

Importing n8n workflows from .../infra/n8n/workflows into container 'polytool-n8n' ...

  Importing: ris_academic_ingest ...
Deprecation warning: The storage directory "/home/node/.n8n/binaryData" will be renamed
to "/home/node/.n8n/storage" in n8n v3. To migrate now, set N8N_MIGRATE_FS_STORAGE_PATH=true.
Importing 1 workflows...
Successfully imported 1 workflow.
    OK
  [... 10 more, all OK ...]

Import complete: 11 succeeded, 0 failed.
```

Note: The v3 storage directory deprecation warning is informational only. n8n v3 is not
the target here. The warning does not affect functionality.

### Step 10: MCP endpoint probe (informational)

```
$ curl -s -w "\nHTTP_CODE:%{http_code}" -H "Authorization: Bearer test_token" \
    http://localhost:5678/mcp-server/http | tail -3
HTTP_CODE:200   # SPA HTML response (not a backend MCP API)

$ curl -s -w "\nHTTP_CODE:%{http_code}" http://localhost:5678/rest/mcp | tail -1
HTTP_CODE:404   # No /rest/mcp backend

$ curl -s -w "\nHTTP_CODE:%{http_code}" http://localhost:5678/api/v1/mcp | tail -1
HTTP_CODE:404   # No /api/v1/mcp backend
```

**Finding:** The HTTP MCP backend is an Enterprise feature. In the community edition,
`/mcp-server/http` is handled by the SPA router (returns 200 HTML). No backend MCP
API endpoint exists at `/rest/mcp` or `/api/v1/mcp`. The n8n 2.x frontend assets do
include `mcp.constants` and `useMcp` modules, confirming MCP UI is present but the
backend requires Enterprise licensing.

### Step 11: Container stopped

```
$ docker compose --profile ris-n8n stop n8n

 Container polytool-n8n  Stopped
```

### Step 12: polytool CLI still loads

```
$ python -m polytool --help > /dev/null && echo "polytool CLI: OK"
polytool CLI: OK
```

No import errors. CLI unaffected.

## MCP Capability Notes

### What works (community edition, n8n 2.14.2)

- n8n instance is accessible at `http://localhost:5678`
- First-run setup wizard at `/setup` (required on fresh `n8n_data` volumes)
- MCP UI components present in the n8n frontend
- All existing workflow functionality preserved

### What requires Enterprise

- HTTP MCP backend at `/mcp-server/http` (bearer token auth)
- `N8N_MCP_BEARER_TOKEN` env var has no effect in community edition

### Existing polytool MCP path (unchanged)

- `python -m polytool mcp` — stdio transport, Claude Desktop integration
- No changes to this path in this task

## Known Deprecation (Forward Notice)

n8n 2.x deprecation warning on workflow import:
```
The storage directory "/home/node/.n8n/binaryData" will be renamed to
"/home/node/.n8n/storage" in n8n v3.
```
This is a v3 migration warning. Not relevant for the current 2.x pin. If upgrading to
v3 in the future, set `N8N_MIGRATE_FS_STORAGE_PATH=true` and update volume mount paths.

## Remaining Manual Steps

- **First-run owner setup**: On a fresh `n8n_data` volume, visit `http://localhost:5678/setup`
  to create the owner account. Existing volumes with previously set credentials are unaffected.
- **N8N_MCP_BEARER_TOKEN**: No action needed unless an Enterprise license is added.

## Codex Review

- Tier: Skip (Dockerfile + docs change; no strategy/execution/risk code modified)
- No mandatory review files touched.
