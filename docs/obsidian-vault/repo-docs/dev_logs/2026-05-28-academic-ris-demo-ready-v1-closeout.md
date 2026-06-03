---
title: Academic Ris Demo Ready V1 Closeout
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-28_academic-ris-demo-ready-v1-closeout.md
last_synced: '2026-06-03T02:26:56Z'
lifecycle: reviewed
generator: repo-sync
---

# Academic RIS — Developer/Operator Demo-Ready v1 Closeout

**Date:** 2026-05-28
**Author:** Claude Code (Sonnet 4.6)
**Scope:** Documentation closeout only. No implementation code, no test changes, no runtime artifact mutation, no Batch C/D.

---

## Summary

Academic RIS is developer/operator demo-ready v1 as of 2026-05-28. This log records the
three-step completion protocol: feature doc created, INDEX updated, CURRENT_DEVELOPMENT
updated. Caveats are preserved visibly in all three documents.

Codex verdict on Batch B validation: **PASS WITH CONCERNS** — approved for demo-ready v1
closeout with named caveats (lexical false positive, Docker Chroma gap, JIT cache
uncertainty, Batch C/D deferred).

---

## Files Changed

| File | Change | Why |
|------|--------|-----|
| `docs/features/FEATURE-ris-academic-demo-ready-v1.md` | Created | Feature doc (completion protocol step 1) |
| `docs/INDEX.md` | Added feature doc row + 3 dev log rows | Completion protocol step 2 |
| `docs/CURRENT_STATE.md` | Appended demo-ready v1 section | Truth record updated |
| `docs/CURRENT_DEVELOPMENT.md` | Fixed 2 stale notes; added Recently Completed row | Completion protocol step 3 |
| `docs/dev_logs/2026-05-28_academic-ris-demo-ready-v1-closeout.md` | Created | This log (mandatory per policy) |

No implementation code, tests, runbooks (beyond status note scope), queue artifacts, or
Batch C/D artifacts were touched.

---

## Evidence Summarized

### Cumulative corpus (post-Batch-B)

| Metric | Value |
|--------|-------|
| Queue done | 20 |
| Queue failed | 0 |
| Queue sidecar_count | 20 |
| Chroma chunks | 917 |
| Chroma unique papers | 21 |
| Chroma missing_ks_doc_id | 0 |
| Chroma ks_doc_id_not_in_ks | 0 |

### Batch B (10 medium papers, 2026-05-28)

- All 10: `body_source=marker`, `marker_ready=True`, `ipc_warm_worker_used=True`
- 505 KS chunks, 2490 claims extracted
- Parse range: 31s (fast, short PDF) to 3249s (eq-heavy, JIT cold-start)
- All 10 within 7200s timeout
- 7 topic query probes: `had_fallback=False`, `retrieval_mode=semantic`
- Rejection probe (protein folding): `had_fallback=True` ✅
- Rejection probe (weather forecast): 1 lexical false positive from arxiv:2605.00493 ⚠️

### Codex verification (independent)

Codex reviewed artifacts, ran `check-chroma-links`, ran 5 query probes independently.
Confirmed parse evidence matches, Chroma clean, relevant queries return expected Batch B
papers with `retrieval_mode=semantic`. Verdict: PASS WITH CONCERNS (named, not blockers).

---

## Closeout Protocol Checklist

| Item | Status |
|------|--------|
| Feature doc exists (`docs/features/FEATURE-ris-academic-demo-ready-v1.md`) | ✅ Created |
| INDEX.md updated (feature doc row + dev log rows added) | ✅ Done |
| CURRENT_DEVELOPMENT.md updated (Recently Completed row added) | ✅ Done |
| CURRENT_STATE.md updated (demo-ready v1 section appended) | ✅ Done |
| Stale "not semantic/vector retrieval" note fixed in CURRENT_DEVELOPMENT.md | ✅ Fixed |
| Stale "ChromaDB academic path deferred" note fixed in CURRENT_DEVELOPMENT.md | ✅ Fixed |
| No implementation code changed | ✅ Confirmed |
| No Batch C/D executed | ✅ Confirmed |
| Caveats visible in feature doc | ✅ All 4 Codex caveats present |
| "demo-ready" language used (not "production-ready") | ✅ Consistent |

---

## Caveats Recorded

1. **Lexical false positive** — `weather forecast` returns 1 citation from arxiv:2605.00493
   (paper mentions weather as a control category). Semantic guard is working; false positive
   is in lexical fallback. Post-v1 hardening item.

2. **Docker Chroma gap** — `ris-scheduler-gpu` lacks `chromadb`. Chroma embedding requires
   Windows host via `index-done --reindex-chroma --force`. NTFS colon handled by
   `cid.replace(":", "")` fallback. Operational friction, not a correctness defect.

3. **JIT cache persistence unresolved** — `TORCHINDUCTOR_CACHE_DIR` empty after batch
   runs. In-session reuse works; cross-restart not confirmed. Run `jit-cache-check`
   before large batches.

4. **Batch C/D deferred** — 9 pending Tier-3/large papers. `arxiv:2409.02025` and
   `arxiv:1011.6402` require Tier-3 operator approval. Do not run without JIT cache
   verification first.

---

## Commands Run (doc changes only)

No shell commands were run for this closeout. All changes are text file edits. The
evidence from Batch B and Codex review is in the referenced dev logs.

Pre-edit stale-statement check:
- `CURRENT_DEVELOPMENT.md` line ~144: "not semantic or vector retrieval" → confirmed stale (L2.1 shipped)
- `CURRENT_DEVELOPMENT.md` line ~152: "ChromaDB academic path deferred" → confirmed stale (L2.1 complete)

---

## Commit / Staging

This closeout touches only docs files. Suitable for a single commit:

```
docs(ris): academic pipeline demo-ready v1 closeout
```

Files to stage:
- `docs/features/FEATURE-ris-academic-demo-ready-v1.md`
- `docs/INDEX.md`
- `docs/CURRENT_STATE.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/dev_logs/2026-05-28_academic-ris-demo-ready-v1-closeout.md`

---

## Next Recommended Work Item

**Immediate (if pipeline work continues):**
1. Resolve Docker Chroma gap (add `chromadb` to `ris-scheduler-gpu` image or finalize
   Windows-host path as permanent documented practice).
2. Run `jit-cache-check` inside Docker before any Batch C planning.
3. Operator decision on Tier-3 papers (`arxiv:2409.02025`, `arxiv:1011.6402`) before
   Batch C.

**Post-v1 hardening (when prioritized):**
- Improve lexical false positive rejection for unrelated-domain queries.
- Snippet quality pass for table-heavy papers (reference-section snippets).
- Bulk pdfplumber corpus re-ingest with Marker.

**Deferred (not blocking demo-ready v1):**
- Batch C/D execution.
- Production hardening (throughput SLAs, automated Chroma embedding, SVM enforce).
