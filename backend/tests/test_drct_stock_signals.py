from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.app.core.database import Base
from backend.app.schemas.drct_stock_signal_schema import (
    DrctSignalMarkerLinksPut,
    DrctSignalSearchCreate,
    DrctSignalSearchPatch,
    DrctSignalVersionCreate,
)
from backend.app.services.drct_stock_signal_service import DrctStockSignalService


def _db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _create_search(service: DrctStockSignalService, name: str = "테스트 검색식") -> dict:
    return service.create_search(DrctSignalSearchCreate(
        name=name,
        description="설명",
        hts_reference_conditions="A 원본 조건",
        hts_condition_expression="A",
        change_note="최초 등록",
    ))


def _seed_marker_cases(db: Session) -> tuple[int, int]:
    db.execute(text("""
        INSERT INTO stocks(id,stock_code,stock_name,is_active,created_at,updated_at)
        VALUES (1,'000001','테스트종목',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
    """))
    db.execute(text("""
        INSERT INTO chart_marker_groups(id,name,color,sort_order,is_active,created_at,updated_at)
        VALUES (1,'지지/저항 시그널','#16a34a',10,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
    """))
    db.execute(text("""
        INSERT INTO chart_markers(id,marker_group_id,name,symbol,sort_order,is_active,created_at,updated_at)
        VALUES (1,1,'지지 라인 - 이평조정 5선','V',10,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
               (2,1,'지지 라인 - 이평조정 10선','V',20,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
    """))
    cases = [
        (1, 1, 1, date(2026, 1, 2), "S"),
        (2, 1, 1, date(2026, 1, 3), "F"),
        (3, 1, 1, date(2026, 1, 4), None),
        (4, 1, 2, date(2026, 1, 5), "S"),
    ]
    db.execute(text("""
        INSERT INTO chart_marker_events
        (id,stock_id,marker_id,marker_date,review_result,created_at,updated_at)
        VALUES (:id,:stock_id,:marker_id,:marker_date,:review_result,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
    """), [
        {"id": row[0], "stock_id": row[1], "marker_id": row[2], "marker_date": row[3], "review_result": row[4]}
        for row in cases
    ])
    db.commit()
    return 1, 2


def test_search_crud_versions_and_soft_deactivation() -> None:
    db = _db()
    service = DrctStockSignalService(db)
    created = _create_search(service)
    assert created["current_version_no"] == 1
    assert service.list_searches()[0]["name"] == "테스트 검색식"
    assert service.get_search(created["id"])["current_version"]["hts_reference_conditions"] == "A 원본 조건"

    updated = service.update_search(created["id"], DrctSignalSearchPatch(
        name="수정 검색식", description="수정 설명", display_order=15,
    ))
    assert updated["name"] == "수정 검색식"
    assert updated["current_version_no"] == 1

    version = service.create_version(created["id"], DrctSignalVersionCreate(
        hts_reference_conditions="A 원본 조건\nB 추가 조건",
        hts_condition_expression="A and B",
        drct_rule_text="MA20 > MA60",
        change_note="B 조건 추가",
    ))
    assert version["version_no"] == 2
    versions = service.list_versions(created["id"])
    assert [row["version_no"] for row in versions] == [2, 1]
    assert versions[0]["is_current"] is True
    assert versions[1]["is_current"] is False
    assert versions[1]["hts_reference_conditions"] == "A 원본 조건"

    inactive = service.update_search(created["id"], DrctSignalSearchPatch(is_active=False))
    assert inactive["is_active"] is False
    assert inactive["lifecycle_status"] == "INACTIVE"
    assert db.execute(text("SELECT COUNT(*) FROM drct_signal_searches WHERE id=:id"), {"id": created["id"]}).scalar_one() == 1


def test_marker_links_and_dynamic_training_summary() -> None:
    db = _db()
    marker_a, marker_b = _seed_marker_cases(db)
    service = DrctStockSignalService(db)
    search = _create_search(service)

    links = service.replace_marker_links(search["id"], DrctSignalMarkerLinksPut(
        marker_definition_ids=[marker_a, marker_b, marker_a],
    ))
    assert len(links) == 2
    assert service.training_summary(search["id"]) == {
        "linked_marker_count": 2,
        "total_case_count": 4,
        "success_count": 2,
        "failure_count": 1,
        "undecided_count": 1,
        "latest_case_date": "2026-01-05",
    }

    service.replace_marker_links(search["id"], DrctSignalMarkerLinksPut(marker_definition_ids=[marker_a]))
    summary = service.training_summary(search["id"])
    assert summary["linked_marker_count"] == 1
    assert summary["total_case_count"] == 3

    service.replace_marker_links(search["id"], DrctSignalMarkerLinksPut(marker_definition_ids=[]))
    assert service.training_summary(search["id"])["total_case_count"] == 0


def test_missing_ids_and_seed_are_safe() -> None:
    db = _db()
    service = DrctStockSignalService(db)
    with pytest.raises(HTTPException) as search_error:
        service.get_search(999)
    assert search_error.value.status_code == 404

    search = _create_search(service)
    with pytest.raises(HTTPException) as marker_error:
        service.replace_marker_links(search["id"], DrctSignalMarkerLinksPut(marker_definition_ids=[999]))
    assert marker_error.value.status_code == 404

    assert service.seed_defaults() == 3
    assert service.seed_defaults() == 0
    assert db.execute(text("SELECT COUNT(*) FROM drct_signal_searches")).scalar_one() == 4
    seeded = db.execute(text("""
        SELECT s.name,v.version_no,v.hts_condition_expression
        FROM drct_signal_searches s JOIN drct_signal_search_versions v ON v.search_id=s.id
        WHERE s.search_key='DOUBLE_BOTTOM_TREND_REVERSAL'
    """)).one()
    assert seeded.name == "쌍바닥 추세 전환 패턴"
    assert seeded.version_no == 1
    assert seeded.hts_condition_expression == "A and B and C and D and E and F and G and H and I"
