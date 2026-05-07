# L3 v1 SVM Topic Filter — Director Approval Packet

**Date:** 2026-05-06
**Track:** Research Intelligence System — L3 v1 SVM Topic Filter
**Scope:** Docs only. No code behavior changes. No feature closeout. No enforcement activation.
**Type:** Director approval packet + session dev log

---

## Purpose

This packet presents the evidence, caveats, and decision options for the L3 v1 SVM Topic Filter.
The Director must make two explicit decisions before the feature can advance beyond its current
default-off, enforce-blocked state:

1. **Model selection** — declare `BAAI/bge-large-en-v1.5` as production, or pursue SPECTER2.
2. **Enforce scope** — what (if anything) to unlock after approval.

Do not move Feature 3 to Recently Completed. Do not create `docs/features/FEATURE-ris-svm-filter-v1.md`.
Do not remove the `rc=1` enforce block. None of these happen without explicit Director approval
recorded in `docs/CURRENT_DEVELOPMENT.md`.

---

## Current State

| Item | State |
|---|---|
| Feature slot | Feature 3 (Active) — max-3 reached |
| Integration | **Default-off.** SVM available with explicit flags: `research-acquire` uses `--prefetch-filter-scorer svm`; `research-prefetch-discover` uses `--filter-scorer svm`. |
| Default scorer | Lexical v1.1 (`RelevanceScorer`) — unchanged, still default. |
| Enforce | **Hard-blocked at rc=1** with message: "SVM enforce is blocked until >=150 labels and Director approval." |
| Label gate | **MET.** 156 >= 150. |
| Director approval | **PENDING.** This packet is the request for that approval. |
| Feature closeout | Blocked — requires Director approval first. |

---

## Evidence Summary

### Label Corpus (2026-05-06)

| Field | Value |
|---|---|
| Total labeled | 156 |
| Allow | 74 |
| Reject | 82 |
| Pending (unlabeled) | 3 |
| Label gate threshold | >= 150 |
| Gate status | **MET** |
| labels.jsonl SHA256 | `56cebcc2210ba7ff1a47ba1cb6a64de649472833d23fb9d3eb4e38bec387767e` |

Labels were not modified during training. SHA verified before and after the retrain/eval run.

### Expanded 156-Label Retrain/Eval (2026-05-06)

| Metric | Value |
|---|---|
| Embedding model | BAAI/bge-large-en-v1.5 |
| Classifier | LinearSVC (scikit-learn 1.8.0) |
| Seed | 42 (fixed, deterministic) |
| Train / test split | 117 / 39 (stratified, 75/25) |
| Accuracy | 1.000 |
| Precision — allow | 1.000 |
| Precision — reject | 1.000 |
| Precision — macro | 1.000 |
| Recall — allow | 1.000 |
| Recall — reject | 1.000 |
| Recall — macro | 1.000 |
| F1 — macro | **1.000** |
| Confusion matrix | `[[19, 0], [0, 20]]` — 0 false positives, 0 false negatives |
| Targeted tests | **123 passed, 0 failed** |
| Embed cache | 156 vectors (61 reused from prior run, 95 new) |
| Model artifact size | 33,997 bytes |

### Artifact Paths

| Artifact | Path |
|---|---|
| Model (.joblib) | `artifacts/research/svm_filter_models/expanded_156/svm_model_BAAI_bge-large-en-v1.5_42.joblib` |
| Metadata JSON | `artifacts/research/svm_filter_models/expanded_156/svm_metadata_BAAI_bge-large-en-v1.5_42.json` |
| Embedding cache | `artifacts/research/svm_filter_models/embeddings/` (156 files) |
| Prior 61-label model | `artifacts/research/svm_filter_models/svm_model_BAAI_bge-large-en-v1.5_42.joblib` (untouched) |
| Labels (read-only) | `artifacts/research/svm_filter_labels/labels.jsonl` |

---

## 61-Label vs 156-Label Comparison

