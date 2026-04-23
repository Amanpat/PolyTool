"""Tests for WP2-C: DeepSeekV3Provider thin subclass.

Covers:
- Direct construction with explicit api_key
- Default model and base_url
- Env-var credential resolution (DEEPSEEK_API_KEY)
- Fail-fast PermissionError when credentials missing
- _PROVIDER_NAME / .name property
- model_id and generation_params metadata
- get_provider() factory routing for "deepseek"
- Factory guard: PermissionError without RIS_ENABLE_CLOUD_PROVIDERS=1
- Factory guard: PermissionError propagated when DEEPSEEK_API_KEY missing
- Unimplemented cloud providers still raise ValueError after guard
- Regression: ManualProvider and OllamaProvider unaffected
- Inheritance: score() delegates to inherited _call_with_retry -> _make_request
"""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from packages.research.evaluation.providers import (
    DeepSeekV3Provider,
    ManualProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
    get_provider,
    get_provider_metadata,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_openai_response(dims: dict | None = None) -> str:
    """Build a minimal valid OpenAI-envelope JSON string."""
    if dims is None:
        dims = {
            "relevance": {"score": 4, "rationale": "r"},
            "novelty": {"score": 3, "rationale": "n"},
            "actionability": {"score": 3, "rationale": "a"},
            "credibility": {"score": 4, "rationale": "c"},
            "total": 14,
            "epistemic_type": "EMPIRICAL",
            "summary": "test",
            "key_findings": [],
            "eval_model": "deepseek-chat",
        }
    content = json.dumps(dims)
    outer = {
        "choices": [{"message": {"content": content}}]
    }
    return json.dumps(outer)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestDeepSeekV3ProviderConstruction(unittest.TestCase):

    def test_explicit_api_key_accepted(self):
        p = DeepSeekV3Provider(api_key="sk-test")
        self.assertIsInstance(p, DeepSeekV3Provider)
        self.assertIsInstance(p, OpenAICompatibleProvider)

    def test_default_model_is_deepseek_chat(self):
        p = DeepSeekV3Provider(api_key="sk-test")
        self.assertEqual(p.model_id, "deepseek-chat")

    def test_custom_model_accepted(self):
        p = DeepSeekV3Provider(api_key="sk-test", model="deepseek-reasoner")
        self.assertEqual(p.model_id, "deepseek-reasoner")

    def test_default_base_url(self):
        p = DeepSeekV3Provider(api_key="sk-test")
        self.assertEqual(p._base_url, "https://api.deepseek.com/v1")

    def test_default_max_retries(self):
        p = DeepSeekV3Provider(api_key="sk-test")
        self.assertEqual(p._max_retries, 3)

    def test_custom_max_retries(self):
        p = DeepSeekV3Provider(api_key="sk-test", max_retries=5)
        self.assertEqual(p._max_retries, 5)

    def test_default_timeout(self):
        p = DeepSeekV3Provider(api_key="sk-test")
        self.assertEqual(p._timeout, 60)

    def test_custom_timeout(self):
        p = DeepSeekV3Provider(api_key="sk-test", timeout=120)
        self.assertEqual(p._timeout, 120)


# ---------------------------------------------------------------------------
# Env-var credential resolution
# ---------------------------------------------------------------------------

class TestDeepSeekV3ProviderCredentials(unittest.TestCase):

    def test_env_var_used_when_no_explicit_key(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-from-env"}):
            p = DeepSeekV3Provider()
        self.assertEqual(p._api_key, "sk-from-env")

    def test_explicit_key_takes_precedence_over_env(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-from-env"}):
            p = DeepSeekV3Provider(api_key="sk-explicit")
        self.assertEqual(p._api_key, "sk-explicit")

    def test_missing_key_raises_permission_error(self):
        env = {k: v for k, v in os.environ.items() if k != "DEEPSEEK_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(PermissionError) as ctx:
                DeepSeekV3Provider()
        self.assertIn("DEEPSEEK_API_KEY", str(ctx.exception))

    def test_empty_env_var_raises_permission_error(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}):
            with self.assertRaises(PermissionError):
                DeepSeekV3Provider()


# ---------------------------------------------------------------------------
# Provider identity and metadata
# ---------------------------------------------------------------------------

class TestDeepSeekV3ProviderMetadata(unittest.TestCase):

    def setUp(self):
        self.provider = DeepSeekV3Provider(api_key="sk-test")

    def test_name_property(self):
        self.assertEqual(self.provider.name, "deepseek")

    def test_provider_name_class_var(self):
        self.assertEqual(DeepSeekV3Provider._PROVIDER_NAME, "deepseek")

    def test_model_id_property(self):
        self.assertEqual(self.provider.model_id, "deepseek-chat")

    def test_generation_params_has_required_keys(self):
        params = self.provider.generation_params
        self.assertIn("temperature", params)
        self.assertIn("max_tokens", params)
        self.assertIn("response_format", params)

    def test_get_provider_metadata_duck_typing(self):
        meta = get_provider_metadata(self.provider)
        self.assertEqual(meta["provider_name"], "deepseek")
        self.assertEqual(meta["model_id"], "deepseek-chat")
        self.assertIsInstance(meta["generation_params"], dict)


# ---------------------------------------------------------------------------
# Factory routing
# ---------------------------------------------------------------------------

class TestGetProviderDeepSeek(unittest.TestCase):

    def _env_with_cloud_and_key(self):
        return {"RIS_ENABLE_CLOUD_PROVIDERS": "1", "DEEPSEEK_API_KEY": "sk-factory-test"}

    def test_factory_returns_deepseek_provider(self):
        with patch.dict(os.environ, self._env_with_cloud_and_key()):
            p = get_provider("deepseek")
        self.assertIsInstance(p, DeepSeekV3Provider)

    def test_factory_deepseek_name_property(self):
        with patch.dict(os.environ, self._env_with_cloud_and_key()):
            p = get_provider("deepseek")
        self.assertEqual(p.name, "deepseek")

    def test_factory_no_cloud_guard_raises_permission_error(self):
        env = {k: v for k, v in os.environ.items() if k != "RIS_ENABLE_CLOUD_PROVIDERS"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(PermissionError) as ctx:
                get_provider("deepseek")
        self.assertIn("RIS_ENABLE_CLOUD_PROVIDERS", str(ctx.exception))

    def test_factory_cloud_guard_set_but_no_api_key_raises_permission_error(self):
        env = {k: v for k, v in os.environ.items() if k != "DEEPSEEK_API_KEY"}
        env["RIS_ENABLE_CLOUD_PROVIDERS"] = "1"
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(PermissionError) as ctx:
                get_provider("deepseek")
        self.assertIn("DEEPSEEK_API_KEY", str(ctx.exception))

    def test_factory_passes_kwargs_to_provider(self):
        with patch.dict(os.environ, self._env_with_cloud_and_key()):
            p = get_provider("deepseek", model="deepseek-reasoner", max_retries=1)
        self.assertEqual(p.model_id, "deepseek-reasoner")
        self.assertEqual(p._max_retries, 1)


# ---------------------------------------------------------------------------
# Unimplemented cloud providers still raise ValueError
# ---------------------------------------------------------------------------

class TestUnimplementedCloudProvidersUnchanged(unittest.TestCase):

    def test_gemini_raises_permission_error_without_api_key(self):
        env = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
        env["RIS_ENABLE_CLOUD_PROVIDERS"] = "1"
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(PermissionError) as ctx:
                get_provider("gemini")
        self.assertIn("GEMINI_API_KEY", str(ctx.exception))

    def test_openai_still_raises_value_error(self):
        with patch.dict(os.environ, {"RIS_ENABLE_CLOUD_PROVIDERS": "1"}):
            with self.assertRaises(ValueError) as ctx:
                get_provider("openai")
        self.assertIn("not yet implemented", str(ctx.exception))

    def test_anthropic_still_raises_value_error(self):
        with patch.dict(os.environ, {"RIS_ENABLE_CLOUD_PROVIDERS": "1"}):
            with self.assertRaises(ValueError) as ctx:
                get_provider("anthropic")
        self.assertIn("not yet implemented", str(ctx.exception))


# ---------------------------------------------------------------------------
# Regression: local providers unaffected
# ---------------------------------------------------------------------------

class TestLocalProvidersRegression(unittest.TestCase):

    def test_manual_provider_unaffected(self):
        p = get_provider("manual")
        self.assertIsInstance(p, ManualProvider)

    def test_ollama_provider_unaffected(self):
        p = get_provider("ollama")
        self.assertIsInstance(p, OllamaProvider)

    def test_unknown_provider_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            get_provider("nonexistent_provider")
        self.assertIn("unknown provider", str(ctx.exception))


# ---------------------------------------------------------------------------
# Inheritance: score() delegates to base HTTP machinery
# ---------------------------------------------------------------------------

class TestDeepSeekV3ProviderScoreDelegation(unittest.TestCase):
    """Verify score() wires through inherited _call_with_retry -> _make_request."""

    def _provider(self):
        return DeepSeekV3Provider(api_key="sk-test")

    def test_score_calls_make_request_via_urlopen(self):
        response_body = _make_openai_response()
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = response_body.encode("utf-8")

        from packages.research.evaluation.types import EvalDocument
        doc = EvalDocument(
            doc_id="d1", title="T", body="B", source_type="manual",
            author="A", source_publish_date=None, source_url=None,
        )

        p = self._provider()
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = p.score(doc, "prompt text")

        parsed = json.loads(result)
        self.assertEqual(parsed["relevance"]["score"], 4)
        self.assertEqual(parsed["credibility"]["score"], 4)

    def test_score_uses_correct_endpoint(self):
        """Ensure the request targets api.deepseek.com/v1/chat/completions."""
        response_body = _make_openai_response()
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = response_body.encode("utf-8")

        from packages.research.evaluation.types import EvalDocument
        doc = EvalDocument(
            doc_id="d1", title="T", body="B", source_type="manual",
            author="A", source_publish_date=None, source_url=None,
        )

        p = self._provider()
        captured_requests = []

        def capture_urlopen(req, timeout=None):
            captured_requests.append(req)
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=capture_urlopen):
            p.score(doc, "prompt text")

        self.assertEqual(len(captured_requests), 1)
        self.assertIn("api.deepseek.com/v1/chat/completions", captured_requests[0].full_url)

    def test_score_sends_bearer_auth(self):
        """API key must appear as Bearer in Authorization header."""
        response_body = _make_openai_response()
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = response_body.encode("utf-8")

        from packages.research.evaluation.types import EvalDocument
        doc = EvalDocument(
            doc_id="d1", title="T", body="B", source_type="manual",
            author="A", source_publish_date=None, source_url=None,
        )

        p = DeepSeekV3Provider(api_key="sk-secret-key")
        captured = []

        def capture_urlopen(req, timeout=None):
            captured.append(req)
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=capture_urlopen):
            p.score(doc, "prompt text")

        auth = captured[0].get_header("Authorization")
        self.assertEqual(auth, "Bearer sk-secret-key")


if __name__ == "__main__":
    unittest.main()
