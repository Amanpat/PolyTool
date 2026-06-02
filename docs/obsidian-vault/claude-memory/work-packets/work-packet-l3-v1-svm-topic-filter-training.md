---
title: "Work Packet — L3 v1 SVM Topic Filter Readiness + Training"
type: work_packet
status: active
source_zone: claude_memory
last_updated: 2026-05-23
lifecycle: reviewed
tags: [work-packet, ris, filtering, svm, closed]
target_agent: claude-code
acceptance_criteria:
  - See body for full criteria
---

# Work Packet — L3 v1 SVM Topic Filter Readiness + Training

**Status: CLOSED 2026-05-07 — default-off integrated; dry-run + hold-review ready; enforce deferred pending future Director approval.**

Director decision (2026-05-07): `BAAI/bge-large-en-v1.5` approved as production model for default-off use. SVM enforce remains hard-blocked at rc=1. Feature 3 moved to Recently Completed. Feature doc: `docs/features/FEATURE-ris-svm-filter-v1.md`.

---

## Goal

Train and integrate an L3 v1 SVM-based topic filter that replaces (or supplements)
the lexical `RelevanceScorer` in the prefetch pipeline. The trained model generalizes
beyond keyword overlap using learned embeddings.

---

## Trigger

SVM training is triggered when the label store reaches **≥30 allow AND ≥30 reject**
labels in `artifacts/research/svm_filter_labels/labels.jsonl`.

**Status: MET** — 30 allow / 31 reject as of 2026-05-05. Expanded to **74 allow / 82 reject (156 total)** as of 2026-05-06 after Batch A/B label application. Label gate (>=150) fully satisfied.

---

## Current Step

**CLOSED 2026-05-07 — completion protocol complete.**

Director decision recorded. Feature doc created. INDEX, CURRENT_STATE.md, CURRENT_DEVELOPMENT.md, Current-Focus, and Work Packet all updated. Feature 3 moved to Recently Completed. Enforce remains deferred. Marker IPC warm-worker next.

### Step 4 — Feature Closeout (2026-05-07)

**Step 3 — Expanded 156-label retrain/eval complete (2026-05-06). Director approval review complete.**

Corpus: 156 labels (74 allow / 82 reject, 3 pending). Label gate (>=150) MET.
Train=117, test=39 (stratified, random_state=42). Metrics: accuracy=1.000, macro-F1=1.000,
confusion_matrix=[[19,0],[0,20]]. No degradation vs prior 61-label run; test set nearly 2.5×
larger (16→39). Artifacts in `artifacts/research/svm_filter_models/expanded_156/`; prior
61-label artifacts untouched. Shared embedding cache grew 61→156 vectors (95 new, 61 reused).
123 targeted SVM tests pass. Labels SHA unchanged. Enforce still hard-blocked at rc=1.

Next: Director approval for enforce consideration + model selection decision (bge-large-en-v1.5
vs SPECTER2 path). Do not create feature closeout doc until Director approves.

Dev log: `docs/dev_logs/2026-05-06_l3-v1-svm-expanded-156-train-eval.md`

### Step 3 — Expanded retrain/eval metrics (2026-05-06)

| Metric | 61-label run | 156-label run | Change |
|---|---|---|---|
| label_count | 61 | 156 | +95 |
| allow_count | 30 | 74 | +44 |
| reject_count | 31 | 82 | +51 |
| train_size | 45 | 117 | +72 |
| test_size | 16 | 39 | +23 |
| Accuracy | 1.000 | 1.000 | same |
| Macro F1 | 1.000 | 1.000 | same |
| Confusion matrix | [[8,0],[0,8]] | [[19,0],[0,20]] | scaled, perfect |
| Embedding model | BAAI/bge-large-en-v1.5 | BAAI/bge-large-en-v1.5 | same |

