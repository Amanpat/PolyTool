# Codex Verify: Marker Docker IPC Warm-Worker v1 Closeout

Date: 2026-05-08
Type: docs-only closeout verification
Scope: Feature 3 - Marker Docker IPC Warm-Worker v1 closeout under revised functional gate
Verdict: **FAIL**

---

## Summary

FAIL. The core completion protocol is present in the primary docs: the feature doc exists,
`docs/INDEX.md` links the feature doc and closeout dev log, and
`docs/CURRENT_DEVELOPMENT.md` moved Marker Docker IPC Warm-Worker v1 from Active to
Recently Completed. `CURRENT_DEVELOPMENT.md` now has only Feature 1 and Feature 2 active.

The revised functional gate itself is documented correctly: three full PDFs completed in
one warm session, papers 2+ deltas are 0.13s and 0.22s, `body_source=marker`,
`ipc_warm_worker_used=true`, no pdfplumber fallback, no daemon error, and clean shutdown.
The real timings remain visible: 45.55s, 69.73s, 48.31s. The docs do not claim
`<=10s/paper` was achieved.

Closeout is not accepted because two current closeout context docs still contain
active-looking stale language that says closeout is pending / Feature 3 is not yet closed:

- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md:113`
  says: "Feature 3 is NOT yet closed -- closeout verification by Codex required before
  Feature 3 is marked complete and L1 production is unblocked."
- `docs/obsidian-vault/Claude Desktop/Current-Focus.md:20` says L1 remains blocked by
  Marker Docker IPC warm-worker Feature 3 closeout verification and points to "Active
  Feature 3" in `CURRENT_DEVELOPMENT.md`.

These conflict with the closeout state in `CURRENT_DEVELOPMENT.md`, `CURRENT_STATE.md`,
`docs/INDEX.md`, the feature doc, and the top of the same work packet.

---

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/CURRENT_STATE.md`
- `docs/INDEX.md`
- `docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md`
- `docs/obsidian-vault/Claude Desktop/Current-Focus.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`
- `docs/dev_logs/2026-05-08_marker-docker-ipc-warm-worker-v1-closeout.md`
- `docs/dev_logs/2026-05-08_codex-verify-marker-structural-parser-frontmatter-timing-gate.md`

---

## Verification Matrix

| Check | Result | Notes |
| --- | --- | --- |
| Feature doc exists and describes shipped work | PASS | `Test-Path` returned `True`; feature doc covers IPC worker, queue integration, direct-PDF path, CLI, result persistence, revised gate, non-goals, tests, and follow-ons. |
| `docs/INDEX.md` links feature doc and closeout dev log | PASS | Lines 121 and 156 link both. |
| `docs/CURRENT_DEVELOPMENT.md` moved Feature 3 to Recently Completed | PASS | Feature appears in Recently Completed at line 92. |
| Active count is now 2; no replacement Feature 3 | PASS | Active headings are only Feature 1 and Feature 2. |
| `CURRENT_STATE.md` says blocker resolved under revised gate | PASS | Lines 1783 and 1803-1855 mark warm-worker complete and L1 unblocked. |
| Actual timings preserved | PASS | 45.55s, 69.73s, 48.31s appear in closeout docs. |
| No claim that `<=10s/paper` was achieved | PASS | Current references reject/supersede the old gate or preserve historical context. |
| No claim full academic/RIS pipeline complete | PASS | `rg` found no full academic/RIS pipeline complete claim in reviewed current docs. |
| L2/PaperQA2 and L4 remain blocked/stubbed | PASS | Current docs say L2 and L4 remain stubbed/gated; no activation found. |
| No implementation/test/Docker changes by closeout | PASS with caveat | Current tree has feature-stream code/test/Docker diffs, but the prior structural-parser verification log already showed the same scoped implementation diff before closeout. No evidence closeout added new implementation/test/Docker changes. |
| Completion protocol complete | PASS | Feature doc created, INDEX updated, CURRENT_DEVELOPMENT moved entry to Recently Completed. |
| Feature 3 closeout accepted | FAIL | Stale active-looking closeout-pending language remains in Current-Focus and the work packet. |

---

## Revised Gate Verification

Revised functional gate status: PASS.

Evidence preserved in reviewed docs:

