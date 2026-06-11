from __future__ import annotations

from statistics import mean
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.repositories.pattern_research_repository import PatternResearchRepository
from backend.app.services.pattern_research_engine import _features


JUDGEMENT_LABELS = {
    "promising": "유망",
    "review": "검토",
    "overfit_warning": "과최적화 주의",
    "capital_risk": "자금 부담 큼",
    "weak": "효과 약함",
    "no_sample": "샘플 없음",
    "error": "오류",
}


def simulate_ai_scenarios(db: Session, request: dict[str, Any]) -> dict[str, Any]:
    goal = request.get("goal") or {}
    risk_plan = request.get("risk_plan") or {}
    stocks = request.get("stocks") or []
    candidates = request.get("candidates") or []
    _validate_request(goal, stocks, candidates)

    repo = PatternResearchRepository(db)
    stock_rows = load_stock_price_indicator_rows(repo, stocks)
    if not any(stock_rows.values()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="선택 종목의 가격 데이터가 없습니다.")

    scenario_results = []
    for index, candidate in enumerate(candidates):
        try:
            scenario_results.append(_simulate_scenario(index, candidate, goal, risk_plan, stock_rows))
        except Exception as exc:  # keep a single bad scenario from failing the batch
            scenario_results.append(_error_result(index, candidate, str(exc)))

    completed = [item for item in scenario_results if item.get("status") == "completed"]
    summary = {
        "executed_scenarios": len(scenario_results),
        "total_candidates": sum(int(item.get("candidate_count") or 0) for item in completed),
        "best_strategy_success_rate": max([float(item.get("strategy_success_rate") or 0) for item in completed] or [0]),
        "best_efficiency_score": max([float(item.get("efficiency_score") or 0) for item in completed] or [0]),
        "add_buy_effective_count": sum(1 for item in completed if int(item.get("recovery_count_after_add_buy") or 0) > 0),
        "overfit_warning_count": sum(1 for item in completed if item.get("judgement") == "overfit_warning"),
    }
    return {"summary": summary, "scenario_results": scenario_results}


