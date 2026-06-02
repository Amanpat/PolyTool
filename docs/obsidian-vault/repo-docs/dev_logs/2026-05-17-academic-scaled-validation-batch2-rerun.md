---
title: Academic Scaled Validation Batch2 Rerun
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-17_academic-scaled-validation-batch2-rerun.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Academic Pipeline Scaled Validation — Batch 2 Full Rerun

**Date:** 2026-05-17  
**Type:** Execution record — full 29-paper scaled validation  
**Track:** Research Intelligence System — L1/L2  
**Prerequisites:**
- `docs/dev_logs/2026-05-17_academic-validation-triage-fixes.md` — 5-blocker triage
- `docs/dev_logs/2026-05-17_academic-validation-smoke-after-triage.md` — 4-paper smoke PASS

---

## Objective

Run all 29 operator-curated arXiv papers through the full Marker pipeline
(fetch → parse → body sidecar → index-done → research-query) using the
triage-fixed Docker/GPU container. Produce a validation classification:
production-ready / demo-ready / needs-triage.

---

## Files Changed

| File | Action | Reason |
|------|--------|--------|
| `docs/dev_logs/2026-05-17_academic-scaled-validation-batch2-rerun.md` | Created | This dev log |
| `docs/CURRENT_STATE.md` | Updated (post-run) | Record factual validation outcome |

No implementation code, benchmarks, L3 enforce settings, or spec files were changed.

---

## Pre-flight Checks

### Git Branch / Status

```
Branch: main
Triage fixes not yet committed (safe — live mounts carry the fixes into the container):
  M docker-compose.yml
  M packages/research/ingestion/fetchers.py
  M packages/research/ingestion/marker_ipc_worker.py
  M tests/test_ris_fetchers.py
  M docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md
  M docs/CURRENT_STATE.md
  M .gitignore
Untracked (smoke + triage dev logs, packages/__init__.py):
  ?? docs/dev_logs/2026-05-17_academic-validation-smoke-after-triage.md
  ?? docs/dev_logs/2026-05-17_academic-validation-triage-fixes.md
  ?? packages/__init__.py
```

### CLI Load

```
python -m polytool --help → OK (all research-marker-queue, index-done, research-query present)
```

### Docker / GPU

```
Container: polytool-ris-scheduler-gpu — Up 2 hours (post-smoke recreate)
GPU: RTX 2070 SUPER | 8192 MiB VRAM | CUDA 13.2 | Driver 595.97
GPU-Util: 2% idle | Memory: 799 MiB used at start (smoke models freed)
```

### KS State Pre-run

```
Academic docs: 78
Marker-indexed docs: 7
Snapshot: artifacts/debug/scaled_val_v2_prerun_discover.txt
```

### v2 Queue State Before Enqueue

```
pending: 0, done: 0, failed: 0, total: 0  (fresh queue)
```

---

## Step 1 — Enqueue

All 29 papers enqueued from the host using `enqueue --url ARXIV_ID --title TITLE`.
Enqueue calls are lightweight (title provided; no arXiv PDF fetch).

**Post-enqueue counts:** pending=29, done=0, failed=0, total=29

| # | arXiv ID | Category | Title hint |
|---|----------|----------|-----------|
| 1 | 1105.3115 | equation-heavy | inventory-risk market-making model HJB/ODE |
| 2 | 1106.5040 | equation-heavy | optimal HFT limit and market orders LOB |
| 3 | 1605.01862 | equation-heavy | general optimal market-making framework |
| 4 | 1206.4810 | equation-heavy | inventory-constrained market-making mid-price |
| 5 | 1705.01446 | equation-heavy | microstructural LOB model FIFO stochastic arrivals |
| 6 | 2003.05958 | equation-heavy | market making persistent order flow Hawkes |
| 7 | 2203.13053 | equation-heavy | mean-field game market making strategic traders |
| 8 | 1810.04383 | equation-heavy | closed-form approximations multi-asset market making |
| 9 | 2409.02025 | equation-heavy | regret analysis ergodic Avellaneda-Stoikov |
| 10 | 2307.14129 | equation-heavy | macroscopic market-making optimal execution bridge |
| 11 | 1011.6402 | table-heavy | empirical price-impact NYSE TAQ 50 stocks |
| 12 | 1609.03471 | table-heavy | binary prediction markets belief convergence |
| 13 | 2508.03474 | table-heavy | Polymarket arbitrage probabilistic-forest |
| 14 | 2605.00864 | table-heavy | algorithmic arbitrage Polymarket NBA markets |
| 15 | 2605.11640 | table-heavy | Polymarket non-retail trading behavioral tiers |
| 16 | 2605.02286 | table-heavy | information leakage Polymarket insider cases |
| 17 | 2605.00493 | table-heavy | ForesightFlow information-leakage score |
| 18 | 2507.08921 | table-heavy | Polymarket polling 2024 presidential election |
| 19 | 2604.10005 | table-heavy | institutional liquidity effects prediction markets |
| 20 | 2403.09267 | table-heavy | deep LOB forecasting microstructural guide benchmark |
| 21 | 2510.05533 | prose/survey | LLMs financial prediction and trading survey |
| 22 | 2212.12717 | prose/survey | deep learning stock market prediction survey |
| 23 | 2308.04947 | prose/survey | external knowledge stock-price prediction survey |
| 24 | 2507.01990 | prose/survey | LLMs financial applications structured review |
| 25 | 2208.13564 | prose/survey | NLP ML stock market movement prediction survey |
| 26 | 2604.20050 | outlier | information aggregation AI agents prediction markets |
| 27 | 2601.18815 | outlier | prediction markets Bayesian inverse problems |
| 28 | 2605.10400 | outlier | resolution-aware perpetual futures binary prediction markets |
| 29 | 2602.21091 | outlier | interest-bearing positions long-horizon prediction market liquidity |

