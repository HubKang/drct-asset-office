from __future__ import annotations

import os
import sqlite3
from importlib import metadata
from pathlib import Path
from pprint import pprint


ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "db" / "drct_asset.sqlite3"


def package_version(name: str) -> str:
    try:
        return metadata.version(name)
    except Exception:
        return "NOT_INSTALLED"


def get_latest_trade_date() -> str | None:
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.cursor()
        row = cur.execute("SELECT MAX(trade_date) FROM stock_daily_prices WHERE source='pykrx'").fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def pykrx_probe(target_date: str, tickers: list[str]) -> dict:
    result: dict = {
        "functions": [],
        "per_ticker": {},
        "by_ticker": {},
        "errors": [],
    }
    proxy_keys = ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]
    backup = {k: os.environ.get(k) for k in proxy_keys}
    mpl_dir = ROOT / ".mpltcache"
    mpl_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_dir.resolve()))

    try:
        for key in proxy_keys:
            os.environ.pop(key, None)
        os.environ["NO_PROXY"] = "*"
        try:
            from pykrx import stock
        except Exception as exc:
            result["errors"].append(f"pykrx_import_error={exc!r}")
            return result

        result["functions"] = sorted([name for name in dir(stock) if "market_cap" in name.lower()])

        for ticker in tickers:
            ticker_result = {}
            try:
                df = stock.get_market_cap(target_date, target_date, ticker)
                ticker_result["get_market_cap_columns"] = list(df.columns)
                ticker_result["get_market_cap_rows"] = len(df)
                ticker_result["get_market_cap_index_name"] = df.index.name
                if not df.empty:
                    ticker_result["get_market_cap_head"] = df.head(1).reset_index().to_dict(orient="records")
            except Exception as exc:
                ticker_result["get_market_cap_error"] = repr(exc)

            try:
                df = stock.get_market_cap_by_date(target_date, target_date, ticker)
                ticker_result["get_market_cap_by_date_columns"] = list(df.columns)
                ticker_result["get_market_cap_by_date_rows"] = len(df)
                ticker_result["get_market_cap_by_date_index_name"] = df.index.name
                if not df.empty:
                    ticker_result["get_market_cap_by_date_head"] = df.head(1).reset_index().to_dict(orient="records")
            except Exception as exc:
                ticker_result["get_market_cap_by_date_error"] = repr(exc)

            result["per_ticker"][ticker] = ticker_result

        try:
            df_all = stock.get_market_cap_by_ticker(target_date)
            result["by_ticker"]["columns"] = list(df_all.columns)
            result["by_ticker"]["rows"] = len(df_all)
            result["by_ticker"]["index_name"] = df_all.index.name
            result["by_ticker"]["matches"] = {ticker: ticker in df_all.index for ticker in tickers}
            matched = [ticker for ticker in tickers if ticker in df_all.index]
            if matched:
                result["by_ticker"]["sample"] = df_all.loc[matched].reset_index().to_dict(orient="records")
        except Exception as exc:
            result["by_ticker"]["error"] = repr(exc)
    finally:
        for key, value in backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    return result


def main() -> None:
    latest_trade_date = get_latest_trade_date()
    target_date = (latest_trade_date or "2026-05-12").replace("-", "")
    tickers = ["000020", "454910"]

    print("[versions]")
    for name in ["pykrx", "FinanceDataReader", "marcap"]:
        print(f"{name}={package_version(name)}")

    print("\n[db]")
    print(f"latest_trade_date={latest_trade_date}")
    print(f"target_date={target_date}")
    print(f"tickers={tickers}")

    print("\n[pykrx]")
    pprint(pykrx_probe(target_date=target_date, tickers=tickers), sort_dicts=False)

    print("\n[notes]")
    print(f"python_executable={os.sys.executable}")
    print("- FinanceDataReader is not probed unless installed.")
    print("- marcap is not probed unless installed.")
    print("- This script does not modify DB, API, or production collectors.")


if __name__ == "__main__":
    main()
