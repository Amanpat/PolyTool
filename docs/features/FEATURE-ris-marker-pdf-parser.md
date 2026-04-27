# Feature: RIS Marker PDF Parser (Layer 1)

## Summary

Optional structured PDF parsing for the Research Intelligence System (RIS).
When `marker-pdf` is installed, academic PDFs are converted to Markdown with
rich structured metadata. When absent or on failure, the system falls back
silently to pdfplumber (Layer 0), preserving all existing behavior.

---

## Parser Selection

### Default: auto mode

Without any configuration, the fetcher runs in `auto` mode:

| Marker installed? | Result | `body_source` |
|---|---|---|
| No | pdfplumber (silent) | `"pdf"` |
| Yes, success | Marker Markdown | `"marker"` |
| Yes, runtime error | pdfplumber fallback | `"pdfplumber_fallback"` |
| Yes, output < 200 chars | pdfplumber fallback | `"pdfplumber_fallback"` |
| Yes, timeout exceeded | pdfplumber fallback | `"pdfplumber_fallback"` |

### Env var: `RIS_PDF_PARSER`

Override the parser mode at runtime without code changes:

```bash
RIS_PDF_PARSER=auto        # default — marker if installed, else pdfplumber
RIS_PDF_PARSER=pdfplumber  # always pdfplumber, skip Marker even if installed
RIS_PDF_PARSER=marker      # always attempt Marker; fall back if unavailable
```

### LLM boost flag: `RIS_MARKER_LLM`

Reserved for future LLM-enriched extraction. Currently a no-op flag that
sets `body_source="marker_llm_boost"` in metadata for traceability.
**Disabled by default.** Do not enable in production without a working
LLM-boost implementation.

```bash
RIS_MARKER_LLM=1  # sets body_source=marker_llm_boost (no actual LLM call yet)
```

---

## Installation

### Base RIS (default, Docker-safe)

```bash
pip install "polytool[ris]"
```

Includes pdfplumber only. No PyTorch, no model weights. Safe for Docker and
minimal installs. This is what the base Docker image uses.

### With Marker (host/GPU machine)

```bash
pip install "polytool[ris-marker]"
# or from the repo:
python -m pip install -e ".[ris-marker]"
```

Pulls `marker-pdf>=1.0` which depends on PyTorch and surya-ocr. First run
downloads model weights (~1–3 GB) into the local cache
(`~/.cache/datalab/` or `$DATALAB_CACHE_DIR`).

### Verify installation

```bash
python -c "import marker; print('marker import ok')"
python -m polytool research-parser-benchmark --urls 2510.15205 --parsers marker --marker-timeout 60
```

---

## CPU / GPU Notes

- **GPU**: Marker runs significantly faster on CUDA GPUs. Enable via PyTorch's
  standard CUDA installation.
- **CPU**: Marker model loading + inference takes 5–10+ minutes per paper on
  typical laptop CPUs. The default timeout is 300 seconds; tune with
  `_marker_timeout_seconds` in code or `--marker-timeout` in the benchmark CLI.
- **Docker base image**: Marker is deliberately excluded from the base Docker
  image (`.[ris,mcp,...]`). Do not add it there without operator approval —
  it would add ~3–5 GB to the image and requires GPU pass-through for
  acceptable performance.

---

## Parser Benchmark CLI

Compare pdfplumber vs Marker on a set of arXiv PDFs:

```bash
# Quick pdfplumber-only baseline
python -m polytool research-parser-benchmark --parsers pdfplumber

# Compare both with a short marker timeout (shows CPU fallback behavior)
python -m polytool research-parser-benchmark --parsers pdfplumber,marker --marker-timeout 30

# Full run with output artifact
python -m polytool research-parser-benchmark \
  --urls 2510.15205,2309.01454,2206.14965 \
  --parsers pdfplumber,marker \
  --marker-timeout 300 \
  --output-dir artifacts/benchmark/parser
```

Output columns: `body_source`, `body_length`, `section_count` (H1/H2/H3
headers), `table_count`, `equation_block_count`, `equation_inline_count`,
`parse_seconds`, `cache_meta_bytes`.

---

## Metadata Fields

### In `raw_source` (RawSourceCache JSON, disk only)

| Field | Type | Description |
|---|---|---|
| `body_source` | str | Parser used: `pdf`, `marker`, `pdfplumber_fallback`, `abstract_fallback` |
| `body_length` | int | Characters in extracted body |
| `page_count` | int | Page count from parser |
| `has_structured_metadata` | bool | True when Marker produced structured output |
| `marker_version` | str | marker-pdf version string |
| `structured_metadata` | dict | Full Marker output (may be large; cache-only) |
| `structured_metadata_truncated` | bool | True if metadata exceeded 20 MB cap |
| `fallback_reason` | str | Why Marker fell back (if applicable) |

### In `ExtractedDocument.metadata` (propagated to ChromaDB)

All fields above **except** `structured_metadata` (too large for vector store).
An additional compact summary is added:

| Field | Type | Description |
|---|---|---|
| `structured_metadata_summary` | dict | Compact signals: `key_count`, `section_count`, `has_toc` |

---

## Known Limitations (Layer 1)

- **CPU performance**: Marker is slow on CPU (5–10+ min per paper). The 300s
  default timeout causes CPU-mode fallback to pdfplumber for most papers.
  A GPU machine or a cloud-GPU runner is needed for production Marker use.
- **Model caching**: `create_model_dict()` is called per `extract()` call.
  For bulk processing, reuse the extractor instance to amortize model loading.
- **API stability**: `text_from_rendered` return shape is version-specific.
  The extractor uses defensive tuple unpacking to tolerate changes.
- **LLM boost**: `RIS_MARKER_LLM=1` sets the body_source flag only — no
  actual LLM call is wired. This is a Layer 2 deliverable.
- **Retrieval gains**: Structured Markdown improves chunking quality but
  retrieval-quality gains require Layer 2 (structured chunking strategy).
  Do not make retrieval-quality claims based on Layer 1 parser output alone.
- **arXiv cache invalidation**: No version-aware cache invalidation (unchanged
  from Layer 0). Re-ingesting a paper will dedup against the cached version.
