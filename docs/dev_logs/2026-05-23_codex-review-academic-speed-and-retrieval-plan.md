# Codex Review - Academic Speed and Retrieval Plan

**Date:** 2026-05-23
**Reviewer:** Codex
**Scope:** Read-only review plus this dev log
**Verdict:** PASS WITH CONCERNS - delay the 29-paper cached rerun and build a speed/observability packet first

---

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/CURRENT_STATE.md`
- `docs/dev_logs/2026-05-23_academic-one-paper-retrieval-quality.md`
- `docs/dev_logs/2026-05-23_academic-processing-speed-diagnosis.md`
- `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`
- Supporting source records referenced by the speed diagnosis:
  - `docs/dev_logs/2026-05-17_academic-validation-smoke-after-triage.md`
  - `docs/dev_logs/2026-05-17_academic-scaled-validation-batch2-rerun.md`
  - `docs/dev_logs/2026-05-18_academic-ris-operational-triage.md`
  - `docs/dev_logs/2026-05-19_academic-prefetch-separation-wp1.md`
  - `docs/dev_logs/2026-05-22_academic-prefetch-wp1-5paper-e2e.md`
  - `docs/dev_logs/2026-05-22_academic-prefetch-wp1-cached-e2e-closeout.md`
- Read-only architecture checks:
  - `packages/research/synthesis/academic_query.py`
  - `packages/research/ingestion/retriever.py`
  - `packages/research/ingestion/pipeline.py`
  - `packages/research/ingestion/marker_queue.py`
  - `tools/cli/research_marker_queue.py`

---

## Evidence Checked

### Startup / repo-state checks

Command:

```powershell
git status --short
```

Key output:

```text
?? docs/dev_logs/2026-05-23_academic-one-paper-retrieval-quality.md
?? docs/dev_logs/2026-05-23_academic-processing-speed-diagnosis.md
M docs/obsidian-vault/.obsidian/graph.json
...
```

Interpretation: the two source dev logs were untracked before this review. There is also a large unrelated dirty `docs/obsidian-vault/` change set. I did not touch those files.

Command:

```powershell
git log --oneline -5
```

Output:

```text
76db8a1 docs(ris): WP-1 cached PDF E2E closeout - PASS
22f9201 fix(ris): POSIX path separator in prefetch_pdfs for Docker/Linux compatibility
50775d1 feat(ris): WP-1 academic PDF prefetch separation
1fb000d Academic Pipeline Improvements/Testing
de72208 docs(ris): academic pipeline scaled validation - Batch 1 execution record
```

Command:

```powershell
python -m polytool --help
```

Result: exited 0 and listed the current CLI, including `research-marker-queue` and `research-query`.

### One-paper retrieval evidence

Command:

```powershell
python -m polytool research-stats summary
```

Key output:

```text
[Knowledge Store]
  Documents : 131  (by family: academic=80  blog=24  book=1  book_foundational=11  external_knowledge=7  github=5  manual=3)
  Claims    : 1598
```

This matches the one-paper retrieval log's aggregate KS state.

Command:

```powershell
python -m polytool research-query --question "language model"
```

Key output:

```json
{
  "question": "language model",
  "citations": [
    {
      "title": "The New Quant: A Survey of Large Language Models in Financial Prediction and Trading",
      "arxiv_id": "2510.05533",
      "paper_score": 0.7,
      "body_source": "marker",
      "claim_count": 20
    }
  ],
  "total_claims_found": 20,
  "had_fallback": false
}
```

Command:

```powershell
python -m polytool research-query --question "temporal leakage"
```

Key output:

```json
{
  "question": "temporal leakage",
  "citations": [
    {
      "title": "The New Quant: A Survey of Large Language Models in Financial Prediction and Trading",
      "arxiv_id": "2510.05533",
      "paper_score": 0.7,
      "body_source": "marker",
      "claim_count": 3
    }
  ],
  "total_claims_found": 3,
  "had_fallback": false
}
```

Command:

```powershell
python -m polytool research-query --question "benchmark evaluation"
python -m polytool research-query --question "language model financial prediction"
python -m polytool research-query --question "quantitative finance neural network"
python -m polytool research-query --question "weather forecast"
```

Key outputs:

```json
{"question":"benchmark evaluation","citations":[],"total_claims_found":0,"had_fallback":true}
{"question":"language model financial prediction","citations":[],"total_claims_found":0,"had_fallback":true}
{"question":"quantitative finance neural network","citations":[],"total_claims_found":0,"had_fallback":true}
{"question":"weather forecast","citations":[],"total_claims_found":0,"had_fallback":true}
```

Command:

```powershell
python -m polytool research-query --question "LLM"
```

Key output:

```json
{
  "question": "LLM",
  "had_fallback": false,
  "marker_only_count": 4,
  "total_claims_found": 21,
  "citations": [
    {"title": "Closed-form approximations in multi-asset market making", "claim_count": 1},
    {"title": "The New Quant: A Survey of Large Language Models in Financial Prediction and Trading", "claim_count": 11},
    {"title": "High-frequency market-making with inventory constraints and directional bets", "claim_count": 7},
    {"title": "A mean-field game of market-making against strategic traders", "claim_count": 2}
  ]
}
```

This does not support the source log's specific claim that `LLM` returns `had_fallback=True` in the current KS. It does support the deeper concern: abbreviations are not semantically expanded. The current substring matcher can also produce noisy false positives, for example matching `LLM` inside unrelated words such as `Bellman`.

SQLite inspection via Python because `sqlite3` CLI is not installed:

```powershell
@'
import sqlite3, json
con = sqlite3.connect('kb/rag/knowledge/knowledge.sqlite3')
cur = con.cursor()
rows = cur.execute("SELECT id,title,source_family,chunk_count,source_url,metadata_json FROM source_documents WHERE source_url LIKE '%2510.05533%' OR title LIKE '%New Quant%'").fetchall()
print('rows', len(rows))
for doc_id, title, family, chunks, source_url, meta_json in rows:
    meta = json.loads(meta_json)
    print(doc_id, title, family, chunks, meta.get('body_source'), meta.get('body_length'), source_url)
    print('claims', cur.execute('SELECT COUNT(*) FROM derived_claims WHERE source_document_id=?', (doc_id,)).fetchone()[0])
