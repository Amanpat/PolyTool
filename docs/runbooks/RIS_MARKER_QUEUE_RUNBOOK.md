# RIS Marker Parse Queue — L1 Operator Runbook

**Status:** Production-ready as of 2026-05-09 (L1 Marker Production Readiness Rollout complete)
**Track:** Research Intelligence System — Layer 1
**Feature doc:** `docs/features/FEATURE-ris-l1-marker-production-readiness-rollout.md`
**IPC warm-worker doc:** `docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md`

---

## Top-Down Pipeline Flow (Discover → Filter → Parse → Query)

The full academic pipeline has four layers. Each layer produces output for the next.
No paper becomes RAG-ready until it completes L1 Marker parse.

```
L4 Harvest (research-harvest)
  └─ AcademicCandidate records (metadata only — no PDF, no Marker)
       ↓
L3 Relevance Filter (scored inline by research-harvest)
  └─ allow/review → ReviewQueueStore
  └─ reject → dropped
       ↓
Operator label (research-prefetch-review list / label)
  └─ allow → enqueue to Marker queue
       ↓
L1 Marker Parse (research-marker-queue enqueue + warm-process)
  └─ body_source=marker, body_length>=5000 → RAG-ready
  └─ body text + metadata persisted to bodies/{candidate_id}.body.txt/.meta.json
  └─ marker_failed / short → rejected (retryable)
       ↓
Index (research-marker-queue index-done)
  └─ reads bodies/ sidecar → IngestPipeline → KnowledgeStore
  └─ idempotent: tracks indexed.jsonl; skips already-indexed
       ↓
L2 Query (research-query --question "...")
  └─ multi-angle KS query over Marker-ready academic corpus
```

### Quick start (full pipeline)

```bash
# Step 1 — Discover candidates (L4, no PDF, no Marker)
python -m polytool research-harvest \
  --search "prediction markets microstructure" \
  --source all --max-results 10

# Step 2 — Review and label candidates
python -m polytool research-prefetch-review list
python -m polytool research-prefetch-review label --id CANDIDATE_ID --label allow

# Step 3 — Enqueue allowed papers to Marker queue (L1)
python -m polytool research-marker-queue enqueue --url ARXIV_ID

# Step 4 — Parse (inside Docker/GPU container)
python -m polytool research-marker-queue warm-process --max-items 5

# Step 4b — Index completed papers AND extract claims (L2 handoff)
#           Claims are extracted automatically; no separate step needed.
python -m polytool research-marker-queue index-done

# Step 5 — Query the Marker-ready corpus (L2)
python -m polytool research-query --question "optimal spread in prediction markets"
```

Current L1 direct enqueue supports arXiv IDs/URLs. L4 candidates discovered from
Crossref or OpenReview can still be reviewed and labeled, but they need operator
resolution to an arXiv URL before the current Marker queue can parse them.

---

## Overview

The Marker parse queue is the canonical production path for ingesting academic PDFs into
the RIS knowledge store. Papers enqueued here are parsed by Marker (GPU-accelerated,
structure-preserving), and only `body_source=marker` papers are eligible for ChromaDB
indexing.

**pdfplumber is legacy/debug only.** `RIS_PDF_PARSER=pdfplumber` is a debug override, not a
production path.

---

## Prerequisites

- Docker Desktop with GPU passthrough enabled on the dev machine
- RTX 2070 Super, CUDA 13.2 (validated 2026-05-08)
- `docker compose --profile ris-gpu up -d` running (or use `run --rm`)
- Marker model weights volume-mounted from `~/.cache/datalab/` on the host

Verify GPU passthrough before first use:
```bash
docker compose --profile ris-gpu run --rm ris-scheduler-gpu nvidia-smi
```

---

## Operator Path (end-to-end)

### Step 1 — Enqueue one or more arXiv papers

```bash
# By arXiv ID
python -m polytool research-marker-queue enqueue --url 2604.24366

# By full URL
python -m polytool research-marker-queue enqueue \
  --url https://arxiv.org/abs/2604.24366

# With optional title hint (skips arXiv API resolution)
python -m polytool research-marker-queue enqueue \
  --url 2604.24366 --title "Polymarket microstructure"

# Enqueue multiple papers
python -m polytool research-marker-queue enqueue --url 2604.24366
python -m polytool research-marker-queue enqueue --url 2109.07581
python -m polytool research-marker-queue enqueue --url 1910.08858

# Force re-enqueue (resets existing entry to pending)
python -m polytool research-marker-queue enqueue --url 2604.24366 --force
```

Output: `Enqueued: arxiv:2604.24366  (status=pending)`

### Step 2 — Check the queue

