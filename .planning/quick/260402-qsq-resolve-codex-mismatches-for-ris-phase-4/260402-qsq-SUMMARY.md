# Quick Task 260402-qsq: RIS Phase 4 Source Acquisition Truth Alignment

**Completed:** 2026-04-02
**Type:** Truth alignment — no code changes

## What Was Done

Corrected three factual errors in STATE.md's quick-task table entry for 260402-ogu (RIS Phase 4 external source acquisition). All other documentation (feature doc, dev log, CURRENT_STATE.md, SUMMARY.md) was inspected and confirmed accurate.

## Mismatches Found and Fixed

| Claim in STATE.md (incorrect) | Reality (code/feature doc) | Fix |
|---|---|---|
| `JSONL keyed by acquisition_id` | Per-source `.json` files keyed by `source_id=sha256[:16]` | Updated to `per-source JSON keyed by source_id=sha256[:16]` |
| `research-acquire CLI (acquire-fixture subcommand, --family/--source-url/--dry-run)` | `research-ingest --from-adapter` CLI path with `--source-family`/`--cache-dir` flags | Updated to `research-ingest --from-adapter CLI path (--source-family/--cache-dir flags)` |
| `canonical IDs (DOI/arXiv/SSRN/repo URL dedup)` | Canonical IDs are extracted and stored; dedup wiring is explicitly deferred in the feature doc | Changed `dedup` to `extraction` |

## Files Changed

- `.planning/STATE.md` — corrected line 141 (260402-ogu entry)

## Files Confirmed Accurate (no changes needed)

- `docs/features/FEATURE-ris-phase4-source-acquisition.md`
- `docs/dev_logs/2026-04-02_ris_phase4_source_acquisition.md`
- `.planning/quick/260402-ogu-*/260402-ogu-SUMMARY.md`
- `docs/CURRENT_STATE.md`
- `packages/research/ingestion/source_cache.py` — per-source .json with source_id
- `tools/cli/research_ingest.py` — --from-adapter, --source-family, --cache-dir flags

## Codex Verification Resolution

The Codex mismatches were documentation drift between STATE.md and the actual implementation. The implementation, feature doc, dev log, and SUMMARY were all consistent. Only STATE.md's one-line description was wrong — it captured intent from planning rather than the shipped reality.
