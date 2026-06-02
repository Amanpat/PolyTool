---
title: Academic Validation Smoke After Triage
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-17_academic-validation-smoke-after-triage.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Academic Pipeline Smoke Test — Post-Triage Verification

**Date:** 2026-05-17  
**Type:** Execution record — smoke test  
**Track:** Research Intelligence System — L1/L2  
**Prerequisite:** `docs/dev_logs/2026-05-17_academic-validation-triage-fixes.md`

---

## Objective

Run 4 curated papers through the full Marker pipeline (fetch → parse → body sidecar → index-done → research-query) using the triage-fixed container configuration. Confirm Blockers 1, 3, and 5 are resolved in practice. Do not run the full 29-paper corpus.

---

## Files Changed

| File | Action | Reason |
|------|--------|--------|
| `packages/__init__.py` | Created (empty) | Smoke exposed missing root `__init__.py` — without it, Python finds the old site-packages `packages` package before the live-mounted `/app/packages`. Adding this makes `packages/` a regular package so the live mount takes precedence. |
| `docs/dev_logs/2026-05-17_academic-validation-smoke-after-triage.md` | Created | This dev log |

No source logic, config, baselines, or L3 enforce settings were changed.

---

## Pre-flight Checks

### Git Branch / Status
```
Branch: main (1 commit ahead of origin)
Modified (triage fixes, uncommitted):
  .gitignore, docker-compose.yml
  packages/research/ingestion/fetchers.py
  packages/research/ingestion/marker_ipc_worker.py
  tests/test_ris_fetchers.py
Untracked:
  docs/dev_logs/2026-05-17_academic-validation-triage-fixes.md
  docs/dev_logs/2026-05-17_academic-validation-smoke-after-triage.md (this file)
```

### CURRENT_STATE.md Review
The "Scaled Validation Triage" section (line 1976) accurately describes the current state. Minor factual inaccuracy: it says "2 clean parses" but Batch 1 final result was 7 clean parses. Does not overstate readiness; left unchanged.

### CLI Load
```
python -m polytool --help → OK
research-marker-queue, index-done, research-query all present
```

### Docker Desktop
- Initially not running. Started by operator on request.
- Container `polytool-ris-scheduler-gpu` was up but using 24h-old config (no live source mounts).
- ClickHouse started (`docker compose up -d clickhouse`) to satisfy `depends_on`.
- Container force-recreated: `docker compose --profile ris-gpu up -d --force-recreate ris-scheduler-gpu`

### Volume Mount Verification (after recreate)
```
D:\...\artifacts → /app/artifacts   ✅
D:\...\kb → /app/kb                 ✅
~/.cache/datalab → /home/polytool/.cache/datalab  ✅
D:\...\packages → /app/packages     ✅ NEW (Blocker 3 fix)
D:\...\tools → /app/tools           ✅ NEW (Blocker 3 fix)
D:\...\cache → /app/cache           ✅ NEW (Blocker 4 fix)
```

### GPU Status
```
RTX 2070 SUPER | 8192 MiB VRAM | CUDA 13.2 | Driver 595.97
GPU-Util: 7% (idle) | Memory: 1462 MiB used at start
```

### Code Fix Verification (inside container)
```
_persist_body_sidecar  in marker_queue.py          → 2 hits ✅
index-done/index_done  in research_marker_queue.py → 6 hits ✅
WORKER_PAGE_THRESHOLD  in marker_ipc_worker.py     → 2 hits ✅
_fetch_arxiv_api       in fetchers.py              → 6 hits ✅
```

### Container Env Vars
```
WORKER_PAGE_THRESHOLD=999999         ✅ (Blocker 1)
RIS_PDF_PARSER=marker                ✅
TORCHINDUCTOR_CACHE_DIR=/app/cache/torchinductor  ✅ (Blocker 4)
```

---

## Additional Blocker Encountered: packages/__init__.py Missing

**Symptom:** `warm-process` inside the container immediately failed:
```
ModuleNotFoundError: No module named 'packages.research.ingestion'
```

**Root cause:** The Docker image (built 2026-05-08, before L1 Marker rollout) has `packages.research` installed in site-packages but WITHOUT the `ingestion/` subdirectory. The live source mount `./packages:/app/packages` puts the current `packages/research/ingestion/` at `/app/packages/research/ingestion/`. However, `packages/` in the repo has no `__init__.py`, making it a namespace package. Python's import system finds the site-packages regular package (`packages/__init__.py` is present there but has no `ingestion/`) before the namespace package at `/app/packages/`. Result: import fails.

