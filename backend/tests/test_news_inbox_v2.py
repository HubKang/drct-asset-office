from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from backend.app.core.database import Base
from backend.app.entities.news import NewsItem
from backend.app.entities.stock import Stock
from backend.app.repositories.news_repository import NewsRepository
from backend.app.services.collector_service import CollectorService
from backend.app.services.news_service import NewsService


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def add_stock(db: Session, *, code: str = "005930", name: str = "삼성전자") -> Stock:
    stock = Stock(
        stock_code=code, stock_name=name, market="KOSPI", sector=None,
        industry=None, isin_code=None, corp_name=None, corp_reg_no=None,
        last_synced_at=None, source=None, security_type="보통주", is_active=1,
        created_at="2026-08-28 09:00:00", updated_at="2026-08-28 09:00:00",
    )
    db.add(stock); db.commit(); db.refresh(stock)
    return stock


def add_news(db: Session, stock_id: int, *, url: str | None, fingerprint: str | None,
             summary: str | None = None, published_at: str = "2026-08-28 08:00:00",
             created_at: str = "2026-08-28 09:00:00") -> NewsItem:
    row = NewsItem(
        stock_id=stock_id, title="테스트 뉴스", source="naver_news", url=url,
        article_fingerprint=fingerprint, published_at=published_at,
        collected_at="2026-08-28 09:00:00", raw_text_path=None, summary=summary,
        sentiment="neutral", importance_score=10, ai_summary="기존 AI 필드",
        ai_sentiment="positive", ai_importance_score=77, ai_tags="legacy",
        ai_processed_at="2026-08-28 09:01:00", ai_summary_error=None,
        created_at=created_at,
    )
    db.add(row); db.commit(); db.refresh(row)
    return row


def test_news_inbox_is_sorted_by_latest_published_at() -> None:
    db = make_session(); stock = add_stock(db)
    older = add_news(
        db, stock.id, url="https://news.example.com/older", fingerprint="older",
        published_at="2026-08-27 18:00:00", created_at="2026-08-28 10:00:00",
    )
    newer = add_news(
        db, stock.id, url="https://news.example.com/newer", fingerprint="newer",
        published_at="2026-08-28 08:00:00", created_at="2026-08-28 09:00:00",
    )

    rows = NewsRepository(db).list_with_stock(stock.id, None, None, None, 20, 0)

    assert [news.id for news, _stock in rows] == [newer.id, older.id]
    db.close()


def test_collection_persists_no_provider_source_or_provider_description(monkeypatch) -> None:
    db = make_session(); stock = add_stock(db)

    class Collector:
        name = "naver_news_collector"

        def collect_by_keyword(self, **_kwargs):
            return {"total": 1, "items": [{
                "title": "<b>삼성전자</b> 신규 투자",
                "description": "저장하면 안 되는 공급자 설명 원문",
                "originallink": "https://news.example.com/article?id=7&utm_source=naver",
                "pubDate": "Fri, 28 Aug 2026 08:00:00 +0900",
            }]}

    monkeypatch.setattr("backend.app.services.collector_service.NaverNewsCollector", Collector)
    result = CollectorService(db).collect_news_for_stock(stock.id, ["naver"], 10, "date")
    saved = db.scalar(select(NewsItem))

    assert result["saved_count"] == 1
    assert saved is not None
    assert saved.title == "삼성전자 신규 투자"
    assert saved.source is None
    assert saved.summary is None
    assert saved.raw_text_path is None
    assert "utm_source" not in (saved.url or "")
    assert "공급자 설명" not in str(vars(saved))
    db.close()


def test_collection_skips_title_without_official_stock_name(monkeypatch) -> None:
    db = make_session(); stock = add_stock(db, code="097230", name="HJ중공업")

    class Collector:
        name = "naver_news_collector"

        def collect_by_keyword(self, **_kwargs):
            return {"total": 2, "items": [
                {"title": "HJ중공업, 신조선 수주 확대", "originallink": "https://news.example.com/pass", "pubDate": "Fri, 28 Aug 2026 08:00:00 +0900"},
                {"title": "국내 조선사 신규 수주 확대", "originallink": "https://news.example.com/skip", "pubDate": "Fri, 28 Aug 2026 08:00:00 +0900"},
            ]}

    monkeypatch.setattr("backend.app.services.collector_service.NaverNewsCollector", Collector)
    monkeypatch.setattr(CollectorService, "_today_kst", lambda _self: date(2026, 8, 28))
    result = CollectorService(db).collect_news_for_stock(stock.id, ["naver"], 20, "date")

    assert result["saved_count"] == 1
    assert result["name_mismatch_skipped"] == 1
    assert db.scalar(select(NewsItem.title)) == "HJ중공업, 신조선 수주 확대"
    db.close()


