from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class KiwoomRestRequest:
    path: str
    api_id: str
    body: dict[str, Any]
    cont_yn: str | None = None
    next_key: str | None = None


@dataclass
class KiwoomRestResponse:
    status_code: int
    headers: dict[str, str]
    json_body: dict[str, Any]
    raw_text_preview: str
    elapsed_ms: int
    cont_yn: str
    next_key: str


@dataclass
class KiwoomTokenResponse:
    token: str
    token_type: str | None
    expires_at: str | None
    raw: dict[str, Any]
