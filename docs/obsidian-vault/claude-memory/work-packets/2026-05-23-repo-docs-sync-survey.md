---
title: Repo-Docs Sync Survey 2026-05-23
type: work_packet
status: active
source_zone: claude_memory
last_updated: 2026-05-25
lifecycle: reviewed
target_agent: claude-code
acceptance_criteria:
  - All 787 NEW files created in repo-docs/ with correct vault frontmatter
  - All 64 DIVERGED files updated (source body replaces mirror body, vault fields preserved)
  - 1 ORPHANED file flagged with orphaned=true and warning callout
  - validate-vault-frontmatter.py passes with ≥ 220 files and 0 INVALID_ENUM/MISSING_REQUIRED errors in Zone A
  - fix-wikilinks.py --dry-run reports 0 unresolved and 0 ambiguous
---

# Repo-Docs Sync Survey 2026-05-23

**Generated:** 2026-05-25  
**Script:** `docs/scripts/sync-repo-docs.py` (dry-run)  
**Source root:** `docs/` (read-only)  
**Mirror target:** `docs/obsidian-vault/repo-docs/` (write target)

---

## Summary Counts

| Category | Count | Notes |
|----------|-------|-------|
| NEW | 787 | Files in docs/ not yet mirrored |
| DIVERGED | 64 | Mirror bodies differ from source (previous sync appended `## Connections` sections) |
| ORPHANED | 1 | Mirror file whose source was removed or relocated |
| UNCHANGED | 0 | No files were already in sync |
| **TOTAL** | **852** | Files processed |

---

## Root Cause: DIVERGED

All 64 existing mirror files show as DIVERGED because the previous sync script appended a `## Connections` section to every mirror body:

```
## Connections

- [[repo-docs/_index|Repo Docs Index]]
- [[index|Vault Home]]
```

This section does not exist in the source files. The new sync removes these appended sections by replacing mirror bodies with current source content. All vault-added frontmatter fields (source_zone, mirror_of, last_synced, lifecycle, generator) are preserved.

---

## NEW Files by Subfolder

| Subfolder | Count | Source |
|-----------|-------|--------|
| root | 11 | `docs/` root .md files not previously mirrored |
| specs/ | 3 | `docs/specs/` new since last sync |
| adrs/ | 1 | `docs/adr/` new since last sync (adr-0012) |
| features/ | 99 | `docs/features/` — entire directory new |
| dev_logs/ | 637 | `docs/dev_logs/` — entire directory new |
| runbooks/ | 25 | `docs/runbooks/` — entire directory new |
| reference/ | 5 | `docs/reference/` — entire directory new |
| external_knowledge/ | 7 | `docs/external_knowledge/` — entire directory new |
| **Total** | **787** | |

### New root-level files (11)
Files in `docs/` not previously mirrored to `repo-docs/root/`:
- CURRENT_DEVELOPMENT.md → current-development.md
- DOCS_BEST_PRACTICES.md → docs-best-practices.md
- INDEX.md → index.md
- KNOWLEDGE_BASE_CONVENTIONS.md → knowledge-base-conventions.md
- PROJECT_CONTEXT_PUBLIC.md → project-context-public.md
- PROJECT_OVERVIEW.md → project-overview.md
- README.md → readme.md
- RISK_POLICY.md → risk-policy.md
- ROADMAP.md → roadmap.md
- TODO.md → todo.md
- CLAUDE.md (repo root) → claude-md-repo.md

### New specs/ files (3)
Files in `docs/specs/` added since last sync:
- ADR-benchmark-versioning-and-crypto-unavailability.md → adr-benchmark-versioning-and-crypto-unavailability.md
- LLM_BUNDLE_CONTRACT.md → llm-bundle-contract.md
- SPEC-RIS-L2-1-*.md → spec-ris-l2-1-*.md (exact name TBD at runtime)

### New adrs/ file (1)
- `docs/adr/ADR-0012-*.md` or `docs/adr/0012-*.md` → adr-0012-*.md

---

## DIVERGED Files by Subfolder

| Subfolder | Count | Root Cause |
|-----------|-------|------------|
| root/ | 5 | `## Connections` appended by previous sync |
| specs/ | 46 | `## Connections` appended by previous sync |
| adrs/ | 13 | `## Connections` appended by previous sync |
| **Total** | **64** | All caused by appended Connections sections |

### Diverged root files (5)
- current-state.md → source: `docs/CURRENT_STATE.md`
- architecture.md → source: `docs/ARCHITECTURE.md`
- plan-of-record.md → source: `docs/PLAN_OF_RECORD.md`
- overview.md (STRATEGY_PLAYBOOK) → source: `docs/STRATEGY_PLAYBOOK.md`
- architect-context-pack.md → source: `docs/ARCHITECT_CONTEXT_PACK.md`

---

## ORPHANED Files (1)

| Vault Path | Reason |
|-----------|--------|
| `repo-docs/adrs/adr-benchmark-versioning-and-crypto-unavailability.md` | Source `docs/adr/ADR-benchmark-versioning-and-crypto-unavailability.md` does not exist — the actual file is in `docs/specs/` (not `docs/adr/`). Mirror was created in wrong subfolder by previous sync. |

**Action**: Mark as orphaned (orphaned: true, orphaned_at: 2026-05-25, status: archived) and prepend warning callout. The correct mirror of the specs/ source will be created in `repo-docs/specs/` as a NEW file.

---

## Connections

- [[claude-memory/spec/vault-redesign-spec]]
- [[claude-memory/work-packets/2026-05-23-vault-redesign-execution-report]]
