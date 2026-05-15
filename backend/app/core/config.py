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
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH.as_posix()}")
SQLITE_BUSY_TIMEOUT_MS = int(os.getenv("SQLITE_BUSY_TIMEOUT_MS", "10000"))
SQLITE_JOURNAL_MODE = os.getenv("SQLITE_JOURNAL_MODE", "WAL").upper()
SQLITE_SYNCHRONOUS = os.getenv("SQLITE_SYNCHRONOUS", "NORMAL").upper()

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
DATA_API_SERVICE_KEY = os.getenv("DATA_API_SERVICE_KEY", "").strip()
DATA_API_BASE_URL = os.getenv(
    "DATA_API_BASE_URL",
    "https://apis.data.go.kr/1160100/service/GetKrxListedInfoService/getItemInfo",
)
DATA_API_KEY_MODE = os.getenv("DATA_API_KEY_MODE", "encoded").lower()
DATA_API_TIMEOUT_SECONDS = int(os.getenv("DATA_API_TIMEOUT_SECONDS", "15"))
DATA_API_MAX_PAGES = int(os.getenv("DATA_API_MAX_PAGES", "10"))
KRX_OPEN_API_AUTH_KEY = os.getenv("KRX_OPEN_API_AUTH_KEY", "").strip()
KRX_OPEN_API_BASE_URL = os.getenv("KRX_OPEN_API_BASE_URL", "https://data-dbg.krx.co.kr/svc/apis").strip()
KRX_OPEN_API_TIMEOUT_SECONDS = int(os.getenv("KRX_OPEN_API_TIMEOUT_SECONDS", "20"))

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
KIS_APP_KEY = os.getenv("KIS_APP_KEY", "").strip()
KIS_APP_SECRET = os.getenv("KIS_APP_SECRET", "").strip()
KIS_BASE_URL = os.getenv("KIS_BASE_URL", "https://openapi.koreainvestment.com:9443").strip()
KIS_PAPER_BASE_URL = os.getenv("KIS_PAPER_BASE_URL", "https://openapivts.koreainvestment.com:29443").strip()
KIS_USE_PAPER = os.getenv("KIS_USE_PAPER", "true").strip().lower() in {"1", "true", "yes", "y", "on"}
KIS_ACCOUNT_NO = os.getenv("KIS_ACCOUNT_NO", "").strip()
KIS_PRODUCT_CODE = os.getenv("KIS_PRODUCT_CODE", "01").strip()
KIS_ACCESS_TOKEN = os.getenv("KIS_ACCESS_TOKEN", "").strip()
KIS_TOKEN_EXPIRES_AT = os.getenv("KIS_TOKEN_EXPIRES_AT", "").strip()
KIS_TIMEOUT_SECONDS = int(os.getenv("KIS_TIMEOUT_SECONDS", "15"))
KIS_DAILY_MAX_ROWS = int(os.getenv("KIS_DAILY_MAX_ROWS", "100"))


def now_kst() -> str:
    return datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
