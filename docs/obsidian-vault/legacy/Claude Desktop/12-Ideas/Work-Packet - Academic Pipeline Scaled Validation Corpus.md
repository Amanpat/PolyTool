---
tags: [work-packet, ris, academic, marker, validation, benchmark, corpus]
date: 2026-05-13
status: draft
priority: high
phase: post-completion-polish
target-layer: L1/L2/L5
prerequisites:
  - "L5 v0.1 rerun complete (2026-05-13) — all 9 metrics confirmed stable on 23-paper v0 corpus"
  - "L1 Marker Production Readiness Rollout COMPLETE (2026-05-09)"
  - "L2 Academic Query COMPLETE (2026-05-09)"
  - "3-paper operator validation COMPLETE (2026-05-09)"
unblocks:
  - "L5 v1 baseline — requires new QA pairs + operator review (separate work packet)"
  - "Benchmark Recommendation A (pre-fetch filtering) — corpus quality data needed first"
do-not-start-until:
  - "Operator selects and approves 20-30 arXiv URLs (fill table in Section 3)"
---

# Work Packet — Academic Pipeline Scaled Validation Corpus

> [!INFO] Status: DRAFT — Awaiting Operator URL Selection
> This is a planning document. No ingestion, benchmarking, or code changes should be made
> from this packet alone. The execution session must create its own dev log.

> [!WARNING] Scope Guard
> - Do NOT implement L2 semantic/vector retrieval (deferred as L2.1)
> - Do NOT enable SVM enforce mode — hard-blocked pending Director approval
> - Do NOT add SSRN/NBER harvesters — deferred per SOURCE_CAPABILITY_MATRIX
> - Do NOT validate Docker IPC batch performance — separate optional infra follow-up
> - Do NOT bulk-accept QA pairs — each pair requires individual operator verification
> - Do NOT claim academic pipeline production-ready from this run alone

---

## 1. Purpose and Context

The L5 v0.1 rerun (2026-05-13) confirmed that all 9 benchmark metrics are **identical** to
baseline_v0 (2026-05-02) because the benchmark manifest still targets the original 23-paper
corpus. The KnowledgeStore has since grown to 74 academic records, including 3 Marker-parsed
papers from the 3-paper operator validation (2026-05-09). However, none of those 3 papers
are in the v0 corpus manifest.

This work packet defines the next validation step: run 20–30 operator-curated arXiv papers
through the **full Marker pipeline** (enqueue → warm-process → index-done), verify each
paper's parse quality, run `research-query` probes, collect structured metrics, and produce
a summary report. This is not a new feature — it exercises the existing production path at
a scale that reveals real-world failure modes (timeouts, short-body rejections, equation
density mismatches) that 3 papers cannot surface.

**Why this matters:**
- The 3-paper validation used `ipc_warm_worker_used=false` (Windows warm-thread, not Docker
  GPU IPC). Scaled validation reveals whether Marker throughput is consistent across diverse
  PDF structures.
- The v0 corpus's 23 papers are PDF-parsed (`body_source=pdf`). This run will produce the
  first Marker-parsed corpus large enough to run a meaningful benchmark pass.
- Failures discovered here (not in a 3-paper run) justify triage and potential bug fixes
  before any v1 baseline is locked.

**Outcome of this work packet (not a new feature):**
1. A structured metrics table for all 20-30 papers
2. A final parse-quality summary report
3. A determination of production-ready vs demo-ready corpus state
4. Optional: a new corpus manifest candidate (`research_eval_benchmark_v1_corpus.draft.json`)
   if ≥20 papers parse successfully (operator decision required before promotion)

---

## 2. KS Health Pre-checks (Run Before Enqueueing)

These discrepancies were identified in the v0.1 rerun (2026-05-13) and should be triaged
before the scaled run begins. Record actual findings in the execution dev log.

### 2.1 `0838c7de` — KS/index desync candidate

| Field | KnowledgeStore state | Lexical index state |
|-------|---------------------|---------------------|
| chunk_count | 1 (stub) | 39 chunks (indexed 2026-05-13) |
| body_source | unknown | — |
| body_length | None | body text present in raw_source_cache |

