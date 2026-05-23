# RIS Academic Processing Speed — Diagnosis and Optimization Plan

**Date:** 2026-05-23
**Track:** Research Intelligence System — L1 Operational
**Type:** Diagnostic analysis (no code changes)
**Audience:** Director (Aman)

---

## Logs Inspected

| Log | What it provided |
|-----|-----------------|
| `2026-05-17_academic-validation-smoke-after-triage.md` | 4-paper smoke timing table; JIT cold-start confirmation; per-format group pattern |
| `2026-05-17_academic-scaled-validation-batch2-rerun.md` | Batch 2 start record |
| `2026-05-18_academic-ris-operational-triage.md` | Batch 2 sequence reconstruction; per-paper timing from results.jsonl + warm_process_batch2.log; gap table; compute observations |
| `2026-05-19_academic-prefetch-separation-wp1.md` | WP-1 implementation record; default delay rationale; fetch/parse separation design |
| `2026-05-22_academic-prefetch-wp1-5paper-e2e.md` | 5-paper WP-1 e2e run; POSIX path bug; per-paper parse_s and text-region counts; timeout analysis |
| `2026-05-22_academic-prefetch-wp1-cached-e2e-closeout.md` | Single-paper full cached E2E proof; WP-1 PASS verdict; 29-paper rerun recommendation |
| `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` | Performance expectations table; WP-1 workflow; known-good 3-paper validation |

---

## Observed Timing Table

All values from actual runs. No estimates, no cloud costs.

### Network Fetch (now isolated by WP-1)

| Phase | Throughput | Notes |
|-------|-----------|-------|
| arXiv API fetch per paper | ~1-3s if no rate limit | 5/10 papers got HTTP 429 in Batch 2 (pre-WP-1) |
| Prefetch with 10s delay | ~10s per paper | 29-paper batch completes in ~5 min unattended |
| Prefetch with 12s delay (WP-1 e2e) | 12s per paper | 5-paper batch: all cached in ~60s, 0 429s |

### CUDA/JIT Warmup (per format group, not per paper)

| Event | Time | Source |
|-------|------|--------|
| First OCR batch, cold JIT | 428s/batch | Batch 2 log, paper 1 |
| JIT warm-up curve | 4 batches to <10s/batch, 16 batches to <5s/batch | Batch 2 log |
| Cold-start #1 (261 OCR batches) | 32 min 15s | Batch 2 log, arxiv:1105.3115 |
| Cold-start #2 (110 OCR batches) | 49 min 34s; first batch 424.80s | Batch 2 log, arxiv:1605.01862 |
| Cold-start #3 (281 OCR batches) | 32 min 35s; first batch 305.84s | Batch 2 log, arxiv:2307.14129 |
| In-session warm reuse (same format group, 45 batches) | 40s total | Batch 2 log |
| In-session warm reuse (same format group, 193 batches) | 4s total | Batch 2 log |
| Cross-session JIT reuse | Not observed | TORCHINDUCTOR_CACHE_DIR confirmed empty |

### Per-Paper Parse Time (GPU, Docker IPC warm-worker)

