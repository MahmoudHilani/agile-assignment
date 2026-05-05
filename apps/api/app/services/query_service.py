from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, AsyncGenerator

import httpx

from app.core.config import Settings, get_settings
from app.domain.models import ChatTurn, SearchResult
from app.services.document_service import search_documents


class LLMProviderError(RuntimeError):
    pass


OFF_TOPIC_RESPONSE = (
    "I can only answer questions about the company, its services, portfolio, "
    "technologies, or how it may help with customer projects."
)
STREAM_ERROR_RESPONSE = "Sorry, I could not generate a response right now. Please try again later."
MAX_HISTORY_MESSAGES = 12

_CUSTOMER_COMPANY_QUERY_TERMS = {
    "about",
    "app",
    "application",
    "automation",
    "available",
    "availability",
    "booking",
    "build",
    "business",
    "case",
    "client",
    "clients",
    "company",
    "contact",
    "cost",
    "customer",
    "experience",
    "help",
    "hire",
    "integrate",
    "integrates",
    "integration",
    "integrations",
    "offer",
    "offers",
    "platform",
    "portfolio",
    "price",
    "pricing",
    "product",
    "products",
    "project",
    "projects",
    "service",
    "services",
    "serve",
    "serves",
    "solution",
    "solutions",
    "specialise",
    "specialize",
    "team",
    "technologies",
    "technology",
    "timeline",
    "user",
    "users",
    "website",
}

_CUSTOMER_COMPANY_QUERY_PHRASES = (
    "what do you do",
    "who are you",
    "get started",
    "work with you",
    "your company",
    "your services",
    "your portfolio",
    "your team",
)


@dataclass(frozen=True, slots=True)
class RagRequest:
    prompt: str
    results: list[SearchResult]
    history: list[ChatTurn]


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


def run_rag_query(
    query: str,
    top_k: int,
    history: Sequence[ChatTurn] = (),
) -> tuple[str, list[str]]:
    rag_request = _build_rag_request(query, top_k, history)
    if rag_request is None:
        return OFF_TOPIC_RESPONSE, []

    try:
        answer = get_chat_provider().generate(
            rag_request.prompt,
            rag_request.results,
            rag_request.history,
        )
    except LLMProviderError:
        raise
    except Exception as exc:
        raise LLMProviderError("LLM provider failed") from exc
    return answer, _sources(rag_request.results)


async def run_rag_query_stream(
    query: str,
    top_k: int,
    history: Sequence[ChatTurn] = (),
) -> AsyncGenerator[str, None]:
    try:
        rag_request = _build_rag_request(query, top_k, history)
        if rag_request is None:
            yield OFF_TOPIC_RESPONSE
            return

        provider = get_chat_provider()
        async for chunk in provider.generate_stream(
            rag_request.prompt,
            rag_request.results,
            rag_request.history,
        ):
            yield chunk

    except Exception as exc:
        print(f"BACKEND STREAM ERROR: {str(exc)}")
        yield STREAM_ERROR_RESPONSE


def _build_rag_request(
    query: str,
    top_k: int,
    history: Sequence[ChatTurn] = (),
) -> RagRequest | None:
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("Query cannot be empty")

    recent_history = _recent_history(history)
    if not is_customer_company_query(normalized_query, recent_history):
        return None

    results = search_documents(normalized_query, top_k=top_k)
    prompt = build_rag_prompt(normalized_query, results, recent_history)
    return RagRequest(prompt=prompt, results=results, history=recent_history)