**Paper:** "High frequency market microstructure noise estimates and liquidity measures"  
**Action:** Run `research-marker-queue index-done` OR re-acquire via `research-acquire --url <url>`.
Confirm KS entry updates to `chunk_count≥30, body_source=marker` after the fix.
Record outcome in the execution dev log. Do NOT count this paper in v0.1 metrics — it is
not part of the 23-paper corpus evaluation.

### 2.2 `bad51e5db` — missing raw body cache

| Field | KnowledgeStore state | raw_source_cache |
|-------|---------------------|-----------------|
| chunk_count | 1 (stub) | file absent (skipped on 2026-05-13 refresh) |
| body_source | unknown | — |

**Paper:** "The Homogenous Properties of Automated Market Makers"  
**Action:** Determine if this is intentionally removed or a cache gap. Re-acquire if desired.
Record outcome. No QA pairs target this paper, so it is not blocking benchmark metrics.

### 2.3 Pre-existing test failures in `test_ris_phase4_source_acquisition.py`

Three tests in `TestEndToEnd` fail due to `academic_marker_gate` rejecting abstract-only
fixtures. These failures pre-date this work packet (introduced in commit `03c9546`).
**Do not fix in this session** — they require fixture updates and belong in a separate
targeted bug-fix prompt. Record their status (still failing / fixed) in the execution dev log.

---

## 3. Target Corpus — Operator Input Required

> [!NOTE] Exclusion
> `0805.1521` was intentionally excluded because it is not Avellaneda-Stoikov on arXiv.

Approved 29-paper corpus (operator-curated 2026-05-16). Required columns:

| # | arXiv URL | Category | Reason selected | Expected difficulty | Known external context / notes |
|---:|---|---|---|---|---|
| 1 | https://arxiv.org/abs/1105.3115 | equation-heavy microstructure/math | Canonical inventory-risk market-making model; HJB/ODE derivations and optimal quotes. | High | Substitute for Avellaneda-Stoikov because it is arXiv-native and directly relevant to market making. |
| 2 | https://arxiv.org/abs/1106.5040 | equation-heavy microstructure/math | Optimal high-frequency trading with limit and market orders in a limit order book. | High | Good test for equations, stochastic control, and LOB terminology. |
| 3 | https://arxiv.org/abs/1605.01862 | equation-heavy microstructure/math | General optimal market-making framework extending Avellaneda-Stoikov-style models. | High | Tests long derivations and multi-section mathematical structure. |
| 4 | https://arxiv.org/abs/1206.4810 | equation-heavy microstructure/math | Extends inventory-constrained market-making models to broader mid-price processes. | High | Useful for parser handling of equations, utility functions, and model variants. |
| 5 | https://arxiv.org/abs/1705.01446 | equation-heavy microstructure/math | Microstructural limit-order-book model with FIFO queues and stochastic order arrivals. | High | Strong fit for replay/fill-model research. |
| 6 | https://arxiv.org/abs/2003.05958 | equation-heavy microstructure/math | Market making with persistent order flow using Hawkes/order-flow dynamics. | High | Tests Hawkes-process notation and dense theorem/proof structure. |
| 7 | https://arxiv.org/abs/2203.13053 | equation-heavy microstructure/math | Mean-field game of market making against strategic traders. | High | Tests coupled HJB/Fokker-Planck style content. |
| 8 | https://arxiv.org/abs/1810.04383 | equation-heavy microstructure/math | Closed-form approximations in multi-asset market making. | High | Good parser stress case: many formulas, figures, and references. |
| 9 | https://arxiv.org/abs/2409.02025 | equation-heavy microstructure/math | Regret analysis in the ergodic Avellaneda-Stoikov market-making model. | High | Good modern math-heavy stress test. |
| 10 | https://arxiv.org/abs/2307.14129 | equation-heavy microstructure/math | Macroscopic market-making model bridging market making and optimal execution. | Medium-High | Useful bridge between theory and execution-style models. |
| 11 | https://arxiv.org/abs/1011.6402 | table-heavy empirical | Empirical price-impact study using NYSE TAQ data for 50 stocks. | High | Strong table/figure/charts candidate; directly relevant to order-flow imbalance. |
| 12 | https://arxiv.org/abs/1609.03471 | table-heavy empirical | Empirical study of binary prediction markets and belief convergence. | Medium-High | Direct prediction-market retrieval test. |
| 13 | https://arxiv.org/abs/2508.03474 | table-heavy empirical | Polymarket arbitrage / probabilistic-forest paper. | High | Domain-specific and likely highly relevant to PolyTool strategy research. |
| 14 | https://arxiv.org/abs/2605.00864 | table-heavy empirical | Empirical analysis of algorithmic arbitrage in Polymarket NBA markets. | High | Very relevant to sports/Polymarket arbitrage; recent and likely table-heavy. |
| 15 | https://arxiv.org/abs/2605.11640 | table-heavy empirical | Polymarket non-retail trading / behavioral tiers / microstructure signatures. | High | Strong test for large empirical claims, clustering, and market microstructure language. |
| 16 | https://arxiv.org/abs/2605.02286 | table-heavy empirical | Empirical evaluation of information leakage on documented Polymarket insider cases. | Medium-High | Useful for informed-trading and event-timing retrieval probes. |
| 17 | https://arxiv.org/abs/2605.00493 | table-heavy empirical | ForesightFlow information-leakage score for decentralized prediction markets. | Medium-High | Good test for methods, score definitions, and empirical examples. |
| 18 | https://arxiv.org/abs/2507.08921 | table-heavy empirical | Compares Polymarket and polling in the 2024 presidential election. | Medium | Good applied prediction-market paper with easier language but empirical tables. |
| 19 | https://arxiv.org/abs/2604.10005 | table-heavy empirical | Studies institutional liquidity effects in prediction markets. | Medium-High | Useful for liquidity/spread/slow-trader retrieval probes. |
| 20 | https://arxiv.org/abs/2403.09267 | table-heavy empirical | Deep limit-order-book forecasting with a microstructural guide and benchmark framing. | High | Strong parser stress case for tables, figures, model comparisons, and LOB terminology. |
| 21 | https://arxiv.org/abs/2510.05533 | prose/survey | Survey of LLMs in financial prediction and trading. | Medium | Good prose-heavy RAG test; relevant to research-agent architecture. |
| 22 | https://arxiv.org/abs/2212.12717 | prose/survey | Survey of deep learning techniques for stock market prediction. | Medium | Good long-survey parsing and retrieval baseline. |
| 23 | https://arxiv.org/abs/2308.04947 | prose/survey | Survey on acquiring/incorporating external knowledge into stock-price prediction models. | Medium | Relevant to RAG and external-knowledge ingestion. |
| 24 | https://arxiv.org/abs/2507.01990 | prose/survey | Structured review of LLMs in financial applications. | Medium | Useful for prose/reference-heavy parser validation. |
| 25 | https://arxiv.org/abs/2208.13564 | prose/survey | Survey of NLP and ML techniques for stock-market movement prediction. | Medium | Tests survey-style chunking, citations, and taxonomy retrieval. |
| 26 | https://arxiv.org/abs/2604.20050 | outlier | Information aggregation with AI agents in prediction markets. | Medium-High | Outlier because it mixes LLM agents, market trading, and prediction-market theory. |
| 27 | https://arxiv.org/abs/2601.18815 | outlier | Prediction markets framed as Bayesian inverse problems. | High | Outlier because it is mathematically framed but domain-specific to prediction markets. |
| 28 | https://arxiv.org/abs/2605.10400 | outlier | Resolution-aware perpetual futures on binary prediction markets using Polymarket data. | High | Outlier because it blends derivatives/perps, prediction markets, and empirical risk design. |
| 29 | https://arxiv.org/abs/2602.21091 | outlier | Interest-bearing positions and the long-horizon prediction-market liquidity problem. | Medium-High | Outlier because it tests policy/simulation-style content rather than pure microstructure. |

### Category Definitions