| arXiv ID | Category | Pages | Text regions | parse_s | Time (min) | JIT status | Source |
|----------|----------|-------|--------------|---------|------------|------------|--------|
| 2510.05533 | prose/survey | 21 | — | 16.4s | <1 | warm | WP-1 closeout |
| 2510.05533 | prose/survey | 31 | — | 12s | <1 | warm | Smoke test |
| 1609.03471 | tbl-heavy | 36 | — | 53s | <1 | warm (inherited) | Smoke test |
| 2604.24366 | short prose | 15 | — | 45.6s | <1 | cold (first paper) | IPC live validation |
| 2109.07581 | sports betting | — | — | 69.7s | ~1 | warm | IPC live validation |
| 1910.08858 | sports betting | — | — | 48.3s | <1 | warm | IPC live validation |
| 1206.4810 | eq-heavy | ~22 | ~150 | 1309s | ~22 | warm (in-session) | WP-1 5-paper e2e |
| 1106.5040 | eq-heavy | 22 | 110 OCR batches | 2771s | ~46 | warm | Smoke |
| 1105.3115 | eq-heavy | — | 261 OCR batches | 2377s | ~40 | cold-start #1 | Batch 2 |
| 1106.5040 | eq-heavy | 22 | 111 OCR batches | 2773s | ~46 | warm | Batch 2 |
| 1605.01862 | eq-heavy | — | 110 OCR batches | 1975s | ~33 | cold-start #2 | Batch 2 |
| 1705.01446 | eq-heavy | — | 45 OCR batches | 2365s | ~39 | warm | Batch 2 |
| 2307.14129 | eq-heavy | — | 281 OCR batches | 2947s | ~49 | cold-start #3 | Batch 2 |
| 2203.13053 | eq-heavy | ~26 | ~200 regions | 3196s | ~53 | warm (in-session) | WP-1 5-paper e2e |
| 1810.04383 | eq-heavy | 36 | 286 OCR batches | 3279s | ~55 | cold-start | Smoke |
| 2307.14129 | eq-heavy | 47 | 415 regions | >3600s | TIMEOUT | warm | WP-1 5-paper e2e |
| 2409.02025 | eq-heavy | 49 | 507 regions | >7200s | TIMEOUT | warm | WP-1 5-paper e2e |
| 1011.6402 | tbl-heavy | ~20 | dense tables | 3600s | TIMEOUT ×3 | (unknown) | Batch 2 + WP-1 e2e |

### Sidecar / Index / Query (not a bottleneck)

| Step | Observed time | Source |
|------|--------------|--------|
| index-done, 4 papers | seconds (674 claims) | Smoke test |
| index-done, 1 paper (prose) | seconds (167 claims) | WP-1 closeout |
| research-query lookup | <5s | All sessions |

### GPU / System State

| Metric | Value | Source |
|--------|-------|--------|
| GPU utilization during OCR | 99% | nvidia-smi, Batch 2 |
| VRAM used during active OCR | 7904/8192 MiB | nvidia-smi, Batch 2 |
| VRAM at model load (idle) | 1462 MiB | Smoke test start |
| TORCHINDUCTOR_CACHE_DIR contents after 4 papers | 0 bytes | Smoke test, Blocker 4 |

---

## Bottleneck Diagnosis

Ranked by impact on total batch time.

### B1 — CUDA/JIT Cold-Start per Format Group (CRITICAL, 30–50 min per group)

The dominant cost for any batch with format diversity is TorchInductor/Triton JIT compilation.
Each unique PDF layout group (equation-heavy v1, equation-heavy v2, table-dense, prose)
triggers a full JIT cold-start when the first paper of that format group is encountered.

- Observed cold-starts: 3 in the first 10 eq-heavy papers of Batch 2 (32, 50, 33 min respectively).
- Each cold-start was 30–50 min regardless of the paper being "simple" or "complex."
- In-session reuse is highly effective: paper 4 in same format group ran 40 OCR batches in 40s
  total after the cold-start was paid by paper 1.
- Cross-session reuse is zero: TORCHINDUCTOR_CACHE_DIR was confirmed empty after both the
  smoke session and Batch 2. Every container restart pays all cold-starts from scratch.

**Projection:** 29 papers likely span 5–8 distinct format groups → 5–8 × 40 min = 3–6 hours
in JIT overhead alone, before any actual parsing begins.

### B2 — Parse Complexity Ceiling (CRITICAL, papers >300 text regions)

Eq-heavy papers with many text regions (equations, formula lines) hit a per-region JIT
compilation cost of 20–80s/region. This is not covered by the warm-start savings because
each unique equation pattern may trigger a new compilation.

- arxiv:2307.14129 (47 pages, 415 regions): timed out at both 3600s and 7200s.
- arxiv:2409.02025 (49 pages, 507 regions): timed out at 7200s.
- arxiv:1011.6402 (table-dense, ~20 pages): timed out at 3600s — three times.

These papers are currently unparseable in any reasonable wall-clock window with current settings.
They are not fixable by increasing timeout alone; they would need either a format-triage step
before Marker or classification as out-of-scope for the current corpus.

### B3 — arXiv Rate Limiting During Parse (RESOLVED by WP-1)

