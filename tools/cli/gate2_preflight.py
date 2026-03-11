"""Operator preflight for Gate 2 sweep readiness.

READY means:
  - at least one tape is eligible for binary complement arb, and
  - eligible tapes cover politics, sports, and new_market.

BLOCKED means one or both conditions are missing. The command explains why and
prints the next operator action.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_DEFAULT_TAPES_DIR = Path("artifacts/simtrader/tapes")
_DEFAULT_MAX_SIZE = 50.0
_DEFAULT_BUFFER = 0.01
_REQUIRED_REGIMES = ("politics", "sports", "new_market")
_VALID_REGIMES = frozenset((*_REQUIRED_REGIMES, "unknown"))
_EVENT_TYPE_BOOK = "book"
_EVENT_TYPE_PRICE_CHANGE = "price_change"
_EXIT_READY = 0
_EXIT_BLOCKED = 2


@dataclass(frozen=True)
class TapeRecord:
    tape_dir: str
    slug: str
    regime: str
    eligible: bool


@dataclass(frozen=True)
class CorpusSummary:
    eligible_count: int
    regime_coverage: dict[str, Any]


def _format_regimes(regimes: tuple[str, ...] | list[str]) -> str:
    if not regimes:
        return "none"
    return ", ".join(regimes)


def _load_json(path: Path) -> Optional[dict[str, Any]]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _read_regime(tape_dir: Path) -> str:
    for meta_name in ("watch_meta.json", "prep_meta.json"):
        data = _load_json(tape_dir / meta_name)
        if data is None:
            continue
        regime = str(data.get("regime") or "").strip().lower()
        if regime in _VALID_REGIMES:
            return regime

    data = _load_json(tape_dir / "meta.json")
    if data is None:
        return "unknown"

    for ctx_key in ("shadow_context", "quickrun_context"):
        ctx = data.get(ctx_key)
        if isinstance(ctx, dict):
            regime = str(ctx.get("regime") or "").strip().lower()
            if regime in _VALID_REGIMES:
                return regime

    regime = str(data.get("regime") or "").strip().lower()
    if regime in _VALID_REGIMES:
        return regime
    return "unknown"


def _read_slug(tape_dir: Path) -> str:
    for meta_name in ("watch_meta.json", "prep_meta.json"):
        data = _load_json(tape_dir / meta_name)
        if data is None:
            continue
        slug = str(data.get("market_slug") or data.get("slug") or "").strip()
        if slug:
            return slug

    data = _load_json(tape_dir / "meta.json")
    if data is not None:
        for ctx_key in ("shadow_context", "quickrun_context"):
            ctx = data.get(ctx_key)
            if isinstance(ctx, dict):
                slug = str(ctx.get("market") or ctx.get("market_slug") or "").strip()
                if slug:
                    return slug
        slug = str(data.get("market_slug") or data.get("slug") or "").strip()
        if slug:
            return slug

    return tape_dir.name


def _discover_asset_ids(events_path: Path) -> tuple[str, str]:
    seen: list[str] = []
    try:
        with events_path.open(encoding="utf-8-sig") as handle:
            for raw_line in handle:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    event = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict):
                    continue
                if event.get("event_type") == _EVENT_TYPE_BOOK:
                    asset_id = str(event.get("asset_id") or "").strip()
                    if asset_id and asset_id not in seen:
                        seen.append(asset_id)
                elif event.get("event_type") == _EVENT_TYPE_PRICE_CHANGE:
                    for entry in event.get("price_changes") or ():
                        if not isinstance(entry, dict):
                            continue
                        asset_id = str(entry.get("asset_id") or "").strip()
                        if asset_id and asset_id not in seen:
                            seen.append(asset_id)
                    if len(seen) < 2:
                        asset_id = str(event.get("asset_id") or "").strip()
                        if asset_id and asset_id not in seen:
                            seen.append(asset_id)
                if len(seen) >= 2:
                    return seen[0], seen[1]
    except OSError:
        return "", ""
    if len(seen) >= 2:
        return seen[0], seen[1]
    return "", ""


def _read_asset_ids(tape_dir: Path) -> tuple[str, str]:
    for meta_name in ("watch_meta.json", "prep_meta.json"):
        data = _load_json(tape_dir / meta_name)
        if data is None:
            continue
        yes_id = str(data.get("yes_asset_id") or "").strip()
        no_id = str(data.get("no_asset_id") or "").strip()
        if yes_id and no_id:
            return yes_id, no_id

    data = _load_json(tape_dir / "meta.json")
    if data is not None:
        for ctx_key in ("shadow_context", "quickrun_context"):
            ctx = data.get(ctx_key)
            if isinstance(ctx, dict):
                yes_id = str(ctx.get("yes_asset_id") or "").strip()
                no_id = str(ctx.get("no_asset_id") or "").strip()
                if yes_id and no_id:
                    return yes_id, no_id

    return _discover_asset_ids(tape_dir / "events.jsonl")


def _parse_decimal(value: Any) -> Optional[Decimal]:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _parse_asks(levels: list[Any]) -> dict[str, Decimal]:
    asks: dict[str, Decimal] = {}
    for level in levels:
        if isinstance(level, dict):
            price = str(level.get("price") or level.get("p") or "").strip()
            size_raw = level.get("size") or level.get("s") or "0"
        elif isinstance(level, (list, tuple)) and len(level) >= 2:
            price = str(level[0]).strip()
            size_raw = level[1]
        else:
            continue
        size = _parse_decimal(size_raw)
        if price and size is not None and size > 0:
            asks[price] = size
    return asks


def _apply_ask_change(book: dict[str, Decimal], change: dict[str, Any]) -> None:
    side = str(change.get("side") or "").upper()
    if side != "SELL":
        return

    price = str(change.get("price") or "").strip()
    if not price:
        return

    size = _parse_decimal(change.get("size", "0"))
    if size is None:
        return
    if size <= 0:
        book.pop(price, None)
        return
    book[price] = size


def _best_ask(book: dict[str, Decimal]) -> tuple[Optional[Decimal], Optional[Decimal]]:
    if not book:
        return None, None
    best_price_str = min(book, key=lambda price: Decimal(price))
    return Decimal(best_price_str), book[best_price_str]


def _is_tape_eligible(events_path: Path, yes_id: str, no_id: str, max_size: float, buffer: float) -> bool:
    max_size_decimal = Decimal(str(max_size))
    threshold = Decimal("1") - Decimal(str(buffer))
    yes_book: dict[str, Decimal] = {}
    no_book: dict[str, Decimal] = {}
    yes_initialized = False
    no_initialized = False

    try:
        with events_path.open(encoding="utf-8-sig") as handle:
            for raw_line in handle:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    event = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict):
                    continue

                event_type = event.get("event_type")
                if event_type == _EVENT_TYPE_BOOK:
                    asset_id = str(event.get("asset_id") or "").strip()
                    if asset_id == yes_id:
                        yes_book = _parse_asks(event.get("asks") or [])
                        yes_initialized = True
                    elif asset_id == no_id:
                        no_book = _parse_asks(event.get("asks") or [])
                        no_initialized = True
                    else:
                        continue
                elif event_type == _EVENT_TYPE_PRICE_CHANGE:
                    if event.get("price_changes"):
                        for entry in event.get("price_changes") or ():
                            if not isinstance(entry, dict):
                                continue
                            asset_id = str(entry.get("asset_id") or "").strip()
                            if asset_id == yes_id and yes_initialized:
                                _apply_ask_change(yes_book, entry)
                            elif asset_id == no_id and no_initialized:
                                _apply_ask_change(no_book, entry)
                    elif event.get("changes"):
                        asset_id = str(event.get("asset_id") or "").strip()
                        if asset_id == yes_id and yes_initialized:
                            for entry in event.get("changes") or ():
                                if isinstance(entry, dict):
                                    _apply_ask_change(yes_book, entry)
                        elif asset_id == no_id and no_initialized:
                            for entry in event.get("changes") or ():
                                if isinstance(entry, dict):
                                    _apply_ask_change(no_book, entry)
                    else:
                        asset_id = str(event.get("asset_id") or "").strip()
                        if asset_id == yes_id and yes_initialized:
                            _apply_ask_change(yes_book, event)
                        elif asset_id == no_id and no_initialized:
                            _apply_ask_change(no_book, event)
                else:
                    continue

                yes_ask, yes_size = _best_ask(yes_book)
                no_ask, no_size = _best_ask(no_book)
                if None in (yes_ask, yes_size, no_ask, no_size):
                    continue
                if yes_size >= max_size_decimal and no_size >= max_size_decimal:
                    if yes_ask + no_ask < threshold:
                        return True
    except OSError:
        return False

    return False


def scan_tapes_dir(tapes_dir: Path, *, max_size: float, buffer: float) -> list[TapeRecord]:
    records: list[TapeRecord] = []
    for tape_dir in sorted(path for path in tapes_dir.iterdir() if path.is_dir()):
        events_path = tape_dir / "events.jsonl"
        yes_id, no_id = _read_asset_ids(tape_dir)
        eligible = False
        if events_path.is_file() and yes_id and no_id:
            eligible = _is_tape_eligible(events_path, yes_id, no_id, max_size, buffer)
        record = TapeRecord(
            tape_dir=str(tape_dir),
            slug=_read_slug(tape_dir),
            regime=_read_regime(tape_dir),
            eligible=eligible,
        )
        records.append(record)
        logger.debug("Tape %s eligible=%s regime=%s", record.slug, record.eligible, record.regime)
    return records


def build_corpus_summary(records: list[TapeRecord]) -> CorpusSummary:
    eligible_records = [record for record in records if record.eligible]
    regime_counts = {
        regime: sum(1 for record in eligible_records if record.regime == regime)
        for regime in _REQUIRED_REGIMES
    }
    covered_regimes = tuple(regime for regime in _REQUIRED_REGIMES if regime_counts[regime] > 0)
    missing_regimes = tuple(regime for regime in _REQUIRED_REGIMES if regime_counts[regime] == 0)
    return CorpusSummary(
        eligible_count=len(eligible_records),
        regime_coverage={
            "satisfies_policy": len(missing_regimes) == 0,
            "covered_regimes": covered_regimes,
            "missing_regimes": missing_regimes,
            "regime_counts": regime_counts,
        },
    )


def _eligible_records(records: list[TapeRecord]) -> list[TapeRecord]:
    return [record for record in records if record.eligible]


def _next_action(summary: CorpusSummary) -> tuple[str, str]:
    coverage = summary.regime_coverage or {}
    missing_regimes = tuple(str(regime) for regime in coverage.get("missing_regimes") or ())

    if summary.eligible_count <= 0:
        return (
            "No eligible tapes. Gate 2 sweep still lacks a tape with executable_ticks > 0.",
            "python -m polytool scan-gate2-candidates --all --top 20 --explain",
        )

    if coverage.get("satisfies_policy") is not True:
        if missing_regimes:
            first_missing = missing_regimes[0]
            return (
                f"Missing mixed-regime coverage: {', '.join(missing_regimes)}.",
                f"Capture an eligible {first_missing} tape, then rerun: python -m polytool gate2-preflight",
            )
        return (
            "Mixed-regime coverage is incomplete.",
            "Capture another eligible tape in a missing named regime, then rerun: python -m polytool gate2-preflight",
        )

    return (
        "At least one eligible tape exists and mixed-regime coverage is complete.",
        "python tools/gates/close_sweep_gate.py",
    )


def print_preflight_summary(records: list[TapeRecord], summary: CorpusSummary) -> int:
    coverage = summary.regime_coverage or {}
    covered_regimes = tuple(str(regime) for regime in coverage.get("covered_regimes") or ())
    missing_regimes = tuple(str(regime) for regime in coverage.get("missing_regimes") or ())
    eligible_records = _eligible_records(records)

    blocker, next_action = _next_action(summary)
    ready = summary.eligible_count > 0 and coverage.get("satisfies_policy") is True
    result = "READY" if ready else "BLOCKED"

    print("Gate 2 Preflight")
    print("================")
    print(f"Result: {result}")
    print(f"Eligible tapes: {summary.eligible_count}")
    if eligible_records:
        print("Eligible tape list:")
        for record in eligible_records:
            print(f"  - {record.slug} :: {record.tape_dir}")
    else:
        print("Eligible tape list: none")
    print(
        "Mixed-regime coverage: "
        f"{'READY' if coverage.get('satisfies_policy') is True else 'BLOCKED'}"
    )
    print(f"Covered regimes: {_format_regimes(covered_regimes)}")
    print(f"Missing regimes: {_format_regimes(missing_regimes)}")
    print(f"Blocker: {'none' if ready else blocker}")
    print(f"Next action: {next_action}")

    return _EXIT_READY if ready else _EXIT_BLOCKED


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gate2-preflight",
        description=(
            "Check whether Gate 2 sweep is ready using existing tape eligibility "
            "and mixed-regime coverage rules."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--tapes-dir",
        default=str(_DEFAULT_TAPES_DIR),
        metavar="DIR",
        help="Directory containing tape subdirectories.",
    )
    parser.add_argument(
        "--max-size",
        type=float,
        default=_DEFAULT_MAX_SIZE,
        metavar="N",
        help="Required depth at best ask per leg in shares.",
    )
    parser.add_argument(
        "--buffer",
        type=float,
        default=_DEFAULT_BUFFER,
        metavar="F",
        help="Edge buffer: entry when sum_ask < 1 - buffer.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(level=log_level, format="%(levelname)s %(name)s: %(message)s")

    tapes_dir = Path(args.tapes_dir)
    if not tapes_dir.is_dir():
        print(f"Error: --tapes-dir '{tapes_dir}' is not a directory.", file=sys.stderr)
        return 1

    max_size = float(args.max_size)
    buffer = float(args.buffer)
    if max_size <= 0:
        print("Error: --max-size must be positive.", file=sys.stderr)
        return 1
    if not (0.0 < buffer < 1.0):
        print("Error: --buffer must be between 0 and 1.", file=sys.stderr)
        return 1

    records = scan_tapes_dir(tapes_dir, max_size=max_size, buffer=buffer)
    summary = build_corpus_summary(records)
    return print_preflight_summary(records, summary)


if __name__ == "__main__":
    raise SystemExit(main())

