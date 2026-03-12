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

# Regime filter choices (subset of REQUIRED_REGIMES; "other"/"unknown" not valid targets)
_REGIME_CHOICES = ("politics", "sports", "new_market")


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
# Explainable ranking output (Gate2RankScore)
# ---------------------------------------------------------------------------

_STATUS_ABBREV = {
    "EXECUTABLE": "EXEC  ",
    "NEAR":       "NEAR  ",
    "EDGE_ONLY":  "EDGE  ",
    "DEPTH_ONLY": "DEPTH ",
    "NO_SIGNAL":  "NONE  ",
}

_COL_STATUS = 6
_COL_SCORE  = 6
_COL_NEW    = 4
_COL_REGIME = 10


def score_and_rank_candidates(
    results: list[CandidateResult],
    *,
    market_meta: Optional[dict] = None,
    reward_configs: Optional[dict] = None,
    orderbooks: Optional[dict] = None,
    max_size: float = _DEFAULT_MAX_SIZE,
    buffer: float = _DEFAULT_BUFFER,
) -> list:
    """Convert CandidateResult list to Gate2RankScore list and rank.

    Args:
        results:       List of CandidateResult from scan_live_markets or scan_tapes.
        market_meta:   Optional {slug: market_dict} with volume_24h, created_at, etc.
        reward_configs: Optional {slug: reward_config_dict}.
        orderbooks:    Optional {slug: orderbook_dict} for competition score.
        max_size:      Depth threshold matching the strategy sane preset.
        buffer:        Edge buffer matching the strategy sane preset.

    Returns:
        List of Gate2RankScore sorted by rank_gate2_candidates.
    """
    from packages.polymarket.market_selection.scorer import (
        score_gate2_candidate,
        rank_gate2_candidates,
    )

    scored = []
    for r in results:
        scored.append(
            score_gate2_candidate(
                r.slug,
                executable_ticks=r.executable_ticks,
                edge_ok_ticks=r.edge_ok_ticks,
                depth_ok_ticks=r.depth_ok_ticks,
                best_edge_raw=r.best_edge,
                depth_yes=r.max_depth_yes,
                depth_no=r.max_depth_no,
                market=(market_meta or {}).get(r.slug),
                reward_config=(reward_configs or {}).get(r.slug),
                orderbook=(orderbooks or {}).get(r.slug),
                source=r.source,
                max_size=max_size,
                buffer=buffer,
            )
        )
    return rank_gate2_candidates(scored)


def _ranked_header_line() -> str:
    return (
        f"{'Market':<{_COL_SLUG}} | "
        f"{'Status':>{_COL_STATUS}} | "
        f"{'Score':>{_COL_SCORE}} | "
        f"{'Exec':>{_COL_EXEC}} | "
        f"{'BestEdge':>{_COL_BEST_EDGE}} | "
        f"{'MaxDepth YES/NO':>{_COL_MAX_DEPTH}} | "
        f"{'New?':>{_COL_NEW}} | "
        f"{'Regime':<{_COL_REGIME}}"
    )