def load_stock_price_indicator_rows(repo: PatternResearchRepository, stocks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for stock in stocks:
        stock_code = str(stock.get("stock_code") or "").strip()
        if not stock_code:
            continue
        resolved = repo.get_stock_by_code(stock_code)
        if not resolved:
            result[stock_code] = []
            continue
        source = repo.resolve_price_source(int(resolved["stock_id"]))
        prices = repo.list_prices(int(resolved["stock_id"]), source)
        enriched = []
        for idx, row in enumerate(prices):
            features = _features(prices, idx)
            features.update(_extra_features(prices, idx, features))
            enriched.append(
                {
                    **row,
                    **features,
                    "stock_code": resolved.get("stock_code"),
                    "stock_name": resolved.get("stock_name"),
                }
            )
        result[stock_code] = enriched
    return result


def evaluate_entry_conditions(row: dict[str, Any], conditions: list[dict[str, Any]]) -> bool:
    return all(evaluate_condition(row, condition) for condition in conditions)


def evaluate_condition(row: dict[str, Any], condition: dict[str, Any]) -> bool:
    key = str(condition.get("indicator_key") or condition.get("indicator") or "").strip()
    operator = str(condition.get("operator") or "").strip()
    actual = _num(row.get(key))
    if actual is None:
        return False
    value = condition.get("value")
    if operator == "between":
        if not isinstance(value, list) or len(value) != 2:
            return False
        left = _num(value[0])
        right = _num(value[1])
        return left is not None and right is not None and left <= actual <= right
    expected = _num(value)
    if expected is None:
        return False
    if operator == ">":
        return actual > expected
    if operator == ">=":
        return actual >= expected
    if operator == "<":
        return actual < expected
    if operator == "<=":
        return actual <= expected
    if operator == "=":
        return actual == expected
    return False


def _simulate_scenario(
    index: int,
    candidate: dict[str, Any],
    goal: dict[str, Any],
    risk_plan: dict[str, Any],
    stock_rows: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    holding_days = int(goal.get("holding_days") or 0)
    min_sample_count = int(goal.get("min_sample_count") or 50)
    conditions = candidate.get("entry_conditions") or []
    if not conditions:
        raise ValueError("entry_conditions가 없습니다.")

    samples: list[dict[str, Any]] = []
    warnings: list[str] = []
    for rows in stock_rows.values():
        for idx, row in enumerate(rows):
            if idx + holding_days >= len(rows):
                continue
            if evaluate_entry_conditions(row, conditions):
                samples.append(_simulate_single_candidate(rows, idx, goal, risk_plan, candidate, warnings))

    return aggregate_scenario_result(index, candidate, samples, goal, risk_plan, warnings, min_sample_count)


def _simulate_single_candidate(
    rows: list[dict[str, Any]],
    entry_index: int,
    goal: dict[str, Any],
    risk_plan: dict[str, Any],
    candidate: dict[str, Any],
    scenario_warnings: list[str],
) -> dict[str, Any]:
    holding_days = int(goal.get("holding_days") or 5)
    target_return_pct = float(goal.get("target_return_pct") or 5)
    stop_loss_pct = float(goal.get("stop_loss_pct") or -5)
    entry_row = rows[entry_index]
    future_rows = rows[entry_index + 1 : entry_index + holding_days + 1]
    entry_price = _num(entry_row.get("close_price"))
    if not entry_price:
        raise ValueError("진입가가 없습니다.")

    base = _judge_path(future_rows, entry_price, target_return_pct, stop_loss_pct, entry_price)
    add_buy = _simulate_add_buy_path(
        future_rows=future_rows,
        entry_price=entry_price,
        base_result=base,
        target_return_pct=target_return_pct,
        risk_plan=risk_plan,
        candidate=candidate,
        scenario_warnings=scenario_warnings,
    )

    highs = [_num(row.get("high_price")) for row in future_rows]
    lows = [_num(row.get("low_price")) for row in future_rows]
    max_return_pct = _pct(max([value for value in highs if value is not None], default=entry_price), entry_price)
    max_drawdown_pct = _pct(min([value for value in lows if value is not None], default=entry_price), entry_price)

    return {
        "stock_code": entry_row.get("stock_code"),
        "stock_name": entry_row.get("stock_name"),
        "entry_date": str(entry_row.get("trade_date")),
        "entry_price": round(entry_price, 4),
        "base_result": base["result"],
        "strategy_result": add_buy["strategy_result"],
        "add_buy_count": add_buy["add_buy_count"],
        "add_buy_price": add_buy.get("add_buy_price"),
        "average_price": add_buy.get("average_price"),
        "capital_used": add_buy["capital_used"],
        "max_return_pct": round(max_return_pct, 4) if max_return_pct is not None else None,
        "max_drawdown_pct": round(max_drawdown_pct, 4) if max_drawdown_pct is not None else None,
        "exit_reason": add_buy["exit_reason"],
        "warnings": add_buy["warnings"],
    }


def _simulate_add_buy_path(
    future_rows: list[dict[str, Any]],
    entry_price: float,
    base_result: dict[str, Any],
    target_return_pct: float,
    risk_plan: dict[str, Any],
    candidate: dict[str, Any],
    scenario_warnings: list[str],
) -> dict[str, Any]:
    plan = candidate.get("add_buy_plan") or {}
    enabled = bool(plan.get("enabled", risk_plan.get("add_buy_enabled", False)))
    max_count = int(plan.get("max_count", risk_plan.get("max_add_buy_count", 0)) or 0)
    initial_amount = float(risk_plan.get("initial_amount") or plan.get("initial_amount") or 1_000_000)
    sample_warnings: list[str] = []
    if not enabled or max_count < 1:
        return _base_strategy(base_result, initial_amount)
    if max_count >= 2:
        warning = "MVP에서는 추가매수를 최대 1회까지만 계산합니다. 2회 이상 전략은 후속 단계에서 지원합니다."
        sample_warnings.append(warning)
        if warning not in scenario_warnings:
            scenario_warnings.append(warning)

    trigger_loss_pct = float(plan.get("trigger_loss_pct", risk_plan.get("add_buy_trigger_loss_pct", -5)) or -5)
    amount_ratio = float(plan.get("amount_ratio", 1.0) or 1.0)
    final_stop_loss_pct = float(plan.get("final_stop_loss_pct", risk_plan.get("final_stop_loss_pct", -5)) or -5)
    stop_loss_basis = str(plan.get("stop_loss_basis") or risk_plan.get("final_stop_loss_basis") or "average_price")
    trigger_price = entry_price * (1 + trigger_loss_pct / 100)

    for cursor, row in enumerate(future_rows):
        low = _num(row.get("low_price"))
        if low is None or low > trigger_price:
            continue
        if _risk_blocks_add_buy(row, candidate.get("risk_filters") or []):
            return {**_base_strategy(base_result, initial_amount), "warnings": sample_warnings + ["위험 필터 조건으로 추가매수가 차단되었습니다."]}

        add_buy_price = trigger_price
        add_buy_amount = initial_amount * amount_ratio
        initial_qty = initial_amount / entry_price
        add_buy_qty = add_buy_amount / add_buy_price
        total_amount = initial_amount + add_buy_amount
        total_qty = initial_qty + add_buy_qty
        average_price = total_amount / total_qty
        stop_base = average_price if stop_loss_basis == "average_price" else entry_price
        judged = _judge_path(
            future_rows[cursor:],
            average_price,
            target_return_pct,
            final_stop_loss_pct,
            stop_base,
        )
        strategy_result = {
            "success": "success_after_add_buy",
            "failure": "failure_after_add_buy",
            "neutral": "neutral_after_add_buy",
        }[judged["result"]]
        return {
            "strategy_result": strategy_result,
            "add_buy_count": 1,
            "add_buy_price": round(add_buy_price, 4),
            "average_price": round(average_price, 4),
            "capital_used": round(total_amount, 4),
            "exit_reason": judged["exit_reason"],
            "warnings": sample_warnings,
        }
    return _base_strategy(base_result, initial_amount)


def aggregate_scenario_result(
    index: int,
    candidate: dict[str, Any],
    samples: list[dict[str, Any]],
    goal: dict[str, Any],
    risk_plan: dict[str, Any],
    warnings: list[str],
    min_sample_count: int,
) -> dict[str, Any]:
    candidate_count = len(samples)
    success_count = sum(1 for sample in samples if sample["base_result"] == "success")
    failure_count = sum(1 for sample in samples if sample["base_result"] == "failure")
    neutral_count = candidate_count - success_count - failure_count
    strategy_success_count = sum(1 for sample in samples if sample["strategy_result"] in {"success", "success_after_add_buy"})
    strategy_failure_count = sum(1 for sample in samples if sample["strategy_result"] in {"failure", "failure_after_add_buy"})
    strategy_neutral_count = candidate_count - strategy_success_count - strategy_failure_count
    add_buy_trigger_count = sum(1 for sample in samples if sample["add_buy_count"] > 0)
    recovery_count = sum(1 for sample in samples if sample["strategy_result"] == "success_after_add_buy")
    initial_amount = float(risk_plan.get("initial_amount") or 1_000_000)

    base_success_rate = _rate(success_count, candidate_count)
    strategy_success_rate = _rate(strategy_success_count, candidate_count)
    failure_rate = _rate(strategy_failure_count, candidate_count)
    avg_capital_used = _avg([sample.get("capital_used") for sample in samples]) or 0
    efficiency_score = calculate_efficiency_score(
        candidate_count,
        min_sample_count,
        base_success_rate,
        strategy_success_rate,
        failure_rate,
        avg_capital_used,
        initial_amount,
    )
    judgement = _judgement(candidate_count, min_sample_count, base_success_rate, strategy_success_rate, failure_rate, avg_capital_used, initial_amount, efficiency_score)
    if candidate_count and strategy_success_rate > base_success_rate and avg_capital_used > initial_amount:
        warnings.append("추가매수 적용 후 성공률은 개선되었지만 평균 투입금액이 증가했습니다.")
    if any(sample.get("exit_reason") == "same_day_stop_first" for sample in samples):
        warnings.append("일봉 기준으로 목표가와 손절가의 장중 도달 순서를 알 수 없어 보수적으로 실패 우선 판정했습니다.")

    success_samples = sorted(
        [sample for sample in samples if sample["strategy_result"] in {"success", "success_after_add_buy"}],
        key=lambda sample: sample.get("max_return_pct") or 0,
        reverse=True,
    )[:5]
    failure_samples = sorted(
        [sample for sample in samples if sample["strategy_result"] in {"failure", "failure_after_add_buy"}],
        key=lambda sample: sample.get("max_drawdown_pct") or 0,
    )[:5]
    add_buy_success_samples = sorted(
        [sample for sample in samples if sample.get("add_buy_count", 0) > 0 and sample["strategy_result"] == "success_after_add_buy"],
        key=lambda sample: sample.get("max_return_pct") or 0,
        reverse=True,
    )[:5]
    add_buy_failure_samples = sorted(
        [sample for sample in samples if sample.get("add_buy_count", 0) > 0 and sample["strategy_result"] in {"failure_after_add_buy", "neutral_after_add_buy"}],
        key=lambda sample: sample.get("max_drawdown_pct") or 0,
    )[:5]

    return {
        "scenario_index": index,
        "scenario_name": candidate.get("scenario_name") or candidate.get("name") or f"시나리오 {index + 1}",
        "scenario_type": candidate.get("scenario_type"),
        "status": "completed",
        "judgement": judgement,
        "judgement_label": JUDGEMENT_LABELS[judgement],
        "candidate_count": candidate_count,
        "success_count": success_count,
        "failure_count": failure_count,
        "neutral_count": neutral_count,
        "base_success_rate": base_success_rate,
        "strategy_success_count": strategy_success_count,
        "strategy_failure_count": strategy_failure_count,
        "strategy_neutral_count": strategy_neutral_count,
        "strategy_success_rate": strategy_success_rate,
        "failure_rate": failure_rate,
        "recovery_count_after_add_buy": recovery_count,
        "recovery_rate_after_add_buy": _rate(recovery_count, add_buy_trigger_count),
        "add_buy_trigger_count": add_buy_trigger_count,
        "avg_add_buy_count": round(_avg([sample.get("add_buy_count") for sample in samples]) or 0, 4),
        "avg_capital_used": round(avg_capital_used, 4),
        "max_capital_used": round(max([sample.get("capital_used") or 0 for sample in samples] or [0]), 4),
        "avg_max_return_pct": round(_avg([sample.get("max_return_pct") for sample in samples]) or 0, 4),
        "avg_max_drawdown_pct": round(_avg([sample.get("max_drawdown_pct") for sample in samples]) or 0, 4),
        "efficiency_score": efficiency_score,
        "warnings": list(dict.fromkeys(warnings)),
        "success_samples": success_samples,
        "failure_samples": failure_samples,
        "add_buy_success_samples": add_buy_success_samples,
        "add_buy_failure_samples": add_buy_failure_samples,
    }


def calculate_efficiency_score(
    candidate_count: int,
    min_sample_count: int,
    base_success_rate: float,
    strategy_success_rate: float,
    failure_rate: float,
    avg_capital_used: float,
    initial_amount: float,
) -> float:
    sample_score = 100 if candidate_count >= min_sample_count * 2 else 80 if candidate_count >= min_sample_count else 50 if candidate_count >= min_sample_count * 0.5 else 20
    capital_ratio = avg_capital_used / initial_amount if initial_amount else 1
    capital_score = 100 if capital_ratio <= 1.2 else 80 if capital_ratio <= 1.5 else 60 if capital_ratio <= 2 else 30
    improvement = strategy_success_rate - base_success_rate
    improvement_score = 100 if improvement >= 10 else 80 if improvement >= 5 else 60 if improvement >= 2 else 40 if improvement >= 0 else 10
    score = strategy_success_rate * 0.35 + (100 - failure_rate) * 0.25 + sample_score * 0.15 + capital_score * 0.15 + improvement_score * 0.10
    return round(max(0, min(100, score)), 2)


def _extra_features(rows: list[dict[str, Any]], idx: int, features: dict[str, Any]) -> dict[str, Any]:
    ma5 = _num(features.get("ma5"))
    ma10 = _num(features.get("ma10"))
    return_1d_values = [_num(_features(rows, cursor).get("return_1d")) for cursor in range(max(0, idx - 29), idx + 1)]
    return {
        "ma5_vs_ma10_pct": _pct(ma5, ma10),
        "recent_10d_return": _return_over(rows, idx, 10),
        "max_return_1d_30d": max([value for value in return_1d_values if value is not None], default=None),
    }


def _judge_path(future_rows: list[dict[str, Any]], target_base: float, target_return_pct: float, stop_loss_pct: float, stop_base: float) -> dict[str, Any]:
    target_price = target_base * (1 + target_return_pct / 100)
    stop_price = stop_base * (1 + stop_loss_pct / 100)
    for row in future_rows:
        high = _num(row.get("high_price"))
        low = _num(row.get("low_price"))
        if high is None or low is None:
            continue
        # Daily bars do not reveal intraday order, so same-day target/stop hits are treated conservatively as failure.
        if low <= stop_price and high >= target_price:
            return {"result": "failure", "exit_reason": "same_day_stop_first"}
        if low <= stop_price:
            return {"result": "failure", "exit_reason": "stop"}
        if high >= target_price:
            return {"result": "success", "exit_reason": "target"}
    return {"result": "neutral", "exit_reason": "holding_period_end"}


def _risk_blocks_add_buy(row: dict[str, Any], risk_filters: list[dict[str, Any]]) -> bool:
    for condition in risk_filters:
        action = condition.get("action")
        if action == "block_add_buy" and evaluate_condition(row, condition):
            return True
    return False


def _base_strategy(base_result: dict[str, Any], initial_amount: float) -> dict[str, Any]:
    return {
        "strategy_result": base_result["result"],
        "add_buy_count": 0,
        "add_buy_price": None,
        "average_price": None,
        "capital_used": round(initial_amount, 4),
        "exit_reason": base_result["exit_reason"],
        "warnings": [],
    }


def _validate_request(goal: dict[str, Any], stocks: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> None:
    if not stocks:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="시뮬레이션 대상 종목이 필요합니다.")
    if not candidates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="시뮬레이션 대상 시나리오 후보가 필요합니다.")
    if int(goal.get("holding_days") or 0) <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="목표 기간은 1거래일 이상이어야 합니다.")
    if float(goal.get("target_return_pct") or 0) <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="목표 수익률은 0보다 커야 합니다.")
    if float(goal.get("stop_loss_pct") or 0) >= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="손실 기준은 음수여야 합니다.")


