# Academic Scaled Validation — Batch B Preflight

**Date:** 2026-05-28
**Author:** Claude Code (Sonnet 4.6)
**Status:** PASS — Batch B ready to schedule
**Scope:** Queue preflight and reorder only. No GPU parsing, no Batch B run, no implementation code changes.
**Codex BLOCK resolved:** Addresses direct blocking issue from `docs/dev_logs/2026-05-28_codex-review-academic-batch-a.md`.

---

## Files / Artifacts Changed

| File | Change |
|------|--------|
| `artifacts/research/scaled_validation_queue_v2/queue.jsonl` | Reordered pending items so Batch B papers occupy positions 1-10 of the pending list; Tier-3 and large papers pushed to positions 11-19 |
| `artifacts/research/scaled_validation_queue_v2/queue.jsonl.bak2` | New backup of pre-reorder queue.jsonl (original was `queue.jsonl.bak`) |
| `docs/dev_logs/2026-05-28_academic-batch-b-preflight.md` | This log |

No implementation code, retrieval logic, parser settings, benchmark baselines, or Batch C/D artifacts were touched.

---

## Step 1 — Git Status Check

```
git status --short | grep -v docs/ | grep -v AGENTS | grep -v claude
```

Result: Only docs/obsidian-vault deletion paths visible — all in `docs/` tree. No implementation files dirty. **PASS.**

---

## Step 2a — Pre-Reorder Status-Report

```
python -m polytool research-marker-queue --queue-dir artifacts/research/scaled_validation_queue_v2 status-report --json
```

Result:
```json
{
  "counts": {"pending": 19, "processing": 0, "done": 10, "failed": 0, "total": 29},
  "prefetch_stats": {"cached": 24, "failed": 0, "total_manifest_entries": 24},
  "sidecar_count": 10,
  "indexed_count": 25
}
```

Note: `indexed_count=25` is audit-log line count, not unique-paper count (same harmless-duplicate pattern documented in Batch A preflight).

### Pre-Reorder Next 10 Pending IDs (positions 1-10 in FIFO)

```
 1. arxiv:1206.4810  — medium, ingest_tier=2, tier3_flag=false  [OK]
 2. arxiv:2003.05958 — medium, ingest_tier=2, tier3_flag=false  [OK]
 3. arxiv:2203.13053 — medium, ingest_tier=2, tier3_flag=false  [OK]
 4. arxiv:1810.04383 — medium, ingest_tier=2, tier3_flag=false  [OK]
 5. arxiv:2409.02025 — medium, ingest_tier=3, tier3_flag=true   [TIER-3 ❌]
 6. arxiv:1011.6402  — medium, ingest_tier=3, tier3_flag=true   [TIER-3 ❌]
 7. arxiv:1609.03471 — medium, ingest_tier=2, tier3_flag=false  [OK]
 8. arxiv:2508.03474 — large,  ingest_tier=2, tier3_flag=true   [LARGE/TIER3-FLAG ❌]
 9. arxiv:2605.11640 — medium, ingest_tier=2, tier3_flag=false  [OK]
10. arxiv:2605.02286 — medium, ingest_tier=2, tier3_flag=false  [OK]
```

**Problem confirmed:** `warm-process --max-items 10` would process 3 excluded papers (positions 5, 6, 8). This matches the Codex BLOCK finding.

---

## Step 2b — Pre-Reorder Check-Chroma-Links

```
python -m polytool research-marker-queue check-chroma-links --json
```

Result:
```json
{"collection":"academic_papers","total_chunks":485,"unique_papers":13,"valid_ks_doc_id":485,"missing_ks_doc_id":0,"ks_doc_id_not_in_ks":0}
```

CLEAN. No orphaned chunks, no missing KS doc IDs.

---

## Step 3 — Identify Intended Batch B Set

Criteria:
- `status=pending`
- `ingest_tier=2` (not Tier-3)
- `tier3_flag=false` (not large/flagged)
- `size_bucket=medium (601-1500KB)` (not small — Batch A — or large — Batch C)
- Not in done_ids (Batch A papers already done)

Excluded from Batch B:
- `arxiv:2409.02025` — `ingest_tier=3`, `tier3_flag=true` — REQUIRES OPERATOR APPROVAL
- `arxiv:1011.6402`  — `ingest_tier=3`, `tier3_flag=true` — REQUIRES OPERATOR APPROVAL
- `arxiv:2508.03474` — `tier3_flag=true`, large (9761KB) — Batch C
- `arxiv:2604.10005` — `tier3_flag=true`, large (1728KB) — Batch C
- `arxiv:2403.09267` — `tier3_flag=true`, large (3583KB) — Batch C
- `arxiv:2212.12717` — `tier3_flag=true`, large (2281KB) — Batch C
- `arxiv:2308.04947` — `tier3_flag=true`, large (6684KB) — Batch C
- `arxiv:2604.20050` — `tier3_flag=true`, large (1834KB) — Batch C
- `arxiv:2602.21091` — `tier3_flag=true`, large (2032KB) — Batch C

