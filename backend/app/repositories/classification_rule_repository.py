from __future__ import annotations

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from backend.app.entities.classification_rule import ClassificationRule


class ClassificationRuleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, rule: ClassificationRule) -> ClassificationRule:
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)
        return rule

    def get_by_id(self, rule_id: int) -> ClassificationRule | None:
        return self.db.get(ClassificationRule, rule_id)

    def update(self, rule_id: int, payload: dict) -> ClassificationRule | None:
        rule = self.get_by_id(rule_id)
        if not rule:
            return None
        for key, value in payload.items():
            setattr(rule, key, value)
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)
        return rule

    def list(
        self,
        target_type: str | None = None,
        rule_group: str | None = None,
        is_active: int | None = None,
        keyword: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ClassificationRule]:
        stmt: Select[tuple[ClassificationRule]] = select(ClassificationRule)
        if target_type:
            stmt = stmt.where(ClassificationRule.target_type == target_type)
        if rule_group:
            stmt = stmt.where(ClassificationRule.rule_group == rule_group)
        if is_active is not None:
            stmt = stmt.where(ClassificationRule.is_active == is_active)
        if keyword:
            keyword_like = f"%{keyword}%"
            stmt = stmt.where(
                or_(
                    ClassificationRule.rule_name.like(keyword_like),
                    ClassificationRule.keywords.like(keyword_like),
                    ClassificationRule.output_value.like(keyword_like),
                    ClassificationRule.description.like(keyword_like),
                )
            )
        stmt = stmt.order_by(ClassificationRule.priority.asc(), ClassificationRule.id.asc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt).all())

    def list_active_by_target(self, target_type: str) -> list[ClassificationRule]:
        stmt: Select[tuple[ClassificationRule]] = (
            select(ClassificationRule)
            .where(ClassificationRule.target_type == target_type, ClassificationRule.is_active == 1)
            .order_by(ClassificationRule.priority.asc(), ClassificationRule.id.asc())
        )
        return list(self.db.scalars(stmt).all())

    def deactivate(self, rule_id: int, updated_at: str) -> ClassificationRule | None:
        rule = self.get_by_id(rule_id)
        if not rule:
            return None
        rule.is_active = 0
        rule.updated_at = updated_at
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)
        return rule
