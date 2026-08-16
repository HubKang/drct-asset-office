from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.services.kms_service import KmsService


def _service_with_knowledge_data() -> tuple[KmsService, Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    db = Session(engine)
    statements = [
        "CREATE TABLE kms_setting_groups (id INTEGER PRIMARY KEY, group_code TEXT, sort_order INTEGER, is_active INTEGER)",
        "CREATE TABLE kms_setting_items (id INTEGER PRIMARY KEY, group_id INTEGER, item_code TEXT, item_name TEXT, color TEXT, icon TEXT, sort_order INTEGER, is_active INTEGER)",
        """CREATE TABLE kms_knowledge_items (
            id INTEGER PRIMARY KEY, legacy_post_id INTEGER, legacy_source_type TEXT, legacy_source_id INTEGER,
            title TEXT, content TEXT, content_format TEXT, one_line_conclusion TEXT, summary TEXT,
            para_type_id INTEGER, category_id INTEGER, status_id INTEGER, importance_id INTEGER,
            usage_context_id INTEGER, source_type_id INTEGER, source_url TEXT, source_title TEXT,
            ai_extract_status TEXT, embedding_status TEXT, is_active INTEGER, created_at TEXT, updated_at TEXT
        )""",
        "CREATE TABLE kms_tags (id INTEGER PRIMARY KEY, name TEXT, description TEXT, use_count INTEGER, is_active INTEGER, tag_type_id INTEGER, created_at TEXT, updated_at TEXT)",
        "CREATE TABLE kms_knowledge_item_tags (id INTEGER PRIMARY KEY, knowledge_item_id INTEGER, tag_id INTEGER, weight REAL, source TEXT, is_confirmed INTEGER, created_at TEXT)",
        "CREATE TABLE kms_knowledge_extractions (id INTEGER PRIMARY KEY, knowledge_item_id INTEGER, extraction_type TEXT, extraction_text TEXT, source TEXT, model_name TEXT, confidence_score REAL, created_at TEXT, updated_at TEXT)",
    ]
    for statement in statements:
        db.execute(text(statement))

    db.execute(text("INSERT INTO kms_setting_groups VALUES (1, 'KNOWLEDGE_CATEGORY', 10, 1), (2, 'KNOWLEDGE_STATUS', 20, 1), (3, 'IMPORTANCE_LEVEL', 30, 1), (4, 'PARA_TYPE', 40, 1), (5, 'SOURCE_TYPE', 50, 1)"))
    db.execute(text("""INSERT INTO kms_setting_items VALUES
        (10, 1, 'MARKET', '시장', '#bfdbfe', NULL, 10, 1),
        (11, 1, 'METHOD', '기법', '#ddd6fe', NULL, 20, 1),
        (20, 2, 'VERIFYING', '검증중', '#fef3c7', NULL, 10, 1),
        (21, 2, 'APPLIED', '적용됨', '#ede9fe', NULL, 20, 1),
        (30, 3, 'CORE', '핵심', '#fee2e2', NULL, 10, 1),
        (31, 3, 'NORMAL', '보통', '#dbeafe', NULL, 20, 1),
        (40, 4, 'RESOURCE', '참고 자료', '#f1f5f9', NULL, 10, 1),
        (50, 5, 'MANUAL', '직접작성', '#f1f5f9', NULL, 10, 1)
    """))
    db.execute(text("""INSERT INTO kms_knowledge_items VALUES
        (1, NULL, NULL, NULL, '시장 글', '<p>시장 본문</p>', 'HTML', NULL, '시장 요약', 40, 10, 20, 30, NULL, 50, NULL, NULL, 'PENDING', 'PENDING', 1, '2026-08-15 10:00:00', '2026-08-15 10:00:00'),
        (2, NULL, NULL, NULL, '기법 글', '<p>기법 본문</p>', 'HTML', NULL, '기법 요약', 40, 11, 21, 31, NULL, 50, NULL, NULL, 'PENDING', 'PENDING', 1, '2026-08-14 10:00:00', '2026-08-14 10:00:00'),
        (3, NULL, NULL, NULL, '비활성 글', '<p>제외</p>', 'HTML', NULL, NULL, 40, 10, 20, 30, NULL, 50, NULL, NULL, 'PENDING', 'PENDING', 0, '2026-08-13 10:00:00', '2026-08-13 10:00:00')
    """))
    db.execute(text("""INSERT INTO kms_tags VALUES
        (1, '금', NULL, 99, 1, NULL, '2026-08-01', '2026-08-01'),
        (2, '금리', NULL, 0, 1, NULL, '2026-08-01', '2026-08-01'),
        (3, '미사용', NULL, 10, 1, NULL, '2026-08-01', '2026-08-01')
    """))
    db.execute(text("""INSERT INTO kms_knowledge_item_tags VALUES
        (1, 1, 1, 1, 'USER', 1, '2026-08-15'),
        (2, 1, 2, 1, 'USER', 1, '2026-08-15'),
        (3, 2, 1, 1, 'USER', 1, '2026-08-14'),
        (4, 3, 3, 1, 'USER', 1, '2026-08-13')
    """))
    db.commit()
    service = KmsService(db)
    service.sync_legacy_posts_to_knowledge_items = lambda: None  # type: ignore[method-assign]
    service.cleanup_knowledge_content_formats = lambda: None  # type: ignore[method-assign]
    return service, db


def test_home_summary_uses_active_knowledge_items_as_source_of_truth() -> None:
    service, db = _service_with_knowledge_data()
    try:
        summary = service.get_home_summary()
        counts = {category.category_name: category.total_posts for category in summary.categories}
        assert summary.overall.total_posts == 2
        assert summary.overall.review_needed_count == 1
        assert summary.overall.practice_candidate_count == 1
        assert summary.overall.core_count == 1
        assert counts == {"시장": 1, "기법": 1}
        assert sum(counts.values()) == summary.overall.total_posts
        assert [(tag.name, tag.use_count) for tag in summary.popular_tags] == [("금", 2), ("금리", 1)]
    finally:
        db.close()


def test_knowledge_page_supports_server_paging_and_and_or_tags() -> None:
    service, db = _service_with_knowledge_data()
    try:
        first_page = service.list_knowledge_items_page(limit=1, offset=0)
        assert first_page.total == 2
        assert len(first_page.items) == 1
        assert sum(entry.count for entry in first_page.category_counts) == 2

        and_page = service.list_knowledge_items_page(tag_names=["금", "금리"], tag_match_mode="AND")
        or_page = service.list_knowledge_items_page(tag_names=["금", "금리"], tag_match_mode="OR")
        assert and_page.total == 1
        assert and_page.items[0].title == "시장 글"
        assert or_page.total == 2
    finally:
        db.close()
