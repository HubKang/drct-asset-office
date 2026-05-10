from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CollectionRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    collector_name: str
    target: str | None
    status: str
    started_at: str
    finished_at: str | None
    message: str | None
    created_at: str
