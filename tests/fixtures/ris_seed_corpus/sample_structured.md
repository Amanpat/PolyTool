# Structured Markdown Sample Document

This document is a test fixture for the StructuredMarkdownExtractor. It contains
multiple sections, a Markdown table, a fenced code block, and enough body text to
verify that the extractor preserves all structural elements while also computing
accurate structure metadata counts.

## Section One: Overview

The Research Intelligence System (RIS) ingests external research documents into a
knowledge store. Each document passes through an extractor that converts raw source
material into an ExtractedDocument with a title, body, and metadata.

The extractor abstraction allows different source types to be handled by specialized
implementations. PlainTextExtractor handles flat text and Markdown. The new
StructuredMarkdownExtractor goes further by parsing section headings, tables, and
code blocks to produce richer metadata.

## Section Two: Architecture

The ingestion pipeline consists of four stages:

1. **Extraction** — converts raw source to ExtractedDocument
2. **Hard-stop check** — rejects documents that fail quality criteria
3. **Evaluation gate** — optional scoring pass for relevance/novelty
4. **KnowledgeStore write** — persists document and chunks to SQLite

### Sub-section: Extractor Hierarchy

All extractors inherit from the `Extractor` abstract base class and implement a
single `extract()` method. The factory function `get_extractor(name)` returns an
instantiated extractor from the registry.

## Section Three: Quality Metrics

The benchmark harness compares extractors across a fixture corpus using the following
quality proxy metrics:

| Metric | Description | Type |
|--------|-------------|------|
| char_count | Number of characters in extracted body | int |
| word_count | Whitespace-delimited word count | int |
| section_count | Number of section headings (H1-H6) | int |
| header_count | Total heading lines found | int |
| table_count | Number of Markdown table blocks | int |
| code_block_count | Number of fenced code blocks | int |
| elapsed_ms | Wall-clock extraction time in milliseconds | float |

A structured extractor that produces higher section_count and table_count values
indicates richer metadata extraction from the same source document.

## Section Four: Code Examples

Below is an example of how to use the extractor directly:

```python
from packages.research.ingestion.extractors import get_extractor

extractor = get_extractor("structured_markdown")
doc = extractor.extract("docs/reference/RIS_OVERVIEW.md", source_type="reference_doc")

print(f"Title: {doc.title}")
print(f"Sections: {doc.metadata['section_count']}")
print(f"Tables: {doc.metadata['table_count']}")
print(f"Code blocks: {doc.metadata['code_block_count']}")
```

The returned `ExtractedDocument` has the full Markdown body preserved in `doc.body`
with all structural elements intact. The metadata dict contains computed quality
proxy counts that the benchmark harness uses for comparison.

## Section Five: Reseed Workflow

When extractors are improved, the corpus can be reseeded without creating duplicate
documents. The `--reseed` flag deletes the existing document by source_url before
re-ingesting, so updated metadata is written fresh.

This preserves the deterministic document ID (based on content hash) while replacing
stale extraction metadata with the improved version.
