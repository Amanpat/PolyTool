# RIS L3 Pre-fetch Relevance Filter — Packet Activation

**Date:** 2026-05-01
**Work packet:** L3 Pre-fetch Relevance Filter — stub → active
**Author:** operator + Claude Code
**Codex review:** Skip — docs-only pass; no execution-path code changed

---

## Summary

L5 Evaluation Benchmark v0 was completed on 2026-05-02 and returned off_topic_rate=30.43%,
firing Rule A (threshold: >30%). This met activation condition (b) for the L3 Pre-fetch
Relevance Filter work packet. This session refined the stub into a full active packet,
distinguished v0 (deterministic cold-start) from v1 (SPECTER2/SVM), set concrete acceptance
gates, documented the training data path, and updated Current-Focus and CURRENT_DEVELOPMENT.

No code was changed. This is a documentation-only activation pass. Prompt A will implement v0.

---

## Activation Evidence

| Source | Signal |
|--------|--------|
| L5 baseline locked 2026-05-02 | `off_topic_rate = 30.43%` (7/23 papers) |
| Rule A threshold | `> 30%` |
| Rule A status | **Fired** — primary recommendation |
| Recommendation | **A — Pre-fetch Relevance Filtering** |
| Baseline artifact | `artifacts/research/eval_benchmark/baseline_v0.json` |
| Feature doc | `docs/features/FEATURE-ris-scientific-eval-benchmark-v0.md` |

The 7 flagged off-topic papers (from L5 corpus):
- Hastelloy-X fatigue life prediction (materials science — clearly off-topic)
- Head/neck cancer outcome prediction (medical ML — clearly off-topic)
- Indian Financial Market cross-correlation (borderline)
- E-commerce delayed conversion modeling (borderline)
- How Market Ecology Explains Market Malfunction (potential false positive)
- On a Class of Diverse Market Models (stochastic portfolio theory — borderline)
- The Inelastic Market Hypothesis (market microstructure — potential false positive)

Three were intentionally included as outliers; four crept in from early broad-topic ingestion.

---

## Status Changes

| Item | Before | After |
|------|--------|-------|
| L3 work packet frontmatter `status` | `stub` | `active` |
| L3 work packet frontmatter `tags` | `[..., stub]` | `[..., active]` |
| L3 work packet title | `Work Packet (stub) — Pre-fetch SVM Topic Filter` | `Work Packet (active) — Pre-fetch Relevance Filter` |
| Current-Focus L3 row | Stub, activation gated | Active — Prompt A next |
| Current-Focus L5 row | `status: ready` — next active packet | ✅ Shipped 2026-05-02 |
| Current-Focus Active Priorities item 1 | L5 next active packet | L5 shipped; L3 now active |
| Current-Focus `updated` frontmatter | 2026-04-29 | 2026-05-01 |
| CURRENT_DEVELOPMENT Feature 3 | Empty slot | L3 Pre-fetch Relevance Filter v0 |
| CURRENT_DEVELOPMENT Notes for Architect | L5 = next RIS packet note | L3 active, v0/v1 scope boundary, gates |

---

## v0 vs v1 Scope Boundary

This is the critical distinction for Prompt A. Do not blur these:

| | v0 (Prompt A — NOW) | v1 (future — after label accumulation) |
|---|---|---|
| ML dependencies | None — keyword list only | SPECTER2, S2FOS, sklearn SVM |
| Training data required | No | Yes — ≥30 accept + ≥30 reject labels |
| Nightly retraining | No | Yes |
| "Model" artifact | Text keyword list | `artifacts/research/svm_filter_models/v1_YYYYMMDD/` |
| Trigger | L5 Rule A fired (now) | YELLOW queue ≥30+30 labels |

v0 is intentionally cheap and deterministic. It establishes the filter integration point,
the decision log schema, and the audit/enforcement mode split — all of which v1 reuses.
v1 then replaces the scoring function (keyword → SVM) without changing the wiring.

---

## Acceptance Gates (v0 — concrete numbers)

All six gates must pass before v0 ships:

1. **Simulated off_topic_rate < 10%** on the 23-paper L5 corpus — retroactive check, not a live benchmark run
2. **Zero false negatives** on the 10 QA papers from `tests/fixtures/research_eval_benchmark/golden_qa_v0.json`
3. **Deterministic replay** — same input metadata, same output, always
4. **Decision log** — every filter call writes: `paper_id`, `decision`, `reason_code`, `score`, `threshold`, `timestamp`
5. **Default safe** — without explicit flag, filter is audit-only; ingestion proceeds as normal
6. **Enforcement explicit** — `--enforce-relevance-filter` (or `RELEVANCE_FILTER_ENFORCE=1`) required for blocking; documented in runbook before ship

---

## Training Data Path

### v0 seed set (for keyword list construction)
- **Positives (~20–30):** the 16 on-topic papers from the L5 23-paper corpus
- **Negatives (~20–30):** the 7 off-topic papers from L5, weighted toward the 3 clearly-off-topic papers

### Label accumulation (v0 → v1 transition)
- Each YELLOW queue accept/reject = one labeled example
- **Storage:** `artifacts/research/svm_filter_labels/labels.jsonl`
- **Schema:** `{"paper_id": "...", "decision": "accept|reject", "reason": "...", "timestamp": "ISO8601", "operator": "..."}`
- **Visibility:** `python -m polytool research-health` must report label counts (add to health output in v0 packet)
- **v1 trigger:** ≥30 accept AND ≥30 reject labels confirmed by `research-health`

