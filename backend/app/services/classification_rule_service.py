from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.entities.classification_rule import ClassificationRule
from backend.app.repositories.classification_rule_repository import ClassificationRuleRepository
from backend.app.schemas.classification_rule_schema import ClassificationRuleCreate, ClassificationRuleUpdate

ALLOWED_TARGET_TYPES = {"news", "disclosure"}
ALLOWED_RULE_GROUPS = {"tag", "sentiment", "importance", "disclosure_event_type", "disclosure_risk_level"}


class ClassificationRuleService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ClassificationRuleRepository(db)

    def _validate(self, target_type: str, rule_group: str) -> None:
        if target_type not in ALLOWED_TARGET_TYPES:
            raise HTTPException(status_code=400, detail="invalid target_type")
        if rule_group not in ALLOWED_RULE_GROUPS:
            raise HTTPException(status_code=400, detail="invalid rule_group")

    def create_rule(self, payload: ClassificationRuleCreate) -> ClassificationRule:
        self._validate(payload.target_type, payload.rule_group)
        now = now_kst()
        rule = ClassificationRule(
            rule_group=payload.rule_group,
            target_type=payload.target_type,
            rule_name=payload.rule_name,
            keywords=payload.keywords,
            output_field=payload.output_field,
            output_value=payload.output_value,
            score_delta=payload.score_delta,
            priority=payload.priority,
            is_active=1 if payload.is_active else 0,
            description=payload.description,
            created_at=now,
            updated_at=now,
        )
        return self.repo.create(rule)

    def update_rule(self, rule_id: int, payload: ClassificationRuleUpdate) -> ClassificationRule:
        rule = self.repo.get_by_id(rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="classification rule not found")

        values = payload.model_dump(exclude_unset=True)
        target_type = values.get("target_type", rule.target_type)
        rule_group = values.get("rule_group", rule.rule_group)
        self._validate(target_type, rule_group)
        if "is_active" in values:
            values["is_active"] = 1 if values["is_active"] else 0
        values["updated_at"] = now_kst()

        updated = self.repo.update(rule_id, values)
        if not updated:
            raise HTTPException(status_code=404, detail="classification rule not found")
        return updated

    def get_rule(self, rule_id: int) -> ClassificationRule:
        rule = self.repo.get_by_id(rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="classification rule not found")
        return rule

    def list_rules(
        self,
        target_type: str | None = None,
        rule_group: str | None = None,
        is_active: bool | None = None,
        keyword: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ClassificationRule]:
        if target_type and target_type not in ALLOWED_TARGET_TYPES:
            raise HTTPException(status_code=400, detail="invalid target_type")
        if rule_group and rule_group not in ALLOWED_RULE_GROUPS:
            raise HTTPException(status_code=400, detail="invalid rule_group")

        return self.repo.list(
            target_type=target_type,
            rule_group=rule_group,
            is_active=(1 if is_active else 0) if is_active is not None else None,
            keyword=keyword,
            limit=limit,
            offset=offset,
        )

    def deactivate_rule(self, rule_id: int) -> ClassificationRule:
        updated = self.repo.deactivate(rule_id, now_kst())
        if not updated:
            raise HTTPException(status_code=404, detail="classification rule not found")
        return updated
