from __future__ import annotations

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
        if status_value in {"COLLECTING", "PARTIAL", "WAITING", STATUS_NOT_COLLECTED}:
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

    def collect(self, *, index_codes: list[str] | None, start_date: str | None, end_date: str | None) -> dict[str, Any]:
        today = self._today()
        end_dt = self._parse_date(end_date, today)
        start_dt = self._parse_date(start_date, end_dt - timedelta(days=365 * 2))
        masters = self._target_indexes(index_codes)
        results = []
        saved_total = 0
        success_count = 0
        failed_count = 0
        for master in masters:
            code = master["index_code"]
            index_name = self._display_name(code, master.get("index_name"))
            try:
                self._update_collect_status(code, "COLLECTING", None, None)
                response = self.provider.get_index_daily_prices(
                    index_code=code,
                    start_date=start_dt.isoformat(),
                    end_date=end_dt.isoformat(),
                )
                rows = response.get("items", [])
                if not rows:
                    rows = self._overview_fallback_row(code, start_dt, end_dt)
                saved = self._upsert_daily_rows(code, rows, source_provider="KIWOOM_REST")
                if saved:
                    self._recalculate_moving_averages(code)
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
                        "message": f"{index_name} 지수 데이터를 갱신했습니다.",
                        "last_collected_date": latest_date,
                        "error_message": None,
                    }
                )
            except UnsupportedMarketIndicatorError as exc:
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
                        "last_collected_date": None,
                        "error_message": message,
                        "to_date": end_dt.isoformat(),
                        "message": message,
                    }
                )
        return {
            "requested_count": len(masters),
            "success_count": success_count,
            "failed_count": failed_count,
            "saved_count": saved_total,
            "message": f"지수 데이터 갱신 완료: 성공 {success_count}건, 실패 {failed_count}건",
            "results": results,
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
        key = "kospi" if index_code.upper() == "KOSPI" else "kosdaq"
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
        saved = 0
        for row in rows:
            if not row.get("price_date") or row.get("close_price") is None:
                continue
            result = self.db.execute(
                text(
                    """
                    INSERT INTO market_index_daily_prices
                    (index_code, price_date, open_price, high_price, low_price, close_price, volume, trading_value,
                     change_rate, source_provider, created_at, updated_at)
                    VALUES (:index_code, :price_date, :open_price, :high_price, :low_price, :close_price, :volume,
                            :trading_value, :change_rate, :source_provider, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT(index_code, price_date) DO UPDATE SET
                        open_price = excluded.open_price,
                        high_price = excluded.high_price,
                        low_price = excluded.low_price,
                        close_price = excluded.close_price,
                        volume = excluded.volume,
                        trading_value = excluded.trading_value,
                        change_rate = excluded.change_rate,
                        source_provider = excluded.source_provider,
                        updated_at = CURRENT_TIMESTAMP
                    """
                ),
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
                },
            )
            saved += max(int(result.rowcount or 0), 0)
        self.db.commit()
        return saved

    def _recalculate_moving_averages(self, index_code: str) -> None:
        rows = self._daily_rows(index_code, None, None)
        closes = [row.get("close_price") for row in rows]
        for idx, row in enumerate(rows):
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


