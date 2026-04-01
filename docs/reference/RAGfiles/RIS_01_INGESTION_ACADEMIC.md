# RIS_01 — Academic Ingestion Pipeline (Pipeline A)
**System:** PolyTool Research Intelligence System  
**Covers:** ArXiv, SSRN, books/ebooks, PDF extraction, manual URL submission

---

## Purpose

Pipeline A ingests structured, high-quality reference material: academic papers, working
papers, and free technical books. These are the highest-confidence sources in the knowledge
base — empirical findings, mathematical derivations, and peer-reviewed analysis that anchor
strategy design decisions.

---

## Sources

### ArXiv (Primary)

**What:** Open-access preprint server for physics, math, CS, quantitative finance, and
statistics. Every major ML and market microstructure paper appears here first.

**Method:** `arxiv` PyPI package (official API wrapper). Search by keyword, fetch metadata
+ abstract, optionally download full PDF for high-scoring papers.

**Rate limit:** 3 requests/second (ArXiv policy — must be respected).

**Topic queries (run on schedule):**
- `"prediction market"` (primary — captures Polymarket-specific research)
- `"market making binary"` (Avellaneda-Stoikov and derivatives)
- `"order flow toxicity"` (adverse selection research)
- `"prediction market microstructure"` (platform mechanics)
- `"sports betting model probability"` (Phase 1C related)
- `"Kelly criterion portfolio"` (position sizing)

**Implementation:**
```python
# packages/research/ingestion/arxiv_ingest.py

import arxiv
from datetime import datetime, timedelta

TOPIC_QUERIES = [
    "prediction market",
    "market making binary",
    "order flow toxicity",
    "prediction market microstructure",
    "sports betting model probability",
    "Kelly criterion portfolio",
]

def fetch_recent_papers(query: str, max_results: int = 50, days_back: int = 30):
    """Fetch recent ArXiv papers matching query."""
    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )
    cutoff = datetime.now() - timedelta(days=days_back)
    papers = []
    for result in client.results(search):
        if result.published.replace(tzinfo=None) < cutoff:
            continue
        papers.append({
            "title": result.title,
            "abstract": result.summary,
            "authors": [a.name for a in result.authors],
            "published": result.published.isoformat(),
            "arxiv_id": result.entry_id.split("/")[-1],
            "pdf_url": result.pdf_url,
            "categories": result.categories,
            "source_type": "arxiv",
            "source_url": result.entry_id,
        })
    return papers
```

**Schedule:** Every 12 hours.

### SSRN (Secondary)

**What:** Social Science Research Network — where finance and economics working papers
appear before journal publication. Contains prediction market efficiency studies,
market microstructure analyses, and quantitative trading research.

**Method:** RSS feeds for relevant categories + `requests` + `BeautifulSoup` for abstract
extraction. SSRN has no official API — scrape gently.

**Rate limit:** 1 request per 5 seconds (respect robots.txt).

**Categories to monitor:**
- Financial Economics
- Market Microstructure
- Derivatives
- Behavioral Finance (prediction market efficiency)

**Schedule:** Every 24 hours.

### Books and Ebooks

**What:** Free technical books under Creative Commons, MIT, or public domain licenses.
Programming references, quantitative trading algorithms, mathematical finance textbooks.

**Sources of free ebooks:**
- Project Gutenberg (public domain — older math/statistics texts)
- MIT OpenCourseWare materials (CC-licensed course notes)
- Open-access textbooks (e.g., "Quantitative Economics with Python" by QuantEcon)
- arXiv-posted book-length manuscripts
- Author-published free PDFs (many quant researchers release their books freely)

**Ingestion approach:**
- One-time curated ingestion (not continuous scraping)
- Operator maintains `config/book_sources.json` with URLs and metadata
- Each book is chunked by chapter/section for embedding
- Full text stored in Chroma; chapters are separate documents linked by `book_id`

**v2 feature — drag-and-drop UI:**
- Local file upload via CLI: `polytool research ingest-book /path/to/book.pdf`
- Future Studio UI: drag-and-drop zone that triggers the ingestion pipeline
- Supports PDF, EPUB (via `ebooklib`), and plain text formats

**Implementation:**
```python
# packages/research/ingestion/book_ingest.py

import json
from pathlib import Path
from ..extraction.pdf_extractor import extract_pdf

def ingest_book(file_path: str, metadata: dict):
    """Ingest a book/ebook into external_knowledge."""
    path = Path(file_path)
    
    if path.suffix.lower() == ".pdf":
        chapters = extract_pdf(file_path, mode="chapters")
    elif path.suffix.lower() == ".epub":
        chapters = extract_epub(file_path)
    elif path.suffix.lower() == ".txt":
        chapters = extract_plaintext(file_path)
    else:
        raise ValueError(f"Unsupported format: {path.suffix}")
    
    book_id = f"book_{path.stem}"
    documents = []
    for i, chapter in enumerate(chapters):
        doc = {
            "text": chapter["text"],
            "title": f"{metadata['title']} — {chapter.get('heading', f'Section {i+1}')}",
            "source_type": "book",
            "source_url": metadata.get("url", f"local:{file_path}"),
            "author": metadata.get("author", "Unknown"),
            "book_id": book_id,
            "chapter_index": i,
            "confidence_tier": metadata.get("confidence_tier", "PRACTITIONER"),
            "freshness_tier": compute_freshness(metadata.get("publish_year")),
        }
        documents.append(doc)
    return documents

def load_book_sources():
    """Load curated book list from config."""
    config_path = Path("config/book_sources.json")
    if config_path.exists():
        return json.loads(config_path.read_text())
    return []
```

