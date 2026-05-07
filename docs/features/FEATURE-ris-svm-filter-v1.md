---
status: default-off integrated — dry-run and hold-review ready; enforce deferred
completed: 2026-05-07
track: Research Intelligence System (L3 v1)
feature_doc_version: 1
---

# Feature: RIS L3 v1 SVM Topic Filter

**Status: Default-off integrated. Dry-run and hold-review ready.
SVM enforce explicitly deferred pending future Director approval.**

Lexical scorer remains the production default. SVM is an opt-in
scoring backend, explicitly activated via CLI flags with a model path.

---

## What Was Built

### SVM Train/Eval CLI

`research-prefetch-svm-train` — full train/eval pipeline:

- Reads labels from `artifacts/research/svm_filter_labels/labels.jsonl` (read-only)
- Embeds each labeled candidate using `sentence-transformers` (BGE-large by default)
- Embedding cache under `artifacts/research/svm_filter_models/embeddings/` — re-used on subsequent runs
- Fits a `LinearSVC` classifier with fixed `random_state=42` for determinism
- Prints precision / recall / F1 / confusion matrix / comparison to lexical v1.1 Scenario B baseline
- Exports model artifact: `svm_model_<embedding_model>_<seed>.joblib`
- Exports metadata ledger: `svm_metadata_<embedding_model>_<seed>.json`

```
python -m polytool research-prefetch-svm-train \
    --model-name BAAI/bge-large-en-v1.5 \
    --out-dir artifacts/research/svm_filter_models/expanded_156
```

### Runtime Scorer

`packages/research/relevance_filter/svm_scorer.py` — `SVMRelevanceScorer`:

- Loaded from a `.joblib` artifact path supplied by the caller
- Embeds the incoming candidate text using the same embedding model
- Returns `(decision, score)` compatible with the existing `RelevanceScorer` interface
- Graceful failure: if `sentence-transformers` or `scikit-learn` are missing, raises an
  `ImportError` with a clear install hint — does not silently fall through

### Default-Off Integration

Both acquisition CLIs wire SVM as an opt-in backend behind explicit flags.

**`research-acquire`:**

```
--prefetch-filter-scorer {lexical,svm}   default: lexical
--prefetch-svm-model PATH                required when scorer=svm and mode is not off
```

**`research-prefetch-discover`:**

```
--filter-scorer {lexical,svm}            default: lexical
--svm-model PATH                         required when scorer=svm
--svm-metadata PATH                      optional; inferred from model path when omitted
```

### Label Corpus

156 labeled examples in `artifacts/research/svm_filter_labels/labels.jsonl`:

- 74 allow
- 82 reject
- 3 pending (unlabeled; do not affect training)
- SHA256: `56CEBCC2210BA7FF1A47BA1CB6A64DE649472833D23FB9D3EB4E38BEC387767E`

Labels accumulated via:
- `research-acquire --prefetch-filter-mode hold-review` (live acquisition with hold-review queuing)
- `research-prefetch-discover` (arXiv metadata-only discovery path; no PDF/Marker/index)
- `research-prefetch-review label` (manual labeling of queued REVIEW candidates)

### Expanded Artifacts

Two train runs are preserved:

| Artifact dir | label_count | train | test | notes |
|---|---|---|---|---|
| `artifacts/research/svm_filter_models/` | 61 | 45 | 16 | first real run; untouched |
| `artifacts/research/svm_filter_models/expanded_156/` | 156 | 117 | 39 | production L3 v1 artifact |

Production artifact files (expanded_156):

- `svm_model_BAAI_bge-large-en-v1.5_42.joblib` (33,997 bytes)
- `svm_metadata_BAAI_bge-large-en-v1.5_42.json` (1,182 bytes)

---

## Evidence

### Expanded 156-Label Run (2026-05-06) — production metrics

| Metric | Value |
|---|---|
| label_count | 156 |
| allow_count | 74 |
| reject_count | 82 |
| train_size | 117 |
| test_size | 39 |
| seed | 42 |
| embedding_model | BAAI/bge-large-en-v1.5 |
| model_type | LinearSVC |
| accuracy | 1.000 |
| precision (allow/reject/macro) | 1.000 / 1.000 / 1.000 |
| recall (allow/reject/macro) | 1.000 / 1.000 / 1.000 |
| F1 (allow/reject/macro) | 1.000 / 1.000 / 1.000 |
| confusion_matrix | [[19, 0], [0, 20]] |
| lexical_baseline_note | Lexical v1.1 Scenario B: 5.88% off-topic rate |

### Comparison to Prior 61-Label Run

