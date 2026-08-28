from __future__ import annotations

import html
import hashlib
import logging
import re
import unicodedata
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.collectors.disclosures.dart_disclosure_collector import DartDisclosureCollector
from backend.app.collectors.news.naver_news_collector import NaverNewsCollector
from backend.app.core.config import DART_DISCLOSURE_DEFAULT_DAYS, DART_PAGE_COUNT, now_kst
from backend.app.entities.disclosure import Disclosure
from backend.app.entities.news import NewsItem
from backend.app.repositories.collection_run_repository import CollectionRunRepository
from backend.app.repositories.disclosure_repository import DisclosureRepository
from backend.app.repositories.news_repository import NewsRepository
from backend.app.repositories.stock_repository import StockRepository
from backend.app.repositories.watchlist_repository import WatchlistRepository

logger = logging.getLogger(__name__)


class CollectorService:
    NEWS_INITIAL_LIMIT = 20
    NEWS_SAFETY_DAYS = 90
    NEWS_PROVIDER_PAGE_SIZE = 100
    NEWS_PROVIDER_MAX_RESULTS = 1000

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

    @staticmethod
    def _normalize_news_match_text(value: str | None) -> str:
        normalized = unicodedata.normalize("NFKC", value or "")
        return re.sub(r"\s+", " ", normalized).strip().casefold()

    def _news_published_date(self, pub_date: str | None) -> date | None:
        converted = self._convert_pub_date(pub_date)
        if not converted:
            return None
        try:
            return datetime.fromisoformat(converted).date()
        except ValueError:
            return None

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

    @staticmethod
    def _canonicalize_news_url(value: str | None) -> str | None:
        raw = (value or "").strip().rstrip(".,;:!?)")
        if not raw:
            return None
        try:
            parts = urlsplit(raw)
            if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
                return None
            blocked = {"fbclid", "gclid", "igshid", "mc_cid", "mc_eid"}
            query = [(key, val) for key, val in parse_qsl(parts.query, keep_blank_values=True)
                     if not key.lower().startswith("utm_") and key.lower() not in blocked]
            return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/") or "/", urlencode(sorted(query)), ""))
        except Exception:
            return None

    @classmethod
    def _news_fingerprint(cls, url: str) -> tuple[str, str] | None:
        canonical = cls._canonicalize_news_url(url)
        if not canonical:
            return None
        return canonical, hashlib.sha256(canonical.encode("utf-8")).hexdigest()

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
        official_stock_name = (stock.stock_name or "").strip()
        search_keyword = (keyword or official_stock_name).strip()
        if not search_keyword:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="keyword is empty")
        normalized_stock_name = self._normalize_news_match_text(official_stock_name)
        if not normalized_stock_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="official stock name is empty")

        today = self._today_kst()
        cursor_text = self.news_repo.get_collection_cursor(stock.id)
        try:
            cursor_date = date.fromisoformat(cursor_text) if cursor_text else None
        except ValueError:
            cursor_date = None
        if cursor_date is None:
            mode = "INITIAL"
            from_date = today - timedelta(days=self.NEWS_SAFETY_DAYS - 1)
            save_limit = min(max(int(display), 1), self.NEWS_INITIAL_LIMIT)
        elif cursor_date >= today:
            mode = "SAME_DAY"
            from_date = today
            save_limit = max(int(display), 1)
        else:
            mode = "INCREMENTAL"
            from_date = cursor_date + timedelta(days=1)
            save_limit = max(int(display), 1)
        to_date = today

        run = self.run_repo.create_running("naver_news_collector", target)
        collector = NaverNewsCollector()

        news_to_save: list[NewsItem] = []
        skipped_count = 0
        skip_reasons: dict[str, int] = {}
        seen_fingerprints: set[str] = set()
        target_date = today.isoformat()
        self.news_repo.cleanup_exclusions(target_date)
        scanned_count = 0
        matched_count = 0
        total = 0

        def add_skip(reason: str, count: int = 1) -> None:
            skip_reasons[reason] = skip_reasons.get(reason, 0) + count

        try:
            start = 1
            while start <= self.NEWS_PROVIDER_MAX_RESULTS and len(news_to_save) < save_limit:
                response_payload = collector.collect_by_keyword(
                    keyword=search_keyword,
                    display=self.NEWS_PROVIDER_PAGE_SIZE,
                    start=start,
                    sort=sort,
                )
                items = list(response_payload.get("items") or [])
                total = int(response_payload.get("total") or 0)
                if not items:
                    break

                scanned_count += len(items)
                reached_older_range = False
                for item in items:
                    published_date = self._news_published_date(item.get("pubDate"))
                    if published_date is None:
                        skipped_count += 1
                        add_skip("invalid_date")
                        continue
                    if published_date > to_date:
                        continue
                    if published_date < from_date:
                        reached_older_range = True
                        continue

                    title = self._normalize_text(item.get("title"))
                    if not title:
                        skipped_count += 1
                        add_skip("no_title")
                        continue
                    if normalized_stock_name not in self._normalize_news_match_text(title):
                        skipped_count += 1
                        add_skip("name_mismatch")
                        continue
                    matched_count += 1

                    raw_url = item.get("originallink") or item.get("link")
                    fingerprint_result = self._news_fingerprint(raw_url)
                    if not fingerprint_result:
                        skipped_count += 1
                        add_skip("missing_url")
                        continue
                    url, fingerprint = fingerprint_result
                    if fingerprint in seen_fingerprints:
                        skipped_count += 1
                        add_skip("duplicate_url")
                        continue
                    if self.news_repo.is_excluded(target_date, stock.id, fingerprint):
                        skipped_count += 1
                        add_skip("deleted_today")
                        continue
                    if self.news_repo.get_by_stock_and_fingerprint(stock.id, fingerprint):
                        skipped_count += 1
                        add_skip("duplicate_url")
                        continue
                    seen_fingerprints.add(fingerprint)

                    now = now_kst()
                    news_to_save.append(NewsItem(
                        stock_id=stock.id,
                        title=title,
                        source=None,
                        url=url,
                        article_fingerprint=fingerprint,
                        published_at=self._convert_pub_date(item.get("pubDate")),
                        collected_at=now,
                        raw_text_path=None,
                        summary=None,
                        sentiment=None,
                        importance_score=0,
                        created_at=now,
                    ))
                    if len(news_to_save) >= save_limit:
                        break

                if len(news_to_save) >= save_limit:
                    break
                if sort == "date" and reached_older_range:
                    break
                start += self.NEWS_PROVIDER_PAGE_SIZE
                if start > min(total, self.NEWS_PROVIDER_MAX_RESULTS):
                    break
        except ValueError as exc:
            self.run_repo.mark_failed(run, str(exc))
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except Exception as exc:
            self.run_repo.mark_failed(run, f"collector error: {exc}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="news collection failed") from exc

        saved_count, skipped_bulk = self.news_repo.bulk_create_skip_duplicates(news_to_save)
        skipped_count += skipped_bulk
        if skipped_bulk > 0:
            add_skip("duplicate_url", skipped_bulk)
        collected_count = scanned_count
        completed_at = now_kst()
        self.news_repo.update_collection_cursor(stock.id, to_date.isoformat(), completed_at)
        skip_reason_text = ",".join(f"{k}:{v}" for k, v in sorted(skip_reasons.items())) if skip_reasons else "none"

        message = (
            f"keyword={search_keyword}, mode={mode}, range={from_date.isoformat()}..{to_date.isoformat()}, "
            f"total={total}, scanned_count={scanned_count}, matched_count={matched_count}, "
            f"saved_count={saved_count}, skipped_count={skipped_count}, skip_reasons={{{skip_reason_text}}}"
        )
        self.run_repo.mark_success(run, message)

        return {
            "collector_name": collector.name,
            "status": "success",
            "target": target,
            "mode": mode,
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "collected_count": collected_count,
            "scanned_count": scanned_count,
            "matched_count": matched_count,
            "saved_count": saved_count,
            "skipped_count": skipped_count,
            "name_mismatch_skipped": skip_reasons.get("name_mismatch", 0),
            "duplicate_skipped": skip_reasons.get("duplicate_url", 0),
            "excluded_skipped": skip_reasons.get("deleted_today", 0),
            "invalid_skipped": skip_reasons.get("no_title", 0) + skip_reasons.get("invalid_date", 0) + skip_reasons.get("missing_url", 0),
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
                        "mode": result["mode"],
                        "from_date": result["from_date"],
                        "to_date": result["to_date"],
                        "scanned_count": result["scanned_count"],
                        "matched_count": result["matched_count"],
                        "name_mismatch_skipped": result["name_mismatch_skipped"],
                        "duplicate_skipped": result["duplicate_skipped"],
                        "excluded_skipped": result["excluded_skipped"],
                        "invalid_skipped": result["invalid_skipped"],
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



