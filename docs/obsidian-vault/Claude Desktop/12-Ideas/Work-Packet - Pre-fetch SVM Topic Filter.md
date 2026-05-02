---
tags: [work-packet, ris, ingestion, filtering, shipped]
date: 2026-04-29
activated: 2026-05-01
shipped: 2026-05-02
status: shipped
priority: medium
phase: 2
target-layer: 3
parent-architecture: "[[11-Scientific-RAG-Target-Architecture]]"
parent-decision: "[[Decision - Scientific RAG Architecture Adoption]]"
prerequisites:
  - "[[Work-Packet - Academic Pipeline PDF Download Fix]] (Layer 0 — shipped)"
  - "[[Work-Packet - Scientific RAG Evaluation Benchmark]] (Layer 5 — quantifies off-topic rate, justifies activation)"
  - "Operator review queue accumulating accept/reject decisions (~30+ each) OR Layer 5 measures off-topic rate >30%"
---

# Work Packet (shipped) — Pre-fetch Relevance Filter

> [!IMPORTANT] Activation — 2026-05-01
> Activated by L5 Evaluation Benchmark v0 result: **off_topic_rate = 30.43% (7/23 papers), Rule A fired**.
> Activation condition (b) from the original stub was met. Prompt A scope is **v0: deterministic cold-start metadata filter** — no heavy ML dependencies. SPECTER2 / S2FOS / SVM is the **v1 path**, activated after ≥30 accept and ≥30 reject operator labels accumulate in the YELLOW queue.

## Layer

Layer 3 of the [[11-Scientific-RAG-Target-Architecture|four-layer scientific RAG target]].

## Activation Evidence

L5 Evaluation Benchmark v0 baseline locked 2026-05-02. Source: `docs/features/FEATURE-ris-scientific-eval-benchmark-v0.md`.

| Metric | Value | Signal |
|--------|-------|--------|
| Off-topic rate | **30.43%** (7/23 papers) | **Rule A fired** — primary recommendation |
| Fallback rate | 0.0% | No signal |
| Retrieval P@5 | 1.0 (35/35 papers found at rank ≤5) | No signal |
| Median chunk count | 25 | No signal |

Rule A fires when `off_topic_rate > 30%`. The threshold is 30%. 30.43% > 30% — condition met by one paper above threshold. The 7 flagged papers:

- Hastelloy-X fatigue life prediction (materials science — clearly off-topic)
- Head/neck cancer outcome prediction (medical ML — clearly off-topic)
- Indian Financial Market cross-correlation (borderline — microstructure but not PM)
- E-commerce delayed conversion modeling (borderline)
- How Market Ecology Explains Market Malfunction (market microstructure — potential false positive)
- On a Class of Diverse Market Models (stochastic portfolio theory — borderline)
- The Inelastic Market Hypothesis (market microstructure — potential false positive)

Three were intentional outlier entries when the draft corpus was built. The other four crept in during early broad-topic ingestion.

## What ships in v0 (Prompt A scope — no SVM)

A deterministic cold-start pre-fetch decision step wired into `research-acquire`. Requires **no heavy ML dependencies** (no SPECTER2, no sklearn SVM, no GPU, no nightly retraining).

Implementation approach:

1. **Seed-topic keyword list** covering: prediction markets, market microstructure, market making, Avellaneda-Stoikov, Kelly criterion, quantitative finance, order flow, CLOB, binary options, limit order book, bid-ask spread
2. **Score** candidate paper title + abstract against seed-topic list (keyword overlap count or lightweight TF-IDF cosine similarity against a seed document)
3. **Decision**: above threshold → proceed to fetch + parse + LLM gate; below threshold → skip with logged reason code
4. **Default mode: `off`** — filter is not invoked unless explicitly activated via `--prefetch-filter-mode`
5. **Operating modes** (via `--prefetch-filter-mode {off,dry-run,enforce}`):
   - `off` (default) — filter not called
   - `dry-run` — score and log; always proceed with ingest (audit mode)
   - `enforce` — REJECT candidates skipped; REVIEW candidates ingested with audit flag

The seed keyword list is the "model" for v0. It is a text file, not a trained artifact.

## What ships in v1 (future — after label accumulation)

The ML-backed filter specified in [[Decision - Scientific RAG Architecture Adoption]] item 3:

