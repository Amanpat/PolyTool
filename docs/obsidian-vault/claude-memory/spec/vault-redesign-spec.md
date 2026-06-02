---
title: PolyTool Vault Redesign Specification
type: spec
status: active
source_zone: claude_memory
last_updated: 2026-05-23
last_verified: 2026-05-23
confidence: 0.9
lifecycle: reviewed
spec_version: 1
spec_status: implemented
human_authored: false
generator: claude-desktop
aliases:
  - Vault Redesign Spec
  - Vault Design v1
tags:
  - spec
  - vault-design
  - tier-1
  - source-of-truth
sources:
  - "[[claude-memory/research/2026-05-23-research-llm-obsidian-vault-design]]"
references:
  - "2026-05-23-session-research-captured-vault-redesign (C-004: file not yet
    exported from Claude Desktop)"
related:
  - "claude-memory/decisions/2026-05-23-chroma-vs-obsidian-rag (missing:
    decision doc not yet created)"
depends_on: []
---

# PolyTool Vault Redesign Specification

> [!info] What this is
> Tier 1 design specification for the new PolyTool Obsidian vault. This document is the contract that Claude Code execution will be measured against. It is itself an example of the schema and conventions it defines.

## TL;DR

Build a three-zone Obsidian vault optimized primarily for LLM consumption, secondarily for human navigation. The centerpiece is **Zone C (`ris-mirror/`)**, a read-only mirror of the Chroma-backed RIS system that gives humans and LLMs at-a-glance visibility into the canonical research state. Two supporting zones — **Zone A (`repo-docs/`)** for repo documentation and **Zone B (`claude-memory/`)** for agent working memory — round out the vault. Every document carries strict YAML frontmatter that serves as the machine-readable API for filtering, weighting, and trust calibration.

Ten anchoring decisions:

1. Three-zone folder separation with `source_zone` frontmatter enum
2. Strict frontmatter schema with required + optional fields
3. kebab-case slugs for content; ISO date prefix for temporal docs
4. `index.md` + `log.md` at vault root as primary LLM navigation surface
5. RIS mirror gitignored, regenerable from Chroma, one-way sync via manifest
6. Plugin stack: Bases, Templater, Local REST API, Linter, MetaEdit, Mermaid
7. Tier hierarchy enforced in CLAUDE.md and AGENTS.md rules
8. Consolidation pattern: tier + ADR + archive, never delete
9. Frontmatter is authoritative over body text
10. Never silently overwrite — record contradictions explicitly

## Goals & Non-Goals

### Goals

- **Primary:** Give LLMs (Claude Desktop, Claude Code, Codex) a predictable, contradiction-free vault to ground on.
- **Primary:** Provide at-a-glance visibility into the RIS system's actual state via the Zone C mirror.
- **Secondary:** Give humans a navigable, graph-explorable view of the same content.
- **Tertiary:** Establish a foundation that supports future vault-level autoresearch (lint, synthesis, contradiction promotion).

### Non-Goals

- This redesign does not change how RIS operates internally. Chroma stays the canonical store; write-gates and partitions stay enforced in code.
- This is not a universal vault — it is project-scoped to PolyTool.
- This is not a replacement for the eventual Studio Knowledge tab (Phase 7). It supersedes the need for it, but Studio integration is separate work.
- We are not building the RIS mirror sync service in this redesign. The vault gets the structure and policies; the sync service is a separate work packet.

## Three-Zone Architecture

### Zone Overview

| Zone | Folder | Purpose | Writable By | Read-Only To |
|------|--------|---------|-------------|--------------|
| A | `repo-docs/` | Mirror of PolyTool repo docs | Repo sync process | Humans, agents |
| B | `claude-memory/` | Agent + human working memory | Humans, Claude Desktop, Claude Code | (No one — fully writable) |
| C | `ris-mirror/` | Mirror of Chroma RIS state | RIS sync service only | Humans, agents, all other writers |

### Zone A — `repo-docs/`

