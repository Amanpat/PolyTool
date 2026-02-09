# Documentation Hub

Use this page as the entry point for all public docs. For a quick-reference
table, see [INDEX.md](INDEX.md).

## Table of contents
- [Start here (recommended order)](#start-here-recommended-order)
- [Local config and CLI naming](#local-config-and-cli-naming)
- [Core docs](#core-docs)
- [Workflows](#workflows)
- [Planning & Context](#planning--context)
- [Directories](#directories)
- [Archive (historical)](#archive-historical)

## Start here (recommended order)
1. [Project overview](PROJECT_OVERVIEW.md)
2. [Plan of Record](PLAN_OF_RECORD.md)
3. [Architecture](ARCHITECTURE.md)
4. [Risk policy](RISK_POLICY.md)
5. [Roadmap](ROADMAP.md)
6. [Trust Artifacts](TRUST_ARTIFACTS.md)
7. [Runbook: Manual examine (legacy orchestration)](RUNBOOK_MANUAL_EXAMINE.md)
8. [Hypothesis standard](HYPOTHESIS_STANDARD.md)
9. [Local RAG workflow](LOCAL_RAG_WORKFLOW.md)
10. [LLM evidence bundle workflow](LLM_BUNDLE_WORKFLOW.md)
11. [Current state / what we built](CURRENT_STATE.md)
12. [Docs best practices](DOCS_BEST_PRACTICES.md)

## Local config and CLI naming
- Copy the committed example config before running local workflows: `cp polytool.example.yaml polytool.yaml`
- Use `python -m polytool ...` as the canonical invocation.
- `python -m polyttool ...` is a deprecated shim kept for compatibility and scheduled for removal after `v0.2.0` (see [ADR-0001](adr/ADR-0001-cli-and-module-rename.md)).

## Core docs
- [Plan of Record](PLAN_OF_RECORD.md) - Durable plan (mission, data gaps, fees, taxonomy, validation)
- [Hypothesis standard](HYPOTHESIS_STANDARD.md) - Prompt template, output rules, quality rubric
- [Trust artifacts](TRUST_ARTIFACTS.md) - Scan-emitted coverage report + run manifest contract
- [Docs best practices](DOCS_BEST_PRACTICES.md)
- [Knowledge base conventions](KNOWLEDGE_BASE_CONVENTIONS.md)
- [RAG implementation report](RAG_IMPLEMENTATION_REPORT.md)
- [Strategy playbook](STRATEGY_PLAYBOOK.md)
- [Project tree (full)](PROJECT_TREE_FULL.txt)

## Workflows
- [Runbook: Scan-first manual workflow](RUNBOOK_MANUAL_EXAMINE.md) - Scan canonical flow, examine legacy notes
- [Local RAG workflow](LOCAL_RAG_WORKFLOW.md)
- [LLM evidence bundle workflow](LLM_BUNDLE_WORKFLOW.md)
- [Research sources](RESEARCH_SOURCES.md)

## Planning & Context
- [Plan of Record](PLAN_OF_RECORD.md) - Durable plan with full design decisions
- [Roadmap](ROADMAP.md) - Milestone checklist, acceptance criteria, kill conditions
- [Project context (public)](PROJECT_CONTEXT_PUBLIC.md) - Goals, data gaps, artifact contract
- [Architect context pack](ARCHITECT_CONTEXT_PACK.md) - Deep technical context snapshot
- [TODO](TODO.md) - Deferred items by priority
- [Documentation index](INDEX.md) - Quick-reference table of all docs

## Directories
- [ADRs](adr/)
- [Specs (canonical)](specs/)
- [Feature docs](features/)
- [Eval suites](eval/)
- [Archive policy + historical docs](archive/)

## Archive (historical)
These are historical or superseded docs preserved for reference.
- [Dashboards](archive/DASHBOARDS.md)
- [LLM research packets](archive/LLM_RESEARCH_PACKETS.md)
- [Next steps readiness report](archive/NEXT_STEPS_READINESS_REPORT.md)
- [Packet 5.2.1.4 tradeability](archive/packet_5_2_1_4_tradeability.md)
- [Packet 5.2.1.5 metadata refresh](archive/packet_5_2_1_5_metadata_refresh.md)
- [Packet 5.2.1.6 token resolution](archive/packet_5_2_1_6_token_resolution.md)
- [Packet 5.2.1.7 market backfill](archive/packet_5_2_1_7_market_backfill.md)
- [Packet 5.2.1.8 liquidity enrichment](archive/packet_5_2_1_8_liquidity_enrichment.md)
- [Packet 6 opportunities](archive/PACKET_6_OPPORTUNITIES.md)
- [Plays view](archive/PLAYS_VIEW.md)
- [Public data blueprint](archive/PUBLIC_DATA_BLUEPRINT.md)
- [Quality confidence](archive/QUALITY_CONFIDENCE.md)
- [Repo architecture (legacy)](archive/REPO_ARCHITECTURE.md)
- [Reverse engineer copy map](archive/REVERSE_ENGINEER_COPY_MAP.md)
- [Reverse engineer spec](archive/REVERSE_ENGINEER_SPEC.md)
- [Strategy catalog](archive/STRATEGY_CATALOG.md)
- [Strategy detectors v1](archive/STRATEGY_DETECTORS_V1.md)
- [Troubleshooting buckets](archive/TROUBLESHOOTING_BUCKETS.md)
- [Troubleshooting PnL](archive/TROUBLESHOOTING_PNL.md)
