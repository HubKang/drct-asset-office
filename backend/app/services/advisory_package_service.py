from __future__ import annotations

from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.entities.analysis_source_item import AnalysisSourceItem
from backend.app.entities.research_report import ResearchReport
from backend.app.repositories.analysis_source_item_repository import AnalysisSourceItemRepository
from backend.app.repositories.disclosure_repository import DisclosureRepository
from backend.app.repositories.news_repository import NewsRepository
from backend.app.repositories.research_report_repository import ResearchReportRepository
from backend.app.repositories.stock_repository import StockRepository
from backend.app.schemas.advisory_package_schema import AdvisoryPackageGenerateResponse


PackageType = Literal["swing", "long_term"]


class AdvisoryPackageService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.stock_repo = StockRepository(db)
        self.news_repo = NewsRepository(db)
        self.disclosure_repo = DisclosureRepository(db)
        self.report_repo = ResearchReportRepository(db)
        self.analysis_source_repo = AnalysisSourceItemRepository(db)

    def generate_package(
        self,
        stock_id: int,
        news_ids: list[int],
        disclosure_ids: list[int],
        title: str,
        purpose: str,
        package_type: PackageType,
    ) -> AdvisoryPackageGenerateResponse:
        stock = self.stock_repo.get_by_id(stock_id)
        if not stock:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stock not found")

        safe_news_ids = sorted(set(news_ids or []))
        safe_disclosure_ids = sorted(set(disclosure_ids or []))

        selected_news = self.news_repo.list_by_ids(stock_id=stock_id, ids=safe_news_ids) if safe_news_ids else []
        selected_disclosures = (
            self.disclosure_repo.list_by_ids(stock_id=stock_id, ids=safe_disclosure_ids) if safe_disclosure_ids else []
        )

        if safe_news_ids and len(selected_news) != len(safe_news_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="some news_ids do not belong to stock_id or do not exist",
            )
        if safe_disclosure_ids and len(selected_disclosures) != len(safe_disclosure_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="some disclosure_ids do not belong to stock_id or do not exist",
            )

        created_at = now_kst()
        markdown_content = self._build_markdown(
            package_type=package_type,
            stock=stock,
            purpose=purpose,
            created_at=created_at,
            selected_news=selected_news,
            selected_disclosures=selected_disclosures,
        )
        report_type = "gpt_swing_advisory_package" if package_type == "swing" else "gpt_long_term_advisory_package"
        report_summary = "GPT Plus 스윙투자 자문 패키지" if package_type == "swing" else "GPT Plus 장기투자 자문 패키지"

        report = self.report_repo.create(
            ResearchReport(
                stock_id=stock.id,
                report_type=report_type,
                title=title.strip(),
                report_date=created_at.split(" ")[0],
                summary=report_summary,
                markdown_content=markdown_content,
                markdown_path="db://markdown_content",
                generated_by="drct-asset-office",
                created_at=created_at,
            )
        )

        source_rows = [
            AnalysisSourceItem(
                report_id=report.id,
                stock_id=stock.id,
                source_type="news",
                source_id=item.id,
                used_stage="gpt_advisory_package",
                created_at=created_at,
            )
            for item in selected_news
        ] + [
            AnalysisSourceItem(
                report_id=report.id,
                stock_id=stock.id,
                source_type="disclosure",
                source_id=item.id,
                used_stage="gpt_advisory_package",
                created_at=created_at,
            )
            for item in selected_disclosures
        ]
        self.analysis_source_repo.create_many(source_rows)

        return AdvisoryPackageGenerateResponse(
            id=report.id,
            stock_id=report.stock_id or stock_id,
            title=report.title,
            report_type=report.report_type,
            package_type=package_type,
            markdown_content=markdown_content,
            created_at=report.created_at,
        )

    def _build_markdown(
        self,
        package_type: PackageType,
        stock,
        purpose: str,
        created_at: str,
        selected_news: list,
        selected_disclosures: list,
    ) -> str:
        if package_type == "swing":
            return self._build_swing_markdown(stock, purpose, created_at, selected_news, selected_disclosures)
        return self._build_long_term_markdown(stock, purpose, created_at, selected_news, selected_disclosures)

    def _build_swing_markdown(self, stock, purpose: str, created_at: str, selected_news: list, selected_disclosures: list) -> str:
        lines: list[str] = []
        lines.append("# DrCT에셋 GPT 스윙투자 자문 패키지")
        lines.append("")
        lines.append("## 1. 사용자 목표")
        lines.append("- 투자 유형: 2주 이내 스윙투자")
        lines.append("- 목표: 눌림목 구간에서 강한 주도주 가능성 검토")
        lines.append(f"- 사용자가 입력한 검토 목적: {purpose.strip()}")
        lines.append("")
        lines.extend(self._common_target_section(stock, created_at))
        lines.append("")
        lines.append("## 3. 제공 데이터 범위")
        lines.append("### 포함된 데이터")
        lines.append("- 선택 뉴스 요약")
        lines.append("- 선택 공시 요약")
        lines.append("- AI 감성/중요도/태그")
        lines.append("- 공시 이벤트/리스크")
        lines.append("")
        lines.append("### 현재 포함되지 않은 데이터")
        lines.append("- 현재가")
        lines.append("- 금일 등락률")
        lines.append("- 거래량")
        lines.append("- 거래대금")
        lines.append("- 3분봉 흐름")
        lines.append("- 외국인/기관 수급")
        lines.append("- 검색량/커뮤니티 관심도")
        lines.append("")
        lines.append("중요 지시:")
        lines.append("제공되지 않은 시세, 수급, 3분봉, 거래량, 거래대금, 관심도 데이터는 임의로 추정하지 말고 “추가 확인 필요”로 표시해 주세요.")
        lines.append("")
        lines.extend(self._news_section(selected_news))
        lines.append("")
        lines.extend(self._disclosure_section(selected_disclosures))
        lines.append("")
        lines.append("## 6. 주요 리스크 신호")
        lines.extend(self._risk_signals(selected_news=selected_news, selected_disclosures=selected_disclosures))
        lines.append("")
        lines.append("## 7. GPT 역할과 분석 요청")
        lines.append("당신은 실시간 데이터 기반의 주도주 선별 전문 주식 분석 어시스턴트입니다.")
        lines.append("")
        lines.append("아래 자료를 바탕으로 이 종목이 2주 이내 스윙투자 관점에서 적합한지 분석해 주세요.")
        lines.append("")
        lines.append("반드시 다음을 분석해 주세요.")
        lines.append("1. 산업군 및 핵심 테마 요약")
        lines.append("2. 최근 상승 또는 관심 요인")
        lines.append("3. 뉴스/공시 기반 단기 모멘텀")
        lines.append("4. 리스크 요인")
        lines.append("5. 눌림목 판단을 위해 추가 확인해야 할 시세 데이터")
        lines.append("6. 내일 또는 단기 상승 가능성 분석")
        lines.append("7. 상승 확률 0~100% 추정")
        lines.append("8. 확률 추정의 신뢰도: 낮음 / 중간 / 높음")
        lines.append("9. 추가 확인이 필요한 데이터")
        lines.append("")
        lines.append("중요:")
        lines.append("상승 확률은 제공된 근거를 바탕으로 한 정성적 추정치이며, 실제 통계 모델의 예측값이 아닙니다.")
        lines.append("시세, 수급, 거래대금 데이터가 제공되지 않은 경우 확률의 신뢰도를 낮게 표시해 주세요.")
        lines.append("자동 매수/매도 판단은 하지 마세요.")
        lines.append("최종 판단은 GPT Plus 자문과 사용자의 판단으로 해야 합니다.")
        lines.append("")
        lines.append("## 8. 출력 형식")
        lines.append("📌 종목명:")
        lines.append("📈 산업군 및 테마 요약:")
        lines.append("📰 최근 상승/관심 이유:")
        lines.append("📉 시세 흐름 판단:")
        lines.append("📊 수급 및 관심도 판단:")
        lines.append("⚠️ 리스크 요약:")
        lines.append("🔮 2주 스윙 관점 상승 가능성 및 확률:")
        lines.append("- 상승 가능성 추정:")
        lines.append("- 신뢰도:")
        lines.append("- 긍정 근거:")
        lines.append("- 부정 근거:")
        lines.append("- 부족한 데이터:")
        lines.append("✅ 최종 의견:")
        lines.append("- 매수/보유/관망 단정이 아니라, 추가 확인 후 판단해야 할 조건 중심으로 정리")
        lines.append("")
        return "\n".join(lines)

    def _build_long_term_markdown(self, stock, purpose: str, created_at: str, selected_news: list, selected_disclosures: list) -> str:
        lines: list[str] = []
        lines.append("# DrCT에셋 GPT 장기투자 자문 패키지")
        lines.append("")
        lines.append("## 1. 사용자 목표")
        lines.append("- 투자 유형: 장기투자")
        lines.append("- 목표: 기업의 중장기 성장성, 리스크, 산업 경쟁력 검토")
        lines.append(f"- 사용자가 입력한 검토 목적: {purpose.strip()}")
        lines.append("")
        lines.extend(self._common_target_section(stock, created_at))
        lines.append("")
        lines.append("## 3. 제공 데이터 범위")
        lines.append("### 포함된 데이터")
        lines.append("- 선택 뉴스 요약")
        lines.append("- 선택 공시 요약")
        lines.append("- AI 감성/중요도/태그")
        lines.append("- 공시 이벤트/리스크")
        lines.append("")
        lines.append("### 추가로 확인하면 좋은 데이터")
        lines.append("- 최근 3년 매출/영업이익/순이익")
        lines.append("- 부채비율")
        lines.append("- 현금흐름")
        lines.append("- PER/PBR/ROE")
        lines.append("- 배당성향")
        lines.append("- 시장점유율")
        lines.append("- 경쟁사 비교")
        lines.append("- 장기 산업 성장률")
        lines.append("")
        lines.extend(self._news_section(selected_news))
        lines.append("")
        lines.extend(self._disclosure_section(selected_disclosures))
        lines.append("")
        lines.append("## 6. 주요 리스크 신호")
        lines.extend(self._risk_signals(selected_news=selected_news, selected_disclosures=selected_disclosures))
        lines.append("")
        lines.append("## 7. GPT 역할과 분석 요청")
        lines.append("당신은 장기투자 관점의 기업 분석 전문 어시스턴트입니다.")
        lines.append("")
        lines.append("아래 자료를 바탕으로 이 종목이 장기투자 관점에서 적합한지 분석해 주세요.")
        lines.append("")
        lines.append("반드시 다음을 분석해 주세요.")
        lines.append("1. 산업의 중장기 성장성")
        lines.append("2. 기업의 경쟁력")
        lines.append("3. 최근 뉴스가 장기 투자 thesis에 주는 영향")
        lines.append("4. 공시 리스크가 지배구조 또는 주주가치에 미치는 영향")
        lines.append("5. 장기 보유 시 확인해야 할 핵심 지표")
        lines.append("6. 장기투자 매력도 0~100점")
        lines.append("7. 매력도 점수의 신뢰도: 낮음 / 중간 / 높음")
        lines.append("8. 분할매수 또는 관망이 필요한 조건")
        lines.append("")
        lines.append("중요:")
        lines.append("장기투자 매력도는 제공된 근거를 바탕으로 한 정성적 추정치이며, 실제 통계 모델의 예측값이 아닙니다.")
        lines.append("재무제표, 밸류에이션, 경쟁사 비교 데이터가 제공되지 않은 경우 점수의 신뢰도를 낮게 표시해 주세요.")
        lines.append("제공되지 않은 시세, 수급, 3분봉, 거래량 데이터는 임의로 추정하지 말고 추가 확인 필요로 표시해 주세요.")
        lines.append("자동 매수/매도 판단은 하지 마세요.")
        lines.append("최종 판단은 GPT Plus 자문과 사용자의 판단으로 해야 합니다.")
        lines.append("")
        lines.append("## 8. 출력 형식")
        lines.append("📌 종목명:")
        lines.append("🏭 산업 및 장기 성장성:")
        lines.append("💼 기업 경쟁력:")
        lines.append("📰 뉴스가 장기 투자 thesis에 주는 영향:")
        lines.append("📑 공시 리스크:")
        lines.append("📊 추가 확인해야 할 재무/밸류에이션 지표:")
        lines.append("🔮 장기투자 매력도:")
        lines.append("- 매력도 점수:")
        lines.append("- 신뢰도:")
        lines.append("- 긍정 근거:")
        lines.append("- 부정 근거:")
        lines.append("- 부족한 데이터:")
        lines.append("✅ 최종 의견:")
        lines.append("- 매수/보유/관망 단정이 아니라, 장기투자 판단 전에 확인할 조건 중심으로 정리")
        lines.append("")
        return "\n".join(lines)

    def _common_target_section(self, stock, created_at: str) -> list[str]:
        return [
            "## 2. 분석 대상",
            f"- 종목명: {stock.stock_name}",
            f"- 종목코드: {stock.stock_code}",
            f"- 시장: {stock.market or '-'}",
            f"- 섹터: {stock.sector or '-'}",
            f"- 산업: {stock.industry or '-'}",
            f"- 생성일시: {created_at}",
        ]

    def _news_section(self, selected_news: list) -> list[str]:
        lines: list[str] = ["## 4. 선택 뉴스 요약"]
        if not selected_news:
            lines.append("- 선택된 뉴스가 없습니다.")
            return lines
        for item in selected_news:
            ai_summary = item.ai_summary.strip() if item.ai_summary else "AI 요약 미처리"
            tags = item.ai_tags.strip() if item.ai_tags else "미분류"
            lines.append(f"### 뉴스 #{item.id}")
            lines.append(f"- 제목: {item.title}")
            lines.append(f"- 출처: {item.source or '-'}")
            lines.append(f"- 발행일: {item.published_at or '-'}")
            lines.append(f"- 중요도: {item.ai_importance_score if item.ai_importance_score is not None else item.importance_score}")
            lines.append(f"- 감성: {item.ai_sentiment or item.sentiment or 'neutral'}")
            lines.append(f"- 태그: {tags}")
            lines.append(f"- AI 요약: {ai_summary}")
            lines.append(f"- URL: {item.url or '-'}")
            if item.ai_summary_error:
                lines.append(f"- 요약 오류: {item.ai_summary_error}")
            lines.append("")
        return lines

    def _disclosure_section(self, selected_disclosures: list) -> list[str]:
        lines: list[str] = ["## 5. 선택 공시 요약"]
        if not selected_disclosures:
            lines.append("- 선택된 공시가 없습니다.")
            return lines
        for item in selected_disclosures:
            ai_summary = item.ai_summary.strip() if item.ai_summary else "AI 요약 미처리"
            tags = item.ai_tags.strip() if item.ai_tags else "미분류"
            raw_risk = (item.ai_risk_level or "unknown").lower()
            risk_text = "미분류 / 규칙 확인 필요" if raw_risk == "unknown" else raw_risk
            lines.append(f"### 공시 #{item.id}")
            lines.append(f"- 공시 제목: {item.disclosure_title}")
            lines.append(f"- 공시 유형: {item.disclosure_type or '-'}")
            lines.append(f"- 공시일: {item.disclosed_at or '-'}")
            lines.append(f"- 이벤트 유형: {item.ai_event_type or '기타'}")
            lines.append(f"- 리스크 수준: {risk_text}")
            lines.append(f"- 중요도: {item.ai_importance_score if item.ai_importance_score is not None else item.importance_score}")
            lines.append(f"- 태그: {tags}")
            lines.append(f"- AI 요약: {ai_summary}")
            lines.append(f"- URL: {item.url or '-'}")
            if item.ai_summary_error:
                lines.append(f"- 요약 오류: {item.ai_summary_error}")
            lines.append("")
        return lines

    def _risk_signals(self, selected_news: list, selected_disclosures: list) -> list[str]:
        high_risk_disclosures = [d for d in selected_disclosures if (d.ai_risk_level or "").lower() == "high"]
        negative_news = [n for n in selected_news if (n.ai_sentiment or n.sentiment or "").lower() == "negative"]
        high_importance_news = [
            n for n in selected_news if (n.ai_importance_score if n.ai_importance_score is not None else n.importance_score) >= 80
        ]
        high_importance_disclosures = [
            d
            for d in selected_disclosures
            if (d.ai_importance_score if d.ai_importance_score is not None else d.importance_score) >= 80
        ]
        unknown_risk = [d for d in selected_disclosures if (d.ai_risk_level or "unknown").lower() == "unknown"]
        summary_errors = [n for n in selected_news if n.ai_summary_error] + [d for d in selected_disclosures if d.ai_summary_error]
        lines: list[str] = []
        lines.append(
            f"- high risk 공시: {len(high_risk_disclosures)}건"
            + (f" (ID: {', '.join(str(d.id) for d in high_risk_disclosures)})" if high_risk_disclosures else "")
        )
        lines.append(
            f"- negative 뉴스: {len(negative_news)}건"
            + (f" (ID: {', '.join(str(n.id) for n in negative_news)})" if negative_news else "")
        )
        high_importance_ids = [str(n.id) for n in high_importance_news] + [str(d.id) for d in high_importance_disclosures]
        lines.append(
            f"- 중요도 80 이상 항목: {len(high_importance_ids)}건"
            + (f" (ID: {', '.join(high_importance_ids)})" if high_importance_ids else "")
        )
        lines.append(
            f"- ai_risk_level unknown 항목: {len(unknown_risk)}건"
            + (f" (ID: {', '.join(str(d.id) for d in unknown_risk)})" if unknown_risk else "")
        )
        lines.append(
            f"- ai_summary_error가 있는 항목: {len(summary_errors)}건"
            + (f" (ID: {', '.join(str(x.id) for x in summary_errors)})" if summary_errors else "")
        )
        return lines
