---
title: Ris Academic Query Natural Language Normalization Docs Sync
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-09_ris-academic-query-natural-language-normalization-docs-sync.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# RIS Academic Query — Natural-Language Normalization: Docs Sync (2026-05-09)

**Date:** 2026-05-09
**Type:** Docs-only sync
**Track:** Research Intelligence System — L2 Academic Query

---

## Summary

This is a docs-only closeout sync for the query-layer normalization fix applied to
`academic_query.py`. The fix resolves a subtle retrieval failure where simple
natural-language questions with question preambles (e.g., "what are prediction markets")
returned no citations even though the same topic phrase without the preamble
("prediction markets") worked correctly.

The academic pipeline is confirmed **development-complete / operator-tested v1**. This
session only updates docs; no code or tests were written here.

---

## Root Cause

`research-query` used verbatim substring matching against the KnowledgeStore. The
KS query checked whether claim text or source metadata contained the full question
string character-for-character. This meant:

- `"prediction markets"` → matched correctly (topic phrase in claim text)
- `"what are prediction markets"` → no match (full string not in claim text)

The query string was passed to the KS retriever unchanged. The fix adds
`_normalize_question()` and `_build_sub_queries()` to `packages/research/synthesis/academic_query.py`
so simple question preambles are stripped **for retrieval only**. The original question
is preserved in the JSON output.

---

## Fix Summary

**File modified:** `packages/research/synthesis/academic_query.py`

**New functions:**

| Function | Purpose |
|----------|---------|
| `_normalize_question(q)` | Strips common question preambles from the start of a question string (e.g., "what are", "explain", "how does") and returns the normalized retrieval phrase |
| `_build_sub_queries(question)` | Returns a list of query strings: the original question plus the normalized form (deduplicated) so both are used in the multi-angle retrieval pass |

**Behavior contract:**

| Input | Retrieval also searches |
|-------|------------------------|
| `"prediction markets"` | `"prediction markets"` (no change — already a phrase) |
| `"what are prediction markets"` | `"prediction markets"` (preamble stripped) |
| `"explain sports betting markets"` | `"sports betting markets"` (preamble stripped) |
| `"avellaneda stoikov model"` | `"avellaneda stoikov model"` (no change) |

**Unrelated questions** (e.g., "what is the weather today") still return no citations
with the correct no-match warning when academic docs exist but no claim text matches.

**JSON output:** The `question` field in output always reflects the **original**
question string. Only retrieval uses the normalized form.

---

## No-Result Cases

After the fix, `research-query` has two distinct no-result cases:

| Case | `had_fallback` | Cause | Action |
|------|----------------|-------|--------|
| Empty academic corpus | `true` | KnowledgeStore has no academic source documents | Run `index-done` first or confirm `warm-process` produced `marker_ready=True` results |
| Docs exist but no matching claims | `true` | Academic docs are indexed but no claim text matches the query (including normalized form) | Expand corpus with `research-harvest` + `warm-process` + `index-done`, or try a different topic phrase |

Both cases return `had_fallback=true`. The warning message text distinguishes them at
runtime. The retrieval system is conservative substring/normalized phrase matching — not
semantic/vector retrieval. Queries for topics not covered by any indexed paper body text
will not return results.

---

## Test Results

| Suite | Result |
|-------|--------|
| `tests/test_research_query.py` | **54 passed** (was 36 before normalization tests added) |
| Adjacent RIS suite (test_ris_marker_queue, test_ris_claim_extraction, test_ris_evaluation, test_academic_harvesters) | **203 passed, 1 skipped** |

No regressions in adjacent suites. The 1 skip is the existing Linux-only IPC platform
skip on Windows (pre-existing, correct behavior).

---

## Files Updated This Session

| File | Change |
|------|--------|
| `docs/dev_logs/2026-05-09_ris-academic-query-natural-language-normalization-docs-sync.md` | Created (this file) |
| `docs/CURRENT_STATE.md` | Added query normalization sub-note in L2 section; updated test count 36→54 |
| `docs/CURRENT_DEVELOPMENT.md` | Added architect note about query normalization fix and updated test count |
| `docs/INDEX.md` | Added this dev log to Recent Dev Logs |
| `docs/features/FEATURE-ris-l2-academic-query.md` | Documented two no-result cases; added normalization section with examples; updated test count 36→54 |
| `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` | Updated L2 query section with natural-language query examples and no-result case guidance |
| `docs/obsidian-vault/Claude Desktop/Current-Focus.md` | Added session context for query normalization fix |

---

## Grep Verification (run after edits)

```bash
rg -n "what are prediction markets|normalize|normalization|no relevant claims|No academic documents found|semantic|vector|Docker/GPU|ipc_warm_worker" \
  docs/CURRENT_STATE.md \
  docs/CURRENT_DEVELOPMENT.md \
  docs/INDEX.md \
  docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md \
  docs/features/FEATURE-ris-l2-academic-query.md \
  "docs/obsidian-vault/Claude Desktop/Current-Focus.md"
```

**Expected results:**

- `normalize` / `normalization` — appears in docs describing the fix; OK
- `what are prediction markets` — appears only in examples/tables showing it NOW WORKS; no doc says it fails
- `No academic documents found` — appears only as a runtime warning description; OK
- `semantic` / `vector` — must not appear as a claim about current retrieval capability (only as deferred/not-implemented notes)
- `Docker/GPU` — must appear only as optional performance/infra follow-up language; not as passed validation claim

---

## Caveats and Scope Guards

- **Conservative retrieval only.** The normalization fix is substring/phrase-based.
  It is NOT semantic or vector retrieval. Do not describe it as such.
- **Docker/GPU IPC 3-paper batch**: validated separately on 2026-05-08 with
  `ipc_warm_worker_used=true`. That validation stands. No new Docker validation was
  run or claimed in this session.
- **ChromaDB academic retrieval (L2.1)**: still deferred. `body_source` is not in
  ChromaDB chunk metadata. This is unchanged.
- **SSRN/NBER**: still deferred. Only arXiv papers in the validated corpus.

---

## Remaining Follow-Ups (all optional)

| Item | Type | Blocker? |
|------|------|---------|
| Docker/GPU IPC 3-paper batch repeat with normalization fix | Performance/infra | No |
| ChromaDB academic retrieval (L2.1 — body_source in chunk metadata) | Retrieval quality | No |
| Discovery quality tuning (SSRN/NBER, L3 coverage expansion) | Scope | No |

**Recommendation:** Move future debugging/patching work for the RIS academic pipeline
to a new chat session. This is the closeout sync before that transition.
