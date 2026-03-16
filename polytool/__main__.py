"""Module entrypoint for running PolyTool CLI commands.

This is the canonical CLI entrypoint for PolyTool.
Usage: python -m polytool <command> [options]
"""

from __future__ import annotations

import importlib
import sys
from typing import Optional


def _run_command(module_path: str, args: list[str]) -> int:
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    main_fn = getattr(module, "main", None)
    if main_fn is None:
        print(
            f"Error: {module_path} does not expose a main() entrypoint.",
            file=sys.stderr,
        )
        return 1
    return main_fn(args)


def _command_entrypoint(module_path: str):
    def _main(args: list[str]) -> int:
        return _run_command(module_path, args)

    return _main


export_clickhouse_main = _command_entrypoint("tools.cli.export_clickhouse")
export_dossier_main = _command_entrypoint("tools.cli.export_dossier")
agent_run_main = _command_entrypoint("tools.cli.agent_run")
batch_run_main = _command_entrypoint("tools.cli.batch_run")
audit_coverage_main = _command_entrypoint("tools.cli.audit_coverage")
hypotheses_main = _command_entrypoint("tools.cli.hypotheses")
wallet_scan_main = _command_entrypoint("tools.cli.wallet_scan")
alpha_distill_main = _command_entrypoint("tools.cli.alpha_distill")
llm_bundle_main = _command_entrypoint("tools.cli.llm_bundle")
llm_save_main = _command_entrypoint("tools.cli.llm_save")
market_scan_main = _command_entrypoint("tools.cli.market_scan")
scan_gate2_candidates_main = _command_entrypoint("tools.cli.scan_gate2_candidates")
prepare_gate2_main = _command_entrypoint("tools.cli.prepare_gate2")
watch_arb_candidates_main = _command_entrypoint("tools.cli.watch_arb_candidates")
tape_manifest_main = _command_entrypoint("tools.cli.tape_manifest")
gate2_preflight_main = _command_entrypoint("tools.cli.gate2_preflight")
historical_import_main = _command_entrypoint("tools.cli.historical_import")
smoke_historical_main = _command_entrypoint("tools.cli.smoke_historical")
fetch_price_2min_main = _command_entrypoint("tools.cli.fetch_price_2min")
make_session_pack_main = _command_entrypoint("tools.cli.make_session_pack")
rag_index_main = _command_entrypoint("tools.cli.rag_index")
rag_eval_main = _command_entrypoint("tools.cli.rag_eval")
rag_query_main = _command_entrypoint("tools.cli.rag_query")
rag_run_main = _command_entrypoint("tools.cli.rag_run")
scan_main = _command_entrypoint("tools.cli.scan")
simtrader_main = _command_entrypoint("tools.cli.simtrader")


_COMMAND_HANDLER_NAMES = {
    "agent-run": "agent_run_main",
    "alpha-distill": "alpha_distill_main",
    "audit-coverage": "audit_coverage_main",
    "batch-run": "batch_run_main",
    "export-clickhouse": "export_clickhouse_main",
    "export-dossier": "export_dossier_main",
    "gate2-preflight": "gate2_preflight_main",
    "hypothesis-register": "hypotheses_main",
    "hypothesis-status": "hypotheses_main",
    "hypothesis-diff": "hypotheses_main",
    "hypothesis-summary": "hypotheses_main",
    "hypothesis-validate": "hypotheses_main",
    "experiment-init": "hypotheses_main",
    "experiment-run": "hypotheses_main",
    "llm-bundle": "llm_bundle_main",
    "llm-save": "llm_save_main",
    "make-session-pack": "make_session_pack_main",
    "market-scan": "market_scan_main",
    "prepare-gate2": "prepare_gate2_main",
    "rag-eval": "rag_eval_main",
    "rag-index": "rag_index_main",
    "rag-query": "rag_query_main",
    "rag-run": "rag_run_main",
    "scan": "scan_main",
    "scan-gate2-candidates": "scan_gate2_candidates_main",
    "simtrader": "simtrader_main",
    "tape-manifest": "tape_manifest_main",
    "watch-arb-candidates": "watch_arb_candidates_main",
    "wallet-scan": "wallet_scan_main",
    "import-historical": "historical_import_main",
    "smoke-historical": "smoke_historical_main",
    "fetch-price-2min": "fetch_price_2min_main",
}

_FULL_ARGV_COMMANDS = {
    "hypothesis-register",
    "hypothesis-status",
    "hypothesis-diff",
    "hypothesis-summary",
    "hypothesis-validate",
    "experiment-init",
    "experiment-run",
}


