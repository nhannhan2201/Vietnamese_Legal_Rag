"""Combine text-only BM25 and dense rankings using reciprocal rank fusion.

No new index is built. Load the two existing indexes once, then reuse them.
Ranks start at 1. Each list contributes 1 / (rrf_k + rank), with equal weight.
Raw BM25 and cosine scores are kept for inspection, never added together.
"""

import json
import math

from legal_rag.config import PROJECT_ROOT, ProjectConfig
from legal_rag.models.embedding import EmbeddingClient
from legal_rag.retrieval.bm25 import load_bm25, search_bm25
from legal_rag.retrieval.dense import load_dense, search_dense


def _positive_integer(value: int, name: str) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer.")


def load_hybrid(config: ProjectConfig) -> dict:
    """Load verified indexes for the same corpus, without calling the API.

    The existing loaders check dataset, revision, checksums and index settings.
    Refuse a manifest changed during loading rather than mix index versions.
    """
    path = PROJECT_ROOT / "data/indexes/sample_200/manifest.json"
    before = path.read_bytes()
    manifest = json.loads(before)
    bm25 = load_bm25(config)
    dense = load_dense(config)
    if path.read_bytes() != before:
        raise ValueError("Index manifest changed while loading; retry after indexing finishes.")
    if (bm25["chunks_sha256"] != manifest.get("chunks_sha256")
            or dense["manifest"] != manifest.get("dense")
            or len(bm25["chunks"]) != dense["manifest"].get("chunk_count")):
        raise ValueError("BM25 and dense indexes do not describe the same chunk corpus.")
    return {"bm25": bm25, "dense": dense}


def reciprocal_rank_fusion(bm25_hits: list[dict], dense_hits: list[dict], *,
                           top_k: int = 5, rrf_k: int = 60) -> list[dict]:
    """Fuse already ranked candidates; return each chunk_id at most once.

    Empty lists are allowed. Duplicate IDs within one list are rejected to
    prevent counting one retriever twice. Matching IDs across lists must have
    identical source records. Equal RRF scores are ordered by chunk_id.
    Neither input list nor its records are modified.
    """
    _positive_integer(top_k, "top_k")
    _positive_integer(rrf_k, "rrf_k")
    records, details = {}, {}
    for name, hits in (("bm25", bm25_hits), ("dense", dense_hits)):
        seen = set()
        for rank, hit in enumerate(hits, 1):
            chunk_id = hit.get("chunk_id")
            if not isinstance(chunk_id, str) or not chunk_id or chunk_id in seen:
                raise ValueError(f"Invalid or duplicate chunk_id in {name} results.")
            seen.add(chunk_id)
            score = hit.get("score")
            if (isinstance(score, bool) or not isinstance(score, (int, float))
                    or not math.isfinite(score)):
                raise ValueError(f"Invalid {name} score for {chunk_id}.")
            # These are the only search-specific fields added by our retrievers.
            record = {key: value for key, value in hit.items()
                      if key not in ("score", "distance")}
            if (not isinstance(record.get("doc_id"), str)
                    or not record["doc_id"]
                    or not isinstance(record.get("text"), str)
                    or not record["text"].strip()
                    or not isinstance(record.get("metadata"), dict)):
                raise ValueError(f"Invalid source record for {chunk_id}.")
            if chunk_id in records and records[chunk_id] != record:
                raise ValueError(f"Different source records share chunk_id {chunk_id}.")
            records[chunk_id] = record
            if chunk_id not in details:
                details[chunk_id] = {
                    "score": 0.0,
                    "bm25_rank": None, "dense_rank": None,
                    "bm25_score": None, "dense_score": None,
                }
            details[chunk_id]["score"] += 1.0 / (rrf_k + rank)
            details[chunk_id][f"{name}_rank"] = rank
            details[chunk_id][f"{name}_score"] = float(score)
    ordered = sorted(records, key=lambda cid: (-details[cid]["score"], cid))[:top_k]
    return [{**records[cid], **details[cid]} for cid in ordered]


def search_hybrid(index: dict, embedding_client: EmbeddingClient,
                  query: str, top_k: int = 5, *, bm25_k: int = 20,
                  dense_k: int = 20, rrf_k: int = 60) -> list[dict]:
    """Retrieve candidates sequentially, fuse by rank and return top-k chunks.

    Use an index returned by load_hybrid. By default each retriever supplies
    up to 20 candidates and fusion returns 5 unique chunks. Candidate depths
    must be at least top_k; a small corpus can still return fewer results.
    A missing candidate contributes zero from that list. Retrieval/API errors
    propagate; no silent fallback to one retriever. Metadata is not filtered.
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string.")
    for name, value in (("top_k", top_k), ("bm25_k", bm25_k),
                        ("dense_k", dense_k), ("rrf_k", rrf_k)):
        _positive_integer(value, name)
    if bm25_k < top_k or dense_k < top_k:
        raise ValueError("bm25_k and dense_k must both be at least top_k.")
    bm25_hits = search_bm25(index["bm25"], query, top_k=bm25_k)
    dense_hits = search_dense(index["dense"], embedding_client, query, top_k=dense_k)
    return reciprocal_rank_fusion(bm25_hits, dense_hits, top_k=top_k, rrf_k=rrf_k)
