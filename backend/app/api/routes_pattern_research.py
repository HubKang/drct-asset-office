from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.pattern_research_schema import (
    PatternGptGoalParsePromptRequest,
    PatternGptGoalParsePromptResponse,
    PatternGptGoalResultValidateRequest,
    PatternGptGoalResultValidateResponse,
    PatternGoalParseRequest,
    PatternGoalParseResponse,
    PatternIndicatorListResponse,
    PatternResearchGptPackageResponse,
    PatternResearchRunCreateResponse,
    PatternResearchRunDetailResponse,
    PatternResearchRunListResponse,
    PatternResearchRunRequest,
    PatternResearchRunSimulateResponse,
    PatternResearchSampleListResponse,
)
from backend.app.services.pattern_research_service import PatternResearchService

router = APIRouter(prefix="/pattern-research", tags=["pattern-research"])


@router.get("/stocks")
def list_pattern_research_stocks(
    keyword: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    return PatternResearchService(db).list_stocks(keyword=keyword, limit=limit)


@router.get("/indicators", response_model=PatternIndicatorListResponse)
def list_pattern_research_indicators(db: Session = Depends(get_db)) -> dict:
    return PatternResearchService(db).list_indicators()


@router.post("/parse-goal", response_model=PatternGoalParseResponse)
def parse_pattern_goal(payload: PatternGoalParseRequest, db: Session = Depends(get_db)) -> dict:
    return PatternResearchService(db).parse_goal(payload.goal_text, use_llm=payload.use_llm, llm_mode=payload.llm_mode)


@router.post("/gpt-goal-parse-prompt", response_model=PatternGptGoalParsePromptResponse)
def build_gpt_goal_parse_prompt(payload: PatternGptGoalParsePromptRequest, db: Session = Depends(get_db)) -> dict:
    return PatternResearchService(db).gpt_goal_parse_prompt(payload.goal_text, payload.parsed_goal)


@router.get("/gpt-goal-parse-prompt", response_model=PatternGptGoalParsePromptResponse)
def get_gpt_goal_parse_prompt(
    goal_text: str = Query(min_length=1),
    db: Session = Depends(get_db),
) -> dict:
    return PatternResearchService(db).gpt_goal_parse_prompt(goal_text)


@router.post("/validate-gpt-goal-result", response_model=PatternGptGoalResultValidateResponse)
def validate_gpt_goal_result(payload: PatternGptGoalResultValidateRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return PatternResearchService(db).validate_gpt_goal_result(payload.goal_text, payload.gpt_result_text, payload.parsed_goal)
    except Exception as exc:
        return {
            "status": "validation_failed",
            "validated_conditions": [],
            "new_indicator_candidates": [],
            "unsupported_items": [],
            "warnings": [],
            "interpretation_conflicts": [],
            "raw_error": f"GPT 결과 검증 API 처리 중 오류가 발생했습니다: {exc}",
            "validation_message": f"GPT 결과 검증 API 처리 중 오류가 발생했습니다: {exc}",
            "parsed_json": {},
        }


@router.post("/runs", response_model=PatternResearchRunCreateResponse)
def create_pattern_research_run(payload: PatternResearchRunRequest, db: Session = Depends(get_db)) -> dict:
    return PatternResearchService(db).create_run(payload)


@router.post("/runs/simulate", response_model=PatternResearchRunSimulateResponse)
def simulate_pattern_research_run(payload: PatternResearchRunRequest, db: Session = Depends(get_db)) -> dict:
    return PatternResearchService(db).simulate_run(payload)


@router.get("/runs", response_model=PatternResearchRunListResponse)
def list_pattern_research_runs(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    return PatternResearchService(db).list_runs(limit=limit)


@router.get("/runs/{run_id}", response_model=PatternResearchRunDetailResponse)
def get_pattern_research_run(run_id: int, db: Session = Depends(get_db)) -> dict:
    return PatternResearchService(db).get_run(run_id)


@router.get("/runs/{run_id}/samples", response_model=PatternResearchSampleListResponse)
def list_pattern_research_samples(
    run_id: int,
    label: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    return PatternResearchService(db).list_samples(run_id, label=label)


@router.get("/runs/{run_id}/gpt-package", response_model=PatternResearchGptPackageResponse)
def get_pattern_research_gpt_package(run_id: int, db: Session = Depends(get_db)) -> dict:
    return PatternResearchService(db).gpt_package(run_id)


@router.get("/runs/{run_id}/csv")
def download_pattern_research_csv(run_id: int, db: Session = Depends(get_db)) -> Response:
    csv_text = PatternResearchService(db).csv_text(run_id)
    return Response(
        content="\ufeff" + csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="pattern_research_{run_id}.csv"'},
    )
