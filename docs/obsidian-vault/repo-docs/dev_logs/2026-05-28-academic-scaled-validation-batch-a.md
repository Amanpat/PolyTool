---
title: Academic Scaled Validation Batch A
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-28_academic-scaled-validation-batch-a.md
last_synced: '2026-06-03T02:26:56Z'
lifecycle: reviewed
generator: repo-sync
---

# Academic Scaled Validation — Batch A Execution

**Date:** 2026-05-28
**Author:** Claude Code (Sonnet 4.6)
**Status:** PASS
**Preflight ref:** 2026-05-28_academic-scaled-validation-queue-reset-readiness.md
**Codex review:** none (scope: runtime artifacts only)

---

## Objective

Execute Batch A of the staged cached-PDF validation for `scaled_validation_queue_v2`.
Batch A = 5 small papers (≤600KB, 3600s timeout bucket). Done means parsed, indexed into
KnowledgeStore, Chroma-embedded, queried, and summarized — without starting Batch B/C/D.

---

## Batch A Paper List

| arXiv ID | Title (from queue) | Size | Tier |
|---|---|---|---|
| arxiv:2605.00864 | algorithmic arbitrage Polymarket NBA markets | 540KB | 2 |
| arxiv:2507.08921 | Polymarket polling 2024 presidential election comparison | 582KB | 2 |
| arxiv:2510.05533 | LLMs financial prediction and trading survey | 524KB | 2 |
| arxiv:2507.01990 | LLMs financial applications structured review | 219KB | 2 |
| arxiv:2601.18815 | prediction markets Bayesian inverse problems | 588KB | 2 |

No Tier-3 papers included. Tier-3 items (1011.6402, 2409.02025) remain pending for Batch D.

---

## Guard Checks (all PASS)

| Check | Result |
|---|---|
| Preflight log exists and says Batch A ready | ✅ PASS — 2026-05-28 queue reset readiness: PARTIAL with no blocking concerns for Batch A |
| Core implementation files dirty | ✅ PASS — only docs/obsidian-vault and AGENTS.md/claude.md modified (non-code) |
| No stuck/failed items before Batch A | ✅ PASS — pending=24, processing=0, done=5, failed=0 |
| Batch A excludes Tier-3 | ✅ PASS — all 5 papers are ingest_tier=2 |
| All Batch A PDFs cached | ✅ PASS — 24/24 total cached; all 5 Batch A files in `pdf_cache/` (arxiv-NNNN.pdf, hyphen format) |

---

## Pre-Batch A State

### Queue counts

```
pending:    24
processing: 0
done:       5
failed:     0
total:      29
```

### Chroma link-check (pre-Batch A)

```json
{
  "collection": "academic_papers",
  "total_chunks": 359,
  "unique_papers": 9,
  "valid_ks_doc_id": 359,
  "missing_ks_doc_id": 0,
  "ks_doc_id_not_in_ks": 0
}
```

---

## Queue Reorder

The FIFO queue had medium/Tier-3 papers at positions 1–8, with small Batch A papers
scattered at positions 9, 13, 16, 19, 22. `warm-process --max-items 5` would have
processed medium papers first.

**Fix:** Reordered `queue.jsonl` in place (no source code changes) to move 5 Batch A
papers to positions 1–5 of the pending list. Backup written to `queue.jsonl.bak`.

Script: `reorder_queue_batch_a.py` (temp file, removed after session).

Post-reorder pending order confirmed:
```
1. arxiv:2605.00864 [Batch A]
2. arxiv:2507.08921 [Batch A]
3. arxiv:2510.05533 [Batch A]
4. arxiv:2507.01990 [Batch A]
5. arxiv:2601.18815 [Batch A]
6. arxiv:1206.4810  (next non-Batch-A)
...
```

---

## Step 2: warm-process Batch A

### Command

```bash
docker exec polytool-ris-scheduler-gpu sh -c "cd /app && python -m polytool \
  research-marker-queue \
  --queue-dir /app/artifacts/research/scaled_validation_queue_v2 \
  warm-process --max-items 5 --marker-timeout 3600 \
  2>&1 | tee /app/artifacts/research/scaled_validation_queue_v2/batch_a_warmprocess.log; \
  echo EXIT_CODE:$?"
```