def _error_result(index: int, candidate: dict[str, Any], message: str) -> dict[str, Any]:
    return {
        "scenario_index": index,
        "scenario_name": candidate.get("scenario_name") or candidate.get("name") or f"시나리오 {index + 1}",
        "scenario_type": candidate.get("scenario_type"),
        "status": "error",
        "judgement": "error",
        "judgement_label": JUDGEMENT_LABELS["error"],
        "candidate_count": 0,
        "success_count": 0,
        "failure_count": 0,
        "neutral_count": 0,
        "base_success_rate": 0,
        "strategy_success_count": 0,
        "strategy_failure_count": 0,
        "strategy_neutral_count": 0,
        "strategy_success_rate": 0,
        "failure_rate": 0,
        "recovery_count_after_add_buy": 0,
        "recovery_rate_after_add_buy": 0,
        "add_buy_trigger_count": 0,
        "avg_add_buy_count": 0,
        "avg_capital_used": 0,
        "max_capital_used": 0,
        "avg_max_return_pct": 0,
        "avg_max_drawdown_pct": 0,
        "efficiency_score": 0,
        "warnings": [],
        "errors": [message],
        "success_samples": [],
        "failure_samples": [],
        "add_buy_success_samples": [],
        "add_buy_failure_samples": [],
    }


