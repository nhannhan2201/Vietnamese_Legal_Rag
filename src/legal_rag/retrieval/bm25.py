"""Build and search a text-only BM25 baseline for the pilot corpus.

Pickle is executable Python serialization: only load artifacts you trust.
Checksums detect accidental mismatches; they do not make untrusted pickle safe.
"""

from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import pickle
import tempfile
import unicodedata

from rank_bm25 import BM25Okapi

from legal_rag.config import PROJECT_ROOT, ProjectConfig


TOKENIZATION = "nfc_lower_whitespace_v1"
PARAMETERS = {"k1": 1.5, "b": 0.75, "epsilon": 0.25}


def tokenize(text: str) -> list[str]:
    """Normalize NFC, lowercase and split on whitespace, keeping punctuation."""
    return unicodedata.normalize("NFC", text).lower().split()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _check_identity(manifest: dict, config: ProjectConfig) -> None:
    for key, expected in (("repo_id", config.dataset.repo_id),
                          ("revision", config.dataset.revision)):
        if manifest.get(key) != expected:
            raise ValueError(f"Manifest does not match configured {key}.")


def _check_chunks(chunks: list[dict]) -> None:
    if not chunks:
        raise ValueError("The chunk corpus must not be empty.")
    seen = set()
    for position, chunk in enumerate(chunks):
        if not isinstance(chunk, dict):
            raise ValueError(f"Chunk {position} must be an object.")
        chunk_id = chunk.get("chunk_id")
        if not isinstance(chunk_id, str) or not chunk_id or chunk_id in seen:
            raise ValueError(f"Invalid or duplicate chunk_id at position {position}.")
        seen.add(chunk_id)
        if not isinstance(chunk.get("text"), str) or not tokenize(chunk["text"]):
            raise ValueError(f"Missing or empty text: {chunk_id}")
        if (not isinstance(chunk.get("doc_id"), str) or not chunk["doc_id"]
                or not isinstance(chunk.get("metadata"), dict)
                or str(chunk["metadata"].get("id")) != chunk["doc_id"]):
            raise ValueError(f"Invalid document identity or metadata: {chunk_id}")


def build_bm25(config: ProjectConfig) -> Path:
    """Build from the verified pilot chunks; preserve every original record."""
    source_dir = PROJECT_ROOT / "data/processed/sample_200"
    source_path = source_dir / "chunks.jsonl"
    source_manifest = json.loads((source_dir / "manifest.json").read_text(encoding="utf-8"))
    _check_identity(source_manifest, config)
    chunking = source_manifest.get("chunking", {})
    digest = hashlib.sha256()
    chunks = []
    print(f"Reading chunks from: {source_path}", flush=True)
    with source_path.open("rb") as file:
        for number, line in enumerate(file, 1):
            digest.update(line)
            try:
                chunks.append(json.loads(line))
            except (ValueError, UnicodeError) as exc:
                raise ValueError(f"Invalid JSON in {source_path}, line {number}.") from exc
    source_hash = digest.hexdigest()
    if source_hash != chunking.get("output_sha256"):
        raise ValueError("chunks.jsonl checksum differs from the chunking manifest.")
    _check_chunks(chunks)
    if len(chunks) != chunking.get("total_chunks"):
        raise ValueError("Chunk count differs from the chunking manifest.")
    counts = {}
    for chunk in chunks:
        doc_id = chunk["doc_id"]
        counts[doc_id] = counts.get(doc_id, 0) + 1
    if (counts != chunking.get("chunks_per_document")
            or list(counts) != source_manifest.get("selected_ids")):
        raise ValueError("Chunk document IDs/counts differ from the source manifest.")

    directory = PROJECT_ROOT / "data/indexes/sample_200"
    manifest_path = directory / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        _check_identity(manifest, config)
        if manifest.get("chunks_sha256") != source_hash:
            raise ValueError("Existing index manifest belongs to a different chunk corpus.")

    print(f"Building BM25 for {len(chunks)} chunks...", flush=True)
    bm25 = BM25Okapi([tokenize(chunk["text"]) for chunk in chunks], **PARAMETERS)
    if not all(math.isfinite(float(value)) for value in bm25.idf.values()):
        raise ValueError("BM25 produced non-finite token weights.")
    payload = {
        "format_version": 1, "bm25": bm25, "chunks": chunks,
        "chunks_sha256": source_hash, "tokenization": TOKENIZATION,
    }
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / "bm25.pkl"
    temporary = manifest_temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, prefix=".bm25.", delete=False) as file:
            temporary = Path(file.name)
            pickle.dump(payload, file, protocol=pickle.HIGHEST_PROTOCOL)
        manifest.update({
            "repo_id": config.dataset.repo_id, "revision": config.dataset.revision,
            "chunks_sha256": source_hash,
        })
        manifest["bm25"] = {
            "format_version": 1,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_path": str(source_path), "chunk_count": len(chunks),
            "tokenization": TOKENIZATION, "parameters": PARAMETERS,
            "rank_bm25_version": version("rank-bm25"),
            "artifact": "bm25.pkl", "artifact_sha256": _sha256(temporary),
        }
        with tempfile.NamedTemporaryFile(dir=directory, prefix=".bm25-manifest.", delete=False) as file:
            manifest_temporary = Path(file.name)
        manifest_temporary.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(destination)
        manifest_temporary.replace(manifest_path)
    finally:
        for path in (temporary, manifest_temporary):
            if path is not None:
                path.unlink(missing_ok=True)
    print(f"Saved BM25: {destination}", flush=True)
    print(f"Index manifest: {manifest_path}", flush=True)
    return destination


