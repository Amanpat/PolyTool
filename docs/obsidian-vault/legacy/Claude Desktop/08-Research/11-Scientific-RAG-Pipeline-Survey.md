---
tags: [research, ris, scientific-rag, survey]
date: 2026-04-27
status: authoritative
source: GLM-5 Scientific RAG Pipeline Survey
related-decisions:
  - "[[Decision - Scientific RAG Architecture Adoption]]"
related-architecture:
  - "[[11-Scientific-RAG-Target-Architecture]]"
---

# 11 — Scientific RAG Pipeline Survey

Source-of-truth document capturing the full GLM-5 survey of open-source projects addressing scientific PDF ingestion, embedding, and retrieval for technical content. Run on 2026-04-27 in response to gaps identified during the academic pipeline diagnosis (see [[2026-04-27 Academic Pipeline Diagnosis]]).

The survey scope was narrow: find existing projects we can copy or adapt, addressing the five specific gaps PolyTool's RIS currently has. The full survey output is preserved here verbatim. The shortlist and adoption decisions are condensed into [[Decision - Scientific RAG Architecture Adoption]]. The four-layer target design synthesizing the survey's "concrete combination" is in [[11-Scientific-RAG-Target-Architecture]].

---

## Survey scope

The survey addressed five gaps:

1. Scientific PDF ingestion that preserves structure (sections, equations, tables, figures, references)
2. Pre-fetch topic filtering — decide a paper is on-topic before downloading and evaluating it
3. Embedding strategies suited to dense technical content with math, not prose
4. Retrieval that returns source handles (PDF page, paragraph, equation ID) not just text chunks
5. Multi-source academic ingestion beyond arXiv (SSRN, OpenReview, Semantic Scholar, NBER, RePEc, direct PDF URLs)

Constraints applied: skip projects with last commit > 18 months ago unless foundational; skip generic LangChain/LlamaIndex examples; skip "chat with one PDF" demos; flag commercial-license issues; flag Linux-only or paid-API dependencies; require evidence the surveyor read README and at least one substantive code file or paper section.

---

## Project survey

### PaperQA2

URL: https://github.com/future-house/paper-qa
Last commit: 2026-03-20 · License: Apache-2.0

End-to-end scientific RAG library: ingests PDFs/text/Office, fetches metadata (citations, retraction checks) from Semantic Scholar/Crossref/Unpaywall, builds a full-text index, then runs an agentic RAG loop (dense retrieval + LLM reranking + contextual summarization) to answer questions with in-text citations.

What it solves for us:
- Scientific PDF ingestion with structure (uses PyMuPDF internally, preserves some structure for citation-aware chunking)
- Pre-fetch topic filtering via paper-level metadata + embedding search
- Embedding/chunking via metadata-aware embeddings and contextual summarization (RCS) tied to document sections and citation spans
- Source handles via citations mapped to specific pages/sections
- Multi-source ingestion via Semantic Scholar, Crossref, Unpaywall

What's not a fit:
- Opinionated pipeline (LiteLLM, OpenAI embeddings by default); swapping to ChromaDB+SQLite hybrid and our evaluation gate requires non-trivial surgery
- Chunking is text-centric, not explicitly math-aware
- Heavy dependency on external APIs

Worth copying:
- Agentic RAG control flow (paper search tool + evidence gatherer + answer synthesis with source handles)
- Metadata-aware embedding + re-ranking + contextual summarization pattern
- Citation-to-source-location mapping logic (page/section IDs)
- Multi-source metadata enrichment patterns

Integration cost: medium — rip out their vector DB and embedding defaults, wire into ChromaDB + SQLite, but RAG control flow and citation logic are reusable.

### Marker

URL: https://github.com/datalab-to/marker
Last commit: 2026-04-24 · License: GPL-3.0 (code), modified AI Pubs Open Rail-M (model weights, commercial restrictions)

PDF→Markdown/JSON/HTML/chunks converter with layout analysis, table detection, inline math/equation formatting (to LaTeX), and image extraction. Optional LLM-boosted mode for better tables, math, forms.

