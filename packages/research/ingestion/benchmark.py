"""RIS Phase 2 — extractor benchmark harness.

Compares extractor outputs on a fixture directory of files, recording per-file
timing, character/word counts, and any errors.  Results are written to an
inspectable JSON artifact.

Usage::

    from packages.research.ingestion.benchmark import run_extractor_benchmark

    result = run_extractor_benchmark(
        Path("tests/fixtures/ris_seed_corpus"),
        extractors=["plain_text", "markdown"],
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
    """

    extractor_name: str
    file_name: str
    char_count: int
    word_count: int
    elapsed_ms: float
    error: Optional[str] = None


@dataclass
class BenchmarkResult:
    """Aggregate results from :func:`run_extractor_benchmark`.

    Attributes
    ----------
    metrics:
        Flat list of :class:`ExtractorMetric` objects.
    summary:
        Per-extractor dict with ``success_count`` and ``fail_count``.
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
    ``NotImplementedError`` from stub extractors) is caught and recorded as an
    error metric rather than crashing the run.

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
                metrics.append(ExtractorMetric(
                    extractor_name=extractor_name,
                    file_name=file_path.name,
                    char_count=char_count,
                    word_count=word_count,
                    elapsed_ms=elapsed_ms,
                    error=None,
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
                ))
                summary[extractor_name]["fail_count"] += 1

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