**Fix:** Added empty `packages/__init__.py` to the repo root packages directory. This makes the local `packages/` directory a regular package, which Python finds via `''` (current dir) in sys.path before site-packages.

**Scope justification:** This is a configuration fix that the smoke exposed. Not implementation code. The site-packages `packages/__init__.py` is also empty. No functional change.

**Test regression check:** 216 passed, 1 skipped, 0 failed in RIS test suite after the addition.

---

## Smoke Paper Selection

| # | arXiv ID | Category | Reason | Expected difficulty |
|---|----------|----------|--------|---------------------|
| 1 | 1106.5040 | eq-heavy | Previously successful in Batch 1 — tests sidecar write path | High |
| 2 | 1810.04383 | eq-heavy | Previously HTTP 429 (max attempts exhausted) — tests arXiv retry fix | High |
| 3 | 1609.03471 | tbl-heavy | Not attempted in Batch 1 — tests different format group | Medium-High |
| 4 | 2510.05533 | prose/survey | Not attempted — tests prose format and different content type | Medium |

Enqueued to fresh isolated queue: `artifacts/research/smoke_test_queue/`

---

## Warm-Process Run

**Command (inside container):**
```bash
docker exec polytool-ris-scheduler-gpu sh -c "cd /app && python -m polytool \
  research-marker-queue --queue-dir /app/artifacts/research/smoke_test_queue \
  warm-process --max-items 4 --marker-timeout 3600"
```

**Result: 4/4 PASS, 0 failed**

### Per-Paper Parse Metrics

| # | arXiv ID | Category | pages | ocr_batches | parse_s | body_len | ipc | marker_ready | failure |
|---|----------|----------|-------|-------------|---------|----------|-----|--------------|---------|
| 1 | 1106.5040 | eq-heavy | 22 | 110 | 2771 | 67,440 | True | True | None |
| 2 | 1810.04383 | eq-heavy | 36 | 286 | 3279 | 116,221 | True | True | None |
| 3 | 1609.03471 | tbl-heavy | 36 | — | 53 | 61,281 | True | True | None |
| 4 | 2510.05533 | prose | 31 | — | 12 | 93,720 | True | True | None |

**Key timing observation:** Papers 1 and 2 each triggered a JIT cold-start (~46 min and ~55 min respectively), indicating different page-format groups. Papers 3 and 4 ran at 53s and 12.5s — their formats had already been compiled by papers 1 and 2. In-session JIT reuse is highly effective when the same format groups appear across papers.

### Blocker 1 Verification — Daemon Process Chain
- **Status: FIXED ✅**
- No "daemonic processes are not allowed to have children" errors in any of the 4 papers.
- `WORKER_PAGE_THRESHOLD=999999` confirmed active via container env; IPC warm-worker ran all 4 papers without subprocess crash.

### Blocker 5 Verification — arXiv Rate-Limiting
- **Status: NOT TRIGGERED (favorable finding)**
- Papers 2, 3, and 4 all fetched from arXiv successfully on the first attempt with no 429 errors.
- Reason: sequential processing with long inter-paper gaps (paper 1 took 46 min) means the arXiv rate-limit window resets naturally between fetches.
- The `_fetch_arxiv_api()` retry code is correct and tested (5 offline tests pass), but the retry did not need to fire in this run. The retry path will be exercised when rapid consecutive fetches are attempted (e.g., if papers are pre-fetched in a batch before warm-process starts).
- **Practical recommendation:** For the 29-paper full rerun, pre-enqueue all papers in one batch (`enqueue` calls are lightweight) then start a single `warm-process --max-items 29` session. The arXiv API is only called once per paper during the warm-process fetch step, not during enqueue with `--title`.

---

## Body Sidecar Verification — Blocker 3

### Blocker 3 Verification — Stale Container Image
- **Status: FIXED ✅**
- All 8 sidecar files confirmed present inside container:

```
/app/artifacts/research/smoke_test_queue/bodies/
  arxiv:1106.5040.body.txt    (67585 bytes confirmed via wc -c)
  arxiv:1106.5040.meta.json
  arxiv:1810.04383.body.txt
  arxiv:1810.04383.meta.json
  arxiv:1609.03471.body.txt
  arxiv:1609.03471.meta.json
  arxiv:2510.05533.body.txt
  arxiv:2510.05533.meta.json
```

### Windows-Specific Finding: Colon in Candidate ID Filenames

**Symptom:** Running `index-done` from the Windows host Python reported "body file missing" for all 4 papers. Host-side `os.listdir()` raised `UnicodeEncodeError` with character `` (fullwidth colon ：).

