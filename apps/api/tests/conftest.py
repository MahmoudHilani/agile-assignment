import hashlib
import math
import re
import zipfile
from io import BytesIO
from xml.sax.saxutils import escape

import pytest

from app.services import embedding_providers
from app.services.embedding_providers import LocalEmbeddingProvider

EMBEDDING_DIMENSIONS = 64


def make_pdf_bytes(text: str) -> bytes:
    import fitz

    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    content = document.tobytes()
    document.close()
    return content


def make_docx_bytes(text: str) -> bytes:
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>{escape(text)}</w:t></w:r></w:p>
  </w:body>
</w:document>
"""
    content_types = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


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
