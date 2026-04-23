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

Usage (compare subcommand):
  python -m polytool research-eval compare --provider-a manual --provider-b ollama --title T --body B
  python -m polytool research-eval compare --provider-a gemini --provider-b deepseek --enable-cloud --file doc.md --json

Cloud provider guard:
  Implemented cloud providers (gemini, deepseek) require either:
  - RIS_ENABLE_CLOUD_PROVIDERS=1 env var, or
  - --enable-cloud flag

  Recognized but not yet implemented: openai, anthropic.
  Local providers (manual, ollama) always work without any env var.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Subcommands recognized by the CLI. Used for backward-compat routing.
_KNOWN_SUBCOMMANDS = frozenset({"eval", "replay", "list-providers", "compare"})

# Local providers that do not require the cloud guard env var.
_LOCAL_PROVIDERS = frozenset({"manual", "ollama"})

# Cloud providers with a working implementation.
_IMPLEMENTED_CLOUD_PROVIDERS = frozenset({"gemini", "deepseek"})

# Cloud providers recognized by name but not yet implemented.
_UNIMPLEMENTED_CLOUD_PROVIDERS = frozenset({"openai", "anthropic"})


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
    elif subcommand == "compare":
        return _cmd_compare(rest)

    _print_top_help()
    return 1


