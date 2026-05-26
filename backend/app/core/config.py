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
YOUTUBE_API_ENABLED = os.getenv("YOUTUBE_API_ENABLED", "false").strip().lower() in {"1", "true", "yes", "y", "on"}
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "").strip()
YOUTUBE_API_TIMEOUT_SECONDS = int(os.getenv("YOUTUBE_API_TIMEOUT_SECONDS", "10"))
YOUTUBE_PLAYLIST_REFRESH_DEFAULT_LIMIT = int(os.getenv("YOUTUBE_PLAYLIST_REFRESH_DEFAULT_LIMIT", "20"))
ECONOMIC_BRIEFING_LLM_ENABLED = os.getenv("ECONOMIC_BRIEFING_LLM_ENABLED", "false").strip().lower() in {"1", "true", "yes", "y", "on"}
ECONOMIC_BRIEFING_LLM_PROVIDER = os.getenv("ECONOMIC_BRIEFING_LLM_PROVIDER", "local_lmstudio").strip()
ECONOMIC_BRIEFING_LLM_TIMEOUT_SECONDS = int(os.getenv("ECONOMIC_BRIEFING_LLM_TIMEOUT_SECONDS", "120"))
ECONOMIC_BRIEFING_LLM_MODEL = os.getenv("ECONOMIC_BRIEFING_LLM_MODEL", "").strip()
ECONOMIC_BRIEFING_CHUNK_MAX_CHARS = int(os.getenv("ECONOMIC_BRIEFING_CHUNK_MAX_CHARS", "4000"))
ECONOMIC_BRIEFING_CHUNK_OVERLAP_CHARS = int(os.getenv("ECONOMIC_BRIEFING_CHUNK_OVERLAP_CHARS", "50"))
ECONOMIC_BRIEFING_CHUNK_MAX_TOKENS = int(os.getenv("ECONOMIC_BRIEFING_CHUNK_MAX_TOKENS", "700"))
ECONOMIC_BRIEFING_CHUNK_RETRY_MAX_TOKENS = int(os.getenv("ECONOMIC_BRIEFING_CHUNK_RETRY_MAX_TOKENS", "1000"))
ECONOMIC_BRIEFING_OVERALL_MAX_TOKENS = int(os.getenv("ECONOMIC_BRIEFING_OVERALL_MAX_TOKENS", "1800"))
ECONOMIC_BRIEFING_TEMPERATURE = float(os.getenv("ECONOMIC_BRIEFING_TEMPERATURE", "0.2"))
ECONOMIC_BRIEFING_SUMMARY_SKIP_IF_EXISTS = os.getenv("ECONOMIC_BRIEFING_SUMMARY_SKIP_IF_EXISTS", "true").strip().lower() in {"1", "true", "yes", "y", "on"}
ECONOMIC_BRIEFING_SKIP_IF_SUMMARIZED = os.getenv("ECONOMIC_BRIEFING_SKIP_IF_SUMMARIZED", "true").strip().lower() in {"1", "true", "yes", "y", "on"}
TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "false").strip().lower() in {"1", "true", "yes", "y", "on"}
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID", "").strip()
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "").strip()
TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE", "").strip()
TELEGRAM_SESSION_DIR = os.getenv("TELEGRAM_SESSION_DIR", "backend/.local/telegram_sessions").strip()
TELEGRAM_USE_MOCK = os.getenv("TELEGRAM_USE_MOCK", "false").strip().lower() in {"1", "true", "yes", "y", "on"}
TELEGRAM_COLLECT_MAX_MESSAGES_PER_DAY = int(os.getenv("TELEGRAM_COLLECT_MAX_MESSAGES_PER_DAY", "200"))
TELEGRAM_LLM_ENABLED = os.getenv("TELEGRAM_LLM_ENABLED", "true").strip().lower() in {"1", "true", "yes", "y", "on"}
TELEGRAM_LLM_PROVIDER = os.getenv("TELEGRAM_LLM_PROVIDER", "local_lmstudio").strip()
TELEGRAM_LLM_MODEL = os.getenv("TELEGRAM_LLM_MODEL", "").strip()
TELEGRAM_LLM_MAX_TOKENS = int(os.getenv("TELEGRAM_LLM_MAX_TOKENS", "1200"))
TELEGRAM_LLM_TEMPERATURE = float(os.getenv("TELEGRAM_LLM_TEMPERATURE", "0.1"))
TELEGRAM_LLM_RESPONSE_FORMAT_JSON = os.getenv("TELEGRAM_LLM_RESPONSE_FORMAT_JSON", "false").strip().lower() in {"1", "true", "yes", "y", "on"}
PYKRX_DISABLE_PROXY = os.getenv("PYKRX_DISABLE_PROXY", "false").strip().lower() in {"1", "true", "yes", "y", "on"}