def test_collection_normalizes_whitespace_but_rejects_partial_name(monkeypatch) -> None:
    db = make_session(); stock = add_stock(db, code="000660", name="SK하이닉스")

    class Collector:
        name = "naver_news_collector"

        def collect_by_keyword(self, **_kwargs):
            return {"total": 3, "items": [
                {"title": "SK하이닉스   HBM4 공급 확대", "originallink": "https://news.example.com/space", "pubDate": "Fri, 28 Aug 2026 08:00:00 +0900"},
                {"title": "하이닉스 협력사 실적 개선", "originallink": "https://news.example.com/partial", "pubDate": "Fri, 28 Aug 2026 08:00:00 +0900"},
                {"title": "   ", "originallink": "https://news.example.com/blank", "pubDate": "Fri, 28 Aug 2026 08:00:00 +0900"},
            ]}

    monkeypatch.setattr("backend.app.services.collector_service.NaverNewsCollector", Collector)
    monkeypatch.setattr(CollectorService, "_today_kst", lambda _self: date(2026, 8, 28))
    result = CollectorService(db).collect_news_for_stock(stock.id, ["naver"], 20, "date")

    assert result["saved_count"] == 1
    assert result["name_mismatch_skipped"] == 1
    assert result["invalid_skipped"] == 1
    db.close()


def test_initial_collection_pages_until_twenty_matching_titles(monkeypatch) -> None:
    db = make_session(); stock = add_stock(db, code="000660", name="SK하이닉스")
    calls: list[int] = []

    class Collector:
        name = "naver_news_collector"

        def collect_by_keyword(self, **kwargs):
            start = int(kwargs["start"]); calls.append(start)
            match_count = 8 if start == 1 else 12
            items = [
                {"title": f"SK하이닉스 HBM 확대 {start}-{index}", "originallink": f"https://news.example.com/{start}/{index}", "pubDate": "Fri, 28 Aug 2026 08:00:00 +0900"}
                for index in range(match_count)
            ]
            items.extend({
                "title": f"반도체 업황 기사 {start}-{index}", "originallink": f"https://news.example.com/miss/{start}/{index}", "pubDate": "Fri, 28 Aug 2026 08:00:00 +0900",
            } for index in range(100 - match_count))
            return {"total": 200, "items": items}

    monkeypatch.setattr("backend.app.services.collector_service.NaverNewsCollector", Collector)
    monkeypatch.setattr(CollectorService, "_today_kst", lambda _self: date(2026, 8, 28))
    result = CollectorService(db).collect_news_for_stock(stock.id, ["naver"], 30, "date")

    assert calls == [1, 101]
    assert result["saved_count"] == 20
    assert result["mode"] == "INITIAL"
    assert db.scalar(select(func.count(NewsItem.id))) == 20
    db.close()


def test_zero_match_still_advances_collection_cursor(monkeypatch) -> None:
    db = make_session(); stock = add_stock(db, code="097230", name="HJ중공업")

    class Collector:
        name = "naver_news_collector"

        def collect_by_keyword(self, **_kwargs):
            return {"total": 1, "items": [{
                "title": "국내 조선사 신규 수주 확대", "originallink": "https://news.example.com/no-match", "pubDate": "Fri, 28 Aug 2026 08:00:00 +0900",
            }]}

    monkeypatch.setattr("backend.app.services.collector_service.NaverNewsCollector", Collector)
    monkeypatch.setattr(CollectorService, "_today_kst", lambda _self: date(2026, 8, 28))
    result = CollectorService(db).collect_news_for_stock(stock.id, ["naver"], 20, "date")

    assert result["saved_count"] == 0
    assert NewsRepository(db).get_collection_cursor(stock.id) == "2026-08-28"
    db.close()


