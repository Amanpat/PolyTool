# 2026-04-24 Vera — NVIDIA Build / NIM Provider Check

## Scope

Investigate whether vera-hermes-agent can use NVIDIA Build / NIM as an
OpenAI-compatible fallback provider. Goal: know if it's supported; add
safe config template; run a non-mutating auth/model test if a key is present.

## Files Changed

| File | Change | Why |
|---|---|---|
| `/home/patel/.hermes/profiles/vera-hermes-agent/.env` | Added commented `NVIDIA_API_KEY=` template (lines 119–132) | Objective: add template for user to fill |
| `docs/dev_logs/2026-04-24_vera-nvidia-provider-check.md` | Created (this file) | Mandatory per repo convention |

No skill files changed. No config.yaml changed. No code changed.
`approvals.mode: deny` preserved throughout.

---

## Step 1 — Does Hermes Support Custom OpenAI-Compatible Providers?

### Finding: YES — confirmed from source and tests

Hermes exposes `provider: custom` in the `fallback_model` config block.
Exact syntax (confirmed from
`/home/patel/.hermes/hermes-agent/tests/run_agent/test_fallback_model.py`,
`test_custom_base_url` at line 207):

```yaml
fallback_model:
  provider: custom
  model: meta/llama-3.1-8b-instruct
  base_url: https://integrate.api.nvidia.com/v1
  api_key_env: NVIDIA_API_KEY
```

**IMPORTANT CORRECTION:** The comment block in `config.yaml` reads:
```
# For custom OpenAI-compatible endpoints, add base_url and key_env.
```
The actual field name is `api_key_env`, NOT `key_env`. Using `key_env` will
silently fail to load the credential. The test file is authoritative.

### How the custom provider path works (from run_agent.py line 6257–6276)

Hermes calls `resolve_provider_client()` with the `fallback_model` dict.
When `provider == "custom"`, it reads `base_url` and `api_key_env` from the
config dict, resolves the env var value, and builds an OpenAI SDK client
pointing at the custom endpoint. This is the same client used for all other
OpenAI-compatible providers. NVIDIA NIM exposes the exact same API surface,
so it is directly compatible.

---

## Step 2 — NVIDIA_API_KEY Presence Check

Checked:
- `/home/patel/.hermes/profiles/vera-hermes-agent/.env` — no `NVIDIA_API_KEY` entry (before this session)
- WSL environment (`printenv | grep NVIDIA`) — not set
- Global `/home/patel/.hermes/.env` — not checked, but vera profile .env takes precedence

**Result: NVIDIA_API_KEY not present. Steps 4–6 (fallback config + test) cannot execute.**

---

## Step 3 — .env Template Added

Added commented NVIDIA block to
`/home/patel/.hermes/profiles/vera-hermes-agent/.env`
before the `TOOL API KEYS` section (new lines 119–132):

```bash
# =============================================================================
# LLM PROVIDER (NVIDIA Build / NIM)
# =============================================================================
# NVIDIA Build exposes OpenAI-compatible inference for free open models.
# Get your key at: https://build.nvidia.com (free tier, no credit card)
# To use as a Hermes fallback, add to config.yaml fallback_model:
#   fallback_model:
#     provider: custom
#     model: meta/llama-3.1-8b-instruct
#     base_url: https://integrate.api.nvidia.com/v1
#     api_key_env: NVIDIA_API_KEY
# Note: field is api_key_env (not key_env — the config comment is wrong).
# NVIDIA_API_KEY=
```

---

## Step 4–6 — Deferred: NVIDIA_API_KEY Not Present

Per objective constraints: do not configure the fallback and do not run
provider tests when the key is absent. These steps are blocked until the
user adds a value.

---

## Additional Finding — Existing Fallback Misconfiguration

The current `config.yaml` has an **active** (uncommented) `fallback_model` block:

```yaml
fallback_model:
  provider: openrouter
  model: google/gemini-2.0-flash-001
```

However, `OPENROUTER_API_KEY` in `.env` is **commented out**. Running
`vera-hermes-agent doctor` shows: `"OpenRouter API (not configured)"`.

If the Ollama Cloud primary provider fails (e.g., 429 quota), the fallback
will also fail silently because the OpenRouter key is absent. This is an
existing gap from the previous session — it is not introduced by this work.

---

## Provider Unlock Path (User Action Required)

### To activate NVIDIA Build as fallback

1. Sign up at https://build.nvidia.com (no credit card required for free tier)
2. Generate an API key under "Get API Key"
3. Fill in `.env`:
   ```
   NVIDIA_API_KEY=nvapi-<your-key>
   ```
4. In `config.yaml` under `fallback_model`, replace the existing block with:
   ```yaml
   fallback_model:
     provider: custom
     model: meta/llama-3.1-8b-instruct
     base_url: https://integrate.api.nvidia.com/v1
     api_key_env: NVIDIA_API_KEY
   ```
5. Run the minimal auth test:
   ```bash
   wsl bash -lc "vera-hermes-agent chat -Q -q 'Reply with exactly: nvidia nim ready'"
   ```
6. If that passes, run F2–F8 from `docs/dev_logs/2026-04-23_vera-operator-validation-closeout.md`

### Recommended NVIDIA NIM models (free tier)

| Model | ID for config | Notes |
|---|---|---|
| Meta Llama 3.1 8B | `meta/llama-3.1-8b-instruct` | Fast, free, broadly capable |
| Meta Llama 3.2 3B | `meta/llama-3.2-3b-instruct` | Smallest, fastest |
| Mistral 7B | `mistralai/mistral-7b-instruct-v0.3` | Solid instruction following |
| Nemotron 70B | `nvidia/llama-3.1-nemotron-70b-instruct` | Highest quality, slower |

`meta/llama-3.1-8b-instruct` is the recommended default for Vera's
read-only Q&A workload — small enough to be fast, capable enough for
doc retrieval and summarization.

### Alternative: Use existing OpenRouter fallback instead

If the user prefers OpenRouter (which is already wired in config.yaml):
1. Uncomment and fill in `.env`:
   ```
   OPENROUTER_API_KEY=sk-or-v1-<your-key>
   ```
2. No config.yaml change needed — the OpenRouter block is already active.
3. Run the same minimal test:
   ```bash
   wsl bash -lc "vera-hermes-agent chat -Q -q 'Reply with exactly: openrouter ready'"
   ```

---

## Summary

| Item | Result |
|---|---|
| Hermes custom OpenAI-compatible provider support | **CONFIRMED** — `provider: custom` + `base_url` + `api_key_env` |
| NVIDIA Build / NIM endpoint compatibility | **YES** — OpenAI-compatible; no Hermes changes needed |
| Correct config field name | **`api_key_env`** (not `key_env` as the config.yaml comment says) |
| NVIDIA_API_KEY present | **NO** — template added for user to fill |
| Fallback configured | **NO** — key absent; config.yaml not changed |
| Safety posture | **UNCHANGED** — `approvals.mode: deny` preserved |
| F2–F8 tests | **STILL DEFERRED** — provider key required |

## Codex Review

Tier: Skip — docs and .env template only, no code changed.