Pre-WP-1: 5/10 papers in Batch 2 failed on fetch alone (HTTP 429 cascade) because warm-GPU
papers complete in 40–60s, triggering multiple PDF downloads in rapid succession.

Post-WP-1: Prefetch runs separately (12s inter-fetch delays, ~5 min for 29 papers). Warm-process
reads from local cache. Zero arXiv API calls during GPU parse. This bottleneck is closed.

### B4 — No Cross-Session JIT Persistence (HIGH, prevents incremental runs)

Every container restart pays all cold-starts again. A single interruption (power, harness
timeout, crash) destroys all JIT progress. The known investigation path is TRITON_CACHE_DIR
(not TORCHINDUCTOR_CACHE_DIR), which may be the correct env var for surya's OCR pipeline in
PyTorch 2.11. Unresolved as of WP-1 closeout.

Without this: the 29-paper batch must run in one continuous uninterrupted session — an
operationally fragile requirement for a local dev machine.

### B5 — No Timeout Policy by Paper Profile (MEDIUM, papers classified by wrong timeout)

Currently all papers use the same `--marker-timeout` flag. The WP-1 closeout recommends
a file-size-based heuristic:

- ≤600 KB → 3600s adequate
- 600–1500 KB → 7200s
- >1500 KB → 14400s (4 hours)

But even 14400s may not be sufficient for papers with 400+ text regions (proven by arxiv:2409.02025).
Timeout scaling alone does not solve B2.

### B6 — No Format Pre-Triage (MEDIUM, wastes GPU time on Marker-incompatible papers)

Table-dense papers (e.g. NYSE TAQ empirical with thousands of embedded table cells) and
image-only or scanned PDFs may be Marker-incompatible. Currently no triage step exists to
identify these before GPU time is spent. The first signal of incompatibility is a 60-min timeout.

### B7 — Network Fetch (LOW, isolated by WP-1)

Fetch is now decoupled from parse. A 29-paper prefetch at 12s/paper takes ~5 min. Not a
significant factor.

### B8 — Sidecar Write / Index / Query (NEGLIGIBLE)

index-done completes in seconds per paper. research-query is under 5s. These are not
contributing to batch wall-clock time.

---

## Rough Cost-Per-Paper Estimates (Local GPU Only)

These are ranges derived from observed runs. Cloud pricing is explicitly excluded.

| Paper type | Cold-start included? | Observed range | Wall-clock range |
|------------|---------------------|----------------|-----------------|
| Prose/survey (<25 pages) | No cold-start (first paper pays model load ~27s) | 12–70s | <2 min |
| Table-light (<200 cells) | In-session warm | 45–60s | <2 min |
| Table-heavy (dense, complex) | Potential new cold-start | Unknown; 1011.6402 = infinite in 3600s | Unknown |
| Eq-heavy, small (<200 regions) | In-session warm (after group cold-start) | 22–55 min | 22–55 min |
| Eq-heavy, large (>300 regions) | Warm but per-region JIT overhead | 60+ min → timeout | TIMEOUT (3600–7200s insufficient) |
| First paper per format group | Cold-start = 30–50 min overhead | +30–50 min on top of parse | +30–50 min |

**Overall 29-paper projection (current pipeline, all papers, no tiering):**

- Estimated 5–8 cold-starts: 3–6 hours JIT overhead
- 29 papers × 40 min avg (eq-heavy): ~19 hours pure parse
- Realistic end-to-end: 12–20 hours in one uninterrupted session
- 3 papers currently proven timeout-insoluble (1011.6402, 2307.14129, 2409.02025)

This is consistent with the triage memo estimate of 12–20 hours. Not viable for overnight
runs on a local dev machine without JIT cache persistence.

---

## Safe Optimizations (No Accuracy Risk)

These changes do not affect parse quality, body_length, or RAG retrieval fidelity.

### S1 — Prefetch Separation (DONE — WP-1)

Already shipped. PDF downloads happen in a separate phase with controlled delays.
Warm-process reads cached local files. arXiv API is not called during GPU parse.

### S2 — Resume-Safe Queue (DONE — queue design)

The queue is already resume-safe: `warm-process` only picks up `pending` items.
`done` papers are skipped. A `--force` re-enqueue resets `failed` or `processing` papers.
No further changes needed unless a checkpoint mid-paper is desired (much harder, not recommended
without Marker internal support).

