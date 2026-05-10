from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.classification_rule_schema import (
    ClassificationRuleCreate,
    ClassificationRuleResponse,
    ClassificationRuleUpdate,
)
from backend.app.services.classification_rule_service import ClassificationRuleService

router = APIRouter(prefix="/classification-rules", tags=["classification-rules"])


@router.get("", response_model=list[ClassificationRuleResponse])
def list_classification_rules(
    target_type: str | None = None,
    rule_group: str | None = None,
    is_active: bool | None = None,
    keyword: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[ClassificationRuleResponse]:
    return ClassificationRuleService(db).list_rules(
        target_type=target_type,
        rule_group=rule_group,
        is_active=is_active,
        keyword=keyword,
        limit=limit,
        offset=offset,
    )


@router.get("/{rule_id}", response_model=ClassificationRuleResponse)
def get_classification_rule(rule_id: int, db: Session = Depends(get_db)) -> ClassificationRuleResponse:
    return ClassificationRuleService(db).get_rule(rule_id)


@router.post("", response_model=ClassificationRuleResponse)
def create_classification_rule(payload: ClassificationRuleCreate, db: Session = Depends(get_db)) -> ClassificationRuleResponse:
    return ClassificationRuleService(db).create_rule(payload)


@router.patch("/{rule_id}", response_model=ClassificationRuleResponse)
def update_classification_rule(
    rule_id: int,
    payload: ClassificationRuleUpdate,
    db: Session = Depends(get_db),
) -> ClassificationRuleResponse:
    return ClassificationRuleService(db).update_rule(rule_id, payload)


@router.post("/{rule_id}/deactivate", response_model=ClassificationRuleResponse)
def deactivate_classification_rule(rule_id: int, db: Session = Depends(get_db)) -> ClassificationRuleResponse:
    return ClassificationRuleService(db).deactivate_rule(rule_id)
