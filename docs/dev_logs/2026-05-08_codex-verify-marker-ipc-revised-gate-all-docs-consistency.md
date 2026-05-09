# Codex Verify: Marker IPC Revised Gate All-Docs Consistency

Date: 2026-05-08
Type: read-only documentation consistency review
Scope: Feature 3 - Marker Docker IPC Warm-Worker v1 revised gate closeout readiness
Verdict: **FAIL**

---

## Summary

FAIL. Feature 3 closeout should **not** run next yet.

The main state docs now agree that Marker Docker IPC Warm-Worker v1 is Active Feature 3,
pending Codex closeout verification, and no longer deferred from Queue v0. The revised
functional gate is also present in the core current docs, and the measured timings are
preserved honestly: 45.55s, 69.73s, 48.31s.

However, all-doc consistency is still not clean. Current/affected docs still contain active
or active-looking Marker GPU throughput requirements/claims around `<=10s` or 5-10s per
paper that are not clearly superseded in place. The clearest blocker is the current hosting
decision checklist item requiring `<=10 s/paper` on the production host.

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
- `docs/features/ris-marker-structural-parser-scaffold.md`
- `docs/dev_logs/2026-05-08_codex-verify-marker-ipc-revised-gate-doc-consistency.md`
- `docs/dev_logs/2026-05-08_fix-marker-ipc-revised-gate-all-docs-consistency.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Prefetch Label Discovery Mode.md`
- `docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md`
- `docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md`
- Current diffs for the changed docs above

---

## Verification Results

### 1. Feature 3 active and pending closeout

PASS.

`docs/CURRENT_DEVELOPMENT.md` contains `### Feature 3: Marker Docker IPC Warm-Worker v1`
with status "Implementation complete - all revised functional gates PASS - pending Codex
closeout verification." The current step says to await Codex closeout verification before
creating the feature doc, updating INDEX, and moving to Recently Completed.

### 2. CURRENT_STATE no longer says deferred from Queue v0

PASS.

`docs/CURRENT_STATE.md:1783` now says Marker Docker IPC warm-worker v1 is **Active Feature 3**
and pending Codex closeout verification. The required grep for current deferred language found
only historical dev-log references, not current state text.

### 3. No current doc presents <=10s/paper or 10 seconds/paper as active full-PDF gate

FAIL.

The acceptance gate row in `Work-Packet - Marker Structural Parser Integration.md` was fixed,
but other current/affected docs still have active or active-looking old timing language:

- `docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md:102`
  still has an unchecked prerequisite item: `GPU performance baseline run: <=10 s/paper on
  the production host`.
- `docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md:19`
  still says Marker on a 2070 Super "runs in 5-10 seconds" without a local supersession note.
- `docs/features/ris-marker-structural-parser-scaffold.md:89` still says GPU is required
  for production throughput `(~5-10 s/paper on RTX 2070 Super; 300 s timeout on CPU)`.
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md:43`
  still says papers 2+ are expected `<=10s` on warm RTX 2070 Super VRAM.
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md:56`
  still says Marker on this hardware is `~5-10s/paper` and "fast enough for production."

These are not all framed as the revised gate; several read as current assumptions or checklist
items rather than historical/rejected/superseded text.

### 4. Remaining <=10s references historical/rejected/superseded

FAIL.

Many remaining references are correctly historical or superseded, including the core Feature 3
block, CURRENT_STATE, Current-Focus, INDEX, and the revised acceptance gates in the Docker IPC
work packet. The examples listed above are not clearly superseded in place.

Additional weaker cleanup candidates:

- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md:181`
  describes "papers 2+ expected <=10s warm" in reference material.
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md:204`
  repeats the same reference-material phrase.
- `docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md` was recently edited to
  add stale notes but still says L1 remains blocked pending `>=3 warm papers at <=10s/paper`.
  Because it is a dev log, this is less severe than current docs, but it is not aligned with
  the 2026-05-08 revision.

### 5. Revised gate consistency

PARTIAL.

Consistent in the core state docs:

- `>=3` full academic PDFs in one warm session
- Papers 2+ delta (`total_seconds - parse_seconds`) `<=5s`
- `body_source=marker`
- `ipc_warm_worker_used=true`
- no pdfplumber fallback
- no daemon-process error
- queue semantics intact
- clean shutdown

Not consistent across all current/affected docs because of the active-looking old performance
claims above.

### 6. Actual timings preserved honestly

PASS.

The current docs and fix log preserve:

- Paper 1: 45.55s parse, 72.31s total, delta 26.76s
- Paper 2: 69.73s parse, 69.86s total, delta 0.13s
- Paper 3: 48.31s parse, 48.53s total, delta 0.22s