| Metric | 61-label run | 156-label run | Change |
|---|---|---|---|
| label_count | 61 | 156 | +95 |
| train_size | 45 | 117 | +72 |
| test_size | 16 | 39 | +23 |
| accuracy | 1.000 | 1.000 | no degradation |
| macro F1 | 1.000 | 1.000 | no degradation |
| confusion_matrix | [[8,0],[0,8]] | [[19,0],[0,20]] | scaled, still perfect |

### Enforce Guard Verification

```
python -m polytool research-acquire \
    --source-family academic \
    --url https://example.com \
    --prefetch-filter-scorer svm \
    --prefetch-filter-mode enforce \
    --prefetch-svm-model artifacts/research/svm_filter_models/expanded_156/svm_model_BAAI_bge-large-en-v1.5_42.joblib

# Exit code: 1
# Output: Error: SVM enforce is blocked until >=150 labels and Director approval.
#         Use --prefetch-filter-mode dry-run or hold-review for evidence collection.
```

### Test Coverage

123 targeted SVM tests pass:

- `tests/test_ris_prefetch_svm_train.py`
- `tests/test_ris_prefetch_svm_train_cli.py`
- `tests/test_ris_prefetch_svm_scorer.py`

All tests are offline (no model weight downloads in CI).

---

## Director Decision (2026-05-07)

- **Approved:** `BAAI/bge-large-en-v1.5` as the L3 v1 SVM production model for default-off use.
- **Enforce deferred:** SVM enforce remains blocked. Requires explicit future Director approval.
- **Closeout scope:** Feature 3 closed as default-off integrated / dry-run + hold-review ready.

---

## How to Use Safely

### Dry-run (safe — no filtering effect)

Score and log, always ingest. Use this to observe SVM decisions without altering pipeline
behavior.

```
python -m polytool research-acquire \
    --url https://arxiv.org/abs/2401.12345 \
    --source-family academic \
    --prefetch-filter-mode dry-run \
    --prefetch-filter-scorer svm \
    --prefetch-svm-model artifacts/research/svm_filter_models/expanded_156/svm_model_BAAI_bge-large-en-v1.5_42.joblib
```

### Hold-review (safe — queues REVIEW; never blocks ingest)

ALLOW candidates ingest normally. REVIEW candidates go to queue without ingesting.
REJECT candidates are skipped. No paper is silently lost — reviewable items queue first.

```
python -m polytool research-acquire \
    --url https://arxiv.org/abs/2401.12345 \
    --source-family academic \
    --prefetch-filter-mode hold-review \
    --prefetch-filter-scorer svm \
    --prefetch-svm-model artifacts/research/svm_filter_models/expanded_156/svm_model_BAAI_bge-large-en-v1.5_42.joblib
```

### SVM with prefetch-discover

```
python -m polytool research-prefetch-discover \
    --query "prediction market calibration" \
    --filter-scorer svm \
    --svm-model artifacts/research/svm_filter_models/expanded_156/svm_model_BAAI_bge-large-en-v1.5_42.joblib
```

### SVM enforce — BLOCKED

```
--prefetch-filter-scorer svm --prefetch-filter-mode enforce
```

Returns `rc=1` with a clear error message. This is intentional. Enforce requires future
Director approval and is not unblocked by this closeout.

### Default behavior unchanged

Omitting `--prefetch-filter-scorer` keeps the lexical v1.1 scorer active — the
production default. SVM is never activated silently.

---

## Safety Posture

1. **No silent rejection.** SVM dry-run logs decisions but never suppresses ingestion.
   Hold-review queues REVIEW items; they remain inspectable via `research-prefetch-review list`.
2. **Enforce blocked at rc=1.** The CLI refuses enforce mode with a clear error. The block
   was preserved through the Director approval sequence — no code path bypasses it.
3. **Labels read-only.** `labels.jsonl` format is unchanged by this feature; no migration.
4. **Graceful dep failure.** If `sentence-transformers` or `scikit-learn` are absent, the
   error is an `ImportError` with install guidance — the pipeline in other modes is unaffected.
5. **Lexical remains default.** No acquisition path activates SVM without an explicit
   `--prefetch-filter-scorer svm` flag and a `--prefetch-svm-model PATH` argument.

---

## Known Caveats

- **39-sample evaluation is encouraging but not conclusive.** Perfect scores on a 39-sample
  test indicate easy linear separability in the BGE-large embedding space — not necessarily
  generalization to unseen topic distributions. Expand the label corpus before enabling enforce.
- **SPECTER2 path unresolved.** `allenai/specter2` uses the old AdapterHub format; `peft`
  0.19.1 cannot load it (`peft_type` key missing). The Director chose Option C: declare
  `BAAI/bge-large-en-v1.5` as the production model. `peft` is NOT in `pyproject.toml`
  ris-svm extras and is not needed for the bge-large path.
- **Model file size identical between 61- and 156-label runs** (33,997 bytes). This is
  consistent with easy linear separability — the SVM support vector structure converges
  regardless of corpus size in this regime. It is not a bug.
