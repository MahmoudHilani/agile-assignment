from app.document_service import process_document
from app.vector_store import VECTOR_DB

def test_document_processing():
    VECTOR_DB.clear()

    process_document("tests/sample.txt", "test_v1", use_mock=True)

    assert len(VECTOR_DB) > 0