1. SPECTER2 embedding of (title + abstract)
2. S2FOS field-of-study labels (when Semantic Scholar metadata is available)
3. Domain-specific SVM trained on operator accept/reject decisions plus a seed set
4. Above threshold → proceed to fetch + parse + LLM gate; below threshold → skip

**v1 trigger**: ≥30 accept labels AND ≥30 reject labels accumulated in the YELLOW queue.

Training data path: operator decisions in the YELLOW queue (each accept/reject = one labeled example). SVM retrains nightly. The v0 seed keyword decisions seed the initial positive/negative set for v1 training.

## Scope guards

- Do NOT replace the LLM evaluation gate — this filter is upstream of it, not a substitute. The LLM gate scores depth and substance; this filter screens relevance.
- **v0 only: keyword/TF-IDF scoring** — no neural classifier, no SVM, no SPECTER2 in Prompt A
- **v1 only**: SVM — no neural classifier beyond SPECTER2 (per arXiv-Sanity-Lite pattern; minimal infra)
- Threshold tunable via config; start permissive (low false-negative rate), tighten as operator review accumulates
- Filter decisions logged with structured reason codes — feed back into training data via the acquisition review JSONL
- Filter runs on metadata only (title + abstract) — no PDF download required before the decision
- Do NOT modify Layer 4 fetchers — they call the filter; the filter doesn't reach into them
- Default safe: `--prefetch-filter-mode` defaults to `off` — filter is not invoked; use `dry-run` for audit, `enforce` for reject-only blocking

## Acceptance gates (v0)

All six gates must pass before v0 is declared shipped:

1. **Simulated off-topic rate**: filter applied retrospectively to the 23-paper L5 v0 corpus produces a simulated pass/reject outcome where ≤2 of the 7 currently-flagged off-topic papers would have been ingested (simulated off_topic_rate < 10%)
2. **Zero false negatives on golden corpus**: all 10 distinct QA papers from `tests/fixtures/research_eval_benchmark/golden_qa_v0.json` score above threshold and would pass the filter (no core papers blocked)
3. **Deterministic replay**: identical input metadata always produces the same pass/reject decision across multiple runs (no randomness, no timestamp dependence)
4. **Decision log**: every filter invocation writes a structured log entry containing: `paper_id`, `decision` (pass/reject), `reason_code`, `score`, `threshold`, `timestamp`
5. **Default safe**: default mode is `off` (filter not invoked); `dry-run` logs without blocking; `enforce` blocks only REJECT decisions — ingestion proceeds for ALLOW and REVIEW in all modes
6. **Enforcement explicit**: blocking mode requires `--prefetch-filter-mode enforce`; REVIEW candidates are never skipped in enforce mode (ingested with audit flag); flag documented in operator runbook

## Shipped Results (v0 — DB-backed, 2026-05-02)

Config version v1.1 (`allow_threshold=0.80`, `review_threshold=0.35`), run against the 23-paper L5 corpus:

| Metric | Value |
|--------|-------|
| Decisions | ALLOW 17, REVIEW 3, REJECT 3 |
| Baseline off_topic_rate | 30.43% (7/23) |
| Scenario A — reject excluded, review included | 20.0% (4/20 off-topic) |
| Scenario B — allow-only (reject+review excluded) | **5.88%** (1/17 off-topic) |
| Target <10% (Scenario B) | **YES** |
| QA papers in REJECT | **0** (zero false negatives) |
| Tests | 113 passed, 0 failed |

> [!WARNING] Scenario A ≠ <10% gate
> Reject-only enforcement (`--prefetch-filter-mode enforce`) corresponds to **Scenario A (20.0%)**, not Scenario B. Do not claim enforce mode achieves the <10% target. The <10% success is the allow-only simulation (Scenario B), not the current enforce path.

## Enforcement Readiness (from Codex re-review PASS WITH FIXES)

| Mode | Status |
|------|--------|
| `dry-run` | **Safe now** — logs decisions, never blocks |
| `enforce` (reject-only) | **Mechanically safe — experimental** — QA REJECT=0; removes 3 clear negatives; Scenario A = 20.0% |
| Full enforce-ready | **Not yet** — Scenario A ≠ <10%; enforce fails open on scoring/config errors |

## Training data plan

### v0 seed set (used to build keyword list and initial labels)

