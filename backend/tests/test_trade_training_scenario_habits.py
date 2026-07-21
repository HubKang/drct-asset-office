from backend.app.services.trade_training_service import TradeTrainingService


def _reach(event_id: int, day: int, event_type: str = "FULL_STOP_REACHED") -> dict:
    return {
        "id": event_id,
        "risk_scenario_id": 7,
        "risk_plan_step_id": 11,
        "event_type": event_type,
        "chart_date": f"2026-01-{day:02d}",
    }


def test_category_score_exposes_denominator_and_distribution():
    result = TradeTrainingService._score_category(
        "change_warning",
        "계획 변경·경고 대응",
        [1.0, 0.5, 0.5, 0.0, 0.0, 0.0, 0.0],
        excluded_count=3,
    )

    assert result["score"] == 28.57
    assert result["applicable_trade_count"] == 1
    assert result["applicable_item_count"] == 7
    assert result["earned_score"] == 2.0
    assert result["max_score"] == 7.0
    assert result["full_count"] == 1
    assert result["partial_count"] == 2
    assert result["miss_count"] == 4
    assert result["excluded_count"] == 3


def test_non_applicable_category_is_not_reported_as_zero_percent():
    result = TradeTrainingService._score_category("profit_exit", "익절·분할 청산", [])

    assert result["applicable"] is False
    assert result["score"] is None
    assert result["max_score"] == 0.0


def test_consecutive_reaches_form_one_unresolved_episode():
    reaches = [_reach(index, index) for index in range(1, 28)]
    date_index = {f"2026-01-{day:02d}": day - 1 for day in range(1, 28)}

    episodes = TradeTrainingService._build_reach_episodes(reaches, [], date_index)
    distribution = TradeTrainingService._episode_distribution(episodes)

    assert len(episodes) == 1
    assert episodes[0]["duration_bars"] == 27
    assert distribution["unit"] == "EPISODE"
    assert distribution["episode_count"] == 1
    assert distribution["unresolved_count"] == 1
    assert distribution["max_unresolved_bars"] == 27


def test_response_closes_episode_before_next_reach():
    reaches = [_reach(1, 1), _reach(2, 2)]
    responses = [{
        "id": 10,
        "chart_date": "2026-01-01",
        "actual_value": {"reach_event_id": 1},
    }]
    date_index = {"2026-01-01": 0, "2026-01-02": 1}

    episodes = TradeTrainingService._build_reach_episodes(reaches, responses, date_index)
    distribution = TradeTrainingService._episode_distribution(episodes)

    assert len(episodes) == 2
    assert distribution["same_day_count"] == 1
    assert distribution["unresolved_count"] == 1


def test_late_response_keeps_consecutive_reaches_in_one_episode():
    reaches = [_reach(index, index) for index in range(1, 28)]
    responses = [{
        "id": 50,
        "chart_date": "2026-01-27",
        "actual_value": {"reach_event_id": 1},
    }]
    date_index = {f"2026-01-{day:02d}": day - 1 for day in range(1, 28)}

    episodes = TradeTrainingService._build_reach_episodes(reaches, responses, date_index)
    distribution = TradeTrainingService._episode_distribution(episodes)

    assert len(episodes) == 1
    assert episodes[0]["duration_bars"] == 27
    assert episodes[0]["response_bars"] == 26
    assert distribution["over_3_count"] == 1
    assert distribution["unresolved_count"] == 0

def test_warning_technical_events_are_grouped_by_user_behavior():
    warnings = [
        {"simulation_trade_id": 3, "risk_plan_step_id": 4, "chart_date": "2026-01-02", "acknowledged": False},
        {"simulation_trade_id": 3, "risk_plan_step_id": 4, "chart_date": "2026-01-02", "acknowledged": True},
        {"simulation_trade_id": 5, "risk_plan_step_id": 6, "chart_date": "2026-01-03", "acknowledged": False},
    ]

    assert TradeTrainingService._warning_behavior_scores(warnings) == [1.0, 0.0]