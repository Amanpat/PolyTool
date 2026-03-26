#!/usr/bin/env python3
"""Close the market maker Gate 2 sweep."""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.gates.mm_sweep import (
    DEFAULT_GATE2_MANIFEST_PATH,
    DEFAULT_MM_SWEEP_FEE_RATE_BPS,
    DEFAULT_MM_SWEEP_MARK_METHOD,
    DEFAULT_MM_SWEEP_MIN_ELIGIBLE_TAPES,
    DEFAULT_MM_SWEEP_MIN_EVENTS,
    DEFAULT_MM_SWEEP_MULTIPLIERS,
    DEFAULT_MM_SWEEP_OUT_DIR,
    DEFAULT_MM_SWEEP_STARTING_CASH,
    DEFAULT_MM_SWEEP_TAPES_DIR,
    DEFAULT_MM_SWEEP_THRESHOLD,
    format_mm_sweep_summary,
    run_mm_sweep,
)


def _parse_decimal(raw: str, field_name: str) -> Decimal:
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"invalid {field_name}: {raw!r}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tapes-dir", default=str(DEFAULT_MM_SWEEP_TAPES_DIR), metavar="PATH")
    parser.add_argument("--out", default=str(DEFAULT_MM_SWEEP_OUT_DIR), metavar="PATH")
    parser.add_argument("--manifest", default=str(DEFAULT_GATE2_MANIFEST_PATH), metavar="PATH")
    parser.add_argument(
        "--benchmark-manifest",
        default=None,
        metavar="PATH",
        help=(
            "Path to config/benchmark_v1.tape_manifest. "
            "When provided, overrides --tapes-dir and --manifest and runs the sweep "
            "against all 50 benchmark tapes."
        ),
    )
    parser.add_argument("--threshold", type=float, default=DEFAULT_MM_SWEEP_THRESHOLD, metavar="FLOAT")
    parser.add_argument(
        "--starting-cash",
        default=str(DEFAULT_MM_SWEEP_STARTING_CASH),
        metavar="USDC",
    )
    parser.add_argument(
        "--fee-rate-bps",
        default=str(DEFAULT_MM_SWEEP_FEE_RATE_BPS),
        metavar="BPS",
    )
    parser.add_argument(
        "--mark-method",
        choices=["bid", "midpoint"],
        default=DEFAULT_MM_SWEEP_MARK_METHOD,
    )
    parser.add_argument(
        "--min-events",
        type=int,
        default=DEFAULT_MM_SWEEP_MIN_EVENTS,
        metavar="COUNT",
        help=(
            "Minimum effective event count required for a tape to be swept "
            f"(default: {DEFAULT_MM_SWEEP_MIN_EVENTS})."
        ),
    )
    parser.add_argument(
        "--min-eligible-tapes",
        type=int,
        default=DEFAULT_MM_SWEEP_MIN_ELIGIBLE_TAPES,
        metavar="COUNT",
        help=(
            "Minimum number of tapes that must meet --min-events to compute a Gate 2 "
            f"verdict (default: {DEFAULT_MM_SWEEP_MIN_ELIGIBLE_TAPES}). "
            "If fewer tapes qualify, result is NOT_RUN, not FAILED."
        ),
    )
    parser.add_argument(
        "--spread-multipliers",
        type=float,
        nargs="+",
        default=list(DEFAULT_MM_SWEEP_MULTIPLIERS),
        metavar="FLOAT",
        help=(
            "Spread multipliers to apply to the A-S spread before quoting "
            f"(default: {' '.join(str(value) for value in DEFAULT_MM_SWEEP_MULTIPLIERS)})."
        ),
    )
    args = parser.parse_args(argv)

    try:
        result = run_mm_sweep(
            tapes_dir=Path(args.tapes_dir),
            out_dir=Path(args.out),
            manifest_path=Path(args.manifest),
            benchmark_manifest_path=(
                Path(args.benchmark_manifest) if args.benchmark_manifest else None
            ),
            threshold=float(args.threshold),
            starting_cash=_parse_decimal(args.starting_cash, "starting_cash"),
            fee_rate_bps=_parse_decimal(args.fee_rate_bps, "fee_rate_bps"),
            mark_method=args.mark_method,
            min_events=int(args.min_events),
            min_eligible_tapes=int(args.min_eligible_tapes),
            spread_multipliers=tuple(float(value) for value in args.spread_multipliers),
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(format_mm_sweep_summary(result))
    if result.gate_payload is None:
        print(f"NOT_RUN: {result.not_run_reason}", file=sys.stderr)
        return 0
    return 0 if result.gate_payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
