# Codex Verify: Marker IPC Revised Gate and Result Evidence

Date: 2026-05-08
Type: read-only verification review
Scope: Feature 3 Marker Docker IPC warm-worker v1 revised gate + result evidence fix
Verdict: FAIL

---

## Summary

FAIL. The evidence persistence code change is acceptable and the targeted tests pass, but
Feature 3 closeout should NOT run next because the documentation state is not internally
consistent with the Director-approved revised gate.

Blocking documentation findings:

1. Current docs still contain active, unstruck <=10s warm-paper gate language outside the
   revised gate section.
2. `docs/CURRENT_DEVELOPMENT.md` does not show Marker Docker IPC warm-worker as Active
   Feature 3 pending closeout. It still lists the warm-worker and L1 validation rows under
   Paused / Deferred with <=10s resume triggers.

The workpacket and revised-gate dev log do document the new functional gate clearly:
>=3 full PDFs in one Docker/GPU warm-worker session, body_source=marker, IPC true, no
fallback, no daemon error, queue semantics intact, clean shutdown, and papers 2+ delta
<=5s. The measured timings are preserved honestly: 45.55s, 69.73s, and 48.31s parse time;
paper 2/3 deltas 0.13s and 0.22s.

This review changed only this dev log.

---

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`
- `docs/dev_logs/2026-05-08_marker-ipc-daemon-fix-direct-pdf-live-validation.md`
- `docs/dev_logs/2026-05-08_codex-verify-marker-ipc-daemon-fix-direct-pdf-live-validation.md`
- `docs/dev_logs/2026-05-08_marker-ipc-revised-gate-and-result-evidence.md`
- `packages/research/ingestion/marker_queue.py`
- `packages/research/ingestion/fetchers.py`
- `packages/research/ingestion/marker_ipc_worker.py`
- `tools/cli/research_marker_queue.py`
- `tests/test_ris_marker_queue.py`
- `tests/test_ris_marker_ipc_worker.py`
- `artifacts/research/marker_ipc_validation/daemon_fix_direct_pdf_live_20260508_115111.log`
- `artifacts/research/marker_validation_queue_direct/results.jsonl`
- `docs/INDEX.md`
- `docs/obsidian-vault/Claude Desktop/Current-Focus.md`
- `docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md`
- `docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md`

---

## Revised Gate Verification

PASS in the workpacket and revised-gate dev log:

- Director-approved revision is explicit: original <=10s/paper gate rejected as unrealistic
  for full academic PDFs on RTX 2070 Super.
- Revised functional gate is stated: >=3 full PDFs in one warm session, papers 2+ delta
  <=5s, `body_source=marker`, `ipc_warm_worker_used=true`, no pdfplumber/fallback,
  no daemon-process error, clean shutdown/no orphans, and persisted IPC evidence.
- Actual measured timings are preserved:
  - `arxiv:2604.24366`: parse_seconds=45.55, total_seconds=72.31, delta=26.76s
  - `arxiv:2109.07581`: parse_seconds=69.73, total_seconds=69.86, delta=0.13s
  - `arxiv:1910.08858`: parse_seconds=48.31, total_seconds=48.53, delta=0.22s

FAIL in broader current docs:

- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`
  still has active <=10s wording in the Goal and v1 fix sections:
  - line 38: "papers 2+ parse from warm VRAM at <=10s/paper"
  - line 57: "Multiple queued papers are processed sequentially through the warm worker with <=10s/paper for papers 2+"
- `docs/CURRENT_DEVELOPMENT.md` still has <=10s resume triggers:
  - line 114: "validates >=3 papers warm (<=10s/paper for papers 2+)"
  - line 115: "parse_seconds <=10s for papers 2+"
- `docs/obsidian-vault/Claude Desktop/Current-Focus.md` still has current blocked/unblocked language tied to <=10s:
  - line 20: ">=3 warm papers, <=10s/paper for papers 2+"
  - line 29: "validates >=3 papers warm (<=10s/paper for papers 2+)"
  - line 72: "validates >=3 papers at <=10s/paper"
