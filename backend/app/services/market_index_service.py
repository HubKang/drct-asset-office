from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.providers.market_data.kiwoom_rest_market_indicator_provider import KiwoomRestMarketIndicatorProvider, UnsupportedMarketIndicatorError

DEFAULT_INDEX_NAMES = {
    "KOSPI": "코스피",
    "KOSDAQ": "코스닥",
    "NASDAQ": "나스닥",
    "DOW": "다우지수",
    "SP500": "S&P500",
    "USDKRW": "원/달러",
    "GOLD": "금",
    "WTI": "WTI",
}

STATUS_NOT_COLLECTED = "NOT_COLLECTED"
STATUS_LATEST = "LATEST"
STATUS_ERROR = "ERROR"
STATUS_WAITING = "WAITING"
STATUS_NO_OFFICIAL_INDEX = "NO_OFFICIAL_INDEX"
STATUS_CUSTOM_INDEX_REQUIRED = "CUSTOM_INDEX_REQUIRED"
STATUS_EXCLUDED = "EXCLUDED"
EXCLUDED_COLLECT_STATUSES = {STATUS_NO_OFFICIAL_INDEX, STATUS_CUSTOM_INDEX_REQUIRED, STATUS_EXCLUDED}

logger = logging.getLogger(__name__)


class MarketIndexService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.provider = KiwoomRestMarketIndicatorProvider()

    @staticmethod
    def _today() -> date:
        return date.today()

    @staticmethod
    def _parse_date(value: str | None, fallback: date) -> date:
        if not value:
            return fallback
        for fmt in ("%Y-%m-%d", "%Y%m%d"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid date: {value}")

    @staticmethod
    def _display_name(index_code: str, raw_name: str | None) -> str:
        name = (raw_name or "").strip()
        if name and "?" not in name:
            return name
        code = index_code.strip().upper()
        return DEFAULT_INDEX_NAMES.get(code, code)

    @staticmethod
    def _normalize_status(raw_status: str | None, latest_date: str | None = None) -> str:
        status_value = (raw_status or "").strip().upper()
        if status_value in {"SUCCESS", "LATEST"}:
            return STATUS_LATEST
        if status_value in {"FAILED", "ERROR"}:
            return STATUS_ERROR
        if status_value in {"COLLECTING", "PARTIAL", "WAITING", STATUS_NOT_COLLECTED, STATUS_NO_OFFICIAL_INDEX, STATUS_CUSTOM_INDEX_REQUIRED, STATUS_EXCLUDED}:
            return status_value
        return STATUS_LATEST if latest_date else STATUS_NOT_COLLECTED

    @staticmethod
    def _calc_sma(values: list[float | None], idx: int, window: int) -> float | None:
        if idx + 1 < window:
            return None
        sub = values[idx - window + 1 : idx + 1]
        if any(value is None for value in sub):
            return None
        return round(sum(float(value) for value in sub) / window, 4)

    @staticmethod
    def _return_rate(rows: list[dict[str, Any]], days: int) -> float | None:
        if len(rows) <= days:
            return None
        latest = rows[-1].get("close_price")
        base = rows[-1 - days].get("close_price")
        if latest in (None, 0) or base in (None, 0):
            return None
        return round((float(latest) / float(base) - 1) * 100, 2)

    def list_indexes(self, *, active_only: bool = True, category: str | None = None) -> dict[str, Any]:
        clauses = []
        params: dict[str, Any] = {}
        if active_only:
            clauses.append("mi.is_active = 1")
        if category:
            clauses.append("mi.category = :category")
            params["category"] = category
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.db.execute(
            text(
                f"""
                SELECT mi.*, p.price_date AS latest_price_date, p.close_price AS latest_close_price,
                       p.volume AS latest_volume, p.trading_value AS latest_trading_value
                FROM market_indexes mi
                LEFT JOIN market_index_daily_prices p
                  ON p.index_code = mi.index_code
                 AND p.price_date = (
                    SELECT MAX(price_date) FROM market_index_daily_prices WHERE index_code = mi.index_code
                 )
                {where_sql}
                ORDER BY mi.display_order, mi.index_name
                """
            ),
            params,
        ).mappings().all()
        items = []
        for row in rows:
            row_dict = dict(row)
            price_rows = self._daily_rows(row_dict["index_code"], None, None)
            recent_5d = self._return_rate(price_rows, 5)
            recent_20d = self._return_rate(price_rows, 20)
            latest_date = row_dict.get("latest_price_date")
            latest_close = row_dict.get("latest_close_price")
            items.append(
                {
                    **row_dict,
                    "index_name": self._display_name(row_dict["index_code"], row_dict.get("index_name")),
                    "is_active": bool(row_dict["is_active"]),
                    "collection_status": self._normalize_status(row_dict.get("collection_status"), latest_date),
                    "latest_close_price": latest_close,
                    "latest_close": latest_close,
                    "recent_5d_return": recent_5d,
                    "recent_20d_return": recent_20d,
                    "recent_5d_return_pct": recent_5d,
                    "recent_20d_return_pct": recent_20d,
                }
            )
        return {"items": items}

    def get_daily_prices(self, *, index_code: str, start_date: str | None, end_date: str | None) -> dict[str, Any]:
        master = self._get_index(index_code)
        if not master:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market index not found")
        return {
            "index_code": master["index_code"],
            "index_name": self._display_name(master["index_code"], master.get("index_name")),
            "items": self._daily_rows(master["index_code"], start_date, end_date),
        }

    def compare_indexes(
        self,
        *,
        index_codes: list[str],
        start_date: str | None,
        end_date: str | None,
        normalize: bool,
    ) -> dict[str, Any]:
        codes = [code.strip().upper() for code in index_codes if code.strip()]
        if not codes:
            codes = ["KOSPI", "KOSDAQ"]
        series = []
        for code in codes:
            master = self._get_index(code)
            if not master:
                continue
            rows = self._daily_rows(code, start_date, end_date)
            first_close = next((row["close_price"] for row in rows if row.get("close_price")), None)
            points = []
            for row in rows:
                close_price = row.get("close_price")
                value = None
                if close_price is not None:
                    value = round(float(close_price) / float(first_close) * 100, 4) if normalize and first_close else float(close_price)
                points.append({"date": row["price_date"], "value": value, "close_price": close_price})
            series.append(
                {
                    "index_code": code,
                    "index_name": self._display_name(code, master.get("index_name")),
                    "points": points,
                }
            )
        return {"normalize": normalize, "start_date": start_date, "end_date": end_date, "series": series}

    def _resolve_collect_window(
        self,
        *,
        index_code: str,
        today: date,
        start_date: str | None,
        end_date: str | None,
        period_years: int,
        overlap_days: int,
        force_full_refresh: bool,
    ) -> tuple[str, date, date, str | None]:
        safe_period_years = max(1, period_years)
        safe_overlap_days = max(0, overlap_days)
        end_dt = self._parse_date(end_date, today)
        full_start = end_dt - timedelta(days=safe_period_years * 365)

        if start_date or end_date:
            start_dt = self._parse_date(start_date, full_start)
            if start_dt > end_dt:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="start_date must be earlier than or equal to end_date",
                )
            return "manual_range", start_dt, end_dt, None

        if force_full_refresh:
            return "full_refresh", full_start, end_dt, None

        latest_price_date = self._latest_price_date(index_code)
        if not latest_price_date:
            return "initial_backfill", full_start, end_dt, None

        latest_dt = self._parse_date(str(latest_price_date), end_dt)
        start_dt = latest_dt - timedelta(days=safe_overlap_days)
        return "incremental_overlap", start_dt, end_dt, str(latest_price_date)

    def collect(
        self,
        *,
        index_codes: list[str] | None,
        start_date: str | None,
        end_date: str | None,
        period_years: int = 2,
        overlap_days: int = 7,
        force_full_refresh: bool = False,
    ) -> dict[str, Any]:
        today = self._today()
        preview_end_dt = self._parse_date(end_date, today)
        preview_start_dt = self._parse_date(start_date, preview_end_dt - timedelta(days=max(1, period_years) * 365))
        if preview_start_dt > preview_end_dt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_date must be earlier than or equal to end_date",
            )
        preview_mode = "manual_range" if start_date or end_date else ("full_refresh" if force_full_refresh else "incremental_or_initial")
        masters = self._target_indexes(index_codes)
        include_inactive_policy_rows = index_codes is None
        results = []
        saved_total = 0
        success_count = 0
        failed_count = 0
        waiting_count = 0
        excluded_count = 0
        for master in masters:
            code = master["index_code"]
            index_name = self._display_name(code, master.get("index_name"))
            current_status = self._normalize_status(master.get("collection_status"), master.get("last_collected_date"))
            mode = preview_mode
            start_dt = preview_start_dt
            end_dt = preview_end_dt
            latest_price_date_before = None
            if current_status in EXCLUDED_COLLECT_STATUSES or not bool(master.get("is_active", 1)):
                excluded_count += 1
                message = master.get("error_message") or master.get("description") or '공식 업종지수 수집 대상이 아닙니다.'
                results.append(
                    {
                        "index_code": code,
                        "index_name": index_name,
                        "status": current_status,
                        "collected_count": 0,
                        "saved_count": 0,
                        "from_date": start_dt.isoformat(),
                        "to_date": end_dt.isoformat(),
                        "collection_mode": mode,
                        "latest_price_date_before": latest_price_date_before,
                        "overlap_days": overlap_days,
                        "force_full_refresh": force_full_refresh,
                        "last_collected_date": master.get("last_collected_date"),
                        "error_message": message,
                        "message": message,
                    }
                )
                continue
            try:
                mode, start_dt, end_dt, latest_price_date_before = self._resolve_collect_window(
                    index_code=code,
                    today=today,
                    start_date=start_date,
                    end_date=end_date,
                    period_years=period_years,
                    overlap_days=overlap_days,
                    force_full_refresh=force_full_refresh,
                )
                logger.info(
                    "[MARKET INDEX PRICE DEBUG] index_code=%s index_name=%s mode=%s latest_price_date=%s requested_start_date=%s requested_end_date=%s overlap_days=%s force_full_refresh=%s",
                    code,
                    index_name,
                    mode,
                    latest_price_date_before,
                    start_dt.isoformat(),
                    end_dt.isoformat(),
                    overlap_days,
                    force_full_refresh,
                )
                self._update_collect_status(code, "COLLECTING", None, None)
                mapping = self._get_enabled_provider_mapping(code)
                if mapping is None and code.upper() not in {"KOSPI", "KOSDAQ"}:
                    raise UnsupportedMarketIndicatorError("키움 provider mapping이 아직 설정되지 않은 지표입니다.")
                response = self.provider.get_index_daily_prices(
                    index_code=code,
                    start_date=start_dt.isoformat(),
                    end_date=end_dt.isoformat(),
                    mapping=mapping,
                )
                rows = response.get("items", [])
                if not rows:
                    rows = self._overview_fallback_row(code, start_dt, end_dt)
                saved = self._upsert_daily_rows(code, rows, source_provider="KIWOOM_REST")
                if saved:
                    changed_dates = [str(row.get("price_date")) for row in rows if row.get("price_date")]
                    self._recalculate_moving_averages(code, changed_dates=changed_dates)
                latest_date = self._latest_price_date(code)
                final_status = STATUS_LATEST if latest_date else STATUS_NOT_COLLECTED
                self._update_collect_status(code, final_status, latest_date, None)
                saved_total += saved
                success_count += 1
                results.append(
                    {
                        "index_code": code,
                        "index_name": index_name,
                        "status": final_status,
                        "collected_count": len(rows),
                        "saved_count": saved,
                        "from_date": start_dt.isoformat(),
                        "to_date": end_dt.isoformat(),
                        "collection_mode": mode,
                        "latest_price_date_before": latest_price_date_before,
                        "overlap_days": overlap_days,
                        "force_full_refresh": force_full_refresh,
                        "message": f"{index_name} 지수 데이터를 갱신했습니다.",
                        "last_collected_date": latest_date,
                        "error_message": None,
                    }
                )
            except UnsupportedMarketIndicatorError as exc:
                waiting_count += 1
                message = str(exc)[:900]
                self._update_collect_status(code, STATUS_WAITING, None, message)
                results.append(
                    {
                        "index_code": code,
                        "index_name": index_name,
                        "status": STATUS_WAITING,
                        "collected_count": 0,
                        "saved_count": 0,
                        "from_date": start_dt.isoformat(),
                        "to_date": end_dt.isoformat(),
                        "collection_mode": mode,
                        "latest_price_date_before": latest_price_date_before,
                        "overlap_days": overlap_days,
                        "force_full_refresh": force_full_refresh,
                        "last_collected_date": None,
                        "error_message": message,
                        "message": message,
                    }
                )
            except Exception as exc:
                failed_count += 1
                message = str(exc)[:900]
                self._update_collect_status(code, STATUS_ERROR, None, message)
                results.append(
                    {
                        "index_code": code,
                        "index_name": index_name,
                        "status": STATUS_ERROR,
                        "collected_count": 0,
                        "saved_count": 0,
                        "from_date": start_dt.isoformat(),
                        "to_date": end_dt.isoformat(),
                        "collection_mode": mode,
                        "latest_price_date_before": latest_price_date_before,
                        "overlap_days": overlap_days,
                        "force_full_refresh": force_full_refresh,
                        "last_collected_date": None,
                        "error_message": message,
                        "message": message,
                    }
                )
        if include_inactive_policy_rows:
            excluded_rows = self._excluded_policy_indexes()
            existing_codes = {str(item.get("index_code", "")).upper() for item in results}
            for master in excluded_rows:
                code = str(master["index_code"]).upper()
                if code in existing_codes:
                    continue
                index_name = self._display_name(code, master.get("index_name"))
                current_status = self._normalize_status(master.get("collection_status"), master.get("last_collected_date"))
                excluded_count += 1
                message = master.get("error_message") or master.get("description") or '공식 업종지수 수집 대상이 아닙니다.'
                results.append(
                    {
                        "index_code": code,
                        "index_name": index_name,
                        "status": current_status,
                        "collected_count": 0,
                        "saved_count": 0,
                        "from_date": preview_start_dt.isoformat(),
                        "to_date": preview_end_dt.isoformat(),
                        "collection_mode": preview_mode,
                        "latest_price_date_before": None,
                        "overlap_days": overlap_days,
                        "force_full_refresh": force_full_refresh,
                        "last_collected_date": master.get("last_collected_date"),
                        "error_message": message,
                        "message": message,
                    }
                )
        custom_index_required_count = sum(1 for item in results if item.get("status") == STATUS_CUSTOM_INDEX_REQUIRED)
        return {
            "requested_count": len(masters),
            "success_count": success_count,
            "failed_count": failed_count,
            "waiting_count": waiting_count,
            "excluded_count": excluded_count,
            "custom_index_required_count": custom_index_required_count,
            "saved_count": saved_total,
            "message": f"지수 데이터 갱신 완료: 성공 {success_count}건, 대기 {waiting_count}건, 제외 {excluded_count}건, 실패 {failed_count}건",
            "results": results,
        }

    def list_provider_mappings(self) -> dict[str, Any]:
        rows = self.db.execute(
            text(
                """
                SELECT mi.index_code, mi.index_name, m.id, m.provider, m.api_type, m.provider_symbol,
                       m.market_type, m.indicator_type, m.request_params_json, m.api_id, m.endpoint_url,
                       m.is_enabled, m.is_verified, m.verified_at, m.last_test_status, m.last_test_message, m.last_tested_at
                FROM market_indexes mi
                LEFT JOIN market_index_provider_mappings m
                  ON m.index_code = mi.index_code AND m.provider = mi.provider
                WHERE mi.is_active = 1
                ORDER BY mi.display_order, mi.index_name
                """
            )
        ).mappings().all()
        return {
            "items": [
                {
                    **dict(row),
                    "index_name": self._display_name(str(row["index_code"]), row.get("index_name")),
                    "provider": row.get("provider") or "KIWOOM_REST",
                    "is_enabled": bool(row.get("is_enabled") or 0),
                    "is_verified": bool(row.get("is_verified") or 0),
                    "last_test_status": row.get("last_test_status") or "WAITING",
                    "last_test_message": row.get("last_test_message") or (None if row.get("is_verified") else "키움 provider mapping이 아직 설정되지 않은 지표입니다."),
                }
                for row in rows
            ]
        }

    def upsert_provider_mapping(self, index_code: str, payload: Any) -> dict[str, Any]:
        master = self._get_index(index_code)
        if not master:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market index not found")
        provider = (payload.provider or "KIWOOM_REST").strip().upper()
        request_params_json = self._normalize_request_params_json(payload.request_params_json)
        api_id = (payload.api_id or self._infer_api_id(payload.api_type, master.get("category"))).strip()
        endpoint_url = (payload.endpoint_url or "/api/dostk/chart").strip()
        self.db.execute(
            text(
                """
                INSERT OR IGNORE INTO market_index_provider_mappings
                (index_code, provider, api_type, provider_symbol, market_type, indicator_type, request_params_json,
                 api_id, endpoint_url, is_enabled, is_verified, last_test_status, last_test_message, created_at, updated_at)
                VALUES (:index_code, :provider, :api_type, :provider_symbol, :market_type, :indicator_type,
                        :request_params_json, :api_id, :endpoint_url, :is_enabled, 0, 'WAITING', :message, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            ),
            {
                "index_code": master["index_code"],
                "provider": provider,
                "api_type": payload.api_type,
                "provider_symbol": payload.provider_symbol,
                "market_type": payload.market_type,
                "indicator_type": payload.indicator_type or master.get("category"),
                "request_params_json": request_params_json,
                "api_id": api_id,
                "endpoint_url": endpoint_url,
                "is_enabled": 1 if payload.is_enabled else 0,
                "message": "provider mapping 저장 후 검증이 필요합니다.",
            },
        )
        self.db.execute(
            text(
                """
                UPDATE market_index_provider_mappings
                SET api_type = :api_type, provider_symbol = :provider_symbol, market_type = :market_type,
                    indicator_type = :indicator_type, request_params_json = :request_params_json,
                    api_id = :api_id, endpoint_url = :endpoint_url,
                    is_enabled = :is_enabled,
                    is_verified = CASE WHEN provider_symbol = :provider_symbol AND is_verified = 1 THEN 1 ELSE 0 END,
                    last_test_status = CASE WHEN provider_symbol = :provider_symbol AND is_verified = 1 THEN last_test_status ELSE 'WAITING' END,
                    last_test_message = CASE WHEN provider_symbol = :provider_symbol AND is_verified = 1 THEN last_test_message ELSE 'provider mapping 저장 후 검증이 필요합니다.' END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE index_code = :index_code AND provider = :provider
                """
            ),
            {
                "index_code": master["index_code"],
                "provider": provider,
                "api_type": payload.api_type,
                "provider_symbol": payload.provider_symbol,
                "market_type": payload.market_type,
                "indicator_type": payload.indicator_type or master.get("category"),
                "request_params_json": request_params_json,
                "api_id": api_id,
                "endpoint_url": endpoint_url,
                "is_enabled": 1 if payload.is_enabled else 0,
            },
        )
        self.db.commit()
        return self._get_provider_mapping(master["index_code"], provider) or {}

    def test_provider_mapping(self, index_code: str, payload: Any) -> dict[str, Any]:
        master = self._get_index(index_code)
        if not master:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market index not found")
        provider = (payload.provider or "KIWOOM_REST").strip().upper()
        stored_mapping = self._get_provider_mapping(master["index_code"], provider)
        mapping = dict(stored_mapping or {})
        for key in ("api_type", "provider_symbol", "market_type", "request_params_json", "api_id", "endpoint_url"):
            value = getattr(payload, key, None)
            if value not in (None, ""):
                mapping[key] = value
        mapping["index_code"] = master["index_code"]
        mapping["provider"] = provider
        mapping["is_enabled"] = bool(mapping.get("provider_symbol"))

        if provider != "KIWOOM_REST":
            return self._record_mapping_test(master["index_code"], provider, "ERROR", "지원하지 않는 provider입니다.", [])
        if not mapping.get("provider_symbol"):
            return self._record_mapping_test(master["index_code"], provider, STATUS_WAITING, "키움 provider mapping이 아직 설정되지 않은 지표입니다.", [])

        try:
            end_dt = self._parse_date(payload.end_date, self._today())
            start_dt = self._parse_date(payload.start_date, end_dt - timedelta(days=30))
            response = self.provider.get_index_daily_prices(
                index_code=master["index_code"],
                start_date=start_dt.isoformat(),
                end_date=end_dt.isoformat(),
                mapping=mapping,
            )
            rows = response.get("items", [])
            if not rows:
                return self._record_mapping_test(master["index_code"], provider, "ERROR", "provider mapping 검증 실패: 파싱된 일봉 데이터가 없습니다.", [])
            if payload.save_result:
                saved = self._upsert_daily_rows(master["index_code"], rows, source_provider=provider)
                if saved:
                    self._recalculate_moving_averages(master["index_code"])
            return self._record_mapping_test(master["index_code"], provider, "SUCCESS", "provider mapping 검증 성공", rows, verified=True)
        except UnsupportedMarketIndicatorError as exc:
            return self._record_mapping_test(master["index_code"], provider, STATUS_WAITING, str(exc), [])
        except Exception as exc:
            return self._record_mapping_test(master["index_code"], provider, "ERROR", str(exc)[:900], [])

    def activate_provider_mapping(self, index_code: str, provider: str = "KIWOOM_REST") -> dict[str, Any]:
        master = self._get_index(index_code)
        if not master:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market index not found")
        mapping = self._get_provider_mapping(master["index_code"], provider.upper())
        if not mapping or not mapping.get("is_verified"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="검증 성공한 provider mapping만 활성화할 수 있습니다.")
        self.db.execute(
            text(
                """
                UPDATE market_index_provider_mappings
                SET is_enabled = 1, updated_at = CURRENT_TIMESTAMP
                WHERE index_code = :index_code AND provider = :provider
                """
            ),
            {"index_code": master["index_code"], "provider": provider.upper()},
        )
        self.db.execute(
            text(
                """
                UPDATE market_indexes
                SET collection_status = CASE WHEN collection_status = 'WAITING' THEN 'NOT_COLLECTED' ELSE collection_status END,
                    error_message = CASE WHEN collection_status = 'WAITING' THEN NULL ELSE error_message END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE index_code = :index_code
                """
            ),
            {"index_code": master["index_code"]},
        )
        self.db.commit()
        return self._get_provider_mapping(master["index_code"], provider.upper()) or {}

    def collect_provider_codes(self, *, provider: str = "KIWOOM_REST", market_types: list[str] | None = None) -> dict[str, Any]:
        provider = (provider or "KIWOOM_REST").strip().upper()
        targets = [str(item).strip() for item in (market_types or ["0", "1", "2"]) if str(item).strip()]
        results = []
        success_count = 0
        failed_count = 0
        for market_type in targets:
            try:
                if provider != "KIWOOM_REST":
                    raise ValueError("지원하지 않는 provider입니다.")
                rows = self.provider.fetch_sector_code_list(market_type)
                saved = self._upsert_provider_codes(provider, market_type, rows)
                success_count += 1
                results.append({"market_type": market_type, "count": saved, "status": "SUCCESS", "error_message": None})
            except Exception as exc:
                failed_count += 1
                results.append({"market_type": market_type, "count": 0, "status": "ERROR", "error_message": str(exc)[:900]})
        return {"requested_count": len(targets), "success_count": success_count, "failed_count": failed_count, "results": results}

    def list_provider_codes(self, *, provider: str = "KIWOOM_REST", market_type: str | None = None, keyword: str | None = None) -> dict[str, Any]:
        clauses = ["pc.provider = :provider"]
        params: dict[str, Any] = {"provider": provider.strip().upper()}
        if market_type:
            clauses.append("pc.market_type = :market_type")
            params["market_type"] = market_type.strip()
        if keyword:
            clauses.append("(pc.code LIKE :keyword OR pc.name LIKE :keyword OR COALESCE(pc.group_name, '') LIKE :keyword)")
            params["keyword"] = f"%{keyword.strip()}%"
        rows = self.db.execute(
            text(
                f"""
                SELECT pc.*, m.index_code AS matched_index_code, mi.index_name AS matched_index_name
                FROM market_index_provider_codes pc
                LEFT JOIN market_index_provider_mappings m
                  ON m.provider = pc.provider AND m.provider_symbol = pc.code AND COALESCE(m.api_id, '') = 'ka20006'
                LEFT JOIN market_indexes mi ON mi.index_code = m.index_code
                WHERE {' AND '.join(clauses)}
                ORDER BY pc.market_type, pc.code, pc.name
                """
            ),
            params,
        ).mappings().all()
        return {"items": [{**dict(row), "is_active": bool(row.get("is_active"))} for row in rows]}

    def auto_match_sector_codes(self, *, provider: str = "KIWOOM_REST") -> dict[str, Any]:
        provider = provider.strip().upper()
        targets = self._sector_match_targets()
        results = []
        matched_count = 0
        waiting_count = 0
        for index_code, spec in targets.items():
            master = self._get_index(index_code)
            if not master:
                continue
            current_status = self._normalize_status(master.get("collection_status"), master.get("last_collected_date"))
            if current_status in EXCLUDED_COLLECT_STATUSES or not bool(master.get("is_active", 1)):
                results.append({"index_code": index_code, "index_name": self._display_name(index_code, master.get("index_name")), "matched_code": None, "matched_name": None, "status": current_status, "message": master.get("error_message") or master.get("description")})
                continue
            candidates = self._find_provider_code_candidates(provider, spec["market_type"], spec["keywords"])
            if len(candidates) == 1:
                candidate = candidates[0]
                request_params_json = json.dumps({"inds_cd": candidate["code"]}, ensure_ascii=False)
                self._upsert_mapping_direct(
                    index_code=index_code,
                    provider=provider,
                    api_type="SECTOR_DAILY",
                    provider_symbol=candidate["code"],
                    market_type=spec["market_type"],
                    indicator_type=master.get("category"),
                    request_params_json=request_params_json,
                    api_id="ka20006",
                    endpoint_url="/api/dostk/chart",
                    message="업종코드 자동 매칭 완료. provider mapping 검증이 필요합니다.",
                )
                matched_count += 1
                results.append({"index_code": index_code, "index_name": self._display_name(index_code, master.get("index_name")), "matched_code": candidate["code"], "matched_name": candidate["name"], "status": "MATCHED", "message": "provider mapping 검증이 필요합니다."})
            else:
                waiting_count += 1
                message = "업종코드 자동 매칭 실패"
                if len(candidates) > 1:
                    message = "업종코드 자동 매칭 실패: 후보가 2개 이상입니다."
                self._mark_mapping_waiting(index_code, provider, message)
                results.append({"index_code": index_code, "index_name": self._display_name(index_code, master.get("index_name")), "matched_code": None, "matched_name": None, "status": "WAITING", "message": message})
        return {"matched_count": matched_count, "waiting_count": waiting_count, "results": results}

    @staticmethod
    def _normalize_request_params_json(value: str | None) -> str:
        if not value or not str(value).strip():
            return "{}"
        try:
            parsed = json.loads(str(value))
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="request_params_json must be valid JSON") from exc
        if not isinstance(parsed, dict):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="request_params_json must be a JSON object")
        return json.dumps(parsed, ensure_ascii=False)

    @staticmethod
    def _infer_api_id(api_type: str | None, category: str | None = None) -> str:
        value = (api_type or "").upper()
        if "GOLD" in value or category == "금현물":
            return "ka50081"
        return "ka20006"

    def _upsert_provider_codes(self, provider: str, market_type: str, rows: list[dict[str, Any]]) -> int:
        saved = 0
        for row in rows:
            if not row.get("code") or not row.get("name"):
                continue
            result = self.db.execute(
                text(
                    """
                    INSERT INTO market_index_provider_codes
                    (provider, market_type, market_code, code, name, group_name, source_api_id, is_active, created_at, updated_at)
                    VALUES (:provider, :market_type, :market_code, :code, :name, :group_name, 'ka10101', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT(provider, market_type, code) DO UPDATE SET
                        market_code = excluded.market_code,
                        name = excluded.name,
                        group_name = excluded.group_name,
                        source_api_id = excluded.source_api_id,
                        is_active = 1,
                        updated_at = CURRENT_TIMESTAMP
                    """
                ),
                {"provider": provider, "market_type": market_type, "market_code": row.get("market_code"), "code": row.get("code"), "name": row.get("name"), "group_name": row.get("group_name")},
            )
            saved += max(int(result.rowcount or 0), 0)
        self.db.commit()
        return saved

    def _upsert_mapping_direct(self, *, index_code: str, provider: str, api_type: str, provider_symbol: str, market_type: str | None, indicator_type: str | None, request_params_json: str, api_id: str, endpoint_url: str, message: str) -> None:
        self.db.execute(
            text(
                """
                INSERT OR IGNORE INTO market_index_provider_mappings
                (index_code, provider, api_type, provider_symbol, market_type, indicator_type, request_params_json, api_id, endpoint_url,
                 is_enabled, is_verified, last_test_status, last_test_message, created_at, updated_at)
                VALUES (:index_code, :provider, :api_type, :provider_symbol, :market_type, :indicator_type, :request_params_json, :api_id, :endpoint_url,
                        0, 0, 'WAITING', :message, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            ),
            {"index_code": index_code, "provider": provider, "api_type": api_type, "provider_symbol": provider_symbol, "market_type": market_type, "indicator_type": indicator_type, "request_params_json": request_params_json, "api_id": api_id, "endpoint_url": endpoint_url, "message": message},
        )
        self.db.execute(
            text(
                """
                UPDATE market_index_provider_mappings
                SET api_type = :api_type, provider_symbol = :provider_symbol, market_type = :market_type,
                    indicator_type = :indicator_type, request_params_json = :request_params_json,
                    api_id = :api_id, endpoint_url = :endpoint_url, is_enabled = 0, is_verified = 0,
                    last_test_status = 'WAITING', last_test_message = :message, updated_at = CURRENT_TIMESTAMP
                WHERE index_code = :index_code AND provider = :provider
                """
            ),
            {"index_code": index_code, "provider": provider, "api_type": api_type, "provider_symbol": provider_symbol, "market_type": market_type, "indicator_type": indicator_type, "request_params_json": request_params_json, "api_id": api_id, "endpoint_url": endpoint_url, "message": message},
        )
        self.db.commit()

    def _mark_mapping_waiting(self, index_code: str, provider: str, message: str) -> None:
        self.db.execute(
            text(
                """
                UPDATE market_index_provider_mappings
                SET is_enabled = 0, is_verified = 0, last_test_status = 'WAITING', last_test_message = :message, updated_at = CURRENT_TIMESTAMP
                WHERE index_code = :index_code AND provider = :provider AND is_verified = 0
                """
            ),
            {"index_code": index_code, "provider": provider, "message": message},
        )
        self.db.commit()

    def _find_provider_code_candidates(self, provider: str, market_type: str, keywords: tuple[str, ...]) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT * FROM market_index_provider_codes
                WHERE provider = :provider AND market_type = :market_type AND is_active = 1
                ORDER BY code
                """
            ),
            {"provider": provider, "market_type": market_type},
        ).mappings().all()
        candidates = []
        for row in rows:
            normalized_name = self._normalize_match_text(str(row.get("name") or ""))
            if any(self._normalize_match_text(keyword) in normalized_name for keyword in keywords):
                candidates.append(dict(row))
        return candidates

    @staticmethod
    def _normalize_match_text(value: str) -> str:
        return value.replace(" ", "").replace("\u00b7", "").replace("/", "").replace("&", "").upper()

    @staticmethod
    def _sector_match_targets() -> dict[str, dict[str, Any]]:
        return {
            "KOSPI_ELECTRONICS": {"market_type": "0", "keywords": ("전기전자",)},
            "KOSPI_PHARMA": {"market_type": "0", "keywords": ("의약품", "제약")},
            "KOSPI_CHEMICAL": {"market_type": "0", "keywords": ("화학",)},
            "KOSPI_MACHINERY": {"market_type": "0", "keywords": ("기계", "기계장비")},
            "KOSPI_TRANSPORT_EQUIPMENT": {"market_type": "0", "keywords": ("운수장비", "운송장비부품")},
            "KOSPI_STEEL_METAL": {"market_type": "0", "keywords": ("??",)},
            "KOSPI_FINANCE": {"market_type": "0", "keywords": ("금융업", "금융")},
            "KOSPI_CONSTRUCTION": {"market_type": "0", "keywords": ("건설업", "건설")},
            "KOSPI_TRANSPORT_WAREHOUSE": {"market_type": "0", "keywords": ("운수창고", "운송창고")},
            "KOSPI_SERVICE": {"market_type": "0", "keywords": ("서비스업", "일반서비스")},
            "KOSDAQ_SEMICONDUCTOR": {"market_type": "1", "keywords": ("반도체",)},
            "KOSDAQ_IT_HW": {"market_type": "1", "keywords": ("ITHW", "IT하드웨어", "IT부품")},
            "KOSDAQ_IT_SW_SVC": {"market_type": "1", "keywords": ("ITSW", "소프트웨어", "ITSWSVC", "IT서비스")},
            "KOSDAQ_PHARMA": {"market_type": "1", "keywords": ("제약",)},
            "KOSDAQ_GENERAL_ELECTRONICS": {"market_type": "1", "keywords": ("일반전기전자", "전기전자")},
            "KOSDAQ_MACHINE_EQUIPMENT": {"market_type": "1", "keywords": ("기계장비",)},
            "KOSDAQ_CHEMICAL": {"market_type": "1", "keywords": ("화학",)},
            "KOSDAQ_MEDICAL_PRECISION": {"market_type": "1", "keywords": ("의료정밀기기",)},
        }

    def _get_provider_mapping(self, index_code: str, provider: str = "KIWOOM_REST") -> dict[str, Any] | None:
        row = self.db.execute(
            text("SELECT * FROM market_index_provider_mappings WHERE UPPER(index_code) = :code AND provider = :provider"),
            {"code": index_code.strip().upper(), "provider": provider.strip().upper()},
        ).mappings().first()
        if not row:
            return None
        row_dict = dict(row)
        row_dict["is_enabled"] = bool(row_dict.get("is_enabled"))
        row_dict["is_verified"] = bool(row_dict.get("is_verified"))
        return row_dict

    def _get_enabled_provider_mapping(self, index_code: str, provider: str = "KIWOOM_REST") -> dict[str, Any] | None:
        mapping = self._get_provider_mapping(index_code, provider)
        if not mapping or not mapping.get("is_enabled") or not mapping.get("is_verified"):
            return None
        return mapping

    def _record_mapping_test(self, index_code: str, provider: str, status_value: str, message: str, rows: list[dict[str, Any]], *, verified: bool = False) -> dict[str, Any]:
        sample = rows[:5]
        first_date = rows[0].get("price_date") if rows else None
        last_date = rows[-1].get("price_date") if rows else None
        self.db.execute(
            text(
                """
                INSERT OR IGNORE INTO market_index_provider_mappings
                (index_code, provider, is_enabled, is_verified, last_test_status, last_test_message, last_tested_at, created_at, updated_at)
                VALUES (:index_code, :provider, 0, 0, :status, :message, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            ),
            {"index_code": index_code, "provider": provider, "status": status_value, "message": message},
        )
        self.db.execute(
            text(
                """
                UPDATE market_index_provider_mappings
                SET is_verified = CASE WHEN :verified = 1 THEN 1 ELSE is_verified END,
                    verified_at = CASE WHEN :verified = 1 THEN CURRENT_TIMESTAMP ELSE verified_at END,
                    last_test_status = :status,
                    last_test_message = :message,
                    last_tested_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE index_code = :index_code AND provider = :provider
                """
            ),
            {"index_code": index_code, "provider": provider, "status": status_value, "message": message, "verified": 1 if verified else 0},
        )
        self.db.commit()
        return {
            "index_code": index_code,
            "status": status_value,
            "sample_count": len(rows),
            "first_date": first_date,
            "last_date": last_date,
            "message": message,
            "sample": sample,
        }

    def _get_index(self, index_code: str) -> dict[str, Any] | None:
        row = self.db.execute(
            text("SELECT * FROM market_indexes WHERE UPPER(index_code) = :code"),
            {"code": index_code.strip().upper()},
        ).mappings().first()
        return dict(row) if row else None

    def _target_indexes(self, index_codes: list[str] | None) -> list[dict[str, Any]]:
        if index_codes:
            masters = []
            for code in index_codes:
                master = self._get_index(code)
                if master:
                    masters.append(master)
            if not masters:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="수집할 지수가 없습니다.")
            return masters
        return [
            dict(row)
            for row in self.db.execute(
                text("SELECT * FROM market_indexes WHERE is_active = 1 ORDER BY display_order, index_name")
            ).mappings().all()
        ]

    def _excluded_policy_indexes(self) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in self.db.execute(
                text(
                    """
                    SELECT *
                    FROM market_indexes
                    WHERE collection_status IN ('NO_OFFICIAL_INDEX', 'CUSTOM_INDEX_REQUIRED', 'EXCLUDED')
                    ORDER BY display_order, index_name
                    """
                )
            ).mappings().all()
        ]

    def _daily_rows(self, index_code: str, start_date: str | None, end_date: str | None) -> list[dict[str, Any]]:
        clauses = ["index_code = :code"]
        params: dict[str, Any] = {"code": index_code.strip().upper()}
        if start_date:
            clauses.append("price_date >= :start_date")
            params["start_date"] = start_date
        if end_date:
            clauses.append("price_date <= :end_date")
            params["end_date"] = end_date
        return [
            dict(row)
            for row in self.db.execute(
                text(
                    f"""
                    SELECT id, index_code, price_date, open_price, high_price, low_price, close_price,
                           volume, trading_value, change_rate, ma5, ma20, ma60, ma120, source_provider
                    FROM market_index_daily_prices
                    WHERE {' AND '.join(clauses)}
                    ORDER BY price_date
                    """
                ),
                params,
            ).mappings().all()
        ]

    def _overview_fallback_row(self, index_code: str, start_dt: date, end_dt: date) -> list[dict[str, Any]]:
        overview = self.provider.get_market_overview()
        upper_code = index_code.upper()
        if upper_code not in {"KOSPI", "KOSDAQ"}:
            return []
        key = "kospi" if upper_code == "KOSPI" else "kosdaq"
        row = overview.get(key, {}) if isinstance(overview, dict) else {}
        base_date = row.get("base_date") or end_dt.isoformat()
        if base_date < start_dt.isoformat() or base_date > end_dt.isoformat() or row.get("index_value") is None:
            return []
        close = float(row["index_value"])
        return [
            {
                "price_date": base_date,
                "open_price": close,
                "high_price": close,
                "low_price": close,
                "close_price": close,
                "volume": row.get("volume"),
                "trading_value": row.get("trading_value"),
                "change_rate": row.get("change_rate"),
            }
        ]

    def _upsert_daily_rows(self, index_code: str, rows: list[dict[str, Any]], *, source_provider: str) -> int:
        params: list[dict[str, Any]] = []
        for row in rows:
            if not row.get("price_date") or row.get("close_price") is None:
                continue
            existing = self.db.execute(
                text(
                    """
                    SELECT open_price, high_price, low_price, close_price, volume, trading_value, change_rate
                    FROM market_index_daily_prices
                    WHERE index_code = :index_code AND price_date = :price_date
                    """
                ),
                {"index_code": index_code, "price_date": row.get("price_date")},
            ).mappings().first()
            changed = not existing or any(existing.get(key) != row.get(key) for key in ("open_price", "high_price", "low_price", "close_price", "volume", "trading_value", "change_rate"))
            params.append(
                {
                    "index_code": index_code,
                    "price_date": row.get("price_date"),
                    "open_price": row.get("open_price"),
                    "high_price": row.get("high_price"),
                    "low_price": row.get("low_price"),
                    "close_price": row.get("close_price"),
                    "volume": row.get("volume"),
                    "trading_value": row.get("trading_value"),
                    "change_rate": row.get("change_rate"),
                    "source_provider": source_provider,
                    "revised_at": datetime.now().isoformat(timespec="seconds") if existing and changed else None,
                }
            )
        if not params:
            return 0

        sql = text(
            """
            INSERT INTO market_index_daily_prices
            (index_code, price_date, open_price, high_price, low_price, close_price, volume, trading_value,
             change_rate, source_provider, collected_at, revised_at, created_at, updated_at)
            VALUES (:index_code, :price_date, :open_price, :high_price, :low_price, :close_price, :volume,
                    :trading_value, :change_rate, :source_provider, CURRENT_TIMESTAMP, :revised_at, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(index_code, price_date) DO UPDATE SET
                open_price = excluded.open_price,
                high_price = excluded.high_price,
                low_price = excluded.low_price,
                close_price = excluded.close_price,
                volume = excluded.volume,
                trading_value = excluded.trading_value,
                change_rate = excluded.change_rate,
                source_provider = excluded.source_provider,
                collected_at = CURRENT_TIMESTAMP,
                revised_at = COALESCE(excluded.revised_at, market_index_daily_prices.revised_at),
                updated_at = CASE
                    WHEN market_index_daily_prices.open_price IS NOT excluded.open_price
                      OR market_index_daily_prices.high_price IS NOT excluded.high_price
                      OR market_index_daily_prices.low_price IS NOT excluded.low_price
                      OR market_index_daily_prices.close_price IS NOT excluded.close_price
                      OR market_index_daily_prices.volume IS NOT excluded.volume
                      OR market_index_daily_prices.trading_value IS NOT excluded.trading_value
                      OR market_index_daily_prices.change_rate IS NOT excluded.change_rate
                    THEN CURRENT_TIMESTAMP
                    ELSE market_index_daily_prices.updated_at
                END
            """
        )
        self.db.execute(sql, params)
        self.db.commit()
        logger.info(
            "market index daily price batch upsert completed: index_code=%s rows_count=%s saved_count=%s upsert_mode=batch",
            index_code,
            len(rows),
            len(params),
        )
        return len(params)

    def _recalculate_moving_averages(self, index_code: str, *, changed_dates: list[str] | None = None) -> None:
        rows = self._daily_rows(index_code, None, None)
        update_from_idx = 0
        if changed_dates:
            changed_set = {value for value in changed_dates if value}
            first_idx = next((idx for idx, row in enumerate(rows) if row.get("price_date") in changed_set), 0)
            update_from_idx = max(0, first_idx - 120)
        closes = [row.get("close_price") for row in rows]
        for idx, row in enumerate(rows):
            if idx < update_from_idx:
                continue
            self.db.execute(
                text(
                    """
                    UPDATE market_index_daily_prices
                    SET ma5 = :ma5, ma20 = :ma20, ma60 = :ma60, ma120 = :ma120, updated_at = CURRENT_TIMESTAMP
                    WHERE id = :id
                    """
                ),
                {
                    "id": row["id"],
                    "ma5": self._calc_sma(closes, idx, 5),
                    "ma20": self._calc_sma(closes, idx, 20),
                    "ma60": self._calc_sma(closes, idx, 60),
                    "ma120": self._calc_sma(closes, idx, 120),
                },
            )
        self.db.commit()

    def _latest_price_date(self, index_code: str) -> str | None:
        return self.db.execute(
            text("SELECT MAX(price_date) FROM market_index_daily_prices WHERE index_code = :code"),
            {"code": index_code},
        ).scalar()

    def _update_collect_status(self, index_code: str, status_value: str, latest_date: str | None, message: str | None) -> None:
        self.db.execute(
            text(
                """
                UPDATE market_indexes
                SET collection_status = :status, last_collected_date = COALESCE(:latest_date, last_collected_date),
                    error_message = :message, updated_at = CURRENT_TIMESTAMP
                WHERE index_code = :code
                """
            ),
            {"code": index_code, "status": status_value, "latest_date": latest_date, "message": message},
        )
        self.db.commit()

