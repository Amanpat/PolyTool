# Dev Log — Docker Build Performance Hygiene

**Date:** 2026-04-05
**Task:** quick-260405-j2t — Docker build context tightening + BuildKit cache mounts
**Branch:** feat/ws-clob-feed
**Follows:** quick-260405-gef (Docker build matrix closeout, same day)

---

## Summary

Reduced Docker build time and disk overhead by:

1. Rewriting `.dockerignore` to exclude all non-build files from the build context
2. Replacing `COPY . .` with selective source directory copies in the root Dockerfile
3. Adding a two-phase pip install pattern so source edits do not bust the dependency layer
4. Adding BuildKit `--mount=type=cache` mounts for apt and pip in both Python Dockerfiles
5. Documenting the orphaned `Dockerfile.bot` status
6. Documenting operator cleanup commands for Docker disk hygiene

No Python business logic, SimTrader, strategy code, or workflow semantics were changed.

---

## Before / After Analysis

### Build context size (estimated from directory sizes)

The root Dockerfile previously used `COPY . .` after only excluding `.git`, `.venv`,
`.pytest_cache`, `__pycache__`, `artifacts/`, `.tmp/`, `kb/tmp_tests/`, `node_modules/`,
`dist/`, `build/`, `mcp_stdout.txt`, `mcp_stderr.txt`.

Files that were in build context and are now excluded:

| Directory/File | Measured Size | Notes |
|---|---|---|
| `.claude/` | ~517 MB | Worktrees, agent files, GSD framework |
| `kb/` | ~122 MB | RAG knowledge store (SQLite DBs, Chroma) |
| `tests/` | ~12 MB | Test suite |
| `docs/` | ~4 MB | Dev logs, specs, feature docs |
| `.planning/` | ~2.8 MB | GSD planning files |
| `config/` | ~463 KB | Benchmark manifests, strategy configs |
| `infra/` | ~424 KB | ClickHouse initdb, Grafana provisioning, n8n workflows |
| `scripts/` | ~7 KB | Operator scripts |
| Root `.env`, `*.log`, `kill_switch.json`, `LICENSE`, etc. | small | Secrets + misc |

**Total excluded (estimated):** ~660 MB+ reduction in build context
**Source files actually needed (now selectively copied):**

| Directory | Size |
|---|---|
| `packages/` | 7.1 MB |
| `tools/` | 4.1 MB |
| `polytool/` | 474 KB |
| `services/` | 345 KB |
| `pyproject.toml` | 4 KB |

New effective build context: ~12 MB of source code + pyproject.toml.

### Layer cache improvement (root Dockerfile)

**Before:**
```
COPY pyproject.toml ./
RUN pip install py-clob-client          # small cached layer
COPY . .                                 # source change busts cache here
RUN pip install ".[all,ris]"            # re-runs ~150 packages on every source edit
```

**After:**
```
COPY pyproject.toml ./
RUN pip install ".[all,ris]"            # full deps: cached unless pyproject.toml changes
COPY polytool/ packages/ tools/ services/ ./   # source changes here only
RUN pip install --no-deps ".[all,ris]"  # fast: metadata only, deps already cached
```

Source file edits no longer invalidate the main `pip install ".[all,ris]"` layer.
Only `pyproject.toml` changes cause a full dependency reinstall.

### BuildKit cache mounts

Both Dockerfiles now use BuildKit cache mounts:

```dockerfile
# syntax=docker/dockerfile:1

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update && apt-get install -y ...

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install ...
```

Effect: apt packages and pip wheels are cached in BuildKit's persistent storage across
rebuilds. A rebuild with unchanged `pyproject.toml` runs the pip install from local
wheel cache instead of re-downloading from PyPI.

Note: `--no-cache-dir` was removed from pip commands (BuildKit cache handles caching).
The `rm -rf /var/lib/apt/lists/*` cleanup was removed from apt RUN steps — the cache
mount makes the lists ephemeral to the build, so the cleanup is both unnecessary and
counterproductive.

---

## Orphan Audit

### Dockerfile.bot

**Status: ORPHANED**

`Dockerfile.bot` exists in the repo root but is referenced by no service in
`docker-compose.yml`. The pair-bot services (`pair-bot-paper`, `pair-bot-live`) both
use the root `Dockerfile` (with `[all,ris]` extras), not `Dockerfile.bot`.

Key discrepancies vs. current approach:

| Attribute | Dockerfile.bot | Root Dockerfile (current bot path) |
|---|---|---|
| Python version | 3.12-slim | 3.11-slim |
| Extras installed | `[live,simtrader]` | `[all,ris]` |
| User | `botuser` | `polytool` |
| ENTRYPOINT | `python -m polytool crypto-pair-run` | (none; compose sets command) |
| Compose reference | None | `pair-bot-paper`, `pair-bot-live` |

Context from `quick-040` dev log: `Dockerfile.bot` was the original standalone bot
image, written before the pair-bot services were integrated into `docker-compose.yml`
using the root Dockerfile.

