---
title: Codex Final Review Academic Ris Demo Ready V1
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-28_codex-final-review-academic-ris-demo-ready-v1.md
last_synced: '2026-06-03T02:26:56Z'
lifecycle: reviewed
generator: repo-sync
---

# Codex Final Review - Academic RIS Demo-Ready v1 Closeout

**Date:** 2026-05-28
**Scope:** Final docs-only closeout review plus this dev log. No implementation code, tests,
runtime artifacts, Batch C/D, benchmark baselines, or unrelated docs changed.
**Verdict:** PASS - Academic RIS demo-ready v1 is formally closed.

## Files reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/CURRENT_STATE.md`
- `docs/INDEX.md`
- `docs/features/FEATURE-ris-academic-demo-ready-v1.md`
- `docs/dev_logs/2026-05-28_academic-ris-demo-ready-v1-closeout.md`
- `docs/dev_logs/2026-05-28_codex-review-academic-ris-demo-ready-v1-closeout.md`
- `docs/dev_logs/2026-05-28_academic-ris-closeout-current-development-unblock.md`

## Commands run and output

### Session hygiene

```powershell
git status --short
```

Output: dirty tree with many pre-existing modified/deleted/untracked files, including the
Academic RIS closeout docs and unrelated Obsidian vault changes. I did not modify or revert
pre-existing changes.

```powershell
git log --oneline -5
```

Output:

```text
c249ff5 docs(ris): operator-path simplicity test - 9 runbook corrections, readiness verdict
b921857 fix(ris): L2.1 one-paper acceptance repair - Chroma embed, span strip, NTFS fallback
7fc6bf2 fix(ris): L2.1 Deliverable B - offline-safe semantic fallback, resolves Codex BLOCK
15ef471 docs(ris): repo hygiene before L2.1 Deliverable A - closeout log
3348e79 feat(ris): L2.1 Deliverable C - display-only snippet sanitation
```

```powershell
python -m polytool --help
```

Output: command succeeded and printed the PolyTool command list, including RIS commands
`research-eval`, `research-precheck`, `research-ingest`, `research-marker-queue`,
`research-query`, and `research-harvest`.

### Current-facing stale-language search

```powershell
rg -n -i "ChromaDB academic retrieval remains deferred|ChromaDB academic path deferred|Chroma deferred|semantic retrieval deferred|not semantic|not vector retrieval|29-paper complete|production-ready" docs/CURRENT_STATE.md docs/CURRENT_DEVELOPMENT.md docs/INDEX.md docs/features/FEATURE-ris-academic-demo-ready-v1.md
```

Output:

```text
docs/features/FEATURE-ris-academic-demo-ready-v1.md:14:**Readiness level:** Developer/operator demo-ready. **NOT production-ready.** See caveats.
docs/features/FEATURE-ris-academic-demo-ready-v1.md:180:(retrieval_mode=lexical, not semantic). The false positive is in the lexical fallback path
docs/CURRENT_DEVELOPMENT.md:92:| RIS Academic Pipeline - Developer/Operator Demo-Ready v1    | 2026-05-28 | RIS      | `docs/features/FEATURE-ris-academic-demo-ready-v1.md` - Batch B (10 medium papers): done=20, failed=0, sidecar_count=20; Chroma 917 chunks / 21 papers / 0 orphans; 7 semantic probes pass. Codex PASS WITH CONCERNS. Caveats: weather lexical false positive (non-blocking), Docker Chroma gap (Windows host fallback), JIT cache unresolved, Batch C/D deferred. Not production-ready. |
docs/CURRENT_DEVELOPMENT.md:155:- **RIS academic pipeline is operator-tested v1 (2026-05-09).** Full functional path (enqueue->warm-process->index-done->research-query) passed with 3 arXiv papers on Windows/local warm-thread path. Queue: 3 done, 0 failed. 79 chunks, 373 claims. `research-query` returned `had_fallback=false` for both queries (`"prediction markets"`, `"sports betting markets" --step-back`). `ipc_warm_worker_used=false` for this run - Docker/GPU IPC batch was a separate optional performance/infra follow-up, not a functional blocker. Historical note: at this 2026-05-09 checkpoint, SSRN/NBER and L2.1 ChromaDB semantic retrieval were not yet complete; L2.1 completed on 2026-05-25. Academic RIS reached developer/operator demo-ready v1 on 2026-05-28; Batch C/D are deferred to post-v1 hardening, and the pipeline is not production-ready. Dev log: `docs/dev_logs/2026-05-09_ris-academic-pipeline-3paper-operator-validation.md`.
docs/CURRENT_STATE.md:2019:Batch 2 is **not a valid 29-paper measurement**. Classification (production-ready /
docs/CURRENT_STATE.md:2161:**Not production-ready.** Parse throughput (~45-70s/paper warm, up to 3249s
```

