"""Tests for WP2-A: OpenAICompatibleProvider base class.

Covers:
- Successful structured response path (mock urllib)
- Malformed outer JSON / missing content path
- Retryable vs non-retryable HTTP status codes
- Float-to-int score normalization
- JSON in markdown code block fallback (_try_extract_json)
- _post_validate: missing dims, out-of-range scores
- get_provider_metadata() duck-typing with OpenAICompatibleProvider
- No regressions for ManualProvider and OllamaProvider
"""
from __future__ import annotations

import json
import unittest
import urllib.error
from io import BytesIO
from unittest.mock import MagicMock, patch

from packages.research.evaluation.providers import (
    ManualProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
    _NonRetryableError,
    _RetryableError,
    get_provider_metadata,
)
from packages.research.evaluation.types import EvalDocument


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_doc() -> EvalDocument:
    return EvalDocument(
        doc_id="test-doc-001",
        title="Test Document",
        author="Test Author",
        source_type="manual",
        source_url=None,
        source_publish_date=None,
        body="Test body text.",
        metadata={},
    )


def _make_provider(
    api_key: str = "test-key",
    base_url: str = "https://api.example.com/v1",
    model: str = "test-model",
    max_retries: int = 3,
    timeout: int = 10,
) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        api_key=api_key,
        base_url=base_url,
        model=model,
        max_retries=max_retries,
        timeout=timeout,
    )


def _make_valid_inner_payload() -> dict:
    return {
        "relevance": {"score": 4, "rationale": "Relevant to prediction markets."},
        "novelty": {"score": 3, "rationale": "Some new angles."},
        "actionability": {"score": 3, "rationale": "Has testable ideas."},
        "credibility": {"score": 4, "rationale": "Peer-reviewed source."},
        "total": 14,
        "epistemic_type": "EMPIRICAL",
        "summary": "A useful paper about prediction markets.",
        "key_findings": ["Finding 1", "Finding 2"],
        "eval_model": "test-model",
    }


def _make_outer_response(inner: dict) -> bytes:
    """Wrap inner payload in OpenAI chat completions envelope."""
    envelope = {
        "choices": [{"message": {"content": json.dumps(inner)}}]
    }
    return json.dumps(envelope).encode("utf-8")


