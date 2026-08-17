from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.app.services import image_file_service
from backend.app.services.kms_service import KmsService
from backend.app.schemas.kms_schema import KmsKnowledgeItemCreate, KmsKnowledgeItemUpdate


def image_html(name: str, width: int = 50) -> str:
    return (
        f'<img src="http://127.0.0.1:8000/static/kms_images/2026/08/{name}" '
        f'alt="{name}" width="{width}%" data-kms-width="{width}" '
        f'style="width: {width}%; max-width: 100%; height: auto;">'
    )


def make_db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    db = Session(engine)
    db.execute(text("CREATE TABLE kms_knowledge_items (id INTEGER PRIMARY KEY, content TEXT, is_active INTEGER NOT NULL DEFAULT 1)"))
    db.execute(text("CREATE TABLE app_images (id INTEGER PRIMARY KEY, domain TEXT, owner_type TEXT, owner_id INTEGER, relative_path TEXT, updated_at TEXT)"))
    db.commit()
    return db


def make_content_db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    db = Session(engine)
    db.execute(text("""
        CREATE TABLE kms_knowledge_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT, legacy_post_id INTEGER, legacy_source_type TEXT, legacy_source_id INTEGER,
            title TEXT, content TEXT, content_format TEXT, one_line_conclusion TEXT, summary TEXT,
            para_type_id INTEGER, category_id INTEGER, status_id INTEGER, importance_id INTEGER,
            usage_context_id INTEGER, source_type_id INTEGER, source_url TEXT, source_title TEXT,
            ai_extract_status TEXT, embedding_status TEXT, is_active INTEGER, created_at TEXT, updated_at TEXT
        )
    """))
    db.execute(text("CREATE TABLE app_images (id INTEGER PRIMARY KEY, domain TEXT, owner_type TEXT, owner_id INTEGER, relative_path TEXT, updated_at TEXT)"))
    db.commit()
    return db


def test_extract_kms_images_uses_html_parser_and_rejects_foreign_or_traversal_paths() -> None:
    db = make_db()
    service = KmsService(db)
    html = (
        image_html("안전.png")
        + '<img src="https://example.com/test.jpg">'
        + '<img src="/static/kms_images/../../important.file">'
    )

    _, paths = service._extract_kms_image_refs(html)

    assert paths == {"data/kms_images/2026/08/안전.png"}


