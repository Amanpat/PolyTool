# Codex Verify: Marker IPC Revised Gate Doc Consistency

Date: 2026-05-08
Type: read-only documentation consistency review
Scope: Feature 3 Marker Docker IPC Warm-Worker v1 revised gate closeout readiness
Verdict: FAIL

---

## Summary

FAIL. Feature 3 closeout should NOT run next yet.

The main four revised-gate docs are mostly aligned: `CURRENT_DEVELOPMENT.md`,
`Current-Focus.md`, `INDEX.md`, and the active Marker Docker IPC work packet now describe
Feature 3 as active/pending closeout, use the revised functional gate, preserve the real
timings, and say L2/PaperQA2 plus L4 remain blocked/stubbed.

However, the broader docs set still has current feature/work-packet references that require
or imply the old `<=10s/paper` gate, and `CURRENT_STATE.md` still says Marker Docker IPC
warm-worker v1 is deferred from queue v0. Those are not clearly superseded in place. The
repo-level status/diff also still shows code, test, Docker, and SVM smart-env file changes in
the worktree, so the requested "no code/tests/Docker/SVM files changed during this docs fix"
check is not proven by the command output.

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
- `docs/dev_logs/2026-05-08_codex-verify-marker-ipc-revised-gate-and-result-evidence.md`
- `docs/dev_logs/2026-05-08_fix-marker-ipc-revised-gate-doc-consistency.md`
- `docs/dev_logs/2026-05-08_marker-ipc-revised-gate-and-result-evidence.md`
- `docs/features/ris-marker-structural-parser-scaffold.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Prefetch Label Discovery Mode.md`
- Current diffs for `docs/CURRENT_DEVELOPMENT.md`, `docs/INDEX.md`,
  `docs/obsidian-vault/Claude Desktop/Current-Focus.md`,
  `docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md`, and
  `docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md`

---

## Revised Gate Verification

PASS for the core revised-gate docs:

- `docs/CURRENT_DEVELOPMENT.md` has active `Feature 3: Marker Docker IPC Warm-Worker v1`,
  status "Implementation complete - all revised functional gates PASS - pending Codex
  closeout verification."
- The Paused/Deferred row for "RIS Marker Queue - Docker IPC Warm-Worker (v1)" is marked
  `ACTIVATED 2026-05-07` and points to Active Feature 3.
- `docs/obsidian-vault/Claude Desktop/Current-Focus.md` says Marker Docker IPC warm-worker
  v1 is Active Feature 3, all revised gates pass, and L1 remains blocked only until Feature 3
  closeout verification.
- `docs/INDEX.md` summarizes the revised gate and the actual timings.
- The active Marker Docker IPC work packet states the old `<=10s/paper` timing gate was
  rejected as unrealistic and replaced by the functional warm-worker gate.

Revised gate currently documented:

- At least 3 full academic PDFs in one warm session.
- Papers 2+ delta (`total_seconds - parse_seconds`) <=5s.
- `body_source=marker` for all papers.
- `ipc_warm_worker_used=true` for all papers.
- No pdfplumber fallback.
- No daemon-process error.
- Queue semantics intact.
- Clean shutdown.

Actual timings are preserved honestly in the core docs:

- Paper 1: 45.55s parse, 72.31s total, delta 26.76s.
- Paper 2: 69.73s parse, 69.86s total, delta 0.13s.
- Paper 3: 48.31s parse, 48.53s total, delta 0.22s.

L2/PaperQA2 and L4 remain blocked/stubbed in the core docs:

- `Current-Focus.md`: L2 is stubbed; L4 is stubbed.
- Marker Docker IPC work packet: "No L2 work" and "No L4 work"; L2 remains stubbed and
  blocked until closeout.
- `CURRENT_DEVELOPMENT.md`: do not start L2 or L4.

Feature 3 has not been moved to Recently Completed:

- `CURRENT_DEVELOPMENT.md` has Feature 3 under Active Features.
- The Recently Completed table starts after that section and does not contain Marker Docker IPC
  Warm-Worker v1.
