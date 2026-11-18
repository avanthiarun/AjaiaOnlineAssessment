"""Small helpers shared by the test modules."""

from typing import Any

from fastapi.testclient import TestClient

PASSWORD = "demo1234"


def login(client: TestClient, email: str) -> TestClient:
    """Sign the client in and return it."""
    response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return client


def create_doc(client: TestClient, **body: Any) -> dict[str, Any]:
    """Create a document and return its JSON."""
    response = client.post("/api/documents", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def share(owner: TestClient, doc_id: str, email: str, role: str) -> None:
    """Share a document (asserts it succeeded)."""
    response = owner.post(f"/api/documents/{doc_id}/shares", json={"email": email, "role": role})
    assert response.status_code in (200, 201), response.text
