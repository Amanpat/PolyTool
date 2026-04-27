# 2026-04-27 — RIS Marker Core Integration (Layer 1)

## Objective

Add optional `marker-pdf` structured parsing alongside the existing pdfplumber (Layer 0)
path. When Marker is installed, academic PDFs are converted to Markdown with rich structured
metadata. When Marker is absent or fails, the system silently falls back to pdfplumber or
abstract, preserving all Layer 0 semantics.

---

## Files Changed

### `packages/research/ingestion/extractors.py`

- Added `_MARKER_METADATA_SIZE_LIMIT = 20 * 1024 * 1024` module constant (20 MB cap).
- Added `MarkerPDFExtractor(Extractor)` class:
  - `__init__(_marker_modules=None, _enable_llm=False)` — `_marker_modules` is an injectable
    dict for offline tests; `_enable_llm` activates via param or `RIS_MARKER_LLM=1` env var.
  - `_load_marker()` — lazily imports `marker.converters.pdf.PdfConverter`,
    `marker.models.create_model_dict`, `marker.output.text_from_rendered`. Raises
    `ImportError("...install polytool[ris-marker]")` if marker-pdf is absent.
  - `_discover_version()` — reads `importlib.metadata.version("marker-pdf")` for provenance.
  - `extract(source, **kwargs)` — runs Marker converter, strips image binaries from out_meta,
    enforces 20 MB JSON cap (sets `structured_metadata_truncated=True` if exceeded), and returns
    `ExtractedDocument` with `body_source="marker"` (or `"marker_llm_boost"` when LLM flag set),
    `has_structured_metadata=True`, `structured_metadata`, `marker_version`, `page_count`.
  - Registered as `"marker_pdf"` in `EXTRACTOR_REGISTRY`.

### `packages/research/ingestion/fetchers.py`

Extended `LiveAcademicFetcher`:

**New `__init__` parameters:**
- `_pdf_parser: str = "auto"` — resolved from `RIS_PDF_PARSER` env var if set; accepted
  values `auto | pdfplumber | marker`.
- `_marker_extractor_cls = None` — injectable Marker extractor class for tests.
- `_pdfplumber_extractor_cls = None` — injectable pdfplumber extractor class for tests.

**Refactored methods (from single `_fetch_pdf_body`):**
- `_fetch_pdf_body` — outer method, handles PDF download + temp file lifecycle.
- `_parse_pdf(tmp_path)` — dispatcher: routes to `_compat_extract` (legacy injection),
  `_pdfplumber_extract` (explicit pdfplumber), or `_try_marker_or_fallback`.
- `_compat_extract(tmp_path)` — backward-compat path for injected `_pdf_extractor_cls`;
  behavior identical to Layer 0.
- `_try_marker_or_fallback(tmp_path)` — tries Marker; on `ImportError` in `auto` mode falls
  through silently (`body_source="pdf"`); on `ImportError` in `marker` mode or any runtime
  exception (`body_source="pdfplumber_fallback"` + `fallback_reason`). Short Marker output
  (< 200 chars) also triggers fallback.
- `_pdfplumber_extract(tmp_path, fallback_reason)` — runs pdfplumber. If `fallback_reason`
  is set, returns `body_source="pdfplumber_fallback"`; otherwise `body_source="pdf"`.
- `_build_marker_result(body_text, doc_meta)` — assembles meta dict from a successful Marker
  extraction, propagating `marker_version`, `structured_metadata`, `page_count` etc.

### `packages/research/ingestion/adapters.py`

`AcademicAdapter.adapt()`: extended propagation loop to also surface Marker fields in
`doc.metadata`:
- `has_structured_metadata`
- `marker_version`
- `structured_metadata_truncated`

Note: `structured_metadata` (potentially large) is intentionally NOT propagated to
`doc.metadata` (ChromaDB). It persists in the `RawSourceCache` JSON on disk only.

### `pyproject.toml`

Added `ris-marker` optional extra:
```toml
ris-marker = [
    "marker-pdf>=1.0",
]
```

`marker-pdf` is NOT part of `ris` base — keeps the base install free of PyTorch/model deps.

### `tests/test_ris_academic_pdf.py`

Added `import pytest` and 16 new tests across three new classes:

