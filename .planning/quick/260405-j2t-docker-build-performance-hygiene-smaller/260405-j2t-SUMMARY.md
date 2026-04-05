---
phase: quick-260405-j2t
plan: "01"
subsystem: docker-infra
tags: [docker, buildkit, cache, dockerfile, dockerignore, hygiene]
dependency_graph:
  requires: []
  provides: [faster-docker-builds, smaller-build-context, buildkit-cache-mounts]
  affects: [Dockerfile, services/api/Dockerfile, .dockerignore]
tech_stack:
  added: []
  patterns: [buildkit-cache-mounts, two-phase-pip-install, selective-copy]
key_files:
  created:
    - docs/dev_logs/2026-04-05_docker_perf_hygiene.md
  modified:
    - .dockerignore
    - Dockerfile
    - services/api/Dockerfile
    - docs/CURRENT_STATE.md
decisions:
  - "Selective COPY (polytool/, packages/, tools/, services/) instead of COPY . . to prevent source edits from busting dep cache"
  - "Two-phase pip install: full deps on pyproject.toml (cached), then --no-deps after source copy (fast metadata update)"
  - "Remove --no-cache-dir from pip (BuildKit pip cache mount handles caching)"
  - "Remove rm -rf /var/lib/apt/lists/* (apt cache mount makes cleanup unnecessary)"
  - "Dockerfile.bot documented as orphaned, not deleted (operator decision required)"
metrics:
  duration_minutes: 30
  completed_date: "2026-04-05"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 4
---

# Phase quick-260405-j2t Plan 01: Docker Build Performance Hygiene Summary

**One-liner:** Comprehensive `.dockerignore` excluding ~660 MB of non-build files plus two-phase pip install and BuildKit cache mounts in both Python Dockerfiles.

---

## What Was Done

### Task 1: Tighten .dockerignore and fix Dockerfile cache patterns

**`.dockerignore` rewrite (1A)**

Added 20+ new exclusions. Before: only `.git`, `.venv`, `.pytest_cache`, `__pycache__`, `artifacts/`, `.tmp/`, `kb/tmp_tests/`, `node_modules/`, `dist/`, `build/`, and two log files.

After: additionally excludes:
- `docs/` (4 MB), `tests/` (12 MB), `kb/` (122 MB), `.planning/` (2.8 MB), `infra/` (424 KB), `scripts/` (7 KB), `config/` (463 KB), `.claude/` (517 MB), `docker_data/`
- `.env`, `.env.*` (with `!.env.example` negation — security: no secrets in image layers)
- `kill_switch.json`, `*.log`, `logs/`, `tmp/`, `LICENSE`, `README.md`, `CLAUDE.md`
- Additional Python cache dirs: `.mypy_cache`, `.ruff_cache`, `htmlcov/`, `polytool.egg-info/`

Build context reduced from ~660 MB+ to ~12 MB of actual source code.

**Root Dockerfile cache fix (1B)**

Before: `COPY . .` before `pip install ".[all,ris]"` — every source edit busted the ~150-package dependency install layer.

After: Two-phase pattern:
1. `COPY pyproject.toml ./` + full `pip install ".[all,ris]"` with BuildKit pip cache mount (cached until pyproject.toml changes)
2. `COPY polytool/ packages/ tools/ services/ ./` (selective, not `COPY . .`)
3. `pip install --no-deps ".[all,ris]"` — fast metadata-only reinstall with pip cache mount

Also added BuildKit cache mounts for apt (`/var/cache/apt`, `/var/lib/apt/lists`). Added `# syntax=docker/dockerfile:1` header. Removed `--no-cache-dir` and `rm -rf /var/lib/apt/lists/*` (BuildKit handles both).

**`services/api/Dockerfile` cache mounts (1C)**

Layer ordering was already correct (requirements.txt before source copy). Added only:
- `# syntax=docker/dockerfile:1` header
- `--mount=type=cache` for apt and pip
- Removed `--no-cache-dir` and `rm -rf /var/lib/apt/lists/*`

`infra/n8n/Dockerfile` was not touched (already optimal: 3-line apk add, scoped context).

### Task 2: Dev log and documentation

