"""Bulk historical import foundation v0.

CLI: python -m polytool import-historical <subcommand> [options]

Subcommands:
  validate-layout   Check that a local data directory has the expected layout
                    for a given source kind. Dry-run -- no import, no ClickHouse.
  show-manifest     Generate and print a provenance manifest for a local dataset.

Source kinds:
  pmxt_archive        Hourly L2 Parquet snapshots from archive.pmxt.dev
  jon_becker          72.1M-trade dataset (s3.jbecker.dev/data.tar.zst, MIT)
  price_history_2min  2-minute price history via polymarket-apis PyPI

These commands NEVER import data or write to ClickHouse. They are the
validation and provenance layer that precedes bulk import.

Examples:
  python -m polytool import-historical validate-layout \\
      --source-kind pmxt_archive --local-path /data/pmxt

  python -m polytool import-historical validate-layout \\
      --source-kind jon_becker --local-path /data/jbecker

  python -m polytool import-historical show-manifest \\
      --source-kind pmxt_archive --local-path /data/pmxt \\
      --out artifacts/imports/pmxt_manifest.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from packages.polymarket.historical_import.manifest import (
    SourceKind,
    make_import_manifest,
    make_provenance_record,
)
from packages.polymarket.historical_import.validators import (
    validate_jon_becker_layout,
    validate_pmxt_layout,
    validate_price_history_layout,
)

_VALIDATOR_MAP = {
    SourceKind.PMXT_ARCHIVE.value: validate_pmxt_layout,
    SourceKind.JON_BECKER.value: validate_jon_becker_layout,
    SourceKind.PRICE_HISTORY_2MIN.value: validate_price_history_layout,
}

_SOURCE_KIND_CHOICES = sorted(_VALIDATOR_MAP.keys())


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="import-historical",
        description=(
            "Bulk historical import foundation v0.\n\n"
            "Validates and documents local historical datasets before import.\n"
            "Does NOT import data. Does NOT write to ClickHouse.\n\n"
            "Source kinds:\n"
            "  pmxt_archive        archive.pmxt.dev hourly Parquet L2 snapshots\n"
            "  jon_becker          Jon-Becker 72M-trade dataset\n"
            "  price_history_2min  polymarket-apis 2-minute price history"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")

    val = sub.add_parser(
        "validate-layout",
        help="Check local data directory layout (dry-run, no import).",
    )
    val.add_argument(
        "--source-kind", required=True, choices=_SOURCE_KIND_CHOICES, metavar="KIND",
        help=f"One of: {', '.join(_SOURCE_KIND_CHOICES)}",
    )
    val.add_argument("--local-path", required=True, metavar="PATH",
                     help="Local path to the data directory.")

    show = sub.add_parser(
        "show-manifest",
        help="Generate and print a provenance manifest for a local dataset.",
    )
    show.add_argument(
        "--source-kind", required=True, choices=_SOURCE_KIND_CHOICES, metavar="KIND",
        help=f"One of: {', '.join(_SOURCE_KIND_CHOICES)}",
    )
    show.add_argument("--local-path", required=True, metavar="PATH",
                      help="Local path to the data directory.")
    show.add_argument("--snapshot-version", default="", metavar="VERSION",
                      help="Optional version/snapshot label (e.g. '2026-03').")
    show.add_argument("--notes", default="", metavar="TEXT",
                      help="Optional free-form notes to embed in the manifest.")
    show.add_argument("--out", default=None, metavar="PATH",
                      help="Write manifest JSON here (prints to stdout if omitted).")
    return p


def _cmd_validate_layout(args: argparse.Namespace) -> int:
    validator = _VALIDATOR_MAP[args.source_kind]
    result = validator(args.local_path)

    status = "OK" if result.valid else "FAILED"
    print(f"[import-historical validate-layout]")
    print(f"  source_kind: {args.source_kind}")
    print(f"  path:        {args.local_path}")
    print(f"  status:      {status}")
    print(f"  file_count:  {result.file_count}")
    if result.checksum:
        print(f"  checksum:    {result.checksum[:16]}...")
    if result.notes:
        print(f"  notes:       {result.notes}")
    for w in result.warnings:
        print(f"  WARNING:     {w}")
    for e in result.errors:
        print(f"  ERROR:       {e}")
    if result.valid:
        print(
            "\nLayout valid. Run 'show-manifest' to generate a provenance record."
        )
    return 0 if result.valid else 1


def _cmd_show_manifest(args: argparse.Namespace) -> int:
    validator = _VALIDATOR_MAP[args.source_kind]
    val_result = validator(args.local_path)

    status = "validated" if val_result.valid else "staged"
    record = make_provenance_record(
        source_kind=args.source_kind,
        local_path=args.local_path,
        status=status,
        file_count=val_result.file_count,
        checksum=val_result.checksum,
        snapshot_version=getattr(args, "snapshot_version", ""),
        notes=args.notes or val_result.notes,
    )
    manifest = make_import_manifest([record])
    manifest_json = manifest.to_json()

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(manifest_json, encoding="utf-8")
        print(f"[import-historical show-manifest] Manifest written: {out_path}", file=sys.stderr)
        if not val_result.valid:
            print(
                f"[import-historical show-manifest] WARNING: layout validation failed "
                f"({len(val_result.errors)} error(s)); status='staged'",
                file=sys.stderr,
            )
            for e in val_result.errors:
                print(f"  ERROR: {e}", file=sys.stderr)
    else:
        print(manifest_json)
        if not val_result.valid:
            for e in val_result.errors:
                print(f"# ERROR: {e}", file=sys.stderr)

    return 0 if val_result.valid else 1


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.subcommand is None:
        parser.print_help()
        return 0
    if args.subcommand == "validate-layout":
        return _cmd_validate_layout(args)
    if args.subcommand == "show-manifest":
        return _cmd_show_manifest(args)
    print(f"Unknown subcommand: {args.subcommand}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
