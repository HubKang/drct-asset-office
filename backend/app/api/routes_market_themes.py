from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.market_theme_schema import (
    MarketThemeCreateRequest,
    MarketThemeDeleteResponse,
    MarketThemeResponse,
    MarketThemeUpdateRequest,
)
from backend.app.schemas.market_theme_stock_schema import (
    MarketThemeByStockResponse,
    MarketThemeStockMemoResponse,
    MarketThemeStockCreateRequest,
    MarketThemeStockResponse,
    MarketThemeStockMemoUpdateRequest,
    MarketThemeStockSupplySummaryResponse,
    MarketThemeStockUpdateRequest,
)
from backend.app.schemas.market_theme_return_prediction_schema import (
    MarketThemeReturnPredictionRequest,
    MarketThemeReturnPredictionResponse,
    MarketThemeReturnValidationRequest,
    MarketThemeReturnMLRequest,
    MarketThemeReturnMLSelectRequest,
    MarketThemeReturnMLStatusResponse,
    MarketThemeReturnMLTrainResponse,
)
from backend.app.schemas.market_theme_observation_schema import (
    MarketThemeObservationRequest,
    MarketThemeObservationResponse,
    MarketThemeObservationMLTrainResponse,
    MarketThemeObservationDiagnosticsResponse,
)
from backend.app.schemas.realtime_theme_schema import (
    RealtimeThemeRefreshResponse,
    RealtimeThemeStocksResponse,
    RealtimeThemeTreemapResponse,
)
from backend.app.services.market_theme_service import MarketThemeService
from backend.app.services.market_theme_return_prediction_service import MarketThemeReturnPredictionService
from backend.app.services.market_theme_return_ml_service import MarketThemeReturnMLService
from backend.app.services.market_theme_return_rank_ml_service import MarketThemeReturnRankMLService
from backend.app.services.market_theme_observation_service import MarketThemeObservationService
from backend.app.services.market_theme_observation_ml_service import MarketThemeObservationMLService
from backend.app.services.market_theme_observation_validation_service import MarketThemeObservationValidationService
from backend.app.services.market_theme_stock_service import MarketThemeStockService
from backend.app.services.market_theme_flow_trend_service import invalidate_market_theme_flow_trend_cache
from backend.app.services.realtime_theme_service import RealtimeThemeService

router = APIRouter()


@router.post("/market-themes/realtime/refresh", response_model=RealtimeThemeRefreshResponse)
def refresh_realtime_market_themes(db: Session = Depends(get_db)) -> RealtimeThemeRefreshResponse:
    return RealtimeThemeService(db).refresh()


@router.get("/market-themes/realtime/treemap", response_model=RealtimeThemeTreemapResponse)
def get_realtime_market_theme_treemap(db: Session = Depends(get_db)) -> RealtimeThemeTreemapResponse:
    return RealtimeThemeService(db).get_treemap()


@router.get("/market-themes/realtime/{theme_id}/stocks", response_model=RealtimeThemeStocksResponse)
def get_realtime_market_theme_stocks(theme_id: int, db: Session = Depends(get_db)) -> RealtimeThemeStocksResponse:
    return RealtimeThemeService(db).get_theme_stocks(theme_id)


@router.get("/market-themes/observation-priorities/latest", response_model=MarketThemeObservationResponse)
def get_latest_market_theme_observation(db: Session = Depends(get_db)) -> MarketThemeObservationResponse:
    return MarketThemeObservationService(db).latest()


@router.get("/market-themes/observation-priorities", response_model=MarketThemeObservationResponse)
def get_market_theme_observation(
    target_date: str = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
) -> MarketThemeObservationResponse:
    return MarketThemeObservationService(db).get(target_date)


@router.post("/market-themes/observation-priorities/calculate", response_model=MarketThemeObservationResponse)
def calculate_market_theme_observation(
    payload: MarketThemeObservationRequest,
    db: Session = Depends(get_db),
) -> MarketThemeObservationResponse:
    return MarketThemeObservationService(db).calculate_with_market_option(
        payload.target_date,
        refresh_market_indicators=payload.refresh_market_indicators,
    )


@router.post("/market-themes/observation-priorities/validate", response_model=MarketThemeObservationResponse)
def validate_market_theme_observation(
    payload: MarketThemeObservationRequest,
    db: Session = Depends(get_db),
) -> MarketThemeObservationResponse:
    return MarketThemeObservationService(db).validate(payload.target_date)


@router.post("/market-themes/observation-priorities/ml/train", response_model=MarketThemeObservationMLTrainResponse)
def train_market_theme_observation_ml(db: Session = Depends(get_db)) -> MarketThemeObservationMLTrainResponse:
    return MarketThemeObservationMLService(db).train()


