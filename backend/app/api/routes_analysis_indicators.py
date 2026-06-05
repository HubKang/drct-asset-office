from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.analysis_indicator_schema import (
    AnalysisConditionTemplateCreate,
    AnalysisConditionTemplateItem,
    AnalysisConditionTemplateListResponse,
    AnalysisConditionTemplateUpdate,
    AnalysisIndicatorCandidateCreate,
    AnalysisIndicatorCandidateItem,
    AnalysisIndicatorCandidateListResponse,
    AnalysisIndicatorCandidateUpdate,
    AnalysisIndicatorAliasCreate,
    AnalysisIndicatorAliasItem,
    AnalysisIndicatorAliasListResponse,
    AnalysisIndicatorAliasUpdate,
    AnalysisIndicatorCreate,
    AnalysisIndicatorItem,
    AnalysisIndicatorListResponse,
    AnalysisIndicatorUpdate,
    AnalysisLlmCatalogResponse,
)
from backend.app.services.analysis_indicator_service import AnalysisIndicatorService

router = APIRouter(tags=["analysis-indicators"])


@router.get("/analysis-indicators", response_model=AnalysisIndicatorListResponse)
def list_analysis_indicators(
    keyword: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    category: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    available_for_llm: bool | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    return AnalysisIndicatorService(db).list_indicators(
        keyword=keyword,
        source_type=source_type,
        category=category,
        active_only=active_only,
        available_for_llm=available_for_llm,
    )


@router.get("/analysis-indicators/llm-catalog", response_model=AnalysisLlmCatalogResponse)
def get_analysis_indicator_llm_catalog(db: Session = Depends(get_db)) -> dict:
    return AnalysisIndicatorService(db).llm_catalog()


@router.post("/analysis-indicators", response_model=AnalysisIndicatorItem)
def create_analysis_indicator(payload: AnalysisIndicatorCreate, db: Session = Depends(get_db)) -> dict:
    return AnalysisIndicatorService(db).create_indicator(payload)


@router.patch("/analysis-indicators/{indicator_id}", response_model=AnalysisIndicatorItem)
def update_analysis_indicator(indicator_id: int, payload: AnalysisIndicatorUpdate, db: Session = Depends(get_db)) -> dict:
    return AnalysisIndicatorService(db).update_indicator(indicator_id, payload)


@router.delete("/analysis-indicators/{indicator_id}", response_model=AnalysisIndicatorItem)
def delete_analysis_indicator(indicator_id: int, db: Session = Depends(get_db)) -> dict:
    return AnalysisIndicatorService(db).delete_indicator(indicator_id)


@router.get("/analysis-indicator-aliases", response_model=AnalysisIndicatorAliasListResponse)
def list_analysis_indicator_aliases(
    keyword: str | None = Query(default=None),
    indicator_key: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> dict:
    return AnalysisIndicatorService(db).list_aliases(keyword=keyword, indicator_key=indicator_key, active_only=active_only)


@router.post("/analysis-indicator-aliases", response_model=AnalysisIndicatorAliasItem)
def create_analysis_indicator_alias(payload: AnalysisIndicatorAliasCreate, db: Session = Depends(get_db)) -> dict:
    return AnalysisIndicatorService(db).create_alias(payload)


@router.patch("/analysis-indicator-aliases/{alias_id}", response_model=AnalysisIndicatorAliasItem)
def update_analysis_indicator_alias(alias_id: int, payload: AnalysisIndicatorAliasUpdate, db: Session = Depends(get_db)) -> dict:
    return AnalysisIndicatorService(db).update_alias(alias_id, payload)


@router.delete("/analysis-indicator-aliases/{alias_id}", response_model=AnalysisIndicatorAliasItem)
def delete_analysis_indicator_alias(alias_id: int, db: Session = Depends(get_db)) -> dict:
    return AnalysisIndicatorService(db).delete_alias(alias_id)


@router.get("/analysis-condition-templates", response_model=AnalysisConditionTemplateListResponse)
def list_analysis_condition_templates(
    active_only: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> dict:
    return AnalysisIndicatorService(db).list_templates(active_only=active_only)


@router.post("/analysis-condition-templates", response_model=AnalysisConditionTemplateItem)
def create_analysis_condition_template(payload: AnalysisConditionTemplateCreate, db: Session = Depends(get_db)) -> dict:
    return AnalysisIndicatorService(db).create_template(payload)


@router.patch("/analysis-condition-templates/{template_id}", response_model=AnalysisConditionTemplateItem)
def update_analysis_condition_template(template_id: int, payload: AnalysisConditionTemplateUpdate, db: Session = Depends(get_db)) -> dict:
    return AnalysisIndicatorService(db).update_template(template_id, payload)


@router.delete("/analysis-condition-templates/{template_id}", response_model=AnalysisConditionTemplateItem)
def delete_analysis_condition_template(template_id: int, db: Session = Depends(get_db)) -> dict:
    return AnalysisIndicatorService(db).delete_template(template_id)


@router.get("/analysis-indicator-candidates", response_model=AnalysisIndicatorCandidateListResponse)
def list_analysis_indicator_candidates(
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> dict:
    return AnalysisIndicatorService(db).list_candidates(status=status, keyword=keyword, active_only=active_only)


@router.post("/analysis-indicator-candidates", response_model=AnalysisIndicatorCandidateItem)
def create_analysis_indicator_candidate(payload: AnalysisIndicatorCandidateCreate, db: Session = Depends(get_db)) -> dict:
    return AnalysisIndicatorService(db).create_candidate(payload)


@router.patch("/analysis-indicator-candidates/{candidate_id}", response_model=AnalysisIndicatorCandidateItem)
def update_analysis_indicator_candidate(candidate_id: int, payload: AnalysisIndicatorCandidateUpdate, db: Session = Depends(get_db)) -> dict:
    return AnalysisIndicatorService(db).update_candidate(candidate_id, payload)


@router.post("/analysis-indicator-candidates/{candidate_id}/approve-as-indicator", response_model=AnalysisIndicatorCandidateItem)
def approve_analysis_indicator_candidate_as_indicator(candidate_id: int, db: Session = Depends(get_db)) -> dict:
    return AnalysisIndicatorService(db).approve_candidate_as_indicator(candidate_id)


@router.post("/analysis-indicator-candidates/{candidate_id}/approve-reference-only", response_model=AnalysisIndicatorCandidateItem)
def approve_analysis_indicator_candidate_reference_only(candidate_id: int, db: Session = Depends(get_db)) -> dict:
    return AnalysisIndicatorService(db).mark_candidate(candidate_id, "approved_reference_only")


@router.post("/analysis-indicator-candidates/{candidate_id}/reject", response_model=AnalysisIndicatorCandidateItem)
def reject_analysis_indicator_candidate(candidate_id: int, db: Session = Depends(get_db)) -> dict:
    return AnalysisIndicatorService(db).mark_candidate(candidate_id, "rejected")


@router.post("/analysis-indicator-candidates/{candidate_id}/mark-needs-engine", response_model=AnalysisIndicatorCandidateItem)
def mark_analysis_indicator_candidate_needs_engine(candidate_id: int, db: Session = Depends(get_db)) -> dict:
    return AnalysisIndicatorService(db).mark_candidate(candidate_id, "needs_engine")