- `docs/INDEX.md` still summarizes the current L1 blocker as `>=3 warm papers, <=10s/paper for papers 2+`.

---

## Evidence Persistence Verification

PASS for the code path going forward:

- `MarkerParseQueue.process_next()` now accepts `_extra_result_fields`.
- `process_next()` merges those fields into `result_record` before `_append_result()`.
- `process_next_ipc()` passes `{"ipc_warm_worker_used": ipc_used}` through that path.
- The new `TestIPCResultPersistence` tests read back `results.jsonl` and verify:
  - `True` persists when an IPC worker is provided.
  - `False` persists on the injected non-worker IPC path.
  - non-IPC `process_next()` does not add the field.
  - multiple IPC results all persist the field.

Caveat:

- The existing live validation artifact `artifacts/research/marker_validation_queue_direct/results.jsonl`
  still does not contain `ipc_warm_worker_used`, because it was produced before this fix and
  the queue was not mutated during this review. This is acceptable only as a pre-fix artifact;
  it should not be cited as proof that persisted IPC evidence existed during the live run.

---

## Scope / Non-Mutation Verification

No live Marker jobs, Docker rebuilds, Docker prunes, or queue mutations were run by this
review. The reviewed revised-gate dev log also states that live Docker/GPU validation was
not rerun and no Docker rebuild/prune or queue mutation occurred in that session.

No trading, SVM enforcement, L2, or L4 source changes were found in the reviewed Marker IPC
implementation paths. There are pre-existing dirty Obsidian smart-env files and historical
SVM doc references in the worktree, but the changed implementation/test paths reviewed here
are Marker queue/fetcher/IPC/CLI/tests.

One pre-existing tracked Dockerfile change exists (`Dockerfile.ris` adds
`packages/research/relevance_filter` to the placeholder directory list). I did not run any
Docker build/prune command.

---

## Feature 3 / Closeout Verdict

Closeout may NOT run next.

Reason:

- `docs/CURRENT_DEVELOPMENT.md` does not show Marker Docker IPC warm-worker as Active
  Feature 3 pending closeout. It still lists Marker IPC under Paused / Deferred.
- Several current docs still contain active <=10s gate wording, so the docs do not yet fully
  satisfy "no longer require <=10s/paper for full academic PDFs."

After those documentation conflicts are fixed, the revised functional gate and persistence
fix are otherwise acceptable based on this review.

---

## Commands Run

### `git status --short`

Exit code: 0. Key output:

```text
 M Dockerfile.ris
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
?? docs/dev_logs/2026-05-08_marker-ipc-revised-gate-and-result-evidence.md
?? "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md"
?? packages/research/ingestion/marker_ipc_worker.py
?? tests/test_ris_marker_ipc_worker.py
```

There are many additional pre-existing untracked dev logs from 2026-05-07 and 2026-05-08.

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

Exit code: 0. CLI loaded successfully and listed `research-marker-queue` under RIS commands.

### `python -m pytest tests/test_ris_marker_ipc_worker.py tests/test_ris_marker_queue.py -q`

Exit code: 0.

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: C:\Users\CodexSandboxOffline\.codex\.sandbox\cwd\44f493c2f0bf4629
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 159 items

tests\test_ris_marker_ipc_worker.py .................................... [ 22%]
........                                                                 [ 27%]
tests\test_ris_marker_queue.py ......................................... [ 53%]
...................s.................................................... [ 98%]
..                                                                       [100%]

======================= 158 passed, 1 skipped in 3.33s ========================
```

### `python -m polytool research-marker-queue warm-process --help`

Exit code: 0.

```text
usage: polytool research-marker-queue warm-process [-h] [--max-items N]
                                                   [--marker-timeout SECONDS]
                                                   [--json]

