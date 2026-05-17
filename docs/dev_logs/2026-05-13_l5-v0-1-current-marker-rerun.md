# Dev Log: RIS L5 Benchmark — v0.1 Rerun (Post-L1/L2/L4)

**Date:** 2026-05-13  
**Objective:** Rerun the existing L5 Scientific RAG evaluation benchmark against the current
Marker-indexed academic corpus, create `baseline_v0.1.json`, and compare to `baseline_v0.json`.  
**Scope:** Read-only data rerun. No implementation code changed.

---

## Files Changed

| File | Action | Reason |
|------|--------|--------|
| `artifacts/research/eval_benchmark/baseline_v0.1.json` | **Created** | v0.1 baseline artifact |
| `artifacts/research/eval_benchmark/2026-05-13_benchmark_report.md` | **Created** | Dated Markdown report |
| `artifacts/research/eval_benchmark/2026-05-13_benchmark_report.json` | **Created** | Dated JSON report (source for v0.1) |
| `docs/dev_logs/2026-05-13_l5-v0-1-current-marker-rerun.md` | **Created** | This dev log |

`baseline_v0.json` was **not modified** (confirmed: `run_ts=2026-05-02T20:12:44.074784+00:00`).

---

## Pre-flight Checks

```
git status: clean — nothing to commit
Branch: main
```

```
python -m polytool research-eval-benchmark --help  → help displayed OK
```

KnowledgeStore state at rerun time:
- Total academic records: **74** (was ~23 at v0 time — +51 since L4 harvesters shipped)
- Marker-indexed papers (body_source=marker): **3** new records
  - `2c26902b...` Beating the House: How Inadequate Risk Controls...
  - `a1921b9a...` The Anatomy of a Decentralized Prediction Market
  - `d023674c...` The Impact of COVID-19 on Sports Betting Markets
- These 3 papers are **not** in the 23-paper v0 corpus manifest — they are new KS entries

---

## Commands Run

### Step 1 — Scoped lexical refresh (v0 corpus only)

```
python -m polytool research-eval-benchmark --corpus v0 --refresh-lexical
```

Output:
```
[refresh-lexical] corpus entries: 23
[refresh-lexical] cache_dir: artifacts/research/raw_source_cache/academic
[refresh-lexical] lexical_db: kb/rag/lexical/lexical.sqlite3
[refresh-lexical] resolved 23/23 URLs from KnowledgeStore
[refresh-lexical] found 50 bodies in cache_dir
  [indexed]      b1982ae05e5cd305...  chunks=33
  [indexed]      8cebfdb3f9eb1480...  chunks=27
  [indexed]      e35787572e54d216...  chunks=24
  [indexed]      68acefe962491c08...  chunks=27
  [indexed]      0c8b3c3acdf4e7e0...  chunks=39
  [indexed]      27560f3abe1bede0...  chunks=35
  [indexed]      82267d0774e149cc...  chunks=26
  [indexed]      64d01f09fdcb5eaf...  chunks=25
  [indexed]      89b902e6a792a3a8...  chunks=32
  [indexed]      387a457ed0eeb940...  chunks=30
  [indexed]      9495ffda89417b8e...  chunks=9
  [indexed]      af8935f6dc477ff0...  chunks=47
  [indexed]      40fd58b73a73b54d...  chunks=45
  [indexed]      310125723f52bad6...  chunks=14
  [indexed]      6e911b4fbe2c0414...  chunks=21
  [indexed]      4f5c91b1fe0abb14...  chunks=18
  [indexed]      97351df20211559d...  chunks=9
  [indexed]      210dbdc2b5b98b02...  chunks=34
  [indexed]      4a4dfe303eb33546...  chunks=12
  [indexed]      6501fe75fe8496ab...  chunks=4
  [skip:no-body] d744370bac4412c9...  (url=https://arxiv.org/abs/2301.12345)
  [skip:no-body] bad51e5db2b12124...  (url=https://arxiv.org/abs/2105.02782)
  [indexed]      0838c7de30c5bea5...  chunks=39
done — indexed=21, skipped=2 (no_body=2), total_chunks=550, elapsed=2.1s
```

**Delta from v0 refresh:**
- v0 (2026-05-02): indexed=22, skipped=1 (`d744370b` only), total_chunks=567
- v0.1 (today):   indexed=21, skipped=2 (`d744370b` + `bad51e5d`), total_chunks=550
- **`bad51e5d`** (The Homogenous Properties of Automated Market Makers) is now skipped — its
  raw body cache file is absent. The KnowledgeStore still records it as chunk_count=1, unknown.
- **`0838c7de`** (High frequency market microstructure noise estimates, "the stub") now has
  body text in `raw_source_cache/academic/` and was indexed with 39 chunks. However, its
  KnowledgeStore entry still shows `chunk_count=1, body_source=unknown` — the KS metadata
  was not re-ingested/updated. This is a KS state discrepancy (see Open Questions below).

