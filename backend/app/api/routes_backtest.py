from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.backtest_schema import (
    BacktestEquityPointResponse,
    BacktestConditionFieldListResponse,
    BacktestRuleCreate,
    BacktestRuleListResponse,
    BacktestRuleResponse,
    BacktestRuleUpdate,
    BacktestRunCreateResponse,
    BacktestRunDetailResponse,
    BacktestRunListResponse,
    BacktestRunRequest,
    BacktestStockListResponse,
    BacktestTradeResponse,
)
from backend.app.services.backtest_service import BacktestService

router = APIRouter(tags=["backtest"])


@router.get("/backtest/stocks", response_model=BacktestStockListResponse)
def list_backtest_stocks(
    keyword: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    return BacktestService(db).list_stocks(keyword=keyword, limit=limit)


@router.get("/backtest/condition-fields", response_model=BacktestConditionFieldListResponse)
def list_backtest_condition_fields(db: Session = Depends(get_db)) -> dict:
    return BacktestService(db).list_condition_fields()


@router.get("/backtest/rules", response_model=BacktestRuleListResponse)
def list_backtest_rules(
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict:
    return BacktestService(db).list_rules(include_inactive=include_inactive)


@router.post("/backtest/rules", response_model=BacktestRuleResponse)
def create_backtest_rule(payload: BacktestRuleCreate, db: Session = Depends(get_db)) -> dict:
    return BacktestService(db).create_rule(payload)


@router.get("/backtest/rules/{rule_id}", response_model=BacktestRuleResponse)
def get_backtest_rule(rule_id: int, db: Session = Depends(get_db)) -> dict:
    return BacktestService(db).get_rule(rule_id)


@router.patch("/backtest/rules/{rule_id}", response_model=BacktestRuleResponse)
def update_backtest_rule(rule_id: int, payload: BacktestRuleUpdate, db: Session = Depends(get_db)) -> dict:
    return BacktestService(db).update_rule(rule_id, payload)


@router.delete("/backtest/rules/{rule_id}", response_model=BacktestRuleResponse)
def delete_backtest_rule(rule_id: int, db: Session = Depends(get_db)) -> dict:
    return BacktestService(db).deactivate_rule(rule_id)


@router.post("/backtest/runs", response_model=BacktestRunCreateResponse)
def run_backtest(payload: BacktestRunRequest, db: Session = Depends(get_db)) -> dict:
    return BacktestService(db).run_backtest(payload)


@router.get("/backtest/runs", response_model=BacktestRunListResponse)
def list_backtest_runs(
    rule_id: int | None = Query(default=None),
    stock_code: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    return BacktestService(db).list_runs(rule_id=rule_id, stock_code=stock_code, limit=limit)


@router.get("/backtest/runs/{run_id}", response_model=BacktestRunDetailResponse)
def get_backtest_run(run_id: int, db: Session = Depends(get_db)) -> dict:
    return BacktestService(db).get_run_detail(run_id)


@router.get("/backtest/runs/{run_id}/trades", response_model=list[BacktestTradeResponse])
def list_backtest_trades(run_id: int, db: Session = Depends(get_db)) -> list[dict]:
    return BacktestService(db).list_trades(run_id)


@router.get("/backtest/runs/{run_id}/equity-curve", response_model=list[BacktestEquityPointResponse])
def list_backtest_equity_curve(run_id: int, db: Session = Depends(get_db)) -> list[dict]:
    return BacktestService(db).list_equity_curve(run_id)
