from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.entities.watchlist import Watchlist
from backend.app.entities.watchlist_evaluation import WatchlistEvaluationFactor, WatchlistEvaluationRun, WatchlistEvaluationScore
from backend.app.repositories.stock_repository import StockRepository
from backend.app.repositories.watchlist_evaluation_repository import WatchlistEvaluationRepository
from backend.app.repositories.watchlist_repository import WatchlistRepository
from backend.app.schemas.watchlist_evaluation_schema import (
    WatchlistEvaluateAllRequest,
    WatchlistEvaluateRequest,
    WatchlistEvaluateResponse,
    WatchlistEvaluationFactorResponse,
    WatchlistEvaluationHistoryItem,
    WatchlistEvaluationListItem,
    WatchlistEvaluationListResponse,
    WatchlistEvaluationScoreResponse,
    WatchlistEvaluationSummary,
    WatchlistGptPromptResponse,
)


MARKET_FACTOR_META = {
    "DOMESTIC_INDEX_TREND": ("국내 지수 흐름", 30.0),
    "MARKET_BREADTH": ("시장 체감/폭", 20.0),
    "MARKET_LIQUIDITY": ("시장 유동성", 15.0),
    "US_MARKET_TREND": ("미국 시장 흐름", 20.0),
    "EXTERNAL_RISK": ("외부 위험", 15.0),
}

MARKET_MISSING_LABELS = {
    "DOMESTIC_INDEX_TREND": "국내 지수 흐름",
    "MARKET_BREADTH": "시장 체감/폭",
    "MARKET_LIQUIDITY": "시장 유동성",
    "US_MARKET_TREND": "미국 시장 흐름",
    "EXTERNAL_RISK": "외부 위험",
}


