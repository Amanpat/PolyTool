#!/usr/bin/env python3
"""Save an LLM report run into the private KB."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from polytool.user_context import UserContext, resolve_user_context

logger = logging.getLogger(__name__)

_MODEL_SLUG_RE = re.compile(r"[^a-z0-9_-]")
_MULTI_UNDERSCORE_RE = re.compile(r"_+")


def _utcnow() -> datetime:
    return datetime.utcnow()


def _short_uuid() -> str:
    return uuid.uuid4().hex[:8]


def _model_to_slug(model: str) -> str:
    cleaned = model.strip().lower()
    cleaned = _MODEL_SLUG_RE.sub("_", cleaned)
    cleaned = _MULTI_UNDERSCORE_RE.sub("_", cleaned)
    cleaned = cleaned.strip("_-")
    return cleaned or "model"


def _format_utc(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat() + "Z"


def _parse_date(raw: Optional[str], now: datetime) -> str:
    if raw:
        try:
            parsed = datetime.strptime(raw, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("Invalid --date. Expected YYYY-MM-DD.") from exc
        return parsed.strftime("%Y-%m-%d")
    return now.strftime("%Y-%m-%d")


def _parse_tags(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    return [tag.strip() for tag in raw.split(",") if tag.strip()]


def _resolve_run_id(raw: Optional[str]) -> str:
    if raw is None:
        return _short_uuid()
    cleaned = raw.strip()
    if not cleaned:
        raise ValueError("Error: --run-id cannot be empty.")
    if cleaned in (".", ".."):
        raise ValueError("Error: --run-id must not be '.' or '..'.")
    for sep in ("/", "\\", os.sep, os.altsep):
        if sep and sep in cleaned:
            raise ValueError("Error: --run-id must not contain path separators.")
    return cleaned


def _read_text(path: Optional[str], label: str) -> str:
    if path:
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"{label} path not found: {path}")
        return file_path.read_text(encoding="utf-8")
    return sys.stdin.read()


def _ensure_within_root(root: Path, target: Path) -> None:
    root_path = root.resolve()
    target_path = target.resolve()
    if os.path.commonpath([str(root_path), str(target_path)]) != str(root_path):
        raise ValueError("Output directory must live under kb/.")


def _resolve_repo_relative(path: Path) -> str:
    try:
        rel = path.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        return path.resolve().as_posix()
    return rel.as_posix()


def _max_backticks(text: str) -> int:
    matches = re.findall(r"`+", text)
    if not matches:
        return 0
    return max(len(match) for match in matches)


def _fence_for(text: str) -> str:
    return "`" * max(3, _max_backticks(text) + 1)


def _render_prompt_block(text: str) -> str:
    fence = _fence_for(text)
    prompt_body = text
    if not prompt_body.endswith("\n"):
        prompt_body += "\n"
    return f"{fence}text\n{prompt_body}{fence}"


def _write_llm_note(
    *,
    date_label: str,
    now: datetime,
    user_ctx: UserContext,
    model_slug: str,
    run_id: str,
    report_path: Path,
    summary_bullets: Optional[List[str]] = None,
) -> Path:
    """Write a user-facing note entry to kb/users/<slug>/notes/LLM_notes/."""
    user_slug = user_ctx.slug
    notes_dir = user_ctx.llm_notes_dir
    notes_dir.mkdir(parents=True, exist_ok=True)

    note_path = notes_dir / f"{date_label}_{model_slug}_{run_id}.md"

    bullets = summary_bullets or ["See full report for details."]
    bullets_text = "\n".join(f"- {b}" for b in bullets)

    lines: List[str] = [
        "---",
        f"date_utc: {_format_utc(now)}",
        f"user_slug: {user_slug}",
        f"model_slug: {model_slug}",
        f"run_id: {run_id}",
        "type: llm_note",
        "---",
        "",
        "# LLM Analysis Note",
        "",
        "## Summary",
        bullets_text,
        "",
        "## Links",
        f"- Full report: {_resolve_repo_relative(report_path)}",
        f"- Full hypothesis: {_resolve_repo_relative(report_path.parent / 'hypothesis.json')} (if generated)",
        "",
        "## Metadata",
        f"- User: {user_slug}",
        f"- Model: {model_slug}",
        f"- Run ID: {run_id}",
        f"- Created: {_format_utc(now)}",
        "",
    ]

    note_path.write_text("\n".join(lines), encoding="utf-8")
    return note_path


def _write_devlog(
    *,
    date_label: str,
    now: datetime,
    user_slug: str,
    model_slug: str,
    run_id: str,
    report_path: Path,
    input_paths: List[str],
    prompt_source: str,
    prompt_text: str,
) -> Path:
    devlog_dir = Path("kb") / "devlog"
    devlog_dir.mkdir(parents=True, exist_ok=True)
    devlog_path = devlog_dir / f"{date_label}_llm_save_{user_slug}_{model_slug}_{run_id}.md"

    input_lines = input_paths or []

    lines: List[str] = [
        "---",
        f"date_utc: {_format_utc(now)}",
        "run_type: llm_save",
        f"user_slug: {user_slug}",
        f"model_slug: {model_slug}",
        f"run_id: {run_id}",
        f"prompt_source: {prompt_source}",
        "---",
        "",
        "# LLM Save Run",
        "",
        "## Summary",
        "TODO",
        "",
        "## Details",
        f"Report path: {_resolve_repo_relative(report_path)}",
        f"Inputs count: {len(input_lines)}",
        f"Prompt source: {prompt_source}",
    ]

    lines.extend([
        "",
        "Inputs:",
        "```text",
        *(input_lines or ["(none)"]),
        "```",
    ])

    lines.extend([
        "",
        "## Prompt",
        _render_prompt_block(prompt_text),
        "",
        "## Notes",
        "TODO",
        "",
        "## Next Steps",
        "TODO",
        "",
    ])

    devlog_path.write_text("\n".join(lines), encoding="utf-8")
    return devlog_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Save an LLM report run into the private KB.",
    )
    parser.add_argument("--user", required=True, help="User handle (with or without @).")
    parser.add_argument("--model", required=True, help="Model name or identifier.")
    parser.add_argument("--run-id", help="Run identifier (default: short uuid).")
    parser.add_argument("--date", help="Override date label (YYYY-MM-DD).")
    parser.add_argument(
        "--report-path",
        help="Path to report markdown (defaults to stdin if omitted).",
    )
    parser.add_argument(
        "--prompt-path",
        help="Path to prompt text (defaults to stdin if omitted).",
    )
    parser.add_argument(
        "--input",
        action="append",
        default=[],
        help="Input file path supplied to the LLM (repeatable).",
    )
    parser.add_argument("--rag-query-path", help="Optional rag-query JSON output path.")
    parser.add_argument("--tags", help="Optional comma-separated tags.")
    parser.add_argument(
        "--no-devlog",
        action="store_true",
        help="Skip writing a devlog entry for this run.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    user_raw = args.user.strip() if args.user else ""
    if not user_raw or user_raw == "@":
        print("Error: --user must be a non-empty handle.", file=sys.stderr)
        return 1

    model_raw = args.model.strip() if args.model else ""
    if not model_raw:
        print("Error: --model must be provided.", file=sys.stderr)
        return 1

    if not args.report_path and not args.prompt_path:
        print(
            "Error: provide at least one of --report-path or --prompt-path; "
            "the other can be read from stdin.",
            file=sys.stderr,
        )
        return 1

    try:
        run_id = _resolve_run_id(args.run_id)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    # Use canonical identity resolver for consistent slug derivation
    original_handle = user_raw if user_raw.startswith("@") else f"@{user_raw}"
    user_ctx = resolve_user_context(
        handle=original_handle,
        wallet=None,  # llm-save only uses handle
        kb_root=Path("kb"),
        artifacts_root=Path("artifacts"),
        persist_mapping=False,  # Don't persist without wallet
    )
    user_slug = user_ctx.slug

    logger.debug(
        "Resolved UserContext: slug=%s handle=%s",
        user_slug,
        user_ctx.handle,
    )

    model_slug = _model_to_slug(model_raw)

    now = _utcnow()
    try:
        date_label = _parse_date(args.date, now)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    output_dir = user_ctx.llm_reports_dir / date_label / f"{model_slug}_{run_id}"

    try:
        _ensure_within_root(Path("kb"), output_dir)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    try:
        report_text = _read_text(args.report_path, "Report")
        prompt_text = _read_text(args.prompt_path, "Prompt")
    except (FileNotFoundError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    report_path = output_dir / "report.md"
    manifest_path = output_dir / "inputs_manifest.json"

    report_path.write_text(report_text, encoding="utf-8")

    manifest = {
        "model": model_raw,
        "model_slug": model_slug,
        "run_id": run_id,
        "created_at_utc": _format_utc(now),
        "user_slug": user_slug,
        "input_paths": list(args.input or []),
    }

    tags = _parse_tags(args.tags)
    if tags:
        manifest["tags"] = tags

    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    rag_query_dest = None
    if args.rag_query_path:
        rag_query_dest = output_dir / "rag_query.json"
        try:
            rag_query_text = _read_text(args.rag_query_path, "RAG query")
        except (FileNotFoundError, OSError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        rag_query_dest.write_text(rag_query_text, encoding="utf-8")

    # Write LLM note entry for RAG surfacing
    note_path = _write_llm_note(
        date_label=date_label,
        now=now,
        user_ctx=user_ctx,
        model_slug=model_slug,
        run_id=run_id,
        report_path=report_path,
        summary_bullets=None,  # Could extract from report in future
    )

    print("LLM report saved")
    print(f"Output dir: {output_dir}")
    print(f"Report: {report_path}")
    print(f"Manifest: {manifest_path}")
    print(f"LLM note: {note_path}")
    if rag_query_dest:
        print(f"RAG query: {rag_query_dest}")
    if not args.no_devlog:
        prompt_source = (
            _resolve_repo_relative(Path(args.prompt_path))
            if args.prompt_path
            else "stdin"
        )
        devlog_path = _write_devlog(
            date_label=date_label,
            now=now,
            user_slug=user_slug,
            model_slug=model_slug,
            run_id=run_id,
            report_path=report_path,
            input_paths=list(args.input or []),
            prompt_source=prompt_source,
            prompt_text=prompt_text,
        )
        print(f"Devlog: {devlog_path}")
    print('Suggested next: polytool rag-index --roots "kb,artifacts" --rebuild')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