### 7. L2/PaperQA2 and L4 remain blocked/stubbed

PASS.

- `Current-Focus.md` says L2 is a stub and L4 is a stub.
- The Marker Docker IPC work packet says L2 PaperQA2 remains blocked until Feature 3 closeout
  verification and explicitly lists "No L2 work" and "No L4 work."
- `CURRENT_DEVELOPMENT.md` says do not start L2 or L4.

### 8. Feature 3 not moved to Recently Completed

PASS.

`CURRENT_DEVELOPMENT.md` still has Marker Docker IPC Warm-Worker v1 under Active Features.
The Recently Completed section begins later and does not include that feature. The expected
feature doc path `docs/features/ris-marker-docker-ipc-warm-worker-v1.md` does not exist yet.

### 9. Dirty-tree interpretation

PASS WITH CAVEAT.

The worktree has dirty implementation/test/Docker files, but the fix dev log provides scoped
before/after evidence that those were pre-existing Feature 3 implementation changes, not added
by the docs consistency fix. The current tracked implementation path diff matches that baseline:

```text
M	Dockerfile.ris
M	packages/research/ingestion/fetchers.py
M	packages/research/ingestion/marker_queue.py
M	tests/test_ris_marker_queue.py
M	tools/cli/research_marker_queue.py
```

`git status --short` also shows untracked Feature 3 implementation files that the fix log
identified as pre-existing:

```text
?? packages/research/ingestion/marker_ipc_worker.py
?? tests/test_ris_marker_ipc_worker.py
```

No tracked `artifacts/`, trading, L2, L4, or source SVM implementation path appeared in the
scoped implementation diff. There are modified Obsidian `.smart-env` cache files, including a
cache file whose name contains `SVM_Topic_Filter_Training`; I interpret those as docs/vault
cache changes, not SVM model/label/source implementation changes.

### 10. Closeout may run next

FAIL.

Closeout should wait until the remaining active/current `<=10s` and 5-10s production-throughput
claims are updated or explicitly superseded in place.

---

## Commands Run

### `git status --short`

Exit code: 0. Relevant output:

```text
 M Dockerfile.ris
 M docs/CURRENT_DEVELOPMENT.md
 M docs/CURRENT_STATE.md
 M docs/INDEX.md
 M docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md
 M docs/features/ris-marker-structural-parser-scaffold.md
 M docs/obsidian-vault/.obsidian/workspace.json
 M docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_09-Decisions_Decision_-_Academic_Pipeline_Hosting_md.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_L3_v1_SVM_Topic_Filter_Training_md.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Marker_Canonical_Academic_Parse_Queue_md.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Marker_Structural_Parser_Integration_md.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Prefetch_Label_Discovery_Mode_md.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
 M "docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md"
 M "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md"
 M "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md"
 M "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Prefetch Label Discovery Mode.md"
 M "docs/obsidian-vault/Claude Desktop/Current-Focus.md"
 M packages/research/ingestion/fetchers.py
 M packages/research/ingestion/marker_queue.py
 M tests/test_ris_marker_queue.py
 M tools/cli/research_marker_queue.py
?? docs/dev_logs/2026-05-08_fix-marker-ipc-revised-gate-all-docs-consistency.md
?? "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md"
?? packages/research/ingestion/marker_ipc_worker.py
?? tests/test_ris_marker_ipc_worker.py
```

There were many additional untracked Marker IPC dev logs from 2026-05-07 and 2026-05-08.

### `git log --oneline -5`

Exit code: 0.

```text
4b57400 SVM scoring complete
e482a6d L3 handoff
be8b4f2 fix(ris): resolve Codex FAIL blockers - Marker queue v0
7b81a7a Marker Parser added
a4fdcac docs(ris): close out Marker control surface validation - L1 still blocked
```

### `git grep -n "<=10s\|<=10s\|10s/paper\|10 seconds" docs`

Exit code: 0. The full command returned many matches, including large Obsidian `.smart-env`
cache JSON. Relevant non-cache results included:

