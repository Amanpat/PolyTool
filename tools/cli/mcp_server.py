#!/usr/bin/env python3
"""MCP server for Claude Desktop integration.

Uses the official MCP Python SDK (FastMCP) for protocol-compliant
stdio transport.  ALL diagnostic output goes to stderr — stdout
carries only valid MCP JSON-RPC messages.

Usage:
    polytool mcp
    polytool mcp --log-level DEBUG

The server runs locally and must NOT upload data anywhere.

Tools exposed:
- polymarket_export_dossier: Export a user dossier
- polymarket_llm_bundle: Build an LLM evidence bundle
- polymarket_rag_query: Query the local RAG index
- polymarket_save_hypothesis: Save hypothesis outputs to KB
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---- stderr-only logging, configured before any other import --------
logging.basicConfig(
    stream=sys.stderr,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.WARNING,
)
logger = logging.getLogger("polytool.mcp")

# Ensure project root is on sys.path for local (non-installed) usage
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from mcp.server.fastmcp import FastMCP  # noqa: E402

from polytool.user_context import resolve_user_context  # noqa: E402

# ---- MCP server instance -------------------------------------------
mcp_app = FastMCP("polytool-mcp")


# ---- helpers --------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.utcnow()


def _format_utc(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat() + "Z"


@contextlib.contextmanager
def _suppress_stdout():
    """Capture any stdout emitted by underlying CLI functions.

    The MCP stdio transport uses stdout for JSON-RPC framing.  Any
    human-readable ``print()`` or rich/typer output that leaks onto
    stdout corrupts the protocol stream and causes "Unexpected token"
    parse errors in Claude Desktop.

    This context manager redirects stdout to a ``StringIO`` buffer for
    the duration of the block.  Captured text (if any) is logged to
    stderr so it remains visible for debugging.
    """
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        yield buf
    captured = buf.getvalue()
    if captured.strip():
        truncated = captured[:500]
        logger.warning("Suppressed stdout during MCP tool call: %s", truncated)


# ---- Tool definitions -----------------------------------------------

@mcp_app.tool()
def polymarket_export_dossier(user: str, days: int = 30) -> str:
    """Export a user dossier with trades, positions, and analytics.

    Args:
        user: Polymarket username (@name) or wallet address
        days: Lookback window in days (default 30)
    """
    if not user:
        raise ValueError("user is required")

    from tools.cli.export_dossier import main as export_main

    argv = ["--days", str(days)]
    if user.strip().lower().startswith("0x"):
        argv = ["--wallet", user, *argv]
    else:
        argv = ["--user", user, *argv]

    with _suppress_stdout():
        result = export_main(argv)
    if result == 0:
        return json.dumps({
            "success": True,
            "message": f"Dossier exported for {user}",
            "user": user,
            "days": days,
        })
    raise RuntimeError("Dossier export failed")


@mcp_app.tool()
def polymarket_llm_bundle(user: str) -> str:
    """Build an LLM evidence bundle from the latest dossier.

    Args:
        user: Polymarket username (@name)
    """
    if not user:
        raise ValueError("user is required")

    from tools.cli.llm_bundle import main as bundle_main

    with _suppress_stdout():
        result = bundle_main(["--user", user])
    if result == 0:
        return json.dumps({
            "success": True,
            "message": f"LLM bundle created for {user}",
            "user": user,
        })
    raise RuntimeError("Bundle creation failed")


@mcp_app.tool()
def polymarket_rag_query(question: str, user: str = "", k: int = 8) -> str:
    """Query the local RAG index for evidence.

    Args:
        question: The query to search for
        user: Optional user slug to scope results
        k: Number of results to return (default 8)
    """
    if not question:
        raise ValueError("question is required")

    from polymarket.rag.embedder import (
        DEFAULT_EMBED_MODEL,
        SentenceTransformerEmbedder,
    )
    from polymarket.rag.query import query_index

    with _suppress_stdout():
        embedder = SentenceTransformerEmbedder(model_name=DEFAULT_EMBED_MODEL)
        results = query_index(
            question=question,
            embedder=embedder,
            k=k,
            user_slug=user or None,
            private_only=True,
        )
    return json.dumps({
        "success": True,
        "question": question,
        "results": results,
        "count": len(results),
    })


@mcp_app.tool()
def polymarket_save_hypothesis(
    user: str,
    model: str,
    hypothesis_md: str,
    hypothesis_json: str = "",
) -> str:
    """Save hypothesis outputs to the KB (report + LLM_notes).

    Args:
        user: User slug
        model: Model name/identifier
        hypothesis_md: Hypothesis markdown content
        hypothesis_json: Optional hypothesis JSON content
    """
    if not user or not model or not hypothesis_md:
        raise ValueError("user, model, and hypothesis_md are required")

    import uuid

    with _suppress_stdout():
        original_handle = user.strip()
        if original_handle and not original_handle.startswith("@"):
            original_handle = f"@{original_handle}"

        user_ctx = resolve_user_context(
            handle=original_handle,
            wallet=None,
            kb_root=Path("kb"),
            artifacts_root=Path("artifacts"),
            persist_mapping=False,
        )
        user_slug = user_ctx.slug
        now = _utcnow()
        date_label = now.strftime("%Y-%m-%d")
        run_id = uuid.uuid4().hex[:8]
        model_slug = model.lower().replace(" ", "-").replace("/", "-")[:20]

        report_dir = (
            user_ctx.llm_reports_dir / date_label / f"{model_slug}_{run_id}"
        )
        notes_dir = user_ctx.llm_notes_dir

        report_dir.mkdir(parents=True, exist_ok=True)
        notes_dir.mkdir(parents=True, exist_ok=True)

        # Write hypothesis.md
        report_path = report_dir / "hypothesis.md"
        report_path.write_text(hypothesis_md, encoding="utf-8")

        # Write hypothesis.json if provided
        if hypothesis_json:
            json_path = report_dir / "hypothesis.json"
            json_path.write_text(hypothesis_json, encoding="utf-8")

        # Write manifest
        manifest = {
            "user_slug": user_slug,
            "model": model,
            "model_slug": model_slug,
            "run_id": run_id,
            "created_at_utc": _format_utc(now),
            "has_json": bool(hypothesis_json),
        }
        manifest_path = report_dir / "inputs_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        # Write LLM note
        note_path = notes_dir / f"{date_label}_{model_slug}_{run_id}.md"
        note_content = f"""---
date_utc: {_format_utc(now)}
user_slug: {user_slug}
model_slug: {model_slug}
run_id: {run_id}
type: llm_note
---

# LLM Analysis Note

## Summary
- Hypothesis generated by {model}
- See full report for details

## Links
- Full report: {report_path.as_posix()}
- JSON output: {(report_dir / 'hypothesis.json').as_posix() if hypothesis_json else 'N/A'}

## Metadata
- User: {user_slug}
- Model: {model}
- Run ID: {run_id}
- Created: {_format_utc(now)}
"""
        note_path.write_text(note_content, encoding="utf-8")

    return json.dumps({
        "success": True,
        "message": "Hypothesis saved",
        "report_path": str(report_path),
        "note_path": str(note_path),
        "run_id": run_id,
    })


# ---- CLI entry point ------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Start PolyTool MCP server for Claude Desktop integration.",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level (default: WARNING). All logs go to stderr.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Apply requested log level (all output stays on stderr)
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    logger.info("Starting PolyTool MCP server")

    mcp_app.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
