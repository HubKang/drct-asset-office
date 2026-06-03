from __future__ import annotations

from dataclasses import dataclass
from math import floor
from typing import Any


@dataclass
class Position:
    buy_date: str
    buy_index: int
    buy_price: float
    quantity: int
    buy_amount: float
    buy_fee: float
    buy_signal: dict[str, Any]


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    return float(value)


def _rate(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator * 100, 4)


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _ma(rows: list[dict[str, Any]], index: int, period: int, field: str) -> float | None:
    if period <= 0 or index - period + 1 < 0:
        return None
    values = [_to_float(row.get(field)) for row in rows[index - period + 1 : index + 1]]
    if len(values) != period or any(value <= 0 for value in values):
        return None
    return sum(values) / period


def _compare(left: float, operator: str, right: float) -> bool:
    if operator == ">":
        return left > right
    if operator == ">=":
        return left >= right
    if operator == "<":
        return left < right
    if operator == "<=":
        return left <= right
    if operator in ("==", "="):
        return left == right
    return False


def _field_value(row: dict[str, Any], field: str) -> float:
    allowed = {"open_price", "high_price", "low_price", "close_price", "volume", "trading_value"}
    if field not in allowed:
        return 0.0
    return _to_float(row.get(field))


def _recent_high_excluding_today(rows: list[dict[str, Any]], index: int, period: int) -> float | None:
    if period <= 0 or index - period < 0:
        return None
    values = [_to_float(row.get("high_price")) for row in rows[index - period : index]]
    if len(values) != period or any(value <= 0 for value in values):
        return None
    return max(values)


def _recent_low_excluding_today(rows: list[dict[str, Any]], index: int, period: int) -> float | None:
    if period <= 0 or index - period < 0:
        return None
    values = [_to_float(row.get("low_price")) for row in rows[index - period : index]]
    if len(values) != period or any(value <= 0 for value in values):
        return None
    return min(values)


def _condition_met(rows: list[dict[str, Any]], index: int, condition: dict[str, Any]) -> bool:
    row = rows[index]
    condition_type = str(condition.get("condition_type") or condition.get("type") or "")
    close = _to_float(row.get("close_price"))
    open_price = _to_float(row.get("open_price"))
    volume = _to_float(row.get("volume"))

    if condition_type == "field_value_compare":
        left = condition.get("left") if isinstance(condition.get("left"), dict) else {}
        field = str(left.get("field") or condition.get("field") or "")
        return _compare(_field_value(row, field), str(condition.get("operator") or ">"), _to_float(condition.get("value")))
    if condition_type == "field_vs_field":
        left = condition.get("left") if isinstance(condition.get("left"), dict) else {}
        right = condition.get("right") if isinstance(condition.get("right"), dict) else {}
        return _compare(
            _field_value(row, str(left.get("field") or "")),
            str(condition.get("operator") or ">"),
            _field_value(row, str(right.get("field") or "")),
        )
    if condition_type == "field_vs_indicator":
        left = condition.get("left") if isinstance(condition.get("left"), dict) else {}
        right = condition.get("right") if isinstance(condition.get("right"), dict) else {}
        if right.get("type") != "moving_average":
            return False
        ma = _ma(rows, index, int(right.get("period") or 0), str(right.get("field") or "close_price"))
        return ma is not None and _compare(
            _field_value(row, str(left.get("field") or "")),
            str(condition.get("operator") or ">"),
            ma,
        )
    if condition_type == "field_vs_average_multiplier":
        left = condition.get("left") if isinstance(condition.get("left"), dict) else {}
        right = condition.get("right") if isinstance(condition.get("right"), dict) else {}
        avg_value = _ma(rows, index, int(right.get("period") or 0), str(right.get("field") or left.get("field") or "volume"))
        multiplier = float(right.get("multiplier") or 1)
        return avg_value is not None and _compare(
            _field_value(row, str(left.get("field") or "")),
            str(condition.get("operator") or ">"),
            avg_value * multiplier,
        )
    if condition_type == "candle_pattern":
        pattern = str(condition.get("pattern") or "")
        if pattern == "bullish_candle":
            return close > open_price
        if pattern == "bearish_candle":
            return close < open_price
        if pattern == "close_above_previous_high":
            return index > 0 and close > _to_float(rows[index - 1].get("high_price"))
        if pattern == "close_above_recent_high":
            recent_high = _recent_high_excluding_today(rows, index, int(condition.get("period") or 20))
            return recent_high is not None and close > recent_high
        if pattern == "close_below_recent_low":
            recent_low = _recent_low_excluding_today(rows, index, int(condition.get("period") or 20))
            return recent_low is not None and close < recent_low
        return False

    if condition_type == "close_above_ma":
        ma = _ma(rows, index, int(condition.get("period") or 0), "close_price")
        return ma is not None and close > ma
    if condition_type == "close_below_ma":
        ma = _ma(rows, index, int(condition.get("period") or 0), "close_price")
        return ma is not None and close < ma
    if condition_type == "volume_above_average":
        period = int(condition.get("period") or 0)
        multiplier = float(condition.get("multiplier") or 1)
        avg_volume = _ma(rows, index, period, "volume")
        return avg_volume is not None and volume > avg_volume * multiplier
    if condition_type == "bullish_candle":
        return close > open_price
    if condition_type == "close_above_previous_high":
        if index <= 0:
            return False
        return close > _to_float(rows[index - 1].get("high_price"))
    if condition_type == "close_above_recent_high":
        recent_high = _recent_high_excluding_today(rows, index, int(condition.get("period") or 0))
        return recent_high is not None and close > recent_high

    raise ValueError(f"알 수 없는 매수조건입니다: {condition_type}")


