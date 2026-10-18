"""Chat API tests use HTTP mocks and temporary .env files, never real keys."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from legal_rag.models.llm import LLMClient


class LLMClientTests(unittest.TestCase):
    def setUp(self):
        self.messages = [
            {"role": "system", "content": "Trả lời theo nguồn [1]."},
            {"role": "user", "content": "Nguồn [1]: 03 bộ hồ sơ.\nCần bao nhiêu bộ?"},
        ]

    def client(self, handler, base_url="https://example.test/v1"):
        real_client = httpx.Client
        with patch("legal_rag.models.llm.httpx.Client", side_effect=lambda **kwargs:
                   real_client(**kwargs, transport=httpx.MockTransport(handler))):
            client = LLMClient(base_url, "test-model", "fake-key")
        self.addCleanup(client.close)
        return client

    def test_request_format_answer_and_input_unchanged(self):
        requests = []
        def handler(request):
            requests.append(request)
            return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
                "role": "assistant", "content": "Cần 03 bộ hồ sơ. [1]"}}]})
        before = deepcopy(self.messages)
        with self.client(handler, "https://example.test/v1/") as client:
            for _ in range(2):
                self.assertEqual(client.generate(self.messages, max_tokens=512), "Cần 03 bộ hồ sơ. [1]")
        self.assertTrue(client._client.is_closed)
        self.assertEqual(self.messages, before)
        self.assertEqual(len(requests), 2)
        request = requests[0]
        self.assertEqual(str(request.url), "https://example.test/v1/chat/completions")
        self.assertEqual(request.headers["Authorization"], "Bearer fake-key")
        self.assertEqual(json.loads(request.content), {
            "model": "test-model", "messages": self.messages, "max_tokens": 512, "stream": False})
        client.close()

    def test_invalid_messages_and_limits_never_send_request(self):
        def handler(request):
            self.fail("Invalid inputs must not send requests.")
        client = self.client(handler)
        for messages in ([], "hello", [None], [{"role": "tool", "content": "x"}],
                         [{"role": "user", "content": " "}],
                         [{"role": "system", "content": "x"}],
                         [{"role": "user", "content": "x", "extra": 1}]):
            with self.subTest(messages=messages), self.assertRaises(ValueError):
                client.generate(messages)
        for limit in (0, -1, True, 1.5):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                client.generate(self.messages, max_tokens=limit)

    def test_http_errors_are_redacted_and_not_retried(self):
        for status in (401, 429, 500):
            requests = []
            def handler(request):
                requests.append(request)
                return httpx.Response(status, text="fake-key private request content")
            with self.subTest(status=status), self.client(handler) as client:
                with self.assertRaisesRegex(RuntimeError, f"HTTP {status}") as error:
                    client.generate(self.messages)
                self.assertNotIn("fake-key", str(error.exception))
                self.assertEqual(len(requests), 1)

    def test_timeout_and_connection_error_are_redacted(self):
        for error_type in (httpx.ReadTimeout, httpx.ConnectError):
            def handler(request):
                raise error_type("fake-key private details", request=request)
            with self.subTest(error_type=error_type), self.client(handler) as client:
                with self.assertRaises(RuntimeError) as error:
                    client.generate(self.messages)
                self.assertNotIn("fake-key", str(error.exception))

    def test_invalid_or_empty_responses(self):
        payloads = [[], {}, {"choices": []}, {"choices": [None]},
                    {"choices": [{"message": {"role": "assistant", "content": " "}}]},
                    {"choices": [{"message": {"role": "assistant", "content": None}}]},
                    {"choices": [{"message": {"role": "user", "content": "x"}}]},
                    {"choices": [{"finish_reason": "tool_calls", "message": {"role": "assistant", "content": "x"}}]}]
        for payload in payloads:
            with self.subTest(payload=payload), self.client(
                lambda request: httpx.Response(200, json=payload)
            ) as client, self.assertRaises(ValueError):
                client.generate(self.messages)

    def test_invalid_json(self):
        with self.client(lambda request: httpx.Response(200, text="not json")) as client:
            with self.assertRaisesRegex(ValueError, "invalid JSON"):
                client.generate(self.messages)

    def test_truncation_is_reported(self):
        with self.client(lambda request: httpx.Response(200, json={"choices": [{
            "finish_reason": "length", "message": {"role": "assistant", "content": "Partial"}
        }]})) as client:
            with self.assertRaisesRegex(RuntimeError, "truncated"):
                client.generate(self.messages)

    def test_env_precedence_blank_values_and_no_environment_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env_file = root / ".env"
            env_file.write_text('LLM_BASE_URL=https://file.test/v1\nLLM_MODEL=file-model\n'
                                'LLM_API_KEY="literal-${TOKEN}"\n')
            with patch("legal_rag.models.llm.PROJECT_ROOT", root), patch.dict(
                "os.environ", {"LLM_BASE_URL": "https://env.test/v1", "LLM_MODEL": "env-model",
                               "LLM_API_KEY": "env-key", "TOKEN": "expanded"}, clear=True
            ), patch("legal_rag.models.llm.httpx.Client") as http:
                import os
                before = dict(os.environ)
                client = LLMClient.from_env()
                self.assertEqual(client.model, "file-model")
                self.assertEqual(http.call_args.kwargs["base_url"], "https://file.test/v1/")
                self.assertEqual(http.call_args.kwargs["headers"]["Authorization"], "Bearer literal-${TOKEN}")
                self.assertFalse(http.call_args.kwargs["trust_env"])
                self.assertEqual(dict(os.environ), before)
                env_file.write_text("LLM_API_KEY=\n")
                with self.assertRaisesRegex(ValueError, "LLM_API_KEY"):
                    LLMClient.from_env()
                env_file.unlink()
                self.assertEqual(LLMClient.from_env().model, "env-model")

    def test_invalid_constructor_inputs(self):
        for base_url, model, key in (("", "m", "k"), ("ftp://example.test", "m", "k"),
                                      ("https://user:pass@example.test/v1", "m", "k"),
                                      ("https://example.test/v1?key=secret", "m", "k"),
                                      ("https://example.test/v1/chat/completions", "m", "k"),
                                      ("https://example.test/v1", " ", "k"),
                                      ("https://example.test/v1", "m", ""),
                                      ("https://example.test/v1", "m", "key\ninjection")):
            with self.subTest(base_url=base_url), self.assertRaises(ValueError):
                LLMClient(base_url, model, key)


if __name__ == "__main__":
    unittest.main()
