---
type: architecture
tags: [architecture, llm, status/done]
created: 2026-04-08
---

# LLM Policy

Source: roadmap "LLM Policy — Self-Funding Model" section.

---

## Tier System

| Tier | Model | Cost | When Used |
|------|-------|------|-----------|
| **Tier 1** | Free cloud APIs (DeepSeek V3/R1, Gemini 2.5 Flash) | Free | All automated hypothesis generation, scraper evaluation, signal classification |
| **Tier 1b** | Ollama local (Qwen3-30B or Llama-3-8B) | Free | Fallback when cloud APIs are down or rate-limited |
| **Tier 2** | Manual escalation (Claude / ChatGPT) | Free (operator tokens) | When Tier 1 flags low confidence |
| **Tier 3** | Claude API auto-escalation | Paid API | Only enabled when `bot_profit_30d > api_cost_estimate` |

---

## Offline-First Principle

Llama-3-8B running locally on 32GB RAM alongside Docker + ClickHouse + DuckDB leaves insufficient headroom for quality inference. DeepSeek V3 via free API provides dramatically better reasoning at zero cost. Gemini 2.5 Flash via Google AI Studio gives 1,500 free requests/day — enough for signal classification.

**Graceful degradation:** try Tier 1 cloud → fall back to Tier 1b local → flag for Tier 2 manual if both fail.

---

## Multi-LLM Specialist Routing (Phase 3)

| Specialist | Task | Recommended Model |
|------------|------|-------------------|
| Wallet Analyst | Dossier → hypothesis | DeepSeek V3 (best reasoning) |
| Research Evaluator | Document → quality score | Gemini Flash (fast, free quota) |
| Signal Classifier | News + market → relevance | Gemini Flash |
| Post-mortem Writer | Failed strategy → report | DeepSeek R1 (structured output) |

---

## Human-in-Loop at Tier Boundaries

- Tier 1 flags LOW_CONFIDENCE → Tier 2 manual escalation (human approval required)
- Tier 3 auto-escalation requires `bot_profit_30d > api_cost_estimate` check — never auto-pays unless revenue covers it

---

## Cross-References

- [[RAG]] — ChromaDB and KnowledgeStore serve as the backing knowledge store for LLM context
- [[RIS]] — RIS evaluation subpackage uses LLM providers from `packages/research/evaluation/providers.py`
- [[System-Overview]] — LLM calls live in Python core layer, not FastAPI or CLI
