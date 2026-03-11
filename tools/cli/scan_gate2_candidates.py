"""Diagnostic market scanner for Gate 2 binary_complement_arb candidates.

Scans live Polymarket markets or local tape files and ranks them by how likely
they are to produce an executable Gate 2 tape for the binary_complement_arb
strategy under the 'sane' preset (max_size=50, buffer=0.01).

Gate 2 entry requires BOTH conditions simultaneously:
  1. depth_ok:  both YES and NO best-ask sizes >= max_size (default: 50)
  2. edge_ok:   yes_ask + no_ask < 1 - buffer (default: < 0.99)

Usage
-----
  # Scan live markets (default):
  python -m polytool scan-gate2-candidates

  # Scan local tape directories:
  python -m polytool scan-gate2-candidates --tapes-dir artifacts/simtrader/tapes

  # Show all markets (not just those with signal):
  python -m polytool scan-gate2-candidates --all --top 50

  # Use custom strategy parameters:
  python -m polytool scan-gate2-candidates --max-size 50 --buffer 0.01

Output columns
--------------
  Exec    : ticks (or snapshot slots) where depth_ok AND edge_ok
  Edge    : ticks where yes_ask + no_ask < threshold
  Depth   : ticks where both ask sizes >= max_size
  BestEdge: best observed (threshold - sum_ask); positive = arb window existed
  MaxDepth: peak best-ask size for YES / NO leg
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Strategy 'sane' preset defaults (must match strategy_presets.py)
# ---------------------------------------------------------------------------

_DEFAULT_MAX_SIZE: float = 50.0
_DEFAULT_BUFFER: float = 0.01
_DEFAULT_LIVE_CANDIDATES: int = 50
_DEFAULT_TOP: int = 20


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class CandidateResult:
    """Scoring result for one market (or tape)."""

    slug: str
    total_ticks: int
    depth_ok_ticks: int
    edge_ok_ticks: int
    executable_ticks: int
    best_edge: float        # max(threshold - sum_ask) observed; positive = edge existed
    max_depth_yes: float    # peak best-ask size for first asset (YES)
    max_depth_no: float     # peak best-ask size for second asset (NO)
    source: str = "live"    # "live" or "tape"

    @property
    def executable(self) -> bool:
        return self.executable_ticks > 0

    @property
    def depth_ok(self) -> bool:
        return self.depth_ok_ticks > 0

    @property
    def edge_ok(self) -> bool:
        return self.edge_ok_ticks > 0


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


def rank_candidates(results: list[CandidateResult]) -> list[CandidateResult]:
    """Sort candidates by executability, then edge quality, then depth.

    Ranking key (all descending):
      1. executable_ticks   — most simultaneously executable ticks first
      2. edge_ok_ticks      — most edge ticks (even if depth failed)
      3. depth_ok_ticks     — most depth ticks (even if edge failed)
      4. best_edge          — closest-to-threshold (or furthest above) edge
      5. min(yes, no) depth — best worst-leg depth
    """

    def _key(r: CandidateResult) -> tuple:
        return (
            r.executable_ticks,
            r.edge_ok_ticks,
            r.depth_ok_ticks,
            r.best_edge,
            min(r.max_depth_yes, r.max_depth_no),
        )

    return sorted(results, key=_key, reverse=True)


# ---------------------------------------------------------------------------
# Snapshot scoring (used by both live and tape modes)
# ---------------------------------------------------------------------------


def _best_ask_price_and_size(asks: list) -> tuple[Optional[float], Optional[float]]:
    """Return (best_ask_price, best_ask_size) from a list of CLOB ask levels.

    Levels may be dicts ``{"price": "0.55", "size": "100"}`` or
    ``[price, size]`` tuples.
    """
    best_price: Optional[float] = None
    best_size: Optional[float] = None
    for lvl in asks:
        if isinstance(lvl, dict):
            raw_p = lvl.get("price") or lvl.get("p")
            raw_s = lvl.get("size") or lvl.get("s")
        elif isinstance(lvl, (list, tuple)) and len(lvl) >= 2:
            raw_p, raw_s = lvl[0], lvl[1]
        else:
            continue
        try:
            p = float(raw_p)
            s = float(raw_s)
        except (TypeError, ValueError):
            continue
        if best_price is None or p < best_price:
            best_price = p
            best_size = s
    return best_price, best_size


def score_snapshot(
    yes_asks: list,
    no_asks: list,
    *,
    max_size: float = _DEFAULT_MAX_SIZE,
    buffer: float = _DEFAULT_BUFFER,
) -> dict:
    """Score a single orderbook snapshot for Gate 2 executability.

    Args:
        yes_asks:  Ask levels for the YES token (list of dicts or [p, s] pairs).
        no_asks:   Ask levels for the NO token.
        max_size:  Required size at best ask per leg.
        buffer:    Edge buffer; entry when sum_ask < 1 - buffer.

    Returns dict with keys:
        yes_ask, no_ask, yes_ask_size, no_ask_size,
        sum_ask, edge_gap, depth_ok, edge_ok, executable
    """
    threshold = 1.0 - buffer
    yes_ask, yes_size = _best_ask_price_and_size(yes_asks)
    no_ask, no_size = _best_ask_price_and_size(no_asks)

    result: dict = {
        "yes_ask": yes_ask,
        "no_ask": no_ask,
        "yes_ask_size": yes_size,
        "no_ask_size": no_size,
        "sum_ask": None,
        "edge_gap": None,
        "depth_ok": False,
        "edge_ok": False,
        "executable": False,
    }

    if yes_ask is None or no_ask is None or yes_size is None or no_size is None:
        return result

    sum_ask = yes_ask + no_ask
    edge_gap = threshold - sum_ask
    depth_ok = yes_size >= max_size and no_size >= max_size
    edge_ok = sum_ask < threshold

    result.update({
        "sum_ask": sum_ask,
        "edge_gap": edge_gap,
        "depth_ok": depth_ok,
        "edge_ok": edge_ok,
        "executable": depth_ok and edge_ok,
    })
    return result


# ---------------------------------------------------------------------------
# Live market scan
# ---------------------------------------------------------------------------


def scan_live_markets(
    *,
    max_size: float = _DEFAULT_MAX_SIZE,
    buffer: float = _DEFAULT_BUFFER,
    max_candidates: int = _DEFAULT_LIVE_CANDIDATES,
) -> list[CandidateResult]:
    """Fetch active binary markets and score their current orderbook snapshot.

    Each market contributes exactly 1 tick to the result (the current snapshot).
    Uses MarketPicker to resolve YES/NO token IDs, then re-fetches both books
    for scoring.

    Args:
        max_size:       Required depth at best ask per leg (shares).
        buffer:         Edge buffer for complement sum threshold.
        max_candidates: Maximum number of binary markets to resolve and score.

    Returns:
        List of CandidateResult, one per market successfully scanned.
    """
    from packages.polymarket.clob import ClobClient
    from packages.polymarket.gamma import GammaClient
    from packages.polymarket.simtrader.market_picker import MarketPicker

    gamma = GammaClient()
    clob = ClobClient()
    picker = MarketPicker(gamma, clob)

    threshold = 1.0 - buffer
    skips: list[dict] = []

    resolved_markets = picker.auto_pick_many(
        n=max_candidates,
        max_candidates=max_candidates,
        allow_empty_book=False,
        collect_skips=skips,
    )

    logger.debug("Resolved %d binary markets; %d skipped", len(resolved_markets), len(skips))

    results: list[CandidateResult] = []
    for resolved in resolved_markets:
        try:
            yes_book = clob.fetch_book(resolved.yes_token_id)
            no_book = clob.fetch_book(resolved.no_token_id)
        except Exception as exc:
            logger.debug("fetch_book failed for %r: %s", resolved.slug, exc)
            continue

        yes_asks = (yes_book.get("asks") or []) if isinstance(yes_book, dict) else []
        no_asks = (no_book.get("asks") or []) if isinstance(no_book, dict) else []

        snap = score_snapshot(yes_asks, no_asks, max_size=max_size, buffer=buffer)

        sum_ask = snap["sum_ask"]
        yes_size = snap["yes_ask_size"] or 0.0
        no_size = snap["no_ask_size"] or 0.0
        edge_gap = snap["edge_gap"]
        # best_edge: use a sentinel that sorts below any real edge when no data
        best_edge = float(edge_gap) if edge_gap is not None else (threshold - 99.0)

        results.append(CandidateResult(
            slug=resolved.slug,
            total_ticks=1 if sum_ask is not None else 0,
            depth_ok_ticks=1 if snap["depth_ok"] else 0,
            edge_ok_ticks=1 if snap["edge_ok"] else 0,
            executable_ticks=1 if snap["executable"] else 0,
            best_edge=best_edge,
            max_depth_yes=float(yes_size),
            max_depth_no=float(no_size),
            source="live",
        ))

    return results


# ---------------------------------------------------------------------------
# Tape scan
# ---------------------------------------------------------------------------


def _best_ask_size_l2(book) -> Optional[float]:
    """Return the size at the best (lowest) ask level from an L2Book."""
    asks: dict = getattr(book, "_asks", {})
    if not asks:
        return None
    _, size = min(
        ((Decimal(p), s) for p, s in asks.items()),
        key=lambda row: row[0],
    )
    return float(size)


def _slug_from_tape_dir(tape_dir: Path) -> str:
    """Try to read the market slug from meta.json; fall back to dir name."""
    meta_file = tape_dir / "meta.json"
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            for ctx_key in ("quickrun_context", "shadow_context"):
                ctx = meta.get(ctx_key)
                if isinstance(ctx, dict):
                    market = ctx.get("market") or ctx.get("market_slug")
                    if market:
                        return str(market)
        except Exception:
            pass
    return tape_dir.name


def scan_tapes(
    tapes_dir: Path,
    *,
    max_size: float = _DEFAULT_MAX_SIZE,
    buffer: float = _DEFAULT_BUFFER,
) -> list[CandidateResult]:
    """Replay local tape files and score tick-by-tick for Gate 2 criteria.

    Finds all subdirectories under ``tapes_dir`` that contain ``events.jsonl``,
    replays each tape through L2 books, and computes per-tape statistics.

    Args:
        tapes_dir:  Directory containing tape subdirectories.
        max_size:   Required size at best ask per leg (shares).
        buffer:     Edge buffer for complement sum threshold.

    Returns:
        List of CandidateResult, one per tape with at least one scoreable tick.
    """
    from packages.polymarket.simtrader.orderbook.l2book import L2Book
    from packages.polymarket.simtrader.tape.schema import (
        EVENT_TYPE_BOOK,
        EVENT_TYPE_PRICE_CHANGE,
    )

    threshold = 1.0 - buffer
    results: list[CandidateResult] = []

    tape_dirs = sorted(p for p in tapes_dir.iterdir() if p.is_dir())
    logger.debug("Found %d potential tape directories under %s", len(tape_dirs), tapes_dir)

    for tape_dir in tape_dirs:
        events_file = tape_dir / "events.jsonl"
        if not events_file.exists():
            logger.debug("Skipping %s: no events.jsonl", tape_dir.name)
            continue

        # Load all events
        events: list[dict] = []
        with open(events_file, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        # Discover asset IDs from book events and price_change batches
        seen_assets: list[str] = []
        for evt in events:
            et = evt.get("event_type")
            if et == EVENT_TYPE_BOOK:
                aid = str(evt.get("asset_id") or "")
                if aid and aid not in seen_assets:
                    seen_assets.append(aid)
            elif et == EVENT_TYPE_PRICE_CHANGE and "price_changes" in evt:
                for entry in evt.get("price_changes", []):
                    if isinstance(entry, dict):
                        aid = str(entry.get("asset_id") or "")
                        if aid and aid not in seen_assets:
                            seen_assets.append(aid)

        if len(seen_assets) < 2:
            logger.debug(
                "Skipping %s: only %d distinct assets found (need 2)",
                tape_dir.name, len(seen_assets),
            )
            continue

        aid_a, aid_b = seen_assets[0], seen_assets[1]
        books: dict[str, object] = {
            aid_a: L2Book(aid_a, strict=False),
            aid_b: L2Book(aid_b, strict=False),
        }
        slug = _slug_from_tape_dir(tape_dir)

        # Replay and score each event
        total_ticks = 0
        depth_ok_ticks = 0
        edge_ok_ticks = 0
        executable_ticks = 0
        best_edge = threshold - 99.0  # sentinel: no edge seen
        max_depth_a = 0.0
        max_depth_b = 0.0

        for evt in events:
            et = evt.get("event_type")

            # Update books
            if et == EVENT_TYPE_BOOK:
                aid = str(evt.get("asset_id") or "")
                if aid in books:
                    books[aid].apply(evt)  # type: ignore[union-attr]
            elif et == EVENT_TYPE_PRICE_CHANGE:
                if "price_changes" in evt:
                    for entry in evt.get("price_changes", []):
                        if isinstance(entry, dict):
                            aid = str(entry.get("asset_id") or "")
                            if aid in books:
                                books[aid].apply_single_delta(entry)  # type: ignore[union-attr]
                else:
                    aid = str(evt.get("asset_id") or "")
                    if aid in books:
                        books[aid].apply(evt)  # type: ignore[union-attr]
            else:
                continue  # last_trade_price / tick_size_change: don't score

            # Score current state of the two L2 books
            ask_a = books[aid_a].best_ask  # type: ignore[union-attr]
            ask_b = books[aid_b].best_ask  # type: ignore[union-attr]
            if ask_a is None or ask_b is None:
                continue

            size_a = _best_ask_size_l2(books[aid_a])
            size_b = _best_ask_size_l2(books[aid_b])
            if size_a is None or size_b is None:
                continue

            total_ticks += 1
            sum_ask = ask_a + ask_b
            edge_gap = threshold - sum_ask
            depth_ok = size_a >= max_size and size_b >= max_size
            edge_ok = sum_ask < threshold

            if depth_ok:
                depth_ok_ticks += 1
            if edge_ok:
                edge_ok_ticks += 1
            if depth_ok and edge_ok:
                executable_ticks += 1

            best_edge = max(best_edge, edge_gap)
            max_depth_a = max(max_depth_a, size_a)
            max_depth_b = max(max_depth_b, size_b)

        if total_ticks == 0:
            logger.debug("Skipping %s: no scoreable ticks", tape_dir.name)
            continue

        results.append(CandidateResult(
            slug=slug,
            total_ticks=total_ticks,
            depth_ok_ticks=depth_ok_ticks,
            edge_ok_ticks=edge_ok_ticks,
            executable_ticks=executable_ticks,
            best_edge=best_edge,
            max_depth_yes=max_depth_a,
            max_depth_no=max_depth_b,
            source="tape",
        ))

    return results


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

_COL_SLUG = 44
_COL_EXEC = 6
_COL_EDGE = 6
_COL_DEPTH = 6
_COL_BEST_EDGE = 9
_COL_MAX_DEPTH = 16


def _header_line() -> str:
    return (
        f"{'Market':<{_COL_SLUG}} | "
        f"{'Exec':>{_COL_EXEC}} | "
        f"{'Edge':>{_COL_EDGE}} | "
        f"{'Depth':>{_COL_DEPTH}} | "
        f"{'BestEdge':>{_COL_BEST_EDGE}} | "
        f"{'MaxDepth YES/NO':>{_COL_MAX_DEPTH}}"
    )


def print_table(
    results: list[CandidateResult],
    top: int,
    mode: str,
    max_size: float = _DEFAULT_MAX_SIZE,
    buffer: float = _DEFAULT_BUFFER,
) -> None:
    """Print the ranked candidate table to stdout."""
    if not results:
        print("No candidate signal found.")
        return

    threshold = 1.0 - buffer
    header = _header_line()
    sep = "-" * len(header)
    print(header)
    print(sep)

    for r in results[:top]:
        exec_str = str(r.executable_ticks)
        edge_str = str(r.edge_ok_ticks)
        depth_str = str(r.depth_ok_ticks)
        # best_edge: show as signed float; sentinel values shown as "N/A"
        if r.best_edge > threshold - 99.0 + 1:
            edge_val = f"{r.best_edge:+.4f}"
        else:
            edge_val = "   N/A"
        depth_val = f"{r.max_depth_yes:.0f} / {r.max_depth_no:.0f}"
        slug_col = r.slug[:_COL_SLUG]
        print(
            f"{slug_col:<{_COL_SLUG}} | "
            f"{exec_str:>{_COL_EXEC}} | "
            f"{edge_str:>{_COL_EDGE}} | "
            f"{depth_str:>{_COL_DEPTH}} | "
            f"{edge_val:>{_COL_BEST_EDGE}} | "
            f"{depth_val:>{_COL_MAX_DEPTH}}"
        )

    print(sep)
    shown = min(top, len(results))
    total = len(results)
    note = " (snapshot)" if mode == "live" else f" (over {results[0].total_ticks if results else 0}+ ticks/tape)"
    print(
        f"Showed {shown}/{total} candidates. "
        f"Mode: {mode}{note}. "
        f"Threshold: sum_ask < {threshold:.4f}, depth >= {max_size:.0f} shares."
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="scan-gate2-candidates",
        description=(
            "Rank live Polymarket markets (or local tapes) by Gate 2 executability "
            "for binary_complement_arb. Identifies markets with complement edge "
            "(yes_ask + no_ask < threshold) and sufficient depth at best ask."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--tapes-dir",
        default=None,
        metavar="DIR",
        help="Scan local tape directories instead of live markets.",
    )
    p.add_argument(
        "--max-size",
        type=float,
        default=_DEFAULT_MAX_SIZE,
        metavar="N",
        help="Required best-ask size per leg (shares). Must match strategy max_size.",
    )
    p.add_argument(
        "--buffer",
        type=float,
        default=_DEFAULT_BUFFER,
        metavar="F",
        help="Entry buffer. Strategy enters when sum_ask < 1 - buffer.",
    )
    p.add_argument(
        "--candidates",
        type=int,
        default=_DEFAULT_LIVE_CANDIDATES,
        metavar="N",
        help="Max binary markets to resolve and score (live mode only).",
    )
    p.add_argument(
        "--top",
        type=int,
        default=_DEFAULT_TOP,
        metavar="N",
        help="Number of table rows to print.",
    )
    p.add_argument(
        "--all",
        action="store_true",
        help="Show all markets including those with zero signal.",
    )
    p.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(level=log_level, format="%(levelname)s %(name)s: %(message)s")

    max_size: float = args.max_size
    buffer: float = args.buffer
    top: int = args.top

    if max_size <= 0:
        print("Error: --max-size must be positive.", file=sys.stderr)
        return 1
    if not (0.0 < buffer < 1.0):
        print("Error: --buffer must be between 0 and 1.", file=sys.stderr)
        return 1

    if args.tapes_dir:
        tapes_dir = Path(args.tapes_dir)
        if not tapes_dir.is_dir():
            print(f"Error: --tapes-dir '{tapes_dir}' is not a directory.", file=sys.stderr)
            return 1
        print(
            f"[scan-gate2] Scanning tapes in: {tapes_dir}"
            f"  max_size={max_size}  buffer={buffer}  threshold={1-buffer:.4f}",
            file=sys.stderr,
        )
        results = scan_tapes(tapes_dir, max_size=max_size, buffer=buffer)
        mode = "tape"
    else:
        print(
            f"[scan-gate2] Scanning live markets"
            f"  candidates={args.candidates}  max_size={max_size}"
            f"  buffer={buffer}  threshold={1-buffer:.4f}",
            file=sys.stderr,
        )
        results = scan_live_markets(
            max_size=max_size,
            buffer=buffer,
            max_candidates=args.candidates,
        )
        mode = "live"

    ranked = rank_candidates(results)

    if not args.all:
        signal = [r for r in ranked if r.depth_ok_ticks > 0 or r.edge_ok_ticks > 0]
        if not signal and ranked:
            print(
                "[scan-gate2] No markets with depth or edge signal. "
                "Showing top results anyway (use --all to suppress this filter).",
                file=sys.stderr,
            )
            signal = ranked[:top]
    else:
        signal = ranked

    print_table(signal, top=top, mode=mode, max_size=max_size, buffer=buffer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
