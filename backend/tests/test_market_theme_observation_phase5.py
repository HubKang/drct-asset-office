from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.app.services.market_data_collection_service import MarketDataCollectionService
from backend.app.services.market_theme_observation_feature_service import MarketThemeObservationFeatureService
from backend.app.services.market_theme_observation_service import MarketThemeObservationService


class _ScalarResult:
    def __init__(self, value: object) -> None:
        self.value = value

    def scalar(self) -> object:
        return self.value


class _FakeDB:
    def execute(self, *_args: object, **_kwargs: object) -> _ScalarResult:
        return _ScalarResult("2026-08-08T21:40:00")

    def rollback(self) -> None:
        pass


def test_phase5_routes_are_registered_before_dynamic_theme_route() -> None:
    from backend.app.main import app

    routes = [(route.path, getattr(route, "methods", set())) for route in app.routes]
    expected = {
        ("/market-themes/observation-priorities/latest", "GET"),
        ("/market-themes/observation-priorities", "GET"),
        ("/market-themes/observation-priorities/calculate", "POST"),
    }
    registered = {(path, method) for path, methods in routes for method in methods}
    assert expected <= registered

    calculate_index = next(index for index, (path, _) in enumerate(routes) if path == "/market-themes/observation-priorities/calculate")
    dynamic_index = next(index for index, (path, _) in enumerate(routes) if path == "/market-themes/{theme_id}")
    assert calculate_index < dynamic_index


def test_current_mode_never_calls_market_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MarketThemeObservationService(_FakeDB())  # type: ignore[arg-type]
    monkeypatch.setattr(MarketDataCollectionService, "collect", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("refresh called")))
    monkeypatch.setattr(service, "calculate", lambda target_date, **kwargs: {"target": target_date, **kwargs})
    result = service.calculate_with_market_option("2026-08-10", refresh_market_indicators=False)
    assert result["calculation_mode"] == "CURRENT_MARKET_DATA"  # type: ignore[index]


def test_refreshed_mode_runs_refresh_before_observation(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    service = MarketThemeObservationService(_FakeDB())  # type: ignore[arg-type]

    def refresh(*_args: object, **_kwargs: object) -> dict[str, object]:
        events.append("refresh")
        return {"status": "SUCCESS", "run_id": 7, "inserted_count": 2, "updated_count": 3, "failed_count": 0}

    def calculate(_target_date: str, **kwargs: object) -> SimpleNamespace:
        events.append("calculate")
        return SimpleNamespace(message=None, kwargs=kwargs)

    monkeypatch.setattr(MarketDataCollectionService, "collect", refresh)
    monkeypatch.setattr(service, "calculate", calculate)
    result = service.calculate_with_market_option("2026-08-10", refresh_market_indicators=True)
    assert events == ["refresh", "calculate"]
    assert result.kwargs["calculation_mode"] == "REFRESHED_MARKET_DATA"
    assert result.kwargs["market_indicator_updated_count"] == 5


def test_failed_refresh_blocks_observation(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MarketThemeObservationService(_FakeDB())  # type: ignore[arg-type]
    monkeypatch.setattr(MarketDataCollectionService, "collect", lambda *_args, **_kwargs: {"status": "FAILED", "run_id": 8})
    monkeypatch.setattr(service, "calculate", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("calculation called")))
    with pytest.raises(HTTPException) as exc:
        service.calculate_with_market_option("2026-08-10", refresh_market_indicators=True)
    assert exc.value.status_code == 502
    assert exc.value.detail["code"] == "MARKET_REFRESH_FAILED"


def test_partial_refresh_is_explicit_and_keeps_existing_values(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MarketThemeObservationService(_FakeDB())  # type: ignore[arg-type]
    monkeypatch.setattr(MarketDataCollectionService, "collect", lambda *_args, **_kwargs: {
        "status": "PARTIAL_SUCCESS", "run_id": 9, "inserted_count": 1, "updated_count": 0, "failed_count": 2,
    })
    monkeypatch.setattr(service, "calculate", lambda *_args, **kwargs: SimpleNamespace(message=None, kwargs=kwargs))
    result = service.calculate_with_market_option("2026-08-10", refresh_market_indicators=True)
    assert result.kwargs["market_refresh_status"] == "PARTIAL"
    assert "기존값" in result.message


def test_full_refresh_lock_rejects_duplicate_execution() -> None:
    assert MarketDataCollectionService._incremental_all_lock.acquire(blocking=False)
    try:
        with pytest.raises(HTTPException) as exc:
            MarketDataCollectionService(_FakeDB()).collect(SimpleNamespace(mode="INCREMENTAL_ALL"))  # type: ignore[arg-type]
        assert exc.value.status_code == 409
        assert exc.value.detail["code"] == "MARKET_REFRESH_ALREADY_RUNNING"
    finally:
        MarketDataCollectionService._incremental_all_lock.release()


def test_market_environment_uses_only_available_non_null_features() -> None:
    risk_on = MarketThemeObservationFeatureService._market_environment({"market_kospi_1d": 1.0, "macro_us_nasdaq_1d": 2.0})
    risk_off = MarketThemeObservationFeatureService._market_environment({"market_kospi_1d": -1.0, "macro_us_nasdaq_1d": -2.0})
    assert risk_on is not None and risk_off is not None and risk_on > 50 > risk_off
    assert MarketThemeObservationFeatureService._market_environment({"market_kospi_1d": None}) is None
