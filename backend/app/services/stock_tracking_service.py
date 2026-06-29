from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
import re
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import PROJECT_ROOT, now_kst
from backend.app.repositories.stock_repository import StockRepository
from backend.app.services.stock_price_service import StockPriceService
from backend.app.utils.stock_code import normalize_stock_code
from backend.app.schemas.stock_tracking_schema import (
    CollectStockTrackingPricesRequest,
    CollectStockTrackingPricesResponse,
    CreateTrackingFromConditionResultsRequest,
    CreateTrackingFromConditionResultsResponse,
    RegisterTrackingItemsFromCandidatesRequest,
    RegisterTrackingItemsFromCandidatesResponse,
    StockTrackingBaseMetricSummary,
    StockTrackingChartResponse,
    StockTrackingGroupCreateRequest,
    StockTrackingGroupAnalysisListResponse,
    StockTrackingGroupAnalysisResponse,
    StockTrackingGroupAnalysisSample,
    StockTrackingGroupResponse,
    StockTrackingGroupUpdateRequest,
    StockTrackingImageListResponse,
    StockTrackingImageResponse,
    StockTrackingItemListResponse,
    StockTrackingItemResponse,
    UpdateStockTrackingReviewRequest,
)

ALLOWED_ITEM_STATUS = {"TRACKING", "SUCCESS", "FAIL", "HOLD", "EXCLUDED"}
FINAL_STATUSES = {"SUCCESS", "FAIL", "EXCLUDED"}
ALLOWED_PRICE_STATUS = {"NOT_COLLECTED", "COLLECTING", "LATEST", "PARTIAL", "STOPPED", "ERROR"}
ALLOWED_IMAGE_TYPES = {
    "BASE_DATE": "기준일 차트",
    "SUCCESS": "성공 근거",
    "FAIL": "실패 근거",
    "PULLBACK": "눌림 구간",
    "OVERHEAT": "과열 구간",
    "ENTRY_POINT": "진입 가능 구간",
    "ETC": "기타",
}
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/pjpeg", "image/webp"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024
UPLOAD_ROOT = PROJECT_ROOT / "backend" / "uploads"
BASE_METRIC_KEYS = [
    "close_vs_ma20_pct",
    "close_vs_ma60_pct",
    "recent_5d_return_pct",
    "trading_value_ratio_20",
    "ma60_slope_5d_pct",
    "high_vs_close_pct",
    "close_position_pct",
]



def _today() -> str:
    return now_kst()[:10]


def _normalize_text(value: str | None) -> str | None:
    text_value = (value or "").strip()
    return text_value or None


def _normalize_market_value(value: str | None) -> str | None:
    text_value = (value or "").strip()
    if not text_value or text_value == "-":
        return None
    upper_value = text_value.upper()
    if "KOSDAQ" in upper_value:
        return "KOSDAQ"
    if "KOSPI" in upper_value or upper_value in {"KRX", "K"}:
        return "KOSPI"
    return text_value[:20]


def _sanitize_filename(value: str) -> str:
    name = Path(value or "upload.png").name
    extension = Path(name).suffix.lower()
    stem = Path(name).stem
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._")
    return f"{safe_stem or 'upload'}{extension or '.png'}"


def _avg(values: list[float | int | None]) -> float | None:
    numbers = [float(value) for value in values if value is not None]
    if not numbers:
        return None
    return round(sum(numbers) / len(numbers), 4)


