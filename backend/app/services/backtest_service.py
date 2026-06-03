from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.repositories.backtest_repository import BacktestRepository
from backend.app.schemas.backtest_schema import BacktestRuleCreate, BacktestRuleUpdate, BacktestRunRequest
from backend.app.services.backtest_engine import run_backtest_engine


CONDITION_FIELD_CANDIDATES: list[dict[str, Any]] = [
    {
        "field_key": "open_price",
        "label": "시가",
        "source_table": "stock_daily_prices",
        "source_column": "open_price",
        "data_type": "number",
        "category": "가격",
        "is_active": True,
        "sort_order": 10,
    },
    {
        "field_key": "high_price",
        "label": "고가",
        "source_table": "stock_daily_prices",
        "source_column": "high_price",
        "data_type": "number",
        "category": "가격",
        "is_active": True,
        "sort_order": 20,
    },
    {
        "field_key": "low_price",
        "label": "저가",
        "source_table": "stock_daily_prices",
        "source_column": "low_price",
        "data_type": "number",
        "category": "가격",
        "is_active": True,
        "sort_order": 30,
    },
    {
        "field_key": "close_price",
        "label": "종가",
        "source_table": "stock_daily_prices",
        "source_column": "close_price",
        "data_type": "number",
        "category": "가격",
        "is_active": True,
        "sort_order": 40,
    },
    {
        "field_key": "volume",
        "label": "거래량",
        "source_table": "stock_daily_prices",
        "source_column": "volume",
        "data_type": "number",
        "category": "거래",
        "is_active": True,
        "sort_order": 50,
    },
    {
        "field_key": "trading_value",
        "label": "거래대금",
        "source_table": "stock_daily_prices",
        "source_column": "trading_value",
        "data_type": "number",
        "category": "거래",
        "is_active": True,
        "sort_order": 60,
    },
]


