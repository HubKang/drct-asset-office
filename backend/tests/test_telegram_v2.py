from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.core.database import Base
from backend.app.entities.telegram_source import TelegramSource
from backend.app.repositories.telegram_repository import TelegramRepository
from backend.app.services.telegram_article_service import ArticleExtractionResult, TelegramArticleService
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
                      "missing_url": 1, "fetch_failed": 0, "extraction_failed": 0,
                      "processing_failed": 0}
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
        def fetch_article(self, _url, _title, _stock_name=None):
            text = "기사 본문 " * 100
            return ArticleExtractionResult(True, text, "TITLE_ANCHOR_ARTICLE_BODY", 1.0, len(text), 3)

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
      <main class="news_content"><div class="article-unit">
        <h1>대한광통신, 광섬유 가격 급등…데이터센터향 공급 본격화</h1>
        <div class="news_body" itemprop="articleBody"><p>{actual}</p><p>{actual}</p></div>
        <div class="related-news">관련기사<a>{unrelated}</a></div></div>
      </main>
    </body></html>
    """

    extracted = TelegramArticleService.extract_article_text(
        page, "대한광통신, 광섬유 가격 급등·데이터센터향 공급 본격화", "대한광통신",
    )

    assert "대한광통신" in extracted
    assert "엔비디아" not in extracted
    assert "국민연금" not in extracted


def test_article_extractor_fails_closed_without_article_body() -> None:
    page = "<html><body><main><div class='news-list'>" + ("서로 다른 추천 기사 제목입니다. " * 30) + "</div></main></body></html>"
    assert TelegramArticleService.extract_article_text(page, "대한광통신 광섬유 공급 확대") == ""


def test_article_title_normalization_and_similarity() -> None:
    service = TelegramArticleService
    db_title = "  대한광통신,  광섬유 가격 급등·데이터센터향 공급 &amp; 본격화... "
    html_title = "대한광통신, 광섬유 가격 급등…데이터센터향 공급 & 본격화"
    assert service.normalize_title("ＡI ‘Data’") == service.normalize_title("ai data")
    assert service.title_similarity(db_title, html_title) >= service.ARTICLE_TITLE_MATCH_THRESHOLD


def test_article_anchor_supports_nested_sibling_container() -> None:
    body = "대한광통신은 광섬유 공급을 확대했다. 데이터센터 수요가 늘어 하반기 매출 개선을 기대한다고 밝혔다. " * 7
    page = f"""
    <html><head><meta property="og:title" content="대한광통신 광섬유 공급 본격화"></head><body><main>
      <section><div class="headline"><h1>대한광통신 광섬유 공급 본격화</h1></div>
      <div class="contents"><p>{body}</p><p>{body}</p></div></section>
    </main></body></html>
    """
    result = TelegramArticleService.extract_article(page, "대한광통신 광섬유 공급 본격화", "대한광통신")
    assert result.success is True
    assert result.method == "TITLE_ANCHOR_CONTAINER"
    assert result.paragraph_count >= 2


def test_article_anchor_supports_semantic_div_title() -> None:
    body = "대한광통신은 AI 인프라 공급 확대를 위해 광섬유와 데이터센터용 케이블 투자를 이어갈 계획이라고 밝혔다. " * 7
    page = f"""
    <html><body><div class="page-shell"><div class="article-unit">
      <header><div class="article-head-title">대한광통신 10%대 상승…AI 인프라 공급 확대</div></header>
      <div class="article-view-content"><p>{body}</p><p>{body}</p></div>
    </div></div></body></html>
    """
    result = TelegramArticleService.extract_article(
        page,
        "대한광통신 10%대 상승…AI 인프라 공급 확대",
        "대한광통신",
    )
    assert result.success is True
    assert result.method == "TITLE_ANCHOR_CONTAINER"
    assert "광섬유" in result.text


def test_article_anchor_rejects_different_title_even_with_large_div() -> None:
    page = "<html><body><main><div><h1>엔비디아 분기 실적 발표</h1><p>" + ("대한광통신 광섬유 내용 " * 80) + "</p></div></main></body></html>"
    result = TelegramArticleService.extract_article(page, "대한광통신 광섬유 공급 확대")
    assert result.success is False
    assert result.failure_reason == "TITLE_ANCHOR_NOT_FOUND"


def test_article_anchor_rejects_company_name_only_heading() -> None:
    body = "대한광통신과 무관한 다른 기사 문장입니다. " * 80
    page = f"<html><body><main><h1>대한광통신</h1><article><p>{body}</p><p>{body}</p></article></main></body></html>"
    result = TelegramArticleService.extract_article(
        page,
        "대한광통신, 광섬유 가격 급등·데이터센터향 공급 본격화",
        "대한광통신",
    )
    assert result.success is False
    assert result.failure_reason == "TITLE_ANCHOR_NOT_FOUND"


def test_article_related_links_are_cut_before_validation_and_llm_input() -> None:
    body = "대한광통신은 광섬유 공급을 확대하고 데이터센터 전용 케이블 매출 증가를 예상했다. " * 8
    related = "엔비디아 최대 실적 국민연금 수익률 모건스탠리 대한해운 성장성"
    page = f"""<article><h1>대한광통신 광섬유 공급 확대</h1>
      <div itemprop="articleBody"><p>{body}</p><p>{body}</p><h3>관련기사</h3>
      <a href="/a">{related}</a><a href="/b">{related}</a></div></article>"""
    result = TelegramArticleService.extract_article(page, "대한광통신 광섬유 공급 확대", "대한광통신")
    assert result.success is True
    assert "대한광통신" in result.text
    assert "엔비디아" not in result.text


def test_article_quality_gate_rejects_short_body_and_high_link_density() -> None:
    short = "<article><h1>대한광통신 광섬유 공급 확대</h1><p>대한광통신 광섬유 단신입니다.</p></article>"
    short_result = TelegramArticleService.extract_article(short, "대한광통신 광섬유 공급 확대")
    assert short_result.success is False
    assert short_result.failure_reason == "ARTICLE_BODY_TOO_SHORT"

    links = "".join(f"<a href='/{index}'>대한광통신 광섬유 추천 기사 제목과 링크 내용입니다 {index}</a>" for index in range(30))
    linked_page = f"<article><h1>대한광통신 광섬유 공급 확대</h1><div>{links}</div></article>"
    linked_result = TelegramArticleService.extract_article(linked_page, "대한광통신 광섬유 공급 확대")
    assert linked_result.success is False
    assert linked_result.failure_reason == "ARTICLE_LINK_DENSITY_HIGH"


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