def _diff(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return round(left - right, 4)


def _return_pct(value: float | None, base_price: float | None) -> float | None:
    if value is None or base_price is None or base_price <= 0:
        return None
    return round(((value - base_price) / base_price) * 100, 4)


def _target_start_date(base_date: str) -> str:
    try:
        parsed = datetime.strptime(base_date, "%Y-%m-%d").date()
    except ValueError:
        parsed = datetime.now().date()
    return (parsed - timedelta(days=180)).isoformat()


class StockTrackingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _group_row(self, group_id: int) -> dict[str, object]:
        row = self.db.execute(
            text(
                """
                SELECT g.*,
                       COUNT(i.id) AS item_count,
                       SUM(CASE WHEN i.status = 'TRACKING' THEN 1 ELSE 0 END) AS tracking_count
                FROM stock_tracking_groups g
                LEFT JOIN stock_tracking_items i ON i.group_id = g.id
                WHERE g.id = :group_id
                GROUP BY g.id
                """
            ),
            {"group_id": group_id},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="종목트래킹 그룹을 찾을 수 없습니다.")
        return dict(row)

    @staticmethod
    def _to_group_response(row: dict[str, object]) -> StockTrackingGroupResponse:
        return StockTrackingGroupResponse(
            id=int(row["id"]),
            name=str(row["name"]),
            description=row.get("description"),
            success_rule_note=row.get("success_rule_note"),
            fail_rule_note=row.get("fail_rule_note"),
            observation_note=row.get("observation_note"),
            is_active=int(row.get("is_active") or 0),
            item_count=int(row.get("item_count") or 0),
            tracking_count=int(row.get("tracking_count") or 0),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def list_groups(self, active_only: bool = False) -> list[StockTrackingGroupResponse]:
        where = "WHERE g.is_active = 1" if active_only else ""
        rows = self.db.execute(
            text(
                f"""
                SELECT g.*,
                       COUNT(i.id) AS item_count,
                       SUM(CASE WHEN i.status = 'TRACKING' THEN 1 ELSE 0 END) AS tracking_count
                FROM stock_tracking_groups g
                LEFT JOIN stock_tracking_items i ON i.group_id = g.id
                {where}
                GROUP BY g.id
                ORDER BY g.is_active DESC, g.updated_at DESC, g.id DESC
                """
            )
        ).mappings().all()
        return [self._to_group_response(dict(row)) for row in rows]

    def create_group(self, payload: StockTrackingGroupCreateRequest) -> StockTrackingGroupResponse:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="그룹명을 입력해 주세요.")
        now = now_kst()
        result = self.db.execute(
            text(
                """
                INSERT INTO stock_tracking_groups
                (name, description, success_rule_note, fail_rule_note, observation_note, is_active, created_at, updated_at)
                VALUES (:name, :description, :success_rule_note, :fail_rule_note, :observation_note, :is_active, :created_at, :updated_at)
                """
            ),
            {
                "name": name,
                "description": _normalize_text(payload.description),
                "success_rule_note": _normalize_text(payload.success_rule_note),
                "fail_rule_note": _normalize_text(payload.fail_rule_note),
                "observation_note": _normalize_text(payload.observation_note),
                "is_active": 1 if payload.is_active else 0,
                "created_at": now,
                "updated_at": now,
            },
        )
        self.db.commit()
        return self._to_group_response(self._group_row(int(result.lastrowid)))

    def update_group(self, group_id: int, payload: StockTrackingGroupUpdateRequest) -> StockTrackingGroupResponse:
        self._group_row(group_id)
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="그룹명을 입력해 주세요.")
        self.db.execute(
            text(
                """
                UPDATE stock_tracking_groups
                SET name = :name,
                    description = :description,
                    success_rule_note = :success_rule_note,
                    fail_rule_note = :fail_rule_note,
                    observation_note = :observation_note,
                    is_active = :is_active,
                    updated_at = :updated_at
                WHERE id = :group_id
                """
            ),
            {
                "group_id": group_id,
                "name": name,
                "description": _normalize_text(payload.description),
                "success_rule_note": _normalize_text(payload.success_rule_note),
                "fail_rule_note": _normalize_text(payload.fail_rule_note),
                "observation_note": _normalize_text(payload.observation_note),
                "is_active": 1 if payload.is_active else 0,
                "updated_at": now_kst(),
            },
        )
        self.db.commit()
        return self._to_group_response(self._group_row(group_id))

    def delete_group(self, group_id: int) -> dict[str, object]:
        row = self._group_row(group_id)
        if int(row.get("item_count") or 0) > 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="연결된 트래킹 종목이 있는 그룹은 삭제할 수 없습니다.")
        self.db.execute(text("DELETE FROM stock_tracking_groups WHERE id = :group_id"), {"group_id": group_id})
        self.db.commit()
        return {"success": True, "group_id": group_id}

    @staticmethod
    def _to_item_response(row: dict[str, object]) -> StockTrackingItemResponse:
        return StockTrackingItemResponse(
            id=int(row["id"]),
            group_id=int(row["group_id"]),
            group_name=str(row["group_name"]),
            candidate_id=int(row["candidate_id"]) if row.get("candidate_id") is not None else None,
            condition_no=row.get("condition_no"),
            condition_name=row.get("condition_name"),
            stock_id=int(row["stock_id"]) if row.get("stock_id") is not None else None,
            stock_code=row.get("stock_code"),
            stock_name=row.get("stock_name"),
            detected_date=row.get("detected_date"),
            tracking_base_date=str(row["tracking_base_date"]),
            base_price=float(row["base_price"]) if row.get("base_price") is not None else None,
            base_change_rate=float(row["base_change_rate"]) if row.get("base_change_rate") is not None else None,
            base_volume=int(row["base_volume"]) if row.get("base_volume") is not None else None,
            base_trading_value=int(row["base_trading_value"]) if row.get("base_trading_value") is not None else None,
            status=str(row["status"]),
            review_date=row.get("review_date"),
            review_note=row.get("review_note"),
            price_status=str(row["price_status"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def _item_row(self, item_id: int) -> dict[str, object]:
        row = self.db.execute(
            text(
                """
                SELECT i.*, g.name AS group_name
                FROM stock_tracking_items i
                JOIN stock_tracking_groups g ON g.id = i.group_id
                WHERE i.id = :item_id
                """
            ),
            {"item_id": item_id},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="트래킹 종목을 찾을 수 없습니다.")
        return dict(row)

    def list_items(
        self,
        *,
        group_id: int | None = None,
        item_status: str | None = None,
        price_status: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        keyword: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> StockTrackingItemListResponse:
        clauses: list[str] = ["1 = 1"]
        params: dict[str, object] = {"limit": limit, "offset": offset}
        if group_id:
            clauses.append("i.group_id = :group_id")
            params["group_id"] = group_id
        if item_status:
            clauses.append("i.status = :status")
            params["status"] = item_status
        if price_status:
            clauses.append("i.price_status = :price_status")
            params["price_status"] = price_status
        if from_date:
            clauses.append("i.tracking_base_date >= :from_date")
            params["from_date"] = from_date
        if to_date:
            clauses.append("i.tracking_base_date <= :to_date")
            params["to_date"] = to_date
        if keyword:
            clauses.append("(i.stock_name LIKE :keyword OR i.stock_code LIKE :keyword OR i.condition_name LIKE :keyword)")
            params["keyword"] = f"%{keyword.strip()}%"
        where_sql = " AND ".join(clauses)
        total = self.db.execute(text(f"SELECT COUNT(*) FROM stock_tracking_items i WHERE {where_sql}"), params).scalar_one()
        rows = self.db.execute(
            text(
                f"""
                SELECT i.*, g.name AS group_name
                FROM stock_tracking_items i
                JOIN stock_tracking_groups g ON g.id = i.group_id
                WHERE {where_sql}
                ORDER BY i.tracking_base_date DESC, i.updated_at DESC, i.id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).mappings().all()
        return StockTrackingItemListResponse(items=[self._to_item_response(dict(row)) for row in rows], total=int(total or 0))

    def register_from_candidates(self, payload: RegisterTrackingItemsFromCandidatesRequest) -> RegisterTrackingItemsFromCandidatesResponse:
        group = self._group_row(payload.group_id)
        if int(group.get("is_active") or 0) != 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="비활성 그룹에는 등록할 수 없습니다.")
        candidate_ids = list(dict.fromkeys([int(v) for v in payload.candidate_ids if int(v) > 0]))
        if not candidate_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="등록할 후보 종목을 선택해 주세요.")
        now = now_kst()
        base_date = _today()
        created_ids: list[int] = []
        register_results: list[dict[str, object]] = []
        skipped_count = 0
        for candidate_id in candidate_ids:
            event = self.db.execute(
                text(
                    """
                    SELECT id, trade_date, stock_id, stock_code, stock_name, change_rate, trading_value,
                           condition_seq, condition_name
                    FROM market_trend_events
                    WHERE id = :candidate_id AND COALESCE(is_active, 1) = 1
                    LIMIT 1
                    """
                ),
                {"candidate_id": candidate_id},
            ).mappings().first()
            if not event:
                skipped_count += 1
                register_results.append({"candidate_id": candidate_id, "stock_code": None, "stock_name": None, "status": "SKIPPED", "message": "\uD6C4\uBCF4\uB97C \uCC3E\uC744 \uC218 \uC5C6\uC2B5\uB2C8\uB2E4."})
                continue
            duplicate = self.db.execute(
                text(
                    """
                    SELECT id
                    FROM stock_tracking_items
                    WHERE group_id = :group_id
                      AND (candidate_id = :candidate_id OR (candidate_id IS NULL AND stock_code = :stock_code AND tracking_base_date = :tracking_base_date))
                    LIMIT 1
                    """
                ),
                {
                    "group_id": payload.group_id,
                    "candidate_id": candidate_id,
                    "stock_code": event["stock_code"],
                    "tracking_base_date": base_date,
                },
            ).mappings().first()
            if duplicate:
                skipped_count += 1
                register_results.append({"candidate_id": candidate_id, "stock_code": event["stock_code"], "stock_name": event["stock_name"], "status": "SKIPPED", "message": "\uC774\uBBF8 \uD574\uB2F9 \uADF8\uB8F9\uC5D0 \uB4F1\uB85D\uB41C \uD6C4\uBCF4\uC785\uB2C8\uB2E4."})
                continue
            result = self.db.execute(
                text(
                    """
                    INSERT INTO stock_tracking_items
                    (group_id, candidate_id, condition_no, condition_name, stock_id, stock_code, stock_name,
                     detected_date, tracking_base_date, base_price, base_change_rate, base_volume, base_trading_value,
                     status, review_date, review_note, price_status, created_at, updated_at)
                    VALUES
                    (:group_id, :candidate_id, :condition_no, :condition_name, :stock_id, :stock_code, :stock_name,
                     :detected_date, :tracking_base_date, NULL, :base_change_rate, NULL, :base_trading_value,
                     'TRACKING', NULL, NULL, 'NOT_COLLECTED', :created_at, :updated_at)
                    """
                ),
                {
                    "group_id": payload.group_id,
                    "candidate_id": candidate_id,
                    "condition_no": event["condition_seq"],
                    "condition_name": event["condition_name"],
                    "stock_id": event["stock_id"],
                    "stock_code": event["stock_code"],
                    "stock_name": event["stock_name"],
                    "detected_date": event["trade_date"],
                    "tracking_base_date": base_date,
                    "base_change_rate": event["change_rate"],
                    "base_trading_value": event["trading_value"],
                    "created_at": now,
                    "updated_at": now,
                },
            )
            item_id = int(result.lastrowid)
            created_ids.append(item_id)
            register_results.append({"candidate_id": candidate_id, "stock_code": event["stock_code"], "stock_name": event["stock_name"], "status": "CREATED", "message": None})
            self.db.execute(
                text(
                    """
                    INSERT INTO price_collection_targets
                    (source_type, source_id, stock_id, stock_code, base_date, start_date, end_date, status,
                     last_collected_date, error_message, created_at, updated_at)
                    VALUES
                    ('STOCK_TRACKING', :source_id, :stock_id, :stock_code, :base_date, :start_date, NULL, 'ACTIVE',
                     NULL, NULL, :created_at, :updated_at)
                    """
                ),
                {
                    "source_id": item_id,
                    "stock_id": event["stock_id"],
                    "stock_code": event["stock_code"],
                    "base_date": base_date,
                    "start_date": _target_start_date(base_date),
                    "created_at": now,
                    "updated_at": now,
                },
            )
        self.db.commit()
        return RegisterTrackingItemsFromCandidatesResponse(
            success=True,
            requested_count=len(candidate_ids),
            created_count=len(created_ids),
            skipped_count=skipped_count,
            item_ids=created_ids,
            items=register_results,
            message=f"\uC885\uBAA9\uD2B8\uB798\uD0B9 \uB4F1\uB85D \uC644\uB8CC: \uC2E0\uADDC {len(created_ids)}\uAC74, \uC911\uBCF5 \uC81C\uC678 {skipped_count}\uAC74",
        )


    def register_from_condition_results(self, payload: CreateTrackingFromConditionResultsRequest) -> CreateTrackingFromConditionResultsResponse:
        group = self._group_row(payload.group_id)
        if int(group.get("is_active") or 0) != 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="비활성 그룹에는 등록할 수 없습니다.")
        base_date = (payload.detected_date or _today()).strip()[:10] or _today()
        normalized_items = []
        seen_codes: set[str] = set()
        for item in payload.items:
            code = normalize_stock_code(item.stock_code)
            if not code or code in seen_codes:
                continue
            seen_codes.add(code)
            normalized_items.append((code, item))
        if not normalized_items:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="종목트래킹에 등록할 조건검색 결과 종목을 선택해 주세요.")

        now = now_kst()
        created_ids: list[int] = []
        register_results: list[dict[str, object]] = []
        skipped_count = 0
        for stock_code, item in normalized_items:
            stock_name = _normalize_text(item.stock_name) or stock_code
            duplicate = self.db.execute(
                text(
                    """
                    SELECT id
                    FROM stock_tracking_items
                    WHERE group_id = :group_id
                      AND stock_code = :stock_code
                      AND tracking_base_date = :tracking_base_date
                    LIMIT 1
                    """
                ),
                {"group_id": payload.group_id, "stock_code": stock_code, "tracking_base_date": base_date},
            ).mappings().first()
            if duplicate:
                skipped_count += 1
                register_results.append({"stock_code": stock_code, "stock_name": stock_name, "status": "SKIPPED", "tracking_item_id": int(duplicate["id"]), "reason": "이미 같은 그룹/기준일로 등록된 종목입니다."})
                continue

            market = _normalize_market_value(item.market)
            stock_row = self.db.execute(text("SELECT id, stock_name, market FROM stocks WHERE stock_code = :stock_code LIMIT 1"), {"stock_code": stock_code}).mappings().first()
            if stock_row:
                stock_id = int(stock_row["id"])
                update_values: dict[str, object] = {"stock_id": stock_id, "updated_at": now}
                update_sets = ["updated_at = :updated_at"]
                if stock_name and stock_name != stock_code and stock_name != stock_row.get("stock_name"):
                    update_values["stock_name"] = stock_name
                    update_sets.append("stock_name = :stock_name")
                if market and not stock_row.get("market"):
                    update_values["market"] = market
                    update_sets.append("market = :market")
                if len(update_sets) > 1:
                    self.db.execute(text(f"UPDATE stocks SET {', '.join(update_sets)} WHERE id = :stock_id"), update_values)
            else:
                result = self.db.execute(
                    text(
                        """
                        INSERT INTO stocks
                        (stock_code, stock_name, market, sector, industry, isin_code, corp_name, corp_reg_no,
                         last_synced_at, source, security_type, is_active, created_at, updated_at)
                        VALUES
                        (:stock_code, :stock_name, :market, NULL, NULL, NULL, NULL, NULL,
                         NULL, 'condition_search', 'STOCK', 1, :created_at, :updated_at)
                        """
                    ),
                    {"stock_code": stock_code, "stock_name": stock_name, "market": market, "created_at": now, "updated_at": now},
                )
                stock_id = int(result.lastrowid)

            base_trading_value = int(item.trading_value) if item.trading_value is not None else None
            base_volume = int(item.volume) if item.volume is not None else None
            result = self.db.execute(
                text(
                    """
                    INSERT INTO stock_tracking_items
                    (group_id, candidate_id, condition_no, condition_name, stock_id, stock_code, stock_name,
                     detected_date, tracking_base_date, base_price, base_change_rate, base_volume, base_trading_value,
                     status, review_date, review_note, price_status, created_at, updated_at)
                    VALUES
                    (:group_id, NULL, :condition_no, :condition_name, :stock_id, :stock_code, :stock_name,
                     :detected_date, :tracking_base_date, :base_price, :base_change_rate, :base_volume, :base_trading_value,
                     'TRACKING', NULL, NULL, 'NOT_COLLECTED', :created_at, :updated_at)
                    """
                ),
                {
                    "group_id": payload.group_id,
                    "condition_no": _normalize_text(payload.condition_no),
                    "condition_name": _normalize_text(payload.condition_name),
                    "stock_id": stock_id,
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                    "detected_date": base_date,
                    "tracking_base_date": base_date,
                    "base_price": item.current_price,
                    "base_change_rate": item.change_rate,
                    "base_volume": base_volume,
                    "base_trading_value": base_trading_value,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            item_id = int(result.lastrowid)
            created_ids.append(item_id)
            register_results.append({"stock_code": stock_code, "stock_name": stock_name, "status": "CREATED", "tracking_item_id": item_id, "reason": None})
            self.db.execute(
                text(
                    """
                    INSERT INTO price_collection_targets
                    (source_type, source_id, stock_id, stock_code, base_date, start_date, end_date, status,
                     last_collected_date, error_message, created_at, updated_at)
                    VALUES
                    ('STOCK_TRACKING', :source_id, :stock_id, :stock_code, :base_date, :start_date, NULL, 'ACTIVE',
                     NULL, NULL, :created_at, :updated_at)
                    """
                ),
                {
                    "source_id": item_id,
                    "stock_id": stock_id,
                    "stock_code": stock_code,
                    "base_date": base_date,
                    "start_date": _target_start_date(base_date),
                    "created_at": now,
                    "updated_at": now,
                },
            )
        self.db.commit()
        return CreateTrackingFromConditionResultsResponse(
            success=True,
            requested_count=len(normalized_items),
            created_count=len(created_ids),
            skipped_count=skipped_count,
            item_ids=created_ids,
            items=register_results,
            message=f"\uc885\ubaa9\ud2b8\ub798\ud0b9 \ub4f1\ub85d \uc644\ub8cc: \uc2e0\uaddc {len(created_ids)}\uac74, \uc911\ubcf5 \uc81c\uc678 {skipped_count}\uac74",
        )


    @staticmethod
    def _image_url(image_path: str | None) -> str:
        if not image_path:
            return ""
        normalized = str(image_path).replace("\\", "/")
        prefix = "backend/uploads/"
        if normalized.startswith(prefix):
            return f"/uploads/{normalized[len(prefix):]}"
        if normalized.startswith("uploads/"):
            return f"/{normalized}"
        return f"/{normalized.lstrip('/')}"

    @staticmethod
    def _to_image_response(row: dict[str, object]) -> StockTrackingImageResponse:
        image_type = str(row.get("image_type") or "ETC")
        image_path = str(row.get("image_path") or "")
        return StockTrackingImageResponse(
            id=int(row["id"]),
            tracking_item_id=int(row["tracking_item_id"]),
            image_url=StockTrackingService._image_url(image_path),
            image_path=image_path,
            original_filename=row.get("original_filename"),
            image_type=image_type,
            image_type_label=ALLOWED_IMAGE_TYPES.get(image_type, image_type),
            caption=row.get("caption"),
            created_at=str(row["created_at"]),
            updated_at=str(row.get("updated_at") or row["created_at"]),
        )

    def _image_row(self, image_id: int) -> dict[str, object]:
        row = self.db.execute(
            text("SELECT * FROM stock_tracking_images WHERE id = :image_id"),
            {"image_id": image_id},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="첨부 이미지를 찾을 수 없습니다.")
        return dict(row)

    def list_images(self, item_id: int) -> StockTrackingImageListResponse:
        self._item_row(item_id)
        rows = self.db.execute(
            text("""
                SELECT *
                FROM stock_tracking_images
                WHERE tracking_item_id = :item_id
                ORDER BY id DESC
            """),
            {"item_id": item_id},
        ).mappings().all()
        return StockTrackingImageListResponse(items=[self._to_image_response(dict(row)) for row in rows])

    def upload_image(
        self,
        *,
        item_id: int,
        image_type: str,
        caption: str | None,
        original_filename: str,
        content_type: str | None,
        file_bytes: bytes,
    ) -> StockTrackingImageResponse:
        self._item_row(item_id)
        normalized_type = (image_type or "").strip().upper()
        if normalized_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="지원하지 않는 이미지 유형입니다.")
        if not file_bytes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="이미지 파일을 선택해 주세요.")
        if len(file_bytes) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="이미지 파일은 10MB 이하만 업로드할 수 있습니다.")
        safe_original = _sanitize_filename(original_filename or "upload.png")
        extension = Path(safe_original).suffix.lower()
        if extension not in ALLOWED_IMAGE_EXTENSIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="png, jpg, jpeg, webp 파일만 업로드할 수 있습니다.")
        if content_type and content_type not in ALLOWED_IMAGE_MIME_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="지원하지 않는 이미지 형식입니다.")

        item_dir = UPLOAD_ROOT / "stock_tracking" / str(item_id)
        item_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid4().hex}_{safe_original}"
        save_path = item_dir / filename
        save_path.write_bytes(file_bytes)
        relative_path = save_path.relative_to(PROJECT_ROOT).as_posix()
        now = now_kst()
        result = self.db.execute(
            text("""
                INSERT INTO stock_tracking_images
                (tracking_item_id, image_path, original_filename, image_type, caption, created_at, updated_at)
                VALUES (:tracking_item_id, :image_path, :original_filename, :image_type, :caption, :created_at, :updated_at)
            """),
            {
                "tracking_item_id": item_id,
                "image_path": relative_path,
                "original_filename": original_filename or safe_original,
                "image_type": normalized_type,
                "caption": _normalize_text(caption),
                "created_at": now,
                "updated_at": now,
            },
        )
        self.db.commit()
        return self._to_image_response(self._image_row(int(result.lastrowid)))

    @staticmethod
    def _delete_image_file(image_path: str | None) -> None:
        if not image_path:
            return
        try:
            target = (PROJECT_ROOT / str(image_path)).resolve()
            upload_root = UPLOAD_ROOT.resolve()
            if target.is_file() and str(target).startswith(str(upload_root)):
                target.unlink()
        except OSError:
            pass

    def delete_image(self, image_id: int) -> dict[str, object]:
        row = self._image_row(image_id)
        self.db.execute(text("DELETE FROM stock_tracking_images WHERE id = :image_id"), {"image_id": image_id})
        self.db.commit()
        self._delete_image_file(row.get("image_path"))
        return {"success": True, "image_id": image_id}

    @staticmethod
    def _calculate_tracking_return_from_rows(item: dict[str, object], rows: list[dict[str, object]]) -> dict[str, object] | None:
        base_date = str(item.get("tracking_base_date") or "")[:10]
        if not base_date or not rows:
            return None
        filtered = [row for row in rows if str(row.get("trade_date") or "")[:10] >= base_date]
        if not filtered:
            return None
        base_row = next((row for row in filtered if str(row.get("trade_date") or "")[:10] == base_date), None)
        first_close_row = next((row for row in filtered if row.get("close_price") is not None), None)
        base_price = None
        if base_row and base_row.get("close_price") is not None:
            base_price = float(base_row["close_price"])
        elif item.get("base_price") is not None:
            base_price = float(item["base_price"])
        elif first_close_row and first_close_row.get("close_price") is not None:
            base_price = float(first_close_row["close_price"])
        if base_price is None or base_price <= 0:
            return None
        close_values = [float(row["close_price"]) for row in filtered if row.get("close_price") is not None]
        high_values = [float(row["high_price"]) for row in filtered if row.get("high_price") is not None]
        low_values = [float(row["low_price"]) for row in filtered if row.get("low_price") is not None]
        if not close_values:
            return None
        return {
            "current_return_pct": _return_pct(close_values[-1], base_price),
            "max_return_pct": _return_pct(max(high_values), base_price) if high_values else None,
            "max_drawdown_pct": _return_pct(min(low_values), base_price) if low_values else None,
            "elapsed_trading_days": max(0, len(filtered) - 1),
        }

    @staticmethod
    def _ratio_pct(numerator: float | None, denominator: float | None) -> float | None:
        if numerator is None or denominator is None or denominator == 0:
            return None
        return round((numerator / denominator) * 100, 4)

    @staticmethod
    def _metric_average(rows: list[dict[str, object]], key: str) -> float | None:
        return _avg([row.get(key) for row in rows])

    @staticmethod
    def _metric_summary(rows: list[dict[str, object]]) -> StockTrackingBaseMetricSummary:
        return StockTrackingBaseMetricSummary(**{key: StockTrackingService._metric_average(rows, key) for key in BASE_METRIC_KEYS})

    @staticmethod
    def _metric_diff(success: StockTrackingBaseMetricSummary, fail: StockTrackingBaseMetricSummary) -> StockTrackingBaseMetricSummary:
        return StockTrackingBaseMetricSummary(**{key: _diff(getattr(success, key), getattr(fail, key)) for key in BASE_METRIC_KEYS})

    @staticmethod
    def _calculate_base_date_metrics(item: dict[str, object], rows: list[dict[str, object]]) -> dict[str, object] | None:
        base_date = str(item.get("tracking_base_date") or "")[:10]
        if not base_date or not rows:
            return None
        sorted_rows = sorted(rows, key=lambda row: str(row.get("trade_date") or ""))
        base_idx = next((idx for idx, row in enumerate(sorted_rows) if str(row.get("trade_date") or "")[:10] == base_date), None)
        if base_idx is None:
            base_idx = next((idx for idx, row in enumerate(sorted_rows) if str(row.get("trade_date") or "")[:10] >= base_date), None)
        if base_idx is None:
            return None
        close_values = [float(row["close_price"]) if row.get("close_price") is not None else None for row in sorted_rows]

        def value(row: dict[str, object], key: str) -> float | None:
            return float(row[key]) if row.get(key) is not None else None

        def ma_at(idx: int, window: int) -> float | None:
            row_key = f"ma{window}"
            if sorted_rows[idx].get(row_key) is not None:
                return float(sorted_rows[idx][row_key])
            return StockTrackingService._calc_ma(close_values, idx, window)

        base_row = sorted_rows[base_idx]
        base_close = value(base_row, "close_price")
        base_high = value(base_row, "high_price")
        base_low = value(base_row, "low_price")
        base_trading_value = value(base_row, "trading_value")
        ma20 = ma_at(base_idx, 20)
        ma60 = ma_at(base_idx, 60)
        ma60_5ago = ma_at(base_idx - 5, 60) if base_idx >= 5 else None
        close_5ago = close_values[base_idx - 5] if base_idx >= 5 else None
        previous_values = [value(row, "trading_value") for row in sorted_rows[max(0, base_idx - 20):base_idx]]
        previous_numbers = [number for number in previous_values if number is not None]
        avg_previous_trading_value = sum(previous_numbers) / len(previous_numbers) if len(previous_numbers) >= 10 else None
        metrics = {
            "close_vs_ma20_pct": StockTrackingService._ratio_pct(base_close - ma20, ma20) if base_close is not None and ma20 is not None else None,
            "close_vs_ma60_pct": StockTrackingService._ratio_pct(base_close - ma60, ma60) if base_close is not None and ma60 is not None else None,
            "recent_5d_return_pct": StockTrackingService._ratio_pct(base_close - close_5ago, close_5ago) if base_close is not None and close_5ago is not None else None,
            "trading_value_ratio_20": round(base_trading_value / avg_previous_trading_value, 4) if base_trading_value is not None and avg_previous_trading_value and avg_previous_trading_value > 0 else None,
            "ma60_slope_5d_pct": StockTrackingService._ratio_pct(ma60 - ma60_5ago, ma60_5ago) if ma60 is not None and ma60_5ago is not None else None,
            "high_vs_close_pct": StockTrackingService._ratio_pct(base_close - base_high, base_high) if base_close is not None and base_high is not None else None,
            "close_position_pct": StockTrackingService._ratio_pct(base_close - base_low, base_high - base_low) if base_close is not None and base_high is not None and base_low is not None and base_high != base_low else None,
        }
        return metrics if any(value is not None for value in metrics.values()) else None

    @staticmethod
    def _analysis_sample(item: dict[str, object], metrics: dict[str, object]) -> StockTrackingGroupAnalysisSample:
        return StockTrackingGroupAnalysisSample(
            item_id=int(item["id"]),
            stock_code=item.get("stock_code"),
            stock_name=item.get("stock_name"),
            tracking_base_date=str(item["tracking_base_date"]),
            review_date=item.get("review_date"),
            review_note=item.get("review_note"),
            current_return_pct=metrics.get("current_return_pct"),
            max_return_pct=metrics.get("max_return_pct"),
            max_drawdown_pct=metrics.get("max_drawdown_pct"),
            elapsed_trading_days=metrics.get("elapsed_trading_days"),
            close_vs_ma20_pct=metrics.get("close_vs_ma20_pct"),
            close_vs_ma60_pct=metrics.get("close_vs_ma60_pct"),
            recent_5d_return_pct=metrics.get("recent_5d_return_pct"),
            trading_value_ratio_20=metrics.get("trading_value_ratio_20"),
            ma60_slope_5d_pct=metrics.get("ma60_slope_5d_pct"),
            high_vs_close_pct=metrics.get("high_vs_close_pct"),
            close_position_pct=metrics.get("close_position_pct"),
        )

    def list_group_analysis(
        self,
        *,
        active_only: bool = True,
        group_id: int | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        min_completed_count: int | None = None,
    ) -> StockTrackingGroupAnalysisListResponse:
        clauses = ["1 = 1"]
        params: dict[str, object] = {}
        if active_only:
            clauses.append("g.is_active = 1")
        if group_id is not None:
            clauses.append("g.id = :group_id")
            params["group_id"] = group_id
        if from_date:
            clauses.append("i.tracking_base_date >= :from_date")
            params["from_date"] = from_date
        if to_date:
            clauses.append("i.tracking_base_date <= :to_date")
            params["to_date"] = to_date

        rows = self.db.execute(
            text(f"""
                SELECT g.id AS analysis_group_id, g.name AS group_name, i.*
                FROM stock_tracking_groups g
                LEFT JOIN stock_tracking_items i ON i.group_id = g.id
                WHERE {' AND '.join(clauses)}
                ORDER BY g.id ASC, i.tracking_base_date DESC, i.id DESC
            """),
            params,
        ).mappings().all()

        grouped: dict[int, dict[str, object]] = {}
        for raw in rows:
            row = dict(raw)
            gid = int(row.get("analysis_group_id") or row.get("group_id") or 0)
            group_name = str(row.get("group_name") or "-")
            grouped.setdefault(gid, {"group_id": gid, "group_name": group_name, "items": []})
            if gid > 0 and row.get("id") is not None:
                grouped[gid]["items"].append(row)

        stock_ids = sorted({int(item["stock_id"]) for group in grouped.values() for item in group["items"] if item.get("stock_id")})
        price_map: dict[int, list[dict[str, object]]] = {stock_id: [] for stock_id in stock_ids}
        if stock_ids:
            price_rows = self.db.execute(
                text(f"""
                    SELECT stock_id, trade_date, close_price, high_price, low_price, trading_value, ma20, ma60
                    FROM stock_daily_prices
                    WHERE stock_id IN ({','.join([f':stock_id_{idx}' for idx, _ in enumerate(stock_ids)])})
                    ORDER BY stock_id ASC, trade_date ASC
                """),
                {f"stock_id_{idx}": stock_id for idx, stock_id in enumerate(stock_ids)},
            ).mappings().all()
            for price_row in price_rows:
                price_map.setdefault(int(price_row["stock_id"]), []).append(dict(price_row))

        analysis_items: list[StockTrackingGroupAnalysisResponse] = []
        for group in grouped.values():
            items = list(group["items"])
            status_counts = {"TRACKING": 0, "HOLD": 0, "SUCCESS": 0, "FAIL": 0, "EXCLUDED": 0}
            metric_rows: list[tuple[dict[str, object], dict[str, object]]] = []
            base_metric_rows: list[dict[str, object]] = []
            success_base_metrics: list[dict[str, object]] = []
            fail_base_metrics: list[dict[str, object]] = []
            success_metrics: list[tuple[dict[str, object], dict[str, object]]] = []
            fail_metrics: list[tuple[dict[str, object], dict[str, object]]] = []
            for item in items:
                status_value = str(item.get("status") or "TRACKING").upper()
                if status_value in status_counts:
                    status_counts[status_value] += 1
                metrics = None
                base_metrics = None
                if item.get("stock_id"):
                    item_price_rows = price_map.get(int(item["stock_id"]), [])
                    metrics = self._calculate_tracking_return_from_rows(item, item_price_rows)
                    base_metrics = self._calculate_base_date_metrics(item, item_price_rows)
                if metrics:
                    if base_metrics:
                        metrics.update(base_metrics)
                    metric_rows.append((item, metrics))
                    if status_value == "SUCCESS":
                        success_metrics.append((item, metrics))
                    elif status_value == "FAIL":
                        fail_metrics.append((item, metrics))
                if base_metrics:
                    base_metric_rows.append(base_metrics)
                    if status_value == "SUCCESS":
                        success_base_metrics.append(base_metrics)
                    elif status_value == "FAIL":
                        fail_base_metrics.append(base_metrics)

            completed_count = status_counts["SUCCESS"] + status_counts["FAIL"]
            if min_completed_count is not None and completed_count < min_completed_count:
                continue
            success_rate = round((status_counts["SUCCESS"] / completed_count) * 100, 2) if completed_count > 0 else None
            metric_values = [metrics for _, metrics in metric_rows]
            success_values = [metrics for _, metrics in success_metrics]
            fail_values = [metrics for _, metrics in fail_metrics]
            success_avg_current = _avg([m.get("current_return_pct") for m in success_values])
            fail_avg_current = _avg([m.get("current_return_pct") for m in fail_values])
            success_avg_max = _avg([m.get("max_return_pct") for m in success_values])
            fail_avg_max = _avg([m.get("max_return_pct") for m in fail_values])
            success_avg_drawdown = _avg([m.get("max_drawdown_pct") for m in success_values])
            fail_avg_drawdown = _avg([m.get("max_drawdown_pct") for m in fail_values])
            success_base_avg = self._metric_summary(success_base_metrics)
            fail_base_avg = self._metric_summary(fail_base_metrics)
            success_samples = sorted(success_metrics, key=lambda row: row[1].get("max_return_pct") or -999999, reverse=True)[:10]
            fail_samples = sorted(fail_metrics, key=lambda row: row[1].get("max_drawdown_pct") if row[1].get("max_drawdown_pct") is not None else 999999)[:10]
            analysis_items.append(StockTrackingGroupAnalysisResponse(
                group_id=int(group["group_id"]),
                group_name=str(group["group_name"]),
                total_count=len(items),
                tracking_count=status_counts["TRACKING"],
                hold_count=status_counts["HOLD"],
                success_count=status_counts["SUCCESS"],
                fail_count=status_counts["FAIL"],
                excluded_count=status_counts["EXCLUDED"],
                completed_count=completed_count,
                success_rate=success_rate,
                return_calculated_count=len(metric_rows),
                base_metric_calculated_count=len(base_metric_rows),
                base_metric_summary={
                    "avg": self._metric_summary(base_metric_rows),
                    "success_avg": success_base_avg,
                    "fail_avg": fail_base_avg,
                    "diff": self._metric_diff(success_base_avg, fail_base_avg),
                },
                avg_current_return_pct=_avg([m.get("current_return_pct") for m in metric_values]),
                avg_max_return_pct=_avg([m.get("max_return_pct") for m in metric_values]),
                avg_max_drawdown_pct=_avg([m.get("max_drawdown_pct") for m in metric_values]),
                avg_elapsed_trading_days=_avg([m.get("elapsed_trading_days") for m in metric_values]),
                success_avg_current_return_pct=success_avg_current,
                success_avg_max_return_pct=success_avg_max,
                success_avg_max_drawdown_pct=success_avg_drawdown,
                success_avg_elapsed_trading_days=_avg([m.get("elapsed_trading_days") for m in success_values]),
                fail_avg_current_return_pct=fail_avg_current,
                fail_avg_max_return_pct=fail_avg_max,
                fail_avg_max_drawdown_pct=fail_avg_drawdown,
                fail_avg_elapsed_trading_days=_avg([m.get("elapsed_trading_days") for m in fail_values]),
                diff_avg_current_return_pct=_diff(success_avg_current, fail_avg_current),
                diff_avg_max_return_pct=_diff(success_avg_max, fail_avg_max),
                diff_avg_max_drawdown_pct=_diff(success_avg_drawdown, fail_avg_drawdown),
                success_samples=[self._analysis_sample(item, metrics) for item, metrics in success_samples],
                fail_samples=[self._analysis_sample(item, metrics) for item, metrics in fail_samples],
            ))

        analysis_items.sort(key=lambda row: (row.completed_count, row.success_rate or -1), reverse=True)
        return StockTrackingGroupAnalysisListResponse(items=analysis_items)

    def get_item(self, item_id: int) -> StockTrackingItemResponse:
        return self._to_item_response(self._item_row(item_id))

    def update_review(self, item_id: int, payload: UpdateStockTrackingReviewRequest) -> StockTrackingItemResponse:
        self._item_row(item_id)
        next_status = payload.status.strip().upper()
        if next_status not in ALLOWED_ITEM_STATUS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="지원하지 않는 상태입니다.")
        review_date = _today() if next_status in {"SUCCESS", "FAIL", "HOLD", "EXCLUDED"} else None
        price_status = "STOPPED" if next_status in FINAL_STATUSES else None
        now = now_kst()
        self.db.execute(
            text(
                """
                UPDATE stock_tracking_items
                SET status = :status,
                    review_date = :review_date,
                    review_note = :review_note,
                    price_status = COALESCE(:price_status, price_status),
                    updated_at = :updated_at
                WHERE id = :item_id
                """
            ),
            {
                "item_id": item_id,
                "status": next_status,
                "review_date": review_date,
                "review_note": _normalize_text(payload.review_note),
                "price_status": price_status,
                "updated_at": now,
            },
        )
        if next_status in FINAL_STATUSES:
            self.db.execute(
                text(
                    """
                    UPDATE price_collection_targets
                    SET end_date = :end_date, status = 'STOPPED', updated_at = :updated_at
                    WHERE source_type = 'STOCK_TRACKING' AND source_id = :item_id
                    """
                ),
                {"item_id": item_id, "end_date": review_date, "updated_at": now},
            )
        elif next_status == "HOLD":
            self.db.execute(
                text(
                    """
                    UPDATE price_collection_targets
                    SET status = 'ACTIVE', end_date = NULL, updated_at = :updated_at
                    WHERE source_type = 'STOCK_TRACKING' AND source_id = :item_id
                    """
                ),
                {"item_id": item_id, "updated_at": now},
            )
        self.db.commit()
        return self.get_item(item_id)


    @staticmethod
    def _parse_date(value: str | None) -> date:
        if not value:
            return datetime.now().date()
        try:
            return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
        except ValueError:
            return datetime.now().date()

    def _ensure_price_target(self, item: dict[str, object]) -> dict[str, object]:
        target = self.db.execute(
            text(
                """
                SELECT *
                FROM price_collection_targets
                WHERE source_type = 'STOCK_TRACKING' AND source_id = :item_id
                LIMIT 1
                """
            ),
            {"item_id": item["id"]},
        ).mappings().first()
        if target:
            return dict(target)
        now = now_kst()
        self.db.execute(
            text(
                """
                INSERT INTO price_collection_targets
                (source_type, source_id, stock_id, stock_code, base_date, start_date, end_date, status,
                 last_collected_date, error_message, created_at, updated_at)
                VALUES
                ('STOCK_TRACKING', :source_id, :stock_id, :stock_code, :base_date, :start_date, NULL, 'ACTIVE',
                 NULL, NULL, :created_at, :updated_at)
                """
            ),
            {
                "source_id": item["id"],
                "stock_id": item.get("stock_id"),
                "stock_code": item.get("stock_code"),
                "base_date": item.get("tracking_base_date"),
                "start_date": _target_start_date(str(item.get("tracking_base_date"))),
                "created_at": now,
                "updated_at": now,
            },
        )
        self.db.commit()
        return self._ensure_price_target(item)

    def _latest_price_date(self, stock_id: int) -> str | None:
        value = self.db.execute(
            text("SELECT MAX(trade_date) FROM stock_daily_prices WHERE stock_id = :stock_id"),
            {"stock_id": stock_id},
        ).scalar_one_or_none()
        return str(value) if value else None

    def collect_prices(self, payload: CollectStockTrackingPricesRequest) -> CollectStockTrackingPricesResponse:
        item_ids = list(dict.fromkeys([int(v) for v in payload.item_ids if int(v) > 0]))
        if not item_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="????? ??? ??? ??? ???.")
        price_service = StockPriceService(self.db)
        stock_repo = StockRepository(self.db)
        now = now_kst()
        results: list[dict[str, object]] = []
        success_count = 0
        partial_count = 0
        failed_count = 0
        for item_id in item_ids:
            try:
                item = self._item_row(item_id)
                if str(item.get("status")) not in {"TRACKING", "HOLD"}:
                    partial_count += 1
                    results.append({
                        "item_id": item_id,
                        "stock_code": item.get("stock_code"),
                        "stock_name": item.get("stock_name"),
                        "status": "SKIPPED",
                        "collected_count": 0,
                        "last_collected_date": self._latest_price_date(int(item["stock_id"])) if item.get("stock_id") else None,
                        "message": "?? ?? ??? ???? ?? ??? ????.",
                    })
                    continue
                target = self._ensure_price_target(item)
                if str(target.get("status") or "").upper() == "STOPPED":
                    partial_count += 1
                    results.append({
                        "item_id": item_id,
                        "stock_code": item.get("stock_code"),
                        "stock_name": item.get("stock_name"),
                        "status": "SKIPPED",
                        "collected_count": 0,
                        "last_collected_date": target.get("last_collected_date"),
                        "message": "?? ?? ?????.",
                    })
                    continue
                stock = stock_repo.get_by_id(int(item["stock_id"])) if item.get("stock_id") else None
                if not stock and item.get("stock_code"):
                    stock = stock_repo.get_by_code(str(item["stock_code"]))
                if not stock:
                    raise ValueError("?? ??? ??? ?? ? ????.")
                self.db.execute(text("UPDATE stock_tracking_items SET price_status = 'COLLECTING', updated_at = :updated_at WHERE id = :item_id"), {"item_id": item_id, "updated_at": now})
                self.db.execute(text("UPDATE price_collection_targets SET status = 'ACTIVE', error_message = NULL, updated_at = :updated_at WHERE source_type = 'STOCK_TRACKING' AND source_id = :item_id"), {"item_id": item_id, "updated_at": now})
                self.db.commit()
                start_date = self._parse_date(str(target.get("start_date") or _target_start_date(str(item.get("tracking_base_date")))))
                end_date = datetime.now().date()
                normalized, collected_count, saved_count = price_service._collect_and_upsert(stock=stock, source=payload.source, start_date=start_date, end_date=end_date)
                last_collected = self._latest_price_date(stock.id)
                next_status = "LATEST" if collected_count > 0 else "PARTIAL"
                target_status = "ACTIVE" if collected_count > 0 else "PARTIAL"
                if collected_count > 0:
                    success_count += 1
                    message = None
                else:
                    partial_count += 1
                    message = "?? ??? ??? ????? ????."
                self.db.execute(
                    text("UPDATE stock_tracking_items SET stock_code = COALESCE(:stock_code, stock_code), price_status = :price_status, updated_at = :updated_at WHERE id = :item_id"),
                    {"item_id": item_id, "stock_code": normalized, "price_status": next_status, "updated_at": now_kst()},
                )
                self.db.execute(
                    text("""
                    UPDATE price_collection_targets
                    SET stock_id = :stock_id, stock_code = :stock_code, last_collected_date = :last_collected_date,
                        status = :target_status, error_message = NULL, updated_at = :updated_at
                    WHERE source_type = 'STOCK_TRACKING' AND source_id = :item_id
                    """),
                    {"item_id": item_id, "stock_id": stock.id, "stock_code": normalized, "last_collected_date": last_collected, "target_status": target_status, "updated_at": now_kst()},
                )
                self.db.commit()
                results.append({
                    "item_id": item_id,
                    "stock_code": normalized,
                    "stock_name": stock.stock_name,
                    "status": "SUCCESS" if collected_count > 0 else "PARTIAL",
                    "collected_count": collected_count,
                    "last_collected_date": last_collected,
                    "message": message,
                })
            except Exception as exc:
                self.db.rollback()
                failed_count += 1
                try:
                    item = self._item_row(item_id)
                    self.db.execute(text("UPDATE stock_tracking_items SET price_status = 'ERROR', updated_at = :updated_at WHERE id = :item_id"), {"item_id": item_id, "updated_at": now_kst()})
                    self.db.execute(text("""
                        UPDATE price_collection_targets
                        SET status = 'ERROR', error_message = :error_message, updated_at = :updated_at
                        WHERE source_type = 'STOCK_TRACKING' AND source_id = :item_id
                    """), {"item_id": item_id, "error_message": str(exc)[:900], "updated_at": now_kst()})
                    self.db.commit()
                    stock_code = item.get("stock_code")
                    stock_name = item.get("stock_name")
                except Exception:
                    self.db.rollback()
                    stock_code = None
                    stock_name = None
                results.append({
                    "item_id": item_id,
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                    "status": "FAILED",
                    "collected_count": 0,
                    "last_collected_date": None,
                    "message": str(exc)[:900],
                })
        return CollectStockTrackingPricesResponse(
            requested_count=len(item_ids),
            success_count=success_count,
            partial_count=partial_count,
            failed_count=failed_count,
            items=results,
            message=f"???? ?? ??: ?? {success_count}?, ?? ?? {partial_count}?, ?? {failed_count}?",
        )

    @staticmethod
    def _calc_ma(values: list[float | None], idx: int, window: int) -> float | None:
        if idx + 1 < window:
            return None
        sub = values[idx - window + 1 : idx + 1]
        if any(v is None for v in sub):
            return None
        return round(sum(float(v) for v in sub) / window, 4)

    def get_chart(self, item_id: int) -> StockTrackingChartResponse:
        item = self._item_row(item_id)
        if not item.get("stock_id"):
            return StockTrackingChartResponse(
                item_id=item_id,
                stock_code=item.get("stock_code"),
                stock_name=item.get("stock_name"),
                tracking_base_date=str(item["tracking_base_date"]),
                review_date=item.get("review_date"),
                prices=[],
            )
        target = self._ensure_price_target(item)
        start_date = str(target.get("start_date") or _target_start_date(str(item.get("tracking_base_date"))))
        end_date = str(item.get("review_date") or datetime.now().date().isoformat())
        rows = self.db.execute(
            text(
                """
                SELECT trade_date, open_price, high_price, low_price, close_price, volume, trading_value,
                       ma5, ma10, ma20, ma60, ma120
                FROM stock_daily_prices
                WHERE stock_id = :stock_id AND trade_date >= :start_date AND trade_date <= :end_date
                ORDER BY trade_date ASC
                """
            ),
            {"stock_id": int(item["stock_id"]), "start_date": start_date, "end_date": end_date},
        ).mappings().all()
        close_values = [float(row["close_price"]) if row["close_price"] is not None else None for row in rows]
        prices = []
        for idx, row in enumerate(rows):
            prices.append({
                "date": str(row["trade_date"]),
                "open": float(row["open_price"]) if row["open_price"] is not None else None,
                "high": float(row["high_price"]) if row["high_price"] is not None else None,
                "low": float(row["low_price"]) if row["low_price"] is not None else None,
                "close": float(row["close_price"]) if row["close_price"] is not None else None,
                "volume": int(row["volume"]) if row["volume"] is not None else None,
                "trading_value": int(row["trading_value"]) if row["trading_value"] is not None else None,
                "ma5": float(row["ma5"]) if row["ma5"] is not None else self._calc_ma(close_values, idx, 5),
                "ma10": float(row["ma10"]) if row["ma10"] is not None else self._calc_ma(close_values, idx, 10),
                "ma20": float(row["ma20"]) if row["ma20"] is not None else self._calc_ma(close_values, idx, 20),
                "ma60": float(row["ma60"]) if row["ma60"] is not None else self._calc_ma(close_values, idx, 60),
                "ma120": float(row["ma120"]) if row["ma120"] is not None else self._calc_ma(close_values, idx, 120),
            })
        return StockTrackingChartResponse(
            item_id=item_id,
            stock_code=item.get("stock_code"),
            stock_name=item.get("stock_name"),
            tracking_base_date=str(item["tracking_base_date"]),
            review_date=item.get("review_date"),
            prices=prices,
        )

    def delete_item(self, item_id: int) -> dict[str, object]:
        self._item_row(item_id)
        image_rows = self.db.execute(
            text("SELECT image_path FROM stock_tracking_images WHERE tracking_item_id = :item_id"),
            {"item_id": item_id},
        ).mappings().all()
        self.db.execute(text("DELETE FROM stock_tracking_images WHERE tracking_item_id = :item_id"), {"item_id": item_id})
        self.db.execute(
            text("DELETE FROM price_collection_targets WHERE source_type = 'STOCK_TRACKING' AND source_id = :item_id"),
            {"item_id": item_id},
        )
        self.db.execute(text("DELETE FROM stock_tracking_items WHERE id = :item_id"), {"item_id": item_id})
        self.db.commit()
        for row in image_rows:
            self._delete_image_file(dict(row).get("image_path"))
        return {"success": True, "item_id": item_id}
