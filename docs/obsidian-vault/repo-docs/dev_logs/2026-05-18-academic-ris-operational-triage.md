---
title: Academic Ris Operational Triage
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-18_academic-ris-operational-triage.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Academic RIS — Operational Triage Memo

**Date:** 2026-05-18  
**Type:** Post-interrupt analysis and operational triage  
**Track:** Research Intelligence System — L1/L2  
**Audience:** Aman (Director)  
**Prerequisite logs:**
- `docs/dev_logs/2026-05-17_academic-validation-triage-fixes.md` — 5-blocker triage
- `docs/dev_logs/2026-05-17_academic-validation-smoke-after-triage.md` — 4-paper smoke PASS
- `docs/dev_logs/2026-05-17_academic-scaled-validation-batch2-rerun.md` — Batch 2 start record

---

## Files Changed

| File | Action | Reason |
|------|--------|--------|
| `docs/dev_logs/2026-05-18_academic-ris-operational-triage.md` | Created | This memo |
| `docs/CURRENT_STATE.md` | Updated | Record Batch 2 partial outcome factually; remove any implied completeness |

---

## Logs Inspected

| Log | Size | What it told me |
|-----|------|----------------|
| `artifacts/research/scaled_validation_queue_v2/warm_process_batch2.log` | 191.9 KB | Full OCR progress for every paper attempted; timing per OCR batch |
| `artifacts/research/scaled_validation_queue_v2/results.jsonl` | — | 24 result records: per-paper fetch/parse outcomes, failure reasons, parse_seconds |
| `artifacts/research/scaled_validation_queue_v2/queue.jsonl` | — | Final queue state: 5 done, 5 failed, 1 processing (stuck), 18 pending |

---

## 1. What Happened in Batch 2

### Sequence Reconstruction (from results.jsonl + log)

The warm-process session ran for several hours inside the GPU container before the
background job was terminated by the Claude Code harness. The process continued
running in the container after the monitoring connection dropped, but was eventually
killed. The container-side log captured the full OCR run up to the kill point.

#### Papers processed in order:

| Seq | arXiv ID | Category | Status | parse_s | body_len | JIT group | Failure |
|-----|----------|----------|--------|---------|----------|-----------|---------|
| 1 | 1105.3115 | eq-heavy | **DONE** | 2377s | 82,458 | cold-start (261 OCR batches, 32 min) | — |
| 2 | 1106.5040 | eq-heavy | **DONE** | 2773s | 67,440 | warm (111 batches, 10.5 min) | — |
| 3 | 1605.01862 | eq-heavy | **DONE** | 1975s | 121,154 | cold-start #2 (110 batches, 49.5 min) | — |
| 4 | 1206.4810 | eq-heavy | **FAILED** | 0s | 0 | — | HTTP 429 × 3 (arXiv rate limit, all retries exhausted) |
| 5 | 1705.01446 | eq-heavy | **DONE** | 2365s | 111,431 | warm (45 batches, 40s) | Fetch failed × 2, succeeded attempt 3 |
| 6 | 2003.05958 | eq-heavy | **FAILED** | 0s | 0 | — | Timeout × 3 (arXiv, all retries exhausted) |
| 7 | 2203.13053 | eq-heavy | **FAILED** | 0s | 0 | — | HTTP 429 × 3 (arXiv, all retries exhausted) |
| 8 | 1810.04383 | eq-heavy | **FAILED** | 0s | 0 | — | HTTP 429 × 3 (arXiv, all retries exhausted) |
| 9 | 2409.02025 | eq-heavy | **FAILED** | 0s | 0 | — | Timeout × HTTP 429 × Timeout (all 3 exhausted) |
| 10 | 2307.14129 | eq-heavy | **DONE** | 2947s | 148,987 | cold-start #3 (281 batches, 32.5 min) | Fetch failed × 1, succeeded attempt 2 |
| 11 | 1011.6402 | tbl-heavy | **STUCK** | 3600s (timeout) | 0 | cold-start? | marker_timeout — parsing took >3600s; session killed mid-retry |
| 12–29 | remaining | tbl/prose/outlier | **PENDING** | — | — | — | Never reached |

