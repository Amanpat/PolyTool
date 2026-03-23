"""CLI: dry-run crypto pair opportunity scanner — Track 2 / Phase 1A.

Discovers active BTC/ETH/SOL 5m/15m binary markets, fetches live order-book
best-ask prices for both YES and NO legs, computes the paired cost and gross
edge, then writes a deterministic artifact bundle.

DRY-RUN ONLY — no orders are submitted and no wallet credentials are needed.

Usage:
    python -m polytool crypto-pair-scan [--top N] [--symbol BTC|ETH|SOL] [--duration 5|15]

Output bundle:
    artifacts/crypto_pairs/scan/<YYYY-MM-DD>/<run_id>/
        scan_manifest.json
        opportunities.json
        opportunities.md
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from packages.polymarket.crypto_pairs.market_discovery import discover_crypto_pair_markets
from packages.polymarket.crypto_pairs.opportunity_scan import (
    PairOpportunity,
    rank_opportunities,
    scan_opportunities,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _run_dir(base: Path, date_str: str, run_id: str) -> Path:
    return base / date_str / run_id


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )


def _opp_to_dict(opp: PairOpportunity) -> dict:
    return {
        "slug": opp.slug,
        "symbol": opp.symbol,
        "duration_min": opp.duration_min,
        "question": opp.question,
        "condition_id": opp.condition_id,
        "yes_token_id": opp.yes_token_id,
        "no_token_id": opp.no_token_id,
        "yes_ask": opp.yes_ask,
        "no_ask": opp.no_ask,
        "paired_cost": opp.paired_cost,
        "gross_edge": opp.gross_edge,
        "has_opportunity": opp.has_opportunity,
        "book_status": opp.book_status,
        "assumptions": opp.assumptions,
    }


def _format_edge(gross_edge: Optional[float]) -> str:
    if gross_edge is None:
        return "     n/a"
    return f"{gross_edge:+.4f}"


def _print_table(ranked: list[PairOpportunity], top: int) -> None:
    header = (
        f"{'#':>3} {'sym':>3} {'dur':>4} {'yes_ask':>7} {'no_ask':>7} "
        f"{'cost':>6} {'edge':>8}  slug"
    )
    print(header)
    print("-" * (len(header) + 10))
    for i, opp in enumerate(ranked[:top], start=1):
        yes_str = f"{opp.yes_ask:.4f}" if opp.yes_ask is not None else "   n/a"
        no_str = f"{opp.no_ask:.4f}" if opp.no_ask is not None else "   n/a"
        cost_str = f"{opp.paired_cost:.4f}" if opp.paired_cost is not None else "   n/a"
        edge_str = _format_edge(opp.gross_edge)
        flag = " *" if opp.has_opportunity else "  "
        print(
            f"{i:>3} {opp.symbol:>3} {opp.duration_min:>3}m "
            f"{yes_str:>7} {no_str:>7} {cost_str:>6} {edge_str:>8}"
            f"{flag}  {opp.slug[:50]}"
        )


def _write_markdown(
    path: Path,
    ranked: list[PairOpportunity],
    run_id: str,
    generated_at: str,
) -> None:
    lines = [
        "# Crypto Pair Scan",
        "",
        f"**Run ID**: `{run_id}`  ",
        f"**Generated at**: {generated_at}  ",
        "**Mode**: dry-run (no orders submitted)  ",
        "",
        "## Assumptions",
        "",
        "- Maker orders earn 20 bps rebate on crypto markets (ASSUMPTION — not verified per-market)",
        "- Fills assumed at best ask with no slippage (ASSUMPTION — real maker fills may be worse)",
        "- Maker orders may not fill before market resolves (fills not guaranteed)",
        "- 5m/15m markets resolve quickly; edge window is narrow",
        "- Gross edge = 1.00 - (YES ask + NO ask); does NOT include rebate",
        "",
        "## Results",
        "",
        "Legend: `*` = has_opportunity (gross_edge > 0)",
        "",
        "| # | sym | dur | yes_ask | no_ask | cost | edge | status | slug |",
        "|---|-----|-----|---------|--------|------|------|--------|------|",
    ]

    for i, opp in enumerate(ranked, start=1):
        yes_str = f"{opp.yes_ask:.4f}" if opp.yes_ask is not None else "n/a"
        no_str = f"{opp.no_ask:.4f}" if opp.no_ask is not None else "n/a"
        cost_str = f"{opp.paired_cost:.4f}" if opp.paired_cost is not None else "n/a"
        edge_str = _format_edge(opp.gross_edge).strip() if opp.gross_edge is not None else "n/a"
        flag = "* OPP" if opp.has_opportunity else opp.book_status
        lines.append(
            f"| {i} | {opp.symbol} | {opp.duration_min}m | {yes_str} | "
            f"{no_str} | {cost_str} | {edge_str} | {flag} | {opp.slug} |"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Core scan function (injectable for tests)
# ---------------------------------------------------------------------------

def run_crypto_pair_scan(
    *,
    top: int = 20,
    symbol_filter: Optional[str] = None,
    duration_filter: Optional[int] = None,
    output_base: Optional[Path] = None,
    gamma_client=None,
    clob_client=None,
) -> dict[str, Any]:
    """Run the crypto pair opportunity scan and write artifact bundle.

    DRY-RUN ONLY — no orders are submitted.

    Args:
        top: Number of rows to print in the summary table.
        symbol_filter: Restrict to one symbol: "BTC", "ETH", or "SOL".
        duration_filter: Restrict to one duration: 5 or 15 (minutes).
        output_base: Root artifact directory; defaults to
            ``artifacts/crypto_pairs/scan``.
        gamma_client: Injected GammaClient for testing (default: live).
        clob_client: Injected ClobClient for testing (default: live).

    Returns:
        ``scan_manifest.json`` payload as a dict.
    """
    now = _utcnow()
    date_str = now.date().isoformat()
    run_id = uuid.uuid4().hex[:12]
    base_dir = output_base or Path("artifacts/crypto_pairs/scan")
    run_dir = _run_dir(base_dir, date_str, run_id)
    generated_at = _iso_utc(now)

    print(f"[crypto-pair-scan] Discovering crypto pair markets...")
    pair_markets = discover_crypto_pair_markets(gamma_client=gamma_client)

    # Apply CLI filters
    if symbol_filter:
        pair_markets = [m for m in pair_markets if m.symbol == symbol_filter.upper()]
    if duration_filter:
        pair_markets = [m for m in pair_markets if m.duration_min == duration_filter]

    print(
        f"[crypto-pair-scan] Found {len(pair_markets)} eligible markets. "
        "Fetching order books..."
    )

    opportunities = scan_opportunities(pair_markets, clob_client=clob_client)
    ranked = rank_opportunities(opportunities)

    opp_count = sum(1 for o in ranked if o.has_opportunity)

    manifest: dict[str, Any] = {
        "run_id": run_id,
        "generated_at": generated_at,
        "mode": "dry_run",
        "filters": {
            "symbol": symbol_filter,
            "duration_min": duration_filter,
        },
        "summary": {
            "markets_discovered": len(pair_markets),
            "markets_scanned": len(opportunities),
            "opportunities_found": opp_count,
            "top_requested": top,
        },
        "artifact_dir": str(run_dir),
    }

    _write_json(run_dir / "scan_manifest.json", manifest)
    _write_json(run_dir / "opportunities.json", [_opp_to_dict(o) for o in ranked])
    _write_markdown(run_dir / "opportunities.md", ranked, run_id, generated_at)

    print(f"\n--- Top {top} Crypto Pair Opportunities (dry-run) ---")
    if ranked:
        _print_table(ranked, top=top)
        print(f"\n  * = positive gross edge (has_opportunity=True)")
    else:
        print("  No eligible markets found.")

    print(f"\nOpportunities found: {opp_count}/{len(opportunities)}")
    print(f"Bundle written: {run_dir}")

    return manifest


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Dry-run crypto pair opportunity scanner — Track 2 / Phase 1A. "
            "No orders are submitted. No wallet credentials required."
        )
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Number of rows to print in the summary table (default: 20).",
    )
    parser.add_argument(
        "--symbol",
        choices=["BTC", "ETH", "SOL"],
        default=None,
        help="Restrict scan to one symbol (default: all).",
    )
    parser.add_argument(
        "--duration",
        type=int,
        choices=[5, 15],
        default=None,
        help="Restrict scan to one duration in minutes: 5 or 15 (default: all).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Base artifact directory "
            "(default: artifacts/crypto_pairs/scan)."
        ),
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.top <= 0:
        print("Error: --top must be positive.", file=sys.stderr)
        return 1

    output_base = Path(args.output) if args.output else None
    try:
        run_crypto_pair_scan(
            top=args.top,
            symbol_filter=args.symbol,
            duration_filter=args.duration,
            output_base=output_base,
        )
    except Exception as exc:
        print(
            f"crypto-pair-scan failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
