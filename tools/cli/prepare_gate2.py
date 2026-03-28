"""Gate 2 preparation orchestrator.

Thin workflow glue: scan candidates -> record tapes -> check eligibility -> print verdict.

Reuses (does NOT reimplement):
  - tools.cli.scan_gate2_candidates : candidate scanning and ranking
  - packages.polymarket.simtrader.tape.recorder.TapeRecorder : tape recording
  - packages.polymarket.simtrader.sweeps.eligibility : tape eligibility checking

Does NOT change:
  - Strategy logic or preset sizing
  - Gate thresholds (max_size, buffer, profitability)
  - Fill, fee, or risk models

Usage
-----
  # Full workflow: scan -> record -> check eligibility:
  python -m polytool prepare-gate2

  # Select top 3 candidates, 5-minute tapes:
  python -m polytool prepare-gate2 --top 3 --duration 300

  # Dry-run: show candidates but skip recording and eligibility:
  python -m polytool prepare-gate2 --dry-run

  # Score pre-recorded tapes (skip scan and record):
  python -m polytool prepare-gate2 --tapes-dir artifacts/tapes/gold
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, List, Mapping, Optional

logger = logging.getLogger(__name__)

_DEFAULT_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
_DEFAULT_TOP = 3
_DEFAULT_DURATION = 300.0
_DEFAULT_MAX_SIZE = 50.0
_DEFAULT_BUFFER = 0.01
_DEFAULT_TAPES_BASE = Path("artifacts/tapes/gold")
_DEFAULT_CANDIDATES = 50

_COL_SLUG = 44
_COL_STATUS = 11
_COL_REASON = 52


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class PrepResult:
    """Outcome of one market preparation attempt."""

    slug: str
    tape_dir: Optional[Path] = None
    eligible: Optional[bool] = None  # None = not evaluated (dry-run or resolve failed)
    reject_reason: str = ""
    stats: dict[str, Any] = field(default_factory=dict)


_SNAPSHOT_FIELD_MAP = (
    ("market_slug", "market_slug"),
    ("slug", "market_slug"),
    ("question", "question"),
    ("title", "title"),
    ("category", "category"),
    ("subcategory", "subcategory"),
    ("category_source", "category_source"),
    ("subcategory_source", "subcategory_source"),
    ("tags", "tags"),
    ("tag_names", "tag_names"),
    ("tagNames", "tagNames"),
    ("event_slug", "event_slug"),
    ("event_title", "event_title"),
    ("created_at", "created_at"),
    ("createdAt", "created_at"),
    ("age_hours", "age_hours"),
    ("ageHours", "age_hours"),
    ("captured_at", "captured_at"),
)
_SNAPSHOT_CREATED_AT_KEYS = (
    "created_at",
    "createdAt",
    "created_time",
    "createdTime",
    "published_at",
    "publishedAt",
    "listed_at",
    "listedAt",
)
_SNAPSHOT_AGE_KEYS = ("age_hours", "ageHours")


def _snapshot_value_present(value: Any) -> bool:
    return value not in (None, "", [], {})


def _snapshot_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _snapshot_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _snapshot_datetime(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _merge_market_snapshot(dst: dict[str, Any], src: Mapping[str, Any]) -> dict[str, Any]:
    for src_key, dst_key in _SNAPSHOT_FIELD_MAP:
        value = src.get(src_key)
        if _snapshot_value_present(value) and dst_key not in dst:
            dst[dst_key] = value
    return dst


def _finalize_market_snapshot(
    snapshot: dict[str, Any],
    *,
    captured_at: datetime,
) -> dict[str, Any]:
    snapshot.setdefault("captured_at", _snapshot_iso(captured_at))
    age_hours = None
    for key in _SNAPSHOT_AGE_KEYS:
        age_hours = _snapshot_float(snapshot.get(key))
        if age_hours is not None and age_hours >= 0.0:
            snapshot["age_hours"] = age_hours
            break
    if age_hours is None:
        for key in _SNAPSHOT_CREATED_AT_KEYS:
            created_at = _snapshot_datetime(snapshot.get(key))
            if created_at is None:
                continue
            age_hours = (captured_at - created_at).total_seconds() / 3600.0
            if age_hours >= 0.0:
                snapshot["age_hours"] = age_hours
            break
    return snapshot


def _build_market_snapshot(
    market: Any,
    *,
    captured_at: Optional[datetime] = None,
) -> dict[str, Any]:
    captured_dt = captured_at or datetime.now(timezone.utc)
    snapshot: dict[str, Any] = {}

    for attr in (
        "market_slug",
        "question",
        "category",
        "subcategory",
        "category_source",
        "subcategory_source",
        "tags",
        "event_slug",
        "event_title",
    ):
        value = getattr(market, attr, None)
        if _snapshot_value_present(value):
            snapshot[attr] = value

    raw_json = getattr(market, "raw_json", None)
    if isinstance(raw_json, Mapping):
        _merge_market_snapshot(snapshot, raw_json)

    return _finalize_market_snapshot(snapshot, captured_at=captured_dt)


def _candidate_market_snapshot(candidate: Any) -> dict[str, Any]:
    captured_at = datetime.now(timezone.utc)
    snapshot: dict[str, Any] = {}
    market_meta = getattr(candidate, "market_meta", None)
    if isinstance(market_meta, Mapping):
        _merge_market_snapshot(snapshot, market_meta)
    if getattr(candidate, "slug", None):
        snapshot.setdefault("market_slug", getattr(candidate, "slug"))
    return _finalize_market_snapshot(snapshot, captured_at=captured_at)


def _normalize_resolve_result(result: Any) -> tuple[str, str, dict[str, Any]]:
    if isinstance(result, tuple):
        if len(result) == 3:
            yes_id, no_id, snapshot = result
            snapshot_dict = dict(snapshot) if isinstance(snapshot, Mapping) else {}
            return str(yes_id), str(no_id), snapshot_dict
        if len(result) == 2:
            yes_id, no_id = result
            return str(yes_id), str(no_id), {}
    raise ValueError("resolve function must return (yes_id, no_id) or (yes_id, no_id, snapshot)")


# ---------------------------------------------------------------------------
# Internal helpers (each is independently injectable for testing)
# ---------------------------------------------------------------------------


def _resolve_asset_ids(slug: str) -> tuple[str, str, dict[str, Any]]:
    """Return (yes_token_id, no_token_id, market_snapshot) for a market slug.

    Raises MarketPickerError when the slug cannot be resolved.
    """
    from packages.polymarket.clob import ClobClient
    from packages.polymarket.gamma import GammaClient
    from packages.polymarket.simtrader.market_picker import MarketPicker

    gamma = GammaClient()
    picker = MarketPicker(gamma, ClobClient())
    captured_at = datetime.now(timezone.utc)
    resolved = picker.resolve_slug(slug)
    snapshot = _finalize_market_snapshot(
        {
            "market_slug": resolved.slug,
            "question": resolved.question,
        },
        captured_at=captured_at,
    )
    try:
        markets = gamma.fetch_markets_filtered(slugs=[slug])
    except Exception:
        markets = []
    if markets:
        snapshot = _build_market_snapshot(markets[0], captured_at=captured_at)
        snapshot.setdefault("market_slug", resolved.slug)
        if resolved.question:
            snapshot.setdefault("question", resolved.question)
    return resolved.yes_token_id, resolved.no_token_id, snapshot


def _record_tape(
    slug: str,
    yes_id: str,
    no_id: str,
    tape_dir: Path,
    *,
    duration_seconds: float,
    ws_url: str,
) -> None:
    """Record a tape for the given market.

    Writes ``prep_meta.json`` with YES/NO IDs so the eligibility check can
    find them later without requiring the caller to pass them again.
    """
    from packages.polymarket.simtrader.tape.recorder import TapeRecorder

    tape_dir.mkdir(parents=True, exist_ok=True)
    prep_meta = {
        "market_slug": slug,
        "yes_asset_id": yes_id,
        "no_asset_id": no_id,
    }
    (tape_dir / "prep_meta.json").write_text(
        json.dumps(prep_meta, indent=2), encoding="utf-8"
    )
    recorder = TapeRecorder(tape_dir=tape_dir, asset_ids=[yes_id, no_id])
    recorder.record(duration_seconds=duration_seconds, ws_url=ws_url)


def _read_asset_ids_from_tape(tape_dir: Path) -> tuple[str, str]:
    """Extract (yes_id, no_id) from metadata files in *tape_dir*.

    Search order:
      1. ``prep_meta.json`` — written by this orchestrator.
      2. ``meta.json`` shadow_context / quickrun_context — written by shadow runner.
      3. Fallback: discover first two asset IDs from events.jsonl event stream.

    Returns ("", "") if asset IDs cannot be determined.
    """
    # 1. Orchestrator's own metadata.
    prep_meta_path = tape_dir / "prep_meta.json"
    if prep_meta_path.exists():
        try:
            data = json.loads(prep_meta_path.read_text(encoding="utf-8"))
            yes_id = str(data.get("yes_asset_id", ""))
            no_id = str(data.get("no_asset_id", ""))
            if yes_id and no_id:
                return yes_id, no_id
        except Exception:
            pass

    # 2. Shadow / quickrun meta.json context block.
    meta_path = tape_dir / "meta.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            for ctx_key in ("shadow_context", "quickrun_context"):
                ctx = meta.get(ctx_key)
                if isinstance(ctx, dict):
                    yes_id = str(ctx.get("yes_asset_id", "") or "")
                    no_id = str(ctx.get("no_asset_id", "") or "")
                    if yes_id and no_id:
                        return yes_id, no_id
        except Exception:
            pass

    # 3. Discover from event stream (asset-order-agnostic; symmetric check).
    events_path = tape_dir / "events.jsonl"
    if events_path.exists():
        seen: list[str] = []
        try:
            with open(events_path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        evt = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(evt, dict):
                        continue
                    et = evt.get("event_type", "")
                    if et == "book":
                        aid = str(evt.get("asset_id") or "")
                        if aid and aid not in seen:
                            seen.append(aid)
                    elif et == "price_change" and "price_changes" in evt:
                        for entry in evt.get("price_changes", []):
                            if isinstance(entry, dict):
                                aid = str(entry.get("asset_id") or "")
                                if aid and aid not in seen:
                                    seen.append(aid)
                    if len(seen) >= 2:
                        break
        except OSError:
            pass
        if len(seen) >= 2:
            return seen[0], seen[1]

    return "", ""


def _check_eligibility(
    tape_dir: Path,
    yes_id: str,
    no_id: str,
    max_size: float,
    buffer: float,
) -> Any:
    """Run the pre-sweep eligibility check on an existing tape directory.

    Returns an ``EligibilityResult`` (eligible, reason, stats).
    """
    from packages.polymarket.simtrader.sweeps.eligibility import (
        check_binary_arb_tape_eligibility,
    )

    events_path = tape_dir / "events.jsonl"
    cfg = {
        "yes_asset_id": yes_id,
        "no_asset_id": no_id,
        "max_size": str(max_size),
        "buffer": str(buffer),
    }
    return check_binary_arb_tape_eligibility(events_path, cfg)


# ---------------------------------------------------------------------------
# Core orchestration
# ---------------------------------------------------------------------------


def prepare_candidates(
    candidates: list,
    *,
    top: int,
    tapes_base_dir: Path,
    duration_seconds: float,
    max_size: float,
    buffer: float,
    ws_url: str,
    dry_run: bool,
    regime: str = "unknown",
    # Injectable for testing — pass None to use production implementations.
    _resolve_fn: Optional[Callable] = None,
    _record_fn: Optional[Callable] = None,
    _check_fn: Optional[Callable] = None,
) -> list[PrepResult]:
    """Orchestrate recording and eligibility checking for the top N candidates.

    For each selected candidate:
      1. Resolve YES/NO token IDs via MarketPicker.
      2. Record a tape via TapeRecorder (unless dry-run).
      3. Check eligibility via sweeps.eligibility.

    Args:
        candidates:      Ranked list of CandidateResult from scan_gate2_candidates.
        top:             Number of candidates to process.
        tapes_base_dir:  Base directory for newly recorded tapes.
        duration_seconds: Recording duration per tape (seconds).
        max_size:        Strategy max_size for eligibility check.
        buffer:          Strategy buffer for eligibility check.
        ws_url:          WebSocket URL for recording.
        dry_run:         If True, skip recording and eligibility (show candidates only).
        _resolve_fn:     Injectable resolver: fn(slug) -> (yes_id, no_id)
                         or (yes_id, no_id, market_snapshot).
        _record_fn:      Injectable recorder: fn(slug, yes_id, no_id, tape_dir, *, ...).
        _check_fn:       Injectable check: fn(tape_dir, yes_id, no_id, max_size, buffer).

    Returns:
        List of PrepResult, one per selected candidate.
    """
    resolve_fn = _resolve_fn or _resolve_asset_ids
    record_fn = _record_fn or _record_tape
    check_fn = _check_fn or _check_eligibility

    results: list[PrepResult] = []
    selected = candidates[:top]

    for candidate in selected:
        slug = candidate.slug
        market_snapshot = _candidate_market_snapshot(candidate)
        print(f"\n[prepare-gate2] {slug}", file=sys.stderr)

        if dry_run:
            results.append(PrepResult(slug=slug))
            continue

        # -- Step 1: Resolve YES/NO token IDs. --------------------------------
        try:
            yes_id, no_id, resolved_snapshot = _normalize_resolve_result(resolve_fn(slug))
            if resolved_snapshot:
                merged_snapshot = dict(resolved_snapshot)
                _merge_market_snapshot(merged_snapshot, market_snapshot)
                market_snapshot = _finalize_market_snapshot(
                    merged_snapshot,
                    captured_at=datetime.now(timezone.utc),
                )
        except Exception as exc:
            logger.warning("Could not resolve asset IDs for %r: %s", slug, exc)
            results.append(
                PrepResult(
                    slug=slug,
                    eligible=False,
                    reject_reason=f"resolve failed: {exc}",
                )
            )
            continue

        # -- Step 2: Record tape. ---------------------------------------------
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        tape_dir = tapes_base_dir / f"{ts}_{slug[:20]}"
        print(
            f"[prepare-gate2]   recording {duration_seconds:.0f}s -> {tape_dir}",
            file=sys.stderr,
        )
        try:
            record_fn(
                slug,
                yes_id,
                no_id,
                tape_dir,
                duration_seconds=duration_seconds,
                ws_url=ws_url,
            )
        except Exception as exc:
            logger.warning("Recording failed for %r: %s", slug, exc)
            results.append(
                PrepResult(
                    slug=slug,
                    tape_dir=tape_dir,
                    eligible=False,
                    reject_reason=f"record failed: {exc}",
                )
            )
            continue

        # Write regime label into prep_meta.json (best-effort merge).
        prep_meta_path = tape_dir / "prep_meta.json"
        if prep_meta_path.exists():
            try:
                existing = json.loads(prep_meta_path.read_text(encoding="utf-8"))
                existing["regime"] = regime
                if market_snapshot:
                    existing_snapshot = existing.get("market_snapshot")
                    merged_snapshot = dict(existing_snapshot) if isinstance(existing_snapshot, Mapping) else {}
                    _merge_market_snapshot(merged_snapshot, market_snapshot)
                    existing["market_snapshot"] = _finalize_market_snapshot(
                        merged_snapshot,
                        captured_at=datetime.now(timezone.utc),
                    )
                prep_meta_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
            except Exception:
                pass

        # -- Step 3: Eligibility check. ----------------------------------------
        print("[prepare-gate2]   checking eligibility...", file=sys.stderr)
        try:
            elig = check_fn(tape_dir, yes_id, no_id, max_size, buffer)
            results.append(
                PrepResult(
                    slug=slug,
                    tape_dir=tape_dir,
                    eligible=elig.eligible,
                    reject_reason=elig.reason if not elig.eligible else "",
                    stats=elig.stats,
                )
            )
        except Exception as exc:
            logger.warning("Eligibility check failed for %r: %s", slug, exc)
            results.append(
                PrepResult(
                    slug=slug,
                    tape_dir=tape_dir,
                    eligible=False,
                    reject_reason=f"eligibility check error: {exc}",
                )
            )

    return results


# ---------------------------------------------------------------------------
# Tapes-only mode
# ---------------------------------------------------------------------------


def check_existing_tapes(
    tapes_dir: Path,
    *,
    max_size: float,
    buffer: float,
    _check_fn: Optional[Callable] = None,
) -> list[PrepResult]:
    """Run eligibility checks on all tapes already present in *tapes_dir*.

    Skips the scan and record steps entirely. Useful for evaluating previously
    recorded tapes without starting a new recording session.

    Args:
        tapes_dir:  Directory containing tape subdirectories (each with events.jsonl).
        max_size:   Strategy max_size for eligibility check.
        buffer:     Strategy buffer for eligibility check.
        _check_fn:  Injectable eligibility fn for testing.

    Returns:
        List of PrepResult, one per tape directory containing events.jsonl.
    """
    check_fn = _check_fn or _check_eligibility

    tape_dirs = sorted(
        p for p in tapes_dir.iterdir() if p.is_dir() and (p / "events.jsonl").exists()
    )

    from tools.cli.scan_gate2_candidates import _slug_from_tape_dir

    results: list[PrepResult] = []
    for td in tape_dirs:
        slug = _slug_from_tape_dir(td)
        # Prefer slug from prep_meta.json (written by this orchestrator) when
        # _slug_from_tape_dir falls back to the directory name.
        prep_meta_path = td / "prep_meta.json"
        if prep_meta_path.exists():
            try:
                data = json.loads(prep_meta_path.read_text(encoding="utf-8"))
                slug = str(data.get("market_slug", "") or slug)
            except Exception:
                pass
        yes_id, no_id = _read_asset_ids_from_tape(td)

        if not yes_id or not no_id:
            results.append(
                PrepResult(
                    slug=slug,
                    tape_dir=td,
                    eligible=False,
                    reject_reason="could not determine YES/NO asset IDs from tape metadata",
                )
            )
            continue

        try:
            elig = check_fn(td, yes_id, no_id, max_size, buffer)
            results.append(
                PrepResult(
                    slug=slug,
                    tape_dir=td,
                    eligible=elig.eligible,
                    reject_reason=elig.reason if not elig.eligible else "",
                    stats=elig.stats,
                )
            )
        except Exception as exc:
            results.append(
                PrepResult(
                    slug=slug,
                    tape_dir=td,
                    eligible=False,
                    reject_reason=f"eligibility check error: {exc}",
                )
            )

    return results


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def print_summary(results: list[PrepResult], *, dry_run: bool = False) -> None:
    """Print the compact operator verdict table to stdout."""
    if not results:
        print("No candidates processed.")
        return

    header = (
        f"{'Market':<{_COL_SLUG}} | "
        f"{'Status':<{_COL_STATUS}} | "
        f"Detail"
    )
    sep = "-" * (len(header) + _COL_REASON)
    print()
    print(header)
    print(sep)

    for r in results:
        if dry_run or r.eligible is None:
            status = "DRY-RUN"
            detail = "(skipped)"
        elif r.eligible:
            status = "ELIGIBLE"
            detail = str(r.tape_dir or "")
        else:
            status = "INELIGIBLE"
            detail = r.reject_reason

        slug_col = r.slug[:_COL_SLUG]
        print(
            f"{slug_col:<{_COL_SLUG}} | "
            f"{status:<{_COL_STATUS}} | "
            f"{detail}"
        )

    print(sep)
    eligible_count = sum(1 for r in results if r.eligible)
    print(f"Candidates: {len(results)}  |  Eligible: {eligible_count}")

    if not dry_run and eligible_count > 0:
        print("\nEligible tapes — proceed to Gate 2 sweep:")
        for r in results:
            if r.eligible and r.tape_dir:
                print(
                    f"  python -m polytool simtrader sweep "
                    f"--tape {r.tape_dir / 'events.jsonl'}"
                )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="prepare-gate2",
        description=(
            "Gate 2 preparation orchestrator.\n\n"
            "Scans live candidates, records tapes, checks eligibility, and prints\n"
            "a verdict summary. Reuses scan_gate2_candidates, TapeRecorder, and\n"
            "sweeps.eligibility without reimplementing any logic.\n\n"
            "Deferred: Opportunity Radar — start only after the first clean\n"
            "Gate 2 -> Gate 3 progression. See docs/ROADMAP.md backlog section."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--top",
        type=int,
        default=_DEFAULT_TOP,
        metavar="N",
        help="Number of candidates to process (default: %(default)s).",
    )
    p.add_argument(
        "--duration",
        type=float,
        default=_DEFAULT_DURATION,
        metavar="SECS",
        help="Tape recording duration per candidate in seconds (default: %(default)s).",
    )
    p.add_argument(
        "--tapes-dir",
        default=None,
        metavar="DIR",
        help=(
            "Score existing tapes instead of scanning and recording. "
            "Skips scan and record steps entirely."
        ),
    )
    p.add_argument(
        "--tapes-base-dir",
        default=str(_DEFAULT_TAPES_BASE),
        metavar="DIR",
        help="Base directory for newly recorded tapes (default: %(default)s).",
    )
    p.add_argument(
        "--max-size",
        type=float,
        default=_DEFAULT_MAX_SIZE,
        metavar="N",
        help="Strategy max_size for eligibility check (default: %(default)s).",
    )
    p.add_argument(
        "--buffer",
        type=float,
        default=_DEFAULT_BUFFER,
        metavar="F",
        help="Strategy buffer for eligibility check (default: %(default)s).",
    )
    p.add_argument(
        "--candidates",
        type=int,
        default=_DEFAULT_CANDIDATES,
        metavar="N",
        help="Max live markets to scan (default: %(default)s).",
    )
    p.add_argument(
        "--ws-url",
        default=_DEFAULT_WS_URL,
        metavar="URL",
        help="WebSocket URL for tape recording.",
    )
    p.add_argument(
        "--regime",
        choices=["politics", "sports", "new_market", "unknown"],
        default="unknown",
        metavar="REGIME",
        help=(
            "Market regime label written to tape metadata for corpus tracking. "
            "Used by 'tape-manifest' to verify mixed-regime coverage. "
            "Choices: politics, sports, new_market, unknown (default: unknown)."
        ),
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show candidates but skip recording and eligibility checks.",
    )
    p.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entrypoint: python -m polytool prepare-gate2 [options]."""
    parser = build_parser()
    args = parser.parse_args(argv)

    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(level=log_level, format="%(levelname)s %(name)s: %(message)s")

    from tools.cli.scan_gate2_candidates import rank_candidates, scan_live_markets, scan_tapes

    # -- Tapes-only mode -------------------------------------------------------
    if args.tapes_dir:
        tapes_dir = Path(args.tapes_dir)
        if not tapes_dir.is_dir():
            print(
                f"Error: --tapes-dir '{tapes_dir}' is not a directory.",
                file=sys.stderr,
            )
            return 1
        print(f"[prepare-gate2] tapes-only mode: {tapes_dir}", file=sys.stderr)
        results = check_existing_tapes(
            tapes_dir, max_size=args.max_size, buffer=args.buffer
        )
        print_summary(results)
        return 0

    # -- Live scan mode --------------------------------------------------------
    print(
        f"[prepare-gate2] scanning {args.candidates} live markets "
        f"(max_size={args.max_size}, buffer={args.buffer})...",
        file=sys.stderr,
    )
    raw = scan_live_markets(
        max_size=args.max_size,
        buffer=args.buffer,
        max_candidates=args.candidates,
    )
    ranked = rank_candidates(raw)

    # Prefer markets with some signal; fall back to top of raw ranking.
    signal = [r for r in ranked if r.depth_ok_ticks > 0 or r.edge_ok_ticks > 0]
    if not signal:
        print(
            "[prepare-gate2] no markets with depth or edge signal; "
            "showing top candidates anyway.",
            file=sys.stderr,
        )
        signal = ranked

    if not signal:
        print("[prepare-gate2] no candidates found.", file=sys.stderr)
        return 1

    print(
        f"[prepare-gate2] {len(signal)} candidate(s) with signal; "
        f"processing top {args.top}.",
        file=sys.stderr,
    )

    results = prepare_candidates(
        signal,
        top=args.top,
        tapes_base_dir=Path(args.tapes_base_dir),
        duration_seconds=args.duration,
        max_size=args.max_size,
        buffer=args.buffer,
        ws_url=args.ws_url,
        dry_run=args.dry_run,
        regime=args.regime,
    )

    print_summary(results, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
