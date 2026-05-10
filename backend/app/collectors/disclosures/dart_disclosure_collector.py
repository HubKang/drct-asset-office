from __future__ import annotations

import json
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from pathlib import Path

import requests

from backend.app.collectors.disclosures.base_disclosure_collector import BaseDisclosureCollector
from backend.app.core.config import DART_API_KEY, DART_RAW_DIR, PROJECT_ROOT


class DartDisclosureCollector(BaseDisclosureCollector):
    corp_code_url = "https://opendart.fss.or.kr/api/corpCode.xml"
    list_url = "https://opendart.fss.or.kr/api/list.json"

    def __init__(self) -> None:
        self.api_key = DART_API_KEY or ""
        self.raw_dir = self._resolve_raw_dir()
        self.corp_codes_dir = self.raw_dir / "corp_codes"
        self.disclosures_dir = self.raw_dir / "disclosures"
        self.corp_codes_dir.mkdir(parents=True, exist_ok=True)
        self.disclosures_dir.mkdir(parents=True, exist_ok=True)

    @property
    def name(self) -> str:
        return "dart_disclosure_collector"

    def _resolve_raw_dir(self) -> Path:
        base = Path(DART_RAW_DIR)
        if not base.is_absolute():
            base = PROJECT_ROOT / base
        return base

    def _validate_api_key(self) -> None:
        if not self.api_key:
            raise ValueError("DART_API_KEY is required")

    def ensure_corp_code_file(self, force_download: bool = False) -> Path:
        self._validate_api_key()
        zip_path = self.corp_codes_dir / "corpCode.zip"
        xml_path = self.corp_codes_dir / "CORPCODE.xml"

        if xml_path.exists() and not force_download:
            return xml_path

        response = requests.get(
            self.corp_code_url,
            params={"crtfc_key": self.api_key},
            timeout=30,
        )
        response.raise_for_status()
        zip_path.write_bytes(response.content)

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            if not names:
                raise ValueError("corpCode.zip is empty")
            member = "CORPCODE.xml" if "CORPCODE.xml" in names else names[0]
            with zf.open(member) as src, xml_path.open("wb") as dst:
                dst.write(src.read())

        return xml_path

    def _find_in_xml(self, xml_path: Path, stock_code: str) -> str | None:
        code = (stock_code or "").strip().zfill(6)
        root = ET.parse(xml_path).getroot()
        for item in root.findall("list"):
            stock_code_node = (item.findtext("stock_code") or "").strip()
            if stock_code_node == code:
                corp_code = (item.findtext("corp_code") or "").strip()
                return corp_code or None
        return None

    def find_corp_code_by_stock_code(self, stock_code: str) -> str | None:
        xml_path = self.corp_codes_dir / "CORPCODE.xml"
        if not xml_path.exists():
            xml_path = self.ensure_corp_code_file(force_download=False)

        try:
            corp_code = self._find_in_xml(xml_path, stock_code)
            if corp_code:
                return corp_code
        except ET.ParseError:
            pass

        # Cached XML might be stale/corrupted; refresh once and retry.
        xml_path = self.ensure_corp_code_file(force_download=True)
        try:
            return self._find_in_xml(xml_path, stock_code)
        except ET.ParseError as exc:
            raise ValueError("CORPCODE.xml parse failed") from exc

    def collect_by_corp_code(self, corp_code: str, bgn_de: str, end_de: str, page_count: int = 100) -> dict:
        self._validate_api_key()

        params = {
            "crtfc_key": self.api_key,
            "corp_code": corp_code,
            "bgn_de": bgn_de,
            "end_de": end_de,
            "page_no": 1,
            "page_count": page_count,
            "sort": "date",
            "sort_mth": "desc",
        }
        response = requests.get(self.list_url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        status = str(data.get("status", ""))
        if status not in {"000", "013"}:
            message = data.get("message") or "OpenDART API error"
            raise ValueError(f"DART list API error: {message}")

        return {
            "provider": "dart_disclosure",
            "corp_code": corp_code,
            "bgn_de": bgn_de,
            "end_de": end_de,
            "page_count": page_count,
            "status": status,
            "total_count": int(data.get("total_count") or 0),
            "page_no": int(data.get("page_no") or 1),
            "total_page": int(data.get("total_page") or 0),
            "list": data.get("list", []),
            "response": data,
        }

    def save_disclosure_response(self, stock_code: str, response_payload: dict) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = self.disclosures_dir / f"{stock_code}_{ts}_response.json"
        file_path.write_text(json.dumps(response_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(file_path.relative_to(PROJECT_ROOT)).replace("\\", "/")