```text
docs/CURRENT_DEVELOPMENT.md:85:- **Revised gate (Director 2026-05-08):** Original <=10s/paper timing gate rejected as unrealistic ...
docs/CURRENT_DEVELOPMENT.md:118:... L1 production blocked on <=10s/paper gate at time of closeout (**gate later revised 2026-05-08 - see Active Feature 3**). |
docs/CURRENT_STATE.md:1783:- Marker Docker IPC warm-worker v1 - **Active Feature 3** ... Original <=10s/paper timing gate rejected as unrealistic ...
docs/INDEX.md:155:| [Marker IPC - Revised Gate All-Docs Consistency Fix] ... <=10s/paper gate language superseded ...
docs/features/ris-marker-structural-parser-scaffold.md:7:> ... Original aspirational <=10s/paper timing gate **rejected as unrealistic ...**
docs/features/ris-marker-structural-parser-scaffold.md:14:> ... (<=10s/paper gate superseded 2026-05-08 by functional warm-worker validation ...)
docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md:19:... on a modest GPU ... it runs in 5-10 seconds. Production cannot run on CPU.
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md:61:... original <=10s/paper timing target; **revised gate 2026-05-08:** ...
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md:96:... <=10 seconds.~~ **Superseded (Director 2026-05-08):** ...
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Prefetch Label Discovery Mode.md:152:> **Original <=10s/paper timing gate rejected as unrealistic ...**
```

### `git grep -n "deferred from Queue v0\|warm-worker v1 is deferred\|Marker Docker IPC.*deferred" docs`

Exit code: 0. Results are historical dev logs only; no current `CURRENT_STATE.md` hit:

```text
docs/dev_logs/2026-05-07_codex-verify-l3-v1-svm-feature-closeout.md:310:- Marker Docker IPC warm-worker v1 is deferred, not canceled.
docs/dev_logs/2026-05-07_codex-verify-l3-v1-svm-feature-closeout.md:346:- Operational follow-up remains Marker Docker IPC warm-worker v1, which is deferred but not canceled.
```

A later `rg` of the same pattern also found the previous FAIL log and the fix log documenting
the old `CURRENT_STATE.md` problem as before/after evidence.

### `git grep -n "Feature 3\|Marker Docker IPC" docs/CURRENT_DEVELOPMENT.md`

Exit code: 0. Relevant output:

```text
docs/CURRENT_DEVELOPMENT.md:75:### Feature 3: Marker Docker IPC Warm-Worker v1
docs/CURRENT_DEVELOPMENT.md:137:| RIS Marker Queue - Docker IPC Warm-Worker (v1) | ACTIVATED 2026-05-07 | Director activated 2026-05-07. Implementation shipped; live validation passed all revised functional gates (2026-05-08). Pending Codex closeout verification - see Active Feature 3. | N/A - now Active Feature 3 |
docs/CURRENT_DEVELOPMENT.md:138:| RIS L1 Marker Production Rollout - Validation | 2026-05-05 | ... Blocked on Docker IPC warm-worker (v1) Feature 3 closeout. ... | Docker IPC warm-worker (v1) Feature 3 closeout verification passes |
docs/CURRENT_DEVELOPMENT.md:162:... **Docker IPC warm-worker (v1) is now Active Feature 3** ...
docs/CURRENT_DEVELOPMENT.md:168:- **Marker Docker/Linux IPC Warm-Worker (v1) is NOW ACTIVE as Feature 3 ...** ... Do NOT start L2 or L4.
```

### `git diff --stat`

Exit code: 0. Output before this review dev log:

```text
 Dockerfile.ris                                     |   1 +
 docs/CURRENT_DEVELOPMENT.md                        |  35 +-
 docs/CURRENT_STATE.md                              |   2 +-
 docs/INDEX.md                                      |   9 +-
 ...026-05-03_academic-pipeline-hosting-decision.md |  15 +-
 .../ris-marker-structural-parser-scaffold.md       |   8 +-
 docs/obsidian-vault/.obsidian/workspace.json       |  16 +-
 .../.smart-env/event_logs/event_logs.ajson         | 211 ++++--
 ...s_Decision_-_Academic_Pipeline_Hosting_md.ajson |   5 +-
 ...cket_-_L3_v1_SVM_Topic_Filter_Training_md.ajson | 208 +++---
 ..._Marker_Canonical_Academic_Parse_Queue_md.ajson |  60 +-
 ...-_Marker_Structural_Parser_Integration_md.ajson |   5 +-
 ...Packet_-_Prefetch_Label_Discovery_Mode_md.ajson |  14 +-
 .../multi/Claude_Desktop_Current-Focus_md.ajson    |  57 +-
 .../Decision - Academic Pipeline Hosting.md        |   2 +-
 ...cket - Marker Canonical Academic Parse Queue.md |  13 +-
 ...acket - Marker Structural Parser Integration.md |   2 +-
 .../Work-Packet - Prefetch Label Discovery Mode.md |  19 +-
 .../obsidian-vault/Claude Desktop/Current-Focus.md |  15 +-
 packages/research/ingestion/fetchers.py            | 137 ++++
 packages/research/ingestion/marker_queue.py        | 111 +++-
 tests/test_ris_marker_queue.py                     | 724 +++++++++++++++++++++
 tools/cli/research_marker_queue.py                 | 133 +++-
 23 files changed, 1578 insertions(+), 224 deletions(-)
```

