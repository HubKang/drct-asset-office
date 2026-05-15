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
    market_metrics_source: str = "marcap",
    include_candle_reference: bool = False,
    lookback_days: int = 252,
    recent_candle_limit: int = 60,
    include_raw_candles: bool = False,
    pattern_window: int = 20,
    similar_case_limit: int = 5,
    strategy_horizon: str = "both",
    include_scenario_questions: bool = True,
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
            pattern_window=pattern_window,
            similar_case_limit=similar_case_limit,
            strategy_horizon=strategy_horizon,
            include_scenario_questions=include_scenario_questions,
        ),
    )
