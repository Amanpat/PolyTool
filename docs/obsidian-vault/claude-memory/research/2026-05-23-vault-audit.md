---
title: Vault Audit — Pre-Migration Classification
type: research
status: active
source_zone: claude_memory
last_updated: 2026-05-23
lifecycle: reviewed
confidence: 0.9
generator: claude-code
human_authored: false
tags:
  - audit
  - vault-migration
  - tier-2
session_date: 2026-05-23
---

# Vault Audit — Pre-Migration Classification

Phase 3 of the vault redesign migration playbook. Every document in the current vault is classified as **Tier 1** (keep, migrate — spec/adr/decision), **Tier 2** (keep, migrate — research/concept/reference), **Tier 3** (keep, migrate — session/prompt/work-packet/idea), or **Obsolete** (archive, do not delete).

Conducted by Claude Code on 2026-05-23.

---

## Zone: Claude Desktop/08-Research/ (17 files)

| File | Classification | Target | Notes |
|------|---------------|--------|-------|
| `00-INDEX.md` | Obsolete | archive | Dataview-powered index, replaced by `_index.md` |
| `01-Wallet-Discovery-Pipeline.md` | Tier 2 | `claude-memory/research/` | Active research |
| `02-Metrics-Engine-MVF.md` | Tier 2 | `claude-memory/research/` | Active research |
| `03-Insider-Detection.md` | Tier 2 | `claude-memory/research/` | Active research |
| `04-Loop-B-Live-Monitoring.md` | Tier 2 | `claude-memory/research/` | Active research |
| `05-LLM-Chunking-Strategy.md` | Tier 2 | `claude-memory/research/` | Active research |
| `06-Wallet-Discovery-Roadmap.md` | Tier 2 | `claude-memory/research/` | Active research |
| `07-Backtesting-Repo-Deep-Dive.md` | Tier 2 | `claude-memory/research/` | Active research |
| `08-Copy-Trader-and-Risk-Free-Bot-Deep-Dive.md` | Tier 2 | `claude-memory/research/` | **Duplicate topic** — see 08-Copy-Trader-Deep-Dive.md below |
| `08-Copy-Trader-Deep-Dive.md` | Tier 2 | `claude-memory/research/` | **Duplicate topic** — separate docs, different numbering; both preserved |
| `09-Hermes-PMXT-Deep-Dive.md` | Tier 2 | `claude-memory/research/` | Active research |
| `10-Roadmap-v6.0-Master-Draft.md` | Tier 2 | `claude-memory/research/` | Draft; repo `PLAN_OF_RECORD.md` is more authoritative |
| `11-Scientific-RAG-Pipeline-Survey.md` | Tier 2 | `claude-memory/research/` | Active research |
| `11-Scientific-RAG-Target-Architecture.md` | Tier 2 | `claude-memory/research/` | **Duplicate number** (two "11-" files); both preserved |
| `Hermes Agent - PolyTool Integration Setup Guide.md` | Tier 2 | `claude-memory/research/` | Reference guide |

## Zone: Claude Desktop/09-Decisions/ (14 files)

| File | Classification | Target | Notes |
|------|---------------|--------|-------|
| `Decision-Log.md` | Obsolete | archive | Dataview-powered index, superseded by `decisions/_index.md` |
| `Decision - Academic Pipeline Hosting.md` | Tier 1 | `claude-memory/decisions/` | Active |
| `Decision - Agent Parallelism Strategy for RIS Phase 2.md` | Tier 1 | `claude-memory/decisions/` | Active |
| `Decision - Loop A Leaderboard API.md` | Tier 1 | `claude-memory/decisions/` | Active |
| `Decision - Loop D Managed CLOB Subscription.md` | Tier 1 | `claude-memory/decisions/` | Active |
| `Decision - RIS Evaluation Gate Model Swappability.md` | Tier 1 | `claude-memory/decisions/` | Active |
| `Decision - RIS Evaluation Scoring Policy.md` | Tier 1 | `claude-memory/decisions/` | Active |
| `Decision - RIS n8n Pilot Scope.md` | Tier 1 | `claude-memory/decisions/` | **Contradiction candidate**: overlaps with `repo-docs/adrs/adr-0013-ris-n8n-pilot-scoped`. See contradictions section. |
| `Decision - Roadmap Narrowed to V1.md` | Tier 1 | `claude-memory/decisions/` | Active |
| `Decision - Roadmap v6.0 Slim Master Restructure.md` | Tier 1 | `claude-memory/decisions/` | Active |
| `Decision - Scientific RAG Architecture Adoption.md` | Tier 1 | `claude-memory/decisions/` | Active |
| `Decision - Two-Feed Architecture.md` | Tier 1 | `claude-memory/decisions/` | Active |
| `Decision - Two-Zone Vault Architecture.md` | **SUPERSEDED** | archive | **Contradiction**: two-zone model superseded by three-zone spec. Needs ADR. |
| `Decision - Watchlist ClickHouse Storage.md` | Tier 1 | `claude-memory/decisions/` | Active |
| `Decision - Workflow Harness Refresh 2026-04.md` | Tier 1 | `claude-memory/decisions/` | Active |
| `RIS_OPERATIONAL_READINESS_ROADMAP.md` | Tier 2 | `claude-memory/research/` | **Superseded by v1.1** below |
| `RIS_OPERATIONAL_READINESS_ROADMAP_v1.1.md` | Tier 2 | `claude-memory/research/` | v1.1 supersedes v1.0 |

