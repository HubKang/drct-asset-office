from datetime import date, timedelta

from fastapi.testclient import TestClient

from backend.app.core.config import now_kst
from backend.app.main import app


client = TestClient(app)


def test_monthly_supply_calendar_includes_kst_rolling_30d_summary() -> None:
    response = client.get(
        "/external/kiwoom/theme-flow/monthly/calendar",
        params={"month": "2026-07"},
    )

    assert response.status_code == 200
    body = response.json()
    summary = body["summary_30d"]
    period_end = date.fromisoformat(now_kst()[:10])
    assert summary["period_end_date"] == period_end.isoformat()
    assert summary["period_start_date"] == (period_end - timedelta(days=30)).isoformat()
    assert summary["appeared_theme_count"] >= 0
    assert len(summary["top_stocks"]) <= 3
    assert [item["rank"] for item in summary["top_stocks"]] == list(range(1, len(summary["top_stocks"]) + 1))
    appearances = [item["appearance_count"] for item in summary["top_stocks"]]
    assert appearances == sorted(appearances, reverse=True)


def test_monthly_supply_summary_is_independent_of_selected_calendar_month() -> None:
    june = client.get(
        "/external/kiwoom/theme-flow/monthly/calendar",
        params={"month": "2026-06"},
    )
    july = client.get(
        "/external/kiwoom/theme-flow/monthly/calendar",
        params={"month": "2026-07"},
    )

    assert june.status_code == 200
    assert july.status_code == 200
    assert june.json()["month"] == "2026-06"
    assert july.json()["month"] == "2026-07"
    assert june.json()["summary_30d"] == july.json()["summary_30d"]
