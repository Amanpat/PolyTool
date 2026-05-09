# Codex Verify: Marker Structural Parser Frontmatter Timing Gate

Date: 2026-05-08
Type: read-only documentation consistency review
Scope: Final Structural Parser Integration timing-gate cleanup
Verdict: **PASS**

---

## Summary

PASS. Feature 3 closeout may run next.

The final Structural Parser Integration blocker from
`docs/dev_logs/2026-05-08_codex-verify-marker-last-timing-gate-references.md`
has been fixed. The current
`docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md`
frontmatter and top status now state that the old <=10s/paper timing gate is
historical/rejected/superseded, and the current blocker is Feature 3 closeout:
Marker Docker IPC Warm-Worker v1 pending Codex closeout verification.

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
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Single-Paper Validation Control Surface.md`
- `docs/features/ris-marker-structural-parser-scaffold.md`
- `docs/dev_logs/2026-05-08_codex-verify-marker-last-timing-gate-references.md`
- `docs/dev_logs/2026-05-08_fix-marker-structural-parser-frontmatter-timing-gate.md`

---

## Verification Results

### 1. Structural Parser Integration no longer presents <=10s/paper as current production gate

PASS.

`Work-Packet - Marker Structural Parser Integration.md` now labels all old timing
gate references in the frontmatter/top-status area as historical, rejected,
superseded, or revised:

- line 5: current blocker is Feature 3 closeout; old <=10s/paper timing gate is
  historical and rejected.
- line 31: the prior "fails <=10s/paper production gate" text is struck through
  and labeled historical/rejected/superseded.
- line 34: the old `~5-10s/paper` survey estimate is historical/superseded.
- line 43: revised gate is papers 2+ cold-load delta <=5s; old target rejected.
- line 56: old `~5-10s/paper` claim is struck through and superseded.
- line 96: old "typical arXiv paper in <=10 seconds" gate is struck through and
  superseded.
- line 126: old <=10s warm question is resolved by the 2026-05-08 revised gate.

### 2. Frontmatter/top status says old timing gate is historical/rejected/superseded

PASS.

Frontmatter now starts:

```text
blocked-reason: "CURRENT BLOCKER (2026-05-08): Feature 3 closeout -- Marker Docker IPC Warm-Worker v1 pending Codex closeout verification. HISTORICAL (2026-05-05, gate rejected 2026-05-08): old <=10s/paper timing gate was rejected as unrealistic; async parse queue has shipped. pdfplumber is legacy/debug only. Final embeddings must be Marker-only."
updated: 2026-05-08
```

The DANGER callout now says:

```text
Status: BLOCKED -- Pending Feature 3 Closeout (updated 2026-05-08; queue shipped)
```

### 3. Current blocker points to Feature 3 closeout

PASS.

The Structural Parser work packet no longer says the active blocker is queue
shipping or <=10s timing. It says queue shipped and the current blocker is
Feature 3 closeout verification.

### 4. Remaining timing references are safe

PASS.

Current-state/work-packet timing references are safe because they are explicitly
historical, rejected, superseded, struck through, or immediately adjacent to a
2026-05-08 gate-update note.

Safe current-doc examples:

- `docs/CURRENT_DEVELOPMENT.md:85,118` -- old gate rejected or later revised.
- `docs/CURRENT_STATE.md:1783` -- old timing gate rejected as unrealistic.
- `docs/features/ris-marker-structural-parser-scaffold.md:7,14,23,89` -- old
  gate/estimate rejected, superseded, or not validated.
- `docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md:19,102`
  -- old estimate/gate rejected or superseded; actual timings preserved.
- `Work-Packet - Marker Canonical Academic Parse Queue.md:50,61,102,181` --
  old gate rejected/revised/superseded. Line 23 is a dated 2026-05-05
  measurement in the same top block as the 2026-05-08 v1 gate update.
- `Work-Packet - Marker Single-Paper Validation Control Surface.md:14,21,29,37,151`
  -- line 37 explicitly updates/supersedes the 2026-05-05 measurement text.
- `Work-Packet - Marker Structural Parser Integration.md:5,31,34,43,56,96,126`
  -- all current timing matches are historical/rejected/superseded/revised.
- `docs/obsidian-vault/Claude Desktop/Current-Focus.md:42,53,54,57,81` --
  current line 42 records the revision; older lines are dated session history.

Historical dev-log matches from 2026-05-03 and 2026-05-05 preserve old evidence
and are not current-state blockers. Unrelated matches such as API polling "10
seconds", "5-10 minutes", and "5-10 trades" are not Marker production-gate
claims.

### 5. Revised gate and actual timings are preserved

PASS.

The revised gate is preserved:

- >=3 full academic PDFs in one warm session
- papers 2+ delta <=5s
- `body_source=marker`
- `ipc_warm_worker_used=true`
- no pdfplumber fallback
- no daemon-process error
- queue semantics intact
- clean shutdown

Actual timings remain visible:

- paper 1 = 45.55s
- paper 2 = 69.73s
- paper 3 = 48.31s

### 6. Feature 3 remains Active and pending closeout

PASS.

`docs/CURRENT_DEVELOPMENT.md` keeps Feature 3 under Active Features:

```text
### Feature 3: Marker Docker IPC Warm-Worker v1
```

It is pending Codex closeout verification and is not in Recently Completed.
`Test-Path -LiteralPath "docs/features/ris-marker-docker-ipc-warm-worker-v1.md"`
returned `False`, confirming the closeout feature doc has not been created yet.

### 7. L2/PaperQA2 and L4 remain blocked/stubbed

PASS.

Reviewed docs still say L2/PaperQA2 and L4 are not active:

- `docs/CURRENT_DEVELOPMENT.md:168` says: "Do NOT start L2 or L4."
- `Current-Focus.md:14` says L2 and L4 remain stubs and "Do NOT start L2 yet."
- `Current-Focus.md:30` says PaperQA2 is stubbed.
- `Current-Focus.md:32` says L4 Multi-source Academic Harvesters is stubbed.

### 8. No new implementation/test/Docker/artifact/SVM/trading changes by this docs fix

PASS with caveat.

The worktree already contains implementation/test/Docker changes from the
Marker IPC stream. The scoped implementation diff still shows:

```text
M	Dockerfile.ris
M	packages/research/ingestion/fetchers.py
M	packages/research/ingestion/marker_queue.py
M	tests/test_ris_marker_queue.py
M	tools/cli/research_marker_queue.py
```

The fix dev log records that this scoped list was identical before and after
the Structural Parser docs fix. I found no evidence that the final timing-gate
docs fix added implementation, test, Docker, artifact, SVM, or trading changes.

---

## Commands Run

### Repo state at start

`git status --short`

Exit code: 0. Key output:

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
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Marker_Single-Paper_Validation_Control_Surface_md.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Marker_Structural_Parser_Integration_md.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Prefetch_Label_Discovery_Mode_md.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
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
?? docs/dev_logs/2026-05-08_fix-marker-structural-parser-frontmatter-timing-gate.md
?? "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md"
?? packages/research/ingestion/marker_ipc_worker.py
?? tests/test_ris_marker_ipc_worker.py
```

