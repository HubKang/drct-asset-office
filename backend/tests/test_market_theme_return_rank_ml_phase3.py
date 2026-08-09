from __future__ import annotations

from backend.app.services.market_theme_return_feature_service import (
    FEATURE_NAMES,
    FEATURE_NAMES_V2,
    FEATURE_VERSION,
    FEATURE_VERSION_V2,
    ThemeFeatureRow,
)
from backend.app.services.market_theme_return_rank_ml_service import (
    METRIC_VERSION,
    evaluate_rank_predictions,
    rank_percentiles,
    selection_gate,
    top_k_labels,
    top_percent_labels,
)


def _rows(dates: tuple[str, ...] = ("2026-08-01",), themes: int = 10) -> list[ThemeFeatureRow]:
    return [
        ThemeFeatureRow("2026-07-31", target_date, theme_id, f"theme-{theme_id}", {"base_change_rate": float(theme_id)}, None, float(themes-theme_id))
        for target_date in dates for theme_id in range(1, themes + 1)
    ]


def test_metric_v2_is_date_local_and_date_averaged() -> None:
    rows = _rows(("2026-08-01", "2026-08-02"))
    first = [float(11-row.theme_id) for row in rows[:10]]
    second = [float(row.theme_id) for row in rows[10:]]
    metrics = evaluate_rank_predictions(rows, first + second)
    assert metrics["precision_at_5"] == .5
    assert metrics["spearman"] == 0
    assert metrics["mean_rank_error"] == 2.5


def test_metric_v2_does_not_change_denominator_when_group_is_smaller_than_k() -> None:
    rows = _rows(themes=4)
    metrics = evaluate_rank_predictions(rows, [4, 3, 2, 1])
    assert metrics["precision_at_3"] == 1
    assert metrics["precision_at_5"] is None
    assert metrics["ndcg_at_5"] is None


def test_rank_percentile_and_top_labels_are_created_inside_each_target_date() -> None:
    rows = _rows(("2026-08-01", "2026-08-02"), themes=10)
    percentiles = rank_percentiles(rows)
    top5 = top_k_labels(rows)
    top20 = top_percent_labels(rows)
    for target_date in ("2026-08-01", "2026-08-02"):
        assert percentiles[(target_date, 1)] == 1
        assert percentiles[(target_date, 10)] == 0
        assert sum(top5[(target_date, theme_id)] for theme_id in range(1, 11)) == 5
        assert sum(top20[(target_date, theme_id)] for theme_id in range(1, 11)) == 2


def test_tie_policy_is_deterministic_by_theme_id() -> None:
    rows = [
        ThemeFeatureRow("2026-07-31", "2026-08-01", theme_id, str(theme_id), {}, None, 1.0)
        for theme_id in (3, 1, 2)
    ]
    percentiles = rank_percentiles(rows)
    assert percentiles[("2026-08-01", 1)] > percentiles[("2026-08-01", 2)] > percentiles[("2026-08-01", 3)]


def test_selection_gate_requires_reference_margin_and_fold_stability() -> None:
    reference = {"ndcg_at_5": .60, "precision_at_5": .60}
    candidate = {"ndcg_at_5": .63, "precision_at_5": .59}
    assert selection_gate(candidate, reference, reference, [.03, .02, .01, .01, -.01, -.02])[0] == "PASS"
    assert selection_gate(candidate, reference, reference, [.08, -.01, -.01, -.01, -.01, -.01])[0] == "FAIL"
    assert selection_gate({"ndcg_at_5": .61, "precision_at_5": .59}, reference, reference, [.01] * 6)[0] == "FAIL"


def test_feature_v2_is_additive_and_versioned() -> None:
    assert FEATURE_VERSION == "THEME_RETURN_FEATURE_V1"
    assert FEATURE_VERSION_V2 == "THEME_RETURN_FEATURE_V2"
    assert METRIC_VERSION == "THEME_RETURN_METRIC_V2"
    assert FEATURE_NAMES_V2[:len(FEATURE_NAMES)] == FEATURE_NAMES
    assert {"return_3d_percentile", "combined_flow_percentile", "price_flow_interaction", "return_minus_cross_section_mean"} <= set(FEATURE_NAMES_V2)


def test_rank_model_metrics_leave_return_error_unset() -> None:
    rows = _rows()
    metrics = evaluate_rank_predictions(rows, [float(11-row.theme_id) for row in rows])
    assert metrics["mae"] is None
    assert metrics["rmse"] is None
    assert metrics["direction_accuracy"] is None
    assert metrics["precision_at_5"] == 1