| Category | Use for |
|----------|---------|
| `equation_heavy` | Dense formulas, proofs, stochastic calculus — tests Marker math rendering |
| `table_heavy` | Empirical data tables, regression output — tests Marker table extraction |
| `prose_heavy` | Survey, review, conceptual — tests Marker body completeness |
| `outlier` | Intentionally off-topic (ML, biology, physics unrelated to markets) — tests off-topic classifier |

### Expected Difficulty Definitions

| Difficulty | Meaning |
|-----------|---------|
| `easy` | Clean PDF, typical structure, no special fonts or color figures |
| `medium` | Multi-column layout, moderate equation density, some special characters |
| `hard` | Scanned PDF, dense math, unusual layout, images-as-equations |

### Candidate Suggestions (Operator Review Required)

The following are suggested starting points. Verify each arXiv ID before enqueueing.
**Do not enqueue papers already in the KnowledgeStore unless re-indexing is intended.**
Check `python -m polytool research-eval-benchmark --discover-corpus` before adding a URL.

**Equation-heavy — Market Making / Optimal Control:**
- `0805.1521` — Avellaneda & Stoikov, "High-frequency trading in a limit order book" (THE canonical MM reference)
- `1204.0392` — Gueant, Lehalle, Fernandez-Tapia, "Dealing with the inventory risk: a solution to the market making problem"
- `1910.05733` — "Optimal market making with persistent order flow" (Lehalle / Neuman)
- `2006.05532` — "Reinforcement learning for market making in multi-agent dealer markets"
- `1901.08263` — "Deep reinforcement learning for limit order book management and option hedging"
- `1307.3967` — "Optimal high-frequency trading with limit and market orders"

**Equation-heavy — Prediction Market Theory:**
- `1604.01020` — "Eliciting Expertise without Expert Knowledge" (Witkowski, Bachrach et al)
- `2103.09873` — Papers on binary scoring rules / calibration theory

**Table-heavy — Empirical:**
- `1606.07781` — "Are betting markets efficient?" (empirical sports betting study)
- `2302.04008` — Empirical study of DeFi AMM price impact
- `2106.14745` — "A large-scale empirical analysis of prediction market accuracy"

**Prose/Survey:**
- `2205.02777` — Survey paper on DeFi liquidity provision mechanisms
- `1612.09359` — "A review of market microstructure research"
- `2108.05003` — "Prediction markets: theory and applications survey"

**Outlier (off-topic, for classifier validation):**
- `2301.00001` or similar non-finance arXiv paper — operator selects from CS/Biology/Physics
- Pick 3-5 papers clearly outside prediction markets, market making, quantitative finance

> [!IMPORTANT] Before starting execution
> 1. Fill in all rows with actual arXiv IDs
> 2. Cross-reference against `--discover-corpus` output to avoid re-enqueueing existing papers
> 3. Confirm Docker GPU container is running: `docker compose --profile ris-gpu run --rm ris-scheduler-gpu nvidia-smi`
> 4. Decide queue dir: use a named isolation dir (e.g. `artifacts/research/scaled_validation_queue_v1`) to avoid contaminating the main queue

---

## 4. Execution Flow

Run these steps **in order**. Do not skip or reorder. Every step must be recorded in the
execution session's dev log with actual command output.

### Step 0 — Pre-flight checks

```bash
# 1. Clean git state
git status --short

# 2. CLI loads without error
python -m polytool --help

# 3. Discover current KS corpus (record count for delta tracking)
python -m polytool research-eval-benchmark --discover-corpus > artifacts/debug/scaled_val_prerun_discover.txt

# 4. Queue counts — should be zero if using a fresh queue dir
python -m polytool research-marker-queue --queue-dir artifacts/research/scaled_validation_queue_v1 counts

# 5. GPU available (run inside Docker container)
docker compose --profile ris-gpu run --rm ris-scheduler-gpu nvidia-smi
```

Record: KS total at start, queue initial state, GPU status.

### Step 1 — Enqueue all papers

Enqueue each arXiv paper using the isolated queue dir. Process in batches of 5-10 to
keep the queue manageable.

```bash
# Template (repeat for each paper):
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/scaled_validation_queue_v1 \
  enqueue --url <ARXIV_ID>

# Check queue after all enqueues:
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/scaled_validation_queue_v1 \
  counts
# Expected: pending=N, done=0, failed=0
```

