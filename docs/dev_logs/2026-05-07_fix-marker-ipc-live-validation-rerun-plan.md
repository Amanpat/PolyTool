# Fix: Marker IPC Live-Validation Rerun Plan — Codex Blocker Resolution

**Date:** 2026-05-07
**Type:** Docs-only fix (no code, no queue mutations, no Docker)
**Track:** RIS — L1 Marker IPC Warm-Worker (Feature 3)
**Codex review:** Skip — docs-only
**Scope:** `docs/dev_logs/2026-05-07_marker-ipc-live-validation-rerun-plan.md` only

---

## Objective

Resolve the three blockers Codex identified in
`2026-05-07_codex-verify-marker-ipc-live-validation-fixes.md` that caused the rerun plan to
receive FAIL status. The implementation fixes (Dockerfile stub, worker restart) were already
verified PASS. Only the rerun plan was blocked.

---

## Codex Blockers Addressed

### Blocker 1 — `enqueue` commands omit required `--url`

**Codex finding:** Lines 108, 173, and 200 used `enqueue <id>` or `enqueue <id> --force`
without the required `--url` flag. The CLI requires `--url URL_OR_ID` as a named argument.

**Evidence from CLI help (run this session):**
```
python -m polytool research-marker-queue enqueue --help

usage: polytool research-marker-queue enqueue [-h] --url URL_OR_ID
                                              [--title TITLE] [--force]
                                              [--json]
options:
  --url URL_OR_ID  arXiv URL or bare arXiv ID (e.g. 2604.24366)
  --title TITLE    Optional title hint
  --force          Re-enqueue even if already exists (resets to pending)
  --json           Output result as JSON
```

`--url` is a required named argument, not a positional. All bare-ID calls would fail
at runtime with `error: the following arguments are required: --url`.

**Fix applied:** All three occurrences corrected to `enqueue --url <id> [--force]`.

- Line 108 (Prerequisites): `enqueue 2604.24366 --force` → `enqueue --url 2604.24366 --force`
- Line 173 (Candidate D): `enqueue <arxiv_id> --title "hint title"` → `enqueue --url <arxiv_id> --title "hint title"`
- Step 2 (Prepare queue): Replaced bare-ID enqueue with fresh validation queue approach
  using `--queue-dir artifacts/research/marker_validation_queue` (see Blocker 3).

---

### Blocker 2 — Readiness checklist pre-checked without evidence

**Codex finding:** The "Rerun Prompt Readiness" section at lines 352–356 marked all 5 items
as `[x]` (complete) even though the same plan document stated:
- Docker image was NOT rebuilt (intentionally deferred)
- Queue reset had NOT been run
- Papers 2-3 had NOT been verified
- Queue counts had NOT been verified

**Fix applied:** The pre-checked list was replaced with an explicit **Preflight Checklist**
with 5 numbered items, each:
- Marked `[ ]` (unchecked — no evidence exists yet)
- Stating the exact command to collect evidence
- Stating what output constitutes passing evidence
- Including a stop condition if the check fails

The rerun prompt readiness section now states: "Rerun prompt CAN be issued after all 5
preflight items above are checked." — making the gate explicit and not pre-satisfied.

---

### Blocker 3 — Candidate set not ready; papers 2-3 unverified or risky

**Codex finding:** `2204.05149` was "explicitly unknown" and `2412.14173` was "explicitly
risky with one attempt left." The plan recommended replacing `2412.14173` but did not
provide a concrete exclusion path before the `--max-items 3` run.

**Evidence from queue (run this session):**
```
python -m polytool research-marker-queue list --status all --json

arxiv:2604.24366 — status: failed,  attempts: 3, title: "The Anatomy of a Decentralized Prediction Market"
arxiv:2412.14173 — status: pending, attempts: 2, title: ""   (unknown)
arxiv:2204.05149 — status: pending, attempts: 0, title: ""   (unknown)
```

```
python -m polytool research-marker-queue counts --json
{"pending": 2, "processing": 0, "done": 0, "failed": 1, "total": 3}
```

Local RAG query for `2204.05149` and `2412.14173` returned no matching knowledge-store
entries — no local metadata exists for either paper's content or complexity.

**Fix applied:**

