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
reconstruct_silver_main = _command_entrypoint("tools.cli.reconstruct_silver")
batch_reconstruct_silver_main = _command_entrypoint("tools.cli.batch_reconstruct_silver")
benchmark_manifest_main = _command_entrypoint("tools.cli.benchmark_manifest")
new_market_capture_main = _command_entrypoint("tools.cli.new_market_capture")
capture_new_market_tapes_main = _command_entrypoint("tools.cli.capture_new_market_tapes")
close_benchmark_v1_main = _command_entrypoint("tools.cli.close_benchmark_v1")
summarize_gap_fill_main = _command_entrypoint("tools.cli.summarize_gap_fill")
make_session_pack_main = _command_entrypoint("tools.cli.make_session_pack")
crypto_pair_scan_main = _command_entrypoint("tools.cli.crypto_pair_scan")
crypto_pair_run_main = _command_entrypoint("tools.cli.crypto_pair_run")
crypto_pair_backtest_main = _command_entrypoint("tools.cli.crypto_pair_backtest")
crypto_pair_report_main = _command_entrypoint("tools.cli.crypto_pair_report")
crypto_pair_watch_main = _command_entrypoint("tools.cli.crypto_pair_watch")
crypto_pair_await_soak_main = _command_entrypoint("tools.cli.crypto_pair_await_soak")
crypto_pair_seed_demo_events_main = _command_entrypoint(
    "tools.cli.crypto_pair_seed_demo_events"
)
rag_index_main = _command_entrypoint("tools.cli.rag_index")
rag_eval_main = _command_entrypoint("tools.cli.rag_eval")
rag_query_main = _command_entrypoint("tools.cli.rag_query")
rag_run_main = _command_entrypoint("tools.cli.rag_run")
scan_main = _command_entrypoint("tools.cli.scan")
simtrader_main = _command_entrypoint("tools.cli.simtrader")
research_eval_main = _command_entrypoint("tools.cli.research_eval")
research_precheck_main = _command_entrypoint("tools.cli.research_precheck")
research_ingest_main = _command_entrypoint("tools.cli.research_ingest")
research_seed_main = _command_entrypoint("tools.cli.research_seed")
research_benchmark_main = _command_entrypoint("tools.cli.research_benchmark")
research_calibration_main = _command_entrypoint("tools.cli.research_calibration")
research_extract_claims_main = _command_entrypoint("tools.cli.research_extract_claims")
research_acquire_main = _command_entrypoint("tools.cli.research_acquire")
research_report_main = _command_entrypoint("tools.cli.research_report")
research_scheduler_main = _command_entrypoint("tools.cli.research_scheduler")
research_stats_main = _command_entrypoint("tools.cli.research_stats")
research_health_main = _command_entrypoint("tools.cli.research_health")
research_review_main = _command_entrypoint("tools.cli.research_review")
research_dossier_extract_main = _command_entrypoint("tools.cli.research_dossier_extract")
research_bridge_main = _command_entrypoint("tools.cli.research_bridge")


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
    "reconstruct-silver": "reconstruct_silver_main",
    "batch-reconstruct-silver": "batch_reconstruct_silver_main",
    "benchmark-manifest": "benchmark_manifest_main",
    "new-market-capture": "new_market_capture_main",
    "capture-new-market-tapes": "capture_new_market_tapes_main",
    "close-benchmark-v1": "close_benchmark_v1_main",
    "summarize-gap-fill": "summarize_gap_fill_main",
    "crypto-pair-scan": "crypto_pair_scan_main",
    "crypto-pair-run": "crypto_pair_run_main",
    "crypto-pair-backtest": "crypto_pair_backtest_main",
    "crypto-pair-report": "crypto_pair_report_main",
    "crypto-pair-watch": "crypto_pair_watch_main",
    "crypto-pair-await-soak": "crypto_pair_await_soak_main",
    "crypto-pair-seed-demo-events": "crypto_pair_seed_demo_events_main",
    "research-eval": "research_eval_main",
    "research-precheck": "research_precheck_main",
    "research-ingest": "research_ingest_main",
    "research-seed": "research_seed_main",
    "research-benchmark": "research_benchmark_main",
    "research-calibration": "research_calibration_main",
    "research-extract-claims": "research_extract_claims_main",
    "research-acquire": "research_acquire_main",
    "research-report": "research_report_main",
    "research-scheduler": "research_scheduler_main",
    "research-stats": "research_stats_main",
    "research-health": "research_health_main",
    "research-review": "research_review_main",
    "research-dossier-extract": "research_dossier_extract_main",
    "research-register-hypothesis": "research_bridge_main",
    "research-record-outcome": "research_bridge_main",
}

