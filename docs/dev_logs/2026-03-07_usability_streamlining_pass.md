# Dev Log: Usability Streamlining Pass

**Date:** 2026-03-07
**Branch:** simtrader

---

## Objective

Make the current system easier to understand and easier to operate without
changing core strategy logic, gate thresholds, or live trading scope.

---

## UX Problems Found

### CLI discoverability
- `python -m polytool --help` listed 25+ commands in an unordered flat list.
- No grouping by workflow stage (research vs. execution vs. RAG vs. infra).
- New users had no way to know where to start.

### RAG indexing friction
- "Rebuild the RAG index" required knowing to use `rag-index --rebuild`,
  which is not intuitive as the one-command path.
- The flag `--rebuild` is not self-describing to a first-time user.
- No obvious alias or "start here for RAG" command.

### OPERATOR_QUICKSTART.md was too narrow
- The existing file covered only SimTrader gate commands (steps 6–9 of the
  full workflow).
- Missing: wallet-scan loop, alpha-distill, hypothesis registry, RAG
  one-command, Grafana dashboard links, Studio launch instructions.

### Studio Dashboard tab had no Grafana entry points
- The Dashboard tab had Quick Start buttons (shadow --dry-run, etc.) and
  Recent Sessions, but no links to Grafana.
- Users switching between Studio and Grafana had to remember the URLs manually.

### INDEX.md did not prominently surface the operator quickstart
- OPERATOR_QUICKSTART.md existed but was listed only in the Workflows table,
  not in Getting Started. No "start here" signal.

---

## Changes Made

### 1. `polytool/__main__.py` — CLI help reorganized + `rag-refresh` added

**`print_usage()` rewrite:**
- Commands grouped into 5 categories:
  - Research Loop (Track B)
  - Analysis & Evidence
  - RAG & Knowledge
  - SimTrader / Execution (Track A, gated)
  - Integrations & Utilities
- Examples section now shows 3 real workflows: research loop, single-user
  examination, SimTrader iteration.
- Footer links to the 3 most useful docs.

**New command: `rag-refresh`**
- Thin alias: routes to `rag-index --rebuild` with all additional args passed
  through.
- No new code, no new logic. Pure routing.
- Listed first in the RAG & Knowledge section with the note "use this first".

### 2. `packages/polymarket/simtrader/studio/static/index.html` — Grafana card

- Added a "Grafana Dashboards" card to the Dashboard tab with deep links to:
  - User Trades (`polytool-user-trades`)
  - PnL (`polytool-pnl`)
  - Strategy Detectors (`polytool-strategy-detectors`)
  - User Overview (`polytool-user-overview`)
  - Arb Feasibility (`polytool-arb-feasibility`)
  - Liquidity Snapshots (`polytool-liquidity-snapshots`)
  - All Dashboards (root http://localhost:3000)
- Links open in a new tab with `rel="noopener"`.
- Includes a note: "Requires docker compose up -d".

### 3. `docs/OPERATOR_QUICKSTART.md` — Complete rewrite

Old: 9 steps covering only SimTrader gates.
New: 10-section end-to-end guide covering:

1. What PolyTool Is (component table)
2. Start Services (docker compose, Grafana, ClickHouse)
3. Research Loop (wallet-scan → alpha-distill → hypothesis-register → experiment-run → hypothesis-status)
4. Single-User Examination (scan → llm-bundle → llm-save)
5. RAG — One Command (`rag-refresh`, then query examples)
6. Market Scanner
7. SimTrader Validation Gates (with current status as of 2026-03-07)
8. SimTrader Daily Dev Loop (fast iteration)
9. SimTrader Studio (tab reference table)
10. Grafana Dashboards (link table + integration decision)
+ Stage 0 → Stage 1 section
+ Quick Command Reference

### 4. `docs/LOCAL_RAG_WORKFLOW.md` — `rag-refresh` section added at top

Added a "One-command rebuild" section before the existing content:
```bash
python -m polytool rag-refresh
```
With a note directing to `rag-index` for incremental/advanced use.

### 5. `docs/INDEX.md` — Updated entries

- Added `OPERATOR_QUICKSTART.md` to Getting Started table as "**Start here**".
- Added `OPERATOR_QUICKSTART.md` to Workflows table with "**End-to-end guide**" label.
- Updated LOCAL_RAG_WORKFLOW.md entry to note `rag-refresh` as one-command rebuild.

---

## Grafana Integration Decision

**Decision: Deep links in Studio Dashboard tab. No iframe embedding.**

Rationale:
- Grafana and Studio serve different purposes. Grafana is an analytics
  platform that updates after `scan` ingestion. Studio manages live/replay
  sessions and simulation artifacts.
- The current CLI + Grafana split is already effective. The missing piece was
  discoverability, not embedding.
- Adding iframe embeds would require Grafana embed configuration, anonymous
  access settings, or auth token management — all overhead with no meaningful
  UX gain for a local-first single-operator tool.
- Deep links from the Studio Dashboard tab give one-click access to all key
  dashboards without duplicating data or adding infrastructure.
- This is reversible. If Grafana panel embedding is ever desired, iframes can
  be added to a "Dashboards" workspace type in the future.

---

## One-Command RAG Path

Before this pass: `python -m polytool rag-index --rebuild` (not obvious).
After this pass: `python -m polytool rag-refresh` (self-describing, listed first).

Both do the same thing. `rag-refresh` is a 2-line routing alias in `__main__.py`.

---

## Sample User Flows (after this pass)

### New user onboarding
```
README.md → "For more information, see docs/" → docs/OPERATOR_QUICKSTART.md
→ Follow Section 1 (docker compose up -d)
→ Follow Section 2 (wallet-scan → alpha-distill)
→ Follow Section 5 (rag-refresh, then rag-query)
```

### Returning operator: new wallet scan run
```
python -m polytool wallet-scan --input wallets.txt --profile lite
python -m polytool alpha-distill --wallet-scan-run <path>
python -m polytool rag-refresh     ← one command to make it all searchable
python -m polytool rag-query --question "..." --hybrid --rerank
```

### SimTrader monitoring session
```
Launch Studio → Dashboard tab → click "PnL" link → Grafana opens
Start shadow session in Studio → Sessions tab → view live log
When done → Tapes tab → create OnDemand replay
```

---

## Files Changed

| File | Change |
|------|--------|
| `polytool/__main__.py` | `print_usage()` grouped by workflow; `rag-refresh` command added |
| `packages/polymarket/simtrader/studio/static/index.html` | Grafana deep-link card in Dashboard tab |
| `docs/OPERATOR_QUICKSTART.md` | Complete rewrite as 10-section end-to-end guide |
| `docs/LOCAL_RAG_WORKFLOW.md` | `rag-refresh` one-command section added at top |
| `docs/INDEX.md` | `OPERATOR_QUICKSTART.md` promoted to "Start here" in Getting Started and Workflows |

## Files NOT Changed (explicitly preserved)

- Strategy logic (`market_maker_v0.py`, `binary_complement_arb.py`, etc.)
- Gate thresholds (70% sweep pass rate, etc.)
- All test files
- SimTrader runner/broker/shadow logic
- RAG indexing/retrieval logic
- ClickHouse schema, Grafana dashboard JSON
