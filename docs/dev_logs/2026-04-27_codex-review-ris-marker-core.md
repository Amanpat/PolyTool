# 2026-04-27 Codex Review - RIS Marker Core

## Verdict

PASS WITH FIXES.

The Layer 1 integration is scoped to the academic PDF ingest path, keeps `marker-pdf`
out of the base `ris` extra, imports Marker lazily, and preserves pdfplumber fallback
for import/runtime/short-output failures. Fixes are recommended before Prompt B depends
on adapter-level structured metadata or production Marker execution.

## Files Reviewed

- `pyproject.toml`
- `packages/research/ingestion/fetchers.py`
- `packages/research/ingestion/adapters.py`
- `packages/research/ingestion/extractors.py`
- `tests/test_ris_academic_pdf.py`
- `tests/test_ris_academic_ingest_v1.py`
- `tests/test_ris_research_acquire_cli.py`
- `docs/dev_logs/2026-04-27_ris-marker-core-integration.md`
- `git diff` / `HEAD` scope for Prompt A commit `d2005e6`

## Commands Run

```text
git status --short
```

Output: no output; worktree clean before this review log.

```text
git log --oneline -5
```

Output:
```text
d2005e6 feat(ris): Layer 1 - Marker PDF parser integration with auto/pdfplumber/marker mode
52d77e1 Academic pipeline pdf fix
754174c RIS SYSTEM
d9e9f8b feat(ris): WP3-E - daily digest path at 09:00 UTC with WP3-C structured embed
b2ad984 feat(ris): WP4-B -- hourly n8n execution metrics collector workflow
```

```text
python -m polytool --help
```

Output: exit 0; CLI help loaded and listed `research-acquire`.

```text
git diff --stat
```

Output: no output; Prompt A is committed, so review used `git show HEAD`.

```text
git show --stat --name-status --oneline HEAD
```

Output:
```text
d2005e6 feat(ris): Layer 1 - Marker PDF parser integration with auto/pdfplumber/marker mode
A docs/dev_logs/2026-04-27_ris-marker-core-integration.md
M packages/research/ingestion/adapters.py
M packages/research/ingestion/extractors.py
M packages/research/ingestion/fetchers.py
M pyproject.toml
M tests/test_ris_academic_pdf.py
```

```text
rg -n "marker|Marker|body_source|fallback_reason|structured|page|section|ris-marker|research-acquire" ...
```

Output: failed locally with `Program 'rg.exe' failed to run: Access is denied`; review used PowerShell `Select-String` and `git show` instead.

```text
python -m pytest tests/test_ris_academic_pdf.py tests/test_ris_academic_ingest_v1.py tests/test_ris_research_acquire_cli.py
```

Output:
```text
70 passed in 0.90s
```

```text
python -m polytool research-acquire --help
```

Output: exit 0; help loaded. Options include `--url`, `--search`, `--source-family`, `--dry-run`, `--json`, `--provider`, `--extract-claims`, and `--run-log`.

```text
python -m polytool research-acquire --url "https://arxiv.org/abs/2510.15205" --source-family academic
```

Output:
```text
Acquired: Toward Black Scholes for Prediction Markets: A Unified Kernel and Market Maker's Handbook | family=academic | source_id=aea8351605f4b28c | doc_id=8cebfdb3f9eb... | chunks=27 | dedup=cached
```

```text
python -m pytest tests/ -x -q --tb=short
```

Output:
```text
FAILED tests/test_ris_claim_extraction.py::TestExtractClaimsFromDocument::test_each_claim_has_required_fields
AssertionError: assert 'heuristic_v2_nofrontmatter' == 'heuristic_v1'
==== 1 failed, 2394 passed, 3 deselected, 19 warnings in 66.02s (0:01:06) ====
```

This full-suite failure is outside the Marker diff and matches the pre-existing failure noted in the Prompt A dev log.

## Findings By Severity

### Blocking

None found in dependency hygiene, lazy import, basic pdfplumber fallback, storage cap, or scope guard.

### Non-Blocking Fixes

1. `packages/research/ingestion/adapters.py:140-147` and `tests/test_ris_academic_pdf.py:729-730` - Structured page/section metadata does not flow through adapter metadata.

   `LiveAcademicFetcher` puts `structured_metadata` into raw output at `packages/research/ingestion/fetchers.py:270-271`, but `AcademicAdapter` intentionally omits it from `ExtractedDocument.metadata`, and the test codifies that omission. The review checklist explicitly requires page/section metadata to flow through both raw_source and adapter metadata. Recommended fix: add a bounded, sanitized adapter metadata field for structured page/section data, or a compact `structured_metadata_summary` plus cache reference if full metadata is too large for downstream stores. Update the test to assert the required field instead of asserting absence.

2. `packages/research/ingestion/fetchers.py:203-206` and `packages/research/ingestion/extractors.py:479-481` - Marker execution has no enforced timeout boundary.

   Import/runtime/short-output failures fall back correctly, but a hung Marker model load or conversion call will not raise a timeout and therefore will not reach pdfplumber fallback. Recommended fix: add a Marker extraction timeout, preferably via a killable process boundary or a small runner abstraction, then convert timeout into `TimeoutError` so `_try_marker_or_fallback()` falls back to pdfplumber with `body_source="pdfplumber_fallback"`. Add an offline fake-marker timeout test.

3. `tests/test_ris_academic_pdf.py:456-461` - Optional-dependency absence test assumes Marker is not installed.

   The test passes in the current base environment, but if `polytool[ris-marker]` is installed it will load Marker and then raise `FileNotFoundError` for `/nonexistent/path.pdf` instead of `ImportError`. Recommended fix: simulate Marker import failure with monkeypatch/import hook or skip only this specific absence assertion when Marker is installed. Keep the rest of the tests injection-based and offline.

4. `packages/research/ingestion/fetchers.py:346-357` and `packages/research/ingestion/fetchers.py:446-457` - Fetch logging mislabels Marker and pdfplumber fallback as `abstract_fallback`.

   Metadata is correct, but operator logs say `body_source=abstract_fallback` for any non-`pdf` source, including successful `marker` and `pdfplumber_fallback`. Recommended fix: log `body_meta["body_source"]` dynamically and include `fallback_reason` only when present.

### Informational

- `docs/dev_logs/2026-04-27_ris-marker-core-integration.md:134-151` documents tests and CLI load but not the live `research-acquire --url ...` smoke. This review log documents the live smoke output above.
- `pyproject.toml:63-65` correctly keeps `marker-pdf>=1.0` in `ris-marker` only; it is not in the base `ris` extra.
- `packages/research/ingestion/extractors.py:438-440` imports Marker only inside `_load_marker()`, so module import stays lightweight.
- `packages/research/ingestion/extractors.py:499-515` strips top-level image/binary metadata and enforces a 20 MB JSON cap with a truncation flag.

## Scope Creep Check

PASS. Prompt A touched only:

- RIS academic fetcher/adapter/extractor files
- `pyproject.toml`
- RIS academic PDF tests
- a dev log

No changes were found to chunking, embeddings, retrieval, evaluator/provider chain, n8n workflows, SimTrader, execution, risk, rate limiter, or trading strategy code.

## Prompt B Recommendation

Prompt B should proceed only after the small fixes above are either completed or explicitly accepted as follow-up risk. If Prompt B depends on adapter-level page/section metadata or production Marker execution, fix items 1 and 2 first.
