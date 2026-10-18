"""Exercise the runner using fake retrieval and a fake embedding client only."""

from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from legal_rag.config import load_config
from legal_rag.evaluation.runner import run_evaluation


class EvaluationRunnerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.config = load_config()
        self.questions = [{
            "question_id": f"q{i}", "question": f"Câu hỏi {i}",
            "reference_answer": "Đáp án", "review_status": "verified", "split": None,
            "evidence": [{"doc_id": "A", "start_char": 100, "end_char": 200},
                         {"doc_id": "B", "start_char": 100, "end_char": 200}],
        } for i in (1, 2)]
        self.hits = [{
            "chunk_id": "a", "doc_id": "A", "start_char": 50, "end_char": 250,
            "text": "Đoạn nguồn", "metadata": {"id": "A"}, "score": 0.5,
        }]
        self.evaluation = {
            "dataset": {"repo_id": self.config.dataset.repo_id,
                        "revision": self.config.dataset.revision},
            "source": {"sha256": "cleaned-hash"},
            "questions": {"sha256": "questions-hash"},
        }
        chunk_path = self.root / "data/processed/sample_200/chunks.jsonl"
        chunk_path.parent.mkdir(parents=True)
        chunk_path.write_text('{"chunk_id":"a"}\n')
        self.chunk_hash = hashlib.sha256(chunk_path.read_bytes()).hexdigest()
        self.processed = {
            "repo_id": self.config.dataset.repo_id, "revision": self.config.dataset.revision,
            "chunking": {"input_sha256": "cleaned-hash", "output_sha256": self.chunk_hash},
        }
        self.index_manifest = {
            "repo_id": self.config.dataset.repo_id, "revision": self.config.dataset.revision,
            "chunks_sha256": self.chunk_hash,
            "bm25": {"artifact_sha256": "bm25-hash"},
            "dense": {"fingerprint": "fingerprint", "status": "ready"},
        }
        self.index = {"bm25": {"chunks_sha256": self.chunk_hash},
                      "dense": {"manifest": deepcopy(self.index_manifest["dense"])}}
        self.write_manifests()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch("legal_rag.evaluation.runner.PROJECT_ROOT", self.root))
        stack.enter_context(redirect_stdout(io.StringIO()))
        self.load_questions = stack.enter_context(patch(
            "legal_rag.evaluation.runner.load_eval_set", return_value=self.questions))
        self.load_indexes = stack.enter_context(patch(
            "legal_rag.evaluation.runner.load_hybrid", return_value=self.index))
        self.client = MagicMock()
        self.from_env = stack.enter_context(patch(
            "legal_rag.evaluation.runner.EmbeddingClient.from_env"))
        self.from_env.return_value.__enter__.return_value = self.client
        self.searches = {name: stack.enter_context(patch(
            f"legal_rag.evaluation.runner.search_{name}",
            side_effect=lambda *a, **kw: deepcopy(self.hits)))
            for name in ("bm25", "dense", "hybrid")}

    def write_manifests(self):
        for path, value in (("eval/sample_200/manifest.json", self.evaluation),
                            ("data/processed/sample_200/manifest.json", self.processed),
                            ("data/indexes/sample_200/manifest.json", self.index_manifest)):
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(value), encoding="utf-8")

    def test_full_run_warmup_order_scores_outputs_and_timing(self):
        times = [0, .01, 1, 1.02, 2, 2.03, 3, 3.04, 4, 4.05, 5, 5.06]
        with patch("legal_rag.evaluation.runner.perf_counter", side_effect=times) as clock:
            result = run_evaluation(self.config)
        self.load_questions.assert_called_once_with(self.config)
        self.load_indexes.assert_called_once_with(self.config)
        self.from_env.assert_called_once_with()
        self.from_env.return_value.__exit__.assert_called_once()
        self.assertEqual(clock.call_count, 12)  # six measured searches, no warmup timer
        rows = list(map(json.loads, (result / "retrieval.jsonl").read_text().splitlines()))
        self.assertEqual([(r["question_id"], r["method"]) for r in rows],
                         [(q, m) for q in ("q1", "q2") for m in ("bm25", "dense", "hybrid")])
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[0]["hits"][0], {**self.hits[0], "rank": 1})
        self.assertEqual(rows[0]["metrics"], {"recall@5": .5, "hit@5": 1.0, "rr@5": 1.0})
        summary = json.loads((result / "summary.json").read_text())
        for name, expected_time in (("bm25", 25), ("dense", 35), ("hybrid", 45)):
            self.assertEqual(self.searches[name].call_count, 3)  # warmup plus two queries
            self.assertAlmostEqual(summary[name]["avg_latency_ms"], expected_time)
            self.assertEqual(summary[name]["question_count"], 2)
            self.assertEqual(summary[name]["mrr@5"], 1.0)
        for call in self.searches["dense"].call_args_list:
            self.assertIs(call.args[1], self.client)
            self.assertEqual(call.kwargs["top_k"], 5)
        self.assertEqual(self.searches["hybrid"].call_args.kwargs,
                         {"top_k": 5, "bm25_k": 20, "dense_k": 20, "rrf_k": 60})
        saved = json.loads((result / "config.json").read_text())
        self.assertEqual(saved["status"], "completed")
        self.assertEqual(saved["completed_results"], 6)
        self.assertNotIn("api_key", saved)

    def test_failure_keeps_completed_rows_no_success_summary_or_secrets(self):
        self.searches["dense"].side_effect = [deepcopy(self.hits),
                                               RuntimeError("secret-key-and-private-endpoint")]
        with self.assertRaisesRegex(RuntimeError, "question=q1, method=dense") as caught:
            run_evaluation(self.config)
        result, = (self.root / "results").iterdir()
        rows = list(map(json.loads, (result / "retrieval.jsonl").read_text().splitlines()))
        self.assertEqual(len(rows), 1)
        saved = json.loads((result / "config.json").read_text())
        self.assertEqual(saved["status"], "failed")
        self.assertEqual(saved["completed_results"], 1)
        self.assertEqual(saved["error"]["method"], "dense")
        self.assertFalse((result / "summary.json").exists())
        self.assertNotIn("secret-key", (result / "config.json").read_text())
        self.assertNotIn("secret-key", str(caught.exception))

    def test_warmup_failure_not_scored(self):
        self.searches["hybrid"].side_effect = TimeoutError("private URL")
        with self.assertRaisesRegex(RuntimeError, "phase=warmup"):
            run_evaluation(self.config)
        result, = (self.root / "results").iterdir()
        saved = json.loads((result / "config.json").read_text())
        self.assertEqual(saved["completed_results"], 0)
        self.assertFalse((result / "summary.json").exists())

    def test_corpus_mismatch_stops_before_client(self):
        self.processed["chunking"]["input_sha256"] = "other-cleaned-source"
        self.write_manifests()
        with self.assertRaisesRegex(ValueError, "different cleaned-source"):
            run_evaluation(self.config)
        self.from_env.assert_not_called()
        self.load_indexes.assert_not_called()

    def test_chunk_checksum_mismatch_stops_before_client(self):
        self.index_manifest["chunks_sha256"] = "other-chunks"
        self.write_manifests()
        with self.assertRaisesRegex(ValueError, "Chunk corpus checksum"):
            run_evaluation(self.config)
        self.from_env.assert_not_called()

    def test_changed_manifest_during_loading_is_rejected(self):
        def change_manifest(*args):
            self.index_manifest["changed"] = True
            self.write_manifests()
            return self.index
        self.load_indexes.side_effect = change_manifest
        with self.assertRaisesRegex(ValueError, "manifest changed"):
            run_evaluation(self.config)
        self.from_env.assert_not_called()

    def test_invalid_parameters_do_not_load_or_call_api(self):
        for kwargs in ({"k": 0}, {"k": True}, {"rrf_k": -1}, {"bm25_k": 1}, {"dense_k": 1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                run_evaluation(self.config, **kwargs)
        self.load_questions.assert_not_called()
        self.from_env.assert_not_called()

    def test_empty_hits_are_valid_zero_scores(self):
        self.hits = []
        result = run_evaluation(self.config)
        summary = json.loads((result / "summary.json").read_text())
        for scores in summary.values():
            self.assertEqual(scores["recall@5"], 0)
            self.assertEqual(scores["hit@5"], 0)
            self.assertEqual(scores["mrr@5"], 0)

    def test_output_directories_never_overwrite_previous_runs(self):
        first = run_evaluation(self.config)
        before = (first / "retrieval.jsonl").read_bytes()
        second = run_evaluation(self.config)
        self.assertNotEqual(first, second)
        self.assertEqual((first / "retrieval.jsonl").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