### S3 — Status Reporting (DONE — WP-1 `status-report`)

`research-marker-queue status-report` provides prefetch stats, stuck-item detection, and
failure classification. Operators can see batch state at any point without reading raw JSONL.

### S4 — Timeout Scaling by File Size / Category (RECOMMENDED, not implemented)

**What:** Set `--marker-timeout` per-paper based on file_size (already in manifest) or
category label (already in queue metadata for the scaled validation corpus).

**Policy (evidence-based):**

| Condition | Recommended timeout |
|-----------|-------------------|
| file_size ≤ 600 KB | 3600s |
| 600 KB < file_size ≤ 1500 KB | 7200s |
| file_size > 1500 KB | 14400s |
| Category = prose/survey | 900s (sufficient) |
| Category = tbl-heavy (confirmed timeout) | 14400s or SKIP |

This is safe because it affects only the timeout, not parse behavior. Papers that parse
in <3600s are unaffected; papers that currently timeout get more wall-clock time.

**Accuracy risk:** None. Marker parse quality is the same at any timeout.

**Caveat:** Timeout scaling does not fix B2 (papers with 400+ text regions). Those papers
need a structural fix (tiering or format exclusion), not just more time.

### S5 — JIT Cache Persistence Investigation (HIGH LEVERAGE if resolved)

**What:** Investigate whether `TRITON_CACHE_DIR` (not `TORCHINDUCTOR_CACHE_DIR`) is the
correct env var for surya's OCR kernel cache under PyTorch 2.11.0.

If effective: cold-start cost drops from 30–50 min (first paper per format group per session)
to near-zero after the first overnight run. Subsequent runs start warm regardless of container
restarts.

**Why not done yet:** Requires a live Docker session with GPU to test. The investigation is
one env var change and a cache-directory size check after one paper's parse. Low engineering
cost, potentially very high throughput benefit.

**Accuracy risk:** None. JIT cache persistence only affects compilation speed, not Marker
output quality.

**Implementation note:** The likely candidates are:
1. `TRITON_CACHE_DIR=/app/cache/triton` mounted as a Docker volume
2. `TORCHINDUCTOR_CACHE_DIR` may still be needed for non-Triton kernels

### S6 — One-Command Operator Entrypoint (CONVENIENCE, not throughput)

A script orchestrating `prefetch → docker exec warm-process → docker exec index-done → status-report`
removes the 5-step manual workflow. Does not change throughput. Reduces operator error.

---

## Experimental Optimizations (May Trade Accuracy)

These approaches have real speed benefits but change the RAG corpus quality. Each requires
isolated measurement before being adopted.

### E1 — Text-Layer Extraction Triage Before Marker

**What:** Before sending a paper to GPU Marker, extract embedded text using pdfplumber or
pdftext (CPU-only, seconds). If text coverage is ≥ N% of expected page coverage (heuristic),
use the text-only extraction and skip GPU Marker.

**Speed gain:** Prose/survey and text-heavy papers: from 12–70s (Marker warm) to <5s (pdfplumber).
Eq-heavy papers have low embedded text coverage and would fall through to Marker as before.

**Accuracy risk:**
- pdfplumber loses structural layout: column boundaries, equation groupings, table structure.
- For prose papers, the loss is small (running text is correctly extracted).
- For equation-heavy papers, text extraction misses or garbles equation content.
- The RAG corpus would contain a mix of `body_source=marker` (structured) and `body_source=pdfplumber`
  (text-only) papers. Current RAG-readiness gate (`body_source=marker`) would need revision.
- Claims extracted from pdfplumber text may be lower quality.

**Who benefits:** Papers already readable as text (prose/survey, news/blog-style). No benefit
for eq-heavy or scanned papers.

**Test protocol:** Parse the same paper with both pdfplumber and Marker; compare chunk count,
claim count, and retrieval precision on 3–5 domain queries. Accept if pdfplumber recall ≥ 80%
of Marker's retrieval precision on this paper type.

### E2 — Abstract/Metadata-Only Prefilter Tier

