"""CLI for scanning and ranking Polymarket markets."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Optional

from packages.polymarket.market_selection.api_client import (
    fetch_active_markets,
    fetch_orderbook,
    fetch_reward_config,
)
from packages.polymarket.market_selection.filters import passes_filters
from packages.polymarket.market_selection.scorer import MarketScore, score_market


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _default_output_path(now: Optional[datetime] = None) -> Path:
    stamp = (now or _utcnow()).date().isoformat()
    return Path("artifacts") / "market_selection" / f"{stamp}.json"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )


def _print_top_table(scores: list[MarketScore], top: int) -> None:
    print("rank slug                           composite reward_apr spread fill comp age_h")
    for rank, score in enumerate(scores[:top], start=1):
        print(
            f"{rank:>4} "
            f"{score.market_slug[:30]:30} "
            f"{score.composite:>9.3f} "
            f"{score.reward_apr_est:>10.3f} "
            f"{score.spread_score:>6.3f} "
            f"{score.fill_score:>4.3f} "
            f"{score.competition_score:>4.3f} "
            f"{score.age_hours:>5.1f}"
        )


def run_market_scan(
    *,
    min_volume: float = 5000,
    top: int = 20,
    output_path: Optional[Path] = None,
) -> dict[str, Any]:
    now = _utcnow()
    output_file = output_path or _default_output_path(now)

    candidates = fetch_active_markets(min_volume=min_volume, limit=max(int(top), 50))
    scored_markets: list[MarketScore] = []
    filtered_out: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []

    for market in candidates:
        market_slug = str(market.get("slug") or "").strip()
        reward_config = fetch_reward_config(market_slug)
        passed, reason = passes_filters(market, reward_config)
        if not passed:
            filtered_out.append({"market_slug": market_slug, "reason": reason})
            continue

        token_id = str(market.get("token_id") or "").strip()
        if not token_id:
            skipped.append({"market_slug": market_slug, "reason": "missing_token_id"})
            continue

        try:
            orderbook = fetch_orderbook(token_id)
            scored_markets.append(score_market(market, orderbook, reward_config or {}))
        except Exception as exc:
            skipped.append({"market_slug": market_slug, "reason": f"{type(exc).__name__}: {exc}"})

    scored_markets.sort(key=lambda item: item.composite, reverse=True)

    payload = {
        "generated_at": _iso_utc(now),
        "min_volume": float(min_volume),
        "top": int(top),
        "results": [asdict(score) for score in scored_markets],
        "filtered_out": filtered_out,
        "skipped": skipped,
    }
    _write_json(output_file, payload)

    if scored_markets:
        _print_top_table(scored_markets, top=int(top))
    else:
        print("No markets passed filters.")
    print(f"Wrote market scan: {output_file.as_posix()}")

    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan and rank active Polymarket markets.")
    parser.add_argument(
        "--min-volume",
        type=float,
        default=5000.0,
        help="Minimum 24h volume threshold for fetched markets (default: 5000).",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Number of ranked rows to print (default: 20).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON path (default: artifacts/market_selection/YYYY-MM-DD.json).",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.min_volume < 0:
        print("Error: --min-volume must be non-negative.", file=sys.stderr)
        return 1
    if args.top <= 0:
        print("Error: --top must be positive.", file=sys.stderr)
        return 1

    output_path = Path(args.output) if args.output else _default_output_path()
    try:
        run_market_scan(
            min_volume=float(args.min_volume),
            top=int(args.top),
            output_path=output_path,
        )
    except Exception as exc:
        print(f"market-scan failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
