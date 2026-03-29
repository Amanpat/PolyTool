#!/usr/bin/env python3
"""Run Gate 2 mm sweep against recovery corpus manifest (recovery_corpus_v1 format).

The recovery corpus manifest is a plain JSON list of events.jsonl paths — not the
benchmark_v1 lock format. This driver reads the list, builds TapeCandidate objects
directly (bypassing the legacy selection filter), and calls run_mm_sweep's inner
sweep loop.

Usage:
    python tools/gates/run_recovery_corpus_sweep.py \
        --manifest config/recovery_corpus_v1.tape_manifest \
        --out artifacts/gates/mm_sweep_gate \
        --threshold 0.70

Exit codes:
  0 -- sweep ran; gate status written to --out
  1 -- NOT_RUN or error
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.gates.mm_sweep import (
    DEFAULT_MM_SWEEP_FEE_RATE_BPS,
    DEFAULT_MM_SWEEP_MARK_METHOD,
    DEFAULT_MM_SWEEP_MIN_EVENTS,
    DEFAULT_MM_SWEEP_MULTIPLIERS,
    DEFAULT_MM_SWEEP_OUT_DIR,
    DEFAULT_MM_SWEEP_STARTING_CASH,
    DEFAULT_MM_SWEEP_THRESHOLD,
    TapeCandidate,
    _build_tape_candidate,
    _read_json_object,
    build_mm_sweep_config,
    format_mm_sweep_summary,
)
from packages.polymarket.simtrader.sweeps.runner import (
    SweepConfigError,
    SweepRunParams,
    run_sweep,
)
from tools.gates.mm_sweep import (
    TapeSweepOutcome,
    _build_outcome,
    _build_gate_payload,
    _write_gate_result,
    _clear_gate_artifacts,
    MMSweepResult,
    _NOT_RUN_REASON,
    _TOO_SHORT_STATUS,
    _ERROR_STATUS,
)


def _discover_recovery_corpus_tapes(manifest_path: Path) -> list[TapeCandidate]:
    """Load all tape candidates from a recovery_corpus_v1 manifest (list of events paths)."""
    raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw_manifest, list):
        raise ValueError(f"manifest must be a JSON array; got {type(raw_manifest).__name__}")

    candidates: list[TapeCandidate] = []
    skipped = 0
    for raw_path in raw_manifest:
        events_path = _REPO_ROOT / raw_path if not Path(raw_path).is_absolute() else Path(raw_path)
        if not events_path.exists():
            print(f"  SKIP (missing): {raw_path}", file=sys.stderr)
            skipped += 1
            continue

        tape_dir = events_path.parent
        candidate = _build_tape_candidate(
            tape_dir=tape_dir,
            events_path=events_path,
            meta=_read_json_object(tape_dir / "meta.json"),
            prep_meta=_read_json_object(tape_dir / "prep_meta.json"),
            watch_meta=_read_json_object(tape_dir / "watch_meta.json"),
            market_meta=_read_json_object(tape_dir / "market_meta.json"),
            silver_meta=_read_json_object(tape_dir / "silver_meta.json"),
            manifest_entry={},
            require_selected=False,  # Recovery corpus: bypass legacy selection filter
            explicit_source=str(manifest_path),
        )
        if candidate is not None:
            candidates.append(candidate)
        else:
            print(f"  SKIP (no yes_asset_id): {raw_path}", file=sys.stderr)
            skipped += 1

    print(
        f"  Recovery corpus: {len(candidates)} tapes loaded, {skipped} skipped",
        file=sys.stderr,
    )
    return candidates


def run_recovery_sweep(
    *,
    manifest_path: Path,
    out_dir: Path,
    threshold: float = DEFAULT_MM_SWEEP_THRESHOLD,
    starting_cash: Decimal = DEFAULT_MM_SWEEP_STARTING_CASH,
    fee_rate_bps: Decimal = DEFAULT_MM_SWEEP_FEE_RATE_BPS,
    mark_method: str = DEFAULT_MM_SWEEP_MARK_METHOD,
    min_events: int = DEFAULT_MM_SWEEP_MIN_EVENTS,
    spread_multipliers: tuple[float, ...] = DEFAULT_MM_SWEEP_MULTIPLIERS,
) -> MMSweepResult:
    """Run mm sweep against recovery corpus manifest."""
    tapes = _discover_recovery_corpus_tapes(manifest_path)

    if not tapes:
        _clear_gate_artifacts(out_dir)
        return MMSweepResult(
            tapes=[],
            outcomes=[],
            gate_payload=None,
            artifact_path=None,
            threshold=threshold,
            min_events=min_events,
            not_run_reason=_NOT_RUN_REASON,
        )

    sweep_config = build_mm_sweep_config(spread_multipliers)
    outcomes: list[TapeSweepOutcome] = []
    eligible_outcomes: list[TapeSweepOutcome] = []

    total = len(tapes)
    for idx, tape in enumerate(tapes, 1):
        label = tape.tape_dir.name[:55]
        print(f"  [{idx:02d}/{total}] {label} ... ", end="", flush=True)

        if tape.effective_events < min_events:
            outcomes.append(
                TapeSweepOutcome(
                    tape=tape,
                    status=_TOO_SHORT_STATUS,
                    sweep_dir=None,
                    scenario_rows=[],
                    best_scenario_id=None,
                    best_scenario_name=None,
                    best_net_profit=None,
                    positive=False,
                    error=(
                        f"effective_events={tape.effective_events} "
                        f"(< --min-events {min_events}; "
                        f"raw_events={tape.parsed_events} across {tape.tracked_asset_count} assets)"
                    ),
                )
            )
            print(f"SKIPPED_TOO_SHORT (eff={tape.effective_events})")
            continue

        sweep_id = f"{tape.tape_dir.name}_market_maker_v1_mm_sweep"
        try:
            sweep_result = run_sweep(
                SweepRunParams(
                    events_path=tape.events_path,
                    strategy_name="market_maker_v1",
                    strategy_config=dict({
                        "min_spread": 0.020,
                        "max_spread": 0.120,
                        "spread_multiplier": 1.0,
                        "adverse_selection": {
                            "enabled": True,
                            "order_flow_signal": "proxy",
                        },
                    }),
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
            outcome = _build_outcome(tape, sweep_result)
            best = outcome.best_net_profit
            pnl_str = f"+{best:.2f}" if best and best > 0 else f"{best:.2f}" if best else "n/a"
            print(f"RAN net={pnl_str} positive={outcome.positive}")
        except (SweepConfigError, ValueError) as exc:
            outcome = TapeSweepOutcome(
                tape=tape,
                status=_ERROR_STATUS,
                sweep_dir=None,
                scenario_rows=[],
                best_scenario_id=None,
                best_scenario_name=None,
                best_net_profit=None,
                positive=False,
                error=str(exc),
            )
            print(f"ERROR: {exc}")
        except Exception as exc:  # noqa: BLE001
            outcome = TapeSweepOutcome(
                tape=tape,
                status=_ERROR_STATUS,
                sweep_dir=None,
                scenario_rows=[],
                best_scenario_id=None,
                best_scenario_name=None,
                best_net_profit=None,
                positive=False,
                error=f"unexpected sweep failure: {exc}",
            )
            print(f"ERROR (unexpected): {exc}")

        outcomes.append(outcome)
        eligible_outcomes.append(outcome)

    if not eligible_outcomes:
        _clear_gate_artifacts(out_dir)
        return MMSweepResult(
            tapes=tapes,
            outcomes=outcomes,
            gate_payload=None,
            artifact_path=None,
            threshold=threshold,
            min_events=min_events,
            not_run_reason=_NOT_RUN_REASON,
        )

    payload = _build_gate_payload(outcomes=eligible_outcomes, threshold=threshold)
    artifact_path = _write_gate_result(out_dir=out_dir, passed=payload["passed"], payload=payload)
    return MMSweepResult(
        tapes=tapes,
        outcomes=outcomes,
        gate_payload=payload,
        artifact_path=artifact_path,
        threshold=threshold,
        min_events=min_events,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        default="config/recovery_corpus_v1.tape_manifest",
        metavar="PATH",
        help="Path to the recovery corpus manifest (JSON list of events.jsonl paths)",
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_MM_SWEEP_OUT_DIR),
        metavar="PATH",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_MM_SWEEP_THRESHOLD,
        metavar="FLOAT",
    )
    parser.add_argument(
        "--min-events",
        type=int,
        default=DEFAULT_MM_SWEEP_MIN_EVENTS,
        metavar="N",
    )
    args = parser.parse_args(argv)

    manifest_path = _REPO_ROOT / args.manifest if not Path(args.manifest).is_absolute() else Path(args.manifest)
    out_dir = _REPO_ROOT / args.out if not Path(args.out).is_absolute() else Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Recovery corpus sweep")
    print(f"  manifest : {manifest_path}")
    print(f"  out      : {out_dir}")
    print(f"  threshold: {args.threshold:.0%}")
    print(f"  min-events: {args.min_events}")
    print()

    result = run_recovery_sweep(
        manifest_path=manifest_path,
        out_dir=out_dir,
        threshold=args.threshold,
        min_events=args.min_events,
    )

    print()
    print(format_mm_sweep_summary(result))

    if result.not_run_reason:
        print(f"NOT_RUN: {result.not_run_reason}")
        return 1

    passed = result.gate_payload and result.gate_payload.get("passed", False)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
