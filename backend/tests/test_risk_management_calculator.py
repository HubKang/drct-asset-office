from decimal import Decimal

from backend.app.services.risk_management_calculator import (
    calculate_risk_budget,
    calculate_position_risk,
    classify_risk_usage,
    calculate_risk_usage_pct,
    calculate_scenario_planned_loss,
    calculate_step_planned_loss,
)


def test_calculate_risk_budget_uses_account_pct_as_percent_value():
    assert calculate_risk_budget(Decimal("10000000"), Decimal("1.5")) == Decimal("150000.00")


def test_calculate_step_planned_loss_from_stop_price_and_quantity():
    assert calculate_step_planned_loss(Decimal("10000"), Decimal("9000"), 10) == Decimal("10000.0000")


def test_calculate_scenario_planned_loss_ignores_raw_api_storage_and_sums_plan_steps():
    steps = [
        {"planned_quantity": 10, "trigger_price": 10000},
        {"planned_quantity": 5, "trigger_price": 11000},
    ]
    assert calculate_scenario_planned_loss(steps, Decimal("9000")) == Decimal("20000.00")


def test_calculate_risk_usage_pct():
    assert calculate_risk_usage_pct(Decimal("20000"), Decimal("100000")) == Decimal("20.0000")

def test_calculate_position_risk_includes_exit_cost_and_handles_full_exit():
    assert calculate_position_risk(Decimal("140000"), Decimal("130000"), 35, Decimal("4900")) == Decimal("354900.0000")
    assert calculate_position_risk(Decimal("140000"), Decimal("130000"), 0, Decimal("0")) == Decimal("0.0000")


def test_calculate_position_risk_is_unavailable_without_stop_price():
    assert calculate_position_risk(Decimal("140000"), None, 35) is None


def test_classify_risk_usage_boundaries():
    assert classify_risk_usage(Decimal("79.9999")) == "INFO"
    assert classify_risk_usage(Decimal("80")) == "CAUTION"
    assert classify_risk_usage(Decimal("100")) == "CAUTION"
    assert classify_risk_usage(Decimal("100.0001")) == "WARNING"
    assert classify_risk_usage(None) == "UNAVAILABLE"