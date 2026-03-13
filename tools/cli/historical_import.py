"""Bulk historical import CLI v0.

CLI: python -m polytool import-historical <subcommand> [options]

Subcommands:
  validate-layout   Check that a local data directory has the expected layout
                    for a given source kind. Dry-run -- no import, no ClickHouse.
  show-manifest     Generate and print a provenance manifest for a local dataset.
  import            Import data into ClickHouse (dry-run, sample, or full mode).

Source kinds:
  pmxt_archive        Hourly L2 Parquet snapshots from archive.pmxt.dev
  jon_becker          72.1M-trade dataset (s3.jbecker.dev/data.tar.zst, MIT)
  price_history_2min  2-minute price history via polymarket-apis PyPI

Examples:
  python -m polytool import-historical validate-layout \\
      --source-kind pmxt_archive --local-path /data/pmxt

  python -m polytool import-historical show-manifest \\
      --source-kind pmxt_archive --local-path /data/pmxt \\
      --out artifacts/imports/pmxt_manifest.json

  python -m polytool import-historical import \\
      --source-kind pmxt_archive --local-path /data/pmxt \\
      --import-mode dry-run --out artifacts/imports/pmxt_run.json
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from packages.polymarket.historical_import.manifest import (
    ImportRunRecord,
    SourceKind,
    make_import_manifest,
    make_import_run_record,
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
            "Bulk historical import CLI v0.\n\n"
            "Validates, documents, and imports local historical datasets.\n\n"
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

    imp = sub.add_parser(
        "import",
        help="Import data into ClickHouse (dry-run, sample, or full mode).",
    )
    imp.add_argument(
        "--source-kind", required=True, choices=_SOURCE_KIND_CHOICES, metavar="KIND",
        help=f"One of: {', '.join(_SOURCE_KIND_CHOICES)}",
    )
    imp.add_argument("--local-path", required=True, metavar="PATH",
                     help="Local path to the data directory.")
    imp.add_argument(
        "--import-mode", default="dry-run", choices=["dry-run", "sample", "full"],
        metavar="MODE",
        help="Import mode: dry-run (default), sample, or full.",
    )
    imp.add_argument(
        "--sample-rows", type=int, default=1000, metavar="N",
        help="Row limit per file in sample mode (default: 1000).",
    )
    imp.add_argument("--run-id", default=None, metavar="ID",
                     help="Optional run ID. Auto-generated UUID if omitted.")
    imp.add_argument("--snapshot-version", default="", metavar="V",
                     help="Optional version/snapshot label (e.g. '2026-03').")
    imp.add_argument("--notes", default="", metavar="TEXT",
                     help="Optional free-form notes.")
    imp.add_argument("--out", default=None, metavar="PATH",
                     help="Write JSON run record here (optional).")
    imp.add_argument(
        "--ch-host", default=None, metavar="HOST",
        help="ClickHouse host (default: CLICKHOUSE_HOST env or localhost).",
    )
    imp.add_argument(
        "--ch-port", type=int, default=None, metavar="PORT",
        help="ClickHouse port (default: CLICKHOUSE_PORT env or 8123).",
    )
    imp.add_argument(
        "--ch-user", default=None, metavar="USER",
        help="ClickHouse user (default: CLICKHOUSE_USER env or polytool_admin).",
    )
    imp.add_argument(
        "--ch-password", default=None, metavar="PASS",
        help="ClickHouse password (default: CLICKHOUSE_PASSWORD env or polytool_admin).",
    )

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


def _cmd_import(args: argparse.Namespace) -> int:
    from packages.polymarket.historical_import.importer import (
        ClickHouseClient,
        ImportMode,
        run_import,
    )

    mode_str = args.import_mode
    mode = ImportMode(mode_str)

    # Validate layout first
    validator = _VALIDATOR_MAP[args.source_kind]
    val_result = validator(args.local_path)
    if not val_result.valid and mode != ImportMode.DRY_RUN:
        print(f"[import-historical import] Layout validation FAILED — aborting.", file=sys.stderr)
        for e in val_result.errors:
            print(f"  ERROR: {e}", file=sys.stderr)
        print("Fix the errors above and retry, or use --import-mode dry-run to skip.", file=sys.stderr)
        return 1

    # Build CH client for non-dry-run modes
    ch_client = None
    if mode != ImportMode.DRY_RUN:
        ch_host = args.ch_host or os.environ.get("CLICKHOUSE_HOST", "localhost")
        ch_port = args.ch_port or int(os.environ.get("CLICKHOUSE_PORT", "8123"))
        ch_user = args.ch_user or os.environ.get("CLICKHOUSE_USER", "polytool_admin")
        ch_password = args.ch_password or os.environ.get("CLICKHOUSE_PASSWORD", "polytool_admin")
        ch_client = ClickHouseClient(
            host=ch_host, port=ch_port, user=ch_user, password=ch_password
        )

    result = run_import(
        source_kind=args.source_kind,
        local_path=args.local_path,
        mode=mode,
        ch_client=ch_client,
        run_id=args.run_id or None,
        sample_rows=args.sample_rows,
        snapshot_version=args.snapshot_version,
        notes=args.notes,
    )

    run_record = make_import_run_record(
        result,
        snapshot_version=args.snapshot_version,
        notes=args.notes,
    )

    # Print summary
    print(f"[import-historical import]")
    print(f"  source_kind:          {run_record.source_kind}")
    print(f"  import_mode:          {run_record.import_mode}")
    print(f"  run_id:               {run_record.run_id}")
    print(f"  files_processed:      {run_record.files_processed}")
    print(f"  rows_loaded:          {run_record.rows_loaded}")
    print(f"  rows_skipped:         {run_record.rows_skipped}")
    print(f"  rows_rejected:        {run_record.rows_rejected}")
    print(f"  import_completeness:  {run_record.import_completeness}")
    if run_record.provenance_hash:
        print(f"  provenance_hash:      {run_record.provenance_hash}")

    for w in run_record.warnings:
        print(f"  WARNING: {w}")
    for e in run_record.errors:
        print(f"  ERROR:   {e}", file=sys.stderr)

    if run_record.import_completeness == "dry-run":
        print("\nImport complete (dry-run — no data written to ClickHouse).")
    elif run_record.import_completeness == "complete":
        print(f"\nImport complete ({run_record.rows_loaded} rows loaded).")
    elif run_record.import_completeness == "partial":
        print(
            f"\nImport partial — {run_record.rows_loaded} rows loaded; "
            f"{len(run_record.errors)} error(s).",
            file=sys.stderr,
        )
    else:
        print(f"\nImport FAILED.", file=sys.stderr)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(run_record.to_json(), encoding="utf-8")
        print(f"Run record written: {out_path}", file=sys.stderr)

    success = run_record.import_completeness in ("dry-run", "complete")
    return 0 if success else 1


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
    if args.subcommand == "import":
        return _cmd_import(args)
    print(f"Unknown subcommand: {args.subcommand}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