### `git diff --name-status`

Exit code: 0. Output before this review dev log:

```text
M	Dockerfile.ris
M	docs/CURRENT_DEVELOPMENT.md
M	docs/CURRENT_STATE.md
M	docs/INDEX.md
M	docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md
M	docs/features/ris-marker-structural-parser-scaffold.md
M	docs/obsidian-vault/.obsidian/workspace.json
M	docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
M	docs/obsidian-vault/.smart-env/multi/Claude_Desktop_09-Decisions_Decision_-_Academic_Pipeline_Hosting_md.ajson
M	docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_L3_v1_SVM_Topic_Filter_Training_md.ajson
M	docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Marker_Canonical_Academic_Parse_Queue_md.ajson
M	docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Marker_Structural_Parser_Integration_md.ajson
M	docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Prefetch_Label_Discovery_Mode_md.ajson
M	docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
M	docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md
M	docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md
M	docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md
M	docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Prefetch Label Discovery Mode.md
M	docs/obsidian-vault/Claude Desktop/Current-Focus.md
M	packages/research/ingestion/fetchers.py
M	packages/research/ingestion/marker_queue.py
M	tests/test_ris_marker_queue.py
M	tools/cli/research_marker_queue.py
```

### `git diff --name-status -- packages tools tests polytool config infra docker-compose.yml Dockerfile.ris artifacts`

Exit code: 0. Output:

```text
M	Dockerfile.ris
M	packages/research/ingestion/fetchers.py
M	packages/research/ingestion/marker_queue.py
M	tests/test_ris_marker_queue.py
M	tools/cli/research_marker_queue.py
```

### Focused inspection: stale active-looking timing language

Command:

```text
rg -n "5.?10|10 s/paper|10s|10 seconds|<=10s|<=10s" docs/CURRENT_DEVELOPMENT.md docs/CURRENT_STATE.md docs/INDEX.md docs/features/ris-marker-structural-parser-scaffold.md "docs/obsidian-vault/Claude Desktop/Current-Focus.md" "docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md" "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md" "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md" "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md" "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Prefetch Label Discovery Mode.md"
```

Exit code: 0. Blocking or suspect output:

```text
docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md:19:... on a modest GPU (NVIDIA 2070 Super or better) it runs in 5-10 seconds. Production cannot run on CPU.
docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md:102:- [ ] GPU performance baseline run: <=10 s/paper on the production host
docs/features/ris-marker-structural-parser-scaffold.md:89:for production throughput (~5-10 s/paper on RTX 2070 Super; 300 s timeout
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md:43:> - Models load once at worker start; papers 2+ expected <=10s on warm RTX 2070 Super VRAM
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md:56:> The operator has confirmed GPU availability ... Marker on this hardware is ~5-10s/paper per the survey's evidence - fast enough for production.
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md:126:... Does acceptance gate 2 ("<=10s warm") assume warm scheduler mode only?
```

Unicode symbols in terminal output were normalized to ASCII in this log where needed.

---

## Dirty-Tree Interpretation

The dirty implementation/test/Docker files are real, but they are not new evidence against the
docs fix because `docs/dev_logs/2026-05-08_fix-marker-ipc-revised-gate-all-docs-consistency.md`
records them as pre-existing before the fix session and unchanged after the fix session. This
satisfies the provenance part of item 9.

The current review dev log is the only file intentionally added by this session.

---

## Blockers Before Feature 3 Closeout

1. Supersede or correct the active hosting decision checklist item requiring `<=10 s/paper`.
2. Supersede or correct the current hosting decision claim that the 2070 Super runs Marker in
   5-10 seconds for production.
3. Supersede or correct the scaffold install section that still presents 5-10s/paper as
   production throughput.
4. Supersede or correct active-looking old throughput expectations in the Marker Structural
   Parser Integration work packet.
5. Optionally clean reference-material lines that repeat "papers 2+ expected <=10s warm" so
   they are explicitly historical/rejected under the 2026-05-08 gate revision.

---

## Codex Review Summary

Tier: docs-only closeout-readiness review. No code, tests, Docker, queues, artifacts, SVM
labels/models, L2, L4, trading, or validation runs were touched.

Issues found: current/affected docs still contain active-looking old `<=10s` or 5-10s Marker
throughput requirements/claims. Current state/deferred status blockers from the prior FAIL are
resolved.

Issues addressed: none. Per instruction, only this review dev log was created.
