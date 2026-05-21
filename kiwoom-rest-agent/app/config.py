from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class Settings:
    env: str
    base_url: str
    app_key: str
    secret_key: str
    timeout_seconds: int
    drct_api_base_url: str
    drct_api_enabled: bool
    env_file_path: str
    use_proxy: bool
    ws_url: str
    ws_timeout_seconds: int


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _load_env_file() -> Path:
    current = Path(__file__).resolve()
    agent_root = current.parents[1]
    project_root = current.parents[2]
    candidates = [agent_root / ".env", project_root / ".env"]
    for p in candidates:
        if p.exists():
            load_dotenv(dotenv_path=p, override=False)
            return p
    raise ValueError(
        ".env 파일을 찾지 못했습니다. 다음 위치 중 하나에 .env를 생성해 주세요: "
        + ", ".join(str(x) for x in candidates)
    )


def load_settings() -> Settings:
    loaded_env = _load_env_file()
    env = os.getenv("KIWOOM_REST_ENV", "prod").strip().lower()
    prod_base = os.getenv("KIWOOM_REST_BASE_URL", "https://api.kiwoom.com").strip()
    mock_base = os.getenv("KIWOOM_REST_MOCK_BASE_URL", "https://mockapi.kiwoom.com").strip()
    base_url = prod_base if env == "prod" else mock_base

    app_key = os.getenv("KIWOOM_REST_APP_KEY", "").strip()
    secret_key = os.getenv("KIWOOM_REST_SECRET_KEY", "").strip()
    timeout_seconds = int(os.getenv("KIWOOM_REST_TIMEOUT_SECONDS", "10").strip() or "10")
    use_proxy = _to_bool(os.getenv("KIWOOM_REST_USE_PROXY"), default=False)
    ws_url = os.getenv("KIWOOM_WS_URL", "wss://api.kiwoom.com:10000/api/dostk/websocket").strip()
    ws_timeout_seconds = int(os.getenv("KIWOOM_WS_TIMEOUT_SECONDS", "10").strip() or "10")

    if not app_key or not secret_key:
        raise ValueError(
            "KIWOOM_REST_APP_KEY / KIWOOM_REST_SECRET_KEY가 설정되지 않았습니다. "
            "kiwoom-rest-agent/.env.example를 참고해 .env를 구성해 주세요. "
            f"(loaded_env={loaded_env})"
        )

    return Settings(
        env=env,
        base_url=base_url,
        app_key=app_key,
        secret_key=secret_key,
        timeout_seconds=timeout_seconds,
        drct_api_base_url=os.getenv("DRCT_API_BASE_URL", "http://localhost:8000").strip(),
        drct_api_enabled=_to_bool(os.getenv("DRCT_API_ENABLED"), default=False),
        env_file_path=str(loaded_env),
        use_proxy=use_proxy,
        ws_url=ws_url,
        ws_timeout_seconds=ws_timeout_seconds,
    )
