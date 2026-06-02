from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.collectors.prices.pykrx_price_collector import PykrxPriceCollector
from backend.app.core.config import now_kst
from backend.app.schemas.market_trend_schema import (
    AssignThemeToTrendEventRequest,
    AssignThemeToTrendEventResponse,
    CollectMarketPriceSnapshotsResponse,
    CollectMarketTrendEventsResponse,
    DailyThemeFlowItem,
    DailyThemeFlowResponse,
    DetectEventsFromSnapshotResponse,
    MarketPriceSnapshotResponse,
    MarketTrendEventResponse,
    TrendDetectionSettingResponse,
    TrendDetectionSettingUpdateRequest,
)

KRW_100M = 100_000_000
ALLOWED_MARKET_SCOPE = {"ALL", "KOSPI", "KOSDAQ"}
ALLOWED_THEME_STATUS = {
    "unassigned",
    "manual_assigned",
    "ai_suggested",
    "auto_assigned_pending_review",
    "user_corrected",
}


def _to_yyyymmdd(value: str) -> str:
    return value.replace("-", "")


def _normalize_stock_code(value: str) -> str:
    code = (value or "").strip()
    if len(code) == 7 and code.startswith("A") and code[1:].isdigit():
        return code[1:]
    return code


def _to_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except Exception:
        return None


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