@router.get("/market-themes/observation-priorities/diagnostics", response_model=MarketThemeObservationDiagnosticsResponse)
def get_market_theme_observation_diagnostics(db: Session = Depends(get_db)) -> MarketThemeObservationDiagnosticsResponse:
    return MarketThemeObservationValidationService(db).diagnostics()


@router.get("/market-themes/return-predictions/ml/status", response_model=MarketThemeReturnMLStatusResponse)
def get_market_theme_return_ml_status(db: Session = Depends(get_db)) -> MarketThemeReturnMLStatusResponse:
    return MarketThemeReturnRankMLService(db).status()


@router.post("/market-themes/return-predictions/ml/train-rank-candidates", response_model=MarketThemeReturnMLTrainResponse)
@router.post("/api/market-themes/return-predictions/ml/train-rank-candidates", response_model=MarketThemeReturnMLTrainResponse, include_in_schema=False)
def train_market_theme_return_rank_candidates(db: Session = Depends(get_db)) -> MarketThemeReturnMLTrainResponse:
    return MarketThemeReturnRankMLService(db).train_rank_candidates()


@router.post("/market-themes/return-predictions/ml/select-shadow", response_model=MarketThemeReturnMLStatusResponse)
@router.post("/api/market-themes/return-predictions/ml/select-shadow", response_model=MarketThemeReturnMLStatusResponse, include_in_schema=False)
def select_market_theme_return_shadow(
    payload: MarketThemeReturnMLSelectRequest,
    db: Session = Depends(get_db),
) -> MarketThemeReturnMLStatusResponse:
    return MarketThemeReturnRankMLService(db).select_shadow(payload.model_version)


@router.post("/market-themes/return-predictions/ml/train-shadow", response_model=MarketThemeReturnMLTrainResponse)
def train_market_theme_return_ml_shadow(db: Session = Depends(get_db)) -> MarketThemeReturnMLTrainResponse:
    return MarketThemeReturnMLService(db).train_shadow()


@router.post("/market-themes/return-predictions/ml/predict-shadow", response_model=MarketThemeReturnPredictionResponse)
def predict_market_theme_return_ml_shadow(
    payload: MarketThemeReturnMLRequest,
    db: Session = Depends(get_db),
) -> MarketThemeReturnPredictionResponse:
    return MarketThemeReturnMLService(db).predict_shadow(payload.target_date)


@router.get("/market-themes/return-predictions/latest", response_model=MarketThemeReturnPredictionResponse)
def get_latest_market_theme_return_prediction(db: Session = Depends(get_db)) -> MarketThemeReturnPredictionResponse:
    return MarketThemeReturnPredictionService(db).latest()


@router.get("/market-themes/return-predictions", response_model=MarketThemeReturnPredictionResponse)
def get_market_theme_return_prediction(
    target_date: str = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
) -> MarketThemeReturnPredictionResponse:
    return MarketThemeReturnPredictionService(db).get(target_date)


@router.post("/market-themes/return-predictions/predict", response_model=MarketThemeReturnPredictionResponse)
def predict_market_theme_returns(
    payload: MarketThemeReturnPredictionRequest,
    db: Session = Depends(get_db),
) -> MarketThemeReturnPredictionResponse:
    # theme_group_id is intentionally a presentation filter; official storage always covers every active leaf theme.
    return MarketThemeReturnPredictionService(db).predict(payload.target_date)


@router.post("/market-themes/return-predictions/validate", response_model=MarketThemeReturnPredictionResponse)
def validate_market_theme_returns(
    payload: MarketThemeReturnValidationRequest,
    db: Session = Depends(get_db),
) -> MarketThemeReturnPredictionResponse:
    return MarketThemeReturnPredictionService(db).validate(payload.target_date)


