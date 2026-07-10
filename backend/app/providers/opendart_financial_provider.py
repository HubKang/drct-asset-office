from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Any

import requests

from backend.app.core.config import DART_API_KEY, OPENDART_BASE_URL, OPENDART_TIMEOUT_SECONDS


@dataclass(frozen=True)
class OpenDartCorpCode:
    corp_code: str
    corp_name: str | None
    stock_code: str


class OpenDartFinancialProvider:
    def __init__(self) -> None:
        self.api_key = (DART_API_KEY or "").strip()
        self.base_url = OPENDART_BASE_URL.rstrip("/")
        self.timeout = OPENDART_TIMEOUT_SECONDS

    def _require_key(self) -> None:
        if not self.api_key:
            raise ValueError("DART_API_KEY is required for OpenDART financial collection")

    def _get_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        self._require_key()
        payload = {"crtfc_key": self.api_key, **params}
        response = requests.get(f"{self.base_url}/{path.lstrip('/')}", params=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        status = str(data.get("status") or "")
        if status and status != "000":
            message = data.get("message") or f"OpenDART status {status}"
            raise ValueError(str(message))
        return data

    def fetch_corp_codes(self) -> list[OpenDartCorpCode]:
        self._require_key()
        response = requests.get(f"{self.base_url}/corpCode.xml", params={"crtfc_key": self.api_key}, timeout=self.timeout)
        response.raise_for_status()
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            xml_name = archive.namelist()[0]
            root = ET.fromstring(archive.read(xml_name))
        result: list[OpenDartCorpCode] = []
        for item in root.findall("list"):
            stock_code = (item.findtext("stock_code") or "").strip()
            if not re.fullmatch(r"\d{6}", stock_code):
                continue
            result.append(OpenDartCorpCode(
                corp_code=(item.findtext("corp_code") or "").strip(),
                corp_name=(item.findtext("corp_name") or "").strip() or None,
                stock_code=stock_code,
            ))
        return result

    def get_financial_statements(self, corp_code: str, fiscal_year: int, report_code: str) -> list[dict[str, Any]]:
        last_error: Exception | None = None
        for fs_div in ("CFS", "OFS"):
            try:
                data = self._get_json("fnlttSinglAcntAll.json", {"corp_code": corp_code, "bsns_year": str(fiscal_year), "reprt_code": report_code, "fs_div": fs_div})
            except Exception as exc:
                last_error = exc
                continue
            rows = data.get("list") or []
            if isinstance(rows, list) and rows:
                return rows
        if last_error:
            raise last_error
        return []

    def get_largest_shareholder_status(self, corp_code: str, fiscal_year: int, report_code: str = "11011") -> list[dict[str, Any]]:
        data = self._get_json("hyslrSttus.json", {"corp_code": corp_code, "bsns_year": str(fiscal_year), "reprt_code": report_code})
        rows = data.get("list") or []
        return rows if isinstance(rows, list) else []

    def get_major_stock_reports(self, corp_code: str) -> list[dict[str, Any]]:
        data = self._get_json("majorstock.json", {"corp_code": corp_code})
        rows = data.get("list") or []
        return rows if isinstance(rows, list) else []
