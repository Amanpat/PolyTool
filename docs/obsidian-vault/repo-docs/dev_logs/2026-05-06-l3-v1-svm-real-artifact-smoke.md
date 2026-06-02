---
title: L3 V1 Svm Real Artifact Smoke
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-06_l3-v1-svm-real-artifact-smoke.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# L3 v1 SVM Real-Artifact Smoke Test

Date: 2026-05-06
Author: Claude Code (smoke test + verification pass)
Scope: Default-off SVM integration end-to-end smoke using real trained model artifact.
No implementation code, labels, or model artifacts were modified.

## Verdict

**PASS — integrated but enforce-blocked.**

SVM explicit dry-run and discovery paths execute with the real model artifact. All
required audit fields persist end-to-end. Enforce remains blocked at rc=1 with a
clear message. Labels are unchanged.

---

## 1. Baseline Recorded

**git status --short (selected lines):**
```
 M packages/research/relevance_filter/__init__.py
 M packages/research/relevance_filter/scorer.py
 M polytool/__main__.py
 M pyproject.toml
 M tests/test_ris_prefetch_discovery.py
 M tests/test_ris_research_acquire_cli.py
 M tools/cli/research_acquire.py
 M tools/cli/research_prefetch_discover.py
?? packages/research/relevance_filter/svm_scorer.py
?? packages/research/relevance_filter/svm_training.py
(+ new dev logs and test files)
```

**review counts baseline:**
```json
{
  "total_queued": 62, "pending_unlabeled": 1,
  "labeled_total": 61, "labeled_allow": 30, "labeled_reject": 31
}
```

**labels.jsonl SHA256 (before):** `3940D2FFB1F9F62C2BF65B5A01C33CE3F9BDF7623532916B68F1C5276E6000A2`

---

## 2. SVM Flags Visible on Both CLIs

`python -m polytool research-acquire --help` — confirmed present:
```
--prefetch-filter-mode {off,dry-run,enforce,hold-review}
--prefetch-filter-scorer {lexical,svm}
  svm: trained SVM model — requires --prefetch-svm-model;
  enforce mode is blocked for SVM until >=150 labels and Director approval.
--prefetch-svm-model PATH
--prefetch-svm-metadata PATH
```

`python -m polytool research-prefetch-discover --help` — confirmed present:
```
--filter-scorer {lexical,svm}
  svm: use trained SVM model — requires --svm-model.
--svm-model PATH
--svm-metadata PATH
```

Lexical remains the default scorer on both CLIs.

---

## 3. Artifact Paths Used

- Model: `artifacts/research/svm_filter_models/svm_model_BAAI_bge-large-en-v1.5_42.joblib`
- Metadata: `artifacts/research/svm_filter_models/svm_metadata_BAAI_bge-large-en-v1.5_42.json`

Metadata key fields:
```json
{
  "label_count": 61, "allow_count": 30, "reject_count": 31,
  "train_size": 45, "eval_size": 16, "seed": 42,
  "model_type": "LinearSVC", "embedding_model": "BAAI/bge-large-en-v1.5",
  "metrics": { "accuracy": 1.0, "macro_f1": 1.0 },
  "lexical_baseline_note": "Lexical v1.1 Scenario B: 5.88% off-topic rate"
}
```

---

## 4. Smoke Test A — research-acquire SVM Dry-Run

**Command:**
```
python -m polytool research-acquire \
  --url https://arxiv.org/abs/1802.06101 \
  --source-family academic \
  --dry-run --json \
  --prefetch-filter-mode dry-run \
  --prefetch-filter-scorer svm \
  --prefetch-svm-model artifacts/research/svm_filter_models/svm_model_BAAI_bge-large-en-v1.5_42.joblib \
  --prefetch-svm-metadata artifacts/research/svm_filter_models/svm_metadata_BAAI_bge-large-en-v1.5_42.json \
  --review-dir artifacts/research/svm_filter_smoke
```

