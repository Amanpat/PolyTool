# ADR 0005: Make RAG Optional in llm-bundle

Date: 2026-02-16
Status: Accepted

## Context

`polytool llm-bundle` imported RAG modules (`polymarket.rag.*`) at the top level.
On a travel laptop without the `[rag]` extra installed, running `llm-bundle` crashed
with an `ImportError` before producing any output. The dossier, manifest, and coverage
data were all available locally but inaccessible because of the hard RAG dependency.

## Decision

Make RAG imports lazy with a try/except guard:

- If RAG modules load, behavior is unchanged (queries run, excerpts included).
- If RAG modules are missing, `_RAG_AVAILABLE = False`:
  - `_run_rag_queries()` returns an empty list and prints a warning to stderr.
  - `rag_queries.json` is written as `[]`.
  - Bundle includes "_RAG unavailable; excerpts omitted._" in the RAG section.
  - Coverage section is unaffected.
  - Exit code is 0.

RAG errors at runtime (e.g., index missing) are also caught gracefully and produce
empty excerpts with a warning, rather than a non-zero exit.

## Consequences

- `llm-bundle` works on any machine with base PolyTool installed.
- Users without RAG get a clear message about what's missing.
- Coverage section (the primary Roadmap 4.1 deliverable) never depends on RAG.
