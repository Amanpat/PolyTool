---
tags: [work-packet, ris, ingestion, academic, parser]
date: 2026-04-29
status: blocked
blocked-reason: "Feature 3 closed 2026-05-08: Marker Docker IPC Warm-Worker v1 closed under revised functional gate. L1 warm-worker blocker resolved; next L1 rollout/readiness step requires separate workpacket/Director decision. HISTORICAL (2026-05-05, gate rejected 2026-05-08): old ≤10s/paper timing gate was rejected as unrealistic; async parse queue has shipped. pdfplumber is legacy/debug only. Final embeddings must be Marker-only."
updated: 2026-05-08
priority: high
phase: 2
target-layer: 1
parent-architecture: "[[11-Scientific-RAG-Target-Architecture]]"
parent-decision: "[[Decision - Scientific RAG Architecture Adoption]]"
related-decisions:
  - "[[Decision - Academic Pipeline Hosting]]"
prerequisites:
  - "[[Work-Packet - Academic Pipeline PDF Download Fix]] (Layer 0 — shipped 2026-04-27)"
  - "Hosting decision: which machine hosts the academic pipeline (must have GPU) — RESOLVED 2026-05-02"
  - "[[Work-Packet - Marker Single-Paper Validation Control Surface]] — REQUIRED before rollout can resume"
supersedes-status: "Previous status (implemented-experimental-scaffold) is superseded. Marker becomes the production parser; pdfplumber path is retired."
---

# Work Packet — Marker Structural Parser Integration (Production Rollout)

> [!INFO] Status: Feature 3 Closed — L1 Warm-Worker Blocker Resolved (2026-05-08; queue shipped)
> The control surface (`run-academic-url`) was validated on 2026-05-05.
> Marker parses successfully — but is too slow for synchronous production default.
> **Operator decision recorded 2026-05-05: Option A — async parse queue.**
>
> **Controlled parse result (2026-05-05):**
> - Paper: `2604.24366` — The Anatomy of a Decentralized Prediction Market (15 pages, prose-heavy)
> - `body_source=marker` ✅ | `body_length=56923` ✅ | `exit_code=0` ✅
> - `parse_seconds=85.95s` ❌ — ~~**fails ≤10s/paper production gate by ~8.6×**~~ **(historical — ≤10s/paper gate rejected/superseded 2026-05-08; see revised gate below)**
> - `total_seconds=89.41s` (includes arXiv API + PDF download)
>
> **Root cause (historical — superseded 2026-05-08):** RTX 2070 Super cold-load time dominates per-paper budget. The ~~`~5–10s/paper`
> estimate in the architecture survey was from a warm-model benchmark not replicated here~~ — survey estimate rejected as unrealistic; measured warm-worker timings: 45.55s, 69.73s, 48.31s.
> Cold-start per `docker compose run --rm` invocation = model reload from disk on every paper.
> Warm-worker approach (models loaded once, queue processed sequentially) solves this.
>
> **Operator decision — Option A: Async Parse Queue:**
> - pdfplumber is **legacy/debug only** (`RIS_PDF_PARSER=pdfplumber` debug override only)
> - Final academic embeddings must be **Marker-only** (`body_source=marker`)
> - New papers enqueued immediately; a warm GPU worker processes the queue
> - Models load once at worker start; papers 2+ cold-load delta expected ≤5s (revised gate 2026-05-08; original "≤10s/paper" per-paper target **rejected as unrealistic** — measured warm-worker timings: 45.55s, 69.73s, 48.31s; papers 2–3 deltas: 0.13s, 0.22s)
> - New packet created: [[Work-Packet - Marker Canonical Academic Parse Queue]] (status: ready)
>
> ~~**This packet resumes when [[Work-Packet - Marker Canonical Academic Parse Queue]] ships.**~~ **Queue shipped. Feature 3 closed 2026-05-08. L1 warm-worker blocker resolved; next L1 rollout/readiness step requires separate workpacket/Director decision.**
>
> **Evidence:** `docs/dev_logs/2026-05-05_marker-single-paper-control-surface-validation.md`
> **Decision log:** `docs/dev_logs/2026-05-05_marker-canonical-parse-queue-packet.md`

