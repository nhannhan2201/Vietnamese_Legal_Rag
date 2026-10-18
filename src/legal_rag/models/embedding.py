"""HTTP client for the project's Qwen embedding service; no local model loading."""

import math
import os
from types import TracebackType

import httpx
from dotenv import dotenv_values

from legal_rag.config import PROJECT_ROOT


MODEL = "Qwen/Qwen3-Embedding-0.6B"
DIMENSIONS = 1024
QUERY_INSTRUCTION = (
    "Given a Vietnamese legal question, retrieve relevant legal passages "
    "that answer the question."
)


class EmbeddingClient:
    """Reuse one connection pool for document batches and query embeddings.

    base_url includes /v1, for example http://127.0.0.1:8000/v1.
    Queries get an instruction here; the server must not add another one.
    Returned vectors are validated but never normalized or otherwise changed.
    """

    @classmethod
    def from_env(cls, *, base_url: str | None = None,
                 batch_size: int = 16) -> "EmbeddingClient":
        """Read the project .env directly, without changing os.environ.

        Explicit base_url wins, then values in .env, then process environment.
        A present but blank .env value is an error, not a silent fallback to an
        old exported URL/key. Use the normal constructor for anonymous APIs.
        """
        settings = dotenv_values(PROJECT_ROOT / ".env", interpolate=False)
        url = base_url if base_url is not None else settings.get(
            "EMBEDDING_BASE_URL", os.environ.get("EMBEDDING_BASE_URL")
        )
        key = settings.get("VLLM_API_KEY", os.environ.get("VLLM_API_KEY"))
        if not isinstance(url, str) or not url.strip():
            raise ValueError("Set EMBEDDING_BASE_URL in the project .env file or environment.")
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Set VLLM_API_KEY in the project .env file or environment.")
        return cls(url, batch_size=batch_size, api_key=key)

    def __init__(self, base_url: str, *, batch_size: int = 16,
                 api_key: str | None = None) -> None:
        if not isinstance(base_url, str) or not base_url.strip():
            raise ValueError("base_url must be a non-empty HTTP(S) URL including /v1.")
        url = httpx.URL(base_url.strip())
        if (url.scheme not in ("http", "https") or not url.host
                or url.query or url.fragment or url.userinfo):
            raise ValueError("base_url must be HTTP(S), without credentials, query or fragment.")
        if type(batch_size) is not int or batch_size <= 0:
            raise ValueError("batch_size must be a positive integer.")
        if api_key is not None and (not isinstance(api_key, str) or not api_key.strip()):
            raise ValueError("api_key must be a non-empty string when provided.")
        self.batch_size = batch_size
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.Client(
            base_url=str(url).rstrip("/") + "/",
            headers=headers,
            timeout=httpx.Timeout(connect=5.0, read=60.0, write=60.0, pool=5.0),
            trust_env=False,
        )

    def __enter__(self) -> "EmbeddingClient":
        return self

    def __exit__(self, exc_type: type[BaseException] | None,
                 exc_value: BaseException | None,
                 traceback: TracebackType | None) -> None:
        self.close()

    def close(self) -> None:
        """Close the HTTP connection pool; safe to call more than once."""
        self._client.close()

    @staticmethod
    def _validate_text(text: str, label: str) -> None:
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"{label} must be a non-empty string.")

    def _embed_batch(self, texts: list[str], label: str) -> list[list[float]]:
        try:
            response = self._client.post(
                "embeddings",
                json={"model": MODEL, "input": texts, "encoding_format": "float"},
            )
            response.raise_for_status()
        except httpx.TimeoutException:
            raise RuntimeError(f"{label}: embedding API timed out; no retry was attempted.") from None
        except httpx.HTTPStatusError as exc:
            # Do not echo response bodies, input text or authentication headers.
            raise RuntimeError(f"{label}: embedding API returned HTTP {exc.response.status_code}.") from None
        except httpx.RequestError:
            raise RuntimeError(f"{label}: could not reach the embedding API.") from None

        try:
            payload = response.json()
        except ValueError:
            raise ValueError(f"{label}: embedding API returned invalid JSON.") from None
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list) or len(data) != len(texts):
            raise ValueError(f"{label}: response vector count does not match input count.")
        ordered: list[list[float] | None] = [None] * len(texts)
        for record in data:
            if not isinstance(record, dict):
                raise ValueError(f"{label}: each embedding record must be an object.")
            index = record.get("index")
            if (type(index) is not int or not 0 <= index < len(texts)
                    or ordered[index] is not None):
                raise ValueError(f"{label}: invalid or duplicate embedding index.")
            vector = record.get("embedding")
            if not isinstance(vector, list) or len(vector) != DIMENSIONS:
                raise ValueError(f"{label}: each vector must have {DIMENSIONS} dimensions.")
            try:
                valid = all(
                    type(value) in (int, float) and math.isfinite(value)
                    for value in vector
                )
            except OverflowError:
                valid = False
            if not valid or not any(value != 0 for value in vector):
                raise ValueError(f"{label}: vector must contain finite numbers and not be all zero.")
            ordered[index] = vector
        # Count + unique in-range indices guarantee every slot is filled.
        return [vector for vector in ordered if vector is not None]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed unchanged document text in sequential batches, preserving order."""
        if not isinstance(texts, list):
            raise ValueError("texts must be a list of non-empty strings.")
        for position, text in enumerate(texts):
            self._validate_text(text, f"Document at index {position}")
        vectors = []
        for start in range(0, len(texts), self.batch_size):
            end = min(start + self.batch_size, len(texts))
            label = f"Document batch {start // self.batch_size + 1} (input indices {start}:{end})"
            vectors.extend(self._embed_batch(texts[start:end], label))
        return vectors

    def embed_query(self, question: str) -> list[float]:
        """Format one raw question exactly once and return its embedding."""
        self._validate_text(question, "question")
        text = f"Instruct: {QUERY_INSTRUCTION}\nQuery: {question}"
        return self._embed_batch([text], "Query batch 1")[0]
