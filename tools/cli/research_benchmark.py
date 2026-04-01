"""CLI entrypoint for RIS Phase 2 extractor benchmark harness.

Usage:
  python -m polytool research-benchmark --help
  python -m polytool research-benchmark --fixtures-dir tests/fixtures/ris_seed_corpus --json
  python -m polytool research-benchmark --fixtures-dir <dir> --extractors plain_text,markdown
  python -m polytool research-benchmark --fixtures-dir <dir> --output-dir artifacts/benchmark/extractor_eval --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list) -> int:
    """Run the extractor benchmark harness.

    Returns:
        0 on success
        1 on argument error or fixtures-dir not found
        2 on unexpected exception
    """
    parser = argparse.ArgumentParser(
        prog="research-benchmark",
        description="Compare extractor outputs on a fixture set.",
    )
    parser.add_argument(
        "--fixtures-dir", dest="fixtures_dir", metavar="PATH",
        default=None,
        help="Directory of fixture files to benchmark. Required.",
    )
    parser.add_argument(
        "--extractors", metavar="LIST",
        default=None,
        help=(
            "Comma-separated list of extractor names to run "
            "(default: all registered extractors). "
            "e.g. plain_text,markdown"
        ),
    )
    parser.add_argument(
        "--output-dir", dest="output_dir", metavar="PATH",
        default=None,
        help="Directory to write benchmark_results.json artifact.",
    )
    parser.add_argument(
        "--json", dest="output_json", action="store_true",
        help="Output raw JSON to stdout instead of human-readable text.",
    )

    args = parser.parse_args(argv)

    if args.fixtures_dir is None:
        parser.print_help(sys.stderr)
        return 1

    fixtures_path = Path(args.fixtures_dir)
    if not fixtures_path.exists() or not fixtures_path.is_dir():
        print(f"Error: --fixtures-dir not found or not a directory: {args.fixtures_dir}", file=sys.stderr)
        return 1

    extractor_names: list[str] | None = None
    if args.extractors:
        extractor_names = [e.strip() for e in args.extractors.split(",") if e.strip()]

    output_dir = Path(args.output_dir) if args.output_dir else None

    try:
        from packages.research.ingestion.benchmark import run_extractor_benchmark
        result = run_extractor_benchmark(
            fixtures_path,
            extractors=extractor_names,
            output_dir=output_dir,
        )
    except Exception as exc:
        print(f"Error: benchmark failed: {exc}", file=sys.stderr)
        return 2

    if args.output_json:
        from dataclasses import asdict
        output = {
            "metrics": [asdict(m) for m in result.metrics],
            "summary": result.summary,
        }
        print(json.dumps(output, indent=2))
    else:
        total = len(result.metrics)
        print(f"Benchmark complete: {total} measurements across {len(result.summary)} extractor(s)")
        print()

        # Per-extractor summary
        for name, stats in sorted(result.summary.items()):
            ok = stats.get("success_count", 0)
            fail = stats.get("fail_count", 0)
            print(f"  {name:<20} success={ok}  fail={fail}")

        print()

        # Detailed table
        col_w = 36
        print(f"{'Extractor':<20} {'File':<{col_w}} {'Chars':>8} {'Words':>6} {'ms':>8} {'Error'}")
        print("-" * 100)
        for m in result.metrics:
            err_str = (m.error or "")[:35]
            file_str = m.file_name[:col_w - 1]
            print(
                f"{m.extractor_name:<20} {file_str:<{col_w}} "
                f"{m.char_count:>8} {m.word_count:>6} {m.elapsed_ms:>8.1f} {err_str}"
            )

        if output_dir:
            print()
            print(f"Artifact written: {output_dir}/benchmark_results.json")

    return 0
