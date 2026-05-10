from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH)

DB_PATH = PROJECT_ROOT / "db" / "drct_asset.sqlite3"
DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

NEWS_PROVIDER = os.getenv("NEWS_PROVIDER", "naver")
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
NEWS_DEFAULT_DISPLAY = int(os.getenv("NEWS_DEFAULT_DISPLAY", "20"))
NEWS_DEFAULT_SORT = os.getenv("NEWS_DEFAULT_SORT", "date")
NEWS_RAW_DIR = os.getenv("NEWS_RAW_DIR", "./data/raw/news")

DART_API_KEY = os.getenv("DART_API_KEY")
DART_RAW_DIR = os.getenv("DART_RAW_DIR", "./data/raw/dart")
DART_DISCLOSURE_DEFAULT_DAYS = int(os.getenv("DART_DISCLOSURE_DEFAULT_DAYS", "30"))
DART_PAGE_COUNT = int(os.getenv("DART_PAGE_COUNT", "100"))
KRX_API_SERVICE_KEY = os.getenv("KRX_API_SERVICE_KEY")
KRX_API_BASE_URL = os.getenv(
    "KRX_API_BASE_URL",
    "https://apis.data.go.kr/1160100/service/GetKrxListedInfoService/getItemInfo",
)
KRX_API_KEY_MODE = os.getenv("KRX_API_KEY_MODE", "encoded").lower()
KRX_API_TIMEOUT_SECONDS = int(os.getenv("KRX_API_TIMEOUT_SECONDS", "15"))
KRX_API_MAX_PAGES = int(os.getenv("KRX_API_MAX_PAGES", "10"))

LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
LMSTUDIO_MODEL = os.getenv("LMSTUDIO_MODEL", "google/gemma-4-e2b")
LLM_REPORT_BASE_DIR = os.getenv("LLM_REPORT_BASE_DIR", "./reports/company")

LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "300"))
LLM_MAX_OUTPUT_TOKENS = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "1500"))
LLM_MAX_INPUT_CHARS = int(os.getenv("LLM_MAX_INPUT_CHARS", "4500"))
LLM_MAX_NEWS_ITEMS = int(os.getenv("LLM_MAX_NEWS_ITEMS", "3"))
LLM_MAX_DISCLOSURE_ITEMS = int(os.getenv("LLM_MAX_DISCLOSURE_ITEMS", "3"))
LLM_MAX_ITEM_SUMMARY_CHARS = int(os.getenv("LLM_MAX_ITEM_SUMMARY_CHARS", "120"))
LLM_RETRY_COUNT = int(os.getenv("LLM_RETRY_COUNT", "1"))
ANALYSIS_MAX_NEWS_LIMIT = int(os.getenv("ANALYSIS_MAX_NEWS_LIMIT", "100"))
ANALYSIS_MAX_DISCLOSURE_LIMIT = int(os.getenv("ANALYSIS_MAX_DISCLOSURE_LIMIT", "100"))
LLM_CHUNK_SIZE = int(os.getenv("LLM_CHUNK_SIZE", "3"))
LLM_CHUNK_MAX_OUTPUT_TOKENS = int(os.getenv("LLM_CHUNK_MAX_OUTPUT_TOKENS", "700"))
LLM_FINAL_MAX_OUTPUT_TOKENS = int(os.getenv("LLM_FINAL_MAX_OUTPUT_TOKENS", "1500"))
LLM_ITEM_SUMMARY_TIMEOUT_SECONDS = int(os.getenv("LLM_ITEM_SUMMARY_TIMEOUT_SECONDS", "120"))
LLM_ITEM_SUMMARY_MAX_OUTPUT_TOKENS = int(os.getenv("LLM_ITEM_SUMMARY_MAX_OUTPUT_TOKENS", "500"))
LLM_ITEM_SUMMARY_RETRY_COUNT = int(os.getenv("LLM_ITEM_SUMMARY_RETRY_COUNT", "1"))
AI_SUMMARY_BATCH_NEWS_LIMIT = int(os.getenv("AI_SUMMARY_BATCH_NEWS_LIMIT", "10"))
AI_SUMMARY_BATCH_DISCLOSURE_LIMIT = int(os.getenv("AI_SUMMARY_BATCH_DISCLOSURE_LIMIT", "10"))


def now_kst() -> str:
    return datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
