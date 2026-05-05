"""Deterministic hash-based embedding provider.

This is a **development / testing** embedding implementation that works with
zero external dependencies.  Each token is hashed to a position in a fixed-
dimension vector and the per-token values are summed then L2-normalised.

The result is a stable, reproducible embedding that captures *vocabulary
overlap* between texts, which is sufficient for:

* Integration tests that verify the indexing pipeline end-to-end.
* Local development without an OpenAI / Cohere API key.

Swap for a real embedding provider by implementing the EmbeddingProvider
protocol from interfaces.py.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence


VECTOR_DIMS = 256


class HashEmbeddingProvider:
    """Produce deterministic fixed-dimension embeddings without external APIs."""

    def __init__(self, dims: int = VECTOR_DIMS) -> None:
        if dims < 1:
            raise ValueError("dims must be at least 1")
        self._dims = dims

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one embedding vector per text."""
        return [self._embed(t) for t in texts]

    # ── internal ──────────────────────────────────────────────────────────

    def _embed(self, text: str) -> list[float]:
        tokens = text.lower().split()
        vec = [0.0] * self._dims
        for token in tokens:
            digest = hashlib.sha256(token.encode()).digest()
            # Use pairs of bytes to map into dims positions
            for i in range(0, min(len(digest), self._dims * 2), 2):
                idx = int.from_bytes(digest[i : i + 2], "big") % self._dims
                # Sign from the high bit of the next byte
                sign = 1 if (digest[(i + 2) % len(digest)] & 0x80) else -1
                vec[idx] += sign

        return _l2_normalise(vec)


def _l2_normalise(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        return vec
    return [x / norm for x in vec]