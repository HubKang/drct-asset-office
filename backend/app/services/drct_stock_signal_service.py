from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.entities.chart_marker import ChartMarker
from backend.app.entities.drct_stock_signal import DrctSignalSearch, DrctSignalSearchMarkerLink, DrctSignalSearchRule, DrctSignalSearchVersion
from backend.app.services.drct_rule_engine import DrctRuleValidator
from backend.app.schemas.drct_stock_signal_schema import (
    DrctSignalMarkerLinksPut,
    DrctSignalSearchCreate,
    DrctSignalSearchPatch,
    DrctSignalVersionCreate,
)
from backend.app.services.drct_stock_signal_defaults import INITIAL_DRCT_SIGNAL_SEARCHES


class DrctStockSignalService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _clean(value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    def _get_search(self, search_id: int) -> DrctSignalSearch:
        row = self.db.get(DrctSignalSearch, search_id)
        if row is None:
            raise HTTPException(404, "검색식을 찾을 수 없습니다.")
        return row

    def _current_version(self, search_id: int) -> DrctSignalSearchVersion:
        row = self.db.scalar(select(DrctSignalSearchVersion).where(
            DrctSignalSearchVersion.search_id == search_id,
            DrctSignalSearchVersion.is_current.is_(True),
        ))
        if row is None:
            raise HTTPException(500, "현재 검색식 버전을 찾을 수 없습니다.")
        return row

    def training_summary(self, search_id: int) -> dict[str, Any]:
        self._get_search(search_id)
        row = self.db.execute(text("""
            SELECT COUNT(DISTINCT link.marker_definition_id) AS linked_marker_count,
                   COUNT(event.id) AS total_case_count,
                   SUM(CASE WHEN event.review_result IN ('S','SUCCESS') THEN 1 ELSE 0 END) AS success_count,
                   SUM(CASE WHEN event.review_result IN ('F','FAILURE') THEN 1 ELSE 0 END) AS failure_count,
                   SUM(CASE WHEN event.id IS NOT NULL AND event.review_result IS NULL THEN 1 ELSE 0 END) AS undecided_count,
                   MAX(event.marker_date) AS latest_case_date
            FROM drct_signal_search_marker_links link
            LEFT JOIN chart_marker_events event ON event.marker_id=link.marker_definition_id
            WHERE link.search_id=:search_id
        """), {"search_id": search_id}).mappings().one()
        return {
            "linked_marker_count": int(row["linked_marker_count"] or 0),
            "total_case_count": int(row["total_case_count"] or 0),
            "success_count": int(row["success_count"] or 0),
            "failure_count": int(row["failure_count"] or 0),
            "undecided_count": int(row["undecided_count"] or 0),
            "latest_case_date": str(row["latest_case_date"])[:10] if row["latest_case_date"] else None,
        }

    def _version_dict(self, row: DrctSignalSearchVersion) -> dict[str, Any]:
        rule_row = self.db.scalar(select(DrctSignalSearchRule).where(DrctSignalSearchRule.search_version_id == row.id))
        structured_rule = None
        if rule_row is not None:
            rule_payload = json.loads(rule_row.rule_json)
            validation = DrctRuleValidator.validate(rule_payload)
            structured_rule = {
                "id": rule_row.id,
                "search_version_id": rule_row.search_version_id,
                "schema_version": rule_row.schema_version,
                "validation_status": rule_row.validation_status,
                "rule": rule_payload,
                "validation_errors": validation.errors,
                "required_lookback": validation.required_lookback,
                "created_at": rule_row.created_at,
            }
        return {
            "id": row.id, "search_id": row.search_id, "version_no": row.version_no,
            "hts_reference_conditions": row.hts_reference_conditions,
            "hts_condition_expression": row.hts_condition_expression,
            "drct_rule_text": row.drct_rule_text, "change_note": row.change_note,
            "is_current": bool(row.is_current), "created_at": row.created_at,
            "structured_rule": structured_rule,
        }

    def _base_dict(self, row: DrctSignalSearch) -> dict[str, Any]:
        current = self._current_version(row.id)
        return {
            "id": row.id, "search_key": row.search_key, "name": row.name,
            "description": row.description, "lifecycle_status": row.lifecycle_status,
            "display_order": row.display_order, "is_active": bool(row.is_active),
            "current_version_no": current.version_no,
            "training_summary": self.training_summary(row.id),
            "created_at": row.created_at, "updated_at": row.updated_at,
        }

    def list_searches(self, include_inactive: bool = True) -> list[dict[str, Any]]:
        statement = select(DrctSignalSearch)
        if not include_inactive:
            statement = statement.where(DrctSignalSearch.is_active.is_(True))
        rows = self.db.scalars(statement.order_by(DrctSignalSearch.display_order, DrctSignalSearch.id)).all()
        return [self._base_dict(row) for row in rows]

    def marker_links(self, search_id: int) -> list[dict[str, Any]]:
        self._get_search(search_id)
        rows = self.db.execute(text("""
            SELECT link.id, marker.id marker_definition_id, marker.name marker_name,
                   marker.description marker_description, marker.symbol marker_symbol,
                   group_row.id marker_group_id, group_row.name marker_group_name, group_row.color group_color
            FROM drct_signal_search_marker_links link
            JOIN chart_markers marker ON marker.id=link.marker_definition_id
            JOIN chart_marker_groups group_row ON group_row.id=marker.marker_group_id
            WHERE link.search_id=:search_id
            ORDER BY group_row.sort_order, group_row.name, marker.sort_order, marker.name
        """), {"search_id": search_id}).mappings().all()
        return [dict(row) for row in rows]

    def get_search(self, search_id: int) -> dict[str, Any]:
        row = self._get_search(search_id)
        current = self._current_version(search_id)
        return {**self._base_dict(row), "current_version": self._version_dict(current), "marker_links": self.marker_links(search_id)}

    def create_search(self, payload: DrctSignalSearchCreate) -> dict[str, Any]:
        name = payload.name.strip()
        search_key_base = re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_") or "CUSTOM"
        search_key = f"USER_{search_key_base}"
        suffix = 2
        while self.db.scalar(select(DrctSignalSearch.id).where(DrctSignalSearch.search_key == search_key)):
            search_key = f"USER_{search_key_base}_{suffix}"
            suffix += 1
        next_order = int(self.db.scalar(select(func.coalesce(func.max(DrctSignalSearch.display_order), 0))) or 0) + 10
        row = DrctSignalSearch(
            search_key=search_key, name=name, description=self._clean(payload.description),
            lifecycle_status="REFERENCE", display_order=next_order, is_active=True,
        )
        try:
            self.db.add(row)
            self.db.flush()
            self.db.add(DrctSignalSearchVersion(
                search_id=row.id, version_no=1,
                hts_reference_conditions=payload.hts_reference_conditions,
                hts_condition_expression=payload.hts_condition_expression,
                drct_rule_text=None, change_note=self._clean(payload.change_note), is_current=True,
            ))
            self.db.commit()
            self.db.refresh(row)
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(409, "같은 이름의 검색식이 이미 있습니다.") from exc
        return self.get_search(row.id)

    def update_search(self, search_id: int, payload: DrctSignalSearchPatch) -> dict[str, Any]:
        row = self._get_search(search_id)
        values = payload.model_dump(exclude_unset=True)
        if "name" in values:
            values["name"] = values["name"].strip()
        if "description" in values:
            values["description"] = self._clean(values["description"])
        if values.get("is_active") is False:
            values["lifecycle_status"] = "INACTIVE"
        if values.get("is_active") is True and values.get("lifecycle_status") == "INACTIVE":
            values["lifecycle_status"] = "REFERENCE"
        for key, value in values.items():
            setattr(row, key, value)
        try:
            self.db.commit()
            self.db.refresh(row)
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(409, "같은 이름의 검색식이 이미 있습니다.") from exc
        return self.get_search(search_id)

    def list_versions(self, search_id: int) -> list[dict[str, Any]]:
        self._get_search(search_id)
        rows = self.db.scalars(select(DrctSignalSearchVersion).where(
            DrctSignalSearchVersion.search_id == search_id,
        ).order_by(DrctSignalSearchVersion.version_no.desc())).all()
        return [self._version_dict(row) for row in rows]

    def create_version(self, search_id: int, payload: DrctSignalVersionCreate) -> dict[str, Any]:
        search = self._get_search(search_id)
        current = self._current_version(search_id)
        next_no = current.version_no + 1
        try:
            self.db.execute(text("""
                UPDATE drct_signal_search_versions SET is_current=0
                WHERE search_id=:search_id AND is_current=1
            """), {"search_id": search_id})
            row = DrctSignalSearchVersion(
                search_id=search_id, version_no=next_no,
                hts_reference_conditions=payload.hts_reference_conditions,
                hts_condition_expression=payload.hts_condition_expression,
                drct_rule_text=self._clean(payload.drct_rule_text),
                change_note=payload.change_note.strip(), is_current=True,
            )
            self.db.add(row)
            search.updated_at = datetime.now()
            self.db.commit()
            self.db.refresh(row)
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(409, "검색식 버전을 생성하지 못했습니다. 다시 시도해 주세요.") from exc
        return self._version_dict(row)

    def replace_marker_links(self, search_id: int, payload: DrctSignalMarkerLinksPut) -> list[dict[str, Any]]:
        self._get_search(search_id)
        marker_ids = list(dict.fromkeys(payload.marker_definition_ids))
        if marker_ids:
            markers = self.db.scalars(select(ChartMarker).where(ChartMarker.id.in_(marker_ids))).all()
            found = {marker.id for marker in markers}
            if found != set(marker_ids):
                raise HTTPException(404, "존재하지 않는 차트마커가 포함되어 있습니다.")
            if any(not marker.is_active for marker in markers):
                raise HTTPException(400, "활성 차트마커만 연결할 수 있습니다.")
        self.db.execute(text("DELETE FROM drct_signal_search_marker_links WHERE search_id=:search_id"), {"search_id": search_id})
        self.db.add_all([
            DrctSignalSearchMarkerLink(search_id=search_id, marker_definition_id=marker_id)
            for marker_id in marker_ids
        ])
        self.db.commit()
        return self.marker_links(search_id)

    def marker_options(self) -> dict[str, Any]:
        rows = self.db.execute(text("""
            SELECT group_row.id group_id, group_row.name group_name, group_row.color,
                   marker.id, marker.name, marker.description, marker.symbol, marker.is_active
            FROM chart_marker_groups group_row
            JOIN chart_markers marker ON marker.marker_group_id=group_row.id
            WHERE group_row.is_active=1 AND marker.is_active=1
            ORDER BY group_row.sort_order, group_row.name, marker.sort_order, marker.name
        """)).mappings().all()
        groups: dict[int, dict[str, Any]] = {}
        for row in rows:
            group = groups.setdefault(int(row["group_id"]), {
                "id": int(row["group_id"]), "name": row["group_name"], "color": row["color"], "markers": [],
            })
            group["markers"].append({
                "id": int(row["id"]), "name": row["name"], "description": row["description"],
                "symbol": row["symbol"], "is_active": bool(row["is_active"]),
            })
        return {"items": list(groups.values())}

    def seed_defaults(self) -> int:
        created = 0
        for default in INITIAL_DRCT_SIGNAL_SEARCHES:
            exists = self.db.scalar(select(DrctSignalSearch).where(
                (DrctSignalSearch.search_key == default["search_key"]) | (DrctSignalSearch.name == default["name"])
            ))
            if exists:
                continue
            row = DrctSignalSearch(
                search_key=default["search_key"], name=default["name"], description=default["description"],
                lifecycle_status="REFERENCE", display_order=default["display_order"], is_active=True,
            )
            self.db.add(row)
            self.db.flush()
            self.db.add(DrctSignalSearchVersion(
                search_id=row.id, version_no=1,
                hts_reference_conditions=default["hts_reference_conditions"],
                hts_condition_expression=default["hts_condition_expression"],
                drct_rule_text=None, change_note="DrCT 검색식.txt 원본 초기 등록", is_current=True,
            ))
            created += 1
        self.db.commit()
        return created
