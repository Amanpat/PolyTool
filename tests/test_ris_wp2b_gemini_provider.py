"""Tests for WP2-B: GeminiFlashProvider.

Covers:
- Direct construction: explicit key, default model, env-var resolution
- Fail-fast PermissionError when GEMINI_API_KEY absent or empty
- Provider identity: _PROVIDER_NAME, .name, model_id, generation_params
- get_provider() factory routing for "gemini"
- Factory guard: PermissionError without RIS_ENABLE_CLOUD_PROVIDERS=1
- Factory guard: PermissionError propagated when GEMINI_API_KEY missing
- Unimplemented cloud providers (openai, anthropic) still raise ValueError
- Regression: ManualProvider and OllamaProvider unaffected
- score() endpoint URL (no Bearer header; key in URL query param)
- score() successful round-trip through _validate_and_extract
- safety block (finishReason == "SAFETY") raises ValueError
- 429 with retryDelay in error.details parses correctly
- 503 triggers retryable path
- Missing candidates raises ValueError
- Missing content path raises ValueError
- post_validate called: out-of-range score raises ValueError
- Retry exhaustion raises ConnectionError
- Non-retryable 400 raises ValueError immediately
- 403 raises PermissionError immediately
- rate limiting: min_request_interval=0 skips sleep
"""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from packages.research.evaluation.providers import (
    GeminiFlashProvider,
    ManualProvider,
    OllamaProvider,
    get_provider,
    get_provider_metadata,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_gemini_response(dims: dict | None = None) -> str:
    """Build a minimal valid Gemini generateContent JSON response."""
    if dims is None:
        dims = {
            "relevance": {"score": 4, "rationale": "r"},
            "novelty": {"score": 3, "rationale": "n"},
            "actionability": {"score": 3, "rationale": "a"},
            "credibility": {"score": 4, "rationale": "c"},
        }
    content_text = json.dumps(dims)
    outer = {
        "candidates": [
            {
                "content": {"parts": [{"text": content_text}]},
                "finishReason": "STOP",
            }
        ]
    }
    return json.dumps(outer)


def _mock_urlopen_response(body: str):
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read.return_value = body.encode("utf-8")
    return mock_resp


def _make_doc():
    from packages.research.evaluation.types import EvalDocument
    return EvalDocument(
        doc_id="d1", title="T", body="B", source_type="manual",
        author="A", source_publish_date=None, source_url=None,
    )


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestGeminiFlashProviderConstruction(unittest.TestCase):

    def test_explicit_api_key_accepted(self):
        p = GeminiFlashProvider(api_key="gm-test")
        self.assertIsInstance(p, GeminiFlashProvider)

    def test_default_model(self):
        p = GeminiFlashProvider(api_key="gm-test")
        self.assertEqual(p.model_id, "gemini-2.5-flash-preview-04-17")

    def test_custom_model(self):
        p = GeminiFlashProvider(api_key="gm-test", model="gemini-1.5-pro")
        self.assertEqual(p.model_id, "gemini-1.5-pro")

    def test_default_max_retries(self):
        p = GeminiFlashProvider(api_key="gm-test")
        self.assertEqual(p._max_retries, 3)

    def test_custom_max_retries(self):
        p = GeminiFlashProvider(api_key="gm-test", max_retries=5)
        self.assertEqual(p._max_retries, 5)

    def test_default_timeout(self):
        p = GeminiFlashProvider(api_key="gm-test")
        self.assertEqual(p._timeout, 60)

    def test_custom_timeout(self):
        p = GeminiFlashProvider(api_key="gm-test", timeout=90)
        self.assertEqual(p._timeout, 90)

    def test_default_min_request_interval(self):
        p = GeminiFlashProvider(api_key="gm-test")
        self.assertEqual(p._min_request_interval, 5.0)

    def test_custom_min_request_interval(self):
        p = GeminiFlashProvider(api_key="gm-test", min_request_interval=0.0)
        self.assertEqual(p._min_request_interval, 0.0)


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------

class TestGeminiFlashProviderCredentials(unittest.TestCase):

    def test_env_var_used_when_no_explicit_key(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "gm-from-env"}):
            p = GeminiFlashProvider()
        self.assertEqual(p._api_key, "gm-from-env")

    def test_explicit_key_takes_precedence_over_env(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "gm-from-env"}):
            p = GeminiFlashProvider(api_key="gm-explicit")
        self.assertEqual(p._api_key, "gm-explicit")

    def test_missing_key_raises_permission_error(self):
        env = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(PermissionError) as ctx:
                GeminiFlashProvider()
        self.assertIn("GEMINI_API_KEY", str(ctx.exception))

    def test_empty_env_var_raises_permission_error(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            with self.assertRaises(PermissionError):
                GeminiFlashProvider()


# ---------------------------------------------------------------------------
# Provider identity and metadata
# ---------------------------------------------------------------------------

class TestGeminiFlashProviderMetadata(unittest.TestCase):

    def setUp(self):
        self.provider = GeminiFlashProvider(api_key="gm-test")

    def test_name_property(self):
        self.assertEqual(self.provider.name, "gemini")

    def test_provider_name_class_var(self):
        self.assertEqual(GeminiFlashProvider._PROVIDER_NAME, "gemini")

    def test_model_id_property(self):
        self.assertEqual(self.provider.model_id, "gemini-2.5-flash-preview-04-17")

    def test_generation_params_has_required_keys(self):
        params = self.provider.generation_params
        self.assertIn("temperature", params)
        self.assertIn("max_output_tokens", params)
        self.assertIn("response_mime_type", params)
        self.assertIn("response_schema", params)

    def test_generation_params_response_mime_type(self):
        self.assertEqual(
            self.provider.generation_params["response_mime_type"],
            "application/json",
        )

    def test_get_provider_metadata_duck_typing(self):
        meta = get_provider_metadata(self.provider)
        self.assertEqual(meta["provider_name"], "gemini")
        self.assertEqual(meta["model_id"], "gemini-2.5-flash-preview-04-17")
        self.assertIsInstance(meta["generation_params"], dict)


# ---------------------------------------------------------------------------
# Factory routing
# ---------------------------------------------------------------------------

class TestGetProviderGemini(unittest.TestCase):

    def _env(self):
        return {"RIS_ENABLE_CLOUD_PROVIDERS": "1", "GEMINI_API_KEY": "gm-factory-test"}

    def test_factory_returns_gemini_provider(self):
        with patch.dict(os.environ, self._env()):
            p = get_provider("gemini")
        self.assertIsInstance(p, GeminiFlashProvider)

    def test_factory_gemini_name_property(self):
        with patch.dict(os.environ, self._env()):
            p = get_provider("gemini")
        self.assertEqual(p.name, "gemini")

    def test_factory_no_cloud_guard_raises_permission_error(self):
        env = {k: v for k, v in os.environ.items() if k != "RIS_ENABLE_CLOUD_PROVIDERS"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(PermissionError) as ctx:
                get_provider("gemini")
        self.assertIn("RIS_ENABLE_CLOUD_PROVIDERS", str(ctx.exception))

    def test_factory_cloud_guard_set_but_no_api_key_raises_permission_error(self):
        env = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
        env["RIS_ENABLE_CLOUD_PROVIDERS"] = "1"
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(PermissionError) as ctx:
                get_provider("gemini")
        self.assertIn("GEMINI_API_KEY", str(ctx.exception))

    def test_factory_passes_kwargs_to_provider(self):
        with patch.dict(os.environ, self._env()):
            p = get_provider("gemini", model="gemini-1.5-pro", max_retries=1)
        self.assertEqual(p.model_id, "gemini-1.5-pro")
        self.assertEqual(p._max_retries, 1)


# ---------------------------------------------------------------------------
# Unimplemented cloud providers still raise ValueError
# ---------------------------------------------------------------------------

class TestUnimplementedCloudProvidersUnchanged(unittest.TestCase):

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
# score() HTTP delegation
# ---------------------------------------------------------------------------

class TestGeminiFlashProviderScore(unittest.TestCase):

    def _provider(self):
        return GeminiFlashProvider(api_key="gm-secret", min_request_interval=0.0)

    def test_score_returns_valid_json(self):
        mock_resp = _mock_urlopen_response(_make_gemini_response())
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = self._provider().score(_make_doc(), "prompt text")
        parsed = json.loads(result)
        self.assertEqual(parsed["relevance"]["score"], 4)

    def test_score_uses_generatecontent_endpoint(self):
        mock_resp = _mock_urlopen_response(_make_gemini_response())
        captured = []

        def capture(req, timeout=None):
            captured.append(req)
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=capture):
            self._provider().score(_make_doc(), "prompt")

        self.assertEqual(len(captured), 1)
        url = captured[0].full_url
        self.assertIn("generateContent", url)
        self.assertIn("generativelanguage.googleapis.com", url)

    def test_score_sends_key_as_query_param_not_bearer(self):
        mock_resp = _mock_urlopen_response(_make_gemini_response())
        captured = []

        def capture(req, timeout=None):
            captured.append(req)
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=capture):
            GeminiFlashProvider(
                api_key="gm-secret-key", min_request_interval=0.0
            ).score(_make_doc(), "prompt")

        req = captured[0]
        self.assertIn("gm-secret-key", req.full_url)
        auth = req.get_header("Authorization")
        self.assertIsNone(auth)

    def test_score_model_in_endpoint_url(self):
        mock_resp = _mock_urlopen_response(_make_gemini_response())
        captured = []

        def capture(req, timeout=None):
            captured.append(req)
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=capture):
            GeminiFlashProvider(
                api_key="k", model="gemini-1.5-pro", min_request_interval=0.0
            ).score(_make_doc(), "prompt")

        self.assertIn("gemini-1.5-pro", captured[0].full_url)


