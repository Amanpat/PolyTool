---
tags: [decision]
date: 2026-04-09
status: accepted
---
# Decision — Wallet Discovery Roadmap Narrowed to V1 Slice

## Context
Architect reviewed the full wallet discovery roadmap (7 phases, 4 loops) and correctly identified it as oversized for current project state. Phase 1 revenue gates aren't closed. The roadmap had LLM policy conflicts, unverified Alchemy assumptions, incorrect insider scoring math, and weak acceptance criteria.

## Decision
Treat the full roadmap as a Phase 2 design document. Immediate build covers only:
1. Loop A (leaderboard discovery + churn detection + scan queue)
2. Watchlist ClickHouse table with lifecycle states
3. Unified `polytool scan` command consolidation
4. MVF computation (7 new metrics, Python only, no LLM)

All other phases (Loop B, Loop D, Loop C, insider detection, LLM hypotheses, n8n) remain as documented intent with explicit blockers.

## Key Sub-Decisions
- Loop C hypotheses are EXPLORATORY (`user_data` partition, not `research`)
- Cloud LLM usage for wallet analysis requires PLAN_OF_RECORD update first
- Loop D attribution is "best-effort candidates" not "causative wallets"
- Watchlist promotion requires human review gate in v1
- Insider scoring needs mathematical correction before implementation

See [[10-Session-Notes/2026-04-09 Architect Review Assessment]]
