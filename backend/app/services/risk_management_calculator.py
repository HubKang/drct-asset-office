from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any


MONEY_QUANT = Decimal("0.0001")
PCT_QUANT = Decimal("0.0001")


def to_decimal(value: Any, default: Decimal | None = None) -> Decimal | None:
    if value is None:
        return default
    try:
        return Decimal(str(value).replace(",", "").strip())
    except Exception:
        return default


def quantize_money(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def quantize_pct(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(PCT_QUANT, rounding=ROUND_HALF_UP)


def calculate_risk_budget(equity: Decimal, risk_pct: Decimal) -> Decimal:
    return quantize_money(equity * risk_pct / Decimal("100")) or Decimal("0")


def calculate_step_planned_loss(
    entry_price: Decimal,
    stop_price: Decimal,
    quantity: int,
    estimated_cost: Decimal = Decimal("0"),
) -> Decimal:
    raw = (entry_price - stop_price) * Decimal(max(0, int(quantity))) + estimated_cost
    return quantize_money(max(Decimal("0"), raw)) or Decimal("0")


def calculate_scenario_planned_loss(
    steps: list[dict[str, Any]],
    stop_price: Decimal | None,
) -> Decimal | None:
    if stop_price is None:
        return None
    total = Decimal("0")
    has_calculable_step = False
    for step in steps:
        entry_price = to_decimal(step.get("trigger_price"))
        quantity = int(step.get("planned_quantity") or 0)
        if entry_price is None or quantity <= 0:
            continue
        has_calculable_step = True
        total += calculate_step_planned_loss(entry_price, stop_price, quantity)
    return quantize_money(total) if has_calculable_step else None


def calculate_risk_usage_pct(planned_loss: Decimal | None, risk_budget: Decimal | None) -> Decimal | None:
    if planned_loss is None or risk_budget is None or risk_budget <= 0:
        return None
    return quantize_pct(planned_loss / risk_budget * Decimal("100"))


def calculate_position_risk(
    average_price: Decimal | None,
    stop_price: Decimal | None,
    quantity: int,
    estimated_exit_cost: Decimal = Decimal("0"),
) -> Decimal | None:
    """Estimate long-position loss at the plan stop plus internal liquidation costs."""
    if average_price is None or stop_price is None:
        return None
    qty = max(0, int(quantity))
    if qty == 0:
        return Decimal("0.0000")
    price_risk = max(average_price - stop_price, Decimal("0")) * Decimal(qty)
    return quantize_money(price_risk + max(estimated_exit_cost, Decimal("0")))


def classify_risk_usage(risk_usage_pct: Decimal | None) -> str:
    if risk_usage_pct is None:
        return "UNAVAILABLE"
    if risk_usage_pct < Decimal("80"):
        return "INFO"
    if risk_usage_pct <= Decimal("100"):
        return "CAUTION"
    return "WARNING"