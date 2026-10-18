"""Text chat client for an OpenAI-compatible API, configured through LLM_*.

The caller supplies messages, including retrieved sources when doing RAG.
This client does not retrieve chunks, construct a RAG prompt or verify citations.
"""

import os
from types import TracebackType

import httpx
from dotenv import dotenv_values

from legal_rag.config import PROJECT_ROOT


class LLMClient:
    """Reuse one HTTP connection pool for non-streaming text completions."""

    @classmethod
    def from_env(cls) -> "LLMClient":
        """Read project .env first, then environment for keys absent from .env.

        Blank values in .env are errors, not fallbacks to stale terminal exports.
        Nothing is written to os.environ and secret values are never logged.
        """
        settings = dotenv_values(PROJECT_ROOT / ".env", interpolate=False)
        values = {}
        for name in ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY"):
            value = settings.get(name, os.environ.get(name))
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Set {name} in the project .env file or environment.")
            values[name] = value.strip()
        return cls(base_url=values["LLM_BASE_URL"], model=values["LLM_MODEL"],
                   api_key=values["LLM_API_KEY"])

    def __init__(self, base_url: str, model: str, api_key: str) -> None:
        """base_url includes /v1, without /chat/completions."""
        if not isinstance(base_url, str) or not base_url.strip():
            raise ValueError("base_url must be a non-empty HTTP(S) URL.")
        try:
            url = httpx.URL(base_url.strip())
        except httpx.InvalidURL:
            raise ValueError("base_url is not a valid HTTP(S) URL.") from None
        if (url.scheme not in ("http", "https") or not url.host
                or url.userinfo or url.query or url.fragment):
            raise ValueError("base_url must be HTTP(S), without credentials, query or fragment.")
        if url.path.rstrip("/").endswith("/chat/completions"):
            raise ValueError("base_url must not include /chat/completions.")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a non-empty string.")
        if (not isinstance(api_key, str) or not api_key.strip()
                or "\n" in api_key or "\r" in api_key):
            raise ValueError("api_key must be a non-empty, single-line string.")
        self.model = model.strip()
        self._client = httpx.Client(
            base_url=str(url).rstrip("/") + "/",
            headers={"Authorization": f"Bearer {api_key.strip()}"},
            timeout=httpx.Timeout(connect=5.0, read=120.0, write=60.0, pool=5.0),
            trust_env=False,
        )

    def __enter__(self) -> "LLMClient":
        return self

    def __exit__(self, exc_type: type[BaseException] | None,
                 exc_value: BaseException | None,
                 traceback: TracebackType | None) -> None:
        self.close()

    def close(self) -> None:
        """Close connections; safe to call repeatedly."""
        self._client.close()

    def generate(self, messages: list[dict], *, max_tokens: int = 1024) -> str:
        """Send supplied text messages and return the first assistant answer.

        Messages are not rewritten. Only text system/user/assistant messages are
        supported in this initial client; no tools, streaming or automatic retry.
        Empty, malformed or explicitly truncated responses raise errors rather
        than being silently accepted as complete answers.
        """
        if not isinstance(messages, list) or not messages:
            raise ValueError("messages must be a non-empty list.")
        for position, message in enumerate(messages):
            if not isinstance(message, dict) or set(message) != {"role", "content"}:
                raise ValueError(f"messages[{position}] must contain role and content only.")
            if message["role"] not in ("system", "user", "assistant"):
                raise ValueError(f"messages[{position}] has an unsupported role.")
            if not isinstance(message["content"], str) or not message["content"].strip():
                raise ValueError(f"messages[{position}].content must be a non-empty string.")
        if not any(message["role"] == "user" for message in messages):
            raise ValueError("messages must include a user message.")
        if type(max_tokens) is not int or max_tokens <= 0:
            raise ValueError("max_tokens must be a positive integer.")
        try:
            response = self._client.post("chat/completions", json={
                "model": self.model, "messages": messages,
                "max_tokens": max_tokens, "stream": False,
            })
            response.raise_for_status()
        except httpx.TimeoutException:
            raise RuntimeError("LLM API timed out; no retry was attempted.") from None
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"LLM API returned HTTP {exc.response.status_code}.") from None
        except httpx.RequestError:
            raise RuntimeError("Could not reach the LLM API.") from None
        try:
            payload = response.json()
        except ValueError:
            raise ValueError("LLM API returned invalid JSON.") from None
        choices = payload.get("choices") if isinstance(payload, dict) else None
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ValueError("LLM API response has no valid choices.")
        choice = choices[0]
        if choice.get("finish_reason") == "length":
            raise RuntimeError("LLM answer was truncated; increase max_tokens before trying again.")
        if choice.get("finish_reason") not in (None, "stop"):
            raise ValueError("LLM API did not finish a normal text answer.")
        message = choice.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            raise ValueError("LLM API response has no valid assistant message.")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("LLM API returned an empty or non-text answer.")
        return content
