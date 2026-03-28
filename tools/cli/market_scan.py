"""CLI for scanning and ranking Polymarket markets using the seven-factor engine."""

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
from packages.polymarket.market_selection.scorer import MarketScorer, SevenFactorScore


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


def _print_top_table(scores: list[SevenFactorScore], top: int) -> None:
    header = (
        f"{'rank':>4} "
        f"{'slug':<30} "
        f"{'composite':>9} "
        f"{'cat_edge':>8} "
        f"{'spread':>6} "
        f"{'vol':>5} "
        f"{'comp':>5} "
        f"{'time':>5}"
    )
    print(header)
    for rank, score in enumerate(scores[:top], start=1):
        print(
            f"{rank:>4} "
            f"{score.market_slug[:30]:<30} "
            f"{score.composite:>9.3f} "
            f"{score.category_edge_score:>8.3f} "
            f"{score.spread_score:>6.3f} "
            f"{score.volume_score:>5.3f} "
            f"{score.competition_score:>5.3f} "
            f"{score.time_score:>5.3f}"
        )


def run_market_scan(
    *,
    min_volume: float = 5000,
    top: int = 20,
    all_markets: bool = False,
    include_failing: bool = False,
    skip_events: bool = False,
    max_fetch: Optional[int] = None,
    output_path: Optional[Path] = None,
    print_json: bool = False,
) -> dict[str, Any]:
    now = _utcnow()
    output_file = output_path or _default_output_path(now)

    # Compute fetch limit: use explicit max_fetch when provided, else legacy max(top, 50)
    fetch_limit: int = int(max_fetch) if max_fetch is not None else max(int(top), 50)
    raw_markets = fetch_active_markets(min_volume=min_volume, limit=fetch_limit)

    # Pre-filter with passes_filters (for backward compat) and enrich survivors
    markets: list[dict] = []
    filtered_out: list[dict[str, str]] = []

    for market in raw_markets:
        market_slug = str(market.get("slug") or "").strip()

        # Backward-compat pre-filter: reject markets that fail the five-factor filters
        reward_cfg: dict | None = None
        if not skip_events:
            try:
                reward_cfg = fetch_reward_config(market_slug)
            except Exception:
                pass

        passed, reason = passes_filters(market, reward_cfg or {})
        if not passed:
            filtered_out.append({"market_slug": market_slug, "reason": reason})
            continue

        enriched = dict(market)

        if not skip_events:
            if reward_cfg and isinstance(reward_cfg, dict):
                enriched["reward_rate"] = reward_cfg.get("reward_rate") or 0.0

            token_id = str(market.get("token_id") or "").strip()
            if token_id:
                try:
                    ob = fetch_orderbook(token_id)
                    enriched["bids"] = ob.get("bids") or []
                except Exception:
                    pass

        markets.append(enriched)

    # Score with seven-factor engine
    scorer = MarketScorer(now=now)
    results = scorer.score_universe(markets, include_failing=include_failing)

    passing = [r for r in results if r.gate_passed]
    failing = [r for r in results if not r.gate_passed]

    # Build JSON artifact
    payload: dict[str, Any] = {
        "generated_at": _iso_utc(now),
        "max_fetch": fetch_limit,
        "include_failing": include_failing,
        "results": [asdict(score) for score in passing],
        "filtered_out": filtered_out,
        "gate_failed": (
            [{"market_slug": r.market_slug, "gate_reason": r.gate_reason} for r in failing]
            if include_failing
            else []
        ),
    }

    _write_json(output_file, payload)

    display_scores = passing
    display_top = len(display_scores) if all_markets else top

    if print_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        if display_scores:
            _print_top_table(display_scores, display_top)
        else:
            print("No markets passed gates.")
        print(f"Wrote market scan: {output_file.as_posix()}")

    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="market-scan",
        description="Scan and rank active Polymarket markets using the seven-factor engine.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Number of ranked rows to print (default: 20). Ignored if --all is set.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Print all passing markets (ignores --top).",
    )
    parser.add_argument(
        "--include-failing",
        action="store_true",
        help="Include gate-failed markets in JSON output (not shown in table).",
    )
    parser.add_argument(
        "--skip-events",
        action="store_true",
        help="Skip live reward/orderbook fetches (faster dry run; no reward_rate or orderbook data).",
    )
    parser.add_argument(
        "--max-fetch",
        type=int,
        default=None,
        help="Maximum markets to fetch from Gamma API (default: max(--top, 50)).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Override default JSON output path (default: artifacts/market_selection/YYYY-MM-DD.json).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_out",
        help="Print JSON to stdout instead of table.",
    )
    # Backward-compat alias: min_volume was used in old CLI and existing tests
    parser.add_argument(
        "--min-volume",
        type=float,
        default=5000.0,
        help="Minimum 24h volume for fetched markets (default: 5000). Backward-compat alias.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.top <= 0:
        print("Error: --top must be positive.", file=sys.stderr)
        return 1
    if args.max_fetch is not None and args.max_fetch <= 0:
        print("Error: --max-fetch must be positive.", file=sys.stderr)
        return 1

    output_path = Path(args.output) if args.output else _default_output_path()

    try:
        run_market_scan(
            min_volume=float(args.min_volume),
            top=int(args.top),
            all_markets=args.all,
            include_failing=args.include_failing,
            skip_events=args.skip_events,
            max_fetch=int(args.max_fetch) if args.max_fetch is not None else None,
            output_path=output_path,
            print_json=args.json_out,
        )
    except Exception as exc:
        print(f"market-scan failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
