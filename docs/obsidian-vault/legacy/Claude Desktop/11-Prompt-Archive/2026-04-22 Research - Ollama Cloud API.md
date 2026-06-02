---
tags: [prompt-archive]
date: 2026-04-22
model: Deep Research
topic: Ollama Cloud API Format
---
# Ollama Cloud API — Research Results

## Key Findings
1. **OpenAI-compatible:** Yes. Cloud endpoint at `https://ollama.com/v1/`, same `/v1/chat/completions` format as local.
2. **Auth:** API key via `Authorization: Bearer <OLLAMA_API_KEY>`. Env var: `OLLAMA_API_KEY`.
3. **DeepSeek V3.2 available:** `deepseek-v3.2:cloud` on free tier. Original V3 (671B) NOT available as cloud model.
4. **Free tier limits:** 1 concurrent cloud model, session-based + weekly limits (no published token counts). Light usage only.
5. **Provider implementation:** Trivial subclass of OpenAICompatibleProvider. Only differences: base_url, `:cloud` model suffix, no embeddings.
6. **Friend strategy impact:** Free tier throttling means Gemini (1,500 explicit req/day) is more reliable for friends. Ollama Cloud is secondary option.

## Code Pattern
```python
class OllamaCloudProvider(OpenAICompatibleProvider):
    def __init__(self):
        super().__init__(
            api_key=os.environ["OLLAMA_API_KEY"],
            base_url="https://ollama.com/v1/",
            model="deepseek-v3.2:cloud",
        )
```
Note: append `:cloud` suffix to model names automatically.

## Applied To
- WP2-F in RIS Roadmap v1.1 (confirmed 10-minute implementation)
- Phase 2B friend provider strategy (secondary to Gemini, not primary)

See [[RIS_OPERATIONAL_READINESS_ROADMAP_v1.1]]