The full output also contained many additional untracked 2026-05-07 and
2026-05-08 Marker dev logs.

`git log --oneline -5`

Exit code: 0.

```text
4b57400 SVM scoring complete
e482a6d L3 handoff
be8b4f2 fix(ris): resolve Codex FAIL blockers - Marker queue v0
7b81a7a Marker Parser added
a4fdcac docs(ris): close out Marker control surface validation - L1 still blocked
```

### Required command: timing grep

`git grep -n "<=10 s\|<=10s\|≤10s\|10s/paper\|10 seconds\|5-10\|5–10\|~5-10" docs`

Exit code: 0.

The exact command was run. Its raw output included generated Obsidian
`.smart-env` embedding JSON and was truncated by the Codex tool output display.
I therefore also ran the same timing pattern excluding generated Obsidian
`.smart-env` and `smart-connections/main.js` files for a readable semantic
review. Relevant non-generated matches:

```text
docs/CURRENT_DEVELOPMENT.md:85:- **Revised gate (Director 2026-05-08):** Original <=10s/paper timing gate rejected as unrealistic for full academic PDFs on RTX 2070 Super. Revised: >=3 full PDFs in one warm session; papers 2+ delta <=5s ...
docs/CURRENT_DEVELOPMENT.md:118:... L1 production blocked on <=10s/paper gate at time of closeout (**gate later revised 2026-05-08 -- see Active Feature 3**).
docs/CURRENT_STATE.md:1783:- Marker Docker IPC warm-worker v1 -- **Active Feature 3** ... Original <=10s/paper timing gate rejected as unrealistic (Director 2026-05-08).
docs/INDEX.md:155-165: 2026-05-08 verify/fix rows documenting rejected/superseded timing-gate cleanup.
docs/INDEX.md:186: historical 2026-05-05 control-surface closeout row preserving the old failed gate.
docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md:17,93,94,114: historical gate now annotated as rejected/revised.
docs/dev_logs/2026-05-05_*: historical logs preserving pre-revision acceptance assumptions/evidence.
docs/features/ris-marker-structural-parser-scaffold.md:7,14,23,89: old gate/estimate rejected, superseded, or not validated.
docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md:19,102: old estimate/gate rejected or superseded; measured timings preserved.
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md:23,50,61,102,181: 2026-05-05 measurement plus 2026-05-08 rejected/revised gate notes.
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Single-Paper Validation Control Surface.md:14,21,29,37,151: 2026-05-05 measurement plus line 37 superseding gate update.
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md:5,31,34,43,56,96,126: all historical/rejected/superseded/revised.
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Prefetch Label Discovery Mode.md:152: old timing gate rejected.
docs/obsidian-vault/Claude Desktop/Current-Focus.md:4,42,53,54,57,81: current line 42 records the revision; older lines are dated session history.
docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md:1472: unrelated API polling every 10 seconds.
docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md:120: unrelated 5-10 minute capture note.
docs/runbooks/research_eval_benchmark.md:179: unrelated indexing runtime note.
```