```bash
# Item counts by status
python -m polytool research-marker-queue counts

# List all items
python -m polytool research-marker-queue list

# Filter by status
python -m polytool research-marker-queue list --status pending
python -m polytool research-marker-queue list --status done
python -m polytool research-marker-queue list --status failed
```

### Step 3 — Process with IPC warm-worker (Linux/Docker — production path)

Run the warm-process command inside the GPU Docker container:

```bash
docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
  python -m polytool research-marker-queue warm-process \
  --max-items 5 \
  --marker-timeout 900
```

- `--max-items N` — process up to N pending items in one session (default: 1)
- `--marker-timeout SECONDS` — per-paper Marker extraction timeout (default: 900s)
- Models load once at session start (paper 1 ~72s total); papers 2+ pay only inference (~45-70s)

**Expected output (per paper):**
```
[PASS] arxiv:2604.24366
       body_source:          marker
       body_length:          56,923 chars
       parse_seconds:        45.6s
       queue_status:         done  marker_ready=True
       ipc_warm_worker_used: True
```

### Step 4 — Inspect results

```bash
# Count by status
python -m polytool research-marker-queue counts

# View completed papers
python -m polytool research-marker-queue list --status done

# View failed papers (inspect failure_reason)
python -m polytool research-marker-queue list --status failed

# Raw results log (gitignored)
# Each line is a JSON result record with body_source, body_length, parse_seconds, etc.
type artifacts\research\marker_parse_queue\results.jsonl
```

Key fields in results.jsonl:
- `body_source`: `"marker"` (success) or `"marker_failed"` / `"error"` (failure)
- `body_length`: character count of extracted body
- `parse_seconds`: Marker extraction time
- `ipc_warm_worker_used`: true when IPC warm-worker was active
- `marker_ready`: canonical RAG-readiness flag (`body_source=marker` AND `body_length >= 5000`)
- `failure_reason`: why the paper was rejected (null on success)
- `queue_status`: final queue state after processing (`done` | `pending` | `failed`)

### Step 4b — Index completed papers + extract claims (L2 handoff)

After `warm-process` completes, run `index-done` to load Marker-ready papers
into the KnowledgeStore **and automatically extract claims** so `research-query`
can return citations immediately.

```bash
# Index all marker-ready done items AND extract claims (default)
python -m polytool research-marker-queue index-done

# Index only — skip claim extraction
python -m polytool research-marker-queue index-done --no-extract-claims

# Re-index even already-indexed papers (e.g. after KS corruption)
python -m polytool research-marker-queue index-done --force

# Use a non-default queue dir
python -m polytool research-marker-queue --queue-dir PATH index-done

# JSON output for scripting
python -m polytool research-marker-queue index-done --json
```

**How it works:**