def _buy_signal(rows: list[dict[str, Any]], index: int, buy_rule: dict[str, Any]) -> dict[str, Any] | None:
    if buy_rule.get("operator", "AND") != "AND":
        raise ValueError("MVP에서는 AND 조건만 지원합니다.")
    conditions = buy_rule.get("conditions")
    if not isinstance(conditions, list) or not conditions:
        raise ValueError("매수조건을 1개 이상 선택해 주세요.")
    results = []
    for condition in conditions:
        if not isinstance(condition, dict):
            raise ValueError("매매기준 형식이 올바르지 않습니다.")
        met = _condition_met(rows, index, condition)
        results.append({"condition": condition, "met": met})
    if all(item["met"] for item in results):
        return {"signal_date": rows[index]["trade_date"], "conditions": results}
    return None


def _sell_condition(sell_rule: dict[str, Any], condition_type: str) -> dict[str, Any] | None:
    conditions = sell_rule.get("conditions")
    if isinstance(conditions, list):
        for condition in conditions:
            if isinstance(condition, dict) and condition.get("condition_type") == condition_type:
                return condition
        return None
    if condition_type == "take_profit_pct" and sell_rule.get("take_profit_pct") is not None:
        return {"condition_type": condition_type, "value": sell_rule.get("take_profit_pct")}
    if condition_type == "stop_loss_pct" and sell_rule.get("stop_loss_pct") is not None:
        return {"condition_type": condition_type, "value": sell_rule.get("stop_loss_pct")}
    if condition_type == "close_below_ma":
        close_below_ma = sell_rule.get("exit_on_close_below_ma")
        if isinstance(close_below_ma, dict) and close_below_ma.get("enabled"):
            return {"condition_type": condition_type, "period": close_below_ma.get("period") or 20}
    if condition_type == "max_holding_days" and sell_rule.get("max_holding_days") is not None:
        return {"condition_type": condition_type, "value": sell_rule.get("max_holding_days")}
    return None


