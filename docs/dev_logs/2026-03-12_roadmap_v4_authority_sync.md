# Roadmap v4 Authority Sync

Date: 2026-03-12
Branch: `phase-1`
Scope: docs-only; no code, no gate changes, no milestone promotion.

## Summary

- Adopted `docs/reference/POLYTOOL_MASTER_ROADMAP_v4.md` as the governing
  roadmap reference across `PLAN_OF_RECORD`, `ARCHITECTURE`, `ROADMAP`, and
  `CURRENT_STATE`.
- Reframed `docs/ROADMAP.md` as the legacy implementation ledger under v4
  authority.
- Added explicit conflict notes instead of rewriting current implementation
  truth to match future-state roadmap language.

## Material Conflicts Surfaced

1. Strategic scope vs current shipped scope
   - v4 targets automated discovery, validation, live execution, and a
     self-improving loop.
   - Current shipped truth remains local-first research workflows plus gated
     execution primitives.

2. Automation stack
   - v4 north star assumes thin FastAPI wrappers, n8n orchestration, Discord
     operations, and later AWS hosting.
   - Current architecture remains CLI-first/local-first; those automation
     layers are not current implementation truth.

3. Research breadth
   - v4 Phase 2 makes `candidate-scan`, research scraper, and signals pipelines
     first-class.
   - Current Track B completion covers `wallet-scan`, `alpha-distill`, RAG
     hardening, and hypothesis registry/experiment scaffolding only.

4. Live-bot status
   - v4 Phase 1 includes Stage 0 paper-live and Stage 1 capital deployment.
   - Current repo truth remains Gate 2 not passed, Gate 3 blocked, and no
     Stage 0/Stage 1 completion.

5. UI authority
   - v4 Phase 7 defines a unified Next.js/Tremor/Lightweight Charts Studio
     rebuild.
   - Current operator UI remains the existing Studio, Grafana, and CLI
     surfaces.

6. LLM/API policy
   - v4 allows future paid Claude API auto-escalation after profitability.
   - Current operating policy remains no external LLM API calls from the
     toolchain.

## Path Resolution Note

- The governing roadmap file present during this sync was
  `docs/reference/POLYTOOL_MASTER_ROADMAP_v4.md`.
- A repo-root `POLYTOOL_MASTER_ROADMAP_v4.md` was not present in the working
  tree at sync time.

## Non-Changes

- No code touched.
- No gate criteria changed.
- No blocked milestone was marked complete.
- No branch was created.