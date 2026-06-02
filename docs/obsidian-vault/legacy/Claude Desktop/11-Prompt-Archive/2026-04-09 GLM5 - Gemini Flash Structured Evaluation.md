---
tags: [prompt-archive]
date: 2026-04-09
model: GLM-5 Turbo
topic: Gemini Flash Structured Evaluation
---
# Gemini 2.5 Flash Structured Evaluation — Research Results

## Key Findings

1. **Constrained decoding is Gemini's killer feature.** Setting `response_mime_type="application/json"` + `response_schema={...}` constrains token sampling at the logit level. The model physically cannot return malformed JSON, wrong types, or missing fields. DeepSeek V3 does NOT support this.

2. **Free tier limits:** 15 RPM, 1,500 RPD, 1M TPM. `BatchEvaluator` class paces at 12 RPM (~5s intervals) to avoid 429s.

3. **Error handling matrix:** Retry on 429/503/timeout. No retry on 400/403/safety-block. `retryDelay` field in 429 response tells you how long to wait.

4. **DeepSeek V3 comparison:** Uses OpenAI-compatible client (`openai` package). JSON mode works but schema NOT enforced — needs strict post-validation, float→int normalization, and `_try_extract_json()` fallback. ~90-95% schema conformance vs Gemini's ~99.9%.

5. **Complete implementation provided:** `GeminiDocumentEvaluator` class with structured output, `BatchEvaluator` with RPM pacing, `DeepSeekDocumentEvaluator` with validation, and `filter_for_chromadb()` integration function.

## Applied To
- [[Decision - RIS Evaluation Gate Model Swappability]]
- [[Decision - RIS Evaluation Scoring Policy]]
- RIS Phase 2 Priority 1 implementation

## Source
Deep research prompt run by Aman, results discussed in [[10-Session-Notes/2026-04-09 RIS n8n Workflows and Phase 2 Roadmap]]
