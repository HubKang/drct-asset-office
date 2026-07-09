from __future__ import annotations
from datetime import date
from typing import Any

from sqlalchemy.orm import Session
from backend.app.core.config import now_kst
from backend.app.providers.market_data.kiwoom_rest_market_indicator_provider import KiwoomRestMarketIndicatorProvider
from backend.app.repositories.stock_financial_repository import StockFinancialRepository
from backend.app.repositories.stock_repository import StockRepository
from backend.app.schemas.stock_financial_schema import StockFinancialCollectItem, StockFinancialCollectResponse, StockFinancialDataResponse


class StockFinancialService:
    def __init__(self, db: Session) -> None:
        self.repo=StockFinancialRepository(db)
        self.stock_repo=StockRepository(db)
        self.provider=KiwoomRestMarketIndicatorProvider()

    def collect_selected(self, stock_ids: list[int]) -> StockFinancialCollectResponse:
        items=[]
        for stock_id in list(dict.fromkeys(stock_ids)):
            stock=self.stock_repo.get_by_id(stock_id)
            if not stock:
                items.append(StockFinancialCollectItem(stock_id=stock_id, stock_code="-", status="FAILED", message="종목을 찾을 수 없습니다.")); continue
            try:
                items.append(self._collect(stock.id, stock.stock_code))
            except Exception as exc:
                items.append(StockFinancialCollectItem(stock_id=stock.id, stock_code=stock.stock_code, status="FAILED", message=str(exc)[:300]))
        self.repo.commit()
        success=sum(x.status == "SUCCESS" for x in items); partial=sum(x.status == "PARTIAL" for x in items); failed=sum(x.status == "FAILED" for x in items)
        return StockFinancialCollectResponse(status="SUCCESS" if failed == 0 else "PARTIAL", target_count=len(items), success_count=success, partial_count=partial, failed_count=failed, items=items)

    def _collect(self, stock_id: int, stock_code: str) -> StockFinancialCollectItem:
        raw=self.provider.get_stock_basic_info(stock_code=stock_code)
        today=date.today().isoformat(); now=now_kst()
        financial_keys=("per","pbr","eps","bps","roe","debt_ratio","reserve_ratio")
        has_snapshot=any(raw.get(k) is not None for k in financial_keys)
        if has_snapshot:
            self.repo.upsert_snapshot({"stock_id":stock_id,"stock_code":stock_code,"snapshot_date":today,"source_type":"KIWOOM_REAL","source_method":"kiwoom_rest_ka10001","current_price":raw.get("close_price"),"market_cap":raw.get("market_cap"),"listed_shares":raw.get("listed_shares"),"per":raw.get("per"),"pbr":raw.get("pbr"),"eps":raw.get("eps"),"bps":raw.get("bps"),"roe":raw.get("roe"),"debt_ratio":raw.get("debt_ratio"),"reserve_ratio":raw.get("reserve_ratio"),"created_at":now,"updated_at":now})
        annual_saved=0
        year_text=str(raw.get("financial_year") or "").strip()
        if len(year_text) == 4 and year_text.isdigit() and any(raw.get(k) is not None for k in ("revenue","operating_profit","net_income")):
            year=int(year_text)
            self.repo.upsert_statement({"stock_id":stock_id,"stock_code":stock_code,"statement_type":"ANNUAL","fiscal_year":year,"fiscal_quarter":0,"period_label":str(year),"period_end_date":f"{year}-12-31","source_type":"KIWOOM_REAL","source_method":"kiwoom_rest_ka10001","revenue":raw.get("revenue"),"operating_profit":raw.get("operating_profit"),"net_income":raw.get("net_income"),"total_assets":None,"total_liabilities":None,"total_equity":None,"operating_cash_flow":None,"created_at":now,"updated_at":now}); annual_saved=1
        status="SUCCESS" if has_snapshot and annual_saved else "PARTIAL" if has_snapshot or annual_saved else "FAILED"
        message=None if status=="SUCCESS" else "ka10001 응답에 일부 재무 필드가 없습니다. 제공된 값만 저장했습니다."
        return StockFinancialCollectItem(stock_id=stock_id,stock_code=stock_code,status=status,snapshot_saved=has_snapshot,annual_rows_saved=annual_saved,message=message)

    def get_data(self, stock_id: int) -> StockFinancialDataResponse:
        shareholder=self.repo.latest_foreign_holding(stock_id) or {}
        return StockFinancialDataResponse(stock_id=stock_id,financial_snapshot=self.repo.latest_snapshot(stock_id) or {},financial_annual_statements=self.repo.list_statements(stock_id,"ANNUAL",5),financial_quarterly_statements=self.repo.list_statements(stock_id,"QUARTERLY",8),shareholder_snapshot=shareholder)
