from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.services.dashboard_activity_service import DashboardActivityService


def test_recent_activities_merge_sort_limit_without_persistence(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE trade_journals (id INTEGER, stock_name TEXT, created_at TEXT)"))
        connection.execute(text("CREATE TABLE stocks (id INTEGER, stock_name TEXT)"))
        connection.execute(text("CREATE TABLE chart_markers (id INTEGER, name TEXT)"))
        connection.execute(text("CREATE TABLE chart_marker_events (id INTEGER, stock_id INTEGER, marker_id INTEGER, created_at TEXT)"))
        connection.execute(text("CREATE TABLE market_themes (id INTEGER, theme_name TEXT)"))
        connection.execute(text("CREATE TABLE market_theme_observation_runs (id INTEGER, calculated_at TEXT, evaluated_at TEXT)"))
        connection.execute(text("CREATE TABLE market_theme_observation_items (run_id INTEGER, theme_id INTEGER, observation_rank INTEGER)"))
        connection.execute(text("INSERT INTO trade_journals VALUES (1,'삼성전자','2099-01-05 09:00:00')"))
        connection.execute(text("INSERT INTO stocks VALUES (1,'SK하이닉스')"))
        connection.execute(text("INSERT INTO chart_markers VALUES (1,'장대양봉')"))
        connection.execute(text("INSERT INTO chart_marker_events VALUES (1,1,1,'2099-01-06 09:00:00')"))
        connection.execute(text("INSERT INTO market_themes VALUES (1,'AI반도체')"))
        connection.execute(text("INSERT INTO market_theme_observation_runs VALUES (1,'2099-01-07 09:00:00',NULL)"))
        connection.execute(text("INSERT INTO market_theme_observation_items VALUES (1,1,1)"))

    fake_calendar = {
        "days": [{"items": [{"completed_at": "2099-01-08 00:00:00", "training_type": "STANDALONE", "stock_name": "현대차"}]}]
    }
    monkeypatch.setattr("backend.app.services.dashboard_activity_service.TradeTrainingService.get_training_calendar", lambda self, month: fake_calendar if month == "2099-01" else {"days": []})
    monkeypatch.setattr("backend.app.services.dashboard_activity_service.datetime", type("FixedDateTime", (datetime,), {
        "now": classmethod(lambda cls, tz=None: datetime(2099, 1, 10, 12, 0, tzinfo=tz)),
    }))

    with Session(engine) as session:
        result = DashboardActivityService(session).recent(days=30, limit=3)

    assert len(result["items"]) == 3
    assert [item["type"] for item in result["items"]] == ["TRAINING_COMPLETED", "OBSERVATION_CALCULATION", "CHART_MARKER"]
    assert result["items"][1]["summary"] == "1개 테마 · AI반도체 1위"
    assert all("event_at" in item and "route" in item for item in result["items"])
