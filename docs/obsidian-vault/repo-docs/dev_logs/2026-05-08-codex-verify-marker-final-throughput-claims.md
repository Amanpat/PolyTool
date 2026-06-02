---
title: Codex Verify Marker Final Throughput Claims
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-08_codex-verify-marker-final-throughput-claims.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Codex Verify: Marker Final Throughput Claims

Date: 2026-05-08
Type: read-only documentation consistency review
Scope: Feature 3 - Marker Docker IPC Warm-Worker v1 final throughput-claim cleanup
Verdict: **FAIL**

---

## Summary

FAIL. Feature 3 closeout should **not** run next yet.

The main state docs now correctly show Marker Docker IPC Warm-Worker v1 as Active
Feature 3, pending Codex closeout verification. The revised functional gate is
consistent in the main Feature 3 block and preserves the measured timings:
45.55s, 69.73s, and 48.31s.

However, the all-doc grep still surfaces current work-packet text that presents
the old <=10s/paper gate as active, or leaves <=10s warm-worker expectations not
explicitly superseded in place. This review changed only this dev log.

---

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/CURRENT_STATE.md`
- `docs/INDEX.md`
- `docs/obsidian-vault/Claude Desktop/Current-Focus.md`
- `docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md`
- `docs/features/ris-marker-structural-parser-scaffold.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`
- `docs/dev_logs/2026-05-08_codex-verify-marker-ipc-revised-gate-all-docs-consistency.md`
- `docs/dev_logs/2026-05-08_fix-marker-final-throughput-claims.md`
- Additional files surfaced by grep:
  - `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Single-Paper Validation Control Surface.md`
  - `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md`
  - `docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md`

---

## Verification Results

### 1. No active <=10s or 5-10s full-PDF production gate

FAIL.

The six blocker locations listed in
`2026-05-08_fix-marker-final-throughput-claims.md` were fixed, but additional
current work-packet text remains active-looking:

- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Single-Paper Validation Control Surface.md:14`
  still says production rollout resume is "**still blocked on <=10s/paper gate**".
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Single-Paper Validation Control Surface.md:21`
  says `parse_seconds=85.95s` exceeds the `<=10s/paper production gate`.
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Single-Paper Validation Control Surface.md:29`
  says `parse_seconds: 85.95s` fails `<=10s/paper gate`.
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Single-Paper Validation Control Surface.md:149`
  says L1 production is blocked by the `<=10s/paper` production gate.
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md:181`
  says "papers 2+ expected <=10s warm" in reference material without an adjacent
  2026-05-08 supersession note.

### 2. Remaining timing references historical/rejected/superseded

FAIL.

Many remaining references are safe because they explicitly say rejected,
superseded, historical, or later revised. Examples:

- `docs/CURRENT_DEVELOPMENT.md:85` - original <=10s/paper timing gate rejected.
- `docs/CURRENT_STATE.md:1783` - original <=10s/paper timing gate rejected.
- `docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md:19` - 5-10 seconds is labeled historical and rejected.
- `docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md:102` - checklist item is marked superseded.
- `docs/features/ris-marker-structural-parser-scaffold.md:89` - 5-10s/paper is labeled historical and rejected.
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md:43,56,96,126` - old claims are revised, struck through, or marked resolved/superseded.

The Single-Paper Validation Control Surface and Canonical Academic Parse Queue
references listed above are not clearly superseded in place.

### 3. Hosting decision doc active <=10s checklist

PASS.

`docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md`
now marks the old GPU performance baseline checklist item as superseded:

```text
- [~] GPU performance baseline run: <=10 s/paper on the production host - SUPERSEDED 2026-05-08...
```

The doc also preserves the revised gate and the actual timings.

### 4. Structural parser feature/workpacket 5-10s production throughput

PARTIAL.

The two requested docs were fixed:

- `docs/features/ris-marker-structural-parser-scaffold.md` says the 5-10s/paper
  survey estimate was not validated and was rejected as unrealistic.
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md`
  strikes through or supersedes the prior 5-10s and <=10s claims.

But related work-packet docs still contain active-looking old timing language,
so all-doc consistency is not clean.

### 5. Revised gate and actual timings

PASS.

The current Feature 3 state preserves the revised gate:

- >=3 full PDFs in one warm session
- papers 2+ delta <=5s
- `body_source=marker`
- `ipc_warm_worker_used=true`
- no pdfplumber fallback
- no daemon-process error
- queue semantics intact
- clean shutdown

Measured timings are preserved:

- paper 1 = 45.55s, delta 26.76s
- paper 2 = 69.73s, delta 0.13s
- paper 3 = 48.31s, delta 0.22s

### 6. Feature 3 remains Active and pending closeout

PASS.

`docs/CURRENT_DEVELOPMENT.md` has `### Feature 3: Marker Docker IPC Warm-Worker v1`
under Active Features. Its current step says to await Codex closeout verification
before creating `docs/features/ris-marker-docker-ipc-warm-worker-v1.md`, updating
INDEX, and moving to Recently Completed.

`Test-Path docs/features/ris-marker-docker-ipc-warm-worker-v1.md` returned `False`.

### 7. L2/PaperQA2 and L4 blocked/stubbed

PASS.

- `docs/obsidian-vault/Claude Desktop/Current-Focus.md` says L2 is Stub and L4 is Stub.
- `docs/CURRENT_DEVELOPMENT.md` says do not start L2 until warm-worker closeout completes,
  and the Feature 3 note says do not start L2 or L4.
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`
  states L2 PaperQA2 is blocked until Feature 3 passes closeout verification and lists
  "No L2 work" and "No L4 work" as non-goals.

### 8. No new implementation/test/Docker/artifact/SVM/trading changes added by docs fix

PASS WITH CAVEAT.

The current tree contains dirty implementation/test/Docker files from the Marker IPC
work stream. The fix log records the scoped implementation baseline as identical
before and after the docs fix:

```text
M	Dockerfile.ris
M	packages/research/ingestion/fetchers.py
M	packages/research/ingestion/marker_queue.py
M	tests/test_ris_marker_queue.py
M	tools/cli/research_marker_queue.py
```

This review found no evidence that the final throughput-claims docs fix added new
implementation/test/Docker/artifact/SVM/trading changes. The scoped diff output
still matches the fix log baseline.

---

## Commands Run

### `git status --short`

Exit code: 0. Result before this review dev log was created:

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
?? docs/dev_logs/2026-05-08_fix-marker-final-throughput-claims.md
?? "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md"
?? packages/research/ingestion/marker_ipc_worker.py
?? tests/test_ris_marker_ipc_worker.py
```

There were many additional untracked Marker IPC dev logs from 2026-05-07 and
2026-05-08.

### `git log --oneline -5`

Exit code: 0.

```text
4b57400 SVM scoring complete
e482a6d L3 handoff
be8b4f2 fix(ris): resolve Codex FAIL blockers - Marker queue v0
7b81a7a Marker Parser added
a4fdcac docs(ris): close out Marker control surface validation - L1 still blocked
```

### `git grep -n "<=10 s\|<=10s\|<=10s\|10s/paper\|10 seconds\|5-10\|5-10\|~5-10" docs`

The actual command run included the Unicode variants requested by the operator:
`<=10 s\|<=10s\|<=10s\|10s/paper\|10 seconds\|5-10\|5-10\|~5-10`,
with the third, seventh, and gate-symbol variants as Unicode in the shell.

Exit code: 0. Relevant non-cache results:

