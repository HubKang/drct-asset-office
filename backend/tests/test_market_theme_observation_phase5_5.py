from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.services.market_theme_observation_validation_service import (
    MarketThemeObservationValidationService,
)


def test_diagnostics_route_is_registered_before_dynamic_theme_route() -> None:
    from backend.app.main import app

    paths = [route.path for route in app.routes]
    assert "/market-themes/observation-priorities/diagnostics" in paths
    assert paths.index("/market-themes/observation-priorities/diagnostics") < paths.index("/market-themes/{theme_id}")


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool)
    raw = engine.raw_connection()
    raw.executescript("""
        PRAGMA foreign_keys=ON;
        CREATE TABLE market_themes (id INTEGER PRIMARY KEY, theme_name TEXT NOT NULL, is_active INTEGER NOT NULL DEFAULT 1, theme_level TEXT NOT NULL DEFAULT 'THEME');
        CREATE TABLE market_theme_daily_returns (
            id INTEGER PRIMARY KEY, theme_id INTEGER NOT NULL, return_date TEXT NOT NULL, avg_change_rate REAL, updated_at TEXT
        );
        CREATE TABLE market_theme_return_prediction_models (
            id INTEGER PRIMARY KEY, target_type TEXT NOT NULL, trained_at TEXT NOT NULL
        );
    """)
    migration = Path("backend/app/sql/migrations/033_market_theme_observation_validation_feedback.sql").read_text(encoding="utf-8")
    raw.executescript(migration)
    raw.commit()
    raw.close()
    session = Session(engine)
    session.execute(text("INSERT INTO market_themes(id,theme_name) VALUES " + ",".join(f"({index},'T{index}')" for index in range(1, 11))))
    session.commit()
    return session


def _rows(reverse: bool = False) -> list[dict[str, object]]:
    theme_ids = list(range(1, 11))
    if reverse:
        theme_ids.reverse()
    return [{"theme_id": theme_id, "rank": index + 1, "score": 100 - index * 5,
             "status": "FLOW_LEADING" if index < 2 else "NEUTRAL", "coverage": 1.0}
            for index, theme_id in enumerate(theme_ids)]


def test_validation_schema_contains_only_scalar_feedback_fields() -> None:
    db = _session()
    columns = [dict(row) for row in db.execute(text("PRAGMA table_info(market_theme_observation_validation_samples)")).mappings()]
    names = {str(row["name"]) for row in columns}
    types = {str(row["type"]).upper() for row in columns}
    assert not ({"feature_json", "analysis_json", "actual_change_rate", "market_snapshot"} & names)
    assert not ({"JSON", "BLOB"} & types)
    db.close()


def test_current_and_refreshed_snapshots_are_preserved_and_upserted_independently() -> None:
    db = _session()
    service = MarketThemeObservationValidationService(db)
    service.snapshot("2026-08-10", "CURRENT_MARKET_DATA", _rows())
    service.snapshot("2026-08-10", "REFRESHED_MARKET_DATA", _rows(reverse=True))
    service.snapshot("2026-08-10", "CURRENT_MARKET_DATA", [{**row, "score": 77.0} for row in _rows()])
    db.commit()
    counts = dict(db.execute(text("""
        SELECT calculation_mode,COUNT(*) count FROM market_theme_observation_validation_samples GROUP BY calculation_mode
    """)).all())
    assert counts == {"CURRENT_MARKET_DATA": 10, "REFRESHED_MARKET_DATA": 10}
    score = db.execute(text("""SELECT observation_score FROM market_theme_observation_validation_samples
        WHERE calculation_mode='CURRENT_MARKET_DATA' AND theme_id=1""")).scalar()
    assert score == 77.0
    db.close()


def test_actual_rank_top20_gap_metrics_and_refresh_effect() -> None:
    db = _session()
    service = MarketThemeObservationValidationService(db)
    service.snapshot("2026-08-10", "CURRENT_MARKET_DATA", _rows())
    service.snapshot("2026-08-10", "REFRESHED_MARKET_DATA", _rows(reverse=True))
    db.execute(text("INSERT INTO market_theme_daily_returns(theme_id,return_date,avg_change_rate) VALUES " +
                    ",".join(f"({theme_id},'2026-08-10',{11-theme_id})" for theme_id in range(1, 11))))
    db.commit()
    assert service.evaluate("2026-08-10") == "EVALUATED"

    current = db.execute(text("""SELECT actual_rank,actual_top20,rank_error,rank_gap,top20_hit
        FROM market_theme_observation_validation_samples WHERE calculation_mode='CURRENT_MARKET_DATA' AND theme_id=1""")).mappings().one()
    assert dict(current) == {"actual_rank": 1, "actual_top20": 1, "rank_error": 0, "rank_gap": 0, "top20_hit": 1}
    refreshed = db.execute(text("""SELECT refresh_rank_improvement,refresh_effect
        FROM market_theme_observation_validation_samples WHERE calculation_mode='REFRESHED_MARKET_DATA' AND theme_id=1""")).mappings().one()
    assert refreshed["refresh_rank_improvement"] == -9
    assert refreshed["refresh_effect"] == -9
    metrics = {row["calculation_mode"]: dict(row) for row in db.execute(text("SELECT * FROM market_theme_observation_validation_metrics")).mappings()}
    assert metrics["CURRENT_MARKET_DATA"]["precision_top20"] == 1.0
    assert metrics["CURRENT_MARKET_DATA"]["ndcg_at_5"] == 1.0
    assert metrics["CURRENT_MARKET_DATA"]["mean_rank_error"] == 0.0
    assert metrics["REFRESHED_MARKET_DATA"]["precision_top20"] == 0.0
    assert metrics["REFRESHED_MARKET_DATA"]["improved_theme_count"] == 0
    assert metrics["REFRESHED_MARKET_DATA"]["worsened_theme_count"] == 10
    db.close()