# ---------------------------------------------------------------------------
# _validate_and_extract edge cases
# ---------------------------------------------------------------------------

class TestGeminiValidateAndExtract(unittest.TestCase):

    def _p(self):
        return GeminiFlashProvider(api_key="k", min_request_interval=0.0)

    def test_safety_block_raises_value_error(self):
        safety_body = json.dumps({
            "candidates": [{"finishReason": "SAFETY"}]
        })
        mock_resp = _mock_urlopen_response(safety_body)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            with self.assertRaises(ValueError) as ctx:
                self._p().score(_make_doc(), "prompt")
        self.assertIn("safety", str(ctx.exception).lower())

    def test_empty_candidates_raises_value_error(self):
        body = json.dumps({"candidates": []})
        mock_resp = _mock_urlopen_response(body)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            with self.assertRaises(ValueError):
                self._p().score(_make_doc(), "prompt")

    def test_missing_candidates_key_raises_value_error(self):
        body = json.dumps({"error": "something"})
        mock_resp = _mock_urlopen_response(body)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            with self.assertRaises(ValueError):
                self._p().score(_make_doc(), "prompt")

    def test_missing_content_parts_raises_value_error(self):
        body = json.dumps({
            "candidates": [{"finishReason": "STOP"}]
        })
        mock_resp = _mock_urlopen_response(body)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            with self.assertRaises(ValueError):
                self._p().score(_make_doc(), "prompt")

    def test_out_of_range_score_raises_value_error(self):
        dims = {
            "relevance": {"score": 9, "rationale": "r"},
            "novelty": {"score": 3, "rationale": "n"},
            "actionability": {"score": 3, "rationale": "a"},
            "credibility": {"score": 4, "rationale": "c"},
        }
        body = _make_gemini_response(dims)
        mock_resp = _mock_urlopen_response(body)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            with self.assertRaises(ValueError):
                self._p().score(_make_doc(), "prompt")


