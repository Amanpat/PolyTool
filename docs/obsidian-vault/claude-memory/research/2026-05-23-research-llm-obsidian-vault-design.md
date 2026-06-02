---
title: LLM Obsidian Vault Design Research
type: research
status: active
source_zone: claude_memory
last_updated: 2026-05-23
lifecycle: reviewed
tags:
  - vault
  - llm
  - obsidian
  - design
  - research
contradiction: C-004
---

# LLM Obsidian Vault Design Research
> [!info] About this document
> Five-prompt research packet run through GLM on 2026-05-23 to ground the redesign of the PolyTool Obsidian vault. Findings inform the vault layout, frontmatter schema, RIS mirror architecture, plugin stack, and consolidation strategy. Synthesized into the vault redesign spec (claude-memory/spec/vault-redesign-spec.md).

## TL;DR — Key Decisions Supported by Evidence

1. **Adopt a strict frontmatter schema** with `type`, `status`, `source_zone`, `last_updated`, `confidence`, `lifecycle`, plus cross-references (`sources`, `supersedes`, `depends_on`). Pattern proven in llm-wiki and ClawVault v2.6.0.
2. **Use kebab-case slugs** for content docs; date-prefix only for temporal documents (session logs, daily notes). Confirmed by ClawVault, llm-wiki, and Karpathy's LLM wiki gist.
3. **Maintain an `index.md` + `log.md` at vault root** as the primary LLM navigation surface (Karpathy pattern). Per-folder README files are secondary, for humans.
4. **Three-zone folder separation** (`repo-docs/`, `claude-memory/`, `ris-mirror/`) with frontmatter `source_zone` enum enforcing zone discipline. Mirrors Clearwater Analytics' tiered KB and llm-wiki's `raw/` vs `wiki/` split.
5. **RIS mirror is gitignored, regenerable from Chroma, one-way sync** following Neotoma + knoten patterns. Manifest tracks synced IDs for delete detection.
6. **Plugin stack**: Obsidian Bases (core, replaces Dataview), Templater 2.20.4, Local REST API 0.26.0, Linter, MetaEdit, Mermaid (core).
7. **Sonar's IndexedDB-only index confirms the two-layer architecture is correct**: Chroma stays the canonical RAG backend, Obsidian is the human/LLM browse layer.
8. **Consolidation pattern**: tiered authority (Tier 1 Source of Truth overrides Tier 2), ADRs for decisions, archive superseded docs in `archive/` folder, never delete.

---

# PROMPT A — LLM-Optimized Markdown Knowledge Base Design

## Q1 — Frontmatter as Machine API

**Direct answer.** Emerging 2025–2026 LLM-wiki systems use small, strictly controlled frontmatter schemas centered on `type`, `status`/`lifecycle`, `last_updated`/`last_verified`, and cross-reference fields like `sources`, `depends_on`, and `supersedes`. These fields are treated as the machine-readable API: agents are instructed to treat frontmatter as authoritative over body text, and to filter or weight by status/lifecycle and staleness. Production enforcement is still mostly advisory (runtime warnings, lints), though tools like ClawVault and contextlint are moving toward stronger schema validation.

**Evidence.**

- **llm-wiki AGENTS.md / CLAUDE.md (Pratiyush/llm-wiki)** — Defines page templates for sources, entities, concepts with frontmatter including `type`, `sources`, `last_updated`, `confidence`, and `lifecycle` (draft/reviewed/verified/stale/archived). Schema explicitly states: "Frontmatter is authoritative. Always populate `title`, `type`, `tags`, `sources`, `last_updated`, `confidence`, `lifecycle`, `entity_type`."
- **ClawVault vault structure & frontmatter schema** — All documents use YAML frontmatter with core fields `title`, `date`, `memoryType`, plus relationship fields `related`, `depends_on`/`dependsOn`, `blocked_by`, `blocks`, `owner`, `project`, `people`, `links`. Extracted by a graph indexer to create edges; frontmatter relation fields treated as structured graph edges, not just text.
- **ClawVault template schemas (v2.6.0)** — Templates define YAML schemas with `type`, `required`, `default`, `enum` for fields like `status` and `priority`. Example: `status: {type: string, required: true, default: open, enum: [open, in-progress, blocked, done]}`.
- **SKILL.md / agentskills.io spec** — Constrained frontmatter schema for skills: `name` (kebab-case, max 64 chars), `description` (max 1024 chars), plus optional `version`, `author`, `tags`, `requires`. Enforced at skill registration time.
- **Atlan — LLM Knowledge Base Staleness** — "Active metadata" patterns for staleness: `as_of`, `valid_until`, `last_verified`. Argues that LLMs treat retrieved docs as authoritative, so missing staleness signals lead to confident wrong answers.
- **Stale docs / confident wrong answers** — LLM help centers give confident wrong answers when docs are outdated; recommends explicit freshness metadata and audits.

