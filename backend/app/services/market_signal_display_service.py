from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


ROLE_LABELS = {
    "REQUIRED": "시작 조건",
    "TRIGGER": "시작 조건",
    "CONFIRM": "지지 확인",
    "CONTEXT": "배경 조건",
    "OPPOSING": "반대 근거",
    "INVALIDATION": "무효화 조건",
}

OPERATION_STATUS_LABELS = {
    "DRAFT": "초안",
    "ACTIVE": "운영",
    "INACTIVE": "중지",
    "ARCHIVED": "중지",
}

EVALUATION_STATE_LABELS = {
    "WAITING": "대기",
    "WATCH": "시작 조건 관찰",
    "TRIGGERED": "시작 조건 충족",
    "CONFIRMING": "지지 확인 중",
    "CONFIRMED": "현상 확인",
    "ACTIVE": "현상 확인",
    "STRENGTHENING": "현상 강화",
    "WEAKENING": "현상 약화",
    "RELEASED": "현상 해제",
    "OPPOSED": "반대 근거 우세",
    "INVALIDATED": "무효화",
    "INACTIVE": "대기",
    "DATA_INSUFFICIENT": "데이터 부족",
    "ERROR": "평가 오류",
}

MODEL_FALLBACK_LABELS = {
    "MARKET_PRICE_TREND": "시장가격 추세",
    "MACRO_MOM_YOY_TREND": "거시지표 증감률 추세",
    "POLICY_RATE_REGIME": "정책금리 국면",
    "YIELD_TREND": "금리 추세",
    "FX_TREND": "환율 추세",
    "RELATIVE_STRENGTH": "상대강도",
    "COMMODITY_TREND": "원자재 추세",
    "VOLATILITY_TREND": "변동성 추세",
    "VOLATILITY_REGIME": "변동성 국면",
    "SPREAD_TREND": "금리차·스프레드 추세",
    "SPREAD_REGIME": "금리차·스프레드 국면",
    "SENTIMENT_TREND": "심리 추세",
    "CONDITIONAL_RELATION": "조건 결합형",
}

INDICATOR_FALLBACK_LABELS = {
    "NASDAQ_SP500_RELATIVE": "나스닥·S&P 500 상대강도",
    "SOX_SP500_RELATIVE": "필라델피아 반도체·S&P 500 상대강도",
    "US_NFCI": "시카고 연은 금융여건지수",
    "US_BROAD_DOLLAR": "미국 광의 달러지수",
    "US_INITIAL_CLAIMS": "미국 신규 실업수당 청구",
    "US_10Y_2Y_SPREAD": "미국 국채 10년·2년 금리차",
}

TRANSFORM_LABELS = {
    "RAW_VALUE": "현재값",
    "CHANGE": "변화",
    "CHANGE_RATE": "변화율",
    "MOM": "전월 대비",
    "YOY": "전년 대비",
    "MOVING_AVERAGE": "이동평균",
    "SLOPE": "추세",
    "TURN_UP": "상승 전환",
    "TURN_DOWN": "하락 전환",
    "ACCELERATING": "상승 가속",
    "ACCELERATING_UP": "상승 가속",
    "ACCELERATING_DOWN": "하락 가속",
    "DECELERATING": "둔화",
    "DECELERATING_UP": "상승 둔화",
    "DECELERATING_DOWN": "하락 둔화",
    "Z_SCORE": "표준점수",
    "PERCENTILE": "백분위",
    "DISTANCE_FROM_MA": "이동평균 이격도",
    "N_PERIOD_HIGH": "기간 최고치",
    "N_PERIOD_LOW": "기간 최저치",
    "CONSECUTIVE_UP": "연속 상승",
    "CONSECUTIVE_DOWN": "연속 하락",
    "PERSISTENCE": "지속 기간",
    "TREND_STATE": "추세 방향",
    "TREND_STRENGTH": "추세 강도",
    "CHANNEL_POSITION": "추세 채널 위치",
}


class MarketSignalDisplayService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._indicator_names: dict[str, str] | None = None
        self._model_names: dict[str, str] | None = None

    def resolve_indicator_display_name(self, item_type: str | None, item_code: str | None) -> str:
        code = str(item_code or "").upper()
        if not code:
            return "-"
        if self._indicator_names is None:
            rows = self.db.execute(text("""
                SELECT indicator_code AS code, indicator_name AS name FROM market_indicators
                UNION ALL
                SELECT index_code AS code, index_name AS name FROM market_indexes
            """)).mappings().all()
            self._indicator_names = {str(row["code"]).upper(): str(row["name"]) for row in rows if row.get("name")}
        return self._indicator_names.get(code) or INDICATOR_FALLBACK_LABELS.get(code) or code

    def resolve_model_display_name(self, profile_code: str | None) -> str:
        code = str(profile_code or "CONDITIONAL_RELATION").upper()
        if self._model_names is None:
            rows = self.db.execute(text("SELECT profile_code, profile_name FROM market_signal_model_profiles")).mappings().all()
            self._model_names = {str(row["profile_code"]).upper(): str(row["profile_name"]) for row in rows if row.get("profile_name")}
        return self._model_names.get(code) or MODEL_FALLBACK_LABELS.get(code) or code

    @staticmethod
    def resolve_condition_role_display_name(role: str | None) -> str:
        code = str(role or "").upper()
        return ROLE_LABELS.get(code, code or "조건")

    @staticmethod
    def operation_status_display_name(status: str | None) -> str:
        code = str(status or "").upper()
        return OPERATION_STATUS_LABELS.get(code, code or "-")

    @staticmethod
    def evaluation_state_display_name(state: str | None) -> str:
        code = str(state or "").upper()
        return EVALUATION_STATE_LABELS.get(code, code or "-")

    def build_condition_display_text(self, condition: dict[str, Any], latest_result: dict[str, Any] | None = None) -> str:
        name = self.resolve_indicator_display_name(condition.get("item_type"), condition.get("item_code"))
        transform = str(condition.get("transform_type") or "RAW_VALUE").upper()
        operator = str(condition.get("comparison_operator") or condition.get("operator") or "")
        threshold = condition.get("threshold_value")
        if transform == "SLOPE" and threshold in (0, 0.0):
            return f"{name} {'상승' if operator in {'>', '>='} else '하락'} 추세"
        if transform == "TURN_UP":
            return f"{name} 상승 전환"
        if transform == "TURN_DOWN":
            return f"{name} 하락 전환"
        if transform == "CONSECUTIVE_UP":
            return f"{name} {int(float(threshold or 1))}회 이상 연속 상승"
        if transform == "CONSECUTIVE_DOWN":
            return f"{name} {int(float(threshold or 1))}회 이상 연속 하락"
        if transform == "TREND_STATE" and operator == "!=":
            return f"{name} 방향성 있는 추세 확인"
        transform_name = TRANSFORM_LABELS.get(transform)
        if transform_name is None:
            return f"{name} 고급 조건"
        threshold_text = "" if threshold is None else f" {operator} {float(threshold):g}"
        return f"{name} {transform_name}{threshold_text}"

    def decorate_condition(self, condition: dict[str, Any]) -> dict[str, Any]:
        item = dict(condition)
        item["item_display_name"] = self.resolve_indicator_display_name(item.get("item_type"), item.get("item_code"))
        item["role_display_name"] = self.resolve_condition_role_display_name(item.get("role") or item.get("condition_role"))
        item["display_text"] = self.build_condition_display_text(item)
        item["technical_text"] = " ".join(str(item.get(key) or "") for key in ("item_code", "transform_type", "operator", "comparison_operator", "threshold_value")).strip()
        return item