**Root cause:** NTFS treats `:` in filenames as an Alternate Data Stream (ADS) separator. Docker (via WSL2 virtiofs) writes the files with regular Linux `:` colons. On the Windows host, Python's `open('arxiv:1106.5040.body.txt')` interprets `arxiv` as the file and `1106.5040.body.txt` as the stream name, failing to open a regular file.

**Fix:** Run `index-done` inside the Docker container, where Linux paths use regular colons:
```bash
docker exec polytool-ris-scheduler-gpu sh -c "cd /app && python -m polytool \
  research-marker-queue --queue-dir /app/artifacts/research/smoke_test_queue \
  index-done"
```

**Impact on full 29-paper rerun:** index-done MUST be run inside the container. The runbook Step 4b should be updated to reflect this.

---

## Blocker 4 Verification — Persistent JIT Cache

- **Status: UNCERTAIN ⚠️**
- `/app/cache/torchinductor` volume exists and is mounted correctly.
- After papers 1 and 2 completed (each with full JIT cold-starts), the directory contains 0 bytes.
- No JIT cache files found anywhere on the container filesystem.
- PyTorch version inside container: **2.11.0+cu130**
- `TORCHINDUCTOR_CACHE_DIR=/app/cache/torchinductor` is set in the container env.
- **Hypothesis:** PyTorch 2.11.0 may not write Inductor cache to disk for the surya OCR model pipeline (surya may use Triton compilation, which has a separate `TRITON_CACHE_DIR` mechanism). Or the cache-write path is conditional on a compile threshold not reached with the current model configuration.
- **Practical impact:** JIT cold-starts will repeat after any container restart. Papers sharing format groups within a single warm-process session DO benefit from in-session kernel reuse (confirmed by papers 3 and 4 at 53s and 12.5s). Running all 29 papers in a single `--max-items 29` session without container restart is therefore critical.
- **Required follow-up:** Investigate whether `TRITON_CACHE_DIR` or a different env var controls surya's kernel cache in PyTorch 2.11.0. Out of scope for this smoke packet.

---

## Index-Done Results (run inside container)

```
Indexed 4 paper(s):
  [OK] arxiv:1106.5040  doc_id=c30c...  chunks=30  claims=147
  [OK] arxiv:1810.04383 doc_id=d394...  chunks=44  claims=215
  [OK] arxiv:1609.03471 doc_id=b943...  chunks=29  claims=145
  [OK] arxiv:2510.05533 doc_id=987d...  chunks=34  claims=167

Total: 4 examined — 4 indexed, 0 already-indexed, 0 no-body, 0 failed, 674 claim(s) extracted.
```

All chunk counts ≥ 5 (acceptable threshold). No silent fallbacks.

---

## KnowledgeStore State (Post-Smoke)

| Metric | Pre-smoke | Post-smoke | Delta |
|--------|-----------|-----------|-------|
| Academic docs total | 74 | 78 | +4 |
| Marker-indexed docs | 3 | 7 | +4 |
| Total derived_claims | 519 | 1193 | +674 |

---

## Research-Query Retrieval Probes

The L2 research-query uses conservative lexical (substring) matching. Multi-word phrase queries that don't appear verbatim in claim text return empty. Single or two-word domain terms work reliably.

| Probe | Query | had_fallback | claims | marker_hits | Papers hit |
|-------|-------|--------------|--------|-------------|-----------|
| 1 | "inventory" | **False** | 36 | 2 | 1106.5040, 1810.04383 |
| 2 | "order book" | **False** | 11 | 5 | 1106.5040, 1810.04383 |
| 3 | "prediction markets" | **False** | 9 | 2 | 1609.03471 |
| 4 | "language model" | **False** | 20 | 1 | 2510.05533 |
| 5 | "Polymarket" | **False** | 11 | 1 | existing paper |

**4/4 smoke papers are retrievable** via domain-appropriate queries. `had_fallback=False` on all probes that use terms present in claim text.

Note: Longer descriptive phrases ("optimal bid-ask spread market making", "prediction market calibration information aggregation") return empty because the lexical matcher requires verbatim substring presence. This is a known property of the L2 lexical-only retrieval path (L2.1 ChromaDB semantic retrieval deferred per spec).

---

## Confirmation: No Silent Fallback

- All 4 papers: `body_source=marker` (no pdfplumber fallback)
- All 4 papers: `marker_ready=True`
- All 4 papers: `failure_reason=None`
- `index-done`: 0 no-body, 0 failed
- No "daemonic processes" error in warm-process stdout

---

## Blocker Status Summary (Post-Smoke)

