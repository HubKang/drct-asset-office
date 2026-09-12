from __future__ import annotations

import pytest

from backend.app.services.market_theme_observation_feature_service import (
    OBSERVATION_FEATURE_NAMES,
    PRICE_FLOW_FEATURE_NAMES,
    PRICE_FLOW_FEATURE_VERSION,
    PRICE_FLOW_STAGE_VERSION,
)
from backend.app.services.market_theme_observation_ml_service import (
    MarketThemeObservationMLService,
    _rank_metrics,
)
from backend.app.services.market_theme_price_flow_research_service import (
    MarketThemePriceFlowResearchService,
)
from backend.app.services.market_theme_return_feature_service import MarketThemeReturnFeatureService


def test_next_observed_session_skips_weekend_and_exchange_holiday() -> None:
    dates = ["2026-09-11", "2026-09-14", "2026-09-16"]
    assert MarketThemeReturnFeatureService._next_observed_trading_date(dates, 0) == "2026-09-14"
    assert MarketThemeReturnFeatureService._next_observed_trading_date(dates, 1) == "2026-09-16"
    assert MarketThemeReturnFeatureService._next_observed_trading_date(dates, 2, "2026-09-17") == "2026-09-17"


def test_phase3_versions_and_features_are_additive() -> None:
    assert PRICE_FLOW_STAGE_VERSION == "PRICE_FLOW_STAGE_V1"
    assert PRICE_FLOW_FEATURE_VERSION == "PRICE_FLOW_FEATURE_V3"
    assert PRICE_FLOW_FEATURE_NAMES[: len(OBSERVATION_FEATURE_NAMES)] == OBSERVATION_FEATURE_NAMES
    assert {
        "flow_acceleration_percentile", "flow_persistence_percentile", "sustainability_score",
        "price_headroom_percentile", "price_flow_gap", "flow_lead_score",
    }.issubset(PRICE_FLOW_FEATURE_NAMES)


def test_stage_aggregation_uses_actual_d1_only() -> None:
    rows = [
        {"stage_code": "EARLY", "actual_percentile": 90.0, "label_rank": 2, "label_top20": 1},
        {"stage_code": "EARLY", "actual_percentile": 30.0, "label_rank": 12, "label_top20": 0},
        {"stage_code": "CONFIRMED", "actual_percentile": 80.0, "label_rank": 4, "label_top20": 1},
    ]
    metrics = {item.stage_code: item for item in MarketThemePriceFlowResearchService._stage_metrics(rows)}
    assert metrics["EARLY"].sample_count == 2
    assert metrics["EARLY"].top10_rate == pytest.approx(.5)
    assert metrics["EARLY"].top20_rate == pytest.approx(.5)
    assert metrics["EARLY"].mean_actual_percentile == pytest.approx(60)
    assert metrics["EARLY"].bottom_half_rate == pytest.approx(.5)


def test_success_failure_radar_means_are_axis_local_percentiles() -> None:
    rows = [
        {"price_score": 60, "flow_score": 80, "flow_acceleration_percentile": 90, "breadth_score": 70, "sustainability_score": 75},
        {"price_score": 40, "flow_score": 60, "flow_acceleration_percentile": 70, "breadth_score": 50, "sustainability_score": 55},
    ]
    radar = MarketThemePriceFlowResearchService._radar(rows)
    assert radar.price_strength == pytest.approx(50)
    assert radar.flow_strength == pytest.approx(70)
    assert radar.flow_acceleration == pytest.approx(80)
    assert radar.breadth == pytest.approx(60)
    assert radar.sustainability == pytest.approx(65)


def test_top5_bottom_half_rate_counts_severe_failures() -> None:
    rows = [
        {"target_date": "2026-09-14", "theme_id": index, "label_rank": actual_rank,
         "label_top20": int(actual_rank <= 2), "label_return": float(11 - actual_rank), "score": float(11 - index)}
        for index, actual_rank in enumerate((1, 2, 3, 8, 10, 4, 5, 6, 7, 9), start=1)
    ]
    metrics = _rank_metrics(rows, "score")
    assert metrics["top5_bottom_half_rate"] == pytest.approx(.4)


def test_walk_forward_and_historical_holdout_are_strictly_separated() -> None:
    dates = [f"2026-{month:02d}-{day:02d}" for month in range(1, 5) for day in range(1, 21)]
    development, holdout = dates[:-21], dates[-21:]
    assert max(development) < min(holdout)
    for training, validation in MarketThemeObservationMLService._folds(development):
        assert max(training) < min(validation)
        assert set(training).isdisjoint(validation)


def test_contiguous_stage_folds_cover_dates_once() -> None:
    dates = [f"2026-08-{day:02d}" for day in range(1, 21)]
    folds = MarketThemePriceFlowResearchService._contiguous_folds(dates)
    assert [item for fold in folds for item in fold] == dates
    assert len(folds) == 4
