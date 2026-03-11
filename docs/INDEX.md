# Documentation Index

Quick-reference index of all key docs and what they cover.

## Getting Started

| Doc | Purpose |
|-----|---------|
| [README](../README.md) | Top-level overview, quick start, API reference |
| [Operator Quickstart](OPERATOR_QUICKSTART.md) | **Start here** — end-to-end guide: research loop, RAG, SimTrader, Grafana |
| [docs/README](README.md) | Documentation hub with recommended reading order |
| [Current State](CURRENT_STATE.md) | What exists today, pipeline diagram, CLI commands |
| [Roadmap](ROADMAP.md) | Milestone checklist, acceptance criteria, kill conditions |
| [Roadmap 3 Completion](roadmap3_completion.md) | Final evidence summary for Resolution Coverage milestone completion |
| [Trust Artifacts](TRUST_ARTIFACTS.md) | Roadmap 2 scan trust artifacts: practical schema, warning interpretation, reproducibility fields |

## Planning & Design

| Doc | Purpose |
|-----|---------|
| [Plan of Record](PLAN_OF_RECORD.md) | Durable plan: mission, data gaps, fees policy, taxonomy, validation framework |
| [Architecture](ARCHITECTURE.md) | Components, data flow, RAG metadata schema |
| [Architect Context Pack](ARCHITECT_CONTEXT_PACK.md) | Deep context snapshot for maintainers (generated, high-signal overview) |
| [Project Context (Public)](PROJECT_CONTEXT_PUBLIC.md) | Goals, non-goals, data gaps, artifact contract |
| [Strategy Playbook](STRATEGY_PLAYBOOK.md) | Outcome taxonomy, EV framework, falsification methodology |
| [Hypothesis Standard](HYPOTHESIS_STANDARD.md) | Prompt template, output rules, quality rubric |
| [Risk Policy](RISK_POLICY.md) | Privacy guardrails, pre-push guard, secret scanning |

## Workflows

| Doc | Purpose |
|-----|---------|
| [Operator Quickstart](OPERATOR_QUICKSTART.md) | **End-to-end guide** — research loop, RAG one-command (`rag-refresh`), SimTrader gates, Grafana links |
| [SimTrader Operator Guide](README_SIMTRADER.md) | Replay-first + shadow mode simulated trading, sweeps/batch, and local HTML reports |
| [Bounded Dislocation Capture Trial](dev_logs/2026-03-07_bounded_dislocation_capture_trial.md) | Short operator checklist for the current Gate 2 live trial loop |
| [Stage 1 Live Deployment](runbooks/LIVE_DEPLOYMENT_STAGE1.md) | Stage 1 live deployment operator runbook |
| [Runbook: Manual Examine](RUNBOOK_MANUAL_EXAMINE.md) | Scan-first manual workflow; examine guidance retained as legacy |
| [Local RAG Workflow](LOCAL_RAG_WORKFLOW.md) | RAG index, query, eval, scoping, retrieval modes (`rag-refresh` = one-command rebuild) |
| [LLM Bundle Workflow](LLM_BUNDLE_WORKFLOW.md) | Evidence bundle assembly, prompt template, report saving |
| [Research Sources](RESEARCH_SOURCES.md) | Curated source domains, allowlist, TTL, cache-source usage |

## Standards & Conventions

| Doc | Purpose |
|-----|---------|
| [Docs Best Practices](DOCS_BEST_PRACTICES.md) | Where docs live, ADR format, naming conventions |
| [Knowledge Base Conventions](KNOWLEDGE_BASE_CONVENTIONS.md) | Public/private boundary, KB layout, agent run logs |

## Reference

| Doc | Purpose |
|-----|---------|
| [TODO](TODO.md) | Deferred items by priority, spec stubs |
| [RAG Implementation Report](RAG_IMPLEMENTATION_REPORT.md) | Technical details of RAG implementation |
| [ADR-0001: CLI Rename](adr/ADR-0001-cli-and-module-rename.md) | polytool -> polytool rename decision |