**Copyright rule:** Only ingest books that are explicitly free/CC-licensed or where the
author has made the full text publicly available. When in doubt, ingest a curated summary
of key findings instead of full text. The evaluation gate flags this with
`confidence_tier: PRACTITIONER` for author-published and `PEER_REVIEWED` for
formally published open-access texts.

### Manual URL Submission

**What:** Operator submits a specific URL for immediate ingestion and evaluation.

**Method:** `polytool research ingest-url "https://..."` fetches the page, extracts text
via `BeautifulSoup`, normalizes, evaluates, and ingests if passing.

**Use case:** When an LLM fast-research session (GLM-5, Gemini, ChatGPT) surfaces a
valuable source, the operator saves it to the RIS permanently.

---

## PDF Extraction

### The Problem

Academic papers contain complex layouts: multi-column formats, mathematical equations
(LaTeX notation), charts, tables with equations inside them, and specialized notation.
Standard text extraction (PyMuPDF `fitz`) loses structure, mangles equations, and
misses table relationships.

### Recommended Tools (from Research Report 1)

**Primary: MinerU (OpenDataLab)**
- Best overall for multi-column + math + tables
- Explicit support for single-column, multi-column, and complex layouts
- Formula recognition with LaTeX conversion
- Table recognition to HTML with cross-page merging
- Requirements: 6-10 GB VRAM (GPU), 16-32 GB RAM; CPU pipeline available (slower)
- License: AGPL-3.0 (restrictive for commercial; fine for our use)

**Alternative: Marker (VikParuchuri)**
- Strong tables (benchmarked on FinTabNet)
- Equations as LaTeX with `--force_ocr` or `--use_llm` mode
- Ships a "chunks" export mode purpose-built for embedding workflows
- Requirements: ~5 GB VRAM per worker
- License: GPL-3.0 code; model weights free for research/personal/startups under $2M

**Decision:** Start with MinerU for maximum fidelity on quant finance papers. If AGPL
creates issues or MinerU is too resource-heavy for the dev machine (32 GB RAM, 2070 Super
with 8 GB VRAM), fall back to Marker with `--use_llm` mode for improved accuracy.

**Future consideration: Docling (IBM)** — MIT-licensed, strong table extraction, formula
handling, LangChain/LlamaIndex integrations. Chart understanding is "coming soon" on their
roadmap. Worth evaluating when chart extraction becomes important.

### Implementation

```python
# packages/research/extraction/pdf_extractor.py

from pathlib import Path
from typing import Literal

def extract_pdf(
    file_path: str,
    mode: Literal["full", "chapters", "chunks"] = "full",
    tool: Literal["mineru", "marker"] = "mineru",
) -> list[dict]:
    """Extract text from academic PDF using MinerU or Marker.
    
    Args:
        file_path: Path to PDF file
        mode: "full" = one document, "chapters" = split by sections,
              "chunks" = RAG-optimized chunks
        tool: Which extraction tool to use
    
    Returns:
        List of dicts with 'text', 'heading' (if chapters), 'page_range'
    """
    if tool == "mineru":
        return _extract_mineru(file_path, mode)
    elif tool == "marker":
        return _extract_marker(file_path, mode)
    else:
        raise ValueError(f"Unknown tool: {tool}")

def _extract_mineru(file_path: str, mode: str) -> list[dict]:
    """MinerU extraction — best for multi-column + math."""
    # MinerU CLI: magic-pdf -p <file> -o <output_dir> -m auto
    # Outputs: markdown with LaTeX math, HTML tables, reading order
    import subprocess
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            ["magic-pdf", "-p", file_path, "-o", tmpdir, "-m", "auto"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"MinerU failed: {result.stderr}")
        
        # Read the markdown output
        md_files = list(Path(tmpdir).rglob("*.md"))
        if not md_files:
            raise RuntimeError("MinerU produced no output")
        
        text = md_files[0].read_text(encoding="utf-8")
        
        if mode == "full":
            return [{"text": text, "page_range": "all"}]
        elif mode == "chapters":
            return _split_by_headings(text)
        elif mode == "chunks":
            return _split_by_chunks(text, max_tokens=512)

def _extract_marker(file_path: str, mode: str) -> list[dict]:
    """Marker extraction — best for RAG-ready chunks."""
    # Marker has a native chunks export mode
    import subprocess
    import tempfile
    import json
    
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = ["marker_single", file_path, tmpdir, "--output_format"]
        cmd.append("chunks" if mode == "chunks" else "markdown")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Marker failed: {result.stderr}")
        
        if mode == "chunks":
            chunk_files = list(Path(tmpdir).rglob("*.json"))
            if chunk_files:
                chunks = json.loads(chunk_files[0].read_text())
                return [{"text": c["text"], "heading": c.get("heading", "")} 
                        for c in chunks]
        
        md_files = list(Path(tmpdir).rglob("*.md"))
        text = md_files[0].read_text(encoding="utf-8") if md_files else ""
        
        if mode == "full":
            return [{"text": text, "page_range": "all"}]
        elif mode == "chapters":
            return _split_by_headings(text)

def _split_by_headings(text: str) -> list[dict]:
    """Split markdown text by ## headings into chapter chunks."""
    import re
    sections = re.split(r'\n(?=## )', text)
    result = []
    for section in sections:
        lines = section.strip().split('\n', 1)
        heading = lines[0].lstrip('#').strip() if lines else "Untitled"
        body = lines[1].strip() if len(lines) > 1 else ""
        if body:  # skip empty sections
            result.append({"text": body, "heading": heading})
    return result

def _split_by_chunks(text: str, max_tokens: int = 512) -> list[dict]:
    """Split text into RAG-friendly chunks at paragraph boundaries."""
    paragraphs = text.split('\n\n')
    chunks = []
    current = []
    current_len = 0
    
    for para in paragraphs:
        para_len = len(para.split())
        if current_len + para_len > max_tokens and current:
            chunks.append({"text": '\n\n'.join(current)})
            current = [para]
            current_len = para_len
        else:
            current.append(para)
            current_len += para_len
    
    if current:
        chunks.append({"text": '\n\n'.join(current)})
    
    return chunks
```

