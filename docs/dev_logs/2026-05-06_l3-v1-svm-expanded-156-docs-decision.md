# L3 v1 SVM — Expanded 156-Label Docs Decision

**Date:** 2026-05-06  
**Track:** Research Intelligence System — L3 v1 SVM Topic Filter  
**Scope:** Docs-only update. Records the expanded 156-label retrain/eval verdict across CURRENT_DEVELOPMENT, Current-Focus, and Work Packet. No code, tests, labels, artifacts, or feature docs touched.

---

## Files Changed

| File | Change |
|---|---|
| `docs/CURRENT_DEVELOPMENT.md` | Feature 3 status → "expanded 156-label retrain/eval complete"; current-step updated with full metrics + verdict; blockers updated (label-count blocker removed, Director approval + model selection remain); Architect note updated to reflect label gate met and Director approval as sole enforcement blocker |
| `docs/obsidian-vault/Claude Desktop/Current-Focus.md` | Frontmatter `updated` date; Priority #1 blurb; L3 table row; new session context entry prepended; footer last-updated line |
| `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - L3 v1 SVM Topic Filter Training.md` | Status header; trigger status expanded counts; Current Step rewritten as Step 3 with metrics table + caveats (Step 2 preserved as subsection); open-environment-issues "Next:" line; Blockers section (label-count blocker struck through as resolved, Director approval reframed to "gate now met"); cross-reference label store count |

---

## Metrics Summary (from Prompt A dev log)

| Metric | 61-label run | 156-label run |
|---|---|---|
| label_count | 61 | 156 |
| allow_count | 30 | 74 |
| reject_count | 31 | 82 |
| train_size | 45 | 117 |
| test_size | 16 | **39** |
| Accuracy | 1.000 | 1.000 |
| Macro F1 | 1.000 | 1.000 |
| Confusion matrix | [[8,0],[0,8]] | [[19,0],[0,20]] |
| Embedding model | BAAI/bge-large-en-v1.5 | BAAI/bge-large-en-v1.5 |
| Targeted tests | 240 pass | **123 pass** (SVM-specific suite) |
| Labels SHA | 3940d2ff… | **56cebcc2… (unchanged after training)** |

Artifacts: `artifacts/research/svm_filter_models/expanded_156/svm_model_BAAI_bge-large-en-v1.5_42.joblib` + `svm_metadata_…42.json`. Prior 61-label artifacts in parent dir untouched.

---

## Decision: PROCEED to Director Approval Review

**Rationale:**
- Label gate (>=150) is met: 156 >= 150 ✓
- Expanded retrain/eval complete with no degradation: test set 2.5× larger, same perfect metrics ✓
- All 123 targeted SVM tests pass ✓
- Labels SHA unchanged before/after training ✓
- No code or artifacts modified in this docs session ✓

**Enforce remains hard-blocked at rc=1.** This verdict does not activate enforcement. It advances the feature to the Director approval stage only.

---

## Remaining Blockers

1. **Director approval** — label gate met; enforcement cannot proceed without explicit Director sign-off. Decision items the Director must address:
   - Model selection: declare `BAAI/bge-large-en-v1.5` as production model, or pursue `allenai/specter2_base` / `adapters` library path?
   - Enforce scope: score-only dry-run as first step, or direct to full enforce?

2. **Feature closeout docs** (after Director approval):
   - `docs/features/FEATURE-ris-svm-filter-v1.md` not yet created
   - `docs/CURRENT_STATE.md` RIS L3 v1 section not yet updated
   - Closeout dev log (this is the docs-decision log, not the closeout log)

---

## What Was Not Changed

- No implementation code
- No tests
- `artifacts/research/svm_filter_labels/labels.jsonl` — untouched
- `artifacts/research/svm_filter_models/` parent-dir artifacts — untouched
- `docs/features/` — no feature doc created (requires Director approval first)
- `docs/INDEX.md` — not touched
- L2/L4/Marker IPC code — not touched
- Feature 3 not moved to Recently Completed

---

## Next Recommended Prompt

**Director decision prompt** — present the Director with:
1. Expanded retrain/eval metrics summary (this dev log + Prompt A dev log)
2. Two decisions needed: (a) model selection, (b) enforce scope
3. If Director approves: run feature closeout prompt (create `FEATURE-ris-svm-filter-v1.md`, update `CURRENT_STATE.md`, write closeout dev log, move Feature 3 to Recently Completed)

Do NOT run a closeout prompt without explicit Director approval recorded in `docs/CURRENT_DEVELOPMENT.md`.

---

## Codex Review Summary

Tier: Skip — docs-only session; no implementation code, tests, or live-trading paths changed.  
Issues found: none.  
Issues addressed: n/a.
