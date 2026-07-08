from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.entities.watchlist import Watchlist
from backend.app.entities.watchlist_evaluation import WatchlistEvaluationFactor, WatchlistEvaluationRun, WatchlistEvaluationScore
from backend.app.repositories.stock_repository import StockRepository
from backend.app.repositories.stock_investor_flow_repository import StockInvestorFlowRepository
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
    MaterialDisclosureItem,
    MaterialNewsItem,
    MaterialThemeItem,
    WatchlistEvaluationSummary,
    WatchlistGptPromptResponse,
)



MATERIAL_FACTOR_META = {
    "MATERIAL_NEWS_STRENGTH": ("뉴스 재료 강도", 30.0),
    "MATERIAL_DISCLOSURE_STRENGTH": ("공시 재료 강도", 25.0),
    "MATERIAL_THEME_ALIGNMENT": ("테마 연결도", 20.0),
    "MATERIAL_RECENCY": ("재료 최근성", 15.0),
    "MATERIAL_CONTINUITY": ("재료 지속성", 10.0),
}

MATERIAL_MISSING_LABELS = {
    "MATERIAL_NEWS_STRENGTH": "뉴스 재료 강도",
    "MATERIAL_DISCLOSURE_STRENGTH": "공시 재료 강도",
    "MATERIAL_RECENCY": "재료 최근성",
    "MATERIAL_CONTINUITY": "재료 지속성",
}

MATERIAL_KEYWORDS = ("수주", "계약", "공급", "실적", "매출", "영업이익", "흑자", "테마", "신규", "승인", "허가", "투자", "증설", "인수", "합병")
MATERIAL_RISK_KEYWORDS = ("소송", "제재", "거래정지", "관리종목", "유상증자", "전환사채", "CB", "BW", "불성실", "감사의견")


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


SUPPLY_FACTOR_META = {
    "SUPPLY_TRADING_VALUE_INTENSITY": ("\uac70\ub798\ub300\uae08 \uac15\ub3c4", 30.0),
    "SUPPLY_CONTINUITY": ("\uc218\uae09 \uc5f0\uc18d\uc131", 25.0),
    "SUPPLY_THEME_ALIGNMENT": ("\ud14c\ub9c8 \ub3d9\uc870", 25.0),
    "SUPPLY_THEME_RELATIVE_POSITION": ("\ud14c\ub9c8 \ub0b4 \uc0c1\ub300 \uc704\uce58", 20.0),
    "SUPPLY_INVESTOR_FLOW": ("\ud22c\uc790\uc8fc\uccb4\ubcc4 \uc218\uae09", 20.0),
}


SUPPLY_MISSING_LABELS = {
    "SUPPLY_TRADING_VALUE_INTENSITY": "거래대금 강도",
    "SUPPLY_CONTINUITY": "수급 연속성",
    "SUPPLY_THEME_ALIGNMENT": "테마 동조",
    "SUPPLY_THEME_RELATIVE_POSITION": "테마 내 상대 위치",
}

