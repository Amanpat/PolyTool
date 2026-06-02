---
title: Ris Marker Production Rollout Validation
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-03_ris-marker-production-rollout-validation.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Dev Log — RIS Marker Production Rollout Validation (Prompt B)

**Date:** 2026-05-03
**Session:** L1 Marker production rollout — Prompt B (Codex fix resolution + GPU validation attempt)
**Branch:** main

---

## Objective

Resolve Codex FAIL blocking issues from `2026-05-03_codex-review-ris-marker-production-rollout.md`,
then validate Marker on Docker GPU with a live arXiv parse and 3-paper benchmark.

---

## Codex FAIL Blockers — Status

### Blocker 1: `marker_failed` not rejected end-to-end (RESOLVED)

**Root cause:** `AcademicAdapter.adapt()` did `body = body_text if body_text else abstract`.
When `body_source="marker_failed"`, `body_text=""` so it silently fell back to `abstract`,
creating an abstract-only ingest record that passed the hard-stop length check.

**Fix:** `packages/research/ingestion/adapters.py`

```python
body_source = raw_source.get("body_source", "")
if body_source == "marker_failed":
    body = ""   # explicit rejection — forces downstream hard-stop
else:
    body = body_text if body_text else abstract
    if not body:
        body = title
```

Also added `failure_reason` to the metadata propagation key list (Marker uses this key;
the older `fallback_reason` key remains for `auto` mode compatibility).

**Tests added:** `TestAcademicAdapterMarkerFailedRejection` (2 tests)
- `test_marker_failed_body_is_empty_in_adapter` — body="" + failure_reason propagated
- `test_marker_failed_abstract_not_used_as_body` — long abstract still does NOT become body

### Blocker 2: Scheduler split not implemented (RESOLVED)

**Root cause:** `start_research_scheduler()` registered all 8 jobs for every caller.
`docker-compose.yml` CPU `ris-scheduler` ran `research-scheduler start` with no filtering,
so `academic_ingest` ran on the CPU host with `RIS_PDF_PARSER=pdfplumber` — defeating
the entire production rollout.

**Fix — scheduler.py:**
Added `exclude_job_ids: Optional[list]` parameter to `start_research_scheduler()`.
When set, matching job IDs are skipped before `scheduler.add_job()` is called.

**Fix — research_scheduler.py CLI:**
Added `--exclude-jobs JOB_ID [JOB_ID ...]` flag to `research-scheduler start`.

**Fix — docker-compose.yml:**
Changed CPU `ris-scheduler` command to:
```
["python", "-m", "polytool", "research-scheduler", "start", "--exclude-jobs", "academic_ingest"]
```

**Tests added:** `tests/test_ris_scheduler_split.py` (5 tests)
- `test_no_exclusion_registers_all_jobs` — baseline: all 8 jobs registered
- `test_exclude_academic_ingest` — academic_ingest absent, all others present
- `test_exclude_multiple_jobs` — multiple job IDs excluded correctly
- `test_exclude_empty_list_registers_all` — empty list = no exclusions
- `test_scheduler_started` — `scheduler.start()` still called after exclusion

### Blocker 3: Cache mount targets `/root/` but container user is `polytool` (RESOLVED)

**Root cause:** `Dockerfile.ris` creates `USER polytool` (home `/home/polytool`).
`docker-compose.yml` mounted the host `~/.cache/datalab` at `/root/.cache/datalab`.
Marker resolves `~/.cache/datalab` as `/home/polytool/.cache/datalab` for the
`polytool` user — so the volume mount was a no-op and models would re-download
on every container start.

**Fix — docker-compose.yml:**
```yaml
- ${USERPROFILE}/.cache/datalab:/home/polytool/.cache/datalab
```

**Fix — Dockerfile.ris header comment:** Updated to reference correct target path.

---

## Non-blocking Fixes Applied

| Finding | Fix |
|---------|-----|
| Stale `_fetch_pdf_body` docstring listing `pdfplumber_fallback` / `pdf` as production values | Updated to reflect production mode values only |
| Feature doc: lifecycle diagram said "immediate pdfplumber" on `_MARKER_DISABLED` | Corrected to "immediate marker_failed" |
| Feature doc: raw_source `body_source` values table was stale | Updated to distinguish production vs auto-mode values; added `failure_reason` key |
| Feature doc: test coverage table | Updated with 3 new test classes and counts |
| Feature doc: deferred items | Removed resolved items; added GPU validation as PENDING with operator command |
| INDEX.md: Marker feature entry still said "Experimental / default pdfplumber" | Updated to reflect production-default status |

---

## Test Results

```
python -m pytest tests/test_ris_academic_pdf.py tests/test_ris_research_acquire_cli.py tests/test_ris_scheduler_split.py -q --tb=short
→ 76 passed in 1.21s

python -m pytest tests/ -x -q --tb=short
→ 2403 passed, 1 pre-existing failure (test_ris_claim_extraction actor mismatch — unrelated)
```

