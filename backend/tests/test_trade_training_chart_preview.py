from __future__ import annotations

from datetime import date, timedelta
import json

from backend.app.services.trade_training_service import (
    TRAINING_PREVIEW_CANDLE_COUNT,
    TradeTrainingService,
)


class ChartPreviewRepo:
    def __init__(self, history_count: int, moving_averages: list[int]) -> None:
        start = date(2026, 4, 1)
        self.history = [self._price(start - timedelta(days=offset)) for offset in range(history_count, 0, -1)]
        self.session_prices = [self._price(start), self._price(start + timedelta(days=1))]
        self.requested_history_limit: int | None = None
        self.session = {
            "id": 1,
            "stock_code": "000001",
            "stock_name": "Preview Test",
            "method_id": None,
            "training_account_id": None,
            "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=1)).isoformat(),
            "current_date": start.isoformat(),
            "current_index": 0,
            "initial_cash": 50_000_000,
            "cash": 50_000_000,
            "position_qty": 0,
            "avg_price": 0,
            "realized_profit": 0,
            "status": "RUNNING",
            "options_json": json.dumps({
                "stock_id": 1,
                "source": "test",
                "moving_averages": moving_averages,
            }),
            "created_at": None,
            "updated_at": None,
        }

    @staticmethod
    def _price(trade_date: date) -> dict:
        close = float(10_000 + trade_date.toordinal() % 100)
        return {
            "trade_date": trade_date.isoformat(),
            "open_price": close - 10,
            "high_price": close + 20,
            "low_price": close - 20,
            "close_price": close,
            "volume": 1_000,
            "trading_value": 10_000_000,
        }

    def get_session(self, session_id: int) -> dict:
        return self.session

    def list_prices(self, stock_id: int, source: str, start_date: str, end_date: str) -> list[dict]:
        return self.session_prices

    def list_prices_before(self, stock_id: int, source: str, before_date: str, limit: int) -> list[dict]:
        self.requested_history_limit = limit
        return self.history[-limit:]

    def get_trade_method(self, method_id: int) -> None:
        return None

    def list_trades(self, session_id: int) -> list[dict]:
        return []


def build_service(history_count: int, moving_averages: list[int]) -> tuple[TradeTrainingService, ChartPreviewRepo]:
    repo = ChartPreviewRepo(history_count, moving_averages)
    service = object.__new__(TradeTrainingService)
    service.repo = repo
    service.db = None
    service.get_current_risk_scenario_detail = lambda session_id: None
    return service, repo


def test_session_detail_includes_exactly_thirty_pre_start_candles() -> None:
    service, repo = build_service(history_count=200, moving_averages=[5, 120])

    detail = service.get_session_detail(1)

    assert repo.requested_history_limit == TRAINING_PREVIEW_CANDLE_COUNT + 119
    assert len(detail["candles"]) == TRAINING_PREVIEW_CANDLE_COUNT + 1
    assert detail["candles"][0]["trade_date"] == repo.history[-TRAINING_PREVIEW_CANDLE_COUNT]["trade_date"]
    assert detail["candles"][-1]["trade_date"] == repo.session["start_date"]
    assert detail["current_candle"]["trade_date"] == repo.session["start_date"]
    assert detail["candles"][0]["moving_averages"]["ma120"] is not None


def test_session_detail_starts_with_first_training_candle_without_history() -> None:
    service, _ = build_service(history_count=0, moving_averages=[5, 20])

    detail = service.get_session_detail(1)

    assert len(detail["candles"]) == 1
    assert detail["candles"][0]["trade_date"] == detail["session"]["start_date"]
    assert detail["current_candle"]["trade_date"] == detail["session"]["start_date"]