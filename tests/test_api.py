"""API contract and resource lifetime using fake clients/indexes only."""

from contextlib import ExitStack
from copy import deepcopy
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from legal_rag.app.api import create_app


class FakeClient:
    def __init__(self):
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True


class APITests(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.index = {"bm25": object(), "dense": object()}
        self.embeddings, self.llm = FakeClient(), FakeClient()
        self.load_config = stack.enter_context(patch("legal_rag.app.api.load_config"))
        self.load_index = stack.enter_context(patch(
            "legal_rag.app.api.load_hybrid", return_value=self.index))
        self.from_embeddings = stack.enter_context(patch(
            "legal_rag.app.api.EmbeddingClient.from_env", return_value=self.embeddings))
        self.from_llm = stack.enter_context(patch(
            "legal_rag.app.api.LLMClient.from_env", return_value=self.llm))
        self.result = {
            "question": "Hồ sơ gồm gì?", "method": "hybrid", "status": "answered",
            "answer": "Cần 03 bộ hồ sơ. [1]", "cited_source_ids": [1],
            "sources": [{"source_id": 1, "chunk_id": "A_chunk_0", "doc_id": "A",
                         "start_char": 0, "end_char": 19, "text": "Nguyên văn đoạn luật",
                         "metadata": {"title": "Văn bản", "linh_vuc": None},
                         "score": .03, "bm25_rank": 2}],
        }
        self.answer = stack.enter_context(patch(
            "legal_rag.app.api.answer_question", side_effect=lambda *a, **kw: deepcopy(self.result)))

    def test_create_app_does_not_load_or_contact_services(self):
        create_app()
        self.load_index.assert_not_called()
        self.from_llm.assert_not_called()
        self.from_embeddings.assert_not_called()

    def test_web_page_assets_and_private_files(self):
        with TestClient(create_app()) as client:
            response = client.get("/")
            self.assertEqual(response.status_code, 200)
            self.assertIn('<html lang="vi">', response.text)
            self.assertIn('/static/app.js', response.text)
            self.assertIn('/static/styles.css', response.text)
            for asset, content_type in (("styles.css", "text/css"),
                                        ("app.js", "javascript"),
                                        ("assets/legal-hero.webp", "image/webp")):
                asset_response = client.get(f"/static/{asset}")
                self.assertEqual(asset_response.status_code, 200)
                self.assertIn(content_type, asset_response.headers["content-type"])
                self.assertGreater(len(asset_response.content), 100)
            for private_path in ("/.env", "/data/raw/manifest.json", "/static/../api.py",
                                 "/static/%2e%2e/%2e%2e/%2e%2e/.env"):
                self.assertEqual(client.get(private_path).status_code, 404)
            self.answer.assert_not_called()

    def test_resources_loaded_once_reused_and_closed(self):
        app = create_app()
        with TestClient(app) as client:
            self.assertEqual(client.get("/health").json(), {"status": "ready"})
            self.answer.assert_not_called()
            for _ in range(2):
                response = client.post("/ask", json={"question": "Hồ sơ gồm gì?"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), self.result)
            self.load_config.assert_called_once()
            self.load_index.assert_called_once_with(self.load_config.return_value)
            self.from_embeddings.assert_called_once_with()
            self.from_llm.assert_called_once_with()
            self.answer.assert_called_with("Hồ sơ gồm gì?", self.index, self.llm,
                                           embedding_client=self.embeddings, method="hybrid")
            self.assertFalse(self.embeddings.closed)
            self.assertFalse(self.llm.closed)
        self.assertTrue(self.embeddings.closed)
        self.assertTrue(self.llm.closed)
        self.assertIsNone(app.state.rag)

    def test_methods_and_question_validation(self):
        with TestClient(create_app()) as client:
            for method in ("bm25", "dense", "hybrid"):
                self.result["method"] = method
                response = client.post("/ask", json={"question": "  Hồ sơ gồm gì?  ", "method": method})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.answer.call_args.args[0], "Hồ sơ gồm gì?")
                self.assertEqual(self.answer.call_args.kwargs["method"], method)
            self.answer.reset_mock()
            for payload in ({}, {"question": ""}, {"question": " \n "}, {"question": 123},
                            {"question": "Hỏi", "method": "unknown"},
                            {"question": "Hỏi", "top_k": 10}):
                with self.subTest(payload=payload):
                    self.assertEqual(client.post("/ask", json=payload).status_code, 422)
            self.answer.assert_not_called()

    def test_empty_or_insufficient_context_is_a_normal_response(self):
        with TestClient(create_app()) as client:
            for status in ("no_sources", "insufficient_context"):
                self.result.update(status=status, answer="Không đủ thông tin.",
                                   cited_source_ids=[], sources=[])
                response = client.post("/ask", json={"question": "Hỏi"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["status"], status)

    def test_pipeline_errors_are_redacted_and_not_retried(self):
        with TestClient(create_app()) as client:
            for error in (RuntimeError("secret-key private-url"), ValueError("secret-key invalid cite")):
                self.answer.reset_mock()
                self.answer.side_effect = error
                with self.assertLogs("legal_rag.app.api", level="ERROR") as logs:
                    response = client.post("/ask", json={"question": "Hỏi"})
                self.assertEqual(response.status_code, 502)
                self.assertNotIn("secret-key", response.text)
                self.assertNotIn("secret-key", "".join(logs.output))
                self.answer.assert_called_once()

    def test_unexpected_error_is_generic_500(self):
        self.answer.side_effect = OSError("secret-key")
        with TestClient(create_app()) as client, self.assertLogs("legal_rag.app.api", level="ERROR"):
            response = client.post("/ask", json={"question": "Hỏi"})
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("secret-key", response.text)

    def test_startup_failure_closes_already_created_client(self):
        self.from_llm.side_effect = ValueError("secret-key")
        with self.assertLogs("legal_rag.app.api", level="ERROR"), \
                self.assertRaisesRegex(RuntimeError, "RAG startup failed") as caught:
            with TestClient(create_app()):
                self.fail("Startup must fail before serving requests.")
        self.assertTrue(self.embeddings.closed)
        self.assertNotIn("secret-key", str(caught.exception))
        self.answer.assert_not_called()

    def test_openapi_contract_available(self):
        schema = create_app().openapi()
        self.assertIn("/ask", schema["paths"])
        self.assertIn("/health", schema["paths"])
        self.assertEqual(schema["components"]["schemas"]["AskRequest"]["properties"]["method"]["default"],
                         "hybrid")


if __name__ == "__main__":
    unittest.main()
