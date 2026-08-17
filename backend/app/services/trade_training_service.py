from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
import json
import logging
from time import perf_counter
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.repositories.trade_training_repository import TradeTrainingRepository
from backend.app.services.risk_management_calculator import (
    calculate_risk_budget,
    calculate_position_risk,
    classify_risk_usage,
    calculate_risk_usage_pct,
    calculate_scenario_planned_loss,
    to_decimal,
)
from backend.app.schemas.trade_training_schema import (
    SimulationReviewSaveRequest,
    TradeTrainingAccountCreate,
    TradeTrainingAccountUpdate,
    TrainingOrderRequest,
    RiskOrderPreviewRequest,
    RiskLevelResponseRequest,
    TradeTrainingRiskScenarioDraftRequest,
    TrainingSessionCreate,
    MultiPeriodTechnicalAnalysisRequest,
    TechnicalAnalysisPreviewRequest,
)
from backend.app.services.technical_analysis_service import (
    DISPLAY_PERIOD_DAYS,
    TECHNICAL_PREVIEW_CACHE,
    calculate_technical_analysis,
    configuration_hash,
    normalize_configuration,
)
from backend.app.services.trade_training_multi_period_preview import build_multi_period_preview


RUNNING_STATUS = "진행중"
FINISHED_STATUS = "완료"
ABORTED_STATUS = "중단"
TRAINING_ACCOUNT_STATUSES = {"ACTIVE", "PAUSED", "COMPLETED", "ARCHIVED"}
TRAINING_PREVIEW_CANDLE_COUNT = 30
logger = logging.getLogger(__name__)


class TradeTrainingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = TradeTrainingRepository(db)

    def list_stocks(self, q: str | None, page: int, page_size: int) -> dict[str, Any]:
        items, total_count = self.repo.list_training_stocks(q=q, page=page, page_size=page_size)
        total_pages = (total_count + page_size - 1) // page_size
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "total_pages": total_pages,
        }

    @staticmethod
    def _clean_account_mas(values: list[int] | None) -> list[int]:
        cleaned = sorted({int(value) for value in values or [] if int(value) > 0})
        return cleaned or [5, 10, 20, 60, 120]

    @staticmethod
    def _account_payload(payload: TradeTrainingAccountCreate | TradeTrainingAccountUpdate) -> dict[str, Any]:
        raw = payload.model_dump(exclude_unset=True)
        if "name" in raw and raw["name"] is not None:
            raw["name"] = str(raw["name"]).strip()
            if not raw["name"]:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="계좌명을 입력해 주세요.")
        if "status" in raw and raw["status"] is not None:
            raw["status"] = str(raw["status"]).upper()
            if raw["status"] not in TRAINING_ACCOUNT_STATUSES:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="지원하지 않는 계좌 상태입니다.")
        if "moving_average_periods_default" in raw:
            raw["moving_average_periods_default"] = TradeTrainingService._clean_account_mas(
                raw.get("moving_average_periods_default")
            )
        return raw

    def list_training_accounts(self, status_filter: str | None = None) -> dict[str, Any]:
        normalized_status = status_filter.upper() if status_filter else None
        if normalized_status and normalized_status not in TRAINING_ACCOUNT_STATUSES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="지원하지 않는 계좌 상태입니다.")
        return {"items": self.repo.list_training_accounts(status_filter=normalized_status)}

    def create_training_account(self, payload: TradeTrainingAccountCreate) -> dict[str, Any]:
        return self.repo.create_training_account(self._account_payload(payload))

    def get_training_account(self, account_id: int) -> dict[str, Any]:
        account = self.repo.get_training_account(account_id)
        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="훈련계좌를 찾을 수 없습니다.")
        return account

    def update_training_account(self, account_id: int, payload: TradeTrainingAccountUpdate) -> dict[str, Any]:
        self.get_training_account(account_id)
        values = self._account_payload(payload)
        if not values:
            return self.get_training_account(account_id)
        return self.repo.update_training_account(account_id, values)

    @staticmethod
    def _profit_loss_stats(closed_trades: list[dict[str, Any]]) -> dict[str, Any]:
        wins = [item for item in closed_trades if float(item.get("net_pnl") or 0) > 0]
        losses = [item for item in closed_trades if float(item.get("net_pnl") or 0) < 0]
        flats = [item for item in closed_trades if float(item.get("net_pnl") or 0) == 0]
        average_profit = sum(float(item["net_pnl"]) for item in wins) / len(wins) if wins else None
        average_loss = sum(float(item["net_pnl"]) for item in losses) / len(losses) if losses else None
        average_loss_abs = abs(average_loss) if average_loss is not None else None
        if not closed_trades:
            status_value = "NO_CLOSED_TRADES"
        elif not wins:
            status_value = "NO_WIN_TRADES"
        elif not losses:
            status_value = "NO_LOSS_TRADES"
        else:
            status_value = "AVAILABLE"
        return {
            "winning_trade_count": len(wins),
            "losing_trade_count": len(losses),
            "flat_trade_count": len(flats),
            "average_profit": None if average_profit is None else round(average_profit, 4),
            "average_loss": None if average_loss is None else round(average_loss, 4),
            "profit_loss_ratio": None if not average_profit or not average_loss_abs else round(average_profit / average_loss_abs, 4),
            "profit_loss_ratio_status": status_value,
            "winning_ratio": None if not closed_trades else round(len(wins) / len(closed_trades) * 100, 4),
        }

    def get_training_account_summary(self, account_id: int) -> dict[str, Any]:
        account = self.get_training_account(account_id)
        initial_capital = float(account.get("initial_capital") or 0)
        closed_trades = self.list_training_account_closed_trades(account_id)["items"]
        sessions = self.repo.list_account_sessions(account_id)
        active_session_count = sum(1 for item in sessions if str(item.get("status") or "") == RUNNING_STATUS)
        realized_pnl = round(sum(float(item.get("net_pnl") or 0) for item in closed_trades), 4)
        realized_equity = round(initial_capital + realized_pnl, 4)
        cash_balance = round(float(account.get("cash_balance") or realized_equity), 4)
        open_position_cost = 0.0
        open_position_market_value = 0.0
        open_position_count = 0
        for session in sessions:
            if str(session.get("status") or "") != RUNNING_STATUS:
                continue
            position_qty = int(session.get("position_qty") or 0)
            if position_qty <= 0:
                continue
            open_position_count += 1
            avg_price = float(session.get("avg_price") or 0)
            open_position_cost += avg_price * position_qty
            try:
                current_candle = self._current_price_row(session)
            except HTTPException:
                current_candle = None
            current_price = float(current_candle.get("close_price") or 0) if current_candle else avg_price
            open_position_market_value += current_price * position_qty
        open_position_cost = round(open_position_cost, 4)
        open_position_market_value = round(open_position_market_value, 4)
        unrealized_pnl = round(open_position_market_value - open_position_cost, 4)
        current_training_equity = round(cash_balance + open_position_market_value, 4)
        stats = self._profit_loss_stats(closed_trades)
        return {
            "account_id": int(account["id"]),
            "initial_capital": initial_capital,
            "cash_balance": cash_balance,
            "training_equity": current_training_equity,
            "current_training_equity": current_training_equity,
            "open_position_cost": open_position_cost,
            "open_position_market_value": open_position_market_value,
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "cumulative_realized_return_pct": self._safe_rate(realized_pnl, initial_capital),
            "current_equity_return_pct": self._safe_rate(current_training_equity - initial_capital, initial_capital),
            "active_session_count": active_session_count,
            "open_position_count": open_position_count,
            "closed_trade_count": len(closed_trades),
            **stats,
        }

    def list_training_account_sessions(self, account_id: int, status_filter: str | None = None) -> dict[str, Any]:
        self.get_training_account(account_id)
        normalized_status = status_filter
        if status_filter and status_filter.upper() == "ACTIVE":
            normalized_status = RUNNING_STATUS
        rows = self.repo.list_account_sessions(account_id, status_filter=normalized_status)
        items = []
        for row in rows:
            options = self._parse_options(row)
            current_candle: dict[str, Any] | None = None
            try:
                current_candle = self._current_price_row(row)
            except HTTPException:
                current_candle = None
            account_values = self._calc_account(row, current_candle)
            position_qty = int(row.get("position_qty") or 0)
            raw_status = str(row.get("status") or "")
            if raw_status == RUNNING_STATUS:
                status_state = "OPEN" if position_qty > 0 else ("WATCHING" if int(row.get("trade_count") or 0) > 0 else "READY")
            elif raw_status == FINISHED_STATUS:
                status_state = "COMPLETED"
            elif raw_status == ABORTED_STATUS:
                status_state = "PAUSED"
            else:
                status_state = "PAUSED"
            stock = self.repo.get_stock_by_code(str(row.get("stock_code") or "")) if row.get("stock_code") else None
            items.append(
                {
                    "id": int(row["id"]),
                    "session_id": int(row["id"]),
                    "training_account_id": int(row.get("training_account_id") or account_id),
                    "stock_id": int(options.get("stock_id") or 0) or (int(stock["stock_id"]) if stock and stock.get("stock_id") else None),
                    "market": stock.get("market") if stock else None,
                    "stock_code": str(row.get("stock_code") or ""),
                    "stock_name": row.get("stock_name"),
                    "status": raw_status,
                    "status_state": status_state,
                    "status_display": status_state,
                    "start_date": str(row.get("start_date") or ""),
                    "end_date": str(row.get("end_date") or ""),
                    "chart_start_date": str(row.get("start_date") or ""),
                    "chart_end_date": str(row.get("end_date") or ""),
                    "current_date": row.get("current_date"),
                    "chart_current_date": row.get("current_date"),
                    "current_index": int(row.get("current_index") or 0),
                    "current_step": int(row.get("current_index") or 0) + 1,
                    "display_days": int(options.get("display_days") or 80),
                    "moving_averages": self._clean_mas(list(options.get("moving_averages") or [5, 20, 60])),
                    "position_qty": position_qty,
                    "position_quantity": position_qty,
                    "avg_price": round(float(row.get("avg_price") or 0), 4),
                    "average_entry_price": round(float(row.get("avg_price") or 0), 4),
                    "current_price": account_values["current_price"],
                    "market_value": account_values["evaluation_amount"],
                    "position_cost": round(position_qty * float(row.get("avg_price") or 0), 4),
                    "unrealized_pnl": account_values["unrealized_profit"],
                    "unrealized_return_pct": account_values["unrealized_return_rate"],
                    "realized_profit": round(float(row.get("realized_profit") or 0), 4),
                    "trade_count": int(row.get("trade_count") or 0),
                    "buy_count": int(row.get("buy_count") or 0),
                    "sell_count": int(row.get("sell_count") or 0),
                    "created_at": row.get("created_at"),
                    "updated_at": row.get("updated_at"),
                    "last_trained_at": row.get("updated_at") or row.get("created_at"),
                }
            )
        return {"items": items}

    def _closed_trades_for_session(self, account_id: int, session: dict[str, Any]) -> list[dict[str, Any]]:
        options = self._parse_options(session)
        trades = self.repo.list_trades(int(session["id"]))
        closed: list[dict[str, Any]] = []
        open_lots: list[dict[str, Any]] = []
        cycle_buy_amount = 0.0
        cycle_sell_amount = 0.0
        cycle_fee = 0.0
        cycle_qty = 0
        cycle_open_date: str | None = None
        cycle_open_index = 0
        position_qty = 0

        for trade in trades:
            side = str(trade.get("side") or "").upper()
            qty = int(trade.get("quantity") or 0)
            price = float(trade.get("price") or 0)
            amount = float(trade.get("amount") or price * qty)
            fee = float(trade.get("fee") or 0)
            trade_date = str(trade.get("trade_date") or "")

            if side == "BUY":
                if position_qty == 0:
                    cycle_buy_amount = 0
                    cycle_sell_amount = 0
                    cycle_fee = 0
                    cycle_qty = 0
                    cycle_open_date = trade_date
                    cycle_open_index = len(closed)
                    open_lots = []
                open_lots.append({**trade, "remaining_quantity": qty})
                position_qty += qty
                cycle_qty += qty
                cycle_buy_amount += amount
                cycle_fee += fee
                continue

            if side != "SELL" or position_qty <= 0:
                continue

            remaining_sell_qty = qty
            sell_cost_basis = 0.0
            sell_buy_fee = 0.0
            while remaining_sell_qty > 0 and open_lots:
                lot = open_lots[0]
                lot_qty = int(lot.get("quantity") or 0)
                matched_qty = min(int(lot.get("remaining_quantity") or 0), remaining_sell_qty)
                lot_price = float(lot.get("price") or 0)
                lot_fee = float(lot.get("fee") or 0)
                sell_cost_basis += lot_price * matched_qty
                sell_buy_fee += lot_fee * (matched_qty / max(1, lot_qty))
                lot["remaining_quantity"] = int(lot["remaining_quantity"]) - matched_qty
                remaining_sell_qty -= matched_qty
                if int(lot["remaining_quantity"]) <= 0:
                    open_lots.pop(0)

            position_qty = max(0, position_qty - qty)
            cycle_sell_amount += amount
            cycle_fee += fee
            if position_qty == 0 and cycle_open_date:
                total_fee = cycle_fee
                net_pnl = round(cycle_sell_amount - cycle_buy_amount - total_fee, 4)
                result_type = "WIN" if net_pnl > 0 else "LOSS" if net_pnl < 0 else "FLAT"
                holding_bars = max(0, len(closed) - cycle_open_index)
                try:
                    holding_bars = max(0, (self._to_date(trade_date) - self._to_date(cycle_open_date)).days)
                except ValueError:
                    pass
                closed.append(
                    {
                        "id": f"{session['id']}-{len(closed) + 1}",
                        "closed_trade_id": f"{session['id']}-{len(closed) + 1}",
                        "trade_sequence": 0,
                        "training_account_id": account_id,
                        "training_session_id": int(session["id"]),
                        "simulation_session_id": int(session["id"]),
                        "stock_id": int(options.get("stock_id") or 0) or None,
                        "stock_code": str(session.get("stock_code") or ""),
                        "stock_name": session.get("stock_name"),
                        "opened_chart_date": cycle_open_date,
                        "closed_chart_date": trade_date,
                        "chart_entry_date": cycle_open_date,
                        "chart_exit_date": trade_date,
                        "completed_at": trade.get("created_at"),
                        "gross_buy_amount": round(cycle_buy_amount, 4),
                        "gross_sell_amount": round(cycle_sell_amount, 4),
                        "gross_pnl": round(cycle_sell_amount - cycle_buy_amount, 4),
                        "commission_amount": round(total_fee, 4),
                        "tax_amount": 0,
                        "net_pnl": net_pnl,
                        "return_pct": self._safe_rate(net_pnl, cycle_buy_amount + sell_buy_fee),
                        "holding_bars": holding_bars,
                        "result_type": result_type,
                        "quantity": cycle_qty,
                        "actual_quantity": cycle_qty,
                        "avg_buy_price": round(cycle_buy_amount / max(1, cycle_qty), 4),
                        "avg_sell_price": round(cycle_sell_amount / max(1, cycle_qty), 4),
                        "average_entry_price": round(cycle_buy_amount / max(1, cycle_qty), 4),
                        "average_exit_price": round(cycle_sell_amount / max(1, cycle_qty), 4),
                        "planned_risk_pct": None,
                        "planned_risk_amount": None,
                        "realized_r": None,
                        "atr_value": None,
                        "atr_pct": None,
                        "recommended_quantity": None,
                    }
                )
                cycle_open_date = None
                cycle_qty = 0
                cycle_buy_amount = 0
                cycle_sell_amount = 0
                cycle_fee = 0
        return closed

    def list_training_account_closed_trades(self, account_id: int) -> dict[str, Any]:
        self.get_training_account(account_id)
        items: list[dict[str, Any]] = []
        for session in self.repo.list_account_sessions(account_id):
            items.extend(self._closed_trades_for_session(account_id, session))
        items.sort(key=lambda item: (str(item.get("completed_at") or ""), int(item.get("training_session_id") or 0), str(item.get("id") or "")))
        for idx, item in enumerate(items, start=1):
            item["trade_sequence"] = idx
        return {"items": items}

    def get_training_account_performance(self, account_id: int) -> dict[str, Any]:
        account = self.get_training_account(account_id)
        initial_capital = float(account.get("initial_capital") or 0)
        equity = initial_capital
        items = []
        closed_trades = self.list_training_account_closed_trades(account_id)["items"]
        for trade in closed_trades:
            equity_before = equity
            equity = round(equity + float(trade.get("net_pnl") or 0), 4)
            cumulative_return_pct = self._safe_rate(equity - initial_capital, initial_capital)
            items.append(
                {
                    "closed_trade_id": trade.get("closed_trade_id") or trade.get("id"),
                    "trade_sequence": int(trade["trade_sequence"]),
                    "simulation_session_id": trade.get("simulation_session_id") or trade.get("training_session_id"),
                    "training_session_id": trade.get("training_session_id"),
                    "training_account_id": account_id,
                    "stock_id": trade.get("stock_id"),
                    "stock_code": trade.get("stock_code"),
                    "stock_name": trade.get("stock_name"),
                    "chart_entry_date": trade.get("chart_entry_date") or trade.get("opened_chart_date"),
                    "chart_exit_date": trade.get("chart_exit_date") or trade.get("closed_chart_date"),
                    "completed_at": trade.get("completed_at"),
                    "quantity": trade.get("quantity"),
                    "average_entry_price": trade.get("average_entry_price") or trade.get("avg_buy_price"),
                    "average_exit_price": trade.get("average_exit_price") or trade.get("avg_sell_price"),
                    "gross_buy_amount": trade.get("gross_buy_amount"),
                    "gross_sell_amount": trade.get("gross_sell_amount"),
                    "gross_pnl": trade.get("gross_pnl"),
                    "commission_amount": trade.get("commission_amount"),
                    "tax_amount": trade.get("tax_amount"),
                    "net_pnl": trade.get("net_pnl"),
                    "return_pct": trade.get("return_pct"),
                    "holding_bars": trade.get("holding_bars"),
                    "equity_before": round(equity_before, 4),
                    "equity_after": equity,
                    "cumulative_return_pct": cumulative_return_pct,
                    "planned_risk_pct": trade.get("planned_risk_pct"),
                    "planned_risk_amount": trade.get("planned_risk_amount"),
                    "realized_r": trade.get("realized_r"),
                    "atr_value": trade.get("atr_value"),
                    "atr_pct": trade.get("atr_pct"),
                    "recommended_quantity": trade.get("recommended_quantity"),
                    "actual_quantity": trade.get("actual_quantity") or trade.get("quantity"),
                }
            )
        stats = self._profit_loss_stats(closed_trades)
        return {
            "account_id": int(account_id),
            "initial_capital": initial_capital,
            "current_realized_equity": equity,
            "cumulative_return_pct": self._safe_rate(equity - initial_capital, initial_capital),
            "closed_trade_count": len(closed_trades),
            **stats,
            "items": items,
        }

    def rebuild_training_account_ledger(self, account_id: int, apply_changes: bool = False) -> dict[str, Any]:
        account = self.get_training_account(account_id)
        initial_capital = float(account.get("initial_capital") or 0)
        stored_cash_balance = round(float(account.get("cash_balance") or 0), 4)
        stored_realized_equity = round(float(account.get("realized_equity") or initial_capital), 4)
        sessions = self.repo.list_account_sessions(account_id)
        session_map = {int(item["id"]): item for item in sessions}
        trade_events = self.repo.list_account_trade_events(account_id)
        ledger_before = self.repo.count_account_ledger_events(account_id)
        closed_trades = self.list_training_account_closed_trades(account_id)["items"]

        cash_balance = initial_capital
        realized_pnl = 0.0
        ledger_events: list[dict[str, Any]] = []
        warnings: list[str] = []
        session_states: dict[int, dict[str, Any]] = {
            int(session["id"]): {
                "qty": 0,
                "avg": 0.0,
                "cycle_buy": 0.0,
                "cycle_sell": 0.0,
                "cycle_fee": 0.0,
                "realized_profit": 0.0,
            }
            for session in sessions
        }

        for trade in trade_events:
            trade_id = int(trade.get("id") or 0)
            session_id = int(trade.get("session_id") or 0)
            state = session_states.setdefault(
                session_id,
                {"qty": 0, "avg": 0.0, "cycle_buy": 0.0, "cycle_sell": 0.0, "cycle_fee": 0.0, "realized_profit": 0.0},
            )
            side = str(trade.get("side") or "").upper()
            qty = int(trade.get("quantity") or 0)
            price = float(trade.get("price") or 0)
            fee = float(trade.get("fee") or 0)
            amount = float(trade.get("amount") or (price * qty))
            if trade_id <= 0 or qty <= 0 or price <= 0 or side not in {"BUY", "SELL"}:
                warnings.append(f"invalid trade skipped: trade_id={trade_id}, side={side}, qty={qty}, price={price}")
                continue

            cash_before = cash_balance
            realized_delta = 0.0
            if side == "BUY":
                if int(state["qty"]) == 0:
                    state["cycle_buy"] = 0.0
                    state["cycle_sell"] = 0.0
                    state["cycle_fee"] = 0.0
                next_qty = int(state["qty"]) + qty
                state["avg"] = ((int(state["qty"]) * float(state["avg"])) + amount) / max(1, next_qty)
                state["qty"] = next_qty
                state["cycle_buy"] = float(state["cycle_buy"]) + amount
                state["cycle_fee"] = float(state["cycle_fee"]) + fee
                cash_delta = -(amount + fee)
                event_type = "BUY" if next_qty == qty else "ADDITIONAL_BUY"
            else:
                if qty > int(state["qty"]):
                    warnings.append(f"sell quantity exceeded: session_id={session_id}, trade_id={trade_id}, position={state['qty']}, sell={qty}")
                    continue
                next_qty = int(state["qty"]) - qty
                state["qty"] = next_qty
                state["cycle_sell"] = float(state["cycle_sell"]) + amount
                state["cycle_fee"] = float(state["cycle_fee"]) + fee
                cash_delta = amount - fee
                event_type = "FULL_SELL" if next_qty == 0 else "PARTIAL_SELL"
                if next_qty == 0:
                    realized_delta = round(float(state["cycle_sell"]) - float(state["cycle_buy"]) - float(state["cycle_fee"]), 4)
                    realized_pnl += realized_delta
                    state["realized_profit"] = float(state["realized_profit"]) + realized_delta
                    state["avg"] = 0.0
                    state["cycle_buy"] = 0.0
                    state["cycle_sell"] = 0.0
                    state["cycle_fee"] = 0.0

            cash_balance = round(cash_balance + cash_delta, 4)
            if cash_balance < -0.0001:
                warnings.append(f"cash balance became negative: trade_id={trade_id}, cash={cash_balance}")
            ledger_events.append(
                {
                    "training_account_id": account_id,
                    "simulation_session_id": session_id,
                    "simulation_trade_id": trade_id,
                    "event_type": event_type,
                    "event_key": f"simulation_trade:{trade_id}",
                    "cash_delta": round(cash_delta, 4),
                    "cash_before": round(cash_before, 4),
                    "cash_after": cash_balance,
                    "realized_pnl_delta": realized_delta,
                    "realized_equity_after": round(initial_capital + realized_pnl, 4),
                    "description": "rebuilt from simulation_trades",
                    "metadata": {"side": side, "amount": round(amount, 4), "fee": round(fee, 4), "quantity": qty, "price": price},
                    "created_at": trade.get("created_at") or None,
                }
            )

        calculated_realized_pnl = round(sum(float(item.get("net_pnl") or 0) for item in closed_trades), 4)
        calculated_realized_equity = round(initial_capital + calculated_realized_pnl, 4)
        open_position_market_value = 0.0
        open_position_cost = 0.0
        open_position_count = 0
        session_updates: list[dict[str, Any]] = []
        for session_id, state in session_states.items():
            qty = int(state["qty"])
            avg = round(float(state["avg"]), 4) if qty > 0 else 0.0
            if qty > 0:
                open_position_count += 1
                open_position_cost += avg * qty
                session = session_map.get(session_id)
                try:
                    current_candle = self._current_price_row(session) if session else None
                except HTTPException:
                    current_candle = None
                current_price = float(current_candle.get("close_price") or avg) if current_candle else avg
                open_position_market_value += current_price * qty
            session_updates.append(
                {
                    "session_id": session_id,
                    "cash": round(cash_balance, 4),
                    "position_qty": qty,
                    "avg_price": avg,
                    "realized_profit": round(float(state["realized_profit"]), 4),
                }
            )
        open_position_market_value = round(open_position_market_value, 4)
        unrealized_pnl = round(open_position_market_value - open_position_cost, 4)
        current_training_equity = round(cash_balance + open_position_market_value, 4)

        cash_difference = round(cash_balance - stored_cash_balance, 4)
        realized_equity_difference = round(calculated_realized_equity - stored_realized_equity, 4)
        ledger_after = len(ledger_events)
        is_consistent_before = abs(cash_difference) <= 0.0001 and abs(realized_equity_difference) <= 0.0001
        cash_identity_difference = round((cash_balance + open_position_market_value) - current_training_equity, 4)
        equity_identity_difference = round(current_training_equity - (cash_balance + open_position_market_value), 4)
        performance_identity_difference = 0.0

        if apply_changes and not warnings:
            self.repo.replace_account_ledger_and_balances(
                account_id,
                ledger_events,
                cash_balance=round(cash_balance, 4),
                realized_equity=calculated_realized_equity,
                session_updates=session_updates,
            )
        return {
            "account_id": account_id,
            "account_name": account.get("name"),
            "initial_capital": initial_capital,
            "session_count": len(sessions),
            "trade_event_count": len(trade_events),
            "closed_trade_count": len(closed_trades),
            "open_position_count": open_position_count,
            "stored_cash_balance": stored_cash_balance,
            "calculated_cash_balance": round(cash_balance, 4),
            "cash_difference": cash_difference,
            "stored_realized_equity": stored_realized_equity,
            "calculated_realized_equity": calculated_realized_equity,
            "realized_equity_difference": realized_equity_difference,
            "calculated_realized_pnl": calculated_realized_pnl,
            "open_position_market_value": open_position_market_value,
            "unrealized_pnl": unrealized_pnl,
            "current_training_equity": current_training_equity,
            "ledger_event_count_before": ledger_before,
            "ledger_event_count_after": ledger_after,
            "cash_identity_difference": cash_identity_difference,
            "equity_identity_difference": equity_identity_difference,
            "performance_identity_difference": performance_identity_difference,
            "is_consistent_before": is_consistent_before,
            "is_consistent_after": not warnings,
            "applied": bool(apply_changes and not warnings),
            "warnings": warnings,
        }

    def delete_training_account(self, account_id: int) -> dict[str, Any]:
        self.get_training_account(account_id)
        counts = self.repo.delete_training_account(account_id)
        return {"deleted": True, "account_id": account_id, "message": "훈련계좌가 삭제되었습니다.", **counts}

    def get_training_calendar(self, month: str) -> dict[str, Any]:
        if not month or len(month) != 7:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="month must be YYYY-MM")
        try:
            datetime.strptime(month, "%Y-%m")
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="month must be YYYY-MM") from exc

        items: list[dict[str, Any]] = []
        for row in self.repo.list_calendar_sessions(month):
            completed_at = str(row.get("completed_at") or "")
            completed_date = completed_at[:10]
            if not completed_date:
                continue
            return_rate = self._calendar_return_rate(row)
            review_done = self._calendar_review_done(row)
            session_id = int(row["id"])
            items.append(
                {
                    "calendar_item_id": f"STANDALONE:{session_id}",
                    "training_type": "STANDALONE",
                    "completed_date": completed_date,
                    "completed_at": completed_at or None,
                    "session_id": session_id,
                    "closed_trade_id": None,
                    "training_account_id": None,
                    "training_account_name": None,
                    "stock_code": str(row.get("stock_code") or "") or None,
                    "stock_name": str(row.get("stock_name") or row.get("stock_code") or "종목 미상"),
                    "chart_entry_date": row.get("start_date"),
                    "chart_exit_date": row.get("current_date") or row.get("end_date"),
                    "net_pnl": round(float(row.get("realized_profit") or 0), 4),
                    "return_rate": return_rate,
                    "result_type": self._calendar_result_type(return_rate),
                    "scenario_execution_rate": None,
                    "review_status": str(row.get("review_status") or "미복기"),
                    "review_done": review_done,
                }
            )

        for account in self.repo.list_training_accounts():
            account_id = int(account["id"])
            account_name = str(account.get("name") or f"훈련계좌 #{account_id}")
            review_cache: dict[int, dict[str, Any] | None] = {}
            scenario_cache: dict[int, list[dict[str, Any]]] = {}
            for trade in self.list_training_account_closed_trades(account_id)["items"]:
                completed_at = str(trade.get("completed_at") or "")
                completed_date = completed_at[:10]
                if not completed_date.startswith(month):
                    continue
                session_id = int(trade["training_session_id"])
                closed_trade_id = str(trade.get("closed_trade_id") or trade.get("id") or "")
                if session_id not in review_cache:
                    review_cache[session_id] = self.repo.get_review(session_id)
                review = review_cache[session_id] or {}
                if session_id not in scenario_cache:
                    scenario_cache[session_id] = self.repo.list_risk_scenarios_by_session(session_id)
                scenario = next(
                    (
                        candidate
                        for candidate in scenario_cache[session_id]
                        if str(candidate.get("closed_trade_id") or "") == closed_trade_id
                    ),
                    None,
                )
                scenario_rate = None
                if scenario:
                    scenario_rate = self.get_risk_scenario_execution_review(int(scenario["id"])).get("overall_execution_rate")
                return_rate = round(float(trade.get("return_pct") or 0), 4)
                review_done = self._calendar_review_done(review)
                items.append(
                    {
                        "calendar_item_id": f"ACCOUNT:{closed_trade_id}",
                        "training_type": "ACCOUNT",
                        "completed_date": completed_date,
                        "completed_at": completed_at or None,
                        "session_id": session_id,
                        "closed_trade_id": closed_trade_id,
                        "training_account_id": account_id,
                        "training_account_name": account_name,
                        "stock_code": str(trade.get("stock_code") or "") or None,
                        "stock_name": str(trade.get("stock_name") or trade.get("stock_code") or "종목 미상"),
                        "chart_entry_date": trade.get("chart_entry_date") or trade.get("opened_chart_date"),
                        "chart_exit_date": trade.get("chart_exit_date") or trade.get("closed_chart_date"),
                        "net_pnl": round(float(trade.get("net_pnl") or 0), 4),
                        "return_rate": return_rate,
                        "result_type": str(trade.get("result_type") or self._calendar_result_type(return_rate)),
                        "scenario_execution_rate": scenario_rate,
                        "review_status": str(review.get("review_status") or "미복기"),
                        "review_done": review_done,
                    }
                )

        return self._build_training_calendar_response(month, items)

    @staticmethod
    def _calendar_return_rate(row: dict[str, Any]) -> float:
        initial_cash = float(row.get("initial_cash") or 0)
        realized_profit = float(row.get("realized_profit") or 0)
        if initial_cash <= 0:
            return 0.0
        return round((realized_profit / initial_cash) * 100, 4)

    @staticmethod
    def _calendar_review_done(row: dict[str, Any]) -> bool:
        status_value = str(row.get("review_status") or "").strip()
        return status_value == "복기완료" or bool(row.get("reviewed_at"))

    @staticmethod
    def _calendar_result_type(return_rate: float) -> str:
        if return_rate > 0:
            return "WIN"
        if return_rate < 0:
            return "LOSS"
        return "FLAT"

    @classmethod
    def _build_training_calendar_response(cls, month: str, raw_items: list[dict[str, Any]]) -> dict[str, Any]:
        unique_items = {
            str(item["calendar_item_id"]): item
            for item in raw_items
            if str(item.get("completed_date") or "").startswith(month)
        }
        day_bucket: dict[str, list[dict[str, Any]]] = {}
        for item in unique_items.values():
            day_bucket.setdefault(str(item["completed_date"]), []).append(item)

        days: list[dict[str, Any]] = []
        for date in sorted(day_bucket):
            day_items = sorted(
                day_bucket[date],
                key=lambda item: (
                    str(item.get("completed_at") or ""),
                    int(item.get("session_id") or 0),
                    str(item.get("calendar_item_id") or ""),
                ),
                reverse=True,
            )
            training_count = len(day_items)
            total_return = round(sum(float(item.get("return_rate") or 0) for item in day_items), 2)
            review_saved = sum(1 for item in day_items if bool(item.get("review_done")))
            stocks = {
                str(item.get("stock_code") or item.get("stock_name") or "")
                for item in day_items
                if item.get("stock_code") or item.get("stock_name")
            }
            result_counts = {
                result: sum(1 for item in day_items if str(item.get("result_type") or "").upper() == result)
                for result in ("WIN", "LOSS", "FLAT")
            }
            days.append(
                {
                    "date": date,
                    "training_count": training_count,
                    "unique_stock_count": len(stocks),
                    "total_return_rate": total_return,
                    "avg_return_rate": round(total_return / training_count, 2) if training_count else 0.0,
                    "win_count": result_counts["WIN"],
                    "loss_count": result_counts["LOSS"],
                    "flat_count": result_counts["FLAT"],
                    "review_saved_count": review_saved,
                    "review_required_count": training_count,
                    "items": day_items,
                }
            )
        daily_by_date = {str(day["date"]): day for day in days}
        month_start = datetime.strptime(f"{month}-01", "%Y-%m-%d")
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        growth: list[dict[str, Any]] = []
        cumulative_return = 0.0
        cursor = month_start
        while cursor < next_month:
            date = cursor.strftime("%Y-%m-%d")
            day = daily_by_date.get(date)
            daily_return = round(float((day or {}).get("avg_return_rate") or 0), 2)
            cumulative_return = round(cumulative_return + daily_return, 2)
            growth.append(
                {
                    "date": date,
                    "training_count": int((day or {}).get("training_count") or 0),
                    "daily_return_rate": daily_return,
                    "cumulative_return_rate": cumulative_return,
                }
            )
            cursor += timedelta(days=1)

        all_items = [item for day in days for item in day["items"]]
        total_trainings = len(all_items)
        review_saved = sum(1 for item in all_items if bool(item.get("review_done")))
        unique_stocks = {
            str(item.get("stock_code") or item.get("stock_name") or "")
            for item in all_items
            if item.get("stock_code") or item.get("stock_name")
        }
        total_return = round(sum(float(item.get("return_rate") or 0) for item in all_items), 2)
        return {
            "month": month,
            "summary": {
                "total_trainings": total_trainings,
                "training_days": len(days),
                "unique_stock_count": len(unique_stocks),
                "total_return_rate": total_return,
                "avg_return_rate": round(total_return / total_trainings, 2) if total_trainings else 0.0,
                "review_completion_rate": round(review_saved / total_trainings * 100, 1) if total_trainings else 0.0,
            },
            "days": days,
            "growth": growth,
        }
    @staticmethod
    def _parse_options(session: dict[str, Any]) -> dict[str, Any]:
        raw = session.get("options_json")
        if not raw:
            return {}
        try:
            data = json.loads(str(raw))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _to_date(value: str) -> datetime:
        return datetime.strptime(value, "%Y-%m-%d")

    @staticmethod
    def _safe_rate(numerator: float, denominator: float) -> float:
        if denominator == 0:
            return 0.0
        return round(numerator / denominator * 100, 4)

    @staticmethod
    def _reason_quality(reason: Any) -> dict[str, str]:
        text = str(reason or "").strip()
        if not text:
            return {"grade": "미작성", "guide": "매매 판단 사유가 기록되지 않았습니다."}

        normalized = "".join(text.split()).lower()
        weak_words = {
            "익절",
            "손절",
            "매도",
            "매수",
            "불안",
            "느낌",
            "오를것같음",
            "떨어질것같음",
        }
        if normalized in weak_words or (len(normalized) <= 4 and normalized in weak_words):
            return {
                "grade": "부족",
                "guide": "결과나 감정 중심 표현입니다. 차트 기준, 가격 기준, 거래량 변화처럼 실제 판단 근거가 필요합니다.",
            }

        evidence_words = [
            "20선",
            "5선",
            "10선",
            "60선",
            "이동평균",
            "전고점",
            "돌파",
            "지지",
            "저항",
            "거래량",
            "거래대금",
            "이탈",
            "눌림",
            "반등",
            "추세",
        ]
        plan_words = [
            "실패",
            "손절",
            "목표",
            "비중",
            "계획",
            "기준",
            "예정",
            "재이탈",
            "분할",
            "추가매수",
            "추격매수",
        ]
        has_evidence = any(word in text for word in evidence_words)
        has_plan = any(word in text for word in plan_words)
        if has_evidence and has_plan:
            return {"grade": "충분", "guide": "객관적 근거와 대응 기준이 함께 기록되어 있습니다."}
        if has_evidence:
            return {"grade": "보통", "guide": "객관적 근거가 있습니다. 실패 기준이나 손절 기준까지 적으면 더 좋습니다."}
        if len(text) >= 12:
            return {"grade": "보통", "guide": "사유가 기록되어 있습니다. 판단 근거가 더 구체적이면 복기 품질이 좋아집니다."}
        return {
            "grade": "부족",
            "guide": "표현이 짧아 판단 근거를 재현하기 어렵습니다. 기준이 된 가격, 지표, 차트 상황을 함께 적어주세요.",
        }

    @staticmethod
    def _quality_counts(pairs: list[dict[str, Any]], field: str) -> dict[str, int]:
        counts = {"충분": 0, "보통": 0, "부족": 0, "미작성": 0}
        for pair in pairs:
            grade = str(pair.get(field) or "미작성")
            counts[grade if grade in counts else "미작성"] += 1
        return counts

    @staticmethod
    def _quality_summary_text(counts: dict[str, int]) -> str:
        return " / ".join(f"{label} {counts.get(label, 0)}건" for label in ["충분", "보통", "부족", "미작성"])

    @staticmethod
    def _label_list(values: Any, labels: dict[str, str]) -> str:
        if not isinstance(values, list) or not values:
            return "기록 없음"
        return ", ".join(labels.get(str(value), str(value)) for value in values)

    @staticmethod
    def _label_value(value: Any, labels: dict[str, str], empty: str = "기록 없음") -> str:
        text = str(value or "").strip()
        if not text:
            return empty
        return labels.get(text, text)

    @staticmethod
    def _has_text(value: Any) -> bool:
        return bool(str(value or "").strip())

    def _method_review_stats(self, pairs: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(pairs)
        buy_reviews = [pair.get("buy_method_review") for pair in pairs if isinstance(pair.get("buy_method_review"), dict)]
        sell_reviews = [pair.get("sell_method_review") for pair in pairs if isinstance(pair.get("sell_method_review"), dict)]
        failure_count = sum(1 for review in buy_reviews if self._has_text(review.get("failure_criteria")))
        stop_loss_count = sum(1 for review in buy_reviews if self._has_text(review.get("stop_loss_rule")))
        target_exit_count = sum(1 for review in buy_reviews if self._has_text(review.get("target_exit_rule")))
        add_buy_count = sum(
            1
            for review in buy_reviews
            if self._has_text(review.get("add_buy_condition"))
            or str(review.get("add_buy_plan_type") or "") not in {"", "none", "undecided"}
        )
        method_fit_count = sum(1 for review in buy_reviews if self._has_text(review.get("method_fit")))
        plan_aligned_count = sum(1 for review in sell_reviews if str(review.get("plan_alignment") or "") in {"match", "partial"})
        no_initial_plan_count = sum(1 for review in sell_reviews if str(review.get("plan_alignment") or "") == "none")
        chase_buy_count = sum(1 for review in buy_reviews if "chase_risk" in list(review.get("entry_type_tags") or []))
        emotion_sell_count = sum(1 for review in sell_reviews if "emotion_risk" in list(review.get("exit_type_tags") or []))
        return {
            "total_pairs": total,
            "buy_review_count": len(buy_reviews),
            "sell_review_count": len(sell_reviews),
            "failure_criteria_count": failure_count,
            "stop_loss_rule_count": stop_loss_count,
            "target_exit_rule_count": target_exit_count,
            "add_buy_plan_count": add_buy_count,
            "method_fit_count": method_fit_count,
            "plan_aligned_count": plan_aligned_count,
            "no_initial_plan_count": no_initial_plan_count,
            "chase_buy_count": chase_buy_count,
            "emotion_sell_count": emotion_sell_count,
        }

    def _format_buy_method_review(self, review: Any) -> str:
        review = review if isinstance(review, dict) else {}
        entry_labels = {
            "planned": "계획 매수",
            "confirmation": "확인 매수",
            "pullback": "눌림 매수",
            "breakout": "돌파 매수",
            "add_buy": "추가매수",
            "early_entry": "조기 진입",
            "chase_risk": "추격매수 가능성 있음",
            "test": "테스트 매수",
        }
        fit_labels = {"fit": "충족", "partial": "일부 충족", "miss": "미충족", "hold": "판단 보류"}
        add_buy_labels = {
            "none": "추가매수 계획 없음",
            "pullback": "눌림 시 추가매수",
            "breakout": "돌파 확인 시 추가매수",
            "loss": "손실 구간 추가매수",
            "profit": "수익 구간 추가매수",
            "undecided": "아직 정하지 않음",
        }
        return "\n".join(
            [
                "[매매기법 기준 복기 - 매수]",
                f"- 선택한 복기 카드: {self._text(review.get('selected_template'), '기록 없음')}",
                f"- 매수 유형: {self._label_list(review.get('entry_type_tags'), entry_labels)}",
                f"- 매매기법 기준 충족 여부: {self._label_value(review.get('method_fit'), fit_labels)}",
                f"- 근거가 된 매수조건: {self._text(review.get('matched_entry_rules'), '기록 없음')}",
                f"- 주의 또는 위반 조건: {self._text(review.get('risk_or_violation_notes'), '기록 없음')}",
                f"- 실패 기준: {self._text(review.get('failure_criteria'), '기록 없음')}",
                f"- 손절 기준: {self._text(review.get('stop_loss_rule'), '기록 없음')}",
                f"- 목표 / 청산 기준: {self._text(review.get('target_exit_rule'), '기록 없음')}",
                f"- 추가매수 기준: {self._label_value(review.get('add_buy_plan_type'), add_buy_labels)}",
                f"- 추가매수 조건: {self._text(review.get('add_buy_condition'), '기록 없음')}",
                f"- 총 비중 계획: {self._text(review.get('max_position_plan'), '기록 없음')}",
                f"- 추가매수 후 손절 기준: {self._text(review.get('add_buy_stop_loss_rule'), '기록 없음')}",
            ]
        )

    def _format_sell_method_review(self, review: Any) -> str:
        review = review if isinstance(review, dict) else {}
        exit_labels = {
            "planned": "계획 매도",
            "target_reached": "목표 도달",
            "stop_loss": "손절",
            "reduce": "비중 축소",
            "profit_protection": "수익 보호",
            "trend_break": "추세 이탈",
            "resistance": "저항 도달",
            "spike_burden": "급등 부담",
            "emotion_risk": "감정 매도 가능성",
            "other": "기타",
        }
        fit_labels = {"fit": "매매기법 기준에 따른 매도", "partial": "일부 기준에 따른 매도", "unrelated": "기준과 무관한 매도", "none": "최초 계획이 없었음"}
        align_labels = {"match": "일치", "partial": "일부 일치", "mismatch": "불일치", "none": "최초 계획 없음"}
        return "\n".join(
            [
                "[매매기법 기준 복기 - 매도]",
                f"- 선택한 복기 카드: {self._text(review.get('selected_template'), '기록 없음')}",
                f"- 매도 유형: {self._label_list(review.get('exit_type_tags'), exit_labels)}",
                f"- 매매기법 기준 매도 여부: {self._label_value(review.get('method_exit_fit'), fit_labels)}",
                f"- 근거가 된 매도조건: {self._text(review.get('matched_exit_rules'), '기록 없음')}",
                f"- 최초 계획과 일치 여부: {self._label_value(review.get('plan_alignment'), align_labels)}",
                f"- 매도 사유 상세: {self._text(review.get('exit_reason_detail'), '기록 없음')}",
                f"- 매도 후 복기 메모: {self._text(review.get('after_review_memo'), '기록 없음')}",
            ]
        )

    @staticmethod
    def _clean_mas(values: list[int]) -> list[int]:
        cleaned = sorted({int(v) for v in values if int(v) > 0 and int(v) <= 240})
        return cleaned or [5, 20, 60]

    def _session_prices(self, session: dict[str, Any]) -> list[dict[str, Any]]:
        options = self._parse_options(session)
        return self.repo.list_prices(
            stock_id=int(options.get("stock_id") or 0),
            source=str(options.get("source") or ""),
            start_date=str(session["start_date"]),
            end_date=str(session["end_date"]),
        )

    def _current_price_row(self, session: dict[str, Any]) -> dict[str, Any]:
        prices = self._session_prices(session)
        if not prices:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="가격 데이터가 없습니다.")
        current_index = min(max(int(session.get("current_index") or 0), 0), len(prices) - 1)
        return prices[current_index]

    def _default_start_date(self, rows: list[dict[str, Any]]) -> str:
        if not rows:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="가격 데이터가 없습니다.")
        latest = self._to_date(str(rows[-1]["trade_date"]))
        cutoff = (latest - timedelta(days=730)).strftime("%Y-%m-%d")
        for row in rows:
            if str(row["trade_date"]) >= cutoff:
                return str(row["trade_date"])
        return str(rows[0]["trade_date"])

    def create_session(self, payload: TrainingSessionCreate) -> dict[str, Any]:
        stock = self.repo.get_stock_by_code(payload.stock_code)
        if not stock:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="종목을 찾을 수 없습니다.")
        source = self.repo.resolve_price_source(int(stock["stock_id"]))
        if source is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="가격 데이터가 없습니다.")

        all_rows = self.repo.list_prices(stock_id=int(stock["stock_id"]), source=source)
        if not all_rows:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="가격 데이터가 없습니다.")

        start_date = payload.start_date or str(all_rows[0]["trade_date"])
        end_date = payload.end_date or str(all_rows[-1]["trade_date"])
        rows = [row for row in all_rows if start_date <= str(row["trade_date"]) <= end_date]
        if not rows:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="선택 기간에 가격 데이터가 없습니다.")

        method_id = None
        if payload.method_id:
            method = self.repo.get_trade_method(int(payload.method_id))
            if method and int(method.get("is_active") or 0) == 1:
                method_id = int(method["id"])

        account_initial_cash = float(payload.initial_cash)
        account_fee_rate = float(payload.fee_rate)
        training_account_name = None
        if payload.training_account_id:
            training_account = self.get_training_account(int(payload.training_account_id))
            if str(training_account.get("status") or "") != "ACTIVE":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "ACCOUNT_NOT_ACTIVE", "message": "활성 훈련계좌만 연결할 수 있습니다."})
            account_initial_cash = float(training_account.get("cash_balance") or training_account.get("initial_capital") or payload.initial_cash)
            account_fee_rate = float(training_account.get("commission_rate") or payload.fee_rate)
            training_account_name = training_account.get("name")

        created = self.repo.create_session(
            {
                "stock_code": stock["stock_code"],
                "stock_name": stock["stock_name"],
                "method_id": method_id,
                "training_account_id": payload.training_account_id,
                "start_date": str(rows[0]["trade_date"]),
                "end_date": str(rows[-1]["trade_date"]),
                "current_date": str(rows[0]["trade_date"]),
                "current_index": 0,
                "initial_cash": account_initial_cash,
                "cash": account_initial_cash,
                "position_qty": 0,
                "avg_price": 0,
                "realized_profit": 0,
                "status": RUNNING_STATUS,
                "options": {
                    "stock_id": int(stock["stock_id"]),
                    "source": source,
                    "fee_rate": account_fee_rate,
                    "display_days": int(payload.display_days),
                    "moving_averages": self._clean_mas(payload.moving_averages),
                    "training_account_id": payload.training_account_id,
                    "training_account_name": training_account_name,
                },
            }
        )
        self._save_snapshot(created, rows[0])
        return self.get_session_detail(int(created["id"]))

    @staticmethod
    def _calc_account(session: dict[str, Any], current_candle: dict[str, Any] | None) -> dict[str, float]:
        close = float(current_candle.get("close_price") or 0) if current_candle else 0.0
        qty = int(session.get("position_qty") or 0)
        avg_price = float(session.get("avg_price") or 0)
        cash = float(session.get("cash") or 0)
        initial_cash = float(session.get("initial_cash") or 0)
        realized_profit = float(session.get("realized_profit") or 0)
        evaluation_amount = close * qty
        position_profit = (close - avg_price) * qty if qty > 0 and avg_price > 0 else 0.0
        position_return_rate = 0 if avg_price == 0 or qty == 0 else round((close - avg_price) / avg_price * 100, 4)
        total_asset = cash + evaluation_amount
        total_profit = total_asset - initial_cash
        return {
            "current_price": round(close, 4),
            "evaluation_amount": round(evaluation_amount, 4),
            "cash_balance": round(cash, 4),
            "open_position_cost": round(avg_price * qty, 4),
            "open_position_market_value": round(evaluation_amount, 4),
            "current_training_equity": round(total_asset, 4),
            "unrealized_profit": round(position_profit, 4),
            "unrealized_return_rate": position_return_rate,
            "position_profit": round(position_profit, 4),
            "position_return_rate": position_return_rate,
            "realized_profit": round(realized_profit, 4),
            "total_asset": round(total_asset, 4),
            "total_profit": round(total_profit, 4),
            "total_return_rate": 0 if initial_cash == 0 else round(total_profit / initial_cash * 100, 4),
        }

    def _save_snapshot(self, session: dict[str, Any], current_candle: dict[str, Any]) -> None:
        account = self._calc_account(session, current_candle)
        self.repo.insert_snapshot(
            {
                "session_id": int(session["id"]),
                "trade_date": str(current_candle["trade_date"]),
                "cash": float(session.get("cash") or 0),
                "position_qty": int(session.get("position_qty") or 0),
                "avg_price": float(session.get("avg_price") or 0),
                "evaluation_amount": account["evaluation_amount"],
                "total_asset": account["total_asset"],
                "unrealized_profit": account["unrealized_profit"],
            }
        )

    @staticmethod
    def _decorate_candles(rows: list[dict[str, Any]], moving_averages: list[int]) -> list[dict[str, Any]]:
        decorated: list[dict[str, Any]] = []
        closes: list[float | None] = []
        for row in rows:
            close = None if row.get("close_price") is None else float(row["close_price"])
            closes.append(close)
            ma_values: dict[str, float | None] = {}
            for window in moving_averages:
                recent = [v for v in closes[-window:] if v is not None]
                ma_values[f"ma{window}"] = round(sum(recent) / window, 4) if len(recent) == window else None
            decorated.append(
                {
                    "trade_date": row["trade_date"],
                    "open": row.get("open_price"),
                    "high": row.get("high_price"),
                    "low": row.get("low_price"),
                    "close": row.get("close_price"),
                    "volume": row.get("volume"),
                    "trading_value": row.get("trading_value"),
                    "moving_averages": ma_values,
                }
            )
        return decorated

    def _response_session(self, session: dict[str, Any]) -> dict[str, Any]:
        data = dict(session)
        options = self._parse_options(session)
        account_id = data.get("training_account_id") or options.get("training_account_id")
        data["training_account_id"] = int(account_id) if account_id else None
        data["training_account_name"] = options.get("training_account_name")
        data["is_account_linked"] = data["training_account_id"] is not None
        data["stock_id"] = int(options.get("stock_id")) if options.get("stock_id") else None
        data["options"] = options
        data.pop("options_json", None)
        return data

    def get_session_detail(self, session_id: int) -> dict[str, Any]:
        session = self.repo.get_session(session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="훈련 세션을 찾을 수 없습니다.")
        prices = self._session_prices(session)
        current_index = min(max(int(session.get("current_index") or 0), 0), max(len(prices) - 1, 0))
        current_candle = prices[current_index] if prices else None
        options = self._parse_options(session)
        moving_averages = self._clean_mas(list(options.get("moving_averages") or [5, 20, 60]))
        visible_prices = prices[: current_index + 1]
        indicator_warmup_count = max(moving_averages, default=1) - 1
        history_limit = TRAINING_PREVIEW_CANDLE_COUNT + indicator_warmup_count
        history_prices = self.repo.list_prices_before(
            stock_id=int(options.get("stock_id") or 0),
            source=str(options.get("source") or ""),
            before_date=str(session["start_date"]),
            limit=history_limit,
        ) if history_limit > 0 else []
        decorated_with_history = self._decorate_candles([*history_prices, *visible_prices], moving_averages)
        preview_count = min(TRAINING_PREVIEW_CANDLE_COUNT, len(history_prices))
        decorated = decorated_with_history[len(history_prices) - preview_count:]
        return {
            "session": self._response_session(session),
            "trade_method": self.repo.get_trade_method(int(session["method_id"])) if session.get("method_id") else None,
            "candles": decorated,
            "current_candle": decorated[-1] if decorated else None,
            "account": self._calc_account(session, current_candle),
            "trades": self.repo.list_trades(session_id),
            "risk_scenario": self.get_current_risk_scenario_detail(session_id),
        }

    def preview_technical_analysis(self, payload: TechnicalAnalysisPreviewRequest) -> dict[str, Any]:
        started_at = perf_counter()
        session = self.repo.get_session(payload.training_session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="훈련 세션을 찾을 수 없습니다.")
        if payload.stock_code and str(payload.stock_code) != str(session.get("stock_code") or ""):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="훈련 세션의 종목과 요청 종목이 일치하지 않습니다.")
        session_as_of = str(session.get("current_date") or session.get("start_date") or "")
        requested_as_of = str(payload.as_of_date or session_as_of)
        as_of_date = min(requested_as_of, session_as_of)
        try:
            datetime.strptime(as_of_date, "%Y-%m-%d")
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="기준일 형식이 올바르지 않습니다.") from exc
        config = normalize_configuration(payload.configuration)
        # The main replay chart intentionally remains a fixed, compact 80-candle analysis.
        config["trend_window"] = 80
        options = self._parse_options(session)
        period = payload.display_period.upper()
        display_count = 244 if period in {"1Y", "ALL"} else max(30, int(DISPLAY_PERIOD_DAYS[period] / 7 * 5) + 5)
        query_limit = min(600, max(display_count, 120) + max(120, config["trend_window"]) + config["swing_confirmation_width"] * 2)
        query_started = perf_counter()
        rows = self.repo.list_prices_through(
            stock_id=int(options.get("stock_id") or 0),
            source=str(options.get("source") or ""),
            end_date=as_of_date,
            limit=query_limit,
        )
        query_ms = (perf_counter() - query_started) * 1000
        latest_date = str(rows[-1]["trade_date"]) if rows else ""
        cache_key = "|".join((str(payload.training_session_id), str(session.get("stock_code") or ""), as_of_date, period, configuration_hash(config), latest_date))
        cached = TECHNICAL_PREVIEW_CACHE.get(cache_key)
        if cached is not None:
            cached["performance"] = {"cache_hit": True, "queried_row_count": len(rows), "query_ms": round(query_ms, 3),
                                     "calculation_ms": 0.0, "total_ms": round((perf_counter()-started_at)*1000, 3)}
            return cached
        calculation_started = perf_counter()
        result = calculate_technical_analysis(rows, as_of_date=as_of_date, display_period=period, configuration=config)
        result["performance"] = {
            "cache_hit": False, "queried_row_count": len(rows), "query_ms": round(query_ms, 3),
            "calculation_ms": round((perf_counter()-calculation_started)*1000, 3),
            "total_ms": round((perf_counter()-started_at)*1000, 3),
        }
        TECHNICAL_PREVIEW_CACHE.put(cache_key, result)
        return result

    def preview_multi_period_technical_analysis(self, payload: MultiPeriodTechnicalAnalysisRequest) -> dict[str, Any]:
        return build_multi_period_preview(self, payload)


    def _running_session(self, session_id: int) -> dict[str, Any]:
        session = self.repo.get_session(session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="훈련 세션을 찾을 수 없습니다.")
        if session.get("status") != RUNNING_STATUS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="진행 중인 세션만 처리할 수 있습니다.")
        return session

    def next_day(self, session_id: int) -> dict[str, Any]:
        session = self._running_session(session_id)
        prices = self._session_prices(session)
        current_index = int(session.get("current_index") or 0)
        if current_index >= len(prices) - 1:
            updated = self.repo.update_session(session_id, {"status": FINISHED_STATUS})
            self._save_snapshot(updated, prices[current_index])
            return self.get_session_detail(session_id)
        next_index = current_index + 1
        values: dict[str, Any] = {
            "current_index": next_index,
            "current_date": str(prices[next_index]["trade_date"]),
        }
        if next_index >= len(prices) - 1:
            values["status"] = FINISHED_STATUS
        updated = self.repo.update_session(session_id, values)
        self._save_snapshot(updated, prices[next_index])
        self.check_risk_level_reaches(session_id, str(prices[next_index]["trade_date"]))
        return self.get_session_detail(session_id)

    @staticmethod
    def _validate_price_in_candle(price: float, candle: dict[str, Any]) -> None:
        low = float(candle.get("low_price") or 0)
        high = float(candle.get("high_price") or 0)
        if low <= 0 or high <= 0 or price < low or price > high:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="주문가격이 현재 일봉 범위를 벗어났습니다.")

    def _linked_account(self, session: dict[str, Any]) -> dict[str, Any] | None:
        account_id = session.get("training_account_id")
        if not account_id:
            return None
        account = self.get_training_account(int(account_id))
        if str(account.get("status") or "") != "ACTIVE":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "ACCOUNT_NOT_ACTIVE", "message": "활성 훈련계좌만 주문할 수 있습니다."})
        return account

    def _insufficient_cash(self, available_cash: float, required_cash: float, price: float, fee_rate: float) -> HTTPException:
        per_share_required = price * (1 + fee_rate)
        max_affordable_quantity = int(available_cash // per_share_required) if per_share_required > 0 else 0
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INSUFFICIENT_CASH",
                "message": "사용 가능 현금이 부족합니다.",
                "available_cash": round(available_cash, 4),
                "required_cash": round(required_cash, 4),
                "shortage_amount": round(max(0, required_cash - available_cash), 4),
                "max_affordable_quantity": max(0, max_affordable_quantity),
            },
        )

    def _realized_equity_for_account(self, account_id: int) -> float:
        account = self.get_training_account(account_id)
        initial_capital = float(account.get("initial_capital") or 0)
        closed_trades = self.list_training_account_closed_trades(account_id)["items"]
        realized_pnl = sum(float(item.get("net_pnl") or 0) for item in closed_trades)
        return round(initial_capital + realized_pnl, 4)

    @staticmethod
    def _float_or_none(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return round(float(value), 4)
        except Exception:
            return None

    @staticmethod
    def _is_stop_plan_type(plan_type: Any) -> bool:
        return str(plan_type or "").upper() in {"STOP", "STOP_LOSS", "FULL_STOP", "PARTIAL_STOP"}

    def _normalize_sell_stop_types(self, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = [dict(step) for step in steps]
        stop_steps = sorted(
            (step for step in normalized if self._is_stop_plan_type(step.get("plan_type"))),
            key=lambda step: (float(step.get("trigger_price") or float("inf")), int(step.get("step_no") or 0)),
        )
        for index, step in enumerate(stop_steps):
            step["plan_type"] = "FULL_STOP" if index == 0 else "PARTIAL_STOP"
            step["trigger_text"] = "전량 손절 가격" if index == 0 else f"{index}차 손절 가격"
            if index == 0 and step.get("planned_ratio_pct") is None:
                step["planned_ratio_pct"] = 100.0
        return normalized

    def _risk_configuration_signature(self, scenario: dict[str, Any], buy_steps: list[dict[str, Any]], sell_steps: list[dict[str, Any]]) -> dict[str, Any]:
        scenario_fields = (
            "buy_plan_mode", "sell_plan_mode", "profit_scenario_text", "stop_scenario_text",
            "stop_price", "primary_target_price", "memo",
        )
        step_fields = (
            "plan_group", "plan_type", "step_no", "trigger_type", "trigger_price", "trigger_text",
            "planned_ratio_pct", "planned_quantity", "planned_amount", "memo",
        )
        canonical_sell = self._normalize_sell_stop_types(sell_steps)
        return {
            "scenario": {field: scenario.get(field) for field in scenario_fields},
            "buy_steps": [{field: step.get(field) for field in step_fields} for step in sorted(buy_steps, key=lambda item: int(item.get("step_no") or 0))],
            "sell_steps": [{field: step.get(field) for field in step_fields} for step in sorted(canonical_sell, key=lambda item: int(item.get("step_no") or 0))],
        }
    def _risk_snapshot(self, scenario: dict[str, Any], buy_steps: list[dict[str, Any]], sell_steps: list[dict[str, Any]], preview: dict[str, Any] | None = None) -> dict[str, Any]:
        normalized_sell = self._normalize_sell_stop_types(sell_steps)
        target_prices = sorted(float(step["trigger_price"]) for step in normalized_sell if str(step.get("plan_type") or "").upper() == "TAKE_PROFIT" and step.get("trigger_price") is not None)
        stop_prices = sorted(float(step["trigger_price"]) for step in normalized_sell if self._is_stop_plan_type(step.get("plan_type")) and step.get("trigger_price") is not None)
        return {
            "scenario": dict(scenario),
            "buy_steps": [dict(step) for step in buy_steps],
            "sell_steps": [dict(step) for step in normalized_sell],
            "price_groups": {
                "entry_prices": [float(step["trigger_price"]) for step in buy_steps if step.get("trigger_price") is not None],
                "take_profit_prices": target_prices,
                "stop_loss": {
                    "full_stop_price": stop_prices[0] if stop_prices else None,
                    "partial_stop_prices": stop_prices[1:],
                },
            },
            "preview": preview or {},
        }
    def _risk_account_basis(self, session: dict[str, Any]) -> tuple[dict[str, Any], Decimal, Decimal, Decimal]:
        account_id = session.get("training_account_id")
        if not account_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "RISK_SCENARIO_ACCOUNT_REQUIRED", "message": "Risk scenarios are available only for account-linked sessions."})
        account = self.get_training_account(int(account_id))
        summary = self.get_training_account_summary(int(account_id))
        equity = to_decimal(summary.get("current_training_equity"), Decimal("0")) or Decimal("0")
        risk_pct = to_decimal(account.get("risk_per_trade_pct"), Decimal("1")) or Decimal("1")
        budget = calculate_risk_budget(equity, risk_pct)
        return account, equity, risk_pct, budget

    def _normalize_risk_steps(self, raw_steps: list[Any], plan_group: str, default_plan_type: str) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        seen: set[int] = set()
        for idx, raw in enumerate(raw_steps or [], start=1):
            data = raw.model_dump() if hasattr(raw, "model_dump") else dict(raw or {})
            step_no = int(data.get("step_no") or idx)
            if step_no in seen:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "DUPLICATE_RISK_STEP", "message": f"Duplicate {plan_group} step_no: {step_no}"})
            seen.add(step_no)
            normalized.append({
                "plan_group": plan_group,
                "plan_type": str(data.get("plan_type") or default_plan_type).upper(),
                "step_no": step_no,
                "status": str(data.get("status") or "PLANNED").upper(),
                "trigger_type": str(data.get("trigger_type") or "CUSTOM").upper(),
                "trigger_price": self._float_or_none(data.get("trigger_price")),
                "trigger_text": str(data.get("trigger_text") or ""),
                "planned_ratio_pct": self._float_or_none(data.get("planned_ratio_pct")),
                "planned_quantity": int(data.get("planned_quantity") or 0) if data.get("planned_quantity") is not None else None,
                "planned_amount": self._float_or_none(data.get("planned_amount")),
                "memo": data.get("memo"),
                "executed_trade_id": data.get("executed_trade_id"),
            })
        ordered = sorted(normalized, key=lambda item: int(item["step_no"]))
        return self._normalize_sell_stop_types(ordered) if plan_group == "SELL" else ordered

    def calculate_risk_scenario_preview(self, session_id: int, payload: TradeTrainingRiskScenarioDraftRequest | None = None, scenario: dict[str, Any] | None = None, buy_steps: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        session = self.repo.get_session(session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="training session not found")
        _, equity, risk_pct, budget = self._risk_account_basis(session)
        if payload is not None:
            stop_price = to_decimal(payload.stop_price)
            steps = self._normalize_risk_steps(payload.buy_steps, "BUY", "ENTRY")
        else:
            stop_price = to_decimal((scenario or {}).get("stop_price"))
            steps = buy_steps or []
        planned_loss = calculate_scenario_planned_loss(steps, stop_price)
        usage = calculate_risk_usage_pct(planned_loss, budget)
        warnings: list[str] = []
        buy_ratio = sum(float(step.get("planned_ratio_pct") or 0) for step in steps)
        if steps and round(buy_ratio, 4) != 100:
            warnings.append(f"BUY_RATIO_SUM_{round(buy_ratio, 4)}")
        if planned_loss is not None and planned_loss > budget:
            warnings.append("PLANNED_LOSS_EXCEEDS_RISK_BUDGET")
        if stop_price is None:
            warnings.append("STOP_PRICE_MISSING")
        return {
            "risk_basis_equity": float(equity),
            "account_risk_pct": float(risk_pct),
            "risk_budget_amount": float(budget),
            "estimated_planned_loss": None if planned_loss is None else float(planned_loss),
            "estimated_risk_usage_pct": None if usage is None else float(usage),
            "warnings": warnings,
        }

    @staticmethod
    def _severity_rank(value: str) -> int:
        return {"UNAVAILABLE": 0, "INFO": 1, "CAUTION": 2, "WARNING": 3}.get(value, 0)

    def _holding_risk_summary(self, session: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
        quantity = int(session.get("position_qty") or 0)
        average_price = to_decimal(session.get("avg_price"))
        stop_price = to_decimal(scenario.get("stop_price"))
        current_price = to_decimal(self._current_price_row(session).get("close"), Decimal("0")) or Decimal("0")
        fee_rate = to_decimal(self._parse_options(session).get("fee_rate"), Decimal("0")) or Decimal("0")
        exit_cost = current_price * Decimal(quantity) * fee_rate
        estimated_risk = calculate_position_risk(average_price, stop_price, quantity, exit_cost)
        budget = to_decimal(scenario.get("risk_budget_amount"))
        usage = calculate_risk_usage_pct(estimated_risk, budget)
        return {
            "current_estimated_risk": None if estimated_risk is None else float(estimated_risk),
            "risk_usage_pct": None if usage is None else float(usage),
            "severity": classify_risk_usage(usage),
            "stop_price": None if stop_price is None else float(stop_price),
        }

    def calculate_risk_order_preview(self, session_id: int, payload: RiskOrderPreviewRequest) -> dict[str, Any]:
        session = self._running_session(session_id)
        if not session.get("training_account_id"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "ACCOUNT_LINK_REQUIRED", "message": "계좌연동 세션에서만 리스크 주문 미리보기를 사용할 수 있습니다."})
        side = str(payload.side or "").upper()
        if side not in {"BUY", "SELL"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="side must be BUY or SELL")
        scenario = self.repo.get_active_risk_scenario(session_id) or self.repo.get_current_risk_scenario(session_id)
        if not scenario:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "RISK_SCENARIO_REQUIRED", "message": "리스크 시나리오가 없습니다."})
        revision = self.repo.get_latest_risk_scenario_revision(int(scenario["id"]))
        current_qty = int(session.get("position_qty") or 0)
        current_avg = float(session.get("avg_price") or 0)
        order_qty = int(payload.quantity)
        order_price = float(payload.price)
        if side == "SELL" and order_qty > current_qty:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="보유수량이 부족합니다.")
        projected_qty = current_qty + order_qty if side == "BUY" else current_qty - order_qty
        projected_avg = ((current_qty * current_avg) + (order_qty * order_price)) / projected_qty if side == "BUY" and projected_qty > 0 else (current_avg if projected_qty > 0 else 0.0)
        stop_price = to_decimal(scenario.get("stop_price"))
        budget = to_decimal(scenario.get("risk_budget_amount"))
        fee_rate = to_decimal(self._parse_options(session).get("fee_rate"), Decimal("0")) or Decimal("0")
        current_price = to_decimal(self._current_price_row(session).get("close"), Decimal("0")) or Decimal("0")
        current_exit_cost = current_price * Decimal(current_qty) * fee_rate
        projected_exit_price = Decimal(str(order_price)) if side == "BUY" else current_price
        projected_exit_cost = projected_exit_price * Decimal(projected_qty) * fee_rate
        current_risk = calculate_position_risk(to_decimal(current_avg), stop_price, current_qty, current_exit_cost)
        projected_risk = calculate_position_risk(to_decimal(projected_avg), stop_price, projected_qty, projected_exit_cost)
        usage = calculate_risk_usage_pct(projected_risk, budget)
        severity = classify_risk_usage(usage)
        warnings: list[dict[str, str]] = []
        selected_step = self.repo.get_risk_plan_step(int(payload.risk_plan_step_id)) if payload.risk_plan_step_id else None
        expected_group = "BUY" if side == "BUY" else "SELL"
        if selected_step and (int(selected_step.get("risk_scenario_id") or 0) != int(scenario["id"]) or str(selected_step.get("plan_group") or "").upper() != expected_group or str(selected_step.get("status") or "").upper() != "PLANNED"):
            selected_step = None
        if selected_step is None and side == "SELL" and hasattr(self.repo, "list_risk_plan_steps"):
            planned_sell = self._normalize_sell_stop_types([
                step for step in self.repo.list_risk_plan_steps(int(scenario["id"]))
                if str(step.get("plan_group") or "").upper() == "SELL"
                and str(step.get("status") or "PLANNED").upper() == "PLANNED"
                and step.get("trigger_price") is not None
            ])
            full_stop_step = next((step for step in planned_sell if str(step.get("plan_type") or "").upper() == "FULL_STOP"), None)
            if full_stop_step and order_price <= float(full_stop_step.get("trigger_price") or 0):
                selected_step = full_stop_step
            else:
                candidates = [step for step in planned_sell if str(step.get("plan_type") or "").upper() != "FULL_STOP"]
                if candidates:
                    selected_step = min(candidates, key=lambda step: abs(float(step.get("trigger_price") or order_price) - order_price))
        price_deviation_pct = None
        if selected_step and selected_step.get("trigger_price"):
            planned_price = float(selected_step["trigger_price"])
            price_deviation_pct = ((order_price - planned_price) / planned_price) * 100 if planned_price else None
            if price_deviation_pct is not None and abs(price_deviation_pct) > 1:
                code = "BUY_PRICE_DEVIATION" if side == "BUY" else "SELL_PRICE_DEVIATION"
                warnings.append({"code": code, "severity": "CAUTION", "message": f"계획가격과 주문가격 차이가 {price_deviation_pct:+.2f}%입니다."})
        else:
            code = "UNPLANNED_BUY" if side == "BUY" else "UNPLANNED_SELL"
            warnings.append({"code": code, "severity": "CAUTION", "message": f"계획 외 {('매수' if side == 'BUY' else '매도')}로 기록됩니다."})
        selected_plan_type = str((selected_step or {}).get("plan_type") or "").upper()
        if side == "SELL" and selected_plan_type == "FULL_STOP" and order_qty < current_qty:
            warnings.append({"code": "FULL_STOP_PARTIAL_QUANTITY", "severity": "CAUTION", "message": f"전량 손절 계획을 선택했지만 일부 수량만 매도합니다. 보유 {current_qty}주 · 매도 {order_qty}주 · 잔여 {projected_qty}주"})
        if side == "SELL" and selected_plan_type == "PARTIAL_STOP" and projected_qty == 0:
            warnings.append({"code": "PARTIAL_STOP_FULL_QUANTITY", "severity": "CAUTION", "message": "분할 손절 계획과 연결했지만 이번 주문으로 전량 매도되어 시나리오가 종료됩니다."})
        if side == "BUY" and stop_price is not None and Decimal(str(order_price)) <= stop_price:
            warnings.append({"code": "STOP_AREA_BUY", "severity": "WARNING", "message": "계획상 손절 검토 구간에서 추가매수를 시도하고 있습니다."})
        if usage is not None and usage > Decimal("100"):
            warnings.append({"code": "RISK_BUDGET_EXCEEDED", "severity": "WARNING", "message": "주문 후 예상 위험이 계좌 위험예산을 초과합니다."})
        elif usage is not None and usage >= Decimal("80"):
            warnings.append({"code": "RISK_BUDGET_NEAR_LIMIT", "severity": "CAUTION", "message": "계좌 위험예산에 근접했습니다."})
        for warning in warnings:
            if self._severity_rank(warning["severity"]) > self._severity_rank(severity):
                severity = warning["severity"]
        return {
            "scenario_id": int(scenario["id"]),
            "revision_id": int(revision["id"]) if revision else None,
            "selected_step": selected_step,
            "current_position": {"quantity": current_qty, "average_price": current_avg},
            "projected_position": {"quantity": projected_qty, "average_price": round(projected_avg, 4)},
            "stop_price": None if stop_price is None else float(stop_price),
            "risk_budget_amount": None if budget is None else float(budget),
            "current_estimated_risk": None if current_risk is None else float(current_risk),
            "projected_estimated_risk": None if projected_risk is None else float(projected_risk),
            "risk_usage_pct": None if usage is None else float(usage),
            "severity": severity,
            "price_deviation_pct": price_deviation_pct,
            "warnings": warnings,
        }
    def _risk_scenario_detail(self, scenario: dict[str, Any] | None) -> dict[str, Any]:
        if not scenario:
            return {"scenario": None, "buy_steps": [], "sell_steps": [], "latest_revision": None, "preview": None, "requires_plan_before_buy": True, "holding_risk": None, "events": []}
        steps = [
            step
            for step in self.repo.list_risk_plan_steps(int(scenario["id"]))
            if str(step.get("status") or "PLANNED").upper() != "CANCELLED" and not bool(step.get("is_removed"))
        ]
        buy_steps = [step for step in steps if str(step.get("plan_group") or "").upper() == "BUY"]
        sell_steps = self._normalize_sell_stop_types([step for step in steps if str(step.get("plan_group") or "").upper() == "SELL"])
        normalized_scenario = dict(scenario)
        full_stop = next((step for step in sell_steps if str(step.get("plan_type") or "").upper() == "FULL_STOP"), None)
        if full_stop:
            normalized_scenario["stop_price"] = self._float_or_none(full_stop.get("trigger_price"))
        preview = self.calculate_risk_scenario_preview(int(scenario["simulation_session_id"]), scenario=normalized_scenario, buy_steps=buy_steps)
        latest_revision = self.repo.get_latest_risk_scenario_revision(int(scenario["id"]))
        events = self.repo.list_risk_events(int(scenario["simulation_session_id"]))
        return {
            "scenario": normalized_scenario,
            "buy_steps": buy_steps,
            "sell_steps": sell_steps,
            "latest_revision": latest_revision,
            "preview": preview,
            "requires_plan_before_buy": False,
            "holding_risk": self._holding_risk_summary(self.repo.get_session(int(scenario["simulation_session_id"])) or {}, scenario) if str(scenario.get("status") or "").upper() == "ACTIVE" else None,
            "events": [self._public_risk_event(event) for event in events],
            "pending_responses": self._pending_risk_responses(events),
        }

    def get_current_risk_scenario_detail(self, session_id: int) -> dict[str, Any]:
        session = self.repo.get_session(session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="training session not found")
        if not session.get("training_account_id"):
            return {"scenario": None, "buy_steps": [], "sell_steps": [], "latest_revision": None, "preview": None, "requires_plan_before_buy": False, "holding_risk": None, "events": []}
        return self._risk_scenario_detail(self.repo.get_current_risk_scenario(session_id))

    def create_or_update_risk_scenario_draft(self, session_id: int, payload: TradeTrainingRiskScenarioDraftRequest) -> dict[str, Any]:
        session = self.repo.get_session(session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="training session not found")
        if not session.get("training_account_id"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "ACCOUNT_LINK_REQUIRED", "message": "Risk scenarios require an account-linked session."})
        if self.repo.get_active_risk_scenario(session_id) and not self.repo.get_draft_risk_scenario(session_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "ACTIVE_SCENARIO_EXISTS", "message": "Cannot create a draft while an active risk scenario exists."})
        buy_steps = self._normalize_risk_steps(payload.buy_steps, "BUY", "ENTRY")
        sell_steps = self._normalize_risk_steps(payload.sell_steps, "SELL", "TAKE_PROFIT")
        full_stop = next((step for step in sell_steps if str(step.get("plan_type") or "").upper() == "FULL_STOP"), None)
        targets = sorted((step for step in sell_steps if str(step.get("plan_type") or "").upper() == "TAKE_PROFIT" and step.get("trigger_price") is not None), key=lambda step: float(step["trigger_price"]))
        if not buy_steps:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "BUY_STEPS_REQUIRED", "message": "At least one buy plan step is required."})
        if not full_stop:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "FULL_STOP_REQUIRED", "message": "A full-stop price is required before the first buy."})
        payload.stop_price = self._float_or_none(full_stop.get("trigger_price"))
        payload.primary_target_price = self._float_or_none(targets[0].get("trigger_price")) if targets else None
        preview = self.calculate_risk_scenario_preview(session_id, payload=payload)
        values = {
            "training_account_id": int(session["training_account_id"]),
            "simulation_session_id": session_id,
            "status": "DRAFT",
            "buy_plan_mode": str(payload.buy_plan_mode or "SINGLE").upper(),
            "sell_plan_mode": str(payload.sell_plan_mode or "SPLIT").upper(),
            "risk_basis_equity": preview["risk_basis_equity"],
            "account_risk_pct": preview["account_risk_pct"],
            "risk_budget_amount": preview["risk_budget_amount"],
            "profit_scenario_text": payload.profit_scenario_text.strip(),
            "stop_scenario_text": payload.stop_scenario_text.strip(),
            "stop_price": payload.stop_price,
            "primary_target_price": payload.primary_target_price,
            "estimated_planned_loss": preview["estimated_planned_loss"],
            "estimated_risk_usage_pct": preview["estimated_risk_usage_pct"],
            "memo": payload.memo,
        }
        existing = self.repo.get_draft_risk_scenario(session_id)
        if existing:
            current_steps = [step for step in self.repo.list_risk_plan_steps(int(existing["id"])) if str(step.get("status") or "PLANNED").upper() != "CANCELLED" and not bool(step.get("is_removed"))]
            current_buy = [step for step in current_steps if str(step.get("plan_group") or "").upper() == "BUY"]
            current_sell = [step for step in current_steps if str(step.get("plan_group") or "").upper() == "SELL"]
            if self._risk_configuration_signature({**existing, **values}, buy_steps, sell_steps) == self._risk_configuration_signature(existing, current_buy, current_sell):
                return self._risk_scenario_detail(existing)
            scenario = self.repo.update_risk_scenario(int(existing["id"]), values)
            revision_type = "PRICE_LINES_UPDATED"
        else:
            scenario = self.repo.create_risk_scenario({**values, "cycle_no": self.repo.get_next_risk_scenario_cycle_no(session_id)})
            revision_type = "CREATE"
        self.repo.replace_risk_plan_steps(int(scenario["id"]), [*buy_steps, *sell_steps])
        scenario = self.repo.get_risk_scenario(int(scenario["id"])) or scenario
        self.repo.create_risk_scenario_revision(int(scenario["id"]), revision_type, self._risk_snapshot(scenario, buy_steps, sell_steps, preview), payload.change_reason)
        self.repo.db.commit()
        return self._risk_scenario_detail(scenario)

    def update_active_risk_scenario(self, scenario_id: int, payload: TradeTrainingRiskScenarioDraftRequest) -> dict[str, Any]:
        scenario = self.repo.get_risk_scenario(scenario_id)
        if not scenario:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="risk scenario not found")
        if str(scenario.get("status") or "") not in {"DRAFT", "ACTIVE"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "SCENARIO_NOT_EDITABLE", "message": "Only draft or active scenarios can be edited."})
        if scenario["status"] == "DRAFT":
            return self.create_or_update_risk_scenario_draft(int(scenario["simulation_session_id"]), payload)
        buy_steps = self._normalize_risk_steps(payload.buy_steps, "BUY", "ENTRY")
        sell_steps = self._normalize_risk_steps(payload.sell_steps, "SELL", "TAKE_PROFIT")
        full_stop = next((step for step in sell_steps if str(step.get("plan_type") or "").upper() == "FULL_STOP"), None)
        targets = sorted((step for step in sell_steps if str(step.get("plan_type") or "").upper() == "TAKE_PROFIT" and step.get("trigger_price") is not None), key=lambda step: float(step["trigger_price"]))
        payload.stop_price = self._float_or_none(full_stop.get("trigger_price")) if full_stop else None
        payload.primary_target_price = self._float_or_none(targets[0].get("trigger_price")) if targets else None
        preview = self.calculate_risk_scenario_preview(int(scenario["simulation_session_id"]), payload=payload)
        values = {
            "buy_plan_mode": str(payload.buy_plan_mode or "SINGLE").upper(),
            "sell_plan_mode": str(payload.sell_plan_mode or "SPLIT").upper(),
            "profit_scenario_text": payload.profit_scenario_text.strip(),
            "stop_scenario_text": payload.stop_scenario_text.strip(),
            "stop_price": payload.stop_price,
            "primary_target_price": payload.primary_target_price,
            "estimated_planned_loss": preview["estimated_planned_loss"],
            "estimated_risk_usage_pct": preview["estimated_risk_usage_pct"],
            "memo": payload.memo,
        }
        current_steps = [step for step in self.repo.list_risk_plan_steps(scenario_id) if str(step.get("status") or "PLANNED").upper() != "CANCELLED" and not bool(step.get("is_removed"))]
        current_buy = [step for step in current_steps if str(step.get("plan_group") or "").upper() == "BUY"]
        current_sell = [step for step in current_steps if str(step.get("plan_group") or "").upper() == "SELL"]
        if self._risk_configuration_signature({**scenario, **values}, buy_steps, sell_steps) == self._risk_configuration_signature(scenario, current_buy, current_sell):
            return self._risk_scenario_detail(scenario)
        updated = self.repo.update_risk_scenario(scenario_id, values)
        self.repo.replace_risk_plan_steps(scenario_id, [*buy_steps, *sell_steps])
        self.repo.create_risk_scenario_revision(scenario_id, "PRICE_LINES_UPDATED", self._risk_snapshot(updated, buy_steps, sell_steps, preview), payload.change_reason)
        self.repo.db.commit()
        return self._risk_scenario_detail(updated)
    def cancel_risk_scenario_draft(self, scenario_id: int) -> dict[str, Any]:
        scenario = self.repo.get_risk_scenario(scenario_id)
        if not scenario:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="risk scenario not found")
        if str(scenario.get("status") or "") != "DRAFT":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "DRAFT_ONLY", "message": "Only draft scenarios can be cancelled."})
        cancelled = self.repo.cancel_risk_scenario(scenario_id)
        self.repo.create_risk_scenario_revision(scenario_id, "CANCEL", self._risk_snapshot(cancelled, self.repo.list_risk_plan_steps(scenario_id), []), None)
        self.repo.db.commit()
        return self._risk_scenario_detail(None)

    def list_risk_scenario_revisions(self, scenario_id: int) -> dict[str, Any]:
        if not self.repo.get_risk_scenario(scenario_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="risk scenario not found")
        return {"items": self.repo.list_risk_scenario_revisions(scenario_id)}

    @staticmethod
    def _reach_response_event_type(reach_type: str, response_type: str) -> str:
        prefix = {
            "TAKE_PROFIT_REACHED": "TAKE_PROFIT",
            "PARTIAL_STOP_REACHED": "PARTIAL_STOP",
            "FULL_STOP_REACHED": "FULL_STOP",
        }.get(reach_type)
        if not prefix:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="지원하지 않는 도달 이벤트입니다.")
        normalized = str(response_type or "").upper()
        if normalized not in {"SELL", "HOLD", "PLAN_REVISED"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="지원하지 않는 대응 유형입니다.")
        return f"{prefix}_RESPONSE_{normalized}"

    @staticmethod
    def _pending_risk_responses(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        reach_types = {"TAKE_PROFIT_REACHED", "PARTIAL_STOP_REACHED", "FULL_STOP_REACHED"}
        answered = {
            int((event.get("actual_value") or {}).get("reach_event_id"))
            for event in events
            if "_RESPONSE_" in str(event.get("event_type") or "")
            and (event.get("actual_value") or {}).get("reach_event_id")
        }
        result = []
        for event in events:
            if str(event.get("event_type") or "") not in reach_types or int(event["id"]) in answered:
                continue
            planned = event.get("planned_value") or {}
            actual = event.get("actual_value") or {}
            result.append(
                {
                    "reach_event_id": int(event["id"]),
                    "event_type": event["event_type"],
                    "chart_date": event.get("chart_date"),
                    "created_at": event.get("created_at"),
                    "risk_scenario_id": event.get("risk_scenario_id"),
                    "risk_scenario_revision_id": event.get("risk_scenario_revision_id"),
                    "risk_plan_step_id": event.get("risk_plan_step_id"),
                    "step_no": planned.get("step_no"),
                    "plan_type": planned.get("plan_type"),
                    "trigger_price": planned.get("trigger_price"),
                    "day_high": actual.get("day_high"),
                    "day_low": actual.get("day_low"),
                    "position_quantity": actual.get("position_quantity"),
                    "sequence_unknown": bool(actual.get("sequence_unknown")),
                }
            )
        return result

    @staticmethod
    def _public_risk_event(event: dict[str, Any]) -> dict[str, Any]:
        actual = event.get("actual_value") or {}
        return {
            "id": event.get("id"),
            "event_type": event.get("event_type"),
            "severity": event.get("severity"),
            "message": event.get("message"),
            "acknowledged": bool(event.get("acknowledged")),
            "chart_date": event.get("chart_date"),
            "created_at": event.get("created_at"),
            "risk_scenario_id": event.get("risk_scenario_id"),
            "risk_plan_step_id": event.get("risk_plan_step_id"),
            "simulation_trade_id": event.get("simulation_trade_id"),
            "reason": actual.get("reason") or actual.get("unplanned_reason"),
            "sequence_unknown": bool(actual.get("sequence_unknown")),
        }

    def check_risk_level_reaches(self, session_id: int, chart_date: str) -> dict[str, Any]:
        session = self.repo.get_session(session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="training session not found")
        scenario = self.repo.get_active_risk_scenario(session_id)
        if not scenario:
            return {"events": [], "pending_responses": []}
        prices = self._session_prices(session)
        candle_index = next((index for index, row in enumerate(prices) if str(row.get("trade_date")) == chart_date), None)
        candle = prices[candle_index] if candle_index is not None else None
        if not candle:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="해당 차트 날짜의 가격 데이터가 없습니다.")
        day_high = float(candle.get("high_price") or 0)
        day_low = float(candle.get("low_price") or 0)
        revision = self.repo.get_latest_risk_scenario_revision(int(scenario["id"]))
        existing_events = self.repo.list_risk_events(session_id)
        answered_reach_ids = {
            int((event.get("actual_value") or {}).get("reach_event_id") or 0)
            for event in existing_events
            if "_RESPONSE_" in str(event.get("event_type") or "")
        }
        reached_rows: list[tuple[dict[str, Any], str]] = []
        for step in self.repo.list_risk_plan_steps(int(scenario["id"])):
            if str(step.get("plan_group") or "").upper() != "SELL":
                continue
            if str(step.get("status") or "PLANNED").upper() != "PLANNED" or bool(step.get("is_removed")):
                continue
            price = self._float_or_none(step.get("trigger_price"))
            plan_type = str(step.get("plan_type") or "").upper()
            event_type = {
                "TAKE_PROFIT": "TAKE_PROFIT_REACHED",
                "PARTIAL_STOP": "PARTIAL_STOP_REACHED",
                "FULL_STOP": "FULL_STOP_REACHED",
            }.get(plan_type)
            if not event_type or price is None:
                continue
            if (event_type == "TAKE_PROFIT_REACHED" and day_high >= price) or (
                event_type != "TAKE_PROFIT_REACHED" and day_low <= price
            ):
                previous_candle = prices[candle_index - 1] if candle_index is not None and candle_index > 0 else None
                previous_still_reached = bool(
                    previous_candle
                    and (
                        (event_type == "TAKE_PROFIT_REACHED" and float(previous_candle.get("high_price") or 0) >= price)
                        or (event_type != "TAKE_PROFIT_REACHED" and float(previous_candle.get("low_price") or 0) <= price)
                    )
                )
                unresolved_episode = any(
                    int(event.get("risk_plan_step_id") or 0) == int(step["id"])
                    and str(event.get("event_type") or "") == event_type
                    and int(event.get("id") or 0) not in answered_reach_ids
                    for event in existing_events
                )
                if previous_still_reached and unresolved_episode:
                    continue
                reached_rows.append((step, event_type))
        sequence_unknown = len(reached_rows) > 1
        created = []
        for step, event_type in reached_rows:
            planned_value = {
                "plan_type": str(step.get("plan_type") or "").upper(),
                "step_no": int(step.get("step_no") or 0),
                "trigger_price": float(step.get("trigger_price") or 0),
            }
            actual_value = {
                "day_high": day_high,
                "day_low": day_low,
                "day_open": self._float_or_none(candle.get("open_price")),
                "day_close": self._float_or_none(candle.get("close_price")),
                "position_quantity": int(session.get("position_qty") or 0),
                "current_price": self._float_or_none(candle.get("close_price")),
                "sequence_unknown": sequence_unknown,
            }
            event = self.repo.insert_risk_event_no_commit(
                {
                    "training_account_id": int(scenario["training_account_id"]),
                    "simulation_session_id": session_id,
                    "risk_scenario_id": int(scenario["id"]),
                    "risk_scenario_revision_id": int(revision["id"]) if revision else None,
                    "risk_plan_step_id": int(step["id"]),
                    "simulation_trade_id": None,
                    "event_key": f"scenario:{scenario['id']}:step:{step['id']}:date:{chart_date}:event:{event_type}",
                    "event_type": event_type,
                    "severity": "WARNING" if event_type == "FULL_STOP_REACHED" else "CAUTION",
                    "planned_value": planned_value,
                    "actual_value": actual_value,
                    "message": "계획 가격에 도달했습니다. 자동 매도하지 않으며 대응을 선택해 기록합니다.",
                    "acknowledged": False,
                    "acknowledgement_note": None,
                    "chart_date": chart_date,
                }
            )
            created.append(self.repo.get_risk_event(int(event["id"])) or event)
        self.repo.db.commit()
        all_events = self.repo.list_risk_events(session_id)
        return {
            "events": [self._public_risk_event(event) for event in created],
            "pending_responses": self._pending_risk_responses(all_events),
        }

    def record_risk_level_response(self, session_id: int, payload: RiskLevelResponseRequest) -> dict[str, Any]:
        session = self.repo.get_session(session_id)
        reach = self.repo.get_risk_event(payload.reach_event_id)
        if not session or not reach or int(reach.get("simulation_session_id") or 0) != session_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="도달 이벤트를 찾을 수 없습니다.")
        event_type = self._reach_response_event_type(str(reach.get("event_type") or ""), payload.response_type)
        existing = next(
            (
                event
                for event in self.repo.list_risk_events(session_id)
                if "_RESPONSE_" in str(event.get("event_type") or "")
                and int((event.get("actual_value") or {}).get("reach_event_id") or 0) == int(reach["id"])
            ),
            None,
        )
        if existing:
            return {
                "event": self._public_risk_event(existing),
                "pending_responses": self._pending_risk_responses(self.repo.list_risk_events(session_id)),
            }
        candle = self._current_price_row(session)
        actual_value = {
            "reach_event_id": int(reach["id"]),
            "response_type": str(payload.response_type).upper(),
            "reason": (payload.reason or "").strip() or None,
            "position_quantity": int(session.get("position_qty") or 0),
            "current_price": self._float_or_none(candle.get("close_price")),
        }
        event = self.repo.insert_risk_event_no_commit(
            {
                "training_account_id": int(reach["training_account_id"]),
                "simulation_session_id": session_id,
                "risk_scenario_id": int(reach["risk_scenario_id"]),
                "risk_scenario_revision_id": reach.get("risk_scenario_revision_id"),
                "risk_plan_step_id": reach.get("risk_plan_step_id"),
                "simulation_trade_id": None,
                "event_key": f"reach:{reach['id']}:response",
                "event_type": event_type,
                "severity": "INFO",
                "planned_value": reach.get("planned_value") or {},
                "actual_value": actual_value,
                "message": "계획 가격 도달 대응을 기록했습니다.",
                "acknowledged": True,
                "acknowledgement_note": actual_value["reason"],
                "chart_date": session.get("current_date"),
            }
        )
        self.repo.db.commit()
        decoded = self.repo.get_risk_event(int(event["id"])) or event
        return {
            "event": self._public_risk_event(decoded),
            "pending_responses": self._pending_risk_responses(self.repo.list_risk_events(session_id)),
        }

    @staticmethod
    def _score_category(key: str, label: str, scores: list[float], excluded_count: int = 0) -> dict[str, Any]:
        normalized = [max(0.0, min(1.0, float(score))) for score in scores]
        if not normalized:
            return {
                "key": key, "label": label, "applicable": False, "score": None, "eligible_count": 0,
                "applicable_trade_count": 0, "applicable_item_count": 0,
                "earned_score": 0.0, "max_score": 0.0,
                "full_count": 0, "partial_count": 0, "miss_count": 0,
                "excluded_count": excluded_count,
            }
        earned_score = sum(normalized)
        max_score = float(len(normalized))
        return {
            "key": key,
            "label": label,
            "applicable": True,
            "score": round(earned_score / max_score * 100, 2),
            "eligible_count": len(normalized),
            "applicable_trade_count": 1,
            "applicable_item_count": len(normalized),
            "earned_score": round(earned_score, 4),
            "max_score": max_score,
            "full_count": sum(1 for score in normalized if score >= 1.0),
            "partial_count": sum(1 for score in normalized if 0 < score < 1.0),
            "miss_count": sum(1 for score in normalized if score <= 0),
            "excluded_count": excluded_count,
        }

    @staticmethod
    def _warning_behavior_scores(warnings: list[dict[str, Any]]) -> list[float]:
        groups: dict[tuple[Any, Any, str], list[dict[str, Any]]] = {}
        for event in warnings:
            key = (
                event.get("simulation_trade_id"),
                event.get("risk_plan_step_id"),
                str(event.get("chart_date") or ""),
            )
            groups.setdefault(key, []).append(event)
        return [1.0 if any(bool(event.get("acknowledged")) for event in rows) else 0.0 for rows in groups.values()]

    @staticmethod
    def _build_reach_episodes(
        reach_events: list[dict[str, Any]],
        response_events: list[dict[str, Any]],
        date_index: dict[str, int],
        price_rows: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        responses_by_reach = {
            int(event.get("reach_event_id") or (event.get("actual_value") or {}).get("reach_event_id")): event
            for event in response_events
            if event.get("reach_event_id") or (event.get("actual_value") or {}).get("reach_event_id")
        }
        grouped: dict[tuple[int, int, str], list[dict[str, Any]]] = {}
        for event in reach_events:
            chart_date = str(event.get("chart_date") or "")
            if chart_date not in date_index:
                continue
            key = (
                int(event.get("risk_scenario_id") or 0),
                int(event.get("risk_plan_step_id") or 0),
                str(event.get("event_type") or ""),
            )
            grouped.setdefault(key, []).append(event)

        episodes: list[dict[str, Any]] = []
        for key, rows in grouped.items():
            rows.sort(key=lambda row: (date_index[str(row.get("chart_date"))], int(row.get("id") or 0)))
            group_episodes: list[dict[str, Any]] = []
            current: dict[str, Any] | None = None
            for event in rows:
                event_index = date_index[str(event.get("chart_date"))]
                response = responses_by_reach.get(int(event.get("id") or 0))
                response_index = date_index.get(str((response or {}).get("chart_date")))
                response_ended = (
                    current is not None
                    and current.get("response_end_index") is not None
                    and event_index > int(current["response_end_index"])
                )
                if current is None or event_index != int(current["last_index"]) + 1 or response_ended:
                    current = {
                        "risk_scenario_id": key[0],
                        "risk_plan_step_id": key[1],
                        "reach_type": key[2],
                        "first_reached_chart_date": event.get("chart_date"),
                        "latest_reached_chart_date": event.get("chart_date"),
                        "start_index": event_index,
                        "last_index": event_index,
                        "reach_event_ids": [int(event.get("id") or 0)],
                        "response_event": response,
                        "response_end_index": response_index,
                        "trigger_price": event.get("trigger_price") or (event.get("planned_value") or {}).get("trigger_price"),
                    }
                    group_episodes.append(current)
                    episodes.append(current)
                else:
                    current["last_index"] = event_index
                    current["latest_reached_chart_date"] = event.get("chart_date")
                    current["reach_event_ids"].append(int(event.get("id") or 0))
                    if response:
                        current["response_event"] = response
                        current["response_end_index"] = response_index

            for episode in group_episodes:
                start_index = int(episode["start_index"])
                last_index = int(episode["last_index"])
                trigger_price = float(episode.get("trigger_price") or 0)
                if price_rows and trigger_price > 0:
                    last_index = start_index
                    for row in price_rows[start_index:]:
                        reached = (
                            float(row.get("high_price") or 0) >= trigger_price
                            if episode["reach_type"] == "TAKE_PROFIT_REACHED"
                            else float(row.get("low_price") or 0) <= trigger_price
                        )
                        if not reached:
                            break
                        last_index += 1
                    last_index = max(start_index, last_index - 1)
                    episode["last_index"] = last_index
                    if 0 <= last_index < len(price_rows):
                        episode["latest_reached_chart_date"] = price_rows[last_index].get("trade_date")
                episode["duration_bars"] = last_index - start_index + 1
                response = episode.get("response_event")
                response_index = date_index.get(str((response or {}).get("chart_date")))
                episode["response_bars"] = (
                    max(0, response_index - start_index) if response_index is not None else None
                )
                episode.pop("start_index", None)
                episode.pop("last_index", None)
                episode.pop("response_end_index", None)
                episode.pop("trigger_price", None)
        return episodes

    @staticmethod
    def _episode_distribution(episodes: list[dict[str, Any]]) -> dict[str, Any]:
        delays = [int(row["response_bars"]) for row in episodes if row.get("response_bars") is not None]
        unresolved = [row for row in episodes if row.get("response_bars") is None]
        counts = {
            "same_day": sum(1 for value in delays if value == 0),
            "one_to_two": sum(1 for value in delays if 1 <= value <= 2),
            "three_plus": sum(1 for value in delays if value >= 3),
            "held_or_unanswered": len(unresolved),
        }
        total = len(episodes)
        return {
            "unit": "EPISODE",
            "episode_count": total,
            "total": total,
            "same_day_count": counts["same_day"],
            "within_1_2_count": counts["one_to_two"],
            "over_3_count": counts["three_plus"],
            "unresolved_count": counts["held_or_unanswered"],
            "max_unresolved_bars": max((int(row.get("duration_bars") or 0) for row in unresolved), default=0),
            "counts": counts,
            "percentages": {key: round(value / total * 100, 2) if total else 0 for key, value in counts.items()},
        }

    def get_risk_scenario_execution_review(self, scenario_id: int) -> dict[str, Any]:
        scenario = self.repo.get_risk_scenario(scenario_id)
        if not scenario:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="risk scenario not found")
        steps = [
            step for step in self.repo.list_risk_plan_steps(scenario_id)
            if not bool(step.get("is_removed")) and str(step.get("status") or "").upper() != "CANCELLED"
        ]
        steps_by_id = {int(step["id"]): step for step in steps}
        scenario_trades = [
            trade
            for trade in self.repo.list_trades(int(scenario["simulation_session_id"]))
            if int(trade.get("risk_scenario_id") or 0) == scenario_id
        ]
        events = self.repo.list_risk_events_by_scenario(scenario_id)
        revisions = self.repo.list_risk_scenario_revisions(scenario_id)
        unplanned = [event for event in events if str(event.get("event_type") or "").startswith("UNPLANNED_")]
        warnings = [event for event in events if str(event.get("severity") or "").upper() == "WARNING"]
        reach_types = {"TAKE_PROFIT_REACHED", "PARTIAL_STOP_REACHED", "FULL_STOP_REACHED"}
        reach_events = [event for event in events if str(event.get("event_type") or "") in reach_types]
        response_events = [event for event in events if "_RESPONSE_" in str(event.get("event_type") or "")]
        reach_groups: dict[tuple[int, str], list[dict[str, Any]]] = {}
        for event in reach_events:
            key = (int(event.get("risk_plan_step_id") or 0), str(event.get("event_type") or ""))
            reach_groups.setdefault(key, []).append(event)
        decorated_reaches = []
        for event in reach_events:
            key = (int(event.get("risk_plan_step_id") or 0), str(event.get("event_type") or ""))
            dates = sorted(str(row.get("chart_date") or "") for row in reach_groups[key] if row.get("chart_date"))
            decorated_reaches.append({
                **self._public_risk_event(event),
                "first_reached_chart_date": dates[0] if dates else None,
                "latest_reached_chart_date": dates[-1] if dates else None,
                "reach_count": len(reach_groups[key]),
                "trigger_price": (event.get("planned_value") or {}).get("trigger_price"),
            })
        review_session = self.repo.get_session(int(scenario["simulation_session_id"])) or {}
        date_index = {str(row.get("trade_date")): idx for idx, row in enumerate(self._session_prices(review_session))}
        reach_by_id = {int(event["id"]): event for event in reach_events}
        decorated_responses = []
        for event in response_events:
            reach_id = int((event.get("actual_value") or {}).get("reach_event_id") or 0)
            reach = reach_by_id.get(reach_id)
            start_index = date_index.get(str((reach or {}).get("chart_date")))
            end_index = date_index.get(str(event.get("chart_date")))
            response_candles = max(0, end_index - start_index) if start_index is not None and end_index is not None else None
            decorated_responses.append({
                **self._public_risk_event(event),
                "reach_event_id": reach_id,
                "response_type": (event.get("actual_value") or {}).get("response_type"),
                "response_candles": response_candles,
            })
        category_scores = [
            self._score_category("pre_plan", "사전 계획", [1.0]),
            self._score_category(
                "split_entry",
                "분할 진입",
                [1.0 if str(step.get("status") or "").upper() == "EXECUTED" else 0.0 for step in steps if str(step.get("plan_group") or "").upper() == "BUY"]
                if len([step for step in steps if str(step.get("plan_group") or "").upper() == "BUY"]) > 1 else [],
            ),
            self._score_category(
                "profit_exit",
                "익절·분할 청산",
                [1.0 if str(step.get("status") or "").upper() == "EXECUTED" else 0.0 for step in steps if str(step.get("plan_type") or "").upper() == "TAKE_PROFIT"],
            ),
            self._score_category(
                "stop_exit",
                "손절·정리",
                [1.0 if str(step.get("status") or "").upper() == "EXECUTED" else 0.0 for step in steps if str(step.get("plan_type") or "").upper() in {"PARTIAL_STOP", "FULL_STOP"}],
            ),
            self._score_category(
                "change_warning",
                "계획 변경·경고 대응",
                self._warning_behavior_scores(warnings)
                + [1.0 for _ in response_events]
                + [0.5 if str(revision.get("change_reason") or "").strip() else 0.0 for revision in revisions if str(revision.get("revision_type") or "") == "PRICE_LINES_UPDATED"]
                + [0.5 if str((event.get("actual_value") or {}).get("unplanned_reason") or "").strip() else 0.0 for event in unplanned],
            ),
        ]
        eligible = [row for row in category_scores if row["applicable"]]
        overall = round(sum(float(row["score"]) for row in eligible) / len(eligible), 2) if eligible else None
        decision_timeline = []
        reconstructed_trade_ids: set[int] = set()
        for trade in scenario_trades:
            step_id = int(trade.get("risk_plan_step_id") or 0)
            step = steps_by_id.get(step_id)
            if not step:
                continue
            trade_id = int(trade["id"])
            reconstructed_trade_ids.add(trade_id)
            side = str(trade.get("side") or "").upper()
            step_no = int(step.get("step_no") or 0)
            plan_type = str(step.get("plan_type") or "").upper()
            action = "매수" if side == "BUY" else ("익절" if plan_type == "TAKE_PROFIT" else "손절")
            decision_timeline.append(
                {
                    "id": f"trade-decision-{trade_id}",
                    "kind": "trade_decision",
                    "event_type": "PLANNED_BUY_EXECUTED" if side == "BUY" else "PLANNED_SELL_EXECUTED",
                    "chart_date": trade.get("trade_date"),
                    "created_at": trade.get("created_at"),
                    "message": f"{step_no}차 {action} 계획대로 실행 · {float(trade.get('price') or 0):,.0f}원 · {int(trade.get('quantity') or 0):,}주",
                    "severity": "INFO",
                    "simulation_trade_id": trade_id,
                    "risk_plan_step_id": step_id,
                    "risk_scenario_id": scenario_id,
                    "acknowledged": True,
                }
            )

        legacy_plan_groups: dict[int, list[dict[str, Any]]] = {}
        for event in events:
            if str(event.get("event_type") or "") not in {"BUY_PLAN_MATCHED", "SELL_PLAN_MATCHED", "PLAN_STEP_EXECUTED"}:
                continue
            if int(event.get("risk_scenario_id") or 0) != scenario_id:
                continue
            trade_id = int(event.get("simulation_trade_id") or 0)
            if trade_id and trade_id not in reconstructed_trade_ids:
                legacy_plan_groups.setdefault(trade_id, []).append(event)
        for trade_id, grouped_events in legacy_plan_groups.items():
            representative = grouped_events[0]
            event_types = {str(event.get("event_type") or "") for event in grouped_events}
            side = "BUY" if "BUY_PLAN_MATCHED" in event_types else "SELL"
            actual = representative.get("actual_value") or {}
            decision_timeline.append(
                {
                    "id": f"legacy-trade-decision-{trade_id}",
                    "kind": "trade_decision",
                    "event_type": "PLANNED_BUY_EXECUTED" if side == "BUY" else "PLANNED_SELL_EXECUTED",
                    "chart_date": representative.get("chart_date"),
                    "created_at": representative.get("created_at"),
                    "message": f"계획대로 {'매수' if side == 'BUY' else '매도'} 실행 · {float(actual.get('order_price') or 0):,.0f}원 · {int(actual.get('order_quantity') or 0):,}주",
                    "severity": "INFO",
                    "simulation_trade_id": trade_id,
                    "risk_plan_step_id": representative.get("risk_plan_step_id"),
                    "risk_scenario_id": scenario_id,
                    "acknowledged": True,
                }
            )

        technical_event_types = {"BUY_PLAN_MATCHED", "SELL_PLAN_MATCHED", "PLAN_STEP_EXECUTED", "MULTIPLE_PLAN_LEVELS_REACHED"}
        timeline = decision_timeline + [
            {
                "id": f"event-{event['id']}",
                "kind": "event",
                "event_type": event.get("event_type"),
                "chart_date": event.get("chart_date"),
                "created_at": event.get("created_at"),
                "message": " · ".join(
                    part for part in [
                        str(event.get("message") or "").strip(),
                        (
                            "사유: " + str((event.get("actual_value") or {}).get("reason") or (event.get("actual_value") or {}).get("unplanned_reason") or "").strip()
                            if str((event.get("actual_value") or {}).get("reason") or (event.get("actual_value") or {}).get("unplanned_reason") or "").strip()
                            else ""
                        ),
                    ] if part
                ),
                "severity": event.get("severity"),
                "simulation_trade_id": event.get("simulation_trade_id"),
                "risk_plan_step_id": event.get("risk_plan_step_id"),
                "risk_scenario_id": event.get("risk_scenario_id"),
                "acknowledged": bool(event.get("acknowledged")),
            }
            for event in events
            if int(event.get("risk_scenario_id") or 0) == scenario_id
            if str(event.get("event_type") or "") not in technical_event_types
        ] + [
            {
                "id": f"revision-{revision['id']}",
                "kind": "revision",
                "event_type": revision.get("revision_type"),
                "chart_date": None,
                "created_at": revision.get("created_at"),
                "message": revision.get("change_reason") or "계획 변경 사유 미입력",
                "severity": "INFO",
            }
            for revision in revisions
            if str(revision.get("revision_type") or "") in {"PRICE_LINES_UPDATED", "UPDATE"}
        ]
        timeline.sort(key=lambda row: (str(row.get("created_at") or ""), str(row.get("id") or "")))
        return {
            "scenario_id": scenario_id,
            "has_scenario_data": True,
            "overall_execution_rate": overall,
            "category_scores": category_scores,
            "timeline": timeline,
            "reach_events": decorated_reaches,
            "response_events": decorated_responses,
            "warning_events": [self._public_risk_event(event) for event in warnings],
            "revision_events": [
                {
                    "id": revision.get("id"),
                    "revision_type": revision.get("revision_type"),
                    "change_reason": revision.get("change_reason"),
                    "created_at": revision.get("created_at"),
                }
                for revision in revisions
            ],
            "rule_based_summary": "계획 단계 실행, 계획 밖 주문의 사유, 경고 확인 및 도달 대응만으로 산출한 규칙 기반 결과입니다.",
        }

    @staticmethod
    def _distribution(delays: list[int], pending_count: int) -> dict[str, Any]:
        counts = {
            "same_day": sum(1 for value in delays if value == 0),
            "one_to_two": sum(1 for value in delays if 1 <= value <= 2),
            "three_plus": sum(1 for value in delays if value >= 3),
            "held_or_unanswered": pending_count,
        }
        total = sum(counts.values())
        return {
            "total": total,
            "counts": counts,
            "percentages": {key: round(value / total * 100, 2) if total else 0 for key, value in counts.items()},
        }

    def get_training_account_scenario_habits(
        self,
        account_id: int,
        range_filter: str = "20",
        stock_id: int | None = None,
        result_filter: str = "all",
        scenario_filter: str = "all",
    ) -> dict[str, Any]:
        account = self.get_training_account(account_id)
        closed = self.list_training_account_closed_trades(account_id)["items"]
        account_order_trades = self.repo.list_account_trade_events(account_id)
        if stock_id:
            closed = [trade for trade in closed if int(trade.get("stock_id") or 0) == stock_id]
        if result_filter != "all":
            closed = [trade for trade in closed if str(trade.get("result_type") or "").lower() == result_filter]
        if range_filter in {"20", "50"}:
            closed = closed[-int(range_filter):]

        reviews: list[tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]] = []
        for trade in closed:
            scenarios = self.repo.list_risk_scenarios_by_session(int(trade["training_session_id"]))
            scenario = next(
                (
                    row for row in scenarios
                    if str(row.get("closed_trade_id") or "") == str(trade.get("closed_trade_id") or "")
                ),
                None,
            )
            if scenario_filter == "planned" and not scenario:
                continue
            if scenario_filter == "unplanned" and scenario:
                continue
            review = self.get_risk_scenario_execution_review(int(scenario["id"])) if scenario else None
            reviews.append((trade, scenario, review))

        scored = [review for _, _, review in reviews if review and review.get("overall_execution_rate") is not None]
        all_events: list[dict[str, Any]] = []
        all_target_episodes: list[dict[str, Any]] = []
        all_stop_episodes: list[dict[str, Any]] = []
        scenario_distributions: dict[int, tuple[dict[str, Any], dict[str, Any]]] = {}
        for trade, scenario, review in reviews:
            if not scenario or not review:
                continue
            all_events.extend(review["timeline"])
            prices = self._session_prices(self.repo.get_session(int(trade["training_session_id"])) or {})
            date_index = {str(row.get("trade_date")): idx for idx, row in enumerate(prices)}
            episodes = self._build_reach_episodes(
                review["reach_events"],
                review["response_events"],
                date_index,
                prices,
            )
            target_episodes = [row for row in episodes if row.get("reach_type") == "TAKE_PROFIT_REACHED"]
            stop_episodes = [row for row in episodes if row.get("reach_type") != "TAKE_PROFIT_REACHED"]
            all_target_episodes.extend(target_episodes)
            all_stop_episodes.extend(stop_episodes)
            scenario_distributions[int(scenario["id"])] = (
                self._episode_distribution(target_episodes),
                self._episode_distribution(stop_episodes),
            )

        category_scores = []
        for key, label in [
            ("pre_plan", "사전 계획"),
            ("split_entry", "분할 진입"),
            ("profit_exit", "익절·분할 청산"),
            ("stop_exit", "손절·정리"),
            ("change_warning", "계획 변경·경고 대응"),
        ]:
            all_rows = [row for review in scored for row in review["category_scores"] if row["key"] == key]
            rows = [row for row in all_rows if row["applicable"]]
            earned_score = sum(
                float(row.get("earned_score") if row.get("earned_score") is not None else float(row.get("score") or 0) / 100 * int(row.get("eligible_count") or 0))
                for row in rows
            )
            max_score = sum(
                float(row.get("max_score") if row.get("max_score") is not None else int(row.get("eligible_count") or 0))
                for row in rows
            )
            applicable_item_count = sum(int(row.get("applicable_item_count") or row.get("eligible_count") or 0) for row in rows)
            category_scores.append(
                {
                    "key": key,
                    "label": label,
                    "applicable": bool(rows),
                    "score": round(earned_score / max_score * 100, 2) if max_score else None,
                    "rate": round(earned_score / max_score * 100, 2) if max_score else None,
                    "eligible_count": len(rows),
                    "applicable_trade_count": len(rows),
                    "applicable_item_count": applicable_item_count,
                    "earned_score": round(earned_score, 4),
                    "max_score": round(max_score, 4),
                    "full_count": sum(int(row.get("full_count") or 0) for row in rows),
                    "partial_count": sum(int(row.get("partial_count") or 0) for row in rows),
                    "miss_count": sum(int(row.get("miss_count") or 0) for row in rows),
                    "excluded_count": sum(int(row.get("excluded_count") or 0) for row in all_rows),
                }
            )

        planned_count = sum(1 for _, scenario, _ in reviews if scenario)
        evaluated_trades: dict[int, dict[str, Any]] = {}
        selected_session_ids = {int(trade["training_session_id"]) for trade, scenario, _ in reviews if scenario}
        for order_trade in account_order_trades:
            if int(order_trade.get("session_id") or 0) in selected_session_ids and order_trade.get("risk_scenario_id"):
                evaluated_trades[int(order_trade["id"])] = order_trade

        def order_key(event: dict[str, Any]) -> str:
            trade_id = event.get("simulation_trade_id")
            return f"trade:{trade_id}" if trade_id is not None else str(event.get("id") or "")

        unplanned_events_by_order: dict[str, dict[str, Any]] = {}
        selected_session_events = [
            event
            for selected_session_id in selected_session_ids
            for event in self.repo.list_risk_events(selected_session_id)
        ]
        for event in selected_session_events:
            if str(event.get("event_type") or "").startswith("UNPLANNED_"):
                unplanned_events_by_order.setdefault(order_key(event), event)
        unplanned_events = list(unplanned_events_by_order.values())
        unplanned_trade_ids = {
            trade_id for trade_id, order_trade in evaluated_trades.items()
            if not order_trade.get("risk_plan_step_id")
        } | {
            int(event.get("simulation_trade_id") or 0)
            for event in unplanned_events
            if int(event.get("simulation_trade_id") or 0) in evaluated_trades
        }
        unplanned_count_by_session: dict[int, int] = {}
        for trade_id in unplanned_trade_ids:
            session_id_for_trade = int(evaluated_trades[trade_id].get("session_id") or 0)
            unplanned_count_by_session[session_id_for_trade] = unplanned_count_by_session.get(session_id_for_trade, 0) + 1
        reasoned_unplanned = sum(
            1 for event in unplanned_events
            if int(event.get("simulation_trade_id") or 0) in unplanned_trade_ids
            if str((event.get("actual_value") or {}).get("unplanned_reason") or "").strip()
        )

        revision_events_by_id = {
            str(event.get("id")): event
            for event in all_events
            if event.get("kind") == "revision" and event.get("event_type") == "PRICE_LINES_UPDATED"
        }
        revisions = list(revision_events_by_id.values())
        reasoned_revisions = sum(1 for event in revisions if event.get("message") != "계획 변경 사유 미입력")

        wins = [trade for trade, _, _ in reviews if trade.get("result_type") == "WIN"]
        losses = [trade for trade, _, _ in reviews if trade.get("result_type") == "LOSS"]
        flats = [trade for trade, _, _ in reviews if trade.get("result_type") == "FLAT"]
        avg_profit = sum(float(row.get("net_pnl") or 0) for row in wins) / len(wins) if wins else None
        avg_loss = abs(sum(float(row.get("net_pnl") or 0) for row in losses) / len(losses)) if losses else None
        avg_win_hold = sum(int(row.get("holding_bars") or 0) for row in wins) / len(wins) if wins else None
        avg_loss_hold = sum(int(row.get("holding_bars") or 0) for row in losses) / len(losses) if losses else None
        completed_result_count = len(wins) + len(losses) + len(flats)
        winning_ratio = round(len(wins) / completed_result_count * 100, 4) if completed_result_count else None
        profit_loss_ratio = round(avg_profit / avg_loss, 4) if avg_profit is not None and avg_loss else None

        summary = self.get_training_account_summary(account_id)
        active_risk = []
        for session in self.repo.list_account_sessions(account_id, status_filter=RUNNING_STATUS):
            scenario = self.repo.get_active_risk_scenario(int(session["id"]))
            if scenario:
                detail = self._risk_scenario_detail(scenario)
                holding = detail.get("holding_risk") or {}
                active_risk.append(
                    {
                        "session_id": int(session["id"]),
                        "stock_name": session.get("stock_name") or session.get("stock_code"),
                        "risk_amount": holding.get("current_estimated_risk"),
                        "risk_usage_pct": holding.get("risk_usage_pct"),
                    }
                )
        account_risk_budget = (
            float(summary.get("training_equity") or account.get("realized_equity") or account.get("initial_capital") or 0)
            * float(account.get("max_open_risk_pct") or 0)
            / 100
        )
        for row in active_risk:
            row["risk_usage_pct"] = self._safe_rate(float(row.get("risk_amount") or 0), account_risk_budget)
        current_open_risk_pct = (
            self._safe_rate(sum(float(row.get("risk_amount") or 0) for row in active_risk), account_risk_budget)
            if account_risk_budget > 0 else None
        )
        average = round(sum(float(review["overall_execution_rate"]) for review in scored) / len(scored), 2) if scored else None
        evaluated_order_count = len(evaluated_trades)
        unplanned_order_count = len(unplanned_trade_ids)

        trades = []
        for trade, scenario, review in reviews:
            scenario_id = int(scenario["id"]) if scenario else None
            target_distribution, stop_distribution = scenario_distributions.get(
                scenario_id or 0,
                (self._episode_distribution([]), self._episode_distribution([])),
            )
            trades.append(
                {
                    **trade,
                    "has_scenario_data": bool(scenario),
                    "scenario_id": scenario_id,
                    "scenario_execution_rate": review.get("overall_execution_rate") if review else None,
                    "category_scores": review.get("category_scores") if review else [],
                    "max_risk_pct": scenario.get("account_risk_pct") if scenario else None,
                    "unplanned_action_count": unplanned_count_by_session.get(int(trade["training_session_id"]), 0),
                    "target_response": target_distribution,
                    "stop_response": stop_distribution,
                }
            )

        return {
            "account_id": account_id,
            "filters": {"range": range_filter, "stock_id": stock_id, "result": result_filter, "scenario": scenario_filter},
            "coverage": {
                "trade_count": len(reviews),
                "closed_trade_count": len(reviews),
                "scenario_trade_count": planned_count,
                "legacy_trade_count": len(reviews) - planned_count,
                "scored_trade_count": len(scored),
                "evaluable_trade_count": len(scored),
            },
            "summary": {
                "average_execution_rate": average,
                "scenario_created_count": planned_count,
                "scenario_creation_denominator": len(reviews),
                "scenario_creation_rate": round(planned_count / len(reviews) * 100, 2) if reviews else None,
                "plan_creation_rate": round(planned_count / len(reviews) * 100, 2) if reviews else None,
                "unplanned_order_count": unplanned_order_count,
                "evaluated_order_count": evaluated_order_count,
                "unplanned_order_rate": (
                    round(unplanned_order_count / evaluated_order_count * 100, 2) if evaluated_order_count else None
                ),
            },
            "execution_trend": [
                {
                    "trade_sequence": trade.get("trade_sequence"),
                    "stock_name": trade.get("stock_name") or trade.get("stock_code"),
                    "result_type": trade.get("result_type"),
                    "score": review.get("overall_execution_rate") if review else None,
                    "scenario_id": int(scenario["id"]) if scenario else None,
                }
                for trade, scenario, review in reviews
            ],
            "category_scores": category_scores,
            "target_response_distribution": self._episode_distribution(all_target_episodes),
            "stop_response_distribution": self._episode_distribution(all_stop_episodes),
            "plan_change_distribution": {
                "total": len(revisions),
                "reason_recorded": reasoned_revisions,
                "reason_recording_rate": round(reasoned_revisions / len(revisions) * 100, 2) if revisions else None,
            },
            "unplanned_action_distribution": {
                "total": unplanned_order_count,
                "reason_recorded": reasoned_unplanned,
                "reason_recording_rate": round(reasoned_unplanned / unplanned_order_count * 100, 2) if unplanned_order_count else None,
            },
            "asymmetry": {
                "average_profit": avg_profit,
                "average_loss": avg_loss,
                "average_win_pnl": avg_profit,
                "average_loss_pnl_abs": avg_loss,
                "average_win_holding_bars": avg_win_hold,
                "average_loss_holding_bars": avg_loss_hold,
                "win_count": len(wins),
                "loss_count": len(losses),
                "flat_count": len(flats),
                "winning_ratio": winning_ratio,
                "profit_loss_ratio": profit_loss_ratio,
            },
            "account_risk": {
                "max_open_risk_pct": account.get("max_open_risk_pct"),
                "current_open_risk_pct": current_open_risk_pct,
                "thresholds": [60, 80, 100],
                "positions": active_risk,
            },
            "volatility_positioning": None,
            "trades": trades,
        }
    def activate_risk_scenario_for_first_buy(self, session: dict[str, Any], trade_values: dict[str, Any]) -> tuple[dict[str, Any] | None, int | None, int | None]:
        if not session.get("training_account_id"):
            return None, None, None
        if int(session.get("position_qty") or 0) > 0:
            active = self.repo.get_active_risk_scenario(int(session["id"]))
            if active:
                revision = self.repo.get_latest_risk_scenario_revision(int(active["id"]))
                return active, int(revision["id"]) if revision else None, trade_values.get("risk_plan_step_id")
            draft = self.repo.get_draft_risk_scenario(int(session["id"]))
            if not draft:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "RISK_SCENARIO_RECOVERY_REQUIRED",
                        "message": "보유수량은 있지만 활성 리스크 관리 계획이 없습니다. 계획을 작성해 상태를 복구해 주세요.",
                        "session_id": int(session["id"]),
                    },
                )
            steps = self.repo.list_risk_plan_steps(int(draft["id"]))
            buy_steps = [step for step in steps if str(step.get("plan_group") or "").upper() == "BUY"]
            sell_steps = [step for step in steps if str(step.get("plan_group") or "").upper() == "SELL"]
            preview = self.calculate_risk_scenario_preview(int(session["id"]), scenario=draft, buy_steps=buy_steps)
            activated = self.repo.activate_risk_scenario(int(draft["id"]), preview)
            revision = self.repo.create_risk_scenario_revision(
                int(activated["id"]), "RECOVERY_ACTIVATE", self._risk_snapshot(activated, buy_steps, sell_steps, preview), "recovered missing active scenario"
            )
            return activated, int(revision["id"]), trade_values.get("risk_plan_step_id") or (int(buy_steps[0]["id"]) if buy_steps else None)
        draft = self.repo.get_draft_risk_scenario(int(session["id"]))
        if not draft:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "RISK_SCENARIO_REQUIRED", "message": "최초 매수 전 리스크 시나리오를 등록해 주세요.", "session_id": int(session["id"])})
        if self.repo.get_active_risk_scenario(int(session["id"])):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "RISK_SCENARIO_ALREADY_ACTIVE", "message": "이미 활성 리스크 시나리오가 있습니다.", "session_id": int(session["id"])})
        steps = self.repo.list_risk_plan_steps(int(draft["id"]))
        buy_steps = [step for step in steps if str(step.get("plan_group") or "").upper() == "BUY"]
        preview = self.calculate_risk_scenario_preview(int(session["id"]), scenario=draft, buy_steps=buy_steps)
        activated = self.repo.activate_risk_scenario(int(draft["id"]), preview)
        revision = self.repo.create_risk_scenario_revision(int(activated["id"]), "ACTIVATE", self._risk_snapshot(activated, buy_steps, [step for step in steps if str(step.get("plan_group") or "").upper() == "SELL"], preview), "first buy activated scenario")
        step_id = trade_values.get("risk_plan_step_id") or (int(buy_steps[0]["id"]) if buy_steps else None)
        return activated, int(revision["id"]), step_id

    def _require_risk_warning_acknowledgement(self, preview: dict[str, Any], payload: TrainingOrderRequest) -> None:
        if str(preview.get("severity") or "") != "WARNING" or payload.risk_warning_acknowledged:
            return
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "RISK_WARNING_ACK_REQUIRED",
                "message": "리스크 경고를 확인한 후 주문을 계속해 주세요.",
                "preview": preview,
            },
        )

    def _record_order_risk_events(
        self,
        session: dict[str, Any],
        payload: TrainingOrderRequest,
        trade: dict[str, Any],
        preview: dict[str, Any],
        scenario_id: int,
        revision_id: int | None,
    ) -> None:
        selected_step = preview.get("selected_step")
        step_id = int(selected_step["id"]) if selected_step else None
        if step_id:
            self.repo.execute_risk_plan_step(step_id, int(trade["id"]), float(payload.price), int(payload.quantity))
        side = str(trade.get("side") or "").upper()
        event_rows: list[dict[str, str]] = []
        if selected_step:
            logger.info(
                "trade training plan step executed",
                extra={"simulation_trade_id": int(trade["id"]), "risk_plan_step_id": step_id, "side": side},
            )
        else:
            event_rows.append({"code": "UNPLANNED_BUY" if side == "BUY" else "UNPLANNED_SELL", "severity": "CAUTION", "message": f"계획 외 {('매수' if side == 'BUY' else '매도')}로 기록되었습니다."})
        existing_codes = {row["code"] for row in event_rows}
        for warning in preview.get("warnings") or []:
            if warning.get("code") not in existing_codes:
                event_rows.append(warning)
                existing_codes.add(str(warning.get("code")))
        planned_value = {
            "planned_step_price": selected_step.get("trigger_price") if selected_step else None,
            "risk_budget_amount": preview.get("risk_budget_amount"),
            "stop_price": preview.get("stop_price"),
        }
        actual_value = {
            "order_price": float(payload.price),
            "order_quantity": int(payload.quantity),
            "estimated_risk_amount": preview.get("projected_estimated_risk"),
            "risk_usage_pct": preview.get("risk_usage_pct"),
            "price_deviation_pct": preview.get("price_deviation_pct"),
            "unplanned_reason": payload.unplanned_reason,
        }
        for row in event_rows:
            severity = str(row.get("severity") or "INFO")
            self.repo.insert_risk_event_no_commit(
                {
                    "training_account_id": int(session["training_account_id"]),
                    "simulation_session_id": int(session["id"]),
                    "risk_scenario_id": scenario_id,
                    "risk_scenario_revision_id": revision_id,
                    "risk_plan_step_id": step_id,
                    "simulation_trade_id": int(trade["id"]),
                    "event_key": f"simulation_trade:{trade['id']}:risk:{row['code']}",
                    "event_type": row["code"],
                    "severity": severity,
                    "planned_value": planned_value,
                    "actual_value": actual_value,
                    "message": row.get("message") or "",
                    "acknowledged": bool(payload.risk_warning_acknowledged and severity == "WARNING"),
                    "acknowledgement_note": payload.risk_warning_acknowledgement_note,
                    "chart_date": trade.get("trade_date"),
                }
            )
    def buy(self, session_id: int, payload: TrainingOrderRequest) -> dict[str, Any]:
        session = self._running_session(session_id)
        candle = self._current_price_row(session)
        self._validate_price_in_candle(payload.price, candle)
        if self.repo.get_trade_by_client_order_id(session_id, payload.client_order_id):
            return self.get_session_detail(session_id)
        options = self._parse_options(session)
        fee_rate = float(options.get("fee_rate") or 0)
        amount = float(payload.price) * int(payload.quantity)
        fee = amount * fee_rate
        linked_account = self._linked_account(session)
        cash = float(linked_account.get("cash_balance") if linked_account else session.get("cash") or 0)
        if amount + fee > cash:
            if linked_account:
                raise self._insufficient_cash(cash, amount + fee, float(payload.price), fee_rate)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="현금이 부족합니다.")
        risk_order_preview = self.calculate_risk_order_preview(
            session_id,
            RiskOrderPreviewRequest(side="BUY", price=payload.price, quantity=payload.quantity, risk_plan_step_id=payload.risk_plan_step_id),
        ) if linked_account else None
        if risk_order_preview:
            self._require_risk_warning_acknowledgement(risk_order_preview, payload)
        if linked_account:
            self.repo.db.info["trade_training_atomic_order"] = True
        try:
            risk_scenario, risk_revision_id, risk_step_id = self.activate_risk_scenario_for_first_buy(session, {"risk_plan_step_id": payload.risk_plan_step_id})
            prev_qty = int(session.get("position_qty") or 0)
            prev_avg = float(session.get("avg_price") or 0)
            next_qty = prev_qty + int(payload.quantity)
            next_avg = ((prev_qty * prev_avg) + (int(payload.quantity) * float(payload.price))) / next_qty
            trade = self.repo.insert_trade(
                {
                    "session_id": session_id, "trade_date": str(candle["trade_date"]), "side": "BUY",
                    "price": float(payload.price), "quantity": int(payload.quantity), "fee": round(fee, 4),
                    "amount": round(amount, 4), "realized_profit": 0, "reason": payload.reason,
                    "method_review": payload.method_review, "client_order_id": payload.client_order_id,
                    "risk_scenario_id": int(risk_scenario["id"]) if risk_scenario else None,
                    "risk_scenario_revision_id": risk_revision_id, "risk_plan_step_id": risk_step_id,
                }
            )
            cash_after = round(cash - amount - fee, 4)
            self.repo.update_session(session_id, {"cash": cash_after, "position_qty": next_qty, "avg_price": round(next_avg, 4)})
            if linked_account:
                account_id = int(linked_account["id"])
                realized_equity_after = float(linked_account.get("realized_equity") or linked_account.get("initial_capital") or 0)
                self.repo.update_training_account_balances(account_id, cash_balance=cash_after)
                self.repo.insert_account_ledger(
                    {
                        "training_account_id": account_id, "simulation_session_id": session_id,
                        "simulation_trade_id": int(trade["id"]), "event_type": "BUY" if prev_qty == 0 else "ADDITIONAL_BUY",
                        "event_key": f"simulation_trade:{trade['id']}", "cash_delta": round(-(amount + fee), 4),
                        "cash_before": round(cash, 4), "cash_after": cash_after, "realized_pnl_delta": 0,
                        "realized_equity_after": realized_equity_after, "description": "account-linked buy order",
                        "metadata": {"amount": round(amount, 4), "fee": round(fee, 4), "quantity": int(payload.quantity), "price": float(payload.price)},
                    }
                )
                if risk_scenario and risk_order_preview:
                    effective_step_id = risk_step_id
                    if effective_step_id and not risk_order_preview.get("selected_step"):
                        risk_order_preview["selected_step"] = self.repo.get_risk_plan_step(int(effective_step_id))
                        risk_order_preview["warnings"] = [warning for warning in risk_order_preview.get("warnings") or [] if warning.get("code") != "UNPLANNED_BUY"]
                        risk_order_preview["severity"] = classify_risk_usage(to_decimal(risk_order_preview.get("risk_usage_pct")))
                        for warning in risk_order_preview["warnings"]:
                            if self._severity_rank(str(warning.get("severity") or "")) > self._severity_rank(str(risk_order_preview["severity"])):
                                risk_order_preview["severity"] = warning["severity"]
                    self._record_order_risk_events(session, payload, trade, risk_order_preview, int(risk_scenario["id"]), risk_revision_id)
                self.repo.db.commit()
        except Exception:
            if linked_account:
                self.repo.db.rollback()
            raise
        finally:
            if linked_account:
                self.repo.db.info.pop("trade_training_atomic_order", None)
        return self.get_session_detail(session_id)
    def sell(self, session_id: int, payload: TrainingOrderRequest) -> dict[str, Any]:
        session = self._running_session(session_id)
        candle = self._current_price_row(session)
        self._validate_price_in_candle(payload.price, candle)
        if self.repo.get_trade_by_client_order_id(session_id, payload.client_order_id):
            return self.get_session_detail(session_id)
        position_qty = int(session.get("position_qty") or 0)
        if payload.quantity > position_qty:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="보유수량이 부족합니다.")
        options = self._parse_options(session)
        fee_rate = float(options.get("fee_rate") or 0)
        amount = float(payload.price) * int(payload.quantity)
        fee = amount * fee_rate
        linked_account = self._linked_account(session)
        active_risk_scenario = self.repo.get_active_risk_scenario(session_id) if linked_account else None
        active_risk_revision = self.repo.get_latest_risk_scenario_revision(int(active_risk_scenario["id"])) if active_risk_scenario else None
        risk_order_preview = self.calculate_risk_order_preview(
            session_id,
            RiskOrderPreviewRequest(side="SELL", price=payload.price, quantity=payload.quantity, risk_plan_step_id=payload.risk_plan_step_id),
        ) if active_risk_scenario else None
        if risk_order_preview:
            self._require_risk_warning_acknowledgement(risk_order_preview, payload)
        if linked_account:
            self.repo.db.info["trade_training_atomic_order"] = True
        try:
            avg_price = float(session.get("avg_price") or 0)
            realized_profit = (float(payload.price) - avg_price) * int(payload.quantity) - fee
            next_qty = position_qty - int(payload.quantity)
            trade = self.repo.insert_trade(
                {
                    "session_id": session_id, "trade_date": str(candle["trade_date"]), "side": "SELL",
                    "price": float(payload.price), "quantity": int(payload.quantity), "fee": round(fee, 4),
                    "amount": round(amount, 4), "realized_profit": round(realized_profit, 4), "reason": payload.reason,
                    "method_review": payload.method_review, "client_order_id": payload.client_order_id,
                    "risk_scenario_id": int(active_risk_scenario["id"]) if active_risk_scenario else None,
                    "risk_scenario_revision_id": int(active_risk_revision["id"]) if active_risk_revision else None,
                    "risk_plan_step_id": payload.risk_plan_step_id,
                }
            )
            session_cash_before = float(session.get("cash") or 0)
            account_cash_before = float(linked_account.get("cash_balance") if linked_account else session_cash_before)
            cash_return = round(amount - fee, 4)
            cash_after = round(account_cash_before + cash_return, 4)
            self.repo.update_session(
                session_id,
                {
                    "cash": cash_after if linked_account else round(session_cash_before + cash_return, 4),
                    "position_qty": next_qty, "avg_price": 0 if next_qty == 0 else avg_price,
                    "realized_profit": round(float(session.get("realized_profit") or 0) + realized_profit, 4),
                },
            )
            if linked_account:
                account_id = int(linked_account["id"])
                realized_equity_after = self._realized_equity_for_account(account_id) if next_qty == 0 else float(linked_account.get("realized_equity") or linked_account.get("initial_capital") or 0)
                self.repo.update_training_account_balances(account_id, cash_balance=cash_after, realized_equity=realized_equity_after)
                if active_risk_scenario and risk_order_preview:
                    self._record_order_risk_events(
                        session, payload, trade, risk_order_preview, int(active_risk_scenario["id"]),
                        int(active_risk_revision["id"]) if active_risk_revision else None,
                    )
                if next_qty == 0 and active_risk_scenario:
                    closed_trades = self._closed_trades_for_session(account_id, {**session, "position_qty": next_qty})
                    last_closed = closed_trades[-1] if closed_trades else {}
                    self.repo.close_risk_scenario(
                        int(active_risk_scenario["id"]),
                        {
                            "closed_trade_id": last_closed.get("closed_trade_id") or f"{session_id}-{trade['id']}",
                            "final_trade_id": int(trade["id"]), "final_net_pnl": last_closed.get("net_pnl"),
                            "final_return_pct": last_closed.get("return_pct"),
                        },
                    )
                self.repo.insert_account_ledger(
                    {
                        "training_account_id": account_id, "simulation_session_id": session_id,
                        "simulation_trade_id": int(trade["id"]), "event_type": "FULL_SELL" if next_qty == 0 else "PARTIAL_SELL",
                        "event_key": f"simulation_trade:{trade['id']}", "cash_delta": cash_return,
                        "cash_before": round(account_cash_before, 4), "cash_after": cash_after,
                        "realized_pnl_delta": round(realized_profit, 4) if next_qty == 0 else 0,
                        "realized_equity_after": realized_equity_after, "description": "account-linked sell order",
                        "metadata": {"amount": round(amount, 4), "fee": round(fee, 4), "quantity": int(payload.quantity), "price": float(payload.price)},
                    }
                )
                self.repo.db.commit()
        except Exception:
            if linked_account:
                self.repo.db.rollback()
            raise
        finally:
            if linked_account:
                self.repo.db.info.pop("trade_training_atomic_order", None)
        return self.get_session_detail(session_id)
    def finish(self, session_id: int) -> dict[str, Any]:
        session = self.repo.get_session(session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="훈련 세션을 찾을 수 없습니다.")
        updated = self.repo.update_session(session_id, {"status": FINISHED_STATUS})
        candle = self._current_price_row(updated)
        self._save_snapshot(updated, candle)
        detail = self.get_session_detail(session_id)
        return {"session": detail["session"], "account": detail["account"], "message": "훈련을 종료했습니다."}

    def abort(self, session_id: int) -> dict[str, Any]:
        session = self.repo.get_session(session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="훈련 세션을 찾을 수 없습니다.")
        updated = self.repo.update_session(session_id, {"status": ABORTED_STATUS})
        account = self._calc_account(updated, self._current_price_row(updated))
        return {"session": self._response_session(updated), "account": account, "message": "훈련을 중단했습니다."}

    def _build_trade_pairs(self, trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
        buy_lots: list[dict[str, Any]] = []
        pairs: list[dict[str, Any]] = []
        for trade in trades:
            side = str(trade.get("side") or "").upper()
            qty = int(trade.get("quantity") or 0)
            if side == "BUY":
                buy_lots.append({**trade, "remaining_quantity": qty})
                continue
            if side != "SELL":
                continue
            remaining_sell_qty = qty
            while remaining_sell_qty > 0 and buy_lots:
                lot = buy_lots[0]
                matched_qty = min(int(lot["remaining_quantity"]), remaining_sell_qty)
                buy_price = float(lot.get("price") or 0)
                sell_price = float(trade.get("price") or 0)
                buy_amount = buy_price * matched_qty
                buy_fee_part = float(lot.get("fee") or 0) * (matched_qty / max(1, int(lot.get("quantity") or 0)))
                sell_fee_part = float(trade.get("fee") or 0) * (matched_qty / max(1, qty))
                profit_amount = (sell_price - buy_price) * matched_qty - buy_fee_part - sell_fee_part
                holding_days = (self._to_date(str(trade["trade_date"])) - self._to_date(str(lot["trade_date"]))).days
                pairs.append(
                    {
                        "buy_date": str(lot["trade_date"]),
                        "sell_date": str(trade["trade_date"]),
                        "buy_price": round(buy_price, 4),
                        "sell_price": round(sell_price, 4),
                        "quantity": matched_qty,
                        "holding_days": holding_days,
                        "profit_amount": round(profit_amount, 4),
                        "profit_rate": self._safe_rate(profit_amount, buy_amount + buy_fee_part),
                        "gross_buy_amount": round(buy_amount, 4),
                        "buy_reason": lot.get("reason"),
                        "sell_reason": trade.get("reason"),
                        "buy_reason_quality": self._reason_quality(lot.get("reason"))["grade"],
                        "sell_reason_quality": self._reason_quality(trade.get("reason"))["grade"],
                        "buy_reason_quality_guide": self._reason_quality(lot.get("reason"))["guide"],
                        "sell_reason_quality_guide": self._reason_quality(trade.get("reason"))["guide"],
                        "buy_method_review": lot.get("method_review"),
                        "sell_method_review": trade.get("method_review"),
                    }
                )
                lot["remaining_quantity"] = int(lot["remaining_quantity"]) - matched_qty
                remaining_sell_qty -= matched_qty
                if int(lot["remaining_quantity"]) <= 0:
                    buy_lots.pop(0)
        return pairs

    def get_training_result(self, session_id: int) -> dict[str, Any]:
        session = self.repo.get_session(session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="훈련 세션을 찾을 수 없습니다.")
        current_candle = self._current_price_row(session)
        account = self._calc_account(session, current_candle)
        trades = self.repo.list_trades(session_id)
        pairs = self._build_trade_pairs(trades)
        performance_by_period: dict[tuple[str, str], list[dict[str, Any]]] = {}
        account_id = int(session.get("training_account_id") or 0)
        if account_id:
            account_performance = self.get_training_account_performance(account_id)
            for item in account_performance.get("items") or []:
                if int(item.get("simulation_session_id") or item.get("training_session_id") or 0) != session_id:
                    continue
                key = (str(item.get("chart_entry_date") or ""), str(item.get("chart_exit_date") or ""))
                performance_by_period.setdefault(key, []).append(item)

        fallback_equity = float(session.get("initial_cash") or 0)
        for pair_index, pair in enumerate(pairs, start=1):
            period_key = (str(pair.get("buy_date") or ""), str(pair.get("sell_date") or ""))
            matched_items = performance_by_period.get(period_key) or []
            performance_item = matched_items.pop(0) if matched_items else None
            if performance_item:
                pair["trade_sequence"] = int(performance_item.get("trade_sequence") or pair_index)
                pair["gross_buy_amount"] = round(float(performance_item.get("gross_buy_amount") or pair.get("gross_buy_amount") or 0), 4)
                pair["equity_before"] = round(float(performance_item.get("equity_before") or 0), 4)
                pair["equity_after"] = round(float(performance_item.get("equity_after") or 0), 4)
                fallback_equity = float(pair["equity_after"])
            else:
                pair["trade_sequence"] = pair_index
                pair["equity_before"] = round(fallback_equity, 4)
                fallback_equity = round(fallback_equity + float(pair.get("profit_amount") or 0), 4)
                pair["equity_after"] = fallback_equity
        buy_trades = [trade for trade in trades if str(trade.get("side") or "").upper() == "BUY"]
        sell_trades = [trade for trade in trades if str(trade.get("side") or "").upper() == "SELL"]
        wins = [pair for pair in pairs if float(pair["profit_amount"]) > 0]
        losses = [pair for pair in pairs if float(pair["profit_amount"]) < 0]
        evens = [pair for pair in pairs if float(pair["profit_amount"]) == 0]
        closed_count = len(wins) + len(losses)
        total_fees = round(sum(float(trade.get("fee") or 0) for trade in trades), 4)
        buy_quality_counts = self._quality_counts(pairs, "buy_reason_quality")
        sell_quality_counts = self._quality_counts(pairs, "sell_reason_quality")
        method_review_stats = self._method_review_stats(pairs)

        snapshots = self.repo.list_snapshots(session_id, end_date=session.get("current_date"))
        curve_by_date: dict[str, dict[str, Any]] = {}
        for snap in snapshots:
            curve_by_date[str(snap["trade_date"])] = {
                "trade_date": str(snap["trade_date"]),
                "total_asset": round(float(snap.get("total_asset") or 0), 4),
                "cash": round(float(snap.get("cash") or 0), 4),
                "evaluation_amount": round(float(snap.get("evaluation_amount") or 0), 4),
            }
        equity_curve = list(curve_by_date.values())

        position_qty = int(session.get("position_qty") or 0)
        avg_price = float(session.get("avg_price") or 0)
        open_position = {
            "position_qty": position_qty,
            "avg_price": round(avg_price, 4),
            "evaluation_amount": account["evaluation_amount"],
            "unrealized_profit": account["unrealized_profit"],
            "unrealized_return_rate": account["unrealized_return_rate"],
        }

        return {
            "session_id": int(session["id"]),
            "stock_code": str(session["stock_code"]),
            "stock_name": session.get("stock_name"),
            "start_date": str(session["start_date"]),
            "end_date": str(session["end_date"]),
            "current_date": session.get("current_date"),
            "status": str(session.get("status") or ""),
            "initial_cash": round(float(session.get("initial_cash") or 0), 4),
            "final_cash": round(float(session.get("cash") or 0), 4),
            "final_evaluation_amount": account["evaluation_amount"],
            "final_total_asset": account["total_asset"],
            "total_profit": account["total_profit"],
            "total_return_rate": account["total_return_rate"],
            "trade_count": len(trades),
            "buy_count": len(buy_trades),
            "sell_count": len(sell_trades),
            "round_trip_count": len(pairs),
            "winning_trade_count": len(wins),
            "losing_trade_count": len(losses),
            "break_even_trade_count": len(evens),
            "win_rate": None if closed_count == 0 else round(len(wins) / closed_count * 100, 4),
            "average_profit_rate": None if not wins else round(sum(float(p["profit_rate"]) for p in wins) / len(wins), 4),
            "average_loss_rate": None if not losses else round(sum(float(p["profit_rate"]) for p in losses) / len(losses), 4),
            "max_profit_amount": None if not wins else round(max(float(p["profit_amount"]) for p in wins), 4),
            "max_loss_amount": None if not losses else round(min(float(p["profit_amount"]) for p in losses), 4),
            "average_holding_days": None if not pairs else round(sum(int(p["holding_days"]) for p in pairs) / len(pairs), 4),
            "total_fees": total_fees,
            "buy_reason_fill_rate": None if not buy_trades else round(sum(1 for t in buy_trades if str(t.get("reason") or "").strip()) / len(buy_trades) * 100, 4),
            "sell_reason_fill_rate": None if not sell_trades else round(sum(1 for t in sell_trades if str(t.get("reason") or "").strip()) / len(sell_trades) * 100, 4),
            "buy_reason_quality_summary": buy_quality_counts,
            "sell_reason_quality_summary": sell_quality_counts,
            "weak_buy_reason_count": buy_quality_counts["부족"] + buy_quality_counts["미작성"],
            "weak_sell_reason_count": sell_quality_counts["부족"] + sell_quality_counts["미작성"],
            "method_review_stats": method_review_stats,
            "trade_pairs": pairs,
            "open_position": open_position,
            "equity_curve": equity_curve,
        }

    @staticmethod
    def _text(value: Any, empty: str = "작성되지 않음") -> str:
        if value is None:
            return empty
        text = str(value).strip()
        return text if text else empty

    @staticmethod
    def _money(value: Any) -> str:
        if value is None:
            return "-"
        return f"{float(value):,.0f}원"

    @staticmethod
    def _pct(value: Any) -> str:
        if value is None:
            return "-"
        return f"{float(value):+.2f}%"

    def _review_response(self, session_id: int, row: dict[str, Any] | None = None) -> dict[str, Any]:
        data = row or {}
        return {
            "session_id": session_id,
            "review_status": data.get("review_status") or "미복기",
            "self_review_text": data.get("self_review_text") or "",
            "gpt_prompt_text": data.get("gpt_prompt_text") or "",
            "gpt_review_text": data.get("gpt_review_text") or "",
            "improvement_point": data.get("improvement_point") or "",
            "next_training_goal": data.get("next_training_goal") or "",
            "main_mistake": data.get("main_mistake") or "",
            "discipline_score": data.get("discipline_score"),
            "reviewed_at": data.get("reviewed_at"),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
        }

    def get_simulation_review(self, session_id: int) -> dict[str, Any]:
        if not self.repo.get_session(session_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="훈련 세션을 찾을 수 없습니다.")
        return self._review_response(session_id, self.repo.get_review(session_id))

    def save_simulation_review(self, session_id: int, payload: SimulationReviewSaveRequest) -> dict[str, Any]:
        if not self.repo.get_session(session_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="훈련 세션을 찾을 수 없습니다.")
        saved = self.repo.upsert_review(
            session_id,
            {
                "review_status": payload.review_status,
                "self_review_text": payload.self_review_text,
                "gpt_prompt_text": payload.gpt_prompt_text,
                "gpt_review_text": payload.gpt_review_text,
                "improvement_point": payload.improvement_point,
                "next_training_goal": payload.next_training_goal,
                "main_mistake": payload.main_mistake,
                "discipline_score": payload.discipline_score,
            },
        )
        return self._review_response(session_id, saved)

    def build_training_gpt_package(self, session_id: int) -> dict[str, Any]:
        result = self.get_training_result(session_id)
        review = self.get_simulation_review(session_id)
        equity_values = [float(point["total_asset"]) for point in result["equity_curve"]]
        equity_summary = {
            "start": equity_values[0] if equity_values else result["initial_cash"],
            "high": max(equity_values) if equity_values else result["final_total_asset"],
            "low": min(equity_values) if equity_values else result["final_total_asset"],
            "final": result["final_total_asset"],
        }
        trade_lines = []
        for idx, pair in enumerate(result["trade_pairs"], start=1):
            trade_lines.append(
                "\n".join(
                    [
                        f"거래 {idx}",
                        f"- 매수일: {pair['buy_date']}",
                        f"- 매도일: {pair['sell_date']}",
                        f"- 보유일: {pair['holding_days']}일",
                        f"- 매수가: {self._money(pair['buy_price'])}",
                        f"- 매도가: {self._money(pair['sell_price'])}",
                        f"- 수량: {pair['quantity']}주",
                        f"- 손익: {self._money(pair['profit_amount'])}",
                        f"- 수익률: {self._pct(pair['profit_rate'])}",
                        f"- 매수 사유: {self._text(pair.get('buy_reason'))}",
                        f"- 매수 사유 품질: {self._text(pair.get('buy_reason_quality'), '미작성')}",
                        f"- 매도 사유: {self._text(pair.get('sell_reason'))}",
                        f"- 매도 사유 품질: {self._text(pair.get('sell_reason_quality'), '미작성')}",
                        "- 손절 기준 작성 여부: 기록 없음",
                        "- 실패 기준 작성 여부: 기록 없음",
                        "- 추가매수/추격매수 구분 여부: 기록 없음",
                        self._format_buy_method_review(pair.get("buy_method_review")),
                        self._format_sell_method_review(pair.get("sell_method_review")),
                    ]
                )
            )
        if not trade_lines:
            trade_lines.append("청산된 거래쌍이 없습니다.")

        training_summary = "\n".join(
            [
                f"- 종목명: {self._text(result.get('stock_name'), '-')}",
                f"- 종목코드: {result['stock_code']}",
                f"- 훈련 기간: {result['start_date']} ~ {result.get('current_date') or result['end_date']}",
                f"- 상태: {result['status']}",
                f"- 초기자금: {self._money(result['initial_cash'])}",
                f"- 최종자산: {self._money(result['final_total_asset'])}",
                f"- 누적손익: {self._money(result['total_profit'])}",
                f"- 누적수익률: {self._pct(result['total_return_rate'])}",
            ]
        )
        performance_summary = "\n".join(
            [
                f"- 총 거래 수: {result['trade_count']}건",
                f"- 매수/매도 수: {result['buy_count']}건 / {result['sell_count']}건",
                f"- 청산 거래쌍: {result['round_trip_count']}건",
                f"- 승/패/보합: {result['winning_trade_count']} / {result['losing_trade_count']} / {result['break_even_trade_count']}",
                f"- 승률: {self._pct(result.get('win_rate'))}",
                f"- 평균 수익률: {self._pct(result.get('average_profit_rate'))}",
                f"- 평균 손실률: {self._pct(result.get('average_loss_rate'))}",
                f"- 최대 수익: {self._money(result.get('max_profit_amount'))}",
                f"- 최대 손실: {self._money(result.get('max_loss_amount'))}",
                f"- 평균 보유일: {self._text(result.get('average_holding_days'), '-')}일",
                f"- 총 수수료: {self._money(result['total_fees'])}",
                f"- 매수 사유 입력률: {self._pct(result.get('buy_reason_fill_rate'))}",
                f"- 매도 사유 입력률: {self._pct(result.get('sell_reason_fill_rate'))}",
                f"- 매수 사유 품질 요약: {self._quality_summary_text(result.get('buy_reason_quality_summary') or {})}",
                f"- 매도 사유 품질 요약: {self._quality_summary_text(result.get('sell_reason_quality_summary') or {})}",
                f"- 부족한 매수 사유 건수: {result.get('weak_buy_reason_count', 0)}건",
                f"- 부족한 매도 사유 건수: {result.get('weak_sell_reason_count', 0)}건",
            ]
        )
        open_position = result["open_position"]
        open_position_summary = "\n".join(
            [
                f"- 보유수량: {open_position['position_qty']}주",
                f"- 평균단가: {self._money(open_position['avg_price'])}",
                f"- 평가금액: {self._money(open_position['evaluation_amount'])}",
                f"- 평가손익: {self._money(open_position['unrealized_profit'])}",
                f"- 평가수익률: {self._pct(open_position['unrealized_return_rate'])}",
            ]
        )
        equity_summary_text = "\n".join(
            [
                f"- 시작 자산: {self._money(equity_summary['start'])}",
                f"- 최고 자산: {self._money(equity_summary['high'])}",
                f"- 최저 자산: {self._money(equity_summary['low'])}",
                f"- 최종 자산: {self._money(equity_summary['final'])}",
            ]
        )
        self_review_summary = "\n".join(
            [
                f"- 사용자의 자기평가: {self._text(review.get('self_review_text'))}",
                f"- 핵심 실수: {self._text(review.get('main_mistake'))}",
                f"- 개선할 점: {self._text(review.get('improvement_point'))}",
                f"- 다음 훈련 목표: {self._text(review.get('next_training_goal'))}",
                f"- 원칙 준수 점수: {self._text(review.get('discipline_score'), '미입력')}",
            ]
        )
        drct_analysis_lines = [
            "- 이 분석은 투자 조언이 아니라 훈련 복기 보조 문구입니다.",
            "- 수익률과 승률이 높아도 원칙 재현성은 별도로 평가해야 합니다.",
            f"- 매수 사유 품질 요약: {self._quality_summary_text(result.get('buy_reason_quality_summary') or {})}",
            f"- 매도 사유 품질 요약: {self._quality_summary_text(result.get('sell_reason_quality_summary') or {})}",
            f"- 부족하거나 미작성된 매수 사유: {result.get('weak_buy_reason_count', 0)}건",
            f"- 부족하거나 미작성된 매도 사유: {result.get('weak_sell_reason_count', 0)}건",
            "- 손절 기준과 실패 기준은 현재 거래별 구조화 데이터로 기록되지 않았습니다.",
            "- 추가 진입이 사전 계획된 추가매수인지, 상승 후 추격매수인지 구분되지 않았습니다.",
            f"- 1회 매수 비중은 거래별 매수금액을 초기자금 {self._money(result['initial_cash'])} 대비로 별도 점검할 필요가 있습니다.",
            f"- 최대 동시 노출 비중은 자산 흐름과 미청산 보유분 기준으로 별도 점검할 필요가 있습니다.",
            "- 다음 훈련에서는 매수 전 실패 기준, 손절 기준, 매도 기준, 추가매수 기준을 사전에 기록하는 것이 필요합니다.",
        ]
        if result.get("losing_trade_count") == 0:
            drct_analysis_lines.insert(1, "- 손실 거래가 없어 최대손실은 '-'로 정리되었습니다.")
        if result.get("weak_sell_reason_count", 0) > 0:
            drct_analysis_lines.append("- 매도 사유가 결과 중심 표현에 머물렀을 가능성이 있으므로 실제 매도 판단 근거를 확인해야 합니다.")
        method_stats = result.get("method_review_stats") or {}
        total_pairs = int(method_stats.get("total_pairs") or 0)
        if total_pairs > 0:
            drct_analysis_lines.extend(
                [
                    f"- 매매기법 기준 복기가 작성된 매수 거래는 {method_stats.get('buy_review_count', 0)}건 / {total_pairs}건입니다.",
                    f"- 실패 기준 작성률: {method_stats.get('failure_criteria_count', 0)}건 / {total_pairs}건",
                    f"- 손절 기준 작성률: {method_stats.get('stop_loss_rule_count', 0)}건 / {total_pairs}건",
                    f"- 목표/청산 기준 작성률: {method_stats.get('target_exit_rule_count', 0)}건 / {total_pairs}건",
                    f"- 추가매수 기준 작성률: {method_stats.get('add_buy_plan_count', 0)}건 / {total_pairs}건",
                    f"- 매매기법 기준 충족 기록: {method_stats.get('method_fit_count', 0)}건 / {total_pairs}건",
                    f"- 매도 계획 일치 기록: {method_stats.get('plan_aligned_count', 0)}건 / {total_pairs}건",
                    f"- 최초 계획 없음 매도: {method_stats.get('no_initial_plan_count', 0)}건",
                    f"- 추격매수 가능성 태그: {method_stats.get('chase_buy_count', 0)}건",
                    f"- 감정 매도 가능성 태그: {method_stats.get('emotion_sell_count', 0)}건",
                ]
            )
        drct_analysis = "\n".join(drct_analysis_lines)
        gpt_request = "\n".join(
            [
                "1. 이번 훈련의 핵심을 요약해 주세요.",
                "2. 수익률보다 원칙 재현성을 평가해 주세요.",
                "3. 매수 사유와 매도 사유의 구체성을 별도로 평가해 주세요.",
                "4. '익절', '손절'처럼 결과 중심 표현이 복기 품질에 어떤 한계가 있는지 평가해 주세요.",
                "5. 손절 기준, 실패 기준, 추가매수 기준이 기록되지 않은 경우의 위험을 평가해 주세요.",
                "6. 손실 거래에서 반복되는 문제를 찾아 주세요.",
                "7. 수익 거래에서 잘한 점을 찾아 주세요.",
                "8. 손절 지연, 조기 매도, 추격매수 가능성을 평가해 주세요.",
                "9. 비중 조절과 리스크 관리 수준을 평가해 주세요.",
                "10. 다음 훈련 목표를 구체적인 행동 문장으로 제안해 주세요.",
                "11. 매매기법의 체크리스트, 매도조건, 실패패턴에 반영할 수 있는 후보를 제안해 주세요.",
                "12. 이번 거래가 매매기법 기준에 맞게 실행되었는지 평가해 주세요.",
                "13. 수익/손실 결과와 별개로 매수 기준, 실패 기준, 손절 기준, 매도 기준의 완성도를 평가해 주세요.",
                "14. 최초 계획과 실제 매도 판단이 일치했는지 평가해 주세요.",
                "15. 계획이 부족한 문제와 실행이 흔들린 문제를 구분해 주세요.",
                "16. 선택한 복기 카드와 실제 입력 내용을 함께 보고, 사용자의 판단이 매매기법 기준에 맞았는지 평가해 주세요.",
                "17. 카드 선택은 사용자의 자기 판단 기록이므로, 결과가 좋았다고 해서 무조건 적절한 판단으로 보지 말고 원칙 준수 여부를 중심으로 평가해 주세요.",
                "18. 이 훈련을 통해 사용자가 배워야 할 핵심 교훈을 정리해 주세요.",
            ]
        )
        structured_json_request = """마지막에는 아래 JSON 형식으로 정리해 주세요.
이 JSON은 DrCT에서 다음 훈련 목표와 매매기법 수정 후보로 활용됩니다.
JSON은 설명 문장과 별도로 마지막에 제공해 주세요.

{
  "training_scores": {
    "principle_adherence": 0,
    "entry_quality": 0,
    "exit_quality": 0,
    "risk_management": 0,
    "position_sizing": 0,
    "record_quality": 0,
    "method_completeness": 0
  },
  "detected_mistakes": [
    {
      "mistake_type": "missing_stop_rule",
      "title": "손절 기준 미작성",
      "evidence": "구체적인 근거",
      "severity": "low|medium|high",
      "next_action": "다음 훈련에서 실행할 행동"
    }
  ],
  "success_lessons": [
    {
      "lesson": "성공 거래에서 재현 가능한 교훈",
      "repeat_condition": "반복 가능한 조건"
    }
  ],
  "failure_lessons": [
    {
      "lesson": "실패 또는 잠재 실패에서 얻을 교훈",
      "preventive_rule": "예방 규칙"
    }
  ],
  "next_training_rules": [
    "다음 훈련에서 반드시 지킬 행동 기준"
  ],
  "method_adjustment_suggestions": [
    {
      "target_section": "entry_rules|exit_rules|failure_patterns|checklist",
      "suggestion": "매매기법에 반영할 수정 후보",
      "reason": "제안 이유"
    }
  ]
}"""
        prompt = f"""[DrCT 매매훈련 복기 요청]

당신은 투자 종목 추천자가 아니라, 개인 투자자의 매매 판단 습관을 교정하는 훈련 코치입니다.
아래 매매훈련 결과를 바탕으로 수익률보다 매수·매도 판단 과정, 손실 관리, 감정 개입, 반복 실수를 중심으로 분석해 주세요.
새로운 종목 추천이나 매수·매도 추천은 하지 마세요.

[분석 요청]
{gpt_request}

[주의]
- 이 분석은 투자 조언이 아니라 매매훈련 복기와 습관 교정을 위한 참고 자료입니다.
- 새로운 매수/매도 종목 추천은 하지 마세요.
- 수익이 났다고 좋은 훈련으로 단정하지 마세요.
- 손실이 났다고 나쁜 훈련으로 단정하지 마세요.
- 매매 결과보다 판단 과정과 실행 가능한 원칙을 중심으로 평가해 주세요.

[1. 훈련 기본정보]
{training_summary}

[2. 훈련 성과 요약]
{performance_summary}

[3. 거래별 매수·매도 판단]
{chr(10).join(trade_lines)}

[4. 미청산 보유분]
{open_position_summary}

[5. 자산 흐름 요약]
{equity_summary_text}

[6. 사용자 훈련 회고]
{self_review_summary}

[7. DrCT 자동 분석]
{drct_analysis}

[8. 최종 요청]
이 훈련 결과를 바탕으로 제가 반복하는 판단 실수와 다음 훈련에서 반드시 고쳐야 할 행동을 구체적으로 분석해 주세요.

[9. 구조화 JSON 출력 요청]
{structured_json_request}
"""
        sections = {
            "training_summary": training_summary,
            "performance_summary": performance_summary,
            "trade_pairs_summary": "\n\n".join(trade_lines),
            "reason_summary": self_review_summary,
            "drct_analysis": drct_analysis,
            "gpt_request": gpt_request,
            "structured_json_request": structured_json_request,
        }
        stock_name = self._text(result.get("stock_name"), result["stock_code"])
        return {
            "session_id": session_id,
            "stock_code": result["stock_code"],
            "stock_name": result.get("stock_name"),
            "package_title": f"{stock_name} 매매훈련 GPT 복기 패키지",
            "generated_prompt": prompt,
            "sections": sections,
        }