**Confidence.** High for status/lifecycle and staleness fields (multiple independent examples); medium for cross-reference fields like `supersedes`/`superseded_by`.

**Gaps.** No widely adopted universal schema; each project rolls its own. Little hard evidence that agents systematically respect `superseded_by` or `valid_until` without explicit prompting. Schema validation is mostly advisory/warning, not blocking.

## Q2 — Maps of Content (MOCs) vs Index Files for LLM Navigation

**Direct answer.** For LLMs without full-text search, single content-oriented index files (e.g., `index.md`) outperform free-form MOCs at scale. The canonical example is Karpathy's LLM wiki, where an `index.md` catalog plus a `log.md` is the recommended navigation layer. Hybrid patterns (top-level index + per-folder READMEs) appear in Neotoma and ClawVault, but per-folder indexes are mostly for humans; LLMs primarily use the top-level index.

**Evidence.**

- **Karpathy LLM wiki — index.md + log.md**: `index.md` is a content-oriented catalog of everything in the wiki — each page listed with a link, a one-line summary, and optionally metadata like date or source count. Organized by category. The LLM updates it on every ingest. When answering a query, the LLM reads the index first to find relevant pages, then drills into them. `log.md` is a chronological, append-only log with `## [YYYY-MM-DD] operation | title` entries.
- **llm-wiki AGENTS.md index format** — Defines a Wiki Index with sections for Overview, Sources, Entities, Projects, Concepts, Syntheses, each with counts and one-line summaries.
- **Neotoma markdown mirror layout** — Top-level `mirror/index.md` and per-type `index.md` files (e.g., `entities/index.md`, `entities/<entity_type>/index.md`).
- **ClawVault default categories** — Per-category implicit indices via directory listing; vault-level `.clawvault.json` and graph index.

**Confidence.** High that index-first navigation works for LLMs at hundreds of pages; medium for hybrid MOC+index at scale.

**Gaps.** No rigorous study comparing MOC depth / link density for LLM agents.

## Q3 — Naming Conventions for Predictable Retrieval

**Direct answer.** For LLM path prediction, kebab-case slugs derived from titles (ClawVault, llm-wiki) are the dominant 2025–2026 pattern — predictable, stable, human-readable. Date prefixes are used only for time-oriented documents (daily notes, session logs). Hash- or number-prefixed IDs are common inside vector DBs but rarely exposed as filenames because they are opaque to LLMs.

**Evidence.**

- **ClawVault file naming** — Filenames generated by slugifying titles: lowercase, remove non-word chars, replace spaces with hyphens, collapse consecutive hyphens. Example: "Use PostgreSQL for auth" → `use-postgresql-for-auth.md`. Document ID = relative path without extension.
- **llm-wiki naming conventions** — Source slugs: `kebab-case`; Entity/Concept pages: `TitleCase.md`; Synthesis pages: `kebab-case.md`.
- **Karpathy LLM wiki — raw layer** — Raw session transcripts use flat naming `YYYY-MM-DDTHH-MM-project-slug.md` (date-prefixed).
- **Obsidian community practice** — Strongly prefer YYYY-MM-DD date prefixes for daily notes and sortable filenames.
- **Stable filename + human-readable alias** — Obsidian supports aliases in frontmatter and resolves wikilinks by filename, not alias. Community pattern: stable kebab-case filenames + `alias:` in frontmatter for human-readable titles.