**Caveats:** 39-sample perfect scores are better evidence than 16-sample but still
statistically marginal — not conclusive. Model file size identical between runs (33,997
bytes); consistent with easy linear separability in bge-large embedding space, not a bug.

### Step 2 — Default-off integration complete (2026-05-06). Smoke PASS — enforce-blocked.

SVM is wired behind `--prefetch-filter-scorer svm` on both `research-acquire` and
`research-prefetch-discover`. Enforce mode is hard-blocked at rc=1 with message:
"SVM enforce is blocked until >=150 labels and Director approval."

### Smoke test results (2026-05-06)

| Check | Result |
|---|---|
| SVM flags visible on both CLIs | PASS |
| Dry-run against real artifact (research-acquire) | PASS — `decision=allow score=0.7712` |
| Dry-run against real artifact (research-prefetch-discover) | PASS — 5 papers, all audit fields present |
| Audit fields: `scorer`, `svm_model_name`, `svm_random_state`, `svm_lexical_baseline_note` | PASS — all 5 records |
| Enforce blocked at rc=1 | PASS — clear message, no fetch, no model load |
| Label integrity (SHA256 before = after) | PASS — labels unchanged |
| 136 targeted tests | PASS (42 acquire + 52 discovery + 42 svm-scorer) |
| Live hold-review real-artifact smoke | NOT COMPLETED — arXiv HTTP 429 after prior API calls; hold-review queue path covered by 52 passing discovery tests |

Dev logs: `docs/dev_logs/2026-05-06_l3-v1-svm-real-artifact-smoke.md`,
`docs/dev_logs/2026-05-06_l3-v1-svm-default-off-integration.md`

### Step 1 — Evidence pass results (2026-05-06, for reference)

| Metric | Value |
|---|---|
| Accuracy | 1.000 |
| Precision macro | 1.000 |
| Recall macro | 1.000 |
| F1 macro | 1.000 |
| Confusion matrix | [[8,0],[0,8]] — perfect on 16-sample test |
| Train / test split | 45 / 16 (stratified, random_state=42) |
| Embedding model | BAAI/bge-large-en-v1.5 (SPECTER2 blocked — see below) |
| Lexical baseline | Scenario B 5.88% off-topic |

Caveat: 16-sample test set is not statistically conclusive. Expand label corpus to 150+
before enabling enforce mode.

### Open environment issues (carry-forward, not new blockers)

1. **SPECTER2 AdapterHub/PEFT schema mismatch** — `allenai/specter2` cache uses old
   AdapterHub format; `peft` 0.19.1 cannot load it (`peft_type` key missing). Integration
   used `BAAI/bge-large-en-v1.5`. Operator must decide: (a) `pip install adapters`, (b)
   download `allenai/specter2_base` (~440 MB, no adapters), or (c) declare `BAAI/bge-large-en-v1.5`
   as the production model.
2. **`peft` NOT in `pyproject.toml` ris-svm extras** — `peft` is NOT needed for the current validated BAAI/bge-large-en-v1.5 path (`ris-svm` extras remain: `scikit-learn`, `sentence-transformers`, `joblib`). `peft` is only relevant if the SPECTER2 AdapterHub path is chosen.

**Label gate MET (156 >= 150). Next: Director approval + model selection decision, then feature closeout docs.**
No enforcement until Director explicitly approves.

---

## Scope

### 1. Embeddings

SPECTER2 (paper-optimized sentence embeddings) and/or S2FOS (field-of-study classifier
features) from Semantic Scholar. Embedding model is loaded via `sentence-transformers`
or equivalent offline-capable library.

- **Cacheable path required.** If a cached embedding already exists for a `candidate_id`,
  do not re-embed. Cache stored under `artifacts/research/svm_filter_models/embeddings/`.
- **Test isolation.** Tiny-fixture tests inject pre-computed mock vectors and do NOT
  download model weights. The full test suite must pass without network access to model
  hosting infrastructure.
