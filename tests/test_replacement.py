import pytest
import shutil
from pathlib import Path
from uuid import uuid4

from app import config
from app.document_service import initialize_company_document, process_document, replace_company_document
from app.vector_store import VECTOR_DB


def test_replacement():
    VECTOR_DB.clear()

    process_document("tests/sample.txt", "v1", use_mock=True)
    first_count = len(VECTOR_DB)

    process_document("tests/sample2.txt", "v2", use_mock=True)
    second_count = len(VECTOR_DB)

    assert second_count > first_count


@pytest.fixture
def company_doc_dir(monkeypatch):
    company_doc_dir = Path("tests/runtime_company_docs") / uuid4().hex
    monkeypatch.setattr(config, "COMPANY_DOC_DIR", company_doc_dir)
    monkeypatch.setattr(config, "CANONICAL_COMPANY_DOC_DIR", company_doc_dir / "current")
    monkeypatch.setattr(config, "ACTIVE_DOC_VERSION", None)
    yield company_doc_dir
    shutil.rmtree(company_doc_dir, ignore_errors=True)
    try:
        company_doc_dir.parent.rmdir()
    except OSError:
        pass


def test_company_document_replacement_refreshes_current_index(company_doc_dir):
    VECTOR_DB.clear()

    first = replace_company_document("tests/sample.txt", use_mock=True)
    assert first["version"] == config.CANONICAL_DOC_VERSION
    assert config.ACTIVE_DOC_VERSION == config.CANONICAL_DOC_VERSION
    assert config.get_canonical_company_document_path().read_text() == (
        "This is a company that builds AI systems for healthcare."
    )
    assert any("healthcare" in item["text"] for item in VECTOR_DB)

    second = replace_company_document("tests/sample2.txt", use_mock=True)

    assert second["version"] == config.CANONICAL_DOC_VERSION
    assert config.get_canonical_company_document_path().read_text() == (
        "This is a logistics company focused on delivery optimization."
    )
    assert len([item for item in VECTOR_DB if item["version"] == config.CANONICAL_DOC_VERSION]) == 1
    assert all("healthcare" not in item["text"] for item in VECTOR_DB)
    assert any("logistics" in item["text"] for item in VECTOR_DB)


def test_initialize_company_document_indexes_canonical_doc(company_doc_dir):
    VECTOR_DB.clear()

    canonical_dir = config.CANONICAL_COMPANY_DOC_DIR
    canonical_dir.mkdir(parents=True)
    canonical_path = canonical_dir / "company_document.txt"
    canonical_path.write_text("Canonical startup knowledge.", encoding="utf-8")

    loaded_path = initialize_company_document(use_mock=True)

    assert loaded_path == canonical_path
    assert config.ACTIVE_DOC_VERSION == config.CANONICAL_DOC_VERSION
    assert [item["text"] for item in VECTOR_DB] == ["Canonical startup knowledge."]


def test_invalid_replacement_does_not_overwrite_current_document(company_doc_dir):
    VECTOR_DB.clear()

    replace_company_document("tests/sample.txt", use_mock=True)
    canonical_path = config.get_canonical_company_document_path()
    original_text = canonical_path.read_text()

    company_doc_dir.mkdir(parents=True, exist_ok=True)
    empty_file = company_doc_dir / "empty.txt"
    empty_file.write_text("   ", encoding="utf-8")

    with pytest.raises(ValueError, match="Empty document"):
        replace_company_document(empty_file, use_mock=True)

    assert canonical_path.read_text() == original_text
    assert any("healthcare" in item["text"] for item in VECTOR_DB)


def test_invalid_supported_file_does_not_overwrite_current_document(company_doc_dir):
    VECTOR_DB.clear()

    replace_company_document("tests/sample.txt", use_mock=True)
    canonical_path = config.get_canonical_company_document_path()
    original_text = canonical_path.read_text()

    company_doc_dir.mkdir(parents=True, exist_ok=True)
    invalid_pdf = company_doc_dir / "invalid.pdf"
    invalid_pdf.write_text("not really a pdf", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid document"):
        replace_company_document(invalid_pdf, use_mock=True)

    assert canonical_path.read_text() == original_text
    assert any("healthcare" in item["text"] for item in VECTOR_DB)