- **No autonomous enforcement.** This feature does not enable autonomous rejection of
  papers from the research pipeline. All rejections require operator review or a future
  explicit Director enforce decision.

---

## Files Changed

| File | Role |
|---|---|
| `packages/research/relevance_filter/svm_scorer.py` | SVMRelevanceScorer runtime |
| `packages/research/relevance_filter/svm_training.py` | train/eval pipeline |
| `packages/research/relevance_filter/__init__.py` | exports |
| `packages/research/relevance_filter/scorer.py` | SVM scorer dispatch hook |
| `tools/cli/research_prefetch_svm_train.py` | `research-prefetch-svm-train` CLI |
| `tools/cli/research_acquire.py` | `--prefetch-filter-scorer svm` + `--prefetch-svm-model` flags |
| `tools/cli/research_prefetch_discover.py` | `--filter-scorer svm` + `--svm-model` flags |
| `polytool/__main__.py` | `research-prefetch-svm-train` registration |
| `pyproject.toml` | `ris-svm` optional extras: `scikit-learn`, `sentence-transformers`, `joblib` |
| `tests/test_ris_prefetch_svm_train.py` | 39 offline train tests |
| `tests/test_ris_prefetch_svm_train_cli.py` | 42 offline CLI tests |
| `tests/test_ris_prefetch_svm_scorer.py` | 42 offline scorer tests |
| `tests/test_ris_research_acquire_cli.py` | acquire SVM flag tests (extended) |
| `tests/test_ris_prefetch_discovery.py` | discovery SVM flag tests (extended) |

Artifacts (gitignored):

| Artifact | Description |
|---|---|
| `artifacts/research/svm_filter_models/expanded_156/svm_model_BAAI_bge-large-en-v1.5_42.joblib` | Production model |
| `artifacts/research/svm_filter_models/expanded_156/svm_metadata_BAAI_bge-large-en-v1.5_42.json` | Metadata ledger |
| `artifacts/research/svm_filter_labels/labels.jsonl` | 156-label corpus (74 allow / 82 reject) |
| `artifacts/research/svm_filter_models/embeddings/` | 156-vector embedding cache |

---

## Install

```
pip install 'polytool[ris-svm]'
# installs: scikit-learn, sentence-transformers, joblib
# peft is NOT required for the BAAI/bge-large-en-v1.5 path
```

---

## Deferred

| Item | Reason |
|---|---|
| SVM enforce mode | Blocked pending future Director approval. Label gate (>=150) is met; enforce requires explicit re-approval. |
| SPECTER2 integration | AdapterHub format mismatch; Director chose BGE-large as production model (Option C). |
| L2 PaperQA2 activation | Gated on L1 Marker production rollout (Docker IPC warm-worker v1). |
| L4 multi-source harvesters | Gated on L1 + L3. |
| Marker Docker IPC warm-worker (v1) | Deferred from Queue v0 (2026-05-05). Must be revisited before L2 production. Not canceled. |

---

## Dev Logs

Key session logs in `docs/dev_logs/`:

| Log | Date | Topic |
|---|---|---|
| `2026-05-07_l3-v1-svm-feature-closeout.md` | 2026-05-07 | Feature closeout — docs only |
| `2026-05-06_codex-verify-l3-v1-svm-director-approval-packet-fixed.md` | 2026-05-06 | Codex PASS — corrected approval packet |
| `2026-05-06_codex-verify-l3-v1-svm-expanded-156.md` | 2026-05-06 | Codex PASS — expanded 156-label train/eval verified |
| `2026-05-06_l3-v1-svm-expanded-156-train-eval.md` | 2026-05-06 | Expanded retrain/eval implementation |
| `2026-05-06_l3-v1-svm-default-off-integration.md` | 2026-05-06 | Default-off integration implementation |
| `2026-05-06_l3-v1-svm-real-artifact-smoke.md` | 2026-05-06 | Smoke test with real artifacts |
| `2026-05-06_l3-v1-svm-training-core.md` | 2026-05-06 | Core training/embedding pipeline |
| `2026-05-06_l3-v1-svm-runtime-scorer.md` | 2026-05-06 | Runtime scorer implementation |
| `2026-05-06_l3-v1-svm-train-cli.md` | 2026-05-06 | Train/eval CLI |

---

## Cross-References

- `docs/features/FEATURE-ris-prefetch-relevance-filter-v0.md` — canonical L3/L3.1/L3.2 feature doc (lexical scorer, hold-review, label store, prefetch-discover)
- `docs/features/FEATURE-ris-scientific-eval-benchmark-v0.md` — L5 baseline (Recommendation A fired this work)
- `docs/CURRENT_STATE.md` — RIS L3 v1 SVM section
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - L3 v1 SVM Topic Filter Training.md` — work packet (closed)