### Required command: Feature 3 grep

`git grep -n "Feature 3\|Marker Docker IPC" docs/CURRENT_DEVELOPMENT.md`

Exit code: 0.

```text
docs/CURRENT_DEVELOPMENT.md:75:### Feature 3: Marker Docker IPC Warm-Worker v1
docs/CURRENT_DEVELOPMENT.md:118:| Marker Single-Paper Validation Control Surface               | 2026-05-05 | RIS      | `run-academic-url` subcommand; process-boundary subprocess cancel; `parse_seconds` in result; 5 new tests. Validated: `body_source=marker`, `body_length=56923`, `parse_seconds=85.95s`. L1 production blocked on <=10s/paper gate at time of closeout (**gate later revised 2026-05-08 -- see Active Feature 3**). |
docs/CURRENT_DEVELOPMENT.md:137:| RIS Marker Queue -- Docker IPC Warm-Worker (v1)         | ACTIVATED 2026-05-07 | Director activated 2026-05-07. Implementation shipped; live validation passed all revised functional gates (2026-05-08). Pending Codex closeout verification -- see Active Feature 3. | N/A -- now Active Feature 3 |
docs/CURRENT_DEVELOPMENT.md:138:| RIS L1 Marker Production Rollout -- Validation          | 2026-05-05     | Operator chose Option A 2026-05-05: async parse queue. Queue v0 complete (Codex re-review PASS). Blocked on Docker IPC warm-worker (v1) Feature 3 closeout. pdfplumber is legacy/debug only. RAG-ready requires `body_source=marker`. | Docker IPC warm-worker (v1) Feature 3 closeout verification passes |
docs/CURRENT_DEVELOPMENT.md:162:- **RIS Marker Canonical Academic Parse Queue v0 is COMPLETE (2026-05-05).** ... **Docker IPC warm-worker (v1) is now Active Feature 3** -- activated 2026-05-07; revised functional gates PASS (2026-05-08 live validation). **L1 Marker Production Rollout remains PAUSED** -- blocked on Docker IPC warm-worker v1 Feature 3 closeout verification. Do NOT start L2 until warm-worker Feature 3 closeout completes.
docs/CURRENT_DEVELOPMENT.md:167:- **RIS L3 v1 SVM Topic Filter is COMPLETE (2026-05-07).** ... **Marker Docker IPC warm-worker v1 activated as Feature 3 (2026-05-07) -- active count is now 3 (max-3 reached).** All revised functional gates PASS (2026-05-08). Pending Codex closeout verification.
docs/CURRENT_DEVELOPMENT.md:168:- **Marker Docker/Linux IPC Warm-Worker (v1) is NOW ACTIVE as Feature 3 (activated 2026-05-07).** Implementation shipped; revised functional gates PASS (2026-05-08 live validation: 3 papers, papers 2+ delta <=5s, `body_source=marker`, `ipc_warm_worker_used=true`, no pdfplumber fallback, no daemon error, clean shutdown). Pending Codex closeout verification. L1 production rollout remains blocked until Feature 3 closeout completes. Do NOT start L2 or L4. Active count: 3 (max-3). See Active Feature 3 block above.
```

