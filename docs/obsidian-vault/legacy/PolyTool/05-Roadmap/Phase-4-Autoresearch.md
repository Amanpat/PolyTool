---
type: phase
phase: 4
status: todo
tags: [phase, status/todo]
created: 2026-04-08
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

- [[SimTrader]] — Validation engine for autoresearch
- [[RIS]] — Knowledge base that autoresearch feeds and reads
- [[LLM-Policy]] — LLM providers used in autoresearch evaluation

