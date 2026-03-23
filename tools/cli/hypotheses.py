"""Hypothesis registry plus experiment-init/experiment-run CLI commands."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from packages.polymarket.hypotheses.diff import (
    diff_hypothesis_documents,
    load_hypothesis_artifact,
)
from packages.polymarket.hypotheses.summary import (
    extract_hypothesis_summary,
    load_hypothesis_summary_artifact,
)
from packages.polymarket.hypotheses.validator import validate_hypothesis_json
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


def handle_hypothesis_validate(args: argparse.Namespace) -> int:
    report_path = Path(args.hypothesis_path)
    try:
        raw = report_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"Error: file not found: {report_path}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error reading file: {exc}", file=sys.stderr)
        return 1

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON in {report_path}: {exc}", file=sys.stderr)
        return 1

    result = validate_hypothesis_json(data)
    print(
        json.dumps(
            {"valid": result.valid, "errors": result.errors, "warnings": result.warnings},
            indent=2,
        )
    )
    return 0 if result.valid else 1


def handle_hypothesis_diff(args: argparse.Namespace) -> int:
    old_path = Path(args.old)
    new_path = Path(args.new)

    try:
        old_doc = load_hypothesis_artifact(old_path)
        new_doc = load_hypothesis_artifact(new_path)
    except FileNotFoundError as exc:
        print(f"Error: file not found: {exc.filename}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error reading file: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    payload = diff_hypothesis_documents(
        old_doc,
        new_doc,
        old_path=old_path.as_posix(),
        new_path=new_path.as_posix(),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def handle_hypothesis_summary(args: argparse.Namespace) -> int:
    hypothesis_path = Path(args.hypothesis_path)

    try:
        document = load_hypothesis_summary_artifact(hypothesis_path)
    except FileNotFoundError:
        print(f"Error: file not found: {hypothesis_path}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error reading file: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    payload = extract_hypothesis_summary(
        document,
        hypothesis_path=hypothesis_path.as_posix(),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
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

    validate_parser = subparsers.add_parser(
        "hypothesis-validate",
        help="Validate a hypothesis JSON file against hypothesis_schema_v1.",
    )
    validate_parser.add_argument(
        "--hypothesis-path",
        required=True,
        help="Path to the hypothesis JSON file to validate.",
    )
    validate_parser.set_defaults(func=handle_hypothesis_validate)

    diff_parser = subparsers.add_parser(
        "hypothesis-diff",
        help="Compare two saved hypothesis JSON artifacts and emit a structured diff.",
    )
    diff_parser.add_argument(
        "--old",
        required=True,
        help="Path to the older hypothesis JSON artifact.",
    )
    diff_parser.add_argument(
        "--new",
        required=True,
        help="Path to the newer hypothesis JSON artifact.",
    )
    diff_parser.set_defaults(func=handle_hypothesis_diff)

    summary_parser = subparsers.add_parser(
        "hypothesis-summary",
        help="Extract a deterministic summary from a saved hypothesis JSON artifact.",
    )
    summary_parser.add_argument(
        "--hypothesis-path",
        required=True,
        help="Path to the hypothesis JSON artifact to summarize.",
    )
    summary_parser.set_defaults(func=handle_hypothesis_summary)


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
