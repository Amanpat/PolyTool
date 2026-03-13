"""Integration tests for tools/cli/historical_import.py (CLI smoke tests)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.cli.historical_import import main


def _make_file(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestValidateLayoutCLI:
    def test_help_exits_0(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0

    def test_validate_layout_help(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["validate-layout", "--help"])
        assert exc_info.value.code == 0

    def test_no_subcommand_exits_0(self):
        rc = main([])
        assert rc == 0

    def test_missing_path_returns_1(self):
        rc = main(["validate-layout", "--source-kind", "pmxt_archive",
                   "--local-path", "/nonexistent/xyz_99999"])
        assert rc == 1

    def test_valid_pmxt_returns_0(self, tmp_path):
        _make_file(tmp_path / "Polymarket" / "snap.parquet", "")
        rc = main(["validate-layout", "--source-kind", "pmxt_archive",
                   "--local-path", str(tmp_path)])
        assert rc == 0

    def test_invalid_pmxt_returns_1(self, tmp_path):
        rc = main(["validate-layout", "--source-kind", "pmxt_archive",
                   "--local-path", str(tmp_path)])
        assert rc == 1

    def test_valid_jon_becker_returns_0(self, tmp_path):
        _make_file(tmp_path / "data" / "polymarket" / "trades" / "t.parquet", "")
        rc = main(["validate-layout", "--source-kind", "jon_becker",
                   "--local-path", str(tmp_path)])
        assert rc == 0

    def test_valid_price_history_returns_0(self, tmp_path):
        _make_file(tmp_path / "token_abc.jsonl", "")
        rc = main(["validate-layout", "--source-kind", "price_history_2min",
                   "--local-path", str(tmp_path)])
        assert rc == 0


class TestShowManifestCLI:
    def test_show_manifest_stdout(self, tmp_path, capsys):
        _make_file(tmp_path / "Polymarket" / "snap.parquet", "")
        rc = main(["show-manifest", "--source-kind", "pmxt_archive",
                   "--local-path", str(tmp_path)])
        assert rc == 0
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert payload["schema_version"] == "import_manifest_v0"
        assert len(payload["sources"]) == 1
        assert payload["sources"][0]["source_kind"] == "pmxt_archive"
        assert payload["sources"][0]["status"] == "validated"

    def test_show_manifest_writes_file(self, tmp_path):
        _make_file(tmp_path / "Polymarket" / "snap.parquet", "")
        out_file = tmp_path / "manifest.json"
        rc = main(["show-manifest", "--source-kind", "pmxt_archive",
                   "--local-path", str(tmp_path), "--out", str(out_file)])
        assert rc == 0
        assert out_file.exists()
        payload = json.loads(out_file.read_text())
        assert payload["schema_version"] == "import_manifest_v0"

    def test_show_manifest_invalid_layout_status_staged(self, tmp_path, capsys):
        # Empty dir -> layout invalid -> status should be 'staged'
        rc = main(["show-manifest", "--source-kind", "pmxt_archive",
                   "--local-path", str(tmp_path)])
        assert rc == 1
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert payload["sources"][0]["status"] == "staged"

    def test_show_manifest_with_notes(self, tmp_path, capsys):
        _make_file(tmp_path / "data" / "polymarket" / "trades" / "t.csv", "")
        rc = main(["show-manifest", "--source-kind", "jon_becker",
                   "--local-path", str(tmp_path), "--notes", "downloaded 2026-03"])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert "downloaded 2026-03" in payload["sources"][0]["notes"]

    def test_show_manifest_deterministic(self, tmp_path, capsys):
        _make_file(tmp_path / "Polymarket" / "snap.parquet", "")
        main(["show-manifest", "--source-kind", "pmxt_archive",
              "--local-path", str(tmp_path)])
        p1 = json.loads(capsys.readouterr().out)

        main(["show-manifest", "--source-kind", "pmxt_archive",
              "--local-path", str(tmp_path)])
        p2 = json.loads(capsys.readouterr().out)

        # manifest_id is deterministic
        assert p1["sources"][0]["manifest_id"] == p2["sources"][0]["manifest_id"]
