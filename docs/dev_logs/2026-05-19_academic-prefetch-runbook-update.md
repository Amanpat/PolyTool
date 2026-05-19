# Academic Pipeline — Prefetch Runbook Update

**Date:** 2026-05-19
**Type:** Documentation update
**Track:** Research Intelligence System — L1 operator runbook
**Prerequisite log:** `docs/dev_logs/2026-05-18_academic-ris-operational-triage.md`

---

## Files Changed

| File | Action | Reason |
|------|--------|--------|
| `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` | Updated | Added WP-1 prefetch-then-parse workflow, troubleshooting, 5-paper checklist, corpus status note |
| `docs/runbooks/RIS_OPERATOR_GUIDE.md` | Updated | Added one-line pointer to Marker Queue runbook at top of Quick Reference |
| `docs/dev_logs/2026-05-19_academic-prefetch-runbook-update.md` | Created | This log |

---

## What Changed in the Runbook

### 1. Header

Added WP-1 status line and link to the operational triage log. Previously the header
only listed the L1 feature doc — the triage memo was invisible to operators landing on
the runbook.

### 2. Pipeline flow diagram

Added a `prefetch` step between enqueue and warm-process to show it as part of the
canonical flow.

### 3. Quick start block

Replaced the old 5-step quick start with a WP-1-aware version that includes:
- `research-marker-queue prefetch` between enqueue and warm-process
- `docker exec`-based `index-done` (not the host-side form)
- A callout box explaining the WP-1 dependency and when the old path is still valid
  (1–3 papers on a reliable connection)

### 4. New "Prefetch then Parse (WP-1 Workflow)" section

This is the main addition. Inserted between the Overview and Prerequisites sections.
Contents:

**Why this exists** — plain-English explanation for non-coders. Two sentences: arXiv
rate limiting cascades during GPU parse; separating fetch from parse fixes both the
failures and the idle GPU problem.

**Step-by-step operator path (7 steps):**
- Step 1: Enqueue
- Step 2: Prefetch (WP-1 command, host-side, with expected outputs and a `--status` check)
- Step 3: Start Docker / verify GPU
- Step 4: warm-process (with output table showing [PASS]/[FAIL] interpretation)
- Step 5: Inspect results
- Step 6: index-done inside Docker (with the Windows NTFS rationale)
- Step 7: research-query probes

**Troubleshooting (6 scenarios):**
1. arXiv 429 / timeout during prefetch
2. Cached PDF missing or zero-byte
3. Docker not running
4. index-done run on Windows host instead of inside container
5. Marker timeout on one paper (3 options: retry with longer timeout, skip, inspect)
6. Interrupted run / resuming after session kill

**5-paper E2E validation checklist** — 6-row table with command and expected result per
check. Designed to be run before any large batch.

**Corpus status note (2026-05-18)** — table showing current state of the 29-paper
`scaled_validation_queue_v2` (5 done, 5 failed, 1 stuck, 18 pending). Explicit
"do not" list: do not run warm-process without prefetch, do not reset failed papers
until WP-1 ships.

### 5. RIS_OPERATOR_GUIDE.md pointer

Added a three-line callout at the top of Quick Reference. The operator guide predates
L1 Marker (last verified 2026-04-09) and had no reference to the Marker queue at all.
A non-coder following the guide would have no path to the academic ingest flow.

---

## Simplicity Concerns Surfaced

These are interface complexities I encountered while writing the operator path. Flagged
for implementation awareness (Claude Prompt A / WP-1 scope).

### C1 — `docker exec` container name is brittle

The `index-done` Docker exec command requires knowing the exact running container name
(`polytool-ris-scheduler-gpu`). This name depends on the `docker compose` project name,
which can vary by machine or Docker Desktop configuration. A non-coder who gets
`container not found` has no obvious recovery path.

**Recommendation:** The `index-done` command should either (a) detect when it is running
on Windows and emit a clear error with the exact `docker exec` command to run, or (b)
accept a `--via-docker` flag that constructs and runs the exec internally.

### C2 — Queue dir path appears in every command

The `--queue-dir` flag must be repeated on every subcommand. For a non-coder running a
multi-step workflow, it is easy to forget it on one step and mix the test queue with
the main corpus. A persistent config file or an env var (`RIS_MARKER_QUEUE_DIR`) would
reduce this friction.

### C3 — `prefetch --status` is a separate invocation

After running prefetch, the operator needs to run `prefetch --status` to verify
completion. It would be more operator-friendly if prefetch printed a summary table at
the end of the run, so a single command gives both fetch results and a readiness check.

### C4 — No clear "is WP-1 shipped?" indicator

The runbook documents the `prefetch` command but notes `[requires WP-1]`. A non-coder
who tries to run it before WP-1 ships will get a command-not-found error. The runbook
cannot check this for them. Consider adding a `research-marker-queue version` or
`research-marker-queue capabilities` subcommand that lists available subcommands, so
operators can confirm `prefetch` is available before following the WP-1 path.

### C5 — Two "Step 1" labels

The existing "Operator Path" section and the new "Prefetch then Parse" section both use
step numbers starting at 1. A non-coder may try to combine them. The old "Operator Path"
section is now redundant for the WP-1 path. After WP-1 ships and is validated, consider
marking the old path as "legacy / pre-WP-1" or removing it.

---

## Open Questions for Implementation (Claude Prompt A)

1. **Prefetch manifest format:** Does `prefetch --status` read from a manifest file in
   the queue directory, or does it inspect the bodies/ directory directly? The runbook
   assumes a structured manifest that tracks `cached=True/False` per candidate. If the
   implementation uses a different mechanism, the `--status` output description needs
   updating.

2. **Prefetch scope:** Does `prefetch` only download PDFs for `pending` items, or does
   it also pre-cache papers that are currently `done` but whose PDF was deleted? The
   runbook assumes pending-only for simplicity.

3. **warm-process cache path:** Does warm-process automatically check `bodies/` for a
   cached PDF before attempting a live fetch, or does it require a flag like
   `--prefer-cached`? The runbook assumes automatic cache preference with no extra flag.

4. **Windows path for prefetch:** `prefetch` runs on the Windows host. Does it write
   to the same `bodies/` directory that Docker reads via volume mount? The runbook
   assumes yes. If the volume mount path differs, the `docker exec index-done` form
   will need a different `--queue-dir`.

5. **`prefetch --status` subcommand:** The runbook calls `prefetch --status`. If this
   is implemented as a separate subcommand (e.g. `prefetch-status`) rather than a flag,
   the commands in the runbook need updating.

---

## What Is Not Documented Here (Out of Scope)

- L2 semantic retrieval (ChromaDB academic path, L2.1) — deferred
- SSRN / NBER harvester paths — deferred
- WP-2 tiered ingestion modes — not yet designed
- WP-3 single-command entrypoint script — not yet built
- TorchInductor / TRITON_CACHE_DIR investigation — separate follow-up

---

## Codex Review

Tier: Skip — no implementation code changed. Documentation only.