## Zone: Claude Desktop/10-Session-Notes/ (10 files)

| File | Classification | Target | Notes |
|------|---------------|--------|-------|
| `Session-Index.md` | Obsolete | archive | Dataview-powered index |
| `2026-04-09 Architect Review Assessment.md` | Tier 3 | `claude-memory/session-notes/` | Session note |
| `2026-04-09 RIS n8n Workflows and Phase 2 Roadmap.md` | Tier 3 | `claude-memory/session-notes/` | Session note |
| `2026-04-09 Wallet Discovery Pipeline Design.md` | Tier 3 | `claude-memory/session-notes/` | Session note |
| `2026-04-10 Open Source Repo Integration Final Review.md` | Tier 3 | `claude-memory/session-notes/` | Session note |
| `2026-04-10 RIS Phase 2 Audit Results.md` | Tier 3 | `claude-memory/session-notes/` | Session note |
| `2026-04-21 Workflow Harness Refresh.md` | Tier 3 | `claude-memory/session-notes/` | Session note |
| `2026-04-22 RIS Roadmap v1.1 Review.md` | Tier 3 | `claude-memory/session-notes/` | Session note |
| `2026-04-27 Academic Pipeline Diagnosis.md` | Tier 3 | `claude-memory/session-notes/` | Session note |
| `2026-05-22 Continuous Development Workflow Research.md` | Tier 3 | `claude-memory/session-notes/` | Session note |

## Zone: Claude Desktop/11-Prompt-Archive/ (15 files)

| File | Classification | Target | Notes |
|------|---------------|--------|-------|
| `Archive-Index.md` | Obsolete | archive | Dataview-powered index |
| `2026-04-09 Claude - Architect Response.md` | Tier 3 | `claude-memory/prompts/` | Prompt archive |
| `2026-04-09 Codex - RIS Phase 2 Audit.md` | Tier 3 | `claude-memory/prompts/` | Prompt archive |
| `2026-04-09 GLM5 - CLOB WebSocket and Alchemy CU.md` | Tier 3 | `claude-memory/prompts/` | Prompt archive |
| `2026-04-09 GLM5 - Gemini Flash Structured Evaluation.md` | Tier 3 | `claude-memory/prompts/` | Prompt archive |
| `2026-04-09 GLM5 - n8n Advanced Patterns.md` | Tier 3 | `claude-memory/prompts/` | Prompt archive |
| `2026-04-09 GLM5 - n8n ClickHouse Grafana Metrics.md` | Tier 3 | `claude-memory/prompts/` | Prompt archive |
| `2026-04-09 GLM5 - Polymarket Event Volume.md` | Tier 3 | `claude-memory/prompts/` | Prompt archive |
| `2026-04-09 GLM5 - Polymarket Leaderboard API.md` | Tier 3 | `claude-memory/prompts/` | Prompt archive |
| `2026-04-09 GLM5 - RAG Retrieval Quality Testing.md` | Tier 3 | `claude-memory/prompts/` | Prompt archive |
| `2026-04-10 GLM5 - n8n Claude Code Tooling.md` | Tier 3 | `claude-memory/prompts/` | Prompt archive |
| `2026-04-10 GLM5 - Unified Gap Fill Open Source Integration.md` | Tier 3 | `claude-memory/prompts/` | Prompt archive |
| `2026-04-21 Architect Custom Instructions v2.md` | Tier 3 | `claude-memory/prompts/` | Prompt archive |
| `2026-04-22 Architect Custom Instructions v3.md` | Tier 3 | `claude-memory/prompts/` | Prompt archive |
| `2026-04-22 Research - Ollama Cloud API.md` | Tier 3 | `claude-memory/prompts/` | Prompt archive |