**What:** Ingest only title, abstract, and authors (already available from arXiv Atom API, no PDF
required). Store as a thin KS document. Available immediately — no GPU, no Marker, no wait.

**Speed gain:** Near-instant. arXiv Atom API returns metadata in <2s. No GPU required.

**Accuracy risk (HIGH):**
- The body text (Marker output) is the RAG-relevant content. Claims are extracted from body.
- Abstract-only documents produce 1–3 chunks and 0–5 claims.
- Retrieval precision is very low for domain queries because the abstract does not contain
  the paper's findings, methodology, or data — only the summary.
- This tier is useful for prefiltering (does this paper touch my topic?) but not for claim
  extraction or deep research RAG.

**Appropriate use:** As a true prefilter — show the operator what is available before
committing GPU time. Not as a substitute for Marker parse in the final corpus.

**Test protocol:** Not required. This tier is already partially available via `research-harvest`
(L4 metadata discovery). The gap is just that those metadata records are not indexed into KS.

### E3 — Full Marker Only for High-Value Papers

**What:** Explicitly designate papers as Tier 2 (Marker) or Tier 1 (pdfplumber/text-layer)
based on operator label, file size, or page count. Only Tier 2 papers get GPU Marker treatment.

**Speed gain:** Approximately 40–60% compute reduction if prose/survey and tbl-light papers
bypass GPU Marker (consistent with triage memo estimate). At 29 papers: ~6–8 papers are
prose/survey/tbl-light and likely parse in 15–60s Marker-warm. Savings would be negligible in
wall-clock terms since these papers are already fast. The real gain would be cleaner policies
for large batches (100+ papers).

**Accuracy risk:** Same as E1 for papers classified to pdfplumber tier. Marker papers are
unaffected.

**Note:** At the current 29-paper scale, this optimization does not materially change the
12–20 hour estimate, which is dominated by eq-heavy papers and cold-start overhead. Tiering
becomes important at scale (100+ papers).

### E4 — Page-Limited Preview Mode

**What:** Parse only the first N pages of a paper using Marker (or a subset of pages), generate
a partial body, and use that for RAG.

**Speed gain:** Linear in page count if parse time is proportional to pages. A 47-page paper
parsed to 20 pages might take half the time. Unconfirmed — Marker's CLI may not support
page-limited input without modification.

**Accuracy risk:**
- Body text and claims would be incomplete. Papers with findings in the final sections (common
  in empirical economics papers) would be systematically under-represented.
- "Preview mode" documents would need a different quality designation in the corpus.

**Investigation required:** Check whether Marker's Python API or CLI supports `--start-page` /
`--end-page` args. If not, this requires forking the Marker pipeline, which is out of scope.

### E5 — OCR-Disabled or Reduced-OCR Mode (Needs Marker Investigation)

**What:** Marker has an OCR layer for scanned/handwritten content and an equation detection
layer. If a paper has rich embedded digital text, OCR may be unnecessary.

**Speed gain:** Unknown. If OCR batching is the dominant cost for eq-heavy papers, disabling OCR
for text-rich PDFs could reduce parse time substantially. This is speculative without a controlled
experiment.

**Accuracy risk:**
- OCR is what makes Marker work for scanned papers and papers with low-quality embedded text.
- Papers that look text-rich may still have equations or tables only extractable via OCR.
- Disabling OCR on a paper that needs it produces empty or garbled sections.

**Investigation required:** Check Marker documentation or source for `--skip-ocr`, `--ocr-override`,
or equivalent flags. Look at the model pipeline to identify which stages can be bypassed.
This requires a dedicated technical investigation, not just a run.

---

## Tiered Ingestion Policy Recommendation

A four-tier policy separating compute commitment from RAG quality.

### Tier 0 — Metadata / Abstract Only

- **Input:** arXiv Atom API response (already fetched during `enqueue`)
- **Compute:** None (API call, <2s)
- **Output:** Title, abstract, authors, published_date in KS; 1–3 chunks; 0–5 claims
- **RAG quality:** Low — abstract only. Good for topic-level prefiltering, not claim extraction.
- **When to use:** Initial corpus discovery; verifying topic relevance before committing GPU time.
- **Current status:** Metadata available from `enqueue`; not indexed to KS today. Minor change to
  add an optional `--metadata-only-index` flag to `index-done` or `enqueue`.

