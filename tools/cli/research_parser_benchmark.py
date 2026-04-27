"""CLI — PDF parser benchmark: pdfplumber vs Marker.

Compares pdfplumber and Marker on a set of arXiv PDFs and reports per-paper
quality proxy metrics: body_length, section headers, table markers, equation
markers, parse time, and cache metadata size.

Usage::

    python -m polytool research-parser-benchmark --help
    python -m polytool research-parser-benchmark
    python -m polytool research-parser-benchmark --urls 2510.15205,2309.01454,2401.12345
    python -m polytool research-parser-benchmark --marker-timeout 120 --output-dir artifacts/benchmark/parser
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import time
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

# Default arXiv IDs to benchmark when no --urls provided.
# Chosen to cover: prediction-markets (prose), math-heavy, short paper.
_DEFAULT_ARXIV_IDS = [
    "2510.15205",  # Black-Scholes for Prediction Markets (prose + math)
    "2309.01454",  # arXiv paper with equations
    "2401.00001",  # short prose paper
]

_H1_RE = re.compile(r"^#{1,3}\s+\S", re.MULTILINE)
_TABLE_RE = re.compile(r"^\|", re.MULTILINE)
_EQ_BLOCK_RE = re.compile(r"\$\$|\\\[", re.MULTILINE)
_EQ_INLINE_RE = re.compile(r"\$[^$\n]+\$")


@dataclass
class ParserResult:
    arxiv_id: str
    parser: str
    body_source: str
    body_length: int
    section_count: int
    table_count: int
    equation_block_count: int
    equation_inline_count: int
    parse_seconds: float
    cache_meta_bytes: int
    fallback_reason: str
    error: str


def _count_metrics(text: str) -> dict:
    return {
        "section_count": len(_H1_RE.findall(text)),
        "table_count": len(_TABLE_RE.findall(text)),
        "equation_block_count": len(_EQ_BLOCK_RE.findall(text)),
        "equation_inline_count": len(_EQ_INLINE_RE.findall(text)),
    }


def _run_parser(arxiv_id: str, parser: str, timeout: float) -> ParserResult:
    from packages.research.ingestion.fetchers import LiveAcademicFetcher

    t0 = time.perf_counter()
    try:
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        with urllib.request.urlopen(pdf_url, timeout=30) as resp:
            pdf_bytes = resp.read()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_bytes)
            tmp_path = f.name

        fetcher = LiveAcademicFetcher(
            _pdf_parser=parser,
            _marker_timeout_seconds=timeout,
        )
        body_text, meta = fetcher._parse_pdf(tmp_path)

        elapsed = time.perf_counter() - t0
        body_source = meta.get("body_source", "unknown")
        body_text = body_text or ""
        metrics = _count_metrics(body_text)
        cache_meta = meta.get("structured_metadata")
        cache_meta_bytes = len(json.dumps(cache_meta).encode()) if cache_meta else 0

        try:
            import os
            os.unlink(tmp_path)
        except OSError:
            pass

        return ParserResult(
            arxiv_id=arxiv_id,
            parser=parser,
            body_source=body_source,
            body_length=len(body_text),
            section_count=metrics["section_count"],
            table_count=metrics["table_count"],
            equation_block_count=metrics["equation_block_count"],
            equation_inline_count=metrics["equation_inline_count"],
            parse_seconds=round(elapsed, 2),
            cache_meta_bytes=cache_meta_bytes,
            fallback_reason=meta.get("fallback_reason", ""),
            error="",
        )

    except Exception as exc:
        elapsed = time.perf_counter() - t0
        return ParserResult(
            arxiv_id=arxiv_id,
            parser=parser,
            body_source="error",
            body_length=0,
            section_count=0,
            table_count=0,
            equation_block_count=0,
            equation_inline_count=0,
            parse_seconds=round(elapsed, 2),
            cache_meta_bytes=0,
            fallback_reason="",
            error=str(exc)[:200],
        )


def _print_table(results: list[ParserResult]) -> None:
    header = (
        f"{'arxiv_id':<14} {'parser':<11} {'body_src':<22} "
        f"{'len':>7} {'sec':>4} {'tbl':>4} {'eq_b':>5} {'eq_i':>5} "
        f"{'secs':>6} {'meta_kb':>8}  {'note'}"
    )
    print(header)
    print("-" * len(header))
    for r in results:
        note = r.fallback_reason[:40] if r.fallback_reason else (r.error[:40] if r.error else "")
        print(
            f"{r.arxiv_id:<14} {r.parser:<11} {r.body_source:<22} "
            f"{r.body_length:>7} {r.section_count:>4} {r.table_count:>4} "
            f"{r.equation_block_count:>5} {r.equation_inline_count:>5} "
            f"{r.parse_seconds:>6.1f} {r.cache_meta_bytes // 1024:>8}  {note}"
        )


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="research-parser-benchmark",
        description="Compare pdfplumber vs Marker on arXiv PDFs.",
    )
    parser.add_argument(
        "--urls", metavar="IDS",
        default=None,
        help=(
            "Comma-separated arXiv IDs or full URLs "
            f"(default: {','.join(_DEFAULT_ARXIV_IDS)})"
        ),
    )
    parser.add_argument(
        "--parsers", metavar="LIST",
        default="pdfplumber,marker",
        help="Comma-separated parsers to run (default: pdfplumber,marker).",
    )
    parser.add_argument(
        "--marker-timeout", dest="marker_timeout", type=float, default=300.0,
        metavar="SECS",
        help="Per-paper Marker timeout in seconds (default: 300). Use 30-60 for quick runs.",
    )
    parser.add_argument(
        "--output-dir", dest="output_dir", metavar="PATH",
        default=None,
        help="Write benchmark_parser_results.json to this directory.",
    )
    parser.add_argument(
        "--json", dest="json_out", action="store_true",
        help="Print results as JSON instead of table.",
    )

    args = parser.parse_args(argv)

    # Resolve arXiv IDs
    if args.urls:
        raw_ids = [u.strip() for u in args.urls.split(",")]
        _ID_RE = re.compile(r"(\d{4}\.\d{4,5})")
        arxiv_ids = []
        for raw in raw_ids:
            m = _ID_RE.search(raw)
            arxiv_ids.append(m.group(1) if m else raw)
    else:
        arxiv_ids = _DEFAULT_ARXIV_IDS

    parsers = [p.strip() for p in args.parsers.split(",")]

    print(f"Parser benchmark: {len(arxiv_ids)} paper(s) × {len(parsers)} parser(s)")
    print(f"arXiv IDs : {', '.join(arxiv_ids)}")
    print(f"Parsers   : {', '.join(parsers)}")
    print(f"Marker timeout: {args.marker_timeout}s")
    print()

    results: list[ParserResult] = []
    for arxiv_id in arxiv_ids:
        for p in parsers:
            print(f"  {arxiv_id} / {p} ... ", end="", flush=True)
            r = _run_parser(arxiv_id, p, args.marker_timeout)
            results.append(r)
            status = r.body_source if not r.error else f"ERROR: {r.error[:40]}"
            print(f"{status} ({r.parse_seconds:.1f}s, body={r.body_length})")

    print()

    if args.json_out:
        print(json.dumps([asdict(r) for r in results], indent=2))
    else:
        _print_table(results)

    if args.output_dir:
        out_path = Path(args.output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        artifact = out_path / "benchmark_parser_results.json"
        artifact.write_text(
            json.dumps([asdict(r) for r in results], indent=2),
            encoding="utf-8",
        )
        print(f"\nResults written to {artifact}")

    return 0
