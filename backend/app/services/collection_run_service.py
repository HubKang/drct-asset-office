from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.repositories.collection_run_repository import CollectionRunRepository


class CollectionRunService:
    def __init__(self, db: Session) -> None:
        self.repo = CollectionRunRepository(db)

    @staticmethod
    def _collector_meta(collector_name: str) -> tuple[str, str, str, str, str]:
        """
        Returns:
        display_name, run_type, run_type_label, collector_group, collector_group_label
        """
        mapping: dict[str, tuple[str, str, str, str, str]] = {
            "watchlist_selected_disclosure_collector": ("선택 공시 수집", "selected_wrapper", "선택 수집 작업", "disclosure", "공시"),
            "dart_disclosure_collector": ("DART 공시 수집", "external_collector", "외부 수집기", "disclosure", "공시"),
            "watchlist_selected_news_collector": ("선택 뉴스 수집", "selected_wrapper", "선택 수집 작업", "news", "뉴스"),
            "naver_news_collector": ("네이버 뉴스 수집", "external_collector", "외부 수집기", "news", "뉴스"),
            "watchlist_selected_price_collector": ("선택 캔들 수집", "selected_wrapper", "선택 수집 작업", "price", "가격·캔들"),
            "pykrx_price_collector": ("PyKRX 가격·캔들 수집", "external_collector", "외부 수집기", "price", "가격·캔들"),
            "watchlist_selected_market_metric_collector": ("선택 시장지표 갱신", "selected_wrapper", "선택 수집 작업", "market_metric", "시장지표"),
            "kis_market_metrics_collector": ("KIS 시장지표 수집", "external_collector", "외부 수집기", "market_metric", "시장지표"),
            "technical_indicator_calculator": ("기술적 지표 재계산", "processor", "후처리 작업", "technical_indicator", "기술지표"),
        }
        return mapping.get(collector_name, (collector_name, "unknown", "기타", "unknown", "기타"))

    def _with_display_fields(self, run):
        display_name, run_type, run_type_label, collector_group, collector_group_label = self._collector_meta(
            run.collector_name
        )
        # response_model(from_attributes=True)에서 읽히도록 런타임 속성을 붙인다.
        run.collector_display_name = display_name
        run.run_type = run_type
        run.run_type_label = run_type_label
        run.collector_group = collector_group
        run.collector_group_label = collector_group_label
        return run

    def list_collection_runs(
        self,
        collector_name: str | None,
        status_value: str | None,
        target: str | None,
        limit: int,
        offset: int,
    ):
        runs = self.repo.list(
            collector_name=collector_name,
            status=status_value,
            target=target,
            limit=limit,
            offset=offset,
        )
        return [self._with_display_fields(run) for run in runs]

    def get_collection_run(self, run_id: int):
        run = self.repo.get_by_id(run_id)
        if not run:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="collection run not found")
        return self._with_display_fields(run)