def test_cleanup_deletes_only_unreferenced_internal_images_after_content_update(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(image_file_service, "PROJECT_ROOT", tmp_path)
    image_root = tmp_path / "data" / "kms_images" / "2026" / "08"
    image_root.mkdir(parents=True)
    for name in ("keep.png", "remove.png", "shared.png", "unused-upload.png"):
        (image_root / name).write_bytes(b"image")

    db = make_db()
    db.execute(text("INSERT INTO kms_knowledge_items (id, content, is_active) VALUES (1, :content, 1)"), {"content": image_html("keep.png")})
    db.execute(text("INSERT INTO kms_knowledge_items (id, content, is_active) VALUES (2, :content, 1)"), {"content": image_html("shared.png")})
    for image_id, name in enumerate(("keep.png", "remove.png", "shared.png", "unused-upload.png"), start=1):
        db.execute(
            text("INSERT INTO app_images (id, domain, relative_path) VALUES (:id, 'kms', :path)"),
            {"id": image_id, "path": f"data/kms_images/2026/08/{name}"},
        )
    db.commit()

    service = KmsService(db)
    result = service._cleanup_unreferenced_knowledge_images(
        old_content=image_html("keep.png") + image_html("remove.png") + image_html("shared.png"),
        new_content=image_html("keep.png"),
        editor_uploaded_image_urls=["/static/kms_images/2026/08/unused-upload.png"],
    )

    assert result == {"deleted": 2, "skipped_in_use": 1, "failed": 0}
    assert (image_root / "keep.png").exists()
    assert (image_root / "shared.png").exists()
    assert not (image_root / "remove.png").exists()
    assert not (image_root / "unused-upload.png").exists()
    remaining = {row[0] for row in db.execute(text("SELECT relative_path FROM app_images")).all()}
    assert remaining == {
        "data/kms_images/2026/08/keep.png",
        "data/kms_images/2026/08/shared.png",
    }


def test_cleanup_does_not_delete_when_edit_is_cancelled(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(image_file_service, "PROJECT_ROOT", tmp_path)
    image_path = tmp_path / "data" / "kms_images" / "2026" / "08" / "cancelled.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"image")
    db = make_db()
    db.execute(text("INSERT INTO kms_knowledge_items (id, content, is_active) VALUES (1, :content, 1)"), {"content": image_html("cancelled.png")})
    db.commit()

    # Cancel does not invoke cleanup; the persisted reference and physical file remain untouched.
    assert KmsService(db)._knowledge_image_is_referenced("data/kms_images/2026/08/cancelled.png") is True
    assert image_path.exists()


def test_cleanup_follows_removed_persisted_link_without_legacy_metadata(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(image_file_service, "PROJECT_ROOT", tmp_path)
    image_path = tmp_path / "data" / "kms_images" / "2026" / "08" / "legacy.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"image")
    db = make_db()
    db.execute(text("INSERT INTO kms_knowledge_items (id, content, is_active) VALUES (1, '', 1)"))
    db.commit()

    result = KmsService(db)._cleanup_unreferenced_knowledge_images(
        old_content=image_html("legacy.png"),
        new_content="<p>이미지 삭제 후 본문</p>",
        editor_uploaded_image_urls=[],
        editor_removed_image_urls=["/static/kms_images/2026/08/legacy.png"],
    )

    assert result == {"deleted": 1, "skipped_in_use": 0, "failed": 0}
    assert not image_path.exists()


def test_cleanup_keeps_image_when_delete_was_undone_before_save(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(image_file_service, "PROJECT_ROOT", tmp_path)
    image_path = tmp_path / "data" / "kms_images" / "2026" / "08" / "restored.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"image")
    db = make_db()
    content = image_html("restored.png")
    db.execute(text("INSERT INTO kms_knowledge_items (id, content, is_active) VALUES (1, :content, 1)"), {"content": content})
    db.execute(text("INSERT INTO app_images (id, domain, relative_path) VALUES (1, 'kms', 'data/kms_images/2026/08/restored.png')"))
    db.commit()

    result = KmsService(db)._cleanup_unreferenced_knowledge_images(
        old_content=content,
        new_content=content,
        editor_uploaded_image_urls=[],
        editor_removed_image_urls=["/static/kms_images/2026/08/restored.png"],
    )

    assert result == {"deleted": 0, "skipped_in_use": 0, "failed": 0}
    assert image_path.exists()


def test_create_then_text_only_update_preserves_all_five_images(monkeypatch) -> None:
    db = make_content_db()
    service = KmsService(db)
    monkeypatch.setattr(service, "_kms_setting_default_ids", lambda: {
        "PARA_TYPE": None,
        "KNOWLEDGE_CATEGORY": None,
        "KNOWLEDGE_STATUS": None,
        "IMPORTANCE_LEVEL": None,
        "USAGE_CONTEXT": None,
        "SOURCE_TYPE": None,
    })
    monkeypatch.setattr(service, "_replace_knowledge_item_tags", lambda *_args, **_kwargs: None)

    def get_item(item_id: int):
        row = db.execute(text("SELECT id, title, content FROM kms_knowledge_items WHERE id = :id"), {"id": item_id}).mappings().one()
        return SimpleNamespace(id=int(row["id"]), title=str(row["title"]), content=str(row["content"]))

    monkeypatch.setattr(service, "get_knowledge_item", get_item)
    five_images = "<p>등록 본문</p>" + "".join(image_html(f"image-{index}.png", 20 + index * 15) for index in range(1, 6))

    created = service.create_knowledge_item(KmsKnowledgeItemCreate(title="이미지 5개", content=five_images))
    _, created_paths = service._extract_kms_image_refs(created.content)
    assert len(created_paths) == 5

    updated_html = created.content.replace("등록 본문", "텍스트만 수정한 본문")
    updated = service.update_knowledge_item(created.id, KmsKnowledgeItemUpdate(content=updated_html))
    _, updated_paths = service._extract_kms_image_refs(updated.content)
    assert updated_paths == created_paths
    assert updated.content.count("data-kms-width") == 5


def test_update_removing_image_deletes_linked_physical_file_and_metadata(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(image_file_service, "PROJECT_ROOT", tmp_path)
    image_path = tmp_path / "data" / "kms_images" / "2026" / "08" / "remove-on-save.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"image")
    db = make_content_db()
    old_content = "<p>삭제 전</p>" + image_html("remove-on-save.png")
    db.execute(
        text(
            "INSERT INTO kms_knowledge_items "
            "(id, title, content, content_format, is_active, created_at, updated_at) "
            "VALUES (1, '삭제 테스트', :content, 'HTML', 1, '2026-08-16', '2026-08-16')"
        ),
        {"content": old_content},
    )
    db.execute(
        text(
            "INSERT INTO app_images (id, domain, owner_type, owner_id, relative_path) "
            "VALUES (1, 'kms', 'kms_knowledge_item', 1, 'data/kms_images/2026/08/remove-on-save.png')"
        )
    )
    db.commit()
    service = KmsService(db)

    def get_item(item_id: int):
        row = db.execute(text("SELECT id, title, content FROM kms_knowledge_items WHERE id = :id"), {"id": item_id}).mappings().one()
        return SimpleNamespace(id=int(row["id"]), title=str(row["title"]), content=str(row["content"]))

    monkeypatch.setattr(service, "get_knowledge_item", get_item)
    service.update_knowledge_item(
        1,
        KmsKnowledgeItemUpdate(
            content="<p>삭제 후</p>",
            editor_removed_image_urls=["/static/kms_images/2026/08/remove-on-save.png"],
        ),
    )

    assert not image_path.exists()
    assert db.execute(text("SELECT COUNT(*) FROM app_images WHERE id = 1")).scalar_one() == 0