**Confidence.** High that kebab-case slugs are best for LLM path prediction; high that date prefixes are appropriate only for temporal documents; medium for alias-based "stable ID + display name" patterns.

**Gaps.** No formal study on LLM wrong-folder lookup rates. Alias-based linking depends on plugin behavior.

## Q4 — Linking Patterns and Graph Topology

**Direct answer.** LLM-oriented wikis favor moderately dense, semantically meaningful wikilinks with a `## Connections` section per page, and rely on forward links + explicit cross-references rather than backlinks for navigation. Block references for fine-grained provenance; page-level links remain primary because they are more stable and easier for LLMs to reason about. Nested tags (`#status/active/strategy`) are useful for filtering but can become noise if over-used.

**Evidence.**

- **Karpathy LLM wiki** — Ingest flow updates entity/concept pages and cross-links everything; lint checks for orphans, broken wikilinks, contradictions, stale pages.
- **llm-wiki cross-linking rule** — Hard rule: "Cross-link everything. Every page should have a `## Connections` section with at least one `[[wikilink]]`."
- **ClawVault graph index & edges** — Wiki-links in content become `wiki_link` edges; frontmatter relation fields (`related`, `depends_on`, `owner`, `project`, `people`, `links`) become `frontmatter_relation` edges.
- **Block-level provenance** — Google-Drive-to-Obsidian pipeline where every key statement ends with a vault link to the exact block in source PDF.
- **Backlink discussions** — Useful for discovery but can be noisy; some argue backlinks "often even harmful" if over-emphasized.
- **Nested tags** — Helpful for clearly hierarchical domains, noisy if hierarchy unclear.

**Confidence.** High that moderate, semantically structured wikilinks are beneficial; medium on backlink vs forward-link preferences.

**Gaps.** No quantitative measure of over-linking failure mode for LLMs.

## Q5 — Anti-Patterns

**Direct answer.** Main documented anti-patterns: (1) duplicate or contradictory documents describing the same fact differently, (2) status drift where multiple ACTIVE docs conflict, (3) hidden context in commit history or file metadata, (4) LLM-induced contamination where agents write back to docs and propagate errors. Explicitly targeted by lint workflows in llm-wiki and tools like KnowledgeBase Guardian and contextlint.

**Evidence.**

