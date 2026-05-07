# L3 v1 SVM Topic Filter — Packet Activation

**Date:** 2026-05-06
**Track:** Research Intelligence System (L3 v1)
**Status:** Complete — docs activation only; no code changed

---

## Summary

Activated the L3 v1 SVM Topic Filter Readiness + Training work packet as Feature 3.
This is a docs-only session: the stub packet was promoted to active, DoD and acceptance
gates were locked, and the three governing docs were updated. No production code was
touched. Active count is now 3 (max-3 reached).

---

## Prerequisite Verification

Active count before this session: **2** (Feature 1: Track 2 Paper Soak; Feature 2: RIS
Phase 2A). Adding Feature 3 brings the count to 3 — within the max-3 limit. No Active
feature was displaced or paused.

SVM trigger confirmation (from L3.2 closeout dev log and `research-prefetch-review counts`):

```
Prefetch review queue : 62 total queued  |  1 pending unlabeled
Labels (in queue)     : 61 labeled  |  30 allow  |  31 reject
SVM trigger (>=30 each) : threshold met - ready for L3 v1 training
```

The one pending unlabeled candidate (`1811.08949`) does not block SVM readiness.

---

## Files Changed

| File | Change |
|------|--------|
| `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - L3 v1 SVM Topic Filter Training.md` | Promoted stub → active. Added Current Step, expanded Scope with concrete sub-items (cacheable embeddings, offline tests, fixed seed, read-only labels), locked full DoD checklist, added 6 concrete Acceptance Gates, added Blockers section (none), retained Non-Goals and Deferred Dependency. |
| `docs/CURRENT_DEVELOPMENT.md` | Replaced Feature 3 comment placeholder with full Feature 3 entry (status, current step, blockers, 11-item DoD). Updated Architect Notes: split L3.2 note from SVM activation note; added new note stating Active count = 3 (max-3). |
| `docs/obsidian-vault/Claude Desktop/Current-Focus.md` | Updated frontmatter date; updated Active Priority 1 to reflect Feature 3 active; updated L3 table row; added session context entry for 2026-05-06; updated footer timestamp. |
| `docs/dev_logs/2026-05-06_l3-v1-svm-packet-activation.md` | Created (this file). |

---

## Decisions Made

### DoD items locked

| Item | Rationale |
|------|-----------|
| Cacheable embeddings under `artifacts/research/svm_filter_models/embeddings/` | SPECTER2 is ~440MB; re-embedding 61 labels on every train run is wasteful and slow. Cache-on-first-embed is the right default. |
| Fixed seed `random_state=42` | With only 61 examples, cross-validation fold assignment is sensitive to seed. Determinism is required for reproducible evaluation reports. |
| Offline-safe tests (injected mock vectors) | CI must not download model weights. Tests that require network access would break in air-gapped or rate-limited environments. |
| Default-off integration | All four existing filter modes (`off`, `dry-run`, `enforce`, `hold-review`) must be unaffected until the operator explicitly enables SVM mode. Silent behavior change would violate the DoD of the lexical v0 feature. |
| Graceful dep failure (not stack trace) | `sentence-transformers` is an optional dep. If it is absent, the error must be operator-readable, not a raw Python traceback. |
| No enforcement until evaluation gates pass | The lexical v1.1 baseline (Scenario B 5.88%) is the comparison target. SVM must demonstrably improve or at minimum not regress before it can replace the lexical scorer in any enforcement path. |

### Scope boundary held

The following were explicitly confirmed out of scope:
- No L2 (PaperQA2) changes — L2 remains a stub
- No L4 (harvesters) changes — L4 remains a stub
- No `labels.jsonl` format changes or `ReviewQueueStore` behavior changes
- No Marker IPC warm-worker code — remains in Paused/Deferred table

---

## Commands Run

No shell commands were needed for this docs-only activation. The following commands
verify the final state of docs but were not run in this session (deferred to next
implementation session):

```bash
# Verify CLI still loads cleanly
python -m polytool --help

# Verify existing L3/L3.1/L3.2 tests still pass (no code was touched)
python -m pytest tests/test_ris_relevance_filter.py tests/test_ris_prefetch_discovery.py -q --tb=short

# Verify current label counts (confirms SVM trigger is still met)
python -m polytool research-prefetch-review counts
```

Because no code was changed, no regression is expected. Test verification is scheduled
at the start of the next implementation session.

---

## Doc Diff Summary

```
git diff -- docs/CURRENT_DEVELOPMENT.md \
            "docs/obsidian-vault/Claude Desktop/Current-Focus.md" \
            "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - L3 v1 SVM Topic Filter Training.md"
```

Expected output: only the three files above are changed, plus this new dev log.
No Python source files, test files, config files, or artifact paths are modified.

---

## Open Questions for Next Prompt

1. **Embedding model choice**: SPECTER2 vs S2FOS vs both? SPECTER2 is the canonical
   paper-embedding model from Semantic Scholar; S2FOS adds field-of-study classification
   features. With only 61 labeled examples, combining them may not help and could hurt
   (curse of dimensionality). Recommend starting with SPECTER2 alone and adding S2FOS
   only if precision/recall is inadequate.

2. **SVM variant**: `LinearSVC` (faster, L2 regularization, no probability estimates)
   vs `SVC(kernel='rbf', probability=True)` (slower, calibrated probabilities useful for
   scoring). With 61 examples, RBF is tractable. Linear is safer for generalization on
   small corpora. Recommend `LinearSVC` as default, with `SVC(probability=True)` as an
   optional eval comparison.

3. **Evaluation protocol**: 5-fold stratified cross-validation on all 61 examples, or
   a fixed 80/20 train-test split? CV is more statistically robust on small corpora.
   Recommend 5-fold stratified CV as primary, with a fixed-seed holdout report as secondary.

4. **Integration path**: Create a new `SVMRelevanceScorer` class parallel to
   `RelevanceScorer`, or extend `RelevanceScorer` with an optional SVM backend?
   Parallel class keeps the lexical path clean and the SVM path independently testable.
   Recommend parallel class dispatched via a new filter mode or config key.

5. **Dep management**: `sentence-transformers` and `scikit-learn` are not currently
   in `pyproject.toml` optional deps. A new `[svm]` or `[ris-svm]` extras group should
   be created so existing installs are not broken.

---

## Deferred Items (unchanged)

**Marker Docker/Linux IPC Warm-Worker (Option A, Queue v1):** Remains deferred.
Must be revisited after the L3/SVM stream completes or before L2 production launch,
whichever comes first. See Paused/Deferred row in `docs/CURRENT_DEVELOPMENT.md`.