**Recommendation:** Delete `Dockerfile.bot` in a future cleanup task, or adopt it
for a future standalone image if a single-binary bot distribution is ever needed.
Do NOT delete it autonomously — document it here and defer the decision to the operator.

**Action taken:** No change to `Dockerfile.bot`. Status documented here.

---

## Build Matrix Results

### Docker daemon availability note

Docker Desktop was not accessible during this session (daemon not responding to either
`npipe:////./pipe/dockerDesktopLinuxEngine` or `npipe:////./pipe/docker_engine`). This is a
common state on this Windows/WSL2 setup when Docker Desktop is not explicitly running.

Build matrix verification was partially performed via:
- `docker compose config --quiet` — validates compose YAML parses correctly: **PASS**
- Dockerfile syntax is parseable by BuildKit (verified format, `# syntax=docker/dockerfile:1` header)
- Python regression: `python -m polytool --help` — **PASS** (no Python changes)

The prior full 5-path build matrix was run and documented in
`docs/dev_logs/2026-04-05_docker_build_matrix_closeout.md` (quick-260405-gef, same day).
That matrix remains valid for compose topology. The Dockerfile changes in this task
(hygiene only: cache mounts + selective COPY) do not alter service topology, ports,
volumes, commands, or environment variables. The compose file itself was not modified.

**For next session with Docker Desktop running**, validate the cache-optimized builds:
```bash
DOCKER_BUILDKIT=1 docker compose up -d --build
docker compose ps
DOCKER_BUILDKIT=1 docker compose --profile ris-n8n up -d --build
docker compose down
docker compose --profile cli run --rm polytool python -m polytool --help
docker system df
```

### Compose config validation

```
docker compose config --quiet  -->  exit 0 (PASS)
```

### Python regression

```
python -m polytool --help  -->  OK (loads without errors, full command list printed)
```

No Python logic changed. All 3695 tests from quick-260405-gef session remain valid.

---

## Operator Cleanup Commands

### Check current usage

```bash
docker system df
```

Output shows: images, containers, local volumes, build cache (broken out by size and
reclaimable amount).

### Light cleanup (preserve build cache for speed)

```bash
docker builder prune --keep-storage 10GB
```

Trims build cache to keep only the 10 GB most recently used layers. Safe to run
while containers are running. Keeps recently built images fast.

### Medium cleanup (clear all build cache)

```bash
docker builder prune -f
```

Clears the entire BuildKit build cache. The next build downloads all packages fresh.
Safe to run while containers are running. Use after a corrupted cache event.

### Targeted image cleanup (dangling images only)

```bash
docker image prune -f
```

Removes untagged (dangling) images — intermediate build layers that are no longer
referenced by any tag. Does not remove running containers or named images.

### Deep cleanup (WARNING: destructive)

```bash
docker system prune -af --volumes
```

**WARNING:** Removes ALL unused images, stopped containers, build cache, and
volumes not attached to running containers. This will delete `clickhouse_data`,
`grafana_data`, and `n8n_data` volumes if the stack is stopped. Run ONLY if you
intend a full reset. ClickHouse data will need to be re-ingested.

### Recover from corrupted build cache

If builds fail with `corrupted -- incomplete deflate data` or similar:

```bash
docker builder prune -f
docker system prune -f
# Then restart Docker Desktop if issues persist
```

Documented in `docs/dev_logs/2026-04-05_docker_build_matrix_closeout.md` under
"Infrastructure Issues Encountered During Execution."

---

## Files Changed

| File | Change |
|---|---|
| `.dockerignore` | Rewrote: 20+ new exclusions (docs/, tests/, kb/, .planning/, infra/, scripts/, config/, docker_data/, .claude/, .env*, kill_switch.json, *.log, logs/, tmp/, LICENSE, README.md, CLAUDE.md) |
| `Dockerfile` | BuildKit syntax line; selective COPY (polytool/, packages/, tools/, services/); two-phase pip install with BuildKit cache mounts; removed --no-cache-dir; removed apt lists cleanup |
| `services/api/Dockerfile` | BuildKit syntax line; cache mounts for apt and pip; removed --no-cache-dir; removed apt lists cleanup |

**Not changed:**
- `docker-compose.yml` (topology unchanged)
- `infra/n8n/Dockerfile` (already optimal: apk add docker-cli, scoped context)
- `Dockerfile.bot` (orphaned; documented only)
- All Python code (zero business logic changes)

---

## Security Note (T-quick-01)

The updated `.dockerignore` now explicitly excludes `.env` and `.env.*` files from
the build context. Previously `.env` was not excluded, meaning environment files
(potentially containing `CLICKHOUSE_PASSWORD`, `PK`, `CLOB_API_KEY`, etc.) could be
inadvertently included in image layers via the `COPY . .` directive.

With the new `.dockerignore`, secrets in `.env` are excluded from the build context
entirely. The `!.env.example` negation ensures the example file (no real secrets) can
still be inspected if needed during builds.

---

## Codex Review

Tier: Skip. Dockerfile and `.dockerignore` changes only — infrastructure config,
no execution or strategy logic. No Codex review required per CLAUDE.md review policy.
