"""Hypothesis registry plus experiment-init/experiment-run CLI commands."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from packages.research.hypotheses.registry import (
    VALID_STATUSES,
    experiment_init,
    experiment_run,
    get_latest,
    register_from_candidate,
    update_status,
)


def handle_hypothesis_register(args: argparse.Namespace) -> int:
    try:
        hypothesis_id = register_from_candidate(
            registry_path=Path(args.registry),
            candidate_file=Path(args.candidate_file),
            rank=args.rank,
            title=args.title,
            notes=args.notes,
        )
    except Exception as exc:
        print(f"Error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(f"Hypothesis registered: {hypothesis_id}")
    print(f"Registry: {Path(args.registry)}")
    return 0


def handle_hypothesis_status(args: argparse.Namespace) -> int:
    try:
        update_status(
            registry_path=Path(args.registry),
            hypothesis_id=args.id,
            status=args.status,
            reason=args.reason,
        )
    except Exception as exc:
        print(f"Error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(f"Hypothesis updated: {args.id} -> {args.status}")
    return 0


def handle_experiment_init(args: argparse.Namespace) -> int:
    try:
        registry_snapshot = get_latest(Path(args.registry), args.id)
        out_path = experiment_init(
            outdir=Path(args.outdir),
            hypothesis_id=args.id,
            registry_snapshot=registry_snapshot,
        )
    except Exception as exc:
        print(f"Error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(f"Experiment initialized: {out_path}")
    return 0


def handle_experiment_run(args: argparse.Namespace) -> int:
    try:
        registry_snapshot = get_latest(Path(args.registry), args.id)
        out_path = experiment_run(
            outdir=Path(args.outdir),
            hypothesis_id=args.id,
            registry_snapshot=registry_snapshot,
        )
    except Exception as exc:
        print(f"Error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(f"Experiment initialized: {out_path}")
    return 0


def register_subparser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    register_parser = subparsers.add_parser(
        "hypothesis-register",
        help="Register a candidate into the offline hypothesis registry.",
    )
    register_parser.add_argument("--candidate-file", required=True, help="Path to alpha_candidates.json.")
    register_parser.add_argument("--rank", required=True, type=int, help="Candidate rank to register.")
    register_parser.add_argument("--registry", required=True, help="Path to registry.jsonl.")
    register_parser.add_argument("--title", default=None, help="Optional title override.")
    register_parser.add_argument("--notes", default=None, help="Optional registration note.")
    register_parser.set_defaults(func=handle_hypothesis_register)

    status_parser = subparsers.add_parser(
        "hypothesis-status",
        help="Append a hypothesis status change event.",
    )
    status_parser.add_argument("--id", required=True, help="Hypothesis ID.")
    status_parser.add_argument(
        "--status",
        required=True,
        choices=VALID_STATUSES,
        help="New lifecycle status.",
    )
    status_parser.add_argument("--reason", required=True, help="Human-readable status change reason.")
    status_parser.add_argument("--registry", required=True, help="Path to registry.jsonl.")
    status_parser.set_defaults(func=handle_hypothesis_status)

    experiment_parser = subparsers.add_parser(
        "experiment-init",
        help="Create an experiment.json skeleton for a registered hypothesis.",
    )
    experiment_parser.add_argument("--id", required=True, help="Hypothesis ID.")
    experiment_parser.add_argument("--registry", required=True, help="Path to registry.jsonl.")
    experiment_parser.add_argument("--outdir", required=True, help="Directory for experiment.json.")
    experiment_parser.set_defaults(func=handle_experiment_init)

    experiment_run_parser = subparsers.add_parser(
        "experiment-run",
        help="Create a generated experiment attempt directory and experiment.json for a registered hypothesis.",
    )
    experiment_run_parser.add_argument("--id", required=True, help="Hypothesis ID.")
    experiment_run_parser.add_argument("--registry", required=True, help="Path to registry.jsonl.")
    experiment_run_parser.add_argument(
        "--outdir",
        required=True,
        help="Parent directory where a generated experiment attempt directory will be created.",
    )
    experiment_run_parser.set_defaults(func=handle_experiment_run)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Offline hypothesis registry, experiment-init, and experiment-run commands.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    register_subparser(subparsers)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 1
    return int(func(args))


if __name__ == "__main__":
    raise SystemExit(main())
