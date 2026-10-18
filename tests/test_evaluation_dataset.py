"""Evaluation input validation with isolated files; no model or indexes."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from legal_rag.config import load_config
from legal_rag.evaluation.dataset import load_eval_set


class EvaluationDatasetTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.config = load_config()
        self.documents = [{"doc_id": "A", "text": "Đọc, xem\nnghe thông tin."}]
        self.questions = [{
            "question_id": "q002", "question": "Hoạt động nào?",
            "reference_answer": "Đọc, xem.",
            "evidence": [{"doc_id": "A", "quote": "Đọc, xem",
                          "start_char": 0, "end_char": 8}],
            "review_status": "verified", "split": None,
        }]
        self.questions.append({**deepcopy(self.questions[0]), "question_id": "q001", "split": "dev"})
        self.manifest = {
            "format_version": 2,
            "dataset": {"repo_id": self.config.dataset.repo_id,
                        "revision": self.config.dataset.revision},
            "source": {"path": "source.jsonl", "text_field": "text"},
            "questions": {"path": "questions.jsonl", "review_status": "verified"},
        }
        self.patch = patch("legal_rag.evaluation.dataset.PROJECT_ROOT", self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def write_inputs(self):
        for name, rows, count_key in (("source", self.documents, "document_count"),
                                      ("questions", self.questions, "count")):
            details = self.manifest[name]
            path = self.root / details["path"]
            path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                            encoding="utf-8")
            details["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            details[count_key] = len(rows)
        self.save_manifest()

    def save_manifest(self):
        (self.root / "manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")

    def load(self):
        return load_eval_set(self.config, "manifest.json")

    def test_valid_preserves_records_unicode_and_order(self):
        self.write_inputs()
        self.assertEqual(self.load(), self.questions)
        self.assertEqual(load_eval_set(self.config, self.root / "manifest.json"), self.questions)

    def test_accepts_two_documents_and_test_split(self):
        self.documents.append({"doc_id": "B", "text": "Nguồn thứ hai"})
        self.questions[0]["evidence"].append(
            {"doc_id": "B", "quote": "Nguồn", "start_char": 0, "end_char": 5})
        self.questions[0]["split"] = "test"
        self.write_inputs()
        self.assertEqual(self.load(), self.questions)

    def test_corrupted_file_checksum(self):
        self.write_inputs()
        for name in ("source", "questions"):
            with self.subTest(name=name):
                self.write_inputs()
                path = self.root / self.manifest[name]["path"]
                path.write_bytes(path.read_bytes() + b" ")
                with self.assertRaisesRegex(ValueError, "Checksum"):
                    self.load()

    def test_duplicate_question_id(self):
        self.questions[1]["question_id"] = "q002"
        self.write_inputs()
        with self.assertRaisesRegex(ValueError, "Duplicate question_id.*q002"):
            self.load()

    def test_duplicate_document_id(self):
        self.documents.append(deepcopy(self.documents[0]))
        self.write_inputs()
        with self.assertRaisesRegex(ValueError, "Duplicate doc_id"):
            self.load()

    def test_bad_question_fields(self):
        original = deepcopy(self.questions)
        for field, value in (("review_status", "pending"), ("question", " "),
                             ("reference_answer", ""), ("split", "train"),
                             ("evidence", [])):
            with self.subTest(field=field):
                self.questions = deepcopy(original)
                self.questions[0][field] = value
                self.write_inputs()
                with self.assertRaisesRegex(ValueError, "q002"):
                    self.load()

    def test_missing_question_field(self):
        del self.questions[0]["split"]
        self.write_inputs()
        with self.assertRaisesRegex(ValueError, "six evaluation question fields"):
            self.load()

    def test_unknown_document_bad_quote_and_offsets(self):
        original = deepcopy(self.questions)
        for field, value in (("doc_id", "unknown"), ("quote", "Sai nội dung"),
                             ("start_char", True), ("start_char", -1),
                             ("end_char", 1000), ("end_char", 0)):
            with self.subTest(field=field, value=value):
                self.questions = deepcopy(original)
                self.questions[0]["evidence"][0][field] = value
                self.write_inputs()
                with self.assertRaisesRegex(ValueError, "q002.*evidence"):
                    self.load()

    def test_wrong_version_dataset_revision_and_status(self):
        self.write_inputs()
        original = deepcopy(self.manifest)
        for section, field, value in ((None, "format_version", 1),
                                      ("dataset", "repo_id", "other/dataset"),
                                      ("dataset", "revision", "0" * 40),
                                      ("questions", "review_status", "pending")):
            with self.subTest(field=field):
                self.manifest = deepcopy(original)
                target = self.manifest if section is None else self.manifest[section]
                target[field] = value
                self.save_manifest()
                with self.assertRaises(ValueError):
                    self.load()

    def test_wrong_counts(self):
        self.write_inputs()
        for section, field in (("source", "document_count"), ("questions", "count")):
            with self.subTest(section=section):
                self.write_inputs()
                self.manifest[section][field] += 1
                self.save_manifest()
                with self.assertRaisesRegex(ValueError, "Record count"):
                    self.load()

    def test_invalid_json_reports_file_and_line(self):
        self.write_inputs()
        path = self.root / "questions.jsonl"
        path.write_bytes(b"{broken json}\n")
        self.manifest["questions"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "questions.jsonl, line 1"):
            self.load()

    def test_missing_file_reports_path(self):
        self.write_inputs()
        (self.root / "source.jsonl").unlink()
        with self.assertRaisesRegex(FileNotFoundError, "source.jsonl"):
            self.load()


if __name__ == "__main__":
    unittest.main()