def load_bm25(config: ProjectConfig) -> dict:
    """Load a trusted artifact after verifying its index manifest and checksum.

    The source JSONL is not needed at query time. If it is present locally,
    reject a stale index whose source has changed.
    """
    directory = PROJECT_ROOT / "data/indexes/sample_200"
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    _check_identity(manifest, config)
    details = manifest.get("bm25", {})
    if (details.get("format_version") != 1
            or details.get("tokenization") != TOKENIZATION
            or details.get("parameters") != PARAMETERS
            or details.get("rank_bm25_version") != version("rank-bm25")):
        raise ValueError("Unsupported BM25 format, settings or library version; rebuild the index.")
    artifact = directory / "bm25.pkl"
    with artifact.open("rb") as file:
        digest = hashlib.file_digest(file, "sha256").hexdigest()
        if digest != details.get("artifact_sha256"):
            raise ValueError("BM25 artifact checksum differs from its manifest.")
        file.seek(0)
        index = pickle.load(file)
    if (not isinstance(index, dict) or index.get("format_version") != 1
            or index.get("tokenization") != TOKENIZATION
            or index.get("chunks_sha256") != manifest.get("chunks_sha256")
            or not isinstance(index.get("bm25"), BM25Okapi)
            or not isinstance(index.get("chunks"), list)):
        raise ValueError("BM25 artifact does not match the index manifest.")
    _check_chunks(index["chunks"])
    if not (len(index["chunks"]) == index["bm25"].corpus_size == details.get("chunk_count")):
        raise ValueError("BM25 positions do not match the stored chunks.")
    source = PROJECT_ROOT / "data/processed/sample_200/chunks.jsonl"
    if source.exists() and _sha256(source) != index["chunks_sha256"]:
        raise ValueError("Local chunks.jsonl has changed; the BM25 index is stale.")
    return index


def search_bm25(index: dict, query: str, top_k: int = 5) -> list[dict]:
    """Return original chunk fields plus score; ties retain corpus order."""
    if not isinstance(query, str) or not (tokens := tokenize(query)):
        raise ValueError("query must be a non-empty string.")
    if type(top_k) is not int or top_k <= 0:
        raise ValueError("top_k must be a positive integer.")
    bm25 = index["bm25"]
    if not any(token in bm25.idf for token in tokens):
        return []
    scores = bm25.get_scores(tokens)
    if not all(math.isfinite(float(score)) for score in scores):
        raise ValueError("BM25 returned non-finite scores.")
    positions = sorted(range(len(scores)), key=lambda i: (-float(scores[i]), i))[:top_k]
    return [{**index["chunks"][i], "score": float(scores[i])} for i in positions]


if __name__ == "__main__":
    from legal_rag.config import load_config

    build_bm25(load_config())
