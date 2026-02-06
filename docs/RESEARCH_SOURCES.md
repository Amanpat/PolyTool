# Research Sources

PolyTool's `cache-source` command fetches and caches trusted web content for
local RAG indexing. This document describes the curated source list, the
allowlist approach, and the TTL concept.

## Allowlist Approach

Only URLs matching the allowlist are fetched. This prevents accidental crawling
of untrusted or irrelevant sites. The allowlist is configured in `polytool.yaml`
under `kb_sources_caching.allowlist` or falls back to the built-in default.

To cache a source:

```powershell
python -m polytool cache-source --url "https://docs.polymarket.com/..." --ttl-days 14
```

If the URL does not match the allowlist, the command exits with an error.

## Curated Source Domains

| Domain | What It Provides |
|--------|-----------------|
| `docs.polymarket.com` | Official Polymarket documentation (API, protocol, fees) |
| `learn.polymarket.com` | Polymarket learning resources and guides |
| `github.com/Polymarket/` | Open-source Polymarket repos (contracts, SDKs) |
| `docs.alchemy.com` | Alchemy blockchain API docs (for on-chain resolution) |
| `thegraph.com/docs` | The Graph indexing docs (subgraph queries) |
| `dune.com/docs` | Dune Analytics docs (SQL-based on-chain analytics) |
| `mlfinlab.readthedocs.io` | ML for finance library docs (feature engineering) |
| `vectorbt.dev/docs` | VectorBT backtesting library docs |
| `arxiv.org` | Academic papers (prediction markets, market microstructure) |
| `papers.ssrn.com` | SSRN working papers (finance, economics) |
| `nber.org/papers` | NBER working papers (economics research) |
| `the-odds-api.com/docs` | Odds API docs (sports/event odds for comparison) |
| `developer.sportradar.com/docs` | Sportradar API docs (sports data) |

## TTL (Time-to-Live)

Each cached source has a TTL that controls when re-fetching is needed:

- **Default TTL**: 14 days (configurable via `--ttl-days` or `polytool.yaml`).
- **Per-domain overrides**: Can be set in `polytool.yaml` under
  `kb_sources_caching.ttl_days.<domain>`.
- **Force refresh**: Use `--force` to re-fetch regardless of TTL.
- **Expiry check**: On each invocation, if the cached version is still within TTL,
  the cached version is used without re-fetching.

## Storage

Cached content lives in:

```
kb/sources/<safe_filename>.md          # Markdown content
kb/sources/<safe_filename>.meta.json   # Metadata (URL, hash, TTL, fetch time)
```

This directory is **private and gitignored**. The actual cached content is never
committed to the repo. Only this documentation page (which lists domains, not
content) is public.

## Robots.txt Compliance

By default, `cache-source` checks `robots.txt` before fetching. The check is
basic (matching `Disallow` rules for `User-agent: *`). Full robots.txt parsing
is a Roadmap 4 item. Use `--skip-robots` to bypass (not recommended).

## Adding New Sources

1. Add the domain to `polytool.yaml` under `kb_sources_caching.allowlist`.
2. Run `python -m polytool cache-source --url "<url>"`.
3. Rebuild the RAG index: `python -m polytool rag-index --roots "kb,artifacts" --rebuild`.
