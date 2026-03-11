---
date_utc: 2026-03-05T00:00:00Z
feature: llm_bundle_report_stub
---

# LLM Bundle Report Stub

## Summary

After `llm-bundle` runs it now automatically creates a blank Markdown report file at:

```
kb/users/<user_slug>/reports/<YYYY-MM-DD>/<bundle_id>_report.md
```

The operator pastes the LLM's report output into this file.

## What changed

- `tools/cli/llm_bundle.py`: added `_write_report_stub()` helper; called in `main()` after
  bundle artifacts are written; prints `Report stub: <path>` to stdout.
- `tests/test_llm_bundle.py`: added `test_report_stub_created_on_bundle_run` and
  `test_report_stub_idempotent_on_rerun`.
- `docs/specs/LLM_BUNDLE_CONTRACT.md`: §1 updated to document the new stub path and behavior.

## Template sections

1. Metadata header: user_slug, bundle_id, generated_at, paths to bundle.md + memo_filled.md
2. Reminder: "Cite evidence anchors (file_path + heading or trade_uid/token_id/condition_id)."
3. ## Executive Summary
4. ## Data Quality / Coverage Gaps
5. ## Findings
6. ## Hypotheses
7. ## Next Experiments
8. ## Go/No-Go (research-only)

## Design decisions

- **Idempotent**: uses `exist_ok=True` for mkdir; `write_text` overwrites on rerun.
- **Separate from bundle dir**: lives under `reports/` not `llm_bundles/` to avoid being
  picked up by the RAG de-noising filter or re-indexed as evidence.
- **No auto-run LLM logic**: stub is blank template only.
- **Not skipped by `--no-devlog`**: the report stub is always written regardless of devlog flag.
