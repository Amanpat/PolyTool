# Knowledge Base Conventions

This document defines where public vs private materials live and how to structure
the private knowledge base (`kb/`) used by Local RAG. It is part of the public
truth-source docs.

## Public vs private boundary

Public (safe to commit):
- `docs/` is the public truth source.
- ADRs stay in `docs/adr/`.
- Canonical public docs include `PROJECT_OVERVIEW.md`, `ARCHITECTURE.md`,
  `RISK_POLICY.md`, ADRs, and any official specs.

Private (never commit):
- `kb/` is the private knowledge base (gitignored).
- `artifacts/` contains private exports + dossiers (gitignored).

See `docs/RISK_POLICY.md` for guardrails and enforcement details.

## Private KB layout (indexed by default)

Store workshop material under `kb/` so it is indexed by Local RAG by default:

- `kb/devlog/` : chronological Agent Run Logs (required for every agent run)
- `kb/specs/` : draft or experimental mini-specs
- `kb/prompts/` : reusable prompts and prompt experiments
- `kb/users/<slug>/notes/` : user-specific notes
- `kb/users/<slug>/llm_reports/<YYYY-MM-DD>/<model_slug>_<run_id>/` :
  `report.md`, `prompt.txt`, `inputs_manifest.json`, `takeaways.json` (optional)

## Agent Run Logs (required)

Every agent run must write a local log file under `kb/devlog/`. These logs are
intentionally private and must remain untracked.

Filename format:
- `kb/devlog/YYYY-MM-DD_<slug>.md`
- Example: `kb/devlog/2026-02-03_packet-a-docs.md`

Frontmatter template:

```markdown
---
date_utc: YYYY-MM-DD
agent: codex|claude
packet: A
scope: docs|code|ops
summary: "..."
files_changed:
  - path: ...
commands_run:
  - ...
notes:
  - ...
next_steps:
  - ...
---

# Agent Run Log

## Summary
## Files Changed
## Commands Run
## Notes
## Next Steps
```
