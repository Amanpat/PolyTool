# Academic Batch A Preflight — Staged Cached Validation

**Date:** 2026-05-28
**Scope:** Preflight only. No GPU parsing, no Batch A run, no parser/retrieval code changes.
**Input:** Queue reset PASS WITH CONCERNS verdict from Codex review
(`docs/dev_logs/2026-05-28_codex-review-academic-queue-reset-readiness.md`).

---

## Files / Artifacts Changed

| File | Change |
|------|--------|
| `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` | Replaced stale pre-reset "Corpus Status (as of 2026-05-18)" section with current reset-state + 4-batch plan table |
| `docs/CURRENT_STATE.md` | Updated Chroma embedding gap from PARTIAL to RESOLVED; added indexed.jsonl duplicate note; added staged plan reference |
| `artifacts/research/scaled_validation_queue_v2/indexed.jsonl` | Appended entries from two `--force` reindex runs (harmless audit duplicates; see below) |

---

## Commands Run

### Step 1 — Git status check

```
git status --short | grep -v "docs/" | grep -v "AGENTS" | grep -v "claude"
```

Result: empty — no implementation files dirty. All uncommitted changes are docs/vault files.

### Step 2 — Baseline status-report

```
python -m polytool research-marker-queue --queue-dir artifacts/research/scaled_validation_queue_v2 status-report --json
```

Result:
```
pending=24, processing=0, done=5, failed=0, total=29
prefetch_stats: cached=24, failed=0
sidecar_count=5, indexed_count=10
Tier-3 flags: 1011.6402 (ingest_tier=3), 2409.02025 (ingest_tier=3), 2508.03474 (tier3_flag=true by size)
```

Note: `indexed_count=10` = 5 papers × 2 prior `--force` runs (not 10 unique papers).

### Step 2b — Baseline check-chroma-links

```
python -m polytool research-marker-queue check-chroma-links --json
```

Result:
```json
{"total_chunks": 162, "unique_papers": 5, "valid_ks_doc_id": 162, "missing_ks_doc_id": 0, "ks_doc_id_not_in_ks": 0}
```

Pre-refresh: 5 unique papers in Chroma. Those papers were: 1106.5040, 1609.03471, 1810.04383,
2510.05533, 2604.24366. Of these, only 1106.5040 was among the 5 done papers; 4 done papers
(1105.3115, 1605.01862, 1705.01446, 2307.14129) were KS-indexed but missing from Chroma.

### Step 3 — indexed.jsonl duplicate inspection

Inspected `artifacts/research/scaled_validation_queue_v2/indexed.jsonl` (10 lines before preflight).

**Findings:**
- Lines 1–5: First `index-done` run at ~11:24 UTC (claims_extracted > 0)
- Lines 6–10: Second `index-done --force` run at ~11:34 UTC (identical doc_ids, chunk_counts)
- All 10 entries correspond to the same 5 candidate_ids with identical doc_ids

**Disposition: HARMLESS AUDIT DUPLICATES.**

The `index_done_items()` function builds `indexed_by_cid` by iterating all lines and overwriting
on duplicate `candidate_id`, so the last record per paper wins. The KS and Chroma contain exactly
5 papers. The inflated `indexed_count` in `status-report` counts all lines, not unique papers.

No repair needed — do not delete history. Note: the raw `indexed_count` field in `status-report`
JSON is not a unique-paper count; use `len(done_ids)` instead.

### Step 4 — Chroma refresh for done papers

**Pre-attempt check:** Python can open body files on Windows because they use U+F03A fullwidth
colon in filenames (NTFS workaround from commit b921857). `sentence-transformers v5.2.2` is
installed on Windows host.

```
python -m polytool research-marker-queue --queue-dir artifacts/research/scaled_validation_queue_v2 index-done --reindex-chroma --force
```

**Result (first run — b2roamujs):**
```
Indexed 5 paper(s):
  [OK] arxiv:1105.3115  doc_id=1b252835...  chunks=36  claims=0  chroma_chunks=36
  [OK] arxiv:1106.5040  doc_id=c30c1027...  chunks=30  claims=0  chroma_chunks=30
  [OK] arxiv:1605.01862  doc_id=0b289e8d...  chunks=47  claims=0  chroma_chunks=47
  [OK] arxiv:1705.01446  doc_id=741fa093...  chunks=49  claims=0  chroma_chunks=49
  [OK] arxiv:2307.14129  doc_id=536aa7b4...  chunks=65  claims=0  chroma_chunks=65
Total: 5 done item(s) examined — 5 indexed, 0 already-indexed, 0 no-body, 0 failed, 0 claims, 227 Chroma chunks upserted.
```

