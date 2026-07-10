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
from backend.app.repositories.stock_financial_repository import StockFinancialRepository
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



FINANCIAL_MODEL_VERSION = "FINANCIAL_V1"
FINANCIAL_FACTOR_META = {
    "FINANCIAL_GROWTH": ("성장성", 25.0),
    "FINANCIAL_PROFITABILITY": ("수익성", 20.0),
    "FINANCIAL_STABILITY": ("안정성", 20.0),
    "FINANCIAL_VALUATION": ("밸류에이션 부담", 20.0),
    "FINANCIAL_SHAREHOLDER_STABILITY": ("주주·지분 안정성", 15.0),
}

CHART_MODEL_VERSION = "CHART_V1"
CHART_FACTOR_META = {
    "CHART_MA60_TREND": ("60일선 추세", 25.0),
    "CHART_MA20_PULLBACK": ("20일선 눌림/근접도", 25.0),
    "CHART_OVERHEAT_DISTANCE": ("과열 이격 위험", 20.0),
    "CHART_RECENT_5D_RISK": ("최근 5일 상승률 위험", 15.0),
    "CHART_TRADING_VALUE_SUPPORT": ("거래대금 동반 여부", 15.0),
}

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


def _financial_grade(score: float | None) -> str:
    if score is None: return "미평가"
    if score >= 80: return "재무 우호"
    if score >= 65: return "재무 양호"
    if score >= 50: return "재무 보통"
    if score >= 35: return "재무 경계"
    return "재무 부담"


def _financial_status(count: int) -> str:
    return "EVALUATED" if count >= 4 else "PARTIAL" if count >= 2 else "DATA_MISSING"


def _financial_confidence(count: int) -> str:
    return "ENOUGH" if count >= 4 else "PARTIAL" if count >= 2 else "LIMITED"

def _chart_grade(score: float | None) -> str:
    if score is None:
        return "미평가"
    if score >= 80:
        return "차트 양호"
    if score >= 65:
        return "차트 적정"
    if score >= 50:
        return "차트 보통"
    if score >= 35:
        return "차트 경계"
    return "차트 부담"


def _chart_status_by_available_count(count: int) -> str:
    if count >= 4:
        return "EVALUATED"
    if count >= 2:
        return "PARTIAL"
    return "DATA_MISSING"


def _chart_confidence_by_available_count(count: int) -> str:
    if count >= 4:
        return "ENOUGH"
    if count >= 2:
        return "PARTIAL"
    return "LIMITED"


