# Documentation Index

Quick-reference index of all key docs and what they cover.

## Getting Started

| Doc | Purpose |
|-----|---------|
| [README](../README.md) | Top-level overview, quick start, API reference |
| [docs/README](README.md) | Documentation hub with recommended reading order |
| [Current State](CURRENT_STATE.md) | What exists today, pipeline diagram, CLI commands |
| [Roadmap](ROADMAP.md) | Milestone checklist, acceptance criteria, kill conditions |
| [Trust Artifacts](TRUST_ARTIFACTS.md) | Scan-emitted trust artifacts (`coverage_reconciliation_report*`, `run_manifest.json`) |

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
| [Runbook: Manual Examine](RUNBOOK_MANUAL_EXAMINE.md) | Scan-first manual workflow; examine guidance retained as legacy |
| [Local RAG Workflow](LOCAL_RAG_WORKFLOW.md) | RAG index, query, eval, scoping, retrieval modes |
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
| [ADR-0001: CLI Rename](adr/ADR-0001-cli-and-module-rename.md) | polyttool -> polytool rename decision |

## Specs

| Doc | Purpose |
|-----|---------|
| [SPEC-0001: Dossier Resolution Enrichment](specs/SPEC-0001-dossier-resolution-enrichment.md) | Resolution outcome enrichment for dossiers |
| [Hypothesis Schema v1](specs/hypothesis_schema_v1.json) | JSON schema for structured hypothesis output |

## Archive

Historical and superseded docs are in `docs/archive/`. See [docs/README](README.md)
for the full archive listing.
