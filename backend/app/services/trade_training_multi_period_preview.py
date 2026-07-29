from __future__ import annotations

from datetime import datetime
import json
from time import perf_counter
from typing import Any

from fastapi import HTTPException, status

from backend.app.services.multi_period_technical_analysis import calculate_multi_period_analysis
from backend.app.services.technical_analysis_service import (
    MULTI_PERIOD_PREVIEW_CACHE,
    configuration_hash,
    normalize_configuration,
)


def build_multi_period_preview(service: Any, payload: Any) -> dict[str, Any]:
    started_at = perf_counter()
    session = service.repo.get_session(payload.training_session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="훈련 세션을 찾을 수 없습니다.",
        )
    if payload.stock_code and str(payload.stock_code) != str(session.get("stock_code") or ""):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="훈련 세션의 종목과 요청 종목이 일치하지 않습니다.",
        )

    session_as_of = str(session.get("current_date") or session.get("start_date") or "")
    requested_as_of = str(payload.as_of_date or session_as_of)
    as_of_date = min(requested_as_of, session_as_of)
    try:
        datetime.strptime(as_of_date, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="기준일 형식이 올바르지 않습니다.",
        ) from exc

    config = normalize_configuration(payload.configuration)
    options = service._parse_options(session)
    query_started = perf_counter()
    rows = service.repo.list_prices_through(
        stock_id=int(options.get("stock_id") or 0),
        source=str(options.get("source") or ""),
        end_date=as_of_date,
        limit=5_000,
    )
    training_start_date = str(session.get("start_date") or "")
    rows = [
        row for row in rows
        if training_start_date <= str(row.get("trade_date") or "") <= as_of_date
    ]
    query_ms = (perf_counter() - query_started) * 1000
    latest_date = str(rows[-1]["trade_date"]) if rows else ""
    cache_key = "|".join((
        "multi-period",
        str(payload.training_session_id),
        str(session.get("stock_code") or ""),
        as_of_date,
        str(payload.selected_period).upper(),
        configuration_hash(config),
        latest_date,
    ))
    cached = MULTI_PERIOD_PREVIEW_CACHE.get(cache_key)
    if cached is not None:
        cached["performance"] = {
            **cached.get("performance", {}),
            "cache_hit": True,
            "queried_row_count": len(rows),
            "query_ms": round(query_ms, 3),
            "calculation_ms": 0.0,
            "total_ms": round((perf_counter() - started_at) * 1000, 3),
        }
        return cached

    calculation_started = perf_counter()
    result = calculate_multi_period_analysis(
        rows,
        as_of_date=as_of_date,
        selected_period=payload.selected_period,
        configuration=config,
    )
    calculation_ms = (perf_counter() - calculation_started) * 1000
    calculation_parts = result.pop("_calculation_performance", {})
    result["performance"] = {
        "cache_hit": False,
        "queried_row_count": len(rows),
        "query_ms": round(query_ms, 3),
        **calculation_parts,
        "calculation_ms": round(calculation_ms, 3),
        "total_ms": round((perf_counter() - started_at) * 1000, 3),
    }
    result["performance"]["payload_bytes"] = len(
        json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    MULTI_PERIOD_PREVIEW_CACHE.put(cache_key, result)
    return result
