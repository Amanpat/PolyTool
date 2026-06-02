---
type: moc
tags: [index]
created: 2026-04-08
---

# PolyTool Dashboard

Master Map of Content for the PolyTool Obsidian vault. All notes are derived from `docs/CODEBASE_AUDIT.md` (primary ground truth), `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md`, `CLAUDE.md`, and `docs/CURRENT_STATE.md`.

---

## Architecture

- [[System-Overview]] — Layer roles, package structure, North Star architecture
- [[Database-Rules]] — All 23 ClickHouse tables, DuckDB, ChromaDB rules
- [[Data-Stack]] — Five free data layers (pmxt, Jon-Becker, polymarket-apis, subgraph, live tape)
- [[Tape-Tiers]] — Gold / Silver / Bronze tier definitions and artifact layout
- [[Risk-Framework]] — Validation ladder, gate definitions, capital stages, kill-switch
- [[LLM-Policy]] — Tier 1/1b/2/3 LLM routing, offline-first principle

---

## Modules

- [[Core-Library]] — packages/polymarket/ top-level modules (30+)
- [[Crypto-Pairs]] — packages/polymarket/crypto_pairs/ (20 files, ~10,599 lines)
- [[SimTrader]] — Multi-subpackage simulation engine
- [[RAG]] — Hybrid vector + lexical retrieval (ChromaDB + SQLite FTS5)
- [[RIS]] — Research Intelligence System (6 subpackages)
- [[Market-Selection]] — 7-factor composite market scorer
- [[Historical-Import]] — Bulk historical trade data import pipeline
- [[Hypothesis-Registry]] — Dual registries (JSON-backed + SQLite-backed)
- [[Notifications]] — Discord webhook alerting
- [[Gates]] — Gate management scripts (tools/gates/, 11 files)
- [[FastAPI-Service]] — services/api/main.py (Phase 3 pre-built, zero tests)

---

## Strategies

- [[Track-1A-Crypto-Pair-Bot]] — Fastest path to first dollar (BLOCKED)
- [[Track-1B-Market-Maker]] — Long-term revenue engine (Gate 2 FAILED)
- [[Track-1C-Sports-Directional]] — Medium-term ML model (TODO)

---

## CLI

- [[CLI-Reference]] — All ~60 commands organized by category

---

## Roadmap

- [[Phase-0-Accounts-Setup]] — Accounts, setup, operator workflow (done)
- [[Phase-1A-Crypto-Pair-Bot]] — Crypto pair bot (blocked)
- [[Phase-1B-Market-Maker-Gates]] — Gate closure → live deployment (todo)
- [[Phase-1C-Sports-Model]] — Sports directional model (todo)
- [[Phase-2-Discovery-Engine]] — Discovery engine + research scraper (conditionally closed)
- [[Phase-3-Hybrid-RAG-Kalshi-n8n]] — Hybrid RAG + Kalshi + n8n (todo)
- [[Phase-4-Autoresearch]] — Autoresearch + validation automation (todo)
- [[Phase-5-Advanced-Strategies]] — Advanced strategies (todo)
- [[Phase-6-Closed-Loop]] — Closed-loop autoresearch (todo)
- [[Phase-7-Unified-UI]] — PolyTool Studio rebuild (todo)
- [[Phase-8-Scale-Platform]] — Scale + platform expansion (todo)

---

## Issues

- [[Issues]] — Index of all known code issues from audit Section 7

---

## Dataview Queries

### Done Items

```dataview
LIST
FROM ""
WHERE contains(tags, "status/done")
SORT file.name ASC
```

### Todo Items

```dataview
LIST
FROM ""
WHERE contains(tags, "status/todo")
SORT file.name ASC
```

### Blocked Items

```dataview
LIST
FROM ""
WHERE contains(tags, "status/blocked")
SORT file.name ASC
```

### All Issues

```dataview
TABLE severity, affected-modules
FROM "PolyTool/07-Issues"
SORT severity DESC
```
