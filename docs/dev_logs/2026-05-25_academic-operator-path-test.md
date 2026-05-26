# Academic Pipeline — Operator Path Simplicity Test

**Date:** 2026-05-25
**Author:** Claude Code (Sonnet 4.6)
**Track:** Research Intelligence System — Operator Readiness
**Status:** COMPLETE — narrow runbook corrections applied; readiness verdict issued

---

## Objective

Test whether `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` is clear enough for a
non-coder to operate the 3-paper enqueue → prefetch → warm-process → index-done →
research-query pipeline without support. Compare documented commands against the actual
CLI. Produce an operator checklist and a plain-English readiness verdict.

This prompt does not re-run the validation. It uses the known-good 3-paper run from
2026-05-09 as the reference workflow.

---

## Runbook Sections Reviewed

- Top-Down Pipeline Flow diagram
- Quick Start (WP-1 prefetch path)
- Prefetch then Parse — Step-by-step
- Troubleshooting (WP-1 prefetch path)
- 5-Paper End-to-End Validation Checklist
- Operator Path (end-to-end, pre-WP-1 path)
- Step 4b — Index completed papers
- Step 4c — Embed into ChromaDB
- Querying the Academic Corpus
- Known-Good 3-Paper Validation section

---

## CLI Checks Run

```
python -m polytool research-marker-queue --help
python -m polytool research-marker-queue prefetch --help
python -m polytool research-marker-queue status-report --help
python -m polytool research-marker-queue index-done --help
python -m polytool research-marker-queue check-chroma-links --help
python -m polytool research-query --help
```

---

## Command Mismatches Found and Fixed

### Issue 1 — `--queue-dir` flag placed after subcommand (CRITICAL — command fails)

`--queue-dir` is a global flag on `research-marker-queue`, not a flag on `prefetch`.
In argparse, global flags MUST appear before the subcommand name.

Wrong form (breaks with "unrecognized arguments"):
```
python -m polytool research-marker-queue prefetch --queue-dir PATH ...
```

Correct form:
```
python -m polytool research-marker-queue --queue-dir PATH prefetch ...
```

**Locations fixed (6 places):**
- Quick Start, Step 3b command block
- Prefetch then Parse, Step 2 command block
- Troubleshooting: arXiv 429 fix
- Troubleshooting: Cached PDF missing fix
- Interrupted run recovery, step 3
- 5-paper checklist, row 1 command column

Also fixed rows 3 and 4 of the 5-paper checklist for `counts` and `list` subcommands
which had `--queue-dir` in wrong position.

### Issue 2 — `--delay-seconds` default documented as 5, CLI reports 10 (MINOR)

Step 2 parameter description said "(default: 5)". CLI help says "(default: 10.0)".

**Fixed:** Updated to `(default: 10)` in the parameter description. The example commands
retained `--delay-seconds 5` as an explicit override (valid — just more conservative than
the default, not harmful).

### Issue 3 — docker exec in Quick Start requires a running container, but Step 4 uses `--rm` (CRITICAL for non-coders)

Quick Start flow:
- Step 4 uses `docker compose ... run --rm ris-scheduler-gpu warm-process` — starts a
  container, runs, then REMOVES it.
- Step 4b used `docker exec polytool-ris-scheduler-gpu` — requires a named running
  container.

A non-coder following the Quick Start sequentially would see Step 4b fail with
"no such container" because `--rm` deleted the container Step 4 created.

**Fixed:** Changed Quick Start Step 4b to use `docker compose run --rm` form (consistent
with Step 4), with a clarifying note explaining the two container patterns and when to
use each.

The detailed Operator Path section (Step 6) was left using `docker exec` since it already
includes context about requiring a running container.

---

## Simplicity Concerns Not Fixed (noted for Director)

### Two parallel operator paths create navigation confusion

The runbook has:
1. **Quick Start** — the WP-1 prefetch path (5+ papers, recommended)
2. **Operator Path (end-to-end)** — the pre-WP-1 path (1–3 papers, no prefetch)

