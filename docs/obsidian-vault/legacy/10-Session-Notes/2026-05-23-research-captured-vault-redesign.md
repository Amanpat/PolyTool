---
title: Session - GLM Research Captured for Vault Redesign
type: session_note
status: active
source_zone: conversation
last_updated: 2026-05-23
generator: claude-desktop
human_authored: false
tags:
  - session
  - research
  - vault-design
  - ris
  - obsidian
references:
  - "[[2026-05-23-research-llm-obsidian-vault-design]]"
related:
  - "[[12-Ideas]]"
aliases:
  - Vault Redesign Research Capture
---

# Session — GLM Research Captured for Vault Redesign

## Context

Five GLM research prompts (A–E) executed and returned. Topics: LLM-optimized vault design, vector-DB-to-markdown sync, multi-source vault patterns, plugin stack, consolidation strategy.

Full research packet too large for direct vault write (~14K words, exceeds append limit). Saved to `/mnt/user-data/outputs/2026-05-23-research-llm-obsidian-vault-design.md` for manual placement in vault. Target location once placed: `09-Decisions/` or new `13-Research/` folder.

## Key Decisions Supported by Evidence

1. Adopt strict frontmatter schema: `type` / `status` / `source_zone` / `last_updated` / `confidence` / `lifecycle` + cross-refs. Pattern proven in llm-wiki and ClawVault v2.6.0.
2. kebab-case slugs for content; ISO date prefix only for temporal docs (sessions, logs).
3. `index.md` + `log.md` at vault root as primary LLM navigation surface (Karpathy pattern).
4. Three-zone separation: `repo-docs/` / `conversations/` / `ris-mirror/` with frontmatter `source_zone` enum.
5. RIS mirror gitignored, regenerable from Chroma, one-way sync. Follow Neotoma + knoten patterns. Manifest tracks IDs for delete detection.
6. Plugin stack: Obsidian Bases (replaces Dataview), Templater 2.20.4, Local REST API 0.26.0, Linter, MetaEdit, Mermaid.
7. **Sonar's IndexedDB-only index confirms two-layer architecture**: Chroma stays canonical RAG, Obsidian is human/LLM browse layer. Pipelines never query Sonar.
8. Consolidation: tier + ADR + archive. Never delete. Mark superseded. Move to `archive/`.

## Reference Sources

- llm-wiki (Pratiyush) — https://github.com/Pratiyush/llm-wiki
- ClawVault v2.6.0 — https://docs.clawvault.dev
- Karpathy LLM wiki — https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- Neotoma mirror — https://neotoma.io/ar/mirror-guide
- knoten v0.4.1 — https://libraries.io/pypi/knoten
- Clearwater KB — Medium, cwan-engineering
- contextlint — https://koborin.ai/tech/contextlint-introduction
- KnowledgeBase Guardian — https://github.com/datarootsio/knowledgebase_guardian
- coddingtonbear/obsidian-local-rest-api v0.26.0 — https://github.com/coddingtonbear/obsidian-local-rest-api
- cyanheads/obsidian-mcp-server — https://github.com/cyanheads/obsidian-mcp-server

## Next Step

Synthesize research into vault design specification (separate document). Design will be a Tier 1 / Source of Truth document covering:

- Final frontmatter schema (typed YAML with enums)
- Three-zone folder layout with explicit examples
- RIS mirror sync architecture diagram and write policy
- Plugin install manifest
- Consolidation playbook for migrating from current vault

## Status

- Research: COMPLETE
- Design synthesis: PENDING (next session)
- Vault modification: NOT STARTED (user constraint: no changes yet)