@router.get("/market-themes", response_model=list[MarketThemeResponse])
def list_market_themes(
    is_active: int | None = Query(default=None),
    theme_type: str | None = Query(default=None),
    theme_level: str | None = Query(default=None),
    parent_theme_id: int | None = Query(default=None),
    is_supply_theme: int | None = Query(default=None),
    keyword: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[MarketThemeResponse]:
    return MarketThemeService(db).list_themes(
        is_active=is_active,
        theme_type=theme_type,
        theme_level=theme_level,
        parent_theme_id=parent_theme_id,
        is_supply_theme=is_supply_theme,
        keyword=keyword,
        limit=limit,
        offset=offset,
    )


@router.get("/market-themes/{theme_id}", response_model=MarketThemeResponse)
def get_market_theme(theme_id: int, db: Session = Depends(get_db)) -> MarketThemeResponse:
    return MarketThemeService(db).get_theme(theme_id)


@router.post("/market-themes", response_model=MarketThemeResponse)
def create_market_theme(payload: MarketThemeCreateRequest, db: Session = Depends(get_db)) -> MarketThemeResponse:
    result = MarketThemeService(db).create_theme(payload)
    invalidate_market_theme_flow_trend_cache()
    return result


@router.put("/market-themes/{theme_id}", response_model=MarketThemeResponse)
def update_market_theme(theme_id: int, payload: MarketThemeUpdateRequest, db: Session = Depends(get_db)) -> MarketThemeResponse:
    result = MarketThemeService(db).update_theme(theme_id, payload)
    invalidate_market_theme_flow_trend_cache()
    return result


@router.patch("/market-themes/{theme_id}/deactivate", response_model=MarketThemeResponse)
def deactivate_market_theme(theme_id: int, db: Session = Depends(get_db)) -> MarketThemeResponse:
    result = MarketThemeService(db).deactivate_theme(theme_id)
    invalidate_market_theme_flow_trend_cache()
    return result


@router.delete("/market-themes/{theme_id}", response_model=MarketThemeDeleteResponse)
def delete_market_theme(theme_id: int, db: Session = Depends(get_db)) -> MarketThemeDeleteResponse:
    result = MarketThemeService(db).delete_theme(theme_id)
    invalidate_market_theme_flow_trend_cache()
    return result


@router.get("/market-themes/{theme_id}/stocks", response_model=list[MarketThemeStockResponse])
def list_market_theme_stocks(theme_id: int, db: Session = Depends(get_db)) -> list[MarketThemeStockResponse]:
    return MarketThemeStockService(db).list_theme_stocks(theme_id)


@router.get(
    "/market-themes/{theme_id}/stocks/{stock_id}/supply-summary",
    response_model=MarketThemeStockSupplySummaryResponse,
)
def get_market_theme_stock_supply_summary(
    theme_id: int,
    stock_id: int,
    db: Session = Depends(get_db),
) -> MarketThemeStockSupplySummaryResponse:
    return MarketThemeStockService(db).get_supply_summary(theme_id, stock_id)


@router.post("/market-themes/{theme_id}/stocks", response_model=MarketThemeStockResponse)
def create_market_theme_stock(
    theme_id: int,
    payload: MarketThemeStockCreateRequest,
    db: Session = Depends(get_db),
) -> MarketThemeStockResponse:
    result = MarketThemeStockService(db).create_theme_stock(theme_id, payload)
    invalidate_market_theme_flow_trend_cache()
    return result


@router.patch("/market-themes/{theme_id}/stocks/{stock_id}/memo", response_model=MarketThemeStockResponse)
def update_market_theme_stock_memo(
    theme_id: int,
    stock_id: int,
    payload: MarketThemeStockMemoUpdateRequest,
    db: Session = Depends(get_db),
) -> MarketThemeStockResponse:
    return MarketThemeStockService(db).update_theme_stock_memo(theme_id, stock_id, payload)


@router.patch("/market-theme-stocks/{mapping_id}", response_model=MarketThemeStockResponse)
def update_market_theme_stock(
    mapping_id: int,
    payload: MarketThemeStockUpdateRequest,
    db: Session = Depends(get_db),
) -> MarketThemeStockResponse:
    result = MarketThemeStockService(db).update_theme_stock(mapping_id, payload)
    invalidate_market_theme_flow_trend_cache()
    return result


@router.patch("/market-theme-stocks/{mapping_id}/deactivate", response_model=MarketThemeStockResponse)
def deactivate_market_theme_stock(mapping_id: int, db: Session = Depends(get_db)) -> MarketThemeStockResponse:
    result = MarketThemeStockService(db).deactivate_theme_stock(mapping_id)
    invalidate_market_theme_flow_trend_cache()
    return result


@router.get("/market-themes/by-stock/{stock_code}", response_model=MarketThemeByStockResponse)
def list_market_themes_by_stock(stock_code: str, db: Session = Depends(get_db)) -> MarketThemeByStockResponse:
    return MarketThemeStockService(db).list_themes_by_stock_code(stock_code)


@router.get("/market-themes/stocks/{stock_code}/memos", response_model=MarketThemeStockMemoResponse)
def list_market_theme_stock_memos(stock_code: str, db: Session = Depends(get_db)) -> MarketThemeStockMemoResponse:
    return MarketThemeStockService(db).list_stock_memos(stock_code)
