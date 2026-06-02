---
title: Codex Verify Marker Last Timing Gate References
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-08_codex-verify-marker-last-timing-gate-references.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Codex Verify: Marker Last Timing Gate References

Date: 2026-05-08
Type: read-only documentation consistency review
Scope: Marker Docker IPC Warm-Worker v1 final timing-gate cleanup
Verdict: **FAIL**

---

## Summary

FAIL. Feature 3 closeout should not run next yet.

The two mandatory blockers from
`docs/dev_logs/2026-05-08_codex-verify-marker-final-throughput-claims.md`
were fixed:

- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Single-Paper Validation Control Surface.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md`

However, the exact grep requested for this review still surfaced current
work-packet text in
`docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md`
that presents the old `<=10s/paper` production gate in active-looking
frontmatter/top-status language. That file was not one of the two final Codex
blockers, but it is a current work packet and should be corrected before
Feature 3 closeout runs.

This review changed only this dev log.

---

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/CURRENT_STATE.md`
- `docs/INDEX.md`
- `docs/obsidian-vault/Claude Desktop/Current-Focus.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Single-Paper Validation Control Surface.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md`
- `docs/features/ris-marker-structural-parser-scaffold.md`
- `docs/dev_logs/2026-05-08_codex-verify-marker-final-throughput-claims.md`
- `docs/dev_logs/2026-05-08_fix-marker-last-timing-gate-references.md`
- `docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md`

---

## Verification Results

### 1. No active old full-PDF production timing gate

FAIL.

Most current docs now say the original `<=10s/paper` gate was rejected,
superseded, or historical. The remaining blocker is:

- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md:5`
  frontmatter still says L1 cannot ship as synchronous default because
  `parse_seconds=85.95s >> <=10s/paper gate` and is "Blocked pending" the
  canonical parse queue shipping. That reads as active state, and the queue has
  already shipped.
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md:31-34`
  top callout still says the controlled parse "fails <=10s/paper production
  gate" and repeats the `~5-10s/paper` survey estimate before the later revised
  gate note. Because this is the top status block of a current work packet, it
  remains active-looking.

### 2. Remaining timing references explicitly historical/rejected/superseded

PARTIAL.

Safe current-doc references:

- `docs/CURRENT_DEVELOPMENT.md:85,118` explicitly say the gate was rejected or
  later revised.
- `docs/CURRENT_STATE.md:1783` explicitly says the original timing gate was
  rejected.
- `docs/features/ris-marker-structural-parser-scaffold.md:7,14,23,89`
  explicitly says the old gate was rejected, superseded, or not validated.
- `docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md:19,102`
  explicitly labels the estimate/gate rejected or superseded and preserves the
  measured timings.
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Single-Paper Validation Control Surface.md:14,37,151`
  now explicitly marks the old gate rejected/superseded. Lines 21 and 29 remain
  as 2026-05-05 measurement text, but the adjacent Gate update at line 37 makes
  the supersession clear.
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md:50,61,102,181`
  now explicitly says the old timing gate was rejected/revised.
- `docs/obsidian-vault/Claude Desktop/Current-Focus.md:53-54` are dated
  historical session-context entries, and line 57 explicitly records the later
  2026-05-08 revision.

Unsafe current-doc references:

- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md:5,31-34`
  are not explicitly superseded in the same frontmatter/top-status text and
  still read as current blocker language.

Historical dev logs and unrelated matches were not treated as active blockers.

### 3. Previously flagged two files fixed

PASS.

- `Work-Packet - Marker Single-Paper Validation Control Surface.md` now has a
  superseded frontmatter entry, an adjacent gate-update paragraph, and a revised
  as-measured verdict note.
- `Work-Packet - Marker Canonical Academic Parse Queue.md:181` now strikes
  through the old `papers 2+ expected <=10s warm` text and records the measured
  warm timings.

### 4. Revised gate consistency and actual timings

PASS.

The revised gate is consistently preserved in the reviewed current-state docs:

- `>=3` full PDFs in one Docker/GPU IPC warm-worker session
- papers 2+ delta `<=5s`
- `body_source=marker`
- `ipc_warm_worker_used=true`
- no pdfplumber fallback
- no daemon-process error
- queue semantics intact
- clean shutdown

Actual timings are preserved:

- paper 1 = `45.55s`
- paper 2 = `69.73s`
- paper 3 = `48.31s`

### 5. Feature 3 active and pending closeout

PASS.

`docs/CURRENT_DEVELOPMENT.md` has `### Feature 3: Marker Docker IPC Warm-Worker v1`
under Active Features. It is pending Codex closeout verification and not in
Recently Completed. `Test-Path docs/features/ris-marker-docker-ipc-warm-worker-v1.md`
returned `False`.