class BacktestService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = BacktestRepository(db)

    @staticmethod
    def _to_date(value: str) -> datetime:
        return datetime.strptime(value, "%Y-%m-%d")

    @staticmethod
    def _summary_from_run(run: dict[str, Any]) -> dict[str, Any]:
        return {
            "initial_cash": float(run.get("initial_cash") or 0),
            "final_asset": float(run.get("final_asset") or 0),
            "total_profit": float(run.get("total_profit") or 0),
            "total_return_rate": float(run.get("total_return_rate") or 0),
            "max_drawdown": float(run.get("max_drawdown") or 0),
            "trade_count": int(run.get("trade_count") or 0),
            "win_count": int(run.get("win_count") or 0),
            "loss_count": int(run.get("loss_count") or 0),
            "breakeven_count": int(run.get("breakeven_count") or 0),
            "win_rate": run.get("win_rate"),
            "avg_profit_rate": run.get("avg_profit_rate"),
            "avg_loss_rate": run.get("avg_loss_rate"),
            "profit_factor": run.get("profit_factor"),
            "avg_holding_days": run.get("avg_holding_days"),
            "total_fee": float(run.get("total_fee") or 0),
        }

    @staticmethod
    def _validate_rule_shape(values: dict[str, Any]) -> None:
        buy_rule = values.get("buy_conditions_json") or {}
        conditions = buy_rule.get("conditions")
        if buy_rule.get("operator", "AND") != "AND":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="매수조건은 AND만 지원합니다.")
        if not isinstance(conditions, list) or not conditions:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="매수조건을 1개 이상 추가해 주세요.")
        position_rule = values.get("position_rule_json") or {}
        percent = float(position_rule.get("percent") or 0)
        if percent <= 0 or percent > 100:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="진입비중은 0보다 크고 100 이하로 입력해 주세요.")

    def list_rules(self, include_inactive: bool = False) -> dict[str, Any]:
        return {"items": self.repo.list_rules(include_inactive=include_inactive)}

    def list_stocks(self, keyword: str | None, limit: int) -> dict[str, Any]:
        return {
            "items": self.repo.list_backtest_stocks(keyword=keyword, limit=limit),
            "keyword": keyword,
            "limit": limit,
        }

    def list_condition_fields(self) -> dict[str, Any]:
        columns = self.repo.table_columns("stock_daily_prices")
        items = [field for field in CONDITION_FIELD_CANDIDATES if str(field["source_column"]) in columns]
        return {"items": items}

    def get_rule(self, rule_id: int) -> dict[str, Any]:
        rule = self.repo.get_rule(rule_id)
        if not rule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="매매기준을 찾을 수 없습니다.")
        return rule

    def create_rule(self, payload: BacktestRuleCreate) -> dict[str, Any]:
        values = payload.model_dump()
        self._validate_rule_shape(values)
        return self.repo.create_rule(values)

    def update_rule(self, rule_id: int, payload: BacktestRuleUpdate) -> dict[str, Any]:
        existing = self.get_rule(rule_id)
        values = payload.model_dump(exclude_unset=True)
        merged = {**existing, **values}
        self._validate_rule_shape(merged)
        return self.repo.update_rule(rule_id, values)

    def deactivate_rule(self, rule_id: int) -> dict[str, Any]:
        self.get_rule(rule_id)
        return self.repo.deactivate_rule(rule_id)

    def _resolve_period(self, stock_id: int, source: str | None, start_date: str | None, end_date: str | None) -> tuple[str, str]:
        all_rows = self.repo.list_prices(stock_id=stock_id, source=source)
        if len(all_rows) < 30:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="해당 종목의 가격 데이터가 부족합니다. 먼저 가격 데이터를 수집해 주세요.")
        resolved_end = end_date or str(all_rows[-1]["trade_date"])
        resolved_start = start_date
        if not resolved_start:
            cutoff = (self._to_date(resolved_end) - timedelta(days=730)).strftime("%Y-%m-%d")
            resolved_start = max(cutoff, str(all_rows[0]["trade_date"]))
        if resolved_start > resolved_end:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="시작일은 종료일보다 늦을 수 없습니다.")
        return resolved_start, resolved_end

    def run_backtest(self, payload: BacktestRunRequest) -> dict[str, Any]:
        rule = self.get_rule(payload.rule_id)
        if int(rule.get("is_active") or 0) != 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="비활성 매매기준은 실행할 수 없습니다.")
        stock = self.repo.get_stock_by_code(payload.stock_code)
        if not stock:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="백테스트할 종목을 찾을 수 없습니다.")
        source = self.repo.resolve_price_source(int(stock["stock_id"]))
        if source is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="해당 종목의 가격 데이터가 부족합니다. 먼저 관심종목 Data분석 화면에서 가격 데이터를 수집해 주세요.",
            )
        start_date, end_date = self._resolve_period(
            stock_id=int(stock["stock_id"]),
            source=source,
            start_date=payload.start_date,
            end_date=payload.end_date,
        )
        prices = self.repo.list_prices(int(stock["stock_id"]), source, start_date=start_date, end_date=end_date)
        if len(prices) < 30:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="해당 종목의 가격 데이터가 부족합니다. 먼저 가격 데이터를 수집해 주세요.")
        try:
            result = run_backtest_engine(prices, rule, payload.initial_cash)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        run_values = {
            "rule_id": int(rule["id"]),
            "stock_code": str(stock["stock_code"]),
            "stock_name": stock.get("stock_name"),
            "start_date": start_date,
            "end_date": end_date,
            "initial_cash": float(payload.initial_cash),
            "message": result["message"],
        }
        run_id = self.repo.create_run_with_results(
            run_values=run_values,
            summary=result["summary"],
            trades=result["trades"],
            equity_curve=result["equity_curve"],
        )
        return {"run_id": run_id, "summary": result["summary"]}

    def list_runs(self, rule_id: int | None, stock_code: str | None, limit: int) -> dict[str, Any]:
        return {"items": self.repo.list_runs(rule_id=rule_id, stock_code=stock_code, limit=limit)}

    def get_run_detail(self, run_id: int) -> dict[str, Any]:
        run = self.repo.get_run(run_id)
        if not run:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="백테스트 실행 결과를 찾을 수 없습니다.")
        return {
            "run": run,
            "summary": self._summary_from_run(run),
            "rule": self.repo.get_rule(int(run["rule_id"])),
            "trades": self.repo.list_trades(run_id),
            "equity_curve": self.repo.list_equity_curve(run_id),
        }

    def list_trades(self, run_id: int) -> list[dict[str, Any]]:
        if not self.repo.get_run(run_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="백테스트 실행 결과를 찾을 수 없습니다.")
        return self.repo.list_trades(run_id)

    def list_equity_curve(self, run_id: int) -> list[dict[str, Any]]:
        if not self.repo.get_run(run_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="백테스트 실행 결과를 찾을 수 없습니다.")
        return self.repo.list_equity_curve(run_id)