- Embedding model weights are fetched once by the operator and then volume-mounted /
  cached locally. No automatic download on every CLI invocation.

### 2. Classifier

Scikit-learn SVM (`sklearn.svm.SVC` or `LinearSVC`) trained on labeled examples
from `labels.jsonl`.

- Train/eval split or cross-validation uses a **fixed seed** (e.g., `random_state=42`)
  for determinism. Two runs on the same label set produce identical metrics.
- `labels.jsonl` is **read-only** — the format must not change. No migration.
- Label store is small (30+31 = 61 examples). Cross-validation (e.g., 5-fold) is
  appropriate given the small corpus.

### 3. Integration

Wire the trained model into `RelevanceScorer` or create a parallel `SVMRelevanceScorer`
that the prefetch pipeline can dispatch to.

- Integration is **default-off**: SVM scoring is not active unless an explicit flag or
  config field enables it (e.g., `--prefetch-filter-mode svm` or a config key).
- All existing filter modes (`off`, `dry-run`, `enforce`, `hold-review`) are unchanged
  by this feature unless the operator explicitly selects SVM mode.
- **No production enforcement** until evaluation gates pass (see Acceptance Gates).

### 4. Evaluation

Compare to the lexical v1.1 baseline (Scenario B 5.88% off-topic rate on the 23-paper
L5 corpus). Evaluation report must include all of:

- Precision (per class: allow / reject)
- Recall (per class)
- F1 (per class and macro-averaged)
- Confusion matrix
- Comparison to lexical v1.1 baseline (Scenario B 5.88%, QA REJECT = 0)

### 5. CLI Surface

A train/eval command (e.g., `research-prefetch-svm-train` or equivalent) that:

- Reads labels from `artifacts/research/svm_filter_labels/labels.jsonl`
- Embeds each labeled candidate (or loads from cache)
- Fits the SVM classifier with the fixed seed
- Prints evaluation metrics (precision / recall / F1 / confusion matrix / baseline comparison)
- Exports the trained model artifact to `artifacts/research/svm_filter_models/` with
  an embedded metadata ledger (see Definition of Done)

---

## Definition of Done

- [x] Train/eval CLI exists and runs end-to-end on real labels without errors
- [x] Uses existing `labels.jsonl` without format changes
- [x] Embedding path is cacheable; cached embeddings are re-used on subsequent runs
- [x] Evaluation report: precision, recall, F1, confusion matrix, comparison to lexical v1.1 baseline
- [x] Exported model artifact includes metadata/ledger:
      `label_count`, `train_size`, `eval_size`, `seed`, `timestamp`, `sklearn_version`,
      `model_type`, `model_params`, `embedding_model`
- [x] Integration is default-off: SVM not active without explicit flag/config
- [x] No production enforcement path enabled until evaluation gates pass (enforce hard-blocked at rc=1)
- [x] Graceful failure if `sentence-transformers` or `scikit-learn` not installed
- [x] `docs/features/FEATURE-ris-svm-filter-v1.md` created
- [x] `docs/CURRENT_STATE.md` RIS L3 v1 section updated
- [x] Dev log created at closeout (`docs/dev_logs/2026-05-07_l3-v1-svm-feature-closeout.md`)

---

## Acceptance Gates

1. **Graceful degradation.** If `sentence-transformers`, `scikit-learn`, or other
   SVM/embedding deps are unavailable, the train/eval CLI exits with a clear error
   message (not a raw Python stack trace). The prefetch pipeline in all other modes
   continues to function normally.

2. **Determinism.** Train/eval split or cross-validation uses `random_state=42`
   (or operator-chosen fixed seed, documented in the model ledger). Two runs on
   the same `labels.jsonl` produce identical precision, recall, and F1 values.

3. **Offline tests.** Tiny-fixture tests inject mock embedding vectors and do NOT
   require downloading model weights. Tests pass with no outbound network access.
   CI must not rely on downloading SPECTER2 or S2FOS model weights.