What it solves for us:
- Scientific PDF ingestion preserving sections, tables, equations, inline math, images, reading order
- Embedding strategy: Markdown/JSON output with LaTeX math is much better embedding input than raw PDF text
- Source handles: page ranges and section headers preserved; JSON output includes bounding boxes

What's not a fit:
- GPL-3.0 + custom model license problematic for commercial RIS; commercial license needed for self-hosting or stay in research mode
- Requires PyTorch + GPU for reasonable speed; CPU mode exists but slower
- LLM-boosted mode calls external models (Gemini/Ollama), adding cost and latency

Worth copying:
- Markdown/JSON schemas for tables, equations, sections, images
- LLM-post-processing pattern for cleaning math/tables and merging cross-page structures
- Page/section chunking with metadata

Integration cost: medium — simple API (`marker_single`), but license compliance and possibly wrapping as a service to avoid GPU requirements.

### GROBID (via spp-grobid / s2orc-doc2json)

URL: https://github.com/allenai/spp-grobid (archived), https://github.com/allenai/s2orc-doc2json
Last commit: 2023-03-07 / 2023-08-22 · License: Apache-2.0

GROBID parses scientific PDFs into structured TEI XML (header, references, body sections). s2orc-doc2json wraps GROBID + custom TEI→JSON parser to produce S2ORC JSON, used in Semantic Scholar's large-scale corpus.

What it solves for us:
- Scientific PDF ingestion with structure: sections, title/abstract, structured bibliography, reference markers
- Source handles via TEI XML / S2ORC JSON paragraph and section IDs mapped to PDF pages
- Multi-source ingestion: S2ORC pipeline ingests both PDF and LaTeX sources

What's not a fit:
- spp-grobid archived; current GROBID at kermitt2/grobid is outside the strict 18-month window
- Java-centric and heavy; requires Java server or Docker container, integrate from Python via HTTP
- Math formula handling imperfect; recent benchmarks show inline/display math misparsed in complex layouts

Worth copying:
- TEI XML and S2ORC JSON schemas for representing paper structure
- "Document → structured XML/JSON → RAG-ready chunks" pipeline pattern
- s2orc-doc2json's `grobid2json` and `tex2json` pipelines as reference for arXiv-centric ingestion

Integration cost: high — Java service, extra infrastructure, XML/JSON munging. Conceptually important for structure representation.

### Nougat

URL: https://facebookresearch.github.io/nougat
Last commit: 2024-01 (paper), code through 2024 · License: MIT (code), CC-BY-NC-4.0 (model weights, non-commercial)

Vision transformer that reads a scientific PDF page image and outputs Markdown/LaTeX markup, focusing on mathematical expressions and tables.

What it solves for us:
- Scientific PDF ingestion with structure: targets equations and tables, converts to LaTeX
- Embedding strategy: Markdown+LaTeX output is math-friendly, suitable for math-aware embeddings
- Source handles: page-structured Markdown, page number implicit

What's not a fit:
- Non-commercial license on model weights — cannot be used in commercial RIS without separate license
- Autoregressive decoding is slow (page-by-page, token-by-token), expensive at scale
- No explicit reference/section extraction; still need GROBID for bibliography

Worth copying:
- Idea of treating PDF pages as images and outputting LaTeX for math/tables
- Vision-to-markup model architecture specialized on scientific documents

Integration cost: high — slow inference, license constraints, must combine with other tools for full structure.

### Docling

URL: https://github.com/docling-project/docling
Last commit: 2026-04-17 · License: MIT

Document processing library with advanced PDF understanding (page layout, reading order, tables, code, formulas, image classification), unified DoclingDocument representation, exports to Markdown/HTML/JSON/DocTags.

What it solves for us:
- Scientific PDF ingestion with structure: layout, tables, formulas, code, image classification; unified format
- Embedding strategy: DoclingDocument and DocTags export as Markdown/JSON with structural tags
- Source handles: preserves page layout and bounding boxes; per-element metadata (page, type, bbox)