## Features

| Doc | Purpose |
|-----|---------|
| [Wallet-Scan v0](features/wallet-scan-v0.md) | Batch scan for handles/wallets -> deterministic leaderboard by net PnL |
| [Alpha-Distill v0](features/alpha-distill-v0.md) | Cross-user segment aggregation -> ranked edge hypothesis candidates (no LLM) |
| [Track A: Live CLOB Wiring + Gate Harness](features/FEATURE-trackA-live-clob-wiring.md) | Track A live CLOB integration, gate harness, market-scan CLI |

## Specs

| Doc | Purpose |
|-----|---------|
| [SPEC-0001: Dossier Resolution Enrichment](specs/SPEC-0001-dossier-resolution-enrichment.md) | Resolution outcome enrichment for dossiers |
| [SPEC-0002: LLM Bundle Coverage Section](specs/SPEC-0002-llm-bundle-coverage.md) | Coverage report inclusion logic in bundle.md |
| [LLM Bundle Input Contract](specs/LLM_BUNDLE_CONTRACT.md) | What files the LLM reads, each file's role, TODO sections, and RAG execution status |
| [SPEC: Wallet-Scan v0](specs/SPEC-wallet-scan-v0.md) | Batch wallet scan spec: input format, output schema, leaderboard ordering, error handling |
| [SPEC: Alpha-Distill v0](specs/SPEC-alpha-distill-v0.md) | Segment edge distillation spec: aggregation, ranking formula, candidate schema, friction flags |
| `packages/polymarket/market_selection/` | Market scoring, filters, Gamma API client |
| [Hypothesis Schema v1](specs/hypothesis_schema_v1.json) | JSON schema for structured hypothesis output |
| [SPEC-0010: SimTrader Vision and Roadmap](specs/SPEC-0010-simtrader-vision-and-roadmap.md) | Full SimTrader architecture, realism constraints, strategy classes, and phased roadmap (MVP0-MVP6) |

## Dev Logs (recent)

| Log | Date | Topic |
|-----|------|-------|
| [Usability Streamlining Pass](dev_logs/2026-03-07_usability_streamlining_pass.md) | 2026-03-07 | CLI grouping, rag-refresh alias, Studio Grafana links, OPERATOR_QUICKSTART rewrite |
| [Wallet Anomaly Backlog Entry](dev_logs/2026-03-07_wallet_anomaly_backlog_entry.md) | 2026-03-07 | Deferred backlog entry for wallet anomaly / flow discrepancy alerts |
| [Docs Sync: SimTrader Status](dev_logs/2026-03-07_docs_sync_simtrader_status.md) | 2026-03-07 | Repo-truth sync for current SimTrader and gate status |
| [Bounded Dislocation Capture Trial](dev_logs/2026-03-07_bounded_dislocation_capture_trial.md) | 2026-03-07 | Operator checklist for the current bounded live trial |
| [Dislocation Watch + Auto-Record](dev_logs/2026-03-07_dislocation_watch_recorder.md) | 2026-03-07 | Bounded live watcher and auto-record flow for Gate 2 capture |
| [Wallet-Scan v0](dev_logs/2026-03-05_wallet_scan_v0.md) | 2026-03-05 | Batch wallet scan implementation |
| [Alpha-Distill v0](dev_logs/2026-03-05_alpha_distill_v0.md) | 2026-03-05 | Cross-user segment distillation implementation |
| [Docs Sync: Track B Foundation](dev_logs/2026-03-05_docs_sync_trackB_foundation.md) | 2026-03-05 | Documentation sync for Track B foundation work |

## Archive

Historical and superseded docs are in `docs/archive/`. See [docs/README](README.md)
for the full archive listing.

| Doc | Purpose |
|-----|---------|
| [Construction Manual Mapping](archive/MASTER_CONSTRUCTION_MANUAL_MAPPING.md) | Future-direction mapping: Construction Manual concepts -> current repo modules; labels live trading as out of scope |
