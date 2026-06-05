from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst


class AnalysisIndicatorRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _row(row: Any) -> dict[str, Any]:
        return dict(row) if row else {}

    def list_indicators(
        self,
        *,
        keyword: str | None = None,
        source_type: str | None = None,
        category: str | None = None,
        active_only: bool = True,
        available_for_llm: bool | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if keyword:
            clauses.append("(indicator_key LIKE :keyword OR indicator_name LIKE :keyword OR COALESCE(description, '') LIKE :keyword)")
            params["keyword"] = f"%{keyword.strip()}%"
        if source_type:
            clauses.append("source_type = :source_type")
            params["source_type"] = source_type
        if category:
            clauses.append("category = :category")
            params["category"] = category
        if active_only:
            clauses.append("is_active = 1")
        if available_for_llm is not None:
            clauses.append("is_available_for_llm = :available_for_llm")
            params["available_for_llm"] = 1 if available_for_llm else 0
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.db.execute(
            text(f"SELECT * FROM analysis_indicators {where} ORDER BY sort_order ASC, id ASC"),
            params,
        ).mappings().all()
        return [dict(row) for row in rows]

    def create_indicator(self, values: dict[str, Any]) -> dict[str, Any]:
        now = now_kst()
        payload = {
            "indicator_key": values["indicator_key"],
            "indicator_name": values["indicator_name"],
            "description": values.get("description"),
            "source_type": values["source_type"],
            "source_table": values.get("source_table"),
            "source_column": values.get("source_column"),
            "calculation_formula": values.get("calculation_formula"),
            "calculation_type": values.get("calculation_type"),
            "parameters_json": values.get("parameters_json") or "{}",
            "required_columns_json": values.get("required_columns_json") or "[]",
            "data_type": values.get("data_type") or "number",
            "unit": values.get("unit"),
            "category": values.get("category") or "condition",
            "allowed_operators_json": values.get("allowed_operators_json") or "[\">\", \">=\", \"<\", \"<=\", \"between\", \"=\", \"!=\"]",
            "default_operator": values.get("default_operator"),
            "default_value_json": values.get("default_value_json"),
            "example_expressions": values.get("example_expressions"),
            "is_available_for_rule": int(values.get("is_available_for_rule", 1)),
            "is_available_for_llm": int(values.get("is_available_for_llm", 1)),
            "is_entry_allowed": int(values.get("is_entry_allowed", 1)),
            "is_success_allowed": int(values.get("is_success_allowed", 0)),
            "is_failure_allowed": int(values.get("is_failure_allowed", 0)),
            "needs_review_default": int(values.get("needs_review_default", 0)),
            "execution_supported": int(values.get("execution_supported", 0)),
            "execution_status": values.get("execution_status"),
            "execution_message": values.get("execution_message"),
            "is_active": int(values.get("is_active", 1)),
            "sort_order": int(values.get("sort_order", 0)),
            "created_at": now,
            "updated_at": now,
        }
        cursor = self.db.execute(
            text(
                """
                INSERT INTO analysis_indicators (
                    indicator_key, indicator_name, description, source_type, source_table, source_column,
                    calculation_formula, calculation_type, parameters_json, required_columns_json, data_type, unit, category, allowed_operators_json,
                    default_operator, default_value_json, example_expressions, is_available_for_rule,
                    is_available_for_llm, is_entry_allowed, is_success_allowed, is_failure_allowed,
                    needs_review_default, execution_supported, execution_status, execution_message, is_active, sort_order, created_at, updated_at
                )
                VALUES (
                    :indicator_key, :indicator_name, :description, :source_type, :source_table, :source_column,
                    :calculation_formula, :calculation_type, :parameters_json, :required_columns_json, :data_type, :unit, :category, :allowed_operators_json,
                    :default_operator, :default_value_json, :example_expressions, :is_available_for_rule,
                    :is_available_for_llm, :is_entry_allowed, :is_success_allowed, :is_failure_allowed,
                    :needs_review_default, :execution_supported, :execution_status, :execution_message, :is_active, :sort_order, :created_at, :updated_at
                )
                """
            ),
            payload,
        )
        self.db.commit()
        return self.get_indicator(int(cursor.lastrowid)) or {}

    def get_indicator(self, indicator_id: int) -> dict[str, Any] | None:
        row = self.db.execute(text("SELECT * FROM analysis_indicators WHERE id = :id"), {"id": indicator_id}).mappings().first()
        return dict(row) if row else None

    def update_indicator(self, indicator_id: int, values: dict[str, Any]) -> dict[str, Any] | None:
        return self._update("analysis_indicators", indicator_id, values)

    def soft_delete_indicator(self, indicator_id: int) -> dict[str, Any] | None:
        return self.update_indicator(indicator_id, {"is_active": 0})

    def list_aliases(
        self,
        *,
        keyword: str | None = None,
        indicator_key: str | None = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if keyword:
            clauses.append("(alias_text LIKE :keyword OR indicator_key LIKE :keyword OR COALESCE(description, '') LIKE :keyword)")
            params["keyword"] = f"%{keyword.strip()}%"
        if indicator_key:
            clauses.append("indicator_key = :indicator_key")
            params["indicator_key"] = indicator_key
        if active_only:
            clauses.append("is_active = 1")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.db.execute(
            text(f"SELECT * FROM analysis_indicator_aliases {where} ORDER BY sort_order ASC, id ASC"),
            params,
        ).mappings().all()
        return [dict(row) for row in rows]

    def create_alias(self, values: dict[str, Any]) -> dict[str, Any]:
        now = now_kst()
        payload = {
            "alias_text": values["alias_text"],
            "indicator_key": values["indicator_key"],
            "alias_type": values.get("alias_type") or "phrase",
            "match_type": values.get("match_type") or "contains",
            "default_operator": values.get("default_operator"),
            "default_value_json": values.get("default_value_json"),
            "default_category": values.get("default_category") or "entry_filter",
            "apply_to_samples_default": int(values.get("apply_to_samples_default", 0)),
            "needs_review": int(values.get("needs_review", 1)),
            "confidence": float(values.get("confidence", 0.8)),
            "description": values.get("description"),
            "is_active": int(values.get("is_active", 1)),
            "sort_order": int(values.get("sort_order", 0)),
            "created_at": now,
            "updated_at": now,
        }
        cursor = self.db.execute(
            text(
                """
                INSERT INTO analysis_indicator_aliases (
                    alias_text, indicator_key, alias_type, match_type, default_operator, default_value_json,
                    default_category, apply_to_samples_default, needs_review, confidence, description,
                    is_active, sort_order, created_at, updated_at
                )
                VALUES (
                    :alias_text, :indicator_key, :alias_type, :match_type, :default_operator, :default_value_json,
                    :default_category, :apply_to_samples_default, :needs_review, :confidence, :description,
                    :is_active, :sort_order, :created_at, :updated_at
                )
                """
            ),
            payload,
        )
        self.db.commit()
        return self.get_alias(int(cursor.lastrowid)) or {}

    def get_alias(self, alias_id: int) -> dict[str, Any] | None:
        row = self.db.execute(text("SELECT * FROM analysis_indicator_aliases WHERE id = :id"), {"id": alias_id}).mappings().first()
        return dict(row) if row else None

    def update_alias(self, alias_id: int, values: dict[str, Any]) -> dict[str, Any] | None:
        return self._update("analysis_indicator_aliases", alias_id, values)

    def soft_delete_alias(self, alias_id: int) -> dict[str, Any] | None:
        return self.update_alias(alias_id, {"is_active": 0})

    def list_templates(self, *, active_only: bool = True) -> list[dict[str, Any]]:
        where = "WHERE is_active = 1" if active_only else ""
        rows = self.db.execute(
            text(f"SELECT * FROM analysis_condition_templates {where} ORDER BY sort_order ASC, id ASC")
        ).mappings().all()
        return [dict(row) for row in rows]

    def create_template(self, values: dict[str, Any]) -> dict[str, Any]:
        now = now_kst()
        payload = {
            "template_key": values["template_key"],
            "template_name": values["template_name"],
            "description": values.get("description"),
            "template_type": values.get("template_type") or "entry_filter",
            "condition_json": values["condition_json"],
            "default_apply_to_samples": int(values.get("default_apply_to_samples", 0)),
            "needs_review": int(values.get("needs_review", 1)),
            "is_available_for_llm": int(values.get("is_available_for_llm", 1)),
            "is_active": int(values.get("is_active", 1)),
            "sort_order": int(values.get("sort_order", 0)),
            "created_at": now,
            "updated_at": now,
        }
        cursor = self.db.execute(
            text(
                """
                INSERT INTO analysis_condition_templates (
                    template_key, template_name, description, template_type, condition_json,
                    default_apply_to_samples, needs_review, is_available_for_llm, is_active,
                    sort_order, created_at, updated_at
                )
                VALUES (
                    :template_key, :template_name, :description, :template_type, :condition_json,
                    :default_apply_to_samples, :needs_review, :is_available_for_llm, :is_active,
                    :sort_order, :created_at, :updated_at
                )
                """
            ),
            payload,
        )
        self.db.commit()
        return self.get_template(int(cursor.lastrowid)) or {}

    def get_template(self, template_id: int) -> dict[str, Any] | None:
        row = self.db.execute(text("SELECT * FROM analysis_condition_templates WHERE id = :id"), {"id": template_id}).mappings().first()
        return dict(row) if row else None

    def update_template(self, template_id: int, values: dict[str, Any]) -> dict[str, Any] | None:
        return self._update("analysis_condition_templates", template_id, values)

    def soft_delete_template(self, template_id: int) -> dict[str, Any] | None:
        return self.update_template(template_id, {"is_active": 0})

    def list_candidates(
        self,
        *,
        status: str | None = None,
        keyword: str | None = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if status:
            clauses.append("decision_status = :status")
            params["status"] = status
        if keyword:
            clauses.append(
                "(suggested_indicator_key LIKE :keyword OR suggested_indicator_name LIKE :keyword OR COALESCE(source_text, '') LIKE :keyword)"
            )
            params["keyword"] = f"%{keyword.strip()}%"
        if active_only:
            clauses.append("is_active = 1")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.db.execute(
            text(f"SELECT * FROM analysis_indicator_candidates {where} ORDER BY id DESC"),
            params,
        ).mappings().all()
        return [dict(row) for row in rows]

    def create_candidate(self, values: dict[str, Any]) -> dict[str, Any]:
        now = now_kst()
        payload = {
            "source_type": values.get("source_type") or "gpt_goal_parse",
            "source_text": values.get("source_text"),
            "suggested_indicator_key": values["suggested_indicator_key"],
            "suggested_indicator_name": values.get("suggested_indicator_name"),
            "description": values.get("description"),
            "calculation_type": values.get("calculation_type"),
            "formula_description": values.get("formula_description"),
            "parameters_json": values.get("parameters_json") or "{}",
            "required_indicators_json": values.get("required_indicators_json") or "[]",
            "usage_json": values.get("usage_json") or "[]",
            "lookahead_risk": int(values.get("lookahead_risk", 0)),
            "validation_status": values.get("validation_status"),
            "validation_message": values.get("validation_message"),
            "execution_supported": int(values.get("execution_supported", 0)),
            "execution_status": values.get("execution_status"),
            "execution_message": values.get("execution_message"),
            "decision_status": values.get("decision_status") or "pending",
            "decision_note": values.get("decision_note"),
            "linked_indicator_id": values.get("linked_indicator_id"),
            "origin_research_run_id": values.get("origin_research_run_id"),
            "is_active": int(values.get("is_active", 1)),
            "created_at": now,
            "updated_at": now,
        }
        cursor = self.db.execute(
            text(
                """
                INSERT INTO analysis_indicator_candidates (
                    source_type, source_text, suggested_indicator_key, suggested_indicator_name, description,
                    calculation_type, formula_description, parameters_json, required_indicators_json, usage_json,
                    lookahead_risk, validation_status, validation_message, execution_supported, execution_status,
                    execution_message, decision_status, decision_note,
                    linked_indicator_id, origin_research_run_id, is_active, created_at, updated_at
                )
                VALUES (
                    :source_type, :source_text, :suggested_indicator_key, :suggested_indicator_name, :description,
                    :calculation_type, :formula_description, :parameters_json, :required_indicators_json, :usage_json,
                    :lookahead_risk, :validation_status, :validation_message, :execution_supported, :execution_status,
                    :execution_message, :decision_status, :decision_note,
                    :linked_indicator_id, :origin_research_run_id, :is_active, :created_at, :updated_at
                )
                """
            ),
            payload,
        )
        self.db.commit()
        return self.get_candidate(int(cursor.lastrowid)) or {}

    def get_candidate(self, candidate_id: int) -> dict[str, Any] | None:
        row = self.db.execute(
            text("SELECT * FROM analysis_indicator_candidates WHERE id = :id"),
            {"id": candidate_id},
        ).mappings().first()
        return dict(row) if row else None

    def update_candidate(self, candidate_id: int, values: dict[str, Any]) -> dict[str, Any] | None:
        return self._update("analysis_indicator_candidates", candidate_id, values)

    def _update(self, table: str, row_id: int, values: dict[str, Any]) -> dict[str, Any] | None:
        allowed = {
            "analysis_indicators": {
                "indicator_key", "indicator_name", "description", "source_type", "source_table", "source_column",
                "calculation_formula", "calculation_type", "parameters_json", "required_columns_json", "data_type", "unit", "category", "allowed_operators_json",
                "default_operator", "default_value_json", "example_expressions", "is_available_for_rule",
                "is_available_for_llm", "is_entry_allowed", "is_success_allowed", "is_failure_allowed",
                "needs_review_default", "execution_supported", "execution_status", "execution_message", "is_active", "sort_order",
            },
            "analysis_indicator_aliases": {
                "alias_text", "indicator_key", "alias_type", "match_type", "default_operator", "default_value_json",
                "default_category", "apply_to_samples_default", "needs_review", "confidence", "description", "is_active", "sort_order",
            },
            "analysis_condition_templates": {
                "template_key", "template_name", "description", "template_type", "condition_json",
                "default_apply_to_samples", "needs_review", "is_available_for_llm", "is_active", "sort_order",
            },
            "analysis_indicator_candidates": {
                "source_type", "source_text", "suggested_indicator_key", "suggested_indicator_name", "description",
                "calculation_type", "formula_description", "parameters_json", "required_indicators_json", "usage_json",
                "lookahead_risk", "validation_status", "validation_message", "execution_supported", "execution_status",
                "execution_message", "decision_status", "decision_note",
                "linked_indicator_id", "origin_research_run_id", "is_active",
            },
        }[table]
        payload = {key: value for key, value in values.items() if key in allowed and value is not None}
        if not payload:
            return self._get_table_row(table, row_id)
        payload["updated_at"] = now_kst()
        payload["id"] = row_id
        assignments = ", ".join(f"{key} = :{key}" for key in payload if key != "id")
        self.db.execute(text(f"UPDATE {table} SET {assignments} WHERE id = :id"), payload)
        self.db.commit()
        return self._get_table_row(table, row_id)

    def _get_table_row(self, table: str, row_id: int) -> dict[str, Any] | None:
        row = self.db.execute(text(f"SELECT * FROM {table} WHERE id = :id"), {"id": row_id}).mappings().first()
        return dict(row) if row else None
