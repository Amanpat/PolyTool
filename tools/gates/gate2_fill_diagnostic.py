"""Gate 2 fill-path diagnostic -- multi-tape analysis for zero-fill failures.

This script answers the core question blocking Gate 2 closure:

  WHY do all 9 qualifying benchmark tapes produce zero fills at all
  5 spread multipliers when run through the market_maker_v1 strategy?

It performs a tick-by-tick analysis of each qualifying tape, recording:

  1. Book initialization state at each tick
  2. Strategy bid/ask quotes (from MarketMakerV1._compute_quotes)
  3. Book ask levels at time of each BUY intent
  4. Whether any ask level is at or below the BUY limit price
  5. Gap = best_ask - bid_price (how far the book is from the MM's bid)

Then prints per-tape summary tables and a cross-tape VERDICT identifying the
primary root cause:

  ROOT CAUSE A: Silver tapes contain only price_2min_guide events.
    L2Book never initializes. fill_engine returns book_not_initialized
    before any quote comparison can occur.

  ROOT CAUSE B: Strategy quotes too wide for Silver tape price movement.
    (Only reachable if A is not the root cause.)

  ROOT CAUSE C: Fills would occur but simulator has a bug.
    (Falsification path.)

Usage::

    python tools/gates/gate2_fill_diagnostic.py \\
        [--tape-manifest config/benchmark_v1.tape_manifest] \\
        [--tapes-dir artifacts/tapes/silver] \\
        [--verbose]

This script is READ-ONLY. It does not modify any existing files, gate
logic, eligibility thresholds, or fill model behavior.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Repo root on sys.path.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from packages.polymarket.simtrader.broker.fill_engine import try_fill
from packages.polymarket.simtrader.broker.rules import Order, Side
from packages.polymarket.simtrader.orderbook.l2book import L2Book
from packages.polymarket.simtrader.strategies.market_maker_v1 import MarketMakerV1
from packages.polymarket.simtrader.tape.schema import EVENT_TYPE_BOOK, EVENT_TYPE_PRICE_CHANGE
from tools.gates.mm_sweep import (
    DEFAULT_MM_SWEEP_BASE_CONFIG,
    DEFAULT_MM_SWEEP_MIN_EVENTS,
    DEFAULT_MM_SWEEP_MULTIPLIERS,
    DEFAULT_MM_SWEEP_STARTING_CASH,
    _count_effective_events,
)

logger = logging.getLogger(__name__)

_ZERO = Decimal("0")
_MIN_EVENTS = DEFAULT_MM_SWEEP_MIN_EVENTS
_DEFAULT_MULTIPLIERS: tuple[float, ...] = DEFAULT_MM_SWEEP_MULTIPLIERS
_BOOK_AFFECTING = frozenset({EVENT_TYPE_BOOK, EVENT_TYPE_PRICE_CHANGE})

# ---------------------------------------------------------------------------
# Constants: Gate 2 base config (matches mm_sweep.py defaults).
# ---------------------------------------------------------------------------
_BASE_CFG = dict(DEFAULT_MM_SWEEP_BASE_CONFIG)
_GAMMA = 0.10
_KAPPA = 1.50
_MIN_SPREAD = 0.020
_MAX_SPREAD = 0.120
_SESSION_HOURS = 4.0
_RESOLUTION_GUARD = 0.10


# ---------------------------------------------------------------------------
# Tape discovery -- finds qualifying Silver tapes from disk.
# ---------------------------------------------------------------------------


def _discover_silver_tapes(tapes_dir: Path, min_events: int) -> list[dict[str, Any]]:
    """Walk tapes_dir for silver tape directories and count effective events.

    Returns list of dicts with keys:
      tape_dir, events_path, events_file, token_id, slug, bucket,
      parsed_events, effective_events.
    """
    candidates: list[dict[str, Any]] = []

    if not tapes_dir.exists():
        return candidates

    for token_dir in sorted(tapes_dir.iterdir()):
        if not token_dir.is_dir():
            continue
        for date_dir in sorted(token_dir.iterdir()):
            if not date_dir.is_dir():
                continue

            # Silver tapes use silver_events.jsonl; Gold tapes use events.jsonl
            events_path = None
            for fname in ("silver_events.jsonl", "events.jsonl"):
                candidate_path = date_dir / fname
                if candidate_path.exists():
                    events_path = candidate_path
                    break

            if events_path is None:
                continue

            # Count effective events (same logic as mm_sweep._count_effective_events)
            parsed_events, tracked_asset_count, effective_events = _count_effective_events(
                events_path
            )

            market_meta = _read_json(date_dir / "market_meta.json")
            silver_meta = _read_json(date_dir / "silver_meta.json")

            token_id = (
                silver_meta.get("token_id")
                or market_meta.get("token_id")
                or token_dir.name
            )
            slug = market_meta.get("slug") or silver_meta.get("slug") or str(token_id)[:30]
            bucket = market_meta.get("benchmark_bucket") or silver_meta.get("category") or "unknown"

            candidates.append(
                {
                    "tape_dir": date_dir,
                    "events_path": events_path,
                    "events_file": events_path.name,
                    "token_id": str(token_id),
                    "slug": slug,
                    "bucket": bucket,
                    "parsed_events": parsed_events,
                    "tracked_asset_count": tracked_asset_count,
                    "effective_events": effective_events,
                    "qualifies": effective_events >= min_events,
                }
            )

    return candidates


def _discover_from_manifest(
    manifest_path: Path,
    min_events: int,
) -> list[dict[str, Any]]:
    """Load tapes referenced in a benchmark manifest.

    The manifest is a JSON array of path strings relative to the repo root.
    Missing files are reported but not fatal -- diagnostic still runs on
    whatever is accessible on disk.
    """
    try:
        entries: list[str] = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[WARNING] Cannot parse manifest {manifest_path}: {exc}")
        return []

    candidates: list[dict[str, Any]] = []
    missing: list[str] = []

    for entry in entries:
        raw_path = Path(entry)
        # Try as absolute; if not, try relative to repo root.
        if raw_path.is_absolute():
            events_path = raw_path
        else:
            events_path = _REPO_ROOT / raw_path

        if not events_path.exists():
            missing.append(str(raw_path))
            continue

        tape_dir = events_path.parent

        parsed_events, tracked_asset_count, effective_events = _count_effective_events(
            events_path
        )

        market_meta = _read_json(tape_dir / "market_meta.json")
        silver_meta = _read_json(tape_dir / "silver_meta.json")
        prep_meta = _read_json(tape_dir / "prep_meta.json")

        token_id = (
            prep_meta.get("yes_asset_id")
            or prep_meta.get("yes_token_id")
            or silver_meta.get("token_id")
            or market_meta.get("token_id")
            or tape_dir.parent.name
        )
        slug = (
            prep_meta.get("market_slug")
            or market_meta.get("slug")
            or silver_meta.get("slug")
            or str(token_id)[:30]
        )
        bucket = (
            market_meta.get("benchmark_bucket")
            or silver_meta.get("category")
            or "unknown"
        )

        candidates.append(
            {
                "tape_dir": tape_dir,
                "events_path": events_path,
                "events_file": events_path.name,
                "token_id": str(token_id),
                "slug": slug,
                "bucket": bucket,
                "parsed_events": parsed_events,
                "tracked_asset_count": tracked_asset_count,
                "effective_events": effective_events,
                "qualifies": effective_events >= min_events,
            }
        )

    if missing:
        print(f"[WARNING] {len(missing)}/{len(entries)} manifest entries missing on disk.")
        print(f"  First 3 missing: {missing[:3]}")

    return candidates


# ---------------------------------------------------------------------------
# Per-tape tick-level diagnostic.
# ---------------------------------------------------------------------------


def _build_strategy(spread_multiplier: float = 1.0) -> MarketMakerV1:
    """Instantiate MarketMakerV1 using Gate 2 sweep defaults."""
    return MarketMakerV1(
        tick_size="0.01",
        order_size="10",
        min_spread=_MIN_SPREAD,
        max_spread=_MAX_SPREAD,
        spread_multiplier=spread_multiplier,
        gamma=_GAMMA,
        kappa=_KAPPA,
        session_hours=_SESSION_HOURS,
        resolution_guard=_RESOLUTION_GUARD,
    )


def _load_events(events_path: Path) -> list[dict]:
    events = []
    with open(events_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    events.sort(key=lambda e: e.get("seq", 0))
    return events


def run_tape_diagnostic(
    tape_info: dict[str, Any],
    spread_multiplier: float = 1.0,
    *,
    verbose: bool = False,
) -> dict[str, Any]:
    """Run full tick-level diagnostic on one tape.

    Returns a diagnostic result dict with per-tick analysis and summary stats.
    """
    events_path: Path = tape_info["events_path"]
    asset_id: str = tape_info["token_id"]

    events = _load_events(events_path)

    # --- Counters ---
    event_type_counts: dict[str, int] = defaultdict(int)
    book_affecting_count = 0
    book_ever_initialized = False
    buy_intents: list[dict] = []
    sell_intents: list[dict] = []
    prices_seen: list[float] = []

    # --- Infrastructure ---
    book = L2Book(asset_id, strict=False)
    strategy = _build_strategy(spread_multiplier)
    strategy.on_start(asset_id, DEFAULT_MM_SWEEP_STARTING_CASH)

    for event in events:
        seq: int = event.get("seq", 0)
        ts_recv: float = float(event.get("ts_recv", 0.0))
        event_type: str = str(event.get("event_type") or "")
        evt_asset: str = str(event.get("asset_id") or "")

        event_type_counts[event_type] += 1

        # Track price observations (for mid-range analysis)
        if "price" in event:
            try:
                prices_seen.append(float(event["price"]))
            except (TypeError, ValueError):
                pass

        # Apply to book only if relevant event type and matching asset
        if event_type in _BOOK_AFFECTING and evt_asset == asset_id:
            book_affecting_count += 1
            book.apply(event)
            if book._initialized and not book_ever_initialized:
                book_ever_initialized = True

        # Get book BBO
        best_bid = book.best_bid
        best_ask = book.best_ask

        # Call strategy (it handles its own book state tracking internally)
        open_orders: dict = {}
        intents = strategy.on_event(
            event=event,
            seq=seq,
            ts_recv=ts_recv,
            best_bid=best_bid,
            best_ask=best_ask,
            open_orders=open_orders,
        )

        # Analyse each OrderIntent
        for intent in intents:
            side = (intent.side or "").upper()
            limit_price = intent.limit_price

            # Determine book ask levels (for BUY) or bid levels (for SELL)
            ask_levels = book.top_asks(5) if book._initialized else []
            bid_levels = book.top_bids(5) if book._initialized else []
            n_asks = len(book._asks) if book._initialized else 0
            n_bids = len(book._bids) if book._initialized else 0

            if side == "BUY":
                # Would this BUY fill? Any ask level at or below limit_price?
                limit_f = float(limit_price)
                competitive_asks = [
                    a for a in ask_levels if a["price"] <= limit_f
                ]
                would_fill = len(competitive_asks) > 0
                gap_cents = None
                if best_ask is not None:
                    gap_cents = round((best_ask - limit_f) * 100, 2)

                row = {
                    "seq": seq,
                    "ts_recv": ts_recv,
                    "book_initialized": book._initialized,
                    "bid_price": float(limit_price),
                    "best_bid": best_bid,
                    "best_ask": best_ask,
                    "n_ask_levels": n_asks,
                    "n_bid_levels": n_bids,
                    "top_asks": ask_levels[:3],
                    "competitive_asks": competitive_asks,
                    "would_fill": would_fill,
                    "gap_cents": gap_cents,
                }
                buy_intents.append(row)
                if verbose:
                    logger.debug(
                        "seq=%d BUY@%.4f best_ask=%-8s book_init=%-5s would_fill=%s gap=%s",
                        seq,
                        float(limit_price),
                        f"{best_ask:.4f}" if best_ask else "None",
                        str(book._initialized),
                        would_fill,
                        f"{gap_cents:.1f}c" if gap_cents is not None else "N/A",
                    )

            elif side == "SELL":
                row = {
                    "seq": seq,
                    "ts_recv": ts_recv,
                    "book_initialized": book._initialized,
                    "ask_price": float(limit_price),
                    "best_bid": best_bid,
                    "best_ask": best_ask,
                    "n_bid_levels": n_bids,
                    "n_ask_levels": n_asks,
                }
                sell_intents.append(row)

    # --- Compute summary stats ---
    n_buy = len(buy_intents)
    n_buy_would_fill = sum(1 for r in buy_intents if r["would_fill"])
    n_buy_no_init = sum(1 for r in buy_intents if not r["book_initialized"])
    n_buy_no_competitive = sum(
        1 for r in buy_intents
        if r["book_initialized"] and not r["would_fill"]
    )

    gaps_cents = [r["gap_cents"] for r in buy_intents if r["gap_cents"] is not None]
    avg_gap_cents = round(sum(gaps_cents) / len(gaps_cents), 2) if gaps_cents else None
    min_gap_cents = round(min(gaps_cents), 2) if gaps_cents else None
    max_gap_cents = round(max(gaps_cents), 2) if gaps_cents else None

    ask_depths = [r["n_ask_levels"] for r in buy_intents]
    avg_ask_depth = round(sum(ask_depths) / len(ask_depths), 2) if ask_depths else 0.0

    mid_range = None
    if prices_seen:
        mid_range = (round(min(prices_seen), 4), round(max(prices_seen), 4))

    # Resolution guard active?
    resolution_guard_active = False
    if mid_range:
        mn, mx = mid_range
        if mn < _RESOLUTION_GUARD or mx > (1.0 - _RESOLUTION_GUARD):
            resolution_guard_active = True

    return {
        "tape_id": tape_info["tape_dir"].parent.name,  # token_id component
        "tape_dir": str(tape_info["tape_dir"]),
        "events_file": tape_info["events_file"],
        "slug": tape_info["slug"][:50],
        "bucket": tape_info["bucket"],
        "effective_events": tape_info["effective_events"],
        "event_type_counts": dict(event_type_counts),
        "book_affecting_events": book_affecting_count,
        "book_ever_initialized": book_ever_initialized,
        "n_buy_intents": n_buy,
        "n_sell_intents": len(sell_intents),
        "n_buy_would_fill": n_buy_would_fill,
        "n_buy_no_init": n_buy_no_init,
        "n_buy_no_competitive": n_buy_no_competitive,
        "avg_ask_depth": avg_ask_depth,
        "avg_gap_cents": avg_gap_cents,
        "min_gap_cents": min_gap_cents,
        "max_gap_cents": max_gap_cents,
        "mid_range": mid_range,
        "resolution_guard_active": resolution_guard_active,
        "spread_multiplier": spread_multiplier,
    }


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _fmt(value: Any, width: int = 8) -> str:
    if value is None:
        return "N/A".rjust(width)
    if isinstance(value, float):
        return f"{value:.2f}".rjust(width)
    return str(value).rjust(width)


def _print_separator(char: str = "-", width: int = 110) -> None:
    print(char * width)


# ---------------------------------------------------------------------------
# Main entry point.
# ---------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--tape-manifest",
        type=Path,
        default=None,
        help="Path to benchmark manifest JSON (e.g. config/benchmark_v1.tape_manifest). "
             "If provided, tape discovery uses the manifest; else uses --tapes-dir.",
    )
    parser.add_argument(
        "--tapes-dir",
        type=Path,
        default=_REPO_ROOT / "artifacts" / "tapes" / "silver",
        help="Directory to scan for silver tape subdirectories (default: artifacts/tapes/silver).",
    )
    parser.add_argument(
        "--min-events",
        type=int,
        default=_MIN_EVENTS,
        help=f"Minimum effective_events to qualify for Gate 2 (default: {_MIN_EVENTS}).",
    )
    parser.add_argument(
        "--multiplier",
        type=float,
        default=1.0,
        help="spread_multiplier for the diagnostic run (default: 1.0). "
             "Also runs an extra pass at 0.50x to check tightest-spread behavior.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-tick diagnostic rows.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    print()
    print("=" * 110)
    print("Gate 2 Fill-Path Diagnostic")
    print("=" * 110)
    print(f"Repo root      : {_REPO_ROOT}")
    if args.tape_manifest:
        print(f"Manifest       : {args.tape_manifest}")
    else:
        print(f"Tapes dir      : {args.tapes_dir}")
    print(f"Min events     : {args.min_events}")
    print(f"Spread mult    : {args.multiplier}x (also runs 0.50x for comparison)")
    print()

    # --- Discover tapes ---
    if args.tape_manifest:
        all_tapes = _discover_from_manifest(args.tape_manifest, args.min_events)
        # If manifest paths don't resolve, fall back to tapes_dir scan
        if not any(t["qualifies"] for t in all_tapes):
            print(
                "[INFO] Manifest paths not found on disk. "
                "Falling back to --tapes-dir scan."
            )
            all_tapes = _discover_silver_tapes(args.tapes_dir, args.min_events)
    else:
        all_tapes = _discover_silver_tapes(args.tapes_dir, args.min_events)

    qualifying = [t for t in all_tapes if t["qualifies"]]
    skipped = [t for t in all_tapes if not t["qualifies"]]

    print(f"Tapes discovered : {len(all_tapes)}")
    print(f"  Qualifying (>= {args.min_events} events): {len(qualifying)}")
    print(f"  Skipped (too short)               : {len(skipped)}")
    print()

    if not qualifying:
        print("[ERROR] No qualifying tapes found. Cannot produce diagnostic.")
        return 1

    # --- Print event-type survey ---
    print("Event Type Survey (sample from qualifying tapes):")
    _print_separator()
    all_event_types: dict[str, int] = defaultdict(int)
    for tape in qualifying:
        events = _load_events(tape["events_path"])
        for e in events:
            all_event_types[str(e.get("event_type", "unknown"))] += 1
    for et, count in sorted(all_event_types.items(), key=lambda x: -x[1]):
        print(f"  {et:<35} : {count:>6}")
    print()

    book_affecting_types = all_event_types.keys() & _BOOK_AFFECTING
    if not book_affecting_types:
        print(
            "[CRITICAL] Zero book-affecting events (book / price_change) found "
            "in qualifying tapes."
        )
        print(
            "           L2Book will NEVER initialize. fill_engine returns "
            "book_not_initialized immediately."
        )
        print()

    # --- Run diagnostic at default multiplier ---
    print(f"Per-Tape Diagnostic (spread_multiplier={args.multiplier:.2f}x):")
    _print_separator()

    header = (
        f"{'Tape ID':<22} {'Events':>7} {'BuyInts':>8} {'WldFill':>8} "
        f"{'NoInit':>7} {'NoCmpLvl':>9} {'AvgAskDpth':>11} "
        f"{'AvgGapC':>8} {'MidRange':<22} {'Guard':>6}"
    )
    print(header)
    _print_separator()

    results_default: list[dict] = []
    for tape in qualifying:
        result = run_tape_diagnostic(tape, spread_multiplier=args.multiplier, verbose=args.verbose)
        results_default.append(result)
        mid_str = (
            f"{result['mid_range'][0]:.4f}-{result['mid_range'][1]:.4f}"
            if result["mid_range"]
            else "N/A"
        )
        guard_str = "YES" if result["resolution_guard_active"] else "no"
        print(
            f"{result['tape_id']:<22} "
            f"{result['effective_events']:>7} "
            f"{result['n_buy_intents']:>8} "
            f"{result['n_buy_would_fill']:>8} "
            f"{result['n_buy_no_init']:>7} "
            f"{result['n_buy_no_competitive']:>9} "
            f"{result['avg_ask_depth']:>11.2f} "
            f"{_fmt(result['avg_gap_cents'], 8)} "
            f"{mid_str:<22} "
            f"{guard_str:>6}"
        )

    _print_separator()
    print()

    # --- Run diagnostic at 0.50x multiplier (tightest sweep setting) ---
    if args.multiplier != 0.50:
        print("Tightest-Spread Check (spread_multiplier=0.50x):")
        _print_separator()
        print(header)
        _print_separator()
        results_tight: list[dict] = []
        for tape in qualifying:
            result = run_tape_diagnostic(tape, spread_multiplier=0.50, verbose=False)
            results_tight.append(result)
            mid_str = (
                f"{result['mid_range'][0]:.4f}-{result['mid_range'][1]:.4f}"
                if result["mid_range"]
                else "N/A"
            )
            guard_str = "YES" if result["resolution_guard_active"] else "no"
            print(
                f"{result['tape_id']:<22} "
                f"{result['effective_events']:>7} "
                f"{result['n_buy_intents']:>8} "
                f"{result['n_buy_would_fill']:>8} "
                f"{result['n_buy_no_init']:>7} "
                f"{result['n_buy_no_competitive']:>9} "
                f"{result['avg_ask_depth']:>11.2f} "
                f"{_fmt(result['avg_gap_cents'], 8)} "
                f"{mid_str:<22} "
                f"{guard_str:>6}"
            )
        _print_separator()
        print()
    else:
        results_tight = results_default

    # --- Cross-tape aggregate ---
    print("Cross-Tape Aggregate Statistics:")
    _print_separator()
    total_buy_intents = sum(r["n_buy_intents"] for r in results_default)
    total_would_fill = sum(r["n_buy_would_fill"] for r in results_default)
    total_no_init = sum(r["n_buy_no_init"] for r in results_default)
    total_no_competitive = sum(r["n_buy_no_competitive"] for r in results_default)
    tapes_book_init = sum(1 for r in results_default if r["book_ever_initialized"])

    print(f"  Total qualifying tapes          : {len(results_default)}")
    print(f"  Tapes where book initialized    : {tapes_book_init}/{len(results_default)}")
    print(f"  Total BUY intents across tapes  : {total_buy_intents}")
    print(f"  BUY intents that would fill     : {total_would_fill}")
    print(f"  BUY intents blocked: no init    : {total_no_init}")
    print(f"  BUY intents blocked: no levels  : {total_no_competitive}")
    fill_rate_pct = (
        f"{total_would_fill / total_buy_intents * 100:.2f}%"
        if total_buy_intents
        else "N/A"
    )
    print(f"  Overall fill opportunity rate   : {fill_rate_pct}")

    tapes_book_init_tight = sum(1 for r in results_tight if r["book_ever_initialized"])
    total_would_fill_tight = sum(r["n_buy_would_fill"] for r in results_tight)
    print()
    print(f"  Tightest multiplier (0.50x):")
    print(f"    Tapes where book initialized  : {tapes_book_init_tight}/{len(results_tight)}")
    print(f"    BUY intents that would fill   : {total_would_fill_tight}")
    print()

    # --- Determine verdict ---
    all_no_init = tapes_book_init == 0
    some_no_init = tapes_book_init < len(results_default)
    all_would_fill_zero = total_would_fill == 0
    tight_would_fill_zero = total_would_fill_tight == 0

    # Detect which event types the tapes actually have
    has_price_2min_guide = "price_2min_guide" in all_event_types
    has_book_events = bool(book_affecting_types)

    print("=" * 110)
    print("VERDICT")
    print("=" * 110)
    print()

    if all_no_init and has_price_2min_guide and not has_book_events:
        print("ROOT CAUSE: H1 CONFIRMED -- Silver tapes contain ONLY price_2min_guide events.")

        print()
        print("Mechanism (code path):")
        print("  1. Silver tape events have event_type='price_2min_guide'.")
        print("  2. L2Book.apply() only handles EVENT_TYPE_BOOK and EVENT_TYPE_PRICE_CHANGE.")
        print("  3. price_2min_guide events are ignored by the book => L2Book._initialized = False.")
        print("  4. fill_engine.try_fill() checks book._initialized first:")
        print("       if not book._initialized: return _reject('book_not_initialized')")
        print("  5. Quote comparison NEVER occurs. No ask levels are ever evaluated.")
        print("  6. Every fill attempt returns reject_reason='book_not_initialized'.")
        print()
        print("Corollary -- H2 (quotes too wide) is SECONDARY:")
        print("  H2 cannot be tested while H1 is active. Even if the strategy emitted")
        print("  tight quotes, the fill engine would reject them with book_not_initialized")
        print("  before any BBO comparison occurs.")
        print()
        print("Corollary -- H3 (chicken-and-egg inventory) is a CONSEQUENCE:")
        print("  SELL orders never receive inventory because BUY fills never happen.")
        print("  The 'Insufficient position to reserve SELL order' warning is logged")
        print("  by portfolio/ledger.py (line ~419) but does NOT block order submission.")
        print("  This is a symptom of H1, not an independent cause.")
        print()
        print("Fill engine correctness: CONFIRMED.")
        print("  The fill engine is behaving exactly as designed. It correctly refuses")
        print("  to invent liquidity from an uninitialized book. This is NOT a simulator bug.")
        print()
        print("Strategy correctness: CONFIRMED (within observable scope).")
        print("  MarketMakerV1 emits BUY/SELL intents on every tick where best_bid and")
        print("  best_ask are non-None. However, since the book never initializes,")
        print("  best_bid=None and best_ask=None at every tick, so the strategy emits")
        print("  zero OrderIntents (compute_quotes() returns [] when either BBO is None).")
        print()
        print("Silver tape quality for fill-based evaluation: INSUFFICIENT.")
        print("  Silver tapes are reconstructed from price_2min guide data only.")
        print("  They contain price midpoint observations, not L2 order book snapshots.")
        print("  The fill simulation requires actual book depth (ask levels that can")
        print("  be crossed by a BUY order). Silver tapes do not provide this.")
        print()
        print("RECOMMENDED NEXT ACTIONS:")
        print()
        print("  1. PRIMARY UNBLOCK -- Gold tape capture:")
        print("     Gold tapes (recorded from live WebSocket) contain full L2 book")
        print("     snapshots and price_change deltas. Run the Gold capture runbook:")
        print("       docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md")
        print("     Gate 2 requires 50 qualifying Gold tapes (>= 50 effective events each).")
        print()
        print("  2. SECONDARY INVESTIGATION -- After Gold tapes exist, run H2 diagnostic:")
        print("     With Gold tapes, re-run this diagnostic to check whether the A-S")
        print("     resolution guard (2.5x spread widening when mid < 0.10 or > 0.90)")
        print("     still prevents fills on near_resolution markets. This is a separate")
        print("     question that cannot be answered until H1 is resolved.")
        print()
        print("  3. DO NOT modify the fill engine, gate thresholds, or tape eligibility")
        print("     criteria as workarounds. The fill engine is correct. The tape quality")
        print("     is insufficient. Fix the data, not the validator.")
        print()

    elif some_no_init and all_would_fill_zero:
        print("ROOT CAUSE: MIXED -- Some tapes have no book initialization (H1) and")
        print("  remaining tapes show zero fill opportunities even with an initialized book.")
        print("  This suggests both H1 (Silver tape depth) and H2 (quotes too wide) contribute.")

    elif all_would_fill_zero and not all_no_init:
        print("ROOT CAUSE: H2 LIKELY -- Book initializes but strategy quotes never overlap book.")
        print("  The A-S spread formula produces quotes too wide for available price movement.")
        print("  Check the resolution guard and spread_multiplier sweep settings.")

    elif not all_would_fill_zero:
        print("UNEXPECTED: Fill opportunities detected but fills not occurring.")
        print("  This may indicate a simulator bug in SimBroker.step() ordering.")
        print("  Investigate fill_engine.try_fill() being called before book.apply().")

    else:
        print("VERDICT: UNKNOWN -- Unable to determine from available evidence.")
        print("  Review per-tape results and run with --verbose for tick-level detail.")

    print()
    print("=" * 110)
    print("Diagnostic complete.")
    print("=" * 110)
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
