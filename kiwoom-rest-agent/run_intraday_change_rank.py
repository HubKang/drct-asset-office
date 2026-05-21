from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from app.auth_client import AuthClient
from app.config import load_settings
from app.kiwoom_rest_client import KiwoomRestClient
from app.mapper import map_to_market_event_payload
from app.rank_client import RankClient


def _extract_items(body: dict) -> list[dict]:
    for key in ["open_pric_pre_flu_rt", "output", "data", "items"]:
        value = body.get(key)
        if isinstance(value, list):
            return value
    return []


def main() -> None:
    settings = load_settings()
    auth = AuthClient(settings)
    rest = KiwoomRestClient(settings)
    rank_client = RankClient(rest)

    token = auth.issue_token().token
    result = rank_client.get_intraday_change_rank(token=token)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    root = Path(__file__).resolve().parent
    raw_path = root / "data" / "raw" / f"ka10028_raw_{ts}.json"
    norm_path = root / "data" / "normalized" / f"ka10028_normalized_{ts}.json"

    raw_path.write_text(json.dumps(result.body, ensure_ascii=False, indent=2), encoding="utf-8")

    items = _extract_items(result.body)
    normalized = map_to_market_event_payload(items)
    norm_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"수신 건수: {len(normalized['items'])}")
    for i, row in enumerate(normalized["items"][:10], start=1):
        print(f"{i:>2}. {row['stock_code']} {row['stock_name']} | 시가대비등락률={row['intraday_change_rate']} | 현재가={row['current_price']}")


if __name__ == "__main__":
    main()
