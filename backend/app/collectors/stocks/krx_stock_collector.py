from __future__ import annotations

from math import ceil
from time import perf_counter
from typing import Any
import logging
import re
from urllib.parse import quote
import xml.etree.ElementTree as ET

import requests

from backend.app.core.config import (
    DATA_API_BASE_URL,
    DATA_API_KEY_MODE,
    DATA_API_MAX_PAGES,
    DATA_API_SERVICE_KEY,
    DATA_API_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)


class KrxStockCollector:
    def __init__(self) -> None:
        self.base_url = DATA_API_BASE_URL
        self.service_key = DATA_API_SERVICE_KEY or ""
        self.key_mode = DATA_API_KEY_MODE
        self.timeout = DATA_API_TIMEOUT_SECONDS
        self.max_pages = DATA_API_MAX_PAGES

    def collect_all(self) -> list[dict[str, str | None]]:
        if not self.service_key:
            raise ValueError(
                "DATA_API_SERVICE_KEY is not configured. "
                "Set DATA_API_SERVICE_KEY in .env. (Encoded key recommended for URL query mode)"
            )

        first_payload = self._request_page(page_no=1, num_of_rows=1000)
        first_items = self._extract_items(first_payload)
        total_count = self._extract_total_count(first_payload)
        total_pages = max(1, ceil(total_count / 1000)) if total_count > 0 else 1
        total_pages = min(total_pages, max(1, self.max_pages))

        rows = self._normalize_items(first_items)
        seen_codes = {row["stock_code"] for row in rows if row.get("stock_code")}
        for page_no in range(2, total_pages + 1):
            payload = self._request_page(page_no=page_no, num_of_rows=1000)
            items = self._extract_items(payload)
            if not items:
                break
            normalized_page = self._normalize_items(items)
            new_count = 0
            for row in normalized_page:
                code = row.get("stock_code")
                if not code or code in seen_codes:
                    continue
                rows.append(row)
                seen_codes.add(code)
                new_count += 1
            if new_count == 0:
                break

        filtered = [row for row in rows if row.get("market") in {"KOSPI", "KOSDAQ"}]
        kospi_count = sum(1 for row in filtered if row.get("market") == "KOSPI")
        kosdaq_count = sum(1 for row in filtered if row.get("market") == "KOSDAQ")
        skipped_count = len(rows) - len(filtered)
        logger.info(
            "[KRX_STOCK_SYNC] completed total_items=%s totalCount=%s kospi=%s kosdaq=%s skipped=%s",
            len(rows),
            total_count,
            kospi_count,
            kosdaq_count,
            skipped_count,
        )
        if not filtered:
            raise ValueError("KRX API returned no valid KOSPI/KOSDAQ items from full listed data")
        return filtered

    def collect_by_market(self, market: str) -> list[dict[str, str | None]]:
        normalized_market = market.strip().upper()
        rows = self.collect_all()
        filtered = [row for row in rows if row.get("market") == normalized_market]
        if not filtered:
            raise ValueError(f"KRX API returned 0 items for market={normalized_market}")
        return filtered

    def _request_page(self, page_no: int, num_of_rows: int) -> dict[str, Any]:
        logger.info("[KRX_STOCK_SYNC] request page=%s numOfRows=%s", page_no, num_of_rows)
        base_params = {
            "resultType": "json",
            "numOfRows": num_of_rows,
            "pageNo": page_no,
        }

        if self.key_mode == "decoded":
            url = self.base_url
            params = {"serviceKey": self.service_key, **base_params}
        else:
            joiner = "&" if "?" in self.base_url else "?"
            encoded_key = quote(self.service_key, safe="%")
            url = f"{self.base_url}{joiner}serviceKey={encoded_key}"
            params = base_params

        started = perf_counter()
        try:
            response = requests.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise ValueError(
                "Failed to call KRX listed-info API. "
                "Check network, DATA_API_BASE_URL, and key type (Encoding/Decoding)."
            ) from exc
        if response.status_code >= 400:
            raise ValueError(
                f"KRX API HTTP error status={response.status_code}. "
                "Check DATA_API_KEY_MODE and service key type (Encoding/Decoding)."
            )
        elapsed = perf_counter() - started

        content_type = response.headers.get("content-type", "").lower()
        text = response.text or ""
        if "json" in content_type or text.strip().startswith("{"):
            data = response.json()
        else:
            data = self._xml_to_dict(text)

        header = (((data.get("response") or {}).get("header")) or {}) if isinstance(data, dict) else {}
        result_code = str(header.get("resultCode", "00"))
        if result_code not in {"00", "0"}:
            result_msg = header.get("resultMsg", "unknown KRX API error")
            raise ValueError(
                "KRX API authentication/request failed "
                f"(code={result_code}, message={result_msg}). "
                "Try Encoding key with DATA_API_KEY_MODE=encoded "
                "or Decoding key with DATA_API_KEY_MODE=decoded."
            )

        items_count = len(self._extract_items(data))
        total_count = self._extract_total_count(data)
        logger.info(
            "[KRX_STOCK_SYNC] response page=%s status=%s elapsed=%.2fs items=%s totalCount=%s",
            page_no,
            response.status_code,
            elapsed,
            items_count,
            total_count,
        )
        return data

    def _extract_items(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        body = (((data.get("response") or {}).get("body")) or {}) if isinstance(data, dict) else {}
        items = body.get("items")
        if isinstance(items, dict):
            item = items.get("item")
            if isinstance(item, list):
                return [x for x in item if isinstance(x, dict)]
            if isinstance(item, dict):
                return [item]
        return []

    def _extract_total_count(self, data: dict[str, Any]) -> int:
        body = (((data.get("response") or {}).get("body")) or {}) if isinstance(data, dict) else {}
        raw = body.get("totalCount")
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0

    def _normalize_items(self, items: list[dict[str, Any]]) -> list[dict[str, str | None]]:
        normalized: list[dict[str, str | None]] = []
        for raw in items:
            stock_code = str(raw.get("srtnCd", "")).strip()
            stock_name = str(raw.get("itmsNm", "")).strip()
            market = self._normalize_market(str(raw.get("mrktCtg", "")).strip())
            if not stock_code or not stock_name or market not in {"KOSPI", "KOSDAQ"}:
                continue
            security_type = self._classify_security_type(stock_name, stock_code, market)
            normalized.append(
                {
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                    "market": market,
                    "security_type": security_type,
                    "isin_code": self._to_opt_str(raw.get("isinCd")),
                    "corp_name": self._to_opt_str(raw.get("corpNm")) or stock_name,
                    "corp_reg_no": self._to_opt_str(raw.get("crno")),
                    "source": "KRX_LISTED_INFO",
                }
            )
        return normalized

    def _classify_security_type(self, stock_name: str, stock_code: str, market: str) -> str:
        _ = stock_code, market
        name = stock_name.strip()
        name_u = name.upper()

        etf_provider_keywords = [
            "KODEX",
            "TIGER",
            "ACE",
            "SOL",
            "KBSTAR",
            "RISE",
            "HANARO",
            "ARIRANG",
            "KOSEF",
            "PLUS",
            "TIMEFOLIO",
        ]
        etf_direct_keywords = ["ETF"]
        etf_theme_keywords = ["200", "2차전지", "미국", "나스닥", "S&P", "국고채", "채권", "선물", "인버스", "레버리지"]

        if any(k in name_u for k in etf_provider_keywords):
            return "etf"
        if any(k in name_u for k in etf_direct_keywords):
            return "etf"
        if any(theme in name for theme in etf_theme_keywords) and any(provider in name_u for provider in etf_provider_keywords):
            return "etf"

        if "ETN" in name_u:
            return "etn"

        if "스팩" in name or "SPAC" in name_u or "기업인수목적" in name:
            return "spac"

        if "리츠" in name or "REIT" in name_u:
            return "reit"

        if name.endswith("우"):
            return "preferred_stock"
        preferred_patterns = ["우B", "1우", "2우", "3우", "우선주"]
        if any(p in name for p in preferred_patterns):
            return "preferred_stock"
        if re.search(r"\d+우$", name):
            return "preferred_stock"
        return "common_stock"

    def _normalize_market(self, value: str) -> str:
        v = value.upper().replace(" ", "")
        if "KOSPI" in v:
            return "KOSPI"
        if "KOSDAQ" in v:
            return "KOSDAQ"
        if "KONEX" in v:
            return "KONEX"
        if "유가증권" in value:
            return "KOSPI"
        if "코스닥" in value:
            return "KOSDAQ"
        if "코넥스" in value:
            return "KONEX"
        return v

    def _to_opt_str(self, value: Any) -> str | None:
        if value is None:
            return None
        v = str(value).strip()
        return v or None

    def _xml_to_dict(self, xml_text: str) -> dict[str, Any]:
        root = ET.fromstring(xml_text)
        response_node = root if root.tag == "response" else root.find("response")
        if response_node is None:
            raise ValueError("KRX API returned invalid XML response")

        def node_text(node: ET.Element | None) -> str | None:
            if node is None or node.text is None:
                return None
            return node.text.strip()

        header_node = response_node.find("header")
        body_node = response_node.find("body")
        result: dict[str, Any] = {
            "response": {
                "header": {
                    "resultCode": node_text(header_node.find("resultCode") if header_node is not None else None),
                    "resultMsg": node_text(header_node.find("resultMsg") if header_node is not None else None),
                },
                "body": {
                    "items": {"item": []},
                    "totalCount": node_text(body_node.find("totalCount") if body_node is not None else None),
                },
            }
        }
        if body_node is None:
            return result

        items_node = body_node.find("items")
        if items_node is None:
            return result
        item_nodes = items_node.findall("item")
        parsed_items: list[dict[str, Any]] = []
        for item_node in item_nodes:
            parsed_items.append({child.tag: (child.text or "").strip() for child in list(item_node)})
        result["response"]["body"]["items"]["item"] = parsed_items
        return result
