---
phase: quick-260405-vbn
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - infra/n8n/Dockerfile
  - docs/adr/0013-ris-n8n-pilot-scoped.md
  - docs/CURRENT_STATE.md
  - docs/dev_logs/2026-04-05_n8n_version_bump.md
autonomous: true
requirements: [quick-260405-vbn]

must_haves:
  truths:
    - "infra/n8n/Dockerfile FROM line uses n8nio/n8n:1.123.28"
    - "docker compose --profile ris-n8n build n8n succeeds"
    - "docker compose --profile ris-n8n up -d n8n starts a healthy container"
    - "All docs mentioning 1.88.0 are updated to 1.123.28 (except historical dev logs)"
    - "Dev log records evidence, commands, and results"
  artifacts:
    - path: "infra/n8n/Dockerfile"
      provides: "Custom n8n image definition"
      contains: "n8nio/n8n:1.123.28"
    - path: "docs/dev_logs/2026-04-05_n8n_version_bump.md"
      provides: "Version bump dev log with evidence and verification"
  key_links:
    - from: "infra/n8n/Dockerfile"
      to: "docker-compose.yml n8n service"
      via: "build context ./infra/n8n"
      pattern: "FROM n8nio/n8n:1\\.123\\.28"
---

<objective>
Update the pinned n8n Docker image from 1.88.0 to 1.123.28 (latest stable 1.x release),
verify the RIS n8n pilot still builds and starts cleanly, and update all docs that
reference the old version.

Purpose: Keep the n8n base image current within the 1.x line to pick up security
patches and bug fixes, while preserving the scoped RIS pilot framing per ADR 0013.

Output: Updated Dockerfile, updated docs, dev log with full evidence trail, verified
container build and startup.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@infra/n8n/Dockerfile
@docker-compose.yml
@docs/adr/0013-ris-n8n-pilot-scoped.md
@docs/CURRENT_STATE.md

<interfaces>
The n8n service in docker-compose.yml uses build context `./infra/n8n` and Dockerfile
within it. The Dockerfile is a simple alpine-based extension that adds docker-cli.
No code changes are needed -- only the base image tag changes.

Current Dockerfile (full contents):
```dockerfile
# Custom n8n image for PolyTool RIS pilot
# Extends n8nio/n8n:1.88.0 with docker-cli so Execute Command nodes can
# use `docker exec polytool-ris-scheduler python -m polytool ...`
FROM n8nio/n8n:1.88.0
USER root
RUN apk add --no-cache docker-cli
USER node
```
</interfaces>

<version_evidence>
## Target Version Evidence (gathered during planning)

The target version is **1.123.28** (latest stable 1.x release).

**Source 1 -- Docker Hub tags** (queried 2026-04-05):
- `1.123.28` published 2026-04-02T10:51:10Z (latest 1.x)
- `1.123.27` published 2026-03-25
- `1.123.26` published 2026-03-19

**Source 2 -- GitHub releases** (queried 2026-04-05):
- `n8n@1.123.28` published 2026-04-02, prerelease=False
- `n8n@1.123.27` published 2026-03-25, prerelease=False

**2.x line exists but is NOT the target:**
- `2.15.0` (prerelease), `2.14.2` (stable), `2.13.4` (stable) are available
- The `latest` Docker tag now points to the 2.x line (updated 2026-03-30)
- Staying on 1.x avoids a major version migration and potential breaking changes
- 1.x line still receives patch releases (1.123.28 is 4 days old)

**Why 1.123.28 and not 2.x:**
- Per ADR 0013: "n8n image tag is pinned. Updates require explicit commit."
- A 1.x -> 2.x migration is a separate scope decision (new ADR required)
- The Dockerfile uses `apk add docker-cli` which requires Alpine base; 1.x confirmed Alpine
- 1.123.28 is the latest patch on the active 1.x maintenance branch

**Docker Hub / GitHub tag numbering:**
Docker Hub tags match GitHub release tags exactly (both use `1.123.28`).
GitHub prefixes with `n8n@` (e.g., `n8n@1.123.28`) but Docker Hub uses bare semver.
No mismatch.
</version_evidence>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Update Dockerfile and docs from 1.88.0 to 1.123.28</name>
  <files>
    infra/n8n/Dockerfile,
    docs/adr/0013-ris-n8n-pilot-scoped.md,
    docs/CURRENT_STATE.md
  </files>
  <action>
Update the pinned n8n base image tag from `1.88.0` to `1.123.28` in these files:

1. **infra/n8n/Dockerfile** (PRIMARY):
   - Line 2 comment: change `n8nio/n8n:1.88.0` to `n8nio/n8n:1.123.28`
   - Line 4 FROM: change `FROM n8nio/n8n:1.88.0` to `FROM n8nio/n8n:1.123.28`
   - Do NOT change the `apk add --no-cache docker-cli` line or USER directives

2. **docs/adr/0013-ris-n8n-pilot-scoped.md** (Image and versioning section, ~line 94-95):
   - Change `polytool-n8n:1.88.0` to `polytool-n8n:1.123.28`
   - Change `n8nio/n8n:1.88.0` to `n8nio/n8n:1.123.28`
   - Leave all other content unchanged

3. **docs/CURRENT_STATE.md** (~lines 1510-1521):
   - Change all occurrences of `1.88.0` to `1.123.28` in the "RIS n8n Runtime Path Fixed"
     section. There are 4 occurrences:
     - `polytool-n8n:1.88.0` (line ~1510)
     - `n8nio/n8n:1.88.0` (line ~1511)
     - `n8n 1.88.0 deprecated` (line ~1518)
     - `n8n 1.88.0` in tag format note (line ~1520)
   - Add a new section after the "RIS n8n Docs Reconciliation" block (~line 1542):
     ```
     ## n8n Version Bump: 1.88.0 -> 1.123.28 (quick-260405-vbn, 2026-04-05)

     - Pinned n8n base image updated from `n8nio/n8n:1.88.0` to `n8nio/n8n:1.123.28`
       (latest stable 1.x release as of 2026-04-05).
     - Evidence: Docker Hub tag `1.123.28` published 2026-04-02; GitHub release
       `n8n@1.123.28` (non-prerelease) published same day.
     - Staying on 1.x line; 2.x migration deferred (would require new ADR).
     - Build and startup verified: `docker compose --profile ris-n8n build n8n` and
       `docker compose --profile ris-n8n up -d n8n` both pass.
     - See `docs/dev_logs/2026-04-05_n8n_version_bump.md` for full evidence.
     ```

**DO NOT** modify historical dev logs (`docs/dev_logs/2026-04-05_ris_n8n_runtime_fix.md`,
`docs/dev_logs/2026-04-05_ris_n8n_pilot.md`, etc.) -- they are historical records of what
happened at the time.

**DO NOT** modify `docs/reference/RAGfiles/RIS_06_INFRASTRUCTURE.md` -- it uses `latest`
(not `1.88.0`) and is a stale reference doc, not an operational artifact.

**DO NOT** modify `docker-compose.yml` -- the n8n service uses `image: polytool-n8n:latest`
as the local build tag, not the upstream base image tag. The base image is only in the
Dockerfile.
  </action>
  <verify>
    <automated>grep -c "1.88.0" infra/n8n/Dockerfile docs/adr/0013-ris-n8n-pilot-scoped.md | grep ":0$" | wc -l</automated>
    Verify: `grep "1.123.28" infra/n8n/Dockerfile` shows 2 matches (comment + FROM).
    Verify: `grep "1.123.28" docs/adr/0013-ris-n8n-pilot-scoped.md` shows 2 matches.
    Verify: `grep "1.88.0" infra/n8n/Dockerfile` returns 0 matches.
    Verify: `docker compose config` succeeds (compose file is still valid YAML).
  </verify>
  <done>
    All occurrences of 1.88.0 in Dockerfile and ADR-0013 replaced with 1.123.28.
    CURRENT_STATE.md updated with version references and a new section documenting the bump.
    No historical dev logs modified. docker-compose.yml unchanged.
  </done>
</task>

<task type="auto">
  <name>Task 2: Build, start, verify n8n container, and write dev log</name>
  <files>docs/dev_logs/2026-04-05_n8n_version_bump.md</files>
  <action>
Run the verification sequence and capture all output for the dev log:

1. **Validate compose config:**
   ```bash
   docker compose config --quiet
   ```
   Confirm exit code 0 (valid YAML).

2. **Build the n8n image:**
   ```bash
   docker compose --profile ris-n8n build n8n
   ```
   Confirm the build completes successfully. The key line to watch for is the
   `apk add --no-cache docker-cli` step -- if the base image switched from Alpine
   to Debian, this will fail. If it fails, STOP and document the blocker.

