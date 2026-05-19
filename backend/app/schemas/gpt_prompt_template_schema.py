from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator


class GptPromptTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    prompt_key: str
    prompt_name: str
    prompt_type: str
    description: str | None
    template_text: str
    is_active: int
    is_default: int
    version: int
    created_at: str
    updated_at: str


class GptPromptTemplateUpdateRequest(BaseModel):
    prompt_name: str
    description: str | None = None
    template_text: str
    is_active: int

    @field_validator("template_text")
    @classmethod
    def validate_template_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("template_text cannot be empty")
        return value


class GptPromptTemplateRestoreResponse(BaseModel):
    message: str
    template: GptPromptTemplateResponse
