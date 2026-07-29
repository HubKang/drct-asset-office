from __future__ import annotations

from datetime import date, timedelta
import json

from backend.app.schemas.trade_training_schema import TechnicalAnalysisPreviewRequest
from backend.app.services.technical_analysis_service import calculate_technical_analysis
from backend.app.services.trade_training_service import TradeTrainingService


def price(day: date, index: int, shock: float = 0) -> dict:
    close = 10_000 + index * 15 + shock
    return {
        "trade_date": day.isoformat(),
        "open_price": close - 10,
        "high_price": close + 35,
        "low_price": close - 30,
        "close_price": close,
        "volume": 1_000 + index * 7 + abs(shock),
        "trading_value": 10_000_000,
    }


def test_future_rows_do_not_change_any_technical_result() -> None:
    start = date(2025, 1, 1)
    known = [price(start + timedelta(days=index), index) for index in range(160)]
    as_of = known[-1]["trade_date"]
    future = [price(start + timedelta(days=160 + index), 160 + index, 1_000_000 if index == 4 else -800_000) for index in range(10)]

    baseline = calculate_technical_analysis(known, as_of_date=as_of, display_period="1Y")
    with_future = calculate_technical_analysis([*known, *future], as_of_date=as_of, display_period="1Y")

    assert with_future == baseline
    assert baseline["analysis_end_date"] == as_of
    assert baseline["current_candle"]["date"] == as_of
    assert all(point["date"] <= as_of for key in ("regression_points", "upper_channel_points", "lower_channel_points") for point in baseline["overlay"][key])


class PreviewRepo:
    def __init__(self) -> None:
        self.as_of = date(2025, 8, 1)
        start = self.as_of - timedelta(days=220)
        self.rows = [price(start + timedelta(days=index), index) for index in range(221)]
        self.session = {
            "id": 99123, "stock_code": "005930", "stock_name": "테스트", "current_date": self.as_of.isoformat(),
            "start_date": (self.as_of - timedelta(days=60)).isoformat(), "options_json": json.dumps({"stock_id": 7, "source": "test"}),
        }
        self.query_end_date = None
        self.write_count = 0

    def get_session(self, session_id: int) -> dict:
        return self.session

    def list_prices_through(self, stock_id: int, source: str, end_date: str, limit: int) -> list[dict]:
        self.query_end_date = end_date
        assert limit <= 600
        return [row for row in self.rows if row["trade_date"] <= end_date][-limit:]

    def __getattr__(self, name: str):
        if name.startswith(("create", "insert", "update", "save", "delete", "upsert")):
            def forbidden(*args, **kwargs):
                self.write_count += 1
                raise AssertionError(f"preview attempted persistence: {name}")
            return forbidden
        raise AttributeError(name)


def test_preview_clamps_future_request_and_does_not_persist() -> None:
    service = object.__new__(TradeTrainingService)
    repo = PreviewRepo()
    service.repo, service.db = repo, None
    payload = TechnicalAnalysisPreviewRequest(
        training_session_id=99123,
        stock_code="005930",
        as_of_date="2099-12-31",
        display_period="ALL",
        configuration={"trend_window": 80},
    )

    first = service.preview_technical_analysis(payload)
    second = service.preview_technical_analysis(payload)

    assert first["as_of_date"] == repo.session["current_date"]
    assert repo.query_end_date == repo.session["current_date"]
    assert first["analysis_observation_count"] == 80
    assert second["performance"]["cache_hit"] is True
    assert repo.write_count == 0
