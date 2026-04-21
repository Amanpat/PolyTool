# Dev Log: Archive Superseded Roadmaps

**Date:** 2026-04-21  
**Objective:** Move POLYTOOL_MASTER_ROADMAP_v4.2.md and POLYTOOL_MASTER_ROADMAP_v5.md from `docs/reference/` to `docs/archive/reference/` with SUPERSEDED frontmatter headers.

---

## Files Moved

| Before | After |
|---|---|
| `docs/reference/POLYTOOL_MASTER_ROADMAP_v4.2.md` | `docs/archive/reference/POLYTOOL_MASTER_ROADMAP_v4.2.md` |
| `docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md` | `docs/archive/reference/POLYTOOL_MASTER_ROADMAP_v5.md` |

Both files received the following YAML frontmatter prepended before any existing content:

```yaml
---
status: superseded
superseded_by: docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md
superseded_date: 2026-04-21
---
**STATUS: SUPERSEDED by v5_1 as of 2026-04-21. Historical reference only.**
```

---

## Reference Sweep Output (verbatim)

Command run:
```
grep -rn "POLYTOOL_MASTER_ROADMAP_v4\.2\|POLYTOOL_MASTER_ROADMAP_v5\.md" \
  --include="*.md" --include="*.py" --include="*.yml" --include="*.json" \
  docs/ config/ tools/ packages/ 2>/dev/null; \
grep -rn "POLYTOOL_MASTER_ROADMAP_v4\.2\|POLYTOOL_MASTER_ROADMAP_v5\.md" \
  --include="*.md" CLAUDE.md AGENTS.md 2>/dev/null
```

Raw output:
```
docs/ARCHITECTURE.md:6:Master Roadmap v5 (`docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md`) is the
docs/archive/CURRENT_STATE_HISTORY.md:197:See `docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md` (Database Architecture).
docs/dev_logs/2026-03-16_benchmark_manifest_contract.md:9:Authority: `docs/reference/POLYTOOL_MASTER_ROADMAP_v4.2.md`
docs/dev_logs/2026-03-16_v42_docs_reconciliation.md:35:From `docs/reference/POLYTOOL_MASTER_ROADMAP_v4.2.md` (Database Architecture):
docs/dev_logs/2026-03-21_phase0_authority_sync_v5.md:10:(docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md) as the governing document.
docs/dev_logs/2026-03-21_phase0_operator_docs_v5.md:39:- `docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md`
docs/dev_logs/2026-03-21_phase0_operator_docs_v5.md:67:Get-Content docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md
docs/dev_logs/2026-03-23_phase1a_paper_soak_rubric_v0.md:19:- `docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md`
docs/dev_logs/2026-03-25_drive_workflow_rclone_sync.md:118:      POLYTOOL_MASTER_ROADMAP_v5.md
docs/dev_logs/2026-04-02_ris_phase2_calibration_and_metadata_hardening.md:52:| `docs/reference/POLYTOOL_MASTER_ROADMAP_v4.2.md` | `book` | `roadmap` | `tier_2_superseded` |
docs/dev_logs/2026-04-02_ris_phase2_calibration_and_metadata_hardening.md:53:| `docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md` | `book` | `roadmap` | `tier_1_internal` |
docs/dev_logs/2026-04-10_repo_cleanup_policy_foundation.md:106:docs/ARCHITECTURE.md:6:Master Roadmap v5 (`docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md`) is the
docs/dev_logs/2026-04-10_repo_cleanup_policy_foundation.md:107:docs/ROADMAP.md:3:Master Roadmap v5 (`docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md`) is the
docs/dev_logs/2026-04-10_roadmap_surface_cleanup_phase2b.md:21:- `docs/ROADMAP.md` still read like a competing authority surface: it said a roadmap was governing, pointed at the obsolete `docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md`, and preserved a full numbered milestone ledger that looked authoritative instead of secondary.
docs/features/FEATURE-ris-v2-seed-and-benchmark.md:36:- 3 roadmap docs: POLYTOOL_MASTER_ROADMAP_v4.2.md, v5.md, v5_1.md
docs/obsidian-vault/09-Decisions/Decision - Workflow Harness Refresh 2026-04.md:23:- **Archive superseded roadmaps.** Move `POLYTOOL_MASTER_ROADMAP_v4.2.md` and `POLYTOOL_MASTER_ROADMAP_v5.md` from `docs/reference/` to `docs/archive/reference/` with a SUPERSEDED header.
docs/runbooks/BULK_HISTORICAL_IMPORT_V0.md:8:> See `docs/reference/POLYTOOL_MASTER_ROADMAP_v4.2.md` (Database Architecture).
docs/specs/SPEC-benchmark-gap-fill-planner-v1.md:5:**Authority:** `docs/reference/POLYTOOL_MASTER_ROADMAP_v4.2.md`
docs/specs/SPEC-benchmark-manifest-contract-v1.md:5:**Authority:** `docs/reference/POLYTOOL_MASTER_ROADMAP_v4.2.md`
docs/specs/SPEC-wallet-discovery-v1.md:9:- `docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md` (governing roadmap)
config/seed_manifest.json:102:      "path": "docs/reference/POLYTOOL_MASTER_ROADMAP_v4.2.md",
config/seed_manifest.json:114:      "path": "docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md",
```

