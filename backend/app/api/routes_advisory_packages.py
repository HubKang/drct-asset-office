from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.advisory_package_schema import (
    AdvisoryEvidencePackageResponse,
    AdvisoryPackageGenerateRequest,
    AdvisoryPackageGenerateResponse,
)
from backend.app.services.advisory_evidence_package_service import AdvisoryEvidencePackageService, EvidencePackageOptions
from backend.app.services.advisory_package_service import AdvisoryPackageService

router = APIRouter()


@router.post("/advisory-packages/generate", response_model=AdvisoryPackageGenerateResponse)
def generate_advisory_package(
    payload: AdvisoryPackageGenerateRequest,
    db: Session = Depends(get_db),
) -> AdvisoryPackageGenerateResponse:
    return AdvisoryPackageService(db).generate_package(
        stock_id=payload.stock_id,
        news_ids=payload.news_ids,
        disclosure_ids=payload.disclosure_ids,
        title=payload.title,
        purpose=payload.purpose,
        package_type=payload.package_type,
    )


@router.get("/advisory/evidence-package/{stock_id}", response_model=AdvisoryEvidencePackageResponse)
def get_advisory_evidence_package(
    stock_id: int,
    price_source: str = "pykrx",
    market_metrics_source: str = "auto",
    include_candle_reference: bool = False,
    lookback_days: int = 252,
    recent_candle_limit: int = 60,
    include_raw_candles: bool = False,
    include_similar_patterns: bool = False,
    pattern_window: int = 20,
    similar_case_limit: int = 5,
    pattern_ma: int = 20,
    search_trading_days: int = 252,
    strategy_horizon: str = "both",
    include_scenario_questions: bool = True,
    include_news_disclosures_risk: bool = True,
    include_technical_indicators: bool = True,
    db: Session = Depends(get_db),
) -> AdvisoryEvidencePackageResponse:
    return AdvisoryEvidencePackageService(db).get_evidence_package(
        stock_id=stock_id,
        options=EvidencePackageOptions(
            price_source=price_source,
            market_metrics_source=market_metrics_source,
            include_candle_reference=include_candle_reference,
            lookback_days=lookback_days,
            recent_candle_limit=recent_candle_limit,
            include_raw_candles=include_raw_candles,
            include_similar_patterns=include_similar_patterns,
            pattern_window=pattern_window,
            similar_case_limit=similar_case_limit,
            pattern_ma=pattern_ma,
            search_trading_days=search_trading_days,
            strategy_horizon=strategy_horizon,
            include_scenario_questions=include_scenario_questions,
            include_news_disclosures_risk=include_news_disclosures_risk,
            include_technical_indicators=include_technical_indicators,
        ),
    )