## Zone: Claude Desktop/12-Ideas/ (18 files)

| File | Classification | Target | Notes |
|------|---------------|--------|-------|
| `Ideas-Index.md` | Obsolete | archive | Dataview-powered index |
| `Idea - Cross-Platform Price Divergence as RIS Signal.md` | Tier 3 | `claude-memory/ideas/` | Idea |
| `Idea - Graphify Pattern Adoption.md` | Tier 3 | `claude-memory/ideas/` | Idea |
| `Idea - pmxt Sidecar Architecture Evaluation.md` | Tier 3 | `claude-memory/ideas/` | Idea |
| `Work-Packet - Academic Pipeline PDF Download Fix.md` | Tier 3 | `claude-memory/work-packets/` | Work packet |
| `Work-Packet - Academic Pipeline Scaled Validation Corpus.md` | Tier 3 | `claude-memory/work-packets/` | Work packet |
| `Work-Packet - Fee Model Maker-Taker + Kalshi.md` | Tier 3 | `claude-memory/work-packets/` | Work packet |
| `Work-Packet - L3 v1 SVM Topic Filter Training.md` | Tier 3 | `claude-memory/work-packets/` | Work packet |
| `Work-Packet - Marker Canonical Academic Parse Queue.md` | Tier 3 | `claude-memory/work-packets/` | Work packet |
| `Work-Packet - Marker Docker IPC Warm-Worker v1.md` | Tier 3 | `claude-memory/work-packets/` | Work packet |
| `Work-Packet - Marker Single-Paper Validation Control Surface.md` | Tier 3 | `claude-memory/work-packets/` | Work packet |
| `Work-Packet - Marker Structural Parser Integration.md` | Tier 3 | `claude-memory/work-packets/` | Work packet |
| `Work-Packet - Multi-source Academic Harvesters.md` | Tier 3 | `claude-memory/work-packets/` | Work packet (likely completed — shipped 2026-05-09) |
| `Work-Packet - PaperQA2 RAG Control Flow.md` | Tier 3 | `claude-memory/work-packets/` | Work packet |
| `Work-Packet - Pre-fetch SVM Topic Filter.md` | Tier 3 | `claude-memory/work-packets/` | Work packet |
| `Work-Packet - Prefetch Label Discovery Mode.md` | Tier 3 | `claude-memory/work-packets/` | Work packet |
| `Work-Packet - Scientific RAG Evaluation Benchmark.md` | Tier 3 | `claude-memory/work-packets/` | Work packet |
| `Work-Packet - Unified Open Source Integration Sprint.md` | Tier 3 | `claude-memory/work-packets/` | Work packet |
| `Work-Packet - Unified Open Source Integration.md` | Tier 3 | `claude-memory/work-packets/` | **Duplicate**: two files with similar names. Both preserved. |

## Zone: Claude Desktop/ root (2 files)

| File | Classification | Target | Notes |
|------|---------------|--------|-------|
| `Current-Focus.md` | Obsolete | archive | Stale status dashboard |
| `Dashboard.md` | Obsolete | archive | Dataview-powered dashboard, non-functional without Dataview |

## Zone: PolyTool/ (49 files)

### PolyTool/00-Index/

| File | Classification | Target | Notes |
|------|---------------|--------|-------|
| `Dashboard.md` | Obsolete | archive | Dataview dashboard |
| `Done.md` | Obsolete | archive | Stale done list |
| `Issues.md` | Obsolete | archive | Superseded by `07-Issues/` detailed files |
| `Todo.md` | Obsolete | archive | Stale todo list |
| `Vault-System-Guide.md` | Obsolete | archive | Old vault rules, superseded by new `CLAUDE.md` + `AGENTS.md` |

### PolyTool/01-Architecture/ (7 files)

All are Tier 2 concept docs. Potentially stale vs. `repo-docs/architecture.md`. Repo doc is authoritative.

| File | Classification | Target | Notes |
|------|---------------|--------|-------|
| `Data-Stack.md` | Tier 2 | `claude-memory/research/` | Check vs. repo `architecture.md` |
| `Database-Rules.md` | Tier 2 | `claude-memory/research/` | May be stale |
| `LLM-Policy.md` | Tier 2 | `claude-memory/research/` | May be stale |
| `Risk-Framework.md` | Tier 2 | `claude-memory/research/` | May be stale |
| `System-Overview.md` | Tier 2 | `claude-memory/research/` | Derived from repo CLAUDE.md |
| `Tape-Tiers.md` | Tier 2 | `claude-memory/research/` | May be stale |
| `Visual-Maps.md` | Tier 2 | `claude-memory/research/` | Mermaid diagrams — keep |

