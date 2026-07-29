from __future__ import annotations

from datetime import date, timedelta
import json

from backend.app.schemas.trade_training_schema import MultiPeriodTechnicalAnalysisRequest
from backend.app.services.multi_period_technical_analysis import (
    calculate_multi_period_analysis,
    calculate_trend_state_series,
)
from backend.app.services.technical_analysis_service import PERIOD_PROFILES
from backend.app.services.trade_training_service import TradeTrainingService


def candle(day: date, close: float, index: int) -> dict:
    return {
        "trade_date": day.isoformat(),
        "open_price": close - 2,
        "high_price": close + 8,
        "low_price": close - 8,
        "close_price": close,
        "volume": 10_000 + index * 17,
        "trading_value": 100_000_000,
    }


def turning_rows(count: int = 420) -> list[dict]:
    start = date(2024, 1, 1)
    rows = []
    for index in range(count):
        close = 10_000 + index * 18 if index < count - 100 else 18_000 - (index - count + 100) * 42
        rows.append(candle(start + timedelta(days=index), close, index))
    return rows


def test_multi_period_returns_all_summaries_and_selected_detail() -> None:
    rows = turning_rows()
    result = calculate_multi_period_analysis(
        rows,
        as_of_date=rows[-1]["trade_date"],
        selected_period="1Y",
    )
    detail = result["selected_period_detail"]
    assert detail["period_summary"]["period"] == "1Y"
    assert detail["period_summary"]["period_direction"] in {"UP", "DOWN", "SIDEWAYS", "UNCLEAR"}
    assert detail["current_trend"]["direction"] == "DOWN_TREND"
    assert detail["current_trend"]["trend_start_date"] is not None
    assert detail["current_trend"]["persistence_count"] > 1
    assert detail["period_overlay"]["regression_points"]
    assert detail["period_overlay"]["regression_points"][0]["date"] == detail["chart_candles"][0]["trade_date"]
    assert detail["period_overlay"]["regression_points"][-1]["date"] == detail["chart_candles"][-1]["trade_date"]
    assert detail["chart_candles"]
    assert "transition_events" not in detail
    assert "period_summaries" not in result


def test_state_series_detects_both_reversal_directions_without_duplicate_events() -> None:
    start = date(2025, 1, 1)
    closes = [100 + index * 2 for index in range(45)]
    closes += [190 - index * 3 for index in range(45)]
    closes += [55 + index * 4 for index in range(45)]
    rows = [candle(start + timedelta(days=index), close, index) for index, close in enumerate(closes)]

    timeline = calculate_trend_state_series(rows, profile=PERIOD_PROFILES["3M"])
    reversal_directions = [
        event["direction"]
        for event in timeline["events"]
        if event["current_state"] == "REVERSAL_CONFIRMED"
    ]

    assert "DOWN_TREND" in reversal_directions
    assert "UP_TREND" in reversal_directions
    event_states = [
        (event["observation_date"], event["current_state"])
        for event in timeline["events"]
    ]
    assert len(event_states) == len(set(event_states))


def test_future_rows_do_not_change_multi_period_result() -> None:
    rows = turning_rows(360)
    as_of = rows[-1]["trade_date"]
    future_start = date.fromisoformat(as_of) + timedelta(days=1)
    future = [
        candle(future_start + timedelta(days=index), 1_000_000 if index % 2 else 1, index)
        for index in range(20)
    ]

    baseline = calculate_multi_period_analysis(rows, as_of_date=as_of, selected_period="ALL")
    with_future = calculate_multi_period_analysis([*rows, *future], as_of_date=as_of, selected_period="ALL")
    baseline.pop("_calculation_performance")
    with_future.pop("_calculation_performance")

    assert with_future == baseline
    assert all(item["trade_date"] <= as_of for item in baseline["selected_period_detail"]["chart_candles"])


class MultiPeriodRepo:
    def __init__(self, session_id: int) -> None:
        self.rows = turning_rows(500)
        self.session = {
            "id": session_id,
            "stock_code": "005930",
            "stock_name": "테스트",
            "current_date": self.rows[-1]["trade_date"],
            "start_date": self.rows[0]["trade_date"],
            "options_json": json.dumps({"stock_id": 7, "source": "test"}),
        }
        self.query_count = 0
        self.write_count = 0

    def get_session(self, session_id: int) -> dict:
        return self.session

    def list_prices_through(self, stock_id: int, source: str, end_date: str, limit: int) -> list[dict]:
        self.query_count += 1
        assert limit == 5_000
        assert end_date == self.session["current_date"]
        return [row for row in self.rows if row["trade_date"] <= end_date]

    def __getattr__(self, name: str):
        if name.startswith(("create", "insert", "update", "save", "delete", "upsert")):
            def forbidden(*args, **kwargs):
                self.write_count += 1
                raise AssertionError(f"multi-period preview attempted persistence: {name}")
            return forbidden
        raise AttributeError(name)


def service_with_repo(session_id: int) -> tuple[TradeTrainingService, MultiPeriodRepo]:
    service = object.__new__(TradeTrainingService)
    repo = MultiPeriodRepo(session_id)
    service.repo = repo
    service.db = None
    return service, repo


def test_service_queries_ohlcv_once_for_five_periods_and_never_writes() -> None:
    service, repo = service_with_repo(880_001)
    payload = MultiPeriodTechnicalAnalysisRequest(
        training_session_id=repo.session["id"],
        stock_code="005930",
        as_of_date="2099-12-31",
        selected_period="6M",
    )

    result = service.preview_multi_period_technical_analysis(payload)

    assert result["as_of_date"] == repo.session["current_date"]
    assert repo.query_count == 1
    assert repo.write_count == 0
    assert result["performance"]["cache_hit"] is False
    assert result["performance"]["queried_row_count"] == 500
    assert result["performance"]["payload_bytes"] > 0


def test_all_starts_at_training_start_and_never_reveals_warmup_rows() -> None:
    service, repo = service_with_repo(880_003)
    repo.session["start_date"] = repo.rows[275]["trade_date"]
    payload = MultiPeriodTechnicalAnalysisRequest(
        training_session_id=repo.session["id"],
        stock_code="005930",
        as_of_date=repo.session["current_date"],
        selected_period="ALL",
    )

    result = service.preview_multi_period_technical_analysis(payload)
    detail = result["selected_period_detail"]

    assert detail["period_summary"]["display_start_date"] == repo.session["start_date"]
    assert detail["chart_candles"][0]["trade_date"] == repo.session["start_date"]
    assert detail["period_overlay"]["regression_points"][0]["date"] == repo.session["start_date"]
    assert all(item["trade_date"] >= repo.session["start_date"] for item in detail["chart_candles"])


def test_cache_hits_and_selected_periods_have_separate_keys() -> None:
    service, repo = service_with_repo(880_002)
    base = {
        "training_session_id": repo.session["id"],
        "stock_code": "005930",
        "as_of_date": repo.session["current_date"],
    }
    six_month = MultiPeriodTechnicalAnalysisRequest(**base, selected_period="6M")
    one_year = MultiPeriodTechnicalAnalysisRequest(**base, selected_period="1Y")

    first = service.preview_multi_period_technical_analysis(six_month)
    second = service.preview_multi_period_technical_analysis(six_month)
    other_period = service.preview_multi_period_technical_analysis(one_year)

    assert first["performance"]["cache_hit"] is False
    assert second["performance"]["cache_hit"] is True
    assert other_period["performance"]["cache_hit"] is False
    assert repo.write_count == 0
