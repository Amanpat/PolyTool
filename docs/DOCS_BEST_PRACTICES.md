# Docs Best Practices

This is the public truth-source for documentation layout and standards.

## Where Things Live
- `docs/` = public, canonical documentation (safe to commit).
- `kb/` = private working knowledge base (gitignored).
- `artifacts/` = private exports and generated evidence (gitignored).

## ADRs (docs/adr)
- ADRs are required for major decisions that change architecture, data contracts, or workflows.
- Use sequential filenames `NNNN-short-title.md` and include date, decision, and status.
- ADRs must live under `docs/adr/` only.

## Specs
- `docs/specs/` = canonical public specs (reviewed and stable).
- `kb/specs/` = private draft specs and scratch work.
- Promote from `kb/specs/` to `docs/specs/` once the spec is ready for public truth-source.

## Feature Docs
- `docs/features/` houses user-facing or product feature descriptions.
- Keep feature docs aligned with shipped behavior; archive stale docs when replaced.

## Agent Run Log (Required)
- Every agent run must write a log under `kb/devlog/`.
- Use `kb/devlog/YYYY-MM-DD_<agent>_<packet>_<slug>.md`.
- Devlog is the canonical record; prompt text is stored inside the run's devlog markdown (no separate prompt files).

## Naming Conventions
- Dates: `YYYY-MM-DD` (UTC).
- User slug: lowercase, no spaces, derived from username/handle.
- `run_id`: short, unique ID (e.g., 8 chars) used in bundle/report folders.
- `model_slug`: lowercase, hyphenated model identifier (e.g., `local-llm`, `gpt-4o`).
