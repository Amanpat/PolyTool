# Project Overview

PolyTool is a local-first toolbox for analyzing Polymarket activity. The repo is public, so it keeps
all private data (exports, dossiers, RAG indices) inside the repo tree but strictly gitignored.

Key goals:
- Local analysis: run scans, exports, and research workflows without external hosted services.
- Public docs as truth source: `docs/` is the canonical public reference.
- Private knowledge base: `kb/` and `artifacts/` store local-only data.
- Local RAG from day one: embeddings + Chroma persistence for offline retrieval.

Data boundaries:
- Public: `docs/`, source code, infra configs.
- Private: `kb/`, `artifacts/` (gitignored + pre-push guard).

See `docs/ARCHITECTURE.md` for the data flow, `docs/RISK_POLICY.md` for guardrails, and
`docs/adr/` for decision records.
