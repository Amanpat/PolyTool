# 2026-04-27 — RIS Marker Layer 1 Documentation Close-out

## Objective

Docs-only close-out for the RIS Marker Layer 1 scaffold after four implementation
prompts (A–D). No code was changed in this pass.

---

## Documents Created / Updated

### Created

| File | Purpose |
|---|---|
| `docs/features/ris-marker-structural-parser-scaffold.md` | Canonical feature doc — full state after Prompts A–D; accurate default (pdfplumber); truthful LLM section; two-layer concurrency guard; benchmark table; deferred items list |
| `docs/dev_logs/2026-04-27_ris-marker-closeout-docs.md` | This file |

### Updated

| File | Change |
|---|---|
| `docs/features/FEATURE-ris-marker-pdf-parser.md` | Superseded with redirect notice — Prompt B doc had stale info (`auto` default, `marker_llm_boost`) that was corrected in Prompts C/D; preserved as historical artifact only |
| `docs/INDEX.md` | Added feature row for `ris-marker-structural-parser-scaffold.md`; added all 5 Marker dev logs to Recent Dev Logs section (newest first) |
| `docs/CURRENT_DEVELOPMENT.md` | Added row to Recently Completed: "RIS Marker Layer 1 scaffold (experimental) — not production rollout" |

---

## INDEX.md Links Added

Feature section:
- `features/ris-marker-structural-parser-scaffold.md` — Experimental; Layer 1 scaffold

Dev log section (all inserted above the 2026-04-22 entries):
- `dev_logs/2026-04-27_ris-marker-closeout-docs.md` — this file
- `dev_logs/2026-04-27_ris-marker-timeout-concurrency-fix.md` — Prompt D
- `dev_logs/2026-04-27_ris-marker-timeout-llm-truthfulness.md` — Prompt C
- `dev_logs/2026-04-27_ris-marker-hardening-validation.md` — Prompt B
- `dev_logs/2026-04-27_codex-review-ris-marker-core.md` — Codex review
- `dev_logs/2026-04-27_ris-marker-core-integration.md` — Prompt A

---

## CURRENT_DEVELOPMENT.md Decision

Marker Layer 1 was never listed as an Active feature (it was background hardening
work alongside RIS Phase 2A). Added one row to Recently Completed with explicit
"**not production rollout**" language. No Active slot was consumed.

---

## Validation

```
git diff --name-only HEAD
```

Changed files:
- `docs/features/ris-marker-structural-parser-scaffold.md` (new)
- `docs/features/FEATURE-ris-marker-pdf-parser.md` (superseded)
- `docs/INDEX.md` (feature row + 6 dev log rows)
- `docs/CURRENT_DEVELOPMENT.md` (Recently Completed row)
- `docs/dev_logs/2026-04-27_ris-marker-closeout-docs.md` (new)

No code files modified.

---

## Remaining Limitations (carried forward into docs)

1. Marker on CPU times out at 300 s for all tested papers. GPU required for
   production use.
2. Timed-out Marker thread cannot be killed on Windows. At most one zombie
   thread per process lifetime (`_MARKER_DISABLED` prevents stacking).
   True cancellation needs a process boundary — deferred.
3. `RIS_MARKER_LLM=1` records intent only; no LLM call is wired. This is a
   Layer 2 deliverable.
4. Retrieval quality claims cannot be made until Layer 2 structured chunking
   is implemented and benchmarked.
5. Marker is not in the base Docker image. Adding it requires Director decision
   and GPU pass-through planning.