def _print_top_help() -> None:
    print(
        "research-eval: RIS document evaluation CLI\n"
        "\n"
        "Subcommands:\n"
        "  eval            Evaluate a document through the quality gate (default)\n"
        "  replay          Re-run a prior eval with a different provider; diff the results\n"
        "  compare         Run the same document through two providers and diff gate results\n"
        "  list-providers  Show available providers, enablement status, and routing config\n"
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
    """Pre-flight provider check with friendly error messages.

    Checks in order:
      1. Unimplemented cloud providers — hard error regardless of cloud guard.
      2. Cloud guard — implemented cloud providers require opt-in env var.

    Returns None if OK to proceed, or an int exit code to return immediately.
    """
    if provider_name in _UNIMPLEMENTED_CLOUD_PROVIDERS:
        print(
            f"Error: '{provider_name}' is recognized but not yet implemented.\n"
            "\n"
            f"Implemented providers: manual, ollama (local); gemini, deepseek (cloud).\n"
            f"'{provider_name}' is on the roadmap but has no backend yet.",
            file=sys.stderr,
        )
        return 1
    if provider_name not in _LOCAL_PROVIDERS:
        if os.environ.get("RIS_ENABLE_CLOUD_PROVIDERS", "") != "1":
            print(
                f"Error: cloud provider '{provider_name}' requires opt-in.\n"
                "\n"
                "Implemented cloud providers (gemini, deepseek) are not enabled by default.\n"
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
        "--provider", metavar="NAME", default=None,
        help=(
            "Evaluation provider (default: auto from routing config, usually 'manual'). "
            "Local: manual, ollama. "
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
    parser.add_argument(
        "--priority-tier", metavar="TIER", dest="priority_tier", default=None,
        choices=["priority_1", "priority_2", "priority_3", "priority_4"],
        help=(
            "Priority tier for gate thresholds (default: config default, usually priority_3). "
            "priority_1 applies lower threshold (2.5) for trusted sources; "
            "priority_4 applies higher threshold (3.5) for low-trust sources."
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

    # Resolve the effective provider for the guard check.
    # If --provider was not supplied, defer to routing config (same logic as evaluate_document).
    if args.provider is not None:
        _effective_provider = args.provider
    else:
        from packages.research.evaluation.config import get_eval_config as _get_eval_cfg
        _routing = _get_eval_cfg().routing
        _effective_provider = _routing.primary_provider if _routing.mode == "route" else "manual"

    guard_rc = _check_provider_guard(_effective_provider)
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

        print(f"Using provider: {_effective_provider}", file=sys.stderr)

        decision = evaluate_document(
            doc,
            provider_name=args.provider,  # None → evaluate_document reads routing config
            artifacts_dir=artifacts_dir,
            priority_tier=getattr(args, "priority_tier", None),
        )

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
                # Phase 2 fields
                "composite_score": decision.scores.composite_score,
                "simple_sum_score": decision.scores.simple_sum_score,
                "priority_tier": decision.scores.priority_tier,
                "reject_reason": decision.scores.reject_reason,
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
                    from packages.research.evaluation.artifacts import normalize_provider_events
                    pe_list = normalize_provider_events(last)
                    if pe_list:
                        output["provider_events"] = pe_list
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

    print("Local providers (always enabled):")
    print("  manual   — rule-based scorer, no API key required")
    print("  ollama   — local LLM via Ollama, no API key required")
    print()
    print("Cloud providers — implemented (require RIS_ENABLE_CLOUD_PROVIDERS=1):")
    gemini_key = "GEMINI_API_KEY set" if os.environ.get("GEMINI_API_KEY") else "GEMINI_API_KEY not set"
    deepseek_key = "DEEPSEEK_API_KEY set" if os.environ.get("DEEPSEEK_API_KEY") else "DEEPSEEK_API_KEY not set"
    gemini_ready = "READY" if (cloud_enabled and os.environ.get("GEMINI_API_KEY")) else ("needs key" if cloud_enabled else "needs guard+key")
    deepseek_ready = "READY" if (cloud_enabled and os.environ.get("DEEPSEEK_API_KEY")) else ("needs key" if cloud_enabled else "needs guard+key")
    print(f"  gemini   — GeminiFlashProvider  [{gemini_ready}] ({gemini_key})")
    print(f"  deepseek — DeepSeekV3Provider   [{deepseek_ready}] ({deepseek_key})")
    print()
    print("Cloud providers — not yet implemented (roadmap only):")
    print("  openai    — recognized but raises error; not yet implemented")
    print("  anthropic — recognized but raises error; not yet implemented")
    print()
    print(f"Cloud guard: RIS_ENABLE_CLOUD_PROVIDERS = {env_status}")
    if not cloud_enabled:
        print("  To enable cloud providers: export RIS_ENABLE_CLOUD_PROVIDERS=1")
        print("  Or pass --enable-cloud on individual commands.")
    print()

    # Show current routing config
    try:
        from packages.research.evaluation.config import get_eval_config
        cfg = get_eval_config()
        r = cfg.routing
        print(f"Routing config (from ris_eval_config.json / env vars):")
        print(f"  mode               = {r.mode}")
        print(f"  primary_provider   = {r.primary_provider}")
        print(f"  escalation_provider= {r.escalation_provider}")
        print()
        print(f"Budget caps (calls/day):")
        for pname, cap in cfg.budget.per_provider.items():
            print(f"  {pname:<10} = {cap}")
    except Exception:
        pass

    return 0


def _cmd_compare(argv: list) -> int:
    """Execute the 'compare' subcommand.

    Runs the same document through two implemented providers in direct mode
    and prints a side-by-side gate/score comparison.
    """
    parser = argparse.ArgumentParser(
        prog="research-eval compare",
        description=(
            "Evaluate the same document with two providers and compare gate results. "
            "Both providers must be implemented (manual, ollama, gemini, deepseek). "
            "Each eval runs in direct mode (routing config is ignored)."
        ),
    )
    parser.add_argument(
        "--provider-a", metavar="NAME", required=True,
        help="First provider (local: manual, ollama; cloud: gemini, deepseek).",
    )
    parser.add_argument(
        "--provider-b", metavar="NAME", required=True,
        help="Second provider.",
    )
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "--file", metavar="PATH",
        help="Read document from file.",
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
        help="Source type (default: manual).",
    )
    parser.add_argument(
        "--author", metavar="TEXT", default="unknown",
    )
    parser.add_argument(
        "--enable-cloud", action="store_true", default=False,
        help="Enable cloud providers for this invocation.",
    )
    parser.add_argument(
        "--json", dest="output_json", action="store_true",
        help="Output comparison as JSON.",
    )
    parser.add_argument(
        "--artifacts-dir", metavar="PATH", default=None,
        help="If set, persist eval artifacts for both runs.",
    )

    if not argv:
        parser.print_help(sys.stderr)
        return 1

    args = parser.parse_args(argv)

    # Apply cloud guard before guard checks
    _apply_cloud_guard(args.enable_cloud)

    # Validate both providers — unimplemented and cloud guard checks
    for slot, pname in (("--provider-a", args.provider_a), ("--provider-b", args.provider_b)):
        rc = _check_provider_guard(pname)
        if rc is not None:
            print(f"  (failed on {slot}={pname!r})", file=sys.stderr)
            return rc

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

    try:
        from packages.research.evaluation.types import EvalDocument
        from packages.research.evaluation.evaluator import evaluate_document
        import hashlib

        doc_id = "cli_cmp_" + hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]
        doc = EvalDocument(
            doc_id=doc_id,
            title=title,
            author=args.author,
            source_type=args.source_type,
            source_url="",
            source_publish_date=None,
            body=body,
        )

        artifacts_dir = Path(args.artifacts_dir) if args.artifacts_dir else None

        print(f"Running provider-a ({args.provider_a})...", file=sys.stderr)
        decision_a = evaluate_document(
            doc,
            provider_name=args.provider_a,
            artifacts_dir=artifacts_dir,
        )
        print(f"Running provider-b ({args.provider_b})...", file=sys.stderr)
        decision_b = evaluate_document(
            doc,
            provider_name=args.provider_b,
            artifacts_dir=artifacts_dir,
        )
    except PermissionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: comparison failed: {exc}", file=sys.stderr)
        return 2

    # Build comparison result
    def _scores_dict(d):
        if not d.scores:
            return None
        s = d.scores
        return {
            "relevance": s.relevance,
            "novelty": s.novelty,
            "actionability": s.actionability,
            "credibility": s.credibility,
            "total": s.total,
            "composite_score": s.composite_score,
            "eval_model": s.eval_model,
            "reject_reason": s.reject_reason,
        }

    gate_changed = decision_a.gate != decision_b.gate
    scores_a = _scores_dict(decision_a)
    scores_b = _scores_dict(decision_b)

    dim_diffs: dict = {}
    if scores_a and scores_b:
        for dim in ("relevance", "novelty", "actionability", "credibility", "total"):
            va, vb = scores_a.get(dim), scores_b.get(dim)
            if va != vb:
                dim_diffs[dim] = {"provider_a": va, "provider_b": vb}

    if args.output_json:
        output = {
            "provider_a": args.provider_a,
            "provider_b": args.provider_b,
            "gate_a": decision_a.gate,
            "gate_b": decision_b.gate,
            "gate_changed": gate_changed,
            "scores_a": scores_a,
            "scores_b": scores_b,
            "dim_diffs": dim_diffs,
        }
        print(json.dumps(output, indent=2))
    else:
        sa = decision_a.scores
        sb = decision_b.scores

        def _fmt(label, pname, d, s):
            if s:
                return (
                    f"  {label} ({pname}): Gate={d.gate} | Total={s.total}/20 | "
                    f"R:{s.relevance} N:{s.novelty} A:{s.actionability} C:{s.credibility} | "
                    f"Model={s.eval_model}"
                )
            return f"  {label} ({pname}): Gate={d.gate}"

        print(_fmt("A", args.provider_a, decision_a, sa))
        print(_fmt("B", args.provider_b, decision_b, sb))
        print(f"  Gate changed: {'yes' if gate_changed else 'no'}")
        if dim_diffs:
            print("  Score diffs:")
            for dim, vals in dim_diffs.items():
                print(f"    {dim}: {vals['provider_a']} (A) vs {vals['provider_b']} (B)")
        else:
            print("  Score diffs: (none)")

    return 0
