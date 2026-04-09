# Dev Log: n8n Workflow Location Migration

**Date:** 2026-04-09
**Task:** quick-260409-khd
**Objective:** Eliminate dual-canonical ambiguity for n8n workflow JSON — establish `infra/n8n/workflows/` as the single source of truth.

---

## Context

The repo had workflow JSON split across two directories with contradictory "legacy" labels in different docs. The 2026-04-08 Codex migration safety test (`quick-260409-jfi`) patched some operator-facing docs but left `docs/CURRENT_STATE.md`, `docs/adr/0013-ris-n8n-pilot-scoped.md`, `infra/n8n/import_workflows.py`, and `scripts/smoke_ris_n8n.py` pointing to the old `workflows/n8n/` location.

---

## Files Changed

| File | Why |
|------|-----|
| `infra/n8n/workflows/ris-unified-dev.json` | Moved from `workflows/n8n/` (canonical active workflow) |
| `infra/n8n/workflows/ris-health-webhook.json` | Moved from `workflows/n8n/` (canonical support workflow) |
| `infra/n8n/workflows/workflow_ids.env` | Moved from `workflows/n8n/` (deployed ID tracking) |
| `infra/n8n/workflows/ris_academic_ingest.json` | Deleted (initial 11-template pilot, superseded) |
| `infra/n8n/workflows/ris_blog_ingest.json` | Deleted (initial 11-template pilot, superseded) |
| `infra/n8n/workflows/ris_freshness_refresh.json` | Deleted (initial 11-template pilot, superseded) |
| `infra/n8n/workflows/ris_github_ingest.json` | Deleted (initial 11-template pilot, superseded) |
| `infra/n8n/workflows/ris_health_check.json` | Deleted (initial 11-template pilot, superseded) |
| `infra/n8n/workflows/ris_manual_acquire.json` | Deleted (initial 11-template pilot, superseded) |
| `infra/n8n/workflows/ris_reddit_others.json` | Deleted (initial 11-template pilot, superseded) |
| `infra/n8n/workflows/ris_reddit_polymarket.json` | Deleted (initial 11-template pilot, superseded) |
| `infra/n8n/workflows/ris_scheduler_status.json` | Deleted (initial 11-template pilot, superseded) |
| `infra/n8n/workflows/ris_weekly_digest.json` | Deleted (initial 11-template pilot, superseded) |
| `infra/n8n/workflows/ris_youtube_ingest.json` | Deleted (initial 11-template pilot, superseded) |
| `workflows/n8n/ris_orchestrator.json` | Deleted (legacy multi-workflow rebuild artifact) |
| `workflows/n8n/ris_global_error_watcher.json` | Deleted (legacy multi-workflow rebuild artifact) |
| `workflows/n8n/ris_sub_academic.json` | Deleted (legacy multi-workflow rebuild artifact) |
| `workflows/n8n/ris_sub_blog_rss.json` | Deleted (legacy multi-workflow rebuild artifact) |
| `workflows/n8n/ris_sub_freshness_refresh.json` | Deleted (legacy multi-workflow rebuild artifact) |
| `workflows/n8n/ris_sub_github.json` | Deleted (legacy multi-workflow rebuild artifact) |
| `workflows/n8n/ris_sub_reddit.json` | Deleted (legacy multi-workflow rebuild artifact) |
| `workflows/n8n/ris_sub_weekly_digest.json` | Deleted (legacy multi-workflow rebuild artifact) |
| `workflows/n8n/ris_sub_youtube.json` | Deleted (legacy multi-workflow rebuild artifact) |
| `workflows/n8n/README.md` | Replaced with stub redirect to `infra/n8n/workflows/` |
| `infra/n8n/import_workflows.py` | Updated `WORKFLOW_DIR` from `workflows/n8n` to `infra/n8n/workflows` |
| `scripts/smoke_ris_n8n.py` | Updated orphan check to verify no JSON in `workflows/n8n/` (stub remains) |
| `infra/n8n/README.md` | Updated Workflow Source Layout table and all path references |
| `docs/RIS_OPERATOR_GUIDE.md` | Updated step 5 import command, canonical file reference, legacy note |
| `docs/CURRENT_STATE.md` | Updated RIS n8n Pilot section canonical path and import command |
| `docs/adr/0013-ris-n8n-pilot-scoped.md` | Updated workflow sources section and legacy note |
| `docs/runbooks/RIS_N8N_SMOKE_TEST.md` | Updated all `workflows/n8n/` path references |