- **Karpathy llm-wiki — lint & contradictions** — Lint workflow checks for contradictions between pages, stale claims, orphans, broken links, missing concepts.
- **llm-wiki AGENTS.md hard rules** — "No silent overwrites. When ingest conflicts with existing wiki content, record both claims under `## Contradictions`."
- **KnowledgeBase Guardian** — LLM-powered tool that detects contradictions when adding new documents to a FAISS vector store; logs contradictions and refuses to extend the store when conflicts are found.
- **contextlint** — Rule-based linter for markdown that enforces cross-reference integrity, stability ordering (stable items don't depend on draft), cross-zone dependency declarations.
- **LLM write-back contamination** — ClawVault fixed wiki-link corruption where LLMs fused word fragments into wiki-links during compression, requiring a `sanitizeWikiLinks()` post-processor.

**Confidence.** High that duplicate docs, status drift, and hidden context are real failure modes; medium that LLM write-back is statistically common.

## Q6 — Token-Efficient Document Patterns

**Direct answer.** Token-efficient patterns for LLMs: (1) TL;DR / executive summaries at the top of documents, (2) structured frontmatter summaries (ClawVault's `memoryType`, `title`, `date`, `tags`), (3) skill-style documents (SKILL.md / CLAUDE.md) that keep instructions and examples short and well-structured. LLMs miss or mis-extract details as documents approach multiple thousands of tokens, especially when key info is buried in the middle. 1–2K tokens (~1–3 markdown pages) is a common practical ceiling for reliable extraction without chunking.

**Evidence.**

- **SKILL.md pattern** — Short, focused files with YAML frontmatter and body sections (Overview, When to Use, Instructions, Output Format, Examples, Notes).
- **Claude skill best practices** — Domain-specific organization, SKILL.md as overview, reference files for details; avoid deep nesting (keep references one level deep).
- **LLM-friendly documentation (Fern)** — Converting HTML docs to markdown reduces token consumption by >90%; clean hierarchies, predictable structure, direct answers at top (TL;DR).
- **Long-document extraction research** — Splitting necessary for long contexts; subjects often at the start of sections, later chunks lose context.

**Confidence.** High that TL;DR + structured frontmatter reduces tokens and improves extraction; medium on exact length ceilings.

## Recommended Frontmatter Schema & Naming Convention (Prompt A)

```yaml
# Required
title: string
type: string           # enum: source, entity, concept, decision, adr, spec, mirror, conversation
status: string         # enum: draft, active, superseded, archived
source_zone: string    # enum: repo, conversation, ris_mirror
last_updated: date
last_verified: date    # optional
confidence: float      # optional, 0–1
lifecycle: string      # enum: draft, reviewed, verified, stale, archived

# Cross-references
sources: list[string]
supersedes: string
superseded_by: string
references: list[string]
depends_on: list[string]

# Provenance
generator: string      # "llm-wiki-agent", "clawvault", "human", etc.
human_authored: bool
mirror_of: string      # for ris_mirror: Chroma ID or URL

# Staleness
as_of: date
valid_until: date      # optional
```

**Naming.**
- kebab-case slugs for content (`decision-chroma-vs-obsidian.md`, `concept-reinforcement-learning.md`)
- ISO date prefix for temporal documents (`2026-05-23-session-chroma-design.md`)
- Avoid numeric-only IDs / hash-prefixed names as primary filenames; store in frontmatter `id:` if needed
- Use `alias:` in frontmatter for human-friendly titles

---

# PROMPT B — Vector Database to Markdown Sync Architectures

## Q1 — Reference Architectures

**Direct answer.** Closest production-style references: **Neotoma's markdown mirror** (SQLite → deterministic filesystem view), **knoten** (remote backend → local markdown vault + SQLite index), and **doc2vec's MARKDOWN_STORE** (website docs → Postgres table + SQLite vector DB). These are one-way, read-only mirrors where the source DB is authoritative and the markdown is regenerable; they render relationships as wikilinks and rebuild deterministically.

**Key system details:**

- **Neotoma mirror** — SQLite source of truth; mirror at `<NEOTOMA_DATA_DIR>/mirror/` with subfolders `entities/`, `relationships/`, `timeline/`, `schemas/`, `sources/`. Regenerated on every DB write. Manual edits overwritten — only DB is authoritative.
- **knoten** — CLI zettelkasten with pluggable remote backend → local markdown vault (`kasten/`) + SQLite index. Local mirror never authoritative. `knoten sync` (incremental) or `--full`; delete detection always runs. `knoten verify` compares body hashes to detect drift.
- **doc2vec MARKDOWN_STORE** — Postgres `markdown_pages` table (url, product_name, markdown, updated_at). Per-source opt-in (`markdown_store: true`).
- **Notion → Hugo (Notion-Hugo)** — Cron sync (midnight by default); Notion properties → frontmatter; Notion content → Hugo markdown. Hugo repo overwritten on sync.

**Confidence.** High that Neotoma and knoten are good analogues for Chroma → Obsidian; medium for Notion/Airtable patterns.

**Gaps.** No widely documented Chroma → markdown mirror project; all analogies from other DBs.

## Q2 — Sync Trigger Patterns

**Direct answer.** Production systems typically use scheduled cron for large doc sets (Notion-Hugo midnight) and event-driven or hybrid for smaller/latency-sensitive datasets (Neotoma mirror on every DB write). Batch updates handled by idempotent upserts and delete detection. Re-syncing the same document is safe with deterministic writes and content-addressed or timestamp-based comparison.

## Q3 — Naming and Identity Stability

**Direct answer.** Systems generate stable filenames from canonical IDs and slugs: Neotoma uses entity slugs and relationship keys; knoten uses note IDs and export-style paths; ClawVault uses slugified titles with stable relative paths. On source rename/delete, mirror regenerates and either updates or removes corresponding file; wikilinks survive only if underlying ID/slug remains stable.

## Q4 — Relationship Rendering

**Direct answer.** Neotoma and ClawVault render foreign-key relationships as wikilinks between entity files (e.g., `[[people/pedro]]`), using frontmatter relation fields (`owner`, `project`, `depends_on`) to decide which links to emit. Bidirectional links typically not explicitly generated; backlinks derived by graph index or Obsidian's backlink feature.

## Q5 — Staleness and Freshness Indicators

**Direct answer.** Mirror systems communicate staleness via frontmatter timestamps (`last_updated`, `updated_at`, `last_verified`) and sync metadata (knoten sync cursor, Neotoma rebuild timestamps). Some support status commands comparing mirror state to source. Few detailed post-mortems on "human acted on stale mirror" exist.

## Q6 — Partial Mirror Policies

**Direct answer.** Partial mirroring via per-kind or per-path filters: Neotoma `--kinds entities,timeline`; knoten families and kinds; doc2vec per-source `markdown_store: true`. Decisions usually based on relevance and sensitivity, not formally documented.

## Q7 — Failure Modes

**Direct answer.** Documented failure modes: sync drift, partial syncs, broken links from deleted source docs, frontmatter schema drift between source and mirror. knoten and contextlint explicitly address via delete detection, hash verification, cross-reference checks. ClawVault wiki-link corruption (v2.0.2) is documented example.

## Recommended Reference Architecture (Prompt B)

```text
Chroma (source of truth)
  │
  │  (1) Change feed / polling
  │
  └─→ Sync Service (Python/Node)
        │
        │  (2) For each changed document:
        │      - Fetch full doc + metadata from Chroma
        │      - Render to markdown using Jinja-style templates
        │      - Compute stable filename: <zone>/<type>/<slug>.md
        │        (slug from Chroma ID or slug field)
        │      - Write frontmatter: chroma_id, source_zone=ris_mirror,
        │        type, status, last_synced, as_of, confidence, etc.
        │      - Render relationships as wikilinks:
        │        [[<zone>/<type>/<related_slug>]]
        │
        │  (3) Delete detection:
        │      - Track synced Chroma IDs in a manifest (JSON/SQLite)
        │      - On each sync, diff current IDs vs previous
        │      - Remove markdown files whose IDs are gone
        │
        │  (4) Idempotent & deterministic:
        │      - Same Chroma state → same vault state
        │      - Use content hashing or Chroma timestamps to skip unchanged docs
        │
        └─→ Obsidian Vault (read-only mirror)
              ├── ris-mirror/
              │    ├── entities/
              │    │    └── <slug>.md
              │    ├── concepts/
              │    │    └── <slug>.md
              │    └── relationships/
              │         └── <rel_type>.md
              └── manifest.json  (list of synced IDs, timestamps)
```

---

# PROMPT C — Multi-Source Markdown Vault Architectures

## Q1 — Zone Separation Patterns

**Direct answer.** Production vaults mixing auto-generated and human-written content typically use folder-based separation (`Source of Truth/`, `meetings/`, `archive/`, `Generated/`) plus frontmatter `source_zone` or `type` fields. ClawVault and llm-wiki also use per-category directories (`decisions/`, `patterns/`, `people/`) with strong conventions that auto-generated content goes into specific categories. Humans prevented from editing auto-generated files via conventions and sometimes gitignore / write-protect flags.

**Key references:**

- **Clearwater Analytics engineering KB** — `Knowledge/Source of Truth/`, `Knowledge/meetings/`, `Knowledge/TEAM/`, `Knowledge/archive/`, `Generated/`.
- **ClawVault categories** — `preferences/`, `decisions/`, `patterns/`, `people/`, `projects/`, `goals/`, `transcripts/`, `inbox/`, `templates/`.
- **llm-wiki layers** — `raw/` (immutable session transcripts) vs `wiki/` (LLM-generated pages).
- **Kepano (Obsidian lead)** — Recommends keeping personally created artifacts separate from agent-created artifacts to avoid contaminating primary vault.

## Q2 — Cross-Zone Linking

**Direct answer.** Cross-zone links should use stable IDs or slugs (not human-readable titles that may change) and point to mirror's canonical path (e.g., `[[ris-mirror/entities/chroma-doc-123]]`). When mirror documents regenerate with different filenames, links break unless ID-slug mapping is preserved. knoten and ClawVault keep document IDs stable; ClawVault rename operations require preserving family prefix.

## Q3 — Frontmatter Conventions for Source Attribution

**Direct answer.** No universal taxonomy, but emerging conventions use `source_zone` (or `zone`), `source`, `generator`, `human_authored`. ClawVault uses `memoryType` and category directories; llm-wiki uses `type` and `sources`; Clearwater KB uses `Source of Truth` tier.

## Q4 — Git Strategies for Mixed-Source Vaults

**Direct answer.** Auto-generated zones typically gitignored or treated as derived state (ClawVault's `.clawvault/graph-index.json`, knoten's cache dir). Human-written zones checked in. For partial-git vaults, version human-authored folders and regenerable folders, exclude caches/indexes. Merge conflicts avoided by never editing auto-generated files in git or by deterministic regeneration.

## Q5 — LLM Trust Models Across Zones

**Direct answer.** Clearest pattern: **tiered authority hierarchy** (Clearwater KB). Tier 1 Source of Truth overrides Tier 2; agents instructed to "never contradict Source of Truth documents" and follow authority hierarchy. LLMs prevented from treating stale mirrors as authoritative by combining frontmatter staleness fields (`last_verified`, `as_of`) with rules preferring newer or higher-tier documents.

## Q6 — Failure Modes

**Direct answer.** Multi-source vaults degrade via: zone contamination (human + agent artifacts mixing), link rot across regenerations, frontmatter schema drift between zones. ClawVault wiki-link corruption is an example of LLM-induced contamination that required a sanitizer fix.

## Recommended Three-Zone Pattern (Prompt C)

```text
vault/
├── repo-docs/          # Zone A – repo docs & specs
│   ├── README.md
│   ├── CLAUDE.md
│   └── specs/
├── claude-memory/      # Zone B – agent + human working memory
│   ├── 2026-05-23-chroma-design.md
│   └── 2026-05-24-obsidian-setup.md
└── ris-mirror/         # Zone C – RIS mirror (read-only)
     ├── entities/
     ├── concepts/
     └── relationships/
```

**Frontmatter source_zone taxonomy.**

```yaml
source_zone: enum [repo, claude_memory, ris_mirror]
generator: string       # "human", "claude-desktop", "ris-sync"
human_authored: bool
mirror_of: string       # for ris_mirror only: Chroma ID or URL
last_synced: datetime   # only for ris_mirror
```

**Git strategy.** `repo-docs/` and `claude-memory/` checked in. `ris-mirror/` gitignored or treated as derived state. `.obsidian/` and plugin configs versioned; caches and indexes gitignored.

---

# PROMPT D — Obsidian Plugin Stack for LLM-Consumed Engineering Documentation

## Q1 — Dataview vs Bases

**Direct answer.** As of 2025–2026, **Obsidian Bases (core plugin)** is the production choice for new engineering vaults that want UI-driven, database-like views without code. **Dataview** remains popular for advanced programmatic queries but is in "resting peacefully" maintenance mode. Bases faster and more integrated for large datasets; Dataview more expressive but less actively developed. Neither exposes a native external API — for external queries, use Local REST API or MCP servers.

- **Obsidian Bases** shipped in Obsidian 1.9 (2025-08-18).
- **Dataview** latest release 0.5.70 on 2025-04-07.
- "Obsidian Dataview Is Dead. Long Live Bases." Medium, 2026-01-02.

## Q2 — Templater and Structured Authoring

**Direct answer.** Templater (v2.20.4, 2026-05-12) is still the primary tool for structured note creation. Linter and MetaEdit focus on enforcing frontmatter schemas and YAML consistency at save time, but not at creation time. Templater + folder templates is the main way to enforce schemas when notes are created.

- Templater: v2.20.4, 2026-05-12
- Linter: 2025-11-24
- MetaEdit: 2024-07-28

## Q3 — MCP-Obsidian Integrations

**Direct answer.** Most capable MCP-Obsidian servers: **cyanheads/obsidian-mcp-server** and **coddingtonbear/obsidian-local-rest-api** (which includes an MCP server). Both support read/write/search/frontmatter. Local REST API MCP server more mature and widely used, with granular PATCH operations and clear docs for Claude Code, Cursor, and other MCP clients.

- cyanheads/obsidian-mcp-server: 14 tools (readers, writers, managers). Last commit 2026-05-23.
- coddingtonbear/obsidian-local-rest-api: v0.26.0 (2026-05-09). REST + MCP server. Surgical PATCH operations by heading/block/frontmatter field.
- StevenStavrakis/obsidian-mcp: simpler tool set. Last commit ~2025-12-30.

## Q4 — Local REST API Plugin Current State

**Direct answer.** v0.26.0 (2026-05-09). Full REST + MCP interface with endpoints for vault CRUD, search, periodic notes, command execution. Supports concurrent connections; used in production for AI agent access. Explicit rate limits and payload size limits not documented; works well for moderate-volume programmatic access.

MCP server runs at `https://127.0.0.1:27124/mcp/` with Bearer token auth.

## Q5 — Visualization Plugins

**Direct answer.** For LLM-consumed vaults: graph view configuration (filters, color rules) useful for debugging link structure. Canvas and Excalidraw helpful only for spatial diagrams or design artifacts. **Mermaid code blocks often sufficient for sequence/flow diagrams and more LLM-friendly than GUI plugins.**

## Q6 — Plugins That Are Actively Harmful

**Direct answer.** Plugins that auto-format or rewrite content (aggressive linters, smart-comma plugins) can break wikilinks or change semantics. Plugins that store content in custom formats or databases (encrypted note plugins, DB-backed plugins) hide text from filesystem and from LLMs. Auto-tagging or AI-writing plugins that silently modify content introduce inconsistencies.

## Q7 — Sonar / Semantic Search Plugins

**Direct answer.** **Sonar stores its index in IndexedDB on the client; no documented external API for Python or other processes to query it directly.** For external semantic search, options are (a) Local REST API with custom semantic search tool, or (b) separate vector DB (Chroma, Qdrant) indexed from markdown files. This confirms the two-layer architecture: Chroma stays the canonical RAG; Sonar (if installed) serves human-facing browse only.

## Recommended Minimum Plugin Set

1. **Obsidian Bases** (core) — replaces Dataview for most query needs
2. **Templater 2.20.4** — structured note creation with folder templates
3. **Local REST API 0.26.0** — REST + MCP server for LLM agent access
4. **Linter** (optional) — enforce frontmatter and formatting rules at save time
5. **MetaEdit** (optional) — manage YAML properties from UI
6. **Mermaid** (core) — diagrams; LLM-friendly

**Do NOT install:** Heavy auto-formatters that rewrite content. Encrypted or DB-backed note plugins that hide content from filesystem. AI-writing or auto-tagging plugins that modify content unpredictably.

---

# PROMPT E — Documentation Consolidation and Conflict Resolution Patterns

## Q1 — Consolidation Methodologies

**Direct answer.** Engineering orgs use **tiered knowledge bases** (Tier 1 Source of Truth, Tier 2 Core Knowledge) and **Architectural Decision Records (ADRs)**. ADRs capture decision and rationale; older docs archived or marked superseded. Clearwater KB explicitly uses tiers; AWS and ADR guides emphasize ADRs as canonical record for architectural decisions.

## Q2 — Conflict Detection

**Direct answer.** Tools for conflict detection: **contextlint** (cross-document linter) and **KnowledgeBase Guardian** (LLM-assisted contradiction detection for vector stores). LLM-assisted detection promising but has known failure modes: may miss subtle contradictions, over-flag stylistic differences, sensitive to prompt wording.

## Q3 — Archive vs Delete

**Direct answer.** Most teams archive superseded docs in `archive/` folder or mark with `status: superseded` rather than deleting. Preserves historical context and audit trails. Deletion reserved for clearly obsolete / low-value docs. Anecdotal warnings that deleting old docs can lose recoverable context.

## Q4 — Single Source of Truth Enforcement

**Direct answer.** After consolidation, SSoT enforced via CI checks (contextlint, markdownlint, yaml-lint), frontmatter schema validation (ClawVault templates, custom validators), and LLM-assisted review at write-time (KnowledgeBase Guardian, custom CLAUDE.md rules). Mechanisms catch drift and contradictions but typically warn rather than block.

## Recommended Consolidation Procedure

1. **Audit & classify** — contextlint + custom scripts identify duplicates and contradictions. Classify each doc as Tier 1 (Source of Truth), Tier 2 (supporting), or obsolete.
2. **Consolidate into Tier 1 docs** — For each topic, choose or create single Tier 1 doc; mark others `status: superseded` and move to `archive/`. Use ADRs for architectural decisions.
3. **Enforce schemas & authority** — Adopt template schemas for frontmatter. Add CI checks (contextlint, markdownlint, yaml-lint) for schemas and cross-reference integrity.
4. **LLM-assisted review** — KnowledgeBase Guardian or custom LLM step to review new/changed docs for contradictions before committing. CLAUDE.md/AGENTS.md rules: "Never contradict Tier 1 docs; always cite sources; mark confidence."
5. **Archive & monitor** — Archive superseded docs; monitor via periodic lints and knoten verify-style checks. Re-run consolidation when new contradictions detected.

---

# CROSS-CUTTING NOTES

- **Dates & recency.** Most cited sources 2025–2026; a few pre-2024 (Zettelkasten numeric IDs, Obsidian link behavior) flagged but still representative.
- **Anecdotal vs documented.** Forum/Reddit observations flagged as anecdotal; architectural patterns (Neotoma, ClawVault, llm-wiki, Clearwater KB) documented in repos or articles.
- **LLM-specific evidence.** Karpathy's LLM wiki, ClawVault, Clearwater KB are richest LLM-specific sources; other patterns inferred from DB→markdown and docs-as-code systems.

---

# Synthesis Decisions to Pull Forward

These are the decisions that informed the vault redesign spec. They are supported by multiple independent sources in the research above.

1. **Frontmatter schema is the API.** Adopt the recommended schema. Validate with contextlint or equivalent at CI time. Warn-not-block enforcement matches established pattern.
2. **Bases over Dataview.** New vault uses Bases. Don't install Dataview unless a specific query case demands it.
3. **Local REST API + cyanheads MCP server.** This is the programmatic surface for LLM agents.
4. **Three-zone folder layout with strict source_zone field.** repo-docs / claude-memory / ris-mirror.
5. **RIS mirror gitignored, regenerable, one-way sync.** Follow Neotoma + knoten pattern. Manifest tracks IDs for delete detection.
6. **Index.md + log.md at vault root.** Top-level LLM navigation surface. Per-folder READMEs are for humans.
7. **Sonar runs on mirror only.** Index lives in IndexedDB, never queried by pipelines. Pipelines query Chroma directly.
8. **Consolidation pattern: tier + ADR + archive.** Never delete. Mark superseded. Move to archive/.
9. **Templater enforces frontmatter at note creation.** Linter enforces at save.
10. **No auto-rewriting plugins.** No DB-backed plugins. No encrypted plugins. Filesystem must remain LLM-readable.

## Connections

- [[claude-memory/spec/vault-redesign-spec]]
- [[claude-memory/decisions/adr-0001-three-zone-vault-architecture]]
- [[index|Vault Home]]