`claims=0` is expected: claim records already exist (INSERT OR IGNORE semantics); the `--force`
re-index path does not re-extract. Original claims_extracted counts from prior runs (165, 147,
235, 241, 318) remain in the KS.

A second duplicate run (bx36ca03b) was inadvertently started and also completed (exit 0). Both
runs produced idempotent Chroma upserts (chunk IDs are deterministic; no duplicate chunks created).
Both runs appended entries to `indexed.jsonl` with `claims_extracted=0` — adding more harmless
audit duplicates. `indexed.jsonl` now has 19 entries for 5 unique papers.

### Step 5 — Post-refresh check-chroma-links and status-report

```
python -m polytool research-marker-queue check-chroma-links --json
```

Result:
```json
{"total_chunks": 359, "unique_papers": 9, "valid_ks_doc_id": 359, "missing_ks_doc_id": 0, "ks_doc_id_not_in_ks": 0}
```

Interpretation:
- 9 unique papers = 5 done papers (1105.3115, 1106.5040, 1605.01862, 1705.01446, 2307.14129)
  + 4 previously-embedded papers that are pending in this queue (1609.03471, 1810.04383,
  2510.05533, 2604.24366). No orphaned chunks. No missing ks_doc_id. CLEAN.
- 359 chunks = 162 (prior) − 0 (1106.5040 overwritten by same data) + 197 (4 newly embedded papers)

```
python -m polytool research-marker-queue --queue-dir artifacts/research/scaled_validation_queue_v2 status-report --json
```

Result: counts unchanged (pending=24, done=5, failed=0); indexed_count now 19 (inflated).

### Step 6 — JIT cache diagnostic

```
python -m polytool research-marker-queue --queue-dir artifacts/research/scaled_validation_queue_v2 jit-cache-check
```

Result:
```
TORCHINDUCTOR_CACHE_DIR = (not set)
TRITON_CACHE_DIR        = (not set)
```

**JIT cache persistence: UNPROVEN.** The diagnostic printed the manual inside-Docker steps.
No GPU parse session was run. Cannot prove persistence without a before/after kernel-file check
inside the container across a restart. Runtime planning must budget for cold-start risk.

---

## indexed.jsonl Duplicate Disposition

**Final state: 19 lines, 5 unique candidate_ids.**

| Run | Time (UTC) | Lines | claims_extracted | Notes |
|-----|-----------|-------|-----------------|-------|
| Run 1 (original) | ~11:24 | 1–5 | 165, 147, 235, 241, 318 | First successful index |
| Run 2 (--force) | ~11:34 | 6–10 | 165, 147, 235, 241, 318 | Same values — no change |
| Run 3 (--reindex-chroma --force) | ~12:10 | 11–14, 15–18 | 0 for all | Chroma backfill; claims not re-extracted |

The 4 extra lines from Run 3 (lines 11–18) reflect interleaved writes from two concurrent runs.
All entries have identical doc_ids to prior runs. The code deduplicates correctly (last-record-wins
per candidate_id). No action needed.

---

## Chroma Refresh Result

**RESOLVED.** All 5 done papers are now semantically embedded in Chroma.

| Before | After |
|--------|-------|
| 162 chunks, 5 papers | 359 chunks, 9 papers |
| 4 done papers missing from Chroma | All 5 done papers in Chroma |
| check-chroma-links: CLEAN | check-chroma-links: CLEAN (0 missing, 0 orphaned) |

The 9 papers in Chroma include 4 pending papers from prior embedding runs; this is correct —
those papers' chunks are already linked to valid KS doc_ids.

---

## JIT Cache Diagnostic Result

**UNPROVEN. Must be verified inside Docker before first Batch A parse.**

