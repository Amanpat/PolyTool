# n8n Version Bump: 1.88.0 -> 1.123.28

**Date:** 2026-04-05
**Quick task:** quick-260405-vbn

## Summary

Updated the pinned n8n Docker base image from `n8nio/n8n:1.88.0` to `n8nio/n8n:1.123.28`.
This is the latest stable release on the 1.x maintenance branch.

**Compatibility note:** n8n 1.123.28 ships as a Docker Hardened Image (DHI) based on
Alpine 3.22, but with the `apk` package manager binary removed. The Dockerfile was updated
to install docker-cli via the official Docker static binary instead of `apk add docker-cli`.
All functionality is preserved.

## Version Evidence

### Docker Hub (queried 2026-04-05)

| Tag | Published | Notes |
|-----|-----------|-------|
| 1.123.28 | 2026-04-02 | Latest 1.x |
| 1.123.27 | 2026-03-25 | Previous 1.x |
| 2.15.0 | 2026-03-30 | Latest 2.x (prerelease) |
| 2.14.2 | 2026-03-26 | Latest stable 2.x |

### GitHub Releases (queried 2026-04-05)

- `n8n@1.123.28` -- 2026-04-02, prerelease=False
- `n8n@2.15.0` -- 2026-03-30, prerelease=True

### Tag numbering

Docker Hub uses bare semver (`1.123.28`). GitHub prefixes with `n8n@` (`n8n@1.123.28`).
No mismatch between the two sources.

### Decision: Stay on 1.x

The `latest` Docker tag now points to the 2.x line. A 1.x -> 2.x migration would be a
major version change requiring a separate ADR. The 1.x line still receives active patch
releases (1.123.28 is 3 days old as of this writing). Staying on 1.x is the conservative,
correct choice per ADR-0013 scoping.

## Files Changed

| File | Change |
|------|--------|
| `infra/n8n/Dockerfile` | `FROM n8nio/n8n:1.88.0` -> `FROM n8nio/n8n:1.123.28`; `apk add docker-cli` -> Docker static binary install |
| `docs/adr/0013-ris-n8n-pilot-scoped.md` | Version references updated (`polytool-n8n:1.88.0` -> `1.123.28`, `n8nio/n8n:1.88.0` -> `1.123.28`) |
| `docs/CURRENT_STATE.md` | 4 operational version references updated + new version bump section added |

## Compatibility Issue Found and Fixed (Auto-fix Rule 1)

**Finding:** `n8n 1.123.28` uses a Docker Hardened Image (DHI) based on Alpine 3.22.
Unlike earlier 1.x releases, DHI removes the `apk` package manager binary from the
image as a security hardening measure. Running `apk add --no-cache docker-cli` fails:

```
#7 [2/2] RUN apk add --no-cache docker-cli
#7 0.222 /bin/sh: apk: not found
#7 ERROR: process "/bin/sh -c apk add --no-cache docker-cli" did not complete successfully: exit code: 127
```

**Diagnosis:**
- OS: `Docker Hardened Images (Alpine) v3.22` (confirmed via `cat /etc/os-release`)
- `apk` binary: not present anywhere in the image (only `/etc/apk/`, `/var/cache/apk/`, `/lib/apk` directories remain)
- Available tools: `wget`, `sh`, `busybox`
- Architecture: `x86_64`

**Fix applied:** Install docker-cli via the official Docker static binary tarball:

```dockerfile
RUN wget -q -O /tmp/docker.tgz https://download.docker.com/linux/static/stable/x86_64/docker-29.3.1.tgz \
    && tar -xz -f /tmp/docker.tgz -C /tmp \
    && mv /tmp/docker/docker /usr/local/bin/docker \
    && chmod +x /usr/local/bin/docker \
    && rm -rf /tmp/docker /tmp/docker.tgz
```

Docker version pinned to `29.3.1` (latest stable as of 2026-04-05).

## Verification Commands and Results