### Required command: scoped implementation diff

`git diff --name-status -- packages tools tests polytool config infra docker-compose.yml Dockerfile.ris artifacts`

Exit code: 0.

```text
M	Dockerfile.ris
M	packages/research/ingestion/fetchers.py
M	packages/research/ingestion/marker_queue.py
M	tests/test_ris_marker_queue.py
M	tools/cli/research_marker_queue.py
warning: in the working copy of 'Dockerfile.ris', LF will be replaced by CRLF the next time Git touches it
```

### Required command: git status

`git status --short`

Exit code: 0.

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
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Marker_Single-Paper_Validation_Control_Surface_md.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Marker_Structural_Parser_Integration_md.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Prefetch_Label_Discovery_Mode_md.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
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
?? docs/dev_logs/2026-05-07_claude-review-marker-docker-ipc-live-validation.md
?? docs/dev_logs/2026-05-07_claude-review-marker-docker-ipc-worker-integration.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-live-validation.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-v1-activation-clean.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-v1-activation-fixed.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-v1-activation.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-worker-implementation.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-worker-integration-fixed.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-ipc-live-validation-fixes.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-ipc-live-validation-rerun-plan-fixed.md
?? docs/dev_logs/2026-05-07_fix-marker-docker-ipc-warm-worker-v1-activation.md
?? docs/dev_logs/2026-05-07_fix-marker-docker-ipc-worker-integration.md
?? docs/dev_logs/2026-05-07_fix-marker-historical-l1-unblocked-claims.md
?? docs/dev_logs/2026-05-07_fix-marker-ipc-live-validation-blockers.md
?? docs/dev_logs/2026-05-07_fix-marker-ipc-live-validation-rerun-plan.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-live-validation.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-activation.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-context-map.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-worker-core.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-worker-queue-cli-integration.md
?? docs/dev_logs/2026-05-07_marker-ipc-live-validation-docker-preflight.md
?? docs/dev_logs/2026-05-07_marker-ipc-live-validation-preflight-queue.md
?? docs/dev_logs/2026-05-07_marker-ipc-live-validation-rerun-plan.md
?? docs/dev_logs/2026-05-08_claude-review-marker-ipc-daemonic-process-fix.md
?? docs/dev_logs/2026-05-08_codex-verify-marker-docker-ipc-warm-worker-goal-loop.md
?? docs/dev_logs/2026-05-08_codex-verify-marker-final-throughput-claims.md
?? docs/dev_logs/2026-05-08_codex-verify-marker-ipc-daemon-fix-direct-pdf-live-validation.md
?? docs/dev_logs/2026-05-08_codex-verify-marker-ipc-daemonic-process-fix.md
?? docs/dev_logs/2026-05-08_codex-verify-marker-ipc-direct-pdf-live-validation.md
?? docs/dev_logs/2026-05-08_codex-verify-marker-ipc-direct-pdf-validation-ready.md
?? docs/dev_logs/2026-05-08_codex-verify-marker-ipc-live-validation-final-preflight.md
?? docs/dev_logs/2026-05-08_codex-verify-marker-ipc-live-validation-preflight.md
?? docs/dev_logs/2026-05-08_codex-verify-marker-ipc-revised-gate-all-docs-consistency.md
?? docs/dev_logs/2026-05-08_codex-verify-marker-ipc-revised-gate-and-result-evidence.md
?? docs/dev_logs/2026-05-08_codex-verify-marker-ipc-revised-gate-doc-consistency.md
?? docs/dev_logs/2026-05-08_codex-verify-marker-last-timing-gate-references.md
?? docs/dev_logs/2026-05-08_fix-marker-final-throughput-claims.md
?? docs/dev_logs/2026-05-08_fix-marker-ipc-daemonic-process-error.md
?? docs/dev_logs/2026-05-08_fix-marker-ipc-revised-gate-all-docs-consistency.md
?? docs/dev_logs/2026-05-08_fix-marker-ipc-revised-gate-doc-consistency.md
?? docs/dev_logs/2026-05-08_fix-marker-ipc-validation-direct-pdf-path.md
?? docs/dev_logs/2026-05-08_fix-marker-last-timing-gate-references.md
?? docs/dev_logs/2026-05-08_fix-marker-structural-parser-frontmatter-timing-gate.md
?? docs/dev_logs/2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun-arxiv.md
?? docs/dev_logs/2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun.md
?? docs/dev_logs/2026-05-08_marker-ipc-daemon-fix-direct-pdf-live-validation.md
?? docs/dev_logs/2026-05-08_marker-ipc-direct-pdf-live-validation.md
?? docs/dev_logs/2026-05-08_marker-ipc-direct-pdf-validation-queue.md
?? docs/dev_logs/2026-05-08_marker-ipc-live-validation-preflight-completion.md
?? docs/dev_logs/2026-05-08_marker-ipc-revised-gate-and-result-evidence.md
?? docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Marker_Docker_IPC_Warm-Worker_v1_md.ajson
?? "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md"
?? packages/research/ingestion/marker_ipc_worker.py
?? tests/test_ris_marker_ipc_worker.py
```

### Required command: git diff stat

`git diff --stat`

Exit code: 0.

```text
 Dockerfile.ris                                     |   1 +
 docs/CURRENT_DEVELOPMENT.md                        |  35 +-
 docs/CURRENT_STATE.md                              |   2 +-
 docs/INDEX.md                                      |  15 +-
 ...026-05-03_academic-pipeline-hosting-decision.md |  18 +-
 .../ris-marker-structural-parser-scaffold.md       |  13 +-
 docs/obsidian-vault/.obsidian/workspace.json       |  22 +-
 .../.smart-env/event_logs/event_logs.ajson         | 297 +++++++--
 ...s_Decision_-_Academic_Pipeline_Hosting_md.ajson |  12 +-
 ...cket_-_L3_v1_SVM_Topic_Filter_Training_md.ajson | 208 +++---
 ..._Marker_Canonical_Academic_Parse_Queue_md.ajson |  64 +-
 ...ingle-Paper_Validation_Control_Surface_md.ajson |  91 ++-
 ...-_Marker_Structural_Parser_Integration_md.ajson |  19 +-
 ...Packet_-_Prefetch_Label_Discovery_Mode_md.ajson |  14 +-
 .../multi/Claude_Desktop_Current-Focus_md.ajson    |  57 +-
 .../Decision - Academic Pipeline Hosting.md        |   6 +-
 ...cket - Marker Canonical Academic Parse Queue.md |  15 +-
 ...rker Single-Paper Validation Control Surface.md |   6 +-
 ...acket - Marker Structural Parser Integration.md |  22 +-
 .../Work-Packet - Prefetch Label Discovery Mode.md |  19 +-
 .../obsidian-vault/Claude Desktop/Current-Focus.md |  15 +-
 packages/research/ingestion/fetchers.py            | 137 ++++
 packages/research/ingestion/marker_queue.py        | 111 +++-
 tests/test_ris_marker_queue.py                     | 724 +++++++++++++++++++++
 tools/cli/research_marker_queue.py                 | 133 +++-
 25 files changed, 1810 insertions(+), 246 deletions(-)
