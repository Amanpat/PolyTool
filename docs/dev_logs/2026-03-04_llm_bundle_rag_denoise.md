---
date_utc: 2026-03-04
topic: llm-bundle RAG excerpt de-noising
status: complete
---

# llm-bundle RAG excerpt de-noising

## Problem

When `rag-index` is run with `--roots "kb,artifacts"` it indexes every file
under those trees, including files written by `llm-bundle` itself
(`rag_queries.json`, `bundle.md`, legacy `prompt.txt`). These are not
evidence — they are toolchain artifacts. Retrieving them as excerpts creates
a self-referential loop: the LLM receives prior run's query log as if it
were dossier evidence, polluting `selected_excerpts` and `bundle.md`.

## Fix

Added a small post-retrieval filter in `_collect_excerpts()` in
`tools/cli/llm_bundle.py`.

**Three constants added** (`_BUNDLE_ARTIFACT_PATTERNS`):

```
kb/users/*/llm_bundles/*/rag_queries.json
kb/users/*/llm_bundles/*/prompt.txt
kb/users/*/llm_bundles/*/bundle.md
```

**`_is_bundle_artifact(file_path)`** — matches a path against the patterns
using `fnmatch.fnmatch` (which treats `*` as matching across `/`).

**`_collect_excerpts` signature change** — now returns
`(excerpts, filtered_count: int)` instead of just `excerpts`. The integer
count is used by `main()` to optionally add `rag_denoise_filtered_count` to
`bundle_manifest.json` when at least one result was dropped.

## Behaviour contract

- Filter applies after retrieval, before excerpt selection.
- No minimum-threshold fallback: if all results are artifacts, `selected_excerpts`
  is `[]` and the bundle continues with dossier evidence only.
- `rag_denoise_filtered_count` is written to `bundle_manifest.json` only when
  `> 0`; absent otherwise (no noise in manifest for clean runs).

## Files changed

- `tools/cli/llm_bundle.py` — filter implementation
- `tests/test_llm_bundle.py` — unit + integration tests (30 total, all pass)
- `docs/specs/LLM_BUNDLE_CONTRACT.md` — §4 de-noising filter sub-section added

## Tests added

- `test_is_bundle_artifact_matches_only_self_referential_outputs` (hook-added)
- `test_collect_excerpts_excludes_bundle_artifacts_and_keeps_audit_paths` (hook-added)
- `TestIsBundleArtifact` (6 cases: each pattern, non-artifact paths, edge cases)
- `TestCollectExcerptsDenoising` (6 cases: pass-through, each artifact type, combined)
- `test_bundle_selected_excerpts_never_contain_bundle_artifacts` (integration)
- `test_bundle_manifest_no_denoise_field_when_nothing_filtered` (manifest cleanliness)