- Host environment: both `TORCHINDUCTOR_CACHE_DIR` and `TRITON_CACHE_DIR` are unset.
- The diagnostic instructions are in the runbook "JIT Cache Persistence (WP-2)" section.
- Cold-start risk: 27–50 min per new format group on first paper per Docker session.
- If cache is not persistent, mounting a host volume for `~/.triton` is the fix.
- **Batch A is not blocked by this** — the 5 small papers may complete in a single session
  before cache persistence matters. But runtime planning should budget for a potential
  27–50 min cold-start on the first paper.

---

## Runbook Stale Text Fixed

**Section:** "Corpus Status (as of 2026-05-18)" in `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`.

**Was:** Pre-reset counts (done=5, failed=5, processing=1, pending=18) with "corpus is paused"
heading and three pre-WP-1 blockers.

**Now:** Post-reset heading (2026-05-28), current counts (done=5, failed=0, processing=0,
pending=24), current open items (JIT cache, Tier-3 approval, indexed.jsonl duplicate note),
and 4-batch plan table with paper IDs and timeouts.

---

## Batch A Paper List

Papers eligible for Batch A: small PDFs (≤600KB), ingest_tier=2, no tier3_flag.

| arXiv ID | File size | Timeout |
|----------|-----------|---------|
| 2507.01990 | 219 KB | 3600s |
| 2510.05533 | 524 KB | 3600s |
| 2605.00864 | 541 KB | 3600s |
| 2507.08921 | 582 KB | 3600s |
| 2601.18815 | 588 KB | 3600s |

**Batch A excludes:**
- Tier-3 papers: 1011.6402 (ingest_tier=3, confirmed timeout), 2409.02025 (ingest_tier=3,
  fetch failures)
- tier3_flag papers (large): 2508.03474, 2604.10005, 2403.09267, 2212.12717, 2308.04947,
  2604.20050, 2602.21091 — deferred to Batch C
- All medium papers — deferred to Batch B

**Command:**
```bash
docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
  python -m polytool research-marker-queue \
  --queue-dir /app/artifacts/research/scaled_validation_queue_v2 \
  warm-process --max-items 5 --marker-timeout 3600
```

**After Batch A:** run `index-done` inside Docker (not on Windows host — colon restriction
only applies to opening files for reading body text; the U+F03A fallback in body filenames
means Windows Python can open them, but new body files written by GPU parse inside Docker
will use real colons — stick to Docker for index-done after each batch to be safe):

```bash
docker exec polytool-ris-scheduler-gpu sh -c "cd /app && python -m polytool \
  research-marker-queue \
  --queue-dir /app/artifacts/research/scaled_validation_queue_v2 index-done --json"
```

---

## Batch A Readiness Verdict

| Dimension | Status | Evidence |
|-----------|--------|----------|
| Queue state | PASS | pending=24, done=5, failed=0, processing=0 |
| PDFs cached | PASS | 24/24 prefetched; status-report cached=24, failed=0 |
| Chroma embedding gap | PASS | All 5 done papers embedded; 9 papers, 359 chunks, 0 orphans |
| indexed.jsonl duplicates | HARMLESS | 19 lines, 5 unique; code deduplicates correctly |
| Tier-3 exclusion | PASS | 1011.6402 and 2409.02025 tagged ingest_tier=3; not in Batch A list |
| Runbook stale text | FIXED | "Corpus Status" section updated to post-reset state |
| JIT cache persistence | UNPROVEN | Must run inside-Docker before/after diagnostic; does not block Batch A start but adds runtime uncertainty |

**Overall: PARTIAL PASS — Batch A is ready to schedule with one named caveat.**

The single open caveat is JIT cache persistence. Batch A can start without resolving this —
the 5 small papers may complete in a single Docker session, and the cold-start cost on the
first paper is a one-time overhead, not a blocking failure. If cold-start adds 27–50 min on
paper 1, warm papers 2–5 will still complete in expected ~50–70s each.

**Hard blocks remaining before Batch D (not before Batch A):**
- Operator approval for Tier-3 papers (1011.6402, 2409.02025)

**Stop condition for Batch A:** If >1 paper fails with `marker_timeout` at 3600s, stop and
diagnose before continuing. A single timeout is within expected variance for cold-start.

---

## Codex Review Note

N/A — this is a docs/preflight session only. No implementation code changes were made.
No Codex review triggered.
