"""Dislocation watch + auto-record for binary_complement_arb candidates.

Polls a user-specified watchlist of market slugs at a configurable interval.
When the *near-edge trigger* fires for a market:
  - both YES and NO best-ask sizes >= --min-depth
  - yes_ask + no_ask < --near-edge threshold (default 1.00; strategy enters at < 0.99)

...tape recording starts automatically for that market.

This is diagnostic capture logic, not strategy logic.
  - Does NOT change strategy entry thresholds (0.99 buffer)
  - Does NOT change preset sizing (max_size=50)
  - Does NOT change gate rules

Usage
-----
  # Monitor two markets, trigger at sum_ask < 1.00 with 50-share depth:
  python -m polytool watch-arb-candidates --markets slug1,slug2

  # Seed the watcher from a session pack (sets threshold from regime automatically):
  python -m polytool watch-arb-candidates --session-plan artifacts/debug/session_packs/pack.json

  # Seed the watcher from a report-derived watchlist file:
  python -m polytool watch-arb-candidates --watchlist-file artifacts/watchlist.json

  # Tighter trigger — only record when very close to the strategy entry threshold:
  python -m polytool watch-arb-candidates --markets slug1,slug2 --near-edge 0.995

  # Custom poll interval and recording duration:
  python -m polytool watch-arb-candidates --markets slug1,slug2 \\
      --poll-interval 15 --duration 300

  # Dry-run: resolve markets and print trigger evaluations without recording:
  python -m polytool watch-arb-candidates --markets slug1,slug2 --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULT_NEAR_EDGE: float = 1.00   # near-edge trigger; strategy enters at < 0.99
_DEFAULT_MIN_DEPTH: float = 50.0   # shares at best ask per leg (matches sane preset)
_DEFAULT_POLL_INTERVAL: float = 30.0  # seconds between book polls per market
_DEFAULT_DURATION: float = 300.0   # tape recording duration in seconds
_DEFAULT_TAPES_BASE = Path("artifacts/tapes/gold")
_DEFAULT_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
_DEFAULT_MAX_CONCURRENT: int = 2   # max simultaneously recording markets

# Provenance sentinel — used when threshold comes from a session plan
_SOURCE_SESSION_PLAN: str = "session-plan"


# ---------------------------------------------------------------------------
# Resolved market info
# ---------------------------------------------------------------------------


@dataclass
class ResolvedWatch:
    """YES/NO token IDs and metadata for one watched market."""

    slug: str
    yes_token_id: str
    no_token_id: str
    regime: str = "unknown"
    market_snapshot: Optional[dict] = field(default=None)


@dataclass(frozen=True)
class WatchTarget:
    """One requested market slug plus optional watchlist metadata."""

    slug: str
    metadata: dict[str, Any] = field(default_factory=dict)
    source: str = "markets"


def _parse_watchlist_timestamp(text: str, *, field_name: str, row_number: int) -> datetime:
    """Parse a watchlist timestamp into an aware UTC datetime."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError(
            f"watchlist[{row_number}] field {field_name!r} must be a non-empty ISO-8601 string."
        )

    try:
        parsed = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            f"watchlist[{row_number}] field {field_name!r} must be valid ISO-8601."
        ) from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_markets_arg(markets: Optional[list[str]]) -> list[WatchTarget]:
    """Parse direct --markets input into watch targets.

    Accepts either space-separated tokens (from ``nargs="+"`` argparse) or
    comma-separated slugs within a single token, or a mix of both.
    """
    if not markets:
        return []

    slugs: list[str] = []
    for token in markets:
        for part in token.split(","):
            part = part.strip()
            if part:
                slugs.append(part)

    return [WatchTarget(slug=slug, source="markets") for slug in slugs]


