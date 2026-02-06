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
- `docs/specs/` contains canonical public specs.

Private (never commit):
- `kb/` is the private knowledge base (gitignored).
- `kb/specs/` contains private draft specs and working notes.
- `artifacts/` contains private exports + dossiers (gitignored).

See `docs/RISK_POLICY.md` for guardrails and enforcement details.

## Private KB layout (indexed by default)

Store workshop material under `kb/` so it is indexed by Local RAG by default:

- `kb/devlog/` : chronological Agent Run Logs (required for every agent run)
- `kb/specs/` : draft or experimental mini-specs
- `kb/sources/` : cached web sources for RAG indexing (from `cache-source`)
- `kb/users/<slug>/notes/` : user-specific notes
- `kb/users/<slug>/notes/LLM_notes/` : LLM-generated note entries (auto-created by `llm-save`)
- `kb/users/<slug>/llm_reports/<YYYY-MM-DD>/<model_slug>_<run_id>/` :
  `report.md`, `hypothesis.md`, `hypothesis.json`, `inputs_manifest.json`
- `kb/users/<slug>/llm_bundles/<YYYY-MM-DD>/<run_id>/` : evidence bundle outputs
- `kb/users/<slug>/exports/<YYYY-MM-DD>/` : ClickHouse export datasets

## LLM_notes Directory

The `kb/users/<slug>/notes/LLM_notes/` directory contains user-facing note entries
that summarize LLM analysis runs. These notes are automatically created by `llm-save`
and serve as an index into the full reports stored under `llm_reports/`.

Each note contains:
- Summary bullets (when available)
- Links to full hypothesis.md and hypothesis.json
- Metadata (user, wallet, run_id, model, created_at)

This structure ensures LLM analysis notes are surfaced during RAG queries about
a user's trading activity.

Prompt text for llm-save and agent runs is stored inside each devlog markdown file.

## Bootstrap (local-only)

Run the bootstrap script once on a new machine to create the private KB folders:

```powershell
powershell -ExecutionPolicy Bypass -File tools\bootstrap_kb.ps1
```

Optionally create user-specific folders at the same time:

```powershell
powershell -ExecutionPolicy Bypass -File tools\bootstrap_kb.ps1 --user "@example"
```

## Agent Run Logs (required)

Every agent run must write a local log file under `kb/devlog/`. These logs are
intentionally private and must remain untracked.

Filename format:
- `kb/devlog/YYYY-MM-DD_<agent>_<packet>_<slug>.md`
- Example: `kb/devlog/2026-02-03_codex_packet-a_docs.md`

Frontmatter template:

```markdown
---
date_utc: YYYY-MM-DDTHH:MM:SSZ
agent: codex|claude
packet: <id>
scope: docs|code|ops
run_id: <uuid4>
prompt_sha256: <sha256>
spec_path: <optional path>
notes: []
next_steps: []
---

# Agent Run Log

## Summary
TODO
## Prompt
```text
<verbatim prompt>
```
## Files Changed
TODO
## Commands Run
TODO
## Notes
TODO
## Next Steps
TODO
```