### Step 1: Validate compose config

```
$ docker compose config --quiet && echo "compose config: OK"
compose config: OK
```

Exit code 0. Valid YAML.

### Step 2: Build the n8n image

```
$ docker compose --profile ris-n8n build n8n

#6 [1/2] FROM docker.io/n8nio/n8n:1.123.28@sha256:f71b38c2dd5eea428306f5a9e473bfb280d834e304735911f73fdf55e3115069
#6 CACHED

#7 [2/2] RUN wget -q -O /tmp/docker.tgz https://download.docker.com/linux/static/stable/x86_64/docker-29.3.1.tgz     && tar -xz -f /tmp/docker.tgz -C /tmp     && mv /tmp/docker/docker /usr/local/bin/docker     && chmod +x /usr/local/bin/docker     && rm -rf /tmp/docker /tmp/docker.tgz
#7 DONE 5.3s

#8 exporting to image
#8 naming to docker.io/library/polytool-n8n:latest done
 polytool-n8n:latest  Built
```

Build successful. docker-cli installed via static binary (Docker 29.3.1).

### Step 3: Start the n8n container

```
$ docker compose --profile ris-n8n up -d n8n

 Container polytool-n8n  Recreated
 Container polytool-n8n  Started
```

### Step 4: Container status

```
$ docker compose --profile ris-n8n ps

NAME                     IMAGE                    COMMAND    SERVICE   CREATED        STATUS        PORTS
polytool-n8n             polytool-n8n:latest      ...        n8n       8 seconds ago  Up 7 seconds  0.0.0.0:5678->5678/tcp, [::]:5678->5678/tcp
```

Container running.

### Step 5: Health check

```
$ curl -s http://localhost:5678/healthz

{"status":"ok"}
```

n8n responding on healthz endpoint.

### Step 6: Verify docker-cli inside container

```
$ docker exec polytool-n8n docker --version

Docker version 29.3.1, build c2be9cc
```

docker-cli confirmed working inside container.

### Step 7: Workflow import test

```
$ bash infra/n8n/import-workflows.sh

Importing n8n workflows from /infra/n8n/workflows into container 'polytool-n8n' ...

  Importing: ris_academic_ingest ... OK
  Importing: ris_blog_ingest ... OK
  Importing: ris_freshness_refresh ... OK
  Importing: ris_github_ingest ... OK
  Importing: ris_health_check ... OK
  Importing: ris_manual_acquire ... OK
  Importing: ris_reddit_others ... OK
  Importing: ris_reddit_polymarket ... OK
  Importing: ris_scheduler_status ... OK
  Importing: ris_weekly_digest ... OK
  Importing: ris_youtube_ingest ... OK

Import complete: 11 succeeded, 0 failed.
```

All 11 workflows imported successfully.

### Step 8: Container stopped

```
$ docker compose --profile ris-n8n stop n8n

 Container polytool-n8n  Stopped
```

### Step 9: polytool CLI still loads

```
$ python -m polytool --help

PolyTool - Polymarket analysis toolchain

Usage: polytool <command> [options]
       python -m polytool <command> [options]
```

No import errors. CLI healthy.

## Compatibility Notes

- Alpine base: confirmed (Alpine 3.22 DHI)
- apk binary: removed in DHI -- fixed by using Docker static binary download
- docker-cli: confirmed installed (Docker 29.3.1, build c2be9cc) and functional
- n8n healthz: confirmed responding (`{"status":"ok"}`)
- Workflow import: 11/11 succeeded
- polytool CLI: confirmed loading

## Manual Follow-Up

- None required. All verification steps passed.
- If considering 2.x migration in future: create a new ADR, test workflow JSON
  compatibility, and verify the docker-beside-docker pattern still works.
- Note for future bumps: DHI base images do not include `apk`. Continue using
  the Docker static binary approach for docker-cli installation.

## Codex Review

- Tier: Skip (Dockerfile change, no strategy/execution/risk code modified)