Synced from the PolyTool code repository. Contains canonical project documentation: `CLAUDE.md`, `CURRENT_STATE.md`, `ARCHITECTURE.md`, `PLAN_OF_RECORD.md`, all `SPEC-*.md` files, ADRs.

**Sync direction:** Repo → Vault. Edits happen in the repo and propagate via sync. Editing files in `repo-docs/` is forbidden — they will be overwritten.

**Trigger:** Manual `vault-sync repo` command initially; eventually post-commit hook on the repo.

**Frontmatter:** Synced docs gain `source_zone: repo`, `generator: repo-sync`, `mirror_of: <repo-path>`, `last_synced: <iso-datetime>`. Original repo doc content is preserved verbatim in the body.

### Zone B — `claude-memory/`

Where Claude Desktop sessions accumulate. Contains decisions, session notes, prompts (archived), research results, work packets, ideas, and the eventual archive of superseded documents.

**Write discipline:** Humans and agents write freely. Every new document must carry full frontmatter.

**Trigger:** Manual writes from sessions. No automated sync.

**The "memory" framing:** This zone is not a brain — it is persistent context for agents that have no persistent memory of their own. The next agent session reads from here to recover context the previous session built.

### Zone C — `ris-mirror/`

Auto-generated from the Chroma RIS. Read-only mirror that gives humans and LLMs visibility into the canonical research state without querying Chroma directly.

**Sync direction:** Chroma → Vault. One-way, never reversed.

**Trigger:** Hybrid — post-write hook for high-importance partitions (`research`), nightly cron for high-volume partitions (`external_knowledge`, `user_data`).

**Gitignored:** Yes. The mirror is regenerable from Chroma; committing it would bloat the repo and create merge conflicts.

**Editing:** Forbidden. The next sync overwrites manual changes. Any human annotation should go to `claude-memory/` and link back to the mirror document.

## Vault Root Layout

```
PolyTool-Vault/
├── .obsidian/                    # plugin configs (versioned, except caches)
├── .gitignore
├── README.md                     # human-facing vault overview
├── CLAUDE.md                     # rules for Claude (vault-level)
├── AGENTS.md                     # rules for any LLM agent
├── index.md                      # primary LLM navigation surface
├── log.md                        # append-only chronological log
│
├── repo-docs/                    # Zone A
│   ├── README.md
│   ├── _index.md
│   ├── overview.md
│   ├── current-state.md
│   ├── claude-md-repo.md
│   ├── architecture.md
│   ├── plan-of-record.md
│   ├── specs/
│   │   ├── _index.md
│   │   ├── spec-0010-simtrader.md
│   │   └── spec-0011-execution-layer.md
│   ├── adrs/
│   │   ├── _index.md
│   │   └── (sequential ADRs from repo)
│   └── reference/
│       ├── _index.md
│       └── (reference materials)
│
├── claude-memory/                # Zone B
│   ├── README.md
│   ├── _index.md
│   ├── decisions/
│   │   ├── _index.md
│   │   └── (active strategy/architecture decisions)
│   ├── session-notes/
│   │   ├── _index.md
│   │   └── (per-session captures)
│   ├── prompts/
│   │   ├── _index.md
│   │   └── (archived research/work prompts)
│   ├── research/
│   │   ├── _index.md
│   │   └── (research results)
│   ├── spec/
│   │   ├── _index.md
│   │   └── (design specifications — this doc lives here)
│   ├── work-packets/
│   │   ├── _index.md
│   │   └── (implementation work packets for Claude Code/Codex)
│   ├── ideas/
│   │   ├── _index.md
│   │   └── (exploratory ideas, may graduate to decisions)
│   └── archive/
│       ├── _index.md
│       └── (superseded docs from this zone)
│
└── ris-mirror/                   # Zone C (gitignored)
    ├── README.md
    ├── _index.md
    ├── manifest.json             # synced Chroma IDs + timestamps
    ├── user_data/
    │   ├── _index.md
    │   └── (mirrors of user_data partition)
    ├── external_knowledge/
    │   ├── _index.md
    │   └── (mirrors of external_knowledge partition)
    ├── research/
    │   ├── _index.md
    │   └── (mirrors of research partition)
    └── signals/
        ├── _index.md
        └── (mirrors of signals partition)
```

