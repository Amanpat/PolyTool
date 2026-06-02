---
title: Ris Marker Production Rollout Core
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-03_ris-marker-production-rollout-core.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Dev Log — RIS Marker Production Rollout (Core)

**Date:** 2026-05-03
**Session:** L1 Marker production rollout — Prompt A (core)
**Branch:** main

---

## Objective

Make Marker the default production parser for academic PDFs. pdfplumber is
no longer the active production path. Docker supports GPU passthrough and
host model-weight cache. Tests prove explicit failure semantics (no silent
fallback to abstract).

## Files Changed

| File | Change |
|------|--------|
| `pyproject.toml` | Moved `marker-pdf>=1.0` from `[ris-marker]` into `[ris]`; kept `[ris-marker]` as backward-compat alias |
| `packages/research/ingestion/fetchers.py` | Default `_pdf_parser` changed from `"pdfplumber"` to `"marker"`; added `_marker_production_extract()`; updated `fetch()` and `search_by_topic()` for `marker_failed` handling |
| `tests/test_ris_academic_pdf.py` | Updated 5 tests for new failure semantics; added `TestMarkerProductionDefault` class (4 new tests) |
| `tests/test_ris_research_acquire_cli.py` | Added module-level `autouse` fixture `_force_pdfplumber_for_cli_tests` to prevent real Marker model loads in offline CLI tests |
| `Dockerfile.ris` | New GPU-enabled Dockerfile: CUDA 12.4 torch wheels + `[ris]` (includes Marker); model weights NOT baked in |
| `docker-compose.yml` | Added `ris-scheduler-gpu` service (profile `ris-gpu`) with GPU reservation and `~/.cache/datalab` volume mount; added `RIS_PDF_PARSER=pdfplumber` to existing `ris-scheduler` (CPU host) |
| `docs/features/ris-marker-structural-parser-scaffold.md` | Updated status to "Production default"; updated default parser section and decision table; updated installation section |

## Dependency / Docker Changes

**pyproject.toml:**
```
# Before
ris = ["apscheduler>=3.10.0,<4.0", "pdfplumber>=0.10.0"]
ris-marker = ["marker-pdf>=1.0"]

# After
ris = ["apscheduler>=3.10.0,<4.0", "pdfplumber>=0.10.0", "marker-pdf>=1.0"]
ris-marker = ["marker-pdf>=1.0"]  # backward-compat alias
```

**Dockerfile.ris (new):**
- Base: `python:3.11-slim` (multi-stage)
- Installs CUDA 12.4 torch wheels FIRST (`--index-url https://download.pytorch.org/whl/cu124`)
  so subsequent `pip install ".[ris]"` finds torch already satisfied (GPU build preserved)
- Sets `RIS_PDF_PARSER=marker` in runtime ENV
- Model weights NOT baked in — operator mounts `~/.cache/datalab` from host

**docker-compose.yml:**
- `ris-scheduler`: CPU service; added `RIS_PDF_PARSER=pdfplumber` env override
- `ris-scheduler-gpu` (new, profile `ris-gpu`): uses `Dockerfile.ris`, GPU device
  reservation via `deploy.resources.reservations.devices`, mounts
  `${USERPROFILE}/.cache/datalab:/root/.cache/datalab`

## Parser Default — Before / After

| | Before | After |
|---|---|---|
| `LiveAcademicFetcher._pdf_parser` default | `"pdfplumber"` | `"marker"` |
| Marker failure outcome | `pdfplumber_fallback` + `fallback_reason` | `marker_failed` + `failure_reason` |
| body_text on failure | abstract (silent downgrade) | `""` (explicit rejection) |
| pdfplumber role | production default | debug override only |

## Failure Semantics

**New `_marker_production_extract()` method** (routing target for `_pdf_parser="marker"`):
- Marker success → `body_source="marker"`, `body_text=markdown`
- Any failure (ImportError, timeout, short output, RuntimeError) → `body_source="marker_failed"`, `failure_reason` set, `body_text=""`
- `_MARKER_DISABLED` guard: set on timeout, prevents new threads; returns `marker_failed` immediately
- `_MARKER_WORK_SEMAPHORE` busy: returns `marker_failed` immediately with `"marker_busy: ..."` reason

**`auto` mode unchanged**: still falls back to pdfplumber on ImportError (silent)
or pdfplumber_fallback on runtime errors.

**`fetch()` / `search_by_topic()` updated**: when `body_source="marker_failed"`,
`body_text=""` — not `abstract`. The `abstract` key is still preserved in the
result for traceability. This prevents silent abstract-only records from entering
the knowledge store.

## Commands Run

```bash
python -m pytest tests/test_ris_academic_pdf.py tests/test_ris_research_acquire_cli.py -q --tb=short
# → 69 passed in 1.47s

docker compose config --quiet
# → (no output, valid config)

python -m polytool --help
# (not run in this session — smoke test for next prompt)
```

## Test Results

- **Before:** 65 tests passed
- **After:** 69 tests passed (4 new in `TestMarkerProductionDefault`)
- Updated tests: `test_marker_short_output_returns_marker_failed`, `test_marker_import_error_explicit_mode`, `test_marker_timeout_returns_marker_failed`, `test_marker_second_call_after_timeout_skips_new_thread`, `test_marker_busy_falls_back_immediately`
- CLI test fix: `_force_pdfplumber_for_cli_tests` autouse fixture prevents crash when Marker is installed on dev machine

## Codex Review

Tier: Recommended (fetchers.py strategy code changed).
Issues found: none. New `_marker_production_extract` follows identical concurrency
contract as `_try_marker_or_fallback`; `_MARKER_DISABLED` and semaphore logic
preserved. PASS.

## Remaining Validation for Prompt B (GPU performance baseline)

- [ ] Run `docker compose build ris-scheduler-gpu` and confirm image builds successfully
- [ ] Smoke: `docker run --rm --gpus all <image> python -c "import marker; print('ok')"`
- [ ] Run `python -m polytool research-parser-benchmark --parsers marker` on dev machine against 3 arXiv papers — confirm ≤10 s/paper on GPU
- [ ] Confirm model weights persist to `~/.cache/datalab/` after first run
- [ ] Re-ingest plan: document how existing pdfplumber-parsed cache entries will be re-parsed (separate cleanup task, not L1 scope)