```

The command also emitted CRLF warnings for `Dockerfile.ris` and several
Obsidian files.

### Focused inspection: changed work packet

`git diff -- "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md"`

Exit code: 0. Key diff result:

```text
-blocked-reason: "Operator chose Option A 2026-05-05: async parse queue. L1 production rollout cannot ship as synchronous default (parse_seconds=85.95s >> <=10s/paper gate; cold-start dominates). Blocked pending [[Work-Packet - Marker Canonical Academic Parse Queue]] shipping. pdfplumber is legacy/debug only. Final embeddings must be Marker-only."
-updated: 2026-05-05
+blocked-reason: "CURRENT BLOCKER (2026-05-08): Feature 3 closeout -- Marker Docker IPC Warm-Worker v1 pending Codex closeout verification. HISTORICAL (2026-05-05, gate rejected 2026-05-08): old <=10s/paper timing gate was rejected as unrealistic; async parse queue has shipped. pdfplumber is legacy/debug only. Final embeddings must be Marker-only."
+updated: 2026-05-08

-> [!DANGER] Status: BLOCKED -- Awaiting Async Queue Implementation (updated 2026-05-05)
+> [!DANGER] Status: BLOCKED -- Pending Feature 3 Closeout (updated 2026-05-08; queue shipped)

-> - `parse_seconds=85.95s` ... **fails <=10s/paper production gate by ~8.6x**
+> - `parse_seconds=85.95s` ... ~~**fails <=10s/paper production gate by ~8.6x**~~ **(historical -- <=10s/paper gate rejected/superseded 2026-05-08; see revised gate below)**

