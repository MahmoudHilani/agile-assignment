from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any, AsyncGenerator

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

    async def generate_stream(
        self,
        prompt: str,
        context: Sequence[SearchResult],
        history: Sequence[ChatTurn],
    ) -> AsyncGenerator[str, None]:
        try:
            
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    self._url,
                    json={"model": self._model, "prompt": prompt, "stream": True},
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                            if token := chunk.get("response"):
                                yield token
                            if chunk.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue
        except Exception as exc:
            raise LLMProviderError(f"Streaming failed: {str(exc)}")


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
    
    results = search_documents(normalized_query, top_k=top_k)
    prompt = build_rag_prompt(normalized_query, results)
    try:
        answer = get_chat_provider().generate(prompt, results, [])
    except LLMProviderError:
        raise
    except Exception as exc:
        raise LLMProviderError("LLM provider failed") from exc
    return answer, _sources(results)


async def run_rag_query_stream(query: str, top_k: int) -> AsyncGenerator[str, None]:
    
    try:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("Query cannot be empty")

        
        results = search_documents(normalized_query, top_k=top_k)
        
        prompt = build_rag_prompt(normalized_query, results)
        
        
        provider = get_chat_provider()
        async for chunk in provider.generate_stream(prompt, results, []):
            yield chunk
            
    except Exception as e:
        
        print(f"BACKEND STREAM ERROR: {str(e)}")
        yield f"Error: {str(e)}"


def build_rag_prompt(query: str, results: Sequence[SearchResult]) -> str:
    context = "\n\n".join(
        f"Source {index + 1} ({_source(result)}):\n{result.text}"
        for index, result in enumerate(results)
    )
    if not context:
        context = "No retrieved context."
    return (
        "Answer the question using only the retrieved context. "
        "If the answer requires counting items explicitly listed in the context, count them. "
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
    
    message = payload.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return message["content"]

    raise LLMProviderError("LLM provider returned an invalid response")


def _sources(results: Sequence[SearchResult]) -> list[str]:
    return [_source(result) for result in results]


def _source(result: SearchResult) -> str:
    return f"{result.metadata.get('source_name', 'document')}#{result.metadata.get('chunk_index', 0)}"
