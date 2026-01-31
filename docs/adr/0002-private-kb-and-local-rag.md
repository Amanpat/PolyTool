# ADR 0002: Private KB + Local RAG (Local-Only)

Date: 2026-01-30
Status: Accepted

## Context
We need a clean public documentation surface while keeping private user data, exports, and dossiers
inside the repo for offline analysis. We also want retrieval-augmented workflows from day one, but
without external APIs or hosted services.

## Decision
- Establish `kb/` as the private knowledge base root and `artifacts/` for exports/dossiers.
- Gitignore all private data and enforce a local pre-push guard.
- Build a local embedding-based RAG index using Sentence-Transformers + Chroma persistence.
- Restrict indexing to `kb/` and `artifacts/` only (never `docs/`).

## Consequences
- RAG workflows are fully local and reproducible, but require heavier local dependencies.
- Private data remains in-repo for convenience, but is blocked from Git.
- Documentation stays public and auditable, with ADRs capturing decisions.