#### Queue final state

```
done:       5   (all eq-heavy)
failed:     5   (all eq-heavy — fetch failures)
processing: 1   (1011.6402 — stuck after kill; needs enqueue --force to reset)
pending:    18  (11 table-heavy, 5 prose/survey, 4 outlier — never touched)
total:      29
```

### Root Causes

**Root cause A — arXiv rate limiting cascade (failure class: `error`)**

The fetch retry backoff (5s / 15s / 45s) is designed for isolated 429s. In practice,
once warm JIT reuse begins (papers 4+), warm papers complete in 40–60 seconds. Multiple
papers then try to fetch PDFs from `export.arxiv.org` in rapid succession, overwhelming
the rate-limit window. The 45s max backoff is shorter than arXiv's rate-limit reset
window under sustained load. Papers 1206.4810, 2003.05958, 2203.13053, 1810.04383, and
2409.02025 each exhausted all 3 fetch attempts. Note: **1810.04383 succeeded in the smoke
test** but failed here — confirming that rate limiting is session-density-dependent, not
paper-specific.

**Root cause B — Marker timeout on table-heavy paper (failure class: `timeout`)**

1011.6402 ("The Price Impact of Order Book Events" — NYSE TAQ empirical) hit the
`--marker-timeout 3600` limit and `marker_failed`. The paper may have an unusual layout
(scanned tables, embedded figures, multi-column dense data) that breaks the per-batch
budget. This is not an infra failure — it is a paper-format issue. The paper needs either
a longer timeout, a format-specific pre-check, or classification as "Marker-incompatible."

**Root cause C — Session kill without resume (structural)**

The background job was killed after several hours. There is no checkpoint or resume path.
All 18 pending papers (the entire non-eq-heavy corpus: all table-heavy, prose/survey,
outlier) remain unprocessed. The queue is resumable in principle (the `--force` recover
path exists) but requires another overnight session from scratch — including new JIT
cold-starts for any new format groups.

---

## 2. Proven State

These claims are supported by empirical evidence from the smoke test and/or Batch 2.

| Claim | Evidence |
|-------|---------|
| End-to-end pipeline works | 5 papers completed full path: fetch → OCR → sidecar → index-done → retrieval (smoke) |
| IPC warm-worker is stable | No daemon process errors across 5 papers in Batch 2; `ipc_warm_worker_used=True` for all |
| WORKER_PAGE_THRESHOLD fix works | Zero "daemonic processes are not allowed" errors in both smoke and Batch 2 |
| Body sidecar write path works | All 5 Batch 2 successes have `bodies/arxiv:*.body.txt` on disk |
| packages/__init__.py fix resolves import | No ModuleNotFoundError in Batch 2 |
| eq-heavy parse quality is acceptable | 67K–149K chars; all ≥ 5000 threshold; `body_source=marker` for 5/5 |
| JIT in-session reuse is real | Papers 4+: 40s and <5s per warm group after cold-starts; smoke papers 3+4: 53s / 12s |
| arXiv retry code is structurally correct | 1705.01446 survived 2 failures and succeeded on attempt 3; 2307.14129 survived 1 failure |
| index-done works inside container | 4-paper smoke: 4/4 indexed, 674 claims, no errors |
| research-query retrieval works | Smoke: 4/5 probes returned marker citations with `had_fallback=False` |

---

## 3. Unproven State

These are the open unknowns that require actual runs to resolve.

