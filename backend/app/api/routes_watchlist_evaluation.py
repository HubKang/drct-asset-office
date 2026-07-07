from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.watchlist_evaluation_schema import (
    WatchlistEvaluateAllRequest,
    WatchlistEvaluateRequest,
    WatchlistEvaluateResponse,
    WatchlistEvaluationHistoryItem,
    WatchlistEvaluationListResponse,
    WatchlistEvaluationScoreResponse,
    WatchlistGptPromptResponse,
)
from backend.app.services.watchlist_evaluation_service import WatchlistEvaluationService

router = APIRouter()


@router.get("/watchlist/sije-sucha-jae", response_model=WatchlistEvaluationListResponse)
def list_sije_sucha_jae(db: Session = Depends(get_db)) -> WatchlistEvaluationListResponse:
    return WatchlistEvaluationService(db).list_sije_sucha_jae()


@router.post("/watchlist/sije-sucha-jae/evaluate", response_model=WatchlistEvaluateResponse)
def evaluate_sije_sucha_jae(
    payload: WatchlistEvaluateRequest, db: Session = Depends(get_db)
) -> WatchlistEvaluateResponse:
    return WatchlistEvaluationService(db).evaluate(payload)


@router.post("/watchlist/sije-sucha-jae/evaluate-all", response_model=WatchlistEvaluateResponse)
def evaluate_all_sije_sucha_jae(
    payload: WatchlistEvaluateAllRequest, db: Session = Depends(get_db)
) -> WatchlistEvaluateResponse:
    return WatchlistEvaluationService(db).evaluate_all(payload)


@router.get("/watchlist/{watchlist_id}/sije-sucha-jae/history", response_model=list[WatchlistEvaluationHistoryItem])
def get_sije_sucha_jae_history(
    watchlist_id: int, db: Session = Depends(get_db)
) -> list[WatchlistEvaluationHistoryItem]:
    return WatchlistEvaluationService(db).get_history(watchlist_id)


@router.get("/watchlist/sije-sucha-jae/scores/{score_id}", response_model=WatchlistEvaluationScoreResponse)
def get_sije_sucha_jae_score(score_id: int, db: Session = Depends(get_db)) -> WatchlistEvaluationScoreResponse:
    return WatchlistEvaluationService(db).get_score(score_id)


@router.post("/watchlist/sije-sucha-jae/{watchlist_id}/gpt-prompt", response_model=WatchlistGptPromptResponse)
def create_sije_sucha_jae_gpt_prompt(
    watchlist_id: int, db: Session = Depends(get_db)
) -> WatchlistGptPromptResponse:
    return WatchlistEvaluationService(db).create_gpt_prompt(watchlist_id)
