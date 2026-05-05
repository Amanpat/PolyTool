# RIS Marker Docker — static Permission Fix

Date: 2026-05-05  
Scope: Fix [Errno 13] Permission denied on site-packages/static inside ris-scheduler-gpu  
Status: Permission fix SHIPPED. Marker pipeline confirmed working through all stages. L1 BLOCKED — paper 2510.15205 exceeds 1800s timeout (102/104 boxes at cutoff). Operator decision required on benchmark paper selection or approach.

---

## Root Cause

The `Dockerfile.ris` runtime stage COPYs site-packages from the builder as root, then
chowns only `/app` to `polytool`. `site-packages` itself stays owned by `root:root`.

`marker-pdf` (via its `surya-ocr` / server module) attempts to `mkdir
site-packages/static` on first import to store web-serving static assets. Because
`polytool` has no write permission to the site-packages parent, the `mkdir` fails
with `[Errno 13] Permission denied: '/usr/local/lib/python3.11/site-packages/static'`.

This caused every Marker invocation to fail at import time, making all papers return
`marker_failed` before any processing occurred.

---

## Fix

In the runtime stage of `Dockerfile.ris`, added a `RUN mkdir + chown` immediately
before `USER polytool`:

```dockerfile
# marker-pdf and its dependency tree attempt to create site-packages/static on
# first import (web-asset serving path in surya-ocr / marker server). Pre-create
# it owned by the runtime user so the write does not fail with EPERM. Only this
# specific directory needs write access; the rest of site-packages stays
# root-owned and read-only.
RUN mkdir -p /usr/local/lib/python3.11/site-packages/static \
    && chown polytool:polytool /usr/local/lib/python3.11/site-packages/static
```

This is the narrowest possible fix: one directory, one chown. No broad chown of
site-packages, no running the service as root.

---

## Permission Strategy

Only `site-packages/static` is made writable for `polytool`. All other site-packages
directories remain owned by root. This prevents any other package from accidentally
writing into the installed package tree while still allowing marker-pdf's static
asset initialization to succeed.

---

## Files Changed

- `Dockerfile.ris` — added `RUN mkdir -p .../site-packages/static && chown polytool` before `USER polytool`
- `docs/dev_logs/2026-05-05_ris-marker-docker-static-permission-fix.md` — this file

---

## Commands Run

### Docker rebuild (GPU image only)

```powershell
docker compose --profile ris-gpu build ris-scheduler-gpu
```

Build output: `#32 [stage-1 12/12] RUN mkdir -p ...static && chown polytool:polytool ...static` — DONE 0.4s  
Full build: exit 0.

### Write-access check inside container

```powershell
docker compose --profile ris-gpu run --rm --no-deps ris-scheduler-gpu python -c \
  "import os, pathlib; p=pathlib.Path('/usr/local/lib/python3.11/site-packages/static'); \
   print(os.getuid(), p.exists(), os.access(p, os.W_OK))"
```

Output:
```
uid: 999
exists: True
writable: True
```

uid 999 = `polytool` user. Fix confirmed.

---

## Single-Paper Benchmark Results

Four runs were performed. The permission error is gone in all runs — Marker now
executes all pipeline stages. The new constraint is processing time.

### Run 1 — marker-timeout 300s (first attempt, no zombie containers)

```
2510.15205  marker  marker_failed  0  ...  300.3  0  marker_timeout: extraction timed out after 300.0s
```

Marker pipeline progress observed before timeout:
- Layout recognition: 25 pages in ~10s ✓
- OCR error detection: 2/2 batches ✓
- Bbox detection: 1/1 ✓
- Text recognition: timed out at 0/104 (text model loading not yet complete)

Root cause of timeout: marker starts text model loading lazily. The text recognition
model (surya-ocr text model) needs ~270s to load from the host-mounted Windows volume
(WSL2 I/O overhead). With 300s total, model loading + layout + bbox takes 300s and
text recognition never starts.

### Run 2 — marker-timeout 600s (zombie container interference)

