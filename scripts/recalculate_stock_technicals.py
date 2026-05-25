from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.database import SessionLocal
from backend.app.repositories.stock_repository import StockRepository
from backend.app.services.stock_price_service import StockPriceService
from backend.app.utils.stock_code_utils import normalize_kr_stock_code


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recalculate moving averages and technical indicators for selected stocks")
    parser.add_argument("--ticker", action="append", default=[], help="Stock code, repeatable (e.g. --ticker 097230)")
    parser.add_argument("--all", action="store_true", help="Recalculate all active stocks")
    parser.add_argument("--source", default="kiwoom_rest", help="Technical indicator source label to save")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.all and not args.ticker:
        print("error: either --ticker or --all is required")
        return 2

    db = SessionLocal()
    try:
        stock_repo = StockRepository(db)
        service = StockPriceService(db)

        stocks = []
        if args.all:
            stocks = stock_repo.list(keyword=None, is_active=1, market=None, security_type=None, limit=100000, offset=0)
        else:
            for raw in args.ticker:
                code = normalize_kr_stock_code(raw)
                stock = stock_repo.get_by_code(code)
                if stock is None:
                    print(
                        json.dumps(
                            {
                                "stock_code": code,
                                "error_type": "PRICE_DATA_NOT_FOUND",
                                "error_message": "stock not found",
                            },
                            ensure_ascii=False,
                        )
                    )
                    continue
                stocks.append(stock)

        if not stocks:
            print("error: no stocks to process")
            return 3

        for stock in stocks:
            try:
                price_rows = service.price_repo.list_by_stock(stock_id=stock.id, start_date=None, end_date=None, source=args.source, limit=100000, offset=0)
                price_count = len(price_rows)
                if price_count == 0:
                    print(
                        json.dumps(
                            {
                                "stock_code": stock.stock_code,
                                "stock_id": stock.id,
                                "source": args.source,
                                "price_count": 0,
                                "error_type": "PRICE_DATA_NOT_FOUND",
                                "error_message": "no price rows for source",
                            },
                            ensure_ascii=False,
                        )
                    )
                    continue

                service.recalculate_moving_averages(stock.id)
                result = service.technical_indicator_service.calculate_and_save_for_stock(
                    stock_id=stock.id,
                    source_label=args.source,
                )

                print(
                    json.dumps(
                        {
                            "stock_code": stock.stock_code,
                            "stock_id": stock.id,
                            "source": args.source,
                            "price_count": price_count,
                            "calculated_count": int(result.get("calculated_count") or 0),
                            "saved_count": int(result.get("saved_count") or 0),
                            "latest_trade_date": result.get("latest_trade_date"),
                            "status": "success",
                        },
                        ensure_ascii=False,
                    )
                )
            except Exception as exc:
                print(
                    json.dumps(
                        {
                            "stock_code": stock.stock_code,
                            "stock_id": stock.id,
                            "source": args.source,
                            "price_count": 0,
                            "error_type": "TECHNICAL_CALCULATION_FAILED",
                            "error_message": str(exc),
                        },
                        ensure_ascii=False,
                    )
                )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