4. **Regression.** All existing L3/L3.1/L3.2 test files pass with 0 new failures:
   - `pytest tests/test_ris_relevance_filter.py` — 0 new failures
   - `pytest tests/test_ris_prefetch_discovery.py` — 0 new failures
   - Any other `tests/test_ris_*.py` files that were green before this feature

5. **Labels read-only.** `labels.jsonl` format is unchanged. No schema changes,
   no migration steps, no new required fields.

6. **Default-off enforcement.** All four existing filter modes (`off`, `dry-run`,
   `enforce`, `hold-review`) behave identically to their pre-SVM behavior unless
   the operator activates SVM mode via an explicit flag or config key. No behavior
   changes in silent upgrade paths.

---

## Non-Goals

- No production SVM enforcement before evaluation gates pass.
- No L2 (PaperQA2) activation or any code changes to the L2 layer.
- No L4 (multi-source harvesters) activation or code changes.
- No changes to `labels.jsonl` format or `ReviewQueueStore` behavior.
- No Marker IPC warm-worker implementation (deferred to a separate packet — see below).

---

## Blockers

**Default-off dry-run integration is unblocked and complete.** The blockers below apply
only to enforcement and feature closeout.

### Enforce / production blocked

- ~~**Label corpus too small**~~ — **RESOLVED 2026-05-06.** Corpus now 156 labels (74
  allow / 82 reject). Label gate (>=150) fully met. Expanded retrain/eval complete with
  39-sample test set, macro-F1=1.000. See `docs/dev_logs/2026-05-06_l3-v1-svm-expanded-156-train-eval.md`.
- ~~**Director approval required**~~ — **RESOLVED 2026-05-07.** Director decision recorded: `BAAI/bge-large-en-v1.5` approved as L3 v1 SVM production model for default-off use. Enforce deferred — requires future explicit Director approval before autonomous rejection is enabled.
- ~~**Model selection unresolved**~~ — **RESOLVED 2026-05-07.** Director chose Option C: `BAAI/bge-large-en-v1.5` declared as production model. `peft` is NOT in `pyproject.toml` ris-svm extras and NOT needed for this path. SPECTER2 AdapterHub path remains blocked but is not needed for current scope.

### Closeout blocked

- ~~`docs/features/FEATURE-ris-svm-filter-v1.md` not yet created~~ — **RESOLVED 2026-05-07**
- ~~`docs/CURRENT_STATE.md` RIS L3 v1 section not yet updated~~ — **RESOLVED 2026-05-07**
- ~~Closeout dev log not yet created~~ — **RESOLVED 2026-05-07** (`docs/dev_logs/2026-05-07_l3-v1-svm-feature-closeout.md`)

---

## Deferred Dependency (unchanged — not canceled)

**Marker Docker/Linux IPC Warm-Worker (Option A)** must be revisited after this
L3/SVM stream completes or before L2 production launch (whichever comes first).
Do not let this slip past SVM closeout. See Paused/Deferred row in
`docs/CURRENT_DEVELOPMENT.md`.

---

## Cross-References

- [[claude-memory/work-packets/work-packet-prefetch-label-discovery-mode]] — L3.2 (completed; label source)
- [[legacy/Claude Desktop/08-Research/11-Scientific-RAG-Target-Architecture]] — parent design
- `docs/features/FEATURE-ris-prefetch-relevance-filter-v0.md` — canonical L3/L3.1 feature doc
- `artifacts/research/svm_filter_labels/labels.jsonl` — label store (74 allow / 82 reject / 156 total as of 2026-05-06)
- `packages/research/relevance_filter/scorer.py` — current lexical scorer to be extended/replaced
- `docs/dev_logs/2026-05-05_l3-2-prefetch-label-discovery-closeout.md` — closeout that triggered this packet
- `docs/dev_logs/2026-05-06_l3-v1-svm-packet-activation.md` — this activation session
