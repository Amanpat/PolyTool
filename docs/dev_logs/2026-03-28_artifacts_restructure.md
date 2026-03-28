# 2026-03-28 Artifacts Directory Restructure

## Objective

Eliminate structural debt in artifacts/: two tape directories, non-readable silver
tape names at top level, stale one-off debug files at root, and undocumented layout.
53MB of accumulated artifacts had diverged from any documented structure.

## Changes Made

### Filesystem moves
- `artifacts/silver/{id}/` -> `artifacts/tapes/silver/{id}/`
- `artifacts/silver/manual_gap_fill_*/` -> `artifacts/tapes/silver/`
- `artifacts/silver/start_process_probe_*.txt` -> `artifacts/debug/`
- `artifacts/simtrader/tapes/*shadow*/` -> `artifacts/tapes/shadow/`
- `artifacts/simtrader/tapes/{non-shadow}/` -> `artifacts/tapes/gold/`
- `artifacts/simtrader/tapes/new_market_capture/` -> `artifacts/tapes/crypto/new_market_capture/`
- `artifacts/tapes/new_market/` -> `artifacts/tapes/crypto/new_market/`
- `artifacts/crypto_pairs/paper_runs/` -> `artifacts/tapes/crypto/paper_runs/`
- `artifacts/benchmark_closure/` -> `artifacts/benchmark/`
- `artifacts/gates/mm_sweep_gate/` -> `artifacts/gates/gate2_sweep/`
- `artifacts/gates/gate2_tape_manifest.json` -> `artifacts/gates/manifests/gate2_tape_manifest.json`
- Loose root debug files -> `artifacts/debug/`
- `artifacts/corpus_audit/` -> `artifacts/debug/corpus_audit/`

### Deleted stale artifacts
- `artifacts/architect_context_bundle/`
- `artifacts/architect_context_bundle.zip`
- `artifacts/session_packs/`
- `artifacts/simtrader/studio_sessions/`

### Python path constant updates (18 files, 1 commit: 4a0da5d)

All DEFAULT_*_DIR, DEFAULT_*_PATH constants and help/docstring text updated to
match new layout. Business logic untouched. Test files not modified (they use tmp_path).

Files changed:
- `packages/polymarket/crypto_pairs/paper_runner.py` — DEFAULT_PAPER_ARTIFACTS_DIR
- `packages/polymarket/silver_reconstructor.py` — docstring example
- `tools/cli/batch_reconstruct_silver.py` — docstring example
- `tools/cli/capture_new_market_tapes.py` — _DEFAULT_TAPES_ROOT
- `tools/cli/close_benchmark_v1.py` — print statement
- `tools/cli/crypto_pair_run.py` — help text
- `tools/cli/gate2_preflight.py` — _DEFAULT_TAPES_DIR
- `tools/cli/make_session_pack.py` — _DEFAULT_OUTPUT_DIR + docstring
- `tools/cli/prepare_gate2.py` — _DEFAULT_TAPES_BASE + docstring
- `tools/cli/reconstruct_silver.py` — help text, docstring, _default_out_dir() function
- `tools/cli/scan_gate2_candidates.py` — docstring example
- `tools/cli/simtrader.py` — 8 occurrences (print + help text + arg defaults)
- `tools/cli/summarize_gap_fill.py` — docstring examples
- `tools/cli/tape_manifest.py` — _DEFAULT_TAPES_DIR, _DEFAULT_OUT, docstring
- `tools/cli/watch_arb_candidates.py` — _DEFAULT_TAPES_BASE + docstring
- `tools/gates/capture_status.py` — help text print statement
- `tools/gates/corpus_audit.py` — DEFAULT_TAPE_ROOTS list + example commands in output
- `tools/gates/mm_sweep.py` — 3 constants: DEFAULT_MM_SWEEP_TAPES_DIR, DEFAULT_MM_SWEEP_OUT_DIR, DEFAULT_GATE2_MANIFEST_PATH

### Documentation updates
- `CLAUDE.md` — added "Artifacts directory layout" subsection under "What Is Already Built";
  updated "Expected high-value paths" to list specific artifacts subdirs

## Verification

- `python -m polytool --help`: OK (no import errors)
- `python -m pytest tests/ -x -q`: 2717 passed, 25 warnings, 0 failed
- `find artifacts/ -maxdepth 1 -type f`: empty (no loose files at root)
- `find artifacts/ -maxdepth 1 -name silver -o -name benchmark_closure -o -name session_packs`: empty

## Notes

The artifacts/ tree is fully gitignored, so the filesystem restructure produced
no git diff. Only the Python source changes are tracked in version control.