def _load_watchlist_file(path: str | Path, *, now: Optional[datetime] = None) -> list[WatchTarget]:
    """Load a watchlist file and return non-expired watch targets.

    Two formats are supported:

    * **JSON** (``*.json`` extension or content starting with ``{``/``[``):
      A JSON object with a top-level ``watchlist`` array.  Each element must be
      an object containing at least ``market_slug``.

    * **Slug-per-line** (any other extension): one market slug per non-blank
      line.  Blank lines are silently skipped.
    """
    watchlist_path = Path(path)
    try:
        raw_text = watchlist_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"watchlist file not found: {watchlist_path}") from exc

    stripped = raw_text.strip()
    if not stripped:
        raise ValueError("watchlist file is empty")

    # Determine format: JSON extension or content that looks like JSON.
    suffix_lower = watchlist_path.suffix.lower()
    looks_like_json = suffix_lower == ".json" or stripped.startswith(("{", "["))

    if looks_like_json:
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"watchlist file looks like JSON but is not valid JSON: {watchlist_path}"
            ) from exc

        if not isinstance(payload, dict):
            raise ValueError("watchlist file must be a JSON object with a top-level 'watchlist' array.")

        watchlist = payload.get("watchlist")
        if not isinstance(watchlist, list):
            raise ValueError("watchlist file must include a top-level 'watchlist' array.")

        now_utc = now or datetime.now(timezone.utc)
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)
        else:
            now_utc = now_utc.astimezone(timezone.utc)

        targets: list[WatchTarget] = []
        for row_number, item in enumerate(watchlist, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"watchlist[{row_number}] must be an object.")

            slug_raw = item.get("market_slug")
            if not isinstance(slug_raw, str) or not slug_raw.strip():
                raise ValueError(f"watchlist[{row_number}] missing required 'market_slug'.")

            slug = slug_raw.strip()
            expiry_utc = item.get("expiry_utc")
            if expiry_utc is not None:
                expiry_dt = _parse_watchlist_timestamp(
                    expiry_utc,
                    field_name="expiry_utc",
                    row_number=row_number,
                )
                if expiry_dt <= now_utc:
                    logger.debug(
                        "Skipping expired watchlist entry slug=%s expiry_utc=%s source=%s",
                        slug,
                        expiry_utc,
                        watchlist_path,
                    )
                    continue

            metadata = {key: value for key, value in item.items() if key != "market_slug"}
            targets.append(
                WatchTarget(
                    slug=slug,
                    metadata=metadata,
                    source=f"watchlist-file:{watchlist_path}",
                )
            )

        return targets

    # Slug-per-line format
    targets = []
    for line_number, line in enumerate(raw_text.splitlines(), start=1):
        slug = line.strip()
        if not slug:
            continue
        if "," in slug:
            raise ValueError(
                f"watchlist file line {line_number}: expected one market slug per non-blank line, "
                f"but found a comma. Use a JSON watchlist for multiple slugs per entry, or put "
                f"one slug per line."
            )
        targets.append(
            WatchTarget(
                slug=slug,
                metadata={},
                source=f"watchlist-file:{watchlist_path}",
            )
        )
    return targets


def _merge_watch_targets(*sources: list[WatchTarget]) -> list[WatchTarget]:
    """Deduplicate watch targets by slug while preserving the first-seen order."""
    merged: list[WatchTarget] = []
    index_by_slug: dict[str, int] = {}

    for source in sources:
        for target in source:
            existing_index = index_by_slug.get(target.slug)
            if existing_index is None:
                index_by_slug[target.slug] = len(merged)
                merged.append(target)
                continue

            existing = merged[existing_index]
            if target.metadata and not existing.metadata:
                merged[existing_index] = WatchTarget(
                    slug=existing.slug,
                    metadata=target.metadata,
                    source=target.source,
                )
                logger.debug(
                    "Merged watchlist metadata onto duplicate slug=%s from %s",
                    target.slug,
                    target.source,
                )
                continue

            logger.debug("Ignoring duplicate watch target slug=%s from %s", target.slug, target.source)

    return merged


