from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes_analysis import router as analysis_router
from backend.app.api.routes_advisory_packages import router as advisory_packages_router
from backend.app.api.routes_collectors import router as collectors_router
from backend.app.api.routes_collection_runs import router as collection_runs_router
from backend.app.api.routes_classification_rules import router as classification_rules_router
from backend.app.api.routes_disclosures import router as disclosures_router
from backend.app.api.routes_health import router as health_router
from backend.app.api.routes_news import router as news_router
from backend.app.api.routes_reports import router as reports_router
from backend.app.api.routes_schema_comments import router as schema_comments_router
from backend.app.api.routes_stocks import router as stocks_router
from backend.app.api.routes_watchlist import router as watchlist_router
from backend.app.core.logging import setup_logging

setup_logging()

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
app.include_router(stocks_router)
app.include_router(watchlist_router)
app.include_router(schema_comments_router)
app.include_router(news_router)
app.include_router(disclosures_router)
app.include_router(collectors_router)
app.include_router(collection_runs_router)
app.include_router(classification_rules_router)
app.include_router(analysis_router)
app.include_router(reports_router)
app.include_router(advisory_packages_router)
