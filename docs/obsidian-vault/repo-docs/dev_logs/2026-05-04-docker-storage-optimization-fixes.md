---
title: Docker Storage Optimization Fixes
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-04_docker-storage-optimization-fixes.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Docker Storage Optimization — Codex PASS WITH FIXES Resolution

Date: 2026-05-04  
Scope: Resolve Codex PASS WITH FIXES findings from docker-storage-optimization review  
Status: Complete — .dockerignore future-proofed, packet scope documented, validations pass

---

## Codex Findings (from 2026-05-04_codex-review-docker-storage-optimization.md)

Verdict: PASS WITH FIXES

Non-blocking issues flagged:

1. **Unrelated benchmark diff in working tree.** `tools/cli/research_parser_benchmark.py`
   contains Marker failure-diagnosis improvements (added `failure_reason` field, `--verbose`
   flag, `_get_note()` helper, `traceback_text` field, full traceback capture) that are
   unrelated to Docker storage optimization. These were written in the same session as
   `docs/dev_logs/2026-05-03_ris-marker-gpu-failure-diagnosis.md` but not yet committed.
   Codex noted they should be committed separately from the Docker storage packet.

2. **Missing future-proof model/DB .dockerignore patterns.** The existing `.dockerignore`
   covers all current large runtime directories (`artifacts/`, `kb/`, `.venv`, caches).
   It did not include generic patterns for model cache dirs (`.cache/`, `.huggingface/`) or
   local database files (`*.duckdb`, `*.sqlite`, `*.sqlite3`, `*.db`) that could
   accumulate in the repo root if tooling defaults change.

---

## Resolution

### Finding 1 — Benchmark file packet separation

The `tools/cli/research_parser_benchmark.py` changes are **valid code** documented in
`docs/dev_logs/2026-05-03_ris-marker-gpu-failure-diagnosis.md` as part of the Marker
failure-diagnosis packet. They are NOT reverted — reverting would discard tested
diagnostics that are needed for the upcoming L1 GPU validation.

Action taken: the benchmark changes remain in the working tree as a separate pre-staged
unit. The Docker storage packet (`.dockerignore`, `Dockerfile.ris`, `docs/runbooks/docker_storage.md`,
`docs/dev_logs/2026-05-04_docker-storage-optimization.md`) must be committed without
including `tools/cli/research_parser_benchmark.py`.

Commit order required:
1. `fix(ris): L1 Marker benchmark diagnostics` — `tools/cli/research_parser_benchmark.py`
   + `docs/dev_logs/2026-05-03_ris-marker-gpu-failure-diagnosis.md`
   + `docs/dev_logs/2026-05-03_codex-rereview-ris-marker-production-rollout.md`
2. `chore(docker): storage optimization and runbook` — `.dockerignore`, `Dockerfile.ris`,
   `docs/runbooks/docker_storage.md`,
   `docs/dev_logs/2026-05-04_docker-storage-optimization.md`,
   `docs/dev_logs/2026-05-04_docker-storage-optimization-fixes.md`
   (this file)

### Finding 2 — Future-proof .dockerignore patterns

Added a new section to `.dockerignore`:

```
# Local model cache and database files (future-proof)
# Prevents accidental inclusion if a cache dir or DB file lands in the repo root.
.cache/
.huggingface/
*.duckdb
*.sqlite
*.sqlite3
*.db
```

Rationale:
- `.cache/` — generic tool cache dir (e.g. pip, pre-commit, huggingface, datalab if
  someone runs tooling from the repo root rather than the user profile)
- `.huggingface/` — HuggingFace model cache; some tools default to writing it in CWD
- `*.duckdb` — DuckDB database files; the repo uses DuckDB for historical queries and
  a `.duckdb` file could appear in the root if run from there
- `*.sqlite` / `*.sqlite3` — SQLite/SQLite3 files; the RIS knowledge store writes
  `knowledge.sqlite3` under `kb/` (already excluded via `kb/`), but a root-level file
  is possible during debugging or if paths shift
- `*.db` — generic database files

These patterns do not affect the build for the current repo layout (the build context is
already ~12 MB with the existing exclusions). They are preventive hygiene for future sessions.

---

## Files Changed

| File | Change |
|---|---|
| `.dockerignore` | Added `.cache/`, `.huggingface/`, `*.duckdb`, `*.sqlite`, `*.sqlite3`, `*.db` |
| `docs/dev_logs/2026-05-04_docker-storage-optimization-fixes.md` | This file (new) |

No changes to:
- `Dockerfile.ris` — already correct from prior session
- `docker-compose.yml` — already correct from prior session
- `docs/runbooks/docker_storage.md` — accurate as written; `.cache/` / `.huggingface/`
  additions do not require runbook updates since model weights remain host-mounted via
  `${USERPROFILE}/.cache/datalab`, outside the build context regardless of this rule
- `tools/cli/research_parser_benchmark.py` — not part of this packet

---

## Commands Run

```powershell
docker compose config --quiet
# exit 0

git diff --check
# exit 0 (only LF/CRLF line-ending warnings; no whitespace errors)
```

---

## Whether L1 Marker Validation Can Resume

Yes. The Docker storage packet is clean. The Codex blocker was scope hygiene, not a
functional issue. L1 Marker validation may resume after:

1. Committing the two packets in order (benchmark fix first, Docker storage second).
2. Verifying C: has ≥ 15 GB free: `(Get-PSDrive C).Free / 1GB`
3. Running the GPU rebuild and validation steps in `docs/runbooks/docker_storage.md` Section 9.

L1 is NOT shipped. Do not mark as shipped until Step 4 in Section 9 shows
`body_source=marker` and `body_length > 5000` for at least one paper.

---

## Codex Review

Tier: Skip (docs and .dockerignore only — no production code changed).
Issues found: None.
Issues addressed: N/A.