---

## Step 2 — Warm-Process (Docker GPU container)

**Command (run inside container, background job):**
```bash
docker exec polytool-ris-scheduler-gpu sh -c "cd /app && python -m polytool \
  research-marker-queue --queue-dir /app/artifacts/research/scaled_validation_queue_v2 \
  warm-process --max-items 29 --marker-timeout 3600 2>&1 | \
  tee /app/artifacts/research/scaled_validation_queue_v2/warm_process_batch2.log"
```

**Run started:** 2026-05-17 ~22:18 UTC
**IPC warm-worker confirmed:** "Processing up to 29 item(s) via Linux/Docker IPC warm-worker"
**Paper 1 OCR started:** Layout recognition (36 pages) completed in 14s. OCR step started.

**Timing note from smoke test:** Cold JIT starts take 46–55 min per new format group.
Expected ~8 format groups × 50 min + ~21 warm papers × 5 min ≈ 8.5 hours total.
Actual paper 1 layout step ran in 14s (consistent with warm layout model OR fast layout step).
OCR step outcome pending.

---

## Per-Paper Parse Results

*(Populated after warm-process completes)*

| # | arXiv ID | Category | pages | ocr_batches | parse_s | body_len | ipc | marker_ready | failure_class |
|---|----------|----------|-------|-------------|---------|----------|-----|--------------|---------------|
| 1 | 1105.3115 | eq-heavy | — | — | — | — | — | — | — |
| 2 | 1106.5040 | eq-heavy | — | — | — | — | — | — | — |
| 3 | 1605.01862 | eq-heavy | — | — | — | — | — | — | — |
| 4 | 1206.4810 | eq-heavy | — | — | — | — | — | — | — |
| 5 | 1705.01446 | eq-heavy | — | — | — | — | — | — | — |
| 6 | 2003.05958 | eq-heavy | — | — | — | — | — | — | — |
| 7 | 2203.13053 | eq-heavy | — | — | — | — | — | — | — |
| 8 | 1810.04383 | eq-heavy | — | — | — | — | — | — | — |
| 9 | 2409.02025 | eq-heavy | — | — | — | — | — | — | — |
| 10 | 2307.14129 | eq-heavy | — | — | — | — | — | — | — |
| 11 | 1011.6402 | tbl-heavy | — | — | — | — | — | — | — |
| 12 | 1609.03471 | tbl-heavy | — | — | — | — | — | — | — |
| 13 | 2508.03474 | tbl-heavy | — | — | — | — | — | — | — |
| 14 | 2605.00864 | tbl-heavy | — | — | — | — | — | — | — |
| 15 | 2605.11640 | tbl-heavy | — | — | — | — | — | — | — |
| 16 | 2605.02286 | tbl-heavy | — | — | — | — | — | — | — |
| 17 | 2605.00493 | tbl-heavy | — | — | — | — | — | — | — |
| 18 | 2507.08921 | tbl-heavy | — | — | — | — | — | — | — |
| 19 | 2604.10005 | tbl-heavy | — | — | — | — | — | — | — |
| 20 | 2403.09267 | tbl-heavy | — | — | — | — | — | — | — |
| 21 | 2510.05533 | prose | — | — | — | — | — | — | — |
| 22 | 2212.12717 | prose | — | — | — | — | — | — | — |
| 23 | 2308.04947 | prose | — | — | — | — | — | — | — |
| 24 | 2507.01990 | prose | — | — | — | — | — | — | — |
| 25 | 2208.13564 | prose | — | — | — | — | — | — | — |
| 26 | 2604.20050 | outlier | — | — | — | — | — | — | — |
| 27 | 2601.18815 | outlier | — | — | — | — | — | — | — |
| 28 | 2605.10400 | outlier | — | — | — | — | — | — | — |
| 29 | 2602.21091 | outlier | — | — | — | — | — | — | — |

---

## Step 3 — Pre-Index Inspection

*(Populated after warm-process completes)*

---

## Step 4 — Index-Done (inside container)

*(Populated after index-done runs)*

**Command (inside container):**
```bash
docker exec polytool-ris-scheduler-gpu sh -c "cd /app && python -m polytool \
  research-marker-queue --queue-dir /app/artifacts/research/scaled_validation_queue_v2 \
  index-done"
```

---

## Step 5 — KS State Post-Run

*(Populated after index-done)*

---

## Step 6 — Research-Query Probes

*(Populated after index-done)*

| Probe | Query | had_fallback | claims | marker_hits | Papers hit |
|-------|-------|--------------|--------|-------------|-----------|
| 1 | "inventory" | — | — | — | — |
| 2 | "order book" | — | — | — | — |
| 3 | "prediction market" | — | — | — | — |
| 4 | "Polymarket" | — | — | — | — |
| 5 | "calibration" | — | — | — | — |
| 6 | "arbitrage" | — | — | — | — |
| 7 | "market maker" | — | — | — | — |

---

## Corpus-Level Summary Metrics

*(Populated after run)*

| Metric | Target | Result |
|--------|--------|--------|
| attempted | 29 | — |
| marker_ready (parsed OK) | ≥26 | — |
| failed | ≤3 | — |
| no_body_count | ≤3 | — |
| had_fallback_rate | <10% | — |
| low_chunk_suspicious_count | ≤2 | — |
| retrieval_success_rate | ≥80% | — |
| citation_traceability | ≥80% | — |
| total_chunks_indexed | — | — |
| total_claims_extracted | — | — |

---

## Validation Classification

*(Populated after probes)*

Classification: **PENDING**

---

## Open Items / Blockers

*(Populated at close)*

---

## Codex Review

Tier: Skip — no implementation code changed in this session. Only artifacts and dev log produced.
