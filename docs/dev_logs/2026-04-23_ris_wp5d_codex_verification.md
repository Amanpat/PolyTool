---
date: 2026-04-23
slug: ris_wp5d_codex_verification
type: verification
scope: packages/polymarket/rag/eval.py, tools/cli/rag_eval.py, tests/test_rag_eval.py, docs/dev_logs/2026-04-23_ris_wp5d_baseline_save.md
feature: RIS Phase 2A - WP5-D Codex Verification
---

# RIS WP5-D Codex Verification

## Files Inspected

- `packages/polymarket/rag/eval.py`
- `tools/cli/rag_eval.py`
- `tests/test_rag_eval.py`
- `docs/dev_logs/2026-04-23_ris_wp5d_baseline_save.md`

## Commands Run and Exact Results

`python -m polytool --help`
- Result: Exit 0. CLI loaded and printed the command list successfully.

`python -m pytest tests/test_rag_eval.py::BaselineSaveTests -q --tb=short`
- Result: 6 passed, 0 failed

`python -m pytest tests/test_rag_eval.py::CLIBaselineFlagTests -q --tb=short`
- Result: 4 passed, 0 failed

`python -` inline tempdir probe for bare `--save-baseline`
- Result: Exit 0
- Result: baseline path written to temp `artifacts/research/baseline_metrics.json`
- Result: `exists=True`
- Result: top-level keys = `['corpus_hash', 'eval_config', 'frozen_at', 'k', 'modes', 'per_class_modes', 'suite_path', 'timestamp']`

`python -` inline tempdir schema comparison between `report.json` and baseline artifact
- Result: Exit 0
- Result: `report_only=[]`
- Result: `baseline_only=['frozen_at']`
- Result: `modes_equal=True`
- Result: `per_class_modes_equal=True`
- Result: `eval_config_equal=True`

## Verification Outcome

- Baseline save is explicit, not implicit.
  Evidence: `tools/cli/rag_eval.py` sets `default=None` for `--save-baseline` and only calls `save_baseline(...)` inside `if args.save_baseline:`.
- Default artifact path is correct.
  Evidence: parser `const` is `artifacts/research/baseline_metrics.json`, and the bare-flag tempdir probe wrote exactly that relative path.
- Saved JSON is schema-consistent with current report output.
  Evidence: `write_report(...)` writes `json.dumps(asdict(report), ...)`; `save_baseline(...)` writes the same `asdict(report)` payload plus one added top-level `frozen_at` timestamp. Tempdir comparison confirmed the only top-level delta is `frozen_at`.
- No unrelated scope creep was found in the inspected WP5-D surface.
  Evidence: inspected changes are confined to the eval/reporting path plus targeted tests and the implementation dev log. I did not find changes outside the declared RAG eval surface.

## Issues

### Blocking

- None.

### Non-Blocking

- `tools/cli/rag_eval.py:210`
  If baseline persistence fails after `--save-baseline` is explicitly requested, the CLI prints a warning and continues to its normal exit path instead of failing non-zero. This does not block WP5-D acceptance because all save-path checks passed, but it weakens automation guarantees around required artifact creation.

## Recommendation

- WP5-D is verified against the requested acceptance criteria.
- WP5 can be treated as complete for Phase 2A closeout from the baseline-save perspective.
- Next work unit: Phase 2A closeout / baseline-consumption follow-on, or a small hardening follow-up to make explicit baseline-save failures return non-zero when operators request the artifact.

## Notes

- Verification was performed against a dirty worktree with unrelated repo changes already present. Scope judgment for WP5-D was therefore based on direct inspection of the landed eval/CLI/test surface rather than on a clean commit boundary.