Pre-existing failure confirmed unrelated: `test_each_claim_has_required_fields` expects
`claim["actor"] == "heuristic_v1"` but receives `"heuristic_v2_nofrontmatter"` — a claim
extraction actor-string change from a prior session, not touched in this work.

---

## Docker / GPU Validation — PENDING

Docker Desktop was not running during this session. All Docker commands produced
0-byte output after backgrounding. Status:

| Step | Command | Result |
|------|---------|--------|
| Docker config | `docker compose --profile ris-gpu config --services` | ✅ 6 services (clickhouse, api, grafana, migrate, ris-scheduler, ris-scheduler-gpu) |
| Cache mount | `docker compose --profile ris-gpu config \| grep datalab` | ✅ target: `/home/polytool/.cache/datalab` (fix confirmed in config) |
| GPU image build | `docker build -f Dockerfile.ris -t polytool-ris-gpu .` | ⏳ PENDING (Docker not running) |
| GPU smoke | `docker run --rm --gpus all polytool-ris-gpu nvidia-smi` | ⏳ PENDING |
| Live arXiv parse | `research-acquire --url https://arxiv.org/abs/2510.15205` | ⏳ PENDING |
| 3-paper benchmark | `research-parser-benchmark --urls 2510.15205,2309.01454,2206.14965` | ⏳ PENDING |

### Operator: commands to run when Docker is available

```bash
# 1. Build GPU image
docker compose --profile ris-gpu build ris-scheduler-gpu

# 2. Confirm GPU passthrough
docker compose --profile ris-gpu run --rm ris-scheduler-gpu nvidia-smi

# 3. Confirm Marker imports in container
docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
  python -c "import marker; print('marker import ok')"

# 4. Live arXiv parse (first run downloads ~1-3 GB model weights to host cache)
docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
  python -m polytool research-acquire \
  --url "https://arxiv.org/abs/2510.15205" \
  --source-family academic

# 5. Warm 3-paper benchmark (run AFTER weights are cached from step 4)
docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
  python -m polytool research-parser-benchmark \
  --urls 2510.15205,2309.01454,2206.14965 \
  --parsers marker \
  --output-dir artifacts/benchmark/parser

# Acceptance gate: ≤10 s/paper warm on RTX 2070 Super
```

---

## Acceptance Verdict

| Gate | Status |
|------|--------|
| Marker is default and only parser (fetcher) | ✅ PASS |
| `marker_failed` → body="" in adapter (no abstract fallback) | ✅ PASS |
| Scheduler CPU/GPU split implemented | ✅ PASS |
| Docker cache mount correct (`/home/polytool/.cache/datalab`) | ✅ PASS |
| Stale pdfplumber comments/docs cleaned | ✅ PASS |
| Tests: adapter rejection + scheduler split | ✅ PASS (7 new, 76 targeted, 2403 full) |
| Docker GPU image builds | ⏳ PENDING |
| `nvidia-smi` smoke inside container | ⏳ PENDING |
| Live arXiv parse: `body_source=marker` | ⏳ PENDING |
| 3-paper warm benchmark ≤10 s/paper | ⏳ PENDING |

**Overall: NOT YET COMPLETE.** Code and infrastructure fixes are done. GPU validation
requires Docker Desktop running on the dev machine with RTX 2070 Super.

---

## Files Changed

| File | Change |
|------|--------|
| `packages/research/ingestion/adapters.py` | `marker_failed` explicit rejection; `failure_reason` key propagated |
| `packages/research/scheduling/scheduler.py` | `exclude_job_ids` parameter added to `start_research_scheduler()` |
| `tools/cli/research_scheduler.py` | `--exclude-jobs` flag added to `research-scheduler start` |
| `docker-compose.yml` | CPU scheduler `--exclude-jobs academic_ingest`; GPU cache mount `/home/polytool/.cache/datalab` |
| `Dockerfile.ris` | Header comment corrected (cache mount path) |
| `packages/research/ingestion/fetchers.py` | `_fetch_pdf_body` docstring updated (stale body_source values) |
| `docs/features/ris-marker-structural-parser-scaffold.md` | Lifecycle diagram, metadata table, test coverage, deferred items, dev log trail all updated |
| `docs/INDEX.md` | Marker feature entry updated; 3 new dev log entries added |
| `docs/CURRENT_DEVELOPMENT.md` | Feature 3 slot filled with L1 validation status |
| `docs/obsidian-vault/Claude Desktop/Current-Focus.md` | L1 status updated; session entry added |
| `tests/test_ris_academic_pdf.py` | `TestAcademicAdapterMarkerFailedRejection` (2 tests) |
| `tests/test_ris_scheduler_split.py` | New file — `TestSchedulerExcludeJobs` (5 tests) |

---

## Codex Review

Tier: Recommended (scheduler.py strategy routing changed; adapters.py ingestion logic changed).
Issues: None expected — changes are targeted fixes to Codex-identified blockers.
Background review recommended before GPU validation commit.