### PolyTool/02-Modules/ (11 files)

All Tier 2 concept docs.

| File | Classification | Target | Notes |
|------|---------------|--------|-------|
| `Core-Library.md` | Tier 2 | `claude-memory/research/` | Module reference |
| `Crypto-Pairs.md` | Tier 2 | `claude-memory/research/` | Module reference |
| `FastAPI-Service.md` | Tier 2 | `claude-memory/research/` | Module reference |
| `Gates.md` | Tier 2 | `claude-memory/research/` | Module reference |
| `Historical-Import.md` | Tier 2 | `claude-memory/research/` | Module reference |
| `Hypothesis-Registry.md` | Tier 2 | `claude-memory/research/` | Module reference |
| `Market-Selection.md` | Tier 2 | `claude-memory/research/` | Module reference |
| `Notifications.md` | Tier 2 | `claude-memory/research/` | Module reference |
| `RAG.md` | Tier 2 | `claude-memory/research/` | Module reference |
| `RIS.md` | Tier 2 | `claude-memory/research/` | Module reference |
| `SimTrader.md` | Tier 2 | `claude-memory/research/` | Module reference |

### PolyTool/03-Strategies/ (3 files)

| File | Classification | Target | Notes |
|------|---------------|--------|-------|
| `Track-1A-Crypto-Pair-Bot.md` | Tier 2 | `claude-memory/research/` | Strategy reference |
| `Track-1B-Market-Maker.md` | Tier 2 | `claude-memory/research/` | Strategy reference |
| `Track-1C-Sports-Directional.md` | Tier 2 | `claude-memory/research/` | Strategy reference |

### PolyTool/04-CLI/ (1 file)

| File | Classification | Target | Notes |
|------|---------------|--------|-------|
| `CLI-Reference.md` | Tier 2 | `claude-memory/research/` | Reference — may be stale vs. repo |

### PolyTool/05-Roadmap/ (9 files)

| File | Classification | Target | Notes |
|------|---------------|--------|-------|
| `Phase-0-Accounts-Setup.md` | Tier 2 | `claude-memory/research/` | Phase detail |
| `Phase-1A-Crypto-Pair-Bot.md` | Tier 2 | `claude-memory/research/` | Phase detail |
| `Phase-1B-Market-Maker-Gates.md` | Tier 2 | `claude-memory/research/` | Phase detail |
| `Phase-1C-Sports-Model.md` | Tier 2 | `claude-memory/research/` | Phase detail |
| `Phase-2-Discovery-Engine.md` | Tier 2 | `claude-memory/research/` | Phase detail |
| `Phase-3-Hybrid-RAG-Kalshi-n8n.md` | Tier 2 | `claude-memory/research/` | Phase detail |
| `Phase-4-Autoresearch.md` | Tier 2 | `claude-memory/research/` | Phase detail |
| `Phase-5-Advanced-Strategies.md` | Tier 2 | `claude-memory/research/` | Phase detail |
| `Phase-6-Closed-Loop.md` | Tier 2 | `claude-memory/research/` | Phase detail |
| `Phase-7-Unified-UI.md` | Tier 2 | `claude-memory/research/` | Phase detail |
| `Phase-8-Scale-Platform.md` | Tier 2 | `claude-memory/research/` | Phase detail |

### PolyTool/06-Dev-Log/ (1 file)

| File | Classification | Target | Notes |
|------|---------------|--------|-------|
| `README.md` | Obsolete | archive | Dev logs live in repo `docs/dev_logs/` |

### PolyTool/07-Issues/ (8 files)

