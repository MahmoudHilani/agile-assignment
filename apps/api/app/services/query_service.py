from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.domain.models import ChatTurn, SearchResult
from app.services.document_service import search_documents


class LLMProviderError(RuntimeError):
    pass


class OllamaGenerateProvider:
    def __init__(self, url: str, model: str, timeout_seconds: float = 30.0) -> None:
        self._url = url
        self._model = model
        self._timeout_seconds = timeout_seconds

    def generate(
        self,
        prompt: str,
        context: Sequence[SearchResult],
        history: Sequence[ChatTurn],
    ) -> str:
        try:
            response = httpx.post(
                self._url,
                json={"model": self._model, "prompt": prompt, "stream": False},
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMProviderError("LLM provider failed") from exc

        answer = _extract_answer(response.json())
        if not answer.strip():
            raise LLMProviderError("LLM provider returned an empty answer")
        return answer


def get_chat_provider(settings: Settings | None = None) -> OllamaGenerateProvider:
    resolved_settings = settings or get_settings()
    if not resolved_settings.ollama_url or not resolved_settings.model_name:
        raise LLMProviderError("LLM provider is not configured")
    return OllamaGenerateProvider(
        url=resolved_settings.ollama_url,
        model=resolved_settings.model_name,
        timeout_seconds=resolved_settings.llm_timeout_seconds,
    )


def run_rag_query(query: str, top_k: int) -> tuple[str, list[str]]:
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("Query cannot be empty")
    if top_k < 1 or top_k > 25:
        raise ValueError("top_k must be between 1 and 25")

    results = search_documents(normalized_query, top_k=top_k)
    prompt = build_rag_prompt(normalized_query, results)
    try:
        answer = get_chat_provider().generate(prompt, results, [])
    except LLMProviderError:
        raise
    except Exception as exc:
        raise LLMProviderError("LLM provider failed") from exc
    return answer, _sources(results)


def build_rag_prompt(query: str, results: Sequence[SearchResult]) -> str:
    context = "\n\n".join(
        f"Source {index + 1} ({_source(result)}):\n{result.text}"
        for index, result in enumerate(results)
    )
    if not context:
        context = "No retrieved context."
    return (
        "Answer the question using only the retrieved context. "
        "If the context does not contain the answer, say you do not know.\n\n"
        f"Retrieved context:\n{context}\n\n"
        f"Question:\n{query}\n\n"
        "Answer:"
    )


def _extract_answer(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("response"), str):
        return payload["response"]
    if isinstance(payload.get("answer"), str):
        return payload["answer"]
    if isinstance(payload.get("text"), str):
        return payload["text"]

    message = payload.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return message["content"]

    raise LLMProviderError("LLM provider returned an invalid response")


def _sources(results: Sequence[SearchResult]) -> list[str]:
    return [_source(result) for result in results]


def _source(result: SearchResult) -> str:
    return f"{result.metadata.get('source_name', 'document')}#{result.metadata.get('chunk_index', 0)}"
