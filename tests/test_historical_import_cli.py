"""Integration tests for tools/cli/historical_import.py (CLI smoke tests)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from packages.polymarket.historical_import.importer import ImportResult
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


class TestImportCLI:
    """CLI tests for the 'import' subcommand (Packet 2)."""

    def test_import_dry_run_pmxt_exits_0(self, tmp_path):
        _make_file(tmp_path / "Polymarket" / "snap.parquet", "")
        rc = main([
            "import", "--source-kind", "pmxt_archive",
            "--local-path", str(tmp_path),
            "--import-mode", "dry-run",
        ])
        assert rc == 0

    def test_import_dry_run_invalid_path_exits_1(self, tmp_path):
        missing = str(tmp_path / "does_not_exist")
        rc = main([
            "import", "--source-kind", "pmxt_archive",
            "--local-path", missing,
            "--import-mode", "dry-run",
        ])
        assert rc == 1

    def test_import_dry_run_writes_run_record(self, tmp_path, capsys):
        _make_file(tmp_path / "Polymarket" / "snap.parquet", "")
        out_file = tmp_path / "run_record.json"
        rc = main([
            "import", "--source-kind", "pmxt_archive",
            "--local-path", str(tmp_path),
            "--import-mode", "dry-run",
            "--out", str(out_file),
        ])
        assert rc == 0
        assert out_file.exists()
        payload = json.loads(out_file.read_text(encoding="utf-8"))
        assert payload["schema_version"] == "import_run_v0"

    def test_import_dry_run_stdout_shows_summary(self, tmp_path, capsys):
        _make_file(tmp_path / "Polymarket" / "snap.parquet", "")
        rc = main([
            "import", "--source-kind", "pmxt_archive",
            "--local-path", str(tmp_path),
            "--import-mode", "dry-run",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        assert "dry-run" in captured.out

    def test_import_help_exits_0(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["import", "--help"])
        assert exc_info.value.code == 0

    def test_import_dry_run_price_history_exits_0(self, tmp_path):
        _make_file(tmp_path / "token_abc.jsonl", '{"t": 1700000000, "p": 0.73}\n')
        rc = main([
            "import", "--source-kind", "price_history_2min",
            "--local-path", str(tmp_path),
            "--import-mode", "dry-run",
        ])
        assert rc == 0

    def test_import_dry_run_jon_becker_exits_0(self, tmp_path):
        # Build a minimal valid JB layout
        import csv
        trades_dir = tmp_path / "data" / "polymarket" / "trades"
        trades_dir.mkdir(parents=True, exist_ok=True)
        csv_path = trades_dir / "trades.csv"
        with open(str(csv_path), "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=["timestamp", "market_id", "token_id",
                                                     "price", "size", "taker_side",
                                                     "resolution", "category"])
            writer.writeheader()
            writer.writerow({"timestamp": "1700000000", "market_id": "m1", "token_id": "t1",
                             "price": "0.5", "size": "100", "taker_side": "buy",
                             "resolution": "", "category": "sports"})
        rc = main([
            "import", "--source-kind", "jon_becker",
            "--local-path", str(tmp_path),
            "--import-mode", "dry-run",
        ])
        assert rc == 0

    def test_import_dry_run_provenance_hash_in_run_record(self, tmp_path):
        _make_file(tmp_path / "Polymarket" / "snap.parquet", "")
        out_file = tmp_path / "rec.json"
        main([
            "import", "--source-kind", "pmxt_archive",
            "--local-path", str(tmp_path),
            "--import-mode", "dry-run",
            "--snapshot-version", "2026-03",
            "--out", str(out_file),
        ])
        payload = json.loads(out_file.read_text(encoding="utf-8"))
        assert payload.get("provenance_hash", "").startswith("import_manifest_")

    def test_import_sample_reads_clickhouse_credentials_from_dotenv(self, tmp_path, monkeypatch):
        _make_file(tmp_path / "Polymarket" / "snap.parquet", "")
        _make_file(
            tmp_path / ".env",
            "\n".join(
                [
                    "CLICKHOUSE_USER=env_user",
                    "CLICKHOUSE_PASSWORD=env_pass",
                    "CLICKHOUSE_HTTP_PORT=18123",
                ]
            ),
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("CLICKHOUSE_USER", raising=False)
        monkeypatch.delenv("CLICKHOUSE_PASSWORD", raising=False)
        monkeypatch.delenv("CLICKHOUSE_PORT", raising=False)
        monkeypatch.delenv("CLICKHOUSE_HTTP_PORT", raising=False)

        result = ImportResult(
            source_kind="pmxt_archive",
            import_mode="sample",
            run_id="run-123",
            resolved_source_path=str(tmp_path),
            destination_tables=["polytool.pmxt_l2_snapshots"],
            import_completeness="complete",
            files_processed=1,
            rows_attempted=1,
        )

        with patch("packages.polymarket.historical_import.importer.ClickHouseClient") as mock_client, \
             patch("packages.polymarket.historical_import.importer.run_import", return_value=result):
            rc = main([
                "import", "--source-kind", "pmxt_archive",
                "--local-path", str(tmp_path),
                "--import-mode", "sample",
            ])

        assert rc == 0
        mock_client.assert_called_once_with(
            host="localhost",
            port=18123,
            user="env_user",
            password="env_pass",
        )

    def test_import_sample_requires_clickhouse_password(self, tmp_path, monkeypatch, capsys):
        _make_file(tmp_path / "Polymarket" / "snap.parquet", "")
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("CLICKHOUSE_PASSWORD", raising=False)

        rc = main([
            "import", "--source-kind", "pmxt_archive",
            "--local-path", str(tmp_path),
            "--import-mode", "sample",
        ])

        assert rc == 1
        captured = capsys.readouterr()
        assert "CLICKHOUSE_PASSWORD is required" in captured.err