### v1 model ledger
- **Path:** `artifacts/research/svm_filter_models/`
- **Version dir:** `v1_YYYYMMDD/` containing `model.pkl` + `metadata.json`
- **`metadata.json` schema:** `training_date`, `n_positive`, `n_negative`, `precision_heldout`, `recall_heldout`, `threshold`, `specter2_version`
- **Retention:** last 5 model versions; older archived to `artifacts/research/svm_filter_models/archive/`
- **Retraining script:** `tools/scripts/retrain_svm_filter.py` (created in v1 packet, not v0)

---

## Files Changed

| File | Change |
|------|--------|
| `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Pre-fetch SVM Topic Filter.md` | Stub → active. Added activation evidence, v0/v1 distinction, concrete acceptance gates, training data plan. |
| `docs/obsidian-vault/Claude Desktop/Current-Focus.md` | L5 marked shipped, L3 marked active in status table and Active Priorities. Session context added. Blocker "L5 corpus accumulation" marked resolved. `updated` date bumped to 2026-05-01. |
| `docs/CURRENT_DEVELOPMENT.md` | Feature 3 slot filled with L3 v0. Architect notes updated with L3 active status, v0/v1 boundary, acceptance gate summary, label/model paths. |
| `docs/dev_logs/2026-05-01_ris-prefetch-filter-packet-activation.md` | This file. |

### Files NOT changed (out of scope)

| File | Reason |
|------|--------|
| `docs/obsidian-vault/Claude Desktop/08-Research/11-Scientific-RAG-Target-Architecture.md` | Layer 3 status line says "future packet" — not in scope; update deferred to Prompt A closeout or next vault reconciliation |
| `docs/INDEX.md` | No new feature doc exists yet; INDEX entry for L3 deferred to Prompt A closeout (when `FEATURE-ris-prefetch-relevance-filter-v0.md` is created) |
| `docs/features/FEATURE-ris-prefetch-relevance-filter-v0.md` | Does not exist; created by Prompt A at implementation closeout |
| Any code | No code changes — docs-only activation pass |

---

## Current Active-Feature Slot Decision

CURRENT_DEVELOPMENT had an explicit empty Feature 3 slot with the note:
> "Reserve intentionally left open. Adding a third right now would repeat the parallel-stall pattern."

L3 v0 fills this slot because:
- Feature 1 (Track 2 Paper Soak) is blocked on operator time to launch — not actively consuming architect cycles
- Feature 2 (RIS Phase 2A) is complete-pending-operator-validation — not actively consuming architect cycles
- L3 v0 is the top-priority next RIS implementation packet per Recommendation A
- The empty slot was reserved for exactly this kind of ready-to-start feature

Active count is now 3 (Feature 1, Feature 2, Feature 3). Max is 3. No 4th can be added without pausing one.

---

## Open Questions

1. **Threshold calibration:** What keyword overlap count or TF-IDF cosine threshold should be the default for v0? The packet says "start permissive (low false-negative rate)" — Prompt A should set an initial value and document it as tunable via config, not hardcoded.

2. **Integration point:** Does the filter run inside `research-acquire` (before any external HTTP call) or after the metadata fetch but before the PDF download? The correct position is: after metadata is retrieved from Semantic Scholar/arXiv API, before the PDF download begins. This is what "pre-fetch" means — it's pre-PDF-fetch, not pre-metadata-fetch.

3. **YELLOW queue label format:** The YELLOW queue stores pending review items. The label path `artifacts/research/svm_filter_labels/labels.jsonl` needs a write path from the operator review flow. Prompt A should initialize the file with a header comment and an empty JSONL; the actual write path from review → label is a v1 task.

4. **`research-health` counter:** Adding label count to health output is a v0 deliverable in the packet. Prompt A needs to add this to the health check (even if the label file is empty at ship time, the counter should appear as `label_count: 0`).

---

## Next Implementation Handoff to Prompt A

Prompt A receives the following context:

- **Goal:** implement v0 deterministic cold-start relevance filter in `research-acquire`
- **Activation evidence:** off_topic_rate=30.43%, Rule A fired, L5 baseline at `artifacts/research/eval_benchmark/baseline_v0.json`
- **Work packet:** `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Pre-fetch SVM Topic Filter.md` (fully refined, status: active)
- **Feature doc to create on closeout:** `docs/features/FEATURE-ris-prefetch-relevance-filter-v0.md`
- **Do NOT:** introduce SPECTER2, sklearn SVM, or any ML model training in v0
- **Do NOT:** make blocking mode the default — dry-run/audit is the default
- **Acceptance gate check:** run retrospective filter against the 23-paper L5 corpus manifest and verify simulated off_topic_rate < 10%
- **Golden corpus guard:** confirm all 10 QA papers from `tests/fixtures/research_eval_benchmark/golden_qa_v0.json` pass the filter
- **Label store:** create `artifacts/research/svm_filter_labels/labels.jsonl` (empty, with schema comment)
- **Health check:** add `label_count` to `python -m polytool research-health` output
- **Completion protocol:** feature doc + INDEX.md update + CURRENT_DEVELOPMENT move to Recently Completed
