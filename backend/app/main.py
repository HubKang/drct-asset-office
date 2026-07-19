from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes_analysis import router as analysis_router
from backend.app.api.routes_analysis_indicators import router as analysis_indicators_router
from backend.app.api.routes_architecture import router as architecture_router
from backend.app.api.routes_advisory_packages import router as advisory_packages_router
from backend.app.api.routes_backtest import router as backtest_router
from backend.app.api.routes_collectors import router as collectors_router
from backend.app.api.routes_collection_runs import router as collection_runs_router
from backend.app.api.routes_classification_rules import router as classification_rules_router
from backend.app.api.routes_disclosures import router as disclosures_router
from backend.app.api.routes_economic_briefing import router as economic_briefing_router
from backend.app.api.routes_external_kiwoom import router as external_kiwoom_router
from backend.app.api.routes_gpt_prompt_templates import router as gpt_prompt_templates_router
from backend.app.api.routes_health import router as health_router
from backend.app.api.routes_images import router as images_router
from backend.app.api.routes_market_metrics import router as market_metrics_router
from backend.app.api.routes_kms import router as kms_router
from backend.app.api.routes_market_calendar import router as market_calendar_router
from backend.app.api.routes_market_data import router as market_data_router
from backend.app.api.routes_market_indexes import router as market_indexes_router
from backend.app.api.routes_market_indicators import router as market_indicators_router
from backend.app.api.routes_market_signals import router as market_signals_router
from backend.app.api.routes_market_theme_candidates import router as market_theme_candidates_router
from backend.app.api.routes_market_themes import router as market_themes_router
from backend.app.api.routes_market_trends import router as market_trends_router
from backend.app.api.routes_news import router as news_router
from backend.app.api.routes_pattern_research import router as pattern_research_router
from backend.app.api.routes_kiwoom import router as kiwoom_router
from backend.app.api.routes_reports import router as reports_router
from backend.app.api.routes_schema_comments import router as schema_comments_router
from backend.app.api.routes_stocks import router as stocks_router
from backend.app.api.routes_stock_prices import router as stock_prices_router
from backend.app.api.routes_stock_financials import router as stock_financials_router
from backend.app.api.routes_stock_investor_flows import router as stock_investor_flows_router
from backend.app.api.routes_stock_tracking import router as stock_tracking_router
from backend.app.api.routes_telegram import router as telegram_router
from backend.app.api.routes_trade_training import router as trade_training_router
from backend.app.api.routes_trade_journals import router as trade_journals_router
from backend.app.api.routes_trade_reviews import router as trade_reviews_router
from backend.app.api.routes_watchlist import router as watchlist_router
from backend.app.api.routes_watchlist_evaluation import router as watchlist_evaluation_router
from backend.app.core.database import ensure_market_data_collection_schema, ensure_market_signal_schema, ensure_runtime_schema
from backend.app.core.config import PROJECT_ROOT
from backend.app.core.logging import setup_logging

setup_logging()
ensure_runtime_schema()
ensure_market_data_collection_schema()
ensure_market_signal_schema()

app = FastAPI(title="DrCT Asset API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(images_router)
app.include_router(stocks_router)
app.include_router(stock_prices_router)
app.include_router(stock_financials_router)
app.include_router(stock_investor_flows_router)
app.include_router(stock_tracking_router)
app.include_router(market_metrics_router)
app.include_router(market_calendar_router)
app.include_router(market_data_router)
app.include_router(market_indexes_router)
app.include_router(market_indicators_router)
app.include_router(market_signals_router)
app.include_router(market_themes_router)
app.include_router(market_theme_candidates_router)
app.include_router(market_trends_router)
app.include_router(watchlist_evaluation_router)
app.include_router(watchlist_router)
app.include_router(schema_comments_router)
app.include_router(news_router)
app.include_router(kiwoom_router)
app.include_router(kms_router)
app.include_router(disclosures_router)
app.include_router(collectors_router)
app.include_router(collection_runs_router)
app.include_router(classification_rules_router)
app.include_router(analysis_router)
app.include_router(analysis_indicators_router)
app.include_router(reports_router)
app.include_router(advisory_packages_router)
app.include_router(gpt_prompt_templates_router)
app.include_router(external_kiwoom_router)
app.include_router(economic_briefing_router)
app.include_router(telegram_router)
app.include_router(trade_training_router)
app.include_router(backtest_router)
app.include_router(pattern_research_router)
app.include_router(trade_journals_router)
app.include_router(trade_reviews_router)
app.include_router(architecture_router)
app.mount("/static", StaticFiles(directory=str(PROJECT_ROOT / "data")), name="static")
app.mount("/uploads", StaticFiles(directory=str(PROJECT_ROOT / "backend" / "uploads"), check_dir=False), name="uploads")