| Metric | 61-label run | 156-label run | Change |
|---|---:|---:|---|
| label_count | 61 | 156 | +95 |
| allow_count | 30 | 74 | +44 |
| reject_count | 31 | 82 | +51 |
| train_size | 45 | 117 | +72 |
| test_size | 16 | **39** | +23 (+143%) |
| Accuracy | 1.000 | 1.000 | same |
| Macro F1 | 1.000 | 1.000 | same |
| Confusion matrix | [[8,0],[0,8]] | [[19,0],[0,20]] | scaled up, still perfect |
| Embedding model | BAAI/bge-large-en-v1.5 | BAAI/bge-large-en-v1.5 | same |
| Model artifact size | 33,997 bytes | 33,997 bytes | same (see Caveats) |

No degradation across a 2.4× larger test set. The expanded corpus is materially better evidence
than the 61-label run.

---

## Caveats (Honest)

These caveats are not reasons to stop — they are reasons to be proportionate about confidence.

### 1. Small test set (39 samples)

39-sample perfect scores are better evidence than 16-sample, but still below statistical power
thresholds (95% CI for F1 >= 0.95 requires ~200+ test samples). The result strongly suggests
linear separability in bge-large embedding space but cannot prove generalization to unseen
categories at that confidence level.

### 2. Model size unchanged between 61-label and 156-label runs

Both model artifacts are exactly 33,997 bytes. This is not a pipeline bug — `LinearSVC`
converges to a similar boundary when the data is highly linearly separable. It does reinforce the
"easy problem / wide margin" interpretation: financial news, prediction market descriptions, and
arXiv paper titles are likely far apart in bge-large's 1024-dim space. The model does not have
to work hard to find the decision boundary.

### 3. Possible train/test topic leakage

Labels were accumulated from a single labeling session workflow targeting the same arXiv search
domain. The 75/25 stratified split does not guarantee topic-disjoint train/test sets. A paper on
"prediction markets and machine learning" in the test set may have near-duplicates in train.
This is the likeliest explanation for the 1.000 score if genuine — not a labeling error, but a
data distribution artifact.

### 4. SPECTER2 unresolved

The paper-domain-optimized embedding model (`allenai/specter2`) was not validated. The current
validated path is `BAAI/bge-large-en-v1.5`. The SPECTER2 blocker is an AdapterHub format
mismatch with `peft 0.19.1` (`peft_type` key missing in cached weights). SPECTER2 resolution
requires either `pip install adapters` library or downloading `allenai/specter2_base` (~440 MB,
no adapters). Director must decide whether to resolve SPECTER2 or declare bge-large as
production. `peft` is NOT currently in `pyproject.toml` ris-svm extras — it is only needed
for the SPECTER2 AdapterHub path.

### 5. Metadata schema note (from Codex review)

The expanded metadata JSON does not have a literal top-level `model_name` key. Model identity
is present as `embedding_model: "BAAI/bge-large-en-v1.5"` and in the artifact filename. Seed
is present as `seed: 42` and `model_params.random_state: 42`. The Work Packet DoD asks for
`embedding_model`, which is present, so this is not a blocker for Director review. A future
metadata contract that requires exact `model_name`/`random_state` aliases would need a migration.

---

## Decision 1 — Model Selection

Choose the embedding model for L3 v1 SVM production.

### Option A — Recommended: Declare BAAI/bge-large-en-v1.5 as production model

- **Evidence:** Two training runs (61-label, 156-label) both achieve 1.000 macro F1 with
  bge-large. Model loads offline, embedding cache works, no missing deps.
- **Risk:** bge-large is a general-purpose embedding model; SPECTER2 is paper-domain-optimized.
  We do not have a comparative evaluation. bge-large may be sufficient or may miss subtle
  domain distinctions at larger scale.
- **Action required if chosen:** None immediately. Update metadata schema to add `model_name`
  alias if desired. Write it into feature closeout doc.
- **Advantage:** Unblocks everything immediately. No additional downloads or library changes.

### Option B: Block enforce until SPECTER2 is resolved

- **Evidence:** SPECTER2 is the domain-optimal model per the original L3 v1 scope. The
  AdapterHub issue is solvable: `pip install adapters` or use `allenai/specter2_base`.
