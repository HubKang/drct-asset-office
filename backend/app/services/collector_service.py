from __future__ import annotations

import html
import json
import os
import re
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.collectors.disclosures.dart_disclosure_collector import DartDisclosureCollector
from backend.app.collectors.news.naver_news_collector import NaverNewsCollector
from backend.app.core.config import DART_DISCLOSURE_DEFAULT_DAYS, DART_PAGE_COUNT, PROJECT_ROOT, now_kst
from backend.app.entities.disclosure import Disclosure
from backend.app.entities.news import NewsItem
from backend.app.repositories.collection_run_repository import CollectionRunRepository
from backend.app.repositories.disclosure_repository import DisclosureRepository
from backend.app.repositories.news_repository import NewsRepository
from backend.app.repositories.stock_repository import StockRepository
from backend.app.repositories.watchlist_repository import WatchlistRepository


class CollectorService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.stock_repo = StockRepository(db)
        self.watchlist_repo = WatchlistRepository(db)
        self.news_repo = NewsRepository(db)
        self.disclosure_repo = DisclosureRepository(db)
        self.run_repo = CollectionRunRepository(db)

    def _validate_providers(self, providers: list[str]) -> None:
        for provider in providers:
            if provider != "naver":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="only naver provider is supported")

    def _normalize_text(self, value: str | None) -> str | None:
        if not value:
            return None
        cleaned = re.sub(r"<[^>]+>", "", value)
        cleaned = html.unescape(cleaned)
        return cleaned.strip()

    def _convert_pub_date(self, pub_date: str | None) -> str | None:
        if not pub_date:
            return None
        try:
            dt = parsedate_to_datetime(pub_date)
            if dt.tzinfo is not None:
                dt = dt.astimezone(ZoneInfo("Asia/Seoul"))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return pub_date

    def _format_dart_disclosed_at(self, rcept_dt: str | None) -> str | None:
        if not rcept_dt:
            return None
        value = rcept_dt.strip()
        if len(value) == 8 and value.isdigit():
            return f"{value[:4]}-{value[4:6]}-{value[6:8]} 00:00:00"
        if len(value) == 10 and value[4] == "-" and value[7] == "-":
            return f"{value} 00:00:00"
        return value

    def _today_kst(self) -> date:
        return datetime.now(ZoneInfo("Asia/Seoul")).date()

    def _news_raw_dir(self) -> Path:
        raw_dir = os.getenv("NEWS_RAW_DIR", "./data/raw/news")
        base = Path(raw_dir)
        if not base.is_absolute():
            base = PROJECT_ROOT / base
        path = base / "naver"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _save_news_raw_response(self, stock_code: str, response_payload: dict) -> str:
        raw_dir = self._news_raw_dir()
        file_name = f"{stock_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_response.json"
        path = raw_dir / file_name
        path.write_text(json.dumps(response_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")

    def collect_news_for_stock(
        self,
        stock_id: int,
        providers: list[str],
        display: int,
        sort: str,
        keyword: str | None = None,
    ) -> dict:
        self._validate_providers(providers)

        stock = self.stock_repo.get_by_id(stock_id)
        if not stock:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stock not found")

        target = stock.stock_code
        search_keyword = (keyword or stock.stock_name or "").strip()
        if not search_keyword:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="keyword is empty")

        run = self.run_repo.create_running("naver_news_collector", target)
        collector = NaverNewsCollector()

        try:
            response_payload = collector.collect_by_keyword(keyword=search_keyword, display=display, start=1, sort=sort)
            items = response_payload.get("items", [])
            total = int(response_payload.get("total") or 0)
        except ValueError as exc:
            self.run_repo.mark_failed(run, str(exc))
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except Exception as exc:
            self.run_repo.mark_failed(run, f"collector error: {exc}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="news collection failed") from exc

        response_raw_path = self._save_news_raw_response(target, response_payload)

        news_to_save: list[NewsItem] = []
        skipped_count = 0
        seen_urls: set[str] = set()

        for item in items:
            title = self._normalize_text(item.get("title")) or "(no title)"
            url = item.get("originallink") or item.get("link")
            if url and url in seen_urls:
                skipped_count += 1
                continue
            if url and self.news_repo.get_by_url(url):
                skipped_count += 1
                continue
            if url:
                seen_urls.add(url)

            now = now_kst()
            news_to_save.append(
                NewsItem(
                    stock_id=stock.id,
                    title=title,
                    source="naver_news",
                    url=url,
                    published_at=self._convert_pub_date(item.get("pubDate")),
                    collected_at=now,
                    raw_text_path=response_raw_path,
                    summary=self._normalize_text(item.get("description")),
                    sentiment=None,
                    importance_score=0,
                    created_at=now,
                )
            )

        saved_count, skipped_bulk = self.news_repo.bulk_create_skip_duplicates(news_to_save)
        skipped_count += skipped_bulk
        collected_count = len(items)

        message = (
            f"keyword={search_keyword}, total={total}, collected_count={collected_count}, "
            f"saved_count={saved_count}, skipped_count={skipped_count}"
        )
        self.run_repo.mark_success(run, message)

        return {
            "collector_name": collector.name,
            "status": "success",
            "target": target,
            "collected_count": collected_count,
            "saved_count": saved_count,
            "skipped_count": skipped_count,
            "message": message,
        }

    def collect_news_for_watchlist(self, providers: list[str], display: int, sort: str) -> dict:
        self._validate_providers(providers)
        run = self.run_repo.create_running("naver_news_collector", "watchlist")
        rows = self.watchlist_repo.list_with_stock(status=None, keyword=None, limit=1000, offset=0)
        if not rows:
            self.run_repo.mark_success(run, "watchlist is empty")
            return {
                "collector_name": "naver_news_collector",
                "status": "success",
                "target": "watchlist",
                "collected_count": 0,
                "saved_count": 0,
                "skipped_count": 0,
                "message": "watchlist is empty",
            }

        collected_total = 0
        saved_total = 0
        skipped_total = 0
        failed_symbols: list[str] = []

        for watchlist, stock_code, _stock_name in rows:
            try:
                result = self.collect_news_for_stock(
                    stock_id=watchlist.stock_id,
                    providers=providers,
                    display=display,
                    sort=sort,
                )
                collected_total += result["collected_count"]
                saved_total += result["saved_count"]
                skipped_total += result["skipped_count"]
            except HTTPException:
                failed_symbols.append(stock_code)

        if failed_symbols:
            msg = f"partial success with child runs, failed: {', '.join(failed_symbols)}"
            self.run_repo.mark_partial(run, msg)
            status_value = "partial"
        else:
            msg = (
                f"watchlist completed with child runs, collected_count={collected_total}, "
                f"saved_count={saved_total}, skipped_count={skipped_total}"
            )
            self.run_repo.mark_success(run, msg)
            status_value = "success"

        return {
            "collector_name": "naver_news_collector",
            "status": status_value,
            "target": "watchlist",
            "collected_count": collected_total,
            "saved_count": saved_total,
            "skipped_count": skipped_total,
            "message": msg,
        }

    def collect_disclosures_for_stock(self, stock_id: int, days: int = DART_DISCLOSURE_DEFAULT_DAYS, page_count: int = DART_PAGE_COUNT) -> dict:
        stock = self.stock_repo.get_by_id(stock_id)
        if not stock:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stock not found")

        run = self.run_repo.create_running("dart_disclosure_collector", stock.stock_code)
        collector = DartDisclosureCollector()

        try:
            collector.ensure_corp_code_file()
            corp_code = collector.find_corp_code_by_stock_code(stock.stock_code)
            if not corp_code:
                self.run_repo.mark_failed(run, f"corp_code not found for stock_code={stock.stock_code}")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="corp_code not found")

            today = self._today_kst()
            safe_days = days if days > 0 else DART_DISCLOSURE_DEFAULT_DAYS
            bgn_de = (today - timedelta(days=safe_days)).strftime("%Y%m%d")
            end_de = today.strftime("%Y%m%d")

            response_payload = collector.collect_by_corp_code(
                corp_code=corp_code,
                bgn_de=bgn_de,
                end_de=end_de,
                page_count=page_count,
            )
            response_raw_path = collector.save_disclosure_response(stock.stock_code, response_payload)
            items = response_payload.get("list", [])

            disclosure_to_save: list[Disclosure] = []
            for item in items:
                receipt_no = (item.get("rcept_no") or "").strip()
                report_nm = (item.get("report_nm") or "").strip() or "(no title)"
                disclosure_type = (item.get("pblntf_detail_ty") or item.get("pblntf_ty") or "").strip() or None
                disclosed_at = self._format_dart_disclosed_at(item.get("rcept_dt"))
                url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt_no}" if receipt_no else None

                disclosure_to_save.append(
                    Disclosure(
                        stock_id=stock.id,
                        dart_receipt_no=receipt_no or None,
                        disclosure_title=report_nm,
                        disclosure_type=disclosure_type,
                        disclosed_at=disclosed_at,
                        url=url,
                        raw_text_path=response_raw_path,
                        summary=None,
                        importance_score=0,
                        created_at=now_kst(),
                    )
                )

            saved_count, skipped_count = self.disclosure_repo.bulk_create_skip_duplicates(disclosure_to_save)
            collected_count = len(items)

            message = (
                f"corp_code={corp_code}, collected_count={collected_count}, "
                f"saved_count={saved_count}, skipped_count={skipped_count}"
            )
            self.run_repo.mark_success(run, message)

            return {
                "collector_name": collector.name,
                "status": "success",
                "target": stock.stock_code,
                "collected_count": collected_count,
                "saved_count": saved_count,
                "skipped_count": skipped_count,
                "message": message,
            }
        except HTTPException:
            raise
        except ValueError as exc:
            self.run_repo.mark_failed(run, str(exc))
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except Exception as exc:
            self.run_repo.mark_failed(run, f"collector error: {exc}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="disclosure collection failed") from exc

    def collect_disclosures_for_watchlist(self, days: int = DART_DISCLOSURE_DEFAULT_DAYS, page_count: int = DART_PAGE_COUNT) -> dict:
        run = self.run_repo.create_running("dart_disclosure_collector", "watchlist")
        rows = self.watchlist_repo.list_with_stock(status=None, keyword=None, limit=1000, offset=0)
        if not rows:
            self.run_repo.mark_success(run, "watchlist is empty")
            return {
                "collector_name": "dart_disclosure_collector",
                "status": "success",
                "target": "watchlist",
                "collected_count": 0,
                "saved_count": 0,
                "skipped_count": 0,
                "message": "watchlist is empty",
            }

        collected_total = 0
        saved_total = 0
        skipped_total = 0
        failed_symbols: list[str] = []

        for watchlist, stock_code, _stock_name in rows:
            try:
                result = self.collect_disclosures_for_stock(
                    stock_id=watchlist.stock_id,
                    days=days,
                    page_count=page_count,
                )
                collected_total += result["collected_count"]
                saved_total += result["saved_count"]
                skipped_total += result["skipped_count"]
            except HTTPException:
                failed_symbols.append(stock_code)

        if failed_symbols:
            msg = (
                f"partial success with child runs, failed: {', '.join(failed_symbols)}, "
                f"collected_count={collected_total}, saved_count={saved_total}, skipped_count={skipped_total}"
            )
            self.run_repo.mark_partial(run, msg)
            status_value = "partial"
        else:
            msg = (
                f"watchlist completed with child runs, collected_count={collected_total}, "
                f"saved_count={saved_total}, skipped_count={skipped_total}"
            )
            self.run_repo.mark_success(run, msg)
            status_value = "success"

        return {
            "collector_name": "dart_disclosure_collector",
            "status": status_value,
            "target": "watchlist",
            "collected_count": collected_total,
            "saved_count": saved_total,
            "skipped_count": skipped_total,
            "message": msg,
        }



