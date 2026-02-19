import asyncio
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytest.importorskip("fastapi")
pytestmark = pytest.mark.optional_dep
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if "clickhouse_connect" not in sys.modules:
    sys.modules["clickhouse_connect"] = SimpleNamespace(get_client=lambda **_: None)

from services.api import main


class _FakeResult:
    def __init__(self, rows):
        self.result_rows = rows


class _SchemaClient:
    def __init__(self, objects):
        self.objects = list(objects)
        self.calls = []

    def query(self, query, parameters=None):
        self.calls.append((query, parameters))
        if "FROM system.tables" in query:
            return _FakeResult([[name] for name in self.objects])
        raise AssertionError(f"Unexpected query: {query}")


class ExportSchemaGuardTests(unittest.TestCase):
    def test_assert_dossier_export_schema_passes_when_views_exist(self):
        client = _SchemaClient(["user_trade_lifecycle", "user_trade_lifecycle_enriched"])
        main._assert_dossier_export_schema(client)

        self.assertEqual(len(client.calls), 1)
        _, params = client.calls[0]
        self.assertEqual(params["database"], main.CLICKHOUSE_DATABASE)

    def test_assert_dossier_export_schema_raises_when_views_missing(self):
        client = _SchemaClient(["user_trade_lifecycle"])

        with self.assertRaises(main.MissingClickHouseSchemaError) as ctx:
            main._assert_dossier_export_schema(client)

        message = str(ctx.exception)
        self.assertIn("user_trade_lifecycle_enriched", message)
        self.assertIn("docker compose down -v && docker compose up -d --build clickhouse api", message)

    def test_export_user_dossier_api_returns_actionable_error_when_schema_missing(self):
        client = _SchemaClient([])
        request = main.ExportUserDossierRequest(user="@tester")

        with patch.object(main, "get_clickhouse_client", return_value=client), patch.object(
            main.gamma_client,
            "resolve",
            return_value=SimpleNamespace(proxy_wallet="0xabc", username="tester", raw_json={}),
        ), patch.object(
            main,
            "export_user_dossier",
            side_effect=AssertionError("export_user_dossier should not be called when schema is missing"),
        ):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(main.export_user_dossier_api(request))

        self.assertEqual(ctx.exception.status_code, 503)
        detail = str(ctx.exception.detail)
        self.assertIn("Missing ClickHouse schema objects required for dossier export", detail)
        self.assertIn("user_trade_lifecycle", detail)
        self.assertIn("user_trade_lifecycle_enriched", detail)
        self.assertIn("docker compose down -v && docker compose up -d --build clickhouse api", detail)


if __name__ == "__main__":
    unittest.main()
