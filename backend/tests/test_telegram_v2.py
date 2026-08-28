from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.core.database import Base
from backend.app.entities.telegram_source import TelegramSource
from backend.app.repositories.telegram_repository import TelegramRepository
from backend.app.services.telegram_article_service import TelegramArticleService
from backend.app.services.telegram_llm_service import TelegramLLMService
from backend.app.services.telegram_v2_service import TelegramService
from backend.app.llm.lmstudio_client import LMStudioClient


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def add_source(db: Session, source_id: int = 1) -> TelegramSource:
    source = TelegramSource(
        id=source_id, source_name=f"채널 {source_id}", channel_username=f"channel{source_id}",
        channel_title=None, source_type="channel", description=None, is_active=1, is_default=0,
        is_deleted=0, last_collected_message_id=None, last_collected_at=None, memo=None,
        created_at="2026-08-27 10:00:00", updated_at=None,
    )
    db.add(source); db.commit()
    return source


def test_url_fingerprint_removes_tracking_and_deduplicates_channels() -> None:
    first = TelegramService.build_fingerprint("채널 A", "https://news.example.com/a?utm_source=tg&id=7")
    second = TelegramService.build_fingerprint("채널 B", "https://NEWS.example.com/a?id=7&utm_medium=x")
    assert first == second


def test_text_fingerprint_is_whitespace_insensitive() -> None:
    first = TelegramService.build_fingerprint("같은   메시지\n본문", None)
    second = TelegramService.build_fingerprint(" 같은 메시지 본문 ", None)
    assert first == second


def test_delete_creates_same_day_exclusion_and_next_date_cleanup() -> None:
    db = make_session()
    repo = TelegramRepository(db)
    row = repo.create_item({
        "collection_date": "2026-08-27", "message_at": "2026-08-27 09:00:00",
        "title": "테스트 기사", "summary": None, "source_url": None,
        "message_fingerprint": "f" * 64, "created_at": "2026-08-27 09:01:00",
    })
    assert repo.delete_items_with_exclusion([row.id]) == 1
    assert repo.is_excluded("2026-08-27", "f" * 64)
    assert repo.cleanup_exclusions("2026-08-28") == 1
    assert not repo.is_excluded("2026-08-27", "f" * 64)
    db.close()


def test_search_uses_only_durable_fields_and_paginates() -> None:
    db = make_session()
    repo = TelegramRepository(db)
    repo.create_item({
        "collection_date": "2026-08-27", "message_at": "2026-08-27 09:00:00",
        "title": "반도체 수출 증가", "summary": "공식 집계에서 증가가 확인됐습니다.",
        "source_url": "https://example.com/a", "message_fingerprint": "a" * 64,
        "created_at": "2026-08-27 09:01:00",
    })
    items, total, with_summary, title_only = repo.list_items(keyword="반도체", limit=20)
    assert len(items) == total == with_summary == 1
    assert title_only == 0
    assert set(vars(items[0])) >= {"title", "summary", "source_url", "message_fingerprint"}
    db.close()


def test_collect_keeps_raw_message_in_memory_only() -> None:
    db = make_session(); add_source(db)
    service = TelegramService(db)

    class Collector:
        async def collect_channel_messages(self, *_args):
            return {
                "success": True, "source_mode": "real", "telegram_connected": True,
                "session_exists": True, "channel_accessible": True, "diagnostics": {},
                "messages": [{"telegram_message_id": 11, "message_date": "2026-08-27 08:00:00",
                              "message_text": "원문 비저장 테스트 https://example.com/news?id=1",
                              "message_url": "https://example.com/news?id=1"}],
            }

    class Llm:
        def summarize_article(self, _text, _title=None):
            raise AssertionError("collection must never call Local LLM")

    service.collector = Collector()  # type: ignore[assignment]
    service.llm_service = Llm()  # type: ignore[assignment]
    import asyncio
    result = asyncio.run(service.collect_source_by_date(1, "2026-08-27"))
    assert result["inserted"] == 1
    columns = {row[1] for row in db.connection().exec_driver_sql("pragma table_info(telegram_items)")}
    assert "message_text" not in columns and "source_id" not in columns and "summary_status" not in columns
    saved = service.repo.get_item(1)
    assert saved and saved.summary is None
    db.close()


def test_collection_title_is_derived_without_llm() -> None:
    assert TelegramService.derive_title(
        "⚡ 채널 - 반도체 수출 증가 확인 https://example.com/a", "채널"
    ) == "반도체 수출 증가 확인"


def test_article_url_rejects_private_network(monkeypatch) -> None:
    monkeypatch.setattr(TelegramArticleService, "_resolve_ips", staticmethod(lambda *_: {"127.0.0.1"}))
    try:
        TelegramArticleService.validate_public_url("http://example.com/private")
        assert False, "private address must be rejected"
    except ValueError:
        pass