### 6. L2/PaperQA2 and L4 blocked/stubbed

PASS.

Reviewed docs continue to say:

- L2 PaperQA2 is stubbed/blocked until Feature 3 closeout verification passes.
- L4 Multi-source Academic Harvesters remains stubbed and was not activated.
- The warm-worker work packet lists "No L2 work" and "No L4 work" as non-goals.

### 7. No new implementation/test/Docker/artifact/SVM/trading changes by docs fix

PASS WITH CAVEAT.

The worktree is dirty with existing implementation/test/Docker changes from the
Marker IPC stream. The scoped tracked diff still shows the same five paths
called out in the prior review/fix logs:

```text
M	Dockerfile.ris
M	packages/research/ingestion/fetchers.py
M	packages/research/ingestion/marker_queue.py
M	tests/test_ris_marker_queue.py
M	tools/cli/research_marker_queue.py
```

`git status --short` also shows untracked Marker IPC implementation/test files
that predate this docs review. I found no evidence that the final timing-gate
docs fix added new implementation, tests, Docker, artifacts, SVM, or trading
changes.

---

## Commands Run

### `git status --short`

Exit code: 0. Key result:

```text
 M Dockerfile.ris
 M docs/CURRENT_DEVELOPMENT.md
 M docs/CURRENT_STATE.md
 M docs/INDEX.md
 M docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md
 M docs/features/ris-marker-structural-parser-scaffold.md
 M "docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md"
 M "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md"
 M "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Single-Paper Validation Control Surface.md"
 M "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md"
 M "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Prefetch Label Discovery Mode.md"
 M "docs/obsidian-vault/Claude Desktop/Current-Focus.md"
 M packages/research/ingestion/fetchers.py
 M packages/research/ingestion/marker_queue.py
 M tests/test_ris_marker_queue.py
 M tools/cli/research_marker_queue.py
?? docs/dev_logs/2026-05-08_fix-marker-last-timing-gate-references.md
?? "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md"
?? packages/research/ingestion/marker_ipc_worker.py
?? tests/test_ris_marker_ipc_worker.py
```

There are many additional untracked 2026-05-07 and 2026-05-08 Marker dev logs in
the full output.

### `git log --oneline -5`

Exit code: 0.

```text
4b57400 SVM scoring complete
e482a6d L3 handoff
be8b4f2 fix(ris): resolve Codex FAIL blockers - Marker queue v0
7b81a7a Marker Parser added
a4fdcac docs(ris): close out Marker control surface validation - L1 still blocked
```

### `git grep -n "<=10 s\|<=10s\|≤10s\|10s/paper\|10 seconds\|5-10\|5–10\|~5-10" docs`

Exit code: 0. Relevant semantic matches:

```text
docs/CURRENT_DEVELOPMENT.md:85:- **Revised gate (Director 2026-05-08):** Original <=10s/paper timing gate rejected as unrealistic...
docs/CURRENT_DEVELOPMENT.md:118:... L1 production blocked on <=10s/paper gate at time of closeout (**gate later revised 2026-05-08 - see Active Feature 3**).
docs/CURRENT_STATE.md:1783:... Original <=10s/paper timing gate rejected as unrealistic (Director 2026-05-08).
docs/INDEX.md:155-163: recent 2026-05-08 dev-log entries record FAIL/fix/rejected/superseded status.
docs/INDEX.md:184: historical 2026-05-05 dev-log row records the old failed gate.
docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md:17,93-94,114: old gate now annotated as historical/rejected.
docs/features/ris-marker-structural-parser-scaffold.md:7,14,23,89: old gate/estimate rejected, superseded, or not validated.
docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md:19,102: old estimate/gate rejected or superseded; measured timings preserved.
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md:23,50,61,102,181: old gate is dated/rejected/revised; line 181 fixed.
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Single-Paper Validation Control Surface.md:14,21,29,37,151: line 37 now supersedes the 2026-05-05 measurement text.
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md:5,31,34: active-looking old gate language remains in frontmatter/top callout.
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md:43,56,96,126: revised/superseded notes present.
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Prefetch Label Discovery Mode.md:152: old gate rejected.
docs/obsidian-vault/Claude Desktop/Current-Focus.md:42,53,54,57,81: historical session-context/frontmatter matches; line 57 records later revision.
```

