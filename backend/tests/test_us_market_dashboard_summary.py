from __future__ import annotations

from backend.app.schemas.us_market_theme_schema import UsThemeTrendItem, UsThemeTrendPoint, UsThemeTrendResponse
from backend.app.services.us_market_data_service import UsMarketDataService


class _ScalarSession:
    def scalar(self, statement):
        sql = str(statement)
        if "MAX(updated_at)" in sql:
            return "2026-08-26 09:11:46"
        if "COUNT(*)" in sql:
            return 2
        raise AssertionError(sql)


def _point(day: int, simple_return: float, strength: float) -> UsThemeTrendPoint:
    return UsThemeTrendPoint(
        trade_date=f"2026-08-{day:02d}", simple_return=simple_return, theme_strength=strength,
        rolling_30d_simple_return=simple_return * 3, rolling_30d_theme_strength=strength * 3,
        rolling_30d_valid_count=3, breadth_ratio=0.5, valid_stock_count=2, up_count=1,
    )


def test_dashboard_summary_returns_both_rankings_from_one_trend_projection() -> None:
    service = UsMarketDataService(_ScalarSession(), provider=object())
    service.trend = lambda **_: UsThemeTrendResponse(period=30, dates=[], items=[
        UsThemeTrendItem(theme_id=1, theme_group_id=1, theme_group_name="AI", theme_name="Alpha", active=1,
                         points=[_point(day, 1.0, 2.0) for day in range(11, 21)]),
        UsThemeTrendItem(theme_id=2, theme_group_id=1, theme_group_name="AI", theme_name="Beta", active=1,
                         points=[_point(day, -1.0 if day < 20 else 3.0, 5.0) for day in range(11, 21)]),
    ])

    result = service.dashboard_summary()

    assert result.latest_date == "2026-08-20"
    assert result.active_theme_count == 2
    assert [row.theme_name for row in result.top_strength] == ["Beta", "Alpha"]
    assert [row.theme_name for row in result.top_persistence] == ["Alpha", "Beta"]
    assert result.top_persistence[0].positive_days == 10
    assert result.top_persistence[0].persistence_rate == 100.0