What's not a fit:
- Stream of PDF-parsing bugs and open issues; edge cases in complex layouts
- Non-trivial dependency stack (multiple ML models, OCR)

Worth copying:
- DoclingDocument schema and DocTags representation
- Enrichment pipeline for formulas, code, tables (`do_formula_enrichment`)
- Table export and structured extraction patterns

Integration cost: medium — clean Python API, but model downloads and parsing bugs to manage.

### PyMuPDF4LLM

URL: https://github.com/pymupdf/pymupdf4llm
Last commit: 2026-04-14 · License: AGPL-3.0

Lightweight PyMuPDF extension converting PDFs to structured Markdown/JSON/text optimized for RAG, with layout analysis, table detection, header/footer removal, hybrid OCR.

What it solves for us:
- Multi-column layouts, reading order, table detection, header/footer removal, hybrid OCR
- Markdown/JSON output with headings, tables, formatting; page-chunking yields chunks with metadata (page, toc, boxes)
- `page_chunks=True` returns chunk dicts with metadata, `toc_items`, `page_boxes`, text

What's not a fit:
- AGPL-3.0 restrictive for commercial service; commercial PyMuPDF Pro license needed or accept AGPL constraints
- No explicit math/equation handling; tables and layout supported, not LaTeX math

Worth copying:
- Layout-aware Markdown/JSON schema and page-chunking pattern
- Hybrid OCR strategy and selective page processing

Integration cost: low — single import API, but license may be a blocker.

### PaperMage

URL: https://github.com/allenai/papermage
Last commit: 2024-11-08 · License: Apache-2.0

Toolkit for processing visually rich scientific documents; provides `Document` object with layers (pages, rows, sentences, sections) and integrates multiple NLP/CV models.

What it solves for us:
- Fine-grained segmentations (pages, rows, sentences, sections) and cross-layer indexing
- Entities (sections, rows, sentences) mapped back to pages/regions with IDs; supports attributed QA

What's not a fit:
- Explicitly marked research prototype with limited maintenance; recommended replacement is Dolma
- Heavy dependency stack and complex install

Worth copying:
- `Document` + `Entity` layer abstraction for representing scientific documents at multiple granularities
- Recipes for core scientific PDF processing and attributed QA

Integration cost: high — unstable maintenance, complex dependencies, but conceptually strong.

### arXiv-Sanity-Lite

URL: https://github.com/karpathy/arxiv-sanity-lite
Last commit: 2022-02 · License: MIT

ArXiv paper recommendation system; polls arXiv API, computes TF-IDF on abstracts, trains SVMs per user tag, recommends papers using SVM + SPECTER embeddings.

What it solves for us:
- Pre-fetch topic filtering: SVMs over TF-IDF and SPECTER embeddings for paper-level on-topic classification
- Embedding strategy: combination of TF-IDF and SPECTER for paper similarity
- Multi-source ingestion: arXiv crawling and indexing at scale; integrates with SPECTER + FAISS

What's not a fit:
- Last commit > 18 months ago; not actively maintained
- ArXiv-only; no SSRN, OpenReview
- Uses older SPECTER, not SPECTER2

Worth copying:
- Pattern: TF-IDF + SPECTER embeddings + SVMs for paper-level relevance filtering
- ArXiv polling and indexing pipeline

Integration cost: low — code is simple and self-contained, but modernize models and APIs.

### Late Chunking (Jina AI)

URL: https://github.com/jina-ai/late-chunking
Last commit: 2024-09 (paper), repo through 2025 · License: Apache-2.0

Method and reference implementation for "late chunking": run a long-context embedding model over the whole document first, then apply mean pooling to segments of the token-vector sequence to get chunk embeddings that retain long-range context.

What it solves for us:
- Embedding strategy for technical content: directly addresses the "context problem" where chunks lose anaphoric references (e.g., "its", "the city" vs. "Berlin") by conditioning chunk embeddings on the full document context
- Works with any long-context transformer embedding model (e.g., Jina embeddings v2/v4)

