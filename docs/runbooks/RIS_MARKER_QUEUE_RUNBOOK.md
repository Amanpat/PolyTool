# RIS Marker Parse Queue — L1 Operator Runbook

**Status:** L1 pipeline production-ready as of 2026-05-09. WP-1 prefetch separation shipped 2026-05-19 — `prefetch` and `status-report` subcommands are live.
**Track:** Research Intelligence System — Layer 1
**Feature doc:** `docs/features/FEATURE-ris-l1-marker-production-readiness-rollout.md`
**IPC warm-worker doc:** `docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md`
**Operational triage:** `docs/dev_logs/2026-05-18_academic-ris-operational-triage.md`

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
L1 Marker Parse (research-marker-queue enqueue + prefetch + warm-process)
  └─ prefetch: downloads PDFs to local cache before GPU parse (WP-1)
  └─ warm-process reads from cache — no live arXiv calls during parse
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

### Which path to follow

> **First run or 1–3 papers** → skip to [Operator Path (end-to-end)](#operator-path-end-to-end) below.
> **Batches of 5+ papers** → use the [Prefetch then Parse](#prefetch-then-parse-wp-1-workflow) section immediately after this Quick Start.

---

### Quick start (full pipeline — WP-1 prefetch path)

> **Recommended path for batches of 5+ papers.** The `prefetch` command (Step 3b)
> requires WP-1 to ship. For 1–3 papers on a reliable connection, the pre-WP-1 path
> (enqueue → warm-process directly) still works — see [Operator Path](#operator-path-end-to-end) below.

```bash
# Step 1 — Discover candidates (L4, metadata only — no PDF yet)
python -m polytool research-harvest \
  --search "prediction markets microstructure" \
  --source all --max-results 10

# Step 2 — Review and label candidates
python -m polytool research-prefetch-review list
python -m polytool research-prefetch-review label --id CANDIDATE_ID --label allow

# Step 3 — Enqueue allowed papers to Marker queue
python -m polytool research-marker-queue enqueue --url ARXIV_ID

# Step 3b — Prefetch PDFs to local disk before starting GPU parse  [WP-1]
#            Do this on the Windows host, outside Docker. Safe to retry.
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/marker_parse_queue prefetch \
  --max-items 10 \
  --delay-seconds 5

# Step 4 — Parse cached PDFs (inside Docker/GPU container)
#           warm-process reads from local cache; no live arXiv calls.
docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
  python -m polytool research-marker-queue warm-process \
  --max-items 10 \
  --marker-timeout 900

# Step 4b — Index completed papers AND extract claims (run INSIDE Docker)
# Note: `docker exec` requires a named running container. If Step 4 used `run --rm`,
# that container was removed. Either: (a) start a persistent container first with
#   docker compose --profile ris-gpu up -d
# and then use docker exec, or (b) use docker compose run as shown here:
docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
  sh -c "cd /app && python -m polytool research-marker-queue \
  --queue-dir /app/artifacts/research/marker_parse_queue index-done"

# Step 5 — Query the Marker-ready corpus
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

## Prefetch then Parse (WP-1 Workflow)

### Why this exists

The previous workflow fetched each paper's PDF from arXiv **during** the GPU parse session.
This caused two problems in production:

1. **arXiv rate limiting (HTTP 429):** Once GPU parsing warms up, papers complete in 40–60
   seconds each. Multiple consecutive papers then hit arXiv's download endpoint in rapid
   succession. The built-in retry backoff (5 s / 15 s / 45 s) is not long enough for
   arXiv's rate-limit reset window under load. In the 29-paper Batch 2 run, 5 of the
   first 10 papers failed on fetch alone — not on parsing.

2. **Fetch failure aborts a paper that could parse fine:** A network timeout during
   download marks the paper `failed` and counts against its 3 retry attempts. The GPU is
   idle while this happens.

The fix is to separate fetch from parse:
- **Prefetch** runs on the Windows host, outside Docker, before the GPU session starts.
  It downloads PDFs to a local cache with controlled spacing between requests.
- **warm-process** then reads only from local cache — no live arXiv calls during the
  GPU session.

The GPU is fully occupied parsing. Network errors cannot abort a parse run.

---

### Step-by-step: Prefetch then Parse

#### Before you start — check prerequisites

```bash
# 1. Confirm Docker Desktop is running and GPU passthrough works
docker compose --profile ris-gpu run --rm ris-scheduler-gpu nvidia-smi
# Expected: GPU listed, VRAM shown (e.g. 8192 MiB). If this fails, see Prerequisites below.

# 2. Check queue status — how many papers are pending?
python -m polytool research-marker-queue counts
# Expected output example:
#   pending:    10
#   done:        4
#   failed:      1
#   processing:  0
```

#### Step 1 — Enqueue papers

If you have not already enqueued papers (e.g. after `research-harvest` and labeling), do so now:

```bash
# Single paper by arXiv ID
python -m polytool research-marker-queue enqueue --url 2604.24366

# Multiple papers — run once per arXiv ID
python -m polytool research-marker-queue enqueue --url 2604.24366
python -m polytool research-marker-queue enqueue --url 2109.07581
python -m polytool research-marker-queue enqueue --url 1910.08858
```

Output per paper: `Enqueued: arxiv:2604.24366  (status=pending)`

#### Step 2 — Prefetch PDFs to local cache  [requires WP-1]

> **Run this on the Windows host, outside Docker.** Prefetch only downloads files — it
> does not use the GPU and does not require the Docker container to be running.

```bash
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/marker_parse_queue prefetch \
  --max-items 10 \
  --delay-seconds 5
```

- `--max-items N` — how many pending papers to prefetch (default: all pending)
- `--delay-seconds S` — seconds to wait between each download (default: 10). Use 10–15
  for large batches to stay within arXiv's rate limits.
- `--queue-dir PATH` — path to your queue directory; must go BEFORE the subcommand: `research-marker-queue --queue-dir PATH prefetch`

**Expected output (per paper):**
```
[PREFETCH OK] arxiv:2604.24366  cached to bodies/arxiv:2604.24366.pdf  (1.4 MB)
[PREFETCH OK] arxiv:2109.07581  cached to bodies/arxiv:2109.07581.pdf  (2.1 MB)
```

**Expected output if already cached:**
```
[PREFETCH SKIP] arxiv:2604.24366  already cached — skipping
```

**What to check before moving on:**

```bash
# View the queue status — shows cached count, stuck items, and failed details
python -m polytool research-marker-queue --queue-dir artifacts/research/marker_parse_queue status-report
```

Expected: `prefetch_stats.cached` equals the number of papers you intend to parse.
Papers missing from the cache appear as pending with no `pdf_url`; re-run prefetch.

#### Step 3 — Start the GPU container

```bash
# Verify Docker is running
docker compose --profile ris-gpu run --rm ris-scheduler-gpu nvidia-smi
```

If the container is already running from a previous session, you can use `docker exec`
instead of `run --rm` in the next step.

#### Step 4 — Parse cached PDFs (inside Docker)

> **This step MUST run inside the Docker/GPU container.** Do not run warm-process on the
> Windows host — GPU Marker runs on Linux only and requires the container environment.

```bash
docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
  python -m polytool research-marker-queue warm-process \
  --max-items 10 \
  --marker-timeout 900
```

- `--max-items N` — process up to N papers in one session. Start with 5 to verify before
  committing to a long run.
- `--marker-timeout SECONDS` — per-paper timeout. 900 s (15 min) works for most papers.
  Use 3600 s for known equation-heavy papers. See Troubleshooting for timeout failures.

**Expected output (per paper):**
```
[PASS] arxiv:2604.24366
       body_source:          marker
       body_length:          56,923 chars
       parse_seconds:        45.6s
       queue_status:         done  marker_ready=True
       ipc_warm_worker_used: True
```

**What to watch for:**

| Output | Meaning |
|--------|---------|
| `[PASS] ... marker_ready=True` | Paper parsed successfully. Proceed. |
| `[FAIL] ... failure_reason: fetch_failed` | PDF was not cached; warm-process tried live fetch and failed. Run prefetch again for this paper. |
| `[FAIL] ... failure_reason: cache_missing` | Paper has no cached PDF and no live arXiv fetch available. Run `prefetch` before `warm-process`. |
| `[FAIL] ... failure_reason: marker_timeout` | Paper exceeded the timeout. See Troubleshooting. |
| `[FAIL] ... failure_reason: marker_failed` | Marker could not extract text (image-only PDF, corruption). Paper is not RAG-eligible. |
| `[FAIL] ... failure_reason: parse_error` | Marker returned an error or non-zero exit. PDF may be corrupted or unsupported format. |
| `done` / no sidecar | warm-process completed but body sidecar missing. `index-done` will report `skipped_no_body`. Re-enqueue with `--force` and reprocess. |
| `done` / sidecar present / not in indexed.jsonl | `index-done` not yet run for this paper (`index_pending`). Run `index-done`. |
| KS indexed / `research-query` returns nothing | Query not run, or substring mismatch. Check claim text with SQLite inspection. |

**Performance expectations:**

| Scenario | Expected time |
|----------|--------------|
| Paper 1 in session (cold model load) | 72–97 s total |
| Papers 2+ (warm GPU models) | 45–70 s each |
| Equation-heavy paper (25–46 pages) | 40–49 min warm (JIT recompile for new format group) |

The first paper in a new GPU session pays a one-time 27 s model-load overhead.
Papers in the same "format group" (similar layout) share JIT-compiled kernels and
run much faster after the first of that group.

#### Step 5 — Check parse results

```bash
# Summary counts
python -m polytool research-marker-queue counts

# Detailed list of done papers
python -m polytool research-marker-queue list --status done

# Detailed list of failures (inspect failure_reason)
python -m polytool research-marker-queue list --status failed
```

#### Step 6 — Index papers and extract claims (inside Docker)

> **MUST run inside Docker on Windows.** arXiv candidate IDs contain colons
> (`arxiv:1106.5040`). Windows NTFS treats `:` as an Alternate Data Stream separator
> and cannot open these filenames. Running `index-done` from the Windows host reports
> "body file missing" for every paper. Always use the `docker exec` form below.

```bash
docker exec polytool-ris-scheduler-gpu sh -c \
  "cd /app && python -m polytool research-marker-queue \
   --queue-dir /app/artifacts/research/marker_parse_queue index-done"
```

Replace `marker_parse_queue` with your actual queue directory name if using `--queue-dir`.

**Expected output (per paper):**
```
Indexed 1 paper(s):
  [OK] arxiv:2604.24366  doc_id=abc123...  chunks=47  claims=38
Total: 1 done item(s) examined — 1 indexed, 0 already-indexed, 0 no-body, 0 failed, 38 claim(s) extracted.
```

`index-done` is idempotent — running it twice skips already-indexed papers.

#### Step 7 — Query the indexed corpus

```bash
python -m polytool research-query --question "optimal spread in prediction markets"
python -m polytool research-query --question "sports betting inefficiencies" --step-back --k 10
```

A successful query returns citations with `had_fallback=False` and lists papers by title
with matching claim snippets. If `had_fallback=True`, see the No-result cases table in
the [Querying section](#querying-the-academic-corpus-l2--research-query) below.

---

### Troubleshooting (WP-1 Prefetch Path)

#### arXiv 429 / timeout during prefetch

**Symptom:** `[PREFETCH FAIL] arxiv:XXXX  HTTP 429 — rate limited` or connection timeout.

**Cause:** Too many requests too quickly.

**Fix:**
```bash
# Re-run prefetch with a longer delay
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/marker_parse_queue prefetch \
  --delay-seconds 15
```

Prefetch is safe to re-run — already-cached papers are skipped automatically.
If a single paper keeps failing, check whether the arXiv ID is correct:
```bash
# Verify the paper exists on arXiv
python -m polytool research-marker-queue list --status pending
# Check the arxiv_id field matches what you expect
```

#### Cached PDF is missing or zero-byte

**Symptom:** warm-process reports `fetch_failed` even though you ran prefetch, or
`[PREFETCH OK]` showed 0 bytes.

**Check:**
```bash
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/marker_parse_queue status-report
# Look for prefetch cached/failed counts and failed-item details
```

**Fix:** Re-run prefetch for the affected papers:
```bash
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/marker_parse_queue prefetch \
  --delay-seconds 15
```

If the PDF is consistently 0 bytes, the arXiv paper may be HTML-only (no PDF) or
access-restricted. Mark it as manually skipped.

#### Docker not running

**Symptom:** `docker: Cannot connect to the Docker daemon` or container not found.

**Fix:**
1. Open Docker Desktop and wait for it to show "Engine running."
2. Re-run the nvidia-smi check:
   ```bash
   docker compose --profile ris-gpu run --rm ris-scheduler-gpu nvidia-smi
   ```
3. If GPU is not listed, check that Docker Desktop has GPU passthrough enabled:
   Settings → Resources → GPU → enable the toggle.

#### index-done run on Windows host instead of inside container

**Symptom:** `index-done` reports all papers as `no-body` even though warm-process
succeeded and `results.jsonl` shows `marker_ready=True`.

**Cause:** Windows NTFS cannot open filenames that contain colons. arXiv candidate IDs
like `arxiv:1106.5040` contain a colon. The body files exist on disk but the Windows
Python process cannot read them.

**Fix:** Always run `index-done` via docker exec:
```bash
docker exec polytool-ris-scheduler-gpu sh -c \
  "cd /app && python -m polytool research-marker-queue \
   --queue-dir /app/artifacts/research/QUEUE_DIR_NAME index-done"
```

Replace `QUEUE_DIR_NAME` with the name of your queue directory (e.g. `marker_parse_queue`).

This was confirmed in the 2026-05-17 smoke test: host-side run reported 4 no-body
failures; container-side run indexed all 4 papers cleanly.

#### Marker timeout on one paper

**Symptom:** `[FAIL] arxiv:XXXX  failure_reason: marker_timeout`

**Cause:** The paper exceeded `--marker-timeout`. This is common for equation-heavy or
table-dense papers (e.g. NYSE TAQ empirical papers with thousands of embedded table cells).

**Options:**

1. **Retry with a longer timeout** (try 3600 s or 7200 s):
   ```bash
   # Reset the paper to pending
   python -m polytool research-marker-queue enqueue --url ARXIV_ID --force

   # Re-run with a longer timeout
   docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
     python -m polytool research-marker-queue warm-process \
     --max-items 1 \
     --marker-timeout 7200
   ```

2. **Skip the paper** if it consistently times out (likely a scanned/image PDF):
   Leave it as `failed` in the queue. It will not block indexing of other papers.
   `index-done` skips `failed` papers automatically.

3. **Investigate the paper format** before spending GPU time:
   Download the PDF manually and check whether it contains selectable text. If it is
   a scanned-only PDF, Marker cannot extract text regardless of timeout.

#### Interrupted run / resuming after session kill

**Symptom:** The Docker container stopped mid-run. Some papers are `done`, some are
`failed`, one may be stuck in `processing`.

**Fix (3 steps):**

```bash
# 1. Reset any paper stuck in 'processing' (worker was killed mid-parse)
python -m polytool research-marker-queue enqueue \
  --queue-dir artifacts/research/marker_parse_queue \
  --url STUCK_ARXIV_ID --force
# Output: Enqueued: arxiv:XXXX  (status=pending)

# 2. Check which papers are still pending
python -m polytool research-marker-queue counts

# 3. Re-run prefetch to make sure all pending papers are still cached
#    (Docker volumes are persistent across restarts, but verify)
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/marker_parse_queue prefetch \
  --delay-seconds 5

python -m polytool research-marker-queue \
  --queue-dir artifacts/research/marker_parse_queue status-report

# 4. Re-run warm-process — already-done papers are skipped automatically
docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
  python -m polytool research-marker-queue warm-process \
  --max-items 30 \
  --marker-timeout 900
```

The queue is resumable by design: `warm-process` only picks up `pending` items.
`done` and `failed` papers are not re-processed unless you `--force` re-enqueue them.

The in-session JIT cache (TorchInductor/Triton compiled kernels) is **not** persistent
across Docker sessions. After a restart, the first paper in each format group will re-pay
the full JIT cold-start cost (27 s per paper + OCR compile time for equation-heavy papers).

---

### 5-Paper End-to-End Validation Checklist

Run this checklist on a fresh queue of 5 arXiv papers before doing a large batch.
All 5 steps must pass before the corpus is considered minimally validated.

**Setup:** Create an isolated test queue:
```bash
# Use a separate queue dir so you don't mix with your main corpus
mkdir -p artifacts/research/test_5paper_queue
# Enqueue 5 papers of different types
python -m polytool research-marker-queue --queue-dir artifacts/research/test_5paper_queue enqueue --url 2604.24366
python -m polytool research-marker-queue --queue-dir artifacts/research/test_5paper_queue enqueue --url 2109.07581
python -m polytool research-marker-queue --queue-dir artifacts/research/test_5paper_queue enqueue --url 1910.08858
python -m polytool research-marker-queue --queue-dir artifacts/research/test_5paper_queue enqueue --url 2307.14129
python -m polytool research-marker-queue --queue-dir artifacts/research/test_5paper_queue enqueue --url 1705.01446
```

**Checklist:**

| # | Check | Expected result | Command |
|---|-------|-----------------|---------|
| 1 | Prefetch completes without 429 errors | 5 `[PREFETCH OK]` lines, 0 failures | `research-marker-queue --queue-dir ... prefetch --delay-seconds 5` |
| 2 | All 5 PDFs cached and non-zero | `prefetch_stats.cached=5` | `research-marker-queue --queue-dir ... status-report` |
| 3 | warm-process: 5 done, 0 failed, 0 stuck | Queue shows `done: 5` | `research-marker-queue --queue-dir ... counts` |
| 4 | All 5 papers `marker_ready=True` | `body_source=marker`, `body_length>=5000` for all | `research-marker-queue --queue-dir ... list --status done` |
| 5 | index-done (in Docker) indexes all 5 | `5 indexed, 0 no-body, 0 failed` | `docker exec ... research-marker-queue --queue-dir ... index-done` |
| 6 | research-query returns citations | `had_fallback=False` with ≥1 citation | `research-query --question "prediction markets"` |

If any check fails, consult the Troubleshooting section above before running a full batch.

---

### Corpus Status (as of 2026-05-28 — post-reset, pre-Batch-A)

**QUEUE RESET COMPLETE. Staged cached validation is ready to begin at Batch A.**

> **History note:** The pre-reset state (failed=5, processing=1, pending=18) is documented
> in `docs/dev_logs/2026-05-18_academic-ris-operational-triage.md`. The queue was reset
> on 2026-05-28 after WP-1 prefetch separation validated (2026-05-22) and Tier-3 paper
> handling was established. Do not use the pre-reset counts for planning.

Current state of `artifacts/research/scaled_validation_queue_v2`:

| Status | Count | Notes |
|--------|-------|-------|
| done | 5 | All indexed in KS (227 chunks, 1106 claims) and embedded in Chroma |
| failed | 0 | — |
| processing | 0 | — |
| pending | 24 | All PDFs prefetched and cached (24/24) |

**Remaining open items before full 29-paper run:**

1. **JIT cache persistence: UNPROVEN.** `TORCHINDUCTOR_CACHE_DIR` and `TRITON_CACHE_DIR`
   both unset in container; persistence not tested across Docker restarts. Each restart may
   pay 27–50 min cold-start per format group. Run `jit-cache-check` inside Docker and
   follow the manual before/after diagnostic before scheduling large batches.

2. **Tier-3 papers require operator approval before Batch D.**
   - `arxiv:1011.6402`: confirmed timeout at 3600s; `ingest_tier=3`. Do not include in
     Batch A/B/C.
   - `arxiv:2409.02025`: persistent HTTP 429 / fetch failures; `ingest_tier=3`. Do not
     include in Batch A/B/C.
   - `arxiv:2508.03474` (9.7 MB): `tier3_flag=true` by size; requires 14400s timeout.
     Include in Batch C as the first large-paper probe.

3. **indexed.jsonl has duplicate entries.** `status-report` reports `indexed_count=19`
   (inflated by multiple `--force` reindex runs) while unique indexed papers remain 5.
   The code deduplicates by `candidate_id` when reading `indexed.jsonl`, so this is
   harmless audit noise. Do not use raw `indexed_count` as the unique-paper count.

**Run plan — 4 batches:**

| Batch | Papers | `--marker-timeout` | Notes |
|-------|--------|--------------------|-------|
| A (5) | 2507.01990, 2510.05533, 2605.00864, 2507.08921, 2601.18815 | 3600s | Small PDFs (≤600KB); run first |
| B (10) | 1206.4810, 2003.05958, 2203.13053, 1810.04383, 1609.03471, 2605.11640, 2605.02286, 2605.00493, 2208.13564, 2605.10400 | 7200s | Medium PDFs |
| C (7) | 2508.03474, 2308.04947, 2403.09267, 2212.12717, 2602.21091, 2604.20050, 2604.10005 | 14400s | Large PDFs; run 2508.03474 first as probe |
| D (2) | 1011.6402, 2409.02025 | 7200s+ | **Operator approval required before running** |

Stop condition for A/B: if >1 paper fails with `marker_timeout`, stop and diagnose.
Full batch plan with stop conditions: `docs/dev_logs/2026-05-28_academic-scaled-validation-queue-reset-readiness.md`.

**Do not:**
- Run `warm-process` on the 29-paper queue without verifying PDFs are still cached first.
- Include Tier-3 papers (1011.6402, 2409.02025) in Batch A/B/C without operator approval.
- Treat a partial pass (e.g. 20/24 parsed) as a valid 29-paper corpus measurement.
- Reset done papers with `--force` — preserve the 5 successful Batch 2 parses.

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

> **Pre-WP-1 / small-batch path.** Use this for 1–3 papers on a reliable connection
> where arXiv rate limiting is not a concern. For larger batches (5+ papers), use the
> [Prefetch then Parse](#prefetch-then-parse-wp-1-workflow) section above instead.

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
| Chroma embedded log | `artifacts/research/marker_parse_queue/chroma_embedded.jsonl` |

### Step 4c — Embed indexed papers into ChromaDB `academic_papers` collection (L2.1)

After `index-done` succeeds, embed papers into the dedicated `academic_papers` Chroma
collection so semantic retrieval can trace every chunk back to its KnowledgeStore document
via `ks_doc_id`.

```bash
# Index completed papers and embed them into Chroma
python -m polytool research-marker-queue index-done --reindex-chroma

# Re-index and re-embed already-indexed queue items
python -m polytool research-marker-queue index-done --reindex-chroma --force

# Use a non-default Chroma directory
python -m polytool research-marker-queue index-done --reindex-chroma --chroma-path PATH

# Verify linkage health (JSON report)
python -m polytool research-marker-queue check-chroma-links --json
```

There is no separate Chroma embedding subcommand. Chroma population is exposed to
operators through `index-done --reindex-chroma`; use `--force` when you intentionally
want to reprocess queue items that are already recorded in `indexed.jsonl`.

**How `check-chroma-links` works:**

1. Opens `academic_papers` in the Chroma persistent store
2. Fetches all chunk metadata with `collection.get(include=["metadatas"])`
3. For each chunk, checks that `ks_doc_id` is present and non-empty
4. Cross-references each unique `ks_doc_id` against the KnowledgeStore — reports
   any that cannot be found (orphaned chunks)
5. Exits 0 when both `missing_ks_doc_id` and `ks_doc_id_not_in_ks` are 0

**Clean linkage output:**
```json
{
  "collection": "academic_papers",
  "total_chunks": 423,
  "unique_papers": 9,
  "valid_ks_doc_id": 423,
  "missing_ks_doc_id": 0,
  "ks_doc_id_not_in_ks": 0,
  "not_in_ks_doc_ids": []
}
```

**Idempotency:** Chunk IDs are deterministic (`sha256(ks_doc_id + "\x00" + chunk_index)`),
so `index-done --reindex-chroma` is safe to re-run. Use `--force` to reprocess
already-indexed queue items; Chroma upsert overwrites existing chunks by ID.

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
| Dense math/ML paper (25-46 pages) | 33–55 min warm (1975s–3279s observed); JIT cold-start adds 27–50 min for new format groups |

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

**Primary retrieval is semantic (ChromaDB `academic_papers` vector search — L2.1, complete 2026-05-25). Lexical KnowledgeStore fallback activates only when no Chroma chunks exceed the similarity threshold (`had_fallback=true`, `retrieval_mode=lexical`).**

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
- ChromaDB academic retrieval (L2.1) — **COMPLETE 2026-05-25**. Semantic retrieval confirmed in 3-paper category sample (prose/survey, equation-heavy, table-heavy). See the L2.1 section in `docs/CURRENT_STATE.md`.
- **NTFS caveat:** This 2026-05-09 run executed `index-done` on the Windows host, predating the NTFS colon restriction discovery (2026-05-17). arXiv candidate IDs like `arxiv:1106.5040` contain a colon; Windows Python cannot open `bodies/arxiv:1106.5040.body.txt`. The 2026-05-09 run succeeded because it used a queue without colon-bearing IDs. **Always run `index-done` inside Docker** when using the GPU parse path on Windows. The current operator path reflects this requirement.

**Dev log:** `docs/dev_logs/2026-05-09_ris-academic-pipeline-3paper-operator-validation.md`

---

## JIT Cache Persistence (WP-2 — UNRESOLVED)

### Background

Marker uses Surya OCR, which JIT-compiles TorchInductor/Triton CUDA kernels on first
use of each distinct "format group" (unique page layout + equation density class). A
cold-start compile event adds **27–50 min** to the first paper of that format group.
Subsequent papers sharing the same format group reuse the compiled kernel and run at
full warm speed.

If the JIT cache does **not** persist across Docker restarts, every new container session
pays the full cold-start cost for every format group — making full-batch planning impossible.

`TORCHINDUCTOR_CACHE_DIR` was confirmed empty after multiple batch runs (2026-05-23).
`TRITON_CACHE_DIR` (the correct env var for Surya's Triton kernel cache) has not yet been
tested for cross-restart persistence.

### Diagnostic Procedure

Run `jit-cache-check` to print current env state and step-by-step instructions:

```bash
python -m polytool research-marker-queue jit-cache-check
```

Manual investigation steps (inside the Docker container):

```bash
# Step 1 — Find kernel cache before run
find ~/.triton -name '*.cubin' -o -name '*.ptx' 2>/dev/null | head -20

# Step 2 — Process one warm paper, note parse_seconds
python -m polytool research-marker-queue warm-process --max-items 1

# Step 3 — Record cache location after run
ls -la ~/.triton/    # or /root/.triton/ in Docker
find ~/.triton -name '*.cubin' | head -10

# Step 4 — Restart the container (do NOT rm -v the volume)
docker restart <container_name>

# Step 5 — Re-process the same paper with --force, check parse_seconds
#   parse_seconds < 120s → cache IS persistent
#   parse_seconds >= 1800s → cache NOT persistent (JIT recompiles every run)

# Step 6 — If NOT persistent, mount the cache to a host volume:
docker run -v /host/triton_cache:/root/.triton <image>
# And set TRITON_CACHE_DIR=/root/.triton in the container environment.
```

### Known Timeout-Risk Papers

These papers must NOT be included in automated batch runs until Tier-3 handling is in place:

| arXiv ID | Evidence | Action |
|----------|----------|--------|
| `1011.6402` | Confirmed timeout at 3600s (parse_seconds=3600.01) | Re-enqueue with `--tier 3`; operator approval required |
| `2307.14129` | parse_seconds=2947s in scaled validation | Re-enqueue with `--tier 3`; operator approval required |
| `2409.02025` | HTTP 429 / fetch failures across multiple runs | Fix fetch path first; then `--tier 3` |

To classify these correctly before a full batch run:

```bash
# Check status-report for Tier-3 flags on all pending items
python -m polytool research-marker-queue status-report

# Re-enqueue known-risk papers with Tier 3
python -m polytool research-marker-queue enqueue --url 1011.6402 --force --tier 3
python -m polytool research-marker-queue enqueue --url 2307.14129 --force --tier 3
```

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
