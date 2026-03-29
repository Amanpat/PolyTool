"""CLI entrypoint for the crypto-pair backtest harness.

Replays historical or synthetic quote observations from a JSONL file through
the existing fair-value and accumulation logic.  Writes manifest.json,
summary.json, and report.md to a dated artifact directory.

No network calls.  No ClickHouse.  No live-execution imports.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from packages.polymarket.crypto_pairs.backtest_harness import (
    BacktestHarness,
    BacktestObservation,
)


_DEFAULT_OUTPUT_BASE = Path("artifacts/crypto_pairs/backtests")
_PREFIX = "[crypto-pair-backtest]"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Replay historical or synthetic pair-market observations through the "
            "Phase 1A accumulation engine.  Reads a JSONL input file and writes "
            "manifest.json, summary.json, and report.md to a dated artifact directory."
        )
    )
    parser.add_argument(
        "--input",
        required=True,
        metavar="PATH",
        help=(
            "Path to a JSONL file where each line is a JSON object representing one "
            "BacktestObservation.  Required fields: symbol, duration_min, market_id.  "
            "Optional: yes_ask, no_ask, underlying_price, threshold, remaining_seconds, "
            "feed_is_stale (bool, default false), yes_accumulated_size (float, default 0), "
            "no_accumulated_size (float, default 0), timestamp_iso."
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="PATH",
        help=(
            f"Base artifact directory.  Default: {_DEFAULT_OUTPUT_BASE}  "
            "Artifacts are written under <output>/<YYYY-MM-DD>/<run_id>/."
        ),
    )
    parser.add_argument(
        "--symbol",
        action="append",
        default=None,
        choices=["BTC", "ETH", "SOL"],
        metavar="BTC|ETH|SOL",
        help=(
            "Filter observations to this symbol only.  "
            "Repeat the flag to allow multiple symbols."
        ),
    )
    parser.add_argument(
        "--market-duration",
        action="append",
        default=None,
        type=int,
        choices=[5, 15],
        metavar="5|15",
        help=(
            "Filter observations to this market duration in minutes.  "
            "Repeat the flag to allow multiple durations."
        ),
    )
    parser.add_argument(
        "--run-id",
        default=None,
        metavar="STR",
        help="Optional explicit run_id override.  Defaults to auto uuid hex[:12].",
    )
    return parser


def _load_observations(
    input_path: Path,
    symbol_filter: Optional[set[str]],
    duration_filter: Optional[set[int]],
) -> list[BacktestObservation]:
    """Load and optionally filter BacktestObservation records from a JSONL file."""
    observations: list[BacktestObservation] = []
    with input_path.open("r", encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError as exc:
                print(
                    f"{_PREFIX} Warning: skipping invalid JSON on line {line_no}: {exc}",
                    file=sys.stderr,
                )
                continue

            symbol = obj.get("symbol", "")
            duration_min = obj.get("duration_min")

            if symbol_filter and symbol not in symbol_filter:
                continue
            if duration_filter and duration_min not in duration_filter:
                continue

            try:
                obs = BacktestObservation(
                    symbol=symbol,
                    duration_min=int(duration_min) if duration_min is not None else 0,
                    market_id=obj.get("market_id", ""),
                    yes_ask=obj.get("yes_ask"),
                    no_ask=obj.get("no_ask"),
                    underlying_price=obj.get("underlying_price"),
                    threshold=obj.get("threshold"),
                    remaining_seconds=obj.get("remaining_seconds"),
                    feed_is_stale=bool(obj.get("feed_is_stale", False)),
                    yes_accumulated_size=float(obj.get("yes_accumulated_size", 0.0)),
                    no_accumulated_size=float(obj.get("no_accumulated_size", 0.0)),
                    timestamp_iso=obj.get("timestamp_iso"),
                )
            except (TypeError, ValueError) as exc:
                print(
                    f"{_PREFIX} Warning: skipping malformed record on line {line_no}: {exc}",
                    file=sys.stderr,
                )
                continue

            observations.append(obs)

    return observations


def _write_artifacts(
    artifact_dir: Path,
    result_dict: dict,
    input_path: Path,
    filters_applied: dict,
    generated_at: str,
) -> None:
    """Write manifest.json, summary.json, and report.md to artifact_dir."""
    artifact_dir.mkdir(parents=True, exist_ok=True)

    # manifest.json — full context record
    manifest = {
        "run_id": result_dict["run_id"],
        "input_path": str(input_path.resolve()),
        "observations_total": result_dict["observations_total"],
        "filters_applied": filters_applied,
        "generated_at": generated_at,
        "artifact_dir": str(artifact_dir),
        "result": result_dict,
    }
    (artifact_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    # summary.json — machine-readable result only
    (artifact_dir / "summary.json").write_text(
        json.dumps(result_dict, indent=2), encoding="utf-8"
    )

    # report.md — human-readable
    r = result_dict
    avg_cost = (
        f"{r['avg_completed_pair_cost']:.4f}"
        if r["avg_completed_pair_cost"] is not None
        else "N/A"
    )
    est_profit = (
        f"{r['est_profit_per_completed_pair']:.4f}"
        if r["est_profit_per_completed_pair"] is not None
        else "N/A"
    )
    threshold = r.get("config_snapshot", {}).get("edge_buffer_per_leg", "N/A")

    lines = [
        "# Crypto Pair Backtest Report",
        "",
        f"**Run ID:** {r['run_id']}  ",
        f"**Input:** {input_path}  ",
        f"**Generated at:** {generated_at}  ",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "| ------ | ----- |",
        f"| observations_total | {r['observations_total']} |",
        f"| feed_stale_skips | {r['feed_stale_skips']} |",
        f"| quote_skips | {r['quote_skips']} |",
        f"| hard_rule_skips | {r['hard_rule_skips']} |",
        f"| soft_rule_skips | {r['soft_rule_skips']} |",
        f"| intents_generated | {r['intents_generated']} |",
        f"| partial_leg_intents | {r['partial_leg_intents']} |",
        f"| completed_pairs_simulated | {r['completed_pairs_simulated']} |",
        f"| avg_completed_pair_cost | {avg_cost} |",
        f"| est_profit_per_completed_pair | {est_profit} |",
        "",
        "## Config",
        "",
        f"| Parameter | Value |",
        f"| --------- | ----- |",
        f"| edge_buffer_per_leg | {threshold} |",
        "",
        "---",
        "",
        "_Conservative paper-style fill assumptions. No network calls._",
    ]
    (artifact_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        print(
            f"{_PREFIX} Error: input file not found: {input_path}",
            file=sys.stderr,
        )
        return 1

    output_base = Path(args.output) if args.output else _DEFAULT_OUTPUT_BASE
    symbol_filter: Optional[set[str]] = set(args.symbol) if args.symbol else None
    duration_filter: Optional[set[int]] = (
        set(args.market_duration) if args.market_duration else None
    )

    try:
        observations = _load_observations(input_path, symbol_filter, duration_filter)
    except OSError as exc:
        print(f"{_PREFIX} Error reading input: {exc}", file=sys.stderr)
        return 1

    harness = BacktestHarness()
    result = harness.run(observations)

    # Override run_id if explicitly requested
    if args.run_id:
        result.run_id = args.run_id

    generated_at = datetime.now(timezone.utc).isoformat()
    date_str = datetime.now(timezone.utc).date().isoformat()
    artifact_dir = output_base / date_str / result.run_id

    filters_applied: dict = {}
    if symbol_filter:
        filters_applied["symbols"] = sorted(symbol_filter)
    if duration_filter:
        filters_applied["market_durations"] = sorted(duration_filter)

    try:
        _write_artifacts(
            artifact_dir=artifact_dir,
            result_dict=result.to_dict(),
            input_path=input_path,
            filters_applied=filters_applied,
            generated_at=generated_at,
        )
    except OSError as exc:
        print(f"{_PREFIX} Error writing artifacts: {exc}", file=sys.stderr)
        return 1

    print(f"{_PREFIX} run_id        : {result.run_id}")
    print(f"{_PREFIX} observations  : {result.observations_total}")
    print(f"{_PREFIX} intents        : {result.intents_generated}")
    print(f"{_PREFIX} completed_pairs: {result.completed_pairs_simulated}")
    print(f"{_PREFIX} artifact_dir  : {artifact_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