What's not a fit:
- Evaluated mostly on Wikipedia-style prose, not dense math; needs validation on microstructure/econ papers
- Requires long-context encoder and more memory at indexing time

Worth copying:
- Late-chunking algorithm: encode full doc, then pool over contiguous spans of token vectors
- Reference implementation for embedding pipeline integration

Integration cost: medium — adopt long-context encoder and re-implement pooling, but code is small and clear.

### RAPTOR

URL: https://github.com/parthsarthi03/raptor
Last commit: 2024-2025 (active) · License: MIT

Recursive abstractive tree from documents: embeds and clusters chunks, summarizes clusters, repeats to create a tree of summaries at different granularities; at query time, retrieves from this tree.

What it solves for us:
- Hierarchical multi-scale retrieval over long documents — useful for papers requiring both detail and high-level context (methodology vs. conclusions)
- Source handles: each tree node corresponds to a cluster of chunks; can propagate handles up the tree

What's not a fit:
- Relies on OpenAI-style APIs for summarization and QA; need to swap in our LLM endpoint (Gemini/Ollama)
- No special handling for math or equations; abstractions are generic

Worth copying:
- Tree-construction algorithm (embed → cluster → summarize → recurse)
- Abstract `BaseSummarizationModel`, `BaseQAModel`, `BaseEmbeddingModel` interfaces

Integration cost: medium — replace LLM calls and embedding models, but core algorithm is simple and modular.

### ColBERTv2 / PLAID

URL: https://github.com/stanford-futuredata/ColBERT
Last commit: 2022–2024 · License: MIT

Late-interaction neural retrieval: encodes query and documents into multi-token embeddings, computes MaxSim scores; PLAID is the efficient inference engine.

What it solves for us:
- Token-level multi-vector representations capture fine-grained semantics of equations and technical phrases better than single-vector embeddings
- Token-level matches associated with specific spans/lines

What's not a fit:
- Indexing and inference heavier than single-vector models; GPU or well-tuned CPU index needed
- No official scientific-document benchmark; most eval is generic QA

Worth copying:
- Late-interaction retrieval pattern and token-pooling tricks for compressing ColBERT indexes
- PLAID engine design for fast multi-vector retrieval

Integration cost: high — new index format, custom retrieval stack, significant infra investment.

### SciQAG

URL: https://github.com/MasterAI-EAM/SciQAG
Last commit: 2024-07 · License: MIT

Framework for generating science QA pairs from a corpus of papers using LLMs; includes QA generator and evaluator, produces SciQAG-24D dataset over 24 domains.

What it solves for us:
- Benchmark and methodology for evaluating RAG performance on science questions
- QA pairs tied back to papers/sections — model for evidence-grounded QA

What's not a fit:
- Not a RAG engine — a QA-generation and evaluation framework
- Generic science domains, not market microstructure

Worth copying:
- QA generation and evaluation patterns for scientific documents
- Dataset and evaluation protocol for measuring RAG performance on technical content

Integration cost: low — adopt their evaluation design.

### SciDQA

URL: https://github.com/yale-nlp/SciDQA
Last commit: 2024 · License: MIT

Deep reading comprehension dataset over scientific papers; QA pairs sourced from peer reviews and author answers, requiring reasoning across figures, tables, equations, appendices.

What it solves for us:
- Benchmark for evaluating retrieval/comprehension on scientific documents with heavy equations/tables
- Questions require locating evidence in specific sections/figures/equations

What's not a fit:
- Dataset only, not a RAG pipeline

Worth copying:
- Dataset and evaluation protocol for scientific RAG, especially multi-modal evidence

Integration cost: low — primarily a benchmark.

### OpenReview Scraper

URL: https://github.com/pranftw/openreview_scraper
Last commit: 2024 · License: MIT

Scraper for OpenReview conferences (ICML/ICLR/NeurIPS); searches by title/abstract/keywords, extracts metadata and PDF URLs, saves to CSV.

What it solves for us:
- Multi-source academic ingestion: working OpenReview harvester with keyword filtering
- Pre-fetch topic filtering: filters on title/abstract/keywords before downloading PDFs