- `>=3` full academic PDFs in one warm session: done=3, failed=0.
- Papers 2+ delta `<=5s`: paper 2 delta 0.13s, paper 3 delta 0.22s.
- `body_source=marker`: all three.
- `ipc_warm_worker_used=true`: all three.
- No pdfplumber fallback.
- No daemon-process error.
- Clean shutdown.
- Persisted `ipc_warm_worker_used` covered by 4 new persistence tests in the closeout evidence.

The revised gate is acceptable; the closeout documentation state is not fully consistent.

---

## Completion Protocol Status

Completion protocol items requested by `docs/CURRENT_DEVELOPMENT.md`:

1. Feature doc created: PASS.
2. `docs/INDEX.md` updated: PASS.
3. Entry moved to Recently Completed: PASS.

Closeout acceptance still FAILS because the required read-first closeout context contains
contradictory "Feature 3 not yet closed" / "closeout verification pending" language.

---

## Blockers / Fixes Needed

Blocking fixes before accepting closeout:

1. Update `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md:113`
   from "Feature 3 is NOT yet closed" to the post-closeout state: Feature 3 closed
   2026-05-08 under the revised functional gate; L1 production rollout unblocked;
   L2 remains gated on L1 production rollout completion.
2. Update `docs/obsidian-vault/Claude Desktop/Current-Focus.md:20` to remove the stale
   "L1 remains blocked by Marker Docker IPC warm-worker (v1) Feature 3 closeout
   verification" claim and the stale "Active Feature 3" pointer.

Optional cleanup:

- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md:78`
  still phrases the L2 gate as waiting until closeout verification completes. Since
  closeout is now intended to be complete, this should be tightened to "L2 remains
  stubbed and gated on L1 production rollout completion." The top callout already says
  this correctly.

---

## Commands Run

### `git status --short`

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
?? docs/dev_logs/2026-05-08_codex-verify-marker-structural-parser-frontmatter-timing-gate.md
?? docs/dev_logs/2026-05-08_fix-marker-final-throughput-claims.md
?? docs/dev_logs/2026-05-08_fix-marker-ipc-daemonic-process-error.md
?? docs/dev_logs/2026-05-08_fix-marker-ipc-revised-gate-all-docs-consistency.md
?? docs/dev_logs/2026-05-08_fix-marker-ipc-revised-gate-doc-consistency.md
?? docs/dev_logs/2026-05-08_fix-marker-ipc-validation-direct-pdf-path.md
?? docs/dev_logs/2026-05-08_fix-marker-last-timing-gate-references.md
?? docs/dev_logs/2026-05-08_fix-marker-structural-parser-frontmatter-timing-gate.md
?? docs/dev_logs/2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun-arxiv.md
?? docs/dev_logs/2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun.md
?? docs/dev_logs/2026-05-08_marker-docker-ipc-warm-worker-v1-closeout.md
?? docs/dev_logs/2026-05-08_marker-ipc-daemon-fix-direct-pdf-live-validation.md
?? docs/dev_logs/2026-05-08_marker-ipc-direct-pdf-live-validation.md
?? docs/dev_logs/2026-05-08_marker-ipc-direct-pdf-validation-queue.md
?? docs/dev_logs/2026-05-08_marker-ipc-live-validation-preflight-completion.md
?? docs/dev_logs/2026-05-08_marker-ipc-revised-gate-and-result-evidence.md
?? docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md
?? docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Marker_Docker_IPC_Warm-Worker_v1_md.ajson
?? "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md"
?? packages/research/ingestion/marker_ipc_worker.py
?? tests/test_ris_marker_ipc_worker.py
```

### `git diff --stat`

Exit code: 0.