---

## Reference Classification

| File | Type | Classification | Notes |
|---|---|---|---|
| `docs/ARCHITECTURE.md:6` | Active governance doc | **ACTIVE — operator decision needed** | Points v5.md as governing; should be updated to v5_1 |
| `docs/runbooks/BULK_HISTORICAL_IMPORT_V0.md:8` | Active runbook | **ACTIVE — operator decision needed** | References v4.2 for DB architecture |
| `docs/specs/SPEC-benchmark-gap-fill-planner-v1.md:5` | Spec (read-only) | **ACTIVE — operator decision needed** | Authority line points to v4.2 |
| `docs/specs/SPEC-benchmark-manifest-contract-v1.md:5` | Spec (read-only) | **ACTIVE — operator decision needed** | Authority line points to v4.2 |
| `docs/specs/SPEC-wallet-discovery-v1.md:9` | Spec (read-only) | **ACTIVE — operator decision needed** | References v5.md as governing roadmap |
| `docs/features/FEATURE-ris-v2-seed-and-benchmark.md:36` | Active feature doc | **ACTIVE — operator decision needed** | Mentions all 3 roadmap filenames |
| `docs/obsidian-vault/09-Decisions/Decision - Workflow Harness Refresh 2026-04.md:23` | Decision doc | **ACTIVE — informational only** | Already calls for this exact archive action; no update needed |
| `config/seed_manifest.json:102,114` | Live config | **ACTIVE — operator decision needed** | RIS seed manifest has `"path"` fields pointing to old locations; paths will be stale after move |
| `docs/archive/CURRENT_STATE_HISTORY.md:197` | Archive doc | archive — no action | Historical record; stale path acceptable |
| `docs/dev_logs/2026-03-16_benchmark_manifest_contract.md:9` | Dev log | dev_log — no action | Historical record |
| `docs/dev_logs/2026-03-16_v42_docs_reconciliation.md:35` | Dev log | dev_log — no action | Historical record |
| `docs/dev_logs/2026-03-21_phase0_authority_sync_v5.md:10` | Dev log | dev_log — no action | Historical record |
| `docs/dev_logs/2026-03-21_phase0_operator_docs_v5.md:39,67` | Dev log | dev_log — no action | Historical record |
| `docs/dev_logs/2026-03-23_phase1a_paper_soak_rubric_v0.md:19` | Dev log | dev_log — no action | Historical record |
| `docs/dev_logs/2026-03-25_drive_workflow_rclone_sync.md:118` | Dev log | dev_log — no action | Historical record |
| `docs/dev_logs/2026-04-02_ris_phase2_calibration_and_metadata_hardening.md:52,53` | Dev log | dev_log — no action | Historical record |
| `docs/dev_logs/2026-04-10_repo_cleanup_policy_foundation.md:106,107` | Dev log | dev_log — no action | Historical record (itself a grep capture) |
| `docs/dev_logs/2026-04-10_roadmap_surface_cleanup_phase2b.md:21` | Dev log | dev_log — no action | Historical record |

