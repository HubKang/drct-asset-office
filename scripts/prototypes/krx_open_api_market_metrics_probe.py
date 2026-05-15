from __future__ import annotations

import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if load_dotenv is not None:
    load_dotenv(PROJECT_ROOT / ".env")


def getenv_str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


KRX_OPEN_API_AUTH_KEY = getenv_str("KRX_OPEN_API_AUTH_KEY")
KRX_OPEN_API_BASE_URL = getenv_str("KRX_OPEN_API_BASE_URL", "https://data-dbg.krx.co.kr/svc/apis")
KRX_OPEN_API_TIMEOUT_SECONDS = int(getenv_str("KRX_OPEN_API_TIMEOUT_SECONDS", "20"))

TARGET_DATE = "2026-05-12"
TARGET_CODES = {"000020", "454910"}
ENDPOINTS = {
    "KOSPI": "sto/stk_bydd_trd",
    "KOSDAQ": "sto/ksq_bydd_trd",
}


def fetch_market(market: str) -> pd.DataFrame:
    import pandas as pd
    import requests

    session = requests.Session()
    session.trust_env = False
    url = f"{KRX_OPEN_API_BASE_URL.rstrip('/')}/{ENDPOINTS[market]}"
    headers = {
        "AUTH_KEY": KRX_OPEN_API_AUTH_KEY,
        "Accept": "application/json",
    }
    response = session.get(url, headers=headers, params={"basDd": TARGET_DATE.replace("-", "")}, timeout=KRX_OPEN_API_TIMEOUT_SECONDS)
    print(f"[{market}] status={response.status_code}")
    if response.status_code != 200:
        print(response.text[:500])
        raise RuntimeError(f"{market} HTTP {response.status_code}")

    payload = response.json()
    if payload.get("respCode") not in (None, "000", "00"):
        raise RuntimeError(f"{market} API error: {payload.get('respCode')} {payload.get('respMsg', '')}".strip())

    rows = payload.get("OutBlock_1", [])
    df = pd.DataFrame(rows)
    print(f"[{market}] rows={len(df)}")
    print(f"[{market}] columns={list(df.columns)}")
    if not df.empty:
        code_col = "ISU_SRT_CD" if "ISU_SRT_CD" in df.columns else "ISU_CD"
        matched = df[df[code_col].astype(str).isin(TARGET_CODES)]
        print(f"[{market}] matched_target_rows={len(matched)}")
        if not matched.empty:
            keep_cols = [col for col in ["BAS_DD", code_col, "ISU_NM", "TDD_CLSPRC", "ACC_TRDVOL", "ACC_TRDVAL", "MKTCAP", "LIST_SHRS", "MKT_NM"] if col in matched.columns]
            print(matched[keep_cols].to_string(index=False))
        print(f"[{market}] first_row={json.dumps(rows[0], ensure_ascii=False)[:1000]}")
    return df


def main() -> int:
    if not KRX_OPEN_API_AUTH_KEY:
        print("KRX_OPEN_API_AUTH_KEY is not configured. Skipping KRX Open API probe.")
        return 0

    masked = f"****{KRX_OPEN_API_AUTH_KEY[-4:]}" if len(KRX_OPEN_API_AUTH_KEY) >= 4 else "****"
    print(f"KRX_OPEN_API_AUTH_KEY loaded: {masked} (length={len(KRX_OPEN_API_AUTH_KEY)})")
    for market in ("KOSPI", "KOSDAQ"):
        try:
            fetch_market(market)
        except Exception as exc:
            print(f"[{market}] probe_error={exc!r}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