```text
 Dockerfile.ris                                     |   1 +
 docs/CURRENT_DEVELOPMENT.md                        |  13 +-
 docs/CURRENT_STATE.md                              |  58 +-
 docs/INDEX.md                                      |  17 +-
 ...026-05-03_academic-pipeline-hosting-decision.md |  18 +-
 .../ris-marker-structural-parser-scaffold.md       |  13 +-
 docs/obsidian-vault/.obsidian/workspace.json       |  22 +-
 .../.smart-env/event_logs/event_logs.ajson         | 347 ++++++++--
 ...s_Decision_-_Academic_Pipeline_Hosting_md.ajson |  12 +-
 ...cket_-_L3_v1_SVM_Topic_Filter_Training_md.ajson | 208 +++---
 ..._Marker_Canonical_Academic_Parse_Queue_md.ajson |  64 +-
 ...ingle-Paper_Validation_Control_Surface_md.ajson |  91 ++-
 ...-_Marker_Structural_Parser_Integration_md.ajson |  19 +-
 ...Packet_-_Prefetch_Label_Discovery_Mode_md.ajson |  14 +-
 .../multi/Claude_Desktop_Current-Focus_md.ajson    |  77 ++-
 .../Decision - Academic Pipeline Hosting.md        |   6 +-
 ...cket - Marker Canonical Academic Parse Queue.md |  15 +-
 ...rker Single-Paper Validation Control Surface.md |   6 +-
 ...acket - Marker Structural Parser Integration.md |  22 +-
 .../Work-Packet - Prefetch Label Discovery Mode.md |  19 +-
 .../obsidian-vault/Claude Desktop/Current-Focus.md |  16 +-
 packages/research/ingestion/fetchers.py            | 137 ++++
 packages/research/ingestion/marker_queue.py        | 111 +++-
 tests/test_ris_marker_queue.py                     | 724 +++++++++++++++++++++
 tools/cli/research_marker_queue.py                 | 133 +++-
 25 files changed, 1916 insertions(+), 247 deletions(-)
warning: in the working copy of 'Dockerfile.ris', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.obsidian/workspace.json', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_09-Decisions_Decision_-_Academic_Pipeline_Hosting_md.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_L3_v1_SVM_Topic_Filter_Training_md.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Marker_Canonical_Academic_Parse_Queue_md.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Marker_Single-Paper_Validation_Control_Surface_md.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Marker_Structural_Parser_Integration_md.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Prefetch_Label_Discovery_Mode_md.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Single-Paper Validation Control Surface.md', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Prefetch Label Discovery Mode.md', LF will be replaced by CRLF the next time Git touches it
```

### `git diff --name-status`

Exit code: 0.

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
M	docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Marker_Single-Paper_Validation_Control_Surface_md.ajson
M	docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Marker_Structural_Parser_Integration_md.ajson
M	docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Prefetch_Label_Discovery_Mode_md.ajson
M	docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
M	docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md
M	docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md
M	docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Single-Paper Validation Control Surface.md
M	docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md
M	docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Prefetch Label Discovery Mode.md
M	docs/obsidian-vault/Claude Desktop/Current-Focus.md
M	packages/research/ingestion/fetchers.py
M	packages/research/ingestion/marker_queue.py
M	tests/test_ris_marker_queue.py
M	tools/cli/research_marker_queue.py
warning: in the working copy of 'Dockerfile.ris', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.obsidian/workspace.json', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_09-Decisions_Decision_-_Academic_Pipeline_Hosting_md.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_L3_v1_SVM_Topic_Filter_Training_md.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Marker_Canonical_Academic_Parse_Queue_md.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Marker_Single-Paper_Validation_Control_Surface_md.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Marker_Structural_Parser_Integration_md.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Prefetch_Label_Discovery_Mode_md.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Single-Paper Validation Control Surface.md', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Prefetch Label Discovery Mode.md', LF will be replaced by CRLF the next time Git touches it
```

### `git diff --name-status -- packages tools tests polytool config infra docker-compose.yml Dockerfile.ris artifacts`

Exit code: 0.

```text
M	Dockerfile.ris
M	packages/research/ingestion/fetchers.py
M	packages/research/ingestion/marker_queue.py
M	tests/test_ris_marker_queue.py
M	tools/cli/research_marker_queue.py
warning: in the working copy of 'Dockerfile.ris', LF will be replaced by CRLF the next time Git touches it
```

Additional untracked scoped status:

`git status --short -- packages tools tests polytool config infra docker-compose.yml Dockerfile.ris artifacts`

Exit code: 0.

```text
 M Dockerfile.ris
 M packages/research/ingestion/fetchers.py
 M packages/research/ingestion/marker_queue.py
 M tests/test_ris_marker_queue.py
 M tools/cli/research_marker_queue.py
