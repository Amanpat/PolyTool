# 2026-03-04 - RAG Index Progress + Safer File Filters

## Objective
Make `rag-index` observable and safer on Windows by adding progress logging and robust file filtering so indexing `kb/` and `artifacts/` does not stall on binary or oversized files.

## Files Touched
- `tools/cli/rag_index.py`
- `packages/polymarket/rag/index.py`
- `tests/test_rag_index_progress_filters.py`
- `tests/test_rag_collection_defaults.py`

## What Changed
- Added safer default file handling in RAG index build:
  - Text allowlist defaults: `.md`, `.txt`, `.json`, `.jsonl`, `.csv`.
  - Binary/heavy skip list includes: `.png`, `.jpg`, `.jpeg`, `.webp`, `.pdf`, `.zip`, `.7z`, `.gz`, `.db`, `.sqlite`, `.parquet`, `.pptx`, `.docx`, `.exe`.
  - Added max-size guard with default `4 * 1024 * 1024` bytes.
  - UTF-8 decode is strict; `UnicodeDecodeError` files are skipped and counted.
  - Added HF cache directory skips (`.cache`, `huggingface`, `hf_cache`, `hf_home`).
- Added index progress state + callback support in `build_index(...)`:
  - Tracks scanned files, embedded chunks, skip counters, and last path.
  - Emits periodic updates based on file/chunk intervals.
  - Emits final progress snapshot at completion.
- Extended `IndexSummary` with:
  - `scanned_files`
  - `skipped_binary`
  - `skipped_too_big`
  - `skipped_decode`
- Improved `--rebuild` behavior:
  - Attempts to clear persist directory before indexing.
  - Uses safe guardrails to avoid deleting unsafe paths.
  - On Windows lock failures, falls back to collection deletion instead of crashing.
- Added CLI flags:
  - `--max-bytes`
  - `--progress-every-files`
  - `--progress-every-chunks`
- Added CLI progress output lines:
  - `scanned_files=... embedded_chunks=... skipped_binary=... skipped_too_big=... skipped_decode=... last_path="..."`
- Added final CLI summary counters for scanned/skipped totals.

## Tests Added
- `tests/test_rag_index_progress_filters.py`
  - `test_filter_skips_binary_extension`
  - `test_filter_skips_over_max_bytes`
  - `test_decode_failure_increments_skipped_decode`
  - `test_progress_callback_invoked`
  - `test_rebuild_clears_persist_directory`
- `tests/test_rag_collection_defaults.py`
  - Added assertion for `rag_index` parser default `max_bytes`.

## Test Commands Run
- `pytest -q tests/test_rag_index_progress_filters.py tests/test_rag_collection_defaults.py`
  - Result: `7 passed`
- `pytest -q tests/test_rag.py -k "rebuild_same_count or reconcile_noop_when_nothing_stale"`
  - Result: `2 passed`
- `pytest -q`
  - Result: `970 passed`