---

## Files Deleted: 18 Legacy JSON Files

**From `infra/n8n/workflows/` (11 initial pilot templates, superseded 2026-04-07):**
1. `ris_academic_ingest.json`
2. `ris_blog_ingest.json`
3. `ris_freshness_refresh.json`
4. `ris_github_ingest.json`
5. `ris_health_check.json`
6. `ris_manual_acquire.json`
7. `ris_reddit_others.json`
8. `ris_reddit_polymarket.json`
9. `ris_scheduler_status.json`
10. `ris_weekly_digest.json`
11. `ris_youtube_ingest.json`

**From `workflows/n8n/` (7 multi-workflow rebuild artifacts + 2 active files moved):**
1. `ris_orchestrator.json`
2. `ris_global_error_watcher.json`
3. `ris_sub_academic.json`
4. `ris_sub_blog_rss.json`
5. `ris_sub_freshness_refresh.json`
6. `ris_sub_github.json`
7. `ris_sub_reddit.json`
8. `ris_sub_weekly_digest.json`
9. `ris_sub_youtube.json`

---

## Files Moved: 3 Active Files

| From | To | Method |
|------|----|--------|
| `workflows/n8n/ris-unified-dev.json` | `infra/n8n/workflows/ris-unified-dev.json` | git rename (byte-identical verified) |
| `workflows/n8n/ris-health-webhook.json` | `infra/n8n/workflows/ris-health-webhook.json` | git rename (byte-identical verified) |
| `workflows/n8n/workflow_ids.env` | `infra/n8n/workflows/workflow_ids.env` | git rename (byte-identical verified) |

Checksums before and after move confirmed identical via MD5:
- `ris-unified-dev.json`: `5d8ab71eae135e1ec7c9d3e6aeea3ff8`
- `ris-health-webhook.json`: `dd8d4f0a8e0c9f3e71ff0251d2de47c9`
- `workflow_ids.env`: `fb6180a2b6879cc3602811b1fd8733ca`

---

## Verification Results

### JSON validity
```
python -c "import json; [json.load(open(f'infra/n8n/workflows/{f}')) for f in ['ris-unified-dev.json','ris-health-webhook.json']]; print('JSON valid')"
JSON valid
```

### Import script loads correctly
```
python infra/n8n/import_workflows.py --help
```
Exit 0. Script docstring and `WORKFLOW_DIR` now point to `infra/n8n/workflows/`.

### Smoke script orphan check
```
python scripts/smoke_ris_n8n.py
```
`orphan-json-removed`: PASS — No workflow JSON in `workflows/n8n/`

### Old location cleaned
```
ls workflows/n8n/
README.md
```
Only the stub README remains.

### New canonical location
```
ls infra/n8n/workflows/
ris-health-webhook.json  ris-unified-dev.json  workflow_ids.env
```

---

## Key Code Change: import_workflows.py

```python
# Before
WORKFLOW_DIR = ROOT_DIR / "workflows" / "n8n"

# After
WORKFLOW_DIR = ROOT_DIR / "infra" / "n8n" / "workflows"
```

## Key Code Change: smoke_ris_n8n.py

```python
# Before (check that workflows/n8n/ directory does not exist at all)
if ORPHAN_DIR.exists():
    check("orphan-v2-removed", "FAIL", ...)
else:
    check("orphan-v2-removed", "PASS", "workflows/n8n/ not present")

# After (check that no JSON files remain in workflows/n8n/)
orphan_jsons = list(ORPHAN_DIR.glob("*.json")) if ORPHAN_DIR.exists() else []
if orphan_jsons:
    check("orphan-json-removed", "FAIL", ...)
else:
    check("orphan-json-removed", "PASS", "No workflow JSON in workflows/n8n/")
```

---

## Final Canonical Folder

`infra/n8n/workflows/` is the single canonical source for active n8n workflow JSON.

Import command: `python infra/n8n/import_workflows.py`

---

## Remaining Legacy References (Intentional)

- Git history preserves the old `workflows/n8n/` paths in prior commits. This is expected and correct — git history is not rewritten.
- The dev log `docs/dev_logs/2026-04-08_n8n_operator_path_cleanup.md` references the pre-migration state. It is a historical record and should not be updated.

---

## Codex Review

Tier: Skip (docs and config only, no execution/strategy/simtrader code). No Codex review required.