def print_ranked_table(
    scores: list,
    top: int,
    mode: str,
    max_size: float = _DEFAULT_MAX_SIZE,
    buffer: float = _DEFAULT_BUFFER,
    explain: bool = False,
) -> None:
    """Print the ranked Gate2RankScore table to stdout.

    Args:
        scores:   Sorted list of Gate2RankScore.
        top:      How many rows to print.
        mode:     "live" or "tape".
        max_size: Depth threshold (for footer).
        buffer:   Edge buffer (for footer).
        explain:  If True, print the full factor breakdown after each row.
    """
    if not scores:
        print("No candidate signal found.")
        return

    threshold = 1.0 - buffer
    header = _ranked_header_line()
    sep = "-" * len(header)
    print(header)
    print(sep)

    for s in scores[:top]:
        status_abbrev = _STATUS_ABBREV.get(s.gate2_status, s.gate2_status[:6])
        score_str = f"{s.rank_score:.3f}"

        if s.best_edge is not None:
            edge_val = f"{s.best_edge:+.4f}"
        else:
            edge_val = "   N/A"

        depth_val = f"{s.depth_yes:.0f} / {s.depth_no:.0f}"
        new_str = "Y" if s.is_new_market is True else ("N" if s.is_new_market is False else "?")
        regime_str = (s.regime or "?")[:_COL_REGIME]
        slug_col = s.slug[:_COL_SLUG]

        print(
            f"{slug_col:<{_COL_SLUG}} | "
            f"{status_abbrev:>{_COL_STATUS}} | "
            f"{score_str:>{_COL_SCORE}} | "
            f"{str(s.executable_ticks):>{_COL_EXEC}} | "
            f"{edge_val:>{_COL_BEST_EDGE}} | "
            f"{depth_val:>{_COL_MAX_DEPTH}} | "
            f"{new_str:>{_COL_NEW}} | "
            f"{regime_str:<{_COL_REGIME}}"
        )

        if explain:
            for line in s.explanation:
                print(f"    {line}")
            print()

    print(sep)
    shown = min(top, len(scores))
    total = len(scores)
    note = " (snapshot)" if mode == "live" else ""
    executable_count = sum(1 for s in scores if s.executable_ticks > 0)
    print(
        f"Showed {shown}/{total} candidates. "
        f"Mode: {mode}{note}. "
        f"Executable: {executable_count}. "
        f"Threshold: sum_ask < {threshold:.4f}, depth >= {max_size:.0f} shares."
    )
    print(
        "NOTE: rank_score combines depth+edge proximity (50%) with reward/volume/"
        "competition/age (50%). A high score is NOT the same as Gate 2 tradable."
    )
    if any(s.is_new_market is True for s in scores[:top]):
        print(
            "NEW MARKET detected: markets < 48h old have different spread dynamics. "
            "Label tape with --regime new_market during capture."
        )


# ---------------------------------------------------------------------------
# Regime-aware capture threshold resolution
# ---------------------------------------------------------------------------


def resolve_effective_threshold(
    explicit_buffer: Optional[float],
    regime: Optional[str],
) -> tuple[float, str]:
    """Resolve the effective near-edge capture threshold and label its source.

    The threshold defines when a market is capture-eligible for watch/record
    tools: ``yes_ask + no_ask < threshold``.  Thresholds > 1.0 fire before a
    profitable arb exists (near-miss detection); thresholds < 1.0 require
    actual arb.

    Priority: explicit_buffer > regime_default > global_default.

    Args:
        explicit_buffer: If provided (user passed ``--buffer``), convert to
                         threshold: ``threshold = 1.0 - explicit_buffer``.
        regime:          When ``explicit_buffer`` is None and regime is set,
                         use the per-regime capture threshold from
                         :data:`REGIME_CAPTURE_NEAR_EDGE_DEFAULTS`.

    Returns:
        ``(threshold, source_label)`` where ``source_label`` is one of
        ``"user-set"``, ``"regime-default"``, or ``"global-default"``.
    """
    from packages.polymarket.market_selection.regime_policy import (
        get_regime_capture_threshold,
        _DEFAULT_CAPTURE_THRESHOLD,
    )

    if explicit_buffer is not None:
        return 1.0 - explicit_buffer, "user-set"
    if regime is not None:
        return get_regime_capture_threshold(regime), "regime-default"
    return _DEFAULT_CAPTURE_THRESHOLD, "global-default"


# ---------------------------------------------------------------------------
# Regime-inventory discovery helpers
# ---------------------------------------------------------------------------


def _build_live_regime_meta(max_fetch: int = 200) -> "dict[str, dict]":
    """Fetch enriched market metadata from Gamma and classify regimes.

    Returns a ``{slug: enriched_market_dict}`` mapping where each dict has the
    ``regime``, ``regime_source``, ``age_hours``, and ``is_new_market`` fields
    added by :func:`enrich_with_regime`.

    Uses a broad fetch (``min_volume=0``) so that low-volume politics / new-market
    candidates are not silently excluded by the default volume gate.
    """
    from packages.polymarket.market_selection.api_client import fetch_active_markets
    from packages.polymarket.market_selection.regime_policy import enrich_with_regime

    try:
        markets = fetch_active_markets(min_volume=0, limit=max_fetch)
    except Exception as exc:
        logger.warning("fetch_active_markets failed during regime enrichment: %s", exc)
        return {}

    meta: dict[str, dict] = {}
    for m in markets:
        slug = str(m.get("slug") or "").strip()
        if slug:
            meta[slug] = enrich_with_regime(m)
    return meta