### Step 2 — Full benchmark run (no --save-baseline to protect baseline_v0.json)

```
python -m polytool research-eval-benchmark --corpus v0 --golden-set v0 \
  --json --output-dir artifacts/research/eval_benchmark
```

Output summary:
```
Reports written:
  Markdown: artifacts/research/eval_benchmark/2026-05-13_benchmark_report.md
  JSON:     artifacts/research/eval_benchmark/2026-05-13_benchmark_report.json

Recommendation: [A] Pre-fetch relevance filtering (Layer 3)
  High off-topic rate suggests pre-fetch filtering needed
  - Rule A: off_topic_rate=30.43% > 30%
  - Rule D: 100.0% of equation_heavy docs not parseable > 30%

Corpus size:        23 documents
QA review status:   reviewed
Off-topic rate:     30.43%
Fallback rate:      0.0%
Retrieval P@5:      1.0
Median chunk count: 25.0
```

### Step 3 — Create baseline_v0.1.json

`--save-baseline` is hardcoded to write `baseline_v0.json` (no v-tag parameter). To avoid
overwriting the locked baseline, `baseline_v0.1.json` was created by copying the dated JSON
report and adding provenance fields (`_baseline_tag`, `_parent_baseline`, `_rerun_reason`).
No code was changed.

```python
report = json.load(open('artifacts/research/eval_benchmark/2026-05-13_benchmark_report.json'))
v01 = dict(report)
v01['_baseline_tag'] = 'v0.1'
v01['_parent_baseline'] = 'baseline_v0.json'
v01['_rerun_reason'] = 'Post-L1/L2/L4 rerun against same 23-paper v0 corpus; Marker pipeline shipped'
json.dump(v01, open('artifacts/research/eval_benchmark/baseline_v0.1.json', 'w'), indent=2)
```

### Step 4 — JSON validity check

```
python -c "import json; json.load(open('artifacts/research/eval_benchmark/baseline_v0.1.json'))"
→ VALID
```

---

## Test/Results Summary

| Test | Result |
|------|--------|
| `pytest tests/ -k "eval_benchmark or research_eval"` | **86 passed** |
| Full test suite (`pytest tests/ -q --tb=no`) | 5123 passed, 1 skipped, **3 pre-existing failures** |
| `python -m polytool --help` | OK |
| `baseline_v0.json` unchanged | Confirmed (run_ts=2026-05-02) |
| `baseline_v0.1.json` created | Valid JSON, `_baseline_tag=v0.1` |

**Pre-existing failures (not introduced today — zero code changes):**
All 3 failing tests are in `tests/test_ris_phase4_source_acquisition.py::TestEndToEnd`:
- `test_ingest_external_arxiv_fixture`
- `test_ingest_external_with_cache`
- `test_ingest_external_metadata_canonical_ids_preserved`

Failure cause: `academic_marker_gate: body_source='abstract' with body_length=0 is not
Marker-quality` — the test fixtures use abstract-only bodies and the gate now rejects them.
This failure was introduced by the `academic pipeline complete` commit (`03c9546`, pre-session)
and is pre-existing. It is NOT caused by today's work.

---

## baseline_v0 vs baseline_v0.1 Comparison

| Metric | v0 (2026-05-02) | v0.1 (2026-05-13) | Delta |
|--------|-----------------|-------------------|-------|
| **Run date** | 2026-05-02 | 2026-05-13 | +11 days |
| **Corpus size** | 23 | 23 | 0 |
| KnowledgeStore total (academic) | ~23 | 74 | +51 |
| Marker-indexed papers in KS | 0 | 3 | +3 |
| **M1 Off-topic rate** | 30.43% (7/23) | 30.43% (7/23) | **0** |
| **M2 Body source pdf%** | 86.96% | 86.96% | **0** |
| **M2 Body source marker%** | 0% | 0% | **0** |
| **M3 Fallback rate** | 0.0% | 0.0% | **0** |
| **M4 Chunk median** | 25.0 | 25.0 | **0** |
| **M4 Chunk mean** | 22.35 | 22.35 | **0** |
| **M5 Low-chunk suspicious records** | 3 | 3 | **0** |
| **M6 Retrieval P@5** | 1.0 | 1.0 | **0** |
| **M6 Answer correctness rate** | 11.43% (4/35) | 11.43% (4/35) | **0** |
| **M7 Citation traceability** | 11.43% (4/35) | 11.43% (4/35) | **0** |
| **M8 Exact hash dupes** | 0 | 0 | **0** |
| **M8 Title dupes** | 1 | 1 | **0** |
| **M9 Eq-heavy not parseable** | 8/8 (100%) | 8/8 (100%) | **0** |
| **Recommendation** | **A** | **A** | unchanged |
| Rules fired | A + D | A + D | unchanged |
| Lexical: indexed papers | 22 | 21 | -1 |
| Lexical: skipped (no body) | 1 | 2 | +1 |
| Lexical: total chunks | 567 | 550 | -17 |

