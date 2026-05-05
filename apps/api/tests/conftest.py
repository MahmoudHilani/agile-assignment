import hashlib
import math
import re

import pytest

from app.services import embedding_providers
from app.services.embedding_providers import LocalEmbeddingProvider

EMBEDDING_DIMENSIONS = 64


class FakeSentenceTransformer:
    def __init__(self, model_name: str, trust_remote_code: bool) -> None:
        self.model_name = model_name
        self.trust_remote_code = trust_remote_code

    def encode(self, texts: list[str], normalize_embeddings: bool) -> list[list[float]]:
        return [_token_vector(text) for text in texts]


@pytest.fixture(autouse=True)
def fake_local_embedding_model(monkeypatch: pytest.MonkeyPatch):
    LocalEmbeddingProvider._models.clear()
    monkeypatch.setattr(embedding_providers, "SentenceTransformer", FakeSentenceTransformer)
    yield
    LocalEmbeddingProvider._models.clear()


def _token_vector(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS
        vector[bucket] += 1.0

    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        return vector
    return [value / magnitude for value in vector]