What's not a fit:
- No PDF downloading logic, only URLs
- No semantic embedding-based filtering, only keywords

Worth copying:
- OpenReview API usage pattern (openreview-py) and keyword-filter architecture

Integration cost: low — simple scraper; add PDF download and session handling.

### OpenReview Finder (SPECTER2 + ChromaDB)

URL: https://github.com/danmackinlay/openreview_finder
Last commit: 2025 · License: MIT

Indexes NeurIPS 2025 papers via OpenReview API, creates SPECTER2 embeddings, builds ChromaDB semantic search index with web UI.

What it solves for us:
- Pre-fetch topic filtering: SPECTER2 embeddings + ChromaDB similarity search for paper-level relevance
- Embedding strategy: SPECTER2 specifically designed for scientific papers
- Multi-source ingestion: shows how to integrate OpenReview API with SPECTER2 and ChromaDB

What's not a fit:
- Conference-specific (NeurIPS 2025); needs generalization to other venues
- No PDF parsing or chunking; focuses on metadata/abstract search

Worth copying:
- SPECTER2 + ChromaDB pipeline for paper-level semantic search and filtering
- CLI patterns for interacting with the index

Integration cost: low — clean Python CLI using `uv`, easy to adapt.

### SSRN scrapers

URL: https://github.com/talsan/ssrn, https://github.com/karthiktadepalli1/ssrn-scraper
Last commit: 2022–2024 · License: MIT / BSD

Scrapes SSRN abstracts and metadata by JEL code or search; downloads abstract pages and sometimes PDFs.

What it solves for us:
- SSRN is a key source for finance/econ working papers
- JEL codes and search keywords as topic filters before full PDF ingestion

What's not a fit:
- SSRN's anti-scraping measures and session-heavy PDF downloads; need redirect/cookie handling
- No official API; scrapers may break if SSRN changes HTML

Worth copying:
- JEL-code based search and pagination patterns
- Session/cookie handling for PDF downloads behind redirects

Integration cost: medium — brittle scrapers needing maintenance, but essential for SSRN coverage.

### NBER scraper

URL: https://github.com/ledwindra/nber
Last commit: 2021–2022 · License: MIT

Scrapes and analyzes NBER working papers; downloads metadata and some PDF content.

What it solves for us:
- NBER is a core source for macro/finance working papers
- Filter by NBER working group or keywords in abstracts

What's not a fit:
- Not maintained recently; may need updates for current site structure
- No math-aware parsing

Worth copying:
- NBER crawling patterns and working-group filters

Integration cost: low — simple scraper; modernize as needed.

### Semantic Scholar API + S2FOS + SPECTER2

URL: https://www.semanticscholar.org/product/api, https://github.com/allenai/s2_fos, https://github.com/allenai/SPECTER2
Last commit: API ongoing; S2FOS and SPECTER2 through 2024 · License: Apache-2.0 / MIT

REST API with paper metadata, citation graph, fields-of-study (S2FOS), SPECTER2 embeddings; S2FOS is a linear SVM over character n-gram TF-IDF for field-of-study classification.

What it solves for us:
- Pre-fetch topic filtering via S2FOS field-of-study labels; SPECTER2 similarity-based pre-filtering to our domain
- Embedding strategy: SPECTER2 trained for scientific papers using citation graph signals
- Multi-source ingestion: S2 API aggregates many publishers and preprint servers

What's not a fit:
- Rate limits and authentication; not self-contained open-source pipeline
- No PDF parsing; still need GROBID/Marker/Docling for full text

Worth copying:
- S2FOS model and training data for our own field classifier
- SPECTER2 embedding pattern for scientific papers

Integration cost: low — API integration, respect rate limits and licensing.

### Unstructured

URL: https://github.com/Unstructured-IO/unstructured
Last commit: 2026-03-16 · License: Apache-2.0

General-purpose document partitioning library; `partition_pdf` extracts elements (narrative text, tables, headers) with metadata.

What it solves for us:
- Tables, headers, sections; elements carry metadata like page numbers and coordinates
- Element metadata (page, coordinates) usable as source handles