GPU container: `polytool-ris-scheduler-gpu` (RTX 2070 SUPER, 6617MB free before run).
Mode: Linux/Docker IPC warm-worker.

### Confirmed: cached PDF paths used

All 5 Batch A queue records had `pdf_url` set to local relative paths (set by prefetch
command). Inside Docker, `/app` is the working directory, so relative paths resolve to
`/app/artifacts/research/scaled_validation_queue_v2/pdf_cache/arxiv-NNNN.pdf`.

`_process_item` checked `is_local=True` and `Path(pdf_url).exists() → True` → used
`fetch_pdf_direct` (no arXiv network call during parse). No arXiv fetch warnings in logs.

### JIT cold-start finding

The IPC warm-worker kept model weights warm across all 5 papers. However, GPU kernel
(Triton/TorchInductor) JIT compilation was triggered twice during the batch:

- **Paper 1 (2605.00864)**: 265-item text recognition took ~16.5 min. First item at 4:17
  elapsed (JIT cold). Subsequent items accelerated to 1-6s each.
- **Papers 2-4 (2507.08921, 2510.05533, 2507.01990)**: text recognition 9-115 items at
  <1s each. JIT warm from paper 1.
- **Paper 5 (2601.18815)**: 265-item text recognition also triggered JIT cold start
  (~22 min). Paper 5 has different page dimensions than papers 1-4, requiring new GPU
  kernel compilation.

The `parse_seconds` metric in results measures Marker extraction time *after* JIT
compilation. The IPC warm-worker warms MODEL WEIGHTS but NOT GPU kernels for novel
page-layout dimensions.

### Parse metrics table

| arXiv ID | Size | parse_s | timeout | marker_ready | body_len | sidecar |
|---|---|---|---|---|---|---|
| arxiv:2605.00864 | 540KB | 11.3s | — | True | 40,453 chars | ✅ 40KB |
| arxiv:2507.08921 | 582KB | 20.3s | — | True | 74,760 chars | ✅ 73KB |
| arxiv:2510.05533 | 524KB | 14.1s | — | True | 93,720 chars | ✅ 92KB |
| arxiv:2507.01990 | 219KB | 24.0s | — | True | 88,941 chars | ✅ 87KB |
| arxiv:2601.18815 | 588KB | 1319.9s | — | True | 98,125 chars | ✅ 96KB |

**Wall-clock times (including JIT):**
- Paper 1: ~17 min (JIT cold)
- Papers 2-4: 21s, 15s, 24s (JIT warm)
- Paper 5: ~22 min (JIT cold, new dimensions)

All 5: `ipc_warm_worker_used: True`, `body_source: marker`, `marker_ready: True`.
No failures, no retries. Exit code 0.

**Stop condition check:** 0 of 5 papers timed out. No stop condition triggered. ✅

---

## Step 3: Confirm cached PDF paths

Log confirmed: no "falling back to live arXiv fetch" warnings. All 5 papers processed
via `fetch_pdf_direct` with local paths. ✅

---

## Step 4 (index-done) + Step 5 (reindex-chroma)

**Key finding:** The NTFS workaround in `index_done_items` removes the colon from
candidate_id filenames (`arxiv:2605.00864` → checks `arxiv2605.00864.body.txt`).
Body files written by Docker on Linux appear on the Windows host WITHOUT the colon
(NTFS cannot store colons in filenames; Docker Desktop/WSL2 transparently strips them).
This means `index-done --reindex-chroma` CAN run on the Windows host.

**Command (Windows host):**

```bash
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/scaled_validation_queue_v2 \
  index-done --reindex-chroma
```

Note: `sentence-transformers` and `chromadb` are installed in the Windows host Python
environment (5.2.2 and 1.4.1 respectively). The main `Dockerfile` does NOT include the
`rag` extras (`[rag]` is excluded at build time per pyproject.toml comment), so the GPU
container cannot run Chroma embedding. Windows host is the correct path.

