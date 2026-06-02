# Academic Scaled Validation Queue Reset — Readiness Verification

**Date:** 2026-05-28
**Author:** Claude Code (Sonnet 4.6)
**Status:** PARTIAL — queue validation-ready; Chroma embedding gap documented
**Codex review ref:** 2026-05-26_codex-review-academic-demo-ready-docs-queue-triage.md

---

## Objective

Reset `artifacts/research/scaled_validation_queue_v2` into a clean 29-paper
validation-ready state without running the full 29-paper GPU parse. Index the 5
existing done sidecars, reset stuck/failed items, prefetch all pending PDFs, run
JIT cache diagnostic, identify Tier-3 timeout-risk papers, and produce a clear
next-run command plan.

---

## Files and Artifacts Changed

| Artifact | Change |
|----------|--------|
| `artifacts/research/scaled_validation_queue_v2/queue.jsonl` | stuck item reset; 5 failed items reset; Tier-3 tags on 1011.6402 and 2409.02025 |
| `artifacts/research/scaled_validation_queue_v2/indexed.jsonl` | 5 papers recorded as KS-indexed |
| `artifacts/research/scaled_validation_queue_v2/pdf_cache/` | 24 PDFs prefetched (0 → 24 cached) |
| `docs/CURRENT_STATE.md` | 29-paper rerun section updated with queue-reset status |

---

## Pre-Reset Queue State

```
pending:     18
processing:  1  (arxiv:1011.6402 — stuck, session kill during Batch 2)
done:        5  (arxiv:1105.3115, 1106.5040, 1605.01862, 1705.01446, 2307.14129)
failed:      5  (arxiv:1206.4810, 2003.05958, 2203.13053, 1810.04383, 2409.02025)
total:       29
prefetch_stats.cached:  0
sidecar_count:          5
indexed_count:          0
stuck_warning:          true
```

Failed item failure classes (all metadata-fetch failures, not parse failures):

| Candidate ID | Failure class |
|---|---|
| arxiv:1206.4810 | Timeout fetching arXiv metadata API |
| arxiv:2003.05958 | Timeout fetching arXiv metadata API |
| arxiv:2203.13053 | HTTP 429 fetching arXiv metadata API |
| arxiv:1810.04383 | HTTP 429 fetching arXiv metadata API |
| arxiv:2409.02025 | Timeout fetching arXiv metadata API |

---

## Git Status Check (Step 1)

```
M AGENTS.md
M claude.md
M docs/CURRENT_STATE.md
M docs/obsidian-vault/...  (vault churn — unrelated)
```

No core implementation files dirty. Safe to proceed.

---

## Pre-Reset Chroma Link-Check

```json
{
  "collection": "academic_papers",
  "total_chunks": 162,
  "unique_papers": 5,
  "valid_ks_doc_id": 162,
  "missing_ks_doc_id": 0,
  "ks_doc_id_not_in_ks": 0
}
```

Chroma is valid before reset. 5 papers from prior smoke_test_queue sessions are present.

---

## Reset Actions Performed

### Step 3: Index 5 done sidecars (inside Docker)

```bash
docker exec polytool-ris-scheduler-gpu sh -c "cd /app && python -m polytool \
  research-marker-queue --queue-dir /app/artifacts/research/scaled_validation_queue_v2 \
  index-done --reindex-chroma --json"
```

Result: KS indexing succeeded for all 5 papers. Chroma embedding failed (chromadb not
installed in GPU container). Second pass attempted after `pip install chromadb` — still
failed (`sentence-transformers` also not installed in GPU container). See Chroma section.

KS indexing outcome:

| Candidate ID | doc_id (first 8) | Chunks | Claims |
|---|---|---|---|
| arxiv:1105.3115 | 1b252835 | 36 | 165 |
| arxiv:1106.5040 | c30c1027 | 30 | 147 |
| arxiv:1605.01862 | 0b289e8d | 47 | 235 |
| arxiv:1705.01446 | 741fa093 | 49 | 241 |
| arxiv:2307.14129 | 536aa7b4 | 65 | 318 |
| **Total** | | **227** | **1106** |

### Step 4: Reset stuck processing item

```bash
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/scaled_validation_queue_v2 \
  enqueue --url 1011.6402 --force --tier 3
# Output: Reset:    arxiv:1011.6402  (status=pending, attempts=0)
```

Re-enqueued with `--tier 3` because it is a confirmed Tier-3 timeout-risk paper.

### Step 5: Reset 5 failed items