A non-coder opening the runbook sees two full sets of numbered steps. It is not obvious
which to follow for a first-time 3-paper run. The distinction is buried in a blockquote.

**Recommendation:** Add a one-line routing box at the very top of the procedure sections:
> First run or 1–3 papers → go to "Operator Path (end-to-end)".
> Batches of 5+ papers → go to "Prefetch then Parse".

### Known-Good 3-Paper Validation section reflects a pre-WP-1 flow

The Known-Good section documents the 2026-05-09 run which did NOT include prefetch
and ran `index-done` on the Windows host (no Docker). The current runbook says
`index-done` MUST run inside Docker (NTFS colon restriction, confirmed 2026-05-17).

This creates a contradiction: the "Known-Good" section shows a host-side `index-done`
that the current runbook says will fail on Windows. A non-coder using the Known-Good
section as their reference would reproduce a broken step.

**Recommendation:** Add a caveat to the Known-Good section noting that this run predates
the NTFS restriction discovery; current requirement is Docker for `index-done`.

Not fixed in this session (scope: narrow corrections only). Flagged for Director review.

### Step 4c (Chroma) is buried and easily skipped

The `index-done --reindex-chroma` step is in Step 4c, after the query section. A
non-coder may skip it and wonder why semantic queries don't work. Consider promoting
it to a visible callout at the start of the indexing step.

---

## Operator Checklist (Plain English)

This is the 3-paper quick path for a developer demo. Assumes Docker Desktop running,
GPU available, and 3 arXiv IDs chosen. Uses the Windows thread path (no Docker for
warm-process), which avoids Docker complexity for small runs.

---

**Start here**

Open a terminal in the PolyTool project directory.

---

**Step 1: Add papers to the queue**

Run once for each paper (use a bare arXiv ID like `2604.24366`):
```
python -m polytool research-marker-queue --queue-dir artifacts/research/test_queue enqueue --url ARXIV_ID
```
Expected: `Enqueued: arxiv:2604.24366  (status=pending)`

Check the queue looks right:
```
python -m polytool research-marker-queue --queue-dir artifacts/research/test_queue counts
```
Expected: `pending: 3`

---

**Step 2: (Optional but recommended) Prefetch PDFs**

Download the PDFs before parsing so arXiv rate limits don't abort your run:
```
python -m polytool research-marker-queue --queue-dir artifacts/research/test_queue prefetch --delay-seconds 10
```
Expected per paper: `[PREFETCH OK] arxiv:XXXX  cached to bodies/arxiv:XXXX.pdf  (X MB)`

Verify all 3 are cached:
```
python -m polytool research-marker-queue --queue-dir artifacts/research/test_queue status-report
```
Look for `prefetch_stats.cached: 3`. If any are missing, re-run prefetch.

**If it fails:** You got an HTTP 429 (rate limited). Wait 30 seconds and re-run with
`--delay-seconds 15`. Already-cached papers are skipped automatically.

---

**Step 3: Parse the PDFs**

On Windows (no Docker needed for 1–3 papers — uses local thread worker):
```
python -m polytool research-marker-queue --queue-dir artifacts/research/test_queue warm-process --max-items 3
```

The first paper takes ~2–3 minutes (model load overhead). Papers 2–3 take ~1 minute each.

Expected per paper:
```
[PASS] arxiv:2604.24366
       body_source: marker
       body_length: 56,923 chars
       marker_ready: True
```

**If it fails with `marker_timeout`:** Paper is too complex. Re-enqueue with `--force`
and retry with `--marker-timeout 3600`.

**If it fails with `fetch_failed`:** PDF was not cached. Run prefetch first (Step 2).

---

**Step 4: Check parse results**

```
python -m polytool research-marker-queue --queue-dir artifacts/research/test_queue counts
```
Expected: `done: 3, failed: 0, pending: 0`

---

**Step 5: Index papers into the knowledge store**

**IMPORTANT — Windows users:** Run this inside Docker to avoid a Windows file-naming
restriction (NTFS cannot open filenames with colons like `arxiv:1234.body.txt`).

If you have Docker running:
```
docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
  sh -c "cd /app && python -m polytool research-marker-queue \
  --queue-dir /app/artifacts/research/test_queue index-done"
```

