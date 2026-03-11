**Date:** 2026-03-05
**Scope:** doc sync after Track A Week 1 execution primitives and Track B hypothesis registry v0

---

## Summary

Aligned the repo truth docs with the shipped CLI surfaces:

- `docs/ROADMAP.md` now marks Hypothesis Registry v0 + `experiment-init` as complete and records the Track A Week 1 execution primitives.
- `docs/CURRENT_STATE.md` now includes the post-`alpha-distill` registry/init step and the gated `simtrader live` execution shell.
- `docs/archive/MASTER_CONSTRUCTION_MANUAL_MAPPING.md` now notes that Stage-0 execution primitives exist, but remain gated and dry-run-first.
- Added feature notes for the shipped Track A and Track B work.

## Files touched

- `docs/ROADMAP.md`
- `docs/CURRENT_STATE.md`
- `docs/archive/MASTER_CONSTRUCTION_MANUAL_MAPPING.md`
- `docs/features/FEATURE-trackA-week1-execution-primitives.md`
- `docs/features/FEATURE-hypothesis-registry-v0.md`
- `docs/dev_logs/2026-03-05_docsync_post_trackA_trackB.md`

## Verification

Checked the docs against current CLI help output:

- `python -m polytool hypothesis-register --help`
- `python -m polytool hypothesis-status --help`
- `python -m polytool experiment-init --help`
- `python -m polytool simtrader live --help`

No Python code changes were made.