- `docs/features/ris-marker-docker-ipc-warm-worker-v1.md` is not present; it is still a
  pending DoD checkbox.

---

## Blocking Findings

### Blocking 1 - Current docs still contain old active `<=10s` requirements

The required `git grep` and follow-up focused `rg` show remaining non-historical current docs
with old timing-gate language:

- `docs/features/ris-marker-structural-parser-scaffold.md:14` says L1 resumes when the async
  queue ships and the warm worker validates `>=3 papers at <=10s/paper`.
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md:96`
  has an acceptance gate requiring Marker to parse a typical arXiv paper in `<=10 seconds`.
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md:60`
  says the warm GPU worker processes the queue at `<=10s/paper` post-load; line 101 still
  requires papers 2-N at `<=10s/paper`.
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Prefetch Label Discovery Mode.md:154`
  says L1 remains blocked until IPC validates `>=3 papers at <=10s/paper`; line 157 repeats
  the old resume trigger.

Some `<=10s` hits are correctly historical/rejected/superseded, such as the current Marker
Docker IPC work packet's struck-through gates and Director Gate Revision section. The files
above are the remaining problem: they are feature/work-packet docs, not only historical dev logs,
and their old gate text is not clearly superseded in place.

### Blocking 2 - `CURRENT_STATE.md` still says Marker IPC is deferred

`docs/CURRENT_STATE.md` still contains:

```text
L2 PaperQA2 activation - gated on L1 Marker Docker IPC warm-worker v1.
Marker Docker IPC warm-worker v1 - deferred from Queue v0 (2026-05-05); NOT canceled.
```

That conflicts with `CURRENT_DEVELOPMENT.md`, where the same work is Active Feature 3 pending
closeout verification. Since `CURRENT_STATE.md` is a current repo-truth document and has higher
document priority than `CURRENT_DEVELOPMENT.md`, this is a closeout blocker unless the operator
explicitly says `CURRENT_STATE.md` is intentionally stale until closeout.

### Blocking 3 - Repo-level no-code/no-Docker/no-SVM check is not satisfied by current output

The docs-fix dev log claims no code, tests, or artifacts were touched. The current worktree
still includes modified/untracked code, tests, Docker, and SVM smart-env files. These may be
pre-existing Feature 3 implementation changes rather than docs-fix changes, but the requested
repo-level commands cannot prove item 9 as written.

Examples from `git status --short` and `git diff --name-status`:

- `M Dockerfile.ris`
- `M packages/research/ingestion/fetchers.py`
- `M packages/research/ingestion/marker_queue.py`
- `M tools/cli/research_marker_queue.py`
- `M tests/test_ris_marker_queue.py`
- `?? packages/research/ingestion/marker_ipc_worker.py`
- `?? tests/test_ris_marker_ipc_worker.py`
- `M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_L3_v1_SVM_Topic_Filter_Training_md.ajson`

No tracked `artifacts/`, trading, L2, or L4 source paths were shown by `git diff --name-status`.

---

## Commands Run

### `git status --short`

Exit code: 0. Output included:

```text
 M Dockerfile.ris
 M docs/CURRENT_DEVELOPMENT.md
 M docs/INDEX.md
 M docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md
 M docs/obsidian-vault/.obsidian/workspace.json
 M docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_09-Decisions_Decision_-_Academic_Pipeline_Hosting_md.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_L3_v1_SVM_Topic_Filter_Training_md.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
 M "docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md"
 M "docs/obsidian-vault/Claude Desktop/Current-Focus.md"
 M packages/research/ingestion/fetchers.py
 M packages/research/ingestion/marker_queue.py
 M tests/test_ris_marker_queue.py
 M tools/cli/research_marker_queue.py
