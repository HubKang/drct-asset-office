from __future__ import annotations

from datetime import datetime, timedelta
import json
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.repositories.trade_training_repository import TradeTrainingRepository
from backend.app.schemas.trade_training_schema import SimulationReviewSaveRequest, TrainingOrderRequest, TrainingSessionCreate


RUNNING_STATUS = "진행중"
FINISHED_STATUS = "완료"
ABORTED_STATUS = "중단"


class TradeTrainingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = TradeTrainingRepository(db)

    def list_stocks(self, q: str | None, limit: int) -> dict[str, Any]:
        return {"items": self.repo.list_training_stocks(q=q, limit=limit), "limit": limit}

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

        created = self.repo.create_session(
            {
                "stock_code": stock["stock_code"],
                "stock_name": stock["stock_name"],
                "start_date": str(rows[0]["trade_date"]),
                "end_date": str(rows[-1]["trade_date"]),
                "current_date": str(rows[0]["trade_date"]),
                "current_index": 0,
                "initial_cash": float(payload.initial_cash),
                "cash": float(payload.initial_cash),
                "position_qty": 0,
                "avg_price": 0,
                "realized_profit": 0,
                "status": RUNNING_STATUS,
                "options": {
                    "stock_id": int(stock["stock_id"]),
                    "source": source,
                    "fee_rate": float(payload.fee_rate),
                    "display_days": int(payload.display_days),
                    "moving_averages": self._clean_mas(payload.moving_averages),
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
        data["options"] = self._parse_options(session)
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
        display_days = int(options.get("display_days") or 80)
        visible_start = max(0, current_index - display_days + 1)
        visible_prices = prices[visible_start : current_index + 1]
        moving_averages = self._clean_mas(list(options.get("moving_averages") or [5, 20, 60]))
        decorated = self._decorate_candles(visible_prices, moving_averages)
        return {
            "session": self._response_session(session),
            "candles": decorated,
            "current_candle": decorated[-1] if decorated else None,
            "account": self._calc_account(session, current_candle),
            "trades": self.repo.list_trades(session_id),
        }

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
        return self.get_session_detail(session_id)

    @staticmethod
    def _validate_price_in_candle(price: float, candle: dict[str, Any]) -> None:
        low = float(candle.get("low_price") or 0)
        high = float(candle.get("high_price") or 0)
        if low <= 0 or high <= 0 or price < low or price > high:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="주문가격이 현재 일봉 범위를 벗어났습니다.")

    def buy(self, session_id: int, payload: TrainingOrderRequest) -> dict[str, Any]:
        session = self._running_session(session_id)
        candle = self._current_price_row(session)
        self._validate_price_in_candle(payload.price, candle)
        options = self._parse_options(session)
        fee_rate = float(options.get("fee_rate") or 0)
        amount = float(payload.price) * int(payload.quantity)
        fee = amount * fee_rate
        cash = float(session.get("cash") or 0)
        if amount + fee > cash:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="현금이 부족합니다.")
        prev_qty = int(session.get("position_qty") or 0)
        prev_avg = float(session.get("avg_price") or 0)
        next_qty = prev_qty + int(payload.quantity)
        next_avg = ((prev_qty * prev_avg) + (int(payload.quantity) * float(payload.price))) / next_qty
        self.repo.insert_trade(
            {
                "session_id": session_id,
                "trade_date": str(candle["trade_date"]),
                "side": "BUY",
                "price": float(payload.price),
                "quantity": int(payload.quantity),
                "fee": round(fee, 4),
                "amount": round(amount, 4),
                "realized_profit": 0,
                "reason": payload.reason,
            }
        )
        self.repo.update_session(
            session_id,
            {
                "cash": round(cash - amount - fee, 4),
                "position_qty": next_qty,
                "avg_price": round(next_avg, 4),
            },
        )
        return self.get_session_detail(session_id)

    def sell(self, session_id: int, payload: TrainingOrderRequest) -> dict[str, Any]:
        session = self._running_session(session_id)
        candle = self._current_price_row(session)
        self._validate_price_in_candle(payload.price, candle)
        position_qty = int(session.get("position_qty") or 0)
        if payload.quantity > position_qty:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="보유수량이 부족합니다.")
        options = self._parse_options(session)
        fee_rate = float(options.get("fee_rate") or 0)
        amount = float(payload.price) * int(payload.quantity)
        fee = amount * fee_rate
        avg_price = float(session.get("avg_price") or 0)
        realized_profit = (float(payload.price) - avg_price) * int(payload.quantity) - fee
        next_qty = position_qty - int(payload.quantity)
        self.repo.insert_trade(
            {
                "session_id": session_id,
                "trade_date": str(candle["trade_date"]),
                "side": "SELL",
                "price": float(payload.price),
                "quantity": int(payload.quantity),
                "fee": round(fee, 4),
                "amount": round(amount, 4),
                "realized_profit": round(realized_profit, 4),
                "reason": payload.reason,
            }
        )
        self.repo.update_session(
            session_id,
            {
                "cash": round(float(session.get("cash") or 0) + amount - fee, 4),
                "position_qty": next_qty,
                "avg_price": 0 if next_qty == 0 else avg_price,
                "realized_profit": round(float(session.get("realized_profit") or 0) + realized_profit, 4),
            },
        )
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
                        "buy_reason": lot.get("reason"),
                        "sell_reason": trade.get("reason"),
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
        buy_trades = [trade for trade in trades if str(trade.get("side") or "").upper() == "BUY"]
        sell_trades = [trade for trade in trades if str(trade.get("side") or "").upper() == "SELL"]
        wins = [pair for pair in pairs if float(pair["profit_amount"]) > 0]
        losses = [pair for pair in pairs if float(pair["profit_amount"]) < 0]
        evens = [pair for pair in pairs if float(pair["profit_amount"]) == 0]
        closed_count = len(wins) + len(losses)
        total_fees = round(sum(float(trade.get("fee") or 0) for trade in trades), 4)

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
            "max_profit_amount": None if not pairs else round(max(float(p["profit_amount"]) for p in pairs), 4),
            "max_loss_amount": None if not pairs else round(min(float(p["profit_amount"]) for p in pairs), 4),
            "average_holding_days": None if not pairs else round(sum(int(p["holding_days"]) for p in pairs) / len(pairs), 4),
            "total_fees": total_fees,
            "buy_reason_fill_rate": None if not buy_trades else round(sum(1 for t in buy_trades if str(t.get("reason") or "").strip()) / len(buy_trades) * 100, 4),
            "sell_reason_fill_rate": None if not sell_trades else round(sum(1 for t in sell_trades if str(t.get("reason") or "").strip()) / len(sell_trades) * 100, 4),
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
                        f"- 매도 사유: {self._text(pair.get('sell_reason'))}",
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
        gpt_request = "\n".join(
            [
                "1. 이번 훈련의 핵심을 요약해 주세요.",
                "2. 수익/손실 결과보다 매매 판단 과정을 평가해 주세요.",
                "3. 매수 사유의 구체성과 근거 수준을 평가해 주세요.",
                "4. 매도 사유의 적절성과 일관성을 평가해 주세요.",
                "5. 손실 거래에서 반복되는 문제를 찾아 주세요.",
                "6. 수익 거래에서 잘한 점을 찾아 주세요.",
                "7. 손절 지연, 조기 매도, 추격매수 가능성을 평가해 주세요.",
                "8. 비중 조절과 리스크 관리 수준을 평가해 주세요.",
                "9. 다음 훈련에서 반드시 고쳐야 할 행동 3가지를 제안해 주세요.",
                "10. 다음 훈련 전 체크리스트를 제안해 주세요.",
                "11. 원칙 준수 점수를 0~100점으로 평가해 주세요.",
                "12. 이 훈련을 통해 사용자가 배워야 할 핵심 교훈을 정리해 주세요.",
            ]
        )
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

[7. 최종 요청]
이 훈련 결과를 바탕으로 제가 반복하는 판단 실수와 다음 훈련에서 반드시 고쳐야 할 행동을 구체적으로 분석해 주세요.
"""
        sections = {
            "training_summary": training_summary,
            "performance_summary": performance_summary,
            "trade_pairs_summary": "\n\n".join(trade_lines),
            "reason_summary": self_review_summary,
            "gpt_request": gpt_request,
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
