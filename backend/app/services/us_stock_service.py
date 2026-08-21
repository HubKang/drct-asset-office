from __future__ import annotations

import logging
import re
from threading import Lock
from time import monotonic
from urllib.parse import quote

import requests
from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.entities.us_stock import UsStock
from backend.app.repositories.us_stock_repository import UsStockRepository
from backend.app.schemas.us_stock_schema import (
    UsStockBulkCreateResponse,
    UsStockBulkPreviewItem,
    UsStockBulkPreviewResponse,
    UsStockBulkRequest,
    UsStockCreate,
    UsStockDeleteImpactResponse,
    UsStockDeleteResponse,
    UsStockListResponse,
    UsStockSummaryResponse,
    UsStockUpdate,
)
from backend.app.schemas.us_market_theme_schema import UsStockChartResponse

SYMBOL_PATTERN = re.compile(r"[A-Z0-9][A-Z0-9.\-]{0,19}")
NAVER_CHART_CACHE_TTL_SECONDS = 20 * 60
_naver_chart_cache: dict[str, tuple[float, dict[str, str | None]]] = {}
_naver_chart_cache_lock = Lock()
logger = logging.getLogger(__name__)


def _chart_url(value: object) -> str | None:
    if isinstance(value, str) and value.startswith(("https://", "http://")):
        return value
    if isinstance(value, dict):
        for key in ("url", "imageUrl", "image_url"):
            nested = value.get(key)
            if isinstance(nested, str) and nested.startswith(("https://", "http://")):
                return nested
    return None


def _fallback_chart_urls(naver_code: str) -> dict[str, str]:
    encoded_code = quote(naver_code, safe=".-")
    base = "https://financial-vn.pstatic.net/chart/mobile/world/item/candle"
    return {period: f"{base}/{period}/{encoded_code}_end.png" for period in ("day", "week", "month")}


