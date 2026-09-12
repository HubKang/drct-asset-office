from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from backend.app.services.market_theme_observation_feature_service import (
    OBSERVATION_FEATURE_NAMES,
    OBSERVATION_FEATURE_VERSION,
    MarketThemeObservationFeatureService,
)
from backend.app.services.market_theme_observation_ml_service import _ece, _feature_group, _rank_metrics, MarketThemeObservationMLService
from backend.app.services.market_theme_return_feature_service import MarketThemeReturnFeatureService


def test_flow_acceleration_history_window_keeps_six_observations() -> None:
    assert MarketThemeReturnFeatureService._flow_acceleration([1, 2, 3, 4, 5]) is None
    assert MarketThemeReturnFeatureService._flow_acceleration([1, 2, 3, 4, 5, 6]) == 3


def test_cross_section_percentiles_share_tied_positions() -> None:
    assert MarketThemeReturnFeatureService._percentiles({1: 10, 2: 20, 3: 20, 4: 30}) == {
        1: 0.0, 2: 50.0, 3: 50.0, 4: 100.0,
    }


def test_phase4_feature_contract_is_additive_and_separate() -> None:
    assert OBSERVATION_FEATURE_VERSION == "THEME_OBSERVATION_FEATURE_V2"
    assert "observation_rule_score" in OBSERVATION_FEATURE_NAMES
    assert "macro_us_sox_1d" in OBSERVATION_FEATURE_NAMES
    assert "technical_score" in OBSERVATION_FEATURE_NAMES


def test_observation_state_codes_are_deterministic() -> None:
    score, status, confidence = MarketThemeObservationFeatureService._score({
        "price_score": 80, "flow_score": 75, "breadth_score": 70, "liquidity_score": 60,
        "alignment_score": 75, "technical_score": 65, "market_environment_score": 50,
        "penalty_score": 0, "base_change_rate": 2, "data_coverage_rate": .9,
    })
    assert score > 70
    assert status == "STRONG_CONTINUATION"
    assert confidence == "HIGH"
    assert MarketThemeObservationFeatureService._score({"base_change_rate": 9})[1] == "OVERHEAT_RISK"
    assert MarketThemeObservationFeatureService._score({"price_score": 70, "flow_score": 20})[1] == "FLOW_EXIT"


def test_price_flow_signal_stages_are_deterministic() -> None:
    stage = MarketThemeObservationFeatureService.signal_stage
    assert stage({
        "price_score": 45, "flow_score": 88, "flow_acceleration_percentile": 92,
        "breadth_score": 74, "sustainability_score": 86, "penalty_score": 0,
    }) == "EARLY"
    assert stage({
        "price_score": 80, "flow_score": 87, "flow_acceleration_percentile": 78,
        "breadth_score": 84, "sustainability_score": 83, "penalty_score": 0,
    }) == "CONFIRMED"
    assert stage({
        "price_score": 96, "flow_score": 91, "flow_acceleration_percentile": 58,
        "breadth_score": 82, "sustainability_score": 45, "penalty_score": 0,
    }) == "MATURE"
    assert stage({
        "price_score": 78, "flow_score": 55, "flow_acceleration_percentile": 25,
        "breadth_score": 40, "sustainability_score": 22, "penalty_score": 0,
    }) == "EXHAUSTED"


def test_stage_inputs_do_not_change_rule_v2_score() -> None:
    values = {
        "price_score": 80, "flow_score": 75, "breadth_score": 70, "liquidity_score": 60,
        "alignment_score": 75, "technical_score": 65, "market_environment_score": 50,
        "penalty_score": 0, "base_change_rate": 2, "data_coverage_rate": .9,
    }
    original = MarketThemeObservationFeatureService._score(values)
    enriched = MarketThemeObservationFeatureService._score({
        **values, "flow_acceleration_percentile": 1, "sustainability_score": 1,
        "price_flow_gap": -99,
    })
    assert enriched == original


def test_ece_uses_probability_bins_without_zero_filling() -> None:
    assert _ece(np.asarray([0, 0, 1, 1]), np.asarray([.1, .2, .8, .9])) < .2
    assert _ece(np.asarray([0, 0, 1, 1]), np.asarray([.8, .9, .1, .2])) > .6


def test_walk_forward_keeps_validation_after_training() -> None:
    dates = [f"2026-07-{day:02d}" for day in range(1, 25)]
    folds = MarketThemeObservationMLService._folds(dates)
    assert folds
    for training, validation in folds:
        assert max(training) < min(validation)
        assert set(training).isdisjoint(validation)


def test_rank_metrics_are_date_local() -> None:
    rows = []
    for day in ("2026-08-01", "2026-08-02"):
        for theme_id in range(1, 11):
            rows.append({"target_date": day, "theme_id": theme_id, "label_rank": theme_id,
                         "label_top20": int(theme_id <= 2), "label_return": float(11-theme_id), "score": float(11-theme_id)})
    metrics = _rank_metrics(rows, "score")
    assert metrics["precision_top20"] == 1
    assert metrics["recall_top20"] == 1
    assert metrics["ndcg_at_5"] == 1
    assert metrics["precision_at_10"] == .2
    assert metrics["top5_actual_top10_rate"] == 1
    assert metrics["top5_bottom_half_rate"] == 0


def test_feature_groups_keep_flow_acceleration_separate() -> None:
    assert _feature_group("flow_acceleration") == "FLOW_ACCELERATION"
    assert _feature_group("flow_3d_minus_5d") == "FLOW_ACCELERATION"
    assert _feature_group("joint_flow_strength") == "FLOW"
    assert _feature_group("macro_us_sox_1d") == "MARKET"


def test_recent_weights_use_training_order_only() -> None:
    dates = ["2026-01-01", "2026-01-02", "2026-01-03"]
    rows = [SimpleNamespace(base_date=day) for day in dates]
    mild = MarketThemeObservationMLService._weights(rows, dates, "MILD")
    medium = MarketThemeObservationMLService._weights(rows, dates, "MEDIUM")
    assert mild is not None and medium is not None
    assert mild.tolist() == [.75, 1.0, 1.25]
    assert medium.tolist() == [.5, 1.0, 1.5]
