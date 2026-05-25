from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from telethon.sync import TelegramClient

from backend.app.core.config import (
    TELEGRAM_API_HASH,
    TELEGRAM_API_ID,
    TELEGRAM_ENABLED,
    TELEGRAM_PHONE,
    TELEGRAM_SESSION_DIR,
)


def mask(value: str, keep: int = 2) -> str:
    if not value:
        return ""
    if len(value) <= keep * 2:
        return "*" * len(value)
    return f"{value[:keep]}***{value[-keep:]}"


def main() -> None:
    print("[init_telegram_session] start")
    print(f"- TELEGRAM_ENABLED: {TELEGRAM_ENABLED}")
    print(f"- TELEGRAM_API_ID exists: {bool(TELEGRAM_API_ID)}")
    print(f"- TELEGRAM_API_HASH exists: {bool(TELEGRAM_API_HASH)}")
    print(f"- TELEGRAM_PHONE exists: {bool(TELEGRAM_PHONE)} ({mask(TELEGRAM_PHONE)})")

    if not TELEGRAM_ENABLED:
        raise RuntimeError("TELEGRAM_ENABLED=false. .env 설정을 확인해 주세요.")
    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH or not TELEGRAM_PHONE:
        raise RuntimeError("TELEGRAM_API_ID/TELEGRAM_API_HASH/TELEGRAM_PHONE 중 누락된 값이 있습니다.")

    session_dir = Path(TELEGRAM_SESSION_DIR)
    session_dir.mkdir(parents=True, exist_ok=True)
    session_path = session_dir / "drct_asset_telegram"

    print(f"- session dir: {session_dir}")
    client = TelegramClient(str(session_path), int(TELEGRAM_API_ID), TELEGRAM_API_HASH)
    try:
        client.connect()
        if client.is_user_authorized():
            print("- already authorized: true")
        else:
            print("- already authorized: false")
            print("- 인증 코드 입력이 필요합니다. 로컬 터미널에서 코드를 입력해 주세요.")
            client.start(phone=TELEGRAM_PHONE)
    finally:
        client.disconnect()

    session_file = session_path.with_suffix(".session")
    exists = session_file.exists() or session_path.exists()
    print(f"- session exists: {exists}")
    print(f"- session path: {session_file}")
    print("[init_telegram_session] done")


if __name__ == "__main__":
    main()
