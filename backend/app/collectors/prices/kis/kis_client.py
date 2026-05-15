from __future__ import annotations

import logging
from typing import Any

import requests

from backend.app.collectors.prices.kis.kis_auth_client import KisAuthClient
from backend.app.core.config import KIS_BASE_URL, KIS_PAPER_BASE_URL, KIS_TIMEOUT_SECONDS, KIS_USE_PAPER

logger = logging.getLogger(__name__)


class KisClient:
    def __init__(self) -> None:
        self.auth_client = KisAuthClient()
        self.timeout = KIS_TIMEOUT_SECONDS
        self.base_url = KIS_PAPER_BASE_URL if KIS_USE_PAPER else KIS_BASE_URL

    def get_daily_prices(
        self,
        stock_code: str,
        start_date: str,
        end_date: str,
        adjusted: bool = True,
    ) -> dict[str, Any]:
        token = self.auth_client.get_access_token()
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
        headers = {
            "authorization": f"Bearer {token}",
            "appkey": self.auth_client.app_key,
            "appsecret": self.auth_client.app_secret,
            "tr_id": "FHKST03010100",
            "custtype": "P",
        }
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": stock_code,
            "FID_INPUT_DATE_1": start_date,
            "FID_INPUT_DATE_2": end_date,
            "FID_PERIOD_DIV_CODE": "D",
            "FID_ORG_ADJ_PRC": "0" if adjusted else "1",
        }
        response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
        text_preview = (response.text or "")[:300]
        if response.status_code >= 400:
            logger.error(
                "[KIS] daily request failed status=%s stock=%s start=%s end=%s body=%s",
                response.status_code,
                stock_code,
                start_date,
                end_date,
                text_preview,
            )
            raise ValueError(f"KIS 일봉 조회 실패(status={response.status_code})")
        data = response.json()
        rt_cd = str(data.get("rt_cd") or "")
        msg_cd = str(data.get("msg_cd") or "")
        msg1 = str(data.get("msg1") or "")
        if rt_cd not in {"0", ""}:
            logger.error("[KIS] daily business error stock=%s rt_cd=%s msg_cd=%s msg1=%s", stock_code, rt_cd, msg_cd, msg1)
            raise ValueError(f"KIS 일봉 조회 오류(rt_cd={rt_cd}, msg_cd={msg_cd}, msg={msg1})")
        return data