def _json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def _missing_data(price_count: int | None, metrics_count: int | None) -> list[str]:
    missing: list[str] = []
    if not price_count:
        missing.append("price")
        missing.append("chart")
    if not metrics_count:
        missing.append("market")
    missing.append("financial")
    missing.append("supply")
    return list(dict.fromkeys(missing))


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _round(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(value, digits)


def _recent_return(rows: list[dict[str, Any]], days: int) -> float | None:
    if len(rows) <= days:
        return None
    latest = _as_float(rows[-1].get("close_price"))
    base = _as_float(rows[-1 - days].get("close_price"))
    if latest is None or base in (None, 0):
        return None
    return (latest / base - 1) * 100


def _simple_ma(rows: list[dict[str, Any]], window: int) -> float | None:
    if len(rows) < window:
        return None
    values = [_as_float(row.get("close_price")) for row in rows[-window:]]
    if any(value is None for value in values):
        return None
    return sum(value for value in values if value is not None) / window


def _score_grade(score: float | None) -> str:
    if score is None:
        return "미평가"
    if score >= 80:
        return "강한 우호"
    if score >= 65:
        return "우호"
    if score >= 50:
        return "중립"
    if score >= 35:
        return "경계"
    return "위험"


def _score_summary(score: float | None, status_value: str, missing: list[str]) -> str:
    if score is None:
        return "국내 지수 데이터가 부족해 시장 환경 평가를 제한했습니다."
    grade = _score_grade(score)
    base = {
        "강한 우호": "시장 환경이 관심종목 관찰에 우호적입니다.",
        "우호": "대체로 양호한 시장 환경입니다.",
        "중립": "시장 환경은 중립입니다. 종목별 확인이 필요합니다.",
        "경계": "시장 부담이 있습니다. 추격 판단에 주의가 필요합니다.",
        "위험": "시장 환경이 불리합니다. 보수적 관찰이 필요합니다.",
    }.get(grade, "시장 환경 평가가 필요합니다.")
    if status_value == "PARTIAL" and missing:
        return f"{base} 다만 {', '.join(missing)} 데이터가 없어 일부 판단은 제한됩니다."
    return base


def _confidence_by_available_count(available_count: int, domestic_available: bool) -> str:
    if not domestic_available:
        return "LIMITED"
    if available_count >= 4:
        return "ENOUGH"
    if available_count == 3:
        return "PARTIAL"
    return "LIMITED"


def _status_by_available_count(available_count: int, domestic_available: bool) -> str:
    if not domestic_available:
        return "DATA_MISSING"
    if available_count >= 5:
        return "EVALUATED"
    return "PARTIAL"


class WatchlistEvaluationService:
    def __init__(self, db: Session) -> None:
        self.repo = WatchlistEvaluationRepository(db)
        self.watchlist_repo = WatchlistRepository(db)
        self.stock_repo = StockRepository(db)

    def list_sije_sucha_jae(self) -> WatchlistEvaluationListResponse:
        rows = self.repo.list_watchlist_with_latest_scores()
        factors_by_watchlist_id = self.repo.list_latest_factors_by_watchlist_ids([row[0].id for row in rows])
        items: list[WatchlistEvaluationListItem] = []
        last_evaluated_values: list[str] = []
        for watchlist, stock, score, price_count, metrics_count in rows:
            missing = _json_list(score.missing_data_json) if score else _missing_data(price_count, metrics_count)
            market_factors = self._factor_responses(factors_by_watchlist_id.get(watchlist.id, []), category="MARKET")
            missing_market_data = self._missing_market_data_from_factors(market_factors)
            if score and score.evaluated_at:
                last_evaluated_values.append(score.evaluated_at)
            items.append(
                WatchlistEvaluationListItem(
                    watchlist_id=watchlist.id,
                    stock_id=stock.id,
                    stock_code=stock.stock_code,
                    stock_name=stock.stock_name,
                    market=stock.market,
                    is_active=watchlist.is_active == 1,
                    watch_reason=watchlist.interest_reason,
                    stock_type=stock.security_type or "UNCLASSIFIED",
                    market_score=score.market_score if score else None,
                    market_status=score.market_status if score else "NOT_EVALUATED",
                    market_grade=_score_grade(score.market_score if score else None),
                    market_summary=score.summary_text if score else "시장 평가 전입니다.",
                    market_factors=market_factors,
                    missing_market_data=missing_market_data,
                    material_score=score.material_score if score else None,
                    supply_score=score.supply_score if score else None,
                    chart_score=score.chart_score if score else None,
                    financial_score=score.financial_score if score else None,
                    total_score=score.total_score if score else None,
                    data_confidence=score.data_confidence if score else "NOT_EVALUATED",
                    last_evaluated_at=score.evaluated_at if score else None,
                    missing_data=missing,
                )
            )
        evaluated_count = len([item for item in items if item.last_evaluated_at])
        return WatchlistEvaluationListResponse(
            items=items,
            summary=WatchlistEvaluationSummary(
                watchlist_count=len(items),
                active_count=len([item for item in items if item.is_active]),
                inactive_count=len([item for item in items if not item.is_active]),
                evaluated_count=evaluated_count,
                not_evaluated_count=len(items) - evaluated_count,
                missing_data_count=len([item for item in items if item.missing_data or item.missing_market_data]),
                last_evaluated_at=max(last_evaluated_values) if last_evaluated_values else None,
            ),
        )

    def evaluate(self, payload: WatchlistEvaluateRequest) -> WatchlistEvaluateResponse:
        if not payload.watchlist_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="평가할 관심종목을 선택해 주세요.")
        rows = self.repo.list_watchlist_by_ids(payload.watchlist_ids)
        return self._create_scores(rows, payload.run_type)

    def evaluate_all(self, payload: WatchlistEvaluateAllRequest) -> WatchlistEvaluateResponse:
        rows = self.repo.list_all_watchlist(payload.include_inactive)
        return self._create_scores(rows, payload.run_type)

    def _create_scores(self, rows: list[Watchlist], run_type: str) -> WatchlistEvaluateResponse:
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="평가할 관심종목이 없습니다.")

        now = now_kst()
        run = self.repo.create_run(
            WatchlistEvaluationRun(
                run_date=now[:10],
                run_type=run_type or "MANUAL",
                status="SUCCESS",
                memo="2단계-1: 시장 탭 실제 평가 연결",
                created_at=now,
                updated_at=now,
            )
        )
        for item in rows:
            stock = self.stock_repo.get_by_id(item.stock_id)
            market_result = self._evaluate_market_for_watchlist_stock(stock.market if stock else None)
            missing_data = ["financial", "supply"] + [f"market:{code}" for code in market_result["missing_codes"]]
            score = self.repo.create_score(
                WatchlistEvaluationScore(
                    run_id=run.id,
                    watchlist_stock_id=item.id,
                    stock_id=item.stock_id,
                    evaluated_at=now,
                    market_score=market_result["score"],
                    material_score=None,
                    supply_score=None,
                    chart_score=None,
                    financial_score=None,
                    total_score=None,
                    market_status=market_result["status"],
                    material_status="NOT_EVALUATED",
                    supply_status="NOT_EVALUATED",
                    chart_status="NOT_EVALUATED",
                    financial_status="NOT_EVALUATED",
                    overall_status="미평가",
                    data_confidence=market_result["confidence"],
                    risk_flags_json="[]",
                    missing_data_json=json.dumps(missing_data, ensure_ascii=False),
                    summary_text=market_result["summary"],
                    created_at=now,
                    updated_at=now,
                )
            )
            for factor in market_result["factors"]:
                self.repo.create_factor(
                    WatchlistEvaluationFactor(
                        score_id=score.id,
                        category="MARKET",
                        factor_code=factor["factor_code"],
                        factor_name=factor["factor_name"],
                        raw_value=factor.get("raw_value"),
                        normalized_score=factor.get("normalized_score"),
                        weight=factor.get("weight"),
                        contribution_score=factor.get("contribution_score"),
                        reason=factor.get("reason"),
                        source_table=factor.get("source_table"),
                        source_date=factor.get("source_date"),
                        created_at=now,
                    )
                )
        self.repo.commit()
        return WatchlistEvaluateResponse(run_id=run.id, evaluated_count=len(rows), status="SUCCESS")

    def _evaluate_market_for_watchlist_stock(self, stock_market: str | None) -> dict[str, Any]:
        factors = [
            self._domestic_index_factor(stock_market),
            self._market_breadth_factor(),
            self._market_liquidity_factor(stock_market),
            self._us_market_factor(),
            self._external_risk_factor(),
        ]
        domestic_available = factors[0].get("contribution_score") is not None
        available_factors = [factor for factor in factors if factor.get("contribution_score") is not None and factor.get("weight")]
        available_weight = sum(float(factor["weight"]) for factor in available_factors)
        contribution_sum = sum(float(factor["contribution_score"]) for factor in available_factors)
        if not domestic_available or available_weight <= 0:
            score_value = None
        else:
            score_value = round(contribution_sum / available_weight * 100, 2)
        missing_codes = [factor["factor_code"] for factor in factors if factor.get("contribution_score") is None]
        missing_labels = [MARKET_MISSING_LABELS.get(code, code) for code in missing_codes]
        status_value = _status_by_available_count(len(available_factors), domestic_available)
        return {
            "score": score_value,
            "status": status_value,
            "confidence": _confidence_by_available_count(len(available_factors), domestic_available),
            "summary": _score_summary(score_value, status_value, missing_labels),
            "missing_codes": missing_codes,
            "factors": factors,
        }

    def _factor(self, code: str, *, score: float | None, raw: str | None, reason: str, source_table: str | None, source_date: str | None) -> dict[str, Any]:
        name, weight = MARKET_FACTOR_META[code]
        normalized = None if score is None else max(0.0, min(weight, round(score, 2)))
        return {
            "factor_code": code,
            "factor_name": name,
            "raw_value": raw,
            "normalized_score": normalized,
            "weight": weight,
            "contribution_score": normalized,
            "reason": reason,
            "source_table": source_table,
            "source_date": source_date,
        }

    def _domestic_index_factor(self, stock_market: str | None) -> dict[str, Any]:
        kospi = self._index_component_score("KOSPI")
        kosdaq = self._index_component_score("KOSDAQ")
        weights = self._domestic_weights(stock_market)
        components = [("KOSPI", kospi, weights["KOSPI"]), ("KOSDAQ", kosdaq, weights["KOSDAQ"])]
        available = [(code, item, weight) for code, item, weight in components if item.get("score") is not None]
        if not available:
            return self._factor(
                "DOMESTIC_INDEX_TREND",
                score=None,
                raw=None,
                reason="KOSPI/KOSDAQ 지수 가격 데이터가 없어 국내 지수 흐름을 평가하지 않았습니다.",
                source_table=None,
                source_date=None,
            )
        weight_sum = sum(weight for _, _, weight in available)
        avg_15 = sum(float(item["score"]) * weight for _, item, weight in available) / weight_sum
        score = avg_15 / 15 * 30
        raw = "; ".join(str(item["raw"]) for _, item, _ in available)
        source_date = max(str(item["source_date"]) for _, item, _ in available if item.get("source_date"))
        reason = "KOSPI/KOSDAQ의 20일선·60일선 위치, 당일 등락률, 최근 5일 수익률을 관심종목 시장구분 가중치로 반영했습니다."
        return self._factor("DOMESTIC_INDEX_TREND", score=score, raw=raw, reason=reason, source_table="market_index_daily_prices", source_date=source_date)

    @staticmethod
    def _domestic_weights(stock_market: str | None) -> dict[str, float]:
        market = (stock_market or "").upper()
        if market == "KOSPI":
            return {"KOSPI": 0.7, "KOSDAQ": 0.3}
        if market == "KOSDAQ":
            return {"KOSPI": 0.3, "KOSDAQ": 0.7}
        return {"KOSPI": 0.5, "KOSDAQ": 0.5}

    def _index_component_score(self, index_code: str) -> dict[str, Any]:
        rows = self.repo.list_market_index_daily_rows(index_code, limit=80)
        if not rows:
            return {"score": None}
        latest = rows[-1]
        close = _as_float(latest.get("close_price"))
        ma20 = _as_float(latest.get("ma20")) or _simple_ma(rows, 20)
        ma60 = _as_float(latest.get("ma60")) or _simple_ma(rows, 60)
        change = _as_float(latest.get("change_rate"))
        ret5 = _recent_return(rows, 5)
        if close is None or ma20 is None or ma60 is None:
            return {"score": None}
        above20 = close >= ma20
        above60 = close >= ma60
        score = 15.0 if above20 and above60 else 11.0 if above20 else 8.0 if above60 else 4.0
        if change is not None:
            if change >= 1:
                score += 2
            elif change <= -1:
                score -= 2
        if ret5 is not None:
            if ret5 >= 2:
                score += 2
            elif ret5 <= -2:
                score -= 2
        score = max(0.0, min(15.0, score))
        raw = f"{index_code} 종가 {close:.2f}, 20일선 {'위' if above20 else '아래'}, 60일선 {'위' if above60 else '아래'}, 등락률 {change if change is not None else '-'}%, 5일 {round(ret5, 2) if ret5 is not None else '-'}%"
        return {"score": score, "raw": raw, "source_date": latest.get("price_date")}

    def _market_breadth_factor(self) -> dict[str, Any]:
        components = []
        for code in ("KOSPI", "KOSDAQ"):
            rows = self.repo.list_market_index_daily_rows(code, limit=5)
            if rows and _as_float(rows[-1].get("change_rate")) is not None:
                components.append((code, float(rows[-1]["change_rate"]), rows[-1].get("price_date")))
        if not components:
            return self._factor(
                "MARKET_BREADTH",
                score=None,
                raw=None,
                reason="상승/하락 종목 수 또는 대체 지수 등락률 데이터가 없어 시장 체감/폭을 점수에 반영하지 않았습니다.",
                source_table=None,
                source_date=None,
            )
        avg_change = sum(value for _, value, _ in components) / len(components)
        score = 20 if avg_change >= 1 else 17 if avg_change >= 0.5 else 14 if avg_change >= 0 else 10 if avg_change >= -0.5 else 6 if avg_change >= -1 else 3
        raw = ", ".join(f"{code} {change:+.2f}%" for code, change, _ in components)
        return self._factor(
            "MARKET_BREADTH",
            score=float(score),
            raw=f"대체지표 평균 등락률 {avg_change:+.2f}% ({raw})",
            reason="상승/하락 종목 수 데이터가 없어 KOSPI/KOSDAQ 당일 등락률 평균을 시장 체감/폭의 대체 지표로 사용했습니다.",
            source_table="market_index_daily_prices",
            source_date=max(str(date) for _, _, date in components if date),
        )

    def _market_liquidity_factor(self, stock_market: str | None) -> dict[str, Any]:
        market = (stock_market or "").upper()
        codes = [market] if market in {"KOSPI", "KOSDAQ"} else ["KOSPI", "KOSDAQ"]
        ratios: list[tuple[str, float, str]] = []
        for code in codes:
            rows = self.repo.list_market_index_daily_rows(code, limit=30)
            values = [_as_float(row.get("trading_value")) for row in rows]
            if len(values) < 2 or values[-1] is None:
                continue
            previous = [value for value in values[-21:-1] if value is not None and value > 0]
            if not previous:
                continue
            ratios.append((code, float(values[-1]) / (sum(previous) / len(previous)), str(rows[-1].get("price_date"))))
        if not ratios:
            return self._factor(
                "MARKET_LIQUIDITY",
                score=None,
                raw=None,
                reason="시장 거래대금 또는 20일 평균 거래대금 데이터가 없어 시장 유동성을 점수에 반영하지 않았습니다.",
                source_table=None,
                source_date=None,
            )
        ratio = sum(item[1] for item in ratios) / len(ratios)
        score = 15 if ratio >= 1.3 else 12 if ratio >= 1.1 else 9 if ratio >= 0.9 else 6 if ratio >= 0.7 else 3
        raw = ", ".join(f"{code} 20일 평균 대비 {value * 100:.1f}%" for code, value, _ in ratios)
        return self._factor(
            "MARKET_LIQUIDITY",
            score=float(score),
            raw=raw,
            reason="관심종목 시장구분에 맞춰 시장 거래대금이 최근 20일 평균 대비 어느 정도인지 반영했습니다.",
            source_table="market_index_daily_prices",
            source_date=max(date for _, _, date in ratios),
        )

    def _indicator_change_pct(self, code: str) -> tuple[float | None, str | None]:
        latest = self.repo.get_market_indicator_latest(code)
        if latest and _as_float(latest.get("latest_change_pct")) is not None:
            return _as_float(latest.get("latest_change_pct")), latest.get("latest_value_date")
        rows = self.repo.list_market_indicator_values(code, limit=2)
        if len(rows) >= 2:
            current = _as_float(rows[-1].get("value"))
            previous = _as_float(rows[-2].get("value"))
            if current is not None and previous not in (None, 0):
                return (current / previous - 1) * 100, rows[-1].get("value_date")
        return None, None

    def _indicator_rate_change_bp(self, code: str) -> tuple[float | None, str | None]:
        latest = self.repo.get_market_indicator_latest(code)
        if latest and _as_float(latest.get("latest_change_value")) is not None:
            return _as_float(latest.get("latest_change_value")) * 100, latest.get("latest_value_date")
        rows = self.repo.list_market_indicator_values(code, limit=2)
        if len(rows) >= 2:
            current = _as_float(rows[-1].get("value"))
            previous = _as_float(rows[-2].get("value"))
            if current is not None and previous is not None:
                return (current - previous) * 100, rows[-1].get("value_date")
        return None, None

    def _us_market_factor(self) -> dict[str, Any]:
        scores: list[tuple[str, float, float, str | None]] = []
        for code, label in (("US_NASDAQ", "NASDAQ"), ("US_SP500", "S&P500"), ("US_DOW", "DOW"), ("US_SOX", "SOX")):
            change, value_date = self._indicator_change_pct(code)
            if change is None:
                continue
            point = 5 if change >= 1 else 4 if change > 0 else 3 if change > -1 else 2 if change > -2 else 1
            scores.append((label, float(point), change, value_date))
        if not scores:
            return self._factor(
                "US_MARKET_TREND",
                score=None,
                raw=None,
                reason="NASDAQ/S&P500/DOW/SOX 데이터가 없어 미국 시장 흐름을 점수에 반영하지 않았습니다.",
                source_table=None,
                source_date=None,
            )
        score = sum(item[1] for item in scores) / (len(scores) * 5) * 20
        raw = ", ".join(f"{label} {change:+.2f}%" for label, _, change, _ in scores)
        dates = [str(value_date) for _, _, _, value_date in scores if value_date]
        return self._factor("US_MARKET_TREND", score=score, raw=raw, reason="미국 주요 지수의 직전 변화율을 각 5점 만점으로 환산했습니다.", source_table="market_indicators", source_date=max(dates) if dates else None)

    def _external_risk_factor(self) -> dict[str, Any]:
        deductions: list[tuple[str, float]] = []
        observed_dates: list[str] = []
        usd_change, usd_date = self._indicator_change_pct("USD_KRW")
        if usd_date:
            observed_dates.append(str(usd_date))
        usd_rows = self.repo.list_market_indicator_values("USD_KRW", limit=6)
        usd_5d = None
        if len(usd_rows) >= 6:
            latest = _as_float(usd_rows[-1].get("value"))
            base = _as_float(usd_rows[-6].get("value"))
            if latest is not None and base not in (None, 0):
                usd_5d = (latest / base - 1) * 100
                observed_dates.append(str(usd_rows[-1].get("value_date")))
        us10y_bp, us10y_date = self._indicator_rate_change_bp("US_10Y")
        us2y_bp, us2y_date = self._indicator_rate_change_bp("US_2Y")
        if us10y_date:
            observed_dates.append(str(us10y_date))
        if us2y_date:
            observed_dates.append(str(us2y_date))
        if usd_change is not None and usd_change >= 1:
            deductions.append((f"원/달러 당일 +{usd_change:.2f}%", 4))
        if usd_5d is not None and usd_5d >= 2:
            deductions.append((f"원/달러 5일 +{usd_5d:.2f}%", 4))
        if us10y_bp is not None and us10y_bp >= 5:
            deductions.append((f"미국 10년물 +{us10y_bp:.1f}bp", 3))
        if us2y_bp is not None and us2y_bp >= 5:
            deductions.append((f"미국 2년물 +{us2y_bp:.1f}bp", 2))
        if us10y_bp is not None and us2y_bp is not None and us10y_bp >= 5 and us2y_bp >= 5:
            deductions.append(("미국 10년물·2년물 동반 급등", 2))
        if usd_change is None and usd_5d is None and us10y_bp is None and us2y_bp is None:
            return self._factor(
                "EXTERNAL_RISK",
                score=None,
                raw=None,
                reason="환율과 미국 금리 데이터가 없어 외부 위험을 점수에 반영하지 않았습니다.",
                source_table=None,
                source_date=None,
            )
        total_deduction = sum(value for _, value in deductions)
        score = max(0.0, 15.0 - total_deduction)
        raw_parts = [label for label, _ in deductions] or ["위험 감점 조건 없음"]
        return self._factor(
            "EXTERNAL_RISK",
            score=score,
            raw=", ".join(raw_parts),
            reason="환율 급등과 미국 금리 급등 여부를 감점 방식으로 반영했습니다.",
            source_table="market_indicators",
            source_date=max(observed_dates) if observed_dates else None,
        )

    def get_history(self, watchlist_id: int) -> list[WatchlistEvaluationHistoryItem]:
        if not self.watchlist_repo.get_by_id(watchlist_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="watchlist not found")
        return [
            WatchlistEvaluationHistoryItem(
                score_id=score.id,
                run_id=run.id,
                run_date=run.run_date,
                run_type=run.run_type,
                status=run.status,
                evaluated_at=score.evaluated_at,
                market_score=score.market_score,
                market_status=score.market_status,
                market_grade=_score_grade(score.market_score),
                material_score=score.material_score,
                supply_score=score.supply_score,
                chart_score=score.chart_score,
                financial_score=score.financial_score,
                total_score=score.total_score,
                overall_status=score.overall_status,
                data_confidence=score.data_confidence,
                missing_data=_json_list(score.missing_data_json),
            )
            for score, run in self.repo.list_history(watchlist_id)
        ]

    def get_score(self, score_id: int) -> WatchlistEvaluationScoreResponse:
        score = self.repo.get_score(score_id)
        if not score:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="score not found")
        factors = self._factor_responses(self.repo.list_factors(score_id))
        market_factors = [factor for factor in factors if factor.category == "MARKET"]
        return WatchlistEvaluationScoreResponse(
            id=score.id,
            run_id=score.run_id,
            watchlist_stock_id=score.watchlist_stock_id,
            stock_id=score.stock_id,
            evaluated_at=score.evaluated_at,
            market_score=score.market_score,
            market_status=score.market_status,
            market_grade=_score_grade(score.market_score),
            market_summary=score.summary_text,
            market_factors=market_factors,
            missing_market_data=self._missing_market_data_from_factors(market_factors),
            material_score=score.material_score,
            supply_score=score.supply_score,
            chart_score=score.chart_score,
            financial_score=score.financial_score,
            total_score=score.total_score,
            material_status=score.material_status,
            supply_status=score.supply_status,
            chart_status=score.chart_status,
            financial_status=score.financial_status,
            overall_status=score.overall_status,
            data_confidence=score.data_confidence,
            risk_flags=_json_list(score.risk_flags_json),
            missing_data=_json_list(score.missing_data_json),
            summary_text=score.summary_text,
            created_at=score.created_at,
            updated_at=score.updated_at,
            factors=factors,
        )

    def _factor_responses(self, factors: list[WatchlistEvaluationFactor], category: str | None = None) -> list[WatchlistEvaluationFactorResponse]:
        rows = [factor for factor in factors if category is None or factor.category == category]
        return [WatchlistEvaluationFactorResponse.model_validate(factor) for factor in rows]

    @staticmethod
    def _missing_market_data_from_factors(factors: list[WatchlistEvaluationFactorResponse]) -> list[str]:
        return [factor.factor_name for factor in factors if factor.contribution_score is None]

    def create_gpt_prompt(self, watchlist_id: int) -> WatchlistGptPromptResponse:
        item = self.watchlist_repo.get_by_id(watchlist_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="watchlist not found")
        stock = self.stock_repo.get_by_id(item.stock_id)
        if not stock:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stock not found")
        latest = next((row for row in self.repo.list_watchlist_with_latest_scores() if row[0].id == watchlist_id), None)
        missing = _json_list(latest[2].missing_data_json) if latest and latest[2] else []
        prompt = "\n".join(
            [
                f"DrCT 관심종목 시재수차재 평가 검토 요청: {stock.stock_name}({stock.stock_code})",
                f"- 시장: {stock.market or '-'}",
                f"- 관심 사유: {item.interest_reason or '-'}",
                f"- 관심종목 활성 여부: {'활성' if item.is_active == 1 else '비활성'}",
                f"- 시장 점수: {latest[2].market_score if latest and latest[2] else '미평가'}",
                f"- 시장 상태: {latest[2].market_status if latest and latest[2] else '미평가'}",
                f"- 미수집/미반영 데이터: {', '.join(missing) if missing else '없음'}",
                "",
                "시장, 재료, 수급, 차트, 재무 관점에서 현재 사용할 수 있는 근거와 부족한 근거를 구분해 주세요.",
                "1차 개발 단계이므로 매수/매도 추천 문구 대신 추가 확인 항목과 리스크만 정리해 주세요.",
            ]
        )
        return WatchlistGptPromptResponse(watchlist_id=watchlist_id, prompt=prompt)