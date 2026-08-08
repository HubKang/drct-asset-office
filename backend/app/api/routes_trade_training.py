from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.trade_training_schema import (
    TradeTrainingAccountCreate,
    TradeTrainingAccountDeleteResponse,
    TradeTrainingAccountListResponse,
    TradeTrainingAccountPerformanceResponse,
    TradeTrainingAccountRebuildRequest,
    TradeTrainingAccountRebuildResponse,
    TradeTrainingAccountResponse,
    TradeTrainingAccountSessionListResponse,
    TradeTrainingAccountSummaryResponse,
    TradeTrainingAccountUpdate,
    TradeTrainingClosedTradeListResponse,
    TradeTrainingPriceCollectRequest,
    TradeTrainingPriceCollectResponse,
    TradeTrainingRiskScenarioDetail,
    TradeTrainingRiskScenarioDraftRequest,
    TradeTrainingRiskScenarioRevisionListResponse,
    RiskOrderPreviewRequest,
    RiskOrderPreviewResponse,
    RiskLevelReachCheckRequest,
    RiskLevelResponseRequest,
    TrainingFinishResponse,
    TrainingGptPackageResponse,
    TrainingOrderRequest,
    TrainingSessionCreate,
    TrainingSessionDetailResponse,
    TrainingResultResponse,
    SimulationReviewResponse,
    SimulationReviewSaveRequest,
    TrainingCalendarResponse,
    TrainingStockListResponse,
    MultiPeriodTechnicalAnalysisRequest,
    MultiPeriodTechnicalAnalysisResponse,
    TechnicalAnalysisPreviewRequest,
    TechnicalAnalysisPreviewResponse,
)
from backend.app.services.trade_training_service import TradeTrainingService
from backend.app.services.stock_price_service import StockPriceService

router = APIRouter(tags=["trade-training"])