def test_waiting_actual_does_not_create_fake_metrics() -> None:
    db = _session()
    service = MarketThemeObservationValidationService(db)
    service.snapshot("2026-08-10", "CURRENT_MARKET_DATA", _rows())
    db.commit()
    assert service.evaluate("2026-08-10") == "WAITING_ACTUAL"
    assert db.execute(text("SELECT COUNT(*) FROM market_theme_observation_validation_metrics")).scalar() == 0
    assert db.execute(text("SELECT COUNT(*) FROM market_theme_observation_validation_samples WHERE evaluation_status!='PENDING'")).scalar() == 0
    db.close()


def test_quality_gate_and_diagnostics_use_persisted_scalar_metrics() -> None:
    db = _session()
    service = MarketThemeObservationValidationService(db)
    service.snapshot("2026-08-10", "CURRENT_MARKET_DATA", _rows())
    db.execute(text("INSERT INTO market_theme_daily_returns(theme_id,return_date,avg_change_rate) VALUES " +
                    ",".join(f"({theme_id},'2026-08-10',{11-theme_id})" for theme_id in range(1, 11))))
    db.commit()
    service.evaluate("2026-08-10")
    diagnostics = service.diagnostics()
    assert diagnostics.quality_evaluated_days == 1
    assert diagnostics.recent_5.current.precision_top20 == 1.0
    assert diagnostics.diagnostic_status == "INSUFFICIENT_DATA"
    assert diagnostics.messages[0].code == "INSUFFICIENT_DATA"
    assert diagnostics.status_performance
    assert diagnostics.score_bucket_performance
    db.close()


def test_auto_validation_waits_when_actual_universe_is_incomplete() -> None:
    db = _session()
    db.execute(text("INSERT INTO market_theme_daily_returns(theme_id,return_date,avg_change_rate) VALUES " +
                    ",".join(f"({theme_id},'2026-08-10',{theme_id})" for theme_id in range(1, 5))))
    db.commit()
    result = MarketThemeObservationValidationService(db).auto_validate_latest_actual()
    assert result["status"] == "AUTO_VALIDATION_WAITING_ACTUAL"
    assert db.execute(text("SELECT COUNT(*) FROM market_theme_observation_validation_metrics")).scalar() == 0
    db.close()


def test_auto_validation_skips_latest_actual_without_observation_snapshot() -> None:
    db = _session()
    db.execute(text("INSERT INTO market_theme_daily_returns(theme_id,return_date,avg_change_rate) VALUES " +
                    ",".join(f"({theme_id},'2026-08-10',{theme_id})" for theme_id in range(1, 11))))
    db.commit()
    result = MarketThemeObservationValidationService(db).auto_validate_latest_actual()
    assert result["status"] == "AUTO_VALIDATION_SKIPPED_NO_OBSERVATION"
    assert result["target_date"] == "2026-08-10"
    db.close()


def test_auto_validation_catches_up_modes_and_revalidates_modified_actual() -> None:
    db = _session()
    service = MarketThemeObservationValidationService(db)
    service.snapshot("2026-08-10", "CURRENT_MARKET_DATA", _rows())
    service.snapshot("2026-08-10", "REFRESHED_MARKET_DATA", _rows(reverse=True))
    db.execute(text("INSERT INTO market_theme_daily_returns(theme_id,return_date,avg_change_rate,updated_at) VALUES " +
                    ",".join(f"({theme_id},'2026-08-10',{11-theme_id},'2026-08-08T09:00:00')" for theme_id in range(1, 11))))
    db.commit()
    first = service.auto_validate_latest_actual()
    assert first["status"] == "SUCCESS"
    assert first["modes"] == ["CURRENT_MARKET_DATA", "REFRESHED_MARKET_DATA"]
    assert db.execute(text("SELECT COUNT(*) FROM market_theme_observation_validation_metrics")).scalar() == 2
    second = service.auto_validate_latest_actual()
    assert second["status"] == "AUTO_VALIDATION_UP_TO_DATE"

    db.execute(text("UPDATE market_theme_daily_returns SET avg_change_rate=-avg_change_rate,updated_at='2099-01-01T00:00:00' WHERE return_date='2026-08-10'"))
    db.commit()
    third = service.auto_validate_latest_actual()
    assert third["status"] == "SUCCESS"
    assert db.execute(text("SELECT COUNT(*) FROM market_theme_observation_validation_metrics")).scalar() == 2
    current_precision = db.execute(text("""SELECT precision_top20 FROM market_theme_observation_validation_metrics
        WHERE calculation_mode='CURRENT_MARKET_DATA'""")).scalar()
    assert current_precision == 0.0
    db.close()