**All 9 benchmark metrics are numerically identical to v0.**

---

## Interpretation

### Why metrics are unchanged

The 23-paper v0 corpus manifest lists exactly the same papers as before. L1 (Marker),
L2 (academic query), and L4 (harvesters) shipped 51 new KS entries and 3 Marker-indexed
papers — but none of those are in the v0 corpus manifest. The benchmark reads corpus
metrics from the KnowledgeStore (`chunk_count`, `body_source`) for the 23 listed papers,
and those KS entries are unchanged.

This means: **the v0.1 rerun is a stability validation, not a delta signal.** The corpus
that was evaluated is the same corpus. What changed is the surrounding KnowledgeStore
(now 74 papers) and the lexical index refresh behavior.

### Lexical index delta explained

- `bad51e5d` (The Homogenous Properties of Automated Market Makers): previously indexed
  with 1 chunk from an abstract-stub body; body cache file was deleted or never saved to
  the path the scoped refresh expects. Now skipped in the lexical refresh. KS entry is
  still chunk_count=1, unknown.
- `0838c7de` (High frequency market microstructure noise estimates, "the stub copy"):
  body text appeared in `raw_source_cache/academic/` between v0 and today — this paper was
  likely re-acquired via `research-acquire`. The lexical refresh indexed it with 39 chunks.
  However, the KnowledgeStore entry was NOT updated (still chunk_count=1, unknown). This is
  a KS desync: body exists in raw_source_cache but KS metadata has not been refreshed.

Neither of these changes affects the 9 benchmark metrics (which read from KS, not the
raw cache). They do not affect P@5 since none of the 35 QA pairs target those two stubs.

---

## Recommendation

**[A] Pre-fetch Relevance Filtering (Layer 3)** — unchanged from v0.

Both Rule A (off_topic_rate=30.43% > 30%) and Rule D (100% eq-heavy not parseable) remain
active. Interpretation from v0 is unchanged:
- Rule A: 7/23 papers are off-topic; 3 were intentional outlier entries. Pre-fetch relevance
  filtering is the correct next step.
- Rule D: heuristic limitation of pdfplumber text extraction; not an actionable blocker.
  Do not treat Rule D as priority above Recommendation A.

---

## Decisions Made

1. **No code changes**: `--save-baseline` is hardcoded to `baseline_v0.json`. Rather than
   modifying the CLI, `baseline_v0.1.json` was created by augmenting the dated JSON report
   with provenance metadata. This avoids any risk of altering the benchmark tool behavior.
2. **Same corpus manifest**: The v0.1 rerun uses the same 23-paper corpus. An alternative
   would have been to expand to all 74 papers, but that would not be a comparable rerun —
   it would be a v1 baseline requiring a new golden QA set.
3. **Feature doc not updated**: The feature doc
   (`docs/features/FEATURE-ris-scientific-eval-benchmark-v0.md`) was NOT updated. It
   describes the v0 baseline run and its locked state (2026-05-02). Benchmark reruns produce
   new versioned artifacts; the feature doc tracks the feature contract, not individual run
   results. This dev log and `baseline_v0.1.json` are the canonical record.

---

## Open Questions

1. **KS desync for `0838c7de`**: The raw body cache now has this paper's full text (39 chunks
   in lexical DB), but the KnowledgeStore still shows `chunk_count=1, body_source=unknown`.
   Should a `research-marker-queue index-done` or manual re-acquire be run to sync the KS
   entry? This is a maintenance item, not a blocker.

2. **`bad51e5d` body cache missing**: The body for The Homogenous Properties of Automated
   Market Makers is gone from raw_source_cache. Was it intentionally deleted? Should it be
   re-acquired? Currently harmless (no QA pairs target it).

3. **v0 corpus expansion for v1 baseline**: The 74-paper KS now includes 3 Marker-indexed
   papers and many new academic papers from L4 harvesters. A v1 baseline that covers the full
   74-paper KS would require: (a) updating the corpus manifest to 74 entries with categories,
   (b) adding QA pairs covering the new papers, (c) operator review of the new QA pairs.
   This is the correct next step after Recommendation A (pre-fetch filtering) is implemented.

4. **Marker impact on corpus metrics**: None of the original 23 papers were re-ingested
   through the Marker pipeline. When/if those papers are re-acquired with Marker, their
   `body_source` would change from `pdf` to `marker` and `chunk_count` may change. The v0.1
   benchmark cannot measure this; it requires a targeted re-acquire + re-run.

---

## Codex Review

Tier: Skip (no strategy/execution/WebSocket/ClickHouse code changed).
