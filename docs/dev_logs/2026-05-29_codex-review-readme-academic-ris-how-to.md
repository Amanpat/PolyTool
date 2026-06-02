# Dev Log: Codex Review - README Academic RIS How-To

**Date:** 2026-05-29
**Scope:** Review-only except this dev log. No implementation code, runtime artifacts, Batch C/D, benchmark baselines, or README edits were changed.
**Verdict:** BLOCK

---

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `README.md`
- `docs/features/FEATURE-ris-academic-demo-ready-v1.md`
- `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`
- `docs/CURRENT_STATE.md`
- `docs/dev_logs/2026-05-29_readme-academic-ris-how-to.md`

## Commands and Link Checks Run

- `git status --short`
  - Exit 0.
  - Output showed a pre-existing dirty tree, including `M README.md`, `M AGENTS.md`, `M docs/CURRENT_STATE.md`, `M docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`, implementation/test changes, many vault changes, and untracked dev logs. Treated as review input; no existing changes reverted.
- `git log --oneline -5`
  - Exit 0.
  - Latest commits:
    - `c249ff5 docs(ris): operator-path simplicity test - 9 runbook corrections, readiness verdict`
    - `b921857 fix(ris): L2.1 one-paper acceptance repair - Chroma embed, span strip, NTFS fallback`
    - `7fc6bf2 fix(ris): L2.1 Deliverable B - offline-safe semantic fallback, resolves Codex BLOCK`
    - `15ef471 docs(ris): repo hygiene before L2.1 Deliverable A - closeout log`
    - `3348e79 feat(ris): L2.1 Deliverable C - display-only snippet sanitation`
- `python -m polytool --help`
  - Exit 0.
  - Output includes `research-marker-queue` and `research-query`.
- `git diff -- README.md`
  - Exit 0.
  - Output shows one added section only: `### Academic RIS: research paper ingestion and querying`, inserted after RIS pre-build precheck and before Crypto pair bot.
- `rg -n "Academic RIS|RIS academic|research-marker-queue|research-query|demo-ready|production-ready|Batch C|Batch D|29-paper|29 paper|perfect|unrelated" README.md`
  - Exit 0.
  - Hits are confined to the new Academic RIS section for the relevant phrases.
- `Test-Path docs\features\FEATURE-ris-academic-demo-ready-v1.md`
  - Output: `True`
- `Test-Path docs\runbooks\RIS_MARKER_QUEUE_RUNBOOK.md`
  - Output: `True`
- `Test-Path docs\dev_logs\2026-05-29_readme-academic-ris-how-to.md`
  - Output: `True`
- `python -m polytool research-marker-queue --help`
  - Exit 0.
  - Subcommands include `enqueue`, `warm-process`, `index-done`, `prefetch`, `status-report`, `jit-cache-check`, and `check-chroma-links`.
- `python -m polytool research-query --help`
  - Exit 0.
  - Output includes required `--question QUESTION`.
- `python -m polytool research-marker-queue index-done --help`
  - Exit 0.
  - Output includes `--force`, `--reindex-chroma`, `--chroma-path PATH`, and `--json`.
- `python -m polytool research-marker-queue check-chroma-links --help`
  - Exit 0.
  - Output includes `--json`.
- `python -m polytool research-marker-queue warm-process --help`
  - Exit 0.
  - Output includes `--max-items N`, `--marker-timeout SECONDS`, and `--auto-timeout`.
- `python -m polytool research-marker-queue prefetch --help`
  - Exit 0.
  - Output includes `--max-items N`, `--delay-seconds SECONDS`, and `--json`.
- `rg -n "full 29-paper validation|29-paper validation|29 paper validation|full .*29|production-ready|production ready|perfect unrelated|perfect.*rejection|perfect rejection|no false positive|all 29|29/29|developer/operator demo-ready|NOT production-ready|Batch C/D deferred" README.md`
  - Exit 0.
  - Only acceptable readiness/caveat hits were found: developer/operator demo-ready v1, NOT production-ready, Batch C/D deferred.

No pipeline validation, Chroma query, parse, prefetch, Batch C/D, or benchmark command was run.

## Accuracy Verdict

README diff scope is acceptable: the README change is limited to the Academic RIS how-to section.

Command names and linked command surfaces exist:

- `prefetch`: present in `research-marker-queue --help`.
- `status-report`: present in `research-marker-queue --help`.
- `warm-process`: present in `research-marker-queue --help` and runbook.
- `index-done --reindex-chroma`: present in CLI help and runbook.
- `check-chroma-links --json`: present in CLI help.
- `research-query --question`: present in CLI help.

Blocking accuracy issue:

- The README happy path runs container-side `index-done` first, then tells the operator to run host-side `index-done --reindex-chroma` without `--force`. Source code and CLI help confirm `index-done` skips candidates already present in `indexed.jsonl` unless `--force` is used. `docs/features/FEATURE-ris-academic-demo-ready-v1.md` and `docs/CURRENT_STATE.md` both document the Windows-host Chroma step as `index-done --reindex-chroma --force`. As written, the README's host Chroma step can no-op after the prior Docker indexing step, leaving semantic retrieval/link checks dependent on prior state.

## Caveat Verdict

Required caveats are preserved:

- README states `developer/operator demo-ready v1`.
- README states `NOT production-ready`.
- README states Batch C/D are deferred and require JIT cache verification plus Tier-3 operator approval.
- README preserves the lexical false-positive caveat instead of claiming perfect unrelated-query rejection.
- README preserves the Docker Chroma gap and JIT cache persistence uncertainty.

Overclaim checks:

- No claim found that full 29-paper validation is complete.
- No claim found that the pipeline is production-ready.
- No claim found that unrelated-query rejection is perfect.

## Review Verdict

BLOCK.

The section is useful and appropriately cautious, and the links exist, but the Chroma embedding command should be corrected before treating the README how-to as operator-ready.

## Exact Next Action

Make a tiny README command fix:

```bash
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/scaled_validation_queue_v2 \
  index-done --reindex-chroma --force
```

Also update the matching caveat sentence to say `index-done --reindex-chroma --force` on the Windows host, matching `docs/features/FEATURE-ris-academic-demo-ready-v1.md` and `docs/CURRENT_STATE.md`.
