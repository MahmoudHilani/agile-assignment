import math
from collections.abc import Sequence
from threading import Lock
from typing import Any, Literal

from app.core.config import Settings, get_settings

EmbeddingMode = Literal["document", "query"]
SentenceTransformer: Any = None
_sentence_transformer_import_attempted = False


class EmbeddingProviderError(RuntimeError):
    pass


class LocalEmbeddingProvider:
    _models: dict[str, Any] = {}
    _lock = Lock()

    def __init__(self, model_name: str, trust_remote_code: bool = False) -> None:
        self._model_name = model_name
        self._trust_remote_code = trust_remote_code

    def embed_texts(self, texts: Sequence[str], mode: EmbeddingMode = "document") -> list[list[float]]:
        if not texts:
            return []

        prefixed_texts = [_prefix_text(text, mode) for text in texts]
        try:
            encoded = self._model().encode(prefixed_texts, normalize_embeddings=True)
        except Exception as exc:
            raise EmbeddingProviderError("Local embedding provider failed") from exc

        embeddings = _as_list(encoded)
        if len(embeddings) != len(texts):
            raise EmbeddingProviderError("Local embedding provider returned an unexpected number of vectors")
        return [_normalize_vector(_coerce_vector(item)) for item in embeddings]

    def _model(self) -> Any:
        with self._lock:
            cache_key = f"{self._model_name}:{self._trust_remote_code}"
            if cache_key not in self._models:
                transformer = _sentence_transformer_class()
                try:
                    self._models[cache_key] = transformer(
                        self._model_name,
                        trust_remote_code=self._trust_remote_code,
                    )
                except Exception as exc:
                    raise EmbeddingProviderError("Local embedding model failed to load") from exc
            return self._models[cache_key]


def get_embedding_provider(
    settings: Settings | None = None,
) -> LocalEmbeddingProvider:
    resolved_settings = settings or get_settings()
    if not resolved_settings.embedding_model_name:
        raise EmbeddingProviderError("Local embedding provider requires EMBEDDING_MODEL_NAME")
    trust_remote_code = getattr(resolved_settings, "embedding_trust_remote_code", False)
    trusted_remote_embedding_models = getattr(
        resolved_settings,
        "trusted_remote_embedding_models",
        "nomic-ai/nomic-embed-text-v1.5",
    )
    if trust_remote_code:
        allowed_models = {
            model.strip()
            for model in trusted_remote_embedding_models.split(",")
            if model.strip()
        }
        if resolved_settings.embedding_model_name not in allowed_models:
            raise EmbeddingProviderError("Embedding model is not allowed to execute remote code")
    return LocalEmbeddingProvider(
        resolved_settings.embedding_model_name,
        trust_remote_code=trust_remote_code,
    )


def _coerce_vector(value: Any) -> list[float]:
    if isinstance(value, dict):
        value = value.get("embedding")
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, list):
        raise EmbeddingProviderError("Embedding provider returned an invalid vector")
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError) as exc:
        raise EmbeddingProviderError("Embedding provider returned a non-numeric vector") from exc


def _as_list(value: Any) -> list[Any]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, list):
        raise EmbeddingProviderError("Embedding provider returned an invalid response")
    return value


def _normalize_vector(vector: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        return vector
    return [value / magnitude for value in vector]


def _prefix_text(text: str, mode: EmbeddingMode) -> str:
    if mode == "document":
        return f"search_document: {text}"
    if mode == "query":
        return f"search_query: {text}"
    raise EmbeddingProviderError(f"Unsupported embedding mode '{mode}'")


def _sentence_transformer_class() -> Any:
    global SentenceTransformer, _sentence_transformer_import_attempted
    if SentenceTransformer is None and not _sentence_transformer_import_attempted:
        _sentence_transformer_import_attempted = True
        try:
            from sentence_transformers import SentenceTransformer as imported
        except ImportError as exc:
            raise EmbeddingProviderError("Local embedding provider requires sentence-transformers") from exc
        SentenceTransformer = imported
    if SentenceTransformer is None:
        raise EmbeddingProviderError("Local embedding provider requires sentence-transformers")
    return SentenceTransformer
