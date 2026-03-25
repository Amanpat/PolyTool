"""CLI: market availability watcher for crypto pair bot — Track 2 / Phase 1A.

Checks whether eligible BTC/ETH/SOL 5m/15m binary markets exist on Polymarket.
In one-shot mode, prints availability counts and a next-action suggestion, then
exits 0. In watch mode, polls until markets appear (exit 0) or the timeout
expires (exit 1).

DRY-RUN ONLY — no orders are submitted. No wallet credentials required.

Usage:
    python -m polytool crypto-pair-watch [--watch] [--timeout SECONDS] [--poll-interval SECONDS]

Output bundle:
    artifacts/crypto_pairs/watch/<YYYY-MM-DD>/<run_id>/
        watch_manifest.json
        availability_summary.json
        availability_summary.md
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from packages.polymarket.crypto_pairs.market_watch import (
    AvailabilitySummary,
    run_availability_check,
    run_watch_loop,
)


# ---------------------------------------------------------------------------
# Helpers (mirror pattern from crypto_pair_scan.py)
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


def _next_action(summary: AvailabilitySummary) -> str:
    if summary.eligible_now:
        return "Run: python -m polytool crypto-pair-scan (then crypto-pair-run when ready)"
    return "Markets unavailable. Re-run later or use --watch --timeout 3600"


def _print_summary(summary: AvailabilitySummary) -> None:
    eligible_str = "yes" if summary.eligible_now else "no"
    by_sym = summary.by_symbol
    by_dur = summary.by_duration
    print(f"[crypto-pair-watch] eligible_now : {eligible_str}")
    print(f"[crypto-pair-watch] total_eligible: {summary.total_eligible}")
    print(
        f"[crypto-pair-watch] by_symbol     : "
        f"BTC={by_sym.get('BTC', 0)} "
        f"ETH={by_sym.get('ETH', 0)} "
        f"SOL={by_sym.get('SOL', 0)}"
    )
    print(
        f"[crypto-pair-watch] by_duration   : "
        f"5m={by_dur.get('5m', 0)} "
        f"15m={by_dur.get('15m', 0)}"
    )
    print(f"[crypto-pair-watch] checked_at    : {summary.checked_at}")
    print(f"[crypto-pair-watch] next_action   : {_next_action(summary)}")


def _write_markdown(
    path: Path,
    summary: AvailabilitySummary,
    run_id: str,
    mode: str,
    generated_at: str,
) -> None:
    eligible_str = "YES" if summary.eligible_now else "NO"
    by_sym = summary.by_symbol
    by_dur = summary.by_duration
    next_action = _next_action(summary)

    lines = [
        "# Crypto Pair Watch — Availability Report",
        "",
        f"**Run ID**: `{run_id}`  ",
        f"**Generated at**: {generated_at}  ",
        f"**Mode**: {mode}  ",
        "",
        "## Availability",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| eligible_now | {eligible_str} |",
        f"| total_eligible | {summary.total_eligible} |",
        f"| BTC markets | {by_sym.get('BTC', 0)} |",
        f"| ETH markets | {by_sym.get('ETH', 0)} |",
        f"| SOL markets | {by_sym.get('SOL', 0)} |",
        f"| 5m markets | {by_dur.get('5m', 0)} |",
        f"| 15m markets | {by_dur.get('15m', 0)} |",
        f"| checked_at | {summary.checked_at} |",
        "",
    ]

    if summary.first_eligible_slugs:
        lines += [
            "## First Eligible Slugs",
            "",
        ]
        for slug in summary.first_eligible_slugs:
            lines.append(f"- `{slug}`")
        lines.append("")
    elif summary.rejection_reason:
        lines += [
            "## Rejection Reason",
            "",
            summary.rejection_reason,
            "",
        ]

    lines += [
        "## Next Action",
        "",
        next_action,
        "",
        "## Assumptions",
        "",
        "- Market eligibility: active=True, accepting_orders!=False, exactly 2 CLOB tokens",
        "- Symbol match: BTC/Bitcoin, ETH/Ethereum/Ether, SOL/Solana (case-insensitive, keyword match)",
        "- Duration match: 5m/5min/5 minute, 15m/15min/15 minute (keyword match)",
        "- v0: --symbol/--duration flags are accepted for future filter wiring but do not filter",
        "  the underlying Gamma query in this release; discovery always returns all eligible markets",
        "",
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_artifacts(
    run_dir: Path,
    run_id: str,
    mode: str,
    summary: AvailabilitySummary,
    generated_at: str,
) -> dict:
    manifest: dict[str, Any] = {
        "run_id": run_id,
        "generated_at": generated_at,
        "mode": mode,
        "summary_ref": str(run_dir / "availability_summary.json"),
        "artifact_dir": str(run_dir),
    }
    _write_json(run_dir / "watch_manifest.json", manifest)
    _write_json(run_dir / "availability_summary.json", dataclasses.asdict(summary))
    _write_markdown(
        run_dir / "availability_summary.md",
        summary,
        run_id,
        mode,
        generated_at,
    )
    return manifest


# ---------------------------------------------------------------------------
# Core watch function (injectable for tests)
# ---------------------------------------------------------------------------

def run_crypto_pair_watch(
    *,
    watch_mode: bool = False,
    poll_interval_seconds: int = 60,
    timeout_seconds: int = 3600,
    output_base: Optional[Path] = None,
    gamma_client=None,
    _check_fn: Optional[Callable[[], AvailabilitySummary]] = None,
    _sleep_fn: Optional[Callable[[float], None]] = None,
) -> dict[str, Any]:
    """Run the market availability check and write artifact bundle.

    DRY-RUN ONLY — no orders are submitted.

    Args:
        watch_mode: If True, poll until eligible markets appear or timeout.
        poll_interval_seconds: Seconds between polls in watch mode.
        timeout_seconds: Max seconds to poll before giving up (watch mode only).
        output_base: Root artifact directory; defaults to
            ``artifacts/crypto_pairs/watch``.
        gamma_client: Injected GammaClient for testing (default: live).
        _check_fn: Replaces run_availability_check for offline testing.
        _sleep_fn: Replaces time.sleep for offline testing.

    Returns:
        ``watch_manifest.json`` payload as a dict.
    """
    now = _utcnow()
    date_str = now.date().isoformat()
    run_id = uuid.uuid4().hex[:12]
    base_dir = output_base or Path("artifacts/crypto_pairs/watch")
    run_dir = _run_dir(base_dir, date_str, run_id)
    generated_at = _iso_utc(now)

    effective_check_fn = (
        _check_fn
        if _check_fn is not None
        else lambda: run_availability_check(gamma_client=gamma_client)
    )

    if not watch_mode:
        # One-shot mode
        summary = effective_check_fn()
        _print_summary(summary)
        mode = "one_shot"
    else:
        # Watch mode
        print(
            f"[crypto-pair-watch] Entering watch mode "
            f"(poll every {poll_interval_seconds}s, timeout {timeout_seconds}s)..."
        )
        found, summary = run_watch_loop(
            poll_interval_seconds=poll_interval_seconds,
            timeout_seconds=timeout_seconds,
            gamma_client=gamma_client,
            _sleep_fn=_sleep_fn,
            _check_fn=effective_check_fn,
        )
        _print_summary(summary)
        if found:
            slugs_str = ", ".join(summary.first_eligible_slugs)
            print(
                f"[crypto-pair-watch] Markets found: {slugs_str}"
            )
            print(
                "[crypto-pair-watch] Next action: run crypto-pair-scan then crypto-pair-run"
            )
        else:
            print(
                f"[crypto-pair-watch] Watch mode timed out after {timeout_seconds}s. "
                "No eligible markets found."
            )
        mode = "watch"

    manifest = _write_artifacts(run_dir, run_id, mode, summary, generated_at)
    print(f"[crypto-pair-watch] Bundle written: {run_dir}")
    return manifest


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Market availability watcher for crypto pair bot — Track 2 / Phase 1A. "
            "Checks whether eligible BTC/ETH/SOL 5m/15m binary markets exist. "
            "No orders are submitted. No wallet credentials required."
        )
    )
    parser.add_argument(
        "--symbol",
        choices=["BTC", "ETH", "SOL"],
        default=None,
        help=(
            "Reserved for future filter wiring (v0: accepted but does not filter "
            "the Gamma query; all eligible symbols are always returned)."
        ),
    )
    parser.add_argument(
        "--duration",
        type=int,
        choices=[5, 15],
        default=None,
        help=(
            "Reserved for future filter wiring (v0: accepted but does not filter "
            "the Gamma query; all eligible durations are always returned)."
        ),
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Enter watch mode: poll until eligible markets appear or --timeout elapses.",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=60,
        help="Seconds between polls in watch mode (default: 60).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=3600,
        help="Watch mode timeout in seconds (default: 3600). Exit 1 when reached.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Base artifact directory (default: artifacts/crypto_pairs/watch).",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    output_base = Path(args.output) if args.output else None
    try:
        manifest = run_crypto_pair_watch(
            watch_mode=args.watch,
            poll_interval_seconds=args.poll_interval,
            timeout_seconds=args.timeout,
            output_base=output_base,
        )
    except Exception as exc:
        print(
            f"crypto-pair-watch failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1

    if args.watch:
        # Watch mode: check summary to determine exit code
        # The manifest doesn't carry found flag, so we re-read it.
        # Simpler: read availability_summary.json from the artifact dir.
        artifact_dir = Path(manifest["artifact_dir"])
        summary_path = artifact_dir / "availability_summary.json"
        try:
            data = json.loads(summary_path.read_text(encoding="utf-8"))
            return 0 if data.get("eligible_now") else 1
        except Exception:
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
