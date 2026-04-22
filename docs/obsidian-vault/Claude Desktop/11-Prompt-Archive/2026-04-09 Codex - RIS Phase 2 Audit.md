---
tags: [prompt-archive]
date: 2026-04-09
model: Codex
topic: RIS Phase 2 Completion Audit
---
# RIS Phase 2 Completion Audit — Codex Prompt

## Purpose
Verify architect's claim that RIS Phase 2 roadmap is complete by inspecting actual codebase. Read-only audit — no code changes.

## What's Being Verified
1. Weighted composite evaluation gate (fail-closed, per-priority thresholds)
2. Cloud provider routing: Gemini primary, DeepSeek escalation, Ollama fallback
3. Ingest/review integration: ACCEPT/REVIEW/REJECT/BLOCKED dispositions
4. Monitoring: provider failure detection, review queue backlog, 7 health checks
5. Retrieval benchmark: query class segmentation, per-class metrics, baseline artifacts
6. Discord embed alerting via n8n

## 12 Inspection Sections
1. Evaluation providers (GeminiFlash, DeepSeek, OpenAICompatible base class)
2. Fail-closed contract (no silent auto-accept)
3. Scoring policy (weighted composite + per-dimension floor)
4. Review queue (pending_review table, CLI, accept/reject)
5. Multi-provider routing (primary → escalation → fallback)
6. Budget control (daily caps, per-source ceilings)
7. Monitoring & health checks (7 checks, provider failure detection)
8. Retrieval benchmark (golden set, benchmark script, baseline artifacts)
9. n8n workflows (unified dev workflow, import script, SOPs)
10. Novelty scoring (retrieval-backed, dedup protection)
11. ClickHouse metrics (DDL, Grafana dashboard)
12. Integration tests (full pipeline, per-provider)

## Output
`docs/audits/2026-04-09_ris_phase2_audit.md` — structured report with CONFIRMED/PARTIAL/MISSING per claim.

## Cross-References
- [[10-Session-Notes/2026-04-09 RIS n8n Workflows and Phase 2 Roadmap]]
- [[02-Modules/RIS]] — claims Phase 2 shipped