Interpretation: no current-facing stale Chroma-deferred contradiction remains. Hits are
intentional not-production-ready warnings, the lexical fallback caveat, and a clearly
historical-at-the-time L2.1 note.

### Batch C/D and 29-paper claim search

```powershell
rg -n -i "Batch C.*(complete|passed|done)|Batch D.*(complete|passed|done)|full 29.*(complete|passed|done)|29-paper.*(complete|passed|done)|29 paper.*(complete|passed|done)" docs/CURRENT_STATE.md docs/CURRENT_DEVELOPMENT.md docs/INDEX.md docs/features/FEATURE-ris-academic-demo-ready-v1.md
```

Output:

```text
docs/CURRENT_STATE.md:2057:**29-paper rerun:** QUEUE RESET COMPLETE (2026-05-28). `scaled_validation_queue_v2` is in a
```

Interpretation: no current-facing doc claims Batch C/D passed, Batch C/D completed, or full
29-paper validation passed. The only hit is queue reset completion, not validation completion.

### Unrelated-query rejection search

```powershell
rg -n -i "perfect|correctly rejected|unrelated.*reject|reject.*unrelated" docs/CURRENT_STATE.md docs/CURRENT_DEVELOPMENT.md docs/INDEX.md docs/features/FEATURE-ris-academic-demo-ready-v1.md
```

Output:

```text
docs/features/FEATURE-ris-academic-demo-ready-v1.md:152:| Unrelated rejection (protein folding) | had_fallback=True |
docs/features/FEATURE-ris-academic-demo-ready-v1.md:211:| Lexical false positive fix | Medium | Improve unrelated-query rejection in lexical fallback path |
docs/CURRENT_STATE.md:1774:- 39-sample perfect score is encouraging but not statistically conclusive.
docs/CURRENT_STATE.md:2134:- Unrelated rejection (protein folding): `had_fallback=True`
```

Interpretation: no closeout doc claims unrelated-query rejection is perfect. The weather
lexical false-positive caveat remains preserved, and the unrelated rejection text is limited
to the protein-folding probe result.

### Closeout protocol evidence

```powershell
Select-String -Path docs\INDEX.md -Pattern "FEATURE-ris-academic-demo-ready-v1|Academic RIS.*Demo-Ready|RIS Academic Pipeline.*Demo-Ready|Batch C/D deferred|weather lexical" -Context 0,1
```

Output confirms:

```text
docs\INDEX.md:120:| [RIS Academic Pipeline - Demo-Ready v1](features/FEATURE-ris-academic-demo-ready-v1.md) | **COMPLETE 2026-05-28.** Developer/operator demo-ready v1: L1-L4 + L2.1 semantic retrieval. Batch B (10 medium papers): done=20, failed=0, sidecar_count=20; Chroma 917 chunks / 21 papers / 0 orphans. Codex PASS WITH CONCERNS. Caveats: weather lexical false positive, Docker Chroma gap, JIT cache unresolved, Batch C/D deferred. |
docs\INDEX.md:161:| [Academic RIS - Demo-Ready v1 Closeout](dev_logs/2026-05-28_academic-ris-demo-ready-v1-closeout.md) | 2026-05-28 | Docs-only closeout. Feature doc created, INDEX + CURRENT_STATE.md + CURRENT_DEVELOPMENT.md updated. Batch B: 10/10 marker_ready=True, 917 Chroma chunks / 21 papers / 0 orphans, 7 semantic probes pass. Weather lexical false positive documented. Batch C/D deferred. |
```

```powershell
Select-String -Path docs\CURRENT_DEVELOPMENT.md -Pattern "Developer/Operator Demo-Ready v1|L2\.1 ChromaDB semantic|ChromaDB academic path COMPLETE|Historical note|Batch C/D are deferred|Not production-ready|weather lexical false positive" -Context 0,1
```

Output confirms:

```text
docs\CURRENT_DEVELOPMENT.md:92:| RIS Academic Pipeline - Developer/Operator Demo-Ready v1    | 2026-05-28 | RIS      | `docs/features/FEATURE-ris-academic-demo-ready-v1.md` - Batch B (10 medium papers): done=20, failed=0, sidecar_count=20; Chroma 917 chunks / 21 papers / 0 orphans; 7 semantic probes pass. Codex PASS WITH CONCERNS. Caveats: weather lexical false positive (non-blocking), Docker Chroma gap (Windows host fallback), JIT cache unresolved, Batch C/D deferred. Not production-ready. |
docs\CURRENT_DEVELOPMENT.md:153:- **RIS L2 Academic Query is COMPLETE (2026-05-09).** ... **ChromaDB academic path COMPLETE (L2.1, 2026-05-25):** ... semantic vector search is now the primary retrieval path. ...
docs\CURRENT_DEVELOPMENT.md:155:- **RIS academic pipeline is operator-tested v1 (2026-05-09).** ... Historical note: at this 2026-05-09 checkpoint, SSRN/NBER and L2.1 ChromaDB semantic retrieval were not yet complete; L2.1 completed on 2026-05-25. Academic RIS reached developer/operator demo-ready v1 on 2026-05-28; Batch C/D are deferred to post-v1 hardening, and the pipeline is not production-ready. ...
```