1. Reads `results.jsonl` — finds all records with `queue_status=done` AND `marker_ready=True`
2. For each candidate, reads body text from `bodies/{candidate_id}.body.txt`
3. Reads fetch metadata from `bodies/{candidate_id}.meta.json` (title, abstract, authors, etc.)
4. Adds a `body_file` pointer (file:// URI) to the source metadata so the claim extractor
   can read the body without duplicating large text in the KnowledgeStore DB
5. Calls `IngestPipeline.ingest_external(raw_source, "academic")` — enforces Marker gate
6. Runs heuristic claim extraction (`extract_and_link`) for each indexed paper (non-fatal;
   failure is logged but the paper is still recorded as indexed)
7. Records indexed candidates in `indexed.jsonl` for idempotency

**Expected output (per paper):**
```
Indexed 1 paper(s):
  [OK] arxiv:2604.24366  doc_id=abc123...  chunks=47  claims=38
Total: 1 done item(s) examined — 1 indexed, 0 already-indexed, 0 no-body, 0 failed, 38 claim(s) extracted.
```

**Idempotency:** Running `index-done` twice skips already-indexed papers. Use
`--force` to re-index (e.g. after rebuilding the KnowledgeStore). Claim
extraction is idempotent: re-running on the same doc produces the same claim IDs
(INSERT OR IGNORE semantics in the KnowledgeStore).

**Windows host note (NTFS colon restriction):** Candidate IDs like `arxiv:1106.5040`
contain colons. NTFS treats `:` as an Alternate Data Stream separator, so Windows
Python cannot open `bodies/arxiv:1106.5040.body.txt` as a regular file. Running
`index-done` from the Windows host will report "body file missing" for all papers.
**Always run `index-done` inside the Docker container** when using the GPU parse path:

```bash
docker exec polytool-ris-scheduler-gpu sh -c "cd /app && python -m polytool \
  research-marker-queue --queue-dir /app/artifacts/research/QUEUE_DIR index-done"
```

Confirmed 2026-05-17 smoke test: `index-done` inside container indexed all 4 papers
(674 claims) cleanly; host-side run reported 4 no-body failures for the same files.

**Body file missing (pre-fix queue items):** Papers processed before 2026-05-09
do not have body sidecar files. `index-done` reports them as `no-body` and
suggests re-enqueuing with `--force`:

```bash
python -m polytool research-marker-queue enqueue --url ARXIV_ID --force
python -m polytool research-marker-queue warm-process --max-items 1
python -m polytool research-marker-queue index-done
```

Output locations (gitignored):

| Artifact | Path |
|----------|------|
| Body text | `artifacts/research/marker_parse_queue/bodies/{candidate_id}.body.txt` |
| Fetch metadata | `artifacts/research/marker_parse_queue/bodies/{candidate_id}.meta.json` |
| Indexed log | `artifacts/research/marker_parse_queue/indexed.jsonl` |

---

## Queue States

| State | Meaning | Operator action |
|-------|---------|-----------------|
| `pending` | Enqueued; not yet picked up by worker | None — worker will process on next run |
| `processing` | Worker actively parsing this paper | Wait. If stuck (worker crashed mid-paper), re-enqueue with `--force` |
| `done` | Parse complete; result written to results.jsonl | Check `marker_ready` in results.jsonl |
| `failed` | Max retries (3) exceeded; terminal failure | Inspect `failure_reason` in results.jsonl; paper is not RAG-eligible |

**Note on retries:** A paper returns to `pending` on transient failure (timeout, container
restart) until `attempts >= MAX_ATTEMPTS=3`, then becomes `failed`. Use `--force` on
`enqueue` to reset attempts to 0 and return to `pending`.

---

## RAG-Readiness Rule

```
marker_ready = body_source == "marker" AND body_length >= 5000 chars
```

Only `marker_ready=True` papers are eligible for ChromaDB embedding and indexing.
Papers with `body_source=marker_failed`, `pdfplumber`, `abstract_fallback`, or
`error` are **not** RAG-eligible regardless of body length.

This rule is enforced by `is_marker_ready()` in `packages/research/ingestion/marker_queue.py`
and the `IngestPipeline.ingest_external()` academic gate in `packages/research/ingestion/pipeline.py`.

---

## Output Locations

All artifacts are gitignored.

| Artifact | Path |
|----------|------|
| Queue state | `artifacts/research/marker_parse_queue/queue.jsonl` |
| Results log (append-only) | `artifacts/research/marker_parse_queue/results.jsonl` |
| Custom queue dir | `--queue-dir PATH` flag on all subcommands |

---

## Recovery Procedures

### Paper stuck in `processing` (worker crashed)
```bash
python -m polytool research-marker-queue enqueue --url ARXIV_ID --force
```
Resets attempts to 0 and returns the paper to `pending`.

### Paper in `failed` (max retries exceeded)
1. Inspect failure reason:
   ```bash
   type artifacts\research\marker_parse_queue\results.jsonl
   # Find the candidate_id and read failure_reason
   ```
2. If the failure was transient (timeout, container restart): re-enqueue with `--force`
3. If the failure is permanent (image-only PDF, corrupted file, missing text): the paper
   is not suitable for Marker. Leave as `failed`.

### No GPU available
- The warm IPC worker requires a CUDA-capable GPU inside the container.
- Without GPU, Marker falls back to CPU (very slow: 300+ s/page on complex papers).
- Check GPU passthrough with `nvidia-smi` before starting a batch.

---

## Platform Behavior

| Platform | Worker mode | Production? |
|----------|-------------|-------------|
| Windows local dev | Thread warm worker — pre-loads model dict once | Dev/debug only |
| Linux/Docker | **IPC warm-worker** — models in GPU VRAM across all papers | **Production target** |

On Windows, `warm-process` falls back to the thread warm worker automatically.
The IPC warm-worker (Linux/Docker) is the production path validated on 2026-05-08.

---

## Performance Expectations

| Scenario | Expected time |
|----------|--------------|
| Paper 1 (cold model load) | ~45-70s inference + ~27s cold-load overhead ≈ 72-97s total |
| Papers 2+ (warm) | ~45-70s inference, ≤1s overhead (models stay in GPU VRAM) |
| Short prose paper (15 pages) | ~45-55s warm |
| Dense math/ML paper (25-46 pages) | ~60-70s warm |

These times are hardware constants for the RTX 2070 Super with Marker's five-model
pipeline. They cannot be reduced by queue design. The IPC warm-worker eliminates only
the cold-load overhead (27s) for papers 2+.

Validated timings from 2026-05-08 live session:
- arxiv:2604.24366 (15p) — 45.55s parse, 72.31s total (cold)
- arxiv:2109.07581 (COVID-19 sports betting) — 69.73s parse, 69.86s total (warm, delta=0.13s)
- arxiv:1910.08858 (Sports betting inefficiencies) — 48.31s parse, 48.53s total (warm, delta=0.22s)

---

## Querying the Academic Corpus (L2 — research-query)

Once papers are processed (`queue_status=done, marker_ready=True`), query
the academic corpus with the `research-query` command:

```bash
# Keyword query
python -m polytool research-query --question "market microstructure"

# Natural-language questions also work — preamble stripped for retrieval only
python -m polytool research-query --question "what are prediction markets"
python -m polytool research-query --question "explain sports betting markets"

# More citations with step-back context angle
python -m polytool research-query \
  --question "sports betting inefficiencies" \
  --k 10 --step-back

# Single-angle query (primary only, no template expansions)
python -m polytool research-query \
  --question "avellaneda stoikov spread model" \
  --max-angles 1
```

**How it works:**

1. Multi-angle query planning (up to `--max-angles` template variants)
2. Question preambles stripped for retrieval ("what are prediction markets" → also searches "prediction markets"); original question preserved in JSON output
3. KnowledgeStore queried with `source_family="academic"` for each angle
4. Source metadata is re-checked: `body_source=marker` and `body_length >= 5000`
5. Claims deduplicated by ID; grouped by source paper
6. Papers ranked by highest claim score
7. Citations returned with: title, arxiv_id, source_url, snippet, body_source

**Retrieval is conservative substring/phrase matching — not semantic or vector retrieval.**

**Prerequisite:** Papers must be indexed into the KnowledgeStore first.
Use `research-marker-queue` (Steps 1–4 above) then **Step 4b** (`index-done`):

```bash
python -m polytool research-marker-queue index-done
```

**No-result cases** — both return `had_fallback=true` with an actionable warning:

| Case | Cause | Action |
|------|-------|--------|
| Empty corpus | KnowledgeStore has no academic documents | Run `index-done` first; confirm `warm-process` produced `marker_ready=True` results |
| Corpus exists, no matches | Academic docs indexed but no claim text matches the query | Expand corpus or try a different topic phrase |

Feature doc: `docs/features/FEATURE-ris-l2-academic-query.md`

---

## Known-Good 3-Paper Validation (2026-05-09)

The full pipeline sequence was operator-validated on 2026-05-09 using an isolated queue
(`artifacts/research/operator_test_queue_3paper`).

**High-level sequence run:**

```
research-harvest (or manual enqueue)
  → research-marker-queue enqueue --url ARXIV_ID
  → research-marker-queue warm-process --max-items 3
  → research-marker-queue index-done
  → research-query --question "..."
```

**Pass criteria met:**

| Criterion | Result |
|-----------|--------|
| Queue: 3 done, 0 failed | ✅ |
| All papers: `body_source=marker` | ✅ |
| All papers: `body_length >= 5000` | ✅ (56,856 / 51,370 / 60,814 chars) |
| Total chunks indexed | 79 |
| Total claims extracted | 373 |
| `research-query "prediction markets"` → `had_fallback=false` | ✅ |
| `research-query "sports betting markets" --step-back` → 2 Marker citations | ✅ |

**Caveats:**

- Run used **Windows/local warm-thread path** (`ipc_warm_worker_used=false`). This is a
  functional validation, not a Docker/GPU IPC performance run.
- Docker/GPU IPC 3-paper batch (`ipc_warm_worker_used=true`) was validated separately on
  2026-05-08 and is an optional performance/infra follow-up.
- SSRN/NBER sources deferred. Only arXiv papers used.
- ChromaDB academic retrieval (L2.1) deferred.

**Dev log:** `docs/dev_logs/2026-05-09_ris-academic-pipeline-3paper-operator-validation.md`

---

## Scope Notes

- **L2 PaperQA2** — COMPLETE 2026-05-09. `research-query` CLI ships multi-angle
  KS query with paper-level citations and a query-time Marker-ready guard. See
  feature doc above.
- **L4 Multi-source harvesters** — COMPLETE 2026-05-09. `research-harvest`
  ships arXiv, Semantic Scholar, Crossref, and OpenReview metadata discovery,
  source selection, deduplication, L3 scoring, and review-queue enqueue. SSRN/NBER
  remain deferred with explicit rationale.
- **SVM enforce** remains hard-blocked at rc=1. Default lexical filter is active.
- **pdfplumber** is legacy/debug only. Never used in the production canonical path.
- **Bulk re-ingest** of existing pdfplumber-parsed ChromaDB entries is a separate cleanup
  task — not part of this runbook.