options:
  -h, --help            show this help message and exit
  --max-items N         Maximum number of pending items to process (default:
                        1)
  --marker-timeout SECONDS
                        Marker extraction timeout in seconds (default: 900)
  --json                Output results as JSON
```

### `git diff --stat`

Exit code: 0.

```text
 Dockerfile.ris                                     |   1 +
 docs/INDEX.md                                      |   2 +-
 ...026-05-03_academic-pipeline-hosting-decision.md |  15 +-
 docs/obsidian-vault/.obsidian/workspace.json       |   2 +-
 .../.smart-env/event_logs/event_logs.ajson         | 118 ++--
 ...s_Decision_-_Academic_Pipeline_Hosting_md.ajson |   5 +-
 ...cket_-_L3_v1_SVM_Topic_Filter_Training_md.ajson | 208 +++---
 .../multi/Claude_Desktop_Current-Focus_md.ajson    |  31 +-
 .../Decision - Academic Pipeline Hosting.md        |   2 +-
 .../obsidian-vault/Claude Desktop/Current-Focus.md |   4 +-
 packages/research/ingestion/fetchers.py            | 137 ++++
 packages/research/ingestion/marker_queue.py        | 111 +++-
 tests/test_ris_marker_queue.py                     | 724 +++++++++++++++++++++
 tools/cli/research_marker_queue.py                 | 133 +++-
 14 files changed, 1310 insertions(+), 183 deletions(-)
```

### `git diff --name-status`

Exit code: 0.

```text
M	Dockerfile.ris
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

Note: `git diff --name-status` does not list untracked files. `git status --short` shows
untracked `packages/research/ingestion/marker_ipc_worker.py`,
`tests/test_ris_marker_ipc_worker.py`, the workpacket, and multiple dev logs.

### `rg -n "<=10s|<=10|parse_seconds <=10" ...`

Exit code: 0. Relevant blocking matches:

```text
docs/obsidian-vault/Claude Desktop/Current-Focus.md:20:... L1 remains blocked by Marker Docker IPC warm-worker validation (>=3 warm papers, <=10s/paper for papers 2+) ...
docs/obsidian-vault/Claude Desktop/Current-Focus.md:29:... L1 production Marker rollout remains blocked until v1 IPC warm-worker validates >=3 papers warm (<=10s/paper for papers 2+) ...
docs/obsidian-vault/Claude Desktop/Current-Focus.md:72:... L1 blocked until warm-worker validates >=3 papers at <=10s/paper.
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md:38:... papers 2+ parse from warm VRAM at <=10s/paper ...
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md:57:... processed sequentially through the warm worker with <=10s/paper for papers 2+
docs/CURRENT_DEVELOPMENT.md:114:... validates >=3 papers warm (<=10s/paper for papers 2+)
docs/CURRENT_DEVELOPMENT.md:115:... validates >=3 papers with parse_seconds <=10s for papers 2+
docs/INDEX.md:181:... L1 remains blocked pending Marker Docker IPC warm-worker validation (>=3 warm papers, <=10s/paper for papers 2+)
```

---

## Blockers / Fixes Needed

Blocking before closeout:

- Update `docs/CURRENT_DEVELOPMENT.md` so Marker Docker IPC warm-worker is the active
  Feature 3 pending closeout, or otherwise record the Director-approved state in the
  higher-priority development doc.
- Remove or clearly mark stale all active <=10s/paper requirements for full academic PDFs
  in the workpacket, CURRENT_DEVELOPMENT, Current-Focus, and INDEX.

No code fix is required for the result-evidence persistence issue based on this review.

---

## Codex Review Summary

Tier: research ingestion / queue consumer verification. Mandatory trading, execution,
kill-switch, risk-manager, rate-limiter, SVM enforcement, L2, and L4 code were not in scope.

Issues found: documentation blockers prevent Feature 3 closeout from running next. Evidence
persistence fix accepted; targeted tests pass.

Issues addressed: none. Per instruction, only this dev log was created.