def _read_tape_market_fields(tape_dir: Path) -> "dict | None":
    """Extract market metadata fields from a tape directory's meta files.

    Searches ``meta.json``, ``watch_meta.json``, and ``prep_meta.json`` in order.
    Extracts fields useful for regime classification: ``slug``, ``created_at``,
    ``age_hours``, ``category``, ``tags``, ``question``, ``title``, and any
    operator-provided ``regime`` label.

    Returns a flat market-like dict, or ``None`` if no readable metadata found.
    """
    _REGIME_META_FILES = ("meta.json", "watch_meta.json", "prep_meta.json")
    _REGIME_FIELDS = (
        "market_slug", "slug", "market", "regime", "created_at", "age_hours",
        "category", "tags", "question", "title", "event_slug",
    )

    for meta_filename in _REGIME_META_FILES:
        meta_file = tape_dir / meta_filename
        if not meta_file.exists():
            continue
        try:
            raw = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            continue

        # Try context blocks first (shadow_context / quickrun_context carry most metadata)
        for ctx_key in ("quickrun_context", "shadow_context"):
            ctx = raw.get(ctx_key)
            if not isinstance(ctx, dict):
                continue
            fields: dict = {}
            for f in _REGIME_FIELDS:
                val = ctx.get(f)
                if val is not None:
                    fields[f] = val
            if fields:
                if "slug" not in fields:
                    fields["slug"] = fields.get("market_slug") or fields.get("market") or ""
                return fields

        # Fall back to top-level fields
        fields = {}
        for f in _REGIME_FIELDS:
            val = raw.get(f)
            if val is not None:
                fields[f] = val
        if fields:
            if "slug" not in fields:
                fields["slug"] = fields.get("market_slug") or fields.get("market") or ""
            return fields

    return None


