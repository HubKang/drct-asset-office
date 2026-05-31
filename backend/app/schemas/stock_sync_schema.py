from __future__ import annotations

from pydantic import BaseModel, Field
from pydantic import field_validator

ALLOWED_SECURITY_TYPES = {"common_stock", "preferred_stock", "etf", "etn", "spac", "reit", "other"}


class StockSyncRequest(BaseModel):
    markets: list[str] = Field(default_factory=lambda: ["KOSPI", "KOSDAQ"])
    dry_run: bool = False
    deactivate_missing: bool = True
    include_security_types: list[str] = Field(default_factory=lambda: ["common_stock"])
    mode: str = "upsert"

    @field_validator("include_security_types")
    @classmethod
    def validate_security_types(cls, value: list[str]) -> list[str]:
        normalized = [v.strip().lower() for v in value if v and v.strip()]
        if not normalized:
            return ["common_stock"]
        invalid = [v for v in normalized if v not in ALLOWED_SECURITY_TYPES]
        if invalid:
            raise ValueError(f"invalid include_security_types: {','.join(invalid)}")
        deduped: list[str] = []
        for item in normalized:
            if item not in deduped:
                deduped.append(item)
        return deduped


class StockSyncResponse(BaseModel):
    markets: list[str]
    dry_run: bool
    mode: str = "upsert"
    rebuild_strategy: str | None = None
    raw_fetched_count: int
    eligible_count: int
    type_counts: dict[str, int]
    type_samples: dict[str, list[dict[str, str | None]]] | None = None
    deleted_existing_count: int = 0
    fetched_count: int
    inserted_count: int
    updated_count: int
    reactivated_count: int
    deactivated_count: int
    skipped_count: int
    error_count: int
    started_at: str
    finished_at: str
    message: str
