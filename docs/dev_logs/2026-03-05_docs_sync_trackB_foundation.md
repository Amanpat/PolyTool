# Dev Log: Docs Sync — Track B Foundation (2026-03-05)

## Objective

Synchronize repository documentation with the implemented Track B foundation:
Wallet-Scan v0, Alpha-Distill v0, and RAG/llm-bundle reliability hardening.

Scope: documentation only. No code or CLI behavior changed.

---

## Files Touched

| File | Change |
|------|--------|
| `docs/CURRENT_STATE.md` | Added "Recently completed (Track B foundation)" section, "Primary research loop (today)" pipeline text, and "Known limitations" list |
| `docs/ROADMAP.md` | Added "Track B - Research Loop Foundation [COMPLETE]" section with acceptance criteria + done artifacts; added "Planned: Hypothesis Registry v0" next milestone |
| `docs/ARCHITECTURE.md` | Added "Research loop (Track B)" dataflow block and "Research artifacts layout" directory tree |
| `docs/INDEX.md` | Added "Features" table (wallet-scan-v0, alpha-distill-v0), added two new rows to "Specs" table, added "Dev Logs (recent)" table |
| `docs/features/wallet-scan-v0.md` | New — feature doc for wallet-scan v0 |
| `docs/features/alpha-distill-v0.md` | New — feature doc for alpha-distill v0 |
| `docs/dev_logs/2026-03-05_docs_sync_trackB_foundation.md` | This file |

---

## What changed and why

### CURRENT_STATE.md

Added three new sections:

1. **"Recently completed (Track B foundation)"**: summarizes wallet-scan v0, alpha-distill v0, and five RAG/llm-bundle hardening items. Each item has CLI, input, output, and links to spec + feature doc.

2. **"Primary research loop (today)"**: a `wallets.txt → wallet-scan → alpha-distill → review` pipeline text diagram showing the end-to-end research flow.

3. **"Known limitations"**: four concrete limitations — category coverage dependency, CLV snapshot timing, lack of multi-window persistence, sequential execution — plus a fee-estimate caveat.

The top "What exists today" bullet list gained two new bullets for `wallet-scan` and `alpha-distill`.

### ROADMAP.md

Added a "Track B" section between Roadmap 5 and Roadmap 6 to capture work that runs parallel to the numbered infrastructure roadmaps.

- **[COMPLETE] Track B Foundation**: 8 items checked, acceptance criteria (6 points), done artifacts list.
- **[NOT STARTED] Hypothesis Registry v0 + Experiment Runner skeleton**: 5 planned items, acceptance criteria, kill condition. Research-only; no live trading language.

### ARCHITECTURE.md

Added two new blocks after the existing data flow diagram:
- **Research loop (Track B)**: text diagram from `wallets.txt` through `wallet-scan` → `alpha-distill` → review loop, including artifact paths.
- **Research artifacts layout**: directory tree showing where wallet-scan and alpha-distill write their outputs relative to `artifacts/dossiers/`.

### INDEX.md

- Added a new "Features" section with links to the two new feature docs.
- Added `SPEC-wallet-scan-v0.md` and `SPEC-alpha-distill-v0.md` to the Specs table.
- Added a "Dev Logs (recent)" table covering the 2026-03-04 and 2026-03-05 work.

### docs/features/wallet-scan-v0.md (new)

Plain-English feature doc: what it does, CLI usage, input format, output files, field descriptions, failure handling, leaderboard ordering, limitations, and pointer to alpha-distill.

### docs/features/alpha-distill-v0.md (new)

Plain-English feature doc: what it does, CLI usage, segment dimensions, ranking philosophy and formula, candidate JSON schema summary, friction risk flags, limitations, and full typical research loop example.

---

## Verification steps

### Referenced files exist

```
docs/specs/SPEC-wallet-scan-v0.md        ✓ (exists)
docs/specs/SPEC-alpha-distill-v0.md      ✓ (exists)
docs/specs/LLM_BUNDLE_CONTRACT.md        ✓ (exists)
docs/features/wallet-scan-v0.md          ✓ (just created)
docs/features/alpha-distill-v0.md        ✓ (just created)
tools/cli/wallet_scan.py                 ✓ (exists)
tools/cli/alpha_distill.py               ✓ (exists)
tools/cli/rag_run.py                     ✓ (exists)
packages/polymarket/rag/defaults.py      ✓ (exists)
tests/test_wallet_scan.py                ✓ (exists)
tests/test_alpha_distill.py              ✓ (exists)
```

### No live-trading language

All new doc text uses research-only framing: "research-only", "no order placement",
"no external LLM API calls", "manual review". No doc claims Track A (live execution)
is implemented.

### PLAN_OF_RECORD.md not touched

`docs/PLAN_OF_RECORD.md` was not modified.

### Relative links checked

All new cross-doc links use relative paths consistent with the `docs/` directory
hierarchy (e.g., `../specs/SPEC-wallet-scan-v0.md` from `docs/features/`,
`features/wallet-scan-v0.md` from `docs/INDEX.md`).

---

## Not implemented

- No new code or CLI features.
- No refactoring of existing CLIs.
- `docs/PLAN_OF_RECORD.md` unchanged.
- No aspirational claims without "planned/next" labeling.