| Unknown | Why it matters | What would prove it |
|---------|---------------|-------------------|
| Full 29-paper success rate | 5/29 done is not a corpus | Complete warm-process run to completion |
| Category-level failure rates | Zero table-heavy, prose, outlier papers parsed | Resume + complete remaining 24 papers |
| arXiv rate-limit behavior under spacing | Failed with rapid fetching; unknown if spacing fixes it | Pre-fetch PDFs separately before warm-process |
| Marker timeout on large/complex PDFs | 1011.6402 timed out; unknown if this is isolated | Profile the paper; try with extended timeout or skip |
| Cross-restart JIT persistence | TorchInductor cache is empty after sessions; no disk write confirmed | Investigate TRITON_CACHE_DIR path in PyTorch 2.11 |
| research-query quality at 29-paper scale | Only 4-paper corpus probed | Run probes after full corpus is indexed |
| Cost-per-paper by category | eq-heavy avg: 33–49 min; table/prose/outlier: unknown | Complete the run and measure |
| Non-coder operator path | All steps require docker exec, Linux paths, container names | Document or build a single-command entrypoint |

---

## 4. Operational Gap Table

### Track A — Evidence / Validation Visibility

| # | Gap | Impact | Severity |
|---|-----|--------|----------|
| A1 | No structured progress report during runs | Can't tell how many papers parsed, failed, or remain without tailing a noisy log | High |
| A2 | No resume after kill | 8+ hours of JIT work lost on session termination | High |
| A3 | Full 29-paper corpus not yet measured | Classification (production-ready / demo-ready) is still undefined | High |
| A4 | 1011.6402 in `processing` limbo | Must be manually reset before any future run | Medium |

### Track B — Usability / Operator Simplicity

| # | Gap | Impact | Severity |
|---|-----|--------|----------|
| B1 | `index-done` requires Linux container exec | Non-coders cannot run it from Windows; not documented prominently | High |
| B2 | warm-process requires `docker exec` with exact container name | Fails silently if container name changes or is not running | High |
| B3 | arXiv rate limiting causes silent exhaustion | Papers quietly hit max retries during a long run with no operator alert | High |
| B4 | No fetch / parse separation | PDF fetch failures abort papers that could parse fine; no pre-fetch path | Medium |
| B5 | Session MUST NOT be interrupted | JIT cache not persistent; restart = restart all cold-starts | High |
| B6 | No single-command operator entrypoint | Each step is a different `docker exec` + `python -m polytool` incantation | Medium |

### Track C — Compute / Cost Optimization

| # | Gap | Impact | Severity |
|---|-----|--------|----------|
| C1 | JIT cold-start per format group: ~30–50 min each | Measured 3 distinct cold-starts in 10 papers; 29 papers may have 5–8 = 4–7 hours just in JIT | High |
| C2 | TORCHINDUCTOR_CACHE_DIR not writing to disk | Confirmed: cache directory was empty after smoke session; every new session re-JITs | High |
| C3 | No tiered ingestion | Prose/survey papers (12s warm in smoke) run the same pipeline as eq-heavy (49 min cold) | Medium |
| C4 | Cost per paper unknown | No GPU-hour tracking; can't make informed decisions about which papers to ingest | Medium |
| C5 | eq-heavy parse time is ~40 min even warm | At this rate: 29 papers × 40 min avg = ~19 hours. Non-viable for overnight runs | High |

---

## 5. Compute Observations (from observed data only)

These are measured values, not projections.

| Metric | Value | Source |
|--------|-------|--------|
| First OCR batch (cold JIT, group 1) | 7m 8s (428 s/batch) | Batch 2 log, paper 1 |
| JIT warm-up curve | 4 batches to <10s/batch, ~16 batches to <5s/batch | Batch 2 log |
| Warm OCR throughput (group 1, 261 batches) | Full run: 32m 15s | Batch 2 log |
| Cold-start #2 (110 batches, different format) | First batch: 424.80s/batch; full run: 49m 34s | Batch 2 log |
| Cold-start #3 (281 batches, another group) | First batch: 305.84s/batch; full run: 32m 35s | Batch 2 log |
| Warm papers after cold-start | 45 batches → 40s; 193 batches → 4s | Batch 2 log |
| Total parse time per eq-heavy paper | 33–49 min (includes fetch + OCR + post-processing) | results.jsonl |
| Papers per hour, eq-heavy only | ~1.3–1.8/hr depending on JIT cold-starts encountered | Computed from results.jsonl |
| GPU utilization during OCR | 99% | nvidia-smi during Batch 2 |
| VRAM usage | 7904/8192 MiB during active OCR | nvidia-smi |
| Marker timeout (1011.6402) | 3600s hit; paper `marker_failed` | results.jsonl |

