# Private Knowledge Base (local-only)

This folder is for **local, private** research data and outputs. Everything under `kb/` is
.gitignored except this README and the `.gitkeep` placeholder.

Expected subfolders (all private, gitignored):
- `kb/users/` - per-user exports, notes, and LLM outputs
- `kb/research_dumps/` - raw dumps from external sources
- `kb/incidents/` - incident notes and timelines
- `kb/experiments/` - scratch experiments and trials
- `kb/rag/index/` - local Chroma index persistence
- `kb/rag/manifests/` - index manifests

Keep sensitive data here, not in `docs/`.