- **Risk:** Resolving SPECTER2 requires an additional work session: download ~440 MB weights,
  validate embedding consistency with prior bge-large labels (embeddings are model-specific;
  existing cache is bge-large only), re-run train/eval, repeat smoke test. Labels remain
  compatible — only embeddings change.
- **Action required if chosen:** Separate SPECTER2 resolution prompt before enforce can proceed.
  Feature 3 stays active; enforce remains blocked.
- **Timeline impact:** One additional work packet estimate.

### Option C: Keep default-off, close without enforce, revisit at L4 or L5 re-evaluation

- **Evidence:** L3 v1 dry-run/score-only mode adds audit fields to every acquisition run.
  This data accumulates without enforce risk. A bigger label corpus and/or a comparative
  bge-large vs SPECTER2 eval could be done later.
- **Risk:** Feature 3 never closes; SVM path is on indefinitely in a half-open state.
- **Action required if chosen:** Feature doc scoped to default-off dry-run only; enforce
  explicitly deferred in CURRENT_DEVELOPMENT.md.

---

## Decision 2 — Enforce Scope

Choose what to unlock after Director model selection decision.

### Option 1 — Recommended: Approve continued default-off, score-only evidence collection

SVM dry-run and hold-review modes are **already available** with an explicit scorer flag and
model path — no code unlock is required. The enforce block at rc=1 remains in place and
stays unchanged. This option is a Director decision to keep evidence collection running in
score-only mode: SVM scores are logged as audit fields but no papers are auto-rejected.
A separate Director prompt is required before enforce (auto-reject) mode is unblocked.

- **Benefit:** Evidence accumulates with zero false-positive risk. Operator sees SVM
  scores alongside lexical scores in audit logs. Can compare against lexical baseline
  empirically in production.
- **Risk:** Papers the SVM would have rejected continue to flow through. Hold-review queue
  may grow.
- **Prerequisite:** Model selection decision (Option A, B, or C above) must be made first.
- **What changes in code:** Nothing. Dry-run and hold-review already work with explicit flags.
  The enforce rc=1 guard stays in place. The only remaining code decision is whether to
  remove or modify the enforce block — that is a separate prompt.

### Option 2: Approve guarded enforce path now

Fully unlock enforce mode (`--prefetch-filter-mode enforce`) with explicit flags and a
labeled model path. Lexical scorer remains the default (no flags = no SVM). Operator must
explicitly activate both `--prefetch-filter-scorer svm` and `--prefetch-filter-mode enforce`.

- **Benefit:** Complete feature closure in one pass.
- **Risk:** At 39-sample evaluation, false-positive rate on unseen paper categories is
  unknown. A paper the model incorrectly rejects does not re-appear in the pipeline.
  Auto-reject risk is real even with perfect hold-out metrics.
- **Prerequisite:** Model selection decision. Strong recommendation to do a dry-run soak
  (collect SVM scores for 1–2 weeks) before switching to enforce in production sessions.

### Option 3: Do not unlock enforce — collect more evidence

Keep the enforce guard exactly as-is. Continue accumulating labels via `hold-review` mode
with the lexical scorer. Revisit after corpus reaches 250+ labels or after 5-fold
cross-validation is added.

- **Benefit:** No code behavior change needed. Zero false-positive risk.
- **Risk:** Feature 3 stays open indefinitely. Director decision deferred again.
- **What changes:** Nothing in code. Update `docs/CURRENT_DEVELOPMENT.md` to reflect
  the decision to defer enforce. Can still create feature closeout docs if Director chooses
  Option C for model selection (close as default-off only).

---

## Director Signoff Section

**Instructions for Aman (Director):** Reply with the exact phrase below, filling in the
bracketed selections. Claude Code will not proceed with any closeout or enforce-unlock
prompts until this reply is recorded in `docs/CURRENT_DEVELOPMENT.md`.

---

**Reply template:**

```
L3 v1 SVM Director Approval — 2026-05-06

Model selection: [Option A / Option B / Option C]
Enforce scope: [Option 1 / Option 2 / Option 3]

Notes: [optional — any conditions, caveats, or sequencing requirements]

Approved by: Aman
```

---

**Checkboxes for Director (for clarity before replying):**

