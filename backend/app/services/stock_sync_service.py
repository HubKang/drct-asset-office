from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.collectors.stocks.krx_stock_collector import KrxStockCollector
from backend.app.core.config import now_kst
from backend.app.entities.stock import Stock
from backend.app.repositories.collection_run_repository import CollectionRunRepository
from backend.app.repositories.stock_repository import StockRepository
from backend.app.schemas.stock_sync_schema import StockSyncResponse


@dataclass
class StockSyncCounts:
    raw_fetched_count: int = 0
    eligible_count: int = 0
    type_counts: dict[str, int] | None = None
    type_samples: dict[str, list[dict[str, str | None]]] | None = None
    fetched_count: int = 0
    inserted_count: int = 0
    updated_count: int = 0
    reactivated_count: int = 0
    deactivated_count: int = 0
    skipped_count: int = 0
    error_count: int = 0


class StockSyncService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.stock_repo = StockRepository(db)
        self.run_repo = CollectionRunRepository(db)
        self.collector = KrxStockCollector()

    def sync_stocks(
        self,
        markets: list[str],
        dry_run: bool = False,
        deactivate_missing: bool = True,
        include_security_types: list[str] | None = None,
    ) -> StockSyncResponse:
        if not self.collector.service_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "DATA_API_SERVICE_KEY is not configured. "
                    "Add it to .env. For requests params, use the Decoding key."
                ),
            )

        normalized_markets = self._normalize_markets(markets)
        included_types = self._normalize_security_types(include_security_types)
        started_at = now_kst()
        target = ",".join(normalized_markets)
        run = self.run_repo.create_running("krx_stock_master_sync", target) if not dry_run else None
        counts = StockSyncCounts(type_counts={}, type_samples={})

        try:
            all_fetched = self.collector.collect_all()
            counts.raw_fetched_count = len(all_fetched)
            fetched_by_market: dict[str, list[dict[str, str | None]]] = {}
            for market in normalized_markets:
                market_items = [i for i in all_fetched if i.get("market") == market]
                if len(market_items) == 0:
                    raise ValueError(f"KRX API returned 0 items for market={market}")
                fetched_by_market[market] = market_items

            all_market_items = [item for market in normalized_markets for item in fetched_by_market[market]]
            type_counts: dict[str, int] = {}
            for item in all_market_items:
                st = str(item.get("security_type") or "other")
                type_counts[st] = type_counts.get(st, 0) + 1
            counts.type_counts = type_counts
            counts.type_samples = self._build_type_samples(all_market_items)

            eligible_items = [item for item in all_market_items if str(item.get("security_type") or "other") in included_types]
            counts.eligible_count = len(eligible_items)
            counts.fetched_count = counts.eligible_count

            existing_map = {
                stock.stock_code: stock
                for stock in self.stock_repo.get_by_codes(
                    sorted({item["stock_code"] for item in eligible_items if item.get("stock_code")})
                )
            }

            sync_time = now_kst()
            for item in eligible_items:
                code = (item.get("stock_code") or "").strip()
                if not code:
                    counts.skipped_count += 1
                    continue
                existing = existing_map.get(code)
                if not existing:
                    counts.inserted_count += 1
                    if not dry_run:
                        created = Stock(
                            stock_code=code,
                            stock_name=item.get("stock_name") or code,
                            market=item.get("market"),
                            sector=None,
                            industry=None,
                            isin_code=item.get("isin_code"),
                            corp_name=item.get("corp_name"),
                            corp_reg_no=item.get("corp_reg_no"),
                            security_type=item.get("security_type"),
                            last_synced_at=sync_time,
                            source=item.get("source") or "KRX_LISTED_INFO",
                            is_active=1,
                            created_at=sync_time,
                            updated_at=sync_time,
                        )
                        self.db.add(created)
                    continue

                was_inactive = existing.is_active == 0
                changed = False
                fields = {
                    "stock_name": item.get("stock_name") or existing.stock_name,
                    "market": item.get("market") or existing.market,
                    "isin_code": item.get("isin_code"),
                    "corp_name": item.get("corp_name") or existing.corp_name,
                    "corp_reg_no": item.get("corp_reg_no"),
                    "security_type": item.get("security_type") or existing.security_type,
                    "source": item.get("source") or existing.source or "KRX_LISTED_INFO",
                }
                field_changes: dict[str, str | None] = {}
                for key, value in fields.items():
                    if getattr(existing, key) != value:
                        field_changes[key] = value
                        changed = True

                if was_inactive:
                    counts.reactivated_count += 1
                    changed = True

                if changed:
                    if not dry_run:
                        for key, value in field_changes.items():
                            setattr(existing, key, value)
                        if was_inactive:
                            existing.is_active = 1
                        existing.last_synced_at = sync_time
                        existing.updated_at = sync_time
                    if not was_inactive:
                        counts.updated_count += 1
                else:
                    counts.skipped_count += 1

            if deactivate_missing:
                for market in normalized_markets:
                    valid_codes = {
                        item["stock_code"]
                        for item in eligible_items
                        if item.get("stock_code") and item.get("market") == market
                    }
                    active_stocks = self.stock_repo.list_active_by_market(market, security_types=included_types)
                    for stock in active_stocks:
                        if stock.security_type is None:
                            continue
                        if stock.stock_code in valid_codes:
                            continue
                        counts.deactivated_count += 1
                        if not dry_run:
                            stock.is_active = 0
                            stock.last_synced_at = sync_time
                            stock.updated_at = sync_time

            if not dry_run:
                self.db.commit()

            finished_at = now_kst()
            message = self._build_message(counts, normalized_markets, dry_run, deactivate_missing)
            if run:
                self.run_repo.mark_success(run, message)

            return StockSyncResponse(
                markets=normalized_markets,
                dry_run=dry_run,
                raw_fetched_count=counts.raw_fetched_count,
                eligible_count=counts.eligible_count,
                type_counts=counts.type_counts or {},
                type_samples=counts.type_samples or {},
                fetched_count=counts.fetched_count,
                inserted_count=counts.inserted_count,
                updated_count=counts.updated_count,
                reactivated_count=counts.reactivated_count,
                deactivated_count=counts.deactivated_count,
                skipped_count=counts.skipped_count,
                error_count=counts.error_count,
                started_at=started_at,
                finished_at=finished_at,
                message=message,
            )
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            counts.error_count += 1
            finished_at = now_kst()
            message = f"stock sync failed: {exc}"
            if run:
                self.run_repo.mark_failed(run, message)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=message) from exc

    def _normalize_markets(self, markets: list[str]) -> list[str]:
        if not markets:
            return ["KOSPI", "KOSDAQ"]
        normalized: list[str] = []
        for value in markets:
            v = (value or "").strip().upper()
            if v == "ALL":
                return ["KOSPI", "KOSDAQ"]
            if v in {"KOSPI", "KOSDAQ"} and v not in normalized:
                normalized.append(v)
        if not normalized:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="markets must include KOSPI/KOSDAQ/ALL")
        return normalized

    def _build_message(self, counts: StockSyncCounts, markets: list[str], dry_run: bool, deactivate_missing: bool) -> str:
        prefix = "dry_run preview completed" if dry_run else "stock sync completed"
        return (
            f"{prefix} markets={','.join(markets)} deactivate_missing={deactivate_missing} "
            f"raw_fetched={counts.raw_fetched_count} eligible={counts.eligible_count} "
            f"types={counts.type_counts or {}} "
            f"fetched={counts.fetched_count} inserted={counts.inserted_count} "
            f"updated={counts.updated_count} reactivated={counts.reactivated_count} "
            f"deactivated={counts.deactivated_count} skipped={counts.skipped_count} errors={counts.error_count}"
        )

    def _normalize_security_types(self, include_security_types: list[str] | None) -> list[str]:
        allowed = {"common_stock", "preferred_stock", "etf", "etn", "spac", "reit", "other"}
        values = include_security_types or ["common_stock"]
        normalized: list[str] = []
        for value in values:
            v = (value or "").strip().lower()
            if v in allowed and v not in normalized:
                normalized.append(v)
        if not normalized:
            return ["common_stock"]
        return normalized

    def _build_type_samples(self, items: list[dict[str, str | None]]) -> dict[str, list[dict[str, str | None]]]:
        targets = ["common_stock", "etf", "etn", "preferred_stock", "reit", "spac", "other"]
        samples: dict[str, list[dict[str, str | None]]] = {key: [] for key in targets}
        for item in items:
            st = str(item.get("security_type") or "other")
            if st not in samples:
                continue
            if len(samples[st]) >= 20:
                continue
            samples[st].append(
                {
                    "stock_code": item.get("stock_code"),
                    "stock_name": item.get("stock_name"),
                    "market": item.get("market"),
                    "security_type": st,
                    "isin_code": item.get("isin_code"),
                    "corp_name": item.get("corp_name"),
                }
            )
            if all(len(samples[key]) >= 20 for key in targets):
                break
        return samples
