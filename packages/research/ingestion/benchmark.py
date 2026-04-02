"""RIS Phase 2 — extractor benchmark harness.

Compares extractor outputs on a fixture directory of files, recording per-file
timing, character/word counts, and any errors.  Results are written to an
inspectable JSON artifact.

Phase 3 enhancement: quality proxy metrics (section_count, header_count,
table_count, code_block_count, extractor_used) are populated from
ExtractedDocument metadata when available.

Usage::

    from packages.research.ingestion.benchmark import run_extractor_benchmark

    result = run_extractor_benchmark(
        Path("tests/fixtures/ris_seed_corpus"),
        extractors=["plain_text", "structured_markdown"],
        output_dir=Path("artifacts/benchmark/extractor_eval"),
    )
    print(result.summary)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class ExtractorMetric:
    """Per-file, per-extractor measurement.

    Attributes
    ----------
    extractor_name:
        Registry key of the extractor used (e.g. ``"plain_text"``).
    file_name:
        Filename only (not the full path).
    char_count:
        Number of characters in the extracted body (0 on error).
    word_count:
        Number of whitespace-delimited words in the extracted body (0 on error).
    elapsed_ms:
        Wall-clock time for the ``extract()`` call in milliseconds.
    error:
        Exception message if extraction raised; None on success.
    section_count:
        Number of section headings found (populated from metadata when extractor
        provides structural analysis, e.g. StructuredMarkdownExtractor).
    header_count:
        Total heading lines found (populated from metadata, same source as
        section_count for Markdown extractors).
    table_count:
        Number of Markdown table blocks detected (populated from metadata).
    code_block_count:
        Number of fenced code blocks detected (populated from metadata).
    extractor_used:
        The extractor registry key used for this measurement (mirrors
        extractor_name; provided for downstream JSON consumers).
    """

    extractor_name: str
    file_name: str
    char_count: int
    word_count: int
    elapsed_ms: float
    error: Optional[str] = None
    section_count: int = 0
    header_count: int = 0
    table_count: int = 0
    code_block_count: int = 0
    extractor_used: str = ""


@dataclass
class BenchmarkResult:
    """Aggregate results from :func:`run_extractor_benchmark`.

    Attributes
    ----------
    metrics:
        Flat list of :class:`ExtractorMetric` objects.
    summary:
        Per-extractor dict with ``success_count``, ``fail_count``,
        ``avg_section_count``, ``avg_header_count``, and
        ``total_table_count``.
    """

    metrics: list[ExtractorMetric] = field(default_factory=list)
    summary: dict[str, dict] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

# File extensions considered supported by each extractor for matching purposes.
# The benchmark always attempts all files against all requested extractors
# and records errors gracefully — this mapping is only used for filtering
# when a caller wants per-type runs (future extension).
_EXTENSION_HINTS: dict[str, set[str]] = {
    "plain_text": {".txt", ".md", ".rst", ".csv", ".log"},
    "markdown": {".md", ".markdown"},
    "structured_markdown": {".md", ".markdown"},
    "pdf": {".pdf"},
    "docx": {".docx", ".doc"},
}

# Extensions that are skipped entirely (binary non-text assets, etc.)
_SKIP_EXTENSIONS: set[str] = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".bin"}


def run_extractor_benchmark(
    fixture_dir: "str | Path",
    *,
    extractors: list[str] | None = None,
    output_dir: "str | Path | None" = None,
) -> BenchmarkResult:
    """Run the extractor benchmark on all files in *fixture_dir*.

    For each (extractor, file) combination, the extractor's ``extract()`` is
    called and the result is measured.  Any exception (including
    ``NotImplementedError`` from stub extractors or ``ImportError`` from
    optional-dep extractors) is caught and recorded as an error metric rather
    than crashing the run.

    Quality proxy metrics (section_count, header_count, table_count,
    code_block_count) are populated from ``ExtractedDocument.metadata``
    when the extractor provides structural analysis
    (e.g. ``StructuredMarkdownExtractor``).  Plain extractors leave these at 0.

    Parameters
    ----------
    fixture_dir:
        Directory of files to benchmark.  Searched recursively.
    extractors:
        List of registry keys to benchmark (default: all registered extractors).
    output_dir:
        If given, ``benchmark_results.json`` is written there.

    Returns
    -------
    BenchmarkResult
    """
    from packages.research.ingestion.extractors import EXTRACTOR_REGISTRY, get_extractor

    fixture_path = Path(fixture_dir)
    if not fixture_path.is_dir():
        raise ValueError(f"fixture_dir is not a directory: {fixture_path}")

    extractor_names = extractors if extractors is not None else list(EXTRACTOR_REGISTRY.keys())

    # Collect all files (non-recursive for flat fixture dirs, but also handles subdirs)
    all_files = sorted(
        p for p in fixture_path.rglob("*")
        if p.is_file() and p.suffix.lower() not in _SKIP_EXTENSIONS
    )

    metrics: list[ExtractorMetric] = []
    summary: dict[str, dict] = {
        name: {"success_count": 0, "fail_count": 0}
        for name in extractor_names
    }

    for extractor_name in extractor_names:
        try:
            extractor = get_extractor(extractor_name)
        except KeyError:
            # Unknown extractor name — record a synthetic error for all files
            for file_path in all_files:
                metrics.append(ExtractorMetric(
                    extractor_name=extractor_name,
                    file_name=file_path.name,
                    char_count=0,
                    word_count=0,
                    elapsed_ms=0.0,
                    error=f"Unknown extractor: {extractor_name}",
                    extractor_used=extractor_name,
                ))
                summary.setdefault(extractor_name, {"success_count": 0, "fail_count": 0})
                summary[extractor_name]["fail_count"] += 1
            continue

        for file_path in all_files:
            t0 = time.perf_counter()
            try:
                doc = extractor.extract(file_path, source_type="manual")
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                char_count = len(doc.body)
                word_count = len(doc.body.split())

                # Extract quality proxy metrics from metadata if available
                meta = doc.metadata
                section_count = int(meta.get("section_count", 0))
                header_count = int(meta.get("header_count", 0))
                table_count = int(meta.get("table_count", 0))
                code_block_count = int(meta.get("code_block_count", 0))

                metrics.append(ExtractorMetric(
                    extractor_name=extractor_name,
                    file_name=file_path.name,
                    char_count=char_count,
                    word_count=word_count,
                    elapsed_ms=elapsed_ms,
                    error=None,
                    section_count=section_count,
                    header_count=header_count,
                    table_count=table_count,
                    code_block_count=code_block_count,
                    extractor_used=extractor_name,
                ))
                summary[extractor_name]["success_count"] += 1
            except Exception as exc:
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                metrics.append(ExtractorMetric(
                    extractor_name=extractor_name,
                    file_name=file_path.name,
                    char_count=0,
                    word_count=0,
                    elapsed_ms=elapsed_ms,
                    error=str(exc),
                    extractor_used=extractor_name,
                ))
                summary[extractor_name]["fail_count"] += 1

    # Compute per-extractor quality proxy aggregates
    for extractor_name in extractor_names:
        extractor_metrics = [m for m in metrics if m.extractor_name == extractor_name and m.error is None]
        n = len(extractor_metrics)
        if n > 0:
            avg_section_count = sum(m.section_count for m in extractor_metrics) / n
            avg_header_count = sum(m.header_count for m in extractor_metrics) / n
            total_table_count = sum(m.table_count for m in extractor_metrics)
        else:
            avg_section_count = 0.0
            avg_header_count = 0.0
            total_table_count = 0
        summary.setdefault(extractor_name, {"success_count": 0, "fail_count": 0})
        summary[extractor_name]["avg_section_count"] = avg_section_count
        summary[extractor_name]["avg_header_count"] = avg_header_count
        summary[extractor_name]["total_table_count"] = total_table_count

    result = BenchmarkResult(metrics=metrics, summary=summary)

    # Write artifacts if output_dir requested
    if output_dir is not None:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        artifact_path = out_path / "benchmark_results.json"
        artifact_data = {
            "metrics": [asdict(m) for m in metrics],
            "summary": summary,
        }
        artifact_path.write_text(json.dumps(artifact_data, indent=2), encoding="utf-8")

    return result