3. **Start the n8n container:**
   ```bash
   docker compose --profile ris-n8n up -d n8n
   ```
   Wait a few seconds, then check:
   ```bash
   docker compose --profile ris-n8n ps
   ```
   Container `polytool-n8n` should show status "Up" or "running".

4. **Verify health:**
   ```bash
   curl -s http://localhost:5678/healthz
   ```
   Expected: `{"status":"ok"}` (or similar health response).

5. **Verify docker-cli inside container:**
   ```bash
   docker exec polytool-n8n docker --version
   ```
   Should return a Docker version string (confirms apk install worked).

6. **Optional -- workflow import test** (if ris-scheduler container is also running):
   ```bash
   bash infra/n8n/import-workflows.sh
   ```
   This tests the full import path. If ris-scheduler is not running, skip this step
   and note it in the dev log.

7. **Tear down** (optional, operator preference):
   ```bash
   docker compose --profile ris-n8n stop n8n
   ```

8. **Verify CLI still loads:**
   ```bash
   python -m polytool --help
   ```
   Confirm no import errors (the version bump should not affect Python code).

9. **Write the dev log** to `docs/dev_logs/2026-04-05_n8n_version_bump.md`:

```markdown
# n8n Version Bump: 1.88.0 -> 1.123.28

**Date:** 2026-04-05
**Quick task:** quick-260405-vbn

## Summary

Updated the pinned n8n Docker base image from `n8nio/n8n:1.88.0` to `n8nio/n8n:1.123.28`.
This is the latest stable release on the 1.x maintenance branch.

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
| `infra/n8n/Dockerfile` | `FROM n8nio/n8n:1.88.0` -> `FROM n8nio/n8n:1.123.28` |
| `docs/adr/0013-ris-n8n-pilot-scoped.md` | Version references updated |
| `docs/CURRENT_STATE.md` | Version references updated + new section added |

## Verification Commands and Results

[Paste verbatim output from steps 1-8 here during execution]

## Compatibility Notes

- Alpine base: confirmed (apk add docker-cli succeeded)
- docker-cli: confirmed installed and functional
- n8n healthz: confirmed responding
- Workflow import: [result or "skipped -- ris-scheduler not running"]
- polytool CLI: confirmed loading

## Manual Follow-Up

- None required if all verification steps passed.
- If considering 2.x migration in future: create a new ADR, test workflow JSON
  compatibility, and verify the docker-beside-docker pattern still works.
```

Populate the "Verification Commands and Results" section with actual verbatim command
output captured during steps 1-8. Do NOT use placeholder text.
  </action>
  <verify>
    <automated>docker compose --profile ris-n8n build n8n 2>&1 | tail -1</automated>
    Also verify: `docker compose config --quiet` exits 0.
    Also verify: `test -f docs/dev_logs/2026-04-05_n8n_version_bump.md` exits 0.
  </verify>
  <done>
    n8n container builds successfully with the new base image (1.123.28).
    Container starts and responds on healthz endpoint.
    docker-cli confirmed working inside container.
    Dev log written with verbatim evidence from all verification steps.
    No compatibility blockers found.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Docker Hub -> local build | Pulling a new base image tag from public registry |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-quick-01 | Tampering | Docker Hub image pull | accept | Standard Docker Hub pull; n8n is a widely-used official image. Tag is pinned (not `latest`). Operator can verify image digest if needed. |
| T-quick-02 | Elevation of Privilege | docker.sock mount | accept | Pre-existing risk documented in ADR-0013. No change from version bump. |
</threat_model>

<verification>
1. `grep "1.123.28" infra/n8n/Dockerfile` returns 2 matches
2. `grep "1.88.0" infra/n8n/Dockerfile` returns 0 matches
3. `docker compose config --quiet` exits 0
4. `docker compose --profile ris-n8n build n8n` succeeds
5. `docker compose --profile ris-n8n ps` shows polytool-n8n running
6. `python -m polytool --help` loads without errors
7. Dev log exists at `docs/dev_logs/2026-04-05_n8n_version_bump.md`
</verification>

<success_criteria>
- Dockerfile uses `FROM n8nio/n8n:1.123.28` (not 1.88.0, not latest)
- n8n container builds and starts cleanly
- ADR-0013 and CURRENT_STATE.md reflect the new version
- Dev log documents evidence sources, commands run, and results
- No historical dev logs modified
- No workflow semantics changed
- polytool CLI still loads
</success_criteria>

<output>
After completion, create `.planning/quick/260405-vbn-update-the-repo-s-pinned-n8n-docker-imag/260405-vbn-SUMMARY.md`
</output>