1. `arxiv:2412.14173` **explicitly excluded** from the rerun. The plan now states:
   "`2412.14173` is EXCLUDED from the rerun" with the reason (1 attempt remaining;
   permanent failure if cooldown insufficient).

2. `arxiv:2204.05149` **explicitly marked UNVERIFIED.** The plan now states do not use
   it without operator verification.

3. Adopted **fresh isolated validation queue** approach using `--queue-dir artifacts/research/marker_validation_queue`.
   This:
   - Avoids touching the main queue (`artifacts/research/marker_parse_queue`)
   - Eliminates the `2412.14173` contamination risk entirely
   - Makes the 3-paper candidate set a separate gate that must be filled by the operator
     before the queue is created

4. Added a **"CANDIDATE SELECTION REQUIRED"** section that explicitly blocks live
   validation until the operator verifies 2 additional papers meeting the profile:
   - arXiv category: `econ.GN`, `econ.EM`, `econ.TH`, `q-fin.GN`, `q-fin.TR`, `stat.AP`
   - 8–18 pages (PDF viewer, not counting appendix)
   - Prose-heavy, fewer than 3 full-figure pages, no dense equation blocks

5. All Step 2 enqueue commands now target `--queue-dir artifacts/research/marker_validation_queue`
   with `PAPER2_ID` / `PAPER3_ID` as explicit placeholders that must be filled before running.

---

## Commands Run This Session

| Command | Exit code | Key output |
|---------|-----------|-----------|
| `python -m polytool research-marker-queue enqueue --help` | 0 | `--url URL_OR_ID` is required |
| `python -m polytool research-marker-queue warm-process --help` | 0 | `--max-items N`, `--marker-timeout SECONDS`, `--json` |
| `python -m polytool research-marker-queue counts --help` | 0 | `--json` only |
| `python -m polytool research-marker-queue --help` | 0 | All subcommands confirmed; `--queue-dir PATH` global option confirmed |
| `python -m polytool research-marker-queue list --status all --json` | 0 | 3 items; titles of papers 2-3 are empty strings |
| `python -m polytool research-marker-queue counts --json` | 0 | `{"pending": 2, "failed": 1, "total": 3}` |
| `python -m polytool rag-query --question "arxiv 2204.05149" ...` | 0 | No matching knowledge-store entries |
| `python -m polytool rag-query --question "arxiv 2412.14173" ...` | 0 | No matching knowledge-store entries |

No queue mutations, no Docker commands, no warm-process runs were executed.

---

## Files Changed

| File | Change |
|------|--------|
| `docs/dev_logs/2026-05-07_marker-ipc-live-validation-rerun-plan.md` | Fixed enqueue syntax (3 sites); replaced paper 2-3 sections with "SELECTION REQUIRED"; replaced pre-checked readiness list with unchecked preflight checklist; adopted `--queue-dir` fresh queue approach; updated Docker commands; updated artifact paths |
| `docs/dev_logs/2026-05-07_fix-marker-ipc-live-validation-rerun-plan.md` | This dev log (created) |

**No implementation files touched. No tests changed. No queue mutated.**

---

## Whether Codex Can Re-Review

Yes. The plan now satisfies all three Codex blockers:

1. All `enqueue` commands include `--url` — verified against `enqueue --help`.
2. Preflight checklist is fully unchecked; each item requires specific command output
   as evidence before it can be marked complete.
3. Candidate set is "SELECTION REQUIRED" — live validation is explicitly blocked until
   the operator verifies and supplies 2 paper IDs. `2412.14173` is excluded. `2204.05149`
   is marked unverified. No false readiness claims remain.

The plan is now safe to re-review. The Codex re-review should verify:
- `enqueue --url` syntax appears at all enqueue call sites
- No `[x]` items remain in the preflight checklist
- "CANDIDATE SELECTION REQUIRED" gate is present and blocks the Docker run
- `--queue-dir artifacts/research/marker_validation_queue` is used throughout Step 2 and Step 3
- L1 remains BLOCKED in the plan footer

---

## L1 Production Status

**BLOCKED.** No change. Feature 3 live Docker/GPU validation has not been run.
The plan is now correctable — live validation can be attempted once all 5 preflight
items are checked with evidence.
