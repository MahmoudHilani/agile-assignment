import pytest

from app.core.config import Settings
from app.services import embedding_providers
from app.services.embedding_providers import (
    EmbeddingProviderError,
    LocalEmbeddingProvider,
    get_embedding_provider,
)


def _settings(**overrides: object) -> Settings:
    values = {
        "embedding_model_name": "nomic-ai/nomic-embed-text-v1.5",
    }
    values.update(overrides)
    return Settings(**values)


def test_local_provider_selection_requires_model_name() -> None:
    provider = get_embedding_provider(_settings())

    assert isinstance(provider, LocalEmbeddingProvider)


def test_local_provider_without_model_name_raises_controlled_error() -> None:
    with pytest.raises(EmbeddingProviderError, match="EMBEDDING_MODEL_NAME"):
        get_embedding_provider(_settings(embedding_model_name=""))


def test_remote_code_requires_allowlisted_model() -> None:
    with pytest.raises(EmbeddingProviderError, match="not allowed"):
        get_embedding_provider(
            _settings(
                embedding_model_name="untrusted/model",
                embedding_trust_remote_code=True,
            )
        )


def test_remote_code_is_passed_only_after_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[tuple[str, bool]] = []

    class FakeSentenceTransformer:
        def __init__(self, model_name: str, trust_remote_code: bool) -> None:
            created.append((model_name, trust_remote_code))

        def encode(self, texts: list[str], normalize_embeddings: bool) -> list[list[int]]:
            return [[1, 0] for _ in texts]

    LocalEmbeddingProvider._models.clear()
    monkeypatch.setattr(embedding_providers, "SentenceTransformer", FakeSentenceTransformer)

    provider = get_embedding_provider(
        _settings(
            embedding_trust_remote_code=True,
            trusted_remote_embedding_models="nomic-ai/nomic-embed-text-v1.5",
        )
    )
    provider.embed_texts(["chunk text"])

    assert created == [("nomic-ai/nomic-embed-text-v1.5", True)]


def test_local_provider_prefixes_texts_and_returns_normalized_float_lists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    encoded_inputs: list[list[str]] = []

    class FakeSentenceTransformer:
        def __init__(self, model_name: str, trust_remote_code: bool) -> None:
            self.model_name = model_name
            self.trust_remote_code = trust_remote_code

        def encode(self, texts: list[str], normalize_embeddings: bool) -> list[list[int]]:
            assert normalize_embeddings is True
            encoded_inputs.append(texts)
            return [[3, 4] for _ in texts]

    LocalEmbeddingProvider._models.clear()
    monkeypatch.setattr(embedding_providers, "SentenceTransformer", FakeSentenceTransformer)

    provider = LocalEmbeddingProvider("nomic-ai/nomic-embed-text-v1.5")
    document_vectors = provider.embed_texts(["chunk text"], mode="document")
    query_vectors = provider.embed_texts(["user query"], mode="query")

    assert encoded_inputs == [
        ["search_document: chunk text"],
        ["search_query: user query"],
    ]
    assert document_vectors == [[0.6, 0.8]]
    assert query_vectors == [[0.6, 0.8]]
    assert all(isinstance(value, float) for value in document_vectors[0])
