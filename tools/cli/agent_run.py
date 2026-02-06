#!/usr/bin/env python3
"""Write a one-file-per-run agent log to kb/devlog/."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional


_SLUG_RE = re.compile(r"[^a-z0-9_-]")
_MULTI_UNDERSCORE_RE = re.compile(r"_+")


def _utcnow() -> datetime:
    return datetime.utcnow()


def _format_utc(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat() + "Z"


def _normalize_component(value: str, label: str) -> str:
    if value is None:
        raise ValueError(f"{label} is required.")

    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{label} is required.")
    if cleaned in (".", ".."):
        raise ValueError(f"{label} must not be '.' or '..'.")
    for sep in ("/", "\\", os.sep, os.altsep):
        if sep and sep in cleaned:
            raise ValueError(f"{label} must not contain path separators.")

    cleaned = cleaned.lower()
    cleaned = _SLUG_RE.sub("_", cleaned)
    cleaned = _MULTI_UNDERSCORE_RE.sub("_", cleaned)
    cleaned = cleaned.strip("_-")
    if not cleaned:
        raise ValueError(f"{label} must contain at least one valid character.")
    return cleaned


def _parse_agent(value: str) -> str:
    cleaned = value.strip().lower() if value else ""
    if cleaned not in {"codex", "claude"}:
        raise ValueError("Error: --agent must be one of: codex, claude.")
    return cleaned


def _parse_scope(value: str) -> str:
    cleaned = value.strip().lower() if value else ""
    if cleaned not in {"docs", "code", "ops"}:
        raise ValueError("Error: --scope must be one of: docs, code, ops.")
    return cleaned


def _parse_spec(value: str) -> str:
    cleaned = value.strip().lower() if value else "none"
    if cleaned not in {"kb", "docs", "none"}:
        raise ValueError("Error: --spec must be one of: kb, docs, none.")
    return cleaned


def _read_prompt(path: Optional[str]) -> str:
    if path:
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {path}")
        return file_path.read_text(encoding="utf-8")
    return sys.stdin.read()


def _prompt_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


def _render_spec_template(
    prompt_text: str,
    include_prompt: bool,
    devlog_path: str,
) -> str:
    lines = [
        "# Spec",
        "",
        "## Summary",
        "TODO",
        "",
        "## Context",
        "TODO",
        "",
        "## Requirements",
        "TODO",
        "",
        "## Plan",
        "TODO",
        "",
        "## Open Questions",
        "TODO",
        "",
        "## Prompt",
    ]

    if include_prompt:
        lines.append(_render_prompt_block(prompt_text))
    else:
        lines.append(f"Prompt stored in devlog: {devlog_path}")

    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Write a one-file-per-run agent log to kb/devlog/.",
    )
    parser.add_argument("--agent", required=True, help="codex or claude")
    parser.add_argument("--packet", required=True, help="Packet identifier")
    parser.add_argument("--slug", required=True, help="Short run slug")
    parser.add_argument(
        "--scope",
        default="code",
        help="docs, code, or ops (default: code)",
    )
    parser.add_argument(
        "--prompt-file",
        help="Optional prompt file path (defaults to stdin if omitted)",
    )
    parser.add_argument(
        "--spec",
        default="none",
        help="Optional spec stub destination: kb, docs, none (default: none)",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        agent = _parse_agent(args.agent)
        scope = _parse_scope(args.scope)
        spec_mode = _parse_spec(args.spec)
        packet = _normalize_component(args.packet, "packet")
        slug = _normalize_component(args.slug, "slug")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        prompt_text = _read_prompt(args.prompt_file)
    except (FileNotFoundError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    now = _utcnow()
    date_label = now.strftime("%Y-%m-%d")
    run_id = str(uuid.uuid4())
    prompt_hash = _prompt_sha256(prompt_text)

    devlog_dir = Path("kb") / "devlog"
    devlog_dir.mkdir(parents=True, exist_ok=True)
    devlog_path = devlog_dir / f"{date_label}_{agent}_{packet}_{slug}.md"

    spec_path = None
    if spec_mode in {"kb", "docs"}:
        spec_root = Path("kb") / "specs" if spec_mode == "kb" else Path("docs") / "specs"
        spec_root.mkdir(parents=True, exist_ok=True)
        spec_path = spec_root / f"{date_label}_{packet}_{slug}.md"

        spec_body = _render_spec_template(
            prompt_text=prompt_text,
            include_prompt=spec_mode == "kb",
            devlog_path=devlog_path.as_posix(),
        )
        spec_path.write_text(spec_body, encoding="utf-8")

    frontmatter_lines = [
        "---",
        f"date_utc: {_format_utc(now)}",
        f"agent: {agent}",
        f"packet: {packet}",
        f"scope: {scope}",
        f"run_id: {run_id}",
        f"prompt_sha256: {prompt_hash}",
    ]
    if spec_path is not None:
        frontmatter_lines.append(f"spec_path: {spec_path.as_posix()}")
    frontmatter_lines.extend([
        "notes: []",
        "next_steps: []",
        "---",
        "",
        "# Agent Run Log",
        "",
        "## Summary",
        "TODO",
        "",
        "## Prompt",
        _render_prompt_block(prompt_text),
        "",
        "## Files Changed",
        "TODO",
        "",
        "## Commands Run",
        "TODO",
        "",
        "## Notes",
        "TODO",
        "",
        "## Next Steps",
        "TODO",
        "",
    ])

    devlog_path.write_text("\n".join(frontmatter_lines), encoding="utf-8")

    print("Agent run log written")
    print(f"Devlog: {devlog_path}")
    if spec_path is not None:
        print(f"Spec: {spec_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