def _build_tape_regime_meta(tapes_dir: Path) -> "dict[str, dict]":
    """Build ``{slug: enriched_market_dict}`` regime metadata from tape directories.

    Each tape directory is inspected for meta files.  Available fields are fed
    through :func:`enrich_with_regime` so that UNKNOWN/off-target tapes get
    ``regime='other'`` and are never silently promoted to a named regime.
    """
    from packages.polymarket.market_selection.regime_policy import enrich_with_regime

    meta: dict[str, dict] = {}
    try:
        tape_dirs = sorted(p for p in tapes_dir.iterdir() if p.is_dir())
    except Exception:
        return meta

    for tape_dir in tape_dirs:
        slug = _slug_from_tape_dir(tape_dir)
        fields = _read_tape_market_fields(tape_dir)
        if fields is None:
            # No meta found: create a minimal dict so the classifier still runs
            fields = {"slug": slug}
        elif "slug" not in fields:
            fields["slug"] = slug
        enriched = enrich_with_regime(fields)
        meta[slug] = enriched

    return meta


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
        default=None,
        metavar="F",
        help=(
            f"Gate 2 scoring buffer. Strategy enters when sum_ask < 1 - buffer. "
            f"Default: {_DEFAULT_BUFFER}. "
            "This controls Gate 2 pass criteria only. "
            "Regime-aware capture thresholds (for near-miss detection) are "
            "separate and do not affect Gate 2 scoring."
        ),
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
    p.add_argument(
        "--explain",
        action="store_true",
        help="Show full factor breakdown for each candidate (reward, volume, competition, age, regime).",
    )
    p.add_argument(
        "--regime",
        choices=_REGIME_CHOICES,
        default=None,
        metavar="REGIME",
        help=(
            "Filter output to a specific regime: politics | sports | new_market. "
            "Bypasses the signal-only filter so ALL matching markets are shown, "
            "not just those with Gate 2 edge/depth signal. "
            "UNKNOWN/off-target markets are never included. "
            "For live mode, fetches enriched Gamma metadata; for tape mode, reads tape meta files."
        ),
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(level=log_level, format="%(levelname)s %(name)s: %(message)s")

    max_size: float = args.max_size
    top: int = args.top

    # Gate 2 scoring buffer — always uses the user-provided --buffer or the
    # global default (0.01).  Regime selection does NOT change Gate 2 scoring.
    gate2_buffer: float = args.buffer if args.buffer is not None else _DEFAULT_BUFFER

    # Regime-aware capture threshold — used for near-miss detection in
    # watch/capture tools and for provenance reporting only.  May be > 1.0 for
    # politics / new_market (fires before arb is fully profitable).
    capture_threshold, threshold_source = resolve_effective_threshold(
        args.buffer, args.regime
    )

    if max_size <= 0:
        print("Error: --max-size must be positive.", file=sys.stderr)
        return 1
    if not (0.0 < gate2_buffer < 1.0):
        print("Error: --buffer must be between 0 and 1.", file=sys.stderr)
        return 1

    if args.tapes_dir:
        tapes_dir = Path(args.tapes_dir)
        if not tapes_dir.is_dir():
            print(f"Error: --tapes-dir '{tapes_dir}' is not a directory.", file=sys.stderr)
            return 1
        _regime_label = f"  regime={args.regime}" if args.regime else ""
        print(
            f"[scan-gate2] Scanning tapes in: {tapes_dir}"
            f"  max_size={max_size}  gate2_buffer={gate2_buffer:.4f}"
            f"  capture_threshold={capture_threshold:.4f} ({threshold_source})"
            f"{_regime_label}",
            file=sys.stderr,
        )
        results = scan_tapes(tapes_dir, max_size=max_size, buffer=gate2_buffer)
        mode = "tape"
    else:
        _regime_label = f"  regime={args.regime}" if args.regime else ""
        print(
            f"[scan-gate2] Scanning live markets"
            f"  candidates={args.candidates}  max_size={max_size}"
            f"  gate2_buffer={gate2_buffer:.4f}"
            f"  capture_threshold={capture_threshold:.4f} ({threshold_source})"
            f"{_regime_label}",
            file=sys.stderr,
        )
        results = scan_live_markets(
            max_size=max_size,
            buffer=gate2_buffer,
            max_candidates=args.candidates,
        )
        mode = "live"

    ranked = rank_candidates(results)

    # --- Regime-inventory discovery: filter and enrich by target regime ----------
    regime_meta: "dict[str, dict]" = {}
    if args.regime:
        if args.tapes_dir:
            regime_meta = _build_tape_regime_meta(Path(args.tapes_dir))
        else:
            fetch_count = max(args.candidates * 2, 200)
            print(
                f"[scan-gate2] Regime filter '{args.regime}': fetching enriched metadata "
                f"(limit={fetch_count}, min_volume=0) …",
                file=sys.stderr,
            )
            regime_meta = _build_live_regime_meta(max_fetch=fetch_count)

        # Show ALL matching-regime candidates independent of Gate2 signal (bypass signal filter)
        signal_raw = [
            r for r in ranked
            if regime_meta.get(r.slug, {}).get("regime") == args.regime
        ]
        regime_count = sum(
            1 for m in regime_meta.values() if m.get("regime") == args.regime
        )
        print(
            f"[scan-gate2] Regime '{args.regime}': {len(signal_raw)} of {len(ranked)} "
            f"scanned markets matched ({regime_count} total in metadata pool).",
            file=sys.stderr,
        )
        if not signal_raw:
            print(
                f"[scan-gate2] No '{args.regime}' markets found. "
                "The regime is absent in this scan batch — not just ranked low.",
                file=sys.stderr,
            )
            print(
                f"regime_used={args.regime}  near_edge_threshold_used={capture_threshold:.4f}"
                f"  gate2_buffer_used={gate2_buffer:.4f}  threshold_source={threshold_source}"
            )
            return 0
    # --- Normal signal filter (no --regime) ------------------------------------
    elif not args.all:
        signal_raw = [r for r in ranked if r.depth_ok_ticks > 0 or r.edge_ok_ticks > 0]
        if not signal_raw and ranked:
            print(
                "[scan-gate2] No markets with depth or edge signal. "
                "Showing top results anyway (use --all to suppress this filter).",
                file=sys.stderr,
            )
            signal_raw = ranked[:top]
    else:
        signal_raw = ranked

    ranked_scores = score_and_rank_candidates(
        signal_raw,
        market_meta=regime_meta if regime_meta else None,
        max_size=max_size,
        buffer=gate2_buffer,
    )

    print_ranked_table(
        ranked_scores,
        top=top,
        mode=mode,
        max_size=max_size,
        buffer=gate2_buffer,
        explain=args.explain,
    )

    # Regime + threshold provenance line: always printed so artifacts/logs
    # unambiguously record which capture threshold was actually used and why.
    if args.regime:
        print(
            f"regime_used={args.regime}  near_edge_threshold_used={capture_threshold:.4f}"
            f"  gate2_buffer_used={gate2_buffer:.4f}  threshold_source={threshold_source}"
        )
    elif threshold_source != "global-default":
        print(
            f"near_edge_threshold_used={capture_threshold:.4f}"
            f"  gate2_buffer_used={gate2_buffer:.4f}  threshold_source={threshold_source}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
