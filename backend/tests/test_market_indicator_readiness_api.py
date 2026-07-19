from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_market_indicator_readiness_api() -> None:
    response = client.get("/market-indicators-data/readiness?indicator_codes=WTI&indicator_codes=US_CORE_PCE")
    assert response.status_code == 200
    body = response.json()
    assert body["items"]
    codes = {item["indicator_code"]: item for item in body["items"]}
    assert "WTI" in codes
    assert codes["WTI"]["mapping_ready"] is True
    assert codes["WTI"]["readiness"] in {"MAPPING_READY", "COMPARE_READY", "SIGNAL_READY"}
    assert "summary_counts" in body
