from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.app.services.market_data_collection_service import MarketDataCollectionService
from backend.app.services.market_theme_observation_service import MarketThemeObservationService
from backend.app.services.market_theme_observation_validation_service import MarketThemeObservationValidationService


class _ScalarResult:
    def scalar(self) -> object:
        return "2026-08-09T09:00:00"


class _FakeDB:
    def execute(self, *_args: object, **_kwargs: object) -> _ScalarResult:
        return _ScalarResult()

    def rollback(self) -> None:
        pass


def _summary(events: list[str]) -> dict[str, object]:
    events.append("auto_validation")
    return {"status": "SUCCESS", "target_date": "2026-08-08", "modes": ["CURRENT_MARKET_DATA"],
            "quality_status": "QUALIFIED", "message": "validated", "diagnostic_status": "HEALTHY"}


def test_current_workflow_validates_before_observation_calculation(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    service = MarketThemeObservationService(_FakeDB())  # type: ignore[arg-type]
    monkeypatch.setattr(MarketThemeObservationValidationService, "auto_validate_latest_actual", lambda _self: _summary(events))
    monkeypatch.setattr(service, "calculate", lambda *_args, **_kwargs: events.append("calculate") or SimpleNamespace())
    result = service.calculate_with_market_option("2026-08-10", refresh_market_indicators=False)
    assert events == ["auto_validation", "calculate"]
    assert result.pre_validation_status == "SUCCESS"


def test_refreshed_workflow_validates_then_refreshes_then_calculates(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    service = MarketThemeObservationService(_FakeDB())  # type: ignore[arg-type]
    monkeypatch.setattr(MarketThemeObservationValidationService, "auto_validate_latest_actual", lambda _self: _summary(events))
    monkeypatch.setattr(MarketDataCollectionService, "collect", lambda *_args, **_kwargs: events.append("market_refresh") or
                        {"status": "SUCCESS", "run_id": 1, "inserted_count": 1, "updated_count": 0, "failed_count": 0})
    monkeypatch.setattr(service, "calculate", lambda *_args, **_kwargs: events.append("calculate") or SimpleNamespace(message=None))
    result = service.calculate_with_market_option("2026-08-10", refresh_market_indicators=True)
    assert events == ["auto_validation", "market_refresh", "calculate"]
    assert result.pre_validation_status == "SUCCESS"


def test_auto_validation_exception_does_not_block_d1_calculation(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    service = MarketThemeObservationService(_FakeDB())  # type: ignore[arg-type]
    monkeypatch.setattr(MarketThemeObservationValidationService, "auto_validate_latest_actual",
                        lambda _self: (_ for _ in ()).throw(RuntimeError("validation unavailable")))
    monkeypatch.setattr(service, "calculate", lambda *_args, **_kwargs: events.append("calculate") or SimpleNamespace())
    result = service.calculate_with_market_option("2026-08-10", refresh_market_indicators=False)
    assert events == ["calculate"]
    assert result.pre_validation_status == "AUTO_VALIDATION_FAILED"