What's not a fit:
- No special math/equation handling
- More general-purpose than scientific-specific; may miss some domain structures

Worth copying:
- Partition API and element model
- Table extraction and metadata patterns

Integration cost: low — easy `partition_pdf` call, but domain-specific post-processing for math.

---

## Top 3 recommendations

1. **Marker as primary PDF→structured Markdown/JSON converter.** Best balance of layout, tables, math support; explicitly formats equations and inline math to LaTeX; handles tables and images. Caveat: GPL + model license likely requires commercial license if self-hosted in commercial product.

2. **Adopt PaperQA2's RAG control flow and citation-aware retrieval, wired into our own vector/lexical DB and evaluation gate.** PaperQA2 already solves scientific RAG with metadata-aware embeddings, re-ranking, contextual summarization, and citation-to-page mapping. Copy: agentic loop, citation traversal, source-handle pattern. Replace: default vector DB and embeddings with ChromaDB + SQLite + custom evaluation gate.

3. **Semantic Scholar API + S2FOS + SPECTER2 for pre-filtering and paper-level embeddings, plus arXiv-Sanity-Lite-style SVMs for on-topic classification.** S2FOS gives field-of-study labels; SPECTER2 gives scientific-document embeddings; Semantic Scholar gives multi-source metadata and PDF URLs. Run our LLM evaluation gate only on papers that pass this filter.

### Concrete combination

- Marker for PDF → structured Markdown/JSON (sections, tables, equations, images)
- PaperQA2's RAG algorithm (minus its vector DB) on top of that structured representation, using ChromaDB + SQLite FTS5 + our LLM gate
- Semantic Scholar API + S2FOS + SPECTER2 + arXiv-Sanity-style SVMs for pre-filtering papers before full PDF ingestion and evaluation
- Wrap SSRN/NBER/OpenReview scrapers around this, using S2FOS/keywords for coarse filtering and the evaluation gate for fine-grained decisions

---

## What we should not do

- **Don't adopt Nougat as primary parser in commercial RIS.** Model weights CC-BY-NC-4.0; commercial use restricted. Even ignoring license, autoregressive page-by-page decoding is slow at scale.
- **Don't rely on GROBID alone for math-heavy PDFs.** Recent benchmarks show GROBID misparses inline/display math in complex layouts. Use GROBID for structural metadata; pair with Marker/Docling for math/tables.
- **Don't copy PaperQA2's default OpenAI-centric stack wholesale.** Default uses OpenAI embeddings and LiteLLM; undermines goal of controllable local RIS. Extract algorithm and citation logic; swap in SPECTER2/Jina or our own math-aware encoder.
- **Don't treat ColBERTv2/PLAID as drop-in replacement without cost modeling.** Multi-vector indexes larger and slower to update; significant infra and complexity costs for potentially modest gains. Document-level embeddings like SPECTER2 already perform well.
- **Don't assume Unstructured's generic PDF partitioning is sufficient for math-heavy finance papers.** Handles tables and layout, not LaTeX. Use as fallback for non-math content, not primary parser for microstructure/econ.
- **Don't build multi-source harvesters that ignore SSRN/NBER session and redirect issues.** Naive scrapers will fail or get blocked. Any harvester must explicitly handle sessions, cookies, and retry logic.
- **Don't treat SciQAG/SciDQA as full RAG systems.** They are benchmarks, not RAG pipelines. Use to measure system, not as architectural templates.

---

## Cross-references

- [[2026-04-27 Academic Pipeline Diagnosis]] — bug that triggered this survey
- [[Work-Packet - Academic Pipeline PDF Download Fix]] — the immediate-fix packet (pdfplumber); this survey informs its successors but does not replace it
- [[Decision - Scientific RAG Architecture Adoption]] — operational decision document derived from this survey
- [[11-Scientific-RAG-Target-Architecture]] — four-layer target design synthesized from the "concrete combination"
- [[RIS]] — current module
- [[RAG]] — current module
- [[Phase-2-Discovery-Engine]] — parent phase
