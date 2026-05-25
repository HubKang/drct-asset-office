from __future__ import annotations

import argparse
from datetime import datetime

from backend.app.collectors.prices.pykrx_price_collector import PykrxPriceCollector


def parse_yyyymmdd(value: str):
    return datetime.strptime(value, "%Y%m%d").date()


def main() -> None:
    parser = argparse.ArgumentParser(description="Test single PyKRX ticker fetch")
    parser.add_argument("--ticker", default="097230")
    parser.add_argument("--start", default="20260520")
    parser.add_argument("--end", default="20260525")
    args = parser.parse_args()

    collector = PykrxPriceCollector()
    try:
        normalized, rows = collector.collect_daily(
            stock_code=args.ticker,
            start_date=parse_yyyymmdd(args.start),
            end_date=parse_yyyymmdd(args.end),
            adjusted=True,
        )
        print(f"ticker={args.ticker} normalized={normalized} start={args.start} end={args.end}")
        print(f"rows={len(rows)}")
        if rows:
            print(f"head={rows[0]}")
            print(f"tail={rows[-1]}")
    except Exception as exc:
        print(f"ticker={args.ticker} start={args.start} end={args.end}")
        print(f"error_type={type(exc).__name__}")
        print(f"error_message={exc}")


if __name__ == "__main__":
    main()
