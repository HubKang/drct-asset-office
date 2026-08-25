from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.app.core.config import now_kst
from backend.app.core.database import get_db
from backend.app.entities.market_theme import MarketTheme
from backend.app.main import app


def _create_us_theme(client: TestClient, group: str, name: str) -> dict:
    group_response = client.post("/us-market-themes/groups", json={"name": group, "sort_order": 1, "active": 1})
    assert group_response.status_code == 201
    response = client.post("/us-market-themes/themes", json={"theme_group_id": group_response.json()["id"], "name": name, "keywords": [], "sort_order": 1, "active": 1})
    assert response.status_code == 201
    return response.json()


def _create_kr_theme(client: TestClient, code: str, group: str, name: str) -> dict:
    override = app.dependency_overrides[get_db]
    session_generator = override()
    db = next(session_generator)
    try:
        now = now_kst()
        parent = MarketTheme(theme_name=group, theme_code=f"{code}_GROUP", theme_type="theme", theme_level="THEME_GROUP", keywords="[]", is_active=1, sort_order=1, created_at=now, updated_at=now)
        db.add(parent); db.flush()
        theme = MarketTheme(theme_name=name, theme_code=code, theme_type="theme", theme_level="THEME", parent_theme_id=parent.id, keywords="[]", is_active=1, sort_order=1, created_at=now, updated_at=now)
        db.add(theme); db.commit(); db.refresh(theme)
        return {"id": theme.id}
    finally:
        session_generator.close()


def test_us_kr_theme_link_crud_and_strict_one_to_one(isolated_api_client: TestClient) -> None:
    client = isolated_api_client
    us_one = _create_us_theme(client, "AI", "AI 반도체/GPU")
    us_two = _create_us_theme(client, "클라우드", "AI 서버·네트워크")
    kr_one = _create_kr_theme(client, "KR_AI_GPU", "반도체", "반도체공정/HBM")
    kr_two = _create_kr_theme(client, "KR_CLOUD", "AI", "AI인프라/AI데이터센터")

    created = client.post("/us-kr-theme-links", json={"us_theme_id": us_one["id"], "kr_theme_id": kr_one["id"], "memo": "D-1 관찰"})
    assert created.status_code == 201
    assert created.json()["us_theme_name"] == "AI 반도체/GPU"

    assert client.post("/us-kr-theme-links", json={"us_theme_id": us_one["id"], "kr_theme_id": kr_two["id"]}).status_code == 409
    assert client.post("/us-kr-theme-links", json={"us_theme_id": us_two["id"], "kr_theme_id": kr_one["id"]}).status_code == 409

    overview = client.get("/us-kr-theme-links/overview")
    assert overview.status_code == 200
    assert overview.json()["summary"] == {"us_active_themes": 2, "kr_active_themes": 2, "linked_themes": 1, "unlinked_us_themes": 1, "unlinked_kr_themes": 1}

    updated = client.patch(f"/us-kr-theme-links/{created.json()['id']}", json={"us_theme_id": us_two["id"], "kr_theme_id": kr_two["id"], "memo": "수정"})
    assert updated.status_code == 200 and updated.json()["memo"] == "수정"
    deleted = client.delete(f"/us-kr-theme-links/{created.json()['id']}")
    assert deleted.status_code == 200
    assert client.get("/us-kr-theme-links/overview").json()["summary"]["linked_themes"] == 0


