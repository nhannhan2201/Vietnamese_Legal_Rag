"""Local RAG API. Startup loads resources; /ask reuses the existing pipeline.

Run: python -m uvicorn legal_rag.app.api:app --host 127.0.0.1 --port 8001
Each server worker has its own indexes and clients; use one worker for the demo.
"""

from contextlib import asynccontextmanager, ExitStack
import logging
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator

from legal_rag.config import load_config
from legal_rag.generation.answer import answer_question
from legal_rag.models.embedding import EmbeddingClient
from legal_rag.models.llm import LLMClient
from legal_rag.retrieval.hybrid import load_hybrid


logger = logging.getLogger(__name__)
Method = Literal["bm25", "dense", "hybrid"]
STATIC_DIR = Path(__file__).resolve().parent / "static"


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: StrictStr = Field(min_length=1)
    method: Method = "hybrid"

    @field_validator("question")
    @classmethod
    def nonempty_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question must not be blank.")
        return value.strip()


class AskResponse(BaseModel):
    question: str
    method: Method
    status: Literal["answered", "no_sources", "insufficient_context"]
    answer: str
    cited_source_ids: list[int]
    # Preserve complete chunk records, including optional retriever diagnostics.
    sources: list[dict[str, Any]]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize once per process; close HTTP pools even if setup fails."""
    with ExitStack() as resources:
        try:
            index = load_hybrid(load_config())
            embeddings = resources.enter_context(EmbeddingClient.from_env())
            llm = resources.enter_context(LLMClient.from_env())
        except Exception as exc:
            logger.error("RAG startup failed (%s).", type(exc).__name__)
            raise RuntimeError(
                "RAG startup failed. Check project configuration, index files and .env settings."
            ) from None
        app.state.rag = {"index": index, "embeddings": embeddings, "llm": llm}
        try:
            yield
        finally:
            app.state.rag = None


def create_app() -> FastAPI:
    """Creating/importing the app does not load indexes or call paid APIs."""
    application = FastAPI(
        title="Vietnamese Legal RAG", version="0.1.0", lifespan=lifespan,
        description="Hỏi đáp dựa trên corpus văn bản pháp luật đã lập chỉ mục.",
    )
    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @application.get("/", include_in_schema=False)
    def home() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})

    @application.get("/health")
    def health(request: Request) -> dict:
        """Local resource readiness only; no external API requests or billing."""
        if getattr(request.app.state, "rag", None) is None:
            raise HTTPException(status_code=503, detail="RAG resources are not ready.")
        return {"status": "ready"}

    # The RAG pipeline is synchronous. A normal def endpoint runs in FastAPI's
    # thread pool rather than blocking the async server event loop.
    @application.post("/ask", response_model=AskResponse)
    def ask(payload: AskRequest, request: Request) -> dict:
        runtime = getattr(request.app.state, "rag", None)
        if runtime is None:
            raise HTTPException(status_code=503, detail="RAG resources are not ready.")
        try:
            return answer_question(
                payload.question, runtime["index"], runtime["llm"],
                embedding_client=runtime["embeddings"], method=payload.method,
            )
        except (ValueError, RuntimeError) as exc:
            # Never echo provider response bodies, URLs, headers or secret keys.
            logger.error("RAG answer failed (%s).", type(exc).__name__)
            raise HTTPException(
                status_code=502,
                detail="RAG could not produce a valid answer. Check the embedding/LLM services and retry.",
            ) from None
        except Exception as exc:
            logger.error("Unexpected RAG error (%s).", type(exc).__name__)
            raise HTTPException(status_code=500, detail="Internal RAG error.") from None

    return application


app = create_app()
