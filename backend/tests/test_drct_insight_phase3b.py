from backend.app.services.drct_insight_service import (
    FOCUS_CANDIDATE_LIMIT,
    FOCUS_MAX_PER_THEME,
    DrctInsightService,
)


def _row(
    stock_id: int,
    theme_id: int,
    *,
    flow: str = "PASS",
    us_up: bool = True,
    rank: int = 1,
    similarity: float = 85,
    relative: float | None = 1.0,
    preliminary: bool = True,
) -> dict:
    return {
        "stock_id": stock_id,
        "stock_name": f"종목 {stock_id}",
        "theme_id": theme_id,
        "observation_rank": rank,
        "preliminary_candidate": preliminary,
        "gates": {"flow": flow},
        "us_lead": {
            "relation_status": "AVAILABLE" if us_up else "MISSING",
            "direction": "UP" if us_up else None,
        },
        "success_similarity": similarity,
        "pattern_status": "PROMISING",
        "relative_strength": relative,
        "change_rate": 2.0,
    }


def test_focus_selector_limits_count_and_diversifies_by_theme() -> None:
    rows = [_row(stock_id, 1, similarity=100 - stock_id) for stock_id in range(1, 8)]
    rows += [_row(stock_id, 2, rank=2, similarity=100 - stock_id) for stock_id in range(8, 13)]
    rows += [_row(stock_id, 3, rank=3, similarity=100 - stock_id) for stock_id in range(13, 18)]
    rows += [_row(stock_id, 4, rank=4, similarity=100 - stock_id) for stock_id in range(18, 23)]

    selected = DrctInsightService._select_focus_candidate_ids(rows)

    assert len(selected) == FOCUS_CANDIDATE_LIMIT
    assert sum(stock_id <= 7 for stock_id in selected) == FOCUS_MAX_PER_THEME
    assert any(8 <= stock_id <= 12 for stock_id in selected)
    assert any(13 <= stock_id <= 17 for stock_id in selected)


def test_focus_selector_uses_explainable_priority_and_preliminary_only() -> None:
    rows = [
        _row(1, 1, flow="WATCH", us_up=True, similarity=99),
        _row(2, 2, flow="PASS", us_up=False, similarity=99),
        _row(3, 3, flow="PASS", us_up=True, similarity=80),
        _row(4, 4, flow="PASS", us_up=True, similarity=100, preliminary=False),
    ]

    assert DrctInsightService._select_focus_candidate_ids(rows) == [3, 2, 1]
