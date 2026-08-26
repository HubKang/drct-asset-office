from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from backend.app.services.stock_price_service import StockPriceService


def _service(stock=None):
    service = StockPriceService.__new__(StockPriceService)
    service.db = Mock()
    service.stock_repo = Mock()
    service.stock_repo.get_by_id.return_value = stock
    service.price_repo = Mock()
    service.price_repo.get_stock_summary_window.return_value = {
        "price_count": 12,
        "min_trade_date": "2026-07-01",
        "max_trade_date": "2026-07-28",
    }
    service.technical_indicator_service = Mock()
    service.technical_indicator_service.calculate_and_save_for_stock.return_value = {"saved_count": 12}
    service._collect_and_upsert_with_stats = Mock(return_value={"collected_count": 5, "saved_count": 5, "pages_fetched": 1})
    service._resolve_collect_window = Mock(return_value=("full_refresh", date(2024, 7, 28), date(2026, 7, 28), "", None))
    return service


def test_trade_training_price_collection_rejects_invalid_mode():
    service = _service()
    with pytest.raises(HTTPException) as exc:
        service.collect_trade_training_stock_prices(stock_id=1, mode="INVALID")
    assert exc.value.status_code == 400


def test_trade_training_price_collection_returns_404_for_missing_stock():
    service = _service(stock=None)
    with pytest.raises(HTTPException) as exc:
        service.collect_trade_training_stock_prices(stock_id=999, mode="RECENT_7D")
    assert exc.value.status_code == 404


def test_recent_collection_targets_one_stock_and_never_promotes_to_full():
    stock = SimpleNamespace(id=7, stock_code="222800", stock_name="심텍")
    service = _service(stock)
    service._resolve_collect_window.side_effect = AssertionError("recent collection must not resolve a full window")

    result = service.collect_trade_training_stock_prices(stock_id=7, mode="RECENT_7D")

    assert result["target_count"] == 1
    assert result["action"] == "selected_recent_7d"
    assert result["requested_start_date"] == (date.today() - timedelta(days=7)).isoformat()
    kwargs = service._collect_and_upsert_with_stats.call_args.kwargs
    assert kwargs["stock"] is stock
    assert kwargs["max_pages"] == 1
    assert kwargs["recalculate_derived"] is True
    service.technical_indicator_service.calculate_and_save_for_stock.assert_called_once_with(7)


def test_full_collection_uses_existing_two_year_policy_for_one_stock():
    stock = SimpleNamespace(id=8, stock_code="475150", stock_name="SK이터닉스")
    service = _service(stock)

    result = service.collect_trade_training_stock_prices(stock_id=8, mode="FULL")

    assert result["target_count"] == 1
    assert result["action"] == "selected_full"
    service._resolve_collect_window.assert_called_once_with(
        8, "kiwoom_rest", period_years=2, overlap_days=7, force_full_refresh=True
    )
    kwargs = service._collect_and_upsert_with_stats.call_args.kwargs
    assert kwargs["max_pages"] is None
    assert kwargs["stock"].id == 8
    assert result["technical_indicator_saved_count"] == 12

def test_empty_recent_response_keeps_existing_summary_and_skips_indicators():
    stock = SimpleNamespace(id=9, stock_code="089030", stock_name="테크윙")
    service = _service(stock)
    service._collect_and_upsert_with_stats.return_value = {"collected_count": 0, "saved_count": 0, "pages_fetched": 1}

    result = service.collect_trade_training_stock_prices(stock_id=9, mode="RECENT_7D")

    assert result["success"] is False
    assert result["price_count"] == 12
    service.technical_indicator_service.calculate_and_save_for_stock.assert_not_called()