@router.get("/trade-training/accounts", response_model=TradeTrainingAccountListResponse)
def list_trade_training_accounts(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    return TradeTrainingService(db).list_training_accounts(status_filter=status)


@router.post("/trade-training/accounts", response_model=TradeTrainingAccountResponse)
def create_trade_training_account(payload: TradeTrainingAccountCreate, db: Session = Depends(get_db)) -> dict:
    return TradeTrainingService(db).create_training_account(payload)


@router.get("/trade-training/accounts/{account_id}", response_model=TradeTrainingAccountResponse)
def get_trade_training_account(account_id: int, db: Session = Depends(get_db)) -> dict:
    return TradeTrainingService(db).get_training_account(account_id)


@router.patch("/trade-training/accounts/{account_id}", response_model=TradeTrainingAccountResponse)
def update_trade_training_account(
    account_id: int,
    payload: TradeTrainingAccountUpdate,
    db: Session = Depends(get_db),
) -> dict:
    return TradeTrainingService(db).update_training_account(account_id, payload)


@router.get("/trade-training/accounts/{account_id}/summary", response_model=TradeTrainingAccountSummaryResponse)
def get_trade_training_account_summary(account_id: int, db: Session = Depends(get_db)) -> dict:
    return TradeTrainingService(db).get_training_account_summary(account_id)


@router.get("/trade-training/accounts/{account_id}/sessions", response_model=TradeTrainingAccountSessionListResponse)
def list_trade_training_account_sessions(
    account_id: int,
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    return TradeTrainingService(db).list_training_account_sessions(account_id, status_filter=status)


@router.get("/trade-training/accounts/{account_id}/closed-trades", response_model=TradeTrainingClosedTradeListResponse)
def list_trade_training_account_closed_trades(account_id: int, db: Session = Depends(get_db)) -> dict:
    return TradeTrainingService(db).list_training_account_closed_trades(account_id)


@router.get("/trade-training/accounts/{account_id}/performance", response_model=TradeTrainingAccountPerformanceResponse)
def get_trade_training_account_performance(account_id: int, db: Session = Depends(get_db)) -> dict:
    return TradeTrainingService(db).get_training_account_performance(account_id)


@router.delete("/trade-training/accounts/{account_id}", response_model=TradeTrainingAccountDeleteResponse)
def delete_trade_training_account(account_id: int, db: Session = Depends(get_db)) -> dict:
    return TradeTrainingService(db).delete_training_account(account_id)


@router.post("/trade-training/accounts/{account_id}/rebuild", response_model=TradeTrainingAccountRebuildResponse)
def rebuild_trade_training_account(account_id: int, payload: TradeTrainingAccountRebuildRequest, db: Session = Depends(get_db)) -> dict:
    return TradeTrainingService(db).rebuild_training_account_ledger(account_id, apply_changes=payload.apply_changes)


@router.get("/trade-training/calendar", response_model=TrainingCalendarResponse)
def get_training_calendar(month: str = Query(..., pattern=r"^\d{4}-\d{2}$"), db: Session = Depends(get_db)) -> dict:
    return TradeTrainingService(db).get_training_calendar(month=month)


@router.get("/trade-training/stocks", response_model=TrainingStockListResponse)
def list_training_stocks(
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=8, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    return TradeTrainingService(db).list_stocks(q=q, page=page, page_size=page_size)


@router.post("/trade-training/stocks/{stock_id}/collect-prices", response_model=TradeTrainingPriceCollectResponse)
def collect_trade_training_stock_prices(
    stock_id: int,
    payload: TradeTrainingPriceCollectRequest,
    db: Session = Depends(get_db),
) -> dict:
    return StockPriceService(db).collect_trade_training_stock_prices(stock_id=stock_id, mode=payload.mode)


@router.post("/trade-training/sessions", response_model=TrainingSessionDetailResponse)
def create_training_session(payload: TrainingSessionCreate, db: Session = Depends(get_db)) -> dict:
    return TradeTrainingService(db).create_session(payload)


@router.get("/trade-training/sessions/{session_id}", response_model=TrainingSessionDetailResponse)
def get_training_session(session_id: int, db: Session = Depends(get_db)) -> dict:
    return TradeTrainingService(db).get_session_detail(session_id)


@router.post("/trade-training/technical-analysis/preview", response_model=TechnicalAnalysisPreviewResponse)
def preview_trade_training_technical_analysis(
    payload: TechnicalAnalysisPreviewRequest,
    db: Session = Depends(get_db),
) -> dict:
    return TradeTrainingService(db).preview_technical_analysis(payload)


@router.post("/trade-training/technical-analysis/multi-period-preview", response_model=MultiPeriodTechnicalAnalysisResponse)
def preview_trade_training_multi_period_technical_analysis(
    payload: MultiPeriodTechnicalAnalysisRequest,
    db: Session = Depends(get_db),
) -> dict:
    return TradeTrainingService(db).preview_multi_period_technical_analysis(payload)


@router.get("/trade-training/sessions/{session_id}/result", response_model=TrainingResultResponse)
def get_training_result(session_id: int, db: Session = Depends(get_db)) -> dict:
    return TradeTrainingService(db).get_training_result(session_id)


@router.get("/trade-training/sessions/{session_id}/gpt-package", response_model=TrainingGptPackageResponse)
def get_training_gpt_package(session_id: int, db: Session = Depends(get_db)) -> dict:
    return TradeTrainingService(db).build_training_gpt_package(session_id)


@router.get("/trade-training/sessions/{session_id}/review", response_model=SimulationReviewResponse)
def get_training_review(session_id: int, db: Session = Depends(get_db)) -> dict:
    return TradeTrainingService(db).get_simulation_review(session_id)


@router.post("/trade-training/sessions/{session_id}/review", response_model=SimulationReviewResponse)
def save_training_review(
    session_id: int,
    payload: SimulationReviewSaveRequest,
    db: Session = Depends(get_db),
) -> dict:
    return TradeTrainingService(db).save_simulation_review(session_id, payload)


@router.get("/trade-training/sessions/{session_id}/risk-scenario", response_model=TradeTrainingRiskScenarioDetail)
def get_trade_training_risk_scenario(session_id: int, db: Session = Depends(get_db)) -> dict:
    return TradeTrainingService(db).get_current_risk_scenario_detail(session_id)


@router.put("/trade-training/sessions/{session_id}/risk-scenario/draft", response_model=TradeTrainingRiskScenarioDetail)
def upsert_trade_training_risk_scenario_draft(
    session_id: int,
    payload: TradeTrainingRiskScenarioDraftRequest,
    db: Session = Depends(get_db),
) -> dict:
    return TradeTrainingService(db).create_or_update_risk_scenario_draft(session_id, payload)


@router.patch("/trade-training/risk-scenarios/{scenario_id}", response_model=TradeTrainingRiskScenarioDetail)
def update_trade_training_risk_scenario(
    scenario_id: int,
    payload: TradeTrainingRiskScenarioDraftRequest,
    db: Session = Depends(get_db),
) -> dict:
    return TradeTrainingService(db).update_active_risk_scenario(scenario_id, payload)


@router.post("/trade-training/risk-scenarios/{scenario_id}/cancel", response_model=TradeTrainingRiskScenarioDetail)
def cancel_trade_training_risk_scenario(scenario_id: int, db: Session = Depends(get_db)) -> dict:
    return TradeTrainingService(db).cancel_risk_scenario_draft(scenario_id)


@router.get("/trade-training/risk-scenarios/{scenario_id}/revisions", response_model=TradeTrainingRiskScenarioRevisionListResponse)
def list_trade_training_risk_scenario_revisions(scenario_id: int, db: Session = Depends(get_db)) -> dict:
    return TradeTrainingService(db).list_risk_scenario_revisions(scenario_id)


@router.get("/trade-training/accounts/{account_id}/scenario-habits")
def get_trade_training_scenario_habits(
    account_id: int,
    range: str = Query(default="20", pattern=r"^(20|50|all)$"),
    stock_id: int | None = Query(default=None),
    result: str = Query(default="all", pattern=r"^(all|win|loss|flat)$"),
    scenario: str = Query(default="all", pattern=r"^(all|planned|unplanned)$"),
    db: Session = Depends(get_db),
) -> dict:
    return TradeTrainingService(db).get_training_account_scenario_habits(account_id, range, stock_id, result, scenario)


@router.get("/trade-training/risk-scenarios/{scenario_id}/execution-review")
def get_trade_training_risk_scenario_execution_review(scenario_id: int, db: Session = Depends(get_db)) -> dict:
    return TradeTrainingService(db).get_risk_scenario_execution_review(scenario_id)


@router.post("/trade-training/sessions/{session_id}/risk-level-reach-check")
def check_trade_training_risk_level_reach(
    session_id: int,
    payload: RiskLevelReachCheckRequest,
    db: Session = Depends(get_db),
) -> dict:
    return TradeTrainingService(db).check_risk_level_reaches(session_id, payload.chart_date)


@router.post("/trade-training/sessions/{session_id}/risk-level-responses")
def record_trade_training_risk_level_response(
    session_id: int,
    payload: RiskLevelResponseRequest,
    db: Session = Depends(get_db),
) -> dict:
    return TradeTrainingService(db).record_risk_level_response(session_id, payload)

@router.post("/trade-training/sessions/{session_id}/risk-order-preview", response_model=RiskOrderPreviewResponse)
def preview_trade_training_risk_order(session_id: int, payload: RiskOrderPreviewRequest, db: Session = Depends(get_db)) -> dict:
    return TradeTrainingService(db).calculate_risk_order_preview(session_id, payload)

@router.post("/trade-training/sessions/{session_id}/next", response_model=TrainingSessionDetailResponse)
def advance_training_session(session_id: int, db: Session = Depends(get_db)) -> dict:
    return TradeTrainingService(db).next_day(session_id)


@router.post("/trade-training/sessions/{session_id}/buy", response_model=TrainingSessionDetailResponse)
def buy_training_order(session_id: int, payload: TrainingOrderRequest, db: Session = Depends(get_db)) -> dict:
    return TradeTrainingService(db).buy(session_id, payload)


@router.post("/trade-training/sessions/{session_id}/sell", response_model=TrainingSessionDetailResponse)
def sell_training_order(session_id: int, payload: TrainingOrderRequest, db: Session = Depends(get_db)) -> dict:
    return TradeTrainingService(db).sell(session_id, payload)


@router.post("/trade-training/sessions/{session_id}/finish", response_model=TrainingFinishResponse)
def finish_training_session(session_id: int, db: Session = Depends(get_db)) -> dict:
    return TradeTrainingService(db).finish(session_id)


@router.post("/trade-training/sessions/{session_id}/abort", response_model=TrainingFinishResponse)
def abort_training_session(session_id: int, db: Session = Depends(get_db)) -> dict:
    return TradeTrainingService(db).abort(session_id)