**Intended Batch B set (10 non-Tier-3 medium papers):**

| Position | arXiv ID | Size (KB) | ingest_tier | tier3_flag |
|----------|----------|-----------|-------------|------------|
| 1 | arxiv:1206.4810  | 720  | 2 | false |
| 2 | arxiv:2003.05958 | 938  | 2 | false |
| 3 | arxiv:2203.13053 | 1126 | 2 | false |
| 4 | arxiv:1810.04383 | 1241 | 2 | false |
| 5 | arxiv:1609.03471 | 1298 | 2 | false |
| 6 | arxiv:2605.11640 | 1041 | 2 | false |
| 7 | arxiv:2605.02286 | 657  | 2 | false |
| 8 | arxiv:2605.00493 | 879  | 2 | false |
| 9 | arxiv:2208.13564 | 1008 | 2 | false |
| 10 | arxiv:2605.10400 | 1029 | 2 | false |

This matches the Batch B list recommended in `docs/dev_logs/2026-05-28_academic-scaled-validation-batch-a.md` (Step 4, Batch B papers).

---

## Step 4 — Queue Reorder

**Pre-reorder state:** 10 done + 19 pending = 29 lines. Done items preserved in-place (lines 1-10). Pending items reordered only.

**Reorder logic:** Among pending items, promote Batch B papers to positions 1-10 (preserving the relative order from the original Batch B plan). Excluded papers (Tier-3 and large) move to positions 11-19 (relative order preserved).

**Backup written:** `artifacts/research/scaled_validation_queue_v2/queue.jsonl.bak2`

No `status`, `attempts`, `created_at`, `updated_at`, `pdf_url`, `pdf_cache_path`, or any other fields were modified. Only line ordering changed.

---

## Step 5 — Post-Reorder Status-Report

```
python -m polytool research-marker-queue --queue-dir artifacts/research/scaled_validation_queue_v2 status-report --json
```

Result:
```json
{
  "counts": {"pending": 19, "processing": 0, "done": 10, "failed": 0, "total": 29},
  "prefetch_stats": {"cached": 24, "failed": 0, "total_manifest_entries": 24},
  "sidecar_count": 10,
  "indexed_count": 25
}
```

### Post-Reorder Next 10 Pending IDs (positions 1-10 in FIFO)

```
 1. arxiv:1206.4810  — medium, ingest_tier=2, tier3_flag=false  [BATCH B ✅]
 2. arxiv:2003.05958 — medium, ingest_tier=2, tier3_flag=false  [BATCH B ✅]
 3. arxiv:2203.13053 — medium, ingest_tier=2, tier3_flag=false  [BATCH B ✅]
 4. arxiv:1810.04383 — medium, ingest_tier=2, tier3_flag=false  [BATCH B ✅]
 5. arxiv:1609.03471 — medium, ingest_tier=2, tier3_flag=false  [BATCH B ✅]
 6. arxiv:2605.11640 — medium, ingest_tier=2, tier3_flag=false  [BATCH B ✅]
 7. arxiv:2605.02286 — medium, ingest_tier=2, tier3_flag=false  [BATCH B ✅]
 8. arxiv:2605.00493 — medium, ingest_tier=2, tier3_flag=false  [BATCH B ✅]
 9. arxiv:2208.13564 — medium, ingest_tier=2, tier3_flag=false  [BATCH B ✅]
10. arxiv:2605.10400 — medium, ingest_tier=2, tier3_flag=false  [BATCH B ✅]
```

**All 10 are non-Tier-3 medium papers. No Tier-3 or large/flagged papers in positions 1-10.**

Positions 11-19 (excluded):
```
11. arxiv:2409.02025 — ingest_tier=3, tier3_flag=true   [TIER-3 — OPERATOR APPROVAL REQUIRED]
12. arxiv:1011.6402  — ingest_tier=3, tier3_flag=true   [TIER-3 — OPERATOR APPROVAL REQUIRED]
13. arxiv:2508.03474 — tier3_flag=true, large           [BATCH C]
14. arxiv:2604.10005 — tier3_flag=true, large           [BATCH C]
15. arxiv:2403.09267 — tier3_flag=true, large           [BATCH C]
16. arxiv:2212.12717 — tier3_flag=true, large           [BATCH C]
17. arxiv:2308.04947 — tier3_flag=true, large           [BATCH C]
18. arxiv:2604.20050 — tier3_flag=true, large           [BATCH C]
19. arxiv:2602.21091 — tier3_flag=true, large           [BATCH C]
```

---

## Step 6 — Tier-3 Exclusion Evidence