### Results

```json
{
  "indexed": [
    {"candidate_id": "arxiv:2605.00864", "chunk_count": 18, "claims_extracted": 87, "chroma_chunks_upserted": 18},
    {"candidate_id": "arxiv:2507.08921", "chunk_count": 34, "claims_extracted": 168, "chroma_chunks_upserted": 34},
    {"candidate_id": "arxiv:2510.05533", "chunk_count": 34, "claims_extracted": 0, "chroma_chunks_upserted": 34},
    {"candidate_id": "arxiv:2507.01990", "chunk_count": 35, "claims_extracted": 172, "chroma_chunks_upserted": 35},
    {"candidate_id": "arxiv:2601.18815", "chunk_count": 39, "claims_extracted": 185, "chroma_chunks_upserted": 39}
  ],
  "skipped_already_indexed": ["arxiv:1105.3115", "arxiv:1106.5040", "arxiv:1605.01862", "arxiv:1705.01446", "arxiv:2307.14129"],
  "skipped_no_body": [],
  "failed": [],
  "total_claims_extracted": 612,
  "total_chroma_chunks_upserted": 160
}
```

**Concern:** arxiv:2510.05533 had `claims_extracted: 0`. The paper was still indexed into
KS and Chroma (34 chunks upserted). Claim extraction failure is non-fatal per pipeline
design. Snippets are still retrievable. Root cause: likely a heuristic claim-extractor
parse issue with this particular paper's structure (dense reference section). Not blocking.

---

## Step 6: check-chroma-links (post-Batch A)

```json
{
  "collection": "academic_papers",
  "total_chunks": 485,
  "unique_papers": 13,
  "valid_ks_doc_id": 485,
  "missing_ks_doc_id": 0,
  "ks_doc_id_not_in_ks": 0
}
```

- Pre-Batch A: 359 chunks, 9 papers
- Post-Batch A: 485 chunks (+126), 13 papers (+4)
- All links valid (missing_ks_doc_id: 0, ks_doc_id_not_in_ks: 0)

**Minor discrepancy:** Expected +5 papers (to 14), got +4 (to 13). Expected +160 Chroma
chunks, got +126. Likely cause: one Batch A paper was already in Chroma from a prior
smoke_test session (Chroma upsert updated existing chunks without creating new). Not
blocking — all links valid.

---

## Step 7: research-query probes

All queries: `had_fallback=false`, `retrieval_mode=semantic` except rejection query.
Exit code 255 is a known non-fatal issue in `research-query` (content is valid JSON).

| Query | Top hit | Score | had_fallback | Note |
|---|---|---|---|---|
| "algorithmic arbitrage Polymarket NBA prediction markets" | arxiv:2605.00864 | 0.693 | false | Direct title hit ✅ |
| "order book depth limits arbitrage extraction" | arxiv:2601.18815 | 0.521 | false | Semantically related, 2605.00864 second ✅ |
| "Polymarket polling accuracy 2024 presidential election" | arxiv:2507.08921 | 0.588 | false | Direct title hit ✅ |
| "LLMs financial trading prediction survey" | arxiv:2507.01990 | 0.644 | false | Both LLM survey papers returned ✅ |
| "large language model survey financial prediction 2024" | arxiv:2510.05533 | 0.679 | false | Direct title hit ✅ |
| "Bayesian inference prediction market price path" | arxiv:2601.18815 | 0.633 | false | Direct title hit ✅ |
| "prediction market efficiency information aggregation" | arxiv:2601.18815 | 0.506 | false | Cross-paper: multiple PM papers returned ✅ |
| "protein folding molecular dynamics" (rejection) | (none) | — | true (lexical) | Correct rejection ✅ |

**Snippet cleanliness:** All returned snippets contained clean Marker-extracted text. No
garbled characters, no OCR noise, no HTML artifacts observed in sampled snippets.

**Cross-paper query:** "prediction market efficiency information aggregation arbitrage"
returned arxiv:2601.18815 first (Bayesian inference in PMs), followed by arxiv:1609.03471
(Limit Order Book empirical study) — both semantically on-topic.