- [ ] I have read the Evidence Summary section
- [ ] I have read the Caveats section (all 5)
- [ ] I understand that Option 1 (enforce scope) does not remove the auto-reject guard
- [ ] I understand that Option 2 (enforce scope) enables auto-reject with explicit flags
- [ ] I understand that "approved" here means approved to proceed to the next prompt;
      no code changes in this packet

---

## What Happens Next (by decision combination)

| Model | Enforce | Next prompt |
|---|---|---|
| A + 1 | No code change — dry-run/hold-review already work; write feature doc scoped to score-only (default-off) | `docs/features/FEATURE-ris-svm-filter-v1.md` + CURRENT_STATE.md update + enforce stays blocked |
| A + 2 | Remove all enforce guards for explicit-flag paths | Feature closeout with full enforce capability |
| A + 3 | No code change | Feature closeout scoped to default-off only; enforce formally deferred |
| B + 1 | SPECTER2 resolution prompt first, then write feature doc scoped to score-only (dry-run/hold-review already work) | Feature 3 stays active; two prompts needed |
| B + 2 | SPECTER2 resolution prompt first, then full enforce unlock | Feature 3 stays active; two prompts needed |
| B + 3 | No code change; SPECTER2 deferred | Feature closeout scoped to default-off only |
| C + any | No code change | Feature closeout scoped to default-off only |

---

## Session Dev Log

### Files Changed

| File | Change | Why |
|---|---|---|
| `docs/dev_logs/2026-05-06_l3-v1-svm-director-approval-packet.md` | Created (this file) | Per scope: approval packet in dev_logs since docs/decisions/ does not exist |

No other files changed. This is a docs-only session that writes the approval packet and
nothing else.

### Evidence Summarized

Expanded 156-label retrain/eval complete. BAAI/bge-large-en-v1.5 LinearSVC achieves 1.000
macro F1 on 39-sample hold-out. Test set 2.4× larger than prior 61-label run; no degradation.
123 targeted SVM tests pass. Label gate met (156 >= 150). Enforce hard-blocked at rc=1
pending Director approval. Labels SHA unchanged. No code changed in this session.

### Options Presented

- **Model selection:** Option A (declare bge-large production — recommended), Option B
  (block until SPECTER2 resolved), Option C (close without enforce).
- **Enforce scope:** Option 1 (staged unlock, score-only first — recommended), Option 2
  (approve full enforce now), Option 3 (do not unlock enforce).

### Remaining Blockers

1. Director reply with chosen options (this packet)
2. Feature closeout docs (after Director approval): `docs/features/FEATURE-ris-svm-filter-v1.md`,
   `docs/CURRENT_STATE.md` RIS L3 v1 section, closeout dev log, Feature 3 → Recently Completed
3. If Option B chosen: SPECTER2 resolution work packet before any enforce unlock

### Next Prompt After Director Decision

Include the approved decision combination in the prompt. Use exact wording:

```
Director approved L3 v1 SVM as follows:
  Model selection: [Option A/B/C]
  Enforce scope: [Option 1/2/3]
  Notes: [if any]

Proceed with: [closeout / enforce-unlock / SPECTER2-resolution] prompt.
```

The next prompt should NOT start until the Director's reply is recorded here. Claude Code
will refuse to create the feature doc or remove the enforce guard without that record.

### Codex Review Summary

Tier: Skip — docs-only session; approval packet creation. No implementation code, tests,
labels, artifacts, live-trading paths, risk manager, rate limiter, or kill-switch code changed.
Issues found: none. Issues addressed: n/a.

---

## Test Plan Verification

| Check | Expected | Status |
|---|---|---|
| Approval packet exists | `docs/dev_logs/2026-05-06_l3-v1-svm-director-approval-packet.md` created | This file |
| No code changes | No implementation files modified | PASS — docs only |
| No label changes | `labels.jsonl` untouched | PASS — not touched in this session |
| No artifact changes | Model/metadata artifacts untouched | PASS — read-only references only |
| No feature closeout | Feature 3 not moved to Recently Completed | PASS — explicitly not done |
| No enforce unlock | rc=1 guard unchanged | PASS — no code modified |
