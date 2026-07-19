from __future__ import annotations

import time
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.services.market_index_service import MarketIndexService
from backend.app.services.market_indicator_service import MarketIndicatorService


class MarketDataCollectionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def collect(self, payload: Any) -> dict[str, Any]:
        mode = str(getattr(payload, "mode", "SELECTED") or "SELECTED").upper()
        if mode not in {"SELECTED", "BACKFILL", "INCREMENTAL_ALL"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="mode must be SELECTED, BACKFILL, or INCREMENTAL_ALL")
        targets = self._targets(mode, getattr(payload, "items", None))
        if mode in {"SELECTED", "BACKFILL"} and not targets:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="items are required for selected collection modes")
        start_date = getattr(payload, "start_date", None)
        end_date = getattr(payload, "end_date", None)

        started = time.perf_counter()
        run_id = self._create_run(mode, len(targets), getattr(payload, "triggered_by", None))
        results: list[dict[str, Any]] = []
        for target in targets:
            item_started = time.perf_counter()
            result: dict[str, Any]
            try:
                if target["item_type"] == "INDEX":
                    result = self._collect_index(target["item_code"])
                else:
                    result = self._collect_indicator(target["item_code"], skip_error_status=(mode == "INCREMENTAL_ALL"), start_date=start_date, end_date=end_date)
            except Exception as exc:  # noqa: BLE001 - isolate item failures.
                result = {
                    "item_type": target["item_type"],
                    "item_code": target["item_code"],
                    "status": "ERROR",
                    "error_type": exc.__class__.__name__,
                    "error_message": str(exc)[:500],
                    "failed_count": 1,
                }
            result["elapsed_ms"] = int((time.perf_counter() - item_started) * 1000)
            self._insert_run_item(run_id, result)
            self._update_policy(target["item_type"], target["item_code"], result)
            results.append(result)

        totals = self._summarize(results)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        final_status = "SUCCESS" if totals["failed_count"] == 0 and totals["skipped_count"] == 0 else "PARTIAL_SUCCESS"
        if totals["failed_count"] == len(results) and results:
            final_status = "FAILED"
        self._finish_run(run_id, final_status, totals, elapsed_ms)
        return {
            "run_id": run_id,
            "run_type": mode,
            "status": final_status,
            "target_count": len(targets),
            "elapsed_ms": elapsed_ms,
            "message": self._message(mode, totals, elapsed_ms),
            "results": results,
            **totals,
        }

    def list_runs(self, *, limit: int = 30) -> dict[str, Any]:
        rows = self.db.execute(
            text("SELECT * FROM market_data_collection_runs ORDER BY id DESC LIMIT :limit"),
            {"limit": limit},
        ).mappings().all()
        return {"items": [dict(row) for row in rows]}

    def get_run(self, run_id: int) -> dict[str, Any]:
        row = self.db.execute(text("SELECT * FROM market_data_collection_runs WHERE id = :id"), {"id": run_id}).mappings().first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="collection run not found")
        return dict(row)

    def list_run_items(self, run_id: int) -> dict[str, Any]:
        rows = self.db.execute(
            text("SELECT * FROM market_data_collection_run_items WHERE run_id = :run_id ORDER BY id"),
            {"run_id": run_id},
        ).mappings().all()
        return {"items": [dict(row) for row in rows]}

    def _targets(self, mode: str, items: Any) -> list[dict[str, str]]:
        if mode in {"SELECTED", "BACKFILL"}:
            return [
                {"item_type": str(item.item_type).upper(), "item_code": str(item.item_code).upper()}
                for item in (items or [])
                if getattr(item, "item_type", None) and getattr(item, "item_code", None)
            ]
        index_rows = self.db.execute(
            text(
                """
                SELECT 'INDEX' AS item_type, index_code AS item_code
                FROM market_indexes
                WHERE is_active = 1 AND collection_status NOT IN ('ERROR', 'CUSTOM_INDEX_REQUIRED', 'NO_OFFICIAL_INDEX', 'EXCLUDED')
                """
            )
        ).mappings().all()
        indicator_rows = self.db.execute(
            text(
                """
                SELECT 'INDICATOR' AS item_type, indicator_code AS item_code
                FROM market_indicators
                WHERE is_active = 1 AND collection_status <> 'ERROR'
                """
            )
        ).mappings().all()
        return [dict(row) for row in [*index_rows, *indicator_rows]]

    def _collect_index(self, code: str) -> dict[str, Any]:
        response = MarketIndexService(self.db).collect(index_codes=[code], start_date=None, end_date=None)
        item = response["results"][0] if response.get("results") else {}
        status_value = str(item.get("status") or "ERROR").upper()
        received_count = int(item.get("collected_count") or 0)
        saved_count = int(item.get("saved_count") or 0)
        return {
            "item_type": "INDEX",
            "item_code": code,
            "provider_code": "KIWOOM_REST",
            "status": "LATEST" if status_value == "LATEST" else status_value,
            "requested_from": item.get("from_date"),
            "requested_to": item.get("to_date"),
            "received_count": received_count,
            "inserted_count": saved_count,
            "updated_count": 0,
            "unchanged_count": max(received_count - saved_count, 0),
            "error_message": item.get("error_message"),
        }

    def _collect_indicator(self, code: str, *, skip_error_status: bool, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        response = MarketIndicatorService(self.db).collect_indicator([code], skip_error_status=skip_error_status, start_date=start_date, end_date=end_date)
        item = response["results"][0] if response.get("results") else {}
        return {
            "item_type": "INDICATOR",
            "item_code": code,
            "provider_code": self._provider_for_indicator(code),
            "status": str(item.get("status") or "ERROR").upper(),
            "requested_from": item.get("requested_from"),
            "requested_to": item.get("requested_to"),
            "received_count": int(item.get("received_count") or 0),
            "inserted_count": int(item.get("inserted_count") or 0),
            "updated_count": int(item.get("updated_count") or 0),
            "unchanged_count": int(item.get("unchanged_count") or 0),
            "skipped_count": 1 if str(item.get("status") or "").upper() == "SKIPPED" else 0,
            "failed_count": 1 if str(item.get("status") or "").upper() == "ERROR" else 0,
            "error_message": item.get("message") if str(item.get("status") or "").upper() in {"ERROR", "WAITING", "SKIPPED"} else None,
        }

    def _provider_for_indicator(self, code: str) -> str | None:
        return self.db.execute(
            text(
                """
                SELECT provider
                FROM market_indicator_provider_mappings
                WHERE indicator_code = :code AND is_enabled = 1 AND is_verified = 1
                ORDER BY CASE provider WHEN 'FRED' THEN 1 WHEN 'BOK_ECOS' THEN 2 WHEN 'KOSIS' THEN 3 WHEN 'DERIVED' THEN 4 ELSE 9 END
                LIMIT 1
                """
            ),
            {"code": code},
        ).scalar()

    def _create_run(self, mode: str, target_count: int, triggered_by: str | None) -> int:
        row = self.db.execute(
            text(
                """
                INSERT INTO market_data_collection_runs (run_type, status, target_count, triggered_by)
                VALUES (:run_type, 'RUNNING', :target_count, :triggered_by)
                RETURNING id
                """
            ),
            {"run_type": mode, "target_count": target_count, "triggered_by": triggered_by},
        ).first()
        self.db.commit()
        return int(row[0])

    def _insert_run_item(self, run_id: int, item: dict[str, Any]) -> None:
        self.db.execute(
            text(
                """
                INSERT INTO market_data_collection_run_items
                (run_id, item_type, item_code, provider_code, status, requested_from, requested_to, received_count,
                 inserted_count, updated_count, unchanged_count, error_type, error_message, elapsed_ms)
                VALUES (:run_id, :item_type, :item_code, :provider_code, :status, :requested_from, :requested_to, :received_count,
                        :inserted_count, :updated_count, :unchanged_count, :error_type, :error_message, :elapsed_ms)
                """
            ),
            {
                "run_id": run_id,
                "item_type": item.get("item_type"),
                "item_code": item.get("item_code"),
                "provider_code": item.get("provider_code"),
                "status": item.get("status"),
                "requested_from": item.get("requested_from"),
                "requested_to": item.get("requested_to"),
                "received_count": item.get("received_count") or 0,
                "inserted_count": item.get("inserted_count") or 0,
                "updated_count": item.get("updated_count") or 0,
                "unchanged_count": item.get("unchanged_count") or 0,
                "error_type": item.get("error_type"),
                "error_message": item.get("error_message"),
                "elapsed_ms": item.get("elapsed_ms") or 0,
            },
        )
        self.db.commit()

    def _update_policy(self, item_type: str, item_code: str, result: dict[str, Any]) -> None:
        ok = str(result.get("status") or "").upper() in {"SUCCESS", "LATEST", "UNCHANGED", "NEW"}
        self.db.execute(
            text(
                """
                UPDATE market_data_collection_policies
                SET last_attempt_at = CURRENT_TIMESTAMP,
                    last_success_at = CASE WHEN :ok = 1 THEN CURRENT_TIMESTAMP ELSE last_success_at END,
                    last_status = :status,
                    last_error_type = :error_type,
                    last_error_message = :error_message,
                    updated_at = CURRENT_TIMESTAMP
                WHERE item_type = :item_type AND item_code = :item_code
                """
            ),
            {
                "item_type": item_type,
                "item_code": item_code,
                "ok": 1 if ok else 0,
                "status": result.get("status"),
                "error_type": result.get("error_type"),
                "error_message": result.get("error_message"),
            },
        )
        self.db.commit()

    def _finish_run(self, run_id: int, status_value: str, totals: dict[str, int], elapsed_ms: int) -> None:
        self.db.execute(
            text(
                """
                UPDATE market_data_collection_runs
                SET status = :status,
                    finished_at = CURRENT_TIMESTAMP,
                    success_count = :success_count,
                    inserted_count = :inserted_count,
                    updated_count = :updated_count,
                    unchanged_count = :unchanged_count,
                    skipped_count = :skipped_count,
                    failed_count = :failed_count,
                    elapsed_ms = :elapsed_ms,
                    error_summary = :error_summary
                WHERE id = :run_id
                """
            ),
            {"run_id": run_id, "status": status_value, "elapsed_ms": elapsed_ms, "error_summary": None, **totals},
        )
        self.db.commit()

    @staticmethod
    def _summarize(results: list[dict[str, Any]]) -> dict[str, int]:
        return {
            "success_count": sum(1 for item in results if str(item.get("status") or "").upper() in {"SUCCESS", "LATEST"}),
            "inserted_count": sum(int(item.get("inserted_count") or 0) for item in results),
            "updated_count": sum(int(item.get("updated_count") or 0) for item in results),
            "unchanged_count": sum(int(item.get("unchanged_count") or 0) for item in results),
            "skipped_count": sum(int(item.get("skipped_count") or 0) for item in results),
            "failed_count": sum(1 for item in results if str(item.get("status") or "").upper() == "ERROR"),
        }

    @staticmethod
    def _message(mode: str, totals: dict[str, int], elapsed_ms: int) -> str:
        seconds = round(elapsed_ms / 1000, 1)
        return (
            f"{mode} collection finished: success {totals['success_count']}, "
            f"inserted {totals['inserted_count']}, updated {totals['updated_count']}, "
            f"unchanged {totals['unchanged_count']}, skipped {totals['skipped_count']}, "
            f"errors {totals['failed_count']}, {seconds}s."
        )