SUPPLY_INVESTOR_FLOW_STATUS = {
    "foreign": "2차 예정",
    "institution": "2차 예정",
    "program": "2차 예정",
    "credit": "2차 예정",
    "short": "2차 예정",
    "loan": "2차 예정",
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




def _date_text(value: Any) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value[:10] if len(text_value) >= 10 else text_value or None


def _parse_date(value: Any) -> date | None:
    text_value = _date_text(value)
    if not text_value:
        return None
    try:
        return datetime.strptime(text_value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _days_between(base_date: str, value: Any) -> int | None:
    base = _parse_date(base_date)
    target = _parse_date(value)
    if not base or not target:
        return None
    return max(0, (base - target).days)


def _material_grade(score: float | None) -> str:
    if score is None:
        return "미평가"
    if score >= 80:
        return "재료 강함"
    if score >= 65:
        return "재료 양호"
    if score >= 50:
        return "재료 보통"
    if score >= 35:
        return "재료 약함"
    return "재료 부족"


def _material_status_by_available_count(available_count: int) -> str:
    if available_count >= 4:
        return "EVALUATED"
    if available_count >= 2:
        return "PARTIAL"
    return "DATA_MISSING"


def _material_confidence_by_available_count(available_count: int) -> str:
    if available_count >= 4:
        return "ENOUGH"
    if available_count >= 2:
        return "PARTIAL"
    return "LIMITED"


def _material_importance(row: dict[str, Any]) -> float:
    ai_score = _as_float(row.get("ai_importance_score"))
    if ai_score is not None and ai_score > 0:
        return max(0.0, min(100.0, ai_score))
    score = _as_float(row.get("importance_score"))
    return max(0.0, min(100.0, score or 0.0))


def _text_contains_any(value: str | None, keywords: tuple[str, ...]) -> bool:
    text_value = (value or "").upper()
    return any(keyword.upper() in text_value for keyword in keywords)


def _supply_grade(score: float | None) -> str:
    if score is None:
        return "미평가"
    if score >= 80:
        return "강한 수급"
    if score >= 65:
        return "수급 양호"
    if score >= 50:
        return "보통"
    if score >= 35:
        return "약한 수급"
    return "수급 부족"


def _supply_status_by_available_count(available_count: int) -> str:
    if available_count >= 3:
        return "EVALUATED"
    if available_count == 2:
        return "PARTIAL"
    return "DATA_MISSING"


def _supply_confidence_by_available_count(available_count: int) -> str:
    if available_count >= 3:
        return "ENOUGH"
    if available_count == 2:
        return "PARTIAL"
    return "LIMITED"


def _combine_confidence(*values: str) -> str:
    rank = {"NOT_EVALUATED": 0, "LIMITED": 1, "PARTIAL": 2, "ENOUGH": 3}
    reverse = {value: key for key, value in rank.items()}
    return reverse.get(min(rank.get(value or "LIMITED", 1) for value in values), "LIMITED")


def _supply_summary(score: float | None, status_value: str | None, missing: list[str], theme_name: str | None = None) -> str:
    if score is None:
        return "수급 평가에 필요한 거래대금 또는 테마 데이터가 부족합니다. 기관·외국인 수급은 2차에서 연결됩니다."
    grade = _supply_grade(score)
    theme_text = f" 대표 테마는 {theme_name}입니다." if theme_name else ""
    base = {
        "강한 수급": "거래대금과 테마 내 위치가 강하게 확인됩니다.",
        "수급 양호": "수급 흐름이 대체로 양호합니다.",
        "보통": "수급 흐름은 보통 수준입니다.",
        "약한 수급": "수급 강도가 약해 추가 확인이 필요합니다.",
        "수급 부족": "거래대금과 테마 흐름 기준 수급 근거가 부족합니다.",
    }.get(grade, "수급 평가가 필요합니다.")
    if status_value == "PARTIAL" and missing:
        return f"{base}{theme_text} 다만 {', '.join(missing)} 데이터가 없어 일부 판단은 제한됩니다."
    return f"{base}{theme_text} 투자주체별 수급 데이터가 없으면 V1 산식을 유지합니다."

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
        self.investor_flow_repo = StockInvestorFlowRepository(db)

    def list_sije_sucha_jae(self) -> WatchlistEvaluationListResponse:
        rows = self.repo.list_watchlist_with_latest_scores()
        factors_by_watchlist_id = self.repo.list_latest_factors_by_watchlist_ids([row[0].id for row in rows])
        items: list[WatchlistEvaluationListItem] = []
        last_evaluated_values: list[str] = []
        for watchlist, stock, score, price_count, metrics_count in rows:
            missing = _json_list(score.missing_data_json) if score else _missing_data(price_count, metrics_count)
            all_latest_factors = factors_by_watchlist_id.get(watchlist.id, [])
            market_factors = self._factor_responses(all_latest_factors, category="MARKET")
            material_factors = self._factor_responses(all_latest_factors, category="MATERIAL")
            supply_factors = self._factor_responses(all_latest_factors, category="SUPPLY")
            missing_market_data = self._missing_market_data_from_factors(market_factors)
            missing_material_data = self._missing_material_data_from_factors(material_factors)
            missing_supply_data = self._missing_supply_data_from_factors(supply_factors)
            material_context = self._evaluate_material_for_watchlist_stock(stock.id, (score.evaluated_at[:10] if score and score.evaluated_at else now_kst()[:10]))
            representative_theme_name, representative_theme_return_30d = self._representative_theme_from_factors(supply_factors)
            investor_flow_summary = self._investor_flow_summary(stock.id)
            investor_flow_subject_count = self._investor_flow_subject_count(investor_flow_summary)
            supply_model_version = "V2" if investor_flow_subject_count >= 2 else "V2_PARTIAL" if investor_flow_subject_count == 1 else "V1_NO_INVESTOR_FLOW"
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
                    material_status=score.material_status if score else "NOT_EVALUATED",
                    material_grade=_material_grade(score.material_score if score else None),
                    material_summary=material_context["summary"] if score else "재료 평가 전입니다.",
                    material_factors=material_factors,
                    missing_material_data=missing_material_data,
                    latest_material_date=material_context["latest_material_date"],
                    material_news_count=material_context["material_news_count"],
                    material_disclosure_count=material_context["material_disclosure_count"],
                    material_theme_names=material_context["material_theme_names"],
                    material_recent_news=material_context["recent_news"],
                    material_recent_disclosures=material_context["recent_disclosures"],
                    material_themes=material_context["themes"],
                    supply_score=score.supply_score if score else None,
                    supply_status=score.supply_status if score else "NOT_EVALUATED",
                    supply_grade=_supply_grade(score.supply_score if score else None),
                    supply_summary=self._supply_summary_v2(score.supply_score if score else None, score.supply_status if score else "NOT_EVALUATED", missing_supply_data, representative_theme_name, investor_flow_summary, supply_model_version),
                    supply_factors=supply_factors,
                    missing_supply_data=missing_supply_data,
                    representative_theme_name=representative_theme_name,
                    representative_theme_return_30d=representative_theme_return_30d,
                    supply_investor_flow_status=self._investor_flow_status_from_summary(investor_flow_summary),
                    supply_model_version=supply_model_version,
                    investor_flow_summary=investor_flow_summary,
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
                missing_data_count=len([item for item in items if item.missing_data or item.missing_market_data or item.missing_material_data or item.missing_supply_data]),
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
                memo="2단계-2: 수급 탭 1차 MVP 평가 연결",
                created_at=now,
                updated_at=now,
            )
        )
        for item in rows:
            stock = self.stock_repo.get_by_id(item.stock_id)
            market_result = self._evaluate_market_for_watchlist_stock(stock.market if stock else None)
            material_result = self._evaluate_material_for_watchlist_stock(item.stock_id, now[:10])
            supply_result = self._evaluate_supply_for_watchlist_stock(item.stock_id)
            missing_data = ["financial"] + [f"market:{code}" for code in market_result["missing_codes"]]
            missing_data += [f"material:{code}" for code in material_result["missing_codes"]]
            missing_data += [f"supply:{code}" for code in supply_result["missing_codes"]]
            if material_result["status"] == "DATA_MISSING":
                missing_data.append("material")
            if supply_result["status"] == "DATA_MISSING":
                missing_data.append("supply")
            missing_data = list(dict.fromkeys(missing_data))
            score = self.repo.create_score(
                WatchlistEvaluationScore(
                    run_id=run.id,
                    watchlist_stock_id=item.id,
                    stock_id=item.stock_id,
                    evaluated_at=now,
                    market_score=market_result["score"],
                    material_score=material_result["score"],
                    supply_score=supply_result["score"],
                    chart_score=None,
                    financial_score=None,
                    total_score=None,
                    market_status=market_result["status"],
                    material_status=material_result["status"],
                    supply_status=supply_result["status"],
                    chart_status="NOT_EVALUATED",
                    financial_status="NOT_EVALUATED",
                    overall_status="미평가",
                    data_confidence=_combine_confidence(market_result["confidence"], material_result["confidence"], supply_result["confidence"]),
                    risk_flags_json="[]",
                    missing_data_json=json.dumps(missing_data, ensure_ascii=False),
                    summary_text=market_result["summary"],
                    created_at=now,
                    updated_at=now,
                )
            )
            for factor in [*market_result["factors"], *material_result["factors"], *supply_result["factors"]]:
                self.repo.create_factor(
                    WatchlistEvaluationFactor(
                        score_id=score.id,
                        category=factor.get("category", "MARKET"),
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


    def _evaluate_material_for_watchlist_stock(self, stock_id: int, base_date: str) -> dict[str, Any]:
        news_rows = self.repo.list_material_news(stock_id, limit=30)
        disclosure_rows = self.repo.list_material_disclosures(stock_id, limit=30)
        theme_rows = self.repo.list_stock_themes(stock_id)
        theme_metrics = self._representative_theme_metrics(stock_id)
        factors = [
            self._material_news_strength_factor(news_rows, base_date),
            self._material_disclosure_strength_factor(disclosure_rows, base_date),
            self._material_theme_alignment_factor(theme_rows, theme_metrics),
        ]
        material_dates = self._material_event_dates(news_rows, disclosure_rows, theme_metrics)
        event_count_30d = self._material_event_count_30d(news_rows, disclosure_rows, base_date)
        factors.extend([
            self._material_recency_factor(material_dates, base_date),
            self._material_continuity_factor(event_count_30d, material_dates),
        ])
        available_factors = [factor for factor in factors if factor.get("contribution_score") is not None and factor.get("weight")]
        available_weight = sum(float(factor["weight"]) for factor in available_factors)
        contribution_sum = sum(float(factor["contribution_score"]) for factor in available_factors)
        score_value = round(contribution_sum / available_weight * 100, 2) if available_weight > 0 else None
        missing_codes = [factor["factor_code"] for factor in factors if factor.get("contribution_score") is None]
        missing_labels = [MATERIAL_MISSING_LABELS.get(code, code) for code in missing_codes]
        status_value = _material_status_by_available_count(len(available_factors))
        latest_material_date = max(material_dates) if material_dates else None
        theme_names = [str(row.get("theme_name")) for row in theme_rows[:5] if row.get("theme_name")]
        summary = self._material_summary(score_value, status_value, news_rows, disclosure_rows, theme_names, latest_material_date, missing_labels)
        return {
            "score": score_value,
            "status": status_value,
            "confidence": _material_confidence_by_available_count(len(available_factors)),
            "summary": summary,
            "missing_codes": missing_codes,
            "factors": factors,
            "latest_material_date": latest_material_date,
            "material_news_count": len(news_rows),
            "material_disclosure_count": len(disclosure_rows),
            "material_theme_names": theme_names,
            "recent_news": self._material_news_items(news_rows),
            "recent_disclosures": self._material_disclosure_items(disclosure_rows),
            "themes": self._material_theme_items(theme_rows, theme_metrics),
        }

    def _material_factor(self, code: str, *, score: float | None, raw: str | None, reason: str, source_table: str | None, source_date: str | None) -> dict[str, Any]:
        name, weight = MATERIAL_FACTOR_META[code]
        normalized = None if score is None else max(0.0, min(weight, round(score, 2)))
        return {
            "category": "MATERIAL",
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

    def _material_news_strength_factor(self, rows: list[dict[str, Any]], base_date: str) -> dict[str, Any]:
        if not rows:
            return self._material_factor(
                "MATERIAL_NEWS_STRENGTH",
                score=None,
                raw=None,
                reason="\uc218\uc9d1\ub41c \ub274\uc2a4 \ub370\uc774\ud130\uac00 \uc5c6\uc5b4 \ub274\uc2a4 \uc7ac\ub8cc \uac15\ub3c4\ub294 \ud3c9\uac00\uc5d0\uc11c \uc81c\uc678\ud588\uc2b5\ub2c8\ub2e4.",
                source_table=None,
                source_date=None,
            )
        recent7 = [row for row in rows if (days := _days_between(base_date, row.get("published_at") or row.get("collected_at"))) is not None and days <= 7]
        recent30 = [row for row in rows if (days := _days_between(base_date, row.get("published_at") or row.get("collected_at"))) is not None and days <= 30]
        direct = [row for row in recent7 if _material_importance(row) >= 60 or _text_contains_any(f"{row.get('title')} {row.get('summary')} {row.get('ai_tags')}", MATERIAL_KEYWORDS)]
        avg_importance = sum(_material_importance(row) for row in recent7 or recent30 or rows) / max(1, len(recent7 or recent30 or rows))
        if len(direct) >= 3 and avg_importance >= 70:
            score = 30
        elif len(direct) >= 1 and avg_importance >= 60:
            score = 24
        elif len(recent30) >= 2:
            score = 18
        elif recent30:
            score = 10
        else:
            score = 4
        latest = max((_date_text(row.get("published_at") or row.get("collected_at")) for row in rows), default=None)
        return self._material_factor(
            "MATERIAL_NEWS_STRENGTH",
            score=float(score),
            raw=f"\ucd5c\uadfc 7\uc77c \ub274\uc2a4 {len(recent7)}\uac74, \ucd5c\uadfc 30\uc77c \ub274\uc2a4 {len(recent30)}\uac74, \ud3c9\uade0 \uc911\uc694\ub3c4 {avg_importance:.1f}",
            reason=f"\ucd5c\uadfc \ub274\uc2a4 {len(recent30)}\uac74 \uc911 \uc7ac\ub8cc \ud0a4\uc6cc\ub4dc \ub610\ub294 \uc911\uc694\ub3c4\uac00 \ud655\uc778\ub41c \ub274\uc2a4 {len(direct)}\uac74\uc744 \ubc18\uc601\ud588\uc2b5\ub2c8\ub2e4.",
            source_table="news_items",
            source_date=latest,
        )

    def _material_disclosure_strength_factor(self, rows: list[dict[str, Any]], base_date: str) -> dict[str, Any]:
        if not rows:
            return self._material_factor(
                "MATERIAL_DISCLOSURE_STRENGTH",
                score=None,
                raw=None,
                reason="\uc218\uc9d1\ub41c \uacf5\uc2dc \ub370\uc774\ud130\uac00 \uc5c6\uc5b4 \uacf5\uc2dc \uc7ac\ub8cc \uac15\ub3c4\ub294 \ud3c9\uac00\uc5d0\uc11c \uc81c\uc678\ud588\uc2b5\ub2c8\ub2e4.",
                source_table=None,
                source_date=None,
            )
        recent30 = [row for row in rows if (days := _days_between(base_date, row.get("disclosed_at") or row.get("created_at"))) is not None and days <= 30]
        recent90 = [row for row in rows if (days := _days_between(base_date, row.get("disclosed_at") or row.get("created_at"))) is not None and days <= 90]
        important = [row for row in recent90 if _material_importance(row) >= 60 or _text_contains_any(f"{row.get('disclosure_title')} {row.get('summary')} {row.get('ai_tags')} {row.get('ai_event_type')}", MATERIAL_KEYWORDS + MATERIAL_RISK_KEYWORDS)]
        risk = [row for row in important if _text_contains_any(f"{row.get('disclosure_title')} {row.get('summary')} {row.get('ai_tags')} {row.get('ai_event_type')}", MATERIAL_RISK_KEYWORDS)]
        avg_importance = sum(_material_importance(row) for row in recent90 or rows) / max(1, len(recent90 or rows))
        if any(row in recent30 for row in important) and avg_importance >= 60:
            score = 25
        elif important:
            score = 18
        elif recent90:
            score = 10
        else:
            score = 4
        latest = max((_date_text(row.get("disclosed_at") or row.get("created_at")) for row in rows), default=None)
        risk_note = f" \ub9ac\uc2a4\ud06c \uc131\uaca9 \uacf5\uc2dc {len(risk)}\uac74\ub3c4 \ud568\uaed8 \ud655\uc778\ub429\ub2c8\ub2e4." if risk else ""
        return self._material_factor(
            "MATERIAL_DISCLOSURE_STRENGTH",
            score=float(score),
            raw=f"\ucd5c\uadfc 30\uc77c \uacf5\uc2dc {len(recent30)}\uac74, \ucd5c\uadfc 90\uc77c \uacf5\uc2dc {len(recent90)}\uac74, \uc911\uc694 \uacf5\uc2dc {len(important)}\uac74",
            reason=f"\ucd5c\uadfc \uacf5\uc2dc \uc911 \uc911\uc694\ub3c4\uc640 \uc7ac\ub8cc \ud0a4\uc6cc\ub4dc\ub97c \uae30\uc900\uc73c\ub85c \uacf5\uc2dc \uc7ac\ub8cc \uac15\ub3c4\ub97c \ud3c9\uac00\ud588\uc2b5\ub2c8\ub2e4.{risk_note}",
            source_table="disclosures",
            source_date=latest,
        )

    def _material_theme_alignment_factor(self, theme_rows: list[dict[str, Any]], theme_metrics: dict[str, Any] | None) -> dict[str, Any]:
        if not theme_rows:
            return self._material_factor(
                "MATERIAL_THEME_ALIGNMENT",
                score=0.0,
                raw="\uc5f0\uacb0 \ud14c\ub9c8 \uc5c6\uc74c",
                reason="\uc5f0\uacb0\ub41c \ud65c\uc131 \ud14c\ub9c8\uac00 \uc5c6\uc5b4 \ud14c\ub9c8 \uc5f0\uacb0\ub3c4\ub294 \ub0ae\uac8c \ud3c9\uac00\ud588\uc2b5\ub2c8\ub2e4.",
                source_table="market_theme_stocks",
                source_date=None,
            )
        ret30 = _as_float(theme_metrics.get("return_30d")) if theme_metrics else None
        ret5 = _as_float(theme_metrics.get("return_5d")) if theme_metrics else None
        primary = any(int(row.get("is_primary") or 0) == 1 for row in theme_rows)
        if ret30 is not None and ret30 > 0 and (ret5 is None or ret5 >= -2):
            score = 20 if primary else 16
        elif ret30 is not None and ret30 > -10:
            score = 15 if primary else 12
        elif ret30 is not None:
            score = 8
        else:
            score = 12 if primary else 8
        theme_names = ", ".join(str(row.get("theme_name")) for row in theme_rows[:3] if row.get("theme_name"))
        return self._material_factor(
            "MATERIAL_THEME_ALIGNMENT",
            score=float(score),
            raw=f"\uc5f0\uacb0 \ud14c\ub9c8: {theme_names or '-'}; \ub300\ud45c \ud14c\ub9c8 30\uc77c \uc218\uc775\ub960: {ret30 if ret30 is not None else '-'}%; 5\uc77c \uc218\uc775\ub960: {ret5 if ret5 is not None else '-'}%",
            reason="\uc885\ubaa9\uc5d0 \uc5f0\uacb0\ub41c \ud65c\uc131 \ud14c\ub9c8\uc640 \ub300\ud45c \ud14c\ub9c8\uc758 \ucd5c\uadfc \ud750\ub984\uc744 \uc7ac\ub8cc \uc5f0\uacb0 \uadfc\uac70\ub85c \ubc18\uc601\ud588\uc2b5\ub2c8\ub2e4.",
            source_table="market_theme_stocks, stock_daily_prices",
            source_date=theme_metrics.get("source_date") if theme_metrics else None,
        )

    def _material_recency_factor(self, material_dates: list[str], base_date: str) -> dict[str, Any]:
        if not material_dates:
            return self._material_factor(
                "MATERIAL_RECENCY",
                score=None,
                raw=None,
                reason="\ub274\uc2a4\u00b7\uacf5\uc2dc\u00b7\ud14c\ub9c8 \uae30\uc900\uc77c\uc774 \uc5c6\uc5b4 \uc7ac\ub8cc \ucd5c\uadfc\uc131\uc740 \ud3c9\uac00\uc5d0\uc11c \uc81c\uc678\ud588\uc2b5\ub2c8\ub2e4.",
                source_table=None,
                source_date=None,
            )
        latest = max(material_dates)
        days = _days_between(base_date, latest)
        if days is None:
            score = None
        elif days <= 3:
            score = 15
        elif days <= 7:
            score = 12
        elif days <= 14:
            score = 8
        elif days <= 30:
            score = 5
        else:
            score = 0
        return self._material_factor(
            "MATERIAL_RECENCY",
            score=float(score) if score is not None else None,
            raw=f"\ucd5c\uc2e0 \uc7ac\ub8cc\uc77c: {latest}, \uae30\uc900\uc77c \ub300\ube44 {days if days is not None else '-'}\uc77c",
            reason="\uac00\uc7a5 \ucd5c\uadfc \ub274\uc2a4\u00b7\uacf5\uc2dc\u00b7\ud14c\ub9c8 \uadfc\uac70\uc758 \ub0a0\uc9dc\ub97c \uae30\uc900\uc73c\ub85c \uc7ac\ub8cc \ucd5c\uadfc\uc131\uc744 \ud3c9\uac00\ud588\uc2b5\ub2c8\ub2e4.",
            source_table="news_items, disclosures, market_theme_stocks",
            source_date=latest,
        )

    def _material_continuity_factor(self, event_count_30d: int, material_dates: list[str]) -> dict[str, Any]:
        if not material_dates:
            return self._material_factor(
                "MATERIAL_CONTINUITY",
                score=None,
                raw=None,
                reason="\ucd5c\uadfc \uc7ac\ub8cc \uc774\ubca4\ud2b8\uac00 \uc5c6\uc5b4 \uc7ac\ub8cc \uc9c0\uc18d\uc131\uc740 \ud3c9\uac00\uc5d0\uc11c \uc81c\uc678\ud588\uc2b5\ub2c8\ub2e4.",
                source_table=None,
                source_date=None,
            )
        if event_count_30d >= 5:
            score = 10
        elif event_count_30d >= 3:
            score = 7
        elif event_count_30d >= 1:
            score = 4
        else:
            score = 0
        return self._material_factor(
            "MATERIAL_CONTINUITY",
            score=float(score),
            raw=f"\ucd5c\uadfc 30\uc77c \uc7ac\ub8cc \uc774\ubca4\ud2b8 {event_count_30d}\uac74",
            reason="\ucd5c\uadfc 30\uc77c \ub274\uc2a4\uc640 \uacf5\uc2dc \uc774\ubca4\ud2b8 \uc218\ub97c \uae30\uc900\uc73c\ub85c \ub2e8\ubc1c\uc131\uc778\uc9c0 \ubc18\ubcf5\uc801\uc73c\ub85c \uc774\uc5b4\uc9c0\ub294\uc9c0 \ud3c9\uac00\ud588\uc2b5\ub2c8\ub2e4.",
            source_table="news_items, disclosures",
            source_date=max(material_dates) if material_dates else None,
        )

    def _material_event_dates(self, news_rows: list[dict[str, Any]], disclosure_rows: list[dict[str, Any]], theme_metrics: dict[str, Any] | None) -> list[str]:
        dates = [_date_text(row.get("published_at") or row.get("collected_at")) for row in news_rows]
        dates += [_date_text(row.get("disclosed_at") or row.get("created_at")) for row in disclosure_rows]
        if theme_metrics and theme_metrics.get("source_date"):
            dates.append(_date_text(theme_metrics.get("source_date")))
        return sorted({date_value for date_value in dates if date_value})

    def _material_event_count_30d(self, news_rows: list[dict[str, Any]], disclosure_rows: list[dict[str, Any]], base_date: str) -> int:
        event_keys: set[str] = set()
        for row in news_rows:
            date_value = _date_text(row.get("published_at") or row.get("collected_at"))
            if date_value and (days := _days_between(base_date, date_value)) is not None and days <= 30:
                event_keys.add(f"news:{date_value}:{str(row.get('title') or '').strip()[:60]}")
        for row in disclosure_rows:
            date_value = _date_text(row.get("disclosed_at") or row.get("created_at"))
            if date_value and (days := _days_between(base_date, date_value)) is not None and days <= 30:
                event_keys.add(f"disclosure:{date_value}:{str(row.get('disclosure_title') or '').strip()[:60]}")
        return len(event_keys)

    def _material_summary(self, score: float | None, status_value: str, news_rows: list[dict[str, Any]], disclosure_rows: list[dict[str, Any]], theme_names: list[str], latest_date: str | None, missing: list[str]) -> str:
        if score is None:
            return "\ub274\uc2a4\u00b7\uacf5\uc2dc\u00b7\ud14c\ub9c8 \uc7ac\ub8cc \ub370\uc774\ud130\uac00 \ubd80\uc871\ud574 \uc7ac\ub8cc \ud3c9\uac00\ub294 \uc81c\ud55c\ub429\ub2c8\ub2e4. \uc5c6\ub294 \ub370\uc774\ud130\ub97c \uc784\uc758\ub85c \uc0dd\uc131\ud558\uc9c0 \uc54a\uc558\uc2b5\ub2c8\ub2e4."
        grade = _material_grade(score)
        parts = [f"{grade} \uad6c\uac04\uc785\ub2c8\ub2e4."]
        if latest_date:
            parts.append(f"\ucd5c\uc2e0 \uc7ac\ub8cc\uc77c\uc740 {latest_date}\uc785\ub2c8\ub2e4.")
        parts.append(f"\ub274\uc2a4 {len(news_rows)}\uac74, \uacf5\uc2dc {len(disclosure_rows)}\uac74\uc744 \ud655\uc778\ud588\uc2b5\ub2c8\ub2e4.")
        if theme_names:
            parts.append(f"\uc5f0\uacb0 \ud14c\ub9c8\ub294 {', '.join(theme_names[:3])}\uc785\ub2c8\ub2e4.")
        if status_value != "EVALUATED" and missing:
            parts.append(f"\ub2e4\ub9cc {', '.join(missing)} \ub370\uc774\ud130\uac00 \ubd80\uc871\ud574 \uc77c\ubd80 \ud310\ub2e8\uc740 \uc81c\ud55c\ub429\ub2c8\ub2e4.")
        return " ".join(parts)

    def _material_news_items(self, rows: list[dict[str, Any]]) -> list[MaterialNewsItem]:
        return [
            MaterialNewsItem(
                id=int(row["id"]),
                title=str(row.get("title") or "-"),
                published_at=row.get("published_at"),
                importance_score=_material_importance(row),
                summary=row.get("ai_summary") or row.get("summary"),
                source=row.get("source"),
                sentiment=row.get("ai_sentiment") or row.get("sentiment"),
            )
            for row in rows[:5]
        ]

    def _material_disclosure_items(self, rows: list[dict[str, Any]]) -> list[MaterialDisclosureItem]:
        return [
            MaterialDisclosureItem(
                id=int(row["id"]),
                title=str(row.get("disclosure_title") or "-"),
                disclosed_at=row.get("disclosed_at"),
                importance_score=_material_importance(row),
                summary=row.get("ai_summary") or row.get("summary"),
                disclosure_type=row.get("disclosure_type") or row.get("ai_event_type"),
                risk_level=row.get("ai_risk_level"),
            )
            for row in rows[:5]
        ]

    def _material_theme_items(self, rows: list[dict[str, Any]], theme_metrics: dict[str, Any] | None) -> list[MaterialThemeItem]:
        items: list[MaterialThemeItem] = []
        for row in rows[:5]:
            is_representative = theme_metrics and int(row.get("theme_id") or 0) == int(theme_metrics.get("theme_id") or 0)
            items.append(
                MaterialThemeItem(
                    theme_id=int(row["theme_id"]) if row.get("theme_id") is not None else None,
                    theme_name=str(row.get("theme_name") or "-"),
                    is_primary=int(row.get("is_primary") or 0) == 1,
                    return_30d=_as_float(theme_metrics.get("return_30d")) if is_representative else None,
                    return_5d=_as_float(theme_metrics.get("return_5d")) if is_representative else None,
                    source_date=theme_metrics.get("source_date") if is_representative else None,
                )
            )
        return items

    def _evaluate_supply_for_watchlist_stock(self, stock_id: int) -> dict[str, Any]:
        price_rows = self.repo.list_stock_daily_price_rows(stock_id, limit=80)
        theme_metrics = self._representative_theme_metrics(stock_id)
        investor_summary = self._investor_flow_summary(stock_id)
        investor_factor = self._supply_investor_flow_factor(investor_summary)
        investor_flow_subject_count = self._investor_flow_subject_count(investor_summary)
        has_investor_flow = investor_flow_subject_count > 0
        model_version = "V2" if investor_flow_subject_count >= 2 else "V2_PARTIAL" if investor_flow_subject_count == 1 else "V1_NO_INVESTOR_FLOW"
        weights = {
            "SUPPLY_TRADING_VALUE_INTENSITY": 25.0,
            "SUPPLY_CONTINUITY": 20.0,
            "SUPPLY_THEME_ALIGNMENT": 20.0,
            "SUPPLY_THEME_RELATIVE_POSITION": 15.0,
        } if has_investor_flow else {}
        factors = [
            self._supply_trading_value_intensity_factor(price_rows, weight=weights.get("SUPPLY_TRADING_VALUE_INTENSITY")),
            self._supply_continuity_factor(price_rows, weight=weights.get("SUPPLY_CONTINUITY")),
            self._supply_theme_alignment_factor(theme_metrics, weight=weights.get("SUPPLY_THEME_ALIGNMENT")),
            self._supply_theme_relative_position_factor(theme_metrics, weight=weights.get("SUPPLY_THEME_RELATIVE_POSITION")),
        ]
        if has_investor_flow:
            factors.append(investor_factor)
        else:
            factors.append(investor_factor)
        available_factors = [factor for factor in factors if factor.get("contribution_score") is not None and factor.get("weight")]
        available_weight = sum(float(factor["weight"]) for factor in available_factors)
        contribution_sum = sum(float(factor["contribution_score"]) for factor in available_factors)
        score_value = round(contribution_sum / available_weight * 100, 2) if available_weight > 0 else None
        missing_codes = [factor["factor_code"] for factor in factors if factor.get("contribution_score") is None]
        missing_labels = [SUPPLY_MISSING_LABELS.get(code, code) for code in missing_codes]
        status_value = _supply_status_by_available_count(len(available_factors))
        summary = self._supply_summary_v2(score_value, status_value, missing_labels, theme_metrics.get("theme_name") if theme_metrics else None, investor_summary, model_version)
        return {
            "score": score_value,
            "status": status_value,
            "confidence": _supply_confidence_by_available_count(len(available_factors)),
            "summary": summary,
            "missing_codes": missing_codes,
            "factors": factors,
            "representative_theme_name": theme_metrics.get("theme_name") if theme_metrics else None,
            "representative_theme_return_30d": theme_metrics.get("return_30d") if theme_metrics else None,
            "investor_flow_status": self._investor_flow_status_from_summary(investor_summary),
            "investor_flow_summary": investor_summary,
            "model_version": model_version,
        }

    def _supply_factor(self, code: str, *, score: float | None, raw: str | None, reason: str, source_table: str | None, source_date: str | None, weight: float | None = None) -> dict[str, Any]:
        name, base_weight = SUPPLY_FACTOR_META[code]
        resolved_weight = base_weight if weight is None else float(weight)
        normalized = None if score is None else max(0.0, min(resolved_weight, round(score, 2)))
        return {
            "category": "SUPPLY",
            "factor_code": code,
            "factor_name": name,
            "raw_value": raw,
            "normalized_score": normalized,
            "weight": resolved_weight,
            "contribution_score": normalized,
            "reason": reason,
            "source_table": source_table,
            "source_date": source_date,
        }

    def _supply_trading_value_intensity_factor(self, rows: list[dict[str, Any]], weight: float | None = None) -> dict[str, Any]:
        latest, previous_values, source_date = self._latest_and_previous_trading_values(rows)
        if latest is None or not previous_values:
            return self._supply_factor(
                "SUPPLY_TRADING_VALUE_INTENSITY",
                score=None,
                raw=None,
                reason="최근 거래대금 또는 20일 평균 거래대금 데이터가 없어 거래대금 강도를 반영하지 않았습니다.",
                source_table=None,
                source_date=None,
                weight=weight,
            )
        avg20 = sum(previous_values) / len(previous_values)
        ratio = latest / avg20 if avg20 > 0 else None
        if ratio is None:
            score = None
        elif ratio >= 3.0:
            score = 30
        elif ratio >= 2.0:
            score = 25
        elif ratio >= 1.5:
            score = 20
        elif ratio >= 1.2:
            score = 16
        elif ratio >= 1.0:
            score = 12
        elif ratio >= 0.7:
            score = 8
        else:
            score = 4
        raw = f"최근 거래대금 20일 평균 대비 {ratio * 100:.1f}%" if ratio is not None else None
        return self._supply_factor(
            "SUPPLY_TRADING_VALUE_INTENSITY",
            score=float(score) if score is not None else None,
            raw=raw,
            reason="최신 거래대금이 직전 20일 평균 대비 얼마나 강한지 반영했습니다.",
            source_table="stock_daily_prices",
            source_date=source_date,
            weight=weight,
        )

    def _supply_continuity_factor(self, rows: list[dict[str, Any]], weight: float | None = None) -> dict[str, Any]:
        latest, previous_values, source_date = self._latest_and_previous_trading_values(rows)
        last5 = rows[-5:] if len(rows) >= 5 else []
        if latest is None or not previous_values or len(last5) < 5:
            return self._supply_factor(
                "SUPPLY_CONTINUITY",
                score=None,
                raw=None,
                reason="최근 5일 거래대금 또는 20일 평균 거래대금 데이터가 부족해 수급 연속성을 반영하지 않았습니다.",
                source_table=None,
                source_date=None,
                weight=weight,
            )
        avg20 = sum(previous_values) / len(previous_values)
        count = sum(1 for row in last5 if (_as_float(row.get("trading_value")) or 0) >= avg20)
        score = {5: 25, 4: 21, 3: 17, 2: 12, 1: 7, 0: 3}.get(count, 3)
        up_closes = sum(1 for row in last5 if (_as_float(row.get("change_rate")) or 0) > 0)
        down_closes = sum(1 for row in last5 if (_as_float(row.get("change_rate")) or 0) < 0)
        if up_closes >= 3:
            score += 2
        if down_closes >= 3:
            score -= 2
        score = max(0, min(25, score))
        raw = f"최근 5일 중 {count}일이 20일 평균 거래대금 이상, 상승일 {up_closes}일, 하락일 {down_closes}일"
        return self._supply_factor(
            "SUPPLY_CONTINUITY",
            score=float(score),
            raw=raw,
            reason="최근 5거래일 거래대금이 20일 평균 이상 유지된 일수와 상승/하락 마감 보정을 반영했습니다.",
            source_table="stock_daily_prices",
            source_date=source_date,
            weight=weight,
        )

    @staticmethod
    def _latest_and_previous_trading_values(rows: list[dict[str, Any]]) -> tuple[float | None, list[float], str | None]:
        if len(rows) < 2:
            return None, [], None
        latest = _as_float(rows[-1].get("trading_value"))
        previous = [_as_float(row.get("trading_value")) for row in rows[-21:-1]]
        previous_values = [value for value in previous if value is not None and value > 0]
        return latest, previous_values, str(rows[-1].get("trade_date")) if rows[-1].get("trade_date") else None

    def _representative_theme_metrics(self, stock_id: int) -> dict[str, Any] | None:
        themes = self.repo.list_stock_themes(stock_id)
        candidates: list[dict[str, Any]] = []
        for theme in themes:
            stocks = self.repo.list_theme_stocks(int(theme["theme_id"]))
            stock_metrics: list[dict[str, Any]] = []
            for theme_stock in stocks:
                rows = self.repo.list_stock_daily_price_rows(int(theme_stock["stock_id"]), limit=40)
                if not rows:
                    continue
                latest = rows[-1]
                stock_metrics.append(
                    {
                        "stock_id": int(theme_stock["stock_id"]),
                        "return_30d": _recent_return(rows, 30),
                        "return_5d": _recent_return(rows, 5),
                        "change_rate": _as_float(latest.get("change_rate")),
                        "trading_value": _as_float(latest.get("trading_value")),
                        "source_date": latest.get("trade_date"),
                    }
                )
            returns_30d = [item["return_30d"] for item in stock_metrics if item.get("return_30d") is not None]
            if not returns_30d:
                continue
            returns_5d = [item["return_5d"] for item in stock_metrics if item.get("return_5d") is not None]
            change_values = [item["change_rate"] for item in stock_metrics if item.get("change_rate") is not None]
            current = next((item for item in stock_metrics if item["stock_id"] == stock_id), None)
            candidates.append(
                {
                    "theme_id": int(theme["theme_id"]),
                    "theme_name": str(theme.get("theme_name") or "-"),
                    "return_30d": sum(returns_30d) / len(returns_30d),
                    "return_5d": sum(returns_5d) / len(returns_5d) if returns_5d else None,
                    "breadth": (sum(1 for value in change_values if value > 0) / len(change_values)) if change_values else None,
                    "current": current,
                    "stock_metrics": stock_metrics,
                    "source_date": max([str(item["source_date"]) for item in stock_metrics if item.get("source_date")] or [None]),
                }
            )
        if not candidates:
            return None
        representative = max(candidates, key=lambda item: (item["return_30d"], 1 if item.get("current") else 0))
        current = representative.get("current")
        metrics = representative["stock_metrics"]
        tv_rank, tv_count = self._rank_desc(current.get("trading_value") if current else None, [item.get("trading_value") for item in metrics])
        change_rank, change_count = self._rank_desc(current.get("change_rate") if current else None, [item.get("change_rate") for item in metrics])
        representative.update({"trading_value_rank": tv_rank, "trading_value_count": tv_count, "change_rate_rank": change_rank, "change_rate_count": change_count})
        return representative

    @staticmethod
    def _rank_desc(value: float | None, values: list[float | None]) -> tuple[int | None, int]:
        valid = [item for item in values if item is not None]
        if value is None or not valid:
            return None, len(valid)
        sorted_values = sorted(valid, reverse=True)
        return sorted_values.index(value) + 1, len(sorted_values)

    def _supply_theme_alignment_factor(self, theme: dict[str, Any] | None, weight: float | None = None) -> dict[str, Any]:
        if not theme or theme.get("return_30d") is None:
            return self._supply_factor(
                "SUPPLY_THEME_ALIGNMENT",
                score=None,
                raw=None,
                reason="연결된 대표 테마의 30일 수익률 데이터가 없어 테마 동조를 반영하지 않았습니다.",
                source_table=None,
                source_date=None,
                weight=weight,
            )
        ret30 = float(theme["return_30d"])
        score = 25 if ret30 >= 20 else 21 if ret30 >= 10 else 17 if ret30 >= 5 else 12 if ret30 >= 0 else 8 if ret30 >= -5 else 4
        bonus_parts: list[str] = []
        breadth = theme.get("breadth")
        ret5 = theme.get("return_5d")
        if breadth is not None and breadth >= 0.6:
            score += 2
            bonus_parts.append("상승 종목 비율 보너스")
        if ret5 is not None and ret5 > 0:
            score += 2
            bonus_parts.append("5일 테마 흐름 보너스")
        score = min(25, score)
        raw = f"대표 테마: {theme['theme_name']}; 30일 수익률: {ret30:+.2f}%"
        if ret5 is not None:
            raw += f"; 5일 수익률: {ret5:+.2f}%"
        if breadth is not None:
            raw += f"; 상승 비율: {breadth * 100:.1f}%"
        if bonus_parts:
            raw += f"; {', '.join(bonus_parts)}"
        return self._supply_factor(
            "SUPPLY_THEME_ALIGNMENT",
            score=float(score),
            raw=raw,
            reason="종목이 속한 테마 중 30일 수익률이 가장 강한 대표 테마를 골라 흐름 동조 여부를 반영했습니다.",
            source_table="market_theme_stocks, stock_daily_prices",
            source_date=theme.get("source_date"),
            weight=weight,
        )

    def _supply_theme_relative_position_factor(self, theme: dict[str, Any] | None, weight: float | None = None) -> dict[str, Any]:
        if not theme:
            return self._supply_factor(
                "SUPPLY_THEME_RELATIVE_POSITION",
                score=None,
                raw=None,
                reason="연결된 테마 구성종목 데이터가 없어 테마 내 상대 위치를 반영하지 않았습니다.",
                source_table=None,
                source_date=None,
                weight=weight,
            )
        parts: list[float] = []
        raw_parts: list[str] = []
        tv_rank, tv_count = theme.get("trading_value_rank"), theme.get("trading_value_count")
        change_rank, change_count = theme.get("change_rate_rank"), theme.get("change_rate_count")
        if tv_rank and tv_count:
            parts.append(self._rank_points(int(tv_rank), int(tv_count)))
            raw_parts.append(f"거래대금 {tv_rank}/{tv_count}위")
        if change_rank and change_count:
            parts.append(self._rank_points(int(change_rank), int(change_count)))
            raw_parts.append(f"등락률 {change_rank}/{change_count}위")
        if not parts:
            return self._supply_factor(
                "SUPPLY_THEME_RELATIVE_POSITION",
                score=None,
                raw=None,
                reason="테마 내 거래대금 또는 등락률 순위 데이터가 부족해 상대 위치를 반영하지 않았습니다.",
                source_table=None,
                source_date=None,
                weight=weight,
            )
        score = sum(parts) / (10 * len(parts)) * 20
        raw = f"대표 테마: {theme['theme_name']}; " + ", ".join(raw_parts)
        return self._supply_factor(
            "SUPPLY_THEME_RELATIVE_POSITION",
            score=score,
            raw=raw,
            reason="대표 테마 구성종목 안에서 해당 종목의 거래대금 순위와 등락률 순위를 20점 만점으로 환산했습니다.",
            source_table="market_theme_stocks, stock_daily_prices",
            source_date=theme.get("source_date"),
            weight=weight,
        )

    @staticmethod
    def _rank_points(rank: int, count: int) -> float:
        if count <= 0:
            return 0.0
        ratio = rank / count
        if ratio <= 0.1:
            return 10.0
        if ratio <= 0.3:
            return 8.0
        if ratio <= 0.5:
            return 6.0
        if ratio <= 0.7:
            return 4.0
        return 2.0

    def _investor_flow_summary(self, stock_id: int) -> dict[str, Any]:
        rows = self.investor_flow_repo.list_by_stock(stock_id, limit=20, real_only=True, exclude_source_methods=["kiwoom_rest_ka10005"])
        selected_source_type = "KIWOOM_REAL" if rows else None
        last5 = rows[-5:]
        empty = {
            "latest_date": None,
            "foreign_5d_net_qty": None,
            "institution_5d_net_qty": None,
            "program_5d_net_qty": None,
            "foreign_streak": 0,
            "institution_streak": 0,
            "program_streak": 0,
            "selected_source_type": selected_source_type,
            "is_real_investor_flow": selected_source_type == "KIWOOM_REAL",
            "source_methods": [],
        }
        if not rows:
            return empty

        def to_int(value: Any) -> int | None:
            if value is None:
                return None
            try:
                return int(float(value))
            except (TypeError, ValueError):
                return None

        def streak(key: str) -> int:
            values = [to_int(row.get(key)) for row in rows]
            values = [value for value in values if value is not None]
            if not values:
                return 0
            sign = 1 if values[-1] > 0 else -1 if values[-1] < 0 else 0
            if sign == 0:
                return 0
            count = 0
            for value in reversed(values):
                if (value > 0 and sign > 0) or (value < 0 and sign < 0):
                    count += 1
                else:
                    break
            return count * sign

        def sum5(key: str) -> int | None:
            values = [to_int(row.get(key)) for row in last5]
            values = [value for value in values if value is not None]
            return sum(values) if values else None

        return {
            "latest_date": str(rows[-1].get("flow_date")) if rows[-1].get("flow_date") else None,
            "foreign_5d_net_qty": sum5("foreign_net_qty"),
            "institution_5d_net_qty": sum5("institution_net_qty"),
            "program_5d_net_qty": sum5("program_net_qty"),
            "foreign_streak": streak("foreign_net_qty"),
            "institution_streak": streak("institution_net_qty"),
            "program_streak": streak("program_net_qty"),
            "selected_source_type": selected_source_type,
            "is_real_investor_flow": selected_source_type == "KIWOOM_REAL",
            "source_methods": self._investor_flow_source_methods(rows),
        }

    @staticmethod
    def _investor_flow_source_methods(rows: list[dict[str, Any]]) -> list[str]:
        source_methods = sorted({str(row.get("source_method")) for row in rows if row.get("source_method")})
        if any(row.get("source_method") == "kiwoom_rest_multi_investor_flow" for row in rows):
            source_methods = ["kiwoom_rest_ka10059", "kiwoom_rest_ka90013"]
        if any(row.get("foreign_holding_qty") is not None or row.get("foreign_holding_ratio") is not None for row in rows):
            if "kiwoom_rest_ka10008" not in source_methods:
                source_methods.append("kiwoom_rest_ka10008")
        return source_methods

    @staticmethod
    def _investor_flow_complete(summary: dict[str, Any]) -> bool:
        return all(summary.get(key) is not None for key in ("foreign_5d_net_qty", "institution_5d_net_qty", "program_5d_net_qty"))

    @staticmethod
    def _investor_flow_subject_count(summary: dict[str, Any]) -> int:
        if not summary.get("is_real_investor_flow"):
            return 0
        return sum(1 for key in ("foreign_5d_net_qty", "institution_5d_net_qty", "program_5d_net_qty") if summary.get(key) is not None)

    @staticmethod
    def _investor_flow_status_from_summary(summary: dict[str, Any] | None) -> dict[str, str]:
        summary = summary or {}
        collected_label = "COLLECTED" if summary.get("is_real_investor_flow") else "NOT_COLLECTED"
        return {
            "foreign": collected_label if summary.get("foreign_5d_net_qty") is not None else "NOT_COLLECTED",
            "institution": collected_label if summary.get("institution_5d_net_qty") is not None else "NOT_COLLECTED",
            "program": collected_label if summary.get("program_5d_net_qty") is not None else "NOT_COLLECTED",
            "credit": "2\uCC28 \uC608\uC815",
            "short": "2\uCC28 \uC608\uC815",
            "loan": "2\uCC28 \uC608\uC815",
        }

    def _supply_investor_flow_factor(self, summary: dict[str, Any]) -> dict[str, Any]:
        parts: list[tuple[str, float, int, int]] = []
        for key, label, max_point in (("foreign", "외국인", 7), ("institution", "기관", 7), ("program", "프로그램", 6)):
            net = summary.get(f"{key}_5d_net_qty")
            streak = int(summary.get(f"{key}_streak") or 0)
            if net is None:
                continue
            net_value = int(net)
            if net_value > 0 and streak >= 2:
                point = float(max_point)
            elif net_value > 0:
                point = 5.0 if max_point == 7 else 4.0
            elif net_value < 0:
                point = 1.0
            else:
                point = 3.0
            parts.append((label, point, net_value, streak))
        if not parts:
            return self._supply_factor(
                "SUPPLY_INVESTOR_FLOW",
                score=None,
                raw=None,
                reason="외국인·기관·프로그램 순매매 데이터가 아직 수집되지 않았습니다.",
                source_table=None,
                source_date=None,
            )
        score = sum(point for _, point, _, _ in parts)
        raw = ", ".join(f"{label} 5일 누적 {net:+,}주, 연속 {streak:+d}일" for label, _, net, streak in parts)
        positives = [label for label, _, net, _ in parts if net > 0]
        negatives = [label for label, _, net, _ in parts if net < 0]
        reason_parts = []
        if positives:
            reason_parts.append(f"{', '.join(positives)}은 최근 5일 누적 순매수입니다")
        if negatives:
            reason_parts.append(f"{', '.join(negatives)}은 최근 5일 누적 순매도입니다")
        return self._supply_factor(
            "SUPPLY_INVESTOR_FLOW",
            score=score,
            raw=raw,
            reason=". ".join(reason_parts) or "투자주체별 수급이 혼조입니다.",
            source_table="stock_investor_flows",
            source_date=summary.get("latest_date"),
            weight=20.0,
        )

    def _supply_summary_v2(self, score: float | None, status_value: str, missing: list[str], theme_name: str | None, investor_summary: dict[str, Any], model_version: str) -> str:
        base = _supply_summary(score, status_value, missing, theme_name)
        if model_version in {"V1", "V1_NO_INVESTOR_FLOW"}:
            return f"{base} 투자주체별 수급 데이터는 아직 수집되지 않아 V1 산식을 유지했습니다."
        parts = []
        for key, label in (("foreign", "외국인"), ("institution", "기관"), ("program", "프로그램")):
            net = investor_summary.get(f"{key}_5d_net_qty")
            if net is None:
                parts.append(f"{label} 미수집")
            elif net > 0:
                parts.append(f"{label} 5일 누적 순매수")
            elif net < 0:
                parts.append(f"{label} 5일 누적 순매도")
            else:
                parts.append(f"{label} 혼조")
        return f"{base} 투자주체별 수급은 {model_version} 산식으로 반영했습니다. {'; '.join(parts)}."
    @staticmethod
    def _representative_theme_from_factors(factors: list[WatchlistEvaluationFactorResponse]) -> tuple[str | None, float | None]:
        factor = next((item for item in factors if item.factor_code == "SUPPLY_THEME_ALIGNMENT" and item.raw_value), None)
        if not factor or not factor.raw_value:
            return None, None
        theme_name: str | None = None
        ret30: float | None = None
        for part in factor.raw_value.split(";"):
            text_value = part.strip()
            if text_value.startswith("대표 테마:"):
                theme_name = text_value.replace("대표 테마:", "", 1).strip() or None
            if text_value.startswith("30일 수익률:"):
                number = text_value.replace("30일 수익률:", "", 1).replace("%", "").strip()
                ret30 = _as_float(number)
        return theme_name, ret30

    @staticmethod
    def _missing_supply_data_from_factors(factors: list[WatchlistEvaluationFactorResponse]) -> list[str]:
        return [factor.factor_name for factor in factors if factor.contribution_score is None]
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
                material_status=score.material_status,
                material_grade=_material_grade(score.material_score),
                material_summary=self._evaluate_material_for_watchlist_stock(score.stock_id, score.evaluated_at[:10])["summary"],
                material_factors=self._factor_responses(self.repo.list_factors(score.id), category="MATERIAL"),
                missing_material_data=self._missing_material_data_from_factors(self._factor_responses(self.repo.list_factors(score.id), category="MATERIAL")),
                latest_material_date=self._evaluate_material_for_watchlist_stock(score.stock_id, score.evaluated_at[:10])["latest_material_date"],
                material_news_count=self._evaluate_material_for_watchlist_stock(score.stock_id, score.evaluated_at[:10])["material_news_count"],
                material_disclosure_count=self._evaluate_material_for_watchlist_stock(score.stock_id, score.evaluated_at[:10])["material_disclosure_count"],
                material_theme_names=self._evaluate_material_for_watchlist_stock(score.stock_id, score.evaluated_at[:10])["material_theme_names"],
                supply_score=score.supply_score,
                supply_status=score.supply_status,
                supply_grade=_supply_grade(score.supply_score),
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
        material_factors = [factor for factor in factors if factor.category == "MATERIAL"]
        supply_factors = [factor for factor in factors if factor.category == "SUPPLY"]
        material_context = self._evaluate_material_for_watchlist_stock(score.stock_id, score.evaluated_at[:10])
        representative_theme_name, representative_theme_return_30d = self._representative_theme_from_factors(supply_factors)
        missing_supply_data = self._missing_supply_data_from_factors(supply_factors)
        investor_flow_summary = self._investor_flow_summary(score.stock_id)
        investor_flow_subject_count = self._investor_flow_subject_count(investor_flow_summary)
        supply_model_version = "V2" if investor_flow_subject_count >= 2 else "V2_PARTIAL" if investor_flow_subject_count == 1 else "V1_NO_INVESTOR_FLOW"
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
            material_status=score.material_status,
            material_grade=_material_grade(score.material_score),
            material_summary=material_context["summary"],
            material_factors=material_factors,
            missing_material_data=self._missing_material_data_from_factors(material_factors),
            latest_material_date=material_context["latest_material_date"],
            material_news_count=material_context["material_news_count"],
            material_disclosure_count=material_context["material_disclosure_count"],
            material_theme_names=material_context["material_theme_names"],
            material_recent_news=material_context["recent_news"],
            material_recent_disclosures=material_context["recent_disclosures"],
            material_themes=material_context["themes"],
            supply_score=score.supply_score,
            supply_grade=_supply_grade(score.supply_score),
            supply_summary=self._supply_summary_v2(score.supply_score, score.supply_status, missing_supply_data, representative_theme_name, investor_flow_summary, supply_model_version),
            supply_factors=supply_factors,
            missing_supply_data=missing_supply_data,
            representative_theme_name=representative_theme_name,
            representative_theme_return_30d=representative_theme_return_30d,
            supply_investor_flow_status=self._investor_flow_status_from_summary(investor_flow_summary),
            supply_model_version=supply_model_version,
            investor_flow_summary=investor_flow_summary,
            chart_score=score.chart_score,
            financial_score=score.financial_score,
            total_score=score.total_score,
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
    def _missing_material_data_from_factors(factors: list[WatchlistEvaluationFactorResponse]) -> list[str]:
        return [factor.factor_name for factor in factors if factor.contribution_score is None]

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
        latest_score = latest[2] if latest and latest[2] else None
        missing = _json_list(latest_score.missing_data_json) if latest_score else []
        material_context = self._evaluate_material_for_watchlist_stock(item.stock_id, latest_score.evaluated_at[:10] if latest_score else now_kst()[:10])
        prompt = "\n".join(
            [
                f"DrCT 관심종목 시재수차재 평가 검토 요청: {stock.stock_name}({stock.stock_code})",
                f"- 시장: {stock.market or '-'}",
                f"- 관심 사유: {item.interest_reason or '-'}",
                f"- 관심종목 활성 여부: {'활성' if item.is_active == 1 else '비활성'}",
                f"- 시장 점수: {latest_score.market_score if latest_score else '미평가'}",
                f"- 시장 상태: {latest_score.market_status if latest_score else '미평가'}",
                f"- 재료 점수: {latest_score.material_score if latest_score else '미평가'}",
                f"- 재료 상태: {latest_score.material_status if latest_score else '미평가'}",
                f"- 재료 요약: {material_context['summary']}",
                f"- 최근 뉴스: {material_context['material_news_count']}건",
                f"- 최근 공시: {material_context['material_disclosure_count']}건",
                f"- 연결 테마: {', '.join(material_context['material_theme_names']) if material_context['material_theme_names'] else '-'}",
                f"- 미수집/미반영 데이터: {', '.join(missing) if missing else '없음'}",
                "",
                "시장, 재료, 수급, 차트, 재무 관점에서 현재 사용할 수 있는 근거와 부족한 근거를 구분해 주세요.",
                "매수/매도 추천은 하지 말고, 재료의 강도·지속성·리스크 여부와 추가 확인 항목만 정리해 주세요.",
            ]
        )
        return WatchlistGptPromptResponse(watchlist_id=watchlist_id, prompt=prompt)