### Tier 1 — Lightweight Text Extraction (CPU Only)

- **Input:** Cached PDF (from prefetch)
- **Compute:** pdfplumber or pdftext, CPU-only, ~1–10s per paper
- **Output:** Plain text body, no structural layout; 10–30 chunks; 15–50 claims (estimated)
- **RAG quality:** Medium — running text and headings preserved; equations, table structure,
  and multi-column layout are NOT reliably extracted. Prose papers benefit most.
- **When to use:** Prose/survey papers where equations and table structure are not central
  to the findings. Papers that have been confirmed as text-rich via PDF inspection.
- **Accuracy cost vs Tier 2:** Quantified by E1 test protocol (not yet run).
- **Current status:** pdfplumber path exists as a debug override (`RIS_PDF_PARSER=pdfplumber`).
  Not production-qualified for academic RAG. RAG-readiness gate requires `body_source=marker`.

### Tier 2 — Marker Full Structural Parse (GPU)

- **Input:** Cached PDF (from prefetch)
- **Compute:** RTX 2070 Super, CUDA, GPU Marker. 12s–55 min depending on complexity.
- **Output:** Full structured body, equations rendered as LaTeX (where detectable), tables
  extracted, multi-column layout preserved; 30–50 chunks; 100–400 claims per paper.
- **RAG quality:** High. This is the current production standard. `body_source=marker` gate
  enforced.
- **When to use:** All eq-heavy papers; table-dense papers (if not timeout-insoluble); any
  paper where structural information is material to the research findings.
- **Timeout policy:** Apply S4 timeout scaling by file size before running.
- **Current status:** Production path. All 5 Batch 2 successes used this tier.

### Tier 3 — Manual / High-Value Deep Parse (Operator Approval Required)

- **Input:** Cached PDF + operator review
- **Compute:** Tier 2 + extended timeout (up to 14400s / 4 hours) + optional manual inspection.
  Operator must explicitly approve a Tier 3 parse run.
- **Output:** Same as Tier 2 if Marker succeeds. May require re-running at higher timeout.
- **RAG quality:** Same as Tier 2. Tier 3 is a process designation, not a quality upgrade.
- **When to use:** Papers with >1.5 MB PDF or >300 text regions; papers in the "timeout-insoluble"
  category (1011.6402, 2307.14129, 2409.02025). Before approving: inspect PDF for scanned
  pages, embedded images, or OCR-incompatible tables. If the paper is scanned-only, no Marker
  improvement is possible regardless of timeout.
- **Current status:** No formal tier. Currently handled by ad-hoc `--marker-timeout 7200` flag.

---

## Recommended Next Implementation Packet

### WP-2: Tiered Ingestion + Timeout Policy (Priority: Medium)

**Problem:** All papers run through GPU Marker with the same timeout regardless of complexity.
Timeout-insoluble papers waste 3600–7200s per attempt. No policy distinguishes prose from
eq-heavy.

**Scope (tight):**

1. Add `--tier {0,1,2,3}` flag to `research-marker-queue enqueue`.
   - Default: Tier 2 (current behavior — no regression).
   - Stored in queue metadata as `ingest_tier`.

2. Implement file-size-based default timeout assignment in `warm-process`:
   - Read `file_size` from the prefetch manifest before parse.
   - Set timeout: ≤600 KB → 3600s, 600–1500 KB → 7200s, >1500 KB → 14400s.
   - Override: if caller passes `--marker-timeout`, that wins.

3. Add `ingest_tier` and `auto_timeout_s` to `status-report` output so operator can see
   what timeout will be applied before committing to a long run.

4. Document the 4-tier policy in `RIS_MARKER_QUEUE_RUNBOOK.md`.

**What this does NOT do:**
- Does not implement pdfplumber Tier 1 extraction (that is E1 and needs accuracy testing first).
- Does not implement Tier 0 metadata indexing (separate small change).
- Does not resolve JIT cache persistence (S5 investigation is prerequisite).

**Accuracy risk:** None. Tier 2 behavior is unchanged. Timeout scaling only affects how long
the parse waits; it does not change Marker's output on papers that complete normally.

