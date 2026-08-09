from __future__ import annotations

from backend.app.schemas.market_theme_observation_schema import MarketThemeObservationItem
from backend.app.services.market_theme_observation_service import MarketThemeObservationService


def test_actual_relative_strength_uses_shared_zero_to_one_hundred_scale() -> None:
    calculate = MarketThemeObservationService.actual_relative_strength
    assert calculate(1, 35) == 100.0
    assert calculate(18, 35) == 50.0
    assert calculate(35, 35) == 0.0
    assert calculate(1, 1) == 100.0


def test_actual_relative_strength_rejects_missing_or_invalid_rank() -> None:
    calculate = MarketThemeObservationService.actual_relative_strength
    assert calculate(None, 35) is None
    assert calculate(0, 35) is None
    assert calculate(36, 35) is None
    assert calculate(1, 0) is None


def test_relative_strength_gap_uses_actual_minus_prediction_sign() -> None:
    calculate = MarketThemeObservationService.relative_strength_gap
    assert calculate(72.0, 91.2) == 19.2
    assert calculate(78.6, 58.4) == -20.2
    assert calculate(50.0, 50.0) == 0.0
    assert calculate(72.0, None) is None


def test_observation_item_exposes_only_scalar_gap_fields() -> None:
    fields = MarketThemeObservationItem.model_fields
    assert {"actual_relative_strength", "relative_strength_gap", "current_score", "refreshed_score"} <= set(fields)
    assert not any("json" in name or "snapshot" in name for name in fields)