> [!IMPORTANT] Architectural change vs. previous packet
> The earlier version of this packet specified Marker as an opt-in experimental fallback with pdfplumber as the default. **This version supersedes that.** Marker becomes the **single production parser** for the academic pipeline. pdfplumber is retired from the active path.
>
> **Why the change:** consistent embedding quality requires consistent parser output. Two parsers in production produce two flavors of chunks (Marker preserves LaTeX equations and structured tables; pdfplumber produces flat text), and the embedder treats them differently. Queries about "γ in Avellaneda-Stoikov" might match Marker-parsed papers (LaTeX `\gamma` survives) and miss pdfplumber-parsed papers (`γ` becomes Unicode soup). Inconsistent corpus = inconsistent retrieval = no way to reason about why queries succeed or fail.
>
> The operator has confirmed GPU availability (NVIDIA 2070 Super on dev machine). ~~Marker on this hardware is ~5-10s/paper per the survey's evidence — fast enough for production.~~ **Historical note, superseded 2026-05-08:** architecture survey estimate of ~5-10s/paper rejected as unrealistic for full academic PDFs on RTX 2070 Super. Measured warm IPC worker timings: 45.55s, 69.73s, 48.31s. Revised gate is functional warm-worker throughput (≥3 papers in one IPC session, papers 2+ delta ≤5s), not per-paper timing. The CPU timeout problem (300s) the previous scaffold hit goes away with the GPU IPC warm worker.

## Layer

Layer 1 of the [[11-Scientific-RAG-Target-Architecture|four-layer scientific RAG target]].

## What ships

`MarkerPDFExtractor` becomes the default and only parser in `LiveAcademicFetcher`. The existing scaffold (parser dispatch logic, optional dependency, concurrency guards, benchmark CLI) is retained — what changes is the dispatch policy:

- `RIS_PDF_PARSER` config defaults to `marker` (was `pdfplumber`)
- pdfplumber is removed from the active call path
- Marker failure on a given paper rejects the paper with a logged reason — no silent downgrade to pdfplumber
- Marker-required dependencies move from `[ris-marker]` optional extra into the base `[ris]` extra
- Existing pdfplumber code stays in the codebase as deprecated/reference but is not called

