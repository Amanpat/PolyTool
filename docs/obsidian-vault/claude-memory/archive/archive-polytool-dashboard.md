---
title: "PolyTool Dashboard"
type: reference
status: archived
source_zone: claude_memory
last_updated: 2026-05-23
lifecycle: archived
archived_from: PolyTool\00-Index\Dashboard.md
archived_reason: "Dataview-powered dashboard; superseded by index.md and three-zone vault architecture"
archived_at: 2026-05-23
---

# PolyTool Dashboard

Master Map of Content for the PolyTool Obsidian vault. All notes are derived from `docs/CODEBASE_AUDIT.md` (primary ground truth), `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md`, `CLAUDE.md`, and `docs/CURRENT_STATE.md`.

---

## Architecture

- [[legacy/PolyTool/01-Architecture/System-Overview]] — Layer roles, package structure, North Star architecture
- [[legacy/PolyTool/01-Architecture/Database-Rules]] — All 23 ClickHouse tables, DuckDB, ChromaDB rules
- [[legacy/PolyTool/01-Architecture/Data-Stack]] — Five free data layers (pmxt, Jon-Becker, polymarket-apis, subgraph, live tape)
- [[legacy/PolyTool/01-Architecture/Tape-Tiers]] — Gold / Silver / Bronze tier definitions and artifact layout
- [[legacy/PolyTool/01-Architecture/Risk-Framework]] — Validation ladder, gate definitions, capital stages, kill-switch
- [[legacy/PolyTool/01-Architecture/LLM-Policy]] — Tier 1/1b/2/3 LLM routing, offline-first principle

---

## Modules

- [[legacy/PolyTool/02-Modules/Core-Library]] — packages/polymarket/ top-level modules (30+)
- [[legacy/PolyTool/02-Modules/Crypto-Pairs]] — packages/polymarket/crypto_pairs/ (20 files, ~10,599 lines)
- [[legacy/PolyTool/02-Modules/SimTrader]] — Multi-subpackage simulation engine
- [[legacy/PolyTool/02-Modules/RAG]] — Hybrid vector + lexical retrieval (ChromaDB + SQLite FTS5)
- [[legacy/PolyTool/02-Modules/RIS]] — Research Intelligence System (6 subpackages)
- [[legacy/PolyTool/02-Modules/Market-Selection]] — 7-factor composite market scorer
- [[legacy/PolyTool/02-Modules/Historical-Import]] — Bulk historical trade data import pipeline
- [[legacy/PolyTool/02-Modules/Hypothesis-Registry]] — Dual registries (JSON-backed + SQLite-backed)
- [[legacy/PolyTool/02-Modules/Notifications]] — Discord webhook alerting
- [[legacy/PolyTool/02-Modules/Gates]] — Gate management scripts (tools/gates/, 11 files)
- [[legacy/PolyTool/02-Modules/FastAPI-Service]] — services/api/main.py (Phase 3 pre-built, zero tests)

---

## Strategies

- [[legacy/PolyTool/03-Strategies/Track-1A-Crypto-Pair-Bot]] — Fastest path to first dollar (BLOCKED)
- [[legacy/PolyTool/03-Strategies/Track-1B-Market-Maker]] — Long-term revenue engine (Gate 2 FAILED)
- [[legacy/PolyTool/03-Strategies/Track-1C-Sports-Directional]] — Medium-term ML model (TODO)

---

## CLI

- [[legacy/PolyTool/04-CLI/CLI-Reference]] — All ~60 commands organized by category

---

## Roadmap

- [[legacy/PolyTool/05-Roadmap/Phase-0-Accounts-Setup]] — Accounts, setup, operator workflow (done)
- [[legacy/PolyTool/05-Roadmap/Phase-1A-Crypto-Pair-Bot]] — Crypto pair bot (blocked)
- [[legacy/PolyTool/05-Roadmap/Phase-1B-Market-Maker-Gates]] — Gate closure → live deployment (todo)
- [[legacy/PolyTool/05-Roadmap/Phase-1C-Sports-Model]] — Sports directional model (todo)
- [[legacy/PolyTool/05-Roadmap/Phase-2-Discovery-Engine]] — Discovery engine + research scraper (conditionally closed)
- [[legacy/PolyTool/05-Roadmap/Phase-3-Hybrid-RAG-Kalshi-n8n]] — Hybrid RAG + Kalshi + n8n (todo)
- [[legacy/PolyTool/05-Roadmap/Phase-4-Autoresearch]] — Autoresearch + validation automation (todo)
- [[legacy/PolyTool/05-Roadmap/Phase-5-Advanced-Strategies]] — Advanced strategies (todo)
- [[legacy/PolyTool/05-Roadmap/Phase-6-Closed-Loop]] — Closed-loop autoresearch (todo)
- [[legacy/PolyTool/05-Roadmap/Phase-7-Unified-UI]] — PolyTool Studio rebuild (todo)
- [[legacy/PolyTool/05-Roadmap/Phase-8-Scale-Platform]] — Scale + platform expansion (todo)

---

## Issues

- [[legacy/PolyTool/00-Index/Issues]] — Index of all known code issues from audit Section 7

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

## Connections

- [[claude-memory/archive/_index]]
- [[index|Vault Home]]
