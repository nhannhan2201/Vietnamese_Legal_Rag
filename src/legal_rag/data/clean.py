"""Convert sampled HTML documents to text while retaining IDs and metadata."""

from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import tempfile
import unicodedata

from legal_rag.config import PROJECT_ROOT, ProjectConfig


IGNORED_TAGS = {"script", "style", "head", "title", "svg", "noscript"}
BLOCK_TAGS = {
    "address", "article", "aside", "blockquote", "caption", "dd", "div", "dl",
    "dt", "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2",
    "h3", "h4", "h5", "h6", "header", "hr", "li", "main", "nav", "ol", "p",
    "pre", "section", "ul",
}


class _TableShapes(HTMLParser):
    """Identify single-cell layout wrappers separately from data tables."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[dict[str, int]] = []
        self.stack: list[int] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "table":
            self.stack.append(len(self.tables))
            self.tables.append({"rows": 0, "cells": 0})
        elif self.stack:
            if tag == "tr":
                self.tables[self.stack[-1]]["rows"] += 1
            elif tag in ("td", "th"):
                self.tables[self.stack[-1]]["cells"] += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self.stack:
            self.stack.pop()


class _TextExtractor(HTMLParser):
    """Preserve block boundaries and inline text without retaining HTML tags."""

    def __init__(self, shapes: list[dict[str, int]]) -> None:
        super().__init__(convert_charrefs=True)
        self.shapes = shapes
        self.table_index = -1
        self.tables: list[dict] = []
        self.hidden_depth = 0
        self.pre_depth = 0
        self.parts: list[str] = []

    def _inside_data_cell(self) -> bool:
        return any(not table["layout"] and table["in_cell"] for table in self.tables)

    def _block_boundary(self) -> None:
        self.parts.append(" " if self._inside_data_cell() else "\n")

    def handle_starttag(self, tag: str, attrs: list) -> None:
        # Count every table, even in ignored content, to match the shape pass.
        if tag == "table":
            self.table_index += 1
        if tag in IGNORED_TAGS:
            self.hidden_depth += 1
            return
        if self.hidden_depth:
            return
        if tag == "table":
            shape = self.shapes[self.table_index]
            self.parts.append("\n")
            self.tables.append({
                "layout": shape["rows"] <= 1 and shape["cells"] <= 1,
                "row_cells": 0,
                "in_cell": False,
            })
        elif tag == "tr":
            self.parts.append("\n")
            if self.tables:
                self.tables[-1]["row_cells"] = 0
                self.tables[-1]["in_cell"] = False
        elif tag in ("td", "th") and self.tables:
            table = self.tables[-1]
            if not table["layout"] and table["row_cells"]:
                self.parts.append("\t")
            table["row_cells"] += 1
            table["in_cell"] = True
        elif tag == "br":
            self._block_boundary()
        elif tag in BLOCK_TAGS:
            self._block_boundary()
            if tag == "pre":
                self.pre_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in IGNORED_TAGS:
            if self.hidden_depth:
                self.hidden_depth -= 1
            return
        if self.hidden_depth:
            return
        if tag == "table":
            if self.tables:
                self.tables.pop()
            self.parts.append("\n")
        elif tag == "tr":
            if self.tables:
                self.tables[-1]["in_cell"] = False
            self.parts.append("\n")
        elif tag in ("td", "th") and self.tables:
            self.tables[-1]["in_cell"] = False
        elif tag in BLOCK_TAGS:
            if tag == "pre" and self.pre_depth:
                self.pre_depth -= 1
            self._block_boundary()

    def handle_data(self, data: str) -> None:
        if self.hidden_depth:
            return
        # Source-code indentation is not a paragraph boundary. Inline tags
        # must not add spaces: <font>Ủ</font><font>y ban</font> is "Ủy ban".
        self.parts.append(data if self.pre_depth else re.sub(r"\s+", " ", data))


def html_to_text(html: str) -> str:
    """Extract NFC text, using newlines for blocks and tabs for table columns.

    A single-row, single-cell table is treated as a layout wrapper. Paragraphs
    inside data cells are flattened to spaces so the cell stays in its row.
    Images are not OCRed; lists retain their text without inferred numbering.
    """
    if not isinstance(html, str):
        raise TypeError("html_to_text() expects an HTML string.")
    shapes = _TableShapes()
    shapes.feed(html)
    shapes.close()
    parser = _TextExtractor(shapes.tables)
    parser.feed(html)
    parser.close()

    text = unicodedata.normalize("NFC", "".join(parser.parts))
    text = text.replace("\u200b", "").replace("\ufeff", "")
    lines = []
    for line in text.splitlines():
        # Normalize spaces within cells, preserving tabs (including empty cells).
        cells = [" ".join(cell.split()) for cell in line.split("\t")]
        if any(cells):
            lines.append("\t".join(cells))
    return "\n".join(lines)


def _write_manifest(path: Path, manifest: dict) -> None:
    with tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=".clean-manifest.", suffix=".tmp", delete=False
    ) as file:
        temporary = Path(file.name)
    try:
        temporary.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def clean_documents(config: ProjectConfig) -> Path:
    """Clean the pilot JSONL and append cleaning details to its manifest.

    The original sample and metadata are preserved. An empty output document
    is an error rather than a reason to silently remove its ID from the corpus.
    """
    directory = PROJECT_ROOT / "data/processed/sample_200"
    source_path = directory / "documents.jsonl"
    destination = directory / "cleaned_documents.jsonl"
    manifest_path = directory / "manifest.json"
    with manifest_path.open(encoding="utf-8") as file:
        manifest = json.load(file)
    for key, expected in (
        ("repo_id", config.dataset.repo_id), ("revision", config.dataset.revision)
    ):
        if manifest.get(key) != expected:
            raise ValueError(f"The sample manifest does not match configured {key}.")
    expected_ids = manifest.get("selected_ids")
    if (
        not isinstance(expected_ids, list)
        or any(not isinstance(value, str) or not value for value in expected_ids)
        or len(expected_ids) != len(set(expected_ids))
        or len(expected_ids) != manifest.get("sample_size")
        or not expected_ids
    ):
        raise ValueError("The sample manifest must contain a valid non-empty ID list.")

    input_digest = hashlib.sha256()
    output_digest = hashlib.sha256()
    ids = []
    seen = set()
    character_counts = []
    image_documents = []
    print(f"Cleaning documents from: {source_path}", flush=True)
    with tempfile.NamedTemporaryFile(
        dir=directory, prefix=".cleaned-documents.", suffix=".tmp", delete=False
    ) as file:
        temporary = Path(file.name)
    try:
        with source_path.open("rb") as source, temporary.open("wb") as output:
            for line_number, line in enumerate(source, start=1):
                input_digest.update(line)
                try:
                    document = json.loads(line)
                    if not isinstance(document, dict):
                        raise ValueError("Each JSONL line must contain an object.")
                    doc_id = document.get("doc_id")
                    metadata = document.get("metadata")
                    if not isinstance(doc_id, str) or not doc_id or doc_id in seen:
                        raise ValueError(f"Missing, invalid or duplicate doc_id: {doc_id!r}")
                    if not isinstance(metadata, dict) or str(metadata.get("id")) != doc_id:
                        raise ValueError(f"Metadata ID does not match doc_id: {doc_id}")
                    raw_html = document.get("content_html")
                    if not isinstance(raw_html, str):
                        raise ValueError(f"content_html must be a string: ID {doc_id}")
                    text = html_to_text(raw_html)
                    if not text.strip():
                        raise ValueError(f"Cleaning produced empty text: ID {doc_id}")
                    result = {"doc_id": doc_id, "text": text, "metadata": metadata}
                    encoded = (json.dumps(result, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
                    output.write(encoded)
                    output_digest.update(encoded)
                    ids.append(doc_id)
                    seen.add(doc_id)
                    character_counts.append(len(text))
                    if re.search(r"<img\b", raw_html, re.IGNORECASE):
                        image_documents.append(doc_id)
                except Exception as exc:
                    raise ValueError(f"Cannot clean {source_path}, line {line_number}: {exc}") from exc
                if line_number % 25 == 0:
                    print(f"  Cleaned {line_number} documents.", flush=True)

        if ids != expected_ids:
            raise ValueError("Document IDs or their order do not match the sample manifest.")
        if input_digest.hexdigest() != manifest.get("documents_sha256"):
            raise ValueError("documents.jsonl does not match the source checksum in its manifest.")

        manifest["cleaning"] = {
            "version": 1,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "input_path": str(source_path),
            "input_sha256": input_digest.hexdigest(),
            "output_path": str(destination),
            "output_sha256": output_digest.hexdigest(),
            "document_count": len(ids),
            "text_characters": {
                "minimum": min(character_counts),
                "maximum": max(character_counts),
                "total": sum(character_counts),
            },
            "table_format": "Newlines separate rows; tabs separate data cells; single-cell layout wrappers are unwrapped.",
            "documents_with_image_tags": image_documents,
            "quality_note": "Cleaning does not establish source completeness. Image text is not OCRed; HTML list numbering is not inferred.",
        }
        temporary.replace(destination)
        _write_manifest(manifest_path, manifest)
    finally:
        temporary.unlink(missing_ok=True)

    print(f"\nSaved {len(ids)} cleaned documents: {destination}", flush=True)
    print(f"Updated cleaning details in: {manifest_path}", flush=True)
    if image_documents:
        print(f"Review image content in {len(image_documents)} documents; IDs are recorded in the manifest.", flush=True)
    return destination


if __name__ == "__main__":
    from legal_rag.config import load_config

    clean_documents(load_config())