def test_lead_analysis_matches_next_real_kr_date_and_calculates_metrics(isolated_api_client: TestClient) -> None:
    client = isolated_api_client
    us_theme = _create_us_theme(client, "전력", "원전·SMR")
    kr_theme = _create_kr_theme(client, "KR_NUCLEAR", "에너지", "원전")
    link = client.post("/us-kr-theme-links", json={"us_theme_id": us_theme["id"], "kr_theme_id": kr_theme["id"]}).json()
    second_us_theme = _create_us_theme(client, "바이오", "유전자편집 / 신약개발")
    second_kr_theme = _create_kr_theme(client, "KR_BIO", "제약/바이오", "신약&제약")
    second_link = client.post("/us-kr-theme-links", json={"us_theme_id": second_us_theme["id"], "kr_theme_id": second_kr_theme["id"]}).json()

    override = app.dependency_overrides[get_db]
    session_generator = override()
    db = next(session_generator)
    try:
        db.execute(text("""CREATE TABLE market_theme_daily_returns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            theme_id INTEGER NOT NULL,
            return_date TEXT NOT NULL,
            avg_change_rate REAL,
            stock_count INTEGER,
            success_stock_count INTEGER,
            failed_stock_count INTEGER,
            rising_stock_count INTEGER,
            falling_stock_count INTEGER,
            flat_stock_count INTEGER,
            total_trading_value REAL,
            data_source TEXT,
            first_created_at TEXT,
            last_refreshed_at TEXT,
            created_at TEXT,
            updated_at TEXT,
            UNIQUE(theme_id, return_date)
        )"""))
        for index, (day, value) in enumerate([
            ("2026-08-01", 4.0), ("2026-08-17", -0.5), ("2026-08-18", 0.5),
            ("2026-08-19", 1.5), ("2026-08-20", 2.5), ("2026-08-21", 3.5),
        ], start=1):
            db.execute(text("""INSERT INTO us_theme_daily_returns
                (theme_id,trade_date,simple_return,theme_strength,trimmed_mean_return,median_return,breadth_ratio,
                 valid_stock_count,up_count,down_count,flat_count,created_at,updated_at)
                VALUES (:theme_id,:day,:value,:value,:value,:value,0.5,4,2,2,0,'2026-08-24','2026-08-24')"""),
                {"theme_id": us_theme["id"], "day": day, "value": value})
        for day, value in [("2026-08-17", 9.0), ("2026-08-18", -1.0), ("2026-08-19", 0.5), ("2026-08-20", -0.2), ("2026-08-21", 1.0), ("2026-08-24", 2.0)]:
            db.execute(text("""INSERT INTO market_theme_daily_returns
                (theme_id,return_date,avg_change_rate,stock_count,success_stock_count,failed_stock_count,
                 rising_stock_count,falling_stock_count,flat_stock_count,total_trading_value,data_source,
                 first_created_at,last_refreshed_at,created_at,updated_at)
                VALUES (:theme_id,:day,:value,4,4,0,2,2,0,0,'test','2026-08-24','2026-08-24','2026-08-24','2026-08-24')"""),
                {"theme_id": kr_theme["id"], "day": day, "value": value})
        for day, value in [("2026-08-20", -1.0), ("2026-08-21", -2.0)]:
            db.execute(text("""INSERT INTO us_theme_daily_returns
                (theme_id,trade_date,simple_return,theme_strength,trimmed_mean_return,median_return,breadth_ratio,
                 valid_stock_count,up_count,down_count,flat_count,created_at,updated_at)
                VALUES (:theme_id,:day,:value,:value,:value,:value,0.25,4,1,3,0,'2026-08-24','2026-08-24')"""),
                {"theme_id": second_us_theme["id"], "day": day, "value": value})
        db.execute(text("""INSERT INTO market_theme_daily_returns
            (theme_id,return_date,avg_change_rate,stock_count,success_stock_count,failed_stock_count,
             rising_stock_count,falling_stock_count,flat_stock_count,total_trading_value,data_source,
             first_created_at,last_refreshed_at,created_at,updated_at)
            VALUES (:theme_id,'2026-08-24',9.0,4,4,0,3,1,0,0,'test','2026-08-24','2026-08-24','2026-08-24','2026-08-24')"""),
            {"theme_id": second_kr_theme["id"]})
        db.commit()
    finally:
        session_generator.close()

    response = client.get(f"/us-kr-theme-links/{link['id']}/lead-analysis?window=120&us_metric=theme_strength")
    assert response.status_code == 200
    body = response.json()
    assert body["metrics"]["candidate_count"] == 6
    assert body["metrics"]["sample_count"] == 5
    assert body["metrics"]["excluded_count"] == 1
    assert body["metrics"]["direction_match_rate"] == 80.0
    assert body["metrics"]["us_up_kr_up_rate"] == 75.0
    assert body["metrics"]["us_down_kr_down_rate"] == 100.0
    assert body["metrics"]["avg_kr_return"] == 0.46
    assert body["metrics"]["median_kr_return"] == 0.5
    assert body["metrics"]["pearson_correlation"] is not None
    assert body["metrics"]["spearman_correlation"] is not None
    assert body["pairs"][0]["us_trade_date"] == "2026-08-21"
    assert body["pairs"][0]["kr_trade_date"] == "2026-08-24"
    assert body["pairs"][0]["calendar_gap_days"] == 3
    up_thresholds = [row for row in body["thresholds"] if row["direction"] == "UP"]
    assert [row["sample_count"] for row in up_thresholds] == [4, 3, 2, 1]

    today = client.get("/us-kr-theme-links/today-observation?window=120&us_metric=theme_strength")
    assert today.status_code == 200
    observation = today.json()
    assert observation["latest_us_date"] == "2026-08-21"
    assert observation["previous_us_date"] == "2026-08-20"
    assert observation["kr_target_date"] == "2026-08-24"
    assert observation["summary"] == {"linked_count": 2, "available_count": 2, "missing_count": 0, "up_count": 1, "down_count": 1}
    item = next(row for row in observation["items"] if row["link_id"] == link["id"])
    assert item["latest_value"] == 3.5
    assert item["previous_value"] == 2.5
    assert item["delta"] == 1.0
    assert item["threshold_condition"] == "US ≥ +3%"
    assert item["sample_count"] == up_thresholds[-1]["sample_count"]
    assert item["response_rate"] == up_thresholds[-1]["response_rate"]
    assert item["avg_kr_return"] == up_thresholds[-1]["avg_kr_return"]
    assert item["median_kr_return"] == up_thresholds[-1]["median_kr_return"]
    assert item["previous_kr_date"] == "2026-08-24"
    assert item["previous_kr_return"] == 2.0
    assert item["breadth_ratio"] == 0.5
    assert item["valid_stock_count"] == 4
    second_item = next(row for row in observation["items"] if row["link_id"] == second_link["id"])
    assert second_item["previous_kr_date"] == "2026-08-24"
    assert second_item["previous_kr_return"] == 9.0
    assert client.get(f"/us-kr-theme-links/{link['id']}/lead-analysis?window=61").status_code == 422
    assert client.get("/us-kr-theme-links/today-observation?window=61").status_code == 422


def test_lead_analysis_correlation_is_null_for_constant_or_too_small_samples() -> None:
    from backend.app.services.us_kr_theme_link_service import UsKrThemeLinkService

    assert UsKrThemeLinkService._pearson([1.0], [1.0]) is None
    assert UsKrThemeLinkService._pearson([1.0, 1.0], [2.0, 3.0]) is None
    assert UsKrThemeLinkService._spearman([1.0, 1.0], [2.0, 3.0]) is None
    assert UsKrThemeLinkService._current_threshold(0.0) is None
    assert UsKrThemeLinkService._current_threshold(2.9) == ("UP", 2.0)
    assert UsKrThemeLinkService._current_threshold(-3.1) == ("DOWN", -3.0)