| File | Classification | Target | Notes |
|------|---------------|--------|-------|
| `Issue-CH-Auth-Violations.md` | Tier 2 | `claude-memory/research/` | Known issue |
| `Issue-Dead-Opportunities-Stub.md` | Tier 2 | `claude-memory/research/` | Known issue |
| `Issue-Dual-Fee-Modules.md` | Tier 2 | `claude-memory/research/` | Known issue |
| `Issue-Duplicate-Hypothesis-Registry.md` | Tier 2 | `claude-memory/research/` | Known issue |
| `Issue-Duplicate-WebSocket-Code.md` | Tier 2 | `claude-memory/research/` | Known issue |
| `Issue-FastAPI-Island.md` | Tier 2 | `claude-memory/research/` | Known issue |
| `Issue-Multiple-Config-Loaders.md` | Tier 2 | `claude-memory/research/` | Known issue |
| `Issue-Multiple-HTTP-Clients.md` | Tier 2 | `claude-memory/research/` | Known issue |
| `Issue-Pyproject-Packaging-Gap.md` | Tier 2 | `claude-memory/research/` | Known issue |

## Loose Files (vault root 10-Session-Notes/)

| File | Classification | Target | Notes |
|------|---------------|--------|-------|
| `2026-05-23-research-captured-vault-redesign.md` | Tier 3 | `claude-memory/session-notes/` | Has non-standard `source_zone: conversation` — fix on migrate |
| `2026-05-23-vault-redesign-spec-drafted.md` | Tier 3 | `claude-memory/session-notes/` | Has non-standard `source_zone: conversation` — fix on migrate |

## Vault Root

| File | Classification | Notes |
|------|---------------|-------|
| `AGENT.md` | Obsolete | Old agent rules, superseded by new `AGENTS.md` |

---

## Contradictions Identified

### C-001: Two-Zone vs Three-Zone Vault Architecture

- **Doc A**: `Claude Desktop/09-Decisions/Decision - Two-Zone Vault Architecture.md` (status: accepted, date: 2026-04-08)
  - Defines two zones: Zone A (00-07, repo mirror), Zone B (08-12, working knowledge)
- **Doc B**: `docs/specs/vault-redesign-spec-v1.md` (status: active, date: 2026-05-23)
  - Defines three zones: repo-docs/, claude-memory/, ris-mirror/
- **Resolution**: Three-zone spec supersedes the two-zone decision. Create ADR. Mark two-zone decision `superseded_by: adr-0001-three-zone-vault-architecture`.

### C-002: RIS n8n Pilot Scope Decision vs ADR-0013

- **Doc A**: `Claude Desktop/09-Decisions/Decision - RIS n8n Pilot Scope.md`
- **Doc B**: `repo-docs/adrs/adr-0013-ris-n8n-pilot-scoped.md`
- **Assessment**: Doc B is the repo-committed ADR version of Doc A. Not a true contradiction — ADR is more authoritative. Doc A should be migrated and marked `superseded_by: repo-docs/adrs/adr-0013-ris-n8n-pilot-scoped`.

### C-003: RIS_OPERATIONAL_READINESS_ROADMAP v1.0 vs v1.1

- **Doc A**: `RIS_OPERATIONAL_READINESS_ROADMAP.md`
- **Doc B**: `RIS_OPERATIONAL_READINESS_ROADMAP_v1.1.md`
- **Resolution**: v1.1 supersedes v1.0. Archive v1.0 with `superseded_by: claude-memory/research/ris-operational-readiness-roadmap-v1-1`.

### C-004: Missing Research File

- **Expected**: `docs/research/2026-05-23-research-llm-obsidian-vault-design.md` (per goal spec)
- **Actual**: File not in repo. Was saved to Claude Desktop output `/mnt/user-data/outputs/`. Not accessible in repo filesystem.
- **Resolution**: Create placeholder stub in `claude-memory/research/` noting file location and status.

### C-005: PolyTool/ Architecture Docs vs repo-docs/

- **Doc A**: `PolyTool/01-Architecture/*.md` (dated 2026-04-08, derived from then-current CLAUDE.md)
- **Doc B**: `repo-docs/architecture.md`, `repo-docs/claude-md-repo.md` (2026-05-23 sync)
- **Assessment**: Repo docs are authoritative. PolyTool/ architecture docs are derived context, not source of truth. Migrate with `lifecycle: stale` to signal potential drift.

---

## Summary Counts

| Classification | Count |
|---------------|-------|
| Tier 1 (decision) | 13 |
| Tier 2 (research/concept/reference) | 57 |
| Tier 3 (session/prompt/work-packet/idea) | 40 |
| Obsolete → Archive | 14 |
| **Total** | **124** |

---

## ADR Required

One ADR needed to formalize the vault architecture change (C-001):
- `adr-0001-three-zone-vault-architecture.md` — documents supersession of two-zone by three-zone model

## Connections

- [[claude-memory/spec/vault-redesign-spec]]
- [[claude-memory/work-packets/2026-05-23-vault-redesign-execution-report]]
