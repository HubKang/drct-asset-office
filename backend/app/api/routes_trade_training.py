from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.trade_training_schema import (
    TrainingFinishResponse,
    TrainingGptPackageResponse,
    TrainingOrderRequest,
    TrainingSessionCreate,
    TrainingSessionDetailResponse,
    TrainingResultResponse,
    SimulationReviewResponse,
    SimulationReviewSaveRequest,
    TrainingStockListResponse,
)
from backend.app.services.trade_training_service import TradeTrainingService

router = APIRouter(tags=["trade-training"])


@router.get("/trade-training/stocks", response_model=TrainingStockListResponse)
def list_training_stocks(
    q: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    return TradeTrainingService(db).list_stocks(q=q, limit=limit)


@router.post("/trade-training/sessions", response_model=TrainingSessionDetailResponse)
def create_training_session(payload: TrainingSessionCreate, db: Session = Depends(get_db)) -> dict:
    return TradeTrainingService(db).create_session(payload)


@router.get("/trade-training/sessions/{session_id}", response_model=TrainingSessionDetailResponse)
def get_training_session(session_id: int, db: Session = Depends(get_db)) -> dict:
    return TradeTrainingService(db).get_session_detail(session_id)


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