## Frontmatter Schema

Frontmatter is the machine-readable API. Frontmatter is authoritative over body text. When they contradict, frontmatter wins.

### Universal Required Fields

Every document in the vault must carry these:

```yaml
title: string                  # human-readable title
type: string                   # enum (see below)
status: string                 # enum: draft | active | superseded | archived
source_zone: string            # enum: repo | claude_memory | ris_mirror
last_updated: date             # ISO YYYY-MM-DD of last content change
lifecycle: string              # enum: draft | reviewed | verified | stale | archived
```

### `type` Enum

| Type | Tier | Purpose |
|------|------|---------|
| `spec` | 1 | Design specifications (this doc) |
| `adr` | 1 | Architectural decision records |
| `decision` | 1 | Active strategy or design decisions |
| `index` | — | Index files (`_index.md`) |
| `log` | — | Log files (`log.md`) |
| `research` | 2 | Research findings (e.g., GLM results) |
| `concept` | 2 | Concept explanations |
| `entity` | 2 | Domain entities (e.g., Polymarket, Chroma) |
| `mirror` | 2 | RIS mirror documents |
| `session_note` | 3 | Per-session captures |
| `work_packet` | 3 | Implementation work packets |
| `prompt` | 3 | Archived prompts |
| `conversation` | 3 | Conversation summaries |
| `idea` | 3 | Exploratory ideas |
| `reference` | 3 | Reference materials |

### Type-Specific Required Fields

**`adr` documents add:**
```yaml
adr_number: int                # sequential, vault-wide
decision: string               # one-line summary
context: string                # required body section
consequences: string           # required body section
alternatives_considered: list[string]  # required body section
```

**`decision` documents add:**
```yaml
decided_at: date               # ISO YYYY-MM-DD
decided_by: list[string]       # who decided
```

**`mirror` documents add:**
```yaml
mirror_of: string              # Chroma document ID
last_synced: datetime          # ISO 8601 with timezone
chroma_partition: string       # enum: user_data | external_knowledge | research | signals
chroma_metadata: object        # passthrough of Chroma metadata fields
```

**`session_note` documents add:**
```yaml
session_date: date             # ISO YYYY-MM-DD
participants: list[string]     # e.g., [user, claude-desktop]
```

**`spec` documents add:**
```yaml
spec_version: string           # semver
spec_status: string            # enum: draft | accepted | implemented | deprecated
```

**`work_packet` documents add:**
```yaml
target_agent: string           # enum: claude-code | codex | gemini-cli | manual
acceptance_criteria: list[string]
```

### Universal Optional Fields

```yaml
last_verified: date            # ISO YYYY-MM-DD
confidence: float              # 0.0 - 1.0
as_of: date                    # date this description was true
valid_until: date              # known expiry
generator: string              # who/what created: human | claude-desktop | claude-code | codex | ris-sync | repo-sync
human_authored: bool           # true for human-written
aliases: list[string]          # human-readable display names
tags: list[string]             # kebab-case tags for filtering
```

### Cross-Reference Fields (all optional)

All cross-references use Obsidian wikilink-compatible IDs (file paths relative to vault root, or simple filenames if unambiguous):

```yaml
sources: list[string]          # for derived/research docs: source doc IDs
supersedes: string             # ID of doc this replaces
superseded_by: string          # ID of doc that replaces this
references: list[string]       # other docs this references
depends_on: list[string]       # docs this depends on
related: list[string]          # weakly related docs
```

### Validation

- Templater (folder templates) generates skeleton frontmatter at note creation.
- Linter (Obsidian plugin) checks YAML validity, required fields, enum values at save time. Warns, does not block.
- CI check (post-commit, via contextlint or custom script): validates all frontmatter against schema, fails build on violations.

