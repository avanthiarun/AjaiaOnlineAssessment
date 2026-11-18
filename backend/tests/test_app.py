"""App-wide behavior: security headers and the catch-all error handler."""

import logging

import pytest
from fastapi.testclient import TestClient

from app.main import SECURITY_HEADERS
from app.services import documents as document_service

EXPECTED_CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


def test_responses_carry_security_headers(anon: TestClient) -> None:
    response = anon.get("/api/health")

    assert response.status_code == 200
    assert response.headers["content-security-policy"] == EXPECTED_CSP
    assert response.headers["permissions-policy"] == "camera=(), microphone=(), geolocation=()"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_unhandled_error_returns_generic_500_and_logs_traceback(
    alice: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def explode(*_: object) -> None:
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(document_service, "list_for_user", explode)

    with caplog.at_level(logging.ERROR, logger="app"):
        response = alice.get("/api/documents")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "secret internal detail" not in response.text
    assert all(response.headers[name] == value for name, value in SECURITY_HEADERS.items())
    [record] = [r for r in caplog.records if r.name == "app"]
    assert record.getMessage() == "Unhandled error on GET /api/documents"
    assert record.exc_info is not None and record.exc_info[0] is RuntimeError