'@ | python -
```

Output:

```text
rows 1
987d4883fd8bde918201993abe5ad17b84b592dd5c331a33d9c5caa104c70577 The New Quant: A Survey of Large Language Models in Financial Prediction and Trading academic 34 marker 93720 https://arxiv.org/abs/2510.05533
claims 167
```

Conclusion: the one-paper retrieval log is materially supported for indexed state, simple topic hits, multi-word phrase failures, fixed `paper_score=0.7`, and snippet artifacts. It is not fully supported for the literal `LLM -> had_fallback=True` example against the current KS.

### Speed diagnosis evidence

The timing table is mostly traceable to source logs and artifacts.

Command:

```powershell
Select-String -Path artifacts/research/scaled_validation_queue_v2/results.jsonl -Pattern '1105.3115|1705.01446|1106.5040|1605.01862|2307.14129|1011.6402|2409.02025|parse_seconds|marker_timeout|fetch_failed'
```

Key observed outputs:

```text
arxiv:1105.3115 ... "parse_seconds":2376.57 ... "marker_ready":true
arxiv:1106.5040 ... "parse_seconds":2772.88 ... "marker_ready":true
arxiv:1605.01862 ... "parse_seconds":1974.73 ... "marker_ready":true
arxiv:1705.01446 ... "parse_seconds":2364.55 ... "marker_ready":true
arxiv:2307.14129 ... "parse_seconds":2947.09 ... "marker_ready":true
arxiv:1011.6402 ... "parse_seconds":3600.01 ... "failure_reason":"marker_timeout: extraction timed out after 3600.0s"
arxiv:2409.02025 ... HTTP 429 / timeout fetching failures
```

Command:

```powershell
Select-String -Path artifacts/research/smoke_test_queue/results.jsonl -Pattern '2510.05533|1106.5040|1810.04383|1609.03471|parse_seconds|marker_timeout'
```

Key observed outputs:

```text
arxiv:1106.5040 ... "parse_seconds":2771.28 ... "marker_ready":true
arxiv:1810.04383 ... "parse_seconds":3279.44 ... "marker_ready":true
arxiv:1609.03471 ... "parse_seconds":53.25 ... "marker_ready":true
arxiv:2510.05533 ... "parse_seconds":12.48 ... "marker_ready":true
```

`rg` checks found the cited 5-paper WP-1 stress results in `docs/dev_logs/2026-05-22_academic-prefetch-wp1-5paper-e2e.md`:

```text
arxiv:1206.4810 parse_s=1309 PASS
arxiv:2203.13053 parse_s=3196 PASS
arxiv:1011.6402 parse_s=3600 Timeout x3
arxiv:2307.14129 killed after prior 3600s/7200s timeout evidence
arxiv:2409.02025 killed after prior 7200s timeout evidence
```

The diagnosis is evidence-based for:

- arXiv fetch/rate-limit failures before WP-1
- WP-1 fixing fetch/parse separation
- eq-heavy papers taking tens of minutes
- prose/survey and table-light papers being fast when warm
- timeout risk for `1011.6402`, `2307.14129`, and `2409.02025`
- `TORCHINDUCTOR_CACHE_DIR` not proving cross-session cache persistence

Concern: the 12-20 hour full-run projection and "5-8 format groups" are extrapolations from partial runs, not a measured 29-paper cached run. They are reasonable planning estimates, but should not be treated as direct benchmark output.

### Architecture fit

Relevant current architecture:

- `academic_query.py` explicitly says L2 does not query ChromaDB yet and uses KnowledgeStore academic rows only.
- `retriever.py` filters claims with case-insensitive substring matching: `query_lower in claim_text.lower()`.
- `pipeline.py` enforces the academic Marker gate: `body_source == "marker"` and `body_length >= 5000`.
- `marker_queue.py` indexes only `queue_status=done` and `marker_ready=True`; pdfplumber, abstract fallback, marker failed, and short Marker bodies are rejected.
- `research-marker-queue --help` exposes `enqueue`, `prefetch`, `warm-process`, `status-report`, etc., but no `--tier` or auto-timeout flag today.

Architecture verdict:

- The proposed **timeout/status/observability** packet matches current architecture.
- Adding `ingest_tier` metadata to the queue can fit because queue records already carry metadata and status-report already summarizes queue state.
- A default Tier 2 / Marker path preserves the current production rule.
- Tier 0 metadata-only KS indexing and Tier 1 pdfplumber/text-layer indexing do **not** match the current canonical academic RAG gate unless they are stored outside the Marker-ready corpus or clearly marked non-canonical. Implementing those as canonical `research-query` sources would contradict the current architecture.

---

## Contradictions Found

1. **`LLM` probe contradiction**
   - Source log says `LLM -> had_fallback=True`.
   - Current command returns `had_fallback=false` with 4 citations and 21 claims.
   - Underlying issue remains: substring retrieval does not understand abbreviations and can produce false positives.

2. **CURRENT_STATE vs speed diagnosis**
   - `docs/CURRENT_STATE.md` WP-1 section says: "29-paper rerun: Safe to proceed. Use `--marker-timeout 14400` for eq-heavy papers."
   - The speed diagnosis says the next full 29-paper run is conditional and recommends JIT cache investigation plus Tier 3 handling first.
   - Verdict: CURRENT_STATE is stale or over-broad after the 2026-05-23 speed diagnosis.

3. **Runbook stale corpus-status language**
   - `RIS_MARKER_QUEUE_RUNBOOK.md` says the 29-paper corpus is paused until WP-1 ships, and once WP-1 ships the full rerun can proceed.
   - WP-1 has shipped, but newer evidence identifies unresolved JIT persistence and timeout-insoluble paper risks.
   - Verdict: runbook needs a short update before operator execution.

4. **Runbook performance table underestimates dense math**
   - The runbook still says "Dense math/ML paper (25-46 pages) | ~60-70s warm."
   - Observed eq-heavy timings are 1975s-3279s in the scaled/smoke artifacts.
   - Verdict: this is misleading for 29-paper planning and should be corrected.

5. **Tiered ingestion policy vs Marker-only gate**
   - Tier 0 and Tier 1 as canonical KS/RAG sources would conflict with current `body_source=marker` gate.
   - The safe next packet is queue metadata, auto-timeout, status visibility, and Tier 3 approval handling only. Do not implement pdfplumber or metadata-only canonical academic RAG without a separate architecture decision.

No conflicts found with the high-level CLAUDE.md / AGENTS.md rules as long as the next packet stays CLI-first, docs/runbook-based, and does not alter canonical academic RAG quality gates silently.

---

## Verdict

**PASS WITH CONCERNS.**

Do **not** proceed directly to the full 29-paper cached run now.

Recommended option: **delay and build speed/observability packet first.**

Reason:

- Retrieval is not operator-demo-ready. The one-paper path proves basic queryability, but current L2 is substring-only and brittle for abbreviations, multi-word conjunctions, and ranking.
- The speed bottleneck is real and evidence-backed. Eq-heavy parses take 33-55 minutes in observed artifacts; three specific papers have timeout or timeout-like evidence.
- The full 29-paper rerun is operationally fragile without knowing whether JIT cache persists across Docker restarts.
- Running the full batch now would likely consume a long uninterrupted GPU window while still leaving ambiguous failure causes for hard papers.
- A 3-paper category sample is less useful as the immediate next step because prior 3-paper and 4-paper validations already proved functional flow. The unresolved risk is not basic functionality; it is full-batch speed, timeout policy, and observability.

---

## Recommended Next Action

Build **WP-2A: Academic Marker Speed/Observability Guardrail Packet** before the 29-paper rerun.

Minimum scope:

1. Investigate JIT cache persistence with `TRITON_CACHE_DIR` plus existing `TORCHINDUCTOR_CACHE_DIR`.
2. Add or document per-paper timeout classification in `status-report` before parse:
   - file size bucket
   - known timeout-risk ID
   - recommended timeout
   - Tier 3/operator-approval flag for known hard papers
3. Update `RIS_MARKER_QUEUE_RUNBOOK.md` to remove the stale "WP-1 shipped means rerun can proceed" implication and correct dense math timing expectations.
4. Keep canonical RAG ingestion unchanged: Tier 2 Marker remains the only production academic RAG path.
5. After WP-2A, run a small targeted validation only if needed:
   - one prose/survey cached paper
   - one known eq-heavy paper
   - one known timeout-risk/Tier 3 paper, or explicitly skip it

Then decide whether the 29-paper rerun is a 3-5 hour viable run or a longer dedicated batch requiring manual skip/approval decisions.

---

## Codex Review Summary

Tier: docs / operational plan review.

Issues found:

- Current source logs are mostly evidence-backed.
- One `LLM` retrieval example is contradicted by current CLI output.
- CURRENT_STATE and runbook language are stale relative to the speed diagnosis.
- Tier 0 / Tier 1 canonical ingestion would conflict with the Marker-only academic RAG gate.

Issues addressed:

- No source docs were edited in this review. This log records the independent verdict and next recommended packet.
