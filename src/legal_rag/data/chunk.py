"""Split cleaned pilot documents, preserving source offsets and metadata."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import re
import tempfile

from langchain_text_splitters import RecursiveCharacterTextSplitter

from legal_rag.config import PROJECT_ROOT, ProjectConfig


# Horizontal whitespace only: a heading must fit on one source line.
_ARTICLE = re.compile(r"^[ \t]*Điều[ \t]+\d+[a-zđ]?(?:[ \t]*[.:](?:[ \t].*|$)|[ \t]*)$", re.I)
_STRUCTURE = re.compile(
    r"^[ \t]*(?:(?:Chương|Mục|Phần)[ \t]+(?:[IVXLCDM]+|\d+[a-zđ]?|thứ[ \t]+\w+)(?:[ \t.:].*)?|Phụ[ \t]+lục(?:[ \t.:].*)?)$",
    re.I,
)
_APPENDIX = re.compile(r"^[ \t]*Phụ[ \t]+lục\b", re.I)


@dataclass(frozen=True)
class _Section:
    start: int
    end: int
    heading: str | None


def _sections(text: str) -> list[_Section]:
    """Keep preamble separate; carry structural headings into following text.

    A structural heading plus its title lines is carried into the first article
    if no body paragraph intervenes. This is a formatting heuristic, not a legal
    parser. Every source character remains inside a section.
    """
    result = []
    start = 0
    heading = None
    pending_structure = False
    offset = 0
    for line in text.splitlines(keepends=True):
        title = line.rstrip("\r\n")
        article = bool(_ARTICLE.fullmatch(title))
        structure = bool(_STRUCTURE.fullmatch(title))
        if article or structure:
            # Consecutive structural/title lines belong with the next article.
            carry = pending_structure and not (structure and _APPENDIX.match(title))
            if not carry and offset > start:
                result.append(_Section(start, offset, heading))
                start = offset
            heading = title.strip()
            pending_structure = structure
        elif pending_structure and title.strip():
            # Uppercase title lines remain attached; body text ends the pending
            # heading sequence, so a subsequent article starts its own section.
            if not title.strip().isupper():
                pending_structure = False
        offset += len(line)
    if start < len(text):
        result.append(_Section(start, len(text), heading))
    return result


def _document_chunks(document: dict, splitter: RecursiveCharacterTextSplitter,
                     chunk_size: int) -> list[dict]:
    text = document["text"]
    chunks = []
    covered_end = 0
    for section in _sections(text):
        section_text = text[section.start:section.end]
        for piece in splitter.create_documents([section_text]):
            local_start = piece.metadata["start_index"]
            start = section.start + local_start
            end = start + len(piece.page_content)
            if local_start < 0 or text[start:end] != piece.page_content:
                raise ValueError("Splitter returned an invalid source offset.")
            if not piece.page_content.strip() or len(piece.page_content) > chunk_size:
                raise ValueError("Splitter returned an empty or oversized chunk.")
            if start > covered_end and text[covered_end:start].strip():
                raise ValueError("Chunking left non-whitespace source text uncovered.")
            covered_end = max(covered_end, end)
            index = len(chunks)
            chunks.append({
                "chunk_id": f"{document['doc_id']}_chunk_{index:04d}",
                "doc_id": document["doc_id"],
                "chunk_index": index,
                "section_heading": section.heading,
                "start_char": start,
                "end_char": end,
                "text": piece.page_content,
                "metadata": document["metadata"],
            })
    if not chunks or text[covered_end:].strip():
        raise ValueError("Document is empty or its final content was not covered.")
    return chunks


def chunk_documents(config: ProjectConfig, chunk_size: int = 1000,
                    chunk_overlap: int = 200) -> Path:
    """Write deterministic chunks after validating the cleaned pilot inputs.

    Sizes and offsets count Python characters, not embedding-model tokens.
    This function processes the fixed sample_200 corpus only.
    """
    if (type(chunk_size) is not int or type(chunk_overlap) is not int
            or chunk_size <= 0 or not 0 <= chunk_overlap < chunk_size):
        raise ValueError("Require integer chunk_size > 0 and 0 <= overlap < size.")
    directory = PROJECT_ROOT / "data/processed/sample_200"
    source_path = directory / "cleaned_documents.jsonl"
    output_path = directory / "chunks.jsonl"
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for key, expected in (("repo_id", config.dataset.repo_id),
                          ("revision", config.dataset.revision)):
        if manifest.get(key) != expected:
            raise ValueError(f"Sample manifest does not match configured {key}.")
    expected_ids = manifest.get("selected_ids")
    if (not isinstance(expected_ids, list) or not expected_ids
            or any(not isinstance(i, str) or not i for i in expected_ids)
            or len(set(expected_ids)) != len(expected_ids)
            or len(expected_ids) != manifest.get("sample_size")):
        raise ValueError("Invalid selected_ids in sample manifest.")
    cleaning = manifest.get("cleaning")
    if not isinstance(cleaning, dict) or cleaning.get("document_count") != len(expected_ids):
        raise ValueError("Missing or inconsistent cleaning manifest.")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""], keep_separator=True,
        length_function=len, add_start_index=True,
    )
    input_hash, output_hash = hashlib.sha256(), hashlib.sha256()
    counts = {}
    seen_chunks = set()
    print(f"Chunking documents from: {source_path}", flush=True)
    with tempfile.NamedTemporaryFile(dir=directory, prefix=".chunks.", delete=False) as file:
        temporary = Path(file.name)
    manifest_temporary = None
    try:
        with source_path.open("rb") as source, temporary.open("wb") as output:
            for line_number, line in enumerate(source, 1):
                input_hash.update(line)
                try:
                    document = json.loads(line)
                    doc_id = document.get("doc_id")
                    if not isinstance(doc_id, str) or not doc_id or doc_id in counts:
                        raise ValueError("Invalid or duplicate doc_id.")
                    if not isinstance(document.get("text"), str) or not document["text"].strip():
                        raise ValueError("Missing nonempty cleaned text.")
                    metadata = document.get("metadata")
                    if not isinstance(metadata, dict) or str(metadata.get("id")) != doc_id:
                        raise ValueError("Metadata ID does not match doc_id.")
                    chunks = _document_chunks(document, splitter, chunk_size)
                    for chunk in chunks:
                        if chunk["chunk_id"] in seen_chunks:
                            raise ValueError("Duplicate chunk_id.")
                        seen_chunks.add(chunk["chunk_id"])
                        encoded = (json.dumps(chunk, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
                        output.write(encoded)
                        output_hash.update(encoded)
                    counts[doc_id] = len(chunks)
                except Exception as exc:
                    raise ValueError(f"Cannot chunk {source_path}, line {line_number}: {exc}") from exc
                if line_number % 25 == 0:
                    print(f"  Chunked {line_number} documents.", flush=True)
        if list(counts) != expected_ids:
            raise ValueError("Cleaned document IDs/order differ from sample manifest.")
        if input_hash.hexdigest() != cleaning.get("output_sha256"):
            raise ValueError("Cleaned input checksum differs from cleaning manifest.")
        manifest["chunking"] = {
            "version": 1,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "chunk_size": chunk_size, "chunk_overlap": chunk_overlap,
            "length_unit": "Python characters",
            "separators": ["\n\n", "\n", " ", ""], "keep_separator": True,
            "langchain_text_splitters_version": version("langchain-text-splitters"),
            "input_path": str(source_path), "input_sha256": input_hash.hexdigest(),
            "output_path": str(output_path), "output_sha256": output_hash.hexdigest(),
            "document_count": len(counts), "total_chunks": sum(counts.values()),
            "chunks_per_document": counts,
            "structure_rule": "Line-start article/structural headings; no overlap between sections.",
            "quality_note": "Formatting heuristics only. Validate model token limits before embedding; existing image/list limitations remain.",
        }
        with tempfile.NamedTemporaryFile(dir=directory, prefix=".chunk-manifest.", delete=False) as file:
            manifest_temporary = Path(file.name)
        manifest_temporary.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(output_path)
        manifest_temporary.replace(manifest_path)
    finally:
        temporary.unlink(missing_ok=True)
        if manifest_temporary is not None:
            manifest_temporary.unlink(missing_ok=True)
    print(f"Saved {sum(counts.values())} chunks: {output_path}", flush=True)
    print(f"Updated chunking details in: {manifest_path}", flush=True)
    return output_path


if __name__ == "__main__":
    from legal_rag.config import load_config

    chunk_documents(load_config())
