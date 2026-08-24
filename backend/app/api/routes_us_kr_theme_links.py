from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.us_kr_theme_link_schema import UsKrLeadAnalysisResponse, UsKrThemeLinkInput, UsKrThemeLinkOverview, UsKrThemeLinkResponse, UsKrThemeLinkUpdate, UsKrTodayObservationResponse
from backend.app.services.us_kr_theme_link_service import UsKrThemeLinkService

router = APIRouter(prefix="/us-kr-theme-links", tags=["us-kr-theme-links"])

@router.get("/overview", response_model=UsKrThemeLinkOverview)
def overview(db: Session = Depends(get_db)) -> UsKrThemeLinkOverview:
    return UsKrThemeLinkService(db).overview()


@router.get("/today-observation", response_model=UsKrTodayObservationResponse)
def today_observation(
    window: int = Query(default=120),
    us_metric: Literal["theme_strength", "simple_return"] = Query(default="theme_strength"),
    db: Session = Depends(get_db),
) -> UsKrTodayObservationResponse:
    if window not in {0, 60, 120, 250}:
        raise HTTPException(status_code=422, detail="분석기간은 60, 120, 250 또는 전체(0)만 지원합니다.")
    return UsKrThemeLinkService(db).today_observation(window=window, us_metric=us_metric)


@router.get("/{link_id}/lead-analysis", response_model=UsKrLeadAnalysisResponse)
def lead_analysis(
    link_id: int,
    window: int = Query(default=120),
    us_metric: Literal["theme_strength", "simple_return"] = Query(default="theme_strength"),
    db: Session = Depends(get_db),
) -> UsKrLeadAnalysisResponse:
    if window not in {0, 60, 120, 250}:
        raise HTTPException(status_code=422, detail="분석기간은 60, 120, 250 또는 전체(0)만 지원합니다.")
    return UsKrThemeLinkService(db).lead_analysis(link_id, window=window, us_metric=us_metric)

@router.post("", response_model=UsKrThemeLinkResponse, status_code=status.HTTP_201_CREATED)
def create(payload: UsKrThemeLinkInput, db: Session = Depends(get_db)) -> UsKrThemeLinkResponse:
    return UsKrThemeLinkService(db).create(payload)

@router.patch("/{link_id}", response_model=UsKrThemeLinkResponse)
def update(link_id: int, payload: UsKrThemeLinkUpdate, db: Session = Depends(get_db)) -> UsKrThemeLinkResponse:
    return UsKrThemeLinkService(db).update(link_id, payload)

@router.delete("/{link_id}", response_model=UsKrThemeLinkResponse)
def delete(link_id: int, db: Session = Depends(get_db)) -> UsKrThemeLinkResponse:
    return UsKrThemeLinkService(db).delete(link_id)
