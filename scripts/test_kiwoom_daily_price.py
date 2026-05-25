from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core.database import SessionLocal
from backend.app.providers.market_data.kiwoom_rest_provider import KiwoomRestMarketDataProvider
from backend.app.services.kiwoom_market_data_poc_service import KiwoomMarketDataPocService


def main() -> int:
    parser = argparse.ArgumentParser(description="Kiwoom REST daily price POC tester")
    parser.add_argument("--ticker", default="097230", help="6-digit stock code (or A-prefixed)")
    parser.add_argument("--mode", default="recent", choices=["recent", "backfill"], help="POC mode")
    parser.add_argument("--years", type=int, default=2, help="Backfill years for mode=backfill")
    parser.add_argument("--start", dest="start_date", default=None, help="Start date: YYYY-MM-DD or YYYYMMDD")
    parser.add_argument("--end", dest="end_date", default=None, help="End date: YYYY-MM-DD or YYYYMMDD")
    parser.add_argument("--max-pages", type=int, default=None, help="Max pages for cont-yn pagination")
    parser.add_argument("--repeat", type=int, default=1, help="Repeat call count")
    parser.add_argument("--api-id", default=None, help="Override api-id for probe")
    parser.add_argument("--endpoint", default=None, help="Override endpoint for probe")
    parser.add_argument("--probe", action="store_true", help="Run candidate endpoint/api-id probes")
    parser.add_argument("--save", action="store_true", help="Persist mapped rows into stock_daily_prices")
    parser.add_argument(
        "--calculate-technical",
        action="store_true",
        help="Calculate technical indicators after save (only when --save)",
    )
    args = parser.parse_args()

    if args.probe:
        provider = KiwoomRestMarketDataProvider()
        candidates = [
            {"api_id": "ka10081", "endpoint": "/api/dostk/chart"},
            {"api_id": "ka10078", "endpoint": "/api/dostk/chart"},
            {"api_id": "ka10086", "endpoint": "/api/dostk/chart"},
        ]
        results = []
        for c in candidates:
            try:
                r = provider.get_daily_prices(
                    args.ticker,
                    start_date=args.start_date,
                    end_date=args.end_date,
                    years=args.years if args.mode == "backfill" else 1,
                    max_pages=args.max_pages,
                    api_id=c["api_id"],
                    endpoint=c["endpoint"],
                )
                results.append(
                    {
                        "endpoint": c["endpoint"],
                        "api_id": c["api_id"],
                        "status": "success",
                        "return_code": r.get("return_code"),
                        "return_msg": r.get("return_msg"),
                        "raw_count": r.get("raw_count"),
                        "mapped_count": r.get("mapped_count"),
                        "api_call_count": r.get("api_call_count"),
                        "cont_yn_used": r.get("cont_yn_used"),
                        "next_key_used": r.get("next_key_used"),
                        "sample_keys": r.get("first_item_keys"),
                        "top_level_keys": r.get("top_level_keys"),
                        "list_candidates": r.get("list_candidates"),
                        "elapsed_ms": r.get("elapsed_ms"),
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "endpoint": c["endpoint"],
                        "api_id": c["api_id"],
                        "status": "failed",
                        "error": str(exc),
                    }
                )
        print(json.dumps({"probe": True, "ticker": args.ticker, "results": results}, ensure_ascii=False, indent=2))
        return 0 if any(x.get("status") == "success" for x in results) else 1

    with SessionLocal() as db:
        service = KiwoomMarketDataPocService(db)
        result = service.run_daily_price_poc(
            ticker=args.ticker,
            mode=args.mode,
            years=args.years,
            start_date=args.start_date,
            end_date=args.end_date,
            max_pages=args.max_pages,
            repeat_calls=args.repeat,
            api_id=args.api_id,
            endpoint=args.endpoint,
            save=args.save,
            calculate_technical=args.calculate_technical,
        )
    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
