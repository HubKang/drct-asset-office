from backend.app.services.drct_insight_service import DrctInsightService, _percentile


def test_runtime_percentiles_are_interpolated_without_persisted_thresholds() -> None:
    assert _percentile([], 25) is None
    assert _percentile([10.0, 20.0, 30.0, 40.0], 25) == 17.5
    assert _percentile([10.0, 20.0, 30.0], 50) == 20.0


def test_gate_boundaries_and_missing_data_are_explicit() -> None:
    assert DrctInsightService._theme_gate(None, 5) == "NO_DATA"
    assert DrctInsightService._theme_gate(5, 5) == "PASS"
    assert DrctInsightService._theme_gate(6, 5) == "WATCH"
    assert DrctInsightService._flow_gate(None, 25, 50) == "NO_DATA"
    assert DrctInsightService._flow_gate(50, 25, 50) == "PASS"
    assert DrctInsightService._flow_gate(25, 25, 50) == "WATCH"
    assert DrctInsightService._flow_gate(24.9, 25, 50) == "WEAK"
    assert DrctInsightService._pattern_gate(None, "VERY_SIMILAR", 5, 10) == "NOT_READY"
    assert DrctInsightService._pattern_gate(10, "HIGH_SIMILARITY", 5, 10) == "PASS"
    assert DrctInsightService._pattern_gate(7, "SIMILAR", 5, 10) == "WATCH"
    assert DrctInsightService._pattern_gate(-1, "VERY_SIMILAR", -2, 0) == "WEAK"


def test_final_candidate_requires_all_three_convergence_gates() -> None:
    assert DrctInsightService._is_final_candidate("PASS", "PASS", "PASS")
    assert DrctInsightService._is_final_candidate("PASS", "WATCH", "PASS")
    assert not DrctInsightService._is_final_candidate("WATCH", "PASS", "PASS")
    assert not DrctInsightService._is_final_candidate("PASS", "WEAK", "PASS")
    assert not DrctInsightService._is_final_candidate("PASS", "PASS", "NOT_READY")
