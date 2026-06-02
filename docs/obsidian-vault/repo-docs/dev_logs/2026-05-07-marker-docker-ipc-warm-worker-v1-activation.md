---
title: Marker Docker Ipc Warm Worker V1 Activation
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-activation.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Marker Docker IPC Warm-Worker v1 — Feature 3 Activation

Date: 2026-05-07
Type: docs-only activation
Author: Claude Code (Aman / Director approved)

## Summary

Director approved activating Marker Docker IPC Warm-Worker v1 as Feature 3.
Active count before: 2 (Features 1 and 2). Active count after: 3 (max-3 reached).
No implementation code, tests, artifacts, or model files were touched.

## Active Feature Count

| Moment | Count | Features |
|--------|-------|---------|
| Before this activation | 2 | Feature 1: Track 2 Paper Soak 24h Run; Feature 2: RIS Operational Readiness Phase 2A |
| After this activation | 3 | Features 1 and 2 above + Feature 3: Marker Docker IPC Warm-Worker v1 |
| Max allowed | 3 | Max-3 rule in CURRENT_DEVELOPMENT.md §Rules — now at capacity |

## Files Changed

| File | Change | Why |
|------|--------|-----|
| `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md` | **Created (new)** | Work packet did not exist. Needed to define scope, architecture, acceptance gates, non-goals, and deferred items before implementation can begin. |
| `docs/CURRENT_DEVELOPMENT.md` | Added Feature 3 block; updated Paused/Deferred row; updated Architect notes | Activates the feature, records acceptance gates, enforces max-3 cap awareness |
| `docs/obsidian-vault/Claude Desktop/Current-Focus.md` | Updated Active Priorities, L1 table row, Recent Session Context, Key Blockers, frontmatter date | Living doc that team reads first — must reflect active next work |
| `docs/INDEX.md` | Added dev log row at top of Recent Dev Logs table | Navigation completeness; every activation has an index entry |
| `docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-activation.md` | **Created (this file)** | Mandatory dev log per repo convention |

No code files, test files, artifacts, SVM labels/models, L2/L4 stubs, or trading/Gate 2 files were modified.

## Acceptance Gates (locked at activation)

These gates must ALL pass before L1 Marker production rollout unblocks and Feature 3 moves to Recently Completed.

| # | Gate |
|---|------|
| 1 | Docker/Linux process-boundary IPC warm-worker exists (persistent subprocess with Unix domain socket or named pipe) |
| 2 | Marker models stay loaded across multiple queued papers (no per-paper cold-load after paper 1) |
| 3 | ≥3 papers validate in one warm-worker session (`body_source=marker` on all 3) |
| 4 | Papers 2+ parse at ≤10s/paper on RTX 2070 Super |
| 5 | Queue state/result semantics from v0 remain intact: `is_marker_ready()`, CLI surface (`enqueue`, `list`, `process`, `counts`), state transitions, queue persistence |
| 6 | No pdfplumber fallback exists in any production parse path |
| 7 | Windows local behavior honest and unchanged: thread mode only; IPC is Linux/Docker only |

**L2 gate (derived):** L2 PaperQA2 RAG Control Flow remains stub until all 7 above pass and dev log with Docker timing evidence is written.

## Non-Goals (locked at activation)

- Do not implement warm-worker in this activation session.
- Do not start L2 (PaperQA2 RAG Control Flow) — explicitly blocked.
- Do not start L4 (multi-source harvesters) — explicitly blocked.
- Do not claim L1 production is unblocked — it remains blocked.
- Do not touch SVM labels, models, or enforce status.
- Do not modify trading code, Gate 2 logic, or benchmark files.
- Do not add a pdfplumber fallback.
- pdfplumber remains legacy/debug only.

## Deferred Items

| Item | Reason |
|------|--------|
| IPC warm-worker implementation | Not in this activation session. Next session: Architect designs the implementation prompt for the IPC subprocess. |
| Automatic warm-worker startup on container boot | Deferred even within v1 scope. Manual trigger only for v1. |
| IPC crash recovery / reconnect logic | Post-v1 hardening. |
| Bulk re-ingest of pdfplumber corpus | Separate cleanup task — not this packet. |
| L2 (PaperQA2 RAG Control Flow) | Blocked until Feature 3 passes all gates. |
| L4 (multi-source harvesters) | Blocked until L1 + L3 production. |
| SVM enforce | Hard-blocked at rc=1 pending future Director approval — unrelated to this packet. |

## Context: Why v0 Warm-Worker Is Insufficient for Linux/Docker

Queue v0 shipped `create_warm_thread_worker()` on Windows — thread-based, pre-loads Marker model dict once per process. This works for local dev/debug Windows sessions.

On Linux/Docker, the only path in v0 was `docker compose run --rm` per paper — a new container invocation cold-loads models from disk each time (~136–270s cold-start). This fails the ≤10s/paper gate by 13–27×. v1 fixes this by keeping a persistent subprocess alive inside the container so models stay in GPU VRAM.

v0 documented both modes honestly (thread=warm on Windows; subprocess=cold on Linux/Docker). v1 extends the Linux/Docker path to IPC warm mode without changing the Windows path.

## Context: Why L2 Is Blocked Until Feature 3 Passes

L2 (PaperQA2 RAG Control Flow) requires a Marker-parsed corpus with `body_source=marker`. That corpus cannot be produced at scale until papers 2+ parse in ≤10s warm. Queue v0 can enqueue and process papers but cannot produce a realistically-sized warm corpus on Linux/Docker without the IPC warm-worker. L2 activation before Feature 3 would be premature — the corpus it depends on cannot be built.

## Next Implementation Prompt Needs

When the Architect designs the Feature 3 implementation prompt, include:

1. Read this dev log and the work packet first.
2. Read `packages/research/ingestion/queue.py` and `packages/research/ingestion/worker.py` for v0 queue semantics.
3. Read `packages/research/ingestion/extractors.py` for `MarkerPDFExtractor` API.
4. Read `docs/features/ris-marker-structural-parser-scaffold.md` for the existing Marker scaffold.
5. IPC transport decision: Unix domain socket at `/tmp/marker_worker.sock` preferred (Linux only, ephemeral, matches container lifetime).
6. Request/response: JSON over IPC (debuggable; payloads are small).
7. Worker trigger in v1: manual only (`research-scheduler run-warm-worker`). Queue consumer falls back to per-paper subprocess (cold, warns) if socket is absent.
8. Test strategy: mock IPC server in offline tests — do NOT load real Marker models in CI.
9. Real timing evidence required: run against Docker container with real RTX 2070 Super to get `parse_seconds` for papers 1, 2, 3+.
10. Windows: thread mode is unchanged. No IPC added to Windows path.

## Codex Review Summary

Tier: Skip. Docs-only activation. No mandatory or recommended review-path code changed.
Issues found: none.
Issues addressed: none.

## Open Questions / Blockers

- None blocking this activation.
- Implementation sessions will surface platform-specific questions (IPC socket path, subprocess lifecycle) — handled at that stage.
