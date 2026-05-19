from __future__ import annotations

from datetime import date, timedelta

import requests

from backend.app.core.config import KRX_OPEN_API_AUTH_KEY, KRX_OPEN_API_BASE_URL, KRX_OPEN_API_TIMEOUT_SECONDS


def _recent_business_day() -> str:
    d = date.today()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.isoformat()


def _call(endpoint: str, trade_date: str) -> tuple[int | None, str]:
    if not KRX_OPEN_API_AUTH_KEY:
        return None, "KRX_OPEN_API_AUTH_KEY is not configured."
    url = f"{KRX_OPEN_API_BASE_URL.rstrip('/')}/{endpoint}"
    headers = {"AUTH_KEY": KRX_OPEN_API_AUTH_KEY, "Accept": "application/json"}
    params = {"basDd": trade_date.replace("-", "")}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=KRX_OPEN_API_TIMEOUT_SECONDS)
    except Exception as exc:
        return None, f"request_error: {exc}"
    snippet = response.text[:300].replace("\n", " ")
    return response.status_code, snippet


def main() -> None:
    trade_date = _recent_business_day()
    loaded = bool(KRX_OPEN_API_AUTH_KEY)
    print(f"KRX_OPEN_API_AUTH_KEY loaded: {loaded}")
    print(f"KRX_OPEN_API_AUTH_KEY length: {len(KRX_OPEN_API_AUTH_KEY) if loaded else 0}")
    print(f"trade_date: {trade_date}")

    kospi_status, kospi_msg = _call("sto/stk_bydd_trd", trade_date)
    kosdaq_status, kosdaq_msg = _call("sto/ksq_bydd_trd", trade_date)

    print(f"KOSPI status: {kospi_status}")
    print(f"KOSPI response snippet: {kospi_msg}")
    print(f"KOSDAQ status: {kosdaq_status}")
    print(f"KOSDAQ response snippet: {kosdaq_msg}")

    detected = any(k in (kospi_msg + kosdaq_msg).lower() for k in ("acc_trdval", "trdval", "거래대금"))
    print(f"trading_value field detected: {detected}")

    if kospi_status == 200 and kosdaq_status == 200:
        verdict = "사용 가능"
    elif kospi_status == 401 or kosdaq_status == 401:
        verdict = "인증키는 로딩되나 서비스 승인 필요"
    elif kospi_status is None or kosdaq_status is None:
        verdict = "요청 환경 또는 네트워크 추가 확인 필요"
    else:
        verdict = "요청 파라미터/문서 추가 확인 필요"
    print(f"final_verdict: {verdict}")


if __name__ == "__main__":
    main()