def _load_session_plan(path: str | Path) -> dict:
    """Load and validate a session pack JSON produced by make-session-pack.

    Returns the parsed dict.  Raises ValueError if the file is missing,
    unparseable, or does not contain the expected ``watch_config`` block.
    """
    session_path = Path(path)
    try:
        payload = json.loads(session_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"session plan file not found: {session_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"session plan file is not valid JSON: {session_path}") from exc

    if not isinstance(payload, dict):
        raise ValueError("session plan must be a JSON object.")

    watch_config = payload.get("watch_config")
    if not isinstance(watch_config, dict):
        raise ValueError(
            "session plan missing 'watch_config' block. "
            "Generate it with: python -m polytool make-session-pack"
        )

    return payload


def _collect_watch_targets(
    *,
    markets: Optional[str],
    watchlist_file: Optional[str],
    session_plan: Optional[dict] = None,
    now: Optional[datetime] = None,
) -> list[WatchTarget]:
    """Collect watch targets from direct CLI input, a watchlist file, and/or a session plan."""
    market_targets = _parse_markets_arg(markets)
    watchlist_targets = _load_watchlist_file(watchlist_file, now=now) if watchlist_file else []

    # Session plan: load watchlist entries from the plan's 'watchlist' array
    plan_targets: list[WatchTarget] = []
    if session_plan is not None:
        for item in session_plan.get("watchlist", []):
            if isinstance(item, dict):
                slug = str(item.get("market_slug", "")).strip()
                if slug:
                    metadata = {k: v for k, v in item.items() if k != "market_slug"}
                    plan_targets.append(
                        WatchTarget(slug=slug, metadata=metadata, source="session-plan")
                    )

    combined = _merge_watch_targets(market_targets, watchlist_targets, plan_targets)

    if not combined:
        raise ValueError(
            "supply at least one non-expired market via "
            "--markets slug1 slug2 (space-separated) or "
            '--markets "slug1,slug2" (comma-separated), '
            "--watchlist-file, or --session-plan."
        )

    return combined


# ---------------------------------------------------------------------------
# Trigger evaluation (pure function — easy to test in isolation)
# ---------------------------------------------------------------------------


@dataclass
class WatchSnapshot:
    """Result of evaluating one CLOB snapshot for the near-edge trigger."""

    slug: str
    yes_ask: Optional[float]
    no_ask: Optional[float]
    yes_ask_size: Optional[float]
    no_ask_size: Optional[float]
    sum_ask: Optional[float]
    near_edge: bool   # sum_ask < near_edge_threshold
    depth_ok: bool    # both sizes >= min_depth
    trigger: bool     # near_edge AND depth_ok


def evaluate_trigger(
    yes_asks: list,
    no_asks: list,
    slug: str,
    *,
    near_edge_threshold: float = _DEFAULT_NEAR_EDGE,
    min_depth: float = _DEFAULT_MIN_DEPTH,
) -> WatchSnapshot:
    """Evaluate one CLOB snapshot for the near-edge trigger.

    Uses the same ``_best_ask_price_and_size`` helper as ``scan_gate2_candidates``
    to parse ask levels in both dict and list-pair formats.

    Args:
        yes_asks:            Ask levels for the YES token (list of dicts or [p, s]).
        no_asks:             Ask levels for the NO token.
        slug:                Market slug (for labeling in output).
        near_edge_threshold: Trigger when yes_ask + no_ask < this value.
                             Default 1.00 is looser than the strategy entry
                             threshold of 0.99, capturing near-miss conditions.
        min_depth:           Required best-ask size per leg in shares.
                             Should match the strategy max_size (default 50).

    Returns:
        WatchSnapshot with trigger=True when near_edge AND depth_ok both hold.
    """
    from tools.cli.scan_gate2_candidates import _best_ask_price_and_size

    yes_ask, yes_size = _best_ask_price_and_size(yes_asks)
    no_ask, no_size = _best_ask_price_and_size(no_asks)

    if yes_ask is None or no_ask is None or yes_size is None or no_size is None:
        return WatchSnapshot(
            slug=slug,
            yes_ask=yes_ask,
            no_ask=no_ask,
            yes_ask_size=yes_size,
            no_ask_size=no_size,
            sum_ask=None,
            near_edge=False,
            depth_ok=False,
            trigger=False,
        )

    sum_ask = yes_ask + no_ask
    near_edge = sum_ask < near_edge_threshold
    depth_ok = yes_size >= min_depth and no_size >= min_depth

    return WatchSnapshot(
        slug=slug,
        yes_ask=yes_ask,
        no_ask=no_ask,
        yes_ask_size=yes_size,
        no_ask_size=no_size,
        sum_ask=sum_ask,
        near_edge=near_edge,
        depth_ok=depth_ok,
        trigger=near_edge and depth_ok,
    )


# ---------------------------------------------------------------------------
# Production fetch helper (injectable for testing)
# ---------------------------------------------------------------------------


def _fetch_books(resolved: ResolvedWatch) -> tuple[list, list]:
    """Fetch current YES and NO ask levels for a resolved market.

    Returns:
        (yes_asks, no_asks) — lists of ask levels (dicts with price/size).
        Returns ([], []) on any network error.
    """
    from packages.polymarket.clob import ClobClient

    clob = ClobClient()
    try:
        yes_book = clob.fetch_book(resolved.yes_token_id)
        no_book = clob.fetch_book(resolved.no_token_id)
        yes_asks = (yes_book.get("asks") or []) if isinstance(yes_book, dict) else []
        no_asks = (no_book.get("asks") or []) if isinstance(no_book, dict) else []
        return yes_asks, no_asks
    except Exception as exc:
        logger.debug("fetch_books failed for %r: %s", resolved.slug, exc)
        return [], []


def _resolve_market(slug: str) -> ResolvedWatch:
    """Resolve a market slug to YES/NO token IDs.

    Raises:
        Exception: If the slug cannot be resolved (MarketPickerError or network).
    """
    from packages.polymarket.clob import ClobClient
    from packages.polymarket.gamma import GammaClient
    from packages.polymarket.simtrader.market_picker import MarketPicker

    picker = MarketPicker(GammaClient(), ClobClient())
    resolved = picker.resolve_slug(slug)
    return ResolvedWatch(
        slug=slug,
        yes_token_id=resolved.yes_token_id,
        no_token_id=resolved.no_token_id,
    )


def _record_tape_for_market(
    resolved: ResolvedWatch,
    tape_dir: Path,
    *,
    duration_seconds: float,
    ws_url: str,
    near_edge_threshold: float = _DEFAULT_NEAR_EDGE,
    threshold_source: str = "cli-default",
    regime: Optional[str] = None,
) -> None:
    """Record a tape for the given resolved market.

    Writes ``watch_meta.json`` with market slug, token IDs, and capture
    threshold provenance, then runs TapeRecorder for the requested duration.
    """
    from packages.polymarket.simtrader.tape.recorder import TapeRecorder

    tape_dir.mkdir(parents=True, exist_ok=True)
    effective_regime = regime if regime is not None else resolved.regime
    watch_meta: dict[str, Any] = {
        "market_slug": resolved.slug,
        "yes_asset_id": resolved.yes_token_id,
        "no_asset_id": resolved.no_token_id,
        "triggered_by": "watch-arb-candidates",
        "near_edge_threshold_used": near_edge_threshold,
        "threshold_source": threshold_source,
    }
    if effective_regime and effective_regime != "unknown":
        watch_meta["regime"] = effective_regime
    if resolved.market_snapshot is not None:
        watch_meta["market_snapshot"] = resolved.market_snapshot
    (tape_dir / "watch_meta.json").write_text(
        json.dumps(watch_meta, indent=2), encoding="utf-8"
    )
    recorder = TapeRecorder(
        tape_dir=tape_dir,
        asset_ids=[resolved.yes_token_id, resolved.no_token_id],
    )
    recorder.record(duration_seconds=duration_seconds, ws_url=ws_url)


# ---------------------------------------------------------------------------
# Main watcher class
# ---------------------------------------------------------------------------


class ArbWatcher:
    """Polls a watchlist of markets and auto-starts recording on near-edge trigger.

    Threading model
    ---------------
    The poll loop runs on the calling thread.  Each triggered recording starts
    in a daemon background thread so polling continues uninterrupted for the
    remaining markets.  ``max_concurrent`` limits the number of simultaneous
    recording threads to avoid resource exhaustion.
    """

    def __init__(
        self,
        resolved_markets: list[ResolvedWatch],
        *,
        near_edge_threshold: float,
        threshold_source: str = "cli-default",
        regime: Optional[str] = None,
        min_depth: float,
        poll_interval: float,
        duration_seconds: float,
        tapes_base_dir: Path,
        ws_url: str,
        max_concurrent: int,
        dry_run: bool = False,
        # Injectable for testing
        _fetch_fn: Optional[Callable] = None,
        _record_fn: Optional[Callable] = None,
        _monotonic_fn: Optional[Callable] = None,
        _sleep_fn: Optional[Callable] = None,
    ) -> None:
        self.resolved_markets = resolved_markets
        self.near_edge_threshold = near_edge_threshold
        self.threshold_source = threshold_source
        self.regime = regime
        self.min_depth = min_depth
        self.poll_interval = poll_interval
        self.duration_seconds = duration_seconds
        self.tapes_base_dir = tapes_base_dir
        self.ws_url = ws_url
        self.max_concurrent = max_concurrent
        self.dry_run = dry_run

        self._fetch_fn = _fetch_fn or _fetch_books
        self._record_fn = _record_fn or _record_tape_for_market
        self._monotonic_fn = _monotonic_fn or time.monotonic
        self._sleep_fn = _sleep_fn or time.sleep

        # State tracking
        self._recording_slugs: set[str] = set()  # slugs currently being recorded
        self._lock = threading.Lock()
        self._stop = threading.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Run the watch loop until Ctrl+C."""
        strategy_threshold = 1.0 - 0.01  # 0.99 — the actual strategy entry threshold
        print(
            f"[watch-arb] Watching {len(self.resolved_markets)} market(s)  "
            f"near_edge_threshold={self.near_edge_threshold:.4f}  "
            f"min_depth={self.min_depth:.0f} shares  "
            f"poll_interval={self.poll_interval:.0f}s  "
            f"record_duration={self.duration_seconds:.0f}s"
        )
        print(
            f"[watch-arb] Strategy entry threshold: sum_ask < {strategy_threshold:.4f}  "
            f"(near-edge trigger is LOOSER — captures near-miss conditions)"
        )
        if self.dry_run:
            print("[watch-arb] DRY-RUN: trigger evaluations only, no recording.")
        print("[watch-arb] Press Ctrl+C to stop.")
        print()

        for r in self.resolved_markets:
            print(f"  {r.slug}")
            print(f"    YES: {r.yes_token_id[:20]}...")
            print(f"    NO:  {r.no_token_id[:20]}...")
        print()

        start_time = self._monotonic_fn()
        try:
            while not self._stop.is_set():
                elapsed = self._monotonic_fn() - start_time
                if elapsed >= self.duration_seconds:
                    print("[watch-arb] Duration elapsed; stopping.")
                    break
                self._poll_round()
                # Sleep in small increments so Ctrl+C is responsive and
                # duration exit is checked frequently.
                remaining = self.duration_seconds - (self._monotonic_fn() - start_time)
                sleep_budget = min(self.poll_interval, max(remaining, 0.0))
                slept = 0.0
                while slept < sleep_budget and not self._stop.is_set():
                    chunk = min(0.25, sleep_budget - slept)
                    if chunk <= 0:
                        break
                    self._sleep_fn(chunk)
                    slept += chunk
        except KeyboardInterrupt:
            print("\n[watch-arb] Stopped by operator.")

    def stop(self) -> None:
        """Signal the watch loop to exit after the current poll round."""
        self._stop.set()

    # ------------------------------------------------------------------
    # Internal poll round
    # ------------------------------------------------------------------

    def _poll_round(self) -> None:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%SZ")

        with self._lock:
            concurrent = len(self._recording_slugs)

        for resolved in self.resolved_markets:
            with self._lock:
                if resolved.slug in self._recording_slugs:
                    logger.debug("[watch-arb] %s: already recording — skip poll", resolved.slug)
                    continue

            yes_asks, no_asks = self._fetch_fn(resolved)
            snap = evaluate_trigger(
                yes_asks,
                no_asks,
                resolved.slug,
                near_edge_threshold=self.near_edge_threshold,
                min_depth=self.min_depth,
            )

            self._print_status(ts, snap)

            if snap.trigger:
                with self._lock:
                    concurrent = len(self._recording_slugs)

                if concurrent >= self.max_concurrent:
                    print(
                        f"[watch-arb] {ts}  TRIGGER {resolved.slug}: "
                        f"max_concurrent={self.max_concurrent} already recording — skipping."
                    )
                    continue

                self._start_recording(resolved)

    def _start_recording(self, resolved: ResolvedWatch) -> None:
        """Launch a background recording thread for the triggered market."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        tape_dir = self.tapes_base_dir / f"{ts}_watch_{resolved.slug[:20]}"

        print(
            f"[watch-arb] *** TRIGGER: {resolved.slug}  "
            f"-> recording {self.duration_seconds:.0f}s to {tape_dir}"
        )

        if self.dry_run:
            print(f"[watch-arb]   DRY-RUN: skipping actual recording.")
            return

        with self._lock:
            self._recording_slugs.add(resolved.slug)

        def _record_and_release():
            try:
                self._record_fn(
                    resolved,
                    tape_dir,
                    duration_seconds=self.duration_seconds,
                    ws_url=self.ws_url,
                    near_edge_threshold=self.near_edge_threshold,
                    threshold_source=self.threshold_source,
                    regime=self.regime,
                )
                print(f"[watch-arb] Recording complete: {resolved.slug}  tape={tape_dir}")
            except Exception as exc:
                logger.warning("Recording failed for %r: %s", resolved.slug, exc)
                print(f"[watch-arb] Recording FAILED for {resolved.slug}: {exc}")
            finally:
                with self._lock:
                    self._recording_slugs.discard(resolved.slug)

        t = threading.Thread(target=_record_and_release, daemon=True, name=f"record-{resolved.slug[:20]}")
        t.start()

    @staticmethod
    def _print_status(ts: str, snap: WatchSnapshot) -> None:
        """Print one-line status for a poll snapshot."""
        if snap.sum_ask is None:
            print(f"[watch-arb] {ts}  {snap.slug[:40]:<40}  no BBO")
            return

        trigger_marker = " *** TRIGGER" if snap.trigger else ""
        depth_note = (
            f"YES={snap.yes_ask_size:.0f} NO={snap.no_ask_size:.0f}"
            if snap.yes_ask_size is not None and snap.no_ask_size is not None
            else "depth=N/A"
        )
        print(
            f"[watch-arb] {ts}  {snap.slug[:40]:<40}  "
            f"sum={snap.sum_ask:.4f}  {depth_note}"
            f"  near_edge={'Y' if snap.near_edge else 'N'}  depth_ok={'Y' if snap.depth_ok else 'N'}"
            f"{trigger_marker}"
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="watch-arb-candidates",
        description=(
            "Dislocation watch + auto-record for binary_complement_arb candidates.\n\n"
            "Polls a watchlist of market slugs. When the near-edge trigger fires\n"
            "(sum_ask < near-edge threshold AND depth >= min-depth), tape recording\n"
            "starts automatically. This is diagnostic capture — it does NOT change\n"
            "strategy thresholds, preset sizing, or gate rules."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--markets",
        nargs="+",
        metavar="SLUG",
        help=(
            "One or more market slugs to watch. Can be space-separated "
            "(--markets slug1 slug2) or comma-separated (--markets slug1,slug2). "
            "Can be used alone or alongside --watchlist-file or --session-plan."
        ),
    )
    p.add_argument(
        "--watchlist-file",
        metavar="PATH",
        help=(
            "Path to report-to-watchlist JSON with a top-level 'watchlist' array. "
            "Each row requires market_slug; optional metadata is retained for logging only."
        ),
    )
    p.add_argument(
        "--session-plan",
        metavar="PATH",
        help=(
            "Path to a session pack JSON produced by make-session-pack. "
            "Loads watchlist and sets near_edge_threshold from watch_config unless "
            "--near-edge is also supplied (operator override wins)."
        ),
    )
    p.add_argument(
        "--near-edge",
        type=float,
        default=None,
        metavar="F",
        help=(
            "Trigger threshold: record when yes_ask + no_ask < this value. "
            "Overrides the session plan's watch_config.near_edge_threshold. "
            f"Default (when no session plan): {_DEFAULT_NEAR_EDGE} — looser than the "
            "strategy entry threshold (0.99) to capture near-miss conditions."
        ),
    )
    p.add_argument(
        "--min-depth",
        type=float,
        default=_DEFAULT_MIN_DEPTH,
        metavar="N",
        help=(
            "Required best-ask size per leg in shares. "
            "Should match the strategy max_size (default %(default)s)."
        ),
    )
    p.add_argument(
        "--poll-interval",
        type=float,
        default=_DEFAULT_POLL_INTERVAL,
        metavar="SECS",
        help="Seconds between CLOB book polls per market (default %(default)s).",
    )
    p.add_argument(
        "--duration",
        type=float,
        default=None,
        metavar="SECS",
        help=(
            "Tape recording duration per triggered market in seconds. "
            f"Default: session plan's watch_config.duration_seconds or {_DEFAULT_DURATION}."
        ),
    )
    p.add_argument(
        "--tapes-base-dir",
        default=str(_DEFAULT_TAPES_BASE),
        metavar="DIR",
        help="Base directory for recorded tapes (default %(default)s).",
    )
    p.add_argument(
        "--ws-url",
        default=_DEFAULT_WS_URL,
        metavar="URL",
        help="WebSocket URL for tape recording.",
    )
    p.add_argument(
        "--max-concurrent",
        type=int,
        default=_DEFAULT_MAX_CONCURRENT,
        metavar="N",
        help="Max markets recording simultaneously (default %(default)s).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Evaluate triggers and print status but do not start any recordings.",
    )
    p.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entrypoint: python -m polytool watch-arb-candidates [options]."""
    parser = build_parser()
    args = parser.parse_args(argv)

    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(level=log_level, format="%(levelname)s %(name)s: %(message)s")

    # --- Load session plan (if provided) ------------------------------------
    session_plan: Optional[dict] = None
    if args.session_plan:
        try:
            session_plan = _load_session_plan(args.session_plan)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    # --- Resolve near_edge_threshold with provenance ------------------------
    # Priority: explicit --near-edge (operator override) > session plan > global default
    regime: Optional[str] = None
    if args.near_edge is not None:
        near_edge_threshold = args.near_edge
        threshold_source = "operator-override"
    elif session_plan is not None:
        watch_cfg = session_plan.get("watch_config", {})
        near_edge_threshold = float(watch_cfg.get("near_edge_threshold", _DEFAULT_NEAR_EDGE))
        threshold_source = str(watch_cfg.get("threshold_source", _SOURCE_SESSION_PLAN))
        regime = session_plan.get("session", {}).get("regime")
    else:
        near_edge_threshold = _DEFAULT_NEAR_EDGE
        threshold_source = "cli-default"

    # --- Duration: session plan > CLI default --------------------------------
    duration_seconds: float
    if args.duration is not None:
        duration_seconds = args.duration
    elif session_plan is not None:
        watch_cfg = session_plan.get("watch_config", {})
        duration_seconds = float(watch_cfg.get("duration_seconds", _DEFAULT_DURATION))
    else:
        duration_seconds = _DEFAULT_DURATION

    # --- Validate args -------------------------------------------------------
    if not (0.0 < near_edge_threshold <= 2.0):
        print("Error: near_edge_threshold must be between 0 and 2.", file=sys.stderr)
        return 1
    if args.min_depth <= 0:
        print("Error: --min-depth must be positive.", file=sys.stderr)
        return 1
    if args.poll_interval <= 0:
        print("Error: --poll-interval must be positive.", file=sys.stderr)
        return 1
    if duration_seconds <= 0:
        print("Error: --duration must be positive.", file=sys.stderr)
        return 1
    if args.max_concurrent < 1:
        print("Error: --max-concurrent must be >= 1.", file=sys.stderr)
        return 1

    # --- Collect watch targets -----------------------------------------------
    try:
        watch_targets = _collect_watch_targets(
            markets=args.markets,
            watchlist_file=args.watchlist_file,
            session_plan=session_plan,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    # Resolve all markets upfront before entering the watch loop
    print(f"[watch-arb] Resolving {len(watch_targets)} market(s)...", file=sys.stderr)
    resolved_markets: list[ResolvedWatch] = []
    for target in watch_targets:
        if target.metadata:
            logger.debug("Watch metadata for slug=%s: %s", target.slug, target.metadata)
        try:
            resolved = _resolve_market(target.slug)
            resolved_markets.append(resolved)
            print(f"[watch-arb]   OK  {target.slug}", file=sys.stderr)
        except Exception as exc:
            print(
                f"[watch-arb]   FAIL  {target.slug}: {exc}  (skipping)",
                file=sys.stderr,
            )

    if not resolved_markets:
        print("Error: no markets could be resolved.", file=sys.stderr)
        return 1

    watcher = ArbWatcher(
        resolved_markets=resolved_markets,
        near_edge_threshold=near_edge_threshold,
        threshold_source=threshold_source,
        regime=regime,
        min_depth=args.min_depth,
        poll_interval=args.poll_interval,
        duration_seconds=duration_seconds,
        tapes_base_dir=Path(args.tapes_base_dir),
        ws_url=args.ws_url,
        max_concurrent=args.max_concurrent,
        dry_run=args.dry_run,
    )
    watcher.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
