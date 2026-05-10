from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ClassificationRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_group: str
    target_type: str
    rule_name: str
    keywords: str
    output_field: str
    output_value: str
    score_delta: int
    priority: int
    is_active: bool
    description: str | None
    created_at: str
    updated_at: str


class ClassificationRuleCreate(BaseModel):
    rule_group: str
    target_type: str
    rule_name: str
    keywords: str
    output_field: str
    output_value: str
    score_delta: int = 0
    priority: int = 100
    is_active: bool = True
    description: str | None = None


class ClassificationRuleUpdate(BaseModel):
    rule_group: str | None = None
    target_type: str | None = None
    rule_name: str | None = None
    keywords: str | None = None
    output_field: str | None = None
    output_value: str | None = None
    score_delta: int | None = None
    priority: int | None = None
    is_active: bool | None = None
    description: str | None = None
