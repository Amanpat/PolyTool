"""Module entrypoint for running PolyTool CLI commands.

This is the canonical CLI entrypoint for PolyTool.
Usage: python -m polytool <command> [options]
"""

from __future__ import annotations

import sys
from typing import Optional

from tools.cli.export_clickhouse import main as export_clickhouse_main
from tools.cli.export_dossier import main as export_dossier_main
from tools.cli.agent_run import main as agent_run_main
from tools.cli.batch_run import main as batch_run_main
from tools.cli.llm_bundle import main as llm_bundle_main
from tools.cli.llm_save import main as llm_save_main
from tools.cli.rag_index import main as rag_index_main
from tools.cli.rag_eval import main as rag_eval_main
from tools.cli.rag_query import main as rag_query_main
from tools.cli.scan import main as scan_main


def print_usage() -> None:
    """Print CLI usage information."""
    print("PolyTool - Polymarket analysis toolchain")
    print("")
    print("Usage: polytool <command> [options]")
    print("       python -m polytool <command> [options]")
    print("")
    print("Commands:")
    print("  scan              Run a one-shot scan via the PolyTool API")
    print("  batch-run         Batch-run scans and aggregate a hypothesis leaderboard")
    print("  audit-coverage    Offline accuracy + trust sanity check from scan artifacts")
    print("  export-dossier    Export an LLM Research Packet dossier + memo")
    print("  export-clickhouse Export ClickHouse datasets for a user")
    print("  examine           Orchestrate full examination workflow (scan -> bundle -> prompt)")
    print("  llm-bundle        Build an LLM evidence bundle from dossier + RAG excerpts")
    print("  llm-save          Save an LLM report run into the private KB")
    print("  rag-index         Build or rebuild the local RAG index")
    print("  rag-query         Query the local RAG index")
    print("  rag-eval          Evaluate retrieval quality")
    print("  cache-source      Cache a trusted web source for RAG indexing")
    print("  agent-run         Run an agent task (internal)")
    print("  mcp               Start the MCP server for Claude Desktop integration")
    print("")
    print("Options:")
    print("  -h, --help        Show this help message")
    print("  --version         Show version information")
    print("")
    print("Examples:")
    print('  polytool scan --user "@DrPufferfish" --compute-pnl')
    print('  polytool batch-run --users users.txt --compute-pnl --compute-clv')
    print('  polytool audit-coverage --user "@DrPufferfish" --sample 25')
    print('  polytool export-dossier --user "@DrPufferfish" --days 30')
    print('  polytool examine --user "@DrPufferfish" --days 30')
    print('  polytool llm-bundle --user "@DrPufferfish"')
    print('  polytool rag-query --question "strategy patterns" --hybrid --rerank')
    print("")
    print("For more information, see docs/LOCAL_RAG_WORKFLOW.md")


def print_version() -> None:
    """Print version information."""
    from polytool import __version__
    print(f"polytool {__version__}")


def main(argv: Optional[list[str]] = None) -> int:
    """Main CLI entrypoint."""
    if argv is None:
        argv = sys.argv[1:]

    if len(argv) < 1:
        print_usage()
        return 1

    command = argv[0]

    if command in ("-h", "--help"):
        print_usage()
        return 0

    if command in ("-v", "--version"):
        print_version()
        return 0

    # Route to command handlers
    if command == "scan":
        return scan_main(argv[1:])
    if command == "batch-run":
        return batch_run_main(argv[1:])
    if command == "audit-coverage":
        from tools.cli.audit_coverage import main as audit_coverage_main
        return audit_coverage_main(argv[1:])
    if command == "export-dossier":
        return export_dossier_main(argv[1:])
    if command == "export-clickhouse":
        return export_clickhouse_main(argv[1:])
    if command == "agent-run":
        return agent_run_main(argv[1:])
    if command == "llm-save":
        return llm_save_main(argv[1:])
    if command == "llm-bundle":
        return llm_bundle_main(argv[1:])
    if command == "rag-index":
        return rag_index_main(argv[1:])
    if command == "rag-query":
        return rag_query_main(argv[1:])
    if command == "rag-eval":
        return rag_eval_main(argv[1:])

    # New commands (will be implemented)
    if command == "examine":
        try:
            from tools.cli.examine import main as examine_main
            return examine_main(argv[1:])
        except ImportError:
            print("Error: examine command not yet implemented.", file=sys.stderr)
            return 1

    if command == "cache-source":
        try:
            from tools.cli.cache_source import main as cache_source_main
            return cache_source_main(argv[1:])
        except ImportError:
            print("Error: cache-source command not yet implemented.", file=sys.stderr)
            return 1

    if command == "mcp":
        try:
            from tools.cli.mcp_server import main as mcp_main
            return mcp_main(argv[1:])
        except ImportError as exc:
            if "mcp" in str(exc).lower():
                print(
                    "Error: MCP SDK not installed. Run:  pip install 'mcp>=1.0.0'",
                    file=sys.stderr,
                )
            else:
                print(f"Error: {exc}", file=sys.stderr)
            return 1

    # Deprecated command aliases (for backward compatibility)
    if command == "opus-bundle":
        print(
            "Warning: 'opus-bundle' is deprecated. Use 'llm-bundle' instead.",
            file=sys.stderr,
        )
        return llm_bundle_main(argv[1:])

    print(f"Unknown command: {command}")
    print_usage()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