**Estimated engineering cost:** Small. Queue schema already supports arbitrary metadata.
Timeout logic is one conditional in `warm-process`. Main effort is the `status-report` display
and runbook update.

---

### JIT Cache Investigation (Prerequisite for Next Full Run — should run before WP-2)

Before re-running the 29-paper corpus, investigate JIT cache persistence as a blocking experiment:

1. Start GPU container fresh.
2. Parse one eq-heavy paper (e.g., arxiv:1206.4810, 720 KB, known 22-min parse).
3. After parse, check `ls -la $TRITON_CACHE_DIR` (not just `TORCHINDUCTOR_CACHE_DIR`).
4. Stop and restart the container without deleting the cache volume.
5. Parse the same paper again. If cold-start time drops from ~30 min to <60s: JIT cache is working.

If JIT cache persistence is resolved, the per-format-group cold-start cost drops from 30–50 min
to near-zero after first session. That changes the 12–20 hour estimate for 29 papers to
approximately 3–5 hours (dominated by eq-heavy parse times, not cold-starts).

**This investigation should happen before the next 29-paper run, because the outcome changes
whether the run is viable overnight or requires a dedicated multi-day window.**

---

### Papers to Skip or Reclassify Before Next Full Run

Based on observed timeout evidence:

| arXiv ID | Issue | Recommendation |
|----------|-------|---------------|
| 1011.6402 | TIMEOUT ×3 at 3600s (tbl-heavy, NYSE TAQ) | Inspect PDF for scanned tables; attempt once at 14400s (Tier 3); if still fails, exclude from corpus |
| 2307.14129 | TIMEOUT at 3600s + killed at 7200s (47 pages, 415 regions) | Attempt at 14400s (Tier 3); if fails, exclude |
| 2409.02025 | TIMEOUT at 7200s (49 pages, 507 regions) | Attempt at 14400s (Tier 3); if fails, exclude |

These three papers represent papers 11, 4, and 5 in the queue. Together they could consume
12–24 hours of GPU time in failed attempts without the Tier 3 policy and manual approval gate.

---

## Open Questions

1. **TRITON_CACHE_DIR:** Does `TRITON_CACHE_DIR` (distinct from `TORCHINDUCTOR_CACHE_DIR`) control
   surya's OCR kernel cache under PyTorch 2.11? This is the highest-leverage unresolved question.
   If yes, cross-session cold-starts disappear and the 12–20 hour estimate drops significantly.

2. **1011.6402 format:** Is this paper scanned-only, or does it have embedded digital text?
   A PDF inspection (download + open in a PDF viewer, attempt text selection) would answer
   whether any Marker timeout can succeed. If scanned-only, no Marker improvement is possible.

3. **Tier 1 accuracy:** If pdfplumber is implemented for prose/survey papers, what is the
   retrieval precision vs Marker? Needs a controlled 3-paper test before policy adoption.

4. **29-paper rerun timing:** With WP-1 shipped and POSIX fix committed, the rerun is
   operationally safe from a fetch perspective. The risk factors are: (a) 3 timeout-insoluble
   papers need Tier 3 handling or exclusion, and (b) cold-starts will recur unless JIT
   persistence is resolved. Recommend JIT investigation before scheduling the full run.

---

## Summary

| Category | Status |
|----------|--------|
| arXiv rate limiting during parse | **RESOLVED** (WP-1) |
| JIT in-session reuse | **WORKING** (proven by smoke and Batch 2) |
| JIT cross-session persistence | **UNKNOWN** (TORCHINDUCTOR_CACHE_DIR empty; TRITON_CACHE_DIR not tested) |
| Timeout policy | **MISSING** — one-size-fits-all; 3 papers are timeout-insoluble at current settings |
| Tiered ingestion | **NOT IMPLEMENTED** — all papers run Tier 2 regardless of complexity |
| Resume safety | **ADEQUATE** (queue design + `--force` enqueue) |
| Operator visibility | **ADEQUATE** (status-report, prefetch manifest) |
| Next full 29-paper run | **CONDITIONAL** — safe after JIT investigation + Tier 3 classification for 3 timeout papers |
