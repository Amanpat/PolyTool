---
tags: [decision]
date: 2026-04-09
status: accepted
---
# Decision — RIS Evaluation Gate Model Swappability

## Context
The RIS evaluation gate needs cloud LLM providers (Gemini Flash, DeepSeek V3) to replace the ManualProvider that hardcodes all scores to 3. Multiple models must be testable during calibration, and future models must plug in without code changes.

## Decision
All LLM evaluation providers extend a common `OpenAICompatibleProvider` base class. Switching models is a config change, not a code change.

- **Primary:** Gemini 2.5 Flash (constrained decoding via `response_schema`)
- **Escalation:** DeepSeek V3 (OpenAI-compatible, score 8-12 triggers escalation)
- **Fallback:** Ollama (local, used when cloud APIs fail)
- **Configuration:** `config/ris_eval_config.json` with `primary_provider`, `escalation_provider`, `fallback_provider`
- **CLI flag:** `--provider gemini|deepseek|ollama|all`
- **Env var:** `RIS_EVAL_PROVIDER=gemini` (for scheduler/n8n)

## Key Design Points
- Same evaluation prompt shared across all providers (provider-agnostic)
- Gemini uses constrained decoding (`response_schema`); DeepSeek needs strict post-validation
- Any OpenAI-compatible endpoint (Groq, Together AI, local vLLM) works as a one-line subclass
- Fail-closed contract: provider failure must never auto-accept a document

## Alternatives Considered
- Gemini-only: too fragile, no escalation path
- Provider-specific prompts: maintenance burden, inconsistent scoring
- Hard-coding model versions: prevents testing new releases

## Impact
- Operator can A/B test providers with `--provider all --compare`
- Model upgrades are config changes
- Calibration period uses multi-provider comparison to pick optimal routing

See [[02-Modules/RIS]], [[10-Session-Notes/2026-04-09 RIS n8n Workflows and Phase 2 Roadmap]]
