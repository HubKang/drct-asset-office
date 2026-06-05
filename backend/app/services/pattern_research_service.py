from __future__ import annotations

import csv
import io
import json
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.repositories.analysis_indicator_repository import AnalysisIndicatorRepository
from backend.app.repositories.pattern_research_repository import PatternResearchRepository
from backend.app.schemas.pattern_research_schema import PatternResearchRunRequest
from backend.app.services.analysis_indicator_service import AnalysisIndicatorService
from backend.app.services.pattern_goal_gpt_result_service import PatternGoalGptResultService
from backend.app.services.pattern_goal_llm_service import PatternGoalLLMService, split_goal_text_into_sentences
from backend.app.services.pattern_goal_parser import PatternGoalParser
from backend.app.services.pattern_research_engine import DynamicIndicatorExecutionError, build_pattern_samples


INDICATORS: list[dict[str, Any]] = [
    {"indicator_key": "open_price", "indicator_name": "시가", "description": "일봉 시가", "source_type": "db_column", "source_table": "stock_daily_prices", "source_column": "open_price", "calculation_type": "none", "data_type": "number", "unit": "원", "category": "가격", "status": "available"},
    {"indicator_key": "high_price", "indicator_name": "고가", "description": "일봉 고가", "source_type": "db_column", "source_table": "stock_daily_prices", "source_column": "high_price", "calculation_type": "none", "data_type": "number", "unit": "원", "category": "가격", "status": "available"},
    {"indicator_key": "low_price", "indicator_name": "저가", "description": "일봉 저가", "source_type": "db_column", "source_table": "stock_daily_prices", "source_column": "low_price", "calculation_type": "none", "data_type": "number", "unit": "원", "category": "가격", "status": "available"},
    {"indicator_key": "close_price", "indicator_name": "종가", "description": "일봉 종가", "source_type": "db_column", "source_table": "stock_daily_prices", "source_column": "close_price", "calculation_type": "none", "data_type": "number", "unit": "원", "category": "가격", "status": "available"},
    {"indicator_key": "volume", "indicator_name": "거래량", "description": "일봉 거래량", "source_type": "db_column", "source_table": "stock_daily_prices", "source_column": "volume", "calculation_type": "none", "data_type": "number", "unit": "주", "category": "거래", "status": "available"},
    {"indicator_key": "trading_value", "indicator_name": "거래대금", "description": "일봉 거래대금", "source_type": "db_column", "source_table": "stock_daily_prices", "source_column": "trading_value", "calculation_type": "none", "data_type": "number", "unit": "원", "category": "거래", "status": "available"},
]
for period in (5, 10, 20, 60, 120):
    INDICATORS.append({"indicator_key": f"ma{period}", "indicator_name": f"{period}일 이동평균", "description": f"종가 기준 {period}일 단순 이동평균", "source_type": "calculated", "source_table": "stock_daily_prices", "source_column": "close_price", "calculation_type": "moving_average", "data_type": "number", "unit": "원", "category": "추세", "status": "calculable"})
INDICATORS.extend(
    [
        {"indicator_key": "close_vs_ma20_pct", "indicator_name": "20일선 이격률", "description": "종가와 20일 이동평균의 거리", "source_type": "calculated", "calculation_type": "distance_pct", "data_type": "number", "unit": "%", "category": "추세", "status": "calculable"},
        {"indicator_key": "close_vs_ma60_pct", "indicator_name": "60일선 이격률", "description": "종가와 60일 이동평균의 거리", "source_type": "calculated", "calculation_type": "distance_pct", "data_type": "number", "unit": "%", "category": "추세", "status": "calculable"},
        {"indicator_key": "volume_ratio_20", "indicator_name": "거래량 20일 평균 배수", "description": "당일 거래량이 20일 평균의 몇 배인지", "source_type": "calculated", "calculation_type": "ratio_to_average", "data_type": "number", "unit": "배", "category": "거래", "status": "calculable"},
        {"indicator_key": "trading_value_ratio_20", "indicator_name": "거래대금 20일 평균 배수", "description": "당일 거래대금이 20일 평균의 몇 배인지", "source_type": "calculated", "calculation_type": "ratio_to_average", "data_type": "number", "unit": "배", "category": "거래", "status": "calculable"},
        {"indicator_key": "recent_3d_return", "indicator_name": "최근 3일 수익률", "description": "최근 3거래일 종가 수익률", "source_type": "calculated", "calculation_type": "return_pct", "data_type": "number", "unit": "%", "category": "수익률", "status": "calculable"},
        {"indicator_key": "recent_5d_return", "indicator_name": "최근 5일 수익률", "description": "최근 5거래일 종가 수익률", "source_type": "calculated", "calculation_type": "return_pct", "data_type": "number", "unit": "%", "category": "수익률", "status": "calculable"},
        {"indicator_key": "is_bullish", "indicator_name": "양봉 여부", "description": "종가가 시가 이상인지", "source_type": "calculated", "calculation_type": "boolean", "data_type": "boolean", "unit": None, "category": "캔들", "status": "calculable"},
        {"indicator_key": "close_above_previous_high", "indicator_name": "전일 고가 돌파", "description": "종가가 전일 고가를 돌파했는지", "source_type": "calculated", "calculation_type": "boolean", "data_type": "boolean", "unit": None, "category": "캔들", "status": "calculable"},
    ]
)


