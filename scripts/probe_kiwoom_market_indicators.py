from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.clients.kiwoom import KiwoomApiError, KiwoomRestClient
from backend.app.core import config


def extract_first_row(payload: dict) -> dict | None:
    if any(key in payload for key in ("cur_prc", "pred_pre", "flu_rt", "trde_qty", "trde_prica", "inds_cur_prc_tm")):
        return payload
    for key in ("output", "output1", "output2", "items", "data"):
        value = payload.get(key)
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return value[0]
        if isinstance(value, dict):
            if any(not isinstance(v, (dict, list)) for v in value.values()):
                return value
            for nested in value.values():
                if isinstance(nested, list) and nested and isinstance(nested[0], dict):
                    return nested[0]
    return None


def list_candidates(payload: dict) -> list[str]:
    out: list[str] = []
    for key, value in payload.items():
        if isinstance(value, list):
            out.append(key)
        elif isinstance(value, dict):
            for k2, v2 in value.items():
                if isinstance(v2, list):
                    out.append(f"{key}.{k2}")
    return out


def first_present(row: dict, keys: tuple[str, ...]):
    for key in keys:
        if key in row and row.get(key) not in (None, ""):
            return row.get(key)
    return None


def probe_market(name: str, code: str) -> None:
    client = KiwoomRestClient()
    api_id = config.KIWOOM_REST_MARKET_INDEX_API_ID
    path = config.KIWOOM_REST_MARKET_INDEX_PATH
    market_type = config.KIWOOM_REST_MARKET_KOSPI_TYPE if name == "KOSPI" else config.KIWOOM_REST_MARKET_KOSDAQ_TYPE

    print(f"{name} probe")
    print(f"- endpoint: {path}")
    print(f"- api_id: {api_id}")
    print(f"- request_code: {code}")

    body = {
        config.KIWOOM_REST_MARKET_INDEX_MARKET_FIELD: market_type,
        config.KIWOOM_REST_MARKET_INDEX_CODE_FIELD: code,
    }
    try:
        resp = client.post_json(path, api_id=api_id, body=body)
        payload = resp.json_body
        row = extract_first_row(payload) or {}
        print(f"- body: {body}")
        print("- success: true")
        print(f"- return_code: {payload.get('return_code')}")
        print(f"- return_msg: {payload.get('return_msg')}")
        print(f"- top_level_keys: {list(payload.keys())}")
        print(f"- list_keys: {list_candidates(payload)}")
        print(f"- first_row_keys: {list(row.keys())[:40]}")
        print("- candidate_values:")
        print(f"  - date: {first_present(row, ('stck_bsop_date','base_date','trade_date','dt'))}")
        print(f"  - index_value: {first_present(row, ('bstp_nmix_prpr','indx_prpr','index_value','close_price','close','cur_prc'))}")
        print(f"  - change_value: {first_present(row, ('bstp_nmix_prdy_vrss','indx_prdy_vrss','change_value','change_price','pred_pre'))}")
        print(f"  - change_rate: {first_present(row, ('bstp_nmix_prdy_ctrt','prdy_ctrt','change_rate','flu_rt','trde_tern_rt'))}")
        print(f"  - volume: {first_present(row, ('acml_vol','trading_volume','volume','trde_qty'))}")
        print(f"  - trading_value: {first_present(row, ('acml_tr_pbmn','acml_tr_pbmn2','trading_value','trde_prica'))}")
    except KiwoomApiError as exc:
        print(f"- body: {body}")
        print("- success: false")
        print(f"- return_code/status: {exc.status_code}")
        print(f"- return_msg: {exc.message}")
    except Exception as exc:
        print(f"- body: {body}")
        print("- success: false")
        print(f"- return_msg: {type(exc).__name__}: {exc}")
    print("")


def main() -> int:
    probe_market("KOSPI", config.KIWOOM_REST_MARKET_KOSPI_CODE)
    probe_market("KOSDAQ", config.KIWOOM_REST_MARKET_KOSDAQ_CODE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