Record: exact IDs enqueued, any `already_exists` warnings (re-enqueue with `--force` if intended).

### Step 2 — Parse with Marker (Docker GPU container)

Run `warm-process` **inside** the Docker/GPU container. Use `--max-items` equal to batch
size. For 20-30 papers, consider batches of 10 to allow checkpoint inspection between runs.

```bash
# Run inside GPU container (adjust --max-items as needed):
docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
  python -m polytool research-marker-queue \
    --queue-dir /workspace/artifacts/research/scaled_validation_queue_v1 \
    warm-process \
    --max-items 10 \
    --marker-timeout 900

# After each batch, check status:
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/scaled_validation_queue_v1 \
  list --status failed

python -m polytool research-marker-queue \
  --queue-dir artifacts/research/scaled_validation_queue_v1 \
  counts
```

Record per paper (from results.jsonl): `body_source`, `body_length`, `parse_seconds`,
`ipc_warm_worker_used`, `marker_ready`, `failure_reason`.

**If a paper fails:** Check `failure_reason`. Classify as:
- `short_body` — Marker parsed but extracted <5000 chars (PDF may be scanned/image-only)
- `marker_failed` — Marker crashed or timed out
- `error` — Network, disk, or other infrastructure error
- `timeout` — Exceeded `--marker-timeout`

Do NOT re-enqueue failed papers in the same session without understanding the failure class.
Record all failures in the dev log with the failure_reason and next-action classification.

### Step 3 — Inspect before indexing

Before running `index-done`, verify the `results.jsonl` summary:

```bash
# Print per-paper parse results (PowerShell):
Get-Content artifacts\research\scaled_validation_queue_v1\results.jsonl | ForEach-Object { $_ | ConvertFrom-Json | Select-Object candidate_id, body_source, body_length, parse_seconds, marker_ready, failure_reason } | Format-Table

# Or via Python:
python -c "
import json
results = [json.loads(l) for l in open('artifacts/research/scaled_validation_queue_v1/results.jsonl')]
done = [r for r in results if r.get('queue_status')=='done' and r.get('marker_ready')]
failed = [r for r in results if r.get('queue_status')=='failed']
print(f'Marker-ready: {len(done)}, Failed: {len(failed)}, Total: {len(results)}')
for r in failed:
    print(f'  FAIL: {r.get(\"candidate_id\",\"?\")[:20]}... reason={r.get(\"failure_reason\")}')
"
```

Abort and diagnose if failure rate > 20% before proceeding to index-done.

### Step 4 — Index into KnowledgeStore + extract claims

```bash
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/scaled_validation_queue_v1 \
  index-done

# JSON output for scripted capture:
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/scaled_validation_queue_v1 \
  index-done --json
```

Record: `indexed_count`, `skipped_no_body`, `skipped_already_indexed`, `claim_count` per paper.

### Step 5 — Verify body/chunk/claim counts in KS

```bash
# Discover updated corpus (compare to pre-run snapshot):
python -m polytool research-eval-benchmark --discover-corpus > artifacts/debug/scaled_val_postrun_discover.txt

# Compare counts:
python -c "
pre = open('artifacts/debug/scaled_val_prerun_discover.txt').read()
post = open('artifacts/debug/scaled_val_postrun_discover.txt').read()
pre_count = pre.count('[')
post_count = post.count('[')
print(f'KS academic records: before={pre_count}, after={post_count}, delta=+{post_count-pre_count}')
"
```

For each newly indexed paper, record: `chunk_count`, `body_source`, `body_length` from
the discover output. Flag any paper with `chunk_count < 5` as suspicious.

### Step 6 — Run research-query probes

Run at least 5 representative queries using the L2 CLI. For each query, record whether
citations have `body_source=marker` and `had_fallback=false`.

Suggested probe queries (operator may adjust based on the actual corpus):

