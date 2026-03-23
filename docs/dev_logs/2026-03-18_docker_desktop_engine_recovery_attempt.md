# Dev Log: Docker Desktop Engine Recovery Attempt

**Date:** 2026-03-18
**Branch:** `phase-1`
**Objective:** Diagnose the local Docker Desktop engine blocker without
changing repo code, recover it if possible, and stop with either a healthy
Docker/ClickHouse path or one precise environment blocker with hard evidence.

---

## Outcome

Docker Desktop is healthy on the host when checked as the real Windows user.
The apparent engine failure was limited to the Codex sandbox account, which
cannot access Docker named pipes or WSL enumeration.

- Docker engine: **healthy** outside the sandbox
- WSL backend: **healthy** outside the sandbox (`docker-desktop` running, WSL2)
- Compose services / ClickHouse containers: **not currently started**
- Benchmark closure can resume from a real-user shell after the normal
  `docker compose up -d` startup step

Artifact root for this diagnostic:

- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\docker_recovery_20260318_222424`

---

## Files Changed And Why

- `docs/CURRENT_STATE.md`
  Replaced the stale "Docker itself is broken" state with the verified result:
  Docker Desktop is healthy for the real user, while the Codex sandbox account
  is the scope of the access-denied failures.
- `docs/dev_logs/2026-03-18_docker_desktop_engine_recovery_attempt.md`
  Recorded commands, artifact paths, diagnosis, and exact next actions.

No source code, tests, specs, runbooks, or branches were changed.

---

## Commands Run

1. Repo state capture

```powershell
git branch --show-current
git status --short
Get-Location
```

Summary:

- Branch remained `phase-1`
- Working directory was `D:\Coding Projects\Polymarket\PolyTool`
- Worktree was already dirty before this task; no unrelated changes were reverted

Artifacts:

- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\docker_recovery_20260318_222424\git_branch.txt`
- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\docker_recovery_20260318_222424\git_status_short.txt`
- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\docker_recovery_20260318_222424\pwd.txt`

2. Baseline Docker / WSL diagnosis inside the Codex sandbox account

```powershell
docker version
docker info
docker compose ps
Get-Process *docker*
Get-Service *docker*
sc.exe query com.docker.service
wsl --status
wsl -l -v
```

Summary:

- `docker version`, `docker info`, and `docker compose ps` all failed against
  `//./pipe/dockerDesktopLinuxEngine` with access denied / permission denied
- Docker Desktop frontend/backend processes existed
- `com.docker.service` was present and `Stopped`
- `wsl --status` and `wsl -l -v` both failed with access denied

Artifacts:

- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\docker_recovery_20260318_222424\docker_version_baseline.txt`
- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\docker_recovery_20260318_222424\docker_info_baseline.txt`
- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\docker_recovery_20260318_222424\docker_compose_ps_baseline.txt`
- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\docker_recovery_20260318_222424\get_process_docker_baseline.txt`
- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\docker_recovery_20260318_222424\get_service_docker_baseline.txt`
- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\docker_recovery_20260318_222424\sc_query_com_docker_service_baseline.txt`
- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\docker_recovery_20260318_222424\wsl_status_baseline.txt`
- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\docker_recovery_20260318_222424\wsl_list_verbose_baseline.txt`

3. Install path and Docker Desktop log capture

```powershell
Test-Path "C:\Program Files\Docker\Docker\Docker Desktop.exe"
Test-Path "C:\Program Files\Docker\Docker\Docker Desktop Installer.exe"
Test-Path "C:\Program Files\Docker\Docker\resources\com.docker.backend.exe"
Get-ChildItem "$env:LOCALAPPDATA\Docker" -Recurse -File
Get-ChildItem "$env:APPDATA\Docker" -Recurse -File
Get-Content <recent Docker host/vm logs> -Tail 120
```

Summary:

- Docker Desktop executables exist under `C:\Program Files\Docker\Docker`
- Recent Docker Desktop host/vm logs exist under
  `C:\Users\patel\AppData\Local\Docker\log\...`
- Backend log tails showed Docker Desktop's own backend serving API traffic,
  which contradicted the in-sandbox CLI failures and suggested a user-context
  problem rather than a dead engine

Artifacts:

- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\docker_recovery_20260318_222424\docker_install_paths.txt`
- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\docker_recovery_20260318_222424\docker_recent_logs_paths.txt`
- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\docker_recovery_20260318_222424\docker_desktop_exe_log_tail.txt`
- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\docker_recovery_20260318_222424\com_docker_backend_log_tail.txt`
- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\docker_recovery_20260318_222424\monitor_log_tail.txt`
- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\docker_recovery_20260318_222424\vm_init_log_tail.txt`