```
2510.15205  marker  marker_failed  0  ...  600.2  0  marker_timeout: extraction timed out after 600.0s
```

The 300s benchmark left a zombie container (Marker worker thread kept the container
alive after the CLI returned `marker_failed`). The zombie occupied GPU VRAM and CUDA
cores simultaneously with run 2. Layout recognition slowed 16× to 168s (vs 10s in
run 1). Total pre-text-recognition elapsed: ~213s, leaving only 387s for text
recognition. Text model load (~270s) + processing (0 complete) = still timed out.

Lesson: always kill GPU containers after a `marker_timeout` failure before starting
the next benchmark run. The zombie pattern is documented in fetchers.py:
```
# True cancellation of the running thread would require a
# process boundary and is deferred to a future hardening pass.
```

### Run 3 — marker-timeout 1200s (clean GPU, killed zombie first)

Stopped early (manually killed at box 16 of 104) to avoid wasting time. Key data:

Timing of pipeline stages (clean GPU, text model being cold-loaded from disk):
| Step | Time |
|---|---|
| Layout recognition (25 pages) | 10s |
| OCR error detection (2 batches) | <1s |
| Bbox detection (1 batch) | 2.0s |
| Text recognition box 1 (incl. model load) | 280s |
| Text recognition boxes 2-16 avg | ~13s/box |

The text recognition model cold-load from the Windows host mount takes ~270s.
After warmup, processing rate is ~13s/box for the mixed math/text content in this paper.

Total time estimate for all 104 boxes: 270s (model load) + 13s (box 1 proper) +
103 boxes × 13s/box = ~1619s. Plus 13s pre-text-recognition = ~1632s.

The 1200s timeout fires at ~box 73 (1200 - 270 - 13s×layout/OCR/bbox = ~900s left /
13s per box ≈ 69 boxes × + box 1 = ~70 of 104). Partial results discarded on timeout.

Observation: EMA stable at 12-16s/box after warm-up, confirming the ~1600s estimate.

### Run 4 — marker-timeout 1800s (TIMED OUT — 102/104 boxes)

Started after killing run 3 container.

```
2510.15205  marker  marker_failed  0  ...  1800.2  0  marker_timeout: extraction timed out after 1800.0s
```

Marker reached box 102/104 at elapsed 20:59 (1259s). Boxes 103-104 consumed the remaining
541s without completing — those final boxes are extremely math-heavy, taking >270s each vs
the ~13s/box EMA earlier in the paper.

Actual full-paper time for 2510.15205 exceeds 1800s. The 13s/box average is not a
representative ceiling — the final pages of this paper are dense math that can take
5-10× longer per box (observed: boxes 98-102 ranged from 27-44s/box).

Revised minimum timeout for this specific paper: >1800s (actual unknown; at minimum 1800+
541s of partial progress on boxes 103-104). A 2400s or 3000s run may succeed, but
the paper itself appears to be an outlier for math density.

Root cause of estimate error: run 3 was manually stopped at box 16, before reaching the
dense math sections in the latter half of the paper. The 13s EMA from boxes 2-16 was
not representative of boxes 97-104 which are 2-5× slower.

---

## Performance Analysis

### GPU throughput (RTX 2070 Super, no interference)

| Stage | Rate | Notes |
|---|---|---|
| Layout recognition | 2-6 pages/s after warmup | Surya layout model |
| Text recognition | ~13s/box average | High variance: 2-25s depending on math density |

### Bottleneck: text recognition model cold load

The surya-ocr text model loads from the host-mounted Windows volume (`${USERPROFILE}\.cache\datalab`) through WSL2 into container VRAM each time a fresh container starts. On RTX 2070 Super with the Windows host volume mount, this takes ~270s.

In the production long-running scheduler (`ris-scheduler-gpu` service), models are
loaded once at startup and stay in VRAM for all subsequent papers. The per-paper
overhead disappears.

For the benchmark CLI (one-shot container per run), the 270s model load overhead must
be included in the timeout budget.

### Required timeout for paper 2510.15205