```bash
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/scaled_validation_queue_v2 \
  enqueue --url 1206.4810 --force
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/scaled_validation_queue_v2 \
  enqueue --url 2003.05958 --force
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/scaled_validation_queue_v2 \
  enqueue --url 2203.13053 --force
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/scaled_validation_queue_v2 \
  enqueue --url 1810.04383 --force
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/scaled_validation_queue_v2 \
  enqueue --url 2409.02025 --force --tier 3
```

All 5 reset: `status=pending, attempts=0`. 2409.02025 gets `--tier 3` (persistent HTTP 429).

### Step 6: Prefetch all 24 pending PDFs

```bash
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/scaled_validation_queue_v2 \
  prefetch --max-items 30 --delay-seconds 12
```

Result: **24/24 downloaded, 0 failed, 0 already cached.** All PDFs cached in
`artifacts/research/scaled_validation_queue_v2/pdf_cache/`.

PDF size summary:

| Size bucket | Count | Papers |
|---|---|---|
| Small (≤600KB) | 5 | 2507.01990 (219KB), 2510.05533 (524KB), 2605.00864 (541KB), 2507.08921 (582KB), 2601.18815 (588KB) |
| Medium (601–1500KB) | 12 | 1011.6402, 1206.4810, 1609.03471, 1810.04383, 2003.05958, 2203.13053, 2208.13564, 2409.02025, 2605.00493, 2605.02286, 2605.10400, 2605.11640 |
| Large (>1500KB) | 7 | 2403.09267 (3.5MB), 2508.03474 (9.8MB), 2308.04947 (6.7MB), 2212.12717 (2.3MB), 2602.21091 (2.0MB), 2604.20050 (1.8MB), 2604.10005 (1.7MB) |

---

## Post-Reset Queue State

```
pending:     24
processing:  0
done:        5
failed:      0
total:       29
stuck_warning:              false
prefetch_stats.cached:      24
prefetch_stats.failed:      0
sidecar_count:              5
indexed_count:              5
```

---

## Post-Reset Chroma Link-Check

```json
{
  "collection": "academic_papers",
  "total_chunks": 162,
  "unique_papers": 5,
  "valid_ks_doc_id": 162,
  "missing_ks_doc_id": 0,
  "ks_doc_id_not_in_ks": 0
}
```

Chroma is still valid (162 chunks, 5 papers). No orphaned chunks. The 5 papers from
prior smoke_test sessions are intact. However, 4 of the 5 newly-indexed papers
(1105.3115, 1605.01862, 1705.01446, 2307.14129) are **not** in Chroma yet. See below.

---

## Chroma Embedding Gap (PARTIAL BLOCKER)

**Root cause:** Architectural split between the two compute environments:
- KS indexing: must run inside Docker (NTFS `:` in filenames blocks Windows Python)
- Chroma embedding: needs `sentence-transformers`, which is not installed in the
  `ris-scheduler-gpu` container (Marker parse container, not RAG container)

Attempted fix: `pip install chromadb` inside Docker succeeded; `sentence-transformers`
installation not attempted (large dep, changes GPU container state).

**Impact:** 4 papers (1105.3115, 1605.01862, 1705.01446, 2307.14129) are KS-indexed
but not Chroma-embedded. `research-query` over these papers will use the lexical KS
fallback (`had_fallback=True`). Semantic retrieval is unaffected for the 5 smoke_test
papers already in Chroma.

**Remediation path (post-validation):**

Option A — run `index-done --reindex-chroma --force` via a RAG-capable Docker compose
service (e.g., the main `polytool` service which has sentence-transformers):
```bash
docker compose run --rm polytool python -m polytool research-marker-queue \
  --queue-dir /app/artifacts/research/scaled_validation_queue_v2 \
  index-done --reindex-chroma --force
```

Option B — add `sentence-transformers` to the GPU container image (requires Dockerfile
change and rebuild — invasive, not recommended).

Note: arxiv:1106.5040 IS already in Chroma (doc_id=c30c102..., 30 chunks) from a prior
smoke_test session. Only the 4 NEW done papers lack Chroma embedding.

---

## JIT Cache Diagnostic (Step 8)

Command run on Windows host:
```bash
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/scaled_validation_queue_v2 jit-cache-check
```

Output: Interactive diagnostic printed. Key state:

```
TORCHINDUCTOR_CACHE_DIR = (not set)
TRITON_CACHE_DIR        = (not set)
```

**Persistence verdict: UNPROVEN.** The `/tmp/before_marker` timestamp step has not
been run inside the GPU Docker container this session. Investigation must happen inside
the running Docker container during a GPU parse session. Steps documented in the runbook.

**Risk for full validation batch:** If JIT cache is not persistent across Docker restarts,
each format group (prose/small, equation-heavy, large-table) will pay a 27–50 min cold-start
on the first paper of that group. For the 29-paper batch with 3+ format groups, this could
add 1–2.5 hours to total runtime. Plan accordingly.