4. Permission-oriented evidence capture

```powershell
whoami
whoami /groups
sc.exe qc com.docker.service
sc.exe query LxssManager
Test-Path \\.\pipe\dockerDesktopLinuxEngine
```

Summary:

- Inside the sandbox, the session user was
  `desktop-6l73imi\codexsandboxoffline`
- Group membership showed the sandbox alias, not the normal desktop user
- Pipe probing also failed with access denied
- This made the account boundary the leading hypothesis

Artifacts:

- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\docker_recovery_20260318_222424\whoami.txt`
- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\docker_recovery_20260318_222424\whoami_groups.txt`
- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\docker_recovery_20260318_222424\sc_qc_com_docker_service.txt`
- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\docker_recovery_20260318_222424\sc_query_lxssmanager.txt`
- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\docker_recovery_20260318_222424\docker_pipe_check.txt`

5. Outside-sandbox verification as the real Windows user

```powershell
whoami
docker version
docker info
docker compose ps
wsl --status
wsl -l -v
python -m polytool close-benchmark-v1 --status
```

Summary:

- Outside the sandbox, the session user was `desktop-6l73imi\patel`
- `docker version` succeeded and returned both client and server
- `docker info` succeeded and reported Docker Desktop 4.52.0 / Engine 29.0.1
- `docker compose ps` succeeded; no services were currently running
- `wsl --status` succeeded; default distribution is `docker-desktop`
- `wsl -l -v` succeeded; `docker-desktop` is `Running`, WSL version `2`
- `python -m polytool close-benchmark-v1 --status` succeeded and reported:
  `config\benchmark_v1.tape_manifest` missing, residual shortages still
  present, suggested next step `docker compose up -d`

Artifacts:

- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\docker_recovery_20260318_222424\whoami_escalated.txt`
- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\docker_recovery_20260318_222424\docker_version_escalated.txt`
- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\docker_recovery_20260318_222424\docker_info_escalated.txt`
- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\docker_recovery_20260318_222424\docker_compose_ps_escalated.txt`
- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\docker_recovery_20260318_222424\wsl_status_escalated.txt`
- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\docker_recovery_20260318_222424\wsl_list_verbose_escalated.txt`
- `D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\2026-03-18\docker_recovery_20260318_222424\close_benchmark_v1_status_escalated.txt`

---

## Diagnosis Findings

The narrowest truthful blocker category from the Codex session was
`admin/permissions`, not broken Docker Desktop or broken WSL.

Hard evidence:

- The sandbox account is `desktop-6l73imi\codexsandboxoffline`, and its Docker
  / WSL commands fail with access denied
- The real user account is `desktop-6l73imi\patel`, and the same Docker / WSL
  commands succeed immediately outside the sandbox
- Docker Desktop backend logs showed active API traffic even while the sandbox
  CLI was failing

This means the local Docker Desktop engine was not the failing component. The
failing component was the account context used by the Codex sandbox.

---

## Recovery Attempts Made

- Read-only diagnosis and log capture: completed
- User-process kill/relaunch of Docker Desktop: **not performed**
- Reason it was not performed: once outside-sandbox verification showed Docker
  Desktop and WSL already healthy for the real user, restarting Docker Desktop
  would have been unnecessary and potentially disruptive

---

## Final Health Status

- Docker Desktop engine: healthy for the real user session
- Docker Desktop installation: present and functioning
- WSL backend: healthy for `docker-desktop`
- Compose services: currently down
- ClickHouse readiness for the benchmark workflow: pending normal
  `docker compose up -d`

Whether benchmark closure can resume now:

- **Yes**, from a real-user shell after starting the compose services

---

## Exact Next Action

Exact next manual command now that Docker is healthy:

```powershell
docker compose up -d
```

Exact next manual command after compose services are up:

```powershell
python -m polytool close-benchmark-v1 --skip-new-market --pmxt-root "D:\Coding Projects\Polymarket\PolyToolData\raw\pmxt_archive" --jon-root "D:\Coding Projects\Polymarket\PolyToolData\raw\jon_becker"
```

Exact manual remediation if Docker later appears unhealthy again:

```text
Re-run Docker and WSL checks from a normal real-user shell as desktop-6l73imi\patel, not from the Codex sandbox account desktop-6l73imi\codexsandboxoffline. If access-denied only reproduces in the sandbox account, treat it as an account/permissions boundary rather than a Docker Desktop engine failure.
```

---

## Final Result

The local Docker Desktop engine blocker was **not reproduced** outside the
Codex sandbox. Docker Desktop and WSL are healthy enough to proceed with the
benchmark closure workflow from a real-user shell. The remaining immediate step
is standard compose startup, not machine repair.
