---
tags:
  - work-packet
  - ris
  - ingestion
  - academic
date: 2026-04-27
status: ready
priority: high
phase: 2
tracks-affected:
  - RIS-Phase-2A
parent-roadmap: "[[RIS_OPERATIONAL_READINESS_ROADMAP_v1.1]]"
parent-phase: "[[Phase-2-Discovery-Engine]]"
parent-module: "[[RIS]]"
related-decisions:
  - "[[Decision - RIS Evaluation Scoring Policy]]"
  - "[[Decision - RIS n8n Pilot Scope]]"
assignee: architect → Claude Code agent
---

# Work Packet — Academic Pipeline PDF Download Fix

> [!INFO] Scope discipline
> This packet fixes one specific bug: the academic ingest pipeline never downloads PDFs. It does NOT redesign embedding strategy, multi-source ingestion, or pre-fetch relevance filtering. Those are separate work packets that will be informed by the GLM-5 scientific RAG survey currently running. Land this fix first so the pipeline ingests real paper bodies; the broader rework follows once the survey returns.

---

## Context and Motivation

### The bug

Running `python -m polytool research-acquire --url "https://arxiv.org/abs/<id>" --source-family academic` ingests **only the paper's abstract** into ChromaDB and the SQLite knowledge store. The paper body — methods, results, equations, figures, references — is never fetched, never extracted, never embedded.

Verified from code dump (Codex, 2026-04-27):

1. `LiveAcademicFetcher.fetch()` in `packages/research/ingestion/fetchers.py:93` calls the arXiv Atom API (`http://export.arxiv.org/api/query?id_list=<id>`). The Atom API returns metadata only: `title`, `summary` (abstract), `authors`, `published`. The fetcher returns a dict with keys `url, title, abstract, authors, published_date` — **no `body_text` field is ever populated**.

2. `AcademicAdapter.adapt()` in `packages/research/ingestion/adapters.py:89` constructs the document body using:
   ```
   body = body_text if body_text else abstract
   ```
   Since `body_text` is always absent from the academic raw_source dict, `body` is always the abstract.

3. A real `PDFExtractor` class exists in `packages/research/ingestion/extractors.py:327` using pdfplumber. It is functional but **never called from the academic path**. No code wires it to `LiveAcademicFetcher`.

4. `pdfplumber` is **not installed** in the project venv (`ModuleNotFoundError`). Neither is `pypdf`, `pypdf2`, or `arxiv` (the python package).

The PDF capability was scaffolded and abandoned. This packet wires it up.

### Why this matters

- Every academic doc in ChromaDB is currently a 1500-character abstract. The retrieval index has no real paper bodies to retrieve from. RAG queries return abstracts and call them papers.
- The evaluation gate (Gemini Flash) is scoring abstracts — a 200-word summary written for browsing, not the substantive content the score is meant to measure.
- The Phase R0 seed and any subsequent academic ingest has been silently ineffective. The `research-stats` count is misleading — quantity yes, content depth no.
- This is a foundation bug for the entire RIS academic pipeline. Fixing relevance filtering or embedding strategy on top of a broken fetcher is wasted effort.

### Discovery source

Diagnosed from a Codex code-dump session on 2026-04-27 in the Claude Project. Full evidence trail in [[2026-04-27 Academic Pipeline Diagnosis]].

---

## Scope

### In scope

1. **PDF download path in `LiveAcademicFetcher`** — after the Atom API call succeeds, fetch the corresponding PDF, extract its text, and populate `body_text` in the returned dict.
2. **PDF extractor wiring** — the existing `PDFExtractor` in `extractors.py` is reused. It accepts a file path; we add a path that downloads the PDF to a temp file, extracts text, then deletes the temp file. The cached raw payload at `artifacts/research/raw_source_cache/academic/<source_id>.json` continues to store the extracted text inside the JSON so re-ingest does not re-download.
3. **`pdfplumber` install** — added as a real dependency (not optional). Documented in `requirements.txt` and/or `pyproject.toml`.
4. **Failure semantics** — PDF fetch failure or extraction failure must not silently fall back to "abstract only." The fetcher should raise `FetchError` if the abstract is the only content available, OR populate `body_text` with the abstract and tag `metadata.body_source = "abstract_fallback"` so the evaluation and downstream consumers can see what they got. This is a design choice — see Acceptance Criteria for which option.
5. **Logging** — every academic ingest logs the body length and the source ("pdf" vs "abstract_fallback"). Surfaced in the n8n Code-node output so the operator can see at a glance whether a doc was ingested with a real body.
6. **Regression test** — one new test in `tests/test_ris_academic_ingest_v1.py` (or a new file `tests/test_ris_academic_pdf.py`) that mocks the arXiv Atom API and the PDF HTTP fetch, runs the fetcher end-to-end, and asserts `body_text` is the extracted PDF text, not the abstract. Pure offline, no live network.

