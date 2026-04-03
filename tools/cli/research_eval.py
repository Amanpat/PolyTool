"""CLI entrypoint for RIS v1 document evaluation.

Usage (eval subcommand — default, backward compatible):
  python -m polytool research-eval --file path/to/doc.md
  python -m polytool research-eval --title "Title" --body "Body text..." --source-type arxiv
  python -m polytool research-eval eval --title "Title" --body "Body..." --json
  python -m polytool research-eval eval --provider ollama --title "Title" --body "Body..."
  python -m polytool research-eval eval --provider gemini --enable-cloud --title "T" --body "B"

Usage (replay subcommand):
  python -m polytool research-eval replay --event-id <id> --artifacts-dir <path> --file doc.md
  python -m polytool research-eval replay --event-id <id> --artifacts-dir <path> --provider ollama --title T --body B

Usage (list-providers subcommand):
  python -m polytool research-eval list-providers

Cloud provider guard:
  Non-local providers (gemini, deepseek, openai, anthropic) require either:
  - RIS_ENABLE_CLOUD_PROVIDERS=1 env var, or
  - --enable-cloud flag

  Local providers (manual, ollama) always work without any env var.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Subcommands recognized by the CLI. Used for backward-compat routing.
_KNOWN_SUBCOMMANDS = frozenset({"eval", "replay", "list-providers"})

# Local providers that do not require the cloud guard env var.
_LOCAL_PROVIDERS = frozenset({"manual", "ollama"})


def main(argv: list) -> int:
    """Research-eval CLI entrypoint.

    Dispatches to subcommands: eval (default), replay, list-providers.
    Backward compatible: if argv[0] is not a known subcommand and contains
    --file or --title, routes to the eval subcommand.

    Returns:
        0 on success
        1 on argument/input error
        2 on evaluation error
    """
    if not argv:
        _print_top_help()
        return 1

    # Backward compat routing: if first arg is not a known subcommand,
    # treat as eval subcommand (existing callers use --file/--title directly)
    first = argv[0]
    if first not in _KNOWN_SUBCOMMANDS:
        return _cmd_eval(argv)

    subcommand = argv[0]
    rest = argv[1:]

    if subcommand == "eval":
        return _cmd_eval(rest)
    elif subcommand == "replay":
        return _cmd_replay(rest)
    elif subcommand == "list-providers":
        return _cmd_list_providers(rest)

    _print_top_help()
    return 1


def _print_top_help() -> None:
    print(
        "research-eval: RIS document evaluation CLI\n"
        "\n"
        "Subcommands:\n"
        "  eval          Evaluate a document through the quality gate (default)\n"
        "  replay        Re-run a prior eval with a different provider; diff the results\n"
        "  list-providers  Show available providers, enablement status, and env var needed\n"
        "\n"
        "Run `research-eval <subcommand> --help` for subcommand-specific help.\n"
        "Backward compat: flags like --file/--title without a subcommand route to eval.",
        file=sys.stderr,
    )


def _apply_cloud_guard(args_enable_cloud: bool) -> None:
    """Set the cloud guard env var if --enable-cloud was passed."""
    if args_enable_cloud:
        os.environ["RIS_ENABLE_CLOUD_PROVIDERS"] = "1"


def _check_provider_guard(provider_name: str) -> int | None:
    """Pre-flight cloud guard check with friendly error message.

    Returns None if OK to proceed, or an int exit code to return immediately.
    """
    if provider_name not in _LOCAL_PROVIDERS:
        if os.environ.get("RIS_ENABLE_CLOUD_PROVIDERS", "") != "1":
            print(
                f"Error: cloud provider '{provider_name}' requires opt-in.\n"
                "\n"
                "Cloud providers (gemini, deepseek, openai, anthropic) are not enabled by default.\n"
                "To enable, either:\n"
                "  - Set the env var: RIS_ENABLE_CLOUD_PROVIDERS=1\n"
                "  - Pass the --enable-cloud flag on this command\n"
                "\n"
                "Local providers (manual, ollama) always work without this flag.",
                file=sys.stderr,
            )
            return 1
    return None


def _build_eval_parser(prog: str = "research-eval eval") -> argparse.ArgumentParser:
    """Build the argument parser for the eval subcommand."""
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Evaluate a document through the RIS v1 quality gate.",
    )
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "--file", metavar="PATH",
        help="Read document from file (markdown or plain text). Title from filename.",
    )
    parser.add_argument(
        "--title", metavar="TEXT",
        help="Document title (required if no --file).",
    )
    parser.add_argument(
        "--body", metavar="TEXT",
        help="Document body inline (required if no --file).",
    )
    parser.add_argument(
        "--source-type", metavar="TYPE", default="manual",
        help="Source type (default: manual). Examples: arxiv, reddit, github, blog, news.",
    )
    parser.add_argument(
        "--author", metavar="TEXT", default="unknown",
        help="Document author (default: unknown).",
    )
    parser.add_argument(
        "--provider", metavar="NAME", default="manual",
        help=(
            "Evaluation provider (default: manual). Local: manual, ollama. "
            "Cloud (require --enable-cloud or RIS_ENABLE_CLOUD_PROVIDERS=1): "
            "gemini, deepseek, openai, anthropic."
        ),
    )
    parser.add_argument(
        "--enable-cloud", action="store_true", default=False,
        help="Enable cloud providers by setting RIS_ENABLE_CLOUD_PROVIDERS=1 for this invocation.",
    )
    parser.add_argument(
        "--json", dest="output_json", action="store_true",
        help="Output raw JSON instead of formatted text.",
    )
    parser.add_argument(
        "--artifacts-dir", metavar="PATH", default=None,
        help=(
            "If set, persist a structured eval artifact to PATH/eval_artifacts.jsonl. "
            "When --json is also set, the output includes provider_event metadata."
        ),
    )
    return parser


def _cmd_eval(argv: list) -> int:
    """Execute the 'eval' subcommand."""
    parser = _build_eval_parser()

    if not argv:
        parser.print_help(sys.stderr)
        return 1

    args = parser.parse_args(argv)

    # Apply cloud guard before any provider calls
    _apply_cloud_guard(args.enable_cloud)
    guard_rc = _check_provider_guard(args.provider)
    if guard_rc is not None:
        return guard_rc

    # Resolve document content
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1
        title = file_path.stem
        body = file_path.read_text(encoding="utf-8")
    else:
        if not args.title or not args.body:
            print(
                "Error: --title and --body are required when --file is not provided.",
                file=sys.stderr,
            )
            return 1
        title = args.title
        body = args.body

    # Resolve artifacts_dir
    artifacts_dir = Path(args.artifacts_dir) if args.artifacts_dir else None

    # Build doc and evaluate
    try:
        from packages.research.evaluation.types import EvalDocument
        from packages.research.evaluation.evaluator import evaluate_document
        from packages.research.evaluation.feature_extraction import extract_features
        from packages.research.evaluation.artifacts import load_eval_artifacts

        import hashlib
        doc_id = "cli_" + hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]

        doc = EvalDocument(
            doc_id=doc_id,
            title=title,
            author=args.author,
            source_type=args.source_type,
            source_url="",
            source_publish_date=None,
            body=body,
        )

        print(f"Using provider: {args.provider}", file=sys.stderr)

        decision = evaluate_document(doc, provider_name=args.provider, artifacts_dir=artifacts_dir)

        # Extract features for optional JSON output enrichment
        features_result = extract_features(doc) if args.output_json else None

    except PermissionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: evaluation failed: {exc}", file=sys.stderr)
        return 2

    # Output
    if args.output_json:
        output = {
            "gate": decision.gate,
            "doc_id": decision.doc_id,
            "timestamp": decision.timestamp,
        }
        if decision.scores:
            output["scores"] = {
                "relevance": decision.scores.relevance,
                "novelty": decision.scores.novelty,
                "actionability": decision.scores.actionability,
                "credibility": decision.scores.credibility,
                "total": decision.scores.total,
                "epistemic_type": decision.scores.epistemic_type,
                "summary": decision.scores.summary,
                "key_findings": decision.scores.key_findings,
                "eval_model": decision.scores.eval_model,
            }
        if decision.hard_stop and not decision.hard_stop.passed:
            output["hard_stop"] = {
                "stop_type": decision.hard_stop.stop_type,
                "reason": decision.hard_stop.reason,
            }
        # Include features and near_duplicate in JSON output when artifacts_dir set
        if args.artifacts_dir and features_result is not None:
            output["features"] = {
                "family": features_result.family,
                "values": features_result.features,
                "confidence_signals": features_result.confidence_signals,
            }
            # Load the last artifact to retrieve near_duplicate result and provider_event
            if artifacts_dir is not None:
                loaded = load_eval_artifacts(artifacts_dir)
                if loaded:
                    last = loaded[-1]
                    ndr = last.get("near_duplicate_result")
                    if ndr:
                        output["near_duplicate"] = ndr
                    pe = last.get("provider_event")
                    if pe:
                        output["provider_event"] = pe
                    eid = last.get("event_id")
                    if eid:
                        output["event_id"] = eid
        print(json.dumps(output, indent=2))
    else:
        if decision.hard_stop and not decision.hard_stop.passed:
            print(
                f"Gate: REJECT | Hard stop: {decision.hard_stop.stop_type} "
                f"-- {decision.hard_stop.reason}"
            )
        elif decision.scores:
            s = decision.scores
            print(
                f"Gate: {decision.gate} | Total: {s.total}/20 | "
                f"R:{s.relevance} N:{s.novelty} A:{s.actionability} C:{s.credibility} | "
                f"Model: {s.eval_model}"
            )
        else:
            print(f"Gate: {decision.gate}")

    return 0


def _cmd_replay(argv: list) -> int:
    """Execute the 'replay' subcommand.

    Re-runs scoring on a previously evaluated document and produces a structured
    diff between the original and replay evaluation artifacts.
    """
    parser = argparse.ArgumentParser(
        prog="research-eval replay",
        description="Re-run a prior evaluation with a different provider and compare results.",
    )
    parser.add_argument(
        "--event-id", metavar="ID", required=True,
        help="event_id from a prior eval artifact (16-char hex string).",
    )
    parser.add_argument(
        "--artifacts-dir", metavar="PATH", required=True,
        help="Artifacts directory containing the original eval_artifacts.jsonl.",
    )
    # Document input (required because artifact does not store body)
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "--file", metavar="PATH",
        help="Read document body from file (required — artifact does not store body).",
    )
    parser.add_argument(
        "--title", metavar="TEXT", default=None,
        help="Document title (used when --file is not provided).",
    )
    parser.add_argument(
        "--body", metavar="TEXT", default=None,
        help="Document body inline (required when --file is not provided).",
    )
    parser.add_argument(
        "--provider", metavar="NAME", default="manual",
        help="Provider to use for the replay (default: manual).",
    )
    parser.add_argument(
        "--enable-cloud", action="store_true", default=False,
        help="Enable cloud providers for this invocation.",
    )
    parser.add_argument(
        "--json", dest="output_json", action="store_true",
        help="Output the ReplayDiff as JSON.",
    )

    if not argv:
        parser.print_help(sys.stderr)
        return 1

    args = parser.parse_args(argv)

    # Apply cloud guard
    _apply_cloud_guard(args.enable_cloud)
    guard_rc = _check_provider_guard(args.provider)
    if guard_rc is not None:
        return guard_rc

    artifacts_dir = Path(args.artifacts_dir)

    # Find the original artifact
    try:
        from packages.research.evaluation.replay import (
            find_artifact_by_event_id,
            replay_eval,
            compare_eval_events,
            persist_replay_diff,
        )
        from packages.research.evaluation.artifacts import load_eval_artifacts
        from packages.research.evaluation.types import EvalDocument
    except Exception as exc:
        print(f"Error: import failed: {exc}", file=sys.stderr)
        return 2

    original_artifact = find_artifact_by_event_id(args.event_id, artifacts_dir)
    if original_artifact is None:
        print(
            f"Error: no artifact found with event_id='{args.event_id}' in {artifacts_dir}",
            file=sys.stderr,
        )
        return 1

    # Resolve document content
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1
        title = file_path.stem
        body = file_path.read_text(encoding="utf-8")
    elif args.body:
        title = args.title or original_artifact.get("doc_id", "replay_doc")
        body = args.body
    else:
        print(
            "Error: --file or --body is required for replay "
            "(document body is not stored in the artifact).",
            file=sys.stderr,
        )
        return 1

    # Build doc using original artifact's metadata where available
    import hashlib
    doc_id = original_artifact.get("doc_id", "cli_" + hashlib.sha256(body.encode()).hexdigest()[:12])
    source_type = original_artifact.get("source_type", "manual")

    doc = EvalDocument(
        doc_id=doc_id,
        title=title,
        author="unknown",
        source_type=source_type,
        source_url="",
        source_publish_date=None,
        body=body,
    )

    print(f"Using provider: {args.provider} (replay)", file=sys.stderr)

    # Run replay eval, persisting to a temporary subdir to avoid polluting the main JSONL
    import tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            decision, replay_pe = replay_eval(
                doc, provider_name=args.provider, artifacts_dir=Path(tmp_dir)
            )
        except PermissionError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        except Exception as exc:
            print(f"Error: replay evaluation failed: {exc}", file=sys.stderr)
            return 2

        # Load the replay artifact
        from packages.research.evaluation.artifacts import load_eval_artifacts as _load
        replay_arts = _load(Path(tmp_dir))

    if not replay_arts:
        print("Error: replay produced no artifact (hard-stop triggered?)", file=sys.stderr)
        return 2

    replay_artifact = replay_arts[-1]

    # Compare
    diff = compare_eval_events(original_artifact, replay_artifact)

    # Persist diff
    diff_path = persist_replay_diff(diff, artifacts_dir)

    # Output
    if args.output_json:
        import dataclasses
        print(json.dumps(dataclasses.asdict(diff), indent=2))
    else:
        total_orig = (original_artifact.get("scores") or {}).get("total", "?")
        total_replay = (replay_artifact.get("scores") or {}).get("total", "?")
        orig_pe = original_artifact.get("provider_event") or {}

        print(f"Replay: {args.event_id} -> {replay_artifact.get('event_id', 'N/A')}")
        print(
            f"Original: {diff.provider_original} ({diff.prompt_template_original}) "
            f"-> {diff.original_gate} ({total_orig}/20)"
        )
        print(
            f"Replay:   {diff.provider_replay} ({diff.prompt_template_replay}) "
            f"-> {diff.replay_gate} ({total_replay}/20)"
        )
        print(f"Gate changed: {'yes' if diff.gate_changed else 'no'}")
        if diff.diff_fields:
            print("Diff:")
            for dim, vals in diff.diff_fields.items():
                print(f"  {dim}: {vals['original']} -> {vals['replay']}")
        else:
            print("Diff: (no scoring changes)")
        print(f"Diff saved: {diff_path}")

    return 0


def _cmd_list_providers(argv: list) -> int:
    """Execute the 'list-providers' subcommand."""
    cloud_enabled = os.environ.get("RIS_ENABLE_CLOUD_PROVIDERS", "") == "1"
    env_status = "SET" if cloud_enabled else "not set"

    print("Available providers:")
    print(f"  manual   [local]  — always enabled (no env var needed)")
    print(f"  ollama   [local]  — always enabled (no env var needed)")
    print(f"  gemini   [cloud]  — requires RIS_ENABLE_CLOUD_PROVIDERS=1 (not yet implemented)")
    print(f"  deepseek [cloud]  — requires RIS_ENABLE_CLOUD_PROVIDERS=1 (not yet implemented)")
    print(f"  openai   [cloud]  — requires RIS_ENABLE_CLOUD_PROVIDERS=1 (not yet implemented)")
    print(f"  anthropic [cloud] — requires RIS_ENABLE_CLOUD_PROVIDERS=1 (not yet implemented)")
    print()
    print(f"Cloud guard env var: RIS_ENABLE_CLOUD_PROVIDERS = {env_status}")
    if not cloud_enabled:
        print("  To enable cloud providers: export RIS_ENABLE_CLOUD_PROVIDERS=1")
        print("  Or pass --enable-cloud on individual commands.")
    return 0