**Notes on acquire fetch behavior:** The `research-acquire` academic fetcher downloads
and processes the full PDF with Marker before filter scoring occurs (by design — the full
body is needed for ingestion). Paper `1802.06101` (20 pages) took ~5 minutes for layout
recognition. The `--dry-run` flag prevented caching and ingestion.

**SVM filter output (stderr):**
```
[filter:dry-run] decision=allow score=0.7712 codes=['svm_prediction:allow', 'svm_df:-1.2153', 'svm_allow_confidence:0.7712']
```

**Acquire dry-run JSON output (stdout):**
```json
{
  "source_url": "https://arxiv.org/abs/1802.06101",
  "source_id": "448a58f94241c211",
  "source_family": "academic",
  "normalized_title": "Market Impact in a Latent Order Book",
  "dedup_status": "new",
  "dry_run": true
}
```

Exit code: 0. No ingest, no cache, no review write (per --dry-run).

**Audit record written to `artifacts/research/svm_filter_smoke/filter_decisions.jsonl`:**
```json
{
  "timestamp": "2026-05-06T14:07:25.204482+00:00",
  "source_id": "448a58f94241c211",
  "source_url": "https://arxiv.org/abs/1802.06101",
  "title": "Market Impact in a Latent Order Book",
  "decision": "allow",
  "score": 0.771227,
  "raw_score": -1.215251,
  "allow_threshold": 0.5,
  "review_threshold": 0.35,
  "reason_codes": ["svm_prediction:allow", "svm_df:-1.2153", "svm_allow_confidence:0.7712"],
  "matched_terms": {},
  "config_version": "LinearSVC",
  "input_fields_used": ["title", "abstract"],
  "scorer": "svm",
  "enforced": false,
  "svm_model_name": "BAAI/bge-large-en-v1.5",
  "svm_model_path": "D:\\...\\svm_model_BAAI_bge-large-en-v1.5_42.joblib"
}
```

---

## 5. Smoke Test B — research-prefetch-discover SVM Dry-Run (Primary Audit Field Test)

**Command:**
```
python -m polytool research-prefetch-discover \
  --search "prediction market microstructure" \
  --max-results 5 \
  --dry-run --json \
  --filter-scorer svm \
  --svm-model artifacts/research/svm_filter_models/svm_model_BAAI_bge-large-en-v1.5_42.joblib \
  --svm-metadata artifacts/research/svm_filter_models/svm_metadata_BAAI_bge-large-en-v1.5_42.json \
  --decision-filter all
```

Exit code: 0. No queue writes. Output saved to `artifacts/research/svm_filter_smoke/discovery_dry_run.json`.

