"""Build/resume and query the pilot Chroma index using an external embedding API.

Run one builder at a time. A building index is never accepted by load_dense.
Stop all processes using Chroma before copying its directory and index manifest.
"""

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import tempfile

import chromadb
from chromadb.config import Settings
import numpy as np

from legal_rag.config import PROJECT_ROOT, ProjectConfig, load_config
from legal_rag.models.embedding import EmbeddingClient, MODEL, DIMENSIONS, QUERY_INSTRUCTION
from legal_rag.retrieval.bm25 import _check_chunks, _check_identity, _sha256


COLLECTION = "legal_sample_200"


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _write_manifest(path: Path, manifest: dict) -> None:
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".dense-manifest.", delete=False) as file:
        temporary = Path(file.name)
    try:
        temporary.write_text(_json(manifest) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _protocol(model_revision: str) -> dict:
    # Revision is declared by the operator; the endpoint must serve this exact
    # snapshot. The embeddings API cannot prove which weight revision is loaded.
    if (not isinstance(model_revision, str) or len(model_revision) != 40
            or any(c not in "0123456789abcdefABCDEF" for c in model_revision)):
        raise ValueError("model_revision must be the 40-character SHA actually served by vLLM.")
    return {
        "format_version": 1, "collection": COLLECTION,
        "model": MODEL, "model_revision": model_revision.lower(),
        "dimensions": DIMENSIONS, "document_format": "raw_text_v1",
        "query_instruction": QUERY_INSTRUCTION, "distance": "cosine",
        "chromadb_version": version("chromadb"),
    }


def _open_collection(directory: Path, fingerprint: str, create: bool):
    client = chromadb.PersistentClient(
        path=str(directory), settings=Settings(anonymized_telemetry=False)
    )
    if create:
        collection = client.get_or_create_collection(
            COLLECTION, embedding_function=None,
            metadata={"fingerprint": fingerprint},
            configuration={"hnsw": {"space": "cosine"}},
        )
    else:
        collection = client.get_collection(COLLECTION, embedding_function=None)
    if collection.metadata != {"fingerprint": fingerprint}:
        raise ValueError("Chroma collection belongs to another corpus or embedding configuration.")
    if collection.configuration["hnsw"]["space"] != "cosine":
        raise ValueError("Chroma must use cosine distance.")
    return client, collection


def _inventory(collection) -> tuple[dict[str, dict], str]:
    """Validate stored text/records/vectors and hash logical content, not live DB files."""
    records, hashes = {}, {}
    for offset in range(0, collection.count(), 128):
        page = collection.get(limit=128, offset=offset,
                              include=["documents", "metadatas", "embeddings"])
        for i, chunk_id in enumerate(page["ids"]):
            metadata = page["metadatas"][i]
            record = json.loads(metadata["chunk_json"])
            _check_chunks([record])
            if (record["chunk_id"] != chunk_id or chunk_id in records
                    or record["text"] != page["documents"][i]
                    or metadata["doc_id"] != record["doc_id"]):
                raise ValueError("Stored Chroma record does not match its ID/text/metadata.")
            vector = np.asarray(page["embeddings"][i], dtype="<f4")
            if vector.shape != (DIMENSIONS,) or not np.isfinite(vector).all() or not np.any(vector):
                raise ValueError(f"Invalid stored vector: {chunk_id}")
            records[chunk_id] = record
            h = hashlib.sha256(_json(record).encode("utf-8"))
            h.update(vector.tobytes())
            hashes[chunk_id] = h.hexdigest()
    digest = hashlib.sha256(_json(sorted(hashes.items())).encode("utf-8")).hexdigest()
    return records, digest


def build_dense(config: ProjectConfig, embedding_client: EmbeddingClient, *,
                model_revision: str) -> Path:
    """Build/resume with an exclusive writer lock (Linux local/Kaggle).

    model_revision must identify the actual weights served by the endpoint.
    """
    directory = PROJECT_ROOT / "data/indexes/sample_200"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".dense-build.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another dense builder is already running.") from None
        try:
            return _build_dense(config, embedding_client, model_revision=model_revision)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _build_dense(config: ProjectConfig, embedding_client: EmbeddingClient, *,
                 model_revision: str) -> Path:
    """Resume matching batches; publish ready only after validating the full collection.

    Original metadata including nulls/nested values is preserved in chunk_json,
    a JSON string inside Chroma metadata. No metadata filtering is enabled here.
    Existing data with another source/model signature is refused, never deleted.
    """
    protocol = _protocol(model_revision)
    source_dir = PROJECT_ROOT / "data/processed/sample_200"
    source = source_dir / "chunks.jsonl"
    source_manifest = json.loads((source_dir / "manifest.json").read_text(encoding="utf-8"))
    _check_identity(source_manifest, config)
    # Hash the same bytes we parse, avoiding a hash/read mismatch.
    raw = source.read_bytes()
    source_hash = hashlib.sha256(raw).hexdigest()
    chunking = source_manifest.get("chunking", {})
    if source_hash != chunking.get("output_sha256"):
        raise ValueError("Chunk source checksum differs from the chunking manifest.")
    chunks = [json.loads(line) for line in raw.splitlines()]
    _check_chunks(chunks)
    counts = {}
    for chunk in chunks:
        counts[chunk["doc_id"]] = counts.get(chunk["doc_id"], 0) + 1
    if (len(chunks) != chunking.get("total_chunks")
            or counts != chunking.get("chunks_per_document")
            or list(counts) != source_manifest.get("selected_ids")):
        raise ValueError("Chunk counts/IDs differ from the source manifest.")
    signature = {**protocol, "chunks_sha256": source_hash,
                 "repo_id": config.dataset.repo_id, "revision": config.dataset.revision}
    fingerprint = hashlib.sha256(_json(signature).encode("utf-8")).hexdigest()
    directory = PROJECT_ROOT / "data/indexes/sample_200"
    manifest_path = directory / "manifest.json"
    database = directory / "chroma"
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        _check_identity(manifest, config)
        if manifest.get("chunks_sha256") != source_hash:
            raise ValueError("Existing index manifest belongs to another corpus.")
    previous = manifest.get("dense")
    if previous is not None and previous.get("fingerprint") != fingerprint:
        raise ValueError("Existing dense index uses another embedding protocol; use a separate index.")
    if previous is not None and not database.is_dir():
        raise ValueError("Dense manifest exists but its Chroma directory is missing.")
    if previous is None and database.exists() and any(database.iterdir()):
        raise ValueError("Refusing to reuse an unregistered Chroma directory.")
    directory.mkdir(parents=True, exist_ok=True)
    client, collection = _open_collection(database, fingerprint, create=True)
    stored, integrity = _inventory(collection)
    expected = {c["chunk_id"]: c for c in chunks}
    if any(chunk_id not in expected or record != expected[chunk_id]
           for chunk_id, record in stored.items()):
        raise ValueError("Stored chunks differ from the current corpus.")
    if previous and previous.get("status") == "ready":
        if len(stored) != len(chunks) or integrity != previous.get("content_sha256"):
            raise ValueError("Completed dense index has changed or lost records.")
        print(f"Dense index already complete: {database}", flush=True)
        return database
    manifest.update(repo_id=config.dataset.repo_id, revision=config.dataset.revision,
                    chunks_sha256=source_hash)
    manifest["dense"] = {
        **protocol, "fingerprint": fingerprint, "status": "building",
        "chunk_count": len(chunks), "path": "chroma",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    _write_manifest(manifest_path, manifest)
    missing = [c for c in chunks if c["chunk_id"] not in stored]
    print(f"Dense index: {len(stored)} stored, {len(missing)} remaining.", flush=True)
    for start in range(0, len(missing), embedding_client.batch_size):
        batch = missing[start:start + embedding_client.batch_size]
        try:
            vectors = embedding_client.embed_documents([c["text"] for c in batch])
            collection.upsert(
                ids=[c["chunk_id"] for c in batch],
                documents=[c["text"] for c in batch], embeddings=vectors,
                metadatas=[{"doc_id": c["doc_id"], "chunk_json": _json(c)} for c in batch],
            )
        except Exception as exc:
            raise RuntimeError(
                f"Dense build failed at remaining batch {start // embedding_client.batch_size + 1}; "
                "completed batches are kept. Rerun with the same corpus/model to resume."
            ) from exc
        print(f"  Stored {collection.count()}/{len(chunks)} chunks.", flush=True)
    stored, integrity = _inventory(collection)
    if stored != expected:
        raise ValueError("Final Chroma records do not match the full corpus.")
    manifest["dense"].update(status="ready", content_sha256=integrity,
                             completed_at_utc=datetime.now(timezone.utc).isoformat())
    _write_manifest(manifest_path, manifest)
    print(f"Saved dense index: {database}\nStop the builder process before copying Chroma.", flush=True)
    return database


def load_dense(config: ProjectConfig, *, model_revision: str) -> dict:
    """Validate a complete local or copied Chroma corpus; source files are optional."""
    directory = PROJECT_ROOT / "data/indexes/sample_200"
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    _check_identity(manifest, config)
    details = manifest.get("dense", {})
    if details.get("status") != "ready":
        raise ValueError("Dense index is incomplete. Finish build_dense before searching.")
    protocol = _protocol(model_revision)
    if any(details.get(key) != value for key, value in protocol.items()):
        raise ValueError("Dense model/protocol/Chroma version mismatch.")
    signature = {**protocol, "chunks_sha256": manifest["chunks_sha256"],
                 "repo_id": config.dataset.repo_id, "revision": config.dataset.revision}
    fingerprint = hashlib.sha256(_json(signature).encode("utf-8")).hexdigest()
    if details.get("fingerprint") != fingerprint:
        raise ValueError("Dense fingerprint does not match its manifest.")
    database = directory / "chroma"
    if not (database / "chroma.sqlite3").is_file():
        raise ValueError("Missing Chroma database; copy the entire Chroma directory.")
    source = PROJECT_ROOT / "data/processed/sample_200/chunks.jsonl"
    if source.exists() and _sha256(source) != manifest["chunks_sha256"]:
        raise ValueError("Local chunks have changed; dense index is stale.")
    client, collection = _open_collection(database, fingerprint, create=False)
    records, integrity = _inventory(collection)
    if len(records) != details.get("chunk_count") or integrity != details.get("content_sha256"):
        raise ValueError("Dense content checksum/count mismatch.")
    return {"client": client, "collection": collection, "manifest": details}


def search_dense(index: dict, embedding_client: EmbeddingClient,
                 query: str, top_k: int = 5) -> list[dict]:
    """Return original chunks plus cosine distance and score=1-distance."""
    if type(top_k) is not int or top_k <= 0:
        raise ValueError("top_k must be a positive integer.")
    vector = embedding_client.embed_query(query)
    result = index["collection"].query(
        query_embeddings=[vector], n_results=min(top_k, index["collection"].count()),
        include=["documents", "metadatas", "distances"],
    )
    hits = []
    for i, chunk_id in enumerate(result["ids"][0]):
        record = json.loads(result["metadatas"][0][i]["chunk_json"])
        distance = float(result["distances"][0][i])
        if record["chunk_id"] != chunk_id or not math.isfinite(distance):
            raise ValueError("Invalid dense search result.")
        hits.append({**record, "distance": distance, "score": 1.0 - distance})
    return sorted(hits, key=lambda hit: (-hit["score"], hit["chunk_id"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build/resume the pilot Chroma index.")
    parser.add_argument("--base-url", default=os.environ.get("EMBEDDING_BASE_URL", "http://127.0.0.1:8000/v1"))
    parser.add_argument("--model-revision", required=True, help="Exact HF commit SHA served by vLLM.")
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()
    with EmbeddingClient(args.base_url, batch_size=args.batch_size,
                         api_key=os.environ.get("VLLM_API_KEY")) as embeddings:
        build_dense(load_config(), embeddings, model_revision=args.model_revision)
