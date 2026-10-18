"""Score ranked chunks against evidence spans in the same cleaned documents.

Document Recall counts distinct source documents. Hit and reciprocal rank
require a chunk to fully contain at least one annotated evidence passage.
These functions do not retrieve data, read files or call an embedding API.
"""

import math


def _validate_k(k: int) -> None:
    if type(k) is not int or k <= 0:
        raise ValueError("k must be a positive integer.")


def _validate_span(record: dict, label: str) -> None:
    if not isinstance(record, dict):
        raise ValueError(f"{label} must be an object.")
    doc_id = record.get("doc_id")
    if not isinstance(doc_id, str) or not doc_id.strip():
        raise ValueError(f"{label}.doc_id must be a non-empty string.")
    start, end = record.get("start_char"), record.get("end_char")
    if type(start) is not int or type(end) is not int or not 0 <= start < end:
        raise ValueError(f"{label} must have integer offsets with 0 <= start_char < end_char.")


def _validate_evidence(evidence: list[dict]) -> None:
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("evidence must be a non-empty list for an answerable question.")
    for position, passage in enumerate(evidence):
        _validate_span(passage, f"evidence[{position}]")


def _contains_evidence(chunk: dict, evidence: list[dict]) -> bool:
    return any(
        chunk["doc_id"] == passage["doc_id"]
        and chunk["start_char"] <= passage["start_char"]
        and chunk["end_char"] >= passage["end_char"]
        for passage in evidence
    )


def is_relevant_chunk(chunk: dict, evidence: list[dict]) -> bool:
    """Check full coverage of any evidence span, including equal boundaries.

    Offsets use Python text[start_char:end_char] within one cleaned document.
    Partial overlap, even across two chunks together, does not qualify here.
    Source text/quote integrity must be checked when loading evaluation data.
    """
    _validate_span(chunk, "chunk")
    _validate_evidence(evidence)
    return _contains_evidence(chunk, evidence)


def evaluate_query(hits: list[dict], evidence: list[dict], k: int = 5) -> dict[str, float]:
    """Score one query without changing the input order or records.

    hits must already be ranked best first. Only the first k chunks are used;
    do not refill after deduplicating doc_ids. Fewer than k hits is allowed.
    Empty hits yield zeros. Duplicate chunk_ids in top-k are an error, whereas
    different chunks from the same document are valid and count once in Recall.
    Scores from BM25, dense or RRF are not needed for these metrics.

    Hit/RR indicate at least one evidence passage, not a complete multi-source
    answer. RR is per-query; its average across queries is MRR.
    """
    _validate_k(k)
    _validate_evidence(evidence)
    if not isinstance(hits, list):
        raise ValueError("hits must be a ranked list of chunks.")
    top_hits = hits[:k]
    seen = set()
    for position, chunk in enumerate(top_hits):
        _validate_span(chunk, f"hits[{position}]")
        chunk_id = chunk.get("chunk_id")
        if not isinstance(chunk_id, str) or not chunk_id.strip() or chunk_id in seen:
            raise ValueError("Top-k hits must have non-empty, unique chunk_ids.")
        seen.add(chunk_id)

    required_docs = {passage["doc_id"] for passage in evidence}
    retrieved_docs = {chunk["doc_id"] for chunk in top_hits}
    first_rank = next(
        (rank for rank, chunk in enumerate(top_hits, 1)
         if _contains_evidence(chunk, evidence)),
        None,
    )
    return {
        f"recall@{k}": len(required_docs & retrieved_docs) / len(required_docs),
        f"hit@{k}": float(first_rank is not None),
        f"rr@{k}": 1.0 / first_rank if first_rank is not None else 0.0,
    }


def aggregate_metrics(per_query: list[dict], k: int = 5) -> dict[str, float]:
    """Average query scores equally; rename the mean of RR to MRR.

    A failed retrieval request is not a zero-score query: the evaluation runner
    must report that error. Do not silently omit failures from the summary.
    """
    _validate_k(k)
    if not isinstance(per_query, list) or not per_query:
        raise ValueError("per_query must be a non-empty list of query scores.")
    means = {}
    for metric in ("recall", "hit", "rr"):
        key = f"{metric}@{k}"
        values = []
        for row in per_query:
            value = row.get(key) if isinstance(row, dict) else None
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or not 0 <= value <= 1):
                raise ValueError(f"Each query must have a finite {key} score between 0 and 1.")
            values.append(value)
        output_key = f"mrr@{k}" if metric == "rr" else key
        means[output_key] = math.fsum(values) / len(values)
    return means
