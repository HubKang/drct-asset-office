from __future__ import annotations

import numpy as np

from backend.app.services.market_theme_observation_feature_service import (
    OBSERVATION_FEATURE_NAMES,
    OBSERVATION_FEATURE_VERSION,
    MarketThemeObservationFeatureService,
)
from backend.app.services.market_theme_observation_ml_service import _ece, _rank_metrics, MarketThemeObservationMLService


def test_phase4_feature_contract_is_additive_and_separate() -> None:
    assert OBSERVATION_FEATURE_VERSION == "THEME_OBSERVATION_FEATURE_V1"
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
                         "label_top20": int(theme_id <= 2), "score": float(11-theme_id)})
    metrics = _rank_metrics(rows, "score")
    assert metrics["precision_top20"] == 1
    assert metrics["recall_top20"] == 1
    assert metrics["ndcg_at_5"] == 1
