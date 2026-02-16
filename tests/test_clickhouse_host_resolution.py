"""Tests for ClickHouse connection config resolution.

Validates the host/port/database fallback chain without requiring a real
ClickHouse instance. We monkeypatch clickhouse_connect.get_client and
the docker-detection helper to capture resolved arguments.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Import the helpers from export_dossier (canonical implementation)
# ---------------------------------------------------------------------------
from tools.cli.export_dossier import (
    _get_clickhouse_client,
    _resolve_clickhouse_database,
    _resolve_clickhouse_host,
    _resolve_clickhouse_port,
    _running_in_docker,
)


# ---------------------------------------------------------------------------
# _running_in_docker
# ---------------------------------------------------------------------------

class TestRunningInDocker:
    def test_env_var_override(self, monkeypatch):
        monkeypatch.setenv("POLYTOOL_IN_DOCKER", "1")
        assert _running_in_docker() is True

    def test_dockerenv_file(self, monkeypatch, tmp_path):
        monkeypatch.delenv("POLYTOOL_IN_DOCKER", raising=False)
        with patch("tools.cli.export_dossier.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            assert _running_in_docker() is True

    def test_host_mode(self, monkeypatch):
        monkeypatch.delenv("POLYTOOL_IN_DOCKER", raising=False)
        with patch("tools.cli.export_dossier.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            assert _running_in_docker() is False


# ---------------------------------------------------------------------------
# Host resolution
# ---------------------------------------------------------------------------

class TestResolveClickhouseHost:
    def test_host_mode_defaults_to_localhost(self, monkeypatch):
        monkeypatch.delenv("CLICKHOUSE_HOST", raising=False)
        with patch("tools.cli.export_dossier._running_in_docker", return_value=False):
            assert _resolve_clickhouse_host() == "localhost"

    def test_docker_mode_defaults_to_clickhouse(self, monkeypatch):
        monkeypatch.delenv("CLICKHOUSE_HOST", raising=False)
        with patch("tools.cli.export_dossier._running_in_docker", return_value=True):
            assert _resolve_clickhouse_host() == "clickhouse"

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("CLICKHOUSE_HOST", "my-custom-host")
        assert _resolve_clickhouse_host() == "my-custom-host"


# ---------------------------------------------------------------------------
# Port resolution
# ---------------------------------------------------------------------------

class TestResolveClickhousePort:
    def test_default_port(self, monkeypatch):
        monkeypatch.delenv("CLICKHOUSE_PORT", raising=False)
        monkeypatch.delenv("CLICKHOUSE_HTTP_PORT", raising=False)
        assert _resolve_clickhouse_port() == 8123

    def test_clickhouse_port_takes_priority(self, monkeypatch):
        monkeypatch.setenv("CLICKHOUSE_PORT", "9999")
        monkeypatch.setenv("CLICKHOUSE_HTTP_PORT", "7777")
        assert _resolve_clickhouse_port() == 9999

    def test_http_port_fallback(self, monkeypatch):
        monkeypatch.delenv("CLICKHOUSE_PORT", raising=False)
        monkeypatch.setenv("CLICKHOUSE_HTTP_PORT", "7777")
        assert _resolve_clickhouse_port() == 7777


# ---------------------------------------------------------------------------
# Database resolution
# ---------------------------------------------------------------------------

class TestResolveClickhouseDatabase:
    def test_default_database(self, monkeypatch):
        monkeypatch.delenv("CLICKHOUSE_DATABASE", raising=False)
        monkeypatch.delenv("CLICKHOUSE_DB", raising=False)
        assert _resolve_clickhouse_database() == "polyttool"

    def test_clickhouse_database_takes_priority(self, monkeypatch):
        monkeypatch.setenv("CLICKHOUSE_DATABASE", "mydb")
        monkeypatch.setenv("CLICKHOUSE_DB", "otherdb")
        assert _resolve_clickhouse_database() == "mydb"

    def test_clickhouse_db_fallback(self, monkeypatch):
        monkeypatch.delenv("CLICKHOUSE_DATABASE", raising=False)
        monkeypatch.setenv("CLICKHOUSE_DB", "otherdb")
        assert _resolve_clickhouse_database() == "otherdb"


# ---------------------------------------------------------------------------
# Integration: _get_clickhouse_client captures correct args
# ---------------------------------------------------------------------------

class TestGetClickhouseClient:
    def test_host_mode_no_env(self, monkeypatch):
        """On Windows host with no env vars, should connect to localhost:8123."""
        monkeypatch.delenv("CLICKHOUSE_HOST", raising=False)
        monkeypatch.delenv("CLICKHOUSE_PORT", raising=False)
        monkeypatch.delenv("CLICKHOUSE_HTTP_PORT", raising=False)
        monkeypatch.delenv("CLICKHOUSE_DATABASE", raising=False)
        monkeypatch.delenv("CLICKHOUSE_DB", raising=False)
        monkeypatch.delenv("CLICKHOUSE_USER", raising=False)
        monkeypatch.delenv("CLICKHOUSE_PASSWORD", raising=False)

        mock_client = MagicMock()
        with patch("tools.cli.export_dossier._running_in_docker", return_value=False), \
             patch("tools.cli.export_dossier.clickhouse_connect") as mock_cc:
            mock_cc.get_client.return_value = mock_client
            result = _get_clickhouse_client()

        mock_cc.get_client.assert_called_once_with(
            host="localhost",
            port=8123,
            username="polyttool_admin",
            password="polyttool_admin",
            database="polyttool",
        )
        assert result is mock_client

    def test_docker_mode_no_env(self, monkeypatch):
        """Inside Docker with no env vars, should connect to clickhouse:8123."""
        monkeypatch.delenv("CLICKHOUSE_HOST", raising=False)
        monkeypatch.delenv("CLICKHOUSE_PORT", raising=False)
        monkeypatch.delenv("CLICKHOUSE_HTTP_PORT", raising=False)
        monkeypatch.delenv("CLICKHOUSE_DATABASE", raising=False)
        monkeypatch.delenv("CLICKHOUSE_DB", raising=False)
        monkeypatch.delenv("CLICKHOUSE_USER", raising=False)
        monkeypatch.delenv("CLICKHOUSE_PASSWORD", raising=False)

        with patch("tools.cli.export_dossier._running_in_docker", return_value=True), \
             patch("tools.cli.export_dossier.clickhouse_connect") as mock_cc:
            _get_clickhouse_client()

        mock_cc.get_client.assert_called_once_with(
            host="clickhouse",
            port=8123,
            username="polyttool_admin",
            password="polyttool_admin",
            database="polyttool",
        )

    def test_env_overrides(self, monkeypatch):
        """Explicit env vars override all defaults."""
        monkeypatch.setenv("CLICKHOUSE_HOST", "custom-host")
        monkeypatch.setenv("CLICKHOUSE_HTTP_PORT", "9999")
        monkeypatch.setenv("CLICKHOUSE_DATABASE", "customdb")
        monkeypatch.setenv("CLICKHOUSE_USER", "myuser")
        monkeypatch.setenv("CLICKHOUSE_PASSWORD", "mypass")
        monkeypatch.delenv("CLICKHOUSE_PORT", raising=False)
        monkeypatch.delenv("CLICKHOUSE_DB", raising=False)

        with patch("tools.cli.export_dossier.clickhouse_connect") as mock_cc:
            _get_clickhouse_client()

        mock_cc.get_client.assert_called_once_with(
            host="custom-host",
            port=9999,
            username="myuser",
            password="mypass",
            database="customdb",
        )
