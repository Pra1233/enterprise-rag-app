import io
from unittest.mock import MagicMock

import pytest


class FakeAsyncResult:
    def __init__(self, task_id: str, info=None):
        self.id = task_id
        self.info = info


@pytest.fixture(autouse=True)
def mock_storage(monkeypatch):
    monkeypatch.setattr("src.services.ingestion_service.ensure_bucket", lambda: None)
    monkeypatch.setattr("src.services.ingestion_service.upload_document", lambda *a, **k: None)


@pytest.fixture
def mock_celery_delay(monkeypatch):
    fake_task = MagicMock()
    fake_task.delay = MagicMock(return_value=FakeAsyncResult(task_id="fake-task-123"))
    monkeypatch.setattr("src.services.ingestion_service.ingest_document_task", fake_task)

    # AsyncResult would otherwise hit the real Celery/Redis result backend.
    monkeypatch.setattr(
        "src.services.ingestion_service.celery_app.AsyncResult",
        lambda task_id: FakeAsyncResult(task_id=task_id, info=None),
    )
    return fake_task


def test_successful_document_upload(client, auth_headers, mock_celery_delay):
    """1. Successful document upload."""
    response = client.post(
        "/api/v1/ingestion/upload",
        files={"file": ("report.pdf", io.BytesIO(b"%PDF-1.4 fake pdf content"), "application/pdf")},
        data={"author": "Jane Doe"},
        headers=auth_headers,
    )

    assert response.status_code == 202, response.text
    body = response.json()
    assert "document_id" in body
    assert body["task_id"] == "fake-task-123"
    assert body["status"] == "queued"
    mock_celery_delay.delay.assert_called_once()


def test_invalid_document_upload_rejected(client, auth_headers, mock_celery_delay):
    """2. Invalid document upload (wrong file type) -> 400."""
    response = client.post(
        "/api/v1/ingestion/upload",
        files={"file": ("notes.txt", io.BytesIO(b"plain text"), "text/plain")},
        headers=auth_headers,
    )

    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "BAD_REQUEST"
    mock_celery_delay.delay.assert_not_called()


def test_celery_task_submitted_with_document_id(client, auth_headers, mock_celery_delay):
    """3. Celery task submission — the task is enqueued with the new document's id."""
    response = client.post(
        "/api/v1/ingestion/upload",
        files={"file": ("report.pdf", io.BytesIO(b"%PDF-1.4 fake pdf content"), "application/pdf")},
        headers=auth_headers,
    )
    document_id = response.json()["document_id"]

    mock_celery_delay.delay.assert_called_once_with(document_id)


def test_ingestion_status_retrieval(client, auth_headers, mock_celery_delay):
    """4. Ingestion status retrieval reflects the persisted document status,
    and never fabricates a progress percentage the worker didn't report.
    """
    upload_response = client.post(
        "/api/v1/ingestion/upload",
        files={"file": ("report.pdf", io.BytesIO(b"%PDF-1.4 fake pdf content"), "application/pdf")},
        headers=auth_headers,
    )
    task_id = upload_response.json()["task_id"]
    document_id = upload_response.json()["document_id"]

    status_response = client.get(f"/api/v1/ingestion/status/{task_id}", headers=auth_headers)

    assert status_response.status_code == 200, status_response.text
    body = status_response.json()
    assert body["task_id"] == task_id
    assert body["document_id"] == document_id
    assert body["status"] == "queued"
    assert body["progress_percent"] is None


def test_ingestion_status_unknown_task_404(client, auth_headers):
    response = client.get("/api/v1/ingestion/status/does-not-exist", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