- Dev log written: before/after build context analysis, layer cache improvement rationale, BuildKit cache mount explanation, orphan audit for `Dockerfile.bot`, operator cleanup commands (4 levels from light to deep)
- `CURRENT_STATE.md` updated with full record of all Docker hygiene changes

---

## Decisions Made

1. **Selective COPY vs COPY . .**: Use explicit directory copies (`polytool/`, `packages/`, `tools/`, `services/`) to make layer invalidation predictable and to ensure source edits don't bust the dep cache layer.

2. **Two-phase pip install**: First phase installs all deps with pyproject.toml only (stable, cached). Second phase reinstalls `--no-deps` after source copy to update entry point metadata. This is the correct pattern for editable-install equivalence without actual editable mode.

3. **Remove --no-cache-dir**: BuildKit's persistent pip cache mount (`/root/.cache/pip`) supersedes `--no-cache-dir`. Removing it allows wheels to be cached across rebuilds, saving PyPI round-trips.

4. **Dockerfile.bot left in place**: File is orphaned (no compose reference) and uses Python 3.12 (inconsistent). Documented status clearly; deletion deferred to operator decision. File may be useful as reference for future standalone bot image.

5. **infra/ excluded from root build context**: Safe because `n8n` service uses `context: ./infra/n8n` (its own scoped context, unaffected by root `.dockerignore`). The `api` service uses `context: .` but only needs `services/api/` and `packages/` which are not excluded.

---

## Build Matrix Results

| Check | Method | Result |
|---|---|---|
| `docker compose config` | `docker compose config --quiet` | PASS (exit 0) |
| Python CLI regression | `python -m polytool --help` | PASS |
| Full compose build | Deferred (Docker daemon not running in session) | SEE NOTE |

**Note:** Docker Desktop daemon was not accessible during this session (daemon not running). Full build matrix (5 paths) was verified in the preceding session `quick-260405-gef` for compose topology. The Dockerfile changes in this task (hygiene only) do not alter service topology, ports, volumes, or commands. `docker compose config --quiet` validates that compose YAML still parses correctly.

For validation with Docker running, execute:
```bash
DOCKER_BUILDKIT=1 docker compose up -d --build
docker compose ps
DOCKER_BUILDKIT=1 docker compose --profile ris-n8n up -d --build
docker compose down
docker compose --profile cli run --rm polytool python -m polytool --help
docker system df
```

---

## Deviations from Plan

### Auto-fixed Issues

None.

### Environment Limitation

**Docker daemon not running during session** — The plan called for running `docker compose build` and `docker compose up` to validate all paths. Docker Desktop was not accessible. Mitigated by:
- `docker compose config --quiet` confirms compose YAML is valid
- Dockerfile syntax is correct (verified by inspection and format check)
- Python regression confirms no host Python changes
- Prior full matrix from same-day session (quick-260405-gef) covered all 5 compose paths

This is not a deviation from the code changes — it is an environment state. The next session with Docker Desktop running should confirm the cache-optimized builds work as expected.

---

## Commits

| Task | Commit | Message |
|---|---|---|
| Task 1 | `f6773c0` | chore(quick-260405-j2t): tighten .dockerignore and add BuildKit cache mounts |
| Task 2 | `ae11c2a` | chore(quick-260405-j2t): write docker perf hygiene dev log and update CURRENT_STATE |

---

## Threat Flags

None. The `.env` exclusion from build context addresses T-quick-01 (information disclosure). BuildKit cache mounts are local-only (T-quick-02 accepted per plan threat model).

---

## Self-Check: PASSED

- [x] `.dockerignore` exists and contains new exclusions
- [x] `Dockerfile` has `# syntax=docker/dockerfile:1`, selective COPY, two-phase pip, cache mounts
- [x] `services/api/Dockerfile` has `# syntax=docker/dockerfile:1` and cache mounts
- [x] Dev log exists at `docs/dev_logs/2026-04-05_docker_perf_hygiene.md`
- [x] `CURRENT_STATE.md` updated with Docker hygiene record
- [x] Commits `f6773c0` and `ae11c2a` exist
- [x] `python -m polytool --help` passes
- [x] `docker compose config --quiet` passes
