---
date: 2026-04-23
slug: ris_wp5d_baseline_save
type: feature
scope: packages/polymarket/rag/eval.py, tools/cli/rag_eval.py, tests/test_rag_eval.py
feature: RIS Phase 2A — WP5-D Baseline Save
---

# RIS WP5-D — Baseline Save

## Objective

Add an explicit operator-controlled path to freeze the current benchmark
state to `artifacts/research/baseline_metrics.json` (or any custom path).
Baseline writes must be opt-in — they do not happen on every run.

---

## Files Changed and Why

| File | Change | Reason |
|---|---|---|
| `packages/polymarket/rag/eval.py` | Added `save_baseline(report, path)` function | Core baseline-write logic; reuses `asdict(report)` + adds `frozen_at` timestamp |
| `tools/cli/rag_eval.py` | Import `save_baseline`; add `--save-baseline [PATH]` arg; call `save_baseline` when flag set | CLI surface for the operator; explicit opt-in path |
| `tests/test_rag_eval.py` | Added `BaselineSaveTests` (6 tests) + `CLIBaselineFlagTests` (4 tests) | Cover all acceptance criteria for WP5-D |

---

## Baseline-Save Contract

```
save_baseline(report: EvalReport, path: Path) -> Path
```

- Writes `asdict(report)` (the full `EvalReport` serialized) plus a top-level
  `frozen_at` ISO timestamp to `path`.
- Creates parent directories as needed (`mkdir(parents=True, exist_ok=True)`).
- Returns the `Path` written.
- Never called implicitly — only invoked when the operator passes `--save-baseline`.

### CLI flag

```
python -m polytool rag-eval \
  --suite docs/eval/ris_retrieval_benchmark.jsonl \
  [--save-baseline]                      # writes to artifacts/research/baseline_metrics.json
  [--save-baseline /custom/path.json]    # writes to the specified path
```

- `--save-baseline` not passed → `args.save_baseline` is `None` → no artifact written.
- `--save-baseline` passed with no path → writes to `artifacts/research/baseline_metrics.json` (the `const` value).
- `--save-baseline PATH` → writes to `PATH`.

---

## Baseline Artifact Schema Summary

The artifact is `asdict(EvalReport)` with one additional field:

```json
{
  "frozen_at":     "<ISO timestamp of save>",
  "timestamp":     "<ISO timestamp of eval run>",
  "suite_path":    "docs/eval/ris_retrieval_benchmark.jsonl",
  "k":             8,
  "corpus_hash":   "<SHA-256 of suite file>",
  "eval_config":   { "k": 8, "top_k_vector": 25, ... },
  "modes": {
    "vector":       { "mean_recall_at_k": ..., "mean_mrr_at_k": ..., "mean_precision_at_5": ..., ... },
    "lexical":      { ... },
    "hybrid":       { ... },
    "hybrid+rerank":{ ... }
  },
  "per_class_modes": {
    "factual":      { "vector": {...}, "lexical": {...}, ... },
    "conceptual":   { ... },
    ...
  }
}
```

Key fields for comparison runs:
- `frozen_at` — when this baseline was saved
- `corpus_hash` — validates the suite file has not changed between runs
- `modes[*].mean_recall_at_k` — primary retrieval quality signal
- `modes[*].mean_mrr_at_k` — ranking quality signal
- `modes[*].mean_precision_at_5` — Precision@5 (WP5-B)
- `per_class_modes[*][*]` — per-class breakdown for each mode

The schema is a thin wrapper: no second competing schema was introduced.
`asdict(EvalReport)` is the single source of truth; `frozen_at` is the only
addition.

---

## Commands Run and Exact Pass/Fail Counts

```
python -m pytest tests/test_rag_eval.py::BaselineSaveTests tests/test_rag_eval.py::CLIBaselineFlagTests -v --tb=short
```
**Result:** 10 passed, 0 failed

```
python -m pytest tests/test_rag_eval.py -q --tb=short
```
**Result:** 67 passed, 0 failed (57 pre-existing + 10 new WP5-D tests)

```
python -m polytool --help
```
**Result:** Exit 0. CLI loads cleanly. No import errors.

```
python -m pytest tests/ -x -q --tb=short
```
**Result:** 1 failed (pre-existing), 2364 passed, 3 deselected
- Pre-existing failure: `test_ris_claim_extraction.py::TestExtractClaimsFromDocument::test_each_claim_has_required_fields`
  — actor name mismatch from an earlier WP, unrelated to eval harness. Documented in WP5-B fix log.
- 10 more tests passing than after WP5-B (was 2354). No new failures introduced.

---

## Is WP5 Now Complete Enough for Phase 2A Closeout?

**Yes — all four WP5 sub-items are done.**

| Sub-packet | Deliverable | Status |
|---|---|---|
| WP5-A | 31-query golden set across 5 classes (factual, conceptual, cross-document, paraphrase, negative-control) | COMPLETE |
| WP5-B | Precision@5 metric; fetch-depth fix (always `max(k, 5)`) | COMPLETE |
| WP5-C | Per-class segmented reporting (per_class_modes in report + CLI table) | COMPLETE |
| WP5-D | `--save-baseline` flag; `save_baseline()` function; baseline artifact | COMPLETE (this log) |

**Phase 2A WP1–WP5 acceptance:**
- ✅ 31+ queries across 5 classes
- ✅ Per-class metrics
- ✅ Baseline artifact saved with reproducible schema
- ✅ Baseline writes are explicit and opt-in

---

## Codex Review Note

Codex review tier: **Skip** — no execution, risk, or financial-logic code changed.
Changes are entirely within offline eval tooling and its tests.
