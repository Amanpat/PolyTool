# Fix: SVM Acquire Fail-Closed (Codex P1)

**Date:** 2026-05-06
**Feature:** Feature 3 — RIS L3 v1 SVM Topic Filter
**Scope:** `research_acquire.py` only — no discovery, no labels, no model artifacts

---

## Codex P1 Addressed

Codex review of the default-off SVM integration found:

> SVM score-time load/dependency failures are not handled consistently at the CLI
> boundary. `research-acquire` catches all scoring failures at line 79, warns, returns
> `None`, and then proceeds as if no filter decision existed. In explicit SVM hold-review
> mode this can bypass the intended hold-review evidence path if the model, metadata, or
> optional deps are missing.

**Root cause:** `_score_candidate_for_filter` wrapped the entire dispatch (including SVM
load and score) in a single broad `except Exception` that returned `None` on any error.
`None` causes both callers (`main` and `_run_search_mode`) to skip filter logic entirely —
the equivalent of `mode=off` — allowing unfiltered acquisition to proceed silently.

---

## Files Changed

### `tools/cli/research_acquire.py`

Three targeted changes:

**1. `_score_candidate_for_filter` — split exception handling by scorer type**

Before: one `try/except Exception` around the whole dispatch; any failure returns `None`.

After:
- SVM path: **no try/except**. Exceptions from model load, missing metadata, missing
  deps (`SvmModelLoadError`, `SvmMissingDepsError`, or any other error) propagate to
  the caller unchanged. Callers are responsible for fail-closed behavior.
- Lexical path: retains the original `try/except Exception → warn + return None` behavior.
  Existing lexical tests and production behavior are unchanged.

**2. `main()` — wrap Step 3.5 filter call with fail-closed handler**

```python
try:
    filter_decision = _score_candidate_for_filter(...)
except Exception as exc:
    print(
        f"Error: SVM scoring failed — aborting to prevent unfiltered acquisition. "
        f"Cause: {exc}",
        file=sys.stderr,
    )
    return 1
```

When scorer=svm and scoring raises, rc=1 is returned immediately. The acquisition
pipeline does not continue.

**3. `_run_search_mode()` — wrap per-paper score call with fail-closed handler**

The per-paper inner `try/except` previously would catch SVM exceptions and record
the paper as "rejected with error", then continue processing the next paper. That
behavior allows other papers in the batch to proceed unfiltered after SVM fails.

Fixed by adding a nested `try/except` specifically around `_score_candidate_for_filter`
inside the per-paper loop:

```python
try:
    filter_decision = _score_candidate_for_filter(...)
except Exception as _score_exc:
    if getattr(args, "prefetch_filter_scorer", "lexical") == "svm":
        print(
            f"Error: SVM scoring failed — aborting to prevent "
            f"unfiltered acquisition. Cause: {_score_exc}",
            file=sys.stderr,
        )
        return 1  # outer finally still runs: store.close() executes
    filter_decision = None
```

When SVM scoring fails for any paper in a batch, the entire search mode aborts with
rc=1. The `finally` block still executes, closing the knowledge store cleanly.

---

## Behavior Matrix After Fix

| Mode | Scorer | Score-time error | Before | After |
|------|--------|------------------|--------|-------|
| off | svm | n/a (not called) | rc=0 | rc=0 (unchanged) |
| dry-run | lexical | warn + None | rc=0, proceed | rc=0, proceed (unchanged) |
| dry-run | svm | caught, None | rc=0, proceed **UNFILTERED** | **rc=1, abort** |
| enforce | svm | blocked pre-scoring | rc=1 | rc=1 (unchanged) |
| hold-review | svm | caught, None | rc=0, proceed **UNFILTERED** | **rc=1, abort** |
| hold-review | svm | SvmModelLoadError | caught, rc=0 | **rc=1, abort** |

---

## Tests Added — `TestSvmScorerIntegration`

Three new tests (existing 7 retained):

**`test_svm_hold_review_model_load_error_fails_closed`**
- Monkeypatches `SvmRelevanceScorer.score` to raise `SvmModelLoadError`
- Verifies rc=1 and queue file was NOT created (no unfiltered acquisition)

**`test_svm_dry_run_score_error_fails_closed`**
- Monkeypatches `SvmRelevanceScorer.score` to raise `RuntimeError`
- Verifies rc=1

**`test_svm_off_mode_never_invokes_scorer`**
- Monkeypatches `SvmRelevanceScorer.score` to raise `AssertionError` if called
- Passes `--prefetch-filter-mode off` (default) with `--prefetch-filter-scorer svm`
- Verifies rc=0 (SVM scorer never touched)

---

## Commands Run

### `python -m pytest tests/test_ris_research_acquire_cli.py -q`

```
42 passed in 0.86s
```

### `python -m pytest tests/test_ris_relevance_filter.py tests/test_ris_prefetch_svm_train.py tests/test_ris_prefetch_svm_train_cli.py tests/test_ris_prefetch_discovery.py -q`

```
186 passed in 4.59s
```

Total across all affected suites: **228 passed, 0 failed**.

---

## Remaining Risks

- **Search mode batch abort**: when SVM scoring fails mid-batch in `--search` mode,
  papers already ingested before the failure are committed. This is acceptable; the
  alternative (transactional batch rollback) is out of scope and not required by the spec.
- **Lexical failure path untouched**: if the lexical scorer raises an unhandled exception
  (not expected under normal operation), it would still return `None` and proceed as
  unfiltered. This is existing behavior and not in scope for this fix.
- **No enforce gate for SVM in search mode**: `--prefetch-filter-mode enforce` with
  `--prefetch-filter-scorer svm` is blocked before scoring by the existing validation.
  This is correct and unchanged.
- **Non-blocking Codex findings**: (1) discover queue records lack SVM audit fields,
  (2) discover help text is now updated by linter to mention SVM embeddings. Finding (1)
  is not addressed in this prompt per scope constraint. Finding (2) was resolved by linter.

---

## Codex Review Summary

Tier: Recommended. Files are RIS CLI wiring and tests; no execution/risk/kill-switch code.
Issues found: P1 resolved. No new blocking issues introduced.
