---
title: Fix Marker Docker Ipc Warm Worker V1 Activation
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-07_fix-marker-docker-ipc-warm-worker-v1-activation.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Fix — Marker Docker IPC Warm-Worker v1 Activation Blockers

Date: 2026-05-07
Type: docs-only cleanup / blocker fix
Author: Claude Code (Aman / Director approved)
Precursor: `docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-v1-activation.md` (FAIL verdict)

## Summary

Fixed two blockers identified by Codex verification of the Feature 3 activation session:

1. **Stale "L1 Marker production rollout unblocked" claims** — three locations updated across `docs/INDEX.md` and `docs/obsidian-vault/Claude Desktop/Current-Focus.md`.
2. **Obsidian smart-env metadata noise** — four tracked generated files reverted; one untracked generated ajson removed. Two remaining dirty files are accepted Obsidian runtime metadata (not in scope to suppress while the editor is running).

No implementation code, tests, Marker queue/parser code, artifacts, SVM labels/models, L2/PaperQA2 stubs, L4 stubs, or trading files were touched.

## Stale Claims Fixed

### docs/INDEX.md (line 182)

| | Content |
|---|---|
| **Before** | `...hard-cutover rollout; L1 Marker production rollout unblocked` |
| **After** | `...hard-cutover rollout; hosting blocker resolved (L1 remains blocked by IPC warm-worker v1 — see 2026-05-07 entries)` |

This is the dev log index entry for the 2026-05-03 hosting decision. The entry now accurately distinguishes the hosting blocker being resolved from the overall L1 production rollout status.

### docs/obsidian-vault/Claude Desktop/Current-Focus.md (Open Decisions section, line 20)

| | Content |
|---|---|
| **Before** | `...L1 Marker production rollout is now unblocked.` |
| **After** | `...Hosting blocker resolved; **L1 Marker production rollout remains blocked by IPC warm-worker v1 (Feature 3 — active, see Active Priorities above).**` |

### docs/obsidian-vault/Claude Desktop/Current-Focus.md (Recent Session Context, line 57)

| | Content |
|---|---|
| **Before** | `...L1 Marker production rollout unblocked. Next packet:...` |
| **After** | `...Hosting blocker resolved (L1 subsequently re-blocked by IPC warm-worker v1 requirement — see 2026-05-07 entries). Next packet:...` |

### Historical docs not changed

`docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md` and
`docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md`
both contain "L1 is unblocked" language that accurately reflects what was true on 2026-05-03
(before the IPC warm-worker requirement was discovered on 2026-05-05). These are historical
records and were NOT flagged by the Codex verify; they were not changed.

## Smart-Env Dirty Paths — Resolution

### Tracked files reverted (git checkout --)

| Path | Classification | Action |
|---|---|---|
| `docs/obsidian-vault/.obsidian/workspace.json` | Obsidian UI state (which panel/file is open) | Reverted |
| `docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson` | Smart-env event log, auto-generated | Reverted |
| `docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_L3_v1_SVM_Topic_Filter_Training_md.ajson` | Smart-env embedding index for L3 SVM work packet | Reverted |
| `docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson` | Smart-env embedding index for Current-Focus.md | Reverted |

### Untracked files removed

| Path | Classification | Action |
|---|---|---|
| `docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Marker_Docker_IPC_Warm-Worker_v1_md.ajson` | Smart-env embedding index auto-generated for the new Marker work packet | Removed |

### Remaining dirty files — accepted Obsidian runtime metadata

After the revert, Obsidian immediately re-wrote two files because the editor was running and processed the `Current-Focus.md` change:

| Path | Why still dirty | Decision |
|---|---|---|
| `docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson` | Obsidian logged the edit event (10 new lines) | **Accepted** — live Obsidian runtime behavior; cannot suppress without closing Obsidian |
| `docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson` | Smart-env re-indexed `Current-Focus.md` after our edit (6 new lines, updated embeddings) | **Accepted** — live Obsidian runtime behavior; re-index is expected after any vault edit |

These files are generated metadata, not intentional project docs. Their dirtiness is a function of Obsidian being open, not of this session's changes. They do not affect the context-map accuracy claim in any meaningful way.

### Untracked files retained (intentional project artifacts)

| Path | Why kept |
|---|---|
| `docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-activation.md` | Activation dev log — intentional |
| `docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-context-map.md` | Context map dev log — intentional |
| `docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-v1-activation.md` | Codex FAIL verification log — intentional |
| `docs/dev_logs/2026-05-07_fix-marker-docker-ipc-warm-worker-v1-activation.md` | This fix dev log — intentional |
| `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md` | Feature 3 work packet — intentional project doc |

## Feature 3 Status Confirmation

After fixes, confirmed (by grep and reading):

- Feature 3 active as Marker Docker IPC Warm-Worker v1: **YES** (`CURRENT_DEVELOPMENT.md`)
- Active count 3, max-3 reached: **YES** (`CURRENT_DEVELOPMENT.md`, `Current-Focus.md`)
- L3 v1 SVM Recently Completed, default-off, enforce deferred: **YES**
- Acceptance gates include ≥3 warm papers and ≤10s/paper for papers 2+: **YES** (work packet + activation log)
- L2/PaperQA2 explicitly blocked until Feature 3 passes: **YES** (`Current-Focus.md` L1 table)
- No remaining stale "L1 production rollout unblocked" claims in current/navigation docs: **YES**

## Commands Run

```
git status --short
git diff --name-status
git diff -- docs/INDEX.md "docs/obsidian-vault/Claude Desktop/Current-Focus.md"
git grep -n "L1 Marker production rollout unblocked|..." docs/
git checkout -- <4 smart-env files>
rm docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Marker_Docker_IPC_Warm-Worker_v1_md.ajson
git diff --stat -- <remaining 2 smart-env files>
```

## Implementation Design — May Proceed

All Codex FAIL blockers are resolved:

1. Stale "L1 unblocked" claims in current/navigation docs: **FIXED**.
2. Context-map smart-env noise: **cleaned up**. Two remaining dirty files are accepted Obsidian runtime metadata that will persist while Obsidian is active — they do not represent project state changes.

The next step is designing the Feature 3 implementation prompt (IPC warm-worker architecture, request/response protocol, test strategy). See `docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-activation.md` § "Next Implementation Prompt Needs" for the design checklist.

## Codex Review Summary

Tier: Skip. Docs-only cleanup. No mandatory or recommended review-path implementation code changed.
Issues found: none.
Issues addressed: two Codex FAIL blockers from previous verification session.