The unfiltered command also emitted generated Obsidian `.smart-env` vector-cache
content and unrelated matches such as API polling "every 10 seconds"; those were
not semantically treated as current Marker production gate docs.

### `git grep -n "Feature 3\|Marker Docker IPC" docs/CURRENT_DEVELOPMENT.md`

Exit code: 0.

```text
docs/CURRENT_DEVELOPMENT.md:75:### Feature 3: Marker Docker IPC Warm-Worker v1
docs/CURRENT_DEVELOPMENT.md:118:... gate later revised 2026-05-08 - see Active Feature 3 ...
docs/CURRENT_DEVELOPMENT.md:137:... Pending Codex closeout verification - see Active Feature 3. ...
docs/CURRENT_DEVELOPMENT.md:138:... Blocked on Docker IPC warm-worker (v1) Feature 3 closeout. ...
docs/CURRENT_DEVELOPMENT.md:162:... Docker IPC warm-worker (v1) is now Active Feature 3 ...
docs/CURRENT_DEVELOPMENT.md:167:... Marker Docker IPC warm-worker v1 activated as Feature 3 ...
docs/CURRENT_DEVELOPMENT.md:168:... Marker Docker/Linux IPC Warm-Worker (v1) is NOW ACTIVE as Feature 3 ...
```

### `git diff --name-status -- packages tools tests polytool config infra docker-compose.yml Dockerfile.ris artifacts`

Exit code: 0.

```text
M	Dockerfile.ris
M	packages/research/ingestion/fetchers.py
M	packages/research/ingestion/marker_queue.py
M	tests/test_ris_marker_queue.py
M	tools/cli/research_marker_queue.py
```

Git also warned that `Dockerfile.ris` line endings will be replaced by CRLF the
next time Git touches it.

### `git diff --stat`

Exit code: 0. Key result before this dev log:

```text
 Dockerfile.ris                                     |   1 +
 docs/CURRENT_DEVELOPMENT.md                        |  35 +-
 docs/CURRENT_STATE.md                              |   2 +-
 docs/INDEX.md                                      |  13 +-
 ...026-05-03_academic-pipeline-hosting-decision.md |  18 +-
 .../ris-marker-structural-parser-scaffold.md       |  13 +-
 .../Decision - Academic Pipeline Hosting.md        |   6 +-
 ...cket - Marker Canonical Academic Parse Queue.md |  15 +-
 ...rker Single-Paper Validation Control Surface.md |   6 +-
 ...acket - Marker Structural Parser Integration.md |   8 +-
 .../Work-Packet - Prefetch Label Discovery Mode.md |  19 +-
 .../obsidian-vault/Claude Desktop/Current-Focus.md |  15 +-
 packages/research/ingestion/fetchers.py            | 137 ++++
 packages/research/ingestion/marker_queue.py        | 111 +++-
 tests/test_ris_marker_queue.py                     | 724 +++++++++++++++++++++
 tools/cli/research_marker_queue.py                 | 133 +++-
 25 files changed, 1763 insertions(+), 239 deletions(-)
```

The full stat also includes generated Obsidian `.ajson` and workspace files.

### Focused inspections

`Test-Path -LiteralPath "docs/features/ris-marker-docker-ipc-warm-worker-v1.md"`
returned:

```text
False
```

Focused reads confirmed the blocker text in
`Work-Packet - Marker Structural Parser Integration.md:5,31-34` and confirmed
the two previously flagged files now have supersession notes.

No validation, tests, Docker rebuilds, queue mutations, artifacts, SVM runs, or
trading commands were run.

---

## Blockers Before Feature 3 Closeout

1. Update `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md`
   frontmatter `blocked-reason` so the old `<=10s/paper gate` is explicitly
   historical/rejected/superseded and the current blocker points to Feature 3
   closeout, not queue shipping.
2. Update the same file's top DANGER callout so the `fails <=10s/paper
   production gate` and `~5-10s/paper` survey language is explicitly
   historical/superseded adjacent to the measurement text, not only later in the
   Option A bullet list.

---

## Closeout Verdict

Feature 3 closeout should **not** run next. The final two Codex blockers are
fixed, but the all-doc grep still finds a current work packet with old timing
gate language that is not clearly superseded in the active frontmatter/top
status block.

---

## Codex Review Summary

Tier: docs-only closeout-readiness review.

Issues found: one remaining current work-packet timing-gate blocker in
`Work-Packet - Marker Structural Parser Integration.md`.

Issues addressed: none. Per instruction, only this review dev log was created.
