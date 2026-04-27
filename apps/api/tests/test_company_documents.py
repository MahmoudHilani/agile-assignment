from pathlib import Path
from shutil import rmtree
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.company_documents import (
    CompanyDocumentService,
    company_document_service,
)


@pytest.fixture
def company_document_dir() -> Path:
    path = Path("tests/runtime_company_docs") / uuid4().hex
    yield path
    rmtree(path, ignore_errors=True)
    try:
        path.parent.rmdir()
    except OSError:
        pass


@pytest.fixture
def client(company_document_dir: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    settings = Settings(company_document_dir=company_document_dir)
    service = CompanyDocumentService(settings=settings)
    monkeypatch.setattr(
        "app.api.routes.documents.company_document_service",
        service,
    )
    monkeypatch.setattr(
        "app.api.routes.query.company_document_service",
        service,
    )
    monkeypatch.setattr(
        "app.main.company_document_service",
        service,
    )
    app = create_app(settings=settings)

    with TestClient(app) as test_client:
        yield test_client

    company_document_service.vector_store.clear()
    company_document_service.active_source_name = None


def test_initial_company_document_is_indexed_on_startup(
    company_document_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(company_document_dir=company_document_dir)
    settings.company_document_dir.mkdir(parents=True)
    settings.canonical_company_document_path.write_text(
        "Acme builds clinical AI tools for hospitals.",
        encoding="utf-8",
    )
    service = CompanyDocumentService(settings=settings)
    monkeypatch.setattr("app.main.company_document_service", service)

    app = create_app(settings=settings)
    with TestClient(app):
        pass

    assert service.active_source_name == "company_document.txt"
    assert service.vector_store.count == 1


def test_replacing_company_document_refreshes_future_query_results(client: TestClient) -> None:
    first_response = client.post(
        "/admin/company-document",
        json={
            "source_name": "company.txt",
            "content": "Acme builds clinical AI tools for hospitals.",
        },
    )
    assert first_response.status_code == 200
    assert first_response.json()["chunks_indexed"] == 1

    first_query = client.post("/query", json={"query": "clinical hospital AI"})
    assert first_query.status_code == 200
    assert "clinical AI tools" in first_query.json()["answer"]

    second_response = client.post(
        "/admin/company-document",
        json={
            "source_name": "company.txt",
            "content": "Acme now provides logistics optimization for delivery fleets.",
        },
    )
    assert second_response.status_code == 200

    second_query = client.post("/query", json={"query": "delivery logistics"})
    assert second_query.status_code == 200
    assert "logistics optimization" in second_query.json()["answer"]
    assert "clinical AI tools" not in second_query.json()["answer"]


def test_empty_replacement_document_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/admin/company-document",
        json={"source_name": "company.txt", "content": "   "},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Empty document"


def test_unsupported_replacement_document_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/admin/company-document",
        json={"source_name": "company.pdf", "content": "not supported yet"},
    )

    assert response.status_code == 400
    assert "Unsupported format" in response.json()["detail"]