### Out of scope (don't do list)

- Do NOT add SSRN, OpenReview, Semantic Scholar, NBER, or any non-arXiv source. Multi-source is a separate packet, gated on the GLM-5 survey.
- Do NOT change the chunking strategy. The current `chunk_text()` is naive but works; replacing it is a separate packet.
- Do NOT change embedding model or vector store. ChromaDB + SentenceTransformers stays.
- Do NOT rewrite `AcademicAdapter`. The adapter behavior is correct given a properly-populated `raw_source`. Fix the source, not the consumer.
- Do NOT introduce GROBID, Marker, Nougat, Docling, or any heavy-weight scientific PDF parser. pdfplumber is the right tool for this fix because it is already scaffolded and pure-Python on Windows. A swap to a structural parser is a future packet, again gated on the survey.
- Do NOT add pre-fetch relevance filtering ("is this paper on-topic"). Separate packet.
- Do NOT touch the eval gate, evaluator, or providers. The bug is upstream.
- Do NOT modify `pipeline.py`'s orchestration. The pipeline is correct; only `fetchers.py` and possibly `extractors.py` change.

---

## Technical Design

### URL handling

The arXiv Atom API call already produces a canonical `arxiv_id`. The corresponding PDF URL is deterministic:

```
abs URL: https://arxiv.org/abs/<id>     (or /abs/<id>v<N> for versioned)
PDF URL: https://arxiv.org/pdf/<id>.pdf
```

The existing regex `_ARXIV_URL_ID_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})")` already handles both `/abs/` and `/pdf/` input forms. The fetcher already normalizes to the canonical abs URL after extracting the id. After the Atom call, the fetcher constructs the PDF URL from the same id and downloads it.

### Updated fetch flow

```
1. Extract arxiv_id from input URL                     (existing)
2. Call arXiv Atom API for metadata                    (existing)
3. Parse Atom XML — title, abstract, authors, date     (existing)
4. NEW: Construct PDF URL: https://arxiv.org/pdf/<id>.pdf
5. NEW: Download PDF bytes via _http_fn (same helper as Atom call)
6. NEW: Write PDF to temp file (use tempfile.NamedTemporaryFile)
7. NEW: Run PDFExtractor.extract(temp_path) → ExtractedDocument
8. NEW: Read body from extracted.body
9. NEW: Delete temp file (try/finally)
10. Return raw_source dict with body_text populated
```

The `_http_fn` helper in `fetchers.py` returns bytes — usable directly for both XML and PDF.

### Error handling

Three new failure modes:

1. **PDF download fails** (HTTP error, network issue, 404 for very new papers).
2. **PDF extraction fails** (corrupted PDF, encrypted PDF, image-only scanned PDF with no extractable text).
3. **PDF extraction succeeds but yields suspiciously short body** (<2000 chars typical paper minimum — could indicate an image-only PDF or an extraction failure that didn't raise).

For all three, the fetcher should:

- Log a WARNING with the arxiv_id and the failure reason.
- Set `body_text = abstract` as fallback.
- Set `metadata = {"body_source": "abstract_fallback", "fallback_reason": "<reason>"}`.
- Continue successfully — do NOT raise FetchError. The doc still has metadata value; the evaluation gate will see the short body and likely score it lower, which is correct behavior.

For success:
- Set `metadata = {"body_source": "pdf", "body_length": len(body_text), "page_count": <N>}`.

### Adapter changes

Minor: `AcademicAdapter.adapt()` already reads `metadata` keys via `meta = normalize_metadata(...)`. We extend the metadata it persists onto the `ExtractedDocument`:

```python
metadata = {
    "canonical_ids": meta.canonical_ids,
    "source_type": meta.source_type,
    "publisher": meta.publisher,
    "abstract": abstract[:500] if abstract else "",
    # NEW:
    "body_source": raw_source.get("body_source", "unknown"),
    "body_length": raw_source.get("body_length", 0),
    "page_count": raw_source.get("page_count", 0),
}
```

These flow into the evaluator's `EvalDocument.metadata` and from there into the knowledge store's `metadata_json` column. n8n Code nodes reading from the knowledge store can then surface "ingested with abstract fallback" warnings.

### Dependencies

Add to `requirements.txt` (or wherever active deps are tracked):

```
pdfplumber>=0.10.0
```

`pdfplumber` itself depends on `pdfminer.six` and `pillow`. These are pulled in transitively. No native compilation. Pure-Python on Windows.

The `arxiv` PyPI package is **not** added — we deliberately use the Atom API directly via stdlib `urllib`. The `arxiv` package would be a dependency we don't need.

### Caching behavior

The existing `RawSourceCache.cache_raw()` writes the entire raw_source dict to JSON. After this fix, that JSON includes the extracted PDF text in `body_text`. Re-ingestion of the same arxiv_id reads from cache and does NOT re-download the PDF. This is the correct behavior — already what `cache.has_raw()` enables.

Cache invalidation: not handled in this packet. If a paper is updated on arXiv (new version), the cached body is stale. Versioned arxiv ids (`<id>v2`) are a separate concern — they currently fall through to canonical id without version. This is acceptable for now; a future packet can add version-aware caching.

### Memory and disk

A typical arXiv PDF is 1-5 MB. Downloaded as bytes into memory, written to a temp file, extracted by pdfplumber (which streams pages), then deleted. Peak memory footprint: ~10 MB per fetch. Disk: ephemeral. Cache size grows: extracted text is ~50-200 KB per paper as text — manageable.

### Files to modify

| File | Change | Review level |
|------|--------|-------------|
| `packages/research/ingestion/fetchers.py` | `LiveAcademicFetcher.fetch()` — append PDF download + extraction. `LiveAcademicFetcher.search_by_topic()` — same change applied per result. | Mandatory |
| `packages/research/ingestion/adapters.py` | `AcademicAdapter.adapt()` — propagate `body_source`, `body_length`, `page_count` into metadata. ~5 lines. | Recommended |
| `packages/research/ingestion/extractors.py` | No changes. PDFExtractor is used as-is. | — |
| `requirements.txt` (and/or `pyproject.toml`) | Add `pdfplumber>=0.10.0`. | Mandatory |
| `tests/test_ris_academic_pdf.py` | New file. ≥3 test cases: PDF success, PDF download fail → abstract fallback, PDF extracts to short body → abstract fallback with warning. | Mandatory |
| `tests/fixtures/ris_external_sources/sample.pdf` | New fixture: small canned PDF (a few pages, text-only) for offline tests. | Mandatory |
| `docs/dev_logs/2026-04-XX_ris-academic-pdf-fix.md` | New dev log. Required per repo convention. | Mandatory |

**Execution-critical files NOT touched:** none. This packet does not modify any execution path, kill switch, risk manager, or order-placement logic.

---

## Reference Materials for Architect

### Must read before writing the agent prompt

1. **The Codex code dump from 2026-04-27** — full bodies of `LiveAcademicFetcher`, `AcademicAdapter`, `PDFExtractor`, and the `research-acquire` CLI handler. Located in [[2026-04-27 Academic Pipeline Diagnosis]].
2. **arXiv API terms of use** — `https://info.arxiv.org/help/api/tou.html`. The Atom API and PDF endpoints both have rate limits. Default behavior is one-request-at-a-time per IP. The fetcher must NOT parallelize PDF downloads in this packet. The existing `_http_fn` is synchronous, which is correct.
3. **pdfplumber docs** — `https://github.com/jsvine/pdfplumber`. Confirm `extract_text()` semantics, page handling, and known failure modes.
4. **Existing tests at `tests/test_ris_academic_ingest_v1.py`** — model the new test file's structure on these. The fixture pattern at `tests/fixtures/ris_external_sources/arxiv_sample.json` shows how raw_source dicts are mocked.

---

## Acceptance Criteria

1. **End-to-end real run.** `python -m polytool research-acquire --url "https://arxiv.org/abs/2510.15205" --source-family academic` returns exit 0 and the resulting knowledge-store record's `body_text` length is ≥ 5,000 characters and contains substrings unique to the paper body, not just abstract-page strings.

2. **Abstract fallback identified.** When the PDF download fails (mocked as 404), the ingest still succeeds, `body_text` equals the abstract, and `metadata.body_source == "abstract_fallback"` with a non-empty `fallback_reason`. The acquisition-review JSONL records this.

3. **Cache replay.** Running the same `research-acquire` command twice in a row produces a second invocation that does NOT re-download the PDF (verified via mock counter or log inspection). The cached JSON contains the full extracted body.

4. **Search mode honors the same path.** `python -m polytool research-acquire --search "prediction markets microstructure" --source-family academic --max-results 2` populates `body_text` for each result via the same PDF-download flow.

5. **Existing tests unchanged.** All tests in `tests/test_ris_academic_ingest_v1.py` and `tests/test_ris_research_acquire_cli.py` still pass without modification (backward compat).

6. **New tests pass offline.** New tests in `tests/test_ris_academic_pdf.py` run with no network access. The fixture PDF is small (<100 KB) and committed to the repo.

7. **Dev log written.** `docs/dev_logs/2026-04-XX_ris-academic-pdf-fix.md` exists and describes: changes, test results, remaining limitations (no version handling, no SSRN, no math-aware extraction).

8. **Logging visible to operator.** Each academic fetch logs at INFO level: `academic fetch: arxiv:<id> body_source=pdf body_length=<N> page_count=<P>` or `academic fetch: arxiv:<id> body_source=abstract_fallback reason=<R>`. n8n's Code node can parse this for the structured-output dashboard.

9. **n8n unified-dev workflow re-runs cleanly.** A manual trigger of the academic pipeline in `RIS — Research Intelligence System` succeeds, fetches at least one new paper with body_source=pdf, and the Discord embed shows the structured per-pipeline counts.

---

## Impact on Other Work Packets

- **Existing ChromaDB academic data is now considered low-fidelity.** A separate cleanup task will re-ingest existing arXiv URLs through the fixed pipeline, replacing abstract-only docs with full-body docs. That cleanup is NOT part of this packet — it runs after this packet lands.
- **Phase R0 seed re-run.** The Jon-Becker findings and the Avellaneda-Stoikov / Kelly papers seeded in WP1-D should be re-ingested through the fixed pipeline. Same followup task.
- **Embedding strategy decision.** The GLM-5 scientific RAG survey is running. Once it returns, a follow-up packet will decide on chunking strategy (semantic, structural, parent-document, RAPTOR, late chunking) and may require re-embedding. This packet is forward-compatible: better fetchers do not block better chunkers.
- **Multi-source ingestion.** SSRN, OpenReview, Semantic Scholar, etc. — separate packet, gated on the survey.
- **Pre-fetch relevance filter.** Decide-before-ingest topic gating — separate packet, designed alongside the multi-source work since ingestion volume goes up.

---

## Open Questions for Architect

1. **Failure-mode policy.** Section "Error handling" defaults to abstract-fallback rather than hard-fail. Confirm this matches the eval gate's fail-closed posture. If the operator prefers hard-fail (no doc enters the store unless full body is available), the change is a one-line flip plus updated test expectations.

2. **PDF size cap.** Should the fetcher refuse to download PDFs larger than some threshold (e.g., 50 MB)? Most arXiv papers are <5 MB, but supplementary materials and some books on arXiv can be large. Recommend: 25 MB cap with abstract-fallback on overflow.

3. **Image-only PDF detection.** pdfplumber returns empty text for scanned/image PDFs. The "<2000 chars" heuristic catches this implicitly. Confirm this is acceptable, or specify a more robust detection (e.g., page-count vs body-length ratio).

4. **OCR.** Out of scope per the don't-do list, but worth flagging: scanned papers will fall back to abstract. Approximately <2% of arXiv submissions are image-only, so this is a corner-case, not a primary concern.

---

## Cross-References

- [[RIS]] — module status, current behavior of evaluation/ingestion
- [[RAG]] — knowledge store integration point
- [[Phase-2-Discovery-Engine]] — parent phase
- [[RIS_OPERATIONAL_READINESS_ROADMAP_v1.1]] — authoritative Phase 2A roadmap
- [[Decision - RIS Evaluation Scoring Policy]] — scoring weights affected by body content
- [[Decision - RIS n8n Pilot Scope]] — n8n alerting surface for body_source field
- [[2026-04-27 Academic Pipeline Diagnosis]] — full Codex evidence dump (session note)
