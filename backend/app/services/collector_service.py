from __future__ import annotations

import html
import json
import logging
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

logger = logging.getLogger(__name__)


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

    def _normalize_stock_code_for_dart(self, stock_code: str | None) -> str:
        code = (stock_code or "").strip()
        if code.startswith("A") and len(code) == 7 and code[1:].isdigit():
            return code[1:]
        return code

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
        skip_reasons: dict[str, int] = {}
        seen_urls: set[str] = set()

        def add_skip(reason: str, count: int = 1) -> None:
            skip_reasons[reason] = skip_reasons.get(reason, 0) + count

        for item in items:
            url = item.get("originallink") or item.get("link")
            title = self._normalize_text(item.get("title")) or "(no title)"
            if not url:
                skipped_count += 1
                add_skip("missing_url")
                continue
            if url and url in seen_urls:
                skipped_count += 1
                add_skip("duplicate_url")
                continue
            if url and self.news_repo.get_by_url(url):
                skipped_count += 1
                add_skip("duplicate_url")
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
        if skipped_bulk > 0:
            add_skip("duplicate_url", skipped_bulk)
        collected_count = len(items)
        skip_reason_text = ",".join(f"{k}:{v}" for k, v in sorted(skip_reasons.items())) if skip_reasons else "none"

        message = (
            f"keyword={search_keyword}, total={total}, collected_count={collected_count}, "
            f"saved_count={saved_count}, skipped_count={skipped_count}, skip_reasons={{{skip_reason_text}}}"
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
            "skip_reasons": skip_reasons,
        }

    def collect_news_for_watchlist(self, providers: list[str], display: int, sort: str) -> dict:
        self._validate_providers(providers)
        run = self.run_repo.create_running("naver_news_collector", "watchlist")
        rows = self.watchlist_repo.list_with_stock(status=None, keyword=None, market=None, is_active=1, limit=1000, offset=0)
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

        for watchlist, stock in rows:
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
                failed_symbols.append(stock.stock_code)

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

    def collect_news_for_selected_watchlist(
        self,
        stock_ids: list[int],
        providers: list[str],
        display: int,
        sort: str,
    ) -> dict:
        self._validate_providers(providers)
        selected_ids = [int(stock_id) for stock_id in stock_ids if isinstance(stock_id, int)]
        if not selected_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="선택된 종목이 없습니다.")

        active_watchlist_stock_ids = set(self.watchlist_repo.list_active_stock_ids())
        run_codes: list[str] = []
        for stock_id in selected_ids:
            stock = self.stock_repo.get_by_id(stock_id)
            if stock:
                run_codes.append(stock.stock_code)
        target_value = f"selected:{','.join(run_codes)}" if run_codes else "selected:unknown"
        run = self.run_repo.create_running("watchlist_selected_news_collector", target_value)

        success_count = 0
        failed_count = 0
        skipped_count = 0
        results: list[dict] = []

        for stock_id in selected_ids:
            stock = self.stock_repo.get_by_id(stock_id)
            if not stock:
                failed_count += 1
                results.append(
                    {
                        "stock_id": stock_id,
                        "stock_code": "",
                        "stock_name": "",
                        "status": "failed",
                        "collected_count": 0,
                        "saved_count": 0,
                        "skipped_count": 0,
                        "message": "stock not found",
                    }
                )
                continue

            if stock_id not in active_watchlist_stock_ids:
                skipped_count += 1
                results.append(
                    {
                        "stock_id": stock.id,
                        "stock_code": stock.stock_code,
                        "stock_name": stock.stock_name,
                        "normalized_stock_code": self._normalize_stock_code_for_dart(stock.stock_code),
                        "corp_code": None,
                        "status": "skipped",
                        "collected_count": 0,
                        "saved_count": 0,
                        "skipped_count": 0,
                        "message": "활성 관심종목이 아니어서 건너뜀",
                    }
                )
                continue

            try:
                result = self.collect_news_for_stock(
                    stock_id=stock.id,
                    providers=providers,
                    display=display,
                    sort=sort,
                )
                success_count += 1
                results.append(
                    {
                        "stock_id": stock.id,
                        "stock_code": stock.stock_code,
                        "stock_name": stock.stock_name,
                        "status": "success",
                        "collected_count": result["collected_count"],
                        "saved_count": result["saved_count"],
                        "skipped_count": result["skipped_count"],
                        "message": result["message"],
                    }
                )
            except HTTPException as exc:
                failed_count += 1
                results.append(
                    {
                        "stock_id": stock.id,
                        "stock_code": stock.stock_code,
                        "stock_name": stock.stock_name,
                        "status": "failed",
                        "collected_count": 0,
                        "saved_count": 0,
                        "skipped_count": 0,
                        "message": str(exc.detail),
                    }
                )

        requested_count = len(selected_ids)
        if failed_count > 0 and success_count > 0:
            summary = f"선택 관심종목 뉴스 수집 부분 완료 (요청 {requested_count}, 성공 {success_count}, 실패 {failed_count}, 건너뜀 {skipped_count})"
            self.run_repo.mark_partial(run, summary)
        elif failed_count == requested_count and skipped_count == 0:
            summary = f"선택 관심종목 뉴스 수집 실패 (요청 {requested_count}, 성공 0, 실패 {failed_count})"
            self.run_repo.mark_failed(run, summary)
        else:
            summary = f"선택 관심종목 뉴스 수집 완료 (요청 {requested_count}, 성공 {success_count}, 실패 {failed_count}, 건너뜀 {skipped_count})"
            self.run_repo.mark_success(run, summary)

        return {
            "requested_count": requested_count,
            "success_count": success_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "message": summary,
            "results": results,
        }

    def collect_disclosures_for_stock(self, stock_id: int, days: int = DART_DISCLOSURE_DEFAULT_DAYS, page_count: int = DART_PAGE_COUNT) -> dict:
        stock = self.stock_repo.get_by_id(stock_id)
        if not stock:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stock not found")

        run = self.run_repo.create_running("dart_disclosure_collector", stock.stock_code)
        collector = DartDisclosureCollector()

        try:
            collector.ensure_corp_code_file()
            normalized_code = self._normalize_stock_code_for_dart(stock.stock_code)
            corp_code = collector.find_corp_code_by_stock_code(normalized_code)
            if not corp_code:
                message = f"{stock.stock_code} {stock.stock_name}: DART 기업코드를 찾을 수 없어 공시 수집을 건너뜀"
                self.run_repo.mark_success(run, message)
                return {
                    "collector_name": collector.name,
                    "status": "skipped",
                    "target": stock.stock_code,
                    "collected_count": 0,
                    "saved_count": 0,
                    "skipped_count": 1,
                    "message": message,
                    "skip_reasons": {"corp_code_not_found": 1},
                    "normalized_stock_code": normalized_code,
                    "corp_code": None,
                }

            today = self._today_kst()
            safe_days = days if days > 0 else DART_DISCLOSURE_DEFAULT_DAYS
            bgn_de = (today - timedelta(days=safe_days)).strftime("%Y%m%d")
            end_de = today.strftime("%Y%m%d")
            logger.info(
                "[DART] request stock_code=%s normalized_stock_code=%s stock_name=%s corp_code=%s bgn_de=%s end_de=%s page_no=1 page_count=%s",
                stock.stock_code,
                normalized_code,
                stock.stock_name,
                corp_code,
                bgn_de,
                end_de,
                page_count,
            )

            response_payload = collector.collect_by_corp_code(
                corp_code=corp_code,
                bgn_de=bgn_de,
                end_de=end_de,
                page_count=page_count,
            )
            response_raw = response_payload.get("response", {})
            response_preview = json.dumps(response_raw, ensure_ascii=False)[:300]
            logger.info(
                "[DART] response stock_code=%s normalized_stock_code=%s corp_code=%s status=%s message=%s list_count=%s response_preview=%s",
                stock.stock_code,
                normalized_code,
                corp_code,
                response_raw.get("status"),
                response_raw.get("message"),
                len(response_payload.get("list", [])),
                response_preview,
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

            if collected_count == 0:
                message = (
                    f"corp_code={corp_code}, 조회기간={bgn_de[:4]}-{bgn_de[4:6]}-{bgn_de[6:8]}~{end_de[:4]}-{end_de[4:6]}-{end_de[6:8]}, "
                    "DART 정상 응답, 해당 기간 공시 0건, 저장 0건"
                )
            else:
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
                "skip_reasons": {"duplicate_receipt_no": skipped_count} if skipped_count > 0 else {},
                "normalized_stock_code": normalized_code,
                "corp_code": corp_code,
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
        rows = self.watchlist_repo.list_with_stock(status=None, keyword=None, market=None, is_active=1, limit=1000, offset=0)
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

        for watchlist, stock in rows:
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
                failed_symbols.append(stock.stock_code)

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

    def collect_disclosures_for_selected_watchlist(
        self,
        stock_ids: list[int],
        days: int = DART_DISCLOSURE_DEFAULT_DAYS,
        page_count: int = DART_PAGE_COUNT,
    ) -> dict:
        selected_ids = [int(stock_id) for stock_id in stock_ids if isinstance(stock_id, int)]
        if not selected_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="선택된 종목이 없습니다.")

        active_watchlist_stock_ids = set(self.watchlist_repo.list_active_stock_ids())
        run_codes: list[str] = []
        for stock_id in selected_ids:
            stock = self.stock_repo.get_by_id(stock_id)
            if stock:
                run_codes.append(stock.stock_code)
        target_value = f"selected:{','.join(run_codes)}" if run_codes else "selected:unknown"
        run = self.run_repo.create_running("watchlist_selected_disclosure_collector", target_value)

        success_count = 0
        failed_count = 0
        skipped_count = 0
        results: list[dict] = []

        for stock_id in selected_ids:
            stock = self.stock_repo.get_by_id(stock_id)
            if not stock:
                failed_count += 1
                results.append(
                    {
                        "stock_id": stock_id,
                        "stock_code": "",
                        "stock_name": "",
                        "status": "failed",
                        "collected_count": 0,
                        "saved_count": 0,
                        "skipped_count": 0,
                        "message": "stock not found",
                    }
                )
                continue

            if stock_id not in active_watchlist_stock_ids:
                skipped_count += 1
                results.append(
                    {
                        "stock_id": stock.id,
                        "stock_code": stock.stock_code,
                        "stock_name": stock.stock_name,
                        "status": "skipped",
                        "collected_count": 0,
                        "saved_count": 0,
                        "skipped_count": 0,
                        "message": "활성 관심종목이 아니어서 건너뜀",
                    }
                )
                continue

            try:
                result = self.collect_disclosures_for_stock(
                    stock_id=stock.id,
                    days=days,
                    page_count=page_count,
                )
                if result.get("status") == "skipped":
                    skipped_count += 1
                else:
                    success_count += 1
                results.append(
                    {
                        "stock_id": stock.id,
                        "stock_code": stock.stock_code,
                        "stock_name": stock.stock_name,
                        "normalized_stock_code": result.get("normalized_stock_code") or self._normalize_stock_code_for_dart(stock.stock_code),
                        "corp_code": result.get("corp_code"),
                        "status": result.get("status", "success"),
                        "collected_count": result["collected_count"],
                        "saved_count": result["saved_count"],
                        "skipped_count": result["skipped_count"],
                        "message": result["message"],
                    }
                )
            except HTTPException as exc:
                failed_count += 1
                results.append(
                    {
                        "stock_id": stock.id,
                        "stock_code": stock.stock_code,
                        "stock_name": stock.stock_name,
                        "normalized_stock_code": self._normalize_stock_code_for_dart(stock.stock_code),
                        "corp_code": None,
                        "status": "failed",
                        "collected_count": 0,
                        "saved_count": 0,
                        "skipped_count": 0,
                        "message": str(exc.detail),
                    }
                )

        requested_count = len(selected_ids)
        if failed_count > 0 and success_count > 0:
            summary = f"선택 관심종목 공시 수집 부분 완료 (요청 {requested_count}, 성공 {success_count}, 실패 {failed_count}, 건너뜀 {skipped_count})"
            self.run_repo.mark_partial(run, summary)
        elif failed_count == requested_count and skipped_count == 0:
            summary = f"선택 관심종목 공시 수집 실패 (요청 {requested_count}, 성공 0, 실패 {failed_count})"
            self.run_repo.mark_failed(run, summary)
        else:
            summary = f"선택 관심종목 공시 수집 완료 (요청 {requested_count}, 성공 {success_count}, 실패 {failed_count}, 건너뜀 {skipped_count})"
            self.run_repo.mark_success(run, summary)

        return {
            "requested_count": requested_count,
            "success_count": success_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "message": summary,
            "results": results,
        }



