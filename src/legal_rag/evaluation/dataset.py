"""Read approved evaluation questions and validate their cleaned-source evidence.

Return the original question records in file order. No retrieval, chunk-label
generation, dataset modification or model/API calls happen in this module.
"""

import hashlib
import json
from pathlib import Path

from legal_rag.config import PROJECT_ROOT, ProjectConfig


def _local_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return (path if path.is_absolute() else PROJECT_ROOT / path).resolve()


def _mapping(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object.")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string.")
    return value


def _read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Evaluation input file not found: {path}") from exc


def _read_records(details: dict, count_key: str, label: str) -> tuple[Path, list[dict]]:
    path = _local_path(_string(details.get("path"), f"{label}.path"))
    raw = _read_bytes(path)
    if hashlib.sha256(raw).hexdigest() != details.get("sha256"):
        raise ValueError(f"Checksum does not match evaluation manifest: {path}")
    count = details.get(count_key)
    if type(count) is not int or count <= 0:
        raise ValueError(f"{label}.{count_key} must be a positive integer.")
    records = []
    for number, line in enumerate(raw.splitlines(), 1):
        try:
            record = json.loads(line.decode("utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise ValueError(f"Invalid UTF-8 JSON in {path}, line {number}.") from exc
        records.append(_mapping(record, f"{path}, line {number}"))
    if len(records) != count:
        raise ValueError(f"Record count in {path} differs from manifest {label}.{count_key}.")
    return path, records


def load_eval_set(
    config: ProjectConfig,
    manifest_path: str | Path = "eval/sample_200/manifest.json",
) -> list[dict]:
    """Load verified questions, checking hashes, IDs, counts and exact quotes.

    All relative paths, including paths inside the manifest, are relative to
    PROJECT_ROOT, not the terminal directory or the manifest directory.
    Evidence offsets are Python Unicode character positions with an exclusive
    end. Missing/invalid inputs raise an error; no rows are silently skipped.
    split may be None, 'dev' or 'test'; this loader neither assigns nor filters it.
    """
    path = _local_path(manifest_path)
    try:
        manifest = json.loads(_read_bytes(path).decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ValueError(f"Invalid UTF-8 JSON in evaluation manifest: {path}") from exc
    manifest = _mapping(manifest, str(path))
    if type(manifest.get("format_version")) is not int or manifest["format_version"] != 2:
        raise ValueError(f"Unsupported evaluation format_version in {path}; expected 2.")
    dataset = _mapping(manifest.get("dataset"), f"{path}: dataset")
    if (dataset.get("repo_id") != config.dataset.repo_id
            or dataset.get("revision") != config.dataset.revision):
        raise ValueError(f"Evaluation dataset/revision differs from project configuration: {path}")
    source = _mapping(manifest.get("source"), f"{path}: source")
    questions = _mapping(manifest.get("questions"), f"{path}: questions")
    if source.get("text_field") != "text":
        raise ValueError(f"Expected source.text_field='text' in {path}.")
    if questions.get("review_status") != "verified":
        raise ValueError(f"Evaluation questions are not marked verified in {path}.")

    source_path, documents = _read_records(source, "document_count", f"{path}: source")
    question_path, records = _read_records(questions, "count", f"{path}: questions")
    texts = {}
    for number, document in enumerate(documents, 1):
        label = f"{source_path}, line {number}"
        doc_id = _string(document.get("doc_id"), f"{label}: doc_id")
        if doc_id in texts:
            raise ValueError(f"Duplicate doc_id {doc_id!r} in {label}.")
        texts[doc_id] = _string(document.get("text"), f"{label}: text")

    seen = set()
    fields = {"question_id", "question", "reference_answer", "evidence", "review_status", "split"}
    for number, question in enumerate(records, 1):
        label = f"{question_path}, line {number}"
        question_id = _string(question.get("question_id"), f"{label}: question_id")
        label = f"{label} ({question_id})"
        if question_id in seen:
            raise ValueError(f"Duplicate question_id {question_id!r} in {label}.")
        seen.add(question_id)
        if set(question) != fields:
            raise ValueError(f"{label} must contain exactly the six evaluation question fields.")
        _string(question["question"], f"{label}: question")
        _string(question["reference_answer"], f"{label}: reference_answer")
        if question["review_status"] != "verified":
            raise ValueError(f"{label} is not verified.")
        if question["split"] not in (None, "dev", "test"):
            raise ValueError(f"{label}: split must be null, 'dev' or 'test'.")
        evidence = question["evidence"]
        if not isinstance(evidence, list) or not evidence:
            raise ValueError(f"{label}: evidence must be a non-empty list.")
        for position, passage in enumerate(evidence):
            where = f"{label}: evidence[{position}]"
            passage = _mapping(passage, where)
            doc_id = _string(passage.get("doc_id"), f"{where}.doc_id")
            if doc_id not in texts:
                raise ValueError(f"{where}: doc_id {doc_id!r} does not exist in {source_path}.")
            quote = _string(passage.get("quote"), f"{where}.quote")
            start, end = passage.get("start_char"), passage.get("end_char")
            if (type(start) is not int or type(end) is not int
                    or not 0 <= start < end <= len(texts[doc_id])):
                raise ValueError(f"{where}: invalid offsets for document {doc_id!r}.")
            if texts[doc_id][start:end] != quote:
                raise ValueError(f"{where}: quote does not match document {doc_id!r} at [{start}:{end}].")
    return records
