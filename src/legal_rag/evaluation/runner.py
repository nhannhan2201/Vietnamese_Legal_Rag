"""Run the three retrieval methods against the approved pilot evaluation set.

The embedding endpoint must already be running. This module never builds an
index or generates answers. Run with python -m legal_rag.evaluation.runner.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from legal_rag.config import PROJECT_ROOT, ProjectConfig, load_config
from legal_rag.evaluation.dataset import load_eval_set
from legal_rag.evaluation.metrics import aggregate_metrics, evaluate_query
from legal_rag.models.embedding import EmbeddingClient
from legal_rag.retrieval.bm25 import search_bm25
from legal_rag.retrieval.dense import search_dense
from legal_rag.retrieval.hybrid import load_hybrid, search_hybrid


METHODS = ("bm25", "dense", "hybrid")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                        allow_nan=False) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _preflight(config: ProjectConfig) -> tuple[list[dict], dict, dict, dict]:
    """Check source-to-chunk-to-index identity before opening an API client."""
    paths = {
        "evaluation": PROJECT_ROOT / "eval/sample_200/manifest.json",
        "processed": PROJECT_ROOT / "data/processed/sample_200/manifest.json",
        "index": PROJECT_ROOT / "data/indexes/sample_200/manifest.json",
    }
    snapshots = {name: path.read_bytes() for name, path in paths.items()}
    manifests = {name: json.loads(raw) for name, raw in snapshots.items()}
    questions = load_eval_set(config)
    evaluation, processed, index_manifest = (
        manifests[name] for name in ("evaluation", "processed", "index")
    )
    for name, manifest in (("processed", processed), ("index", index_manifest)):
        if (manifest.get("repo_id") != config.dataset.repo_id
                or manifest.get("revision") != config.dataset.revision):
            raise ValueError(f"{name} manifest differs from configured dataset/revision.")
    chunking = processed.get("chunking", {})
    if evaluation["source"]["sha256"] != chunking.get("input_sha256"):
        raise ValueError("Evaluation evidence and chunks use different cleaned-source versions.")
    chunk_path = PROJECT_ROOT / "data/processed/sample_200/chunks.jsonl"
    with chunk_path.open("rb") as file:
        chunks_sha256 = hashlib.file_digest(file, "sha256").hexdigest()
    if (chunks_sha256 != chunking.get("output_sha256")
            or chunks_sha256 != index_manifest.get("chunks_sha256")):
        raise ValueError("Chunk corpus checksum differs from processed/index manifests.")
    index = load_hybrid(config)
    if (index["bm25"]["chunks_sha256"] != chunks_sha256
            or index["dense"]["manifest"] != index_manifest.get("dense")):
        raise ValueError("Loaded indexes differ from the evaluation corpus snapshot.")
    if any(path.read_bytes() != snapshots[name] for name, path in paths.items()):
        raise ValueError("An input manifest changed during evaluation setup; retry after indexing finishes.")
    identity = {
        "dataset": evaluation["dataset"],
        "questions_sha256": evaluation["questions"]["sha256"],
        "cleaned_source_sha256": evaluation["source"]["sha256"],
        "chunks_sha256": chunks_sha256,
        "manifest_sha256": {name: hashlib.sha256(raw).hexdigest()
                            for name, raw in snapshots.items()},
        "bm25": index_manifest["bm25"],
        "dense": index_manifest["dense"],
        "model": config.embedding.model,
        "model_revision": config.embedding.revision,
    }
    return questions, index, identity, {paths[name]: raw for name, raw in snapshots.items()}


def run_evaluation(
    config: ProjectConfig, *, k: int = 5, bm25_k: int = 20,
    dense_k: int = 20, rrf_k: int = 60,
) -> Path:
    """Measure independent searches and save a complete summary only on success.

    Warmup uses the first question once per method, outside measured results.
    Index loading, metric computation and output serialization are not timed.
    Dense/hybrid latency includes query embedding and network round trips.
    All approved questions are used; this is not an independent held-out test.
    """
    for name, value in (("k", k), ("bm25_k", bm25_k), ("dense_k", dense_k), ("rrf_k", rrf_k)):
        if type(value) is not int or value <= 0:
            raise ValueError(f"{name} must be a positive integer.")
    if bm25_k < k or dense_k < k:
        raise ValueError("bm25_k and dense_k must both be at least k.")
    print("Loading evaluation questions and indexes...", flush=True)
    questions, index, identity, snapshots = _preflight(config)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f") + "_" + uuid4().hex[:8]
    directory = PROJECT_ROOT / "results" / run_id
    directory.mkdir(parents=True, exist_ok=False)
    run_config = {
        "run_id": run_id, "started_at_utc": _now(), "status": "running",
        "methods": list(METHODS), "question_count": len(questions),
        "question_ids": [q["question_id"] for q in questions],
        "parameters": {"k": k, "bm25_k": bm25_k, "dense_k": dense_k, "rrf_k": rrf_k},
        "identity": identity, "completed_results": 0,
        "warmup": "First question once per method; excluded from results and timing.",
        "latency_scope": "Search call only; includes embedding/API/network for dense and hybrid.",
        "evaluation_scope": "All approved questions; dev/test not selected or assigned.",
        "execution_order": "Per question: bm25, dense, hybrid; no shared query vectors/results.",
    }
    _write_json(directory / "config.json", run_config)
    scores = {method: [] for method in METHODS}
    times = {method: [] for method in METHODS}
    phase, question_id, method = "client_setup", None, None
    try:
        with EmbeddingClient.from_env() as client:
            searches = {
                "bm25": lambda query: search_bm25(index["bm25"], query, top_k=k),
                "dense": lambda query: search_dense(index["dense"], client, query, top_k=k),
                "hybrid": lambda query: search_hybrid(
                    index, client, query, top_k=k, bm25_k=bm25_k,
                    dense_k=dense_k, rrf_k=rrf_k),
            }
            phase, question_id = "warmup", questions[0]["question_id"]
            for method in METHODS:
                print(f"Warmup: {method}", flush=True)
                searches[method](questions[0]["question"])
            with (directory / "retrieval.jsonl").open("x", encoding="utf-8") as output:
                phase = "retrieval"
                for number, question in enumerate(questions, 1):
                    question_id = question["question_id"]
                    for method in METHODS:
                        started = perf_counter()
                        hits = searches[method](question["question"])
                        elapsed_ms = (perf_counter() - started) * 1000
                        if not math.isfinite(elapsed_ms) or elapsed_ms < 0:
                            raise ValueError("Invalid retrieval duration.")
                        if len(hits) > k:
                            raise ValueError("Retriever returned more than the requested top-k.")
                        metrics = evaluate_query(hits, question["evidence"], k=k)
                        row = {
                            "question_id": question_id, "question": question["question"],
                            "method": method,
                            "hits": [{**hit, "rank": rank} for rank, hit in enumerate(hits, 1)],
                            "metrics": metrics, "latency_ms": elapsed_ms,
                        }
                        output.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
                        output.flush()
                        scores[method].append(metrics)
                        times[method].append(elapsed_ms)
                        run_config["completed_results"] += 1
                        print(f"[{number}/{len(questions)}] {question_id} {method}: "
                              f"hit={metrics[f'hit@{k}']:.0f}, {elapsed_ms:.1f} ms", flush=True)
        phase, question_id, method = "summary", None, None
        if any(path.read_bytes() != raw for path, raw in snapshots.items()):
            raise ValueError("An input manifest changed during the run.")
        summary = {
            method: {**aggregate_metrics(scores[method], k=k),
                     "avg_latency_ms": math.fsum(times[method]) / len(times[method]),
                     "question_count": len(scores[method])}
            for method in METHODS
        }
        _write_json(directory / "summary.json", summary)
        run_config.update(status="completed", completed_at_utc=_now())
        _write_json(directory / "config.json", run_config)
    except (Exception, KeyboardInterrupt) as exc:
        # API exception strings may contain endpoint/request details. Persist and
        # report only safe context and the exception type, never credentials.
        run_config.update(status="failed", failed_at_utc=_now(), error={
            "phase": phase, "question_id": question_id, "method": method,
            "type": type(exc).__name__,
        })
        (directory / "summary.json").unlink(missing_ok=True)
        _write_json(directory / "config.json", run_config)
        message = (f"Evaluation failed: phase={phase}, question={question_id}, method={method}, "
                   f"error={type(exc).__name__}. Partial results: {directory}")
        raise RuntimeError(message) from None
    print("\nSummary:", flush=True)
    for method, result in summary.items():
        print(f"{method}: Recall@{k}={result[f'recall@{k}']:.4f}, "
              f"Hit@{k}={result[f'hit@{k}']:.4f}, MRR@{k}={result[f'mrr@{k}']:.4f}, "
              f"average={result['avg_latency_ms']:.1f} ms", flush=True)
    print(f"Saved evaluation results: {directory}", flush=True)
    return directory


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate BM25, dense and hybrid retrieval.")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--bm25-k", type=int, default=20)
    parser.add_argument("--dense-k", type=int, default=20)
    parser.add_argument("--rrf-k", type=int, default=60)
    args = parser.parse_args()
    run_evaluation(load_config(), k=args.k, bm25_k=args.bm25_k,
                   dense_k=args.dense_k, rrf_k=args.rrf_k)