---

## Tier-3 Timeout-Risk Paper Classification (Step 9)

From post-reset status-report `timeout_risk_items` with actual PDF sizes:

### Mandatory Tier-3 (confirmed risk, ingest_tier=3):

| arXiv ID | Size | Evidence | Action before batch |
|---|---|---|---|
| arxiv:1011.6402 | 724KB | Confirmed timeout at 3600s in Batch 2 | `--tier 3` already set; operator approval required; use `--marker-timeout 7200` minimum |
| arxiv:2409.02025 | 1022KB | Persistent HTTP 429 / metadata fetch failures | `--tier 3` already set; confirm arXiv metadata fetch succeeds before batch inclusion |

### Tier-3 by size (large, ingest_tier=2, tier3_flag=true):

| arXiv ID | Size | Recommended timeout | Notes |
|---|---|---|---|
| arxiv:2508.03474 | 9761KB | 14400s | Largest PDF in corpus; highest timeout risk |
| arxiv:2308.04947 | 6683KB | 14400s | Very large |
| arxiv:2403.09267 | 3583KB | 14400s | Large |
| arxiv:2212.12717 | 2280KB | 14400s | Large |
| arxiv:2602.21091 | 2032KB | 14400s | Large |
| arxiv:2604.20050 | 1833KB | 14400s | Large |
| arxiv:2604.10005 | 1728KB | 14400s | Large |

These have `ingest_tier=2` in the queue (not re-tagged as tier 3) but are flagged
`tier3_flag=true` by size heuristic. They should be processed in Batch C (extended timeout)
and kept separate from the normal small/medium batch.

### Medium papers (normal extended timeout, tier3_flag=false):

| arXiv ID | Size | Recommended timeout |
|---|---|---|
| arxiv:1206.4810 | 720KB | 7200s |
| arxiv:2003.05958 | 938KB | 7200s |
| arxiv:2203.13053 | 1126KB | 7200s |
| arxiv:1810.04383 | 1241KB | 7200s |
| arxiv:1609.03471 | 1298KB | 7200s |
| arxiv:2605.11640 | 1041KB | 7200s |
| arxiv:2605.02286 | 657KB | 7200s |
| arxiv:2605.00493 | 879KB | 7200s |
| arxiv:2208.13564 | 1008KB | 7200s |
| arxiv:2605.10400 | 1029KB | 7200s |

### Small papers (normal timeout):

| arXiv ID | Size | Recommended timeout |
|---|---|---|
| arxiv:2507.01990 | 219KB | 3600s |
| arxiv:2510.05533 | 524KB | 3600s |
| arxiv:2605.00864 | 540KB | 3600s |
| arxiv:2507.08921 | 582KB | 3600s |
| arxiv:2601.18815 | 588KB | 3600s |

---

## Proposed 29-Paper Validation Command Plan (Step 10)

### Preflight checks (run before starting any GPU session)

```bash
# 1. Confirm queue is clean
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/scaled_validation_queue_v2 counts
# Expected: pending=24, done=5, failed=0, processing=0

# 2. Confirm all PDFs are cached
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/scaled_validation_queue_v2 status-report
# Expected: prefetch_stats.cached=24, prefetch_stats.failed=0

# 3. Confirm GPU passthrough works
docker compose --profile ris-gpu run --rm ris-scheduler-gpu nvidia-smi
# Expected: GPU listed, VRAM shown

# 4. Run JIT cache diagnostic inside Docker (inside the container)
docker exec polytool-ris-scheduler-gpu sh -c \
  "find ~/.triton -name '*.cubin' 2>/dev/null | wc -l; \
   find /root/.triton -name '*.cubin' 2>/dev/null | wc -l"
# Note pre-count for cache persistence test

# 5. Re-run prefetch to verify no PDF was evicted (safe to re-run, skips cached)
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/scaled_validation_queue_v2 prefetch \
  --delay-seconds 5
```

### Batch A — Small papers (5 papers, 3600s timeout)

```bash
docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
  python -m polytool research-marker-queue \
  --queue-dir /app/artifacts/research/scaled_validation_queue_v2 \
  warm-process --max-items 5 --marker-timeout 3600
```

Papers: 2507.01990, 2510.05533, 2605.00864, 2507.08921, 2601.18815

**Stop condition:** If >1 paper fails with `marker_timeout`, stop. Do not proceed to Batch B
without understanding the failure. Check JIT cache state after this batch.

### Batch B — Medium papers (10 papers, 7200s timeout each)

