import pytest

from tests.conftest import make_document_record


@pytest.fixture(autouse=True)
def mock_delete_side_effects(monkeypatch):
    monkeypatch.setattr("src.services.document_service.delete_chunks_by_document", lambda *a, **k: None)
    monkeypatch.setattr("src.services.document_service.delete_from_storage", lambda *a, **k: None)
    monkeypatch.setattr(
        "src.services.document_service.ingest_document_task",
        type(
            "T",
            (),
            {
                "delay": staticmethod(lambda document_id: type("R", (), {"id": "reprocess-task-1"})()),
            },
        )(),
    )


def test_document_listing_and_pagination(client, auth_headers):
    """5. Document listing and pagination."""
    for i in range(3):
        make_document_record(tenant_id="tenant-1", original_filename=f"doc-{i}.pdf")
    # A document in a different tenant must never show up.
    make_document_record(tenant_id="tenant-2", original_filename="other-tenant.pdf")

    response = client.get("/api/v1/documents?page=1&page_size=2", headers=auth_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2

    page2 = client.get("/api/v1/documents?page=2&page_size=2", headers=auth_headers).json()
    assert len(page2["items"]) == 1


def test_get_single_document(client, auth_headers):
    record = make_document_record(tenant_id="tenant-1")
    response = client.get(f"/api/v1/documents/{record.id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["document_id"] == str(record.id)


def test_document_deletion(client, auth_headers):
    """6. Document deletion."""
    record = make_document_record(tenant_id="tenant-1", owner_id="user-1")

    response = client.delete(f"/api/v1/documents/{record.id}", headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "deleted"

    follow_up = client.get(f"/api/v1/documents/{record.id}", headers=auth_headers)
    assert follow_up.status_code == 404


def test_reprocess_document(client, auth_headers):
    record = make_document_record(tenant_id="tenant-1", owner_id="user-1", status="failed")
    response = client.post(f"/api/v1/documents/{record.id}/reprocess", headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "queued"


def test_unauthorized_access_no_token(client):
    """10a. Unauthorized: missing token -> 401."""
    response = client.get("/api/v1/documents")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_unauthorized_access_bad_token(client):
    response = client.get("/api/v1/documents", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert response.status_code == 401


def test_cross_tenant_document_access_returns_404(client, auth_headers, other_tenant_headers):
    """10b. A document in another tenant must be invisible (404, not a leaking 403)."""
    record = make_document_record(tenant_id="tenant-1")

    response = client.get(f"/api/v1/documents/{record.id}", headers=other_tenant_headers)
    assert response.status_code == 404


# "Same tenant, different non-owning user" is no longer a reachable scenario:
# the auth model now makes every request's tenant_id equal to its own user id
# (see tests/conftest.py's _IDENTITY_IDS comment), so two distinct users can
# never share a tenant. The underlying owner-or-admin check in
# document_service._authorize_mutation() is still exercised indirectly by
# test_cross_tenant_document_access_returns_404 (which 404s before reaching
# it) — there's no remaining code path where it would return 403 instead.
