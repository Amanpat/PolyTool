---
tags: [session-note]
date: 2026-04-22
status: complete
topics: [ris, roadmap-review, implementation-details]
---
# RIS Roadmap v1.1 Review — Implementation Details Session

## Context
Reviewed the consolidated v1.1 roadmap. Pushed back on 6 implementation issues. User answered what they could, deferred technical unknowns to Claude Code discovery during WP1.

## User Inputs
- 3 friends confirmed ready to run RIS continuously (while at work)
- Ollama Cloud models preferred (DeepSeek 3.2 free on Ollama Cloud)
- PMXT roadmap completion in progress — Feature 2 slot freeing soon
- Currently setting up Hermes
- Prefers updates to existing n8n workflow over rebuild

## Decisions Made

### WP2 Provider Count: Keep all providers, but prioritize
Ollama Cloud with DeepSeek 3.2 is free and powerful — should be a first-class provider, not a fallback. Adjust provider priority: Gemini primary (operator), Ollama Cloud (friends default), DeepSeek API and OpenRouter as alternatives. Build all providers since friends are confirmed.

### Technical Unknowns: Resolve in WP1, not upfront
- CLI stdout format → Claude Code reads the code on Day 1, adds --json if needed
- WP6 packaging strategy → Claude Code determines minimal dependency set on Day 1
- Calibration budget → default to 10% reserve, adjust after first week of data
- WP3 approach → update existing workflow JSON via REST API

## Roadmap Adjustments
1. Ollama Cloud elevated from "fallback" to "friend default provider"
2. WP7 (continuous mode) timeline shortened — friends want continuous, Hermes setup in progress
3. Added "Day 1 discovery" step to WP1 for technical unknowns
4. WP3 confirmed as update-in-place (not rebuild)

## Cross-References
- [[RIS_OPERATIONAL_READINESS_ROADMAP_v1.1]] — authoritative roadmap
- [[Decision - Agent Parallelism Strategy for RIS Phase 2]]


## Final Review Complete (2026-04-22)

### Status: Ready for architect handoff

### Implementation issues flagged (for architect awareness, not blockers):
1. WP1-E seeding docs need to be extracted as files before ingestion
2. WP3-A depends on CLI stdout format — Day 1 discovery resolves this
3. WP6-A packaging strategy TBD during WP6 scoping (not Phase 2A)
4. Quality calibration loop needs mini-spec before WP6-D testing

### Ollama Cloud research completed:
- OpenAI-compatible at `https://ollama.com/v1/`
- `deepseek-v3.2:cloud` available on free tier
- Free tier: 1 concurrent model, session-based limits (unpublished)
- Provider is trivial subclass (~10 min implementation)
- Gemini remains recommended friend default (explicit 1,500/day quota)

### Files for architect handoff:
1. `RIS_OPERATIONAL_READINESS_ROADMAP_v1.1.md` — authoritative roadmap
2. `Decision - RIS Evaluation Scoring Policy.md` — scoring spec
3. `Decision - RIS Evaluation Gate Model Swappability.md` — provider spec
4. `Decision - Agent Parallelism Strategy for RIS Phase 2.md` — agent allocation
5. `2026-04-10 RIS Phase 2 Audit Results.md` — what's broken
6. `2026-04-09 GLM5 - Gemini Flash Structured Evaluation.md` — implementation code
7. `2026-04-09 GLM5 - n8n ClickHouse Grafana Metrics.md` — DDL + dashboard JSON
8. `2026-04-22 Research - Ollama Cloud API.md` — provider implementation reference

Hermes guide NOT included — only relevant for deferred WP7, would add scope to Phase 2A conversation.
