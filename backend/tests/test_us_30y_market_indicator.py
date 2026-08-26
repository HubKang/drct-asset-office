from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.app.providers.economic_data.fred_provider import FredProvider
from backend.app.services.market_indicator_service import MarketIndicatorService


def _us_30y_mapping() -> dict[str, object]:
    return {
        "provider_symbol": "DGS30",
        "request_params_json": {
            "series_id": "DGS30",
            "frequency": "d",
            "value_field": "value",
            "date_field": "date",
            "scale": 1,
            "source_unit": "PCT",
        },
    }


def test_us_30y_uses_dgs30_and_skips_fred_missing_values(monkeypatch) -> None:
    provider = FredProvider()
    captured: dict[str, object] = {}

    def fake_fetch_series_observations(**kwargs):
        captured.update(kwargs)
        return {
            "status": "SUCCESS",
            "rows": [
                {"date": "2026-08-24", "value": "."},
                {"date": "2026-08-25", "value": "4.625"},
            ],
        }

    monkeypatch.setattr(provider, "fetch_series_observations", fake_fetch_series_observations)

    values = provider.collect_values(
        "US_30Y",
        _us_30y_mapping(),
        start_date="2026-08-24",
        end_date="2026-08-25",
    )

    assert captured["series_id"] == "DGS30"
    assert [(row["value_date"], row["value"]) for row in values] == [("2026-08-25", 4.625)]
    assert values[0]["source_unit"] == "PCT"
    assert values[0]["raw_payload_json"] is None


def test_us_30y_upsert_preserves_one_business_key_row_and_applies_revision() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE market_indicator_values (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                indicator_code TEXT NOT NULL,
                value_date TEXT NOT NULL,
                period_label TEXT,
                value REAL,
                change_value REAL,
                change_pct REAL,
                mom_pct REAL,
                yoy_pct REAL,
                source_provider TEXT,
                source_unit TEXT,
                is_preliminary INTEGER,
                release_date TEXT,
                raw_payload_json TEXT,
                collected_at TEXT,
                revised_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(indicator_code, value_date)
            )
            """
        )

    session = sessionmaker(bind=engine)()
    try:
        service = MarketIndicatorService(session)
        base = {
            "indicator_code": "US_30Y",
            "value_date": "2026-08-25",
            "period_label": None,
            "value": 4.625,
            "change_value": None,
            "change_pct": None,
            "mom_pct": None,
            "yoy_pct": None,
            "source_provider": "FRED",
            "source_unit": "PCT",
            "is_preliminary": 0,
            "release_date": None,
            "raw_payload_json": '{"must_not":"persist"}',
        }
        assert service._upsert_values([base]) == {
            "inserted_count": 1,
            "updated_count": 0,
            "unchanged_count": 0,
        }
        revised = {**base, "value": 4.63}
        assert service._upsert_values([revised]) == {
            "inserted_count": 0,
            "updated_count": 1,
            "unchanged_count": 0,
        }
        session.commit()

        row = session.execute(
            text(
                "SELECT COUNT(1), MAX(value), MAX(raw_payload_json) "
                "FROM market_indicator_values WHERE indicator_code = 'US_30Y' AND value_date = '2026-08-25'"
            )
        ).one()
        assert row == (1, 4.63, None)
    finally:
        session.close()
        engine.dispose()
