from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_schema_comments() -> None:
    response = client.get("/schema-comments", params={"table_name": "stocks"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)
