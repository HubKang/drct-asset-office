from __future__ import annotations

import logging
import re
from typing import Any

from backend.app.clients.kiwoom import KiwoomRestClient
from backend.app.core import config

logger = logging.getLogger(__name__)


class KrxStockCollector:
    """Collect the current KRX security universe from Kiwoom ka10099."""

    API_ID = "ka10099"
    API_PATH = "/api/dostk/stkinfo"
    MARKET_TYPES = ("0", "10", "8", "60", "70", "90", "6", "2", "4")
    ETN_MARKET_CODES = {"60", "70", "90"}

    def __init__(self, client: KiwoomRestClient | None = None) -> None:
        self.client = client or KiwoomRestClient()

    @property
    def is_configured(self) -> bool:
        return bool(
            config.KIWOOM_REST_ENABLED
            and (config.KIWOOM_REST_ACCESS_TOKEN or (config.KIWOOM_REST_APP_KEY and config.KIWOOM_REST_SECRET_KEY))
        )

    def collect_all(self) -> list[dict[str, str | None]]:
        if not self.is_configured:
            raise ValueError("KIWOOM_REST credentials are not configured for KRX stock master collection")

        rows: list[dict[str, str | None]] = []
        seen_codes: set[str] = set()
        source_counts: dict[str, int] = {}
        for market_type in self.MARKET_TYPES:
            raw_items = self._request_market(market_type)
            source_counts[market_type] = len(raw_items)
            for item in self._normalize_items(raw_items):
                code = str(item.get("stock_code") or "")
                if not code or code in seen_codes:
                    continue
                rows.append(item)
                seen_codes.add(code)

        kospi_count = sum(1 for row in rows if row.get("market") == "KOSPI")
        kosdaq_count = sum(1 for row in rows if row.get("market") == "KOSDAQ")
        logger.info(
            "[KRX_STOCK_SYNC] completed api_id=%s source_counts=%s unique=%s kospi=%s kosdaq=%s",
            self.API_ID,
            source_counts,
            len(rows),
            kospi_count,
            kosdaq_count,
        )
        if not rows:
            raise ValueError("Kiwoom ka10099 returned no valid KRX items")
        return rows

    def collect_by_market(self, market: str) -> list[dict[str, str | None]]:
        normalized_market = market.strip().upper()
        rows = self.collect_all()
        filtered = [row for row in rows if row.get("market") == normalized_market]
        if not filtered:
            raise ValueError(f"Kiwoom ka10099 returned 0 items for market={normalized_market}")
        return filtered

    def _request_market(self, market_type: str) -> list[dict[str, Any]]:
        logger.info(
            "[KRX_STOCK_SYNC] request api_id=%s path=%s mrkt_tp=%s",
            self.API_ID,
            self.API_PATH,
            market_type,
        )
        rows: list[dict[str, Any]] = []
        cont_yn: str | None = None
        next_key: str | None = None
        max_pages = max(int(config.KIWOOM_REST_MAX_PAGES or 1), 1)
        for _page in range(max_pages):
            response = self.client.post_json(
                self.API_PATH,
                api_id=self.API_ID,
                body={"mrkt_tp": market_type},
                cont_yn=cont_yn,
                next_key=next_key,
            )
            return_code = response.json_body.get("return_code")
            if return_code not in (None, 0, "0"):
                raise ValueError(
                    f"Kiwoom ka10099 failed mrkt_tp={market_type}: "
                    f"{response.json_body.get('return_msg') or return_code}"
                )
            page_rows = response.json_body.get("list") or []
            if isinstance(page_rows, list):
                rows.extend(item for item in page_rows if isinstance(item, dict))
            cont_yn = response.cont_yn or None
            next_key = response.next_key or None
            if cont_yn != "Y":
                break
        logger.info(
            "[KRX_STOCK_SYNC] response api_id=%s mrkt_tp=%s items=%s",
            self.API_ID,
            market_type,
            len(rows),
        )
        return rows

    def _normalize_items(self, items: list[dict[str, Any]]) -> list[dict[str, str | None]]:
        normalized: list[dict[str, str | None]] = []
        for raw in items:
            stock_code = str(raw.get("code") or "").strip()
            stock_name = str(raw.get("name") or "").strip()
            market_code = str(raw.get("marketCode") or "").strip()
            market = self._normalize_market(market_code)
            if not stock_code or not stock_name or market not in {"KOSPI", "KOSDAQ"}:
                continue
            normalized.append(
                {
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                    "market": market,
                    "security_type": self._classify_security_type(
                        stock_name,
                        market_code=market_code,
                        market_name=str(raw.get("marketName") or ""),
                        company_class_name=str(raw.get("companyClassName") or ""),
                    ),
                    "isin_code": None,
                    "corp_name": stock_name,
                    "corp_reg_no": None,
                    "source": "KIWOOM_REST_KA10099",
                }
            )
        return normalized

    def _classify_security_type(
        self,
        stock_name: str,
        stock_code: str = "",
        market: str = "",
        *,
        market_code: str = "",
        market_name: str = "",
        company_class_name: str = "",
    ) -> str:
        _ = stock_code, market
        official_market_code = market_code.strip()
        official_market_name = market_name.strip().upper()
        official_company_class = company_class_name.strip().upper()

        if official_market_code == "8" or official_market_name == "ETF":
            return "etf"
        if official_market_code in self.ETN_MARKET_CODES or official_market_name.startswith("ETN"):
            return "etn"
        if official_market_code == "6" or official_market_name == "REIT" or market_name.strip() == "리츠":
            return "reit"
        if official_company_class in {"SPAC", "스팩"}:
            return "spac"
        if official_market_code not in {"0", "10"}:
            return "other"

        # ka10099 has no preferred-share flag. Apply the exchange naming
        # convention only after the official product/company fields above.
        name = stock_name.strip()
        if "스팩" in name or "기업인수목적" in name or "SPAC" in name.upper():
            return "spac"
        if name.endswith("우") or re.search(r"(?:\d+우|우B)$", name) or "우선주" in name:
            return "preferred_stock"
        return "common_stock"

    @staticmethod
    def _normalize_market(market_code: str) -> str:
        if market_code == "10":
            return "KOSDAQ"
        if market_code in {"0", "2", "4", "6", "8", "60", "70", "90"}:
            return "KOSPI"
        return market_code