| Paper | ingest_tier | tier3_flag | is_known_timeout_risk | Status |
|-------|-------------|------------|----------------------|--------|
| arxiv:2409.02025 | 3 | true | true | EXCLUDED — Tier-3, operator approval required |
| arxiv:1011.6402  | 3 | true | true | EXCLUDED — Tier-3, operator approval required |
| arxiv:2508.03474 | 2 | true | false | EXCLUDED — tier3_flag (9761KB large) |
| arxiv:2604.10005 | 2 | true | false | EXCLUDED — tier3_flag (1728KB large) |
| arxiv:2403.09267 | 2 | true | false | EXCLUDED — tier3_flag (3583KB large) |
| arxiv:2212.12717 | 2 | true | false | EXCLUDED — tier3_flag (2281KB large) |
| arxiv:2308.04947 | 2 | true | false | EXCLUDED — tier3_flag (6684KB large) |
| arxiv:2604.20050 | 2 | true | false | EXCLUDED — tier3_flag (1834KB large) |
| arxiv:2602.21091 | 2 | true | false | EXCLUDED — tier3_flag (2032KB large) |

All Batch B positions 1-10 have `ingest_tier=2` and `tier3_flag=false`.

---

## Step 7 — PDF Cache Status for Batch B

All 10 Batch B PDFs confirmed cached in `artifacts/research/scaled_validation_queue_v2/pdf_cache/`:

| arXiv ID | Filename | Size (KB) | Cached |
|----------|----------|-----------|--------|
| 1206.4810  | arxiv-1206.4810.pdf  | 720  | ✅ |
| 2003.05958 | arxiv-2003.05958.pdf | 938  | ✅ |
| 2203.13053 | arxiv-2203.13053.pdf | 1126 | ✅ |
| 1810.04383 | arxiv-1810.04383.pdf | 1241 | ✅ |
| 1609.03471 | arxiv-1609.03471.pdf | 1298 | ✅ |
| 2605.11640 | arxiv-2605.11640.pdf | 1041 | ✅ |
| 2605.02286 | arxiv-2605.02286.pdf | 657  | ✅ |
| 2605.00493 | arxiv-2605.00493.pdf | 879  | ✅ |
| 2208.13564 | arxiv-2208.13564.pdf | 1008 | ✅ |
| 2605.10400 | arxiv-2605.10400.pdf | 1029 | ✅ |

**10/10 Batch B PDFs cached. No live arXiv fetches will occur during warm-process.**

---

## Step 8 — Post-Reorder Check-Chroma-Links

```
python -m polytool research-marker-queue check-chroma-links --json
```

Result:
```json
{"collection":"academic_papers","total_chunks":485,"unique_papers":13,"valid_ks_doc_id":485,"missing_ks_doc_id":0,"ks_doc_id_not_in_ks":0}
```

CLEAN. Unchanged from pre-reorder baseline — queue reorder does not affect Chroma.

---

## Step 9 — Timeout Policy Confirmation

From `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` 4-batch plan (updated 2026-05-28):
- Batch B uses `--marker-timeout 7200` (7200s = 2 hours per paper)

All 10 Batch B papers have `recommended_timeout_seconds: 7200.0` per status-report.
**Timeout policy for Batch B: 7200s. Confirmed.**

---

## Batch B Readiness Verdict

| Dimension | Status | Evidence |
|-----------|--------|----------|
| Queue state | PASS | pending=19, done=10, failed=0, processing=0 |
| No Tier-3 in next 10 | PASS | Positions 1-10: all ingest_tier=2, tier3_flag=false |
| Tier-3 papers excluded | PASS | 2409.02025 and 1011.6402 at positions 11-12 (after Batch B window) |
| Large/tier3_flag papers excluded | PASS | 7 large papers at positions 13-19 (Batch C) |
| PDFs cached | PASS | 10/10 Batch B PDFs in pdf_cache/ |
| Chroma links clean | PASS | 485 chunks, 0 missing, 0 orphans |
| Timeout policy | PASS | 7200s per paper for all 10 Batch B items |
| Codex BLOCK condition resolved | PASS | Pre-reorder had Tier-3 at positions 5 and 6; post-reorder they are at 11 and 12 |

**Overall: PASS — Batch B is ready to schedule.**

---

## Batch B Command (for reference — DO NOT RUN NOW)

```bash
docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
  python -m polytool research-marker-queue \
  --queue-dir /app/artifacts/research/scaled_validation_queue_v2 \
  warm-process --max-items 10 --marker-timeout 7200
```

**Batch B was NOT run in this session. This is a preflight-only log.**

---

## Open Items (not blocking Batch B)

1. **Codex rejection-quality BLOCK (partially open):** Codex noted that `protein folding molecular dynamics` returned an unrelated semantic hit (`arxiv:1705.01446`) in its independent re-probe, whereas the Batch A log reported a correct rejection. This is a retrieval-quality concern, not a parse/index concern. Batch B scheduling is not blocked by this, but the semantic threshold behavior should be re-evaluated before the RIS eval benchmark baseline is set.

2. **Tier-3 operator approval:** `arxiv:2409.02025` and `arxiv:1011.6402` require operator approval before Batch D. They are now at positions 11-12 in the queue — they will not be processed by `warm-process --max-items 10`.

---

## Codex Review Note

No implementation code was changed. No Codex review triggered per the review policy (scope: queue artifact only + dev log).
