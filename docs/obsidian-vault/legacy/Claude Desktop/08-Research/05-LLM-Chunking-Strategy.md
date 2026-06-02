# LLM Chunking Strategy — Hybrid Metrics + Exemplars
**Status:** Decided
**Last updated:** 2026-04-08
**Source:** GLM-5 Turbo research on processing large financial datasets through LLMs

## Decision: Hybrid Approach (Option 4 from research)

**Rejected:** Pure map-reduce (loses subtle signals in summarization step)
**Rejected:** Multi-agent mesh (too expensive for free-tier APIs, coordination overhead)
**Rejected:** Full raw data to LLM (exceeds context windows, wastes tokens on noise)

**Chosen:** Programmatic metrics (Python) + selective raw exemplars + single LLM call

## Architecture

1. **Python computes all quantitative metrics** (12-dim MVF + strategy detectors)
   - Deterministic, fast, free
   - LLM never does statistical analysis
2. **Python selects exemplars** (10-20 most anomalous trades)
   - Top PnL, top size, anomalous timing, resolution-proximity trades
   - Each annotated with one-line explanation of WHY it's unusual
3. **Single LLM call** receives compact package:
   - Metrics table (markdown or JSON)
   - Annotated exemplars
   - Existing detector outputs
   - Strategy classification reference
   - Task: "Propose 1-3 non-obvious strategy hypotheses with evidence + testable predictions"

## Why This Works

- LLM's job is PATTERN RECOGNITION and HYPOTHESIS GENERATION on pre-digested data
- Python is better at statistical analysis — let each tool do what it's best at
- Keeps context well under any model's limit, even free-tier 64K models
- Research showed exemplars are critical for novel strategy discovery (in-context learning evidence)
- The detectors catch known patterns; the LLM finds what the detectors weren't designed for

## Model Priority
1. Gemini Flash (1M context, free 1500 req/day) — primary
2. DeepSeek V3 (64K context, free API) — escalation for borderline cases
3. Ollama local (Qwen3-30B) — fallback when cloud APIs down
