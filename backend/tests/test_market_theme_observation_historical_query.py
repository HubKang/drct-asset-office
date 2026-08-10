from __future__ import annotations

from fastapi import HTTPException
import pytest

from backend.app.services.market_theme_observation_service import MarketThemeObservationService


class _EmptyResult:
    def __init__(self, scalar_value: object = None) -> None:
        self.scalar_value = scalar_value

    def scalar(self) -> object:
        return self.scalar_value

    def mappings(self) -> "_EmptyResult":
        return self

    def first(self) -> None:
        return None


class _NoStoredRunSession:
    def execute(self, statement: object, params: object = None) -> _EmptyResult:
        sql = str(statement)
        if "MAX(return_date)" in sql:
            return _EmptyResult("2026-08-10")
        return _EmptyResult()


def test_historical_query_date_is_not_subject_to_calculation_rules() -> None:
    parsed = MarketThemeObservationService.validate_observation_query_date("2026-08-07")
    assert parsed.isoformat() == "2026-08-07"


@pytest.mark.parametrize("target_date", ["2026-08-07", "2026-08-10"])
def test_calculation_rejects_dates_on_or_before_latest_cutoff(target_date: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        MarketThemeObservationService.validate_observation_calculate_date(target_date, "2026-08-10")
    assert exc_info.value.status_code == 422
    assert "과거 대상일" in str(exc_info.value.detail)


def test_calculation_rejects_weekend_after_latest_cutoff() -> None:
    with pytest.raises(HTTPException) as exc_info:
        MarketThemeObservationService.validate_observation_calculate_date("2026-08-15", "2026-08-10")
    assert exc_info.value.status_code == 422
    assert "평일" in str(exc_info.value.detail)


def test_missing_historical_run_keeps_requested_date_out_of_defaulting() -> None:
    result = MarketThemeObservationService(_NoStoredRunSession()).get("2026-08-07")  # type: ignore[arg-type]
    assert result.run is None
    assert result.data_cutoff_date is None
    assert result.calculation_data_cutoff_date == "2026-08-10"
    assert result.default_target_date is None
    assert result.message == "2026-08-07에 저장된 관찰결과가 없습니다."