def _exit_signal(
    rows: list[dict[str, Any]],
    index: int,
    position: Position,
    sell_rule: dict[str, Any],
) -> tuple[float, str, dict[str, Any]] | None:
    row = rows[index]
    low = _to_float(row.get("low_price"))
    high = _to_float(row.get("high_price"))
    close = _to_float(row.get("close_price"))
    trade_date = str(row["trade_date"])

    stop_loss_condition = _sell_condition(sell_rule, "stop_loss_pct")
    stop_loss_pct = stop_loss_condition.get("value") if stop_loss_condition else None
    if stop_loss_pct is not None and float(stop_loss_pct) > 0:
        stop_price = position.buy_price * (1 - float(stop_loss_pct) / 100)
        if low <= stop_price:
            return round(stop_price, 4), "stop_loss", {"trade_date": trade_date, "stop_loss_pct": stop_loss_pct, "condition": stop_loss_condition}

    take_profit_condition = _sell_condition(sell_rule, "take_profit_pct")
    take_profit_pct = take_profit_condition.get("value") if take_profit_condition else None
    if take_profit_pct is not None and float(take_profit_pct) > 0:
        target_price = position.buy_price * (1 + float(take_profit_pct) / 100)
        if high >= target_price:
            return round(target_price, 4), "take_profit", {"trade_date": trade_date, "take_profit_pct": take_profit_pct, "condition": take_profit_condition}

    close_below_ma = _sell_condition(sell_rule, "close_below_ma")
    if close_below_ma:
        period = int(close_below_ma.get("period") or 0)
        ma = _ma(rows, index, period, "close_price")
        if ma is not None and close < ma:
            return round(close, 4), "close_below_ma", {"trade_date": trade_date, "period": period, "ma": round(ma, 4), "condition": close_below_ma}

    max_holding_condition = _sell_condition(sell_rule, "max_holding_days")
    max_holding_days = max_holding_condition.get("value") if max_holding_condition else None
    if max_holding_days is not None and int(max_holding_days) > 0:
        holding_days = max(0, index - position.buy_index)
        if holding_days >= int(max_holding_days):
            return round(close, 4), "max_holding_days", {"trade_date": trade_date, "max_holding_days": max_holding_days, "condition": max_holding_condition}

    return None


