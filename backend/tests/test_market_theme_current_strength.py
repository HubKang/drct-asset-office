from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_market_theme_range_return_supports_current_strength_sort() -> None:
    response = client.get(
        "/external/kiwoom/market-themes/returns/range",
        params={"end_date": "2026-07-22", "days": 30, "sort_by": "CURRENT_STRENGTH"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["sort_by"] == "CURRENT_STRENGTH"
    assert {"current_strength_top", "rolling_30d_top", "trading_value_top", "persistence_top"} <= set(body["summary"])
    scores = [item["theme_strength_score"] for item in body["themes"] if item["theme_strength_score"] is not None]
    assert scores == sorted(scores, reverse=True)


def test_market_theme_range_return_keeps_rolling_30d_sort() -> None:
    response = client.get(
        "/external/kiwoom/market-themes/returns/range",
        params={"end_date": "2026-07-22", "days": 30, "sort_by": "ROLLING_30D_RETURN"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["sort_by"] == "ROLLING_30D_RETURN"
    rolling = [item["rolling_30d_change_rate"] for item in body["themes"] if item["rolling_30d_change_rate"] is not None]
    assert rolling == sorted(rolling, reverse=True)


def test_market_theme_range_return_supports_latest_return_sort() -> None:
    response = client.get(
        "/external/kiwoom/market-themes/returns/range",
        params={"end_date": "2026-07-22", "days": 30, "sort_by": "LATEST_RETURN"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["sort_by"] == "LATEST_RETURN"
    latest_date = max(
        daily["return_date"]
        for theme in body["themes"]
        for daily in theme["daily_returns"]
    )
    values = []
    missing_started = False
    for theme in body["themes"]:
        latest = next((daily["avg_change_rate"] for daily in theme["daily_returns"] if daily["return_date"] == latest_date), None)
        if latest is None:
            missing_started = True
        else:
            assert not missing_started
            values.append(latest)
    assert values == sorted(values, reverse=True)


def test_market_theme_range_return_rejects_unknown_sort() -> None:
    response = client.get(
        "/external/kiwoom/market-themes/returns/range",
        params={"end_date": "2026-07-22", "sort_by": "UNKNOWN"},
    )
    assert response.status_code == 400
