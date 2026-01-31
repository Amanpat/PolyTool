"""Module entrypoint for running PolyTool CLI commands."""

from __future__ import annotations

import sys

from tools.cli.export_clickhouse import main as export_clickhouse_main
from tools.cli.export_dossier import main as export_dossier_main
from tools.cli.rag_index import main as rag_index_main
from tools.cli.rag_query import main as rag_query_main
from tools.cli.scan import main as scan_main


def print_usage() -> None:
    print("Usage: python -m polyttool scan [options]")
    print("       python -m polyttool export-dossier [options]")
    print("       python -m polyttool export-clickhouse [options]")
    print("       python -m polyttool rag-index [options]")
    print("       python -m polyttool rag-query [options]")


def main() -> int:
    if len(sys.argv) < 2:
        print_usage()
        return 1

    command = sys.argv[1]
    if command in ("-h", "--help"):
        print_usage()
        return 0

    if command == "scan":
        return scan_main(sys.argv[2:])
    if command == "export-dossier":
        return export_dossier_main(sys.argv[2:])
    if command == "export-clickhouse":
        return export_clickhouse_main(sys.argv[2:])
    if command == "rag-index":
        return rag_index_main(sys.argv[2:])
    if command == "rag-query":
        return rag_query_main(sys.argv[2:])

    print(f"Unknown command: {command}")
    print_usage()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