class UsStockService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = UsStockRepository(db)

    def list_stocks(self, *, keyword: str | None, exchange: str | None, stock_type: str | None, is_active: int | None, price_status: str | None, page: int, page_size: int) -> UsStockListResponse:
        rows, total = self.repo.list(keyword=keyword, exchange=exchange, stock_type=stock_type, is_active=is_active, price_status=price_status, limit=page_size, offset=(page - 1) * page_size)
        latest = self.repo.latest_prices([row.id for row in rows])
        items = []
        for row in rows:
            price = latest.get(row.id)
            previous = float(price["previous_close"]) if price and price.get("previous_close") is not None else None
            close = float(price["close_price"]) if price else None
            change = (close / previous - 1) * 100 if close is not None and previous else None
            items.append({
                **{column.name: getattr(row, column.name) for column in row.__table__.columns},
                "latest_price_date": str(price["trade_date"]) if price else None,
                "latest_close": close,
                "latest_change_rate": round(change, 4) if change is not None else None,
                "historical_price_row_count": int(price["row_count"] or 0) if price else 0,
                "price_status": row.historical_price_status,
            })
        return UsStockListResponse(items=items, total=total, page=page, page_size=page_size)

    def summary(self) -> UsStockSummaryResponse:
        return UsStockSummaryResponse(**self.repo.summary())

    def get_naver_charts(self, stock_id: int) -> UsStockChartResponse:
        stock = self.get_stock(stock_id)
        naver_code = (stock.naver_code or "").strip()
        if not naver_code:
            return UsStockChartResponse(stock_id=stock.id, naver_code=None, day=None, week=None, month=None, available=False)
        now = monotonic()
        with _naver_chart_cache_lock:
            cached = _naver_chart_cache.get(naver_code)
            if cached and now - cached[0] < NAVER_CHART_CACHE_TTL_SECONDS:
                return UsStockChartResponse(stock_id=stock.id, naver_code=naver_code, available=True, **cached[1])
        charts: dict[str, str | None] = {"day": None, "week": None, "month": None}
        try:
            response = requests.get(
                f"https://api.stock.naver.com/stock/{quote(naver_code, safe='')}/basic",
                headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
                timeout=5,
                # Chart lookup is a public provider request. Do not inherit a
                # stale process-level proxy, which can make every chart fail.
                proxies={"http": "", "https": ""},
            )
            response.raise_for_status()
            payload = response.json()
            candle = ((payload.get("imageChartUrlInfo") or {}).get("candle") or {}) if isinstance(payload, dict) else {}
            if isinstance(candle, dict):
                charts = {period: _chart_url(candle.get(period)) for period in charts}
        except (requests.RequestException, ValueError, TypeError, AttributeError) as exc:
            logger.warning("Failed to fetch Naver chart metadata naver_code=%s error=%s", naver_code, exc)
        if not any(charts.values()):
            charts = _fallback_chart_urls(naver_code)
        with _naver_chart_cache_lock:
            if any(charts.values()):
                _naver_chart_cache[naver_code] = (now, charts)
            else:
                _naver_chart_cache.pop(naver_code, None)
        return UsStockChartResponse(stock_id=stock.id, naver_code=naver_code, available=any(charts.values()), **charts)

    def create_stock(self, payload: UsStockCreate) -> UsStock:
        if self.repo.get_by_symbol_exchange(payload.symbol, payload.exchange):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="같은 거래소에 이미 등록된 Ticker입니다.")
        now = now_kst()
        stock = UsStock(**payload.model_dump(), created_at=now, updated_at=now)
        try:
            return self.repo.create(stock)
        except IntegrityError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="같은 거래소에 이미 등록된 Ticker입니다.") from exc

    def get_stock(self, stock_id: int) -> UsStock:
        stock = self.repo.get_by_id(stock_id)
        if not stock:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="미국 종목을 찾을 수 없습니다.")
        return stock

    def update_stock(self, stock_id: int, payload: UsStockUpdate) -> UsStock:
        stock = self.get_stock(stock_id)
        data = payload.model_dump(exclude_unset=True)
        next_exchange = data.get("exchange", stock.exchange)
        if next_exchange != stock.exchange:
            duplicate = self.repo.get_by_symbol_exchange(stock.symbol, next_exchange)
            if duplicate and duplicate.id != stock.id:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="변경할 거래소에 같은 Ticker가 이미 있습니다.")
        for key, value in data.items():
            setattr(stock, key, value)
        stock.updated_at = now_kst()
        try:
            return self.repo.update(stock)
        except IntegrityError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="변경할 거래소에 같은 Ticker가 이미 있습니다.") from exc

    def get_delete_impact(self, stock_id: int) -> UsStockDeleteImpactResponse:
        stock = self.get_stock(stock_id)
        counts = self.db.execute(text("""
            SELECT
              (SELECT COUNT(*) FROM us_stock_daily_prices WHERE us_stock_id=:stock_id) AS price_row_count,
              (SELECT COUNT(*) FROM us_theme_stocks WHERE us_stock_id=:stock_id) AS theme_link_count,
              (SELECT COUNT(DISTINCT theme_id) FROM us_theme_stocks WHERE us_stock_id=:stock_id) AS affected_theme_count
        """), {"stock_id": stock_id}).mappings().one()
        return UsStockDeleteImpactResponse(
            stock_id=stock.id,
            symbol=stock.symbol,
            price_row_count=int(counts["price_row_count"] or 0),
            theme_link_count=int(counts["theme_link_count"] or 0),
            affected_theme_count=int(counts["affected_theme_count"] or 0),
        )

    def delete_stock(self, stock_id: int, *, confirm_symbol: str) -> UsStockDeleteResponse:
        stock = self.get_stock(stock_id)
        symbol = stock.symbol
        naver_code = stock.naver_code
        if confirm_symbol.strip().upper() != symbol:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"확인용 Ticker에 {symbol}을(를) 정확히 입력해 주세요.")

        theme_ids = [int(value) for value in self.db.scalars(text(
            "SELECT DISTINCT theme_id FROM us_theme_stocks WHERE us_stock_id=:stock_id ORDER BY theme_id"
        ), {"stock_id": stock_id}).all()]
        theme_params = {f"theme_{index}": theme_id for index, theme_id in enumerate(theme_ids)}
        theme_placeholders = ",".join(f":theme_{index}" for index in range(len(theme_ids)))

        try:
            invalidated_returns = 0
            if theme_ids:
                invalidated_returns = max(int(self.db.execute(text(
                    f"DELETE FROM us_theme_daily_returns WHERE theme_id IN ({theme_placeholders})"
                ), theme_params).rowcount or 0), 0)
            deleted_links = max(int(self.db.execute(text(
                "DELETE FROM us_theme_stocks WHERE us_stock_id=:stock_id"
            ), {"stock_id": stock_id}).rowcount or 0), 0)
            deleted_prices = max(int(self.db.execute(text(
                "DELETE FROM us_stock_daily_prices WHERE us_stock_id=:stock_id"
            ), {"stock_id": stock_id}).rowcount or 0), 0)
            self.db.delete(stock)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        if naver_code:
            with _naver_chart_cache_lock:
                _naver_chart_cache.pop(naver_code, None)

        recalculated_theme_count = 0
        if theme_ids:
            try:
                from backend.app.schemas.us_market_theme_schema import UsThemeReturnRecalculateRequest
                from backend.app.services.us_market_data_service import UsMarketDataService

                result = UsMarketDataService(self.db).recalculate_returns(UsThemeReturnRecalculateRequest(theme_ids=theme_ids))
                recalculated_theme_count = result.processed_theme_count
            except Exception:
                self.db.rollback()
                logger.exception("Failed to recalculate US theme returns after physically deleting stock_id=%s", stock_id)

        return UsStockDeleteResponse(
            deleted=True,
            stock_id=stock_id,
            symbol=symbol,
            deleted_price_count=deleted_prices,
            deleted_theme_link_count=deleted_links,
            invalidated_theme_return_count=invalidated_returns,
            recalculated_theme_count=recalculated_theme_count,
            message=(
                f"{symbol} 종목과 관련 데이터가 물리 삭제되었습니다."
                if not theme_ids or recalculated_theme_count
                else f"{symbol} 종목은 삭제되었으며, 영향 테마 등락률은 다음 갱신에서 재계산됩니다."
            ),
        )

    def preview_bulk(self, payload: UsStockBulkRequest) -> UsStockBulkPreviewResponse:
        items: list[UsStockBulkPreviewItem] = []
        seen: set[str] = set()
        for raw in payload.tickers:
            symbol = raw.strip().upper()
            if not SYMBOL_PATTERN.fullmatch(symbol):
                items.append(UsStockBulkPreviewItem(symbol=symbol or raw, exchange=payload.exchange, stock_type=payload.stock_type, status="INVALID", reason="Ticker 형식 오류"))
            elif symbol in seen:
                items.append(UsStockBulkPreviewItem(symbol=symbol, exchange=payload.exchange, stock_type=payload.stock_type, status="DUPLICATE", reason="입력 내 중복"))
            elif self.repo.get_by_symbol_exchange(symbol, payload.exchange):
                seen.add(symbol)
                items.append(UsStockBulkPreviewItem(symbol=symbol, exchange=payload.exchange, stock_type=payload.stock_type, status="EXISTING", reason="이미 등록됨"))
            else:
                seen.add(symbol)
                items.append(UsStockBulkPreviewItem(symbol=symbol, exchange=payload.exchange, stock_type=payload.stock_type, status="NEW"))
        return UsStockBulkPreviewResponse(
            items=items,
            new_count=sum(item.status == "NEW" for item in items),
            existing_count=sum(item.status in {"EXISTING", "DUPLICATE"} for item in items),
            invalid_count=sum(item.status == "INVALID" for item in items),
        )

    def create_bulk(self, payload: UsStockBulkRequest) -> UsStockBulkCreateResponse:
        preview = self.preview_bulk(payload)
        now = now_kst()
        rows = [
            UsStock(symbol=item.symbol, name=None, name_ko=None, exchange=payload.exchange, stock_type=payload.stock_type, naver_code=None, is_active=payload.is_active, last_synced_at=None, created_at=now, updated_at=now)
            for item in preview.items if item.status == "NEW"
        ]
        created = self.repo.create_many(rows) if rows else []
        return UsStockBulkCreateResponse(created_count=len(created), skipped_count=len(preview.items) - len(created), items=created)
