---
type: issue
severity: low
status: open
tags: [issue, http, status/open]
created: 2026-04-08
---

# Issue: Multiple HTTP Client Wrappers

Source: audit Section 7.3.

Three separate HTTP client approaches coexist in the codebase.

---

## Current State

| Approach | Files | Notes |
|----------|-------|-------|
| `packages/polymarket/http_client.py` (shared wrapper) | `gamma.py`, `data_api.py`, `clob.py` | Canonical — has retry/backoff |
| `requests.get` / `requests.post` direct | Several tools and packages | Ad-hoc, no shared session |
| `httpx` (async) | `packages/research/ingestion/fetchers.py` | Different library entirely |

---

## Risk

- Retry/backoff behavior inconsistent across HTTP callers
- Rate limiting not enforced uniformly
- `httpx` async in `fetchers.py` may behave differently from sync `requests` paths under load

---

## Resolution

Consolidate ad-hoc `requests` calls to use `PolyHttpClient` from `http_client.py`. The `httpx` path in `fetchers.py` may be intentional (async I/O for research scraping) — review before changing.

---

## Cross-References

- [[Core-Library]] — `http_client.py` is the canonical HTTP wrapper
- [[RIS]] — `fetchers.py` uses httpx

