"""Login and authentication requirements."""

from fastapi.testclient import TestClient

from app.models import User


def test_login_rejects_wrong_password(anon: TestClient, users: dict[str, User]) -> None:
    response = anon.post("/api/auth/login", json={"email": "alice@ajaia.test", "password": "wrong"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}
    assert anon.get("/api/auth/me").status_code == 401


def test_document_endpoints_require_login(anon: TestClient) -> None:
    calls = [
        ("GET", "/api/documents"),
        ("POST", "/api/documents"),
        ("GET", "/api/documents/some-id"),
        ("PATCH", "/api/documents/some-id"),
        ("DELETE", "/api/documents/some-id"),
        ("GET", "/api/documents/some-id/shares"),
    ]
    for method, url in calls:
        response = anon.request(method, url, json={})
        assert response.status_code == 401, f"{method} {url}"
        assert response.json() == {"detail": "Not signed in"}
