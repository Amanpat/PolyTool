---
tags: [prompt-archive]
date: 2026-04-09
status: sent
model: Claude-Project
---
# Response to Architect — Wallet Discovery Roadmap Review

Sent to ChatGPT architect for processing. Core message: accept nearly all corrections, narrow to v1 slice (Loop A + watchlist + unified scan + MVF only), request narrowed build plan with schema contracts and deterministic acceptance tests.

## V1 Scope Confirmed
1. Loop A leaderboard discovery
2. Watchlist ClickHouse table with lifecycle states
3. Unified scan command consolidation
4. MVF computation (Python only, no LLM)

## Deferred With Explicit Blockers
- Loop B: blocked on Alchemy proof-of-feasibility
- Loop C: blocked on LLM policy reconciliation
- Loop D: blocked on Alchemy POF + anomaly threshold calibration
- Insider detection: blocked on math correction (heterogeneous probability test)
- n8n integration: blocked on n8n operational status + all loops working

## Requested From Architect
- Schema contracts (PKs, dedup keys, retention)
- Wallet lifecycle state machine
- Deterministic acceptance tests
- Work packet prompts for Claude Code

See [[10-Session-Notes/2026-04-09 Architect Review Assessment]]