## Naming Conventions

### Content Documents
- **kebab-case slugs** derived from titles
- Examples: `decision-vault-redesign.md`, `concept-favorite-longshot-bias.md`, `entity-polymarket.md`
- No spaces. No CamelCase except for explicit Entity pages (optional — kebab-case acceptable for entities too).

### Temporal Documents
- **ISO date prefix** for session notes, daily logs, captures
- Format: `YYYY-MM-DD-<slug>.md`
- Examples: `2026-05-23-session-research-captured.md`, `2026-05-23-research-llm-obsidian-vault-design.md`

### ADRs
- **Sequential numbered** with zero-padding to 4 digits
- Format: `adr-NNNN-<slug>.md`
- Examples: `adr-0001-database-split.md`, `adr-0042-chroma-vs-obsidian-rag.md`
- ADR numbers are vault-wide, never reused, never re-sequenced.

### Index Files
- `_index.md` for per-folder indexes (underscore prefix sorts to top in most file explorers)
- `index.md` for vault root index (no underscore — it's the canonical entry point)
- `log.md` for vault root log

### RIS Mirror Documents
- Filename = Chroma document ID, slugified
- Format: `<chroma-id-slug>.md`
- Stable across re-syncs because Chroma IDs don't change

## Linking Patterns

### Wikilinks

- Use full-path links for cross-zone clarity: `[[claude-memory/decisions/decision-vault-redesign]]`
- Within the same folder, short links acceptable: `[[decision-vault-redesign]]`
- Aliases for display: defined in frontmatter `aliases:` field, displayed in Obsidian as the rendered link text

### Connections Section

Every document should have a `## Connections` section near the end with at least one wikilink. This makes the relationship graph explicit and gives LLMs an obvious place to look for related content.

```markdown
## Connections

- [[claude-memory/research/2026-05-23-research-llm-obsidian-vault-design]] — source research
- [[claude-memory/decisions/2026-05-23-chroma-vs-obsidian-rag]] — related architectural decision
- [[CLAUDE|Operating Rules]] — operating rules referenced in this spec
```

### Backlinks

Backlinks are derived by Obsidian, not stored in document body or frontmatter. Forward links + the `## Connections` section provide explicit relationships; backlinks provide discoverability.

### Cross-Zone Linking

Always permitted and encouraged. Cross-zone links use full paths and survive zone-level changes as long as filenames remain stable.

### Vault-Root Short-Name Exception

Short-name links to vault-root files are acceptable from **any zone** without the full-path requirement:

| File | Acceptable short link |
|------|-----------------------|
| `index.md` | `[[index]]` |
| `log.md` | `[[log]]` |
| `CLAUDE.md` | `[[CLAUDE]]` |
| `AGENTS.md` | `[[AGENTS]]` |
| `README.md` | `[[README]]` |

These files live at the vault root, have no zone prefix, and are stable navigation anchors. The full-path rule applies to subfolder files in `claude-memory/`, `repo-docs/`, and `ris-mirror/` only.

## RIS Mirror Sync Architecture

> [!note] Scope
> This section specifies the **target architecture** for the mirror. Building the sync service is a separate work packet, not part of this vault redesign. This redesign establishes the folder structure, manifest format, and frontmatter conventions the eventual sync service will populate.

### Architecture

```
Chroma (canonical RIS state)
  │
  │  (1) Change feed: post-write hook for `research` partition,
  │      nightly cron for `external_knowledge`, `user_data`
  │
  └─→ RIS Sync Service (Python)
        │
        │  (2) For each changed Chroma document:
        │      a. Fetch full document + metadata
        │      b. Render to markdown via Jinja template
        │      c. Compute stable filename: <chroma_id_slug>.md
        │      d. Write frontmatter:
        │         - title (from Chroma title or first heading)
        │         - type: mirror
        │         - status: active
        │         - source_zone: ris_mirror
        │         - mirror_of: <chroma_id>
        │         - last_synced: <iso-datetime>
        │         - chroma_partition: <partition>
        │         - chroma_metadata: { full passthrough }
        │         - confidence: <chroma confidence>
        │         - last_updated: <chroma last_updated>
        │      e. Render relationships as wikilinks:
        │         [[ris-mirror/<partition>/<related_chroma_id_slug>]]
        │      f. Write file to ris-mirror/<partition>/
        │      g. Update manifest.json with chroma_id + timestamp + hash
        │
        │  (3) Delete detection:
        │      - Diff current Chroma IDs vs manifest.json
        │      - Remove markdown files whose Chroma IDs are gone
        │      - Update manifest.json
        │
        │  (4) Idempotent + deterministic:
        │      - Same Chroma state → same vault state
        │      - Content hash comparison: skip unchanged docs
        │
        └─→ ris-mirror/ (read-only mirror)
              ├── manifest.json
              ├── user_data/
              ├── external_knowledge/
              ├── research/
              └── signals/
```

### Manifest Format

`ris-mirror/manifest.json`:

```json
{
  "schema_version": "1.0",
  "last_sync": "2026-05-23T14:30:00Z",
  "documents": {
    "<chroma_id>": {
      "partition": "research",
      "filename": "validated-strategy-ms-v1-3.md",
      "last_synced": "2026-05-23T14:30:00Z",
      "content_hash": "sha256:...",
      "chroma_last_updated": "2026-05-23T14:25:00Z"
    },
    ...
  }
}
```

### Failure Modes & Recovery

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Sync drift (mirror diverged from source) | Periodic `vault-sync verify` checks content hashes | Re-render affected documents |
| Partial sync (interrupted mid-run) | Manifest has timestamp older than expected | Re-run sync; idempotent so safe |
| Broken wikilink (target deleted) | Obsidian shows broken link; periodic lint catches | Sync auto-removes deleted docs on next run |
| Frontmatter schema drift | Linter / CI check fails | Update sync renderer template |
| Manual edit overwritten | Expected behavior, documented | Edits must go to `claude-memory/` with link to mirror |

### Partition Mirroring Policy

- `research` partition: **mirror in full**, post-write hook trigger. High value, low volume.
- `external_knowledge` partition: **mirror in full**, nightly trigger. Medium volume.
- `user_data` partition: **mirror only documents with `confidence >= 0.5`**, nightly trigger. High volume, much is noise.
- `signals` partition: **mirror only documents promoted to RAG** (the `≥10 events, >3% move` threshold from roadmap). Don't mirror raw signal noise.

These policies are tunable per partition in the sync service config.

## Plugin Stack

### Install

| Plugin | Version | Source | Purpose |
|--------|---------|--------|---------|
| Obsidian Bases | Core (1.9+) | Obsidian | Database-like views over frontmatter |
| Templater | 2.20.4 | Community | Structured note creation, folder templates |
| Local REST API | 0.26.0 | Community | REST + MCP server for LLM agent access |
| Linter | latest (≥2.0) | Community | Frontmatter and YAML validation on save |
| MetaEdit | latest | Community | UI for editing YAML properties |
| Mermaid | Core | Obsidian | Diagrams (LLM-friendly) |

### Do Not Install

- **Smart Connections** (paywalled, opaque indexing)
- **Sonar** unless specifically wanted for human semantic browse on the mirror; do NOT use for any pipeline queries
- **Dataview** — superseded by Bases; install only if a specific query case demands it
- Any auto-formatting plugin that rewrites content on save without explicit configuration
- Any encrypted-storage or DB-backed plugin that hides content from the filesystem
- AI-writing or auto-tagging plugins that silently modify content

### Plugin Configuration

- Bases: configure base views per zone (one base per `_index.md` showing all docs in that folder)
- Templater: configure folder templates for each `claude-memory/` subfolder so frontmatter is auto-populated
- Local REST API: bind to `127.0.0.1:27124`, Bearer token auth
- Linter: enable YAML frontmatter rules, disable any rule that rewrites wikilinks

## Vault-Level Operating Rules (CLAUDE.md content)

These rules go in the vault's root `CLAUDE.md` and `AGENTS.md`. The two files are largely identical — `AGENTS.md` exists so non-Claude agents (Codex, etc.) read it without needing Claude-specific framing.

### The Five Hard Rules

1. **Frontmatter is authoritative.** When frontmatter and body contradict, frontmatter wins. Filter and weight content by `status`, `lifecycle`, `confidence`, and `last_updated`.

2. **Respect the tier hierarchy.** Tier 1 documents (`spec`, `adr`, `decision`) override Tier 2 and Tier 3. Never silently contradict a Tier 1 document.

3. **Respect zone discipline.** Never write to `ris-mirror/` (auto-overwritten). Never write to `repo-docs/` (edit the repo instead). New content defaults to `claude-memory/`.

4. **No silent overwrites.** When new information conflicts with existing content, do not overwrite. Either add `## Contradictions` to the new doc, or create an ADR. Mark old doc `superseded_by: <new-doc-id>` and new doc `supersedes: <old-doc-id>`.

5. **No deletion.** Archive instead. Set `status: archived`, move to `archive/`, leave the file in place.

### Operating Sequence

When reading the vault:

1. Read `index.md` to find relevant pages.
2. Read recent entries in `log.md` to understand recency.
3. Read the relevant Tier 1 document.
4. Follow forward links from there.
5. Use frontmatter to filter: skip `status: superseded` and `status: archived` unless explicitly looking for historical context.

When writing to the vault:

1. Check if a document on this topic already exists (search by `type` + `tags` + title).
2. If yes: update existing, or create new with `supersedes:` pointer.
3. If no: create new with full required frontmatter.
4. Append entry to `log.md`: `## [YYYY-MM-DD] <operation> | <title>` followed by 1-2 sentences and a wikilink.
5. Update `index.md` if the new doc is Tier 1 or Tier 2.

## Migration Playbook

Migration runs in six phases. Each has clear acceptance criteria.

### Phase 1 — Scaffold the New Structure

Create the empty vault skeleton. No content migration yet.

**Tasks:**
- Create all folders per the layout above
- Create skeleton `index.md`, `log.md`, `README.md`, `CLAUDE.md`, `AGENTS.md` at vault root
- Create `_index.md` in every folder with frontmatter and TODO content
- Create `.gitignore`
- Install plugin stack
- Configure Templater folder templates

**Acceptance:** Vault opens in Obsidian. All folders exist. All `_index.md` files validate against schema. Plugin stack installed.

### Phase 2 — Migrate Repo Docs to Zone A

Initial population of `repo-docs/` from the PolyTool repo.

**Tasks:**
- Copy `CLAUDE.md`, `CURRENT_STATE.md`, `ARCHITECTURE.md`, `PLAN_OF_RECORD.md` from repo to `repo-docs/`
- Copy all `SPEC-*.md` files to `repo-docs/specs/`
- Copy all ADRs (if any exist in repo) to `repo-docs/adrs/`
- Add `source_zone: repo`, `generator: repo-sync`, `mirror_of: <repo-path>`, `last_synced: <iso-datetime>` frontmatter to each
- Update `repo-docs/_index.md` with full document listing
- Update root `index.md` with Tier 1 entries from this zone

**Acceptance:** All repo docs present in `repo-docs/`. Frontmatter valid. `_index.md` lists them all.

### Phase 3 — Audit Current Vault (`Claude Desktop/` Zone B + Zone A)

Classify every document in the current vault for migration.

**Tasks:**
- List all documents in the current `Claude Desktop/` zone (folders 08–12)
- For each: classify as Tier 1 (keep, migrate), Tier 2 (keep, migrate), or obsolete (archive)
- Identify duplicates and contradictions
- Output: `claude-memory/research/2026-XX-XX-vault-audit.md` with the full classification

**Acceptance:** Audit document exists. Every current document has a classification. Duplicates and contradictions enumerated.

### Phase 4 — Migrate Tier 1 and Tier 2 Documents to Zone B

Move the keepers into the new structure with updated frontmatter.

**Tasks:**
- For each Tier 1 / Tier 2 doc: rewrite with full frontmatter per the schema
- Place in the correct `claude-memory/` subfolder by type
- For contradictory pairs: resolve via ADR, mark old with `superseded_by:`
- For duplicates: merge into a single doc, mark others with `supersedes` chain
- Update wikilinks to point to new locations

**Acceptance:** All Tier 1 / Tier 2 docs present in `claude-memory/`. Frontmatter valid. No broken wikilinks. Contradictions resolved via ADRs.

### Phase 5 — Archive Superseded Documents

Move obsolete and superseded docs to archive, do not delete.

**Tasks:**
- For each obsolete doc: set `status: archived`, move to `claude-memory/archive/`
- For each superseded doc: same, with `superseded_by:` field populated
- Preserve folder structure within `archive/` (e.g., archived ADRs stay in `archive/adrs/`)

**Acceptance:** No files deleted. All archived. `archive/_index.md` lists them with reason for archive.

### Phase 6 — Validation

Verify the migration was complete and correct.

**Tasks:**
- Run frontmatter validation across all docs
- Run wikilink integrity check (no broken links)
- Run contradiction detection (no two active docs disagreeing on the same fact)
- Verify `index.md` and `log.md` are up to date
- Confirm `ris-mirror/` is empty but structured (sync service builds later)
- Confirm `.gitignore` excludes `ris-mirror/`

**Acceptance:** All validation checks pass. Vault is internally consistent. Codex audit confirms structure matches this spec.

## Initial File Skeletons

These are the skeleton files Claude Code should create during Phase 1. Each is provided in full.

### Root `index.md`

```markdown
---
title: PolyTool Vault Index
type: index
status: active
source_zone: claude_memory
last_updated: 2026-05-23
lifecycle: active
aliases: [Home, Vault Home]
---

# PolyTool Vault Index

> [!info] Navigation
> This is the primary navigation surface for the vault. Read this first when looking for content.

## Tier 1 — Source of Truth

### Specifications
- [[claude-memory/spec/vault-redesign-spec]] — Vault structure and design (THIS IS THE GROUNDING DOC)

### Architectural Decision Records
- (none yet)

### Active Decisions
- (populated during migration)

## Zones

- [[repo-docs/_index]] — Zone A: Repo documentation
- [[claude-memory/_index]] — Zone B: Claude memory and working state
- [[ris-mirror/_index]] — Zone C: RIS mirror (auto-generated)

## Operating Rules

- [[CLAUDE|Operating Rules]] — Operating rules (Claude)
- [[AGENTS|Agent Rules]] — Operating rules (any agent)

## Recent Activity

See [[log|Vault Log]] for chronological log.

## Connections

- [[CLAUDE|Operating Rules]]
- [[AGENTS|Agent Rules]]
- [[log|Vault Log]]
```

### Root `log.md`

```markdown
---
title: Vault Log
type: log
status: active
source_zone: claude_memory
last_updated: 2026-05-23
lifecycle: active
---

# Vault Log

> [!info] Format
> Append-only chronological log. Newest entries at top.
> Format: `## [YYYY-MM-DD] <operation> | <title>` + 1-2 sentences + wikilink.

## [2026-05-23] create | Vault redesign specification
Initial spec for three-zone vault structure with frontmatter schema, RIS mirror sync architecture, and migration playbook. Tier 1 document.
Doc: [[claude-memory/spec/vault-redesign-spec]]

## Connections

- [[index|Vault Home]]
```

### Root `CLAUDE.md`

(Content per "Vault-Level Operating Rules" section above, formatted as a standalone document with frontmatter.)

### Root `AGENTS.md`

Same content as `CLAUDE.md` but framed for any LLM agent, not specifically Claude. Identical operating rules.

### Root `README.md`

```markdown
---
title: PolyTool Vault README
type: reference
status: active
source_zone: claude_memory
last_updated: 2026-05-23
lifecycle: active
---

# PolyTool Vault

This is the PolyTool project knowledge vault. Primary consumers: LLM agents (Claude, Claude Code, Codex). Secondary: humans.

## Quick Orientation

- **Looking for project state?** → [[repo-docs/current-state]]
- **Looking for the RIS data?** → [[ris-mirror/_index]]
- **Looking for a past decision?** → [[index|Vault Home]] under "Active Decisions"
- **Want to know the rules?** → [[CLAUDE|Operating Rules]] or [[AGENTS|Agent Rules]]
- **Want the spec for this vault?** → [[claude-memory/spec/vault-redesign-spec]]

## Three Zones

- `repo-docs/` — Mirror of PolyTool code repo documentation
- `claude-memory/` — Claude Desktop sessions, decisions, research, work
- `ris-mirror/` — Auto-generated mirror of Chroma RIS state (gitignored)

## Operating Principles

1. Frontmatter is authoritative.
2. Tier hierarchy: spec/adr/decision > research/concept > session_note/prompt.
3. Never silently overwrite. Record contradictions.
4. Never delete. Archive.

See [[CLAUDE|Operating Rules]] for full rules.

## Connections

- [[index|Vault Home]]
- [[CLAUDE|Operating Rules]]
- [[claude-memory/spec/vault-redesign-spec]]
```

### Root `.gitignore`

```
# Mirror is regenerable - never commit
ris-mirror/

# Obsidian per-machine caches (keep plugin configs and core settings)
.obsidian/workspace.json
.obsidian/workspace-mobile.json
.obsidian/cache/

# OS / editor
.DS_Store
Thumbs.db
*.swp
*.swo
```

## Acceptance Criteria for Claude Code Execution

When Claude Code completes the redesign, the following must all be true:

### Structural
- [ ] All folders exist per layout above
- [ ] All root files exist: `index.md`, `log.md`, `README.md`, `CLAUDE.md`, `AGENTS.md`, `.gitignore`
- [ ] All `_index.md` files exist in each folder
- [ ] Plugin stack installed (Bases, Templater, Local REST API, Linter, MetaEdit, Mermaid)
- [ ] Templater folder templates configured for each `claude-memory/` subfolder

### Content
- [ ] All Tier 1 and Tier 2 docs from the current vault migrated to `claude-memory/`
- [ ] All repo docs synced into `repo-docs/`
- [ ] All obsolete / superseded docs in `archive/` (not deleted)
- [ ] `ris-mirror/` is empty but structured (subfolders + `_index.md` exist)

### Schema Compliance
- [ ] Every document has valid frontmatter per schema
- [ ] Every document has required fields for its type
- [ ] All enums use allowed values only
- [ ] No two active documents contradict each other on the same fact

### Linking
- [ ] No broken wikilinks
- [ ] Every Tier 1 / Tier 2 doc has a `## Connections` section
- [ ] `index.md` lists all Tier 1 docs
- [ ] `log.md` has at least one entry per migration phase

### Verification
- [ ] Codex audit pass (separate work packet)
- [ ] `vault-validate` script runs cleanly
- [ ] Manual spot-check on 5 random documents confirms schema compliance

## Connections

- [[claude-memory/research/2026-05-23-research-llm-obsidian-vault-design]] — source research packet
- <!-- OPERATOR: C-004 open — session note not yet exported from Claude Desktop --> session note that captured the research
- [[CLAUDE|Operating Rules]] — operating rules this spec defines
- [[AGENTS|Agent Rules]] — same rules, framed for non-Claude agents
- [[index|Vault Home]] — vault index, references this as the primary spec

## Changelog

- **2026-05-23** — v1.0 draft. Initial specification synthesized from GLM research packet. Status: draft, awaiting acceptance and Claude Code execution.