KIWOOM_REST_ENABLED = os.getenv("KIWOOM_REST_ENABLED", "false").strip().lower() in {"1", "true", "yes", "y", "on"}
KIWOOM_REST_BASE_URL = os.getenv("KIWOOM_REST_BASE_URL", "https://api.kiwoom.com").strip()
KIWOOM_REST_MOCK_BASE_URL = os.getenv("KIWOOM_REST_MOCK_BASE_URL", "https://mockapi.kiwoom.com").strip()
KIWOOM_REST_USE_MOCK = os.getenv("KIWOOM_REST_USE_MOCK", "true").strip().lower() in {"1", "true", "yes", "y", "on"}
KIWOOM_REST_APP_KEY = os.getenv("KIWOOM_REST_APP_KEY", "").strip()
KIWOOM_REST_SECRET_KEY = os.getenv("KIWOOM_REST_SECRET_KEY", "").strip()
KIWOOM_REST_ACCESS_TOKEN = os.getenv("KIWOOM_REST_ACCESS_TOKEN", "").strip()
KIWOOM_REST_TOKEN_EXPIRES_AT = os.getenv("KIWOOM_REST_TOKEN_EXPIRES_AT", "").strip()
KIWOOM_REST_RATE_LIMIT_PER_SECOND = float(os.getenv("KIWOOM_REST_RATE_LIMIT_PER_SECOND", "2"))
KIWOOM_REST_TIMEOUT_SECONDS = int(os.getenv("KIWOOM_REST_TIMEOUT_SECONDS", "10"))
KIWOOM_REST_MAX_PAGES = int(os.getenv("KIWOOM_REST_MAX_PAGES", "20"))
KIWOOM_REST_DAILY_PRICE_API_ID = os.getenv("KIWOOM_REST_DAILY_PRICE_API_ID", "ka10081").strip()
KIWOOM_REST_DAILY_PRICE_PATH = os.getenv("KIWOOM_REST_DAILY_PRICE_PATH", "/api/dostk/chart").strip()
KIWOOM_REST_MARKET_INDEX_API_ID = os.getenv("KIWOOM_REST_MARKET_INDEX_API_ID", "ka20001").strip()
KIWOOM_REST_MARKET_INDEX_PATH = os.getenv("KIWOOM_REST_MARKET_INDEX_PATH", "/api/dostk/sect").strip()
KIWOOM_REST_MARKET_INDEX_CODE_FIELD = os.getenv("KIWOOM_REST_MARKET_INDEX_CODE_FIELD", "inds_cd").strip()
KIWOOM_REST_MARKET_INDEX_MARKET_FIELD = os.getenv("KIWOOM_REST_MARKET_INDEX_MARKET_FIELD", "mrkt_tp").strip()
KIWOOM_REST_MARKET_KOSPI_CODE = os.getenv("KIWOOM_REST_MARKET_KOSPI_CODE", "001").strip()
KIWOOM_REST_MARKET_KOSDAQ_CODE = os.getenv("KIWOOM_REST_MARKET_KOSDAQ_CODE", "101").strip()
KIWOOM_REST_MARKET_KOSPI_TYPE = os.getenv("KIWOOM_REST_MARKET_KOSPI_TYPE", "0").strip()
KIWOOM_REST_MARKET_KOSDAQ_TYPE = os.getenv("KIWOOM_REST_MARKET_KOSDAQ_TYPE", "1").strip()
KIWOOM_REST_MARKET_DAILY_API_ID = os.getenv("KIWOOM_REST_MARKET_DAILY_API_ID", "ka20006").strip()
KIWOOM_REST_MARKET_DAILY_PATH = os.getenv("KIWOOM_REST_MARKET_DAILY_PATH", "/api/dostk/chart").strip()
KIWOOM_REST_BLOCK_ORDER_API = os.getenv("KIWOOM_REST_BLOCK_ORDER_API", "true").strip().lower() in {"1", "true", "yes", "y", "on"}
KIWOOM_REST_LOG_RAW_PREVIEW = os.getenv("KIWOOM_REST_LOG_RAW_PREVIEW", "false").strip().lower() in {"1", "true", "yes", "y", "on"}


def now_kst() -> str:
    return datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