def _chart_summary(score: float | None, status_value: str, metrics: dict[str, Any], missing: list[str]) -> str:
    if score is None:
        return "가격 또는 이동평균 데이터가 부족해 차트 평가를 표시할 수 없습니다."
    ma20_distance = _as_float(metrics.get("close_vs_ma20_pct"))
    ma60_slope = _as_float(metrics.get("ma60_slope_5d"))
    recent_return = _as_float(metrics.get("recent_5d_return"))
    parts: list[str] = []
    parts.append("60일선 추세가 상승 중입니다" if ma60_slope is not None and ma60_slope > 0 else "60일선 추세의 힘이 약합니다")
    if ma20_distance is not None:
        if -3 <= ma20_distance <= 5:
            parts.append("현재가는 20일선 근처의 눌림 관찰 구간입니다")
        elif ma20_distance >= 12:
            parts.append("20일선 이격이 커 추격 판단에 주의가 필요합니다")
        elif ma20_distance < -8:
            parts.append("20일선 아래로 이탈해 추세 훼손 여부를 확인해야 합니다")
    if recent_return is not None and recent_return >= 15:
        parts.append("최근 5일 급등 부담이 있습니다")
    summary = ". ".join(parts) + "."
    if status_value == "PARTIAL" and missing:
        summary += f" 다만 {', '.join(missing)} 데이터가 없어 일부 판단은 제한됩니다."
    return summary


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
        self.financial_repo = StockFinancialRepository(db)

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
            chart_factors = self._factor_responses(all_latest_factors, category="CHART")
            financial_factors = self._factor_responses(all_latest_factors, category="FINANCIAL")
            missing_market_data = self._missing_market_data_from_factors(market_factors)
            missing_material_data = self._missing_material_data_from_factors(material_factors)
            missing_supply_data = self._missing_supply_data_from_factors(supply_factors)
            missing_chart_data = self._missing_chart_data_from_factors(chart_factors)
            chart_context = self._evaluate_chart_for_watchlist_stock(stock.id)
            financial_context = self._evaluate_financial_for_watchlist_stock(stock.id)
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
                    chart_status=score.chart_status if score else "NOT_EVALUATED",
                    chart_grade=_chart_grade(score.chart_score if score else None),
                    chart_summary=chart_context["summary"] if score else "차트 평가 전입니다.",
                    chart_factors=chart_factors,
                    missing_chart_data=missing_chart_data,
                    chart_model_version=CHART_MODEL_VERSION,
                    chart_metrics=chart_context["metrics"],
                    financial_score=score.financial_score if score else None,
                    financial_status=score.financial_status if score else "NOT_EVALUATED",
                    financial_grade=_financial_grade(score.financial_score if score else None),
                    financial_summary=financial_context["summary"] if score else "재무 평가 전입니다.",
                    financial_factors=financial_factors,
                    missing_financial_data=[x.factor_name for x in financial_factors if x.contribution_score is None],
                    financial_model_version=FINANCIAL_MODEL_VERSION,
                    financial_snapshot=financial_context["snapshot"],
                    financial_annual_statements=financial_context["annual"],
                    financial_quarterly_statements=financial_context["quarterly"],
                    shareholder_snapshot=financial_context["shareholder"],
                    financial_data_sources=financial_context["data_sources"],
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
            chart_result = self._evaluate_chart_for_watchlist_stock(item.stock_id)
            financial_result = self._evaluate_financial_for_watchlist_stock(item.stock_id)
            missing_data = [f"market:{code}" for code in market_result["missing_codes"]]
            missing_data += [f"material:{code}" for code in material_result["missing_codes"]]
            missing_data += [f"supply:{code}" for code in supply_result["missing_codes"]]
            missing_data += [f"chart:{code}" for code in chart_result["missing_codes"]]
            missing_data += [f"financial:{code}" for code in financial_result["missing_codes"]]
            if material_result["status"] == "DATA_MISSING":
                missing_data.append("material")
            if supply_result["status"] == "DATA_MISSING":
                missing_data.append("supply")
            if chart_result["status"] == "DATA_MISSING":
                missing_data.append("chart")
            if financial_result["status"] == "DATA_MISSING":
                missing_data.append("financial")
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
                    chart_score=chart_result["score"],
                    financial_score=financial_result["score"],
                    total_score=None,
                    market_status=market_result["status"],
                    material_status=material_result["status"],
                    supply_status=supply_result["status"],
                    chart_status=chart_result["status"],
                    financial_status=financial_result["status"],
                    overall_status="미평가",
                    data_confidence=_combine_confidence(market_result["confidence"], material_result["confidence"], supply_result["confidence"], chart_result["confidence"], financial_result["confidence"]),
                    risk_flags_json="[]",
                    missing_data_json=json.dumps(missing_data, ensure_ascii=False),
                    summary_text=market_result["summary"],
                    created_at=now,
                    updated_at=now,
                )
            )
            for factor in [*market_result["factors"], *material_result["factors"], *supply_result["factors"], *chart_result["factors"], *financial_result["factors"]]:
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
        ret30_text = f"{ret30:.1f}" if ret30 is not None else "-"
        ret5_text = f"{ret5:.1f}" if ret5 is not None else "-"
        return self._material_factor(
            "MATERIAL_THEME_ALIGNMENT",
            score=float(score),
            raw=f"\uc5f0\uacb0 \ud14c\ub9c8: {theme_names or '-'}; \ub300\ud45c \ud14c\ub9c8 30\uc77c \uc218\uc775\ub960: {ret30_text}%; 5\uc77c \uc218\uc775\ub960: {ret5_text}%",
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

    def _evaluate_financial_for_watchlist_stock(self, stock_id: int) -> dict[str, Any]:
        snapshot=dict(self.financial_repo.latest_snapshot(stock_id) or {})
        annual=self.financial_repo.list_statements(stock_id, "ANNUAL", 5)
        quarterly=self.financial_repo.list_statements(stock_id, "QUARTERLY", 8)
        self._enrich_financial_snapshot(snapshot, annual, quarterly)
        foreign_holding=self.financial_repo.latest_foreign_holding(stock_id) or {}
        shareholder_snapshot=self.financial_repo.latest_shareholder_snapshot(stock_id) or {}
        shareholder={**foreign_holding, **shareholder_snapshot}
        factors=[self._financial_growth_factor(annual, quarterly), self._financial_profitability_factor(snapshot, annual), self._financial_stability_factor(snapshot, annual, quarterly), self._financial_valuation_factor(snapshot), self._financial_shareholder_factor(shareholder)]
        available=[x for x in factors if x.get("contribution_score") is not None]
        weight=sum(float(x["weight"]) for x in available); contribution=sum(float(x["contribution_score"]) for x in available)
        score=round(contribution/weight*100,2) if weight and len(available) >= 2 else None
        missing=[x["factor_code"] for x in factors if x.get("contribution_score") is None]
        status_value=_financial_status(len(available))
        summary="재무 데이터가 부족해 평가를 표시할 수 없습니다." if score is None else f"{_financial_grade(score)} 수준입니다. 실제 수집된 재무지표 {len(available)}개 영역을 기준으로 평가했으며 업종 평균 비교는 반영하지 않았습니다."
        data_sources=self._financial_data_sources(snapshot, annual, quarterly, shareholder)
        return {"score":score,"status":status_value,"confidence":_financial_confidence(len(available)),"grade":_financial_grade(score),"summary":summary,"missing_codes":missing,"factors":factors,"snapshot":snapshot,"annual":annual,"quarterly":quarterly,"shareholder":shareholder,"data_sources":data_sources,"model_version":FINANCIAL_MODEL_VERSION}

    def _financial_data_sources(self, snapshot: dict[str, Any], annual: list[dict[str, Any]], quarterly: list[dict[str, Any]], shareholder: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {"source_name":"Kiwoom ka10001","status":"COLLECTED" if snapshot else "NOT_COLLECTED","used_for":["PER","PBR","EPS","BPS","ROE","시가총액"]},
            {"source_name":"OpenDART","status":"COLLECTED" if annual and quarterly and shareholder.get("largest_shareholder_name") else "PARTIAL" if annual or quarterly or shareholder.get("largest_shareholder_name") else "NOT_COLLECTED","used_for":["연도별 실적","분기별 실적","최대주주","주요주주 변동"]},
            {"source_name":"Kiwoom ka10008","status":"COLLECTED" if shareholder.get("foreign_holding_ratio") is not None else "NOT_COLLECTED","used_for":["외국인 보유율"]},
        ]

    def _financial_factor(self, code: str, score: float | None, raw: str | None, reason: str, source_table: str | None, source_date: str | None) -> dict[str, Any]:
        name,weight=FINANCIAL_FACTOR_META[code]; normalized=None if score is None else max(0.0,min(weight,round(score,2)))
        return {"category":"FINANCIAL","factor_code":code,"factor_name":name,"raw_value":raw,"normalized_score":normalized,"weight":weight,"contribution_score":normalized,"reason":reason,"source_table":source_table,"source_date":source_date}

    def _enrich_financial_snapshot(self, snapshot: dict[str, Any], annual: list[dict[str, Any]], quarterly: list[dict[str, Any]]) -> None:
        self._enrich_per_snapshot(snapshot)
        if _as_float(snapshot.get("debt_ratio")) is not None:
            snapshot.setdefault("debt_ratio_source", snapshot.get("source_type") or "KIWOOM_REAL")
            return
        row=self._latest_statement_with_balance(annual, quarterly)
        if not row:
            return
        liabilities=_as_float(row.get("total_liabilities")); equity=_as_float(row.get("total_equity"))
        if liabilities is None or equity is None or equity <= 0:
            return
        snapshot["debt_ratio"]=round(liabilities / equity * 100, 2)
        snapshot["debt_ratio_source"]="OPENDART"
        snapshot["debt_ratio_calculation_method"]="OPENDART_LIABILITIES_EQUITY_RATIO"
        snapshot["debt_ratio_source_date"]=row.get("period_end_date")

    def _enrich_per_snapshot(self, snapshot: dict[str, Any]) -> None:
        per=_as_float(snapshot.get("per")); eps=_as_float(snapshot.get("eps")); current_price=_as_float(snapshot.get("current_price"))
        if per is not None:
            snapshot.setdefault("per_status", "COLLECTED")
            snapshot.setdefault("per_display_label", f"{per:g}배")
            snapshot.setdefault("per_source", snapshot.get("source_type") or "KIWOOM_REAL")
            return
        if eps is not None and eps <= 0:
            snapshot["per_status"]="LOSS_EXCLUDED"
            snapshot["per_display_label"]="적자 PER"
            snapshot["per_calculation_method"]="EPS_NEGATIVE_PER_EXCLUDED"
            return
        if eps is not None and eps > 0 and current_price is not None:
            calculated=round(current_price / eps, 2)
            snapshot["per"]=calculated
            snapshot["per_status"]="CALCULATED"
            snapshot["per_display_label"]=f"{calculated:g}배"
            snapshot["per_calculation_method"]="CURRENT_PRICE_EPS_PER"
            snapshot["per_source"]="CALCULATED"
            return
        snapshot.setdefault("per_status", "NOT_COLLECTED")

    def _latest_statement_with_balance(self, annual: list[dict[str, Any]], quarterly: list[dict[str, Any]]) -> dict[str, Any] | None:
        for row in reversed(annual or []):
            if any(_as_float(row.get(key)) is not None for key in ("total_assets","total_liabilities","total_equity")):
                return row
        for row in reversed(quarterly or []):
            if any(_as_float(row.get(key)) is not None for key in ("total_assets","total_liabilities","total_equity")):
                return row
        return None

    def _financial_growth_factor(self, annual: list[dict[str, Any]], quarterly: list[dict[str, Any]]) -> dict[str, Any]:
        rows=annual if len(annual)>=2 else quarterly
        basis="연도별" if rows is annual and len(annual)>=2 else "분기별"
        valid=[x for x in rows if _as_float(x.get("revenue")) is not None or _as_float(x.get("operating_profit")) is not None]
        if len(valid)<2:
            return self._financial_factor("FINANCIAL_GROWTH",None,None,"비교 가능한 연도별 또는 분기별 실적이 2개 미만입니다.","stock_financial_statements",None)
        first,last=valid[0],valid[-1]
        first_rev,last_rev=_as_float(first.get("revenue")),_as_float(last.get("revenue"))
        first_op,last_op=_as_float(first.get("operating_profit")),_as_float(last.get("operating_profit"))
        rev_available=first_rev is not None and last_rev is not None
        op_available=first_op is not None and last_op is not None
        rev_up=bool(rev_available and last_rev > first_rev)
        op_up=bool(op_available and last_op > first_op)
        if rev_available and op_available:
            score=25 if rev_up and op_up else 18 if rev_up and not op_up else 16 if (not rev_up and op_up) else 6
            raw=f"{basis} 매출 {'증가' if rev_up else '감소'}, 영업이익 {'증가' if op_up else '감소'}"
            reason=f"{basis} 실적 {len(valid)}개 row의 시작값과 최신값을 기준으로 성장성을 평가했습니다."
        elif rev_available:
            score=16 if rev_up else 7
            raw=f"{basis} 매출 {'증가' if rev_up else '감소'}, 영업이익 미수집"
            reason=f"{basis} 매출액은 비교 가능하지만 영업이익 일부가 누락되어 성장성을 부분 평가했습니다."
        else:
            score=14 if op_up else 6
            raw=f"{basis} 매출 미수집, 영업이익 {'개선' if op_up else '악화'}"
            reason=f"{basis} 영업이익은 비교 가능하지만 매출액 일부가 누락되어 성장성을 부분 평가했습니다."
        return self._financial_factor("FINANCIAL_GROWTH",score,raw,reason,"stock_financial_statements",last.get("period_end_date"))

    def _financial_profitability_factor(self, snapshot: dict[str, Any], annual: list[dict[str, Any]]) -> dict[str, Any]:
        roe=_as_float(snapshot.get("roe")); latest=annual[-1] if annual else {}; op=_as_float(latest.get("operating_profit")); net=_as_float(latest.get("net_income"))
        if roe is None and op is None and net is None: return self._financial_factor("FINANCIAL_PROFITABILITY",None,None,"ROE와 최근 이익 데이터가 없습니다.",None,None)
        if (roe is not None and roe < 0) or (op is not None and op<0) or (net is not None and net<0): score=4
        elif roe is not None and roe>=10 and (net is None or net>0): score=20
        elif net is None or net>=0: score=14
        else: score=10
        return self._financial_factor("FINANCIAL_PROFITABILITY",score,f"ROE {roe if roe is not None else '-'}%, 영업이익 {op if op is not None else '-'}, 순이익 {net if net is not None else '-'}","ROE와 최신 손익의 흑자 여부를 평가했습니다.","stock_financial_snapshots",snapshot.get("snapshot_date"))

    def _financial_stability_factor(self, snapshot: dict[str, Any], annual: list[dict[str, Any]], quarterly: list[dict[str, Any]]) -> dict[str, Any]:
        latest=self._latest_statement_with_balance(annual, quarterly) or {}
        debt=_as_float(snapshot.get("debt_ratio")); assets=_as_float(latest.get("total_assets")); liabilities=_as_float(latest.get("total_liabilities")); equity=_as_float(latest.get("total_equity")); cash=_as_float(latest.get("operating_cash_flow"))
        if debt is None and liabilities is not None and equity is not None and equity > 0:
            debt=round(liabilities / equity * 100, 2)
        if debt is None and assets is None and liabilities is None and equity is None:
            return self._financial_factor("FINANCIAL_STABILITY",None,None,"자산·부채·자본 데이터가 없어 안정성 평가는 제외했습니다.",None,None)
        if equity is not None and equity <= 0:
            score=2
            reason="자본총계가 0 이하로 재무 위험이 큽니다."
        elif debt is not None:
            score=20 if debt < 80 and (cash is None or cash >= 0) else 15 if debt < 150 else 9 if debt < 250 else 5
            reason="OpenDART 최신 재무상태표의 부채총계와 자본총계를 기준으로 부채비율을 계산했습니다." if snapshot.get("debt_ratio_source") == "OPENDART" else "수집된 부채비율과 재무상태표 신호를 기준으로 안정성을 평가했습니다."
            if cash is None:
                reason += " 영업현금흐름 데이터가 없어 안정성은 부분 평가했습니다."
        else:
            available=sum(value is not None for value in (assets, liabilities, equity))
            score=12 if available>=2 else 8
            reason="자산·부채·자본 중 일부 데이터만 있어 안정성을 부분 평가했습니다."
        raw=f"부채비율 {debt if debt is not None else '-'}%, 자산 {assets if assets is not None else '-'}, 부채 {liabilities if liabilities is not None else '-'}, 자본 {equity if equity is not None else '-'}"
        return self._financial_factor("FINANCIAL_STABILITY",score,raw,reason,"stock_financial_statements",latest.get("period_end_date") or snapshot.get("snapshot_date"))

    def _financial_valuation_factor(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        per,pbr,eps,bps=(_as_float(snapshot.get(k)) for k in ("per","pbr","eps","bps"))
        per_status=str(snapshot.get("per_status") or "")
        if per is None and pbr is None and eps is None: return self._financial_factor("FINANCIAL_VALUATION",None,None,"PER/PBR/EPS 데이터가 없습니다.",None,None)
        if eps is not None and eps < 0:
            score=4
            reason="EPS가 음수라 PER은 적자 PER으로 표시하고 밸류에이션 긍정 점수로 반영하지 않았습니다."
        elif per_status == "LOSS_EXCLUDED":
            score=4
            reason="EPS가 0 이하라 PER 계산을 제외했습니다."
        else:
            score=20 if (per is None or per<=12) and (pbr is None or pbr<=1.2) else 14 if (per is None or per<=20) and (pbr is None or pbr<=2) else 8
            reason="업종 평균 비교 없이 절대 PER/PBR 부담만 제한적으로 평가했습니다."
        per_label=snapshot.get("per_display_label") or (f"{per:g}배" if per is not None else "-")
        raw=f"PER {per_label}, PBR {pbr if pbr is not None else '-'}배, EPS {eps if eps is not None else '-'}, BPS {bps if bps is not None else '-'}"
        return self._financial_factor("FINANCIAL_VALUATION",score,raw,reason,"stock_financial_snapshots",snapshot.get("snapshot_date"))

    def _financial_shareholder_factor(self, shareholder: dict[str, Any]) -> dict[str, Any]:
        foreign_ratio=_as_float(shareholder.get("foreign_holding_ratio"))
        largest_ratio=_as_float(shareholder.get("largest_shareholder_ratio"))
        largest_name=shareholder.get("largest_shareholder_name")
        if foreign_ratio is None and largest_ratio is None:
            return self._financial_factor("FINANCIAL_SHAREHOLDER_STABILITY",None,None,"최대주주와 외국인 보유율 데이터가 없습니다.",None,None)
        score=0.0
        if largest_ratio is not None:
            score += 8 if largest_ratio >= 30 else 6 if largest_ratio >= 15 else 3
        if foreign_ratio is not None:
            score += 7 if foreign_ratio >= 5 else 4 if foreign_ratio >= 1 else 2
        score=min(15.0, score)
        raw=f"최대주주 {largest_name or '-'} {largest_ratio if largest_ratio is not None else '-'}%, 외국인 보유율 {foreign_ratio if foreign_ratio is not None else '-'}%"
        reason="OpenDART 최대주주 현황과 ka10008 외국인 보유율을 함께 반영했습니다."
        source_table="stock_shareholder_snapshots, stock_investor_flows"
        return self._financial_factor("FINANCIAL_SHAREHOLDER_STABILITY",score,raw,reason,source_table,shareholder.get("snapshot_date"))

    def _evaluate_chart_for_watchlist_stock(self, stock_id: int) -> dict[str, Any]:
        rows = self.repo.list_stock_daily_price_rows(stock_id, limit=130)
        metrics = self._chart_metrics(rows)
        factors = [self._chart_ma60_factor(metrics), self._chart_ma20_factor(metrics), self._chart_overheat_factor(metrics), self._chart_recent_5d_factor(metrics), self._chart_trading_value_factor(metrics)]
        available = [factor for factor in factors if factor.get("contribution_score") is not None]
        available_weight = sum(float(factor["weight"]) for factor in available)
        contribution_sum = sum(float(factor["contribution_score"]) for factor in available)
        score_value = round(contribution_sum / available_weight * 100, 2) if available_weight else None
        missing_codes = [factor["factor_code"] for factor in factors if factor.get("contribution_score") is None]
        missing_labels = [CHART_FACTOR_META[code][0] for code in missing_codes]
        status_value = _chart_status_by_available_count(len(available))
        return {"score": score_value, "status": status_value, "confidence": _chart_confidence_by_available_count(len(available)), "grade": _chart_grade(score_value), "summary": _chart_summary(score_value, status_value, metrics, missing_labels), "missing_codes": missing_codes, "factors": factors, "metrics": metrics, "model_version": CHART_MODEL_VERSION}

    def _chart_metrics(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not rows:
            return {}
        latest = rows[-1]
        close = _as_float(latest.get("close_price"))
        mas = {window: _simple_ma(rows, window) for window in (5, 10, 20, 60, 120)}
        ma60_5d_ago = _simple_ma(rows[:-5], 60) if len(rows) >= 65 else None
        ma60_slope = ((mas[60] / ma60_5d_ago - 1) * 100) if mas[60] is not None and ma60_5d_ago not in (None, 0) else None
        trading_values = [_as_float(row.get("trading_value")) for row in rows[-21:-1]]
        valid_values = [value for value in trading_values if value is not None and value > 0]
        current_value = _as_float(latest.get("trading_value"))
        average_value = sum(valid_values) / len(valid_values) if valid_values else None
        ratio = current_value / average_value if current_value is not None and average_value not in (None, 0) else None
        return {"trade_date": _date_text(latest.get("trade_date")), "close_price": _round(close), "ma5": _round(mas[5]), "ma10": _round(mas[10]), "ma20": _round(mas[20]), "ma60": _round(mas[60]), "ma120": _round(mas[120]), "close_vs_ma20_pct": _round((close / mas[20] - 1) * 100 if close is not None and mas[20] not in (None, 0) else None), "close_vs_ma60_pct": _round((close / mas[60] - 1) * 100 if close is not None and mas[60] not in (None, 0) else None), "ma60_slope_5d": _round(ma60_slope), "recent_5d_return": _round(_recent_return(rows, 5)), "trading_value_ratio_20": _round(ratio)}

    def _chart_factor(self, code: str, score: float | None, raw: str | None, reason: str, source_date: str | None) -> dict[str, Any]:
        name, weight = CHART_FACTOR_META[code]
        normalized = None if score is None else max(0.0, min(weight, round(score, 2)))
        return {"category": "CHART", "factor_code": code, "factor_name": name, "raw_value": raw, "normalized_score": normalized, "weight": weight, "contribution_score": normalized, "reason": reason, "source_table": "stock_daily_prices" if score is not None else None, "source_date": source_date if score is not None else None}

    def _chart_ma60_factor(self, m: dict[str, Any]) -> dict[str, Any]:
        close, ma60, slope, distance = (_as_float(m.get(k)) for k in ("close_price", "ma60", "ma60_slope_5d", "close_vs_ma60_pct"))
        if None in (close, ma60, slope, distance):
            return self._chart_factor("CHART_MA60_TREND", None, None, "60일선 추세를 계산할 가격 데이터가 부족합니다.", None)
        score = 25 if close >= ma60 and slope > 0 else 20 if close >= ma60 else 16 if abs(distance) <= 3 and slope > 0 else 10 if distance >= -3 else 4
        raw = f"종가 {close:,.0f}, MA60 {ma60:,.1f}, 5일 기울기 {slope:+.2f}%, 이격 {distance:+.2f}%"
        return self._chart_factor("CHART_MA60_TREND", score, raw, "현재가의 60일선 위치와 최근 5거래일 60일선 방향을 함께 평가했습니다.", m.get("trade_date"))

    def _chart_ma20_factor(self, m: dict[str, Any]) -> dict[str, Any]:
        distance = _as_float(m.get("close_vs_ma20_pct"))
        if distance is None:
            return self._chart_factor("CHART_MA20_PULLBACK", None, None, "20일선 이격을 계산할 가격 데이터가 부족합니다.", None)
        score = 25 if -3 <= distance <= 5 else 20 if 5 < distance < 8 else 16 if -8 < distance < -3 else 10 if 8 <= distance < 12 else 4 if distance >= 12 else 6
        return self._chart_factor("CHART_MA20_PULLBACK", score, f"20일선 이격 {distance:+.2f}%", "20일선과 현재가의 거리를 눌림·근접 관찰 기준으로 평가했습니다.", m.get("trade_date"))

    def _chart_overheat_factor(self, m: dict[str, Any]) -> dict[str, Any]:
        d20, d60 = _as_float(m.get("close_vs_ma20_pct")), _as_float(m.get("close_vs_ma60_pct"))
        if d20 is None or d60 is None:
            return self._chart_factor("CHART_OVERHEAT_DISTANCE", None, None, "20일선과 60일선 이격 데이터가 부족합니다.", None)
        score = 3 if d20 >= 15 or d60 >= 35 else 8 if d20 >= 10 or d60 >= 25 else 15 if d20 >= 7 else 20
        return self._chart_factor("CHART_OVERHEAT_DISTANCE", score, f"MA20 {d20:+.2f}%, MA60 {d60:+.2f}%", "이동평균선 대비 이격으로 단기·중기 과열 부담을 평가했습니다.", m.get("trade_date"))

    def _chart_recent_5d_factor(self, m: dict[str, Any]) -> dict[str, Any]:
        value = _as_float(m.get("recent_5d_return"))
        if value is None:
            return self._chart_factor("CHART_RECENT_5D_RISK", None, None, "최근 5거래일 수익률을 계산할 데이터가 부족합니다.", None)
        score = 15 if -3 <= value <= 5 else 12 if 5 < value < 10 else 7 if 10 <= value < 15 else 2 if value >= 15 else 5 if value <= -10 else 10
        return self._chart_factor("CHART_RECENT_5D_RISK", score, f"최근 5일 수익률 {value:+.2f}%", "최근 5거래일 급등·급락에 따른 추격 위험을 평가했습니다.", m.get("trade_date"))

    def _chart_trading_value_factor(self, m: dict[str, Any]) -> dict[str, Any]:
        ratio = _as_float(m.get("trading_value_ratio_20"))
        if ratio is None:
            return self._chart_factor("CHART_TRADING_VALUE_SUPPORT", None, None, "최근 거래대금 또는 20일 평균 거래대금이 부족합니다.", None)
        score = 15 if ratio >= 1.5 else 12 if ratio >= 1.2 else 9 if ratio >= 1 else 5 if ratio >= .7 else 2
        return self._chart_factor("CHART_TRADING_VALUE_SUPPORT", score, f"20일 평균 대비 {ratio:.2f}배", "현재 거래대금이 최근 20일 평균을 얼마나 동반하는지 평가했습니다.", m.get("trade_date"))

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
    @staticmethod
    def _missing_chart_data_from_factors(factors: list[WatchlistEvaluationFactorResponse]) -> list[str]:
        return [factor.factor_name for factor in factors if factor.contribution_score is None]

    def _chart_summary_from_score(self, score: WatchlistEvaluationScore) -> str:
        factors = self._factor_responses(self.repo.list_factors(score.id), category="CHART")
        missing = self._missing_chart_data_from_factors(factors)
        metrics = self._evaluate_chart_for_watchlist_stock(score.stock_id)["metrics"]
        return _chart_summary(score.chart_score, score.chart_status or "NOT_EVALUATED", metrics, missing)

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
                chart_status=score.chart_status,
                chart_grade=_chart_grade(score.chart_score),
                chart_summary=self._chart_summary_from_score(score),
                chart_factors=self._factor_responses(self.repo.list_factors(score.id), category="CHART"),
                missing_chart_data=self._missing_chart_data_from_factors(self._factor_responses(self.repo.list_factors(score.id), category="CHART")),
                chart_model_version=CHART_MODEL_VERSION,
                chart_metrics=self._evaluate_chart_for_watchlist_stock(score.stock_id)["metrics"],
                financial_score=score.financial_score,
                financial_status=score.financial_status,
                financial_grade=_financial_grade(score.financial_score),
                financial_summary=self._evaluate_financial_for_watchlist_stock(score.stock_id)["summary"],
                financial_factors=self._factor_responses(self.repo.list_factors(score.id), category="FINANCIAL"),
                missing_financial_data=[x.factor_name for x in self._factor_responses(self.repo.list_factors(score.id), category="FINANCIAL") if x.contribution_score is None],
                financial_model_version=FINANCIAL_MODEL_VERSION,
                financial_snapshot=self._evaluate_financial_for_watchlist_stock(score.stock_id)["snapshot"],
                financial_annual_statements=self._evaluate_financial_for_watchlist_stock(score.stock_id)["annual"],
                financial_quarterly_statements=self._evaluate_financial_for_watchlist_stock(score.stock_id)["quarterly"],
                shareholder_snapshot=self._evaluate_financial_for_watchlist_stock(score.stock_id)["shareholder"],
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
        chart_factors = [factor for factor in factors if factor.category == "CHART"]
        chart_context = self._evaluate_chart_for_watchlist_stock(score.stock_id)
        financial_factors = [factor for factor in factors if factor.category == "FINANCIAL"]
        financial_context = self._evaluate_financial_for_watchlist_stock(score.stock_id)
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
            chart_grade=_chart_grade(score.chart_score),
            chart_summary=self._chart_summary_from_score(score),
            chart_factors=chart_factors,
            missing_chart_data=self._missing_chart_data_from_factors(chart_factors),
            chart_model_version=CHART_MODEL_VERSION,
            chart_metrics=chart_context["metrics"],
            financial_score=score.financial_score,
            financial_grade=_financial_grade(score.financial_score),
            financial_summary=financial_context["summary"],
            financial_factors=financial_factors,
            missing_financial_data=[x.factor_name for x in financial_factors if x.contribution_score is None],
            financial_model_version=FINANCIAL_MODEL_VERSION,
            financial_snapshot=financial_context["snapshot"],
            financial_annual_statements=financial_context["annual"],
            financial_quarterly_statements=financial_context["quarterly"],
            shareholder_snapshot=financial_context["shareholder"],
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

    def _overall_prompt_lines(self, score: WatchlistEvaluationScore | None, missing: list[str], material_context: dict[str, Any], financial_context: dict[str, Any]) -> list[str]:
        if not score:
            return ["- \uc885\ud569 \ud3c9\uac00: \ubbf8\ud3c9\uac00", "- \uc8fc\uc758: \ub9e4\uc218\u00b7\ub9e4\ub3c4 \ucd94\ucc9c \ubb38\uad6c\ub97c \uc0ac\uc6a9\ud558\uc9c0 \ub9c8\uc138\uc694."]
        axis_scores = {
            "market": score.market_score,
            "material": score.material_score,
            "supply": score.supply_score,
            "chart": score.chart_score,
            "financial": score.financial_score,
        }
        axis_labels = {
            "market": "\uc2dc\uc7a5",
            "material": "\uc7ac\ub8cc",
            "supply": "\uc218\uae09",
            "chart": "\ucc28\ud2b8",
            "financial": "\uc7ac\ubb34",
        }
        weighted = [
            (score.material_score, 0.30),
            (score.supply_score, 0.30),
            (score.chart_score, 0.25),
            (score.market_score, 0.15),
        ]
        available = [(float(value), weight) for value, weight in weighted if value is not None]
        observation = round(sum(value * weight for value, weight in available) / sum(weight for _, weight in available), 1) if len(available) >= 2 and sum(weight for _, weight in available) else None

        grade_order = ["\uc6b0\uc120 \uad00\ucc30", "\uad00\uc2ec \uc720\uc9c0", "\uc870\uac74\ubd80 \uad00\ucc30", "\uad00\ucc30 \ubcf4\ub958", "\uad00\ucc30 \uc6b0\uc120\uc21c\uc704 \ub0ae\uc74c"]
        def obs_grade(value: float | None) -> str:
            if value is None: return "\ubbf8\ud3c9\uac00"
            if value >= 80: return grade_order[0]
            if value >= 65: return grade_order[1]
            if value >= 50: return grade_order[2]
            if value >= 35: return grade_order[3]
            return grade_order[4]
        def limit_grade(current: str, max_grade: str) -> str:
            if current not in grade_order or max_grade not in grade_order:
                return current
            return grade_order[max(grade_order.index(current), grade_order.index(max_grade))]

        risk = 0
        risk_items: list[tuple[int, int, str, str]] = []
        def add_risk(condition: bool, label: str, penalty: int, priority: int, check: str) -> None:
            nonlocal risk
            if condition:
                risk += penalty
                risk_items.append((priority, penalty, label, check))

        financial_score = axis_scores["financial"]
        supply_score = axis_scores["supply"]
        chart_score = axis_scores["chart"]
        market_score = axis_scores["market"]
        add_risk(financial_score is not None and financial_score < 35, "\uc7ac\ubb34 \ub9ac\uc2a4\ud06c", 30, 10, "EPS\u00b7\ubd80\ucc44\ube44\uc728\u00b7\uc601\uc5c5\uc774\uc775 \uac1c\uc120 \uc5ec\ubd80")
        add_risk(financial_score is not None and 35 <= financial_score < 50, "\uc7ac\ubb34 \ubd80\ub2f4", 20, 10, "EPS\u00b7\ubd80\ucc44\ube44\uc728\u00b7\uc601\uc5c5\uc774\uc775 \uac1c\uc120 \uc5ec\ubd80")
        snapshot = financial_context.get("snapshot") or {}
        eps = _as_float(snapshot.get("eps"))
        debt = _as_float(snapshot.get("debt_ratio"))
        add_risk(eps is not None and eps < 0, "EPS \uc74c\uc218", 8, 11, "EPS \ud751\uc790 \uc804\ud658 \uc5ec\ubd80")
        add_risk(debt is not None and debt >= 200, "\ubd80\ucc44\ube44\uc728 \uacfc\ub2e4", 8, 12, "\ubd80\ucc44\ube44\uc728 \uc644\ud654 \uc5ec\ubd80")
        add_risk(supply_score is not None and supply_score < 35, "\uc218\uae09 \ubd80\uc871", 18, 20, "\uc678\uad6d\uc778\u00b7\uae30\uad00\u00b7\ud504\ub85c\uadf8\ub7a8 \uc21c\ub9e4\uc218 \uc804\ud658 \uc5ec\ubd80")
        add_risk(supply_score is not None and 35 <= supply_score < 50, "\uc218\uae09 \uacbd\uacc4", 10, 20, "\uc678\uad6d\uc778\u00b7\uae30\uad00\u00b7\ud504\ub85c\uadf8\ub7a8 \uc21c\ub9e4\uc218 \uc804\ud658 \uc5ec\ubd80")
        add_risk(chart_score is not None and chart_score < 35, "\ucc28\ud2b8 \uc704\ud5d8", 20, 30, "20\uc77c\uc120 \ud68c\ubcf5\uacfc 60\uc77c\uc120 \ucd94\uc138 \ud655\uc778")
        add_risk(chart_score is not None and 35 <= chart_score < 50, "\ucc28\ud2b8 \uacbd\uacc4", 12, 30, "20\uc77c\uc120 \ud68c\ubcf5\uacfc 60\uc77c\uc120 \ucd94\uc138 \ud655\uc778")
        add_risk(market_score is not None and market_score < 35, "\uc2dc\uc7a5 \ud658\uacbd \uc704\ud5d8", 12, 40, "KOSDAQ\u00b7\uc2dc\uc7a5 \uac70\ub798\ub300\uae08 \ud68c\ubcf5 \uc5ec\ubd80")
        add_risk(market_score is not None and 35 <= market_score < 50, "\uc2dc\uc7a5 \uacbd\uacc4", 8, 40, "KOSDAQ\u00b7\uc2dc\uc7a5 \uac70\ub798\ub300\uae08 \ud68c\ubcf5 \uc5ec\ubd80")
        add_risk(bool(missing), "\ubbf8\uc218\uc9d1 \ud56d\ubaa9", min(24, len(missing) * 8), 50, "\ubbf8\uc218\uc9d1 \ud3c9\uac00\ucd95 \uc218\uc9d1 \ud6c4 \uc7ac\ud3c9\uac00")
        theme_return = material_context.get("representative_theme_return_30d")
        add_risk(_as_float(theme_return) is not None and _as_float(theme_return) <= -20, "\ud14c\ub9c8 \uc9c0\uc18d\uc131 \ud655\uc778", 6, 60, "\ub300\ud45c \ud14c\ub9c8 \ud750\ub984 \uc9c0\uc18d \uc5ec\ubd80")
        risk = min(100, risk)
        risk_grade = "\ub192\uc74c" if risk >= 50 else "\uacbd\uacc4" if risk >= 30 else "\ubcf4\ud1b5" if risk >= 15 else "\ub0ae\uc74c"

        overall_grade = obs_grade(observation)
        confidence = score.data_confidence or "NOT_EVALUATED"
        if overall_grade != "\ubbf8\ud3c9\uac00":
            if risk_grade == "\ub192\uc74c": overall_grade = limit_grade(overall_grade, "\uad00\ucc30 \ubcf4\ub958")
            elif risk_grade == "\uacbd\uacc4": overall_grade = limit_grade(overall_grade, "\uc870\uac74\ubd80 \uad00\ucc30")
            if confidence in {"LOW", "NOT_EVALUATED"}: overall_grade = limit_grade(overall_grade, "\uad00\ucc30 \ubcf4\ub958")
            elif confidence == "LIMITED": overall_grade = limit_grade(overall_grade, "\uc870\uac74\ubd80 \uad00\ucc30")
            if financial_score is not None and financial_score < 35: overall_grade = limit_grade(overall_grade, "\uad00\ucc30 \ubcf4\ub958")
            if financial_score is not None and financial_score < 50 and ((supply_score is not None and supply_score < 50) or (chart_score is not None and chart_score < 50)):
                overall_grade = limit_grade(overall_grade, "\uad00\ucc30 \ubcf4\ub958")
            if (supply_score is not None and supply_score < 35) or (chart_score is not None and chart_score < 35):
                overall_grade = limit_grade(overall_grade, "\uad00\ucc30 \ubcf4\ub958")
            if supply_score is not None and supply_score < 50 and chart_score is not None and chart_score < 50:
                overall_grade = limit_grade(overall_grade, "\uc870\uac74\ubd80 \uad00\ucc30")

        strengths = []
        weaknesses = []
        for key, value in sorted(axis_scores.items(), key=lambda row: -1 if row[1] is None else float(row[1])):
            if value is not None and value >= 65 and len(strengths) < 3:
                strengths.append(f"{axis_labels[key]} {round(value)}\uc810")
        for key, value in sorted(axis_scores.items(), key=lambda row: 101 if row[1] is None else float(row[1])):
            if value is not None and value < 50 and len(weaknesses) < 3:
                weaknesses.append(f"{axis_labels[key]} {round(value)}\uc810")
        ordered_risks: list[str] = []
        checks: list[str] = []
        for _, _, label, check in sorted(risk_items, key=lambda row: (row[0], -row[1])):
            if label not in ordered_risks and len(ordered_risks) < 4:
                ordered_risks.append(label)
            if check not in checks and len(checks) < 5:
                checks.append(check)
        if not checks:
            checks.append("5\ub300 \ud3c9\uac00\ucd95 \ubcc0\ud654 \uc5ec\ubd80")
        checklist = [
            "\uc678\uad6d\uc778\u00b7\uae30\uad00 \uc21c\ub9e4\ub3c4\uac00 3\uc77c \uc774\uc0c1 \uc774\uc5b4\uc9c0\ub294\uac00?",
            "20\uc77c\uc120 \uadfc\ucc98\uc5d0\uc11c \uc9c0\uc9c0 \ub610\ub294 \ud68c\ubcf5 \ud750\ub984\uc774 \ub098\uc624\ub294\uac00?",
            "\ud6c4\uc18d \ub274\uc2a4\u00b7\uacf5\uc2dc\uac00 \uc774\uc5b4\uc9c0\ub294\uac00?",
            "EPS \ub610\ub294 \uc601\uc5c5\uc774\uc775 \uac1c\uc120 \uc2e0\ud638\uac00 \ud655\uc778\ub418\ub294\uac00?",
            "\ubbf8\uc218\uc9d1 \ud3c9\uac00\ucd95\uc744 \uc218\uc9d1\ud55c \ub4a4 \uc7ac\ud3c9\uac00\ud588\ub294\uac00?",
        ]
        return [
            f"- \uc885\ud569 \ub4f1\uae09: {overall_grade}",
            f"- \uad00\ucc30 \ub9e4\ub825\ub3c4: {observation if observation is not None else '\ubbf8\ud3c9\uac00'}",
            f"- \ub9ac\uc2a4\ud06c: {risk_grade}({risk}\uc810)",
            f"- \ub370\uc774\ud130 \uc2e0\ub8b0\ub3c4: {confidence}",
            f"- \uac15\uc810: {', '.join(strengths) if strengths else '\uba85\ud655\ud55c \uac15\uc810 \ubd80\uc871'}",
            f"- \uc57d\uc810: {', '.join(weaknesses) if weaknesses else '\ud06c\uac8c \ubd80\uac01\ub418\ub294 \uc57d\uc810 \uc5c6\uc74c'}",
            f"- \ub9ac\uc2a4\ud06c \uc694\uc778: {', '.join(ordered_risks) if ordered_risks else '\uc8fc\uc694 \ub9ac\uc2a4\ud06c \ub0ae\uc74c'}",
            f"- \ub2e4\uc74c \ud655\uc778 \ud56d\ubaa9: {', '.join(checks[:5])}",
            f"- \uad00\ucc30 \uccb4\ud06c\ub9ac\uc2a4\ud2b8: {', '.join(checklist[:6])}",
            "- \uc8fc\uc758: \uc774 \uc885\ud569 \ud3c9\uac00\ub294 \ub9e4\uc218\u00b7\ub9e4\ub3c4 \ucd94\ucc9c\uc774 \uc544\ub2c8\ub77c \uad00\ucc30 \uc6b0\uc120\uc21c\uc704\uc640 \ud655\uc778 \ud56d\ubaa9 \uc815\ub9ac\uc785\ub2c8\ub2e4. \ub9e4\uc218 \ucd94\ucc9c, \uc9c0\uae08 \ub9e4\uc218, \uc9c4\uc785 \uc801\ud569, \ub9e4\ub3c4 \ud544\uc694\uc640 \uac19\uc740 \ubb38\uad6c\ub97c \uc0ac\uc6a9\ud558\uc9c0 \ub9c8\uc138\uc694.",
        ]
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
        financial_context = self._evaluate_financial_for_watchlist_stock(item.stock_id)
        overall_prompt_lines = self._overall_prompt_lines(latest_score, missing, material_context, financial_context)
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
                f"- 차트 점수/등급: {latest_score.chart_score if latest_score else '미평가'} / {_chart_grade(latest_score.chart_score) if latest_score else '미평가'}",
                f"- 차트 상태: {latest_score.chart_status if latest_score else '미평가'}",
                f"- 차트 요약: {self._chart_summary_from_score(latest_score) if latest_score else '차트 평가 전입니다.'}",
                f"- 재무 점수/등급: {latest_score.financial_score if latest_score else '미평가'} / {_financial_grade(latest_score.financial_score) if latest_score else '미평가'}",
                f"- 재무 상태: {latest_score.financial_status if latest_score else '미평가'}",
                f"- \uc7ac\ubb34 \uc694\uc57d: {financial_context['summary']}",
                "",
                *overall_prompt_lines,
                f"- 미수집/미반영 데이터: {', '.join(missing) if missing else '없음'}",
                "",
                "시장, 재료, 수급, 차트, 재무 관점에서 현재 사용할 수 있는 근거와 부족한 근거를 구분해 주세요.",
                "매수/매도 추천은 하지 말고, 20일선 눌림·60일선 추세·과열 이격·최근 5일 상승률·거래대금 동반 여부를 중심으로 설명해 주세요.",
            ]
        )
        return WatchlistGptPromptResponse(watchlist_id=watchlist_id, prompt=prompt)
