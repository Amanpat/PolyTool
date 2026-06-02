---
title: L3 V1 Svm Train Eval Readiness Decision
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-06_l3-v1-svm-train-eval-readiness-decision.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# L3 v1 SVM Train/Eval — Readiness Decision

**Date:** 2026-05-06
**Track:** Research Intelligence System — L3 v1 SVM Topic Filter (Feature 3)
**Scope:** Documentation and decision only. No code touched.

---

## Purpose

Digest the evidence pass results from `docs/dev_logs/2026-05-06_l3-v1-svm-first-real-train-eval.md`
and record a formal readiness decision: PROCEED or BLOCKED.

---

## Evidence Summary (from Prompt A)

**Source artifact:** `artifacts/research/svm_filter_models/svm_metadata_BAAI_bge-large-en-v1.5_42.json`

| Field | Value |
|---|---|
| label_count | 61 (30 allow / 31 reject) |
| train_size / eval_size | 45 / 16 |
| random_state | 42 |
| embedding_model | BAAI/bge-large-en-v1.5 |
| model_type | LinearSVC |
| sklearn_version | 1.8.0 |
| timestamp | 2026-05-06T12:52:38+00:00 |

**Metrics on 16-sample test set:**

| Metric | Allow | Reject | Macro |
|---|---|---|---|
| Precision | 1.000 | 1.000 | 1.000 |
| Recall | 1.000 | 1.000 | 1.000 |
| F1 | 1.000 | 1.000 | 1.000 |
| Accuracy | — | — | 1.000 |

**Confusion matrix:** [[8, 0], [0, 8]] — no misclassifications on hold-out.

**Baseline comparison:**

| System | Metric |
|---|---|
| Lexical v1.1 Scenario B | 5.88% off-topic rate (L5 23-paper corpus) |
| SVM bge-large-en-v1.5 | 0.0% off-topic on 16-sample test |

**Test suite:** 81 SVM-specific tests pass; 99 L3/L3.1/L3.2 regression tests pass; 240 total.

**Determinism:** Two runs on same `labels.jsonl` with `random_state=42` produce identical output.

**Embedding cache:** 61 vectors written on run 1; all reused on run 2 with no re-embedding.

---

## Environment Issues Found in Prompt A

### 1. `peft` not installed / not in pyproject.toml

`allenai/specter2` requires the `peft` package for its PEFT adapter. `peft` was absent from
both the environment and `pyproject.toml`. Prompt A installed `peft==0.19.1` manually.

**Required action before integration commit:** add `peft>=0.14.0` to the `ris-svm` optional
extras group in `pyproject.toml`.

### 2. SPECTER2 AdapterHub/PEFT schema incompatibility

The cached `allenai/specter2` snapshot contains only `adapter_config.json` in the old
AdapterHub format (keys: `factorized_phm_W`, `cross_adapter`, etc.). `peft` 0.19.1 expects
a PEFT-format config with a `peft_type` key and cannot load this file.

Root cause: `allenai/specter2` was built with the `adapter-transformers` library (AdapterHub),
not the HuggingFace `peft` library. `sentence-transformers` 5.2.2 sees `adapter_config.json`
and attempts PEFT loading, which fails.

**Evidence run resolution:** `--model-name BAAI/bge-large-en-v1.5` (documented CLI flag,
no code change). `BAAI/bge-large-en-v1.5` is fully cached locally (12 files).

**Required operator decision before integration:** which embedding model to use in production.
Options:
1. `pip install adapters` — installs the AdapterHub-compatible library; allows original `allenai/specter2` to load
2. Download `allenai/specter2_base` (~440 MB) — no adapters, standard BERT loading, paper-optimized
3. Declare `BAAI/bge-large-en-v1.5` as the production model — already cached, high quality, 1024-dim

---

## Decision

**PROCEED to default-off SVM integration.**

Rationale:
- The train/eval pipeline is proven end-to-end.
- All acceptance gates except integration wiring pass (see table below).
- The two environment issues (peft dependency, SPECTER2 compat) are resolvable during the
  integration work packet and do not block the design phase.
- Metrics on the 16-sample test are encouraging. They cannot confirm production generalization
  but are sufficient justification to wire the integration path.

**Caveats that must accompany the integration:**
- Do not claim the SVM is definitively better than the lexical baseline. 16-sample test is insufficient.
- Do not enable SVM enforce mode until the label corpus is expanded to ≥150 examples and re-evaluated.
- The model selection decision (SPECTER2 vs bge-large) must be resolved before the integration
  commit lands.

### Acceptance gate status

| Gate | Status |
|---|---|
| Train/eval CLI runs end-to-end | ✅ PASS |
| labels.jsonl read-only | ✅ PASS |
| Embedding cache works and reuses | ✅ PASS |
| Metrics: precision/recall/F1/accuracy/confusion_matrix | ✅ PASS |
| Metadata JSON: all required fields | ✅ PASS |
| Lexical baseline note in output | ✅ PASS |
| Determinism (random_state=42) | ✅ PASS |
| Graceful dep failure (CLI exits 1 with clear message) | ✅ PASS |
| No acquisition/discovery wiring | ✅ PASS |
| Existing L3/L3.1/L3.2 tests green | ✅ PASS |
| Default-off (no live pipeline enforcement) | ✅ PASS |
| SPECTER2 loads correctly | ❌ BLOCKED — AdapterHub/PEFT mismatch (decision pending) |
| `peft` in pyproject.toml | ❌ MISSING — must add to ris-svm extras |
| Label corpus ≥150 for reliable enforcement metrics | ❌ NOT YET — 61 labels currently |

---

## Files Changed

| File | Change |
|---|---|
| `docs/CURRENT_DEVELOPMENT.md` | Feature 3: status, current step, blockers updated; DoD items ticked (6 of 11 complete); Notes for Architect entry updated |
| `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - L3 v1 SVM Topic Filter Training.md` | Status line updated; Current Step replaced with evidence pass results table, env issues, and next step |
| `docs/obsidian-vault/Claude Desktop/Current-Focus.md` | Frontmatter updated; Active Priorities item 1 updated; L3 RAG status table row updated; two new Recent Session Context entries prepended |

No code, tests, labels, artifacts, or model files were modified.

---

## Next Recommended Prompt

**Default-off SVM integration.** Wire the trained model artifact behind `--prefetch-filter-mode svm`.

The integration prompt must:
1. Resolve model selection (operator decision above) and document in `pyproject.toml` + code
2. Add `peft` to `pyproject.toml` ris-svm extras
3. Create `SVMRelevanceScorer` (or extend `RelevanceScorer`) that loads the `.joblib` artifact
4. Gate the scorer behind `--prefetch-filter-mode svm` — all other modes unchanged
5. Write offline tests (mock scorer, no model weights)
6. No enforcement path until label corpus ≥150 and re-evaluated

The integration does NOT need to resolve the corpus expansion question — that is a separate
label accumulation step that can run in parallel.

---

## Open Questions

1. **Model selection** — SPECTER2 options vs bge-large-en-v1.5: which does operator prefer?
   This controls whether we need `pip install adapters`, a ~440MB download, or nothing additional.
2. **Corpus expansion trigger** — at what label count (150? 200? 300?) should we re-evaluate
   and consider enabling enforce mode? Should this be gated by a new acceptance criterion in
   the DoD, or left as an operator judgment call?
3. **Cross-validation vs train/test split** — 5-fold CV on 61 examples would give a more
   honest estimate than a single 25% hold-out. Should the integration packet switch to CV
   by default, or keep the current split for simplicity and add CV as `--cv` flag?