If Docker is not set up, you can try running on Windows directly — it works for some
paper IDs but may report "no-body" for papers with colons in their arXiv ID.

Expected: `3 indexed, 0 already-indexed, 0 no-body, 0 failed`

**If it says `0 indexed, 3 no-body`:** You ran index-done on the Windows host instead
of inside Docker. Switch to the `docker exec` or `docker compose run` form above.

---

**Step 6: Embed into semantic search (optional — for semantic queries)**

```
docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
  sh -c "cd /app && python -m polytool research-marker-queue \
  --queue-dir /app/artifacts/research/test_queue index-done --reindex-chroma"
```

Then verify linkage:
```
python -m polytool research-marker-queue check-chroma-links --json
```
Expected: `missing_ks_doc_id: 0, ks_doc_id_not_in_ks: 0`

---

**Step 7: Query the indexed corpus**

```
python -m polytool research-query --question "prediction markets"
python -m polytool research-query --question "sports betting" --step-back --k 10
```

Expected: `had_fallback: false` with at least 1 citation per query.

**If `had_fallback: true`:** Either Step 5 (index-done) didn't run, or the query phrase
doesn't match any indexed claim text. Try a different topic phrase.

---

**When it is safe to continue (to a larger batch)**

All of these must be true:
- Step 4: `done: 3, failed: 0`
- Step 5: `3 indexed, 0 no-body`
- Step 7: `had_fallback: false` on at least one query matching your papers' topics

If any check fails, resolve it before scaling to 5+ papers.

---

## Readiness Verdict

**Operator-ready with caveats**

The pipeline works end-to-end. The 3-paper validation on 2026-05-09 confirmed that.
The runbook now has the critical `--queue-dir` flag-order errors fixed, so commands
will no longer fail with "unrecognized arguments."

**What still requires a developer-level reader:**

1. The two parallel operator paths (Quick Start vs. Operator Path section) require
   judgment to pick the right one. A non-coder may follow the wrong section.

2. The Docker exec vs. `run --rm` distinction requires understanding container lifecycle.
   The Quick Start fix (now uses `docker compose run --rm` for both warm-process and
   index-done) reduces this, but the detailed section still uses `docker exec`.

3. The NTFS colon restriction on Windows is real and unexpected. The warning exists in
   the runbook but is easy to miss. The workaround is non-obvious.

4. The Known-Good 3-Paper Validation section shows a host-side `index-done` that would
   now fail on Windows. This creates a contradiction for readers who use that section as
   their reference.

**For a developer demo:** Ready. A developer can follow the runbook, read error messages,
and adapt. The critical flag-order bug is now fixed.

**For a true non-coder:** Not ready without the routing clarification (which path to
follow) and the Known-Good section caveat.

---

## Should 29-Paper Validation Wait for Runbook Simplification?

**No.** The 29-paper run is already blocked on JIT cache persistence and timeout-risk
papers — independent of runbook quality. Runbook simplification is a documentation task,
not a pipeline blocker.

When the JIT cache question is resolved and the 3 timeout-risk papers have Tier-3
handling, the runbook will be in good enough shape for the developer running that batch
(who is capable of reading error messages).

Runbook simplification should be a background task — not a gate on the 29-paper corpus.

---

## Runbook Changes Made in This Session

| Section | Change |
|---------|--------|
| Quick Start, Step 3b | Fixed `--queue-dir` flag order for prefetch |
| Quick Start, Step 4b | Changed `docker exec` to `docker compose run --rm`; added note about container lifecycle |
| Prefetch then Parse, Step 2 | Fixed `--queue-dir` flag order; corrected default delay-seconds 5→10; added flag-order note |
| Troubleshooting: arXiv 429 | Fixed `--queue-dir` flag order |
| Troubleshooting: Cached PDF | Fixed `--queue-dir` flag order |
| Interrupted run recovery | Fixed `--queue-dir` flag order |
| 5-paper checklist, rows 1/3/4 | Fixed `--queue-dir` flag order in command column |