```powershell
Select-String -Path docs\CURRENT_STATE.md -Pattern "Academic RIS.*developer/operator demo-ready v1|L2\.1 ChromaDB semantic retrieval COMPLETE|Batch C/D deferred|Not production-ready|weather forecast|Feature doc" -Context 0,2
```

Output confirms:

```text
docs\CURRENT_STATE.md:2119:Academic RIS is developer/operator demo-ready v1 as of 2026-05-28.
docs\CURRENT_STATE.md:2125:- L2.1 ChromaDB semantic retrieval COMPLETE (2026-05-25): 3-paper category sample PASS
docs\CURRENT_STATE.md:2144:1. **Lexical false positive** - `weather forecast` returns 1 lexical citation from
docs\CURRENT_STATE.md:2157:4. **Batch C/D deferred** - 9 pending Tier-3/large papers remain in queue.
docs\CURRENT_STATE.md:2161:**Not production-ready.** Parse throughput (~45-70s/paper warm, up to 3249s
docs\CURRENT_STATE.md:2165:**Feature doc:** `docs/features/FEATURE-ris-academic-demo-ready-v1.md`
```

```powershell
Select-String -Path docs\features\FEATURE-ris-academic-demo-ready-v1.md -Pattern "Developer/operator demo-ready|NOT production-ready|ChromaDB semantic|weather forecast|Batch C/D deferred|Do NOT run Batch C/D|not a production service|Unrelated rejection" -Context 0,1
```

Output confirms:

```text
docs\features\FEATURE-ris-academic-demo-ready-v1.md:9:# Feature: RIS Academic Pipeline - Developer/Operator Demo-Ready v1
docs\features\FEATURE-ris-academic-demo-ready-v1.md:14:**Readiness level:** Developer/operator demo-ready. **NOT production-ready.** See caveats.
docs\features\FEATURE-ris-academic-demo-ready-v1.md:28:| L2.1 | ChromaDB semantic vector retrieval as primary path | Complete 2026-05-25 |
docs\features\FEATURE-ris-academic-demo-ready-v1.md:152:| Unrelated rejection (protein folding) | had_fallback=True |
docs\features\FEATURE-ris-academic-demo-ready-v1.md:168:This is NOT a production service. The pipeline requires operator supervision for each
docs\features\FEATURE-ris-academic-demo-ready-v1.md:175:**Caveat 1 - Lexical false positive (`weather forecast`)**
docs\features\FEATURE-ris-academic-demo-ready-v1.md:198:**Caveat 4 - Batch C/D deferred; Tier-3 approval required**
docs\features\FEATURE-ris-academic-demo-ready-v1.md:202:Do NOT run Batch C/D without JIT cache verification and Tier-3 operator approval for
```

## Closeout protocol verdict

PASS.

- Feature doc exists: `docs/features/FEATURE-ris-academic-demo-ready-v1.md`.
- `docs/INDEX.md` links the feature doc and the closeout dev log.
- `docs/CURRENT_DEVELOPMENT.md` records Academic RIS demo-ready v1 in Recently Completed.
- Prior stale Chroma-deferred language is now qualified as historical-at-the-time or replaced
  with L2.1 complete language.

## Consistency verdict

PASS.

`docs/CURRENT_STATE.md`, `docs/CURRENT_DEVELOPMENT.md`, `docs/INDEX.md`, and
`docs/features/FEATURE-ris-academic-demo-ready-v1.md` agree that:

- Academic RIS is developer/operator demo-ready v1 as of 2026-05-28.
- The pipeline is not production-ready.
- L2.1 ChromaDB semantic retrieval is complete as of 2026-05-25.
- Batch C/D are deferred to post-v1 hardening and require JIT cache verification plus Tier-3
  operator approval for the named hard papers.
- The weather lexical-fallback false-positive caveat is preserved.

## Caveats preserved

- Weather lexical false positive from `arxiv:2605.00493`.
- Docker Chroma gap / Windows host fallback.
- JIT cache uncertainty before Batch C/D planning.
- Batch C/D deferred to post-v1 hardening.
- Not production-ready.
- No full 29-paper validation pass claimed.
- No perfect unrelated-query rejection claimed.

## Final verdict

PASS: Academic RIS demo-ready v1 is formally closed.

## Exact next action

Mark Academic RIS developer/operator demo-ready v1 closed in the operator handoff. The next
work should be post-v1 hardening planning, starting with Docker `jit-cache-check` before any
Batch C/D planning; Batch C/D still require explicit Tier-3 operator approval for
`arxiv:2409.02025` and `arxiv:1011.6402`.
