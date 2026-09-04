from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.entities.drct_stock_signal import DrctSignalSearch, DrctSignalSearchRule, DrctSignalSearchVersion
from backend.app.schemas.drct_stock_signal_schema import DrctRuleVersionCreate, DrctStructuredRule
from backend.app.services.drct_rule_engine import DrctRuleValidator
from backend.app.services.drct_stock_signal_service import DrctStockSignalService


class DrctRuleService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def validate(rule: DrctStructuredRule) -> dict[str, Any]:
        result = DrctRuleValidator.validate(rule.model_dump())
        return {"status": result.status, "errors": result.errors, "required_lookback": result.required_lookback}

    def create_rule_version(self, search_id: int, payload: DrctRuleVersionCreate) -> dict[str, Any]:
        search = self.db.get(DrctSignalSearch, search_id)
        if search is None:
            raise HTTPException(404, "검색식을 찾을 수 없습니다.")
        current = self.db.scalar(select(DrctSignalSearchVersion).where(
            DrctSignalSearchVersion.search_id == search_id,
            DrctSignalSearchVersion.is_current.is_(True),
        ))
        if current is None:
            raise HTTPException(500, "현재 검색식 Version을 찾을 수 없습니다.")
        rule_payload = DrctRuleValidator.durable_rule(payload.rule.model_dump())
        validation = DrctRuleValidator.validate(rule_payload)
        source_text = payload.hts_reference_conditions or current.hts_reference_conditions
        expression_text = payload.hts_condition_expression or current.hts_condition_expression
        current_rule = self.db.scalar(select(DrctSignalSearchRule).where(
            DrctSignalSearchRule.search_version_id == current.id,
        ))
        if current_rule is not None:
            saved_rule = DrctRuleValidator.durable_rule(json.loads(current_rule.rule_json))
            same_source = source_text.strip().replace("\r\n", "\n") == current.hts_reference_conditions.strip().replace("\r\n", "\n")
            same_expression = expression_text.strip() == current.hts_condition_expression.strip()
            if saved_rule == rule_payload and same_source and same_expression:
                return DrctStockSignalService(self.db)._version_dict(current)
        next_no = current.version_no + 1
        try:
            self.db.execute(text("""
                UPDATE drct_signal_search_versions SET is_current=0
                WHERE search_id=:search_id AND is_current=1
            """), {"search_id": search_id})
            version = DrctSignalSearchVersion(
                search_id=search_id,
                version_no=next_no,
                hts_reference_conditions=source_text,
                hts_condition_expression=expression_text,
                drct_rule_text=f"Structured Rule v{rule_payload['schema_version']} · {len(rule_payload['conditions'])} conditions",
                change_note=payload.change_note.strip(),
                is_current=True,
            )
            self.db.add(version)
            self.db.flush()
            self.db.add(DrctSignalSearchRule(
                search_version_id=version.id,
                schema_version=int(rule_payload["schema_version"]),
                rule_json=json.dumps(rule_payload, ensure_ascii=False, separators=(",", ":")),
                validation_status=validation.status,
            ))
            search.updated_at = datetime.now()
            self.db.commit()
            self.db.refresh(version)
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(409, "Rule Version을 생성하지 못했습니다. 다시 시도해 주세요.") from exc
        return DrctStockSignalService(self.db)._version_dict(version)