def _judgement(
    candidate_count: int,
    min_sample_count: int,
    base_success_rate: float,
    strategy_success_rate: float,
    failure_rate: float,
    avg_capital_used: float,
    initial_amount: float,
    efficiency_score: float,
) -> str:
    if candidate_count == 0:
        return "no_sample"
    if candidate_count < min_sample_count:
        return "overfit_warning"
    capital_ratio = avg_capital_used / initial_amount if initial_amount else 1
    if strategy_success_rate > base_success_rate and capital_ratio > 2:
        return "capital_risk"
    if strategy_success_rate >= base_success_rate + 3 and failure_rate <= 40 and efficiency_score >= 70:
        return "promising"
    if strategy_success_rate >= base_success_rate and failure_rate <= 55:
        return "review"
    return "weak"


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return ((current - previous) / previous) * 100


def _return_over(rows: list[dict[str, Any]], idx: int, days: int) -> float | None:
    if idx - days < 0:
        return None
    return _pct(_num(rows[idx].get("close_price")), _num(rows[idx - days].get("close_price")))


def _rate(count: int, total: int) -> float:
    return round(count / total * 100, 2) if total else 0


def _avg(values: list[Any]) -> float | None:
    nums = [_num(value) for value in values]
    valid = [value for value in nums if value is not None]
    return mean(valid) if valid else None
