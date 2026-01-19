"""Module entrypoint for running PolyTool CLI commands."""

from __future__ import annotations

import sys

from tools.cli.scan import main as scan_main


def print_usage() -> None:
    print("Usage: python -m polyttool scan [options]")


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

    print(f"Unknown command: {command}")
    print_usage()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
