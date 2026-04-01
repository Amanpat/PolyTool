"""CLI entrypoint for RIS v1 precheck runner.

Usage:
  python -m polytool research-precheck --idea "Is crypto pair accumulation viable?"
  python -m polytool research-precheck --idea "Test idea" --no-ledger
  python -m polytool research-precheck --idea "Test idea" --ledger path/to/ledger.jsonl
  python -m polytool research-precheck --idea "Test idea" --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list) -> int:
    """Run a precheck on an idea and print the recommendation.

    Returns:
        0 on success
        1 on argument error
    """
    parser = argparse.ArgumentParser(
        prog="research-precheck",
        description="Pre-development check: GO / CAUTION / STOP recommendation for an idea.",
    )
    parser.add_argument(
        "--idea", metavar="TEXT", required=True,
        help="The idea or concept to evaluate (required).",
    )
    parser.add_argument(
        "--provider", metavar="NAME", default="manual",
        choices=["manual", "ollama"],
        help="Evaluation provider (default: manual).",
    )
    parser.add_argument(
        "--ledger", metavar="PATH", default=None,
        help="Custom ledger path (default: artifacts/research/prechecks/precheck_ledger.jsonl).",
    )
    parser.add_argument(
        "--no-ledger", action="store_true",
        help="Skip writing to the ledger (dry-run mode).",
    )
    parser.add_argument(
        "--json", dest="output_json", action="store_true",
        help="Output raw JSON instead of formatted text.",
    )

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        raise

    # Resolve ledger path
    if args.no_ledger:
        ledger_path = None
    elif args.ledger:
        ledger_path = Path(args.ledger)
    else:
        # Use default ledger path from ledger module
        from packages.research.synthesis.precheck_ledger import DEFAULT_LEDGER_PATH
        ledger_path = DEFAULT_LEDGER_PATH

    # Run precheck
    try:
        from packages.research.synthesis.precheck import run_precheck
        result = run_precheck(
            args.idea,
            provider_name=args.provider,
            ledger_path=ledger_path,
        )
    except Exception as exc:
        print(f"Error: precheck failed: {exc}", file=sys.stderr)
        return 1

    # Output
    if args.output_json:
        output = {
            "recommendation": result.recommendation,
            "idea": result.idea,
            "supporting_evidence": result.supporting_evidence,
            "contradicting_evidence": result.contradicting_evidence,
            "risk_factors": result.risk_factors,
            "stale_warning": result.stale_warning,
            "timestamp": result.timestamp,
            "provider_used": result.provider_used,
            # Enriched fields (v1)
            "precheck_id": result.precheck_id,
            "reason_code": result.reason_code,
            "evidence_gap": result.evidence_gap,
            "review_horizon": result.review_horizon,
        }
        print(json.dumps(output, indent=2))
    else:
        def _bullet_list(items: list, fallback: str = "  (none)") -> str:
            if not items:
                return fallback
            return "\n".join(f"  - {item}" for item in items)

        print(f"Recommendation: {result.recommendation}")
        print("")
        print(f"Idea: {result.idea}")
        print("")
        print("Supporting:")
        print(_bullet_list(result.supporting_evidence))
        print("")
        print("Contradicting:")
        print(_bullet_list(result.contradicting_evidence))
        print("")
        print("Risks:")
        print(_bullet_list(result.risk_factors))
        print("")
        print(f"Stale warning: {'yes' if result.stale_warning else 'no'}")

        if ledger_path is not None:
            print(f"\nLogged to: {ledger_path}")

    return 0