?? packages/research/ingestion/marker_ipc_worker.py
?? tests/test_ris_marker_ipc_worker.py
```

### `git grep -n "Feature 3\|Marker Docker IPC" docs/CURRENT_DEVELOPMENT.md`

Exit code: 0.

```text
docs/CURRENT_DEVELOPMENT.md:92:| Marker Docker IPC Warm-Worker v1                             | 2026-05-08 | RIS      | `docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md` — IPC warm-worker subprocess; daemon=False fix; `ipc_warm_worker_used` persisted. **Revised gate (Director 2026-05-08): ≥3 full PDFs/session; papers 2+ delta ≤5s; `body_source=marker`; `ipc_warm_worker_used=true`; no pdfplumber fallback; no daemon error; clean shutdown.** Measured: 45.55s/69.73s/48.31s; papers 2–3 delta=0.13s/0.22s. Original ≤10s/paper gate rejected as unrealistic. L1 Marker production rollout UNBLOCKED. L2/L4 remain stubs. Dev log: `docs/dev_logs/2026-05-08_marker-docker-ipc-warm-worker-v1-closeout.md`. |
docs/CURRENT_DEVELOPMENT.md:96:| Marker Single-Paper Validation Control Surface               | 2026-05-05 | RIS      | `run-academic-url` subcommand; process-boundary subprocess cancel; `parse_seconds` in result; 5 new tests. Validated: `body_source=marker`, `body_length=56923`, `parse_seconds=85.95s`. L1 production blocked on ≤10s/paper gate at time of closeout (**gate later revised/superseded 2026-05-08 — see Marker Docker IPC Warm-Worker v1 closeout above**). |
docs/CURRENT_DEVELOPMENT.md:116:| RIS L1 Marker Production Rollout — Validation          | 2026-05-05     | Operator chose Option A 2026-05-05: async parse queue. Queue v0 complete; warm-worker v1 complete (Feature 3 closed 2026-05-08). pdfplumber is legacy/debug only. RAG-ready requires `body_source=marker`. | ✅ Resume trigger met 2026-05-08 — L1 can proceed at next explicit Director workpacket |
docs/CURRENT_DEVELOPMENT.md:140:- **RIS Marker Canonical Academic Parse Queue v0 is COMPLETE (2026-05-05).** Queue, CLI surface, `is_marker_ready()` gate, Marker-only academic indexing gate (`IngestPipeline`), short-body rejection, honest platform docs, 43 tests. Codex re-review PASS. Feature doc: `docs/features/ris-marker-structural-parser-scaffold.md`. pdfplumber is legacy/debug only. RAG-ready requires `body_source=marker`. **Docker IPC warm-worker (v1) is COMPLETE (2026-05-08)** — Feature 3 closed under revised functional gate; feature doc: `docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md`. **L1 Marker Production Rollout is UNBLOCKED** — resume at next explicit Director workpacket. Do NOT start L2 until L1 production rollout completes.
docs/CURRENT_DEVELOPMENT.md:145:- **RIS L3 v1 SVM Topic Filter is COMPLETE (2026-05-07).** Default-off integrated; dry-run + hold-review ready; enforce deferred. Director decision: `BAAI/bge-large-en-v1.5` approved as production model. Feature doc at `docs/features/FEATURE-ris-svm-filter-v1.md`. SVM enforce remains hard-blocked at rc=1 pending future Director approval. SPECTER2 path remains unresolved; BGE-large is the declared production model. **Marker Docker IPC warm-worker v1 is COMPLETE (2026-05-08) — active count is now 2 (Features 1, 2).** Feature doc: `docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md`. L1 Marker Production Rollout unblocked.
```

### `git grep -n "<=10 s\|<=10s\|≤10s\|10s/paper\|5-10\|5–10" docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md docs/CURRENT_DEVELOPMENT.md docs/CURRENT_STATE.md`

Exit code: 0.

```text
docs/CURRENT_DEVELOPMENT.md:92:| Marker Docker IPC Warm-Worker v1                             | 2026-05-08 | RIS      | `docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md` — IPC warm-worker subprocess; daemon=False fix; `ipc_warm_worker_used` persisted. **Revised gate (Director 2026-05-08): ≥3 full PDFs/session; papers 2+ delta ≤5s; `body_source=marker`; `ipc_warm_worker_used=true`; no pdfplumber fallback; no daemon error; clean shutdown.** Measured: 45.55s/69.73s/48.31s; papers 2–3 delta=0.13s/0.22s. Original ≤10s/paper gate rejected as unrealistic. L1 Marker production rollout UNBLOCKED. L2/L4 remain stubs. Dev log: `docs/dev_logs/2026-05-08_marker-docker-ipc-warm-worker-v1-closeout.md`. |
docs/CURRENT_DEVELOPMENT.md:96:| Marker Single-Paper Validation Control Surface               | 2026-05-05 | RIS      | `run-academic-url` subcommand; process-boundary subprocess cancel; `parse_seconds` in result; 5 new tests. Validated: `body_source=marker`, `body_length=56923`, `parse_seconds=85.95s`. L1 production blocked on ≤10s/paper gate at time of closeout (**gate later revised/superseded 2026-05-08 — see Marker Docker IPC Warm-Worker v1 closeout above**). |
docs/CURRENT_STATE.md:1822:Original ≤10s/paper timing gate for papers 2+ is **rejected as unrealistic** for full
```

Note: `git grep` does not search untracked files. I also used `rg` below to include the
untracked feature doc and work packet.

### `git grep -n "^### Feature" docs/CURRENT_DEVELOPMENT.md`

Exit code: 0.

```text
docs/CURRENT_DEVELOPMENT.md:38:### Feature 1: Track 2 Paper Soak — 24h Run
docs/CURRENT_DEVELOPMENT.md:56:### Feature 2: RIS Operational Readiness — Phase 2A
```

### `Test-Path -LiteralPath "docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md"`

Exit code: 0.

```text
True
```

### `git grep -n "Marker Docker IPC Warm-Worker v1\|marker-docker-ipc-warm-worker-v1-closeout" docs/INDEX.md`

Exit code: 0.

```text
docs/INDEX.md:121:| [Marker Docker IPC Warm-Worker v1](features/FEATURE-marker-docker-ipc-warm-worker-v1.md) | **COMPLETE 2026-05-08.** Persistent IPC warm-worker subprocess for Marker parse queue on Linux/Docker. Models load once at startup; papers 2+ pay only inference cost (0.13s, 0.22s delta). daemon=False fix applied. `ipc_warm_worker_used` persisted in `results.jsonl`. Revised gate: ≥3 full PDFs/session, papers 2+ delta ≤5s. Validated: 45.55s/69.73s/48.31s on RTX 2070 Super. L1 production rollout unblocked. L2/L4 remain stubs. |
docs/INDEX.md:156:| [Marker Docker IPC Warm-Worker v1 — Closeout](dev_logs/2026-05-08_marker-docker-ipc-warm-worker-v1-closeout.md) | 2026-05-08 | Docs-only completion protocol. Feature doc created. INDEX + CURRENT_DEVELOPMENT + CURRENT_STATE + Current-Focus + Work Packet updated. Feature 3 moved to Recently Completed. Active count: 3→2. L1 production rollout unblocked. L2/L4 remain stubs. |
```

### `rg -n "NOT yet closed|pending closeout|closeout verification|Active Feature 3|Feature 3 status|L1 remains blocked by Marker Docker IPC|<=10 s|<=10s|≤10s|10s/paper|5-10|5–10" ...`

Exit code: 0. Relevant output:

```text
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md:78:**L2 gate:** L2 PaperQA2 RAG Control Flow remains stub and does NOT activate until gates 1–7 above are all satisfied and closeout verification completes.
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md:113:**Feature 3 status:** All revised functional gates PASS. Feature 3 is NOT yet closed — closeout verification by Codex required before Feature 3 is marked complete and L1 production is unblocked.
docs/obsidian-vault/Claude Desktop/Current-Focus.md:20:- ~~**Academic pipeline hosting**~~ — **RESOLVED 2026-05-02.** Docker with GPU passthrough on dev machine. RTX 2070 Super, CUDA 13.2. Docker GPU passthrough verified via `docker run --gpus all`. Model weights volume-mounted from `~/.cache/datalab/`. See [[Decision - Academic Pipeline Hosting]] (status: accepted). Hosting blocker resolved; L1 remains blocked by Marker Docker IPC warm-worker (v1) Feature 3 closeout verification — see Active Feature 3 in CURRENT_DEVELOPMENT.md.
```

The same command also found historical or rejected `<=10s` references. Those are safe
where explicitly rejected/superseded or in dated historical session context.

### `rg -n "full academic.*complete|full RIS.*complete|academic/RIS pipeline.*complete|RIS pipeline.*complete|academic pipeline.*complete" ...`

Exit code: 1.

```text
```

No full academic/RIS pipeline completion claim found in the reviewed current docs.

### `rg -n "45\.55s|69\.73s|48\.31s|PaperQA2|L4|stub|blocked" ...`

Exit code: 0. Relevant output:

```text
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md:23:> **Live validation 2026-05-08**: daemon=False fix confirmed; 3 papers completed in one warm session; `body_source=marker` all 3; `ipc_warm_worker_used=true` all 3; no daemonic error; clean shutdown (done=3, failed=0). Timings: 45.55s / 69.73s / 48.31s. Papers 2–3 delta: 0.13s / 0.22s.
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md:26:> **L2 PaperQA2 RAG Control Flow remains STUB** — gated on L1 production rollout completion. Do NOT activate.
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md:120:- **No L4 work.** Multi-source academic harvesters remain stub and are not touched.
docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md:116:| 1 (Polymarket microstructure) | 2604.24366 | 45.55s | 72.31s | **26.76s (cold-load)** | marker | true |
docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md:117:| 2 (COVID-19 sports betting) | 2109.07581 | 69.73s | 69.86s | **0.13s (warm)** | marker | true |
docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md:118:| 3 (Sports betting inefficiencies) | 1910.08858 | 48.31s | 48.53s | **0.22s (warm)** | marker | true |
docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md:148:- L2 PaperQA2 RAG Control Flow remains stub. L4 Multi-source Academic Harvesters remain
docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md:178:| L2 PaperQA2 RAG Control Flow | Stub — explicitly blocked | Gated on L1 production rollout completion |
docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md:179:| L4 Multi-source Academic Harvesters | Stub — explicitly blocked | Gated on L1 + L3 |
docs/CURRENT_STATE.md:1832:| arxiv:2604.24366 (paper 1) | 45.55s | 72.31s | 26.76s (cold-load) | marker | true |
docs/CURRENT_STATE.md:1833:| arxiv:2109.07581 (paper 2) | 69.73s | 69.86s | **0.13s (warm)** | marker | true |
docs/CURRENT_STATE.md:1834:| arxiv:1910.08858 (paper 3) | 48.31s | 48.53s | **0.22s (warm)** | marker | true |
docs/CURRENT_STATE.md:1845:- L2 PaperQA2 RAG Control Flow — stub; gated on L1 Marker production rollout completion.
docs/CURRENT_STATE.md:1846:- L4 Multi-source Academic Harvesters — stub; gated on L1 + L3.
docs/INDEX.md:121:| [Marker Docker IPC Warm-Worker v1](features/FEATURE-marker-docker-ipc-warm-worker-v1.md) | **COMPLETE 2026-05-08.** Persistent IPC warm-worker subprocess for Marker parse queue on Linux/Docker. Models load once at startup; papers 2+ pay only inference cost (0.13s, 0.22s delta). daemon=False fix applied. `ipc_warm_worker_used` persisted in `results.jsonl`. Revised gate: ≥3 full PDFs/session, papers 2+ delta ≤5s. Validated: 45.55s/69.73s/48.31s on RTX 2070 Super. L1 production rollout unblocked. L2/L4 remain stubs. |
```

### `git diff --name-status --cached`

Exit code: 0.

```text
```

No staged changes.

### `git log --oneline -5`

Exit code: 0.

```text
4b57400 SVM scoring complete
e482a6d L3 handoff
be8b4f2 fix(ris): resolve Codex FAIL blockers — Marker queue v0
7b81a7a Marker Parser added
a4fdcac docs(ris): close out Marker control surface validation — L1 still blocked
```

---

## Commands Not Run

No tests, Docker validation, Docker rebuild/prune, queue processing, artifact mutation,
SVM commands, L2/L4 commands, or trading commands were run.

I did not run `python -m polytool --help` because the objective explicitly constrained
the review to closeout inspection and said not to run validation.

---

## Codex Review Summary

Tier: docs-only closeout verification.

Issues found:

- Blocking: Work packet still says Feature 3 is not yet closed.
- Blocking: Current-Focus still says L1 remains blocked on Feature 3 closeout and points
  to Active Feature 3.
- Non-blocking cleanup: Work packet L2 gate line should be updated from "until closeout
  verification completes" to "until L1 production rollout completes."

Issues addressed: none in source docs. Per instruction, this review changed only this
dev log.