def test_on_demand_summary_skips_existing_and_missing_url() -> None:
    db = make_session()
    repo = TelegramRepository(db)
    existing = repo.create_item({
        "collection_date": "2026-08-27", "message_at": "2026-08-27 09:00:00",
        "title": "기존 요약", "summary": "이미 충분한 요약이 저장되어 있습니다.",
        "source_url": "https://example.com/a", "message_fingerprint": "b" * 64,
        "created_at": "2026-08-27 09:01:00",
    })
    missing = repo.create_item({
        "collection_date": "2026-08-27", "message_at": "2026-08-27 08:00:00",
        "title": "URL 없음", "summary": None, "source_url": None,
        "message_fingerprint": "c" * 64, "created_at": "2026-08-27 09:01:00",
    })
    result = TelegramService(db).summarize_items([existing.id, missing.id])
    assert result == {"requested": 2, "summarized": 0, "skipped_existing": 1,
                      "missing_url": 1, "fetch_failed": 0, "processing_failed": 0}
    db.close()


def test_on_demand_summary_updates_only_summary() -> None:
    db = make_session()
    repo = TelegramRepository(db)
    item = repo.create_item({
        "collection_date": "2026-08-27", "message_at": "2026-08-27 07:00:00",
        "title": "원래 제목", "summary": None, "source_url": "https://example.com/article",
        "message_fingerprint": "d" * 64, "created_at": "2026-08-27 09:01:00",
    })
    service = TelegramService(db)

    class Article:
        def fetch_text(self, _url): return "기사 본문 " * 100

    class Llm:
        def summarize_article(self, _text, _title=None):
            return {"success": True, "summary": "기사 원문에서 확인한 핵심 사실을 두 문장으로 정리했습니다. 숫자와 일정을 보존했습니다."}

    service.article_service = Article()  # type: ignore[assignment]
    service.llm_service = Llm()  # type: ignore[assignment]
    result = service.summarize_items([item.id])
    refreshed = repo.get_item(item.id)
    assert result["summarized"] == 1
    assert refreshed and refreshed.title == "원래 제목" and refreshed.summary
    db.close()


def test_article_summary_uses_configured_output_budget(monkeypatch) -> None:
    service = TelegramLLMService()
    captured: dict[str, object] = {}

    class Client:
        def generate_text(self, **kwargs):
            captured.update(kwargs)
            return '{"summary":"대한광통신의 광섬유 공급이 확대됐으며 관련 매출이 증가했습니다. 회사는 하반기 실적 개선을 예상했습니다."}'

    service.client = Client()  # type: ignore[assignment]
    result = service.summarize_article("대한광통신 기사 본문입니다. " * 30)

    assert result["success"] is True
    assert captured["max_tokens"] >= 1200


def test_article_extractor_prefers_exact_body_over_unrelated_news_lists() -> None:
    unrelated = "엔비디아 최대 실적 국민연금 수익률 모건스탠리 대한해운 성장성 " * 20
    actual = "대한광통신은 광섬유 가격 상승과 데이터센터향 공급 확대에 힘입어 하반기 실적 개선을 전망했다. " * 8
    page = f"""
    <html><body>
      <main class="news_content"><div class="related-news">{unrelated}</div>
        <div class="news_body" itemprop="articleBody"><p>{actual}</p></div>
      </main>
    </body></html>
    """

    extracted = TelegramArticleService.extract_article_text(page)

    assert "대한광통신" in extracted
    assert "엔비디아" not in extracted
    assert "국민연금" not in extracted


def test_article_extractor_fails_closed_without_article_body() -> None:
    page = "<html><body><main><div class='news-list'>" + ("서로 다른 추천 기사 제목입니다. " * 30) + "</div></main></body></html>"
    assert TelegramArticleService.extract_article_text(page) == ""


def test_lmstudio_retries_length_only_response_with_larger_budget(monkeypatch) -> None:
    requests_payloads: list[dict] = []

    class Response:
        status_code = 200
        text = ""

        def __init__(self, data: dict) -> None:
            self.data = data

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self.data

    responses = iter([
        Response({"choices": [{"finish_reason": "length", "message": {
            "content": "", "reasoning_content": "내부 추론" * 100,
        }}]}),
        Response({"choices": [{"finish_reason": "stop", "message": {
            "content": '{"summary":"출력 한도를 늘린 재시도에서 정상 요약을 반환했습니다."}',
        }}]}),
    ])

    def fake_post(_url, json, timeout):
        requests_payloads.append(dict(json))
        return next(responses)

    monkeypatch.setattr("backend.app.llm.lmstudio_client.LLM_RETRY_COUNT", 1)
    monkeypatch.setattr("backend.app.llm.lmstudio_client.requests.post", fake_post)

    result = LMStudioClient().generate_text("요약", max_tokens=700, purpose="test")

    assert "정상 요약" in result
    assert [payload["max_tokens"] for payload in requests_payloads] == [700, 1400]
