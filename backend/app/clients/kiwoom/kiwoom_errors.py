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


_AUTH_ERROR_TOKENS = (
    "8050",
    "지정단말기 인증",
    "인증에 실패",
    "AUTHENTICATION FAILED",
    "AUTHORIZATION FAILED",
    "INVALID TOKEN",
    "TOKEN EXPIRED",
    "ACCESS TOKEN IS MISSING",
)

_GLOBAL_PROVIDER_ERROR_TOKENS = (
    "/OAUTH2/TOKEN",
    "KIWOOM_AUTH",
    "WINERROR 10013",
    "CONNECTION REFUSED",
    "NAME OR SERVICE NOT KNOWN",
    "TEMPORARY FAILURE IN NAME RESOLUTION",
)


def is_kiwoom_authentication_error(error: BaseException | str) -> bool:
    if isinstance(error, KiwoomApiError):
        if str(error.code) in {
            str(KiwoomErrorCode.KIWOOM_TOKEN_MISSING),
            str(KiwoomErrorCode.KIWOOM_API_ID_MISSING),
            str(KiwoomErrorCode.KIWOOM_DISABLED),
        }:
            return True
        if error.status_code in {401, 403}:
            return True
    normalized = str(error or "").upper()
    return any(token in normalized for token in _AUTH_ERROR_TOKENS)


def is_kiwoom_global_provider_error(error: BaseException | str) -> bool:
    if is_kiwoom_authentication_error(error):
        return True
    if isinstance(error, KiwoomApiError):
        if str(error.code) == str(KiwoomErrorCode.KIWOOM_RATE_LIMITED) or error.status_code == 429:
            return True
    normalized = str(error or "").upper()
    return any(token in normalized for token in _GLOBAL_PROVIDER_ERROR_TOKENS)