---

## Remaining References Requiring Operator Decision

These are active files (outside `docs/archive/` and `docs/dev_logs/`) that still point to the old paths. **None were modified.** Operator should decide case by case: update to v5_1 path, update to new archive path, or leave as historical.

1. **`docs/ARCHITECTURE.md:6`** — References `docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md` as the governing roadmap. Should likely be updated to v5_1.

2. **`docs/runbooks/BULK_HISTORICAL_IMPORT_V0.md:8`** — References v4.2 for Database Architecture. The section it cites may be historical context that is fine to leave, or could point to v5_1.

3. **`docs/specs/SPEC-benchmark-gap-fill-planner-v1.md:5`** — `Authority:` line points to v4.2. Specs are read-only per CLAUDE.md; operator must decide.

4. **`docs/specs/SPEC-benchmark-manifest-contract-v1.md:5`** — `Authority:` line points to v4.2. Same as above.

5. **`docs/specs/SPEC-wallet-discovery-v1.md:9`** — References v5.md as `(governing roadmap)`. Should likely be updated to v5_1.

6. **`docs/features/FEATURE-ris-v2-seed-and-benchmark.md:36`** — Lists all 3 roadmap filenames as RIS seeded docs; the listing is accurate (all 3 were seeded). Updating to reflect new archive paths is optional.

7. **`config/seed_manifest.json:102,114`** — **HIGH PRIORITY.** Contains `"path"` fields used by the RIS seed pipeline. After the move, these paths are stale and the seed pipeline will fail to find the files at the old location. Operator should update to `docs/archive/reference/POLYTOOL_MASTER_ROADMAP_v4.2.md` and `docs/archive/reference/POLYTOOL_MASTER_ROADMAP_v5.md` respectively, or remove the entries if they should no longer be seeded.

---

## Smoke Test Output

```
$ ls docs/reference/
HYPOTHESIS_STANDARD.md
LOCAL_STATE_AND_TOOLING_BOUNDARY.md
POLYTOOL_MASTER_ROADMAP_v5_1.md
RAGfiles
RESEARCH_SOURCES.md
TRUST_ARTIFACTS.md

$ ls docs/archive/reference/
POLYTOOL_MASTER_ROADMAP_v4.2.md
POLYTOOL_MASTER_ROADMAP_v5.md
```

`head -8 docs/archive/reference/POLYTOOL_MASTER_ROADMAP_v4.2.md`:
```
---
status: superseded
superseded_by: docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md
superseded_date: 2026-04-21
---
**STATUS: SUPERSEDED by v5_1 as of 2026-04-21. Historical reference only.**

# PolyTool — Master Roadmap
```

`head -8 docs/archive/reference/POLYTOOL_MASTER_ROADMAP_v5.md`:
```
---
status: superseded
superseded_by: docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md
superseded_date: 2026-04-21
---
**STATUS: SUPERSEDED by v5_1 as of 2026-04-21. Historical reference only.**

# PolyTool — Master Roadmap
```

---

## Codex Review

Tier: Skip (docs only, no code changed).

---

## Open Questions / Blockers

- **`config/seed_manifest.json` paths are now stale.** This is the most actionable item. If the RIS seed pipeline is re-run, it will fail to find files at the old paths. Update paths to `docs/archive/reference/` or remove entries.
- Seven other active-doc references listed above require operator triage before being updated.