def _mock_urlopen_response(body_bytes: bytes, status: int = 200):
    """Return a context-manager mock that reads body_bytes."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = body_bytes
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# ---------------------------------------------------------------------------
# Properties and metadata
# ---------------------------------------------------------------------------

class TestOpenAICompatibleProviderProperties(unittest.TestCase):

    def test_name_returns_class_variable(self):
        p = _make_provider()
        self.assertEqual(p.name, "openai_compatible")

    def test_model_id_returns_model(self):
        p = _make_provider(model="deepseek-chat")
        self.assertEqual(p.model_id, "deepseek-chat")

    def test_generation_params_keys(self):
        p = _make_provider()
        params = p.generation_params
        self.assertIn("temperature", params)
        self.assertIn("max_tokens", params)
        self.assertIn("response_format", params)

    def test_subclass_can_override_provider_name(self):
        class DeepSeekProvider(OpenAICompatibleProvider):
            _PROVIDER_NAME = "deepseek"

        p = DeepSeekProvider(api_key="k", base_url="https://api.deepseek.com", model="deepseek-chat")
        self.assertEqual(p.name, "deepseek")


class TestGetProviderMetadataDuckTyping(unittest.TestCase):

    def test_manual_provider_metadata(self):
        meta = get_provider_metadata(ManualProvider())
        self.assertEqual(meta["provider_name"], "manual")
        self.assertEqual(meta["model_id"], "manual_placeholder")
        self.assertEqual(meta["generation_params"], {})

    def test_ollama_provider_metadata(self):
        meta = get_provider_metadata(OllamaProvider(model="llama3"))
        self.assertEqual(meta["provider_name"], "ollama")
        self.assertEqual(meta["model_id"], "llama3")
        self.assertIn("format", meta["generation_params"])

    def test_openai_compatible_provider_metadata(self):
        p = _make_provider(model="test-model-x")
        meta = get_provider_metadata(p)
        self.assertEqual(meta["provider_name"], "openai_compatible")
        self.assertEqual(meta["model_id"], "test-model-x")
        self.assertIn("temperature", meta["generation_params"])

    def test_subclass_metadata_uses_overridden_name(self):
        class GroqProvider(OpenAICompatibleProvider):
            _PROVIDER_NAME = "groq"

        p = GroqProvider(api_key="k", base_url="https://api.groq.com/openai/v1", model="llama3-8b")
        meta = get_provider_metadata(p)
        self.assertEqual(meta["provider_name"], "groq")
        self.assertEqual(meta["model_id"], "llama3-8b")

    def test_provider_without_model_id_attr_gets_empty_defaults(self):
        """A minimal EvalProvider without model_id/generation_params gets empty defaults."""
        from packages.research.evaluation.providers import EvalProvider

        class MinimalProvider(EvalProvider):
            @property
            def name(self) -> str:
                return "minimal"

            def score(self, doc, prompt):
                return "{}"

        meta = get_provider_metadata(MinimalProvider())
        self.assertEqual(meta["provider_name"], "minimal")
        self.assertEqual(meta["model_id"], "")
        self.assertEqual(meta["generation_params"], {})


# ---------------------------------------------------------------------------
# Successful path
# ---------------------------------------------------------------------------

class TestOpenAICompatibleProviderSuccessPath(unittest.TestCase):

    def test_score_returns_valid_json_string(self):
        p = _make_provider()
        doc = _make_doc()
        inner = _make_valid_inner_payload()
        response_bytes = _make_outer_response(inner)

        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value = _mock_urlopen_response(response_bytes)
            result = p.score(doc, "test prompt")

        parsed = json.loads(result)
        self.assertEqual(parsed["relevance"]["score"], 4)
        self.assertEqual(parsed["novelty"]["score"], 3)
        self.assertEqual(parsed["epistemic_type"], "EMPIRICAL")

    def test_score_normalizes_float_scores_to_int(self):
        p = _make_provider()
        doc = _make_doc()
        inner = _make_valid_inner_payload()
        # Introduce float scores to exercise normalization
        inner["relevance"]["score"] = 4.0
        inner["novelty"]["score"] = 3.9  # should truncate to 3
        inner["actionability"]["score"] = "3"  # string int
        response_bytes = _make_outer_response(inner)

        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value = _mock_urlopen_response(response_bytes)
            result = p.score(doc, "test prompt")

        parsed = json.loads(result)
        self.assertIsInstance(parsed["relevance"]["score"], int)
        self.assertEqual(parsed["relevance"]["score"], 4)
        self.assertEqual(parsed["novelty"]["score"], 3)
        self.assertEqual(parsed["actionability"]["score"], 3)

    def test_score_accepts_flat_int_dimension_format(self):
        """Some providers may return plain int instead of {"score": N} dict."""
        p = _make_provider()
        doc = _make_doc()
        inner = {
            "relevance": 4,
            "novelty": 3,
            "actionability": 3,
            "credibility": 4,
            "total": 14,
            "epistemic_type": "THEORETICAL",
            "summary": "Short summary.",
            "key_findings": [],
            "eval_model": "test-model",
        }
        response_bytes = _make_outer_response(inner)

        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value = _mock_urlopen_response(response_bytes)
            result = p.score(doc, "test prompt")

        parsed = json.loads(result)
        # Flat int format is preserved as-is (normalized to int)
        self.assertIsInstance(parsed["relevance"], int)
        self.assertEqual(parsed["relevance"], 4)


# ---------------------------------------------------------------------------
# JSON in markdown code block fallback
# ---------------------------------------------------------------------------

class TestTryExtractJson(unittest.TestCase):

    def test_extracts_from_json_fenced_block(self):
        text = '```json\n{"a": 1}\n```'
        result = OpenAICompatibleProvider._try_extract_json(text)
        self.assertEqual(result, '{"a": 1}')

    def test_extracts_from_generic_fenced_block(self):
        text = "```\n{\"b\": 2}\n```"
        result = OpenAICompatibleProvider._try_extract_json(text)
        self.assertEqual(result, '{"b": 2}')

    def test_returns_none_for_plain_text(self):
        result = OpenAICompatibleProvider._try_extract_json("no fences here")
        self.assertIsNone(result)

    def test_json_block_fallback_in_score(self):
        """score() succeeds when inner content is wrapped in ```json ... ```."""
        p = _make_provider()
        doc = _make_doc()
        inner = _make_valid_inner_payload()
        # Wrap inner JSON in markdown code block
        inner_json_str = "```json\n" + json.dumps(inner) + "\n```"
        envelope = {"choices": [{"message": {"content": inner_json_str}}]}
        response_bytes = json.dumps(envelope).encode("utf-8")

        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value = _mock_urlopen_response(response_bytes)
            result = p.score(doc, "test prompt")

        parsed = json.loads(result)
        self.assertEqual(parsed["relevance"]["score"], 4)


# ---------------------------------------------------------------------------
# Post-validation errors
# ---------------------------------------------------------------------------

class TestPostValidate(unittest.TestCase):

    def test_passes_valid_payload(self):
        inner = _make_valid_inner_payload()
        # Should not raise
        OpenAICompatibleProvider._post_validate(inner)

    def test_raises_on_missing_dimension(self):
        inner = _make_valid_inner_payload()
        del inner["novelty"]
        with self.assertRaises(_NonRetryableError) as ctx:
            OpenAICompatibleProvider._post_validate(inner)
        self.assertIn("novelty", str(ctx.exception))

    def test_raises_on_missing_score_key_in_dict(self):
        inner = _make_valid_inner_payload()
        inner["relevance"] = {"rationale": "no score here"}
        with self.assertRaises(_NonRetryableError) as ctx:
            OpenAICompatibleProvider._post_validate(inner)
        self.assertIn("score", str(ctx.exception))

    def test_raises_on_score_above_5(self):
        inner = _make_valid_inner_payload()
        inner["credibility"]["score"] = 6
        with self.assertRaises(_NonRetryableError) as ctx:
            OpenAICompatibleProvider._post_validate(inner)
        self.assertIn("credibility", str(ctx.exception))

    def test_raises_on_score_below_1(self):
        inner = _make_valid_inner_payload()
        inner["actionability"]["score"] = 0
        with self.assertRaises(_NonRetryableError) as ctx:
            OpenAICompatibleProvider._post_validate(inner)
        self.assertIn("actionability", str(ctx.exception))

    def test_raises_on_non_numeric_score(self):
        inner = _make_valid_inner_payload()
        inner["novelty"]["score"] = "high"
        with self.assertRaises(_NonRetryableError) as ctx:
            OpenAICompatibleProvider._post_validate(inner)
        self.assertIn("novelty", str(ctx.exception))

    def test_normalizes_float_score_in_place(self):
        inner = _make_valid_inner_payload()
        inner["relevance"]["score"] = 4.7  # truncates to 4
        OpenAICompatibleProvider._post_validate(inner)
        self.assertEqual(inner["relevance"]["score"], 4)
        self.assertIsInstance(inner["relevance"]["score"], int)


# ---------------------------------------------------------------------------
# Validate-and-extract errors
# ---------------------------------------------------------------------------

class TestValidateAndExtract(unittest.TestCase):

    def setUp(self):
        self.p = _make_provider()

    def test_raises_on_malformed_outer_json(self):
        with self.assertRaises(_NonRetryableError):
            self.p._validate_and_extract("not json {{{")

    def test_raises_on_missing_choices(self):
        envelope = {"result": "nothing here"}
        with self.assertRaises(_NonRetryableError):
            self.p._validate_and_extract(json.dumps(envelope))

    def test_raises_on_empty_choices_list(self):
        envelope = {"choices": []}
        with self.assertRaises(_NonRetryableError):
            self.p._validate_and_extract(json.dumps(envelope))

    def test_raises_on_non_string_content(self):
        envelope = {"choices": [{"message": {"content": {"already": "a dict"}}}]}
        with self.assertRaises(_NonRetryableError):
            self.p._validate_and_extract(json.dumps(envelope))

    def test_raises_when_inner_not_json_and_no_code_block(self):
        envelope = {"choices": [{"message": {"content": "plain text no json"}}]}
        with self.assertRaises(_NonRetryableError):
            self.p._validate_and_extract(json.dumps(envelope))

    def test_raises_when_inner_json_fails_post_validate(self):
        inner = _make_valid_inner_payload()
        del inner["credibility"]
        envelope = {"choices": [{"message": {"content": json.dumps(inner)}}]}
        with self.assertRaises(_NonRetryableError):
            self.p._validate_and_extract(json.dumps(envelope))


# ---------------------------------------------------------------------------
# Retry / backoff behavior
# ---------------------------------------------------------------------------

class TestRetryBehavior(unittest.TestCase):

    def _make_http_error(self, code: int, body: str = "") -> urllib.error.HTTPError:
        fp = BytesIO(body.encode("utf-8"))
        return urllib.error.HTTPError(
            url="https://api.example.com/v1/chat/completions",
            code=code,
            msg=f"HTTP {code}",
            hdrs=MagicMock(get=MagicMock(return_value=None)),
            fp=fp,
        )

    def test_429_triggers_retry_and_eventually_raises_connection_error(self):
        p = _make_provider(max_retries=2)
        doc = _make_doc()

        with patch("urllib.request.urlopen") as mock_open, \
             patch("time.sleep") as mock_sleep:
            mock_open.side_effect = self._make_http_error(429)
            with self.assertRaises(ConnectionError) as ctx:
                p.score(doc, "prompt")

        self.assertIn("2 attempts", str(ctx.exception))
        # time.sleep was called between retries
        self.assertEqual(mock_sleep.call_count, 2)

    def test_503_triggers_retry(self):
        p = _make_provider(max_retries=2)
        doc = _make_doc()

        with patch("urllib.request.urlopen") as mock_open, \
             patch("time.sleep"):
            mock_open.side_effect = self._make_http_error(503)
            with self.assertRaises(ConnectionError):
                p.score(doc, "prompt")

    def test_502_triggers_retry(self):
        p = _make_provider(max_retries=2)
        doc = _make_doc()

        with patch("urllib.request.urlopen") as mock_open, \
             patch("time.sleep"):
            mock_open.side_effect = self._make_http_error(502)
            with self.assertRaises(ConnectionError):
                p.score(doc, "prompt")

    def test_400_raises_value_error_immediately_no_retry(self):
        p = _make_provider(max_retries=3)
        doc = _make_doc()

        with patch("urllib.request.urlopen") as mock_open, \
             patch("time.sleep") as mock_sleep:
            mock_open.side_effect = self._make_http_error(400)
            with self.assertRaises(ValueError):
                p.score(doc, "prompt")

        # No retries for non-retryable errors
        mock_sleep.assert_not_called()
        # urlopen was called exactly once
        self.assertEqual(mock_open.call_count, 1)

    def test_403_raises_permission_error_immediately_no_retry(self):
        p = _make_provider(max_retries=3)
        doc = _make_doc()

        with patch("urllib.request.urlopen") as mock_open, \
             patch("time.sleep") as mock_sleep:
            mock_open.side_effect = self._make_http_error(403)
            with self.assertRaises(PermissionError):
                p.score(doc, "prompt")

        mock_sleep.assert_not_called()
        self.assertEqual(mock_open.call_count, 1)

    def test_url_error_triggers_retry(self):
        p = _make_provider(max_retries=2)
        doc = _make_doc()

        with patch("urllib.request.urlopen") as mock_open, \
             patch("time.sleep"):
            mock_open.side_effect = urllib.error.URLError("connection refused")
            with self.assertRaises(ConnectionError):
                p.score(doc, "prompt")

    def test_retry_succeeds_on_second_attempt(self):
        """First call raises 429, second call succeeds."""
        p = _make_provider(max_retries=3)
        doc = _make_doc()
        inner = _make_valid_inner_payload()
        success_response = _mock_urlopen_response(_make_outer_response(inner))

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise self._make_http_error(429)
            return success_response

        with patch("urllib.request.urlopen") as mock_open, \
             patch("time.sleep"):
            mock_open.side_effect = side_effect
            result = p.score(doc, "prompt")

        parsed = json.loads(result)
        self.assertEqual(parsed["relevance"]["score"], 4)
        self.assertEqual(call_count[0], 2)

    def test_429_uses_retry_after_from_header(self):
        """retry_after from Retry-After header is passed to time.sleep."""
        p = _make_provider(max_retries=2)
        doc = _make_doc()

        headers = MagicMock()
        headers.get = MagicMock(return_value="5")  # 5 seconds
        fp = BytesIO(b"")
        exc = urllib.error.HTTPError(
            url="https://api.example.com/v1/chat/completions",
            code=429,
            msg="Too Many Requests",
            hdrs=headers,
            fp=fp,
        )

        with patch("urllib.request.urlopen") as mock_open, \
             patch("time.sleep") as mock_sleep:
            mock_open.side_effect = exc
            with self.assertRaises(ConnectionError):
                p.score(doc, "prompt")

        # time.sleep should have been called with the retry_after value (5.0)
        sleep_calls = [c.args[0] for c in mock_sleep.call_args_list]
        self.assertTrue(all(s == 5.0 for s in sleep_calls))

    def test_malformed_response_raises_value_error_no_retry(self):
        """Malformed outer JSON is non-retryable — raises ValueError immediately."""
        p = _make_provider(max_retries=3)
        doc = _make_doc()

        with patch("urllib.request.urlopen") as mock_open, \
             patch("time.sleep") as mock_sleep:
            mock_open.return_value = _mock_urlopen_response(b"not json {{{")
            with self.assertRaises(ValueError):
                p.score(doc, "prompt")

        mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# No regressions for existing providers
# ---------------------------------------------------------------------------

class TestExistingProviderNoRegression(unittest.TestCase):

    def test_manual_provider_score_returns_valid_json(self):
        p = ManualProvider()
        doc = _make_doc()
        raw = p.score(doc, "unused prompt")
        parsed = json.loads(raw)
        self.assertEqual(parsed["relevance"]["score"], 3)
        self.assertEqual(parsed["total"], 12)

    def test_manual_provider_name(self):
        self.assertEqual(ManualProvider().name, "manual")

    def test_ollama_provider_raises_connection_error_on_bad_url(self):
        p = OllamaProvider(base_url="http://localhost:19999")
        doc = _make_doc()
        with self.assertRaises(ConnectionError):
            p.score(doc, "test prompt")


if __name__ == "__main__":
    unittest.main()