```bash
docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
  python -m polytool research-marker-queue \
  --queue-dir /app/artifacts/research/scaled_validation_queue_v2 \
  warm-process --max-items 10 --marker-timeout 7200
```

Papers: 1206.4810, 2003.05958, 2203.13053, 1810.04383, 1609.03471, 2605.11640,
2605.02286, 2605.00493, 2208.13564, 2605.10400

**Stop condition:** Same as Batch A. Check `failed` count after each batch.

### Batch C — Large papers, extended timeout (7 papers, 14400s timeout each)

**IMPORTANT: Run in single-paper steps first to validate JIT cache state.**

```bash
# Process one large paper to test JIT cold-start cost
docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
  python -m polytool research-marker-queue \
  --queue-dir /app/artifacts/research/scaled_validation_queue_v2 \
  warm-process --max-items 1 --marker-timeout 14400

# Then full batch once single-paper timing is acceptable
docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
  python -m polytool research-marker-queue \
  --queue-dir /app/artifacts/research/scaled_validation_queue_v2 \
  warm-process --max-items 6 --marker-timeout 14400
```

Papers: 2508.03474, 2308.04947, 2403.09267, 2212.12717, 2602.21091, 2604.20050, 2604.10005

**Stop condition:** If 2508.03474 (9.7MB) exceeds 14400s, escalate. That paper is an
outlier and may not be parseable within any reasonable timeout.

### Batch D — Tier-3 papers (requires operator approval before inclusion)

**Do not run without explicit operator approval.**

```bash
# Re-enqueue (already tagged --tier 3 after this reset session)
# arxiv:1011.6402 and arxiv:2409.02025 are already pending with ingest_tier=3

docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
  python -m polytool research-marker-queue \
  --queue-dir /app/artifacts/research/scaled_validation_queue_v2 \
  warm-process --max-items 2 --marker-timeout 7200
```

**For 1011.6402:** If 7200s is not sufficient, try 14400s. If still failing, mark as
permanently excluded from the corpus. This paper confirmed timeout at 3600s in Batch 2.

**For 2409.02025:** Verify PDF is accessible and cached before running. Check
`pdf_cache/arxiv:2409.02025.pdf` exists and is non-zero.

### After each batch: index-done (inside Docker)

```bash
docker exec polytool-ris-scheduler-gpu sh -c "cd /app && python -m polytool \
  research-marker-queue \
  --queue-dir /app/artifacts/research/scaled_validation_queue_v2 index-done --json"
```

Run `index-done` after each warm-process batch to keep indexed_count current.

### After all batches: Chroma embedding (requires remediation of embedding gap first)

See Chroma Embedding Gap section above for remediation path.

### Timeout policy summary

| Paper size bucket | `--marker-timeout` | Batching |
|---|---|---|
| Small (≤600KB) | 3600s | Batch A |
| Medium (601–1500KB) | 7200s | Batch B |
| Large (>1500KB) | 14400s | Batch C |
| Tier-3 confirmed risk | 7200s+ / operator decision | Batch D |

### What NOT to do

- Do not run `warm-process` without verifying all 24 PDFs are still cached first.
- Do not include Tier-3 papers (1011.6402, 2409.02025) in Batch A/B/C automatically.
- Do not skip `index-done` after each batch — keep indexed_count accurate.
- Do not treat a partial pass (e.g. 20/24 parsed) as a valid 29-paper measurement.
- Do not reset done papers with `--force` — preserve Batch 2's 5 successful parses.
- Do not reduce gate thresholds if the batch fails — investigate root cause instead.

---

## Queue Readiness Verdict

**PARTIAL**

| Dimension | Status |
|---|---|
| Queue state (no stuck/failed items) | ✅ PASS — pending=24, failed=0, processing=0 |
| Done sidecars indexed in KS | ✅ PASS — 5 papers, 227 chunks, 1106 claims |
| All pending PDFs prefetched | ✅ PASS — 24/24 cached |
| Chroma embedding of done papers | ⚠️ PARTIAL — 1/5 in Chroma (1106.5040); 4/5 missing (architectural split) |
| JIT cache persistence | ⚠️ UNPROVEN — diagnostic not run inside GPU container this session |
| Tier-3 risk papers identified | ✅ PASS — 1011.6402 and 2409.02025 tagged ingest_tier=3; 7 large papers flagged |
| Next-run command plan | ✅ PASS — 4-batch plan with timeouts and stop conditions |

**The queue is ready to run the full 29-paper warm-process** contingent on:
1. Operator approval for Tier-3 papers (1011.6402, 2409.02025) before Batch D.
2. JIT cache diagnostic inside Docker to bound expected runtime.
3. Chroma embedding gap resolution before treating the final validation as Chroma-complete.
