from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator


class GptPromptTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    domain: str
    prompt_key: str
    prompt_name: str
    description: str | None
    prompt_text: str
    default_prompt_text: str
    is_active: int
    sort_order: int
    created_at: str
    updated_at: str


class GptPromptTemplateUpdateRequest(BaseModel):
    prompt_name: str | None = None
    description: str | None = None
    prompt_text: str | None = None
    is_active: int | None = None
    sort_order: int | None = None

    @field_validator("prompt_text")
    @classmethod
    def validate_prompt_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value.strip():
            raise ValueError("prompt_text cannot be empty")
        return value


class GptPromptTemplateRestoreResponse(BaseModel):
    message: str
    template: GptPromptTemplateResponse