```bash
# Probe 1 — Core domain
python -m polytool research-query --question "optimal bid-ask spread market making" --k 5

# Probe 2 — Prediction market theory
python -m polytool research-query --question "calibration of prediction market prices" --k 5

# Probe 3 — Empirical performance
python -m polytool research-query --question "statistical arbitrage betting markets empirical" --k 5

# Probe 4 — Step-back expansion (tests L2 query normalization)
python -m polytool research-query \
  --question "how does inventory risk affect market maker profitability" \
  --k 10 --step-back

# Probe 5 — Harder cross-paper question
python -m polytool research-query \
  --question "adverse selection informed trading limit order book" \
  --k 10
```

Record for each probe: query string, `had_fallback`, number of citations with
`body_source=marker`, any empty-result or no-citation responses.

### Step 7 — Collect metrics into a structured table

Produce a metrics table for the execution dev log. One row per paper.

---

## 5. Required Metrics

Collect the following for every paper processed. Record in the execution dev log.

### Per-paper parse metrics (from results.jsonl)

| Metric | Source | Acceptable |
|--------|--------|-----------|
| `parse_seconds` | results.jsonl | <300s preferred; >900s = timeout |
| `parser_path` | results.jsonl `body_source` | `marker` = production; else = failure |
| `fallback_flag` | results.jsonl `marker_ready=False` | True = needs triage |
| `body_length` | results.jsonl | ≥5000 chars = RAG-ready |
| `ipc_warm_worker_used` | results.jsonl | `true` if Docker IPC; `false` if local warm-thread |
| `failure_reason` | results.jsonl | null on success; classify on failure |
| `failure_class` | operator-assigned | short_body / marker_failed / timeout / error |

### Per-paper KS verification (from --discover-corpus after index-done)

| Metric | Source | Acceptable |
|--------|--------|-----------|
| `chunk_count` | discover output | ≥5 = acceptable; <5 = suspicious |
| `body_source` | discover output | `marker` for all newly indexed |
| `body_length` | discover output | matches results.jsonl value |

### Per-paper claims (from index-done --json output)

| Metric | Source | Acceptable |
|--------|--------|-----------|
| `claim_count` | index-done output | ≥10 per paper (heuristic) |
| `indexed` | index-done output | True for all marker-ready done items |

### Corpus-level summary metrics

| Metric | Definition | Target |
|--------|-----------|--------|
| `no_body_count` | Papers with `marker_ready=False` or `failure_reason` not null | ≤3 |
| `low_chunk_suspicious_count` | Papers with `chunk_count < 5` after indexing | ≤2 |
| `had_fallback_rate` | Fraction of papers not achieving `body_source=marker` | <10% |
| `retrieval_success_rate` | Probes where `had_fallback=false` / total probes | ≥80% |
| `citation_traceability` | Probes where ≥1 citation has `body_source=marker` | ≥80% |
| `error_class_distribution` | Count by failure class (short_body/marker_failed/timeout/error) | Record all |

---

## 6. Acceptance Criteria

The scaled validation run PASSES when ALL of the following hold:

1. **No silent fallbacks.** Every paper with `marker_ready=False` has an explicit
   `failure_reason` recorded. No paper silently produces a PDF-only or abstract-only
   KS entry without operator acknowledgment.

2. **No unclassified no-body failures.** Every failed paper is assigned one of:
   `short_body`, `marker_failed`, `timeout`, `error`. No catch-all "unknown" failures.

3. **All failures triaged.** For each failed paper: (a) failure class recorded,
   (b) next action documented (re-enqueue with longer timeout / drop / operator decision),
   (c) whether the failure is a Marker bug, a PDF characteristic, or an infra issue.

4. **Query citations returned.** At least 4 of 5 research-query probes return at least
   one citation with `body_source=marker` and `had_fallback=false`.

5. **Corpus metrics within range.** `no_body_count ≤ 3`, `had_fallback_rate < 10%`,
   `low_chunk_suspicious_count ≤ 2`.

6. **Report distinguishes production-ready vs demo-ready.**
   - *Production-ready*: ≥20 papers indexed, no systematic failures, all probes return
     citations, metrics within range. Suitable for a v1 baseline corpus candidate.
   - *Demo-ready*: 10–19 papers indexed, <3 failures, probe citations work. Suitable
     for showcasing the pipeline but not for locking a new benchmark baseline.
   - *Needs triage*: >3 failures OR >1 probe has `had_fallback=true`. Record root causes
     before any next step.