def run_backtest_engine(
    price_rows: list[dict[str, Any]],
    rule: dict[str, Any],
    initial_cash: float,
) -> dict[str, Any]:
    if len(price_rows) < 30:
        raise ValueError("해당 종목의 가격 데이터가 부족합니다. 먼저 가격 데이터를 수집해 주세요.")

    buy_rule = rule["buy_conditions_json"]
    sell_rule = rule["sell_conditions_json"]
    position_rule = rule["position_rule_json"]
    fee_rate = float(rule.get("fee_rate") or 0)
    slippage_rate = float(rule.get("slippage_rate") or 0)
    percent = float(position_rule.get("percent") or 0)
    if percent <= 0 or percent > 100:
        raise ValueError("진입비중은 0보다 크고 100 이하로 입력해 주세요.")

    cash = float(initial_cash)
    position: Position | None = None
    pending_position: Position | None = None
    trades: list[dict[str, Any]] = []
    equity_curve: list[dict[str, Any]] = []
    total_fee = 0.0
    peak_asset = float(initial_cash)

    for index, row in enumerate(price_rows):
        trade_date = str(row["trade_date"])
        close = _to_float(row.get("close_price"))

        if pending_position is not None and pending_position.buy_date == trade_date:
            cash -= pending_position.buy_amount + pending_position.buy_fee
            total_fee += pending_position.buy_fee
            position = pending_position
            pending_position = None

        if position is not None:
            exit_result = _exit_signal(price_rows, index, position, sell_rule)
            if exit_result is not None:
                sell_price, exit_reason, sell_signal = exit_result
                sell_price = sell_price * (1 - slippage_rate)
                sell_amount = sell_price * position.quantity
                sell_fee = sell_amount * fee_rate
                total_fee += sell_fee
                cash += sell_amount - sell_fee
                profit = sell_amount - sell_fee - position.buy_amount - position.buy_fee
                holding_days = max(0, index - position.buy_index)
                trades.append(
                    {
                        "buy_date": position.buy_date,
                        "sell_date": trade_date,
                        "buy_price": round(position.buy_price, 4),
                        "sell_price": round(sell_price, 4),
                        "quantity": position.quantity,
                        "buy_amount": round(position.buy_amount, 4),
                        "sell_amount": round(sell_amount, 4),
                        "fee": round(position.buy_fee + sell_fee, 4),
                        "profit": round(profit, 4),
                        "profit_rate": _rate(profit, position.buy_amount + position.buy_fee),
                        "holding_days": holding_days,
                        "exit_reason": exit_reason,
                        "buy_signal_json": position.buy_signal,
                        "sell_signal_json": sell_signal,
                    }
                )
                position = None

        if position is None and pending_position is None and index < len(price_rows) - 1:
            signal = _buy_signal(price_rows, index, buy_rule)
            if signal is not None:
                next_row = price_rows[index + 1]
                buy_price = _to_float(next_row.get("open_price")) * (1 + slippage_rate)
                if buy_price > 0:
                    quantity = floor((cash * percent / 100) / buy_price)
                    if quantity > 0:
                        buy_amount = buy_price * quantity
                        buy_fee = buy_amount * fee_rate
                        if buy_amount + buy_fee <= cash:
                            pending_position = Position(
                                buy_date=str(next_row["trade_date"]),
                                buy_index=index + 1,
                                buy_price=round(buy_price, 4),
                                quantity=quantity,
                                buy_amount=round(buy_amount, 4),
                                buy_fee=round(buy_fee, 4),
                                buy_signal=signal,
                            )

        position_value = (position.quantity * close) if position else 0.0
        total_asset = cash + position_value
        peak_asset = max(peak_asset, total_asset)
        drawdown_rate = _rate(total_asset - peak_asset, peak_asset)
        equity_curve.append(
            {
                "trade_date": trade_date,
                "cash": round(cash, 4),
                "position_qty": position.quantity if position else 0,
                "position_value": round(position_value, 4),
                "total_asset": round(total_asset, 4),
                "drawdown_rate": drawdown_rate,
            }
        )

    if position is not None:
        last_row = price_rows[-1]
        last_close = _to_float(last_row.get("close_price"))
        position_value = position.quantity * last_close
        unrealized_profit = position_value - position.buy_amount - position.buy_fee
        holding_days = max(0, len(price_rows) - 1 - position.buy_index)
        trades.append(
            {
                "buy_date": position.buy_date,
                "sell_date": None,
                "buy_price": round(position.buy_price, 4),
                "sell_price": None,
                "quantity": position.quantity,
                "buy_amount": round(position.buy_amount, 4),
                "sell_amount": None,
                "fee": round(position.buy_fee, 4),
                "profit": round(unrealized_profit, 4),
                "profit_rate": _rate(unrealized_profit, position.buy_amount + position.buy_fee),
                "holding_days": holding_days,
                "exit_reason": "open_position",
                "buy_signal_json": position.buy_signal,
                "sell_signal_json": {"trade_date": str(last_row["trade_date"]), "valuation_price": last_close},
            }
        )

    final_asset = equity_curve[-1]["total_asset"] if equity_curve else initial_cash
    closed_trades = [trade for trade in trades if trade.get("sell_date")]
    wins = [trade for trade in closed_trades if float(trade.get("profit") or 0) > 0]
    losses = [trade for trade in closed_trades if float(trade.get("profit") or 0) < 0]
    breakevens = [trade for trade in closed_trades if float(trade.get("profit") or 0) == 0]
    total_profit_amount = sum(float(trade.get("profit") or 0) for trade in wins)
    total_loss_amount = sum(float(trade.get("profit") or 0) for trade in losses)
    profit_factor = None if total_loss_amount == 0 else round(total_profit_amount / abs(total_loss_amount), 4)
    profit_rates = [float(trade["profit_rate"]) for trade in wins]
    loss_rates = [float(trade["profit_rate"]) for trade in losses]
    holding_days = [int(trade.get("holding_days") or 0) for trade in closed_trades]

    summary = {
        "initial_cash": round(float(initial_cash), 4),
        "final_asset": round(final_asset, 4),
        "total_profit": round(final_asset - initial_cash, 4),
        "total_return_rate": _rate(final_asset - initial_cash, initial_cash),
        "max_drawdown": min((float(point["drawdown_rate"]) for point in equity_curve), default=0.0),
        "trade_count": len(closed_trades),
        "win_count": len(wins),
        "loss_count": len(losses),
        "breakeven_count": len(breakevens),
        "win_rate": None if not closed_trades else round(len(wins) / len(closed_trades) * 100, 4),
        "avg_profit_rate": None if not profit_rates else round(_avg(profit_rates) or 0, 4),
        "avg_loss_rate": None if not loss_rates else round(_avg(loss_rates) or 0, 4),
        "profit_factor": profit_factor,
        "avg_holding_days": None if not holding_days else round(_avg([float(day) for day in holding_days]) or 0, 4),
        "total_fee": round(total_fee, 4),
    }
    message = "조건을 만족한 매수 신호가 없습니다." if not trades else "백테스트가 완료되었습니다."
    return {"summary": summary, "trades": trades, "equity_curve": equity_curve, "message": message}
