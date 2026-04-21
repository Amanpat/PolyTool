# Dev Log: Roadmap Reference Fixups

**Date:** 2026-04-21  
**Objective:** Update seven active-doc references to superseded roadmap files following the archival of v4.2 and v5 to `docs/archive/reference/`.

---

## Files Updated

| # | File | Line | Change |
|---|---|---|---|
| 1 | `config/seed_manifest.json` | 102 | v4.2 path → archive path |
| 2 | `config/seed_manifest.json` | 114 | v5 path → archive path |
| 3 | `docs/ARCHITECTURE.md` | 6 | v5 governing ref → v5_1 |
| 4 | `docs/specs/SPEC-wallet-discovery-v1.md` | 9 | v5 governing ref → v5_1 |
| 5 | `docs/specs/SPEC-benchmark-gap-fill-planner-v1.md` | 5 | v4.2 authority → archive path + historical clarifier |
| 6 | `docs/specs/SPEC-benchmark-manifest-contract-v1.md` | 5 | v4.2 authority → archive path + historical clarifier |
| 7 | `docs/runbooks/BULK_HISTORICAL_IMPORT_V0.md` | 8 | v4.2 DB arch ref → v5_1 |
| 8 | `docs/features/FEATURE-ris-v2-seed-and-benchmark.md` | 36 | filename list → annotated with archived/current status |

---

## Step 6 Verification — v5_1 Database Architecture Content

Before updating `BULK_HISTORICAL_IMPORT_V0.md` line 8, confirmed that v5_1 contains equivalent or superior Database Architecture content:

From `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md` lines 380–383:
```
### Database Architecture — ClickHouse + DuckDB

**ClickHouse handles all live streaming writes. DuckDB handles all historical Parquet reads.**
```

v5_1 contains the full database architecture section including the one-sentence rule, a routing table (lines 402–408), and the DuckDB zero-config explanation. The runbook reference was correctly updated to point to v5_1.

---

## Before / After for Each Edit

**1 & 2 — config/seed_manifest.json**

Before (line 102):
```json
"path": "docs/reference/POLYTOOL_MASTER_ROADMAP_v4.2.md",
```
After:
```json
"path": "docs/archive/reference/POLYTOOL_MASTER_ROADMAP_v4.2.md",
```

Before (line 114):
```json
"path": "docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md",
```
After:
```json
"path": "docs/archive/reference/POLYTOOL_MASTER_ROADMAP_v5.md",
```

**3 — docs/ARCHITECTURE.md line 6**

Before:
```
Master Roadmap v5 (`docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md`) is the
```
After:
```
Master Roadmap v5.1 (`docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md`) is the
```

**4 — docs/specs/SPEC-wallet-discovery-v1.md line 9**

Before:
```
- `docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md` (governing roadmap)
```
After:
```
- `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md` (governing roadmap)
```

**5 — docs/specs/SPEC-benchmark-gap-fill-planner-v1.md line 5**

Before:
```
**Authority:** `docs/reference/POLYTOOL_MASTER_ROADMAP_v4.2.md`
```
After:
```
**Authority:** `docs/archive/reference/POLYTOOL_MASTER_ROADMAP_v4.2.md` (superseded; retained for historical context)
```

**6 — docs/specs/SPEC-benchmark-manifest-contract-v1.md line 5**

Before:
```
**Authority:** `docs/reference/POLYTOOL_MASTER_ROADMAP_v4.2.md`
```
After:
```
**Authority:** `docs/archive/reference/POLYTOOL_MASTER_ROADMAP_v4.2.md` (superseded; retained for historical context)
```

**7 — docs/runbooks/BULK_HISTORICAL_IMPORT_V0.md line 8**

Before:
```
> See `docs/reference/POLYTOOL_MASTER_ROADMAP_v4.2.md` (Database Architecture).
```
After:
```
> See `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md` (Database Architecture).
```

**8 — docs/features/FEATURE-ris-v2-seed-and-benchmark.md line 36**

Before:
```
- 3 roadmap docs: POLYTOOL_MASTER_ROADMAP_v4.2.md, v5.md, v5_1.md
```
After:
```
- 3 roadmap docs: POLYTOOL_MASTER_ROADMAP_v4.2.md (archived), v5.md (archived), v5_1.md (current)
```

---

## Post-Fix Sweep Output

Command:
```
grep -rn "docs/reference/POLYTOOL_MASTER_ROADMAP_v4\.2\|docs/reference/POLYTOOL_MASTER_ROADMAP_v5\.md" \
  --include="*.md" --include="*.py" --include="*.yml" --include="*.json" \
  docs/ config/ tools/ packages/ 2>/dev/null \
  | grep -v "^docs/archive/" | grep -v "^docs/dev_logs/" | grep -v "^docs/obsidian-vault/"
```

**Output: (empty — no remaining stale references in active docs)**

---

## Smoke Test Results

```
$ python -m json.tool config/seed_manifest.json > /dev/null
JSON valid

$ python -m polytool --help
PolyTool - Polymarket analysis toolchain

Usage: polytool <command> [options]
       python -m polytool <command> [options]
(CLI loads cleanly, no import errors)
```

`git diff --stat` for this task's target files:
```
config/seed_manifest.json                          |  4 +-
docs/ARCHITECTURE.md                               |  2 +-
docs/features/FEATURE-ris-v2-seed-and-benchmark.md |  2 +-
docs/runbooks/BULK_HISTORICAL_IMPORT_V0.md         |  2 +-
docs/specs/SPEC-benchmark-gap-fill-planner-v1.md   |  2 +-
docs/specs/SPEC-benchmark-manifest-contract-v1.md  |  2 +-
docs/specs/SPEC-wallet-discovery-v1.md             |  2 +-
```

All within the ≤6 / ≤3 line-count constraint.

---

## Anomalies

None. All edits were clean single-line replacements. No formatting drift, no content changes beyond the specified substitutions.

---

## Codex Review

Tier: Skip (docs and config only, no code changed).
