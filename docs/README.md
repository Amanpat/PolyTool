# Documentation Hub

Use this page as the entry point for public docs. It is a navigation surface,
not a source-of-truth document. For the public-docs boundary and cleanup
contract, see
[ADR 0014](adr/0014-public-docs-surface-and-repo-hygiene-boundaries.md). For
root-level hidden tooling, local-state boundaries, and cleanliness exclusions,
see
[Local State and Tooling Boundary](reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md).
For a quick-reference table, see [INDEX.md](INDEX.md).

## Table of contents

- [First-class root docs](#first-class-root-docs)
- [Recommended reading order](#recommended-reading-order)
- [Local config and CLI naming](#local-config-and-cli-naming)
- [Reference](#reference)
- [Runbooks](#runbooks)
- [Audits](#audits)
- [Planning & Context](#planning--context)
- [Directories](#directories)
- [Archive (historical)](#archive-historical)

## First-class root docs

These are the only root-level docs that should be treated as first-class public
surface:

1. [Plan of Record](PLAN_OF_RECORD.md)
2. [Architecture](ARCHITECTURE.md)
3. [Strategy Playbook](STRATEGY_PLAYBOOK.md)
4. [Master Roadmap v5.1](reference/POLYTOOL_MASTER_ROADMAP_v5_1.md)
5. [Current State](CURRENT_STATE.md)

`README.md` and [INDEX.md](INDEX.md) are navigation only. `docs/dev_logs/` is
preserved history, and `docs/obsidian-vault/` is a separate subsystem excluded
from public docs count goals. [ROADMAP.md](ROADMAP.md) is retained only as a
non-governing roadmap router/operator-facing companion.

## Recommended reading order

1. [Plan of Record](PLAN_OF_RECORD.md)
2. [Architecture](ARCHITECTURE.md)
3. [Strategy Playbook](STRATEGY_PLAYBOOK.md)
4. [Master Roadmap v5.1](reference/POLYTOOL_MASTER_ROADMAP_v5_1.md)
5. [Current state / what we built](CURRENT_STATE.md)
6. [Project overview](PROJECT_OVERVIEW.md)
7. [Risk policy](RISK_POLICY.md)
8. [Trust Artifacts](reference/TRUST_ARTIFACTS.md)
9. [Runbook: Manual examine (legacy orchestration)](runbooks/RUNBOOK_MANUAL_EXAMINE.md)
10. [Hypothesis standard](reference/HYPOTHESIS_STANDARD.md)
11. [Local RAG workflow](runbooks/LOCAL_RAG_WORKFLOW.md)
12. [LLM evidence bundle workflow](runbooks/LLM_BUNDLE_WORKFLOW.md)
13. [Docs best practices](DOCS_BEST_PRACTICES.md)
14. SimTrader operator guide (optional): [README_SIMTRADER.md](runbooks/README_SIMTRADER.md)
15. [RIS Operator Guide](runbooks/RIS_OPERATOR_GUIDE.md)

## Local config and CLI naming

- Copy the committed example config before running local workflows: `cp polytool.example.yaml polytool.yaml`
- Use `python -m polytool ...` as the canonical invocation.
- The old `polyttool` (double-t) shim has been removed. Use `polytool` or `python -m polytool` (see [ADR-0001](adr/ADR-0001-cli-and-module-rename.md)).

## Reference

- [Hypothesis standard](reference/HYPOTHESIS_STANDARD.md) - Prompt template, output rules, quality rubric
- [Trust artifacts](reference/TRUST_ARTIFACTS.md) - Roadmap 2 scan artifacts: coverage schema, warning rules, run manifest reproducibility
- [Research sources](reference/RESEARCH_SOURCES.md) - Curated source domains, allowlist, TTL, cache-source usage
- [Local state and tooling boundary](reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md) - Root-level classification for hidden tooling, runtime state, scratch, and repo-cleanliness exclusions
- [Docs best practices](DOCS_BEST_PRACTICES.md)
- [Knowledge base conventions](KNOWLEDGE_BASE_CONVENTIONS.md)
- [Strategy playbook](STRATEGY_PLAYBOOK.md)
- [Debug: Windows pytest PermissionError tempdirs](archive/debug/DEBUG-windows-permissionerror-pytest-tempdirs.md)

## Runbooks

- [Operator quickstart](runbooks/OPERATOR_QUICKSTART.md) - Start here for the end-to-end research loop, RAG flow, SimTrader gates, and Grafana checks
- [Operator setup guide](runbooks/OPERATOR_SETUP_GUIDE.md) - Operator-owned setup work before live capital
- [Windows development gotchas](runbooks/WINDOWS_DEVELOPMENT_GOTCHAS.md) - Windows host issues and PowerShell-safe fixes
- [Partner deployment guide (Docker)](runbooks/PARTNER_DEPLOYMENT_GUIDE_docker.md) - Partner-machine deployment path
- [SimTrader operator guide](runbooks/README_SIMTRADER.md) - Replay-first + shadow mode simulated trading, sweeps/batch, and local HTML reports
- [RIS Operator Guide](runbooks/RIS_OPERATOR_GUIDE.md) - Evaluation gate, review queue, ingestion, health monitoring, retrieval benchmarks
- [RIS n8n operator path](../infra/n8n/README.md) - Current canonical n8n quickstart, import command, and smoke steps
- [RIS + n8n Operator SOP cheat sheet](runbooks/RIS_N8N_OPERATOR_SOP.md) - Compact command reference for daily RIS+n8n operations
- [Runbook: Scan-first manual workflow](runbooks/RUNBOOK_MANUAL_EXAMINE.md) - Scan canonical flow, examine legacy notes
- [Wallet Discovery v1 Operator Runbook](runbooks/WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md) - Loop A leaderboard discovery, quick scan with MVF, human review gate
- [Local RAG workflow](runbooks/LOCAL_RAG_WORKFLOW.md)
- [LLM evidence bundle workflow](runbooks/LLM_BUNDLE_WORKFLOW.md)

## Audits

- [Codebase audit](audits/CODEBASE_AUDIT.md)
- [RAG implementation report](audits/RAG_IMPLEMENTATION_REPORT.md)
- [RIS audit report](audits/RIS_AUDIT_REPORT.md)

## Planning & Context

- [Plan of Record](PLAN_OF_RECORD.md) - Durable plan with full design decisions
- [Master Roadmap v5.1](reference/POLYTOOL_MASTER_ROADMAP_v5_1.md) - Strategic roadmap and LLM policy
- [Roadmap router](ROADMAP.md) - Secondary operator-facing roadmap surface; not governing
- [ADR 0014](adr/0014-public-docs-surface-and-repo-hygiene-boundaries.md) - Public docs surface and repo hygiene boundary
- [Local State and Tooling Boundary](reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md) - Root-level hidden tooling/local-state policy that complements ADR 0014
- [Project context (public)](PROJECT_CONTEXT_PUBLIC.md) - Goals, data gaps, artifact contract
- [Architect context pack](ARCHITECT_CONTEXT_PACK.md) - Deep technical context snapshot
- [TODO](TODO.md) - Deferred items by priority
- [Documentation index](INDEX.md) - Quick-reference table of all docs

## Directories

- [Audits](audits/)
- [ADRs](adr/)
- [Reference](reference/)
- [Runbooks](runbooks/)
- [Specs (canonical)](specs/)
- [Feature docs](features/)
- [Eval suites](eval/)
- [Obsidian vault](obsidian-vault/) - Separate subsystem; excluded from public docs count goals
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