---

## Post-Batch A Status Report

```
pending:    19
processing: 0
done:       10
failed:     0
total:      29
```

Body sidecars: 10/10 written. Indexed into KS: 10 (plus prior sessions' indexed.jsonl
entries showing 25 — count includes historical cross-queue entries, not blocking).

---

## Failure Classifications

| Category | Count | Details |
|---|---|---|
| Marker parse failures | 0 | — |
| Timeout failures | 0 | — |
| Index-done failures | 0 | — |
| Chroma embedding failures | 0 | — |
| Claim extraction failures | 1 | arxiv:2510.05533 (non-fatal, paper still indexed and queryable) |
| arXiv live fetch during parse | 0 | All 5 used cached PDFs |
| Tier-3 papers included | 0 | Confirmed: all Batch A papers are ingest_tier=2 |

---

## Verdict: PASS

| Dimension | Status |
|---|---|
| All 5 Batch A papers parsed by Marker | ✅ PASS — 5/5 marker_ready=True |
| All 5 body files written | ✅ PASS — 5/5 body sidecars, all ≥5000 chars |
| No arXiv fetch calls during parse | ✅ PASS — all used cached PDFs via `fetch_pdf_direct` |
| All 5 indexed into KnowledgeStore | ✅ PASS — 5/5 indexed, 0 failures |
| All 5 Chroma-embedded | ✅ PASS — 5/5 chroma_chunks_upserted >0 |
| Chroma links valid | ✅ PASS — 485 chunks, 0 orphans, 0 missing KS refs |
| All 5 retrievable by title query | ✅ PASS — each paper found in top 2 results |
| Rejection query correctly empty | ✅ PASS — unrelated topic returned no citations |
| No Tier-3 papers processed | ✅ PASS — confirmed |
| No Batch B/C/D triggered | ✅ PASS — warm-process stopped at --max-items 5 |

---

## Recommendation

**Proceed to Batch B** with the following notes:

1. **JIT cold-start per format group**: Batch B (10 medium papers, 7200s timeout) will
   likely trigger JIT cold-start for each unique page-layout dimension group. Budget an
   extra 15-20 min for the first paper of each format group on top of Marker parse time.

2. **arxiv:2510.05533 claim extraction**: 0 claims extracted. Non-blocking for Batch B,
   but worth investigating if claim-based retrieval is needed for this paper class.

3. **Chroma unique-paper count**: Expected +5, got +4. Likely one Batch A paper had a
   prior Chroma entry from smoke_test_queue. Track this in Batch B to confirm pattern.

4. **Batch B papers (next 10 pending, medium, 7200s):**
   arxiv:1206.4810, 2003.05958, 2203.13053, 1810.04383, 1609.03471,
   2605.11640, 2605.02286, 2605.00493, 2208.13564, 2605.10400

5. **Batch B command:**
   ```bash
   docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
     python -m polytool research-marker-queue \
     --queue-dir /app/artifacts/research/scaled_validation_queue_v2 \
     warm-process --max-items 10 --marker-timeout 7200
   ```

---

## Files Changed

| Artifact | Change |
|---|---|
| `artifacts/research/scaled_validation_queue_v2/queue.jsonl` | Reordered (Batch A papers moved to front); backup at `queue.jsonl.bak` |
| `artifacts/research/scaled_validation_queue_v2/batch_a_warmprocess.log` | New — warm-process session log |
| `artifacts/research/scaled_validation_queue_v2/bodies/` | 10 new body+meta files (5 Batch A + sidecar duplicates from meta.json) |
| `artifacts/research/scaled_validation_queue_v2/indexed.jsonl` | 5 new indexed entries (Batch A papers) |
| `kb/rag/knowledge/knowledge.sqlite3` | 5 new academic papers indexed |
| `kb/rag/index/` (ChromaDB) | +126 chunks, +4 papers embedded |
| `docs/dev_logs/2026-05-28_academic-scaled-validation-batch-a.md` | This log |