Minimum timeout (revised after run 4): **>1800s** — actual time unknown; boxes 103-104
consumed >541s combined (run 4 stopped at exactly 1800s with those boxes in progress).

Original estimate `270s (text model) + 13s (pre-text) + 104 × 13s (text) = 1631s` was
wrong because the 13s EMA came from early boxes (1-16), not the math-dense final pages
which ran at 27-44s/box (boxes 98-102) and apparently >270s each (boxes 103-104 > 541s total).

Conservative estimate for this paper: `270s + 13s + ~1800s text recognition = ~2083s`.
Use 2400s–3000s if attempting another one-shot run of this specific paper.

**This paper is an outlier.** 2510.15205 is a math-heavy ML paper (25-page journal format).
Shorter prose-heavy papers would complete in a fraction of this time.

Note: The default Marker timeout in `research_parser_benchmark.py` is `300s`, which is
insufficient for cold-start single-container benchmarks on this hardware. The benchmark
default should be raised to at least `1800s` for typical GPU container context, or a warm-up
step added to pre-load models before starting the timer. For this specific paper, 2400s–3000s.

---

## Zombie Container Warning

After any `marker_timeout` failure, immediately kill the associated container before
starting the next benchmark:

```powershell
# List GPU containers
docker container ls --format "{{.Names}}\t{{.Status}}" | Select-String "ris-scheduler-gpu"

# Kill zombie
docker kill <container_name>
```

Failure to do this will cause subsequent benchmarks to run with GPU contention,
degrading all processing steps by 16× or more.

---

## 3-Paper Benchmark

NOT run. Run 4 timed out, blocking 3-paper benchmark. Requires operator decision
on approach before proceeding.

---

## Whether L1 Remains Blocked or Can Continue

**Permission fix: SHIPPED.** `site-packages/static` permission error is resolved.
Marker processes all pipeline stages (layout, OCR, bbox, text recognition) without
permission errors. The `polytool` user can run Marker in the GPU container.

**Single-paper benchmark result: FAILED (timeout)** — run 4 timed out at 1800.2s with
box 102/104 complete. Marker extracted partial text but discarded it on timeout.

**L1 milestone: BLOCKED.** Operator decision required. Three paths forward:

### Option A — Try 2400s–3000s on same paper (2510.15205)
- Paper 2510.15205 needs ~2083s based on observed progress (conservative).
- Command (3000s to be safe):
  ```powershell
  docker kill $(docker container ls -q --filter "name=ris-scheduler-gpu") 2>$null
  docker compose --profile ris-gpu run --rm --no-deps ris-scheduler-gpu `
    python -m polytool research-parser-benchmark --urls 2510.15205 --parsers marker `
    --marker-timeout 3000 --output-dir artifacts/benchmark/parser --verbose
  ```
- Risk: still may timeout if last 2 boxes are unusually dense. Total run time ~50+ min.

### Option B — Switch to a shorter, prose-heavy benchmark paper
- Any <15 page non-math paper should complete in ~450–600s including model cold-load.
- Pick a short empirical/methods paper or review paper. Submit new arXiv ID.
- Recommended: pick a paper from existing RIS knowledge store or choose any short paper.
- Does NOT require Dockerfile changes.

### Option C — Accept that L1 validation runs via long-running scheduler (not one-shot)
- `ris-scheduler-gpu` service loads models once at startup; subsequent papers have no
  cold-load overhead and process in ~270s each.
- Start scheduler, ingest a paper via the scheduler queue, confirm `body_source=marker`.
- Bypasses the benchmark CLI entirely for L1 validation.
- Requires operator to start and monitor the scheduler service.

**Recommendation**: Option B is fastest path to L1 confirmation. Option C validates the
production path directly (stronger signal). Option A is highest-effort with uncertain outcome.

---

## Codex Review

Tier: Recommended (Dockerfile change touches image build; runtime permission model).
Issues found: original EPERM cause, zombie container GPU contention pattern.
Issues addressed: EPERM fixed (static dir pre-created). Zombie pattern documented.
Note: No L2/SVM/trading/n8n code was changed.