**Projection for remaining 24 papers (extrapolation only):**
- If prose/survey parse at smoke speeds (~12–53s warm), they add little time
- If table-heavy papers have complex formats, each may trigger new cold-starts
- Honest range for completing all 29: 12–20 hours in current config
- This is not viable for routine validation without JIT cache persistence (Gap C2)

No cloud pricing estimates are made. Hardware is local i7-8700K + RTX 2070 Super.

---

## 6. Recommended Next Work Packets

Three work packets, listed in priority order. Not yet written in full — these are
scoping recommendations for operator decision.

### WP-1: Resumable Validation Harness + Progress Report (Priority: Highest)

**Problem:** No resume capability, no structured progress output, session kills lose all work.

**Scope:**
- Separate fetch from parse: add `research-marker-queue prefetch --queue-dir DIR` that
  downloads all pending PDFs to disk before warm-process starts. Warm-process reads
  from local cache, not from arXiv live. Eliminates rate-limit during parse phase.
- Add `research-marker-queue status-report --queue-dir DIR` that prints a structured
  table: papers done / failed / remaining / stuck, with failure classification.
- Add stuck-item detection: if a paper is in `processing` with no active warm-process,
  auto-detect and suggest `--force` reset.

**Why now:** Fixes arXiv rate limiting (root cause A), gives visibility (gap A1), enables
clean retries without full restart.

**Codex review tier:** Recommended (touches marker_queue.py fetcher path).

### WP-2: Tiered Ingestion Modes + Cost Policy (Priority: Medium)

**Problem:** All papers run through GPU Marker regardless of complexity. Prose/survey
papers run 12s warm; eq-heavy papers run 40 min. No policy distinguishes them.

**Scope:**
- Define 3 ingest tiers in queue metadata: `fast`, `standard`, `full`
- `fast`: prose/survey → pdfplumber or lightweight OCR, no GPU required, <60s
- `standard`: table-heavy → Marker with 900s timeout
- `full`: equation-heavy → Marker with 3600s+ timeout and explicit operator approval
- Add `--tier` flag to `enqueue`; add tier-level cost metrics to status-report
- Tier assignment can be manual (operator labels) or heuristic (page count + keyword scan)

**Why next:** Reduces total compute by 40–60% if prose/survey bypass GPU Marker.
Also makes cost-per-paper visible for the first time.

**Do not:** Implement L2.1 semantic retrieval, SVM enforce, or SSRN harvesters in this packet.

### WP-3: Operator-Friendly Runbook / One-Command Entrypoint (Priority: Medium)

**Problem:** Non-coders cannot run the pipeline. `index-done` requires Linux container
exec, `warm-process` requires knowing the container name, Windows NTFS prevents host-side
operations. The current runbook assumes deep familiarity.

**Scope:**
- Add `tools/scripts/academic_ingest.sh` (or `.bat`/`.ps1`) that orchestrates: prefetch →
  docker exec warm-process → docker exec index-done → status-report in one invocation.
- Update `RIS_MARKER_QUEUE_RUNBOOK.md` with the one-command path prominently at the top.
- Add a Windows-compatible alternative to `index-done` (or document clearly why it
  must run inside the container and how to invoke it safely).

**Why:** The NTFS colon issue and container exec complexity are not obvious failure modes
and will recur every time a new operator or session runs the pipeline.

---

## 7. Should We Rerun 29 Papers Now?

**Recommendation: NO — pause until WP-1 is complete.**

### Evidence for pausing:
1. A third run without prefetch separation will encounter the same arXiv rate-limit failures.
   The retry backoff (5/15/45s) has been proven insufficient. 5 of the first 10 papers
   failed on fetch alone.
2. Without resume capability, another session kill (power, harness timeout, etc.) loses
   all progress and all in-session JIT cache.
