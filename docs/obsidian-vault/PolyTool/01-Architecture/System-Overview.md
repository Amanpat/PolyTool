---
type: architecture
tags: [architecture, status/done]
created: 2026-04-08
---

# System Overview

PolyTool is a Polymarket-first research, simulation, and execution system. It reverse-engineers profitable wallet behavior, converts discovered behavior into hypotheses and runnable strategies, validates those strategies in replay and shadow environments, and deploys surviving strategies with hard risk limits.

Source: CLAUDE.md "What PolyTool Is" + roadmap North Star Architecture + audit Section 1 module inventory.

---

## Purpose

Three-stage mission:
1. **Reverse-engineer** what top wallets are doing
2. **Simulate and validate** those strategies until profitable
3. **Deploy a live bot** that continuously improves itself

---

## Layer Roles

### Python Core Library

All business logic lives here. Located in `packages/polymarket/` and `packages/research/`.

- Scanners, RAG, SimTrader, strategy logic, execution logic, research evaluation
- The CLI wraps the core for developer speed — never the reverse
- FastAPI and scheduling are thin layers on top

### CLI

Located in `polytool/__main__.py` (routes ~60 commands) and `tools/cli/` (56 files).

- Primary developer interface — fastest way to test and debug
- The CLI never goes away — everything starts as a CLI command
- Automation layers are added on top of working CLI commands

### FastAPI Wrapper

Located in `services/api/main.py` (3054 lines).

- Thin REST skin added in Phase 3 when automation needs HTTP endpoints
- No business logic lives here
- Pre-built but has zero tests — Phase 3 deliverable per CLAUDE.md

### Scheduling

- Phase 1: APScheduler or cron for scheduled Python functions
- Scoped RIS n8n pilot (ADR 0013) shipped for RIS ingestion workflows only (opt-in via `--profile ris-n8n`)
- Phase 3+: broad n8n orchestration when workflow complexity justifies it

### Visualization

- Phase 1: Grafana only (reads from ClickHouse, zero new code required)
- Phase 7: PolyTool Studio rebuild as Next.js application (post-profit)

---

## Package Structure

### packages/polymarket/ — Core Library

30+ top-level modules. Key subsystems:
- `simtrader/` — multi-subpackage simulation engine (batch, broker, execution, orderbook, portfolio, replay, shadow, strategies, strategy, studio, sweeps, tape)
- `crypto_pairs/` — 20 files, ~10,599 lines
- `rag/` — 13 files, ~3,124 lines (ChromaDB + SQLite FTS5)
- `market_selection/` — 7-factor composite scorer
- `historical_import/` — bulk import pipeline
- `hypotheses/` — JSON-backed hypothesis registry
- `notifications/` — Discord webhook alerting

### packages/research/ — Research Intelligence System (RIS)

6 subpackages:
- `evaluation/` — LLM quality evaluator
- `hypotheses/` — SQLite-backed registry (409 lines)
- `ingestion/` — content fetchers (web, ArXiv, Reddit, YouTube)
- `integration/` — links findings to strategies
- `monitoring/` — pipeline health checks
- `scheduling/` — APScheduler-based job scheduler
- `synthesis/` — report generation, precheck verdicts

### polytool/ — CLI Entry Package

- `__main__.py` (367 lines) — routes ~60 commands via lazy importlib
- `user_context.py` — resolves handles/wallets to slugs
- `reports/` — report rendering utilities

### tools/

- `tools/cli/` — 56 CLI handler files
- `tools/gates/` — 11 gate management scripts (4674 total lines)
- `tools/guard/` — 4 pre-commit guard files
- `tools/ops/`, `tools/smoke/`, `tools/setup/` — operational utilities

### services/

- `services/api/` — FastAPI service (Phase 3 pre-built)

---

## Triple-Track Strategy Model

Three independent revenue paths. The bot only needs ONE to work to survive.

- **Track 1 / Phase 1B** — Avellaneda-Stoikov Market Maker: spread capture + liquidity rewards
- **Track 2 / Phase 1A** — Crypto Pair Bot: directional momentum, gabagool22 pattern
- **Track 3 / Phase 1C** — Sports Directional Model: ML probability model

---

## Key Cross-References

- [[Database-Rules]] — ClickHouse + DuckDB separation rule, all 23 tables
- [[Data-Stack]] — Five free data layers
- [[Tape-Tiers]] — Gold / Silver / Bronze tape definitions
- [[Risk-Framework]] — Validation ladder, gate definitions, capital stages
- [[Core-Library]] — Top-level module inventory
- [[SimTrader]] — Simulation engine details
- [[RAG]] — Retrieval-augmented generation architecture
- [[RIS]] — Research Intelligence System
- [[Gates]] — Gate management scripts
- [[FastAPI-Service]] — FastAPI service details
