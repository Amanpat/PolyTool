---
tags: [idea, tooling, parked, agent-workflow]
date: 2026-04-21
status: parked
resume-trigger: "Track 2 ships first dollar AND Claude Code token burn confirmed as measurable pain"
source: https://github.com/safishamsi/graphify (v0.4.9, 2026-04-13)
---

# Idea — Graphify Pattern Adoption

Evaluated graphify (24.9k stars, AI-assistant knowledge-graph skill) for PolyTool adoption on 2026-04-21. Direct adoption rejected (duplicates RIS + polytool_brain; violates First Dollar Before Perfect System). But several patterns are worth selectively stealing.

## Rejected as whole

- Parallel knowledge graph duplicates RIS
- Interactive graph viz doesn't solve a current pain
- PreToolUse hook conflicts with just-refreshed AGENTS.md/CLAUDE.md approach
- 71.5x token reduction benchmark is on 52 files — not calibrated for our 145K LOC + 651 docs

## Patterns worth selectively stealing (ranked by ROI)

### Tier 1: Cheap and concrete
1. **`.claudeignore` + auto-generated `docs/CODEBASE_MAP.md`** — small Python tool, directly addresses Claude Code token burn. Best ROI.
2. **Rationale comment extraction** — grep `# WHY:`, `# HACK:`, `# NOTE:`, `# IMPORTANT:` across `.py` files, produce `docs/RATIONALE_INDEX.md`. Captures decisions dev logs miss.
3. **Confidence-tag convention** — formalize [EXTRACTED]/[INFERRED]/[AMBIGUOUS] as project-wide agent output convention in AGENTS.md.

### Tier 2: Pattern-level
4. **Git-hook-as-invariant-maintainer** — post-commit regenerates derived artifacts (rationale index, codebase map, CLI inventory). Pattern: derived docs are outputs, not hand-edited.
5. **Worked-examples-with-honest-reviews** — graphify's `worked/` has corpora + "what went wrong" reviews. Apply to PolyTool feature docs: `docs/features/<slug>.md` + post-deployment `review.md`.

### Tier 3: Discipline, not tools
6. **Token benchmark as KPI** — print/track per-session token usage. Add `tokens_used` line to dev log template.

## Already covered (skip)

- Multi-modal ingestion → RIS
- Queryable knowledge store → polytool_brain + Chroma + MCP
- Always-on agent context → CLAUDE.md + AGENTS.md + CURRENT_DEVELOPMENT.md
- Markdown wiki per community → A.2 Phase 2 output
- SHA256 caching → RIS cache

## Resume plan

When resume trigger fires, pick up Tier 1 items in order:
1. `.claudeignore` + CODEBASE_MAP.md generator (1 CC session)
2. Rationale index generator + post-commit hook (1 CC session)
3. Confidence-tag formalization in AGENTS.md (10 min edit)

Do NOT fill an Active slot with this during the current Track 2 / Fee Model cycle.

## Cross-references

- [[09-Decisions/Decision - Workflow Harness Refresh 2026-04]] — rejected similar Light RAG for same reason
- [[10-Session-Notes/2026-04-21 Workflow Harness Refresh]] — full context
- CURRENT_DEVELOPMENT.md — Rule 2 (First Dollar Before Perfect System) is why this stays parked
