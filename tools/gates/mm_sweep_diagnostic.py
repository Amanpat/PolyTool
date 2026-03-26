"""Per-tape root cause diagnostic for the market maker Gate 2 sweep.

This tool is read-only analysis — it does NOT modify gate logic or artifacts.
It ingests the benchmark manifest, runs a single-multiplier sweep on each
qualifying tape, and produces a per-tape breakdown table with:
  - eligibility status (SKIPPED_TOO_SHORT / RAN_POSITIVE / RAN_ZERO_PROFIT / ERROR)
  - tape tier (gold / silver / unknown)
  - effective_events count
  - skip reason (for SKIPPED_TOO_SHORT)
  - quote_count proxy
  - fill_opportunity classification
  - fill_count
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from packages.polymarket.simtrader.sweeps.runner import (
    SweepRunParams,
    SweepRunResult,
    run_sweep,
)
from tools.gates.mm_sweep import (
    DEFAULT_MM_SWEEP_BASE_CONFIG,
    DEFAULT_MM_SWEEP_FEE_RATE_BPS,
    DEFAULT_MM_SWEEP_MARK_METHOD,
    DEFAULT_MM_SWEEP_MIN_EVENTS,
    DEFAULT_MM_SWEEP_OUT_DIR,
    DEFAULT_MM_SWEEP_STARTING_CASH,
    TapeCandidate,
    build_mm_sweep_config,
    discover_mm_sweep_tapes,
)


# ---------------------------------------------------------------------------
# TapeDiagnostic dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TapeDiagnostic:
    """Per-tape root cause analysis result."""

    tape_dir: Path
    market_slug: str
    bucket: str | None
    tier: str                   # "gold" | "silver" | "unknown"
    effective_events: int
    parsed_events: int
    tracked_asset_count: int
    status: str                 # SKIPPED_TOO_SHORT | RAN_ZERO_PROFIT | RAN_POSITIVE | ERROR
    skip_reason: str | None     # Set for SKIPPED_TOO_SHORT; None otherwise
    best_net_profit: Decimal | None
    quote_count: int            # Number of actionable quote events (proxy from sweep)
    fill_opportunity: str       # "at_touch" | "no_touch" | "none" | "unknown"
    fill_count: int
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _detect_tier(tape_dir: Path) -> str:
    """Infer tape tier from metadata files present in tape_dir."""
    # Gold: recorded by tape_recorder (shadow mode) or has a watch_meta.json
    meta_path = tape_dir / "meta.json"
    watch_meta_path = tape_dir / "watch_meta.json"
    silver_meta_path = tape_dir / "silver_meta.json"
    market_meta_path = tape_dir / "market_meta.json"

    if watch_meta_path.exists():
        return "gold"

    if meta_path.exists():
        import json

        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
            if isinstance(meta, dict):
                recorded_by = str(meta.get("recorded_by", "")).strip().lower()
                if recorded_by in ("shadow", "tape_recorder"):
                    return "gold"
        except Exception:  # noqa: BLE001
            pass

    if silver_meta_path.exists():
        return "silver"

    if market_meta_path.exists():
        import json

        try:
            market_meta = json.loads(market_meta_path.read_text(encoding="utf-8-sig"))
            if isinstance(market_meta, dict) and market_meta.get("platform") == "silver":
                return "silver"
        except Exception:  # noqa: BLE001
            pass

    # Heuristic: benchmark tapes without gold markers are likely silver reconstructions
    return "unknown"


def _extract_quote_count(sweep_dir: Path | None, sweep_result: Any | None) -> int:
    """Extract quote_count from sweep run artifacts.

    Reads run_manifest.json -> strategy_debug.quote_count if available.
    Falls back to -1 (unknown) and notes are added by the caller.
    """
    if sweep_dir is None or sweep_result is None:
        return 0

    if not sweep_dir.exists():
        return -1

    import json

    # Look through scenario subdirs for a run_manifest.json
    for scenario_dir in sweep_dir.iterdir():
        if not scenario_dir.is_dir():
            continue
        manifest_path = scenario_dir / "run_manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(manifest, dict):
                strategy_debug = manifest.get("strategy_debug", {})
                if isinstance(strategy_debug, dict):
                    quote_count = strategy_debug.get("quote_count")
                    if quote_count is not None:
                        return int(quote_count)
        except Exception:  # noqa: BLE001
            continue

    # quote_count not present in manifests — return -1 to flag as unknown
    return -1


def _extract_fill_count(sweep_result: Any | None) -> int:
    """Extract total fill count from sweep summary."""
    if sweep_result is None:
        return 0

    summary = getattr(sweep_result, "summary", {})
    if not isinstance(summary, dict):
        return 0

    # Sum fills across all scenarios
    total_fills = 0
    for scenario in summary.get("scenarios", []):
        if isinstance(scenario, dict):
            total_fills += int(scenario.get("fill_count", 0))
    return total_fills


def _parse_best_net_profit(sweep_result: Any | None) -> Decimal | None:
    """Extract the best (maximum) net_profit across all scenarios in a sweep."""
    if sweep_result is None:
        return None

    summary = getattr(sweep_result, "summary", {})
    if not isinstance(summary, dict):
        return None

    best: Decimal | None = None
    for scenario in summary.get("scenarios", []):
        if not isinstance(scenario, dict):
            continue
        raw = scenario.get("net_profit")
        if raw is None:
            continue
        try:
            value = Decimal(str(raw))
        except (InvalidOperation, TypeError, ValueError):
            continue
        if best is None or value > best:
            best = value
    return best


def _classify_fill_opportunity(
    *,
    fill_count: int,
    quote_count: int,
    effective_events: int,
    min_events: int,
    status: str,
) -> str:
    """Classify the fill opportunity for a tape.

    - "at_touch" — fills happened (cannot distinguish at_touch from cross without full book)
    - "no_touch"  — strategy quoted but market never crossed the spread
    - "none"      — strategy never quoted (or tape was skipped)
    - "unknown"   — insufficient information
    """
    if status == "SKIPPED_TOO_SHORT":
        return "none"
    if fill_count > 0:
        return "at_touch"
    if quote_count > 0 and effective_events >= min_events:
        return "no_touch"
    if quote_count == 0 and effective_events >= min_events:
        return "none"
    if quote_count == -1:
        return "unknown"
    return "none"


# ---------------------------------------------------------------------------
# _diagnose_tape (core logic, public for testing)
# ---------------------------------------------------------------------------


def _diagnose_tape(
    tape: TapeCandidate,
    min_events: int,
    sweep_result: Any | None,
) -> TapeDiagnostic:
    """Build a TapeDiagnostic for a single tape."""
    tier = _detect_tier(tape.tape_dir)
    notes: list[str] = []

    if tape.effective_events < min_events:
        skip_reason = (
            f"effective_events={tape.effective_events} < min_events={min_events}; "
            f"raw_events={tape.parsed_events} across {tape.tracked_asset_count} assets"
        )
        return TapeDiagnostic(
            tape_dir=tape.tape_dir,
            market_slug=tape.market_slug,
            bucket=tape.bucket,
            tier=tier,
            effective_events=tape.effective_events,
            parsed_events=tape.parsed_events,
            tracked_asset_count=tape.tracked_asset_count,
            status="SKIPPED_TOO_SHORT",
            skip_reason=skip_reason,
            best_net_profit=None,
            quote_count=0,
            fill_opportunity="none",
            fill_count=0,
            notes=notes,
        )

    # Tape ran — extract metrics from sweep result
    sweep_dir = getattr(sweep_result, "sweep_dir", None)
    best_net_profit = _parse_best_net_profit(sweep_result)
    fill_count = _extract_fill_count(sweep_result)
    quote_count = _extract_quote_count(sweep_dir, sweep_result)

    if quote_count == -1:
        notes.append(
            "quote_count not present in run_manifest.json strategy_debug — "
            "fill opportunity classification may be imprecise"
        )

    if sweep_result is None or best_net_profit is None:
        status = "ERROR"
    elif best_net_profit > Decimal("0"):
        status = "RAN_POSITIVE"
    else:
        status = "RAN_ZERO_PROFIT"

    # When quote_count is -1 (no manifest data), we still classify based on fill_count.
    # If fill_count == 0 and the tape ran, assume no_touch (strategy ran but spread was never
    # crossed). "unknown" is reserved for cases where we cannot determine even the fill count.
    effective_quote_count = max(quote_count, 0)
    fill_opportunity = _classify_fill_opportunity(
        fill_count=fill_count,
        quote_count=effective_quote_count if quote_count >= 0 else 1,  # assume quoted when -1
        effective_events=tape.effective_events,
        min_events=min_events,
        status=status,
    )

    return TapeDiagnostic(
        tape_dir=tape.tape_dir,
        market_slug=tape.market_slug,
        bucket=tape.bucket,
        tier=tier,
        effective_events=tape.effective_events,
        parsed_events=tape.parsed_events,
        tracked_asset_count=tape.tracked_asset_count,
        status=status,
        skip_reason=None,
        best_net_profit=best_net_profit,
        quote_count=max(quote_count, 0),
        fill_opportunity=fill_opportunity,
        fill_count=fill_count,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Main entry function
# ---------------------------------------------------------------------------


def run_mm_sweep_diagnostic(
    *,
    benchmark_manifest_path: Path,
    out_dir: Path,
    min_events: int = DEFAULT_MM_SWEEP_MIN_EVENTS,
    spread_multiplier: float = 1.0,
    starting_cash: Decimal = DEFAULT_MM_SWEEP_STARTING_CASH,
    fee_rate_bps: Decimal = DEFAULT_MM_SWEEP_FEE_RATE_BPS,
    mark_method: str = DEFAULT_MM_SWEEP_MARK_METHOD,
) -> list[TapeDiagnostic]:
    """Run per-tape diagnostics against the benchmark manifest.

    For each tape:
    - Tapes with effective_events < min_events get SKIPPED_TOO_SHORT with no sweep run.
    - Qualifying tapes run a single spread_multiplier=1.0 sweep.

    Writes diagnostic_report.md to out_dir.
    Returns the list of TapeDiagnostic objects.
    """
    tapes = discover_mm_sweep_tapes(benchmark_manifest_path=benchmark_manifest_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    sweep_config = build_mm_sweep_config(spread_multipliers=(spread_multiplier,))
    diagnostics: list[TapeDiagnostic] = []

    for tape in tapes:
        if tape.effective_events < min_events:
            diag = _diagnose_tape(tape, min_events=min_events, sweep_result=None)
            diagnostics.append(diag)
            continue

        sweep_id = f"{tape.tape_dir.name}_diagnostic_sweep"
        try:
            sweep_result: Any = run_sweep(
                SweepRunParams(
                    events_path=tape.events_path,
                    strategy_name="market_maker_v1",
                    strategy_config=dict(DEFAULT_MM_SWEEP_BASE_CONFIG),
                    asset_id=tape.yes_asset_id,
                    starting_cash=starting_cash,
                    fee_rate_bps=fee_rate_bps,
                    mark_method=mark_method,
                    latency_submit_ticks=0,
                    latency_cancel_ticks=0,
                    strict=False,
                    sweep_id=sweep_id,
                    artifacts_root=out_dir,
                    strategy_preset=None,
                    market_slug=tape.market_slug,
                ),
                sweep_config=sweep_config,
            )
        except Exception as exc:  # noqa: BLE001
            diag = TapeDiagnostic(
                tape_dir=tape.tape_dir,
                market_slug=tape.market_slug,
                bucket=tape.bucket,
                tier=_detect_tier(tape.tape_dir),
                effective_events=tape.effective_events,
                parsed_events=tape.parsed_events,
                tracked_asset_count=tape.tracked_asset_count,
                status="ERROR",
                skip_reason=None,
                best_net_profit=None,
                quote_count=0,
                fill_opportunity="unknown",
                fill_count=0,
                notes=[f"sweep error: {exc}"],
            )
            diagnostics.append(diag)
            continue

        diag = _diagnose_tape(tape, min_events=min_events, sweep_result=sweep_result)
        diagnostics.append(diag)

    report_text = format_diagnostic_report(diagnostics)
    report_path = out_dir / "diagnostic_report.md"
    report_path.write_text(report_text, encoding="utf-8")

    return diagnostics


# ---------------------------------------------------------------------------
# format_diagnostic_report
# ---------------------------------------------------------------------------


def format_diagnostic_report(diagnostics: list[TapeDiagnostic]) -> str:
    """Render a markdown table and summary for the diagnostic results."""
    lines: list[str] = [
        "# MM Sweep Diagnostic Report",
        "",
        "| Tape | Bucket | Tier | EffEvents | Status | QuoteCount | FillOpp | SkipReason |",
        "|------|--------|------|----------:|--------|------------|---------|------------|",
    ]

    for diag in diagnostics:
        tape_name = diag.tape_dir.name
        bucket = diag.bucket or "-"
        tier = diag.tier
        eff = str(diag.effective_events)
        status = diag.status
        qc = str(diag.quote_count) if diag.quote_count >= 0 else "n/a"
        fill_opp = diag.fill_opportunity
        skip = diag.skip_reason or "-"
        if len(skip) > 60:
            skip = skip[:57] + "..."
        lines.append(
            f"| {tape_name} | {bucket} | {tier} | {eff} | {status} | {qc} | {fill_opp} | {skip} |"
        )

    # Summary section
    total = len(diagnostics)
    skipped_count = sum(1 for d in diagnostics if d.status == "SKIPPED_TOO_SHORT")
    zero_count = sum(1 for d in diagnostics if d.status == "RAN_ZERO_PROFIT")
    positive_count = sum(1 for d in diagnostics if d.status == "RAN_POSITIVE")
    error_count = sum(1 for d in diagnostics if d.status == "ERROR")

    fill_opp_dist: dict[str, int] = {}
    for diag in diagnostics:
        fill_opp_dist[diag.fill_opportunity] = fill_opp_dist.get(diag.fill_opportunity, 0) + 1

    lines += [
        "",
        "## Summary",
        "",
        f"- **Total tapes:** {total}",
        f"- **SKIPPED_TOO_SHORT:** {skipped_count}",
        f"- **RAN_ZERO_PROFIT:** {zero_count}",
        f"- **RAN_POSITIVE:** {positive_count}",
        f"- **ERROR:** {error_count}",
        "",
        "### Fill Opportunity Distribution",
        "",
    ]
    for opp, count in sorted(fill_opp_dist.items()):
        lines.append(f"- {opp}: {count}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Per-tape root cause diagnostic for Gate 2 (market maker sweep)."
    )
    parser.add_argument(
        "--benchmark-manifest",
        required=True,
        metavar="PATH",
        help="Path to config/benchmark_v1.tape_manifest",
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_MM_SWEEP_OUT_DIR / "diagnostic"),
        metavar="PATH",
        help="Output directory for diagnostic_report.md and sweep artifacts.",
    )
    parser.add_argument(
        "--min-events",
        type=int,
        default=DEFAULT_MM_SWEEP_MIN_EVENTS,
        metavar="COUNT",
        help=f"Minimum effective events for a tape to be swept (default: {DEFAULT_MM_SWEEP_MIN_EVENTS}).",
    )
    parser.add_argument(
        "--spread-multiplier",
        type=float,
        default=1.0,
        metavar="FLOAT",
        help="Spread multiplier for the single diagnostic sweep run (default: 1.0).",
    )

    args = parser.parse_args(argv)

    try:
        diagnostics = run_mm_sweep_diagnostic(
            benchmark_manifest_path=Path(args.benchmark_manifest),
            out_dir=Path(args.out),
            min_events=int(args.min_events),
            spread_multiplier=float(args.spread_multiplier),
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(format_diagnostic_report(diagnostics))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