?? docs/dev_logs/2026-05-08_codex-verify-marker-ipc-revised-gate-and-result-evidence.md
?? docs/dev_logs/2026-05-08_fix-marker-ipc-revised-gate-doc-consistency.md
?? docs/dev_logs/2026-05-08_marker-ipc-revised-gate-and-result-evidence.md
?? "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md"
?? packages/research/ingestion/marker_ipc_worker.py
?? tests/test_ris_marker_ipc_worker.py
```

There were many additional untracked 2026-05-07 and 2026-05-08 Marker IPC dev logs.

### `git log --oneline -5`

Exit code: 0.

```text
4b57400 SVM scoring complete
e482a6d L3 handoff
be8b4f2 fix(ris): resolve Codex FAIL blockers - Marker queue v0
7b81a7a Marker Parser added
a4fdcac docs(ris): close out Marker control surface validation - L1 still blocked
```

### `python -m polytool --help`

Exit code: 0. CLI loaded successfully and listed `research-marker-queue`.

### `git grep -n "<=10s\|<=10s\|10s/paper\|10 seconds" docs`

Exit code: 0. The command returned many matches. Relevant exact matches include:

```text
docs/CURRENT_DEVELOPMENT.md:85:- **Revised gate (Director 2026-05-08):** Original <=10s/paper timing gate rejected as unrealistic for full academic PDFs on RTX 2070 Super. Revised: >=3 full PDFs in one warm session; papers 2+ delta <=5s ...
docs/CURRENT_DEVELOPMENT.md:118:| Marker Single-Paper Validation Control Surface ... L1 production blocked on <=10s/paper gate at time of closeout (**gate later revised 2026-05-08 - see Active Feature 3**). |
docs/INDEX.md:157:| [Marker IPC - Revised Gate and Result Evidence] ... Director gate revision: <=10s/paper rejected as unrealistic; revised to >=3 papers warm, papers 2+ delta <=5s. ...
docs/features/ris-marker-structural-parser-scaffold.md:14:> L1 production rollout resumes when the async queue ships and warm worker validates >=3 papers at <=10s/paper.
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md:96:2. **GPU performance baseline.** On the production host (per the hosting decision), Marker parses a typical arXiv paper in <=10 seconds.
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md:60:2. A long-running GPU worker processes the queue with warm models (<=10s/paper post-load on RTX 2070 Super)
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md:101:3. **No per-paper cold-load after first paper.** Papers 2-N in the same worker session show `parse_seconds` consistent with warm-model throughput: <=10s/paper ...
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Prefetch Label Discovery Mode.md:154:> blocked until the IPC warm-worker validates >=3 papers at <=10s/paper (papers 2+).
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Prefetch Label Discovery Mode.md:157:> warm (<=10s/paper for papers 2+). See Paused/Deferred table in `CURRENT_DEVELOPMENT.md`.
```

Note: PowerShell rendered Unicode `<=`/`>=` inconsistently in some terminal output; the files
contain Unicode symbols in several places. The semantic matches above are exact to the
reviewed text with Unicode normalized to ASCII for this log.

### `git grep -n "Paused / Deferred\|Paused/Deferred\|Feature 3\|Marker Docker IPC" docs/CURRENT_DEVELOPMENT.md`

Exit code: 0. Relevant output:

```text
docs/CURRENT_DEVELOPMENT.md:75:### Feature 3: Marker Docker IPC Warm-Worker v1
docs/CURRENT_DEVELOPMENT.md:133:## Paused / Deferred
docs/CURRENT_DEVELOPMENT.md:137:| RIS Marker Queue - Docker IPC Warm-Worker (v1) | ACTIVATED 2026-05-07 | ... see Active Feature 3. | N/A - now Active Feature 3 |
docs/CURRENT_DEVELOPMENT.md:138:| RIS L1 Marker Production Rollout - Validation | 2026-05-05 | ... Blocked on Docker IPC warm-worker (v1) Feature 3 closeout. ... | Docker IPC warm-worker (v1) Feature 3 closeout verification passes |
docs/CURRENT_DEVELOPMENT.md:168:- **Marker Docker/Linux IPC Warm-Worker (v1) is NOW ACTIVE as Feature 3 ...** ... Do NOT start L2 or L4.
```

### `git diff --stat`

Exit code: 0.

```text
 Dockerfile.ris                                     |   1 +
 docs/CURRENT_DEVELOPMENT.md                        |  35 +-
 docs/INDEX.md                                      |   7 +-
 ...026-05-03_academic-pipeline-hosting-decision.md |  15 +-
 docs/obsidian-vault/.obsidian/workspace.json       |  10 +-
 .../.smart-env/event_logs/event_logs.ajson         | 184 ++++--
 ...s_Decision_-_Academic_Pipeline_Hosting_md.ajson |   5 +-
 ...cket_-_L3_v1_SVM_Topic_Filter_Training_md.ajson | 208 +++---
 .../multi/Claude_Desktop_Current-Focus_md.ajson    |  57 +-
 .../Decision - Academic Pipeline Hosting.md        |   2 +-
 .../obsidian-vault/Claude Desktop/Current-Focus.md |  15 +-
 packages/research/ingestion/fetchers.py            | 137 ++++
 packages/research/ingestion/marker_queue.py        | 111 +++-
 tests/test_ris_marker_queue.py                     | 724 +++++++++++++++++++++
 tools/cli/research_marker_queue.py                 | 133 +++-
 15 files changed, 1447 insertions(+), 197 deletions(-)
