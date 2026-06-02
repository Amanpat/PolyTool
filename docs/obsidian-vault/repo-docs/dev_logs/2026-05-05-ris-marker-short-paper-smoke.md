---
title: Ris Marker Short Paper Smoke
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-05_ris-marker-short-paper-smoke.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# RIS Marker — Short-Paper Smoke Validation

Date: 2026-05-05  
Scope: Confirm Marker can produce body_source=marker after the site-packages/static permission fix  
Status: BLOCKED — two papers timed out. One-shot benchmark CLI is not a viable validation path for math-heavy papers. Recommend switching to Option C (scheduler mode validation).

---

## Objective

After the Docker permission fix (see `2026-05-05_ris-marker-docker-static-permission-fix.md`),
run Marker against short/prose-heavy papers to confirm `body_source=marker` and
`body_length > 5000` is achievable. Do not mark L1 shipped.

---

## Papers Attempted

### Paper 1 — 2604.21675 (6 pages, ML with equations)

**Title**: Counterfactual Multi-task Learning for Delayed Conversion  
**Pages**: 6 | **Chars in knowledge store**: 28,579 | **Text recognition boxes**: 121  
**Command**:
```powershell
docker compose --profile ris-gpu run --rm --no-deps ris-scheduler-gpu \
  python -m polytool research-parser-benchmark --urls 2604.21675 \
  --parsers marker --marker-timeout 1200 --output-dir artifacts/benchmark/parser --verbose
```

**Result**:
```
2604.21675  marker  marker_failed  0  ...  1200.5  0  marker_timeout: extraction timed out after 1200.0s
```

**Detailed timeline**:

| Stage | Time | Notes |
|---|---|---|
| Layout recognition (6 pages) | 3s | Fast — small paper |
| OCR error detection | <1s | |
| Bbox detection | 1.6s | |
| Text recognition box 1 (model cold-load) | 136s | Faster than 2510.15205 — probably lighter model path |
| Text recognition boxes 2-107 avg | ~3-7s/box | Normal prose/mixed content |
| Text recognition box 109-113 | 14-25s/box | Math sections begin |
| Text recognition box 114 | 273s | Dense math — single box took 273s |
| Text recognition box 115 | ~106s | Still dense math |
| Timeout at 1200.5s | | Boxes 116-121 not completed (6/121 cut off) |

**Root cause**: The paper's final pages contain dense mathematical formulas. Box 114 alone
consumed 273s — more than the model cold-load. The early EMA (~3-7s/box) was not predictive
of the final pages. Page count (6) was not a reliable proxy for processing time.

---

### Paper 2 — 2510.15205 (25 pages, math-heavy ML paper)

**Title**: Toward Black Scholes for Prediction Markets  
**Result**: marker_failed — timed out at 1800.2s with box 102/104 complete  
**Detail**: See `2026-05-05_ris-marker-docker-static-permission-fix.md` (runs 1-4)

---

## Pattern Analysis

Both papers followed the same failure mode:

1. **Mid-paper processing looks fine.** Early and middle boxes complete at 2-13s/box —
   fast enough to finish any paper within a generous timeout.

2. **Final pages are math-dense.** The last 5-15% of boxes in ML papers contain
   concentrated equation blocks. These spike to 93-273s per box, consuming most of the
   remaining timeout budget.

3. **Page count ≠ processing time.** A 6-page paper produced 121 text recognition boxes
   and timed out. Page count does not predict box count or math density.

4. **Cold model load eats budget.** Each one-shot container starts fresh. The surya-ocr
   text recognition model loads from the host-mounted Windows volume in ~136-270s,
   spending 11-23% of any 1200-1800s budget before any text is processed.

5. **Zombie containers contaminate subsequent runs.** After each timeout, the Marker
   worker thread keeps the container alive. GPU contention from a zombie degraded
   layout recognition 16× in prior runs. Must `docker kill` before each run.

---

## What This Means for L1

The one-shot benchmark CLI (`docker compose run --rm`) is **not a reliable validation
path for Marker** when papers contain any significant math content, because:

- Cold-load overhead is unavoidable (~136-270s per container start)
- Math-dense boxes can spike to 100-300s individually, with no upper bound
- Timeouts that are set to avoid waiting hours will reliably cut off dense final pages
- There is no way to predict timeout requirements from page count alone

Marker itself is NOT broken. The permission fix works. All pipeline stages execute
(layout, OCR, bbox, text recognition). Text recognition runs and produces output for
prose content. The issue is exclusively timeout management in the one-shot container
benchmark path.

---

## Recommendation: Proceed to Option C (Scheduler Mode)

The long-running `ris-scheduler-gpu` service loads models once at startup and holds
them in VRAM. Processing subsequent papers has:

- **Zero cold-load overhead** — models already in VRAM
- **No per-paper timeout** — the scheduler queue processes each paper to completion
- **This is the actual production code path** — validating via the scheduler validates
  what will run in production, not a one-shot approximation

### What Option C looks like

1. Start the GPU scheduler service:
   ```powershell
   docker compose --profile ris-gpu up -d ris-scheduler-gpu
   ```

2. Submit a paper to the scheduler queue (e.g., via the prefetch queue or direct ingest):
   ```powershell
   python -m polytool research-acquire --url https://arxiv.org/abs/2604.21675 \
     --source-family academic --no-eval
   ```
   Or whichever queue-submission path the scheduler monitors.

3. Watch the scheduler process the paper. Confirm the paper record in the knowledge
   store has `body_source=marker` and `body_length > 5000`.

4. If that succeeds: L1 is confirmed. The permission fix is validated end-to-end
   on the production service path.

### Alternative: choose a purely prose-only paper

If scheduler mode isn't ready to run, pick a paper with NO equations:
- Qualitative study, ethnography, policy analysis, historical paper
- Avoid: ML papers, finance quant papers, physics papers, any STEM paper with derivations

A purely prose paper with 8-10 pages would complete in ~280s (model load) + 80 boxes × 2s
= ~440s, well within a 600s timeout.

Suggested candidate from knowledge store: `2604.24366` (15 pages, 51,604 chars —
"The Anatomy of a Decentralized Prediction Market") — this is likely more prose-heavy
as a market analysis paper. Or `2009.09454` (12 pages — "How Market Ecology Explains
Market Malfunction") which is a descriptive/theory paper and likely equation-light.

---

## L1 Status

**Permission fix**: SHIPPED and confirmed working.  
**Marker pipeline stages**: All working — layout, OCR, bbox, text recognition all execute.  
**L1 validation via one-shot CLI**: BLOCKED — math-density timeout is a systematic issue.  
**L1 validation via scheduler mode**: NOT YET RUN — this is the recommended next step.  
**L1 milestone**: NOT SHIPPED. Do not mark shipped until scheduler-mode validation succeeds.

---

## Codex Review

Tier: Skip (no code changes — this is a benchmark run log only).