Marker output (Markdown with LaTeX equations, structured tables, section headers, page numbers) populates `body_text`. Full Marker JSON output is stored in the existing raw-source cache JSON dict (per the original storage policy decision — see the survey's storage discussion). Adapter metadata propagation works unchanged.

## Scope guards

- Marker is the production parser; no fallback parser in the same pipeline
- Failures are surfaced, not hidden — image-only PDFs, encrypted PDFs, OCR-required papers are rejected with clear reasons in the acquisition review JSONL
- LLM-enriched Marker mode (`marker_llm_applied`) remains out of scope — separate future work
- Do NOT change the chunker, embedder, or retrieval API in this packet — those are Layer 2 work
- Do NOT modify `AcademicAdapter` — it consumes whatever is in `body_text` regardless of parser
- Existing `tests/test_ris_academic_pdf.py` continues to pass; new tests cover Marker-specific paths

## Reference materials for architect

The architect should read these before writing the implementation prompt:

1. **`[[11-Scientific-RAG-Pipeline-Survey]]`** — the Marker entry has the full evaluation including license analysis, GPU/CPU performance characterization, and recommended schemas for tables/equations/sections. This is the primary reference.
2. **`[[Decision - Scientific RAG Architecture Adoption]]`** — item 1 in "Adopt" specifies Marker as primary parser. License posture (research/personal under modified Open Rail-M) is established here.
3. **`[[Decision - Academic Pipeline Hosting]]`** — must be created and answered before this packet ships. Determines which machine runs the pipeline.
4. **`docs/features/ris-marker-structural-parser-scaffold.md`** — canonical documentation of the existing scaffold from Prompts A-D (2026-04-27). This packet builds on that scaffold, does not replace it.
5. **The original L0 dev logs** at `docs/dev_logs/2026-04-27_ris-academic-pdf-fix.md` and `docs/dev_logs/2026-04-27_ris-docker-pdf-deps-smoke.md` — establish the patterns for testing and Docker integration this packet must match.

## Acceptance gates

1. **Marker is the default and only parser.** `LiveAcademicFetcher.fetch()` calls Marker for every PDF download. `RIS_PDF_PARSER` env var still exists for testing/debugging but defaults to `marker`. pdfplumber is not called in the production path.
2. **GPU performance baseline.** ~~On the production host (per the hosting decision), Marker parses a typical arXiv paper in ≤10 seconds.~~ **Superseded (Director 2026-05-08):** original ≤10s/paper timing gate rejected as unrealistic for full academic PDFs on RTX 2070 Super. Revised gate: ≥3 papers completed in one warm Docker IPC session; papers 2+ delta (total_seconds − parse_seconds) ≤5s; `body_source=marker`; `ipc_warm_worker_used=true`; no pdfplumber fallback. See `docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md` (closed 2026-05-08).
3. **Structured output preserved end to end.** For 10 test papers, the stored `body_text` contains: at least one LaTeX equation marker (`$$` or `$`), at least one Markdown header (`#`), at least one Markdown table marker (`|`). Confirm via direct ChromaDB inspection.
4. **Failure surfacing.** When Marker fails on a corrupted or image-only PDF (test fixture), the paper is rejected with `body_source=marker_failed`, `failure_reason` populated, and the acquisition review JSONL records the rejection. No silent fallback to abstract or pdfplumber.
5. **Cache compatibility.** Marker JSON metadata is stored in the existing raw-source cache JSON file alongside Markdown body. Re-ingestion of cached papers reads from cache without re-running Marker.
6. **Docker smoke.** Production Docker image includes Marker dependencies (PyTorch + model weights) and successfully parses one paper end-to-end inside the container. GPU passthrough to container confirmed if container is the production host.
7. **Existing L0 tests still pass.** `tests/test_ris_academic_pdf.py` and `tests/test_ris_research_acquire_cli.py` pass without modification (backward compat at the adapter and pipeline layers).
8. **New Marker-specific tests.** New test file `tests/test_ris_marker_extractor.py` with ≥4 tests: Marker success on text PDF, Marker failure on image-only PDF, Marker output contains LaTeX for equation-bearing fixture, cache replay does not re-invoke Marker.
9. **Re-ingestion plan documented.** Existing pdfplumber-parsed papers in the knowledge store are now considered low-fidelity. The packet does not include the re-ingestion task itself, but documents how it will be executed (a separate cleanup task that walks the cache and re-parses through Marker, comparing chunk counts and body lengths to flag regressions).
10. **Dev log written.** `docs/dev_logs/2026-04-XX_ris-marker-production-rollout.md` documents the rollout, GPU performance numbers, and any rejected papers found during validation.

## Files expected to change

| File | Change | Review level |
|------|--------|-------------|
| `packages/research/ingestion/extractors.py` | `MarkerPDFExtractor` already exists from scaffold; verify production-readiness, ensure GPU initialization is robust, error handling is explicit | Mandatory |
| `packages/research/ingestion/fetchers.py` | `LiveAcademicFetcher` parser dispatch defaults to `marker`; pdfplumber path removed from production call site | Mandatory |
| `pyproject.toml` | Marker dependencies move from `[ris-marker]` extra into `[ris]` base extra | Mandatory |
| `Dockerfile` (or equivalent) | Production image includes Marker dependencies; GPU passthrough configured if Docker is the production host | Mandatory |
| `tests/test_ris_marker_extractor.py` | New file with ≥4 test cases | Mandatory |
| `tests/fixtures/ris_external_sources/equation_paper.pdf` | New fixture: small PDF with LaTeX equations for offline testing | Mandatory |
| `docs/features/ris-marker-structural-parser-scaffold.md` | Update to reflect production-default state | Recommended |
| `docs/dev_logs/2026-04-XX_ris-marker-production-rollout.md` | New dev log | Mandatory |

## Open questions for architect

1. ~~**Hosting answer.**~~ **RESOLVED 2026-05-02.** Docker + GPU passthrough on dev machine. RTX 2070 Super, CUDA 13.2. Model weights volume-mounted from `~/.cache/datalab/`. See [[Decision - Academic Pipeline Hosting]] (status: accepted).
2. ~~**GPU passthrough to Docker.**~~ **RESOLVED 2026-05-02.** `docker run --gpus all` verified on dev machine.
3. **Model weight handling.** Volume-mounted from host cache. Resolved by hosting decision (Q5→volume-mount).
4. **Failure-mode policy for Marker rejections.** When Marker fails, the paper is rejected. Should the rejection be recoverable (e.g., a future packet adds OCR for image-only papers) or final? Recommend: recoverable, with the rejected source_id remaining in cache so a future re-ingest can re-attempt.
5. **Rollout strategy.** Hard cutover recommended for new ingests, cleanup as a parallel task. However this question is now moot until the control surface packet ships — rollout cannot begin until single-paper controlled validation succeeds.
6. **NEW (2026-05-05) — RESOLVED 2026-05-08:** Math-heavy paper timeout. Cold model load (~136-270s) + math-dense box spikes (100-300s/box) make one-shot per-paper timeouts unreliable for ML/quant papers. ~~Does acceptance gate 2 ("≤10s warm") assume warm scheduler mode only?~~ **Resolved:** acceptance gate 2 revised (Director 2026-05-08) — original ≤10s/paper per-paper target rejected as unrealistic; revised gate is functional warm-worker throughput (≥3 papers in one Docker IPC session, papers 2+ delta ≤5s, body_source=marker, ipc_warm_worker_used=true). See `docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md` (closed 2026-05-08).

## Cross-references

- [[11-Scientific-RAG-Target-Architecture]] — parent design
- [[Decision - Scientific RAG Architecture Adoption]] — adoption decision
- [[Decision - Academic Pipeline Hosting]] — prerequisite decision
- [[Work-Packet - Academic Pipeline PDF Download Fix]] — Layer 0 (shipped); pdfplumber path retired by this packet
- [[Work-Packet - PaperQA2 RAG Control Flow]] — Layer 2; consumes Marker's structured output
- [[11-Scientific-RAG-Pipeline-Survey]] — Marker entry has the full evaluation
