"""Tests for polytool.reports.manifest — Run Manifest."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from polytool.reports.manifest import (
    build_run_manifest,
    stable_config_hash,
    write_run_manifest,
)


class TestStableConfigHash:
    def test_deterministic(self):
        config = {"window_days": 30, "max_trades": 200, "artifacts_dir": "artifacts"}
        h1 = stable_config_hash(config)
        h2 = stable_config_hash(config)
        assert h1 == h2

    def test_key_order_independent(self):
        c1 = {"a": 1, "b": 2}
        c2 = {"b": 2, "a": 1}
        assert stable_config_hash(c1) == stable_config_hash(c2)

    def test_different_config_different_hash(self):
        c1 = {"window_days": 30}
        c2 = {"window_days": 60}
        assert stable_config_hash(c1) != stable_config_hash(c2)

    def test_secrets_redacted(self):
        with_secret = {"password": "hunter2", "window_days": 30}
        without_secret = {"password": "differentpass", "window_days": 30}
        # Both should hash the same since password is redacted
        assert stable_config_hash(with_secret) == stable_config_hash(without_secret)

    def test_nested_secrets_redacted(self):
        config = {"db": {"password": "secret123", "host": "localhost"}}
        h = stable_config_hash(config)
        # Should not raise and should produce a valid hex string
        assert len(h) == 64

    def test_api_key_redacted(self):
        c1 = {"api_key": "key1", "host": "localhost"}
        c2 = {"api_key": "key2", "host": "localhost"}
        assert stable_config_hash(c1) == stable_config_hash(c2)


class TestBuildRunManifest:
    def test_required_fields(self):
        manifest = build_run_manifest(
            run_id="run-001",
            started_at="2026-02-06T12:00:00+00:00",
            command_name="examine",
            argv=["--user", "@TestUser", "--days", "30"],
            user_input="@TestUser",
            user_slug="testuser",
            wallets=["0xabc123"],
            output_paths={"run_root": "/tmp/test"},
        )
        required = [
            "manifest_version", "run_id", "started_at", "finished_at",
            "duration_seconds", "command_name", "argv", "user_input",
            "user_slug", "wallets", "output_paths",
            "effective_config_hash_sha256", "polytool_version",
        ]
        for field in required:
            assert field in manifest, f"Missing required field: {field}"

    def test_version_matches_package(self):
        import polytool
        manifest = build_run_manifest(
            run_id="run-002",
            started_at="2026-02-06T12:00:00+00:00",
            command_name="examine",
            argv=[],
            user_input="@Test",
            user_slug="test",
            wallets=[],
            output_paths={},
        )
        assert manifest["polytool_version"] == polytool.__version__

    def test_duration_computed(self):
        manifest = build_run_manifest(
            run_id="run-003",
            started_at="2026-02-06T12:00:00+00:00",
            command_name="examine",
            argv=[],
            user_input="@Test",
            user_slug="test",
            wallets=[],
            output_paths={},
            finished_at="2026-02-06T12:05:30+00:00",
        )
        assert manifest["duration_seconds"] == 330.0

    def test_config_hash_present_when_config_given(self):
        manifest = build_run_manifest(
            run_id="run-004",
            started_at="2026-02-06T12:00:00+00:00",
            command_name="examine",
            argv=[],
            user_input="@Test",
            user_slug="test",
            wallets=[],
            output_paths={},
            effective_config={"window_days": 30},
        )
        assert len(manifest["effective_config_hash_sha256"]) == 64

    def test_config_hash_empty_when_no_config(self):
        manifest = build_run_manifest(
            run_id="run-005",
            started_at="2026-02-06T12:00:00+00:00",
            command_name="examine",
            argv=[],
            user_input="@Test",
            user_slug="test",
            wallets=[],
            output_paths={},
        )
        assert manifest["effective_config_hash_sha256"] == ""

    def test_stable_hash_behavior(self):
        """Same config should produce same hash across builds."""
        config = {"window_days": 30, "max_trades": 200}
        m1 = build_run_manifest(
            run_id="run-a", started_at="2026-02-06T12:00:00+00:00",
            command_name="examine", argv=[], user_input="@Test",
            user_slug="test", wallets=[], output_paths={},
            effective_config=config,
        )
        m2 = build_run_manifest(
            run_id="run-b", started_at="2026-02-06T13:00:00+00:00",
            command_name="examine", argv=[], user_input="@Test",
            user_slug="test", wallets=[], output_paths={},
            effective_config=config,
        )
        assert m1["effective_config_hash_sha256"] == m2["effective_config_hash_sha256"]

    def test_no_network_required(self):
        """Building a manifest must not require network/services."""
        manifest = build_run_manifest(
            run_id="offline-run",
            started_at="2026-02-06T12:00:00+00:00",
            command_name="examine",
            argv=["--user", "@OfflineUser"],
            user_input="@OfflineUser",
            user_slug="offlineuser",
            wallets=["0xoffline"],
            output_paths={"run_root": "/tmp/offline"},
        )
        assert manifest["manifest_version"] == "1.0.0"


class TestWriteRunManifest:
    def test_writes_json(self, tmp_path):
        manifest = build_run_manifest(
            run_id="write-test",
            started_at="2026-02-06T12:00:00+00:00",
            command_name="examine",
            argv=[],
            user_input="@Test",
            user_slug="test",
            wallets=[],
            output_paths={},
        )
        path = write_run_manifest(manifest, tmp_path)
        assert Path(path).exists()

        data = json.loads(Path(path).read_text(encoding="utf-8"))
        assert data["run_id"] == "write-test"
        assert data["command_name"] == "examine"