```text
docs/CURRENT_DEVELOPMENT.md:85:- **Revised gate (Director 2026-05-08):** Original <=10s/paper timing gate rejected as unrealistic...
docs/CURRENT_DEVELOPMENT.md:118:... L1 production blocked on <=10s/paper gate at time of closeout (**gate later revised 2026-05-08 - see Active Feature 3**).
docs/CURRENT_STATE.md:1783:- Marker Docker IPC warm-worker v1 - **Active Feature 3** ... Original <=10s/paper timing gate rejected as unrealistic...
docs/INDEX.md:155:... 6 active-looking <=10s / 5-10s/paper claims fixed...
docs/INDEX.md:156:... scaffold install still said ~5-10s/paper...
docs/INDEX.md:157:... <=10s/paper gate language superseded...
docs/INDEX.md:161:... <=10s/paper rejected as unrealistic...
docs/INDEX.md:182:... L1 production BLOCKED - <=10s/paper gate fails 8.6x...
docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md:17:... pending >=3 warm papers at <=10s/paper...
docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md:93:... L1 remains blocked until >=3 warm papers parse at <=10s/paper.
docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md:113:... confirm <=10 s/paper (acceptance gate 2).
docs/features/ris-marker-structural-parser-scaffold.md:7:... Original aspirational <=10s/paper timing gate **rejected as unrealistic...
docs/features/ris-marker-structural-parser-scaffold.md:14:... <=10s/paper gate superseded 2026-05-08...
docs/features/ris-marker-structural-parser-scaffold.md:23:... The ~5-10 s/paper GPU performance claim ... **was not validated**...
docs/features/ris-marker-structural-parser-scaffold.md:89:... historical survey estimate: ~5-10 s/paper ... **rejected as unrealistic...
docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md:19:... surveyed at 5-10 seconds (historical architecture survey estimate - **rejected...
docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md:102:- [~] GPU performance baseline run: <=10 s/paper ... **SUPERSEDED 2026-05-08...
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md:23:... <=10s gate fails by ~8.6x.
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md:50:... Original `parse_seconds <=10s` timing gate **rejected as unrealistic...
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md:61:... original <=10s/paper timing target; **revised gate 2026-05-08:** ...
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md:102:... ~~<=10s/paper ...~~ - **timing gate rejected as unrealistic...
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md:181:... papers 2+ expected <=10s warm
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Single-Paper Validation Control Surface.md:14:... **still blocked on <=10s/paper gate**
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Single-Paper Validation Control Surface.md:21:... exceeds the <=10s/paper production gate.
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Single-Paper Validation Control Surface.md:29:... FAILS <=10s/paper gate
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Single-Paper Validation Control Surface.md:149:**L1 production verdict: BLOCKED** - ... `<=10s/paper` production gate.
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md:43:... original "<=10s/paper" per-paper target **rejected as unrealistic**...
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md:56:... ~~Marker on this hardware is ~5-10s/paper...~~ **Historical note, superseded 2026-05-08:** ...
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md:96:... **Superseded (Director 2026-05-08):** original <=10s/paper...
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md:126:... **Resolved:** acceptance gate 2 revised...
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Prefetch Label Discovery Mode.md:152:... Original <=10s/paper timing gate rejected as unrealistic...
docs/obsidian-vault/Claude Desktop/Current-Focus.md:53:... acceptance gates set ... `parse_seconds <=10s` for papers 2+...
docs/obsidian-vault/Claude Desktop/Current-Focus.md:54:... fails <=10s/paper gate by ~8.6x...
docs/obsidian-vault/Claude Desktop/Current-Focus.md:57:... <=10s/paper gate later rejected/revised 2026-05-08...
```

The command also returned archive, older dev-log, Obsidian plugin, and `.smart-env`
cache matches. Those were not treated as active Marker production gate blockers
unless they pointed to current work-packet text.

### `git grep -n "Feature 3\|Marker Docker IPC" docs/CURRENT_DEVELOPMENT.md`

Exit code: 0.