| # | Description | Status |
|---|-------------|--------|
| 1 | pdftext daemon process chain | **FIXED ✅** — no crashes across 4 papers |
| 2 | CUDA JIT per-format cold-start | **CONFIRMED PERSISTENT** — papers 1 and 2 each took ~46-55 min; in-session reuse works (papers 3 and 4: 53s and 12.5s) |
| 3 | Stale container image | **FIXED ✅** — all 8 body sidecars written |
| 4 | No persistent JIT cache | **UNCERTAIN ⚠️** — TORCHINDUCTOR_CACHE_DIR empty; PyTorch 2.11 may use different mechanism |
| 5 | arXiv API rate-limiting | **NOT TRIGGERED** — retry code correct, natural gap prevented 429s |

**Additional findings (not in original triage):**
- `packages/__init__.py` missing → ModuleNotFoundError with live mounts **[FIXED in this session]**
- `index-done` fails on Windows host (NTFS ADS colon issue) → must run inside container **[DOCUMENTED — runbook update required]**

---

## Runbook Update Required

Add to `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` Step 4b:

**Windows host note:** Due to NTFS ADS restrictions on colon characters in filenames, `index-done` must be run inside the Docker container when candidate IDs contain colons (`arxiv:...`):
```bash
docker exec polytool-ris-scheduler-gpu sh -c "cd /app && python -m polytool \
  research-marker-queue --queue-dir /app/artifacts/research/QUEUE_DIR index-done"
```
Running `index-done` from the Windows host Python will report "body file missing" for all papers.

---

## Recommendation: Full 29-Paper Rerun

**CONDITIONALLY SAFE** — with the following mandatory constraints:

1. Add `packages/__init__.py` (done in this session).
2. Force-recreate the container before the run to pick up the current docker-compose.yml mounts.
3. Enqueue all 29 papers from the host. Enqueue is fast and doesn't hit the arXiv PDF endpoint.
4. Run `warm-process --max-items 29 --marker-timeout 3600` with ONE single docker exec session inside the container — do NOT restart the container mid-run (kills in-session JIT reuse).
5. Run `index-done` inside the container (not from the Windows host).
6. Use `scaled_validation_queue_v2/` to preserve Batch 1 metrics.

**Expected timing for full 29-paper rerun:**
- Assume ~8 distinct format groups across 29 papers.
- First paper per format group: ~45-55 min cold-start.
- Remaining papers per format group: ~1-10 min (warm).
- Estimated total: 8 × 50 min + 21 × 5 min = ~505 min ≈ 8.5 hours.
- Run should be started and left overnight.

**Not safe without:**
- Resolving Blocker 4 (JIT cache persistence): if the container is restarted for any reason during the run, all format groups restart from cold. Running all 29 in one session is the current mitigation.

---

## Corpus-Level Acceptance Criteria (Smoke)

| Criterion | Target | Result |
|-----------|--------|--------|
| No silent fallbacks | All failures explicit | ✅ 0 failures |
| No unclassified no-body | All classified | ✅ N/A |
| All failures triaged | — | ✅ N/A |
| Query citations returned (≥4 of 5 probes) | ≥4 | ✅ 4/5 probes returned marker citations |
| Corpus metrics: no_body_count ≤ 3 | ≤ 3 | ✅ 0/4 |
| had_fallback_rate < 10% | < 10% | ✅ 0% |
| low_chunk_suspicious_count ≤ 2 | ≤ 2 | ✅ 0/4 (all ≥ 29 chunks) |

**Smoke classification: PASS** — all acceptance criteria met for the 4-paper smoke scope.

---

## Codex Review

Tier: Skip (per policy) — only `packages/__init__.py` (empty file) changed. No strategy, execution, or financial logic modified. No review required.

---

## Open Items

1. **Blocker 4 (JIT cache persistence):** Investigate whether `TRITON_CACHE_DIR` controls surya's OCR kernel cache in PyTorch 2.11.0. If so, add to docker-compose env and `./cache` volume. Separate investigation session.
2. **Runbook update:** Document the Windows `index-done` container-exec requirement in `RIS_MARKER_QUEUE_RUNBOOK.md` Step 4b.
3. **Full 29-paper Batch 2 rerun:** Run when an overnight window is available. Use `scaled_validation_queue_v2/` per the command in the triage dev log, modified to exec inside the container.
4. **arXiv retry path exercise:** The `_fetch_arxiv_api` retry code was not triggered in this smoke (natural pacing prevented 429s). Batch 2 with 29 papers may trigger 429s if arXiv API is called rapidly; the retry fix is untested under actual 429 conditions in Docker. Monitor first 15 papers' arXiv fetch logs carefully.