---

## Content Normalizer

All sources (ArXiv, SSRN, books, manual URLs) produce different formats. The normalizer
converts everything into a standard document format before the evaluation gate:

```python
# Standard document format (output of normalizer)
{
    "text": str,              # Main content (cleaned, normalized)
    "title": str,             # Paper title, book chapter, post title
    "source_type": str,       # "arxiv" | "ssrn" | "book" | "manual"
    "source_url": str,        # Permalink or local path
    "author": str,            # Author name(s)
    "source_publish_date": str,  # ISO 8601 date
    "raw_metadata": dict,     # Source-specific metadata preserved
}
```

The normalizer handles:
- Whitespace normalization (collapse multiple spaces/newlines)
- Encoding cleanup (UTF-8 normalization)
- Reference section stripping (optional — citations lists add noise to embeddings)
- Abstract extraction (for papers — the abstract is a standalone chunk)

---

## CLI Commands

```bash
# Run full academic ingestion cycle
polytool research ingest-academic --max-papers 50

# Ingest specific ArXiv topic
polytool research ingest-academic --topic "prediction markets" --days 30

# Ingest a specific ArXiv paper by ID
polytool research ingest-arxiv 2510.15205

# Ingest a book/ebook
polytool research ingest-book /path/to/book.pdf --title "Market Making" --author "Stoikov"

# Submit a manual URL
polytool research ingest-url "https://coinsbench.com/article"

# List ingested academic documents
polytool research catalog --source-type arxiv --min-score 14
polytool research catalog --source-type book
```

---

## v1 vs v2 Features

| Feature | v1 | v2 |
|---------|----|----|
| ArXiv ingestion | Keyword search, abstract + optional full PDF | Citation graph traversal (find papers cited by high-scoring papers) |
| SSRN ingestion | RSS + abstract scraping | Full PDF download for high-scoring papers |
| Book ingestion | CLI command, curated list | Drag-and-drop UI in Studio, EPUB support |
| PDF extraction | MinerU or Marker | Dual-view pipeline (text + ColPali vision retrieval for charts) |
| Manual URL | CLI command | Studio UI submission form + Discord bot command |
| ArXiv monitoring | Scheduled keyword search | Alert on new papers from tracked authors |

---

## Reference Projects (from Research Report 4)

Projects to reference during implementation (do not adopt wholesale — extract patterns):

- **ArXiv Research Assistant RAG App** — ArXiv scrape + LLM Extract/Filter chains.
  Good pattern for pre-insert gating.
- **Arxiv-RAG-Chatbot** — LangChain ArXiv API → Chroma → chatbot. Simple end-to-end reference.
- **PaperQA (Future-House)** — High-accuracy scientific RAG with LLM-based evidence scoring.
  Best-in-class for report quality. Reference for synthesis engine design.
- **OpenResearcher** — ArXiv corpus + LLM grounded answers. Report generation reference.

---

## Hardware Requirements

On Aman's dev machine (i7-8700K, 32 GB RAM, RTX 2070 Super 8 GB VRAM):

- MinerU: Will run but may be tight on VRAM. Use CPU pipeline mode if GPU is busy
  with other processes (ClickHouse, Docker, Grafana).
- Marker: Comfortable fit at ~5 GB VRAM per worker. Can run alongside other processes.
- Recommendation: Run PDF extraction as a batch job (not concurrent with live bot or
  SimTrader). Process papers one at a time, not in parallel, on this hardware.

---

*End of RIS_01 — Academic Ingestion Pipeline*
