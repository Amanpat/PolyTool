"""Tests for the PolyTool MCP server.

Validates that the server speaks correct MCP JSON-RPC over stdio
and never pollutes stdout with non-protocol output.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import subprocess
import time
from pathlib import Path
from unittest import mock

import pytest

# The mcp SDK is an optional dependency — skip gracefully if absent.
mcp_mod = pytest.importorskip("mcp")


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_mcp_initialize_and_list_tools():
    """Spawn the MCP server, send initialize, assert valid JSON-RPC
    response with non-null id and jsonrpc='2.0', then list tools."""
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters

    async def _run() -> None:
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "polytool", "mcp"],
            env={**os.environ, "PYTHONPATH": _project_root()},
        )

        async with stdio_client(server_params) as streams:
            read_stream, write_stream = streams
            async with ClientSession(read_stream, write_stream) as session:
                # initialize — the SDK validates the JSON-RPC envelope
                # (jsonrpc="2.0", non-null id) for us; a malformed
                # response would raise.
                init_result = await session.initialize()
                assert init_result.protocolVersion is not None

                # list tools
                tools_result = await session.list_tools()
                names = {t.name for t in tools_result.tools}
                assert "polymarket_export_dossier" in names
                assert "polymarket_llm_bundle" in names
                assert "polymarket_rag_query" in names
                assert "polymarket_save_hypothesis" in names

    asyncio.run(_run())


def test_mcp_no_stdout_pollution():
    """The server must emit nothing on stdout until it receives a valid
    MCP request.  Any banner / warning on stdout breaks Claude Desktop."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "polytool", "mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "PYTHONPATH": _project_root()},
    )

    # Let the process start up
    time.sleep(1.5)

    # Shut it down without sending any MCP messages
    proc.stdin.close()
    proc.terminate()

    stdout_bytes = proc.stdout.read()
    proc.wait(timeout=10)

    assert stdout_bytes == b"", (
        f"Non-MCP output detected on stdout: {stdout_bytes!r}"
    )


# ---- Regression: stdout suppression during tool execution ------------


def test_suppress_stdout_captures_prints():
    """_suppress_stdout must capture print() calls and keep real stdout clean."""
    from tools.cli.mcp_server import _suppress_stdout

    real_stdout = sys.stdout
    sentinel = io.StringIO()
    sys.stdout = sentinel
    try:
        with _suppress_stdout() as buf:
            # This print targets whatever sys.stdout is, which
            # _suppress_stdout has replaced with buf.
            print("leaked line 1")
            print("leaked line 2")
        # After the context manager, captured text is in buf
        captured = buf.getvalue()
    finally:
        sys.stdout = real_stdout

    assert "leaked line 1" in captured
    assert "leaked line 2" in captured
    # Nothing should have reached the sentinel (our stand-in for real stdout)
    assert sentinel.getvalue() == ""


def test_export_dossier_no_stdout_leak():
    """polymarket_export_dossier must not leak stdout from export_main."""
    from tools.cli.mcp_server import polymarket_export_dossier

    def _noisy_export_main(argv):
        print("Export complete")
        print("Export id: abc123")
        print("Artifact dir: /tmp/test")
        return 0

    real_stdout = sys.stdout
    sentinel = io.StringIO()
    sys.stdout = sentinel
    try:
        with mock.patch(
            "tools.cli.export_dossier.main", side_effect=_noisy_export_main
        ):
            result = polymarket_export_dossier(user="@testuser", days=7)
    finally:
        sys.stdout = real_stdout

    # Tool should succeed
    payload = json.loads(result)
    assert payload["success"] is True

    # No CLI output should have reached real stdout
    leaked = sentinel.getvalue()
    assert leaked == "", f"stdout pollution detected: {leaked!r}"


def test_llm_bundle_no_stdout_leak():
    """polymarket_llm_bundle must not leak stdout from bundle_main."""
    from tools.cli.mcp_server import polymarket_llm_bundle

    def _noisy_bundle_main(argv):
        print("LLM bundle created")
        print("Output dir: /tmp/bundles/test")
        print("Bundle: /tmp/bundles/test/bundle.md")
        return 0

    real_stdout = sys.stdout
    sentinel = io.StringIO()
    sys.stdout = sentinel
    try:
        with mock.patch(
            "tools.cli.llm_bundle.main", side_effect=_noisy_bundle_main
        ):
            result = polymarket_llm_bundle(user="@testuser")
    finally:
        sys.stdout = real_stdout

    payload = json.loads(result)
    assert payload["success"] is True

    leaked = sentinel.getvalue()
    assert leaked == "", f"stdout pollution detected: {leaked!r}"


def test_save_hypothesis_no_stdout_leak(tmp_path):
    """polymarket_save_hypothesis must not leak stdout during file writes."""
    from tools.cli.mcp_server import polymarket_save_hypothesis

    kb_root = tmp_path / "kb"
    artifacts_root = tmp_path / "artifacts"

    real_stdout = sys.stdout
    sentinel = io.StringIO()
    sys.stdout = sentinel
    try:
        with mock.patch(
            "tools.cli.mcp_server.resolve_user_context"
        ) as mock_ctx:
            # Build a minimal UserContext-like object
            ctx = mock.MagicMock()
            ctx.slug = "testuser"
            ctx.llm_reports_dir = kb_root / "users" / "testuser" / "reports"
            ctx.llm_notes_dir = kb_root / "users" / "testuser" / "notes" / "LLM_notes"
            mock_ctx.return_value = ctx

            result = polymarket_save_hypothesis(
                user="testuser",
                model="test-model",
                hypothesis_md="# Test hypothesis\n\nSome content.",
            )
    finally:
        sys.stdout = real_stdout

    payload = json.loads(result)
    assert payload["success"] is True
    assert payload["run_id"]

    # Verify files were actually created
    assert Path(payload["report_path"]).exists()
    assert Path(payload["note_path"]).exists()

    leaked = sentinel.getvalue()
    assert leaked == "", f"stdout pollution detected: {leaked!r}"


def test_tool_call_via_mcp_protocol_no_parse_errors():
    """Call polymarket_save_hypothesis through the full MCP protocol.

    This proves the entire stdio stream stays valid JSON-RPC even when
    a tool handler executes real work (file I/O).  If any stdout
    pollution occurred, the MCP client SDK would raise a parse error.
    """
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters

    async def _run() -> None:
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "polytool", "mcp"],
            env={**os.environ, "PYTHONPATH": _project_root()},
        )

        async with stdio_client(server_params) as streams:
            read_stream, write_stream = streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Call save_hypothesis — the only tool that doesn't
                # need network access (it does pure file I/O).
                result = await session.call_tool(
                    "polymarket_save_hypothesis",
                    arguments={
                        "user": "mcp_test_user",
                        "model": "test-model",
                        "hypothesis_md": "# MCP Test\n\nThis is a protocol test.",
                    },
                )

                # The SDK parsed the response without error — that
                # alone proves no stdout pollution.  Verify content too.
                assert result.content
                text = result.content[0].text
                payload = json.loads(text)
                assert payload["success"] is True

    asyncio.run(_run())