**Do NOT claim the academic pipeline is production-ready based on this run alone.**
The classification above informs the next Director decision, not a promotion.

---

## 7. Output Artifacts

The execution session must produce:

| Artifact | Path | Notes |
|----------|------|-------|
| Queue results | `artifacts/research/scaled_validation_queue_v1/results.jsonl` | Gitignored; capture key rows in dev log |
| Queue bodies | `artifacts/research/scaled_validation_queue_v1/bodies/` | Gitignored |
| Pre-run discover snapshot | `artifacts/debug/scaled_val_prerun_discover.txt` | Gitignored |
| Post-run discover snapshot | `artifacts/debug/scaled_val_postrun_discover.txt` | Gitignored |
| Execution dev log | `docs/dev_logs/YYYY-MM-DD_academic-scaled-validation-run.md` | Committed |
| Corpus manifest candidate (optional) | `config/research_eval_benchmark_v1_corpus.draft.json` | Only if ≥20 papers index cleanly; operator reviews before use |

---

## 8. Don't Do

| Prohibited | Reason |
|-----------|--------|
| L2 semantic/vector retrieval (ChromaDB academic path) | Deferred as L2.1; `body_source` not in Chroma metadata |
| SVM enforce mode | Hard-blocked at rc=1 pending Director approval |
| SSRN/NBER harvesters | Deferred per SOURCE_CAPABILITY_MATRIX (session/cookie brittleness) |
| Docker IPC batch performance validation | Separate optional infra follow-up; not a functional blocker |
| Bulk-accepting QA pairs | Each pair requires individual operator verification against body text |
| Modifying baseline_v0.json or baseline_v0.1.json | Baselines are locked |
| Modifying `config/research_eval_benchmark_v0_corpus.draft.json` | v0 corpus manifest is locked |
| Changing L3 enforce settings | SVM enforce deferred; `hold-review` and `dry-run` safe |
| Lowering academic_marker_gate thresholds | Gate is correct; test fixtures need updating separately |
| Claiming pipeline production-ready without Director sign-off | DoD requires explicit classification |

---

## 9. Dev Log Requirements for Execution Session

The execution session dev log (`docs/dev_logs/YYYY-MM-DD_academic-scaled-validation-run.md`) MUST include:

1. Pre-flight check results (git status, CLI ok, KS count at start, GPU status)
2. Complete list of arXiv IDs enqueued, with category and title
3. Per-paper metrics table (parse_seconds, body_length, chunk_count, claim_count, failure_reason)
4. Corpus-level summary metrics table
5. Research-query probe results (all 5+ probes with had_fallback and citations)
6. KS health status (0838c7de desync resolution, bad51e5d status, test failure status)
7. Production-ready vs demo-ready classification with rationale
8. Open questions and any failures requiring Director decision
9. Codex review line (Tier: Recommended — Marker queue / index-done code paths touched)

---

## 10. Open Questions for Aman (Operator Decisions)

1. **URL selection:** Which 20–30 arXiv papers should be in the validation corpus? Fill in
   Section 3's table. Aim for genuine domain coverage; the candidate suggestions are
   starting points, not a final list.

2. **Queue isolation:** The template uses `scaled_validation_queue_v1` as the queue dir.
   Confirm this is the right name, or specify a different one before starting.

3. **Batch size:** Process all 20-30 papers in one session, or in batches of 10?
   Batches allow checkpointing and failure inspection between runs.

4. **`0838c7de` desync repair:** Should this paper's KS entry be re-indexed before or
   during the scaled run? It is not in the v0 corpus manifest but is in the KS with
   conflicting state.

5. **v1 corpus manifest promotion criteria:** If ≥20 papers index cleanly, do you want
   the execution session to write a draft v1 corpus manifest? Or defer that to a
   separate session after reviewing parse quality?

6. **Pre-existing test failures:** The 3 `academic_marker_gate` test failures should be
   fixed, but is that in scope for the execution session or a separate targeted fix?
   (Recommendation: separate fix session — do not mix into the validation run.)
