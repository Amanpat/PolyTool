---
phase: quick-260405-kh2
plan: "01"
subsystem: docker
tags: [dockerfile, build, setuptools, devops]
dependency_graph:
  requires: []
  provides: [working-root-dockerfile-build]
  affects: [ris-scheduler, all-compose-services]
tech_stack:
  added: []
  patterns: [two-phase-pip-install-with-stubs]
key_files:
  created:
    - docs/dev_logs/2026-04-05_fix-root-dockerfile-layer-order.md
  modified:
    - Dockerfile
decisions:
  - "Expanded stub layer to cover all 24 declared package directories, not just polytool/"
  - "Used find+touch pattern to avoid listing each __init__.py path individually"
metrics:
  duration: "~25 minutes"
  completed: "2026-04-05"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 2
---

# Phase quick-260405-kh2 Plan 01: Fix Root Dockerfile Layer Order Summary

**One-liner:** Stub-creation RUN layer covering all 24 declared package directories fixes setuptools egg_info failure in deps-only pip install.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add stubs before deps-only pip install | 4d6b5e5, 103ac8a | Dockerfile |
| 2 | Write dev log | d77a53c | docs/dev_logs/2026-04-05_fix-root-dockerfile-layer-order.md |

---

## What Was Built

Fixed the root Dockerfile builder stage so `docker compose build` no longer fails with
setuptools errors. The two-phase pip install pattern (deps cached separately from source)
requires all package directories and README.md to exist before the first `pip install` runs.

Added a `RUN` stub layer between `COPY pyproject.toml ./` and the deps-only pip install:

```dockerfile
RUN echo "# PolyTool" > README.md \
    && mkdir -p polytool/reports \
    && mkdir -p packages/polymarket/rag \
    ... (all 24 declared package dirs) \
    && find polytool packages tools -type d -exec touch {}/__init__.py \;
```

Real source is copied in Layer 3 and overwrites all stubs. The `--no-deps` reinstall
corrects entry points and metadata.

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Expanded stub layer to cover all 24 declared package directories**
- **Found during:** Task 1 — first build attempt after inserting initial stub
- **Issue:** pyproject.toml declares 24 package directories under `[tool.setuptools] packages`.
  The plan spec only mentioned `polytool/` and `polytool/__init__.py`. Build still failed on
  `error: package directory './polytool/reports' does not exist` (the second package in the list),
  and would have continued failing for the remaining 22 packages.
- **Fix:** Expanded the stub `RUN` layer to `mkdir -p` every package directory declared in
  pyproject.toml, then used `find ... -exec touch {}/__init__.py` to create all stub inits.
- **Files modified:** Dockerfile
- **Commits:** 4d6b5e5 (initial stub), 103ac8a (expanded stub)

---

## Verification Results

**docker compose config:** Exit 0

**docker compose build ris-scheduler:** Exit 0
- Builder stage completed all 11 steps
- `pip install ".[ris,mcp,simtrader,historical,historical-import,live]"` succeeded
- `pip install --no-deps "[...]"` succeeded
- `polytool-ris-scheduler:latest` built and named

**python -m polytool --help:** Exit 0, CLI loads without import errors

---

## Known Stubs

None in the application code. The stub `__init__.py` files and `README.md` are build-time
artifacts only — overwritten by the real source COPY before the runtime image is assembled.

---

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes introduced.
Dockerfile change is build-time only.

---

## Self-Check: PASSED

- Dockerfile modified: FOUND
- Dev log created: FOUND
- Commits 4d6b5e5, 103ac8a, d77a53c: all present in git log
- docker compose build ris-scheduler: Exit 0 (verified during execution)
- python -m polytool --help: Exit 0 (verified during execution)