-> **Root cause:** ... The ~5-10s/paper estimate ...
+> **Root cause (historical -- superseded 2026-05-08):** ... survey estimate rejected as unrealistic; measured warm-worker timings: 45.55s, 69.73s, 48.31s.

-> **This packet resumes when [[Work-Packet - Marker Canonical Academic Parse Queue]] ships.**
+> ~~**This packet resumes when [[Work-Packet - Marker Canonical Academic Parse Queue]] ships.**~~ **Queue shipped. Current blocker: Feature 3 closeout -- Marker Docker IPC Warm-Worker v1 pending Codex closeout verification.**
```

### Focused inspection: fix dev log

`Get-Content docs/dev_logs/*fix-marker-structural-parser-frontmatter-timing-gate*.md`

Exit code: 0. Key result:

```text
Codex review `docs/dev_logs/2026-05-08_codex-verify-marker-last-timing-gate-references.md`
returned FAIL. ... `Work-Packet - Marker Structural Parser Integration.md` still presented the old
`<=10s/paper` production gate in active-looking frontmatter and top-status language ...
The old gate was rejected/superseded on 2026-05-08 (Director decision). The
current blocker is Feature 3 closeout, not the queue shipping (queue has shipped).

No implementation, test, Docker, artifact, SVM, or trading files were touched
by this docs fix.

Whether Codex Closeout Verification May Rerun: Yes.
```

### Focused inspection: timings preserved

`git grep -n "45.55s\|69.73s\|48.31s" -- docs/CURRENT_DEVELOPMENT.md docs/CURRENT_STATE.md "docs/obsidian-vault/Claude Desktop/Current-Focus.md" "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md" "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md"`

Exit code: 0.

```text
docs/CURRENT_DEVELOPMENT.md:84:- **Live validation (2026-05-08):** 3 papers completed in one Docker/GPU warm-worker session. ... Measured timings: paper 1=45.55s (delta=26.76s cold-load), paper 2=69.73s (delta=0.13s warm), paper 3=48.31s (delta=0.22s warm).
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md:35:... measured warm-worker timings: 45.55s, 69.73s, 48.31s.
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md:43:... measured warm-worker timings: 45.55s, 69.73s, 48.31s; papers 2-3 deltas: 0.13s, 0.22s)
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md:56:... Measured warm IPC worker timings: 45.55s, 69.73s, 48.31s.
docs/obsidian-vault/Claude Desktop/Current-Focus.md:42:... Actual timings preserved and not hidden: 45.55s, 69.73s, 48.31s. Feature 3 NOT marked complete ...
```

### Focused inspection: L2/L4 status

`git grep -n "PaperQA2\|L4\|stub" -- docs/CURRENT_DEVELOPMENT.md "docs/obsidian-vault/Claude Desktop/Current-Focus.md" "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md"`

Exit code: 0.

```text
docs/CURRENT_DEVELOPMENT.md:168:... L1 production rollout remains blocked until Feature 3 closeout completes. Do NOT start L2 or L4. Active count: 3 (max-3). See Active Feature 3 block above.
docs/obsidian-vault/Claude Desktop/Current-Focus.md:14:... L2 and L4 remain stubs. Do NOT start L2 yet.
docs/obsidian-vault/Claude Desktop/Current-Focus.md:30:| L2 | [[Work-Packet - PaperQA2 RAG Control Flow]] | Stub. Activation gated on L5 baseline + L1 production. |
docs/obsidian-vault/Claude Desktop/Current-Focus.md:32:| L4 | [[Work-Packet - Multi-source Academic Harvesters]] | Stub. Activation gated on L1 + L3. Updated 2026-04-29 to add backfill-vs-monitoring distinction. |
```

### Focused inspection: Feature 3 feature doc not created

`Test-Path -LiteralPath "docs/features/ris-marker-docker-ipc-warm-worker-v1.md"`

Exit code: 0.

```text
False
```

---

## Commands Not Run

No validation, tests, Docker rebuild/prune, Docker runtime commands, queue
mutation, artifact mutation, SVM commands, or trading commands were run.

I did not run `python -m polytool --help` because this review was explicitly
constrained to the listed read-only verification commands and said not to run
validation. No code changes were made.

---

## Closeout Verdict

Feature 3 closeout may run next.

Blockers/fixes: none from this review.

---

## Codex Review Summary

Tier: docs-only closeout-readiness review.

Issues found: none blocking. The previous active-looking Structural Parser
frontmatter/top-status <=10s/paper blocker is fixed.

Issues addressed: none in source docs. Per instruction, only this review dev
log was created.