def test_same_article_can_be_linked_to_each_named_stock(monkeypatch) -> None:
    db = make_session()
    samsung = add_stock(db, code="005930", name="삼성전자")
    hynix = add_stock(db, code="000660", name="SK하이닉스")

    class Collector:
        name = "naver_news_collector"

        def collect_by_keyword(self, **_kwargs):
            return {"total": 1, "items": [{
                "title": "삼성전자·SK하이닉스 HBM 경쟁 확대", "originallink": "https://news.example.com/shared", "pubDate": "Fri, 28 Aug 2026 08:00:00 +0900",
            }]}

    monkeypatch.setattr("backend.app.services.collector_service.NaverNewsCollector", Collector)
    monkeypatch.setattr(CollectorService, "_today_kst", lambda _self: date(2026, 8, 28))
    assert CollectorService(db).collect_news_for_stock(samsung.id, ["naver"], 20, "date")["saved_count"] == 1
    assert CollectorService(db).collect_news_for_stock(hynix.id, ["naver"], 20, "date")["saved_count"] == 1
    assert db.scalar(select(func.count(NewsItem.id))) == 2
    db.close()


def test_selected_summary_updates_only_durable_summary() -> None:
    db = make_session(); stock = add_stock(db)
    row = add_news(db, stock.id, url="https://news.example.com/article", fingerprint="a" * 64)
    service = NewsService(db)

    class Article:
        def fetch_text(self, _url):
            return "기사 본문 " * 100

    class Llm:
        def summarize_article(self, _text, _title=None):
            return {"success": True, "summary": "기사 원문에서 확인된 핵심 사실을 요약했습니다. 숫자와 일정도 그대로 보존했습니다."}

    service.article_service = Article()  # type: ignore[assignment]
    service.llm_service = Llm()  # type: ignore[assignment]
    result = service.summarize_news([row.id])
    refreshed = db.get(NewsItem, row.id)

    assert result.summarized == 1
    assert refreshed is not None and refreshed.summary
    assert refreshed.ai_summary == "기존 AI 필드"
    assert refreshed.ai_importance_score == 77
    assert refreshed.source == "naver_news"
    db.close()


def test_delete_is_physical_and_excludes_same_day_fingerprint() -> None:
    db = make_session(); stock = add_stock(db)
    row = add_news(db, stock.id, url="https://news.example.com/deleted", fingerprint="b" * 64)
    service = NewsService(db)

    deleted, failed = service.delete_news_bulk([row.id])
    assert (deleted, failed) == (1, 0)
    assert db.get(NewsItem, row.id) is None
    assert NewsRepository(db).is_excluded("2026-08-28", stock.id, "b" * 64)
    db.close()


def test_deleted_article_is_skipped_when_collected_again_same_day(monkeypatch) -> None:
    db = make_session(); stock = add_stock(db, code="097230", name="HJ중공업")
    url = "https://news.example.com/deleted-again"
    fingerprint = CollectorService._news_fingerprint(url)
    assert fingerprint is not None
    row = add_news(db, stock.id, url=url, fingerprint=fingerprint[1])
    NewsService(db).delete_news_bulk([row.id])

    class Collector:
        name = "naver_news_collector"

        def collect_by_keyword(self, **_kwargs):
            return {"total": 1, "items": [{
                "title": "HJ중공업 수주 확대", "originallink": url, "pubDate": "Fri, 28 Aug 2026 08:00:00 +0900",
            }]}

    monkeypatch.setattr("backend.app.services.collector_service.NaverNewsCollector", Collector)
    monkeypatch.setattr(CollectorService, "_today_kst", lambda _self: date(2026, 8, 28))
    result = CollectorService(db).collect_news_for_stock(stock.id, ["naver"], 20, "date")

    assert result["saved_count"] == 0
    assert result["excluded_skipped"] == 1
    db.close()


def test_summary_filter_treats_blank_summary_as_unsummarized() -> None:
    db = make_session(); stock = add_stock(db)
    add_news(db, stock.id, url="https://news.example.com/blank", fingerprint="c" * 64, summary="  ")
    add_news(db, stock.id, url="https://news.example.com/done", fingerprint="d" * 64, summary="요약 완료")
    repo = NewsRepository(db)

    assert repo.count(stock.id, None, None, "unsummarized") == 1
    assert repo.count(stock.id, None, None, "summarized") == 1
    db.close()
