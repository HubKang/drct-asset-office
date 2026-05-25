from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class KiwoomErrorCode(StrEnum):
    KIWOOM_DISABLED = "KIWOOM_DISABLED"
    KIWOOM_TOKEN_MISSING = "KIWOOM_TOKEN_MISSING"
    KIWOOM_API_ID_MISSING = "KIWOOM_API_ID_MISSING"
    KIWOOM_ORDER_API_BLOCKED = "KIWOOM_ORDER_API_BLOCKED"
    KIWOOM_REQUEST_FAILED = "KIWOOM_REQUEST_FAILED"
    KIWOOM_HTTP_ERROR = "KIWOOM_HTTP_ERROR"
    KIWOOM_JSON_PARSE_FAILED = "KIWOOM_JSON_PARSE_FAILED"
    KIWOOM_RATE_LIMITED = "KIWOOM_RATE_LIMITED"
    KIWOOM_EMPTY_RESPONSE = "KIWOOM_EMPTY_RESPONSE"
    KIWOOM_API_ERROR = "KIWOOM_API_ERROR"


@dataclass
class KiwoomApiError(Exception):
    code: str
    message: str
    status_code: int | None = None
    raw_preview: str | None = None

    def __str__(self) -> str:
        base = f"{self.code}:{self.message}"
        if self.status_code is not None:
            base += f" (status={self.status_code})"
        return base

