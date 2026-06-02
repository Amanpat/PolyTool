# Dev Log: README Academic RIS How-To Force Fix

**Date:** 2026-05-29
**Scope:** Docs-only unblock for the README Academic RIS how-to review.

---

## Files Changed and Why

- `README.md`
  - Added `--force` to the host Chroma refresh command in the Academic RIS how-to section.
  - Updated the Chroma caveat to explain that `--force` refreshes Chroma for queue items already recorded by the Docker-side `index-done` step.
- `docs/dev_logs/2026-05-29_readme-academic-ris-how-to-force-fix.md`
  - Records this narrow unblock.

No implementation code, tests, runtime artifacts, Batch C/D, benchmark baselines, vault files, or unrelated docs were changed.

## Exact Command Fixed

Before:

```bash
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/scaled_validation_queue_v2 \
  index-done --reindex-chroma
```

After:

```bash
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/scaled_validation_queue_v2 \
  index-done --reindex-chroma --force
```

## Caveat Sentence Updated

Updated the Chroma caveat to:

```text
Chroma embedding requires Windows host. The ris-scheduler-gpu Docker image lacks chromadb; run index-done --reindex-chroma --force on the host, not inside the container. --force refreshes Chroma for queue items already recorded by the Docker-side index-done step.
```

## Search and Check Output

`rg -n "index-done --reindex-chroma|Chroma embedding requires Windows host" README.md`

```text
354:  index-done --reindex-chroma --force
373:- **Chroma embedding requires Windows host.** The `ris-scheduler-gpu` Docker image lacks `chromadb`; run `index-done --reindex-chroma --force` on the host, not inside the container. `--force` refreshes Chroma for queue items already recorded by the Docker-side `index-done` step.
```

`rg -n "production-ready" README.md`

```text
317:**Status: developer/operator demo-ready v1. NOT production-ready.**
372:- **Not production-ready.** Each batch requires operator supervision and manual Chroma embedding on the Windows host.
```

`rg -n "developer/operator demo-ready v1|Batch C/D deferred|Lexical false positive|JIT cache persistence unconfirmed" README.md`

```text
317:**Status: developer/operator demo-ready v1. NOT production-ready.**
374:- **Lexical false positive.** A query like `weather forecast` may return a citation from a prediction-market paper that mentions weather forecasting as a control category. The semantic guard is working; the false positive is in the lexical fallback path over legitimately relevant text. Post-v1 hardening item.
375:- **JIT cache persistence unconfirmed.** In-session JIT reuse works, but cross-restart cache persistence is not confirmed. Run `research-marker-queue jit-cache-check` before large batches.
376:- **Batch C/D deferred.** 9 large papers remain (including two timeout/rate-limit cases). Do not run without JIT cache verification and Tier-3 operator approval.
```

## Review Rerun

The README review can be rerun. The prior Codex BLOCK item was the missing `--force` on the host Chroma refresh command, and that specific blocker is resolved.

No pipeline validation, Chroma query, parse, prefetch, Batch C/D, or benchmark command was run.
