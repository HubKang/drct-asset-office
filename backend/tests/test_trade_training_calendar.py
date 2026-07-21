from backend.app.services.trade_training_service import TradeTrainingService


def calendar_item(
    item_id: str,
    training_type: str,
    completed_date: str,
    completed_at: str,
    session_id: int,
    stock_code: str,
    return_rate: float,
    review_done: bool,
) -> dict:
    return {
        "calendar_item_id": item_id,
        "training_type": training_type,
        "completed_date": completed_date,
        "completed_at": completed_at,
        "session_id": session_id,
        "closed_trade_id": item_id.split(":", 1)[1] if training_type == "ACCOUNT" else None,
        "training_account_id": 1 if training_type == "ACCOUNT" else None,
        "training_account_name": "통합 계좌" if training_type == "ACCOUNT" else None,
        "stock_code": stock_code,
        "stock_name": f"종목 {stock_code}",
        "chart_entry_date": "2026-06-01",
        "chart_exit_date": "2026-06-20",
        "net_pnl": return_rate * 10_000,
        "return_rate": return_rate,
        "result_type": "WIN" if return_rate > 0 else "LOSS" if return_rate < 0 else "FLAT",
        "scenario_execution_rate": 80.0 if training_type == "ACCOUNT" else None,
        "review_status": "복기완료" if review_done else "미복기",
        "review_done": review_done,
    }


def test_unified_calendar_groups_mixed_training_by_actual_completion_date() -> None:
    items = [
        calendar_item("STANDALONE:10", "STANDALONE", "2026-07-03", "2026-07-03 09:00:00", 10, "005930", 4.5, True),
        calendar_item("ACCOUNT:20-1", "ACCOUNT", "2026-07-03", "2026-07-03 11:00:00", 20, "005930", -2.0, False),
        calendar_item("ACCOUNT:21-1", "ACCOUNT", "2026-07-05", "2026-07-05 10:00:00", 21, "000660", 3.0, True),
    ]

    result = TradeTrainingService._build_training_calendar_response("2026-07", items)

    assert result["summary"]["total_trainings"] == 3
    assert result["summary"]["training_days"] == 2
    assert result["summary"]["unique_stock_count"] == 2
    assert result["summary"]["total_return_rate"] == 5.5
    assert result["days"][0]["training_count"] == 2
    assert result["days"][0]["unique_stock_count"] == 1
    assert result["days"][0]["win_count"] == 1
    assert result["days"][0]["loss_count"] == 1
    assert result["days"][0]["items"][0]["calendar_item_id"] == "ACCOUNT:20-1"
    assert result["growth"][2]["daily_return_rate"] == 1.25
    assert result["growth"][-1]["cumulative_return_rate"] == 4.25


def test_unified_calendar_deduplicates_physical_trade_and_ignores_other_month() -> None:
    original = calendar_item("ACCOUNT:30-1", "ACCOUNT", "2026-07-08", "2026-07-08 10:00:00", 30, "035420", 1.0, False)
    updated = {**original, "return_rate": 2.5, "net_pnl": 25_000}
    outside = calendar_item("STANDALONE:99", "STANDALONE", "2026-08-01", "2026-08-01 10:00:00", 99, "035720", 9.0, True)

    result = TradeTrainingService._build_training_calendar_response("2026-07", [original, updated, outside])

    assert result["summary"]["total_trainings"] == 1
    assert result["days"][0]["total_return_rate"] == 2.5
    assert result["days"][0]["items"][0]["net_pnl"] == 25_000


def test_unified_calendar_supports_empty_and_single_day_growth() -> None:
    empty = TradeTrainingService._build_training_calendar_response("2026-07", [])
    assert empty["days"] == []
    assert len(empty["growth"]) == 31
    assert empty["growth"][0] == {
        "date": "2026-07-01",
        "training_count": 0,
        "daily_return_rate": 0.0,
        "cumulative_return_rate": 0.0,
    }
    assert empty["growth"][-1]["date"] == "2026-07-31"

    leap_february = TradeTrainingService._build_training_calendar_response("2024-02", [])
    assert len(leap_february["growth"]) == 29
    assert leap_february["growth"][-1]["date"] == "2024-02-29"

    item = calendar_item("STANDALONE:40", "STANDALONE", "2026-07-21", "2026-07-21 15:30:00", 40, "068270", -1.25, False)
    single = TradeTrainingService._build_training_calendar_response("2026-07", [item])
    assert len(single["growth"]) == 31
    assert single["growth"][20] == {
        "date": "2026-07-21",
        "training_count": 1,
        "daily_return_rate": -1.25,
        "cumulative_return_rate": -1.25,
    }
    assert single["growth"][-1]["cumulative_return_rate"] == -1.25