```text
docs/CURRENT_DEVELOPMENT.md:75:### Feature 3: Marker Docker IPC Warm-Worker v1
docs/CURRENT_DEVELOPMENT.md:118:... L1 production blocked on <=10s/paper gate at time of closeout (**gate later revised 2026-05-08 - see Active Feature 3**).
docs/CURRENT_DEVELOPMENT.md:137:| RIS Marker Queue - Docker IPC Warm-Worker (v1) | ACTIVATED 2026-05-07 | ... Pending Codex closeout verification - see Active Feature 3. | N/A - now Active Feature 3 |
docs/CURRENT_DEVELOPMENT.md:138:| RIS L1 Marker Production Rollout - Validation | 2026-05-05 | ... Blocked on Docker IPC warm-worker (v1) Feature 3 closeout. ... | Docker IPC warm-worker (v1) Feature 3 closeout verification passes |
docs/CURRENT_DEVELOPMENT.md:162:... **Docker IPC warm-worker (v1) is now Active Feature 3** ...
docs/CURRENT_DEVELOPMENT.md:167:... **Marker Docker IPC warm-worker v1 activated as Feature 3 (2026-05-07)...
docs/CURRENT_DEVELOPMENT.md:168:- **Marker Docker/Linux IPC Warm-Worker (v1) is NOW ACTIVE as Feature 3...
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

PowerShell/git also emitted:

```text
warning: in the working copy of 'Dockerfile.ris', LF will be replaced by CRLF the next time Git touches it
```

### `git diff --stat`

Exit code: 0. Result before this review dev log was created:

```text
 Dockerfile.ris                                     |   1 +
 docs/CURRENT_DEVELOPMENT.md                        |  35 +-
 docs/CURRENT_STATE.md                              |   2 +-
 docs/INDEX.md                                      |  11 +-
 ...026-05-03_academic-pipeline-hosting-decision.md |  15 +-
 .../ris-marker-structural-parser-scaffold.md       |  13 +-
 docs/obsidian-vault/.obsidian/workspace.json       |  22 +-
 .../.smart-env/event_logs/event_logs.ajson         | 248 +++++--
 ...s_Decision_-_Academic_Pipeline_Hosting_md.ajson |  12 +-
 ...cket_-_L3_v1_SVM_Topic_Filter_Training_md.ajson | 208 +++---
 ..._Marker_Canonical_Academic_Parse_Queue_md.ajson |  60 +-
 ...-_Marker_Structural_Parser_Integration_md.ajson |  12 +-
 ...Packet_-_Prefetch_Label_Discovery_Mode_md.ajson |  14 +-
 .../multi/Claude_Desktop_Current-Focus_md.ajson    |  57 +-
 .../Decision - Academic Pipeline Hosting.md        |   6 +-
 ...cket - Marker Canonical Academic Parse Queue.md |  13 +-
 ...acket - Marker Structural Parser Integration.md |   8 +-
 .../Work-Packet - Prefetch Label Discovery Mode.md |  19 +-
 .../obsidian-vault/Claude Desktop/Current-Focus.md |  15 +-
 packages/research/ingestion/fetchers.py            | 137 ++++
 packages/research/ingestion/marker_queue.py        | 111 +++-
 tests/test_ris_marker_queue.py                     | 724 +++++++++++++++++++++
 tools/cli/research_marker_queue.py                 | 133 +++-
 23 files changed, 1642 insertions(+), 234 deletions(-)
```

### Focused inspections

`Select-String` on `Work-Packet - Marker Single-Paper Validation Control Surface.md`
confirmed active-looking old gate text at lines 14, 21, 29, and 149.

`Select-String` on `Work-Packet - Marker Canonical Academic Parse Queue.md`
confirmed line 181 still says:

```text
performance evidence; warm-model assumption validated (paper 1 = 85.95s cold; papers 2+ expected <=10s warm)
```

`git grep -n "PaperQA2\|L2\|L4\|Multi-source" ...` confirmed L2/PaperQA2 and
L4 remain blocked/stubbed.

`Test-Path -LiteralPath 'docs/features/ris-marker-docker-ipc-warm-worker-v1.md'`
returned:

```text
False
```

---

## Blockers Before Feature 3 Closeout

1. Update `Work-Packet - Marker Single-Paper Validation Control Surface.md` so all
   <=10s/paper production-gate references are explicitly historical/superseded by
   the 2026-05-08 revised gate.
2. Update `Work-Packet - Marker Canonical Academic Parse Queue.md:181` so the
   reference-material line no longer says papers 2+ were expected <=10s warm
   without the revised-gate context.
3. Consider updating `docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md`
   stale-note lines 17, 93, and 113 to mention the 2026-05-08 revised gate, even
   though the file is a historical dev log.

---

## Closeout Verdict

Feature 3 closeout should **not** run next. The final docs cleanup fixed the
previously listed six blockers, but the all-doc grep still finds current
work-packet text that violates the "remaining timing references are explicitly
historical/rejected/superseded" rule.

---

## Codex Review Summary

Tier: docs-only closeout-readiness review. No implementation code, tests, Docker,
queues, artifacts, SVM labels/models, L2, L4, trading, or validation runs were
touched.

Issues found: remaining active-looking old <=10s/paper references in current
Marker work-packet docs.

Issues addressed: none. Per instruction, only this review dev log was created.