# ---------------------------------------------------------------------------
# HTTP error handling
# ---------------------------------------------------------------------------

class TestGeminiHTTPErrors(unittest.TestCase):

    def _p(self):
        return GeminiFlashProvider(api_key="k", max_retries=2, min_request_interval=0.0)

    def _http_error(self, status: int, body: str = "{}"):
        import urllib.error
        import urllib.response
        import io
        err = urllib.error.HTTPError(
            url="https://example.com",
            code=status,
            msg=f"HTTP {status}",
            hdrs={},
            fp=io.BytesIO(body.encode("utf-8")),
        )
        return err

    def test_429_triggers_retry_then_succeeds(self):
        good_resp = _mock_urlopen_response(_make_gemini_response())
        call_count = [0]

        def side_effect(req, timeout=None):
            call_count[0] += 1
            if call_count[0] == 1:
                raise self._http_error(429)
            return good_resp

        with patch("urllib.request.urlopen", side_effect=side_effect):
            with patch("time.sleep"):
                result = self._p().score(_make_doc(), "prompt")
        parsed = json.loads(result)
        self.assertEqual(parsed["relevance"]["score"], 4)
        self.assertEqual(call_count[0], 2)

    def test_429_with_retry_delay_parses_correctly(self):
        err_body = json.dumps({
            "error": {
                "details": [{"retryDelay": "30s"}]
            }
        })
        good_resp = _mock_urlopen_response(_make_gemini_response())
        call_count = [0]

        def side_effect(req, timeout=None):
            call_count[0] += 1
            if call_count[0] == 1:
                raise self._http_error(429, err_body)
            return good_resp

        sleep_calls = []
        with patch("urllib.request.urlopen", side_effect=side_effect):
            with patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
                self._p().score(_make_doc(), "prompt")

        self.assertTrue(any(s >= 30.0 for s in sleep_calls))

    def test_503_triggers_retry(self):
        good_resp = _mock_urlopen_response(_make_gemini_response())
        call_count = [0]

        def side_effect(req, timeout=None):
            call_count[0] += 1
            if call_count[0] == 1:
                raise self._http_error(503)
            return good_resp

        with patch("urllib.request.urlopen", side_effect=side_effect):
            with patch("time.sleep"):
                result = self._p().score(_make_doc(), "prompt")
        self.assertEqual(call_count[0], 2)

    def test_400_raises_value_error_immediately(self):
        call_count = [0]

        def side_effect(req, timeout=None):
            call_count[0] += 1
            raise self._http_error(400)

        with patch("urllib.request.urlopen", side_effect=side_effect):
            with self.assertRaises(ValueError):
                self._p().score(_make_doc(), "prompt")
        self.assertEqual(call_count[0], 1)

    def test_403_raises_permission_error_immediately(self):
        call_count = [0]

        def side_effect(req, timeout=None):
            call_count[0] += 1
            raise self._http_error(403)

        with patch("urllib.request.urlopen", side_effect=side_effect):
            with self.assertRaises(PermissionError):
                self._p().score(_make_doc(), "prompt")
        self.assertEqual(call_count[0], 1)

    def test_retry_exhaustion_raises_connection_error(self):
        import urllib.error

        def side_effect(req, timeout=None):
            raise urllib.error.URLError("connection refused")

        with patch("urllib.request.urlopen", side_effect=side_effect):
            with patch("time.sleep"):
                with self.assertRaises(ConnectionError):
                    self._p().score(_make_doc(), "prompt")


if __name__ == "__main__":
    unittest.main()