3. The 1011.6402 timeout needs classification before re-attempting: is this paper format
   incompatible with Marker, or does it just need a longer timeout (>3600s)?
4. An 8.5–20 hour unattended run on a Windows local dev machine with no checkpointing is
   operationally fragile.

### What can be done immediately without a full rerun:
1. Reset 1011.6402 from `processing` to `pending`:
   ```bash
   python -m polytool research-marker-queue --queue-dir artifacts/research/scaled_validation_queue_v2 enqueue --url 1011.6402 --force
   ```
2. Reset the 5 failed papers for future retry (after prefetch separation is built):
   ```bash
   # For each of: 1206.4810, 2003.05958, 2203.13053, 1810.04383, 2409.02025
   python -m polytool research-marker-queue --queue-dir artifacts/research/scaled_validation_queue_v2 enqueue --url ARXIV_ID --force
   ```
   Do this when ready to rerun, not now (resets attempt count).

3. Investigate 1011.6402 paper format and page count before deciding whether to skip it
   or attempt with longer timeout.

4. Investigate TorchInductor vs Triton cache path in PyTorch 2.11 (Blocker 4 follow-up)
   before the next run. If resolved, JIT cost drops dramatically.

---

## 8. Open Questions for Director

1. **WP-1 priority:** Prefetch separation is the highest-leverage change. Should this be
   the immediate next engineering session, or is there a window constraint?

2. **1011.6402 disposition:** Table-heavy empirical paper (NYSE TAQ) timed out at 3600s.
   Options: (a) increase timeout to 7200s, (b) skip this paper and substitute, (c)
   inspect it manually to diagnose the layout format. Which?

3. **JIT cache investigation:** TRITON_CACHE_DIR may be the correct env var for surya's
   OCR model in PyTorch 2.11 (not TORCHINDUCTOR_CACHE_DIR). If resolved, JIT costs drop
   from 30–50 min per format group to near-zero after first run. Should this be a
   blocking prerequisite for the next full rerun?

4. **arXiv rate limit policy:** The exponential backoff (5/15/45s) is proving insufficient
   at the retrieval density of a 29-paper batch. The correct fix is to pre-fetch PDFs
   before warm-process (WP-1). Alternatively, add 120-second inter-paper delays inside
   warm-process. The delay approach works but would add ~60 min to the full run.

5. **1810.04383 re-enqueue timing:** This paper succeeded in the 4-paper smoke but failed
   in Batch 2 due to rate limiting. It is a known-good parser target. Should it be
   enqueued to the smoke queue and re-indexed to ensure it remains in KS for retrieval
   probes, or wait for the full Batch 2 rerun?

6. **Validation classification timeline:** Current state is 5/29 parsed (all eq-heavy,
   zero coverage of other categories). A valid production-ready / demo-ready classification
   requires at minimum 20+ papers across all 4 categories. Is the goal to achieve that
   classification before the next milestone gate, or is the academic pipeline not yet
   on the critical path?

---

## 9. Validation Classification (Current State)

**INCOMPLETE — not enough data to classify.**

| Criterion | Status |
|-----------|--------|
| No silent fallbacks | ✅ All failures have explicit reasons |
| All failures triaged | ✅ Root cause A (fetch rate-limit) and Root cause B (Marker timeout) documented |
| Query citations returned | ⚠️ Proven for 4-paper smoke only; scale unverified |
| Corpus metrics within range | ❌ 5/29 done; no_body_count=5 (>3 threshold); coverage incomplete |
| Report distinguishes prod vs demo | ❌ Cannot classify; corpus not complete |

**Classification: NEEDS TRIAGE BEFORE RERUN (infrastructure, not Marker accuracy)**

Marker accuracy is not the main blocker. The 5 successful papers produced high-quality
bodies (67K–149K chars) with no parser errors. The blockers are arXiv rate limiting,
session resumability, and JIT cache persistence. These are operationalization problems,
not quality problems.

---

## 10. Codex Review

Tier: Skip — no implementation code changed in this session. Analysis only.