def build_rag_prompt(
    query: str,
    results: Sequence[SearchResult],
    history: Sequence[ChatTurn] = (),
) -> str:
    context = "\n\n".join(
        f"Company knowledge {index + 1}:\n{result.text}"
        for index, result in enumerate(results)
    )
    if not context:
        context = "No retrieved context."
    conversation = _format_history(_recent_history(history))
    return (
        "You are a customer-facing company overview assistant for the website frontend. "
        "You are an AI assistant, not a company employee, founder, sales representative, or team member. "
        "Do not claim to be part of the company or ask users to contact you personally. "
        "Use a helpful, cheerful, and professional tone. "
        "Your goal is to give prospective customers a clear overview of the company, "
        "its members or team when available in the company knowledge, its services, portfolio, "
        "technologies, and how its work may fit customer projects. "
        "If a question is unrelated to the company, politely say you can only answer "
        "questions about the company and its customer-facing work. "
        "Use the retrieved context as internal company knowledge maintained by the company, "
        "not as documents supplied by the website user. "
        "Answer questions about the company and, when a user describes a project, "
        "connect the company's relevant services to the project at a high level. "
        "Answer the question using only the retrieved context and stay within the retrieved context. "
        "Do not invent services, experience, prices, timelines, guarantees, or contact details. "
        "Do not mention sources, documents, chunks, retrieved context, or file names in the answer. "
        "Do not say the user provided the company knowledge. "
        "When encouraging contact, refer to contacting the company or team through the website channels, "
        "not contacting you. "
        "If the conversation shows you asked the user for project details, features, design style, "
        "tone, or preferences, treat the user's reply as in-scope project context and continue helping. "
        "Do not run an extended discovery or sales-closing conversation. "
        "When project details are incomplete, give a brief relevant overview and encourage the user "
        "to contact the team for tailored advice. "
        "If the answer requires counting items explicitly listed in the context, count them. "
        "If the context does not contain the answer, say you do not know and invite the user "
        "to share more project details or contact the company through the available website channels. "
        "Keep the response concise, clear, and customer-ready.\n\n"
        f"Retrieved context:\n{context}\n\n"
        f"Conversation so far:\n{conversation}\n\n"
        f"Question:\n{query}\n\n"
        "Answer:"
    )


def is_customer_company_query(query: str, history: Sequence[ChatTurn] = ()) -> bool:
    normalized = query.lower()
    if _matches_customer_company_query(normalized):
        return True

    return _answers_recent_company_follow_up(history)


def _matches_customer_company_query(normalized: str) -> bool:
    if any(phrase in normalized for phrase in _CUSTOMER_COMPANY_QUERY_PHRASES):
        return True

    words = {
        word.strip(".,!?;:()[]{}\"'")
        for word in normalized.replace("/", " ").replace("-", " ").split()
    }
    return bool(words & _CUSTOMER_COMPANY_QUERY_TERMS)


def _answers_recent_company_follow_up(history: Sequence[ChatTurn]) -> bool:
    recent_history = _recent_history(history)
    if not recent_history or recent_history[-1].role != "assistant":
        return False

    assistant_message = recent_history[-1].content.lower()
    if not _asks_for_project_details(assistant_message):
        return False

    return any(
        turn.role == "user" and _matches_customer_company_query(turn.content.lower())
        for turn in recent_history[:-1]
    )


def _asks_for_project_details(message: str) -> bool:
    if "?" in message:
        return True

    follow_up_phrases = (
        "share more",
        "tell me more",
        "project details",
        "specific features",
        "technology stack",
        "tech stack",
    )
    return any(phrase in message for phrase in follow_up_phrases)


def _extract_answer(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("response"), str):
        return payload["response"]
    if isinstance(payload.get("answer"), str):
        return payload["answer"]
    
    message = payload.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return message["content"]

    raise LLMProviderError("LLM provider returned an invalid response")


def _recent_history(history: Sequence[ChatTurn]) -> list[ChatTurn]:
    return list(history)[-MAX_HISTORY_MESSAGES:]


def _format_history(history: Sequence[ChatTurn]) -> str:
    if not history:
        return "No prior conversation."

    lines = []
    for turn in history:
        speaker = "User" if turn.role == "user" else "Assistant"
        lines.append(f"{speaker}: {turn.content}")
    return "\n".join(lines)


def _sources(results: Sequence[SearchResult]) -> list[str]:
    return [_source(result) for result in results]


def _source(result: SearchResult) -> str:
    return f"{result.metadata.get('source_name', 'document')}#{result.metadata.get('chunk_index', 0)}"
