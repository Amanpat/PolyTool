---
title: L3 2 Prefetch Label Discovery Activation
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-05_l3-2-prefetch-label-discovery-activation.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# L3.2 Prefetch Label Discovery Mode — Activation

Date: 2026-05-05
Scope: Docs-only activation — no runtime code changed.
Status: ACTIVE — Feature 3 slot assigned; work packet ready.

---

## Summary

L3.2 Prefetch Label Discovery Mode is activated as Feature 3. This is a metadata-only
candidate discovery path designed to accumulate SVM training labels without invoking PDF
download, Marker parsing, or the ingest/index pipeline.

Current label state at activation: **7 allow / 20 reject**.
SVM trigger: **≥30 allow + ≥30 reject**.

The primary motivation is that `research-acquire --prefetch-filter-mode hold-review`
is no longer an effective label accumulation path. The Marker-only academic indexing
gate (shipped in queue v0 on 2026-05-05) blocks non-Marker bodies from canonical
embeddings — correct for production ingest, but means many borderline-relevant
candidates are rejected before they become useful label examples. Cold Marker parse
also takes ~85s/paper minimum (GPU cold-start), making full-pipeline ingest expensive
and slow as a label collection strategy.

---

## Feature 3 Activation

Feature 3 slot in `docs/CURRENT_DEVELOPMENT.md` re-assigned to **L3.2 Prefetch Label
Discovery Mode**. Previous Feature 3 (Marker Canonical Parse Queue v0) was moved to
Recently Completed on 2026-05-05.

Active feature count: **3** (Feature 1: Track 2 Paper Soak, Feature 2: RIS Phase 2A,
Feature 3: L3.2 Label Discovery).

---

## Acceptance Gates

Five gates defined in the work packet:

| Gate | Description |
|------|-------------|
| 1 | Command discovers candidates from arXiv metadata (no PDF fetch) |
| 2 | Every candidate scored with existing `RelevanceScorer` + live config |
| 3 | Candidates enqueued with score/reason/decision fields |
| 4 | Duplicate candidate IDs are idempotent |
| 5 | No document records or chunks created |

Operator success condition: operator can reach ≥30 allow + ≥30 reject labels using
the discovery path, satisfying the SVM trigger.

---

## Non-Goals (explicit)

- No PDF download
- No Marker parse
- No ingest / index
- No SVM training (this activates only after ≥30+30 labels)
- No L2 (PaperQA2) work
- No L4 (multi-source harvesters) work
- No Docker / n8n / trading logic

---

## Deferred: Marker Docker/Linux IPC Warm-Worker (Option A)

The Marker Docker/Linux IPC warm-worker (Queue v1) was deferred when queue v0 shipped
(2026-05-05). It is not canceled. This deferral is recorded explicitly here as a
required future action:

> **Marker Docker/Linux IPC warm-worker (Option A) must be revisited after this L3/SVM
> development stream completes, or before L2 production launch (whichever comes first).**

L1 Marker production rollout remains blocked until the warm-worker validates ≥3 papers
at ≤10s/paper (papers 2+). The queue infrastructure (queue.jsonl, results.jsonl, CLI
surface, `is_marker_ready()` gate, Marker-only indexing gate) is all shipped in v0.
The IPC layer that keeps Marker models loaded across papers on Linux/Docker is the
outstanding v1 deliverable.

Resume trigger: `docs/CURRENT_DEVELOPMENT.md` Paused/Deferred row — "RIS Marker Queue —
Docker IPC Warm-Worker (v1)".

---

## Files Changed This Session

| Doc | Change |
|-----|--------|
| `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Prefetch Label Discovery Mode.md` | Created — L3.2 work packet, status active/ready, 5 acceptance gates, deferred warm-worker reminder |
| `docs/CURRENT_DEVELOPMENT.md` | Feature 3 added: L3.2 Prefetch Label Discovery Mode; Notes for Architect updated |
| `docs/obsidian-vault/Claude Desktop/Current-Focus.md` | L3 row updated to show L3.2 active; label counts (7/20) added; deferred warm-worker reminder added |
| `docs/INDEX.md` | This dev log entry added to Recent Dev Logs |
| `docs/dev_logs/2026-05-05_l3-2-prefetch-label-discovery-activation.md` | This file |

---

## Codex Review

Tier: Skip — docs-only session. No runtime code, tests, Docker, or trading logic touched.
