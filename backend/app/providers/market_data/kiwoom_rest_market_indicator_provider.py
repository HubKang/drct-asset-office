from __future__ import annotations

from datetime import date, datetime
from typing import Any

from backend.app.clients.kiwoom import KiwoomRestClient
from backend.app.core import config


class KiwoomRestMarketIndicatorProvider:
    def __init__(self) -> None:
        self.client = KiwoomRestClient()
        self.index_api_id = config.KIWOOM_REST_MARKET_INDEX_API_ID
        self.index_path = config.KIWOOM_REST_MARKET_INDEX_PATH
        self.code_field = config.KIWOOM_REST_MARKET_INDEX_CODE_FIELD
        self.market_field = config.KIWOOM_REST_MARKET_INDEX_MARKET_FIELD
        self.daily_api_id = config.KIWOOM_REST_MARKET_DAILY_API_ID
        self.daily_path = config.KIWOOM_REST_MARKET_DAILY_PATH
        self.stock_basic_api_id = "ka10001"
        self.stock_basic_path = "/api/dostk/stkinfo"
        self.stock_daily_trade_api_id = "ka10015"
        self.stock_daily_trade_path = "/api/dostk/stkinfo"
        self.stock_foreign_ratio_api_id = "ka10009"
        self.stock_foreign_ratio_path = "/api/dostk/frgnistt"
        self.stock_foreign_ratio_fallback_api_id = "ka10008"
        self.stock_foreign_ratio_basic_fallback_api_id = "ka10001"

    def get_market_overview(self) -> dict[str, Any]:
        kospi = self._fetch_index(
            code=config.KIWOOM_REST_MARKET_KOSPI_CODE,
            market_type=config.KIWOOM_REST_MARKET_KOSPI_TYPE,
            label="KOSPI",
        )
        kosdaq = self._fetch_index(
            code=config.KIWOOM_REST_MARKET_KOSDAQ_CODE,
            market_type=config.KIWOOM_REST_MARKET_KOSDAQ_TYPE,
            label="KOSDAQ",
        )
        base_date = kospi.get("base_date") or kosdaq.get("base_date") or date.today().isoformat()

        message = None
        if kospi.get("index_value") is None and kosdaq.get("index_value") is None:
            message = "Kiwoom REST market overview response received, but index fields were not mapped."

        return {
            "source": "kiwoom_rest",
            "base_date": base_date,
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "kospi": kospi,
            "kosdaq": kosdaq,
            "message": message,
        }

    def get_stock_market_metrics(self, *, stock_code: str, market: str | None = None, base_dt: str | None = None) -> dict[str, Any]:
        basic = self.get_stock_basic_info(stock_code=stock_code)
        daily = self.get_stock_daily_trade_detail(stock_code=stock_code, base_dt=base_dt)
        foreign = self.get_foreign_ownership_ratio_with_source(stock_code=stock_code)

        trade_date = daily.get("trade_date") or date.today().isoformat()
        return {
            "trade_date": trade_date,
            "market": market,
            "close_price": daily.get("close_price") or basic.get("close_price"),
            "market_cap": basic.get("market_cap"),
            "listed_shares": basic.get("listed_shares"),
            "trading_volume": daily.get("trading_volume") or basic.get("trading_volume"),
            "trading_value": daily.get("trading_value"),
            "foreign_ownership_ratio": foreign.get("value"),
            "foreign_ownership_api_id": foreign.get("api_id"),
            "used_api_ids": [self.stock_basic_api_id, self.stock_daily_trade_api_id, foreign.get("api_id") or self.stock_foreign_ratio_api_id],
        }

    def get_stock_basic_info(self, *, stock_code: str) -> dict[str, Any]:
        payload = self._post(
            path=self.stock_basic_path,
            api_id=self.stock_basic_api_id,
            body={"stk_cd": stock_code},
        )
        row = self._extract_first_row(payload) or {}
        raw_market_cap = self._get_first_int(row, ("mac",))
        market_cap = None if raw_market_cap is None else int(raw_market_cap)
        return {
            "close_price": self._get_first_float(row, ("cur_prc",)),
            "change_rate": self._get_first_float(row, ("flu_rt", "chg_rt", "change_rate")),
            "market_cap": market_cap,
            "listed_shares": self._get_first_int(row, ("flo_stk",)),
            "trading_volume": self._get_first_int(row, ("trde_qty",)),
            "trading_value": self._to_krw_from_million_unit(self._get_first_int(row, ("trde_prica", "acml_tr_pbmn", "trading_value"))),
            "foreign_exhaustion_rate": self._get_first_str(row, ("for_exh_rt",)),
        }

    def get_stock_daily_trade_detail(self, *, stock_code: str, base_dt: str | None = None) -> dict[str, Any]:
        payload = self._post(
            path=self.stock_daily_trade_path,
            api_id=self.stock_daily_trade_api_id,
            body={
                "stk_cd": stock_code,
                "strt_dt": (base_dt or datetime.now().strftime("%Y%m%d")).replace("-", ""),
            },
        )

        row = self._extract_stock_daily_trade_row(payload) or {}
        trade_date = self._normalize_date(self._get_first_str(row, ("dt", "trade_date", "base_date")))
        trading_value = self._to_krw_from_million_unit(self._get_first_int(row, ("trde_prica",)))
        return {
            "trade_date": trade_date,
            "close_price": self._get_first_float(row, ("close_pric", "cur_prc")),
            "trading_volume": self._get_first_int(row, ("trde_qty",)),
            "trading_value": trading_value,
        }

    def get_foreign_ownership_ratio(self, *, stock_code: str) -> float | None:
        return self.get_foreign_ownership_ratio_with_source(stock_code=stock_code).get("value")

    def get_foreign_ownership_ratio_with_source(self, *, stock_code: str) -> dict[str, Any]:
        payload = self._post(
            path=self.stock_foreign_ratio_path,
            api_id=self.stock_foreign_ratio_api_id,
            body={"stk_cd": stock_code},
        )
        row = self._extract_first_row(payload) or {}
        if isinstance(payload.get("frgnr_qota_rt"), (str, int, float)):
            value = self._to_float(payload.get("frgnr_qota_rt"))
            if value is not None:
                return {"value": value, "api_id": self.stock_foreign_ratio_api_id}
        value = self._get_first_float(row, ("frgnr_qota_rt",))
        if value is not None:
            return {"value": value, "api_id": self.stock_foreign_ratio_api_id}

        fallback_payload = self._post(
            path=self.stock_foreign_ratio_path,
            api_id=self.stock_foreign_ratio_fallback_api_id,
            body={"stk_cd": stock_code},
        )
        fallback_row = self._extract_stock_foreign_row(fallback_payload) or {}
        fallback_value = self._get_first_float(fallback_row, ("wght", "limit_exh_rt"))
        if fallback_value is not None:
            return {"value": fallback_value, "api_id": self.stock_foreign_ratio_fallback_api_id}

        basic = self.get_stock_basic_info(stock_code=stock_code)
        basic_value = self._to_float(basic.get("foreign_exhaustion_rate"))
        if basic_value is not None:
            return {"value": basic_value, "api_id": self.stock_foreign_ratio_basic_fallback_api_id}

        return {"value": None, "api_id": self.stock_foreign_ratio_api_id}

    def _post(self, *, path: str, api_id: str, body: dict[str, Any]) -> dict[str, Any]:
        response = self.client.post_json(path, api_id=api_id, body=body)
        payload = response.json_body
        if str(payload.get("return_code", "")).strip() not in ("0", ""):
            return {}
        return payload

    def _fetch_index(self, *, code: str, market_type: str, label: str) -> dict[str, Any]:
        body = {
            self.market_field: market_type,
            self.code_field: code,
        }
        response = self.client.post_json(
            self.index_path,
            api_id=self.index_api_id,
            body=body,
        )
        payload = response.json_body
        if str(payload.get("return_code", "")).strip() not in ("0", ""):
            return self._empty_row(label)

        row = self._extract_first_row(payload)
        if row is None:
            return self._empty_row(label)

        realtime_list = row.get("inds_cur_prc_tm") if isinstance(row, dict) else None
        latest_tick = None
        if isinstance(realtime_list, list) and realtime_list:
            latest_tick = realtime_list[0] if isinstance(realtime_list[0], dict) else None

        daily_base_date = self._fetch_daily_base_date(code=code)

        mapped = {
            "market": label,
            "index_value": self._get_first_float(row, ("cur_prc",)) or self._get_first_float(latest_tick or {}, ("cur_prc_n",)),
            "change_value": self._get_first_float(row, ("pred_pre",)) or self._get_first_float(latest_tick or {}, ("pred_pre_n",)),
            "change_sign": self._get_first_str(row, ("pred_pre_sig",)) or self._get_first_str(latest_tick or {}, ("pred_pre_sig_n",)),
            "change_rate": self._get_first_float(row, ("flu_rt",)) or self._get_first_float(latest_tick or {}, ("flu_rt_n",)),
            "volume": self._get_first_int(row, ("trde_qty",)) or self._get_first_int(latest_tick or {}, ("trde_qty_n", "acc_trde_qty_n")),
            "trading_value": self._get_first_int(row, ("trde_prica",)),
            "base_time": self._get_first_str(latest_tick or {}, ("tm_n",)),
            "base_date": daily_base_date or date.today().isoformat(),
        }

        if mapped["index_value"] is None:
            return self._empty_row(label, mapped.get("base_date"))

        return mapped

    def _fetch_daily_base_date(self, *, code: str) -> str | None:
        body = {
            self.code_field: code,
            "base_dt": datetime.now().strftime("%Y%m%d"),
        }
        try:
            response = self.client.post_json(
                self.daily_path,
                api_id=self.daily_api_id,
                body=body,
            )
        except Exception:
            return None
        payload = response.json_body
        if str(payload.get("return_code", "")).strip() not in ("0", ""):
            return None

        row = self._extract_daily_row(payload)
        if row is None:
            return None
        raw = self._get_first_str(row, ("dt", "trade_date", "base_date"))
        return self._normalize_date(raw)

    @staticmethod
    def _extract_first_row(payload: dict[str, Any]) -> dict[str, Any] | None:
        # ka20001 may return fields directly at top-level.
        if any(key in payload for key in ("cur_prc", "pred_pre", "flu_rt", "trde_qty", "trde_prica", "inds_cur_prc_tm")):
            return payload
        for key in ("output", "output1", "output2", "items", "data"):
            value = payload.get(key)
            if isinstance(value, dict):
                return value
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return value[0]
        return None

    @staticmethod
    def _extract_daily_row(payload: dict[str, Any]) -> dict[str, Any] | None:
        for key in ("inds_dt_pole_qry", "output", "output1", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return value[0]
            if isinstance(value, dict):
                for nested in value.values():
                    if isinstance(nested, list) and nested and isinstance(nested[0], dict):
                        return nested[0]
        return None

    @staticmethod
    def _extract_stock_daily_trade_row(payload: dict[str, Any]) -> dict[str, Any] | None:
        for key in ("daly_trde_dtl", "output", "output1", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return value[0]
            if isinstance(value, dict):
                for nested in value.values():
                    if isinstance(nested, list) and nested and isinstance(nested[0], dict):
                        return nested[0]
        return None

    @staticmethod
    def _extract_stock_foreign_row(payload: dict[str, Any]) -> dict[str, Any] | None:
        for key in ("stk_frgnr", "output", "output1", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return value[0]
            if isinstance(value, dict):
                for nested in value.values():
                    if isinstance(nested, list) and nested and isinstance(nested[0], dict):
                        return nested[0]
        return None

    @staticmethod
    def _normalize_date(raw: str | None) -> str | None:
        if not raw:
            return None
        cleaned = raw.strip().replace("-", "").replace("/", "").replace(".", "")
        if len(cleaned) != 8 or not cleaned.isdigit():
            return None
        try:
            return datetime.strptime(cleaned, "%Y%m%d").date().isoformat()
        except ValueError:
            return None

    @staticmethod
    def _empty_row(label: str, base_date: str | None = None) -> dict[str, Any]:
        return {
            "market": label,
            "index_value": None,
            "change_value": None,
            "change_sign": None,
            "change_rate": None,
            "volume": None,
            "trading_value": None,
            "base_time": None,
            "base_date": base_date,
        }

    @staticmethod
    def _get_first_str(row: dict[str, Any], keys: tuple[str, ...]) -> str | None:
        for key in keys:
            if key in row and row[key] is not None:
                value = str(row[key]).strip()
                if value:
                    return value
        return None

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None:
            return None
        raw = str(value).replace(",", "").replace("%", "").strip()
        if not raw:
            return None
        try:
            return float(raw)
        except Exception:
            return None

    @staticmethod
    def _to_krw_from_million_unit(value: int | None) -> int | None:
        # Kiwoom trde_prica is provided in million KRW units.
        return None if value is None else int(value) * 1_000_000

    @staticmethod
    def _to_int(value: Any) -> int | None:
        if value is None:
            return None
        raw = str(value).replace(",", "").strip()
        if not raw:
            return None
        try:
            return int(float(raw))
        except Exception:
            return None

    def _get_first_float(self, row: dict[str, Any], keys: tuple[str, ...]) -> float | None:
        for key in keys:
            if key in row:
                value = self._to_float(row.get(key))
                if value is not None:
                    return value
        return None

    def _get_first_int(self, row: dict[str, Any], keys: tuple[str, ...]) -> int | None:
        for key in keys:
            if key in row:
                value = self._to_int(row.get(key))
                if value is not None:
                    return value
        return None