```

PowerShell also emitted line-ending warnings for several working-copy files.

### `git diff --name-status`

Exit code: 0.

```text
M	Dockerfile.ris
M	docs/CURRENT_DEVELOPMENT.md
M	docs/INDEX.md
M	docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md
M	docs/obsidian-vault/.obsidian/workspace.json
M	docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
M	docs/obsidian-vault/.smart-env/multi/Claude_Desktop_09-Decisions_Decision_-_Academic_Pipeline_Hosting_md.ajson
M	docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_L3_v1_SVM_Topic_Filter_Training_md.ajson
M	docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
M	docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md
M	docs/obsidian-vault/Claude Desktop/Current-Focus.md
M	packages/research/ingestion/fetchers.py
M	packages/research/ingestion/marker_queue.py
M	tests/test_ris_marker_queue.py
M	tools/cli/research_marker_queue.py
```

### Additional focused inspection commands

I also ran focused `rg` searches and `git diff -- <path>` inspections to classify the grep
matches. Relevant results:

```text
docs/CURRENT_STATE.md:1782:- L2 PaperQA2 activation - gated on L1 Marker Docker IPC warm-worker v1.
docs/CURRENT_STATE.md:1783:- Marker Docker IPC warm-worker v1 - deferred from Queue v0 (2026-05-05); NOT canceled.
docs/CURRENT_DEVELOPMENT.md:75:### Feature 3: Marker Docker IPC Warm-Worker v1
docs/CURRENT_DEVELOPMENT.md:82:- **Current step:** Await Codex closeout verification. After verification passes: create `docs/features/ris-marker-docker-ipc-warm-worker-v1.md`, update INDEX.md, move to Recently Completed.
docs/CURRENT_DEVELOPMENT.md:95:  - [ ] `docs/features/ris-marker-docker-ipc-warm-worker-v1.md` created
```

---

## Closeout Readiness

Feature 3 closeout may NOT run next.

Required fixes before closeout:

- Update or explicitly supersede current feature/work-packet docs that still require or imply
  `<=10s/paper` for Marker full academic PDFs.
- Update `CURRENT_STATE.md` or explicitly record why its "deferred from Queue v0" Marker IPC
  line is intentionally stale until closeout.
- Clarify the docs-fix evidence against the dirty worktree: either isolate/stage the docs-fix
  files separately or document that code/test/Docker/SVM smart-env changes predated the docs fix.

---

## Codex Review Summary

Tier: docs-only closeout-readiness review. Trading, SVM enforcement, L2, L4, Docker, queue
mutation, and live validation were not run.

Issues found: three blocking documentation/provenance issues above. Core revised-gate docs are
largely aligned, but the broader docs set is not yet consistent enough to run Feature 3
closeout.

Issues addressed: none. Per instruction, only this review dev log was created.