**`TestMarkerPDFExtractorUnit` (6 tests):**
- `test_missing_raises_import_error` — no injection, confirms `ImportError`
- `test_injection_success_body_source_marker` — injected modules, verifies body and metadata
- `test_injection_page_count_in_metadata` — verifies page_count from out_meta
- `test_json_size_cap_truncates` — oversized out_meta → `structured_metadata_truncated=True`
- `test_llm_flag_sets_marker_llm_boost` — `_enable_llm=True` → `body_source="marker_llm_boost"`
- `test_nonexistent_file_raises_file_not_found` — modules injected, path absent

**`TestMarkerFetcherIntegration` (8 tests):**
- `test_marker_success_body_source` — `_pdf_parser="marker"`, success → `body_source="marker"`
- `test_marker_metadata_propagated` — `marker_version` and `structured_metadata` in result
- `test_marker_short_output_falls_back` — < 200 chars triggers fallback
- `test_marker_import_error_explicit_mode` — `_pdf_parser="marker"` + ImportError → `pdfplumber_fallback`
- `test_auto_mode_marker_not_installed_stays_pdf` — auto + ImportError → `body_source="pdf"`
- `test_auto_mode_marker_runtime_error_is_pdfplumber_fallback` — auto + RuntimeError → `pdfplumber_fallback`
- `test_pdfplumber_explicit_mode` — `_pdf_parser="pdfplumber"` → `body_source="pdf"`
- `test_marker_json_size_cap_flagged_in_result` — `structured_metadata_truncated=True` in result

**`TestAcademicAdapterMarkerMetadata` (2 tests):**
- `test_marker_fields_in_doc_metadata` — `has_structured_metadata`, `marker_version` present
- `test_marker_truncated_flag_propagated` — `structured_metadata_truncated=True` in doc.metadata

---

## Dependency Choices

- `marker-pdf>=1.0` in `ris-marker` extra only.
- `ris` base group unchanged (pdfplumber stays the default).
- Marker import is fully lazy: `_load_marker()` runs inside `extract()`, not at module load.
- No GPU required; Marker runs on CPU (slow but functional).

---

## Parser Selection Behavior

| `_pdf_parser` | Marker available | Marker result | `body_source` |
|---|---|---|---|
| `auto` | No (ImportError) | — | `"pdf"` (silent) |
| `auto` | Yes | Success | `"marker"` |
| `auto` | Yes | Exception | `"pdfplumber_fallback"` |
| `auto` | Yes | < 200 chars | `"pdfplumber_fallback"` |
| `marker` | No (ImportError) | — | `"pdfplumber_fallback"` |
| `marker` | Yes | Success | `"marker"` |
| `marker` | Yes | Exception | `"pdfplumber_fallback"` |
| `pdfplumber` | Any | — | `"pdf"` |
| *(legacy `_pdf_extractor_cls`)* | Any | — | `"pdf"` or `"abstract_fallback"` |

Env var `RIS_PDF_PARSER=auto|pdfplumber|marker` overrides the constructor default at runtime.
Env var `RIS_MARKER_LLM=1` activates LLM-boost mode (sets `body_source="marker_llm_boost"`);
disabled by default.

---

## Commands Run

```
python -m pytest tests/test_ris_academic_pdf.py tests/test_ris_academic_ingest_v1.py tests/test_ris_research_acquire_cli.py -v
```

**70 passed, 0 failed.**

```
python -m pytest tests/ -x -q --tb=short
```

**2394 passed, 1 pre-existing failure** (`test_ris_claim_extraction.py::test_each_claim_has_required_fields`
— `actor='heuristic_v2_nofrontmatter' != 'heuristic_v1'`, pre-exists before this change as confirmed by
git stash check).

```
python -m polytool --help
```

CLI loads without errors.

---

## Codex Review

Scope: fetchers.py (strategy-adjacent, Recommended tier), extractors.py (new class, Recommended).
No mandatory files touched. Recommend `/codex:review --background` on fetchers.py.

---

## Known Limitations

- Marker model loading (`create_model_dict()`) is called on every `extract()` call — models
  are not cached across invocations. For bulk use, caller should cache the extractor instance.
- marker-pdf downloads PyTorch model weights on first run (~1–2 GB); not suitable for
  minimal installs.
- `text_from_rendered` API shape is marker-pdf version-specific; the extractor uses
  defensive unpacking (`isinstance(result, tuple)`) to tolerate signature changes.
- No arXiv version-aware cache invalidation (unchanged from Layer 0).
- LLM-boost mode (`RIS_MARKER_LLM=1`) is a flag only; no actual LLM call is wired up.
  Future implementation would need to pass Marker's LLM config here.
