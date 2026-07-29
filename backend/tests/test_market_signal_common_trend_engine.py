from __future__ import annotations

from datetime import date, timedelta

from backend.app.services.market_signal_service import MarketSignalService
from backend.app.services.technical_analysis_service import calculate_regression_channel


def test_market_signal_and_training_share_regression_channel_math() -> None:
    start = date(2025, 1, 1)
    series = [{"date": (start + timedelta(days=index)).isoformat(), "value": 100 + index * .8 + (index % 5) * .1} for index in range(140)]
    model = {
        "trend_window": 120,
        "short_window": 20,
        "medium_window": 60,
        "channel_multiplier": 1.8,
        "minimum_trend_strength": 1.0,
        "minimum_r_squared": .18,
        "minimum_trend_duration": 20,
        "minimum_break_persistence": 3,
    }
    service = object.__new__(MarketSignalService)

    diagnostic = service._trend_diagnostic("MARKET_INDEX", "TEST", series[-1]["date"], model=model, source_series=series)
    shared = calculate_regression_channel([row["value"] for row in series[-120:]], 1.8)

    assert diagnostic["regression_slope"] == round(float(shared["slope"]), 8)
    assert diagnostic["normalized_slope"] == round(float(shared["normalized_slope"]), 6)
    assert diagnostic["trend_strength"] == round(float(shared["trend_strength"]), 6)
    assert diagnostic["channel_position"] == round(float(shared["channel_position"]), 6)
    assert diagnostic["channel_upper"] == round(float(shared["channel_upper"]), 6)
    assert diagnostic["channel_lower"] == round(float(shared["channel_lower"]), 6)