- **Positives (~20–30)**: the 16 in-corpus papers that L5 marked as on-topic. Includes foundational papers: Avellaneda-Stoikov, Kelly criterion, prediction market microstructure, market-making optimization.
- **Negatives (~20–30)**: the 7 off-topic papers from the L5 baseline, weighted toward the 3 clearly-off-topic papers (Hastelloy-X materials science, head/neck cancer ML, e-commerce conversion modeling).

### Label accumulation path (v0 → v1)

- Each YELLOW queue accept/reject decision by the operator produces one labeled example.
- **Accept** → positive label; **Reject** → negative label.
- Labels stored at: `artifacts/research/svm_filter_labels/labels.jsonl`
  - Schema: `{"paper_id": "...", "decision": "accept|reject", "reason": "...", "timestamp": "ISO8601", "operator": "..."}`
- Label count reported by `python -m polytool research-health` (add counter to health output in v0 packet)
- v1 upgrade trigger: `research-health` reports ≥30 accept AND ≥30 reject labels

### v1 model ledger

- Path: `artifacts/research/svm_filter_models/`
- One directory per model version: `v1_YYYYMMDD/model.pkl` + `metadata.json`
  - `metadata.json` schema: `training_date`, `n_positive`, `n_negative`, `precision_heldout`, `recall_heldout`, `threshold`, `specter2_version`
- Nightly retraining script: `tools/scripts/retrain_svm_filter.py` (created in v1 packet)
- Retention: last 5 model versions; older versions archived under `artifacts/research/svm_filter_models/archive/`

## Reference materials for architect

Read these before implementing Prompt A:

1. **`[[11-Scientific-RAG-Pipeline-Survey]]`** — three entries directly relevant:
   - **arXiv-Sanity-Lite** (Karpathy) — TF-IDF + SPECTER + SVM pattern. v0 adopts the TF-IDF scoring pattern only (without SPECTER2 or SVM).
   - **Semantic Scholar API + S2FOS + SPECTER2** — field-of-study labels and scientific-document embeddings. v1 deliverable only.
   - **OpenReview Finder** (danmackinlay) — SPECTER2 + ChromaDB integration reference. v1 deliverable only.
2. **`[[Decision - Scientific RAG Architecture Adoption]]`** item 3 — specifies Semantic Scholar + S2FOS + SPECTER2 + SVM as the long-term design. v0 is the cold-start path to that target; do not re-litigate the v1 design now.
3. **`[[Decision - RIS Evaluation Scoring Policy]]`** — LLM gate scoring policy that this filter feeds into. The pre-fetch filter is upstream of the LLM gate; they should not duplicate work.
4. **L5 baseline report** — `docs/features/FEATURE-ris-scientific-eval-benchmark-v0.md`. Full corpus list and the 7 off-topic papers by paper ID. Use this to validate acceptance gate 1 and 2 without re-running the benchmark.

## Cross-references

- [[11-Scientific-RAG-Target-Architecture]] — parent design (build order: L0→L1→L3 parallel with L2)
- [[Decision - Scientific RAG Architecture Adoption]] — adoption decision (item 3 authorizes this layer)
- [[Work-Packet - Scientific RAG Evaluation Benchmark]] — L5 quantified the off-topic rate that activated this packet
- [[11-Scientific-RAG-Pipeline-Survey]] — arXiv-Sanity-Lite, Semantic Scholar API, S2FOS, SPECTER2, OpenReview Finder entries
- [[Decision - RIS Evaluation Scoring Policy]] — LLM gate scoring policy this filter feeds into
- `docs/dev_logs/2026-05-01_ris-prefetch-filter-packet-activation.md` — activation doc (stub → active)
- `docs/dev_logs/2026-05-02_ris-prefetch-filter-coldstart.md` — Prompt A implementation (v1 threshold; title-only estimates)
- `docs/dev_logs/2026-05-02_codex-review-ris-prefetch-filter-v0.md` — Codex initial review (FAIL; 3 blockers)
- `docs/dev_logs/2026-05-02_ris-prefetch-filter-v0-fix.md` — v1.1 calibration + acquire wiring + audit fields
- `docs/dev_logs/2026-05-02_codex-rereview-ris-prefetch-filter-v0.md` — Codex re-review (PASS WITH FIXES)
- `docs/dev_logs/2026-05-02_ris-prefetch-filter-v0-closeout.md` — close-out; enforcement readiness record
- `docs/features/FEATURE-ris-prefetch-relevance-filter-v0.md` — canonical feature doc (shipped)
