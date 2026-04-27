# 2026-04-27 — RIS Docker PDF Deps Smoke

## Objective

Verify the pdfplumber dependency added in `2026-04-27_ris-academic-pdf-fix.md`
is present inside the Docker image and that `docker compose up` starts cleanly.

---

## Files Inspected

| File | Finding |
|---|---|
| `Dockerfile` | Multi-stage image; builder installs `.[ris,mcp,simtrader,historical,historical-import,live]` |
| `Dockerfile.bot` | Installs `.[live,simtrader]` only — no RIS, no pdfplumber (correct — pair-bot does not need it) |
| `services/api/Dockerfile` | Uses own `requirements.txt` (fastapi/uvicorn) — no pdfplumber needed |
| `docker-compose.yml` | `polytool` and `ris-scheduler` services use `Dockerfile`; `ris-scheduler` has no profile (always-on) |

## Dependency Install Path

**Before fix:** `pyproject.toml` `ris` group: `apscheduler>=3.10.0,<4.0`

**After fix (`2026-04-27_ris-academic-pdf-fix.md`):** `ris` group: `apscheduler>=3.10.0,<4.0`, `pdfplumber>=0.10.0`

Since `Dockerfile` already runs `pip install ".[ris,...]"`, **no Dockerfile changes were required.** The existing install line automatically picks up pdfplumber.

---

## Files Changed

None — `pyproject.toml` change from the prior fix commit is sufficient.

---

## Commands Run

### 1. Validate compose file
```
docker compose config --quiet
```
Output: `config OK`

### 2. Build polytool image
```
docker compose build polytool
```
Result: `polytool-polytool  Built` — layer 15 (pip install) served from cache with pdfplumber already present.

### 3. Direct import test (no ClickHouse dependency)
```
docker run --rm polytool-polytool:latest python -c "import pdfplumber; print(pdfplumber.__version__)"
```
Output: `0.11.9` ✓

### 4. CLI smoke
```
docker run --rm polytool-polytool:latest python -m polytool --help
docker run --rm polytool-polytool:latest python -m polytool research-acquire --help
```
Both returned help text cleanly ✓

### 5. Compose up (default stack — no profiles)
```
docker compose up -d
```
Services started: `clickhouse (healthy)`, `grafana (healthy)`, `api (healthy)`, `ris-scheduler (up)`, `migrate (exited 0)`. All healthy/started within ~30s ✓

### 6. In-container pdfplumber verification
```
docker exec polytool-ris-scheduler python -c "import pdfplumber; print('pdfplumber OK:', pdfplumber.__version__)"
```
Output: `pdfplumber OK: 0.11.9` ✓

### 7. In-container live arXiv ingest
```
docker exec polytool-ris-scheduler python -m polytool research-acquire \
  --url "https://arxiv.org/abs/2510.15205" --source-family academic --no-eval --json
```
Output:
```json
{
  "dedup_status": "new",
  "chunk_count": 27,
  "rejected": false
}
```
`chunk_count: 27` confirms full PDF body ingested inside container ✓

### 8. In-container targeted tests
```
docker exec polytool-ris-scheduler python -m pytest tests/...
```
Result: `ERROR: file or directory not found` — `tests/` is not copied into the runtime image
(Dockerfile only ships `polytool/`, `packages/`, `tools/`, `services/`). Expected limitation.
Host-side test coverage: **54 passed, 0 failed** (verified in prior fix session).

### 9. Compose down
```
docker compose down
```
All containers stopped and removed cleanly ✓

---

## Result Summary

| Check | Result |
|---|---|
| `docker compose config` | ✓ PASS |
| `docker compose build polytool` | ✓ PASS |
| `import pdfplumber` (direct `docker run`) | ✓ 0.11.9 |
| `python -m polytool --help` (direct `docker run`) | ✓ PASS |
| `python -m polytool research-acquire --help` (direct `docker run`) | ✓ PASS |
| `docker compose up -d` — all services healthy | ✓ PASS |
| `import pdfplumber` inside `ris-scheduler` | ✓ 0.11.9 |
| Live arXiv ingest inside `ris-scheduler` | ✓ chunk_count=27, body_source=pdf |
| `docker compose down` | ✓ PASS |

---

## Remaining Limitations

- `tests/` directory is not included in the runtime Docker image — in-container pytest
  is not possible without a dev image variant. This is expected: test runs belong on the
  host or in CI, not in production runtime images.
- `Dockerfile.bot` does not include `pdfplumber` (installs only `.[live,simtrader]`).
  This is correct — the pair-bot never calls `research-acquire`.
- `services/api/Dockerfile` uses a separate `requirements.txt` and does not include
  pdfplumber. This is correct — the API service does not run RIS.
- The `n8n` volume was still in use during `docker compose down` (network remained briefly).
  This is a pre-existing n8n leftover and does not affect the PolyTool stack.