class PatternResearchService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = PatternResearchRepository(db)
        self.parser = PatternGoalParser()

    def list_indicators(self) -> dict[str, Any]:
        return {"items": INDICATORS}

    def list_stocks(self, keyword: str | None, limit: int) -> dict[str, Any]:
        return {"items": self.repo.list_stocks(keyword=keyword, limit=limit), "keyword": keyword, "limit": limit}

    def parse_goal(self, goal_text: str, use_llm: bool = False, llm_mode: str | None = "assist") -> dict[str, Any]:
        if not goal_text.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="찾고 싶은 매매패턴을 자연어로 입력해 주세요.")
        parsed = self.parser.parse(goal_text)
        self._merge_db_reference_matches(goal_text, parsed)
        self._apply_display_labels(parsed)
        parsed_goal = parsed.get("parsed_goal") or {}
        parsed_goal.setdefault(
            "rule_base_result",
            {
                "success_criteria": parsed_goal.get("success_criteria"),
                "failure_criteria": parsed_goal.get("failure_criteria"),
                "entry_filters": parsed_goal.get("entry_filters") or [],
                "exclude_filters": parsed_goal.get("exclude_filters") or [],
            },
        )
        parsed_goal.setdefault("confirmed_conditions", [])
        llm_assist = PatternGoalLLMService.skipped()
        if use_llm:
            catalog = AnalysisIndicatorService(self.db).llm_catalog()
            llm_assist = PatternGoalLLMService().assist(goal_text, parsed, catalog)
            parsed["parsed_goal"]["llm_assist_result"] = llm_assist
            if llm_assist.get("warnings"):
                parsed["warnings"] = list(dict.fromkeys([*(parsed.get("warnings") or []), *llm_assist.get("warnings", [])]))
        parsed["llm_assist"] = llm_assist
        return parsed

    def gpt_goal_parse_prompt(self, goal_text: str, parsed_goal: dict[str, Any] | None = None) -> dict[str, Any]:
        first_pass = {"parsed_goal": parsed_goal} if parsed_goal else self.parse_goal(goal_text, use_llm=False)
        first_pass = self._compact_goal_parse_context(first_pass)
        catalog = AnalysisIndicatorService(self.db).llm_catalog()
        indicator_summary = [
            {
                "indicator_key": item.get("indicator_key"),
                "indicator_name": item.get("indicator_name"),
                "source_type": item.get("source_type"),
                "usage": item.get("allowed_usage"),
                "unit": item.get("unit"),
                "available": item.get("availability"),
            }
            for item in catalog.get("indicators", [])
        ]
        indicator_summary = [item for item in indicator_summary if self._is_prompt_catalog_item_usable(item)]
        calculation_types = [
            "moving_average", "distance_pct", "ratio_to_previous", "ratio_to_average", "rolling_high", "rolling_low",
            "distance_to_rolling_high_pct", "distance_to_rolling_low_pct", "slope", "between_lines", "band_value",
            "band_touch", "cross_up", "cross_down", "candle_body_pct", "candle_range_pct",
        ]
        schema = {
            "conditions": {"success_criteria": [], "failure_criteria": [], "entry_filters": [], "exclude_filters": [], "reference_conditions": []},
            "new_indicator_candidates": [],
            "unsupported_items": [],
            "warnings": [],
            "interpretation_conflicts": [],
        }
        prompt = (
            "당신은 종목 추천자가 아니며 매수/매도 추천을 하지 않습니다. 자연어 매매목표를 DrCT 조건 후보 JSON으로만 해석합니다.\n"
            "반드시 JSON 객체만 반환하세요. 설명, markdown, 코드블록, 실행 가능한 formula 문자열은 반환하지 마세요.\n"
            "DrCT 1차 해석은 보조 해석입니다. 사용자 목표 원문과 충돌하면 사용자 목표 원문을 우선하고, 충돌 내용은 warnings 또는 interpretation_conflicts에 기록하세요.\n"
            "catalog에 없는 지표가 필요하면 조건에 억지로 넣지 말고 new_indicator_candidates에 제안하세요.\n"
            "신규 지표 후보는 calculation_type, required_indicators, parameters를 포함해야 하며 formula 문자열은 실행 대상으로 쓰지 않습니다.\n"
            "신규 지표 예시: {\"source_text\":\"5일선과 10일선 근처\",\"indicator_key\":\"ma5_vs_ma10_pct\",\"indicator_name\":\"5일선과 10일선 이격률\",\"calculation_type\":\"distance_pct\",\"required_indicators\":[\"ma5\",\"ma10\"],\"parameters\":{\"target_indicator\":\"ma5\",\"base_indicator\":\"ma10\",\"unit\":\"%\"},\"usage\":[\"entry_filter\",\"reference\"],\"lookahead_risk\":false,\"needs_user_review\":true}\n\n"
            "너는 종목 추천자가 아니다. 매수/매도 추천을 하지 말고 자연어 매매목표를 DrCT 조건 후보로만 해석한다.\n"
            "반드시 JSON 객체만 반환한다. 설명, markdown, 코드, 실행 가능한 formula는 금지한다.\n"
            "catalog에 없는 지표가 필요하면 조건에 억지로 넣지 말고 new_indicator_candidates에 제안한다.\n"
            "신규 지표는 calculation_type, required_indicators, parameters를 함께 제안한다.\n"
            "미래 결과 지표는 성공/실패 기준에만 사용하고 진입조건에는 사용하지 않는다.\n\n"
            f"[사용자 목표]\n{goal_text}\n\n"
            f"[문장 분리]\n{json.dumps(split_goal_text_into_sentences(goal_text), ensure_ascii=False, indent=2)}\n\n"
            f"[DrCT 1차 해석]\n{json.dumps(first_pass, ensure_ascii=False, indent=2)}\n\n"
            f"[사용 가능 지표 catalog 요약]\n{json.dumps(indicator_summary, ensure_ascii=False, indent=2)}\n\n"
            f"[지원/검토 대상 calculation_type]\n{json.dumps(calculation_types, ensure_ascii=False, indent=2)}\n\n"
            f"[반환 JSON schema]\n{json.dumps(schema, ensure_ascii=False, indent=2)}"
        )
        return {"prompt_text": prompt, "sentence_splits": split_goal_text_into_sentences(goal_text)}

    @staticmethod
    def _compact_goal_parse_context(first_pass: dict[str, Any]) -> dict[str, Any]:
        parsed_goal = first_pass.get("parsed_goal") or {}
        return {
            "parsed_goal": {
                "success_criteria": parsed_goal.get("success_criteria"),
                "failure_criteria": parsed_goal.get("failure_criteria"),
                "entry_filters": parsed_goal.get("entry_filters") or [],
                "exclude_filters": parsed_goal.get("exclude_filters") or [],
                "unsupported_items": parsed_goal.get("unsupported_items") or first_pass.get("unsupported_items") or [],
                "warnings": parsed_goal.get("warnings") or first_pass.get("warnings") or [],
            }
        }

    @staticmethod
    def _is_prompt_catalog_item_usable(item: dict[str, Any]) -> bool:
        key = str(item.get("indicator_key") or "").strip().lower()
        name = str(item.get("indicator_name") or "").strip()
        if not key or "codex_test" in key or "codex_50d_test" in key:
            return False
        if "�" in name or "???" in name:
            return False
        return True

    def validate_gpt_goal_result(self, goal_text: str, gpt_result_text: str, parsed_goal: dict[str, Any] | None) -> dict[str, Any]:
        return PatternGoalGptResultService(self.db).validate(goal_text, gpt_result_text, parsed_goal)

    @staticmethod
    def _json_loads(raw: Any, fallback: Any) -> Any:
        try:
            return json.loads(str(raw or ""))
        except (TypeError, json.JSONDecodeError):
            return fallback

    def _attach_registered_dynamic_indicators(self, parsed: dict[str, Any]) -> dict[str, Any]:
        parsed = dict(parsed or {})
        current = list(parsed.get("dynamic_indicators") or [])
        existing_keys = {str(item.get("indicator_key") or "") for item in current if isinstance(item, dict)}
        for row in AnalysisIndicatorRepository(self.db).list_indicators(active_only=True):
            calculation_type = str(row.get("calculation_type") or "").strip()
            indicator_key = str(row.get("indicator_key") or "").strip()
            if not indicator_key or not calculation_type:
                continue
            execution_supported = int(row.get("execution_supported") or (1 if calculation_type == "distance_pct" else 0)) == 1
            if not execution_supported and calculation_type != "distance_pct":
                continue
            if indicator_key in existing_keys:
                continue
            current.append(
                {
                    "indicator_key": indicator_key,
                    "indicator_name": row.get("indicator_name") or indicator_key,
                    "calculation_type": calculation_type,
                    "parameters": self._json_loads(row.get("parameters_json"), {}),
                    "required_indicators": self._json_loads(row.get("required_columns_json"), []),
                    "execution_supported": execution_supported,
                    "execution_status": row.get("execution_status") or ("supported" if execution_supported else "needs_engine"),
                    "execution_message": row.get("execution_message"),
                    "scope": "registered",
                }
            )
            existing_keys.add(indicator_key)
        parsed["dynamic_indicators"] = current
        return parsed

    def create_run(self, payload: PatternResearchRunRequest) -> dict[str, Any]:
        stock_code = payload.stock_codes[0]
        stock = self.repo.get_stock_by_code(stock_code)
        if not stock:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="분석할 종목을 찾을 수 없습니다.")
        source = self.repo.resolve_price_source(int(stock["stock_id"]))
        rows = self.repo.list_prices(int(stock["stock_id"]), source, end_date=payload.end_date)
        if len(rows) < 30:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="가격 데이터가 부족합니다.")
        parsed = payload.parsed_goal or self.parse_goal(payload.goal_text)["parsed_goal"]
        parsed = self._attach_registered_dynamic_indicators(parsed)
        success_criteria = parsed.get("success_criteria") or parsed.get("success_rule") or {}
        failure_criteria = parsed.get("failure_criteria") or parsed.get("failure_rule") or {}
        target_return_pct = float(success_criteria.get("target_return_pct") or parsed.get("target_return_pct") or 5)
        target_days = int(success_criteria.get("target_days") or parsed.get("target_days") or 5)
        stop_loss_pct = float(failure_criteria.get("stop_loss_pct") or parsed.get("stop_loss_pct") or -5)
        try:
            samples, summary = build_pattern_samples(
                rows,
                stock,
                payload.start_date,
                payload.end_date,
                target_return_pct,
                target_days,
                stop_loss_pct,
                parsed_goal=parsed,
            )
        except DynamicIndicatorExecutionError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.detail) from exc
        if not samples:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="성공/실패 샘플 수가 적습니다. 기간 또는 조건을 조정해 보세요.")
        gpt_prompt = self._build_gpt_prompt(payload.goal_text, stock, payload.start_date, payload.end_date, parsed, summary, samples)
        run_id = self.repo.create_run_with_samples(
            run_values={
                "research_name": payload.research_name or f"{stock.get('stock_name') or stock_code} 패턴 연구",
                "stock_codes": payload.stock_codes,
                "start_date": payload.start_date,
                "end_date": payload.end_date,
                "goal_text": payload.goal_text,
                "target_return_pct": target_return_pct,
                "target_days": target_days,
                "stop_loss_pct": stop_loss_pct,
                "max_holding_days": int(parsed.get("max_holding_days") or target_days),
            },
            parsed_goal=parsed,
            summary=summary,
            gpt_prompt_text=gpt_prompt,
            samples=samples,
        )
        return {"run_id": run_id, "summary": summary}

    def list_runs(self, limit: int) -> dict[str, Any]:
        return {"items": self.repo.list_runs(limit=limit)}

    def get_run(self, run_id: int) -> dict[str, Any]:
        run = self.repo.get_run(run_id)
        if not run:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="연구 실행 결과를 찾을 수 없습니다.")
        return run

    def list_samples(self, run_id: int, label: str | None) -> dict[str, Any]:
        self.get_run(run_id)
        return {"items": self.repo.list_samples(run_id, label=label)}

    def gpt_package(self, run_id: int) -> dict[str, Any]:
        run = self.get_run(run_id)
        summary = run.get("summary") or {}
        return {
            "gpt_prompt_text": run.get("gpt_prompt_text") or "",
            "summary": summary,
            "sample_counts": {
                "SUCCESS": int(summary.get("success_count") or 0),
                "FAILURE": int(summary.get("failure_count") or 0),
                "NEUTRAL": int(summary.get("neutral_count") or 0),
            },
        }

    def csv_text(self, run_id: int) -> str:
        self.get_run(run_id)
        samples = self.repo.list_samples(run_id, limit=10000)
        output = io.StringIO()
        fieldnames = ["stock_code", "stock_name", "trade_date", "entry_price", "max_future_return_pct", "min_future_return_pct", "future_return_pct", "target_hit", "stop_hit", "result_label"]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for sample in samples:
            writer.writerow({key: sample.get(key) for key in fieldnames})
        return output.getvalue()

    def _build_gpt_prompt(self, goal_text: str, stock: dict[str, Any], start_date: str, end_date: str, parsed: dict[str, Any], summary: dict[str, Any], samples: list[dict[str, Any]]) -> str:
        success_examples = self._compact_sample_examples([s for s in samples if s["result_label"] == "SUCCESS"][:5], summary)
        failure_examples = self._compact_sample_examples([s for s in samples if s["result_label"] == "FAILURE"][:5], summary)
        return f"""[역할]
당신은 종목 추천자가 아니라 데이터 기반 매매패턴 연구 보조자입니다.
실제 매수/매도 추천을 하지 마세요.
아래 데이터는 DrCT가 과거 가격 데이터로 성공/실패 샘플을 정량 분류한 결과입니다.
GPT의 역할은 성공/실패 차이를 해석하고, 검증 가능한 매매패턴 후보와 체크리스트를 제안하는 것입니다.

[사용자 매매목표]
{goal_text}

[분석 대상]
- 종목: {stock.get('stock_name')}({stock.get('stock_code')})
- 기간: {start_date} ~ {end_date}

[사용자 자연어에서 추출된 조건/지표 후보]
{self._extracted_indicator_text(parsed, summary)}

[실제 샘플 생성에 적용한 조건]
{self._applied_conditions_text(summary)}

[조건 후보]
{self._candidate_conditions_text(summary)}

[샘플 관찰 지표]
{self._observation_indicator_text(summary)}

[샘플 요약]
- 전체 후보일: {summary.get('total_samples')}
- 성공 샘플: {summary.get('success_count')}
- 실패 샘플: {summary.get('failure_count')}
- 성공률: {summary.get('success_rate')}%

[성공/실패 평균 비교]
{self._metric_comparison_text(summary)}

[조건 후보별 성과]
{self._condition_performance_text(summary)}

[성공 샘플 예시]
{json.dumps(success_examples, ensure_ascii=False, indent=2)}

[실패 샘플 예시]
{json.dumps(failure_examples, ensure_ascii=False, indent=2)}

[분석 요청]
아래 항목을 반드시 포함해 주세요.
1. 현재 성공률의 의미를 평가해 주세요.
2. 성공 샘플과 실패 샘플의 가장 큰 차이 3가지를 정리해 주세요.
3. 실패 샘플에서 과열 진입, 추격 진입, 조건 미충족 진입 가능성이 있는지 분석해 주세요.
4. 사용자 자연어에서 추출된 신규 지표 후보가 실제로 유효한지 평가해 주세요.
5. 샘플 관찰 지표 중 성공/실패를 가장 잘 구분하는 지표를 찾아 주세요.
6. 현재 샘플 적용 조건 중 유지/완화/강화할 조건을 제안해 주세요.
7. 조건 후보 중 샘플 적용 조건으로 승격할 만한 것이 있는지 제안해 주세요.
8. 성공 가능성이 높은 패턴 후보 2~3개를 제안해 주세요.
9. 각 패턴 후보를 DrCT 조건식으로 다시 정리해 주세요.
10. 실패/진입 금지 패턴을 정리해 주세요.
11. 매매훈련용 체크리스트를 만들어 주세요.
12. 과최적화 위험과 추가 검증 필요사항을 알려 주세요.
"""

    @staticmethod
    def _condition_table_text(parsed: dict[str, Any]) -> str:
        lines: list[str] = []
        success = parsed.get("success_criteria") or parsed.get("success_rule") or {}
        failure = parsed.get("failure_criteria") or parsed.get("failure_rule") or {}
        lines.append(f"성공 기준: 원문={success.get('source_text', '-')}, 수식={success.get('expression', '-')}, 출처={success.get('source', 'rule_base')}")
        lines.append(f"실패 기준: 원문={failure.get('source_text', '-')}, 수식={failure.get('expression', '-')}, 출처={failure.get('source', 'rule_base')}")
        lines.append("진입 후보 조건:")
        for item in parsed.get("entry_filters") or []:
            lines.append(f"- {item.get('label')} / {item.get('expression')} / {PatternResearchService._apply_mode_label(item)} / {item.get('source', '-')}")
        lines.append("제외 조건:")
        for item in parsed.get("exclude_filters") or []:
            lines.append(f"- {item.get('label')} / {item.get('expression')} / {PatternResearchService._apply_mode_label(item)} / {item.get('source', '-')}")
        return "\n".join(lines)

    @staticmethod
    def _extracted_indicator_text(parsed: dict[str, Any], summary: dict[str, Any]) -> str:
        lines: list[str] = []
        for item in parsed.get("temporary_indicators") or []:
            params = item.get("parameters") or {}
            lines.append(
                f"- 추출 지표: {item.get('indicator_key')} / 상태=신규 지표 후보·1회성 사용·샘플 관찰 지표 / "
                f"calculation_type={item.get('calculation_type')} / parameters=target:{params.get('target_indicator')}, base:{params.get('base_indicator')}"
            )
        for item in summary.get("dynamic_indicators") or []:
            key = item.get("indicator_key")
            if not key:
                continue
            if any(key in line for line in lines):
                continue
            params = item.get("parameters") or {}
            lines.append(
                f"- 추출 지표: {key} / 상태=동적 계산 지표 / calculation_type={item.get('calculation_type')} / "
                f"parameters=target:{params.get('target_indicator')}, base:{params.get('base_indicator')}"
            )
        return "\n".join(lines) if lines else "- 신규 지표 후보 없음"

    @staticmethod
    def _format_condition(item: dict[str, Any]) -> str:
        if not item:
            return "- 없음"
        label = item.get("label") or item.get("source_text") or item.get("natural_text") or "-"
        indicator = item.get("indicator_key") or item.get("indicator")
        expression = item.get("expression") or (f"{indicator} {item.get('operator')} {item.get('value')}" if indicator else "-")
        return f"- {label}: {expression}"

    @staticmethod
    def _applied_conditions_text(summary: dict[str, Any]) -> str:
        lines = ["성공 기준:", PatternResearchService._format_condition(summary.get("applied_success_criteria") or {})]
        lines.extend(["실패 기준:", PatternResearchService._format_condition(summary.get("applied_failure_criteria") or {})])
        lines.append("진입 필터:")
        applied_entries = summary.get("applied_entry_filters") or []
        lines.extend(PatternResearchService._format_condition(item) for item in applied_entries) if applied_entries else lines.append("- 없음")
        lines.append("제외 필터:")
        applied_excludes = summary.get("applied_exclude_filters") or []
        lines.extend(PatternResearchService._format_condition(item) for item in applied_excludes) if applied_excludes else lines.append("- 없음")
        return "\n".join(lines)

    @staticmethod
    def _candidate_conditions_text(summary: dict[str, Any]) -> str:
        candidates = summary.get("reference_entry_filters") or []
        if not candidates:
            return "- 조건 후보 없음"
        return "\n".join(PatternResearchService._format_condition(item) for item in candidates)

    @staticmethod
    def _observation_indicator_text(summary: dict[str, Any]) -> str:
        indicators = summary.get("observation_indicators") or []
        if not indicators:
            return "- 샘플 관찰 지표가 없습니다. 기본 관찰 지표를 사용합니다."
        return "\n".join(f"- {key}" for key in indicators)

    @staticmethod
    def _metric_comparison_text(summary: dict[str, Any]) -> str:
        keys = summary.get("observation_indicators") or sorted(set(summary.get("avg_success") or {}) | set(summary.get("avg_failure") or {}))
        rows = ["| 지표 | 성공 평균/비율 | 실패 평균/비율 | 차이 |", "|---|---:|---:|---:|"]
        for key in keys:
            rows.append(f"| {key} | {(summary.get('avg_success') or {}).get(key)} | {(summary.get('avg_failure') or {}).get(key)} | {(summary.get('differences') or {}).get(key)} |")
        return "\n".join(rows)

    @staticmethod
    def _condition_performance_text(summary: dict[str, Any]) -> str:
        rows = summary.get("condition_candidate_performance") or []
        if not rows:
            return "- 조건 후보별 성과 없음"
        lines = ["| 조건명 | 조건식 | 통과 샘플 | 성공 | 실패 | 성공률 | 기본 대비 |", "|---|---|---:|---:|---:|---:|---:|"]
        for row in rows:
            lines.append(
                f"| {row.get('condition_label') or '-'} | {row.get('expression') or '-'} | {row.get('passed_count')} | "
                f"{row.get('success_count')} | {row.get('failure_count')} | {row.get('success_rate')} | {row.get('lift_vs_base')} |"
            )
        return "\n".join(lines)

    @staticmethod
    def _compact_sample_examples(samples: list[dict[str, Any]], summary: dict[str, Any]) -> list[dict[str, Any]]:
        feature_keys = [
            "close_vs_ma20_pct",
            "close_vs_ma60_pct",
            "ma5_vs_ma10_pct",
            "volume_ratio_20",
            "trading_value_ratio_20",
            "recent_3d_return",
            "recent_5d_return",
            "is_bullish",
            "close_above_previous_high",
            "matched_conditions",
            "failed_conditions",
        ]
        observation = [key for key in (summary.get("observation_indicators") or []) if key not in feature_keys]
        keys = feature_keys + observation[:4]
        compact: list[dict[str, Any]] = []
        for sample in samples:
            features = sample.get("features") or {}
            compact.append(
                {
                    "trade_date": sample.get("trade_date"),
                    "entry_price": sample.get("entry_price"),
                    "max_future_return_pct": sample.get("max_future_return_pct"),
                    "min_future_return_pct": sample.get("min_future_return_pct"),
                    "future_return_pct": sample.get("future_return_pct"),
                    "result_label": sample.get("result_label"),
                    "features": {key: features.get(key) for key in keys if key in features},
                    "pattern_tags": sample.get("pattern_tags") or [],
                }
            )
        return compact

    @staticmethod
    def _interpretation_status_label(status_value: Any) -> str:
        status_text = str(status_value or "")
        if status_text in {"applied", "confirmed", "sample_applied"}:
            return "확정"
        if status_text in {"calculated", "calculable", "calculatable", "available"}:
            return "계산 가능"
        if status_text == "needs_review":
            return "확인 필요"
        if status_text == "unsupported":
            return "미지원"
        if status_text == "error":
            return "오류"
        return status_text or "-"

    @staticmethod
    def _apply_mode_label(item: dict[str, Any]) -> str:
        if item.get("status") == "unsupported":
            return "미적용"
        return "샘플 필터 적용" if item.get("apply_to_samples") else "조건 후보"

    def _merge_db_reference_matches(self, goal_text: str, parsed: dict[str, Any]) -> None:
        repo = AnalysisIndicatorRepository(self.db)
        parsed_goal = parsed.get("parsed_goal") or {}
        entry_filters = list(parsed_goal.get("entry_filters") or [])
        exclude_filters = list(parsed_goal.get("exclude_filters") or [])
        interpreted_items = list(parsed.get("interpreted_items") or [])
        indicator_candidates = list(parsed_goal.get("indicator_candidates") or [])

        def json_value(raw: Any) -> Any:
            try:
                return json.loads(str(raw)) if raw not in (None, "") else None
            except (TypeError, json.JSONDecodeError):
                return raw

        def add_indicator(key: str | None) -> None:
            if key and key not in indicator_candidates:
                indicator_candidates.append(key)

        def expression_for(indicator_key: str, operator: str | None, value: Any) -> str:
            if operator == "between" and isinstance(value, list) and len(value) == 2:
                return f"{value[0]} <= {indicator_key} <= {value[1]}"
            rendered = str(value).lower() if isinstance(value, bool) else value
            return f"{indicator_key} {operator or '='} {rendered}".strip()

        def merge_condition(condition: dict[str, Any], category: str) -> None:
            target = exclude_filters if category == "exclude_filter" else entry_filters
            for existing in target:
                if (
                    (existing.get("indicator_key") or existing.get("indicator")) == condition.get("indicator_key")
                    and existing.get("operator") == condition.get("operator")
                    and existing.get("value") == condition.get("value")
                ):
                    if condition.get("source") == "db_alias" and "db_alias" not in str(existing.get("source", "")):
                        existing["source"] = f"{existing.get('source', 'rule_base')}+db_alias"
                    return
            target.append(condition)

        compact_goal_text = goal_text.replace(" ", "")
        for alias in repo.list_aliases(active_only=True):
            alias_text = str(alias.get("alias_text") or "")
            if not alias_text or (alias_text not in goal_text and alias_text.replace(" ", "") not in compact_goal_text):
                continue
            indicator_key = str(alias.get("indicator_key") or "")
            operator = alias.get("default_operator") or "="
            value = json_value(alias.get("default_value_json"))
            category = str(alias.get("default_category") or "entry_filter")
            condition = {
                "source_text": alias_text,
                "natural_text": alias_text,
                "label": alias_text,
                "indicator": indicator_key,
                "indicator_key": indicator_key,
                "operator": operator,
                "value": value,
                "expression": expression_for(indicator_key, operator, value),
                "apply_to_samples": bool(alias.get("apply_to_samples_default")),
                "status": "needs_review" if alias.get("needs_review") else "applied",
                "source": "db_alias",
                "alias_id": alias.get("id"),
            }
            if category == "exclude_filter":
                condition["exclude_when_true"] = True
            if category in ("entry_filter", "exclude_filter"):
                merge_condition(condition, category)
            interpreted_items.append({"category": category, "natural_text": alias_text, "expression": condition["expression"], "indicator_key": indicator_key, "status": condition["status"], "source": "db_alias"})
            add_indicator(indicator_key)

        parsed_goal["entry_filters"] = entry_filters
        parsed_goal["exclude_filters"] = exclude_filters
        parsed_goal["hypothesis_conditions"] = entry_filters + exclude_filters
        parsed_goal["indicator_candidates"] = indicator_candidates
        parsed_goal["interpretation_sources"] = sorted({item.get("source") for item in interpreted_items if item.get("source")})
        parsed["interpreted_items"] = interpreted_items
        parsed["entry_filters"] = entry_filters
        parsed["exclude_filters"] = exclude_filters
        parsed["needs_review_items"] = [item for item in entry_filters + exclude_filters if item.get("status") == "needs_review"]

    def _apply_display_labels(self, parsed: dict[str, Any]) -> None:
        parsed_goal = parsed.get("parsed_goal") or {}
        for key in ("success_criteria", "failure_criteria", "success_rule", "failure_rule"):
            item = parsed_goal.get(key)
            if isinstance(item, dict):
                item["interpretation_status_label"] = self._interpretation_status_label(item.get("status", "applied"))
                item["apply_mode_label"] = "항상 적용"
        for item in (parsed_goal.get("entry_filters") or []) + (parsed_goal.get("exclude_filters") or []):
            item["interpretation_status_label"] = self._interpretation_status_label(item.get("status"))
            item["apply_mode_label"] = self._apply_mode_label(item)
        for item in parsed.get("interpreted_items") or []:
            item["interpretation_status_label"] = self._interpretation_status_label(item.get("status"))

    @staticmethod
    def _llm_confirmed_text(parsed: dict[str, Any]) -> str:
        confirmed = [
            item for item in (parsed.get("confirmed_conditions") or [])
            if item.get("original_source") in {"llm_candidate", "gpt_candidate"} or item.get("source") in {"llm_candidate_confirmed", "gpt_candidate_confirmed", "user_modified"}
        ]
        if not confirmed:
            return "- 사용자가 최종 반영한 LLM/GPT 후보 조건이 없습니다."
        return "\n".join(
            f"- {item.get('label') or item.get('source_text')} / {item.get('expression')} / {PatternResearchService._apply_mode_label(item)} / source={item.get('source') or '-'}"
            for item in confirmed
        )
