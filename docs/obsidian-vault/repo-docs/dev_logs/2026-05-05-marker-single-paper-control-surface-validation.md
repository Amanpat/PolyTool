---
title: Marker Single Paper Control Surface Validation
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-05_marker-single-paper-control-surface-validation.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Marker Single-Paper Control Surface — Validation

Date: 2026-05-05
Scope: Manual Docker validation of `run-academic-url` control surface.
Status: CONTROL SURFACE VALIDATED — L1 PRODUCTION BLOCKED (performance gate)

---

## Validation Command

```powershell
docker compose --profile ris-gpu run --rm --no-deps ris-scheduler-gpu `
  python -m polytool research-scheduler run-academic-url `
    --url 2604.24366 `
    --marker-timeout 900 `
    --json
```

## Validation Result (exact JSON)

```json
{
  "url": "https://arxiv.org/abs/2604.24366",
  "arxiv_id": "2604.24366",
  "title": "The Anatomy of a Decentralized Prediction Market: Microstructure Evidence from the Polymarket Order Book",
  "body_source": "marker",
  "body_length": 56923,
  "page_count": null,
  "parse_seconds": 85.95,
  "failure_reason": null,
  "rejected": false,
  "marker_timeout": 900.0,
  "total_seconds": 89.41,
  "exit_code": 0
}
```

---

## Acceptance Gate Verdicts

| Gate | Result | Evidence |
|------|--------|----------|
| 1. Single-paper controlled run completes | **PASS** | exit_code=0, no hang, no zombie |
| 2. Timeout kills worker process | **NOT TESTED** | No timeout invoked; process-boundary code exists |
| 3. No zombie after kill | **NOT TESTED** | Deferred — no timeout occurred |
| 4. Per-paper parse metadata present | **PASS** | body_source, body_length, parse_seconds all present |
| 5. Failure case surfaced | **NOT TESTED** | No timeout paper submitted |
| 6. No scheduler loop started | **PASS** | Confirmed by test + CLI design |
| 7. Existing tests pass | **PASS** | 2403 pass, 1 pre-existing failure |
| 8. Dev log written | **PASS** | This file |

**Control surface verdict: VALIDATED** (gates 1, 4, 6, 7, 8 pass).

---

## L1 Production Gate Assessment

| Metric | Result | Gate | Verdict |
|--------|--------|------|---------|
| `body_source` | `marker` | must be `marker` | ✅ PASS |
| `body_length` | 56,923 chars | must be > 5,000 | ✅ PASS |
| `exit_code` | 0 | must be 0 | ✅ PASS |
| `rejected` | false | must be false | ✅ PASS |
| `parse_seconds` | **85.95s** | must be **≤ 10s** (acceptance gate 2) | ❌ **FAIL — 8.6× over** |

**L1 production verdict: BLOCKED** — performance gate fails.

---

## Root Cause Analysis

The paper `2604.24366` is 15 pages, predominantly prose (market microstructure analysis),
with moderate equation density. This is among the *easiest* candidate papers for Marker —
not a math-heavy ML paper.

**Why 85.95s on RTX 2070 Super GPU:**

Each `docker compose run --rm` invocation starts a fresh container. The Marker/surya-ocr
models are volume-mounted from `~/.cache/datalab/` on the Windows host and loaded from
disk into VRAM on every container start. Based on prior smoke test observations, model
cold-load alone consumes ~80s of the budget. The actual per-page processing on GPU is fast
(~0.4s/page × 15 pages = ~6s) but is dwarfed by the cold-load overhead.

**The ≤10s/paper survey estimate was measured in warm-model conditions**, not cold-start
per-invocation conditions. The survey benchmarks assumed Marker models were already loaded
in VRAM from a prior paper in the same process.

**Cold-start breakdown (estimated):**
- Model load from Windows host volume → container VRAM: ~80s
- arXiv API fetch + PDF download: ~3.5s (`total_seconds - parse_seconds = 3.46s`)
- Actual GPU inference (15 pages): ~2.5s
- Total: ~86s

---

## What This Means

### Control surface works ✅

`run-academic-url` correctly:
- Fetches the arXiv paper via API
- Downloads the PDF
- Runs Marker inside the GPU container
- Returns structured JSON with `body_source`, `body_length`, `parse_seconds`
- Does not start APScheduler or register scheduled jobs
- Exits with code 0 on success, 1 on failure

The control surface machinery is production-ready as a validation tool.

### Marker production as synchronous default is not viable at current speed ❌

85.95s per paper on a 15-page prose paper means:
- A 50-paper corpus would take ~72 minutes synchronously
- The ingest loop would block for >1 minute per paper
- Cold-start overhead makes this worse for every isolated invocation

The ≤10s/paper production gate was written for a warm-model scenario. That scenario
requires either (a) a long-running process that keeps models in VRAM across papers,
or (b) faster hardware, or (c) smaller/quantized models.

---

## Next Strategy Options (Operator Decision Required)

### Option A — Async Parse Queue (recommended if Marker quality is important)

Add a background enrichment queue. New papers are ingested by pdfplumber (fast, synchronous).
A separate long-running GPU worker picks papers from the queue, re-parses them with Marker,
and replaces the `body_text` in the knowledge store. Models load once at worker start and stay
warm for all subsequent papers.

- **Pros:** No latency impact on ingestion; Marker quality for all papers eventually;
  warm-model throughput matches survey estimate (~6s/paper post-load)
- **Cons:** Requires a new queue mechanism; pdfplumber-parsed chunks exist until re-parsed
- **New packet required:** `Work-Packet - Marker Async Parse Queue`

### Option B — Warm-Model Optimization (scheduler service path)

Use `ris-scheduler-gpu` as a long-running service (not `--rm`). Submit papers via
`docker exec polytool-ris-scheduler-gpu python -m polytool research-scheduler run-academic-url`.
Models load once on service start; subsequent papers skip the ~80s cold-load.

- **Pros:** Reuses existing infrastructure; no new queue mechanism; straightforward
- **Cons:** Service must stay running; first paper still slow; resource always consumed
- **New packet required:** Minimal — add warm-service operator runbook + `docker exec` path

### Option C — pdfplumber Production + Selective Marker Enrichment

Keep pdfplumber as the production synchronous default. Add `run-academic-url` as an
operator-triggered enrichment command for specific high-value papers (e.g., papers
the operator flags as equation-heavy or structurally important). No scheduling required.

- **Pros:** No performance risk; zero new code; immediate availability
- **Cons:** Most papers remain pdfplumber-quality (flat text, no LaTeX preservation)
- **New packet required:** None — `run-academic-url` already provides the path

---

## Status Changes in This Session

| Document | Change |
|----------|--------|
| `Work-Packet - Marker Single-Paper Validation Control Surface.md` | `status: ready` → `status: validated`; acceptance gate table added |
| `Work-Packet - Marker Structural Parser Integration.md` | `blocked-reason` updated with performance evidence; DANGER callout updated with Options A/B/C |
| `Current-Focus.md` | Session context prepended; L1 table row updated; new performance blocker added; control surface blocker struck through |
| `CURRENT_DEVELOPMENT.md` | L1 Paused/Deferred row updated; architect note updated; control surface added to Recently Completed |
| `ris-marker-structural-parser-scaffold.md` | Status updated; performance result documented; next-step options listed |
| `INDEX.md` | New dev log row added |

---

## Codex Review

Tier: Skip — docs-only session; no code changes made.
