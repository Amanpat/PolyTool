---
title: "Phase 4 — Autoresearch + SimTrader Validation Automation"
type: reference
status: archived
source_zone: claude_memory
last_updated: 2026-05-23
lifecycle: archived
tags: [phase, status/todo]
---

# Phase 4 — Autoresearch + SimTrader Validation Automation

Source: roadmap v5.1 Phase 4.

**Two goals: (1) automate hypothesis validation; (2) launch parameter-level autoresearch.**

---

## Checklist

- [ ] `strategy-codify` — StrategySpec JSON → runnable SimTrader strategy class (NOT YET IN REPO)
- [ ] Historical tape library import — normalize all sources into standard tape format with tier tags (Silver/Bronze/Gold)
- [ ] Auto Level 1 validation — multi-tape replay automation
- [ ] `autoresearch import-results` — import autoresearch results into RIS (NOT YET IN REPO)
- [ ] Parameter autoresearch — automated parameter sweep with LLM-guided hypothesis generation

---

## Key Notes

- `autoresearch import-results` and `strategy-codify` are Phase 4 deliverables — do not attempt to call these commands; they do not exist in the repo yet.
- Parallel SimTrader (multiprocessing.Pool) is a prerequisite — listed in Phase 1B.

---

## Cross-References

- [[legacy/PolyTool/02-Modules/SimTrader]] — Validation engine for autoresearch
- [[legacy/PolyTool/02-Modules/RIS]] — Knowledge base that autoresearch feeds and reads
- [[legacy/PolyTool/01-Architecture/LLM-Policy]] — LLM providers used in autoresearch evaluation

## Connections

- [[claude-memory/research/_index]]
- [[index|Vault Home]]
- [[repo-docs/_index]]
