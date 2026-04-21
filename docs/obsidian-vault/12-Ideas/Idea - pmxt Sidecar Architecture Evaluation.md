---
tags: [idea, pmxt, architecture]
date: 2026-04-10
status: parked
topics: [pmxt, sidecar, Docker, py-clob-client]
---

# Idea — pmxt Sidecar Architecture Evaluation

## Context

During deep dive of pmxt showcase projects ([[08-Copy-Trader-Deep-Dive]]), discovered that pmxt uses a **Node.js sidecar architecture** — a local Node.js server on port 3847 handles all exchange communication. The Python SDK is a thin HTTP client to this sidecar.

This has implications for our Docker deployment pattern (docker-compose with .env for secrets and host-mounted volumes). The sidecar would need to be either:
- A separate Docker service in docker-compose.yml
- Installed inside our Python container (requires Node.js in the image)
- Run as a subprocess spawned by our Python code

## Decision Needed

Should we commit to pmxt as our unified prediction market SDK, or continue with py-clob-client (Polymarket direct) and build our own Kalshi adapter in Phase 3?

## Recommendation

**Park until Phase 3.** py-clob-client works for Phase 1A/1B. Evaluate when Kalshi integration becomes active.

## Cross-References

- [[08-Copy-Trader-Deep-Dive]] — Where this question was identified
- [[07-Backtesting-Repo-Deep-Dive]] — Backtesting repo also uses pmxt but via NautilusTrader adapter
