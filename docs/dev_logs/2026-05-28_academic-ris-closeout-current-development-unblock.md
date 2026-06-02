# Academic RIS Closeout - CURRENT_DEVELOPMENT Unblock

**Date:** 2026-05-28
**Scope:** Docs-only closeout unblock.
**Files changed:** `docs/CURRENT_DEVELOPMENT.md`; this dev log.

## Why

Codex blocked Academic RIS demo-ready v1 closeout because `docs/CURRENT_DEVELOPMENT.md`
still contained two current-facing stale statements that said L2.1 ChromaDB academic
retrieval remained deferred. That contradicted L2.1 completion on 2026-05-25 and
developer/operator demo-ready v1 status on 2026-05-28.

## Files Changed

- `docs/CURRENT_DEVELOPMENT.md` - qualified the two older 2026-05-09 notes as historical
  and pointed them to the current state:
  - L2.1 ChromaDB semantic retrieval is complete as of 2026-05-25.
  - Academic RIS is developer/operator demo-ready v1 as of 2026-05-28.
  - Batch C/D are deferred to post-v1 hardening.
  - The pipeline is not production-ready.
- `docs/dev_logs/2026-05-28_academic-ris-closeout-current-development-unblock.md` -
  this handoff record.

No implementation code, tests, runtime artifacts, Batch C/D, benchmark baselines, or
unrelated vault/root docs were edited.

## Exact Stale Statements Fixed

1. Recently Completed table row for the 2026-05-09 3-paper validation previously ended:

```text
SSRN/NBER and ChromaDB academic retrieval (L2.1) remain deferred.
```

Replacement:

```text
Historical note: at this 2026-05-09 checkpoint, SSRN/NBER and L2.1 ChromaDB semantic retrieval were not yet complete; L2.1 completed on 2026-05-25, and Academic RIS reached developer/operator demo-ready v1 on 2026-05-28.
```

2. Architect notes entry for the 2026-05-09 operator-tested v1 run previously said:

```text
SSRN/NBER and ChromaDB academic retrieval (L2.1) remain deferred.
```

Replacement:

```text
Historical note: at this 2026-05-09 checkpoint, SSRN/NBER and L2.1 ChromaDB semantic retrieval were not yet complete; L2.1 completed on 2026-05-25. Academic RIS reached developer/operator demo-ready v1 on 2026-05-28; Batch C/D are deferred to post-v1 hardening, and the pipeline is not production-ready.
```

## Commands Run

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
rg -n -i "ChromaDB academic retrieval|ChromaDB academic path|Chroma deferred|not semantic|not vector retrieval|semantic retrieval deferred" docs/CURRENT_DEVELOPMENT.md
```

Pre-fix output showed the stale 2026-05-09 row and note plus the already-correct
L2.1 complete statement:

```text
docs\CURRENT_DEVELOPMENT.md:93:| RIS Academic Pipeline - 3-Paper Operator Validation ... SSRN/NBER and ChromaDB academic retrieval (L2.1) remain deferred. |
docs\CURRENT_DEVELOPMENT.md:153:- **RIS L2 Academic Query is COMPLETE (2026-05-09).** ... **ChromaDB academic path COMPLETE (L2.1, 2026-05-25):** ... semantic vector search is now the primary retrieval path. ...
docs\CURRENT_DEVELOPMENT.md:155:- **RIS academic pipeline is operator-tested v1 (2026-05-09).** ... SSRN/NBER and ChromaDB academic retrieval (L2.1) remain deferred. ...
```

```powershell
rg -n -i "ChromaDB academic retrieval remains deferred|ChromaDB academic path deferred|Chroma deferred|not semantic|not vector retrieval|semantic retrieval deferred" docs/CURRENT_DEVELOPMENT.md docs/CURRENT_STATE.md docs/INDEX.md docs/features/FEATURE-ris-academic-demo-ready-v1.md
```

Post-fix output:

```text
docs/features/FEATURE-ris-academic-demo-ready-v1.md:180:(retrieval_mode=lexical, not semantic). The false positive is in the lexical fallback path
```

Interpretation: the only hit is the intentional weather false-positive caveat. It is not
a stale Chroma-deferred claim and was preserved per instruction not to hide caveats.

```powershell
rg -n -i "ChromaDB academic retrieval.*remain deferred|ChromaDB academic path deferred|Chroma deferred|not vector retrieval|semantic retrieval deferred|Retrieval is conservative substring/phrase matching" docs/CURRENT_DEVELOPMENT.md docs/CURRENT_STATE.md docs/INDEX.md docs/features/FEATURE-ris-academic-demo-ready-v1.md
```

Output:

```text
<no output; rg exited 1>
```

```powershell
rg -n -i "not semantic" docs/CURRENT_DEVELOPMENT.md docs/CURRENT_STATE.md docs/INDEX.md docs/features/FEATURE-ris-academic-demo-ready-v1.md
```

Output:

```text
docs/features/FEATURE-ris-academic-demo-ready-v1.md:180:(retrieval_mode=lexical, not semantic). The false positive is in the lexical fallback path
```

## Decisions

- Kept the 2026-05-09 notes as history instead of deleting them.
- Removed current-facing stale Chroma-deferred wording.
- Preserved caveats: weather lexical false positive, Docker Chroma gap, JIT cache uncertainty,
  Batch C/D deferred, and not-production-ready status.
- Did not run Batch C/D or validation.

## Codex BLOCK Status

Resolved. The two stale `CURRENT_DEVELOPMENT.md` Chroma-deferred statements identified by
Codex are no longer current-facing and now point to the completed L2.1/demo-ready v1 state.

## Final Review Readiness

Final closeout review can be rerun. Remaining `not semantic` text is an intentional caveat
about lexical fallback behavior, not a stale retrieval-status contradiction.