class MarketTrendService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.pykrx_collector = PykrxPriceCollector()

    @staticmethod
    def _validate_market_scope(value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in ALLOWED_MARKET_SCOPE:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid market_scope")
        return normalized

    @staticmethod
    def _to_krw_100m(value: int | None) -> float | None:
        if value is None:
            return None
        return round(value / KRW_100M, 4)

    def _get_active_setting_row(self) -> dict:
        row = self.db.execute(
            text(
                """
                SELECT *
                FROM trend_detection_settings
                WHERE is_active = 1
                ORDER BY is_default DESC, updated_at DESC, id DESC
                LIMIT 1
                """
            )
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="active trend detection setting not found")
        return dict(row)

    def get_detection_settings(self) -> TrendDetectionSettingResponse:
        row = self._get_active_setting_row()
        return TrendDetectionSettingResponse(
            id=int(row["id"]),
            setting_key=str(row["setting_key"]),
            setting_name=str(row["setting_name"]),
            min_market_cap=int(row["min_market_cap"]),
            min_market_cap_krw_100m=self._to_krw_100m(int(row["min_market_cap"])) or 0.0,
            min_trading_value=int(row["min_trading_value"]),
            min_trading_value_krw_100m=self._to_krw_100m(int(row["min_trading_value"])) or 0.0,
            min_change_rate=float(row["min_change_rate"]),
            min_intraday_range_rate=(
                float(row["min_intraday_range_rate"]) if row["min_intraday_range_rate"] is not None else None
            ),
            use_market_cap=bool(row.get("use_market_cap", 1)),
            use_trading_value=bool(row.get("use_trading_value", 1)),
            use_change_rate=bool(row.get("use_change_rate", 1)),
            use_intraday_range=bool(row["use_intraday_range"]),
            market_scope=str(row["market_scope"]),
            is_active=bool(row["is_active"]),
        )

    def update_detection_settings(self, payload: TrendDetectionSettingUpdateRequest) -> TrendDetectionSettingResponse:
        market_scope = self._validate_market_scope(payload.market_scope)
        row = self._get_active_setting_row()
        now = now_kst()
        min_market_cap = int(round(payload.min_market_cap_krw_100m * KRW_100M))
        min_trading_value = int(round(payload.min_trading_value_krw_100m * KRW_100M))

        self.db.execute(
            text(
                """
                UPDATE trend_detection_settings
                SET min_market_cap = :min_market_cap,
                    min_trading_value = :min_trading_value,
                    min_change_rate = :min_change_rate,
                    min_intraday_range_rate = :min_intraday_range_rate,
                    use_market_cap = :use_market_cap,
                    use_trading_value = :use_trading_value,
                    use_change_rate = :use_change_rate,
                    use_intraday_range = :use_intraday_range,
                    market_scope = :market_scope,
                    is_active = :is_active,
                    updated_at = :updated_at
                WHERE id = :id
                """
            ),
            {
                "min_market_cap": min_market_cap,
                "min_trading_value": min_trading_value,
                "min_change_rate": float(payload.min_change_rate),
                "min_intraday_range_rate": payload.min_intraday_range_rate,
                "use_market_cap": 1 if payload.use_market_cap else 0,
                "use_trading_value": 1 if payload.use_trading_value else 0,
                "use_change_rate": 1 if payload.use_change_rate else 0,
                "use_intraday_range": 1 if payload.use_intraday_range else 0,
                "market_scope": market_scope,
                "is_active": 1 if payload.is_active else 0,
                "updated_at": now,
                "id": int(row["id"]),
            },
        )
        self.db.commit()
        return self.get_detection_settings()

    def collect_snapshots(
        self,
        snapshot_date: str | None,
        market_scope: str,
        collect_mode: str = "stock_loop",
        limit: int | None = None,
    ) -> CollectMarketPriceSnapshotsResponse:
        scope = self._validate_market_scope(market_scope)
        mode = (collect_mode or "stock_loop").strip().lower()
        if mode not in {"stock_loop", "market_bulk", "auto"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid collect_mode")

        date_str = snapshot_date or datetime.now().strftime("%Y-%m-%d")
        yyyymmdd = _to_yyyymmdd(date_str)
        snapshot_time = datetime.now().strftime("%H:%M:%S")
        now = now_kst()

        stocks_query = """
            SELECT id, stock_code, stock_name, market, NULL as market_cap
            FROM stocks
            WHERE is_active = 1
              AND (:scope = 'ALL' OR market = :scope)
            ORDER BY id ASC
        """
        params: dict[str, object] = {"scope": scope}
        if limit is not None:
            stocks_query += " LIMIT :limit"
            params["limit"] = limit

        stock_rows = [dict(r) for r in self.db.execute(text(stocks_query), params).mappings().all()]
        code_to_stock = {_normalize_stock_code(str(r["stock_code"])): r for r in stock_rows}
        requested_count = len(stock_rows)
        failed_markets: list[str] = []
        failed_items: list[str] = []
        rows: list[dict[str, object]] = []

        def _append_row(
            *,
            stock_id: int | None,
            stock_code: str,
            stock_name: str | None,
            market_type: str | None,
            open_price: int | None,
            high_price: int | None,
            low_price: int | None,
            close_price: int | None,
            volume: int | None,
            trading_value: int | None,
            market_cap: int | None,
        ) -> None:
            intraday_change_rate = None
            if open_price is not None and open_price > 0 and close_price is not None:
                intraday_change_rate = round(((close_price - open_price) / open_price) * 100, 4)
            intraday_range_rate = None
            if low_price is not None and low_price > 0 and high_price is not None:
                intraday_range_rate = round(((high_price - low_price) / low_price) * 100, 4)

            rows.append(
                {
                    "snapshot_date": date_str,
                    "snapshot_time": snapshot_time,
                    "source": "pykrx",
                    "market_scope": scope,
                    "stock_id": stock_id,
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                    "market_type": market_type,
                    "open_price": open_price,
                    "high_price": high_price,
                    "low_price": low_price,
                    "close_price": close_price,
                    "volume": volume,
                    "trading_value": trading_value,
                    "market_cap": market_cap,
                    "change_rate": intraday_change_rate,
                    "intraday_range_rate": intraday_range_rate,
                    "created_at": now,
                }
            )

        def _collect_market_bulk() -> None:
            try:
                from pykrx import stock  # type: ignore
            except Exception:
                failed_markets.extend(["KOSPI", "KOSDAQ"] if scope == "ALL" else [scope])
                return

            mpl_dir = Path.cwd() / ".mpltcache"
            mpl_dir.mkdir(parents=True, exist_ok=True)
            os.environ.setdefault("MPLCONFIGDIR", str(mpl_dir.resolve()))
            proxy_keys = ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]
            previous_proxy_values = {k: os.environ.get(k) for k in proxy_keys}
            previous_no_proxy = os.environ.get("NO_PROXY")

            markets = ["KOSPI", "KOSDAQ"] if scope == "ALL" else [scope]
            try:
                for key in proxy_keys:
                    if key in os.environ:
                        del os.environ[key]
                os.environ["NO_PROXY"] = "*"

                for market in markets:
                    try:
                        ohlcv = stock.get_market_ohlcv_by_ticker(yyyymmdd, market=market, alternative=True)
                    except Exception:
                        failed_markets.append(market)
                        continue
                    if ohlcv is None or ohlcv.empty:
                        failed_markets.append(market)
                        continue
                    for ticker, raw in ohlcv.iterrows():
                        code = _normalize_stock_code(str(ticker))
                        stock_row = code_to_stock.get(code)
                        if stock_row is None:
                            stock_row = {"id": None, "stock_name": None, "market": market, "market_cap": None}
                        open_price = _to_int(raw.iloc[0]) if len(raw.index) > 0 else None
                        high_price = _to_int(raw.iloc[1]) if len(raw.index) > 1 else None
                        low_price = _to_int(raw.iloc[2]) if len(raw.index) > 2 else None
                        close_price = _to_int(raw.iloc[3]) if len(raw.index) > 3 else None
                        volume = _to_int(raw.iloc[4]) if len(raw.index) > 4 else None
                        trading_value = _to_int(raw.iloc[5]) if len(raw.index) > 5 else None
                        _append_row(
                            stock_id=stock_row.get("id"),
                            stock_code=code,
                            stock_name=stock_row.get("stock_name"),
                            market_type=market,
                            open_price=open_price,
                            high_price=high_price,
                            low_price=low_price,
                            close_price=close_price,
                            volume=volume,
                            trading_value=trading_value,
                            market_cap=_to_int(stock_row.get("market_cap")),
                        )
            finally:
                for key, value in previous_proxy_values.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
                if previous_no_proxy is None:
                    os.environ.pop("NO_PROXY", None)
                else:
                    os.environ["NO_PROXY"] = previous_no_proxy

        def _collect_stock_loop() -> None:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            for s in stock_rows:
                code = _normalize_stock_code(str(s["stock_code"]))
                if not code:
                    failed_items.append(f"invalid_code:{s['stock_code']}")
                    continue
                try:
                    _, daily = self.pykrx_collector.collect_daily(code, target_date, target_date, adjusted=True)
                except Exception as exc:
                    failed_items.append(f"{code}:{exc.__class__.__name__}")
                    continue
                if not daily:
                    failed_items.append(f"{code}:empty")
                    continue
                row = daily[-1]
                _append_row(
                    stock_id=_to_int(s.get("id")),
                    stock_code=code,
                    stock_name=s.get("stock_name"),
                    market_type=s.get("market"),
                    open_price=_to_int(row.open_price),
                    high_price=_to_int(row.high_price),
                    low_price=_to_int(row.low_price),
                    close_price=_to_int(row.close_price),
                    volume=_to_int(row.volume),
                    trading_value=_to_int(row.trading_value),
                    market_cap=_to_int(s.get("market_cap")),
                )

        if mode == "market_bulk":
            _collect_market_bulk()
        elif mode == "stock_loop":
            _collect_stock_loop()
        else:
            _collect_market_bulk()
            if len(rows) == 0:
                _collect_stock_loop()

        if len(rows) == 0:
            zero_message = "스냅샷 데이터를 가져오지 못했습니다. 기준일, 시장 구분, 수집 방식을 확인해 주세요."
            if mode == "market_bulk":
                zero_message = "전체시장 일괄조회 방식으로 데이터를 가져오지 못했습니다. 현재 환경에서는 종목별 loop 방식을 사용해 주세요."
            return CollectMarketPriceSnapshotsResponse(
                snapshot_date=date_str,
                snapshot_time=snapshot_time,
                source="pykrx",
                market_scope=scope,
                collect_mode=mode,
                requested_count=requested_count,
                collected_count=0,
                inserted_count=0,
                failed_count=len(failed_items),
                skipped_count=max(0, requested_count - len(failed_items)),
                matched_stock_count=0,
                unmatched_stock_count=0,
                failed_markets=failed_markets,
                failed_items=failed_items[:20],
                message=zero_message,
            )

        self.db.execute(text("DELETE FROM market_price_snapshots WHERE source = 'pykrx'"))
        inserted_count = 0
        matched_stock_count = 0
        for row in rows:
            self.db.execute(
                text(
                    """
                    INSERT INTO market_price_snapshots (
                        snapshot_date, snapshot_time, source, market_scope, stock_id, stock_code, stock_name, market_type,
                        open_price, high_price, low_price, close_price, volume, trading_value, market_cap, change_rate,
                        intraday_range_rate, created_at
                    ) VALUES (
                        :snapshot_date, :snapshot_time, :source, :market_scope, :stock_id, :stock_code, :stock_name, :market_type,
                        :open_price, :high_price, :low_price, :close_price, :volume, :trading_value, :market_cap, :change_rate,
                        :intraday_range_rate, :created_at
                    )
                    """
                ),
                row,
            )
            inserted_count += 1
            if row["stock_id"] is not None:
                matched_stock_count += 1
        self.db.commit()

        message = "전체시장 스냅샷 갱신이 완료되었습니다."
        if failed_markets:
            message = "일부 시장 데이터 수집에 실패했습니다. 실패한 시장은 failed_markets에서 확인할 수 있습니다."

        return CollectMarketPriceSnapshotsResponse(
            snapshot_date=date_str,
            snapshot_time=snapshot_time,
            source="pykrx",
            market_scope=scope,
            collect_mode=mode,
            requested_count=requested_count,
            collected_count=len(rows),
            inserted_count=inserted_count,
            failed_count=len(failed_items),
            skipped_count=max(0, requested_count - inserted_count - len(failed_items)),
            matched_stock_count=matched_stock_count,
            unmatched_stock_count=max(0, len(rows) - matched_stock_count),
            failed_markets=failed_markets,
            failed_items=failed_items[:20],
            message=message,
        )
    def list_snapshots(
        self,
        *,
        market_scope: str | None,
        limit: int,
        offset: int,
        keyword: str | None,
        sort_by: str | None,
        sort_order: str | None,
    ) -> list[MarketPriceSnapshotResponse]:
        conditions = ["source = 'pykrx'"]
        params: dict[str, object] = {"limit": limit, "offset": offset}
        if market_scope:
            scope = self._validate_market_scope(market_scope)
            if scope != "ALL":
                conditions.append("market_type = :market_scope")
                params["market_scope"] = scope
        if keyword:
            conditions.append("(stock_code LIKE :keyword OR stock_name LIKE :keyword)")
            params["keyword"] = f"%{keyword.strip()}%"
        allowed_sort_by = {"trading_value", "change_rate", "market_cap", "stock_code", "snapshot_date"}
        order_col = sort_by if sort_by in allowed_sort_by else "trading_value"
        order_dir = "ASC" if (sort_order or "").upper() == "ASC" else "DESC"
        query = f"""
            SELECT snapshot_date, snapshot_time, stock_id, stock_code, stock_name, market_type,
                   close_price, change_rate, trading_value, market_cap, intraday_range_rate
            FROM market_price_snapshots
            WHERE {" AND ".join(conditions)}
            ORDER BY {order_col} {order_dir}, change_rate DESC
            LIMIT :limit OFFSET :offset
        """
        rows = self.db.execute(text(query), params).mappings().all()
        return [MarketPriceSnapshotResponse(**dict(r)) for r in rows]

    def detect_events_from_snapshot(self, snapshot_date: str | None) -> DetectEventsFromSnapshotResponse:
        setting = self._get_active_setting_row()
        date_str = snapshot_date
        if not date_str:
            date_str = self.db.execute(
                text("SELECT MAX(snapshot_date) FROM market_price_snapshots WHERE source='pykrx'")
            ).scalar_one()
        if not date_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="?꾩껜?쒖옣 ?ㅻ깄???곗씠?곌? ?놁뒿?덈떎. 癒쇱? ?꾩껜?쒖옣 ?ㅻ깄?룹쓣 ?섏쭛??二쇱꽭??",
            )

        market_scope = str(setting["market_scope"]).upper()
        use_market_cap = bool(setting.get("use_market_cap", 1))
        use_trading_value = bool(setting.get("use_trading_value", 1))
        use_change_rate = bool(setting.get("use_change_rate", 1))
        use_intraday_range = bool(setting["use_intraday_range"])

        conditions = ["snapshot_date = :snapshot_date", "source = 'pykrx'"]
        if market_scope != "ALL":
            conditions.append("market_type = :market_scope")
        if use_market_cap:
            conditions.append("COALESCE(market_cap, 0) >= :min_market_cap")
        if use_trading_value:
            conditions.append("COALESCE(trading_value, 0) >= :min_trading_value")
        if use_change_rate:
            conditions.append("COALESCE(change_rate, 0) >= :min_change_rate")
        if use_intraday_range:
            conditions.append("COALESCE(intraday_range_rate, 0) >= :min_intraday_range_rate")

        params: dict[str, object] = {
            "snapshot_date": date_str,
            "market_scope": market_scope,
            "min_market_cap": int(setting["min_market_cap"]),
            "min_trading_value": int(setting["min_trading_value"]),
            "min_change_rate": float(setting["min_change_rate"]),
            "min_intraday_range_rate": float(setting["min_intraday_range_rate"] or 0.0),
        }
        source_snapshot_count = int(
            self.db.execute(
                text("SELECT COUNT(*) FROM market_price_snapshots WHERE source='pykrx' AND snapshot_date=:snapshot_date"),
                {"snapshot_date": date_str},
            ).scalar_one()
            or 0
        )
        filtered_rows = self.db.execute(
            text(
                f"""
                SELECT *
                FROM market_price_snapshots
                WHERE {" AND ".join(conditions)}
                ORDER BY COALESCE(trading_value, 0) DESC, COALESCE(change_rate, 0) DESC, stock_code ASC
                """
            ),
            params,
        ).mappings().all()

        if not filtered_rows:
            return DetectEventsFromSnapshotResponse(
                snapshot_date=str(date_str),
                source_snapshot_count=source_snapshot_count,
                filtered_count=0,
                inserted_count=0,
                updated_count=0,
                duplicated_count=0,
                applied_condition={
                    "use_market_cap": use_market_cap,
                    "min_market_cap_krw_100m": self._to_krw_100m(int(setting["min_market_cap"])),
                    "use_trading_value": use_trading_value,
                    "min_trading_value_krw_100m": self._to_krw_100m(int(setting["min_trading_value"])),
                    "use_change_rate": use_change_rate,
                    "min_change_rate": float(setting["min_change_rate"]),
                    "use_intraday_range": use_intraday_range,
                    "min_intraday_range_rate": (
                        float(setting["min_intraday_range_rate"]) if setting["min_intraday_range_rate"] is not None else None
                    ),
                    "market_scope": market_scope,
                },
                message="?꾩옱 議곌굔???대떦?섎뒗 ?섍툒 ?대깽??醫낅ぉ???놁뒿?덈떎. 議곌굔???꾪솕?섍굅???ㅻⅨ 湲곗??쇱쓣 ?좏깮??蹂댁꽭??",
            )

        inserted_count = 0
        updated_count = 0
        now = now_kst()
        for row in filtered_rows:
            stock_id = row["stock_id"]
            if stock_id is None:
                mapped = self.db.execute(
                    text("SELECT id, stock_name, market FROM stocks WHERE stock_code = :stock_code"),
                    {"stock_code": row["stock_code"]},
                ).mappings().first()
                if mapped:
                    stock_id = int(mapped["id"])
            if stock_id is None:
                continue

            existing = self.db.execute(
                text(
                    "SELECT id FROM market_trend_events WHERE trade_date=:trade_date AND stock_id=:stock_id AND event_type='supply_surge'"
                ),
                {"trade_date": date_str, "stock_id": stock_id},
            ).mappings().first()

            if existing:
                self.db.execute(
                    text(
                        """
                        UPDATE market_trend_events
                        SET stock_code=:stock_code,
                            stock_name=COALESCE(stock_name, :stock_name),
                            market_type=:market_type,
                            market_cap=:market_cap,
                            trading_value=:trading_value,
                            change_rate=:change_rate,
                            intraday_range_rate=:intraday_range_rate,
                            detection_setting_id=:detection_setting_id,
                            applied_min_market_cap=:applied_min_market_cap,
                            applied_min_trading_value=:applied_min_trading_value,
                            applied_min_change_rate=:applied_min_change_rate,
                            applied_min_intraday_range_rate=:applied_min_intraday_range_rate,
                            applied_use_market_cap=:applied_use_market_cap,
                            applied_use_trading_value=:applied_use_trading_value,
                            applied_use_change_rate=:applied_use_change_rate,
                            applied_use_intraday_range=:applied_use_intraday_range,
                            detection_source='pykrx_snapshot',
                            updated_at=:updated_at
                        WHERE id=:id
                        """
                    ),
                    {
                        "id": int(existing["id"]),
                        "stock_code": row["stock_code"],
                        "stock_name": row["stock_name"],
                        "market_type": row["market_type"],
                        "market_cap": row["market_cap"],
                        "trading_value": row["trading_value"],
                        "change_rate": row["change_rate"],
                        "intraday_range_rate": row["intraday_range_rate"],
                        "detection_setting_id": int(setting["id"]),
                        "applied_min_market_cap": int(setting["min_market_cap"]),
                        "applied_min_trading_value": int(setting["min_trading_value"]),
                        "applied_min_change_rate": float(setting["min_change_rate"]),
                        "applied_min_intraday_range_rate": setting["min_intraday_range_rate"],
                        "applied_use_market_cap": 1 if use_market_cap else 0,
                        "applied_use_trading_value": 1 if use_trading_value else 0,
                        "applied_use_change_rate": 1 if use_change_rate else 0,
                        "applied_use_intraday_range": int(setting["use_intraday_range"]),
                        "updated_at": now,
                    },
                )
                updated_count += 1
            else:
                self.db.execute(
                    text(
                        """
                        INSERT INTO market_trend_events (
                            trade_date, stock_id, stock_code, stock_name, market_type, market_cap, trading_value, change_rate,
                            intraday_range_rate, event_type, detection_setting_id, applied_min_market_cap, applied_min_trading_value,
                            applied_min_change_rate, applied_min_intraday_range_rate, applied_use_market_cap, applied_use_trading_value,
                            applied_use_change_rate, applied_use_intraday_range, theme_id, theme_status,
                            primary_theme_id, reason_summary, user_memo, is_active, detection_source, created_at, updated_at
                        ) VALUES (
                            :trade_date, :stock_id, :stock_code, :stock_name, :market_type, :market_cap, :trading_value, :change_rate,
                            :intraday_range_rate, 'supply_surge', :detection_setting_id, :applied_min_market_cap, :applied_min_trading_value,
                            :applied_min_change_rate, :applied_min_intraday_range_rate, :applied_use_market_cap, :applied_use_trading_value,
                            :applied_use_change_rate, :applied_use_intraday_range, NULL, 'unassigned',
                            NULL, NULL, NULL, 1, 'pykrx_snapshot', :created_at, :updated_at
                        )
                        """
                    ),
                    {
                        "trade_date": date_str,
                        "stock_id": stock_id,
                        "stock_code": row["stock_code"],
                        "stock_name": row["stock_name"],
                        "market_type": row["market_type"],
                        "market_cap": row["market_cap"],
                        "trading_value": row["trading_value"],
                        "change_rate": row["change_rate"],
                        "intraday_range_rate": row["intraday_range_rate"],
                        "detection_setting_id": int(setting["id"]),
                        "applied_min_market_cap": int(setting["min_market_cap"]),
                        "applied_min_trading_value": int(setting["min_trading_value"]),
                        "applied_min_change_rate": float(setting["min_change_rate"]),
                        "applied_min_intraday_range_rate": setting["min_intraday_range_rate"],
                        "applied_use_market_cap": 1 if use_market_cap else 0,
                        "applied_use_trading_value": 1 if use_trading_value else 0,
                        "applied_use_change_rate": 1 if use_change_rate else 0,
                        "applied_use_intraday_range": int(setting["use_intraday_range"]),
                        "created_at": now,
                        "updated_at": now,
                    },
                )
                inserted_count += 1
        self.db.commit()
        message = "?ㅻ깄??湲곗? ?섍툒 ?대깽??媛먯?媛 ?꾨즺?섏뿀?듬땲??"
        if inserted_count == 0 and updated_count > 0:
            message = "湲곗〈 ?섍툒 ?대깽?몃? 理쒖떊 ?ㅻ깄???섏튂濡?媛깆떊?덉뒿?덈떎."
        return DetectEventsFromSnapshotResponse(
            snapshot_date=str(date_str),
            source_snapshot_count=source_snapshot_count,
            filtered_count=len(filtered_rows),
            inserted_count=inserted_count,
            updated_count=updated_count,
            duplicated_count=0,
            applied_condition={
                "use_market_cap": bool(setting.get("use_market_cap", 1)),
                "min_market_cap_krw_100m": self._to_krw_100m(int(setting["min_market_cap"])),
                "use_trading_value": bool(setting.get("use_trading_value", 1)),
                "min_trading_value_krw_100m": self._to_krw_100m(int(setting["min_trading_value"])),
                "use_change_rate": bool(setting.get("use_change_rate", 1)),
                "min_change_rate": float(setting["min_change_rate"]),
                "use_intraday_range": use_intraday_range,
                "min_intraday_range_rate": (
                    float(setting["min_intraday_range_rate"]) if setting["min_intraday_range_rate"] is not None else None
                ),
                "market_scope": market_scope,
            },
            message=message,
        )

    def collect_events(self, trade_date: str | None) -> CollectMarketTrendEventsResponse:
        # 湲곗〈 API ?좎?: stock_daily_prices 湲곗? 媛먯?
        setting = self._get_active_setting_row()
        base_trade_date = trade_date or self.db.execute(text("SELECT MAX(trade_date) FROM stock_daily_prices")).scalar_one()
        if not base_trade_date:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="trade_date not found")
        market_scope = str(setting["market_scope"]).upper()
        use_market_cap = bool(setting.get("use_market_cap", 1))
        use_trading_value = bool(setting.get("use_trading_value", 1))
        use_change_rate = bool(setting.get("use_change_rate", 1))
        conditions = ["p.trade_date = :trade_date"]
        if use_market_cap:
            conditions.append("COALESCE(m.market_cap, 0) >= :min_market_cap")
        if use_trading_value:
            conditions.append("COALESCE(m.trading_value, p.price_trading_value, 0) >= :min_trading_value")
        if use_change_rate:
            conditions.append("COALESCE(p.change_rate, 0) >= :min_change_rate")
        if bool(setting["use_intraday_range"]):
            conditions.append("COALESCE(p.intraday_range_rate, 0) >= :min_intraday_range_rate")
        if market_scope != "ALL":
            conditions.append("UPPER(COALESCE(m.market, s.market, '')) = :market_scope")
        query = f"""
            WITH price_rows AS (
                SELECT
                    p.stock_id,
                    p.trade_date,
                    p.change_rate,
                    p.trading_value AS price_trading_value,
                    CASE
                        WHEN p.low_price IS NOT NULL AND p.high_price IS NOT NULL AND p.close_price IS NOT NULL AND p.close_price != 0
                        THEN ((p.high_price - p.low_price) / p.close_price) * 100.0
                        ELSE NULL
                    END AS intraday_range_rate
                FROM stock_daily_prices p
                WHERE p.trade_date = :trade_date
            ),
            metric_rows AS (
                SELECT stock_id, trade_date, MAX(market_cap) AS market_cap, MAX(trading_value) AS trading_value, MAX(market) AS market
                FROM stock_daily_market_metrics
                WHERE trade_date = :trade_date
                GROUP BY stock_id, trade_date
            )
            SELECT
                p.trade_date, s.id AS stock_id, s.stock_code, s.stock_name, COALESCE(m.market, s.market) AS market_type,
                m.market_cap AS market_cap, COALESCE(m.trading_value, p.price_trading_value) AS trading_value,
                p.change_rate, p.intraday_range_rate
            FROM price_rows p
            JOIN stocks s ON s.id = p.stock_id
            LEFT JOIN metric_rows m ON m.stock_id = p.stock_id AND m.trade_date = p.trade_date
            WHERE {" AND ".join(conditions)}
            ORDER BY COALESCE(m.trading_value, p.price_trading_value, 0) DESC, p.change_rate DESC, s.stock_name ASC
        """
        params = {
            "trade_date": base_trade_date,
            "min_market_cap": int(setting["min_market_cap"]),
            "min_trading_value": int(setting["min_trading_value"]),
            "min_change_rate": float(setting["min_change_rate"]),
            "min_intraday_range_rate": float(setting["min_intraday_range_rate"] or 0.0),
            "market_scope": market_scope,
        }
        rows = [dict(row) for row in self.db.execute(text(query), params).mappings().all()]
        now = now_kst()
        inserted_count = 0
        for row in rows:
            result = self.db.execute(
                text(
                    """
                    INSERT INTO market_trend_events (
                        trade_date, stock_id, stock_code, stock_name, market_type, market_cap, trading_value, change_rate,
                        intraday_range_rate, event_type, detection_setting_id, applied_min_market_cap, applied_min_trading_value,
                        applied_min_change_rate, applied_min_intraday_range_rate, applied_use_market_cap, applied_use_trading_value,
                        applied_use_change_rate, applied_use_intraday_range, theme_id, theme_status,
                        primary_theme_id, reason_summary, user_memo, is_active, detection_source, created_at, updated_at
                    )
                    VALUES (
                        :trade_date, :stock_id, :stock_code, :stock_name, :market_type, :market_cap, :trading_value, :change_rate,
                        :intraday_range_rate, 'supply_surge', :detection_setting_id, :applied_min_market_cap, :applied_min_trading_value,
                        :applied_min_change_rate, :applied_min_intraday_range_rate, :applied_use_market_cap, :applied_use_trading_value,
                        :applied_use_change_rate, :applied_use_intraday_range, NULL, 'unassigned',
                        NULL, NULL, NULL, 1, 'stock_daily_prices', :created_at, :updated_at
                    )
                    ON CONFLICT(trade_date, stock_id, event_type) DO NOTHING
                    """
                ),
                {
                    "trade_date": row["trade_date"],
                    "stock_id": row["stock_id"],
                    "stock_code": row["stock_code"],
                    "stock_name": row["stock_name"],
                    "market_type": row["market_type"],
                    "market_cap": row["market_cap"],
                    "trading_value": row["trading_value"],
                    "change_rate": row["change_rate"],
                    "intraday_range_rate": row["intraday_range_rate"],
                    "detection_setting_id": int(setting["id"]),
                    "applied_min_market_cap": int(setting["min_market_cap"]),
                    "applied_min_trading_value": int(setting["min_trading_value"]),
                    "applied_min_change_rate": float(setting["min_change_rate"]),
                    "applied_min_intraday_range_rate": setting["min_intraday_range_rate"],
                    "applied_use_market_cap": 1 if bool(setting.get("use_market_cap", 1)) else 0,
                    "applied_use_trading_value": 1 if bool(setting.get("use_trading_value", 1)) else 0,
                    "applied_use_change_rate": 1 if bool(setting.get("use_change_rate", 1)) else 0,
                    "applied_use_intraday_range": int(setting["use_intraday_range"]),
                    "created_at": now,
                    "updated_at": now,
                },
            )
            if result.rowcount and result.rowcount > 0:
                inserted_count += 1
        self.db.commit()
        collected_count = len(rows)
        return CollectMarketTrendEventsResponse(
            trade_date=str(base_trade_date),
            applied_condition={
                "min_market_cap_krw_100m": self._to_krw_100m(int(setting["min_market_cap"])) or 0.0,
                "min_trading_value_krw_100m": self._to_krw_100m(int(setting["min_trading_value"])) or 0.0,
                "min_change_rate": float(setting["min_change_rate"]),
                "use_market_cap": bool(setting.get("use_market_cap", 1)),
                "use_trading_value": bool(setting.get("use_trading_value", 1)),
                "use_change_rate": bool(setting.get("use_change_rate", 1)),
                "use_intraday_range": bool(setting["use_intraday_range"]),
                "min_intraday_range_rate": (
                    float(setting["min_intraday_range_rate"]) if setting["min_intraday_range_rate"] is not None else None
                ),
                "market_scope": market_scope,
            },
            collected_count=collected_count,
            inserted_count=inserted_count,
            duplicated_count=max(0, collected_count - inserted_count),
            message="?섍툒 ?대깽??醫낅ぉ ?섏쭛???꾨즺?섏뿀?듬땲??",
        )

    def list_events(
        self,
        *,
        trade_date: str | None,
        theme_status: str | None,
        theme_id: int | None,
        market_scope: str | None,
        limit: int,
        offset: int,
    ) -> list[MarketTrendEventResponse]:
        conditions = ["e.is_active = 1"]
        params: dict[str, object] = {"limit": limit, "offset": offset}
        if trade_date:
            conditions.append("e.trade_date = :trade_date")
            params["trade_date"] = trade_date
        if theme_status:
            if theme_status not in ALLOWED_THEME_STATUS:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid theme_status")
            conditions.append("e.theme_status = :theme_status")
            params["theme_status"] = theme_status
        if theme_id is not None:
            conditions.append("e.theme_id = :theme_id")
            params["theme_id"] = theme_id
        if market_scope:
            scope = self._validate_market_scope(market_scope)
            if scope != "ALL":
                conditions.append("UPPER(COALESCE(e.market_type, '')) = :market_scope")
                params["market_scope"] = scope
        query = f"""
            SELECT
                e.id AS event_id, e.trade_date, e.stock_id, e.stock_code, e.stock_name, e.market_type,
                e.market_cap, e.trading_value, e.change_rate, e.intraday_range_rate, e.event_type, e.detection_source,
                e.theme_id, t.theme_name, e.theme_status, e.reason_summary, e.user_memo,
                e.applied_min_market_cap, e.applied_min_trading_value, e.applied_min_change_rate,
                e.applied_min_intraday_range_rate, e.applied_use_market_cap, e.applied_use_trading_value,
                e.applied_use_change_rate, e.applied_use_intraday_range
            FROM market_trend_events e
            LEFT JOIN market_themes t ON t.id = e.theme_id
            WHERE {" AND ".join(conditions)}
            ORDER BY e.trade_date DESC, COALESCE(e.trading_value, 0) DESC, e.stock_name ASC
            LIMIT :limit OFFSET :offset
        """
        rows = self.db.execute(text(query), params).mappings().all()
        return [
            MarketTrendEventResponse(
                event_id=int(row["event_id"]),
                trade_date=str(row["trade_date"]),
                stock_id=int(row["stock_id"]),
                stock_code=row["stock_code"],
                stock_name=row["stock_name"],
                market_type=row["market_type"],
                market_cap=row["market_cap"],
                trading_value=row["trading_value"],
                change_rate=row["change_rate"],
                intraday_range_rate=row["intraday_range_rate"],
                event_type=str(row["event_type"]),
                detection_source=row["detection_source"],
                theme_id=row["theme_id"],
                theme_name=row["theme_name"],
                theme_status=str(row["theme_status"]),
                reason_summary=row["reason_summary"],
                user_memo=row["user_memo"],
                applied_condition={
                    "min_market_cap_krw_100m": self._to_krw_100m(row["applied_min_market_cap"]),
                    "min_trading_value_krw_100m": self._to_krw_100m(row["applied_min_trading_value"]),
                    "min_change_rate": row["applied_min_change_rate"],
                    "min_intraday_range_rate": row["applied_min_intraday_range_rate"],
                    "use_market_cap": bool(row["applied_use_market_cap"]) if row["applied_use_market_cap"] is not None else True,
                    "use_trading_value": bool(row["applied_use_trading_value"]) if row["applied_use_trading_value"] is not None else True,
                    "use_change_rate": bool(row["applied_use_change_rate"]) if row["applied_use_change_rate"] is not None else True,
                    "use_intraday_range": bool(row["applied_use_intraday_range"]),
                },
            )
            for row in rows
        ]

    def assign_event_theme(self, event_id: int, payload: AssignThemeToTrendEventRequest) -> AssignThemeToTrendEventResponse:
        event = self.db.execute(
            text("SELECT id, stock_id FROM market_trend_events WHERE id = :id AND is_active = 1"),
            {"id": event_id},
        ).mappings().first()
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market trend event not found")
        theme = self.db.execute(
            text("SELECT id, theme_name FROM market_themes WHERE id = :id"),
            {"id": payload.theme_id},
        ).mappings().first()
        if not theme:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market theme not found")

        now = now_kst()
        self.db.execute(
            text(
                """
                UPDATE market_trend_events
                SET theme_id = :theme_id,
                    primary_theme_id = :theme_id,
                    theme_status = 'manual_assigned',
                    reason_summary = :reason_summary,
                    user_memo = :user_memo,
                    updated_at = :updated_at
                WHERE id = :id
                """
            ),
            {
                "theme_id": payload.theme_id,
                "reason_summary": payload.reason_summary,
                "user_memo": payload.user_memo,
                "updated_at": now,
                "id": event_id,
            },
        )

        added = False
        already_mapped = False
        if payload.also_add_to_theme_stocks:
            existing_mapping = self.db.execute(
                text(
                    """
                    SELECT id, is_active
                    FROM market_theme_stocks
                    WHERE theme_id = :theme_id AND stock_id = :stock_id
                    """
                ),
                {"theme_id": payload.theme_id, "stock_id": int(event["stock_id"])},
            ).mappings().first()
            if existing_mapping and int(existing_mapping["is_active"]) == 1:
                already_mapped = True
            else:
                self.db.execute(
                    text(
                        """
                        INSERT INTO market_theme_stocks (
                            theme_id, stock_id, mapping_source, confidence_score, is_primary, is_active, created_at, updated_at
                        )
                        VALUES (:theme_id, :stock_id, 'manual', 1.0, :is_primary, 1, :now, :now)
                        ON CONFLICT(theme_id, stock_id)
                        DO UPDATE SET
                            is_active = 1,
                            is_primary = excluded.is_primary,
                            updated_at = excluded.updated_at
                        """
                    ),
                    {
                        "theme_id": payload.theme_id,
                        "stock_id": int(event["stock_id"]),
                        "is_primary": 1 if payload.is_primary_for_theme else 0,
                        "now": now,
                    },
                )
                added = True

        self.db.commit()
        message = "?섍툒 ?대깽???뚮쭏媛 ??λ릺?덉뒿?덈떎."
        if payload.also_add_to_theme_stocks:
            if already_mapped:
                message = "?섍툒 ?대깽???뚮쭏媛 ??λ릺?덇퀬, ?뺤떇 ?뚮쭏 ?곌껐? ?대? 議댁옱?⑸땲??"
            elif added:
                message = "?섍툒 ?대깽???뚮쭏媛 ??λ릺?덇퀬, ?뺤떇 ?뚮쭏 ?곌껐??異붽??섏뿀?듬땲??"
        return AssignThemeToTrendEventResponse(
            event_id=event_id,
            theme_id=int(theme["id"]),
            theme_name=str(theme["theme_name"]),
            theme_status="manual_assigned",
            added_to_theme_stocks=added,
            already_mapped=already_mapped,
            message=message,
        )

    def get_daily_theme_flow(
        self,
        *,
        trade_date: str | None,
        only_supply_theme: bool,
        market_scope: str | None,
    ) -> DailyThemeFlowResponse:
        base_trade_date = trade_date or self.db.execute(text("SELECT MAX(trade_date) FROM market_trend_events")).scalar_one()
        if not base_trade_date:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="trade_date not found")
        filter_clause = ["e.trade_date = :trade_date", "e.is_active = 1"]
        params: dict[str, object] = {"trade_date": base_trade_date}
        if only_supply_theme:
            filter_clause.append("COALESCE(t.is_supply_theme, 0) = 1")
        if market_scope:
            scope = self._validate_market_scope(market_scope)
            if scope != "ALL":
                filter_clause.append("UPPER(COALESCE(e.market_type, '')) = :market_scope")
                params["market_scope"] = scope
        summary = self.db.execute(
            text(
                f"""
                SELECT
                    COUNT(*) AS event_count,
                    SUM(CASE WHEN e.theme_id IS NOT NULL THEN 1 ELSE 0 END) AS assigned_count,
                    SUM(CASE WHEN e.theme_id IS NULL THEN 1 ELSE 0 END) AS unassigned_count
                FROM market_trend_events e
                LEFT JOIN market_themes t ON t.id = e.theme_id
                WHERE {" AND ".join(filter_clause)}
                """
            ),
            params,
        ).mappings().first() or {"event_count": 0, "assigned_count": 0, "unassigned_count": 0}
        grouped = self.db.execute(
            text(
                f"""
                SELECT
                    e.theme_id, t.theme_name, COALESCE(t.is_supply_theme, 0) AS is_supply_theme,
                    COUNT(*) AS detected_stock_count,
                    CAST(SUM(COALESCE(e.trading_value, 0)) AS INTEGER) AS total_trading_value,
                    AVG(e.change_rate) AS avg_change_rate, MAX(e.change_rate) AS max_change_rate
                FROM market_trend_events e
                JOIN market_themes t ON t.id = e.theme_id
                WHERE {" AND ".join(filter_clause)} AND e.theme_id IS NOT NULL
                GROUP BY e.theme_id, t.theme_name, t.is_supply_theme
                ORDER BY total_trading_value DESC, detected_stock_count DESC, avg_change_rate DESC
                """
            ),
            params,
        ).mappings().all()
        items: list[DailyThemeFlowItem] = []
        for idx, row in enumerate(grouped, start=1):
            top_change_name = self.db.execute(
                text(
                    """
                    SELECT stock_name FROM market_trend_events
                    WHERE trade_date=:trade_date AND is_active=1 AND theme_id=:theme_id
                    ORDER BY change_rate DESC, stock_name ASC LIMIT 1
                    """
                ),
                {"trade_date": base_trade_date, "theme_id": row["theme_id"]},
            ).scalar_one_or_none()
            top_value_name = self.db.execute(
                text(
                    """
                    SELECT stock_name FROM market_trend_events
                    WHERE trade_date=:trade_date AND is_active=1 AND theme_id=:theme_id
                    ORDER BY COALESCE(trading_value, 0) DESC, stock_name ASC LIMIT 1
                    """
                ),
                {"trade_date": base_trade_date, "theme_id": row["theme_id"]},
            ).scalar_one_or_none()
            total_value = int(row["total_trading_value"] or 0)
            items.append(
                DailyThemeFlowItem(
                    theme_id=int(row["theme_id"]),
                    theme_name=str(row["theme_name"]),
                    is_supply_theme=bool(row["is_supply_theme"]),
                    detected_stock_count=int(row["detected_stock_count"]),
                    total_trading_value=total_value,
                    total_trading_value_krw_100m=round(total_value / KRW_100M, 4),
                    avg_change_rate=(round(float(row["avg_change_rate"]), 4) if row["avg_change_rate"] is not None else None),
                    max_change_rate=(round(float(row["max_change_rate"]), 4) if row["max_change_rate"] is not None else None),
                    top_change_stock_name=top_change_name,
                    top_trading_value_stock_name=top_value_name,
                    trend_rank=idx,
                )
            )
        return DailyThemeFlowResponse(
            trade_date=str(base_trade_date),
            description=(
                "본 집계는 사용자가 보정한 테마 기준을 참고 지표로 사용합니다. "
                "공식 업종/테마 분류가 아니므로 최종 판단은 사용자가 수행합니다."
            ),
            summary={
                "event_count": int(summary.get("event_count") or 0),
                "assigned_count": int(summary.get("assigned_count") or 0),
                "unassigned_count": int(summary.get("unassigned_count") or 0),
            },
            items=items,
        )