**Summary:** 5 papers discovered, all scored as `allow` (expected for "prediction market
microstructure" query against this model trained on trading/markets papers).

**Audit field verification (all 5 records):**

| Field | Value | Present |
|---|---|---|
| `scorer` | `"svm"` | ✓ all 5 |
| `svm_model_name` | `"BAAI/bge-large-en-v1.5"` | ✓ all 5 |
| `svm_model_path` | full absolute path to joblib | ✓ all 5 |
| `svm_random_state` | `42` | ✓ all 5 |
| `svm_lexical_baseline_note` | `"Lexical v1.1 Scenario B: 5.88% off-topic rate"` | ✓ all 5 |

Sample record (abridged):
```json
{
  "source_url": "https://arxiv.org/abs/2604.24366",
  "title": "The Anatomy of a Decentralized Prediction Market: Microstructure Evidence...",
  "score": 0.778667,
  "raw_score": -1.257917,
  "decision": "allow",
  "reason_codes": ["svm_prediction:allow", "svm_df:-1.2579", "svm_allow_confidence:0.7787"],
  "scorer": "svm",
  "svm_model_name": "BAAI/bge-large-en-v1.5",
  "svm_model_path": "D:\\...\\svm_model_BAAI_bge-large-en-v1.5_42.joblib",
  "svm_random_state": 42,
  "svm_lexical_baseline_note": "Lexical v1.1 Scenario B: 5.88% off-topic rate"
}
```

---

## 6. Smoke Test C — Hold-Review via Research-Prefetch-Discover (Blocked by Rate Limit)

Attempted `research-prefetch-discover` with `--queue-path artifacts/research/svm_filter_smoke/smoke_queue.jsonl`
(smoke path, not production). Both attempts returned HTTP 429 from arXiv after 2 prior API calls.

**Assessment:** Rate limiting is a transient external API issue, not a code defect.
The audit fields in the dry-run output (Test B) establish end-to-end field correctness.
The `ReviewQueueStore` write path is exercised by existing tests (52 discovery tests pass).
Hold-review queue write path is not a new code path for SVM — only the queued record
audit fields changed (already verified via dry-run output).

---

## 7. SVM Enforce Blocked

**Command:**
```
python -m polytool research-acquire \
  --url https://arxiv.org/abs/1802.06101 \
  --source-family academic \
  --prefetch-filter-mode enforce \
  --prefetch-filter-scorer svm \
  --prefetch-svm-model artifacts/research/svm_filter_models/svm_model_BAAI_bge-large-en-v1.5_42.joblib
```

**Output (stderr):**
```
Error: SVM enforce is blocked until >=150 labels and Director approval.
Use --prefetch-filter-mode dry-run or hold-review for evidence collection.
```

**Exit code:** 1 (verified). No fetch, no ingest, no model load attempted.

---

## 8. Label Integrity After Smoke Tests

**review counts (post-smoke):**
```json
{
  "total_queued": 62, "pending_unlabeled": 1,
  "labeled_total": 61, "labeled_allow": 30, "labeled_reject": 31
}
```
Unchanged from baseline.

**labels.jsonl SHA256 (after):** `3940D2FFB1F9F62C2BF65B5A01C33CE3F9BDF7623532916B68F1C5276E6000A2`

**Match:** SHA before = SHA after. No labels were modified.

---

## 9. Targeted Test Results

```
python -m pytest tests/test_ris_research_acquire_cli.py tests/test_ris_prefetch_discovery.py tests/test_ris_prefetch_svm_scorer.py -q
```

```
collected 136 items

tests\test_ris_research_acquire_cli.py  42 passed
tests\test_ris_prefetch_discovery.py    52 passed
tests\test_ris_prefetch_svm_scorer.py   42 passed

136 passed in 3.80s
```

No regressions.

---

## 10. Smoke Output Artifacts

All captured under `artifacts/research/svm_filter_smoke/`:
- `filter_decisions.jsonl` — acquire dry-run audit record (SVM fields present)
- `discovery_dry_run.json` — discover dry-run JSON output (5 records, all audit fields present)

No writes to production labels, production review queue, or knowledge store.

---

## 11. Open Items (carry-forward, no new blockers)

1. **SPECTER2 blocked** — `allenai/specter2` AdapterHub/PEFT format incompatibility. Evidence
   run used `BAAI/bge-large-en-v1.5`. Operator must decide: `specter2_base`, `adapters` library,
   or declare bge-large as production model.
2. **Label corpus size** — 61 labels (30 allow / 31 reject); enforce gate requires >=150 before
   any Director approval can unlock it.
3. **research-acquire academic dry-run is slow** — fetches full PDF via Marker (~5 min for 20
   pages) even when only title+abstract are needed for SVM scoring. For iterative smoke testing,
   `research-prefetch-discover --dry-run` is more practical (arXiv metadata-only, no Marker).
   Not a blocking issue — the integration path is correct.
4. **arXiv rate limiting** — 429 after 2 API calls in close succession. Hold-review smoke via
   live API not completed. Non-blocking: dry-run evidence is sufficient; queue write mechanism
   tested by existing test suite.

---

## Codex Review Summary

Tier: Skip (no implementation code changed in this session — smoke test only).