_FULL_ARGV_COMMANDS = {
    "hypothesis-register",
    "hypothesis-status",
    "hypothesis-diff",
    "hypothesis-summary",
    "hypothesis-validate",
    "experiment-init",
    "experiment-run",
    "research-register-hypothesis",
    "research-record-outcome",
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
    print("--- Research Intelligence (RIS v1/v2) -----------------------------------")
    print("  research-eval             Evaluate a document through the RIS quality gate")
    print("  research-precheck         Pre-development check: GO / CAUTION / STOP recommendation")
    print("  research-ingest           Ingest a document into the RIS knowledge store")
    print("  research-seed             Seed the RIS knowledge store from a manifest")
    print("  research-benchmark        Compare extractor outputs on a fixture set")
    print("  research-calibration      Inspect precheck calibration health over the ledger")
    print("  research-extract-claims   Extract structured claims from ingested documents (no LLM)")
    print("  research-acquire          Acquire a source from URL and ingest into knowledge store")
    print("  research-report           Save, list, search reports and generate weekly digests")
    print("  research-scheduler        Manage the RIS background ingestion scheduler")
    print("  research-stats            Operator metrics snapshot and local-first export for RIS pipeline")
    print("  research-health           Print RIS health status summary from stored run data")
    print("  research-review           Inspect and resolve RIS review-queue items")
    print("  research-dossier-extract  Parse dossier artifacts -> KnowledgeStore (source_family=dossier_report)")
    print("  research-register-hypothesis  Register a research hypothesis candidate in the JSONL registry")
    print("  research-record-outcome       Record a validation outcome for KnowledgeStore claims")
    print("")
    print("--- Crypto Pair Bot (Track 2 / Phase 1A — standalone) -----------------")
    print("  crypto-pair-scan      Dry-run: discover BTC/ETH/SOL 5m/15m pair markets, compute edge")
    print("  crypto-pair-run       Paper by default; live scaffold behind --live with explicit safety gates")
    print("  crypto-pair-backtest  Replay historical/synthetic pair observations, emit eval artifacts")
    print("  crypto-pair-report    Summarize one completed paper run into rubric-backed markdown + JSON")
    print("  crypto-pair-watch     Check whether eligible BTC/ETH/SOL 5m/15m markets exist; poll with --watch")
    print("  crypto-pair-await-soak Wait for eligible markets, then launch the standard Coinbase paper smoke soak")
    print("  crypto-pair-seed-demo-events Seed dev-only synthetic Track 2 rows into ClickHouse for dashboard checks")
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
    print("  smoke-historical      DuckDB smoke - validate pmxt/Jon raw files directly (no ClickHouse)")
    print("  fetch-price-2min      Fetch 2-min price history from CLOB API -> polytool.price_2min (ClickHouse)")
    print("  reconstruct-silver    Reconstruct a Silver tape (pmxt anchor + Jon fills + price_2min midpoint guide)")
    print("  batch-reconstruct-silver Batch-reconstruct Silver tapes for multiple tokens over one window")
    print("  benchmark-manifest    Build or validate the frozen benchmark_v1 tape manifest contract")
    print("  new-market-capture    Discover newly listed markets (<48h) and plan Gold tape capture")
    print("  capture-new-market-tapes  Record Gold tapes for benchmark_v1 new_market targets (batch)")
    print("  close-benchmark-v1        End-to-end benchmark closure: preflight + Silver + new-market + manifest")
    print("  summarize-gap-fill        Read-only diagnostic summary for gap_fill_run.json artifacts")
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