def print_usage() -> None:
    """Print CLI usage information."""
    print("PolyTool - Polymarket analysis toolchain")
    print("")
    print("Usage: polytool <command> [options]")
    print("       python -m polytool <command> [options]")
    print("")
    print("--- Research Loop (Track B) -------------------------------------------")
    print("  wallet-scan           Batch-scan many wallets/handles -> ranked leaderboard")
    print("  alpha-distill         Distill wallet-scan data -> ranked edge candidates (no LLM)")
    print("  hypothesis-register   Register a candidate in the offline hypothesis registry")
    print("  hypothesis-status     Update lifecycle status for a registered hypothesis")
    print("  hypothesis-diff       Compare two saved hypothesis.json artifacts")
    print("  hypothesis-summary    Extract a deterministic summary from hypothesis.json")
    print("  experiment-init       Create an experiment.json skeleton for a hypothesis")
    print("  experiment-run        Create a generated experiment attempt for a hypothesis")
    print("  hypothesis-validate   Validate a hypothesis JSON file against schema_v1")
    print("")
    print("--- Analysis & Evidence -----------------------------------------------")
    print("  scan                  Run a one-shot scan via the PolyTool API")
    print("  batch-run             Batch-run scans and aggregate a hypothesis leaderboard")
    print("  audit-coverage        Offline accuracy + trust sanity check from scan artifacts")
    print("  export-dossier        Export an LLM Research Packet dossier + memo")
    print("  export-clickhouse     Export ClickHouse datasets for a user")
    print("")
    print("--- RAG & Knowledge ---------------------------------------------------")
    print("  rag-refresh           Rebuild the local RAG index (one-command, use this first)")
    print("  rag-index             Build or rebuild the RAG index (full control)")
    print("  rag-query             Query the local RAG index")
    print("  rag-run               Re-execute bundle rag_queries.json and write results back")
    print("  rag-eval              Evaluate retrieval quality")
    print("  cache-source          Cache a trusted web source for RAG indexing")
    print("  llm-bundle            Build an LLM evidence bundle from dossier + RAG excerpts")
    print("  llm-save              Save an LLM report run into the private KB")
    print("")
    print("--- SimTrader / Execution (Track A, gated) ----------------------------")
    print("  simtrader             Record/replay/shadow/live trading - run 'simtrader --help'")
    print("  market-scan           Rank active Polymarket markets by reward/spread/fill quality")
    print("  scan-gate2-candidates Rank markets by Gate 2 binary_complement_arb executability")
    print("  prepare-gate2         Scan -> record -> check eligibility for Gate 2 (orchestrator)")
    print("  watch-arb-candidates  Watch a market list and auto-record on near-edge dislocation")
    print("  tape-manifest         Scan tape corpus, check eligibility, emit acquisition manifest")
    print("  gate2-preflight       Check whether Gate 2 sweep is ready and why it may be blocked")
    print("  make-session-pack     Create exact watchlist + watcher-compatible session plan for a capture session")
    print("")
    print("--- Data Import (Phase 1 / Bulk Historical Foundation) ----------------")
    print("  import-historical     Validate and document local historical dataset layout")
    print("  smoke-historical      DuckDB smoke — validate pmxt/Jon raw files directly (no ClickHouse)")
    print("  fetch-price-2min      Fetch 2-min price history from CLOB API → polytool.price_2min (ClickHouse)")
    print("")
    print("--- Integrations & Utilities ------------------------------------------")
    print("  mcp                   Start the MCP server for Claude Desktop integration")
    print("  examine               Legacy examination orchestrator (scan -> bundle -> prompt)")
    print("  agent-run             Run an agent task (internal)")
    print("")
    print("Options:")
    print("  -h, --help        Show this help message")
    print("  --version         Show version information")
    print("")
    print("Common workflows:")
    print("  # Research loop")
    print('  polytool wallet-scan --input wallets.txt --profile lite')
    print('  polytool alpha-distill --wallet-scan-run artifacts/research/wallet_scan/YYYY-MM-DD/<id>')
    print('  polytool rag-refresh              # rebuild RAG index (one command)')
    print('  polytool rag-query --question "strategy patterns" --hybrid --rerank')
    print("")
    print("  # Single user examination")
    print('  polytool scan --user "@DrPufferfish"')
    print('  polytool llm-bundle --user "@DrPufferfish"')
    print("")
    print("  # SimTrader (gated)")
    print('  polytool market-scan --top 5')
    print('  polytool simtrader shadow --market <slug> --strategy market_maker_v1 --duration 300')
    print("")
    print("For more information, see:")
    print("  docs/OPERATOR_QUICKSTART.md   (end-to-end guide)")
    print("  docs/LOCAL_RAG_WORKFLOW.md    (RAG details)")
    print("  docs/README_SIMTRADER.md      (SimTrader operator guide)")


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

    if command == "rag-refresh":
        # Thin alias: rag-index --rebuild with default roots (kb,artifacts).
        # Use this after any scan/wallet-scan to make new content searchable.
        return rag_index_main(["--rebuild"] + argv[1:])

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

    handler_name = _COMMAND_HANDLER_NAMES.get(command)
    if handler_name is not None:
        args = argv if command in _FULL_ARGV_COMMANDS else argv[1:]
        return globals()[handler_name](args)

    print(f"Unknown command: {command}")
    print_usage()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
