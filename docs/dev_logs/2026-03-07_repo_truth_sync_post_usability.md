# Dev Log: Repo Truth Sync — Post-Usability Pass

**Date:** 2026-03-07
**Branch:** simtrader

---

## Objective

Sync the top-level source-of-truth docs (`README.md`, `docs/CURRENT_STATE.md`,
`docs/ROADMAP.md`) to match the usability pass completed earlier today. The
usability pass changed `polytool/__main__.py`, Studio `index.html`,
`OPERATOR_QUICKSTART.md`, `LOCAL_RAG_WORKFLOW.md`, and `INDEX.md` but did NOT
update the top-level docs.

---

## Files Changed

| File | Change |
|------|--------|
| `README.md` | Added link to `OPERATOR_QUICKSTART.md` below status table; added `rag-refresh` to Quick Reference |
| `docs/CURRENT_STATE.md` | Added `rag-refresh` to "What exists today"; added grouped CLI help and Studio Grafana card notes; added `rag-refresh` entry to CLI commands section |
| `docs/ROADMAP.md` | Added "Done: Usability Pass (2026-03-07)" section in Track B with all six shipped improvements listed |
| `docs/dev_logs/2026-03-07_repo_truth_sync_post_usability.md` | This file |

No code was changed. No tests were changed. No gate thresholds were changed.

---

## Stale Statements Corrected

### README.md

**Before**: Quick Reference used `python -m polytool rag-index` with no mention
of the simpler one-command path.

**After**: Quick Reference now lists `rag-refresh` first with an explanatory
comment; `rag-index` retained as the advanced form.

**Before**: No link to `OPERATOR_QUICKSTART.md` in the status section.

**After**: A single bolded line points operators to
`docs/OPERATOR_QUICKSTART.md` directly below the current status table.

### docs/CURRENT_STATE.md

**Before**: "What exists today" listed RAG indexing/retrieval but not the
`rag-refresh` alias shipped in the usability pass.

**After**: `rag-refresh` documented as the one-command rebuild path.

**Before**: "What exists today" had no mention of the grouped CLI help
reorganization or the Studio Grafana deep-link card.

**After**: Both improvements are noted under the relevant surface areas.

**Before**: CLI commands section listed `rag-index` only.

**After**: `rag-refresh` listed first (simple path); `rag-index` noted for
incremental and advanced use.

### docs/ROADMAP.md

**Before**: Track B "Done" list ended at the Hypothesis Registry (2026-03-05).
The usability improvements shipped 2026-03-07 had no roadmap entry.

**After**: "Done: Usability Pass (2026-03-07)" section inserted between the
Track B Foundation block and the Hypothesis Registry block, listing all six
shipped improvements.

---

## Final High-Level Repo Status (2026-03-07)

| Area | Status |
|------|--------|
| Research loop (Track B) | Complete: wallet-scan, alpha-distill, hypothesis registry, experiment skeleton |
| RAG | Operational: `rag-refresh` one-command rebuild; grouped help; full index + hybrid query |
| SimTrader Studio | Operational: sessions, tapes, reports, OnDemand replay, Grafana deep links |
| Grafana | Operational: User Trades, PnL, Strategy Detectors, Arb Feasibility, Liquidity Snapshots |
| Gate 1 (Replay) | **PASSED** |
| Gate 2 (Sweep) | Not passed — tooling ready, needs eligible tape with `executable_ticks > 0` |
| Gate 3 (Shadow) | Blocked behind Gate 2 |
| Gate 4 (Dry-Run Live) | **PASSED** |
| Current blocker | Edge scarcity: `yes_ask + no_ask < 0.99` has not appeared in observed markets |
| Current next step | Bounded live dislocation trial via `watch-arb-candidates` on 3–5 catalyst markets |
| Opportunity Radar | Deferred until first clean Gate 2 → Gate 3 progression |
| Wallet anomaly alerts | Deferred (backlog entry in `docs/TODO.md`) |
| Stage 0 paper-live | Blocked until all four gates pass |
| Stage 1 live capital | Blocked until Stage 0 completes cleanly |

---

## Roadmap Wording Adjusted

- Track B "Done" list extended with the usability pass entry (2026-03-07).
- No gate thresholds, no milestone order, no deferred-trigger conditions were
  changed.
