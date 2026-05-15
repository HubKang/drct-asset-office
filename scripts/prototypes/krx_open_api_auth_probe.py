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


def mask_key(value: str) -> str:
    if not value:
        return ""
    suffix = value[-4:] if len(value) >= 4 else value
    return f"****{suffix}"


def main() -> int:
    key = getenv_str("KRX_OPEN_API_AUTH_KEY")
    if not key:
        print("KRX_OPEN_API_AUTH_KEY is not configured.")
        return 0

    print(f"KRX_OPEN_API_AUTH_KEY loaded: {mask_key(key)} (length={len(key)})")

    import requests

    session = requests.Session()
    session.trust_env = False
    url = "https://data-dbg.krx.co.kr/svc/apis/sto/stk_bydd_trd"
    headers = {"AUTH_KEY": key, "Accept": "application/json"}

    try:
        response = session.get(url, headers=headers, params={"basDd": "20260512"}, timeout=30)
        print(f"status={response.status_code}")
        print(f"content_type={response.headers.get('Content-Type', '')}")
        print(response.text[:500])
        try:
            payload = response.json()
            if isinstance(payload, dict):
                print("json_keys=", list(payload.keys())[:20])
                rows = payload.get("OutBlock_1")
                if isinstance(rows, list):
                    print("row_count=", len(rows))
                    if rows:
                        print("sample_keys=", list(rows[0].keys())[:30])
        except Exception as exc:
            print("json_parse_error=", repr(exc))
    except Exception as exc:
        print("request_error=", repr(exc))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